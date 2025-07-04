"""
网关注册服务
向网关层注册数据库服务，实现服务发现和负载均衡
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import httpx
import json

from ..config.database_config import get_database_config
from ..core.connections.database_manager import get_database_manager
from ..core.health.health_checker import get_health_checker

logger = logging.getLogger(__name__)


class GatewayRegistry:
    """网关注册服务"""
    
    def __init__(self):
        self.config = get_database_config()
        self.client = httpx.AsyncClient(timeout=30.0)
        self.registration_task: Optional[asyncio.Task] = None
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.is_registered = False
        self.is_running = False
        self.service_id = f"{self.config.service_name}-{self.config.service_port}"
        
    async def start_registration(self):
        """启动网关注册"""
        if not self.config.gateway_enabled:
            logger.info("网关注册已禁用")
            return
        
        if self.is_running:
            logger.warning("网关注册已在运行中")
            return
        
        self.is_running = True
        logger.info("启动网关注册服务...")
        
        # 启动注册任务
        self.registration_task = asyncio.create_task(self._register_service())
        
        # 启动心跳任务
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        
        logger.info("网关注册服务已启动")
    
    async def stop_registration(self):
        """停止网关注册"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # 取消任务
        if self.registration_task:
            self.registration_task.cancel()
            try:
                await self.registration_task
            except asyncio.CancelledError:
                pass
        
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
        
        # 注销服务
        if self.is_registered:
            await self._deregister_service()
        
        await self.client.aclose()
        logger.info("网关注册服务已停止")
    
    async def _register_service(self):
        """注册服务到网关"""
        try:
            registration_data = await self._get_registration_data()
            
            headers = {}
            if self.config.gateway_token:
                headers["Authorization"] = f"Bearer {self.config.gateway_token}"
            
            response = await self.client.post(
                f"{self.config.gateway_url}/api/gateway/services/register",
                json=registration_data,
                headers=headers
            )
            
            if response.status_code == 200:
                self.is_registered = True
                logger.info(f"服务 {self.service_id} 已成功注册到网关")
            else:
                logger.error(f"服务注册失败: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"服务注册出错: {e}")
    
    async def _deregister_service(self):
        """从网关注销服务"""
        try:
            headers = {}
            if self.config.gateway_token:
                headers["Authorization"] = f"Bearer {self.config.gateway_token}"
            
            response = await self.client.delete(
                f"{self.config.gateway_url}/api/gateway/services/{self.service_id}",
                headers=headers
            )
            
            if response.status_code == 200:
                self.is_registered = False
                logger.info(f"服务 {self.service_id} 已从网关注销")
            else:
                logger.error(f"服务注销失败: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"服务注销出错: {e}")
    
    async def _heartbeat_loop(self):
        """心跳循环"""
        while self.is_running:
            try:
                await asyncio.sleep(30)  # 每30秒发送一次心跳
                
                if self.is_registered:
                    await self._send_heartbeat()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"心跳发送出错: {e}")
    
    async def _send_heartbeat(self):
        """发送心跳到网关"""
        try:
            # 获取当前健康状态
            health_checker = await get_health_checker()
            health_status = health_checker.get_current_status()
            
            heartbeat_data = {
                "service_id": self.service_id,
                "timestamp": datetime.now().isoformat(),
                "status": "healthy" if health_status["overall_status"] == "healthy" else "unhealthy",
                "health_check": health_status
            }
            
            headers = {}
            if self.config.gateway_token:
                headers["Authorization"] = f"Bearer {self.config.gateway_token}"
            
            response = await self.client.post(
                f"{self.config.gateway_url}/api/gateway/services/heartbeat",
                json=heartbeat_data,
                headers=headers
            )
            
            if response.status_code != 200:
                logger.warning(f"心跳发送失败: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"心跳发送出错: {e}")
    
    async def _get_registration_data(self) -> Dict[str, Any]:
        """获取服务注册数据"""
        # 获取数据库管理器和健康检查器
        db_manager = await get_database_manager()
        health_checker = await get_health_checker()
        
        # 获取健康状态
        health_status = health_checker.get_current_status()
        
        return {
            "service_id": self.service_id,
            "service_name": self.config.service_name,
            "service_type": "database",
            "version": "1.0.0",
            "host": self.config.nacos.service_ip,
            "port": self.config.service_port,
            "health_check_url": f"http://{self.config.nacos.service_ip}:{self.config.service_port}/health",
            "metadata": {
                "description": "数据库管理微服务",
                "supported_databases": [
                    "postgresql",
                    "elasticsearch", 
                    "milvus",
                    "redis",
                    "nacos",
                    "rabbitmq"
                ],
                "capabilities": [
                    "connection_management",
                    "health_monitoring",
                    "data_migration",
                    "configuration_management"
                ]
            },
            "routes": [
                {
                    "path": "/api/database/health",
                    "methods": ["GET"],
                    "description": "健康检查"
                },
                {
                    "path": "/api/database/status",
                    "methods": ["GET"],
                    "description": "获取数据库状态"
                },
                {
                    "path": "/api/database/connections",
                    "methods": ["GET", "POST"],
                    "description": "连接管理"
                },
                {
                    "path": "/api/database/migrations",
                    "methods": ["GET", "POST"],
                    "description": "数据迁移"
                },
                {
                    "path": "/api/database/config",
                    "methods": ["GET", "PUT"],
                    "description": "配置管理"
                }
            ],
            "tags": ["database", "infrastructure", "microservice"],
            "registration_time": datetime.now().isoformat(),
            "health_status": health_status
        }
    
    async def update_service_metadata(self, metadata: Dict[str, Any]):
        """更新服务元数据"""
        if not self.is_registered:
            logger.warning("服务未注册，无法更新元数据")
            return
        
        try:
            headers = {}
            if self.config.gateway_token:
                headers["Authorization"] = f"Bearer {self.config.gateway_token}"
            
            response = await self.client.put(
                f"{self.config.gateway_url}/api/gateway/services/{self.service_id}/metadata",
                json=metadata,
                headers=headers
            )
            
            if response.status_code == 200:
                logger.info("服务元数据已更新")
            else:
                logger.error(f"元数据更新失败: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"元数据更新出错: {e}")
    
    async def get_service_info(self) -> Dict[str, Any]:
        """获取服务信息"""
        return {
            "service_id": self.service_id,
            "service_name": self.config.service_name,
            "is_registered": self.is_registered,
            "is_running": self.is_running,
            "gateway_url": self.config.gateway_url,
            "registration_time": datetime.now().isoformat()
        }


# 全局网关注册器实例
_gateway_registry: Optional[GatewayRegistry] = None


async def get_gateway_registry() -> GatewayRegistry:
    """获取网关注册器实例"""
    global _gateway_registry
    if _gateway_registry is None:
        _gateway_registry = GatewayRegistry()
    return _gateway_registry


async def start_gateway_registration():
    """启动网关注册"""
    registry = await get_gateway_registry()
    await registry.start_registration()


async def stop_gateway_registration():
    """停止网关注册"""
    global _gateway_registry
    if _gateway_registry:
        await _gateway_registry.stop_registration()
        _gateway_registry = None 