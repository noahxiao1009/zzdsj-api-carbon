"""
Docker服务管理器
Docker Service Manager for MCP Services
"""

import asyncio
import docker
import json
import logging
import ipaddress
from typing import Dict, List, Optional, Any
from datetime import datetime

from ..models.mcp_models import MCPServiceConfig, MCPNetworkConfig, MCPContainerStats

logger = logging.getLogger(__name__)

class DockerService:
    """Docker服务管理器"""
    
    def __init__(self):
        try:
            self.client = docker.from_env()
            self.client.ping()  # 测试连接
        except Exception as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            self.client = None
        
        # 配置
        self.mcp_network_prefix = "mcp-vlan"
        self.mcp_container_prefix = "mcp-service"
        self.default_vlan_subnet = "172.20.0.0/16"
        self.default_vlan_gateway = "172.20.0.1"
        
        # 端口分配管理
        self.allocated_ports = set()
        self.port_range = (9000, 9999)
    
    async def deploy_mcp_container(self, service_id: str, service_config: MCPServiceConfig) -> Dict[str, Any]:
        """部署MCP服务容器"""
        try:
            if not self.client:
                raise Exception("Docker client not available")
            
            # 1. 确保VLAN网络存在
            network = await self._ensure_vlan_network(service_config.vlan_id or 100)
            
            # 2. 分配端口
            host_port = await self._allocate_port()
            
            # 3. 构建容器配置
            container_config = self._build_container_config(
                service_id, service_config, network, host_port
            )
            
            # 4. 创建并启动容器
            container = self.client.containers.run(
                detach=True,
                **container_config
            )
            
            # 5. 等待容器启动
            await self._wait_for_container_ready(container, timeout=60)
            
            # 6. 获取容器网络信息
            container.reload()
            network_info = await self._get_container_network_info(container, network)
            
            # 7. 构建返回信息
            deployment_info = {
                "container_id": container.id,
                "container_name": container.name,
                "image_name": service_config.image_name,
                "network_id": network.id,
                "network_name": network.name,
                "ip_address": network_info.get("ip_address"),
                "host_port": host_port,
                "container_port": service_config.port,
                "service_url": f"http://{network_info.get('ip_address')}:{service_config.port}",
                "external_url": f"http://localhost:{host_port}",
                "vlan_id": service_config.vlan_id or 100,
                "status": "running",
                "deployed_at": datetime.now().isoformat()
            }
            
            logger.info(f"Successfully deployed MCP container: {service_config.name}")
            return deployment_info
            
        except Exception as e:
            logger.error(f"Failed to deploy MCP container {service_id}: {e}")
            # 清理资源
            await self._cleanup_failed_deployment(service_id)
            raise
    
    async def start_container(self, service_id: str) -> bool:
        """启动容器"""
        try:
            container = await self._get_container_by_service_id(service_id)
            if not container:
                raise Exception(f"Container for service {service_id} not found")
            
            container.start()
            await self._wait_for_container_ready(container)
            
            logger.info(f"Successfully started container for service {service_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start container for service {service_id}: {e}")
            return False
    
    async def stop_container(self, service_id: str) -> bool:
        """停止容器"""
        try:
            container = await self._get_container_by_service_id(service_id)
            if not container:
                logger.warning(f"Container for service {service_id} not found")
                return True
            
            container.stop(timeout=30)
            
            logger.info(f"Successfully stopped container for service {service_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop container for service {service_id}: {e}")
            return False
    
    async def restart_container(self, service_id: str) -> bool:
        """重启容器"""
        try:
            container = await self._get_container_by_service_id(service_id)
            if not container:
                raise Exception(f"Container for service {service_id} not found")
            
            container.restart(timeout=30)
            await self._wait_for_container_ready(container)
            
            logger.info(f"Successfully restarted container for service {service_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restart container for service {service_id}: {e}")
            return False
    
    async def remove_container(self, service_id: str, force: bool = False) -> bool:
        """移除容器"""
        try:
            container = await self._get_container_by_service_id(service_id)
            if not container:
                logger.warning(f"Container for service {service_id} not found")
                return True
            
            # 停止容器
            if container.status == "running":
                container.stop(timeout=30 if not force else 5)
            
            # 移除容器
            container.remove(force=force)
            
            # 释放端口
            await self._release_port_for_service(service_id)
            
            logger.info(f"Successfully removed container for service {service_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove container for service {service_id}: {e}")
            return False
    
    async def get_container_logs(self, service_id: str, lines: int = 100, since: Optional[str] = None) -> List[str]:
        """获取容器日志"""
        try:
            container = await self._get_container_by_service_id(service_id)
            if not container:
                raise Exception(f"Container for service {service_id} not found")
            
            # 构建日志选项
            log_options = {
                "tail": lines,
                "timestamps": True
            }
            
            if since:
                log_options["since"] = since
            
            # 获取日志
            logs = container.logs(**log_options)
            
            # 解码并分割为行
            if isinstance(logs, bytes):
                logs = logs.decode('utf-8')
            
            log_lines = logs.split('\n')
            return [line for line in log_lines if line.strip()]
            
        except Exception as e:
            logger.error(f"Failed to get container logs for service {service_id}: {e}")
            return []
    
    async def get_container_stats(self, container_id: str) -> Optional[MCPContainerStats]:
        """获取容器统计信息"""
        try:
            container = self.client.containers.get(container_id)
            
            # 获取容器统计信息
            stats = container.stats(stream=False)
            
            # 解析统计信息
            cpu_usage = self._calculate_cpu_usage(stats)
            memory_usage = self._calculate_memory_usage(stats)
            network_usage = self._calculate_network_usage(stats)
            
            # 获取容器信息
            container.reload()
            
            return MCPContainerStats(
                container_id=container.id,
                container_name=container.name,
                status=container.status,
                cpu_usage_percent=cpu_usage,
                memory_usage_mb=memory_usage["usage_mb"],
                memory_limit_mb=memory_usage["limit_mb"],
                network_rx_bytes=network_usage["rx_bytes"],
                network_tx_bytes=network_usage["tx_bytes"],
                uptime_seconds=self._calculate_uptime(container),
                created_at=datetime.fromisoformat(container.attrs["Created"].replace("Z", "+00:00"))
            )
            
        except Exception as e:
            logger.error(f"Failed to get container stats {container_id}: {e}")
            return None
    
    async def get_containers_stats(self, running_only: bool = True) -> List[MCPContainerStats]:
        """获取所有MCP容器统计信息"""
        try:
            # 获取所有MCP容器
            containers = self.client.containers.list(
                all=not running_only,
                filters={"name": self.mcp_container_prefix}
            )
            
            stats_list = []
            for container in containers:
                stats = await self.get_container_stats(container.id)
                if stats:
                    stats_list.append(stats)
            
            return stats_list
            
        except Exception as e:
            logger.error(f"Failed to get containers stats: {e}")
            return []
    
    async def create_mcp_network(self, network_config: MCPNetworkConfig) -> str:
        """创建MCP网络"""
        try:
            # 验证网络配置
            self._validate_network_config(network_config)
            
            # 构建网络名称
            network_name = f"{self.mcp_network_prefix}-{network_config.vlan_id}"
            
            # 检查网络是否已存在
            try:
                existing_network = self.client.networks.get(network_name)
                logger.info(f"Network {network_name} already exists")
                return existing_network.id
            except docker.errors.NotFound:
                pass
            
            # 创建网络
            network = self.client.networks.create(
                name=network_name,
                driver="bridge",
                ipam=docker.types.IPAMConfig(
                    pool_configs=[
                        docker.types.IPAMPool(
                            subnet=network_config.subnet,
                            gateway=network_config.gateway
                        )
                    ]
                ),
                options={
                    "com.docker.network.bridge.name": f"mcp-br-{network_config.vlan_id}",
                    "com.docker.network.bridge.enable_icc": "true",
                    "com.docker.network.bridge.enable_ip_masquerade": "true"
                },
                labels={
                    "mcp.network.type": "vlan",
                    "mcp.network.vlan_id": str(network_config.vlan_id),
                    "mcp.network.isolation": str(network_config.isolation_enabled)
                }
            )
            
            logger.info(f"Created MCP network: {network_name}")
            return network.id
            
        except Exception as e:
            logger.error(f"Failed to create MCP network: {e}")
            raise
    
    async def get_mcp_networks(self) -> List[Dict[str, Any]]:
        """获取MCP网络列表"""
        try:
            networks = self.client.networks.list(
                filters={"name": self.mcp_network_prefix}
            )
            
            network_list = []
            for network in networks:
                network_info = {
                    "id": network.id,
                    "name": network.name,
                    "driver": network.attrs.get("Driver"),
                    "scope": network.attrs.get("Scope"),
                    "created": network.attrs.get("Created"),
                    "labels": network.attrs.get("Labels", {}),
                    "ipam": network.attrs.get("IPAM", {}),
                    "containers": len(network.attrs.get("Containers", {}))
                }
                network_list.append(network_info)
            
            return network_list
            
        except Exception as e:
            logger.error(f"Failed to get MCP networks: {e}")
            return []
    
    async def _ensure_vlan_network(self, vlan_id: int):
        """确保VLAN网络存在"""
        try:
            network_name = f"{self.mcp_network_prefix}-{vlan_id}"
            
            try:
                network = self.client.networks.get(network_name)
                return network
            except docker.errors.NotFound:
                # 网络不存在，创建它
                network_config = MCPNetworkConfig(
                    name=network_name,
                    vlan_id=vlan_id,
                    subnet=f"172.{20 + vlan_id}.0.0/16",
                    gateway=f"172.{20 + vlan_id}.0.1"
                )
                
                network_id = await self.create_mcp_network(network_config)
                return self.client.networks.get(network_id)
                
        except Exception as e:
            logger.error(f"Failed to ensure VLAN network {vlan_id}: {e}")
            raise
    
    async def _allocate_port(self) -> int:
        """分配可用端口"""
        for port in range(*self.port_range):
            if port not in self.allocated_ports:
                self.allocated_ports.add(port)
                return port
        
        raise Exception("No available ports in range")
    
    async def _release_port_for_service(self, service_id: str):
        """释放服务的端口"""
        # 这里应该根据服务ID查找并释放端口
        # 暂时跳过实现
        pass
    
    def _build_container_config(self, service_id: str, service_config: MCPServiceConfig, network, host_port: int) -> Dict[str, Any]:
        """构建容器配置"""
        container_name = f"{self.mcp_container_prefix}-{service_config.name}-{service_id[:8]}"
        
        # 环境变量
        environment = {
            "MCP_SERVICE_ID": service_id,
            "MCP_SERVICE_NAME": service_config.name,
            "MCP_SERVICE_VERSION": service_config.version,
            "MCP_SERVICE_PORT": str(service_config.port),
            **service_config.environment
        }
        
        # 端口映射
        ports = {
            f"{service_config.port}/tcp": host_port
        }
        
        # 挂载卷
        volumes = {}
        for volume in service_config.volumes:
            if ":" in volume:
                host_path, container_path = volume.split(":", 1)
                volumes[host_path] = {"bind": container_path, "mode": "rw"}
        
        # 资源限制
        resources = {
            "cpu_quota": int(float(service_config.cpu_limit) * 100000),
            "cpu_period": 100000,
            "mem_limit": service_config.memory_limit
        }
        
        # 健康检查
        healthcheck = {
            "test": ["CMD", "curl", "-f", f"http://localhost:{service_config.port}/health"],
            "interval": 30000000000,  # 30秒，单位纳秒
            "timeout": 10000000000,   # 10秒
            "retries": 3,
            "start_period": 60000000000  # 60秒
        }
        
        config = {
            "image": service_config.image_name,
            "name": container_name,
            "environment": environment,
            "ports": ports,
            "volumes": volumes,
            "network": network.name,
            "restart_policy": {"Name": "unless-stopped"},
            "healthcheck": healthcheck,
            "labels": {
                "mcp.service.id": service_id,
                "mcp.service.name": service_config.name,
                "mcp.service.version": service_config.version,
                "mcp.service.type": service_config.type.value,
                "mcp.service.category": service_config.category.value
            },
            **resources
        }
        
        return config
    
    async def _wait_for_container_ready(self, container, timeout: int = 60):
        """等待容器就绪"""
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                container.reload()
                
                # 检查容器状态
                if container.status == "running":
                    # 检查健康状态
                    health_status = container.attrs.get("State", {}).get("Health", {}).get("Status")
                    if health_status == "healthy" or health_status is None:
                        return
                    elif health_status == "unhealthy":
                        raise Exception("Container is unhealthy")
                
                elif container.status == "exited":
                    raise Exception("Container exited unexpectedly")
                
                await asyncio.sleep(2)
                
            except Exception as e:
                if "unhealthy" in str(e) or "exited" in str(e):
                    raise
                # 其他错误继续等待
                await asyncio.sleep(2)
        
        raise Exception(f"Container not ready within {timeout} seconds")
    
    async def _get_container_network_info(self, container, network) -> Dict[str, Any]:
        """获取容器网络信息"""
        try:
            container.reload()
            network_settings = container.attrs["NetworkSettings"]["Networks"]
            
            if network.name in network_settings:
                network_info = network_settings[network.name]
                return {
                    "ip_address": network_info.get("IPAddress"),
                    "gateway": network_info.get("Gateway"),
                    "mac_address": network_info.get("MacAddress"),
                    "network_id": network_info.get("NetworkID")
                }
            else:
                raise Exception(f"Container not connected to network {network.name}")
                
        except Exception as e:
            logger.error(f"Failed to get container network info: {e}")
            return {}
    
    async def _get_container_by_service_id(self, service_id: str):
        """根据服务ID获取容器"""
        try:
            containers = self.client.containers.list(
                all=True,
                filters={"label": f"mcp.service.id={service_id}"}
            )
            
            if containers:
                return containers[0]
            else:
                return None
                
        except Exception as e:
            logger.error(f"Failed to get container by service ID {service_id}: {e}")
            return None
    
    async def _cleanup_failed_deployment(self, service_id: str):
        """清理失败的部署"""
        try:
            # 尝试移除容器
            await self.remove_container(service_id, force=True)
            
            # 释放端口
            await self._release_port_for_service(service_id)
            
        except Exception as e:
            logger.error(f"Failed to cleanup failed deployment {service_id}: {e}")
    
    def _validate_network_config(self, network_config: MCPNetworkConfig):
        """验证网络配置"""
        # 验证VLAN ID
        if not (1 <= network_config.vlan_id <= 4094):
            raise ValueError("VLAN ID must be between 1 and 4094")
        
        # 验证子网
        try:
            subnet = ipaddress.IPv4Network(network_config.subnet)
        except Exception:
            raise ValueError("Invalid subnet CIDR")
        
        # 验证网关
        try:
            gateway = ipaddress.IPv4Address(network_config.gateway)
            if gateway not in subnet:
                raise ValueError("Gateway must be within subnet")
        except Exception:
            raise ValueError("Invalid gateway IP")
    
    def _calculate_cpu_usage(self, stats: Dict[str, Any]) -> float:
        """计算CPU使用率"""
        try:
            cpu_stats = stats["cpu_stats"]
            precpu_stats = stats["precpu_stats"]
            
            cpu_delta = cpu_stats["cpu_usage"]["total_usage"] - precpu_stats["cpu_usage"]["total_usage"]
            system_delta = cpu_stats["system_cpu_usage"] - precpu_stats["system_cpu_usage"]
            
            if system_delta > 0:
                cpu_usage = (cpu_delta / system_delta) * len(cpu_stats["cpu_usage"]["percpu_usage"]) * 100
                return round(cpu_usage, 2)
            
            return 0.0
            
        except Exception:
            return 0.0
    
    def _calculate_memory_usage(self, stats: Dict[str, Any]) -> Dict[str, float]:
        """计算内存使用情况"""
        try:
            memory_stats = stats["memory_stats"]
            
            usage_mb = memory_stats["usage"] / (1024 * 1024)
            limit_mb = memory_stats["limit"] / (1024 * 1024)
            
            return {
                "usage_mb": round(usage_mb, 2),
                "limit_mb": round(limit_mb, 2)
            }
            
        except Exception:
            return {"usage_mb": 0.0, "limit_mb": 0.0}
    
    def _calculate_network_usage(self, stats: Dict[str, Any]) -> Dict[str, int]:
        """计算网络使用情况"""
        try:
            networks = stats["networks"]
            
            rx_bytes = sum(net["rx_bytes"] for net in networks.values())
            tx_bytes = sum(net["tx_bytes"] for net in networks.values())
            
            return {
                "rx_bytes": rx_bytes,
                "tx_bytes": tx_bytes
            }
            
        except Exception:
            return {"rx_bytes": 0, "tx_bytes": 0}
    
    def _calculate_uptime(self, container) -> int:
        """计算容器运行时间"""
        try:
            started_at = container.attrs["State"]["StartedAt"]
            if started_at and started_at != "0001-01-01T00:00:00Z":
                start_time = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                uptime = (datetime.now(start_time.tzinfo) - start_time).total_seconds()
                return int(uptime)
            
            return 0
            
        except Exception:
            return 0