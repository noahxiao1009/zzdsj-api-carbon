"""
MCP服务的服务间通信集成
统一管理系统定义的MCP服务，使用Docker部署，基于FastMCP V2框架
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
import json
import sys
import os
import uuid
from enum import Enum
import docker
import yaml
from pathlib import Path

# 添加shared模块到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), "../../../shared"))

from service_client import (
    ServiceClient, 
    AsyncServiceClient,
    CallMethod, 
    CallConfig, 
    RetryStrategy,
    ServiceCallError,
    call_service,
    publish_event
)

logger = logging.getLogger(__name__)


class MCPServiceStatus(Enum):
    """MCP服务状态"""
    CREATING = "creating"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    UPDATING = "updating"
    DELETING = "deleting"


class MCPToolCategory(Enum):
    """MCP工具分类"""
    DATA_PROCESSING = "data_processing"
    FILE_OPERATIONS = "file_operations"
    WEB_SCRAPING = "web_scraping"
    API_INTEGRATION = "api_integration"
    DATABASE_OPERATIONS = "database_operations"
    SYSTEM_UTILITIES = "system_utilities"
    AI_TOOLS = "ai_tools"
    CUSTOM = "custom"


class ContainerStatus(Enum):
    """容器状态"""
    CREATED = "created"
    RUNNING = "running"
    EXITED = "exited"
    PAUSED = "paused"
    RESTARTING = "restarting"
    REMOVING = "removing"
    DEAD = "dead"


class MCPServiceIntegration:
    """MCP服务集成类 - 统一管理和部署MCP服务"""
    
    def __init__(self):
        self.service_client = None
        self.async_client = None
        self.docker_client = None
        
        # 配置不同服务的调用参数
        self.auth_config = CallConfig(
            timeout=5,    # 认证要快
            retry_times=2,
            retry_strategy=RetryStrategy.LINEAR
        )
        
        self.base_config = CallConfig(
            timeout=10,   # 基础服务调用
            retry_times=2,
            retry_strategy=RetryStrategy.LINEAR
        )
        
        self.gateway_config = CallConfig(
            timeout=15,   # 网关注册
            retry_times=3,
            retry_strategy=RetryStrategy.LINEAR
        )
        
        self.database_config = CallConfig(
            timeout=20,   # 数据库操作
            retry_times=3,
            retry_strategy=RetryStrategy.LINEAR
        )
        
        # MCP服务功能
        self.mcp_capabilities = {
            "service_management": {
                "description": "MCP服务管理",
                "features": ["create_service", "deploy_service", "monitor_service", "scale_service"]
            },
            "tool_management": {
                "description": "MCP工具管理",
                "features": ["register_tools", "execute_tools", "tool_discovery", "tool_versioning"]
            },
            "container_orchestration": {
                "description": "容器编排",
                "features": ["docker_deployment", "network_management", "resource_allocation", "health_monitoring"]
            },
            "gateway_integration": {
                "description": "网关集成",
                "features": ["service_registration", "auto_discovery", "load_balancing", "health_check"]
            },
            "security_management": {
                "description": "安全管理",
                "features": ["access_control", "authentication", "encryption", "audit_logging"]
            }
        }
        
        # 服务状态和统计
        self.registered_services: Dict[str, Dict[str, Any]] = {}
        self.active_containers: Dict[str, Dict[str, Any]] = {}
        self.available_tools: Dict[str, Dict[str, Any]] = {}
        
        # MCP网络配置
        self.mcp_network_config = {
            "network_name": "mcp-network",
            "network_subnet": "172.20.0.0/16",
            "gateway_ip": "172.20.0.1",
            "dns_servers": ["8.8.8.8", "1.1.1.1"]
        }
        
        # 处理统计
        self.mcp_stats = {
            "total_services": 0,
            "running_services": 0,
            "total_tools": 0,
            "tool_executions": 0,
            "container_deployments": 0,
            "uptime_start": datetime.now()
        }
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.service_client = ServiceClient()
        self.async_client = AsyncServiceClient()
        await self.service_client.__aenter__()
        await self.async_client.__aenter__()
        
        # 初始化Docker客户端
        try:
            self.docker_client = docker.from_env()
            await self._ensure_mcp_network()
        except Exception as e:
            logger.warning(f"Docker客户端初始化失败: {e}")
            
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.service_client:
            await self.service_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.async_client:
            await self.async_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.docker_client:
            self.docker_client.close()
    
    # ==================== 权限验证 ====================
    
    async def _verify_user_permission(self, user_id: str, action: str) -> Dict[str, Any]:
        """验证用户权限"""
        try:
            result = await self.service_client.call(
                service_name="base-service",
                method=CallMethod.POST,
                path="/api/v1/auth/check-permission",
                config=self.auth_config,
                json={
                    "user_id": user_id,
                    "resource_type": "MCP_SERVICE",
                    "action": action,
                    "context": {
                        "service": "mcp-service",
                        "operation": action
                    }
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(f"权限验证失败: {e}")
            return {"allowed": False, "error": str(e)}
    
    # ==================== Docker网络管理 ====================
    
    async def _ensure_mcp_network(self):
        """确保MCP网络存在"""
        try:
            network_name = self.mcp_network_config["network_name"]
            
            # 检查网络是否存在
            try:
                network = self.docker_client.networks.get(network_name)
                logger.info(f"MCP网络已存在: {network_name}")
                return network
            except docker.errors.NotFound:
                pass
            
            # 创建网络
            network = self.docker_client.networks.create(
                name=network_name,
                driver="bridge",
                ipam=docker.types.IPAMConfig(
                    driver="default",
                    pool_configs=[
                        docker.types.IPAMPool(
                            subnet=self.mcp_network_config["network_subnet"],
                            gateway=self.mcp_network_config["gateway_ip"]
                        )
                    ]
                ),
                options={
                    "com.docker.network.bridge.enable_icc": "true",
                    "com.docker.network.bridge.enable_ip_masquerade": "true"
                }
            )
            
            logger.info(f"MCP网络创建成功: {network_name}")
            return network
            
        except Exception as e:
            logger.error(f"MCP网络管理失败: {e}")
            raise
    
    # ==================== MCP服务管理 ====================
    
    async def create_mcp_service_workflow(
        self,
        service_name: str,
        service_config: Dict[str, Any],
        user_id: str,
        deploy_immediately: bool = True
    ) -> Dict[str, Any]:
        """创建MCP服务的完整工作流"""
        try:
            start_time = datetime.now()
            logger.info(f"开始创建MCP服务: {service_name} (用户: {user_id})")
            
            # 1. 权限验证
            auth_result = await self._verify_user_permission(user_id, "create_mcp_service")
            if not auth_result.get("allowed"):
                return {
                    "success": False,
                    "error": "权限不足",
                    "required_permission": "mcp_service:create"
                }
            
            # 2. 验证服务配置
            validation_result = await self._validate_service_config(service_config)
            if not validation_result.get("valid"):
                return {
                    "success": False,
                    "error": f"服务配置无效: {validation_result.get('error')}"
                }
            
            # 3. 检查服务名称冲突
            if service_name in self.registered_services:
                return {
                    "success": False,
                    "error": "服务名称已存在",
                    "service_name": service_name
                }
            
            # 4. 生成服务元数据
            service_id = str(uuid.uuid4())
            service_metadata = {
                "service_id": service_id,
                "service_name": service_name,
                "config": service_config,
                "status": MCPServiceStatus.CREATING.value,
                "created_by": user_id,
                "created_at": start_time,
                "updated_at": start_time,
                "container_id": None,
                "container_status": None,
                "exposed_ports": service_config.get("ports", []),
                "environment": service_config.get("environment", {}),
                "tools": service_config.get("tools", [])
            }
            
            # 5. 注册服务到数据库
            db_result = await self._save_service_to_database(service_metadata)
            if not db_result.get("success"):
                return {
                    "success": False,
                    "error": f"数据库保存失败: {db_result.get('error')}"
                }
            
            # 6. 注册服务信息
            self.registered_services[service_name] = service_metadata
            self.mcp_stats["total_services"] += 1
            
            # 7. 部署服务（如果需要）
            deploy_result = None
            if deploy_immediately:
                deploy_result = await self.deploy_mcp_service(service_name, user_id)
                if not deploy_result.get("success"):
                    logger.warning(f"服务部署失败，但服务已注册: {deploy_result.get('error')}")
            
            # 8. 发布服务创建事件
            await publish_event(
                "mcp_service.created",
                {
                    "service_id": service_id,
                    "service_name": service_name,
                    "created_by": user_id,
                    "deploy_status": deploy_result.get("success") if deploy_result else None,
                    "creation_time": (datetime.now() - start_time).total_seconds(),
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            logger.info(f"MCP服务创建成功: {service_name} (ID: {service_id})")
            
            return {
                "success": True,
                "service_id": service_id,
                "service_name": service_name,
                "status": service_metadata["status"],
                "deploy_result": deploy_result,
                "creation_time": (datetime.now() - start_time).total_seconds()
            }
            
        except Exception as e:
            logger.error(f"MCP服务创建失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "service_name": service_name
            }
    
    async def deploy_mcp_service(self, service_name: str, user_id: str) -> Dict[str, Any]:
        """部署MCP服务到Docker容器"""
        try:
            if service_name not in self.registered_services:
                return {
                    "success": False,
                    "error": "服务未注册",
                    "service_name": service_name
                }
            
            service_metadata = self.registered_services[service_name]
            service_config = service_metadata["config"]
            
            # 权限验证
            auth_result = await self._verify_user_permission(user_id, "deploy_mcp_service")
            if not auth_result.get("allowed"):
                return {
                    "success": False,
                    "error": "权限不足"
                }
            
            # 更新服务状态
            service_metadata["status"] = MCPServiceStatus.CREATING.value
            service_metadata["updated_at"] = datetime.now()
            
            # 构建Docker容器配置
            container_config = {
                "image": service_config.get("image", "fastmcp/base:v2"),
                "name": f"mcp-{service_name}-{uuid.uuid4().hex[:8]}",
                "environment": {
                    **service_config.get("environment", {}),
                    "MCP_SERVICE_NAME": service_name,
                    "MCP_SERVICE_ID": service_metadata["service_id"]
                },
                "ports": self._build_port_mapping(service_config.get("ports", [])),
                "volumes": self._build_volume_mapping(service_config.get("volumes", [])),
                "network": self.mcp_network_config["network_name"],
                "restart_policy": {"Name": "unless-stopped"},
                "labels": {
                    "mcp.service.name": service_name,
                    "mcp.service.id": service_metadata["service_id"],
                    "mcp.service.type": "fastmcp-v2",
                    "mcp.created.by": user_id
                }
            }
            
            # 启动Docker容器
            try:
                container = self.docker_client.containers.run(
                    detach=True,
                    **container_config
                )
                
                # 更新服务信息
                service_metadata["container_id"] = container.id
                service_metadata["container_status"] = ContainerStatus.RUNNING.value
                service_metadata["status"] = MCPServiceStatus.RUNNING.value
                
                # 注册到活跃容器列表
                self.active_containers[container.id] = {
                    "container": container,
                    "service_name": service_name,
                    "service_id": service_metadata["service_id"],
                    "started_at": datetime.now(),
                    "user_id": user_id
                }
                
                self.mcp_stats["running_services"] += 1
                self.mcp_stats["container_deployments"] += 1
                
                # 注册到网关
                await self._register_service_to_gateway(service_name, service_metadata)
                
                logger.info(f"MCP服务部署成功: {service_name} -> {container.id}")
                
                return {
                    "success": True,
                    "service_name": service_name,
                    "container_id": container.id,
                    "container_name": container.name,
                    "status": MCPServiceStatus.RUNNING.value
                }
                
            except docker.errors.DockerException as e:
                service_metadata["status"] = MCPServiceStatus.ERROR.value
                logger.error(f"Docker容器启动失败: {e}")
                return {
                    "success": False,
                    "error": f"容器启动失败: {str(e)}",
                    "service_name": service_name
                }
            
        except Exception as e:
            logger.error(f"MCP服务部署失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "service_name": service_name
            }
    
    async def stop_mcp_service(self, service_name: str, user_id: str) -> Dict[str, Any]:
        """停止MCP服务"""
        try:
            if service_name not in self.registered_services:
                return {
                    "success": False,
                    "error": "服务未注册",
                    "service_name": service_name
                }
            
            service_metadata = self.registered_services[service_name]
            container_id = service_metadata.get("container_id")
            
            if not container_id:
                return {
                    "success": False,
                    "error": "服务未部署",
                    "service_name": service_name
                }
            
            # 权限验证
            auth_result = await self._verify_user_permission(user_id, "stop_mcp_service")
            if not auth_result.get("allowed"):
                return {
                    "success": False,
                    "error": "权限不足"
                }
            
            # 停止容器
            try:
                container = self.docker_client.containers.get(container_id)
                container.stop(timeout=30)  # 30秒超时
                
                # 更新服务状态
                service_metadata["status"] = MCPServiceStatus.STOPPED.value
                service_metadata["container_status"] = ContainerStatus.EXITED.value
                service_metadata["updated_at"] = datetime.now()
                
                # 从活跃容器列表移除
                if container_id in self.active_containers:
                    del self.active_containers[container_id]
                
                self.mcp_stats["running_services"] = max(0, self.mcp_stats["running_services"] - 1)
                
                # 从网关注销
                await self._unregister_service_from_gateway(service_name)
                
                logger.info(f"MCP服务停止成功: {service_name}")
                
                return {
                    "success": True,
                    "service_name": service_name,
                    "container_id": container_id,
                    "status": MCPServiceStatus.STOPPED.value
                }
                
            except docker.errors.NotFound:
                # 容器不存在，更新状态
                service_metadata["status"] = MCPServiceStatus.ERROR.value
                service_metadata["container_status"] = ContainerStatus.DEAD.value
                
                return {
                    "success": False,
                    "error": "容器不存在",
                    "service_name": service_name
                }
            
        except Exception as e:
            logger.error(f"MCP服务停止失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "service_name": service_name
            } 