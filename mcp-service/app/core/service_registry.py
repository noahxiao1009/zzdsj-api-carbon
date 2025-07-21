"""
MCP服务注册和发现机制
MCP Service Registry and Discovery
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Set, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum

from ..models.mcp_models import MCPServiceInfo, MCPServiceStatus, MCPServiceConfig
from shared.service_client import call_service, CallMethod, CallConfig

logger = logging.getLogger(__name__)

class ServiceHealthStatus(str, Enum):
    """服务健康状态"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"

@dataclass
class ServiceRegistration:
    """服务注册信息"""
    service_id: str
    service_name: str
    service_url: str
    service_type: str
    version: str
    tags: List[str]
    metadata: Dict[str, Any]
    health_check_url: Optional[str] = None
    health_check_interval: int = 30
    health_status: ServiceHealthStatus = ServiceHealthStatus.UNKNOWN
    last_health_check: Optional[datetime] = None
    registered_at: datetime = None
    ttl: int = 300  # 生存时间（秒）

    def __post_init__(self):
        if self.registered_at is None:
            self.registered_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        # 转换datetime为ISO格式字符串
        if self.registered_at:
            data['registered_at'] = self.registered_at.isoformat()
        if self.last_health_check:
            data['last_health_check'] = self.last_health_check.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ServiceRegistration':
        """从字典创建实例"""
        # 转换ISO格式字符串为datetime
        if 'registered_at' in data and data['registered_at']:
            data['registered_at'] = datetime.fromisoformat(data['registered_at'])
        if 'last_health_check' in data and data['last_health_check']:
            data['last_health_check'] = datetime.fromisoformat(data['last_health_check'])
        return cls(**data)

class MCPServiceRegistry:
    """MCP服务注册中心"""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self.services: Dict[str, ServiceRegistration] = {}
        self.service_watchers: Dict[str, Set[str]] = {}  # service_name -> set of watcher_ids
        self.health_check_tasks: Dict[str, asyncio.Task] = {}
        self.cleanup_task: Optional[asyncio.Task] = None
        
        # 配置
        self.registry_key_prefix = "mcp:services:"
        self.health_check_enabled = True
        self.cleanup_interval = 60  # 清理间隔（秒）
        
        # 启动清理任务
        self._start_cleanup_task()
    
    async def register_service(self, service_config: MCPServiceConfig, service_url: str) -> str:
        """注册MCP服务"""
        try:
            service_id = f"mcp-{service_config.name}-{datetime.now().timestamp()}"
            
            # 创建服务注册信息
            registration = ServiceRegistration(
                service_id=service_id,
                service_name=service_config.name,
                service_url=service_url,
                service_type=service_config.type.value,
                version=service_config.version,
                tags=[service_config.category.value, service_config.type.value],
                metadata={
                    "display_name": service_config.display_name,
                    "description": service_config.description,
                    "tools_count": len(service_config.tools),
                    "vlan_id": service_config.vlan_id,
                    "image_name": service_config.image_name,
                    "port": service_config.port,
                    "cpu_limit": service_config.cpu_limit,
                    "memory_limit": service_config.memory_limit
                },
                health_check_url=f"{service_url}/health"
            )
            
            # 存储到内存
            self.services[service_id] = registration
            
            # 存储到Redis（如果可用）
            if self.redis_client:
                await self._store_service_to_redis(service_id, registration)
            
            # 启动健康检查
            if self.health_check_enabled:
                await self._start_health_check(service_id)
            
            # 通知网关服务注册
            await self._notify_gateway_registration(registration)
            
            logger.info(f"Service registered: {service_config.name} ({service_id})")
            return service_id
            
        except Exception as e:
            logger.error(f"Failed to register service {service_config.name}: {e}")
            raise
    
    async def unregister_service(self, service_id: str) -> bool:
        """注销MCP服务"""
        try:
            if service_id not in self.services:
                logger.warning(f"Service {service_id} not found for unregistration")
                return False
            
            registration = self.services[service_id]
            
            # 停止健康检查
            await self._stop_health_check(service_id)
            
            # 通知网关服务注销
            await self._notify_gateway_unregistration(registration)
            
            # 从内存中移除
            del self.services[service_id]
            
            # 从Redis中移除
            if self.redis_client:
                await self._remove_service_from_redis(service_id)
            
            logger.info(f"Service unregistered: {registration.service_name} ({service_id})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unregister service {service_id}: {e}")
            return False
    
    async def discover_services(
        self,
        service_name: Optional[str] = None,
        service_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        healthy_only: bool = True
    ) -> List[ServiceRegistration]:
        """发现MCP服务"""
        try:
            # 从Redis恢复服务（如果可用）
            if self.redis_client:
                await self._load_services_from_redis()
            
            services = list(self.services.values())
            
            # 过滤条件
            if service_name:
                services = [s for s in services if s.service_name == service_name]
            
            if service_type:
                services = [s for s in services if s.service_type == service_type]
            
            if tags:
                services = [s for s in services if any(tag in s.tags for tag in tags)]
            
            if healthy_only:
                services = [s for s in services if s.health_status == ServiceHealthStatus.HEALTHY]
            
            return services
            
        except Exception as e:
            logger.error(f"Failed to discover services: {e}")
            return []
    
    async def get_service(self, service_id: str) -> Optional[ServiceRegistration]:
        """获取特定服务信息"""
        try:
            if service_id in self.services:
                return self.services[service_id]
            
            # 尝试从Redis加载
            if self.redis_client:
                await self._load_service_from_redis(service_id)
                return self.services.get(service_id)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get service {service_id}: {e}")
            return None
    
    async def update_service_health(self, service_id: str, health_status: ServiceHealthStatus):
        """更新服务健康状态"""
        try:
            if service_id not in self.services:
                return
            
            registration = self.services[service_id]
            old_status = registration.health_status
            
            registration.health_status = health_status
            registration.last_health_check = datetime.now()
            
            # 更新Redis
            if self.redis_client:
                await self._store_service_to_redis(service_id, registration)
            
            # 如果状态发生变化，通知网关
            if old_status != health_status:
                await self._notify_gateway_health_change(registration)
            
            logger.debug(f"Service {service_id} health updated: {old_status} -> {health_status}")
            
        except Exception as e:
            logger.error(f"Failed to update service health {service_id}: {e}")
    
    async def list_all_services(self) -> List[Dict[str, Any]]:
        """列出所有服务"""
        try:
            # 从Redis恢复服务
            if self.redis_client:
                await self._load_services_from_redis()
            
            services_info = []
            for service_id, registration in self.services.items():
                info = registration.to_dict()
                info['service_id'] = service_id
                services_info.append(info)
            
            return services_info
            
        except Exception as e:
            logger.error(f"Failed to list services: {e}")
            return []
    
    async def get_service_stats(self) -> Dict[str, Any]:
        """获取服务统计信息"""
        try:
            total_services = len(self.services)
            healthy_services = sum(1 for s in self.services.values() 
                                 if s.health_status == ServiceHealthStatus.HEALTHY)
            unhealthy_services = sum(1 for s in self.services.values() 
                                   if s.health_status == ServiceHealthStatus.UNHEALTHY)
            
            service_types = {}
            for service in self.services.values():
                service_types[service.service_type] = service_types.get(service.service_type, 0) + 1
            
            return {
                "total_services": total_services,
                "healthy_services": healthy_services,
                "unhealthy_services": unhealthy_services,
                "degraded_services": total_services - healthy_services - unhealthy_services,
                "service_types": service_types,
                "health_check_enabled": self.health_check_enabled
            }
            
        except Exception as e:
            logger.error(f"Failed to get service stats: {e}")
            return {}
    
    async def _start_health_check(self, service_id: str):
        """启动健康检查任务"""
        if service_id in self.health_check_tasks:
            return
        
        task = asyncio.create_task(self._health_check_worker(service_id))
        self.health_check_tasks[service_id] = task
    
    async def _stop_health_check(self, service_id: str):
        """停止健康检查任务"""
        if service_id in self.health_check_tasks:
            task = self.health_check_tasks[service_id]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            del self.health_check_tasks[service_id]
    
    async def _health_check_worker(self, service_id: str):
        """健康检查工作任务"""
        while True:
            try:
                if service_id not in self.services:
                    break
                
                registration = self.services[service_id]
                
                # 执行健康检查
                if registration.health_check_url:
                    try:
                        config = CallConfig(timeout=10, retry_times=1)
                        result = await call_service(
                            service_name="internal",
                            method=CallMethod.GET,
                            path="",
                            config=config,
                            base_url=registration.health_check_url
                        )
                        
                        if result and result.get("status") == "healthy":
                            await self.update_service_health(service_id, ServiceHealthStatus.HEALTHY)
                        else:
                            await self.update_service_health(service_id, ServiceHealthStatus.DEGRADED)
                    except Exception:
                        await self.update_service_health(service_id, ServiceHealthStatus.UNHEALTHY)
                
                # 等待下次检查
                await asyncio.sleep(registration.health_check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error for service {service_id}: {e}")
                await asyncio.sleep(30)  # 错误后等待30秒再试
    
    async def _notify_gateway_registration(self, registration: ServiceRegistration):
        """通知网关服务注册"""
        try:
            # 向网关服务发送注册信息
            await call_service(
                service_name="gateway-service",
                method=CallMethod.POST,
                path="/api/internal/services/register",
                json={
                    "service_id": registration.service_id,
                    "service_name": registration.service_name,
                    "service_url": registration.service_url,
                    "service_type": "mcp",
                    "health_check_url": registration.health_check_url,
                    "metadata": registration.metadata
                }
            )
            
            logger.debug(f"Notified gateway of service registration: {registration.service_name}")
            
        except Exception as e:
            logger.error(f"Failed to notify gateway of registration: {e}")
    
    async def _notify_gateway_unregistration(self, registration: ServiceRegistration):
        """通知网关服务注销"""
        try:
            await call_service(
                service_name="gateway-service",
                method=CallMethod.DELETE,
                path=f"/api/internal/services/{registration.service_id}"
            )
            
            logger.debug(f"Notified gateway of service unregistration: {registration.service_name}")
            
        except Exception as e:
            logger.error(f"Failed to notify gateway of unregistration: {e}")
    
    async def _notify_gateway_health_change(self, registration: ServiceRegistration):
        """通知网关服务健康状态变化"""
        try:
            await call_service(
                service_name="gateway-service",
                method=CallMethod.PUT,
                path=f"/api/internal/services/{registration.service_id}/health",
                json={
                    "health_status": registration.health_status.value,
                    "last_health_check": registration.last_health_check.isoformat() if registration.last_health_check else None
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to notify gateway of health change: {e}")
    
    async def _store_service_to_redis(self, service_id: str, registration: ServiceRegistration):
        """存储服务到Redis"""
        try:
            key = f"{self.registry_key_prefix}{service_id}"
            data = registration.to_dict()
            
            # 存储服务信息
            await self.redis_client.set(key, json.dumps(data))
            
            # 设置TTL
            await self.redis_client.expire(key, registration.ttl)
            
            # 添加到服务列表
            await self.redis_client.sadd(f"{self.registry_key_prefix}list", service_id)
            
        except Exception as e:
            logger.error(f"Failed to store service to Redis: {e}")
    
    async def _remove_service_from_redis(self, service_id: str):
        """从Redis移除服务"""
        try:
            key = f"{self.registry_key_prefix}{service_id}"
            
            # 删除服务信息
            await self.redis_client.delete(key)
            
            # 从服务列表移除
            await self.redis_client.srem(f"{self.registry_key_prefix}list", service_id)
            
        except Exception as e:
            logger.error(f"Failed to remove service from Redis: {e}")
    
    async def _load_services_from_redis(self):
        """从Redis加载所有服务"""
        try:
            service_ids = await self.redis_client.smembers(f"{self.registry_key_prefix}list")
            
            for service_id in service_ids:
                await self._load_service_from_redis(service_id)
                
        except Exception as e:
            logger.error(f"Failed to load services from Redis: {e}")
    
    async def _load_service_from_redis(self, service_id: str):
        """从Redis加载单个服务"""
        try:
            key = f"{self.registry_key_prefix}{service_id}"
            data = await self.redis_client.get(key)
            
            if data:
                service_data = json.loads(data)
                registration = ServiceRegistration.from_dict(service_data)
                self.services[service_id] = registration
                
                # 重启健康检查
                if self.health_check_enabled and service_id not in self.health_check_tasks:
                    await self._start_health_check(service_id)
                    
        except Exception as e:
            logger.error(f"Failed to load service from Redis: {e}")
    
    def _start_cleanup_task(self):
        """启动清理任务"""
        if self.cleanup_task is None:
            self.cleanup_task = asyncio.create_task(self._cleanup_worker())
    
    async def _cleanup_worker(self):
        """清理过期服务的工作任务"""
        while True:
            try:
                current_time = datetime.now()
                expired_services = []
                
                for service_id, registration in self.services.items():
                    # 检查服务是否过期
                    if (current_time - registration.registered_at).total_seconds() > registration.ttl:
                        expired_services.append(service_id)
                
                # 清理过期服务
                for service_id in expired_services:
                    logger.info(f"Cleaning up expired service: {service_id}")
                    await self.unregister_service(service_id)
                
                await asyncio.sleep(self.cleanup_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup worker error: {e}")
                await asyncio.sleep(60)
    
    async def shutdown(self):
        """关闭服务注册中心"""
        logger.info("Shutting down service registry...")
        
        # 停止所有健康检查任务
        for service_id in list(self.health_check_tasks.keys()):
            await self._stop_health_check(service_id)
        
        # 停止清理任务
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # 注销所有服务
        for service_id in list(self.services.keys()):
            await self.unregister_service(service_id)
        
        logger.info("Service registry shutdown complete")

# 全局服务注册中心实例
_service_registry: Optional[MCPServiceRegistry] = None

def get_service_registry(redis_client=None) -> MCPServiceRegistry:
    """获取服务注册中心实例"""
    global _service_registry
    if _service_registry is None:
        _service_registry = MCPServiceRegistry(redis_client)
    return _service_registry

async def initialize_service_registry(redis_client=None):
    """初始化服务注册中心"""
    global _service_registry
    if _service_registry is None:
        _service_registry = MCPServiceRegistry(redis_client)
    return _service_registry