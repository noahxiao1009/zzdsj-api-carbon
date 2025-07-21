"""
MCP服务管理器
MCP Service Manager
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from ..models.mcp_models import (
    MCPServiceConfig, MCPServiceInfo, MCPServiceStatus, MCPToolInfo,
    MCPToolExecuteRequest, MCPToolExecuteResponse, MCPStreamInfo
)
from ..core.service_registry import get_service_registry, ServiceRegistration
from ..core.fastmcp_integration import FastMCPIntegration
from ..services.docker_service import DockerService
from ..services.sse_service import SSEService
from shared.service_client import call_service, CallMethod, CallConfig

logger = logging.getLogger(__name__)

class MCPService:
    """MCP服务管理器"""
    
    def __init__(self, redis_client=None):
        self.service_registry = get_service_registry(redis_client)
        self.fastmcp_integration = FastMCPIntegration()
        self.docker_service = DockerService()
        self.sse_service = SSEService()
        
        # 服务状态缓存
        self.service_cache: Dict[str, MCPServiceInfo] = {}
        self.cache_ttl = 300  # 5分钟缓存TTL
    
    async def create_service(self, service_config: MCPServiceConfig) -> str:
        """创建MCP服务"""
        try:
            # 验证服务配置
            await self._validate_service_config(service_config)
            
            # 生成服务ID
            service_id = f"mcp-{service_config.name}-{int(datetime.now().timestamp())}"
            
            # 保存服务配置到数据库
            await self._save_service_to_db(service_id, service_config)
            
            logger.info(f"Created MCP service: {service_config.name} ({service_id})")
            return service_id
            
        except Exception as e:
            logger.error(f"Failed to create MCP service {service_config.name}: {e}")
            raise
    
    async def deploy_service_async(self, service_id: str, service_config: MCPServiceConfig):
        """异步部署MCP服务"""
        try:
            # 更新服务状态为部署中
            await self._update_service_status(service_id, MCPServiceStatus.STARTING)
            
            # 1. 部署Docker容器
            container_info = await self.docker_service.deploy_mcp_container(
                service_id, service_config
            )
            
            # 2. 等待容器启动
            await asyncio.sleep(5)
            
            # 3. 部署FastMCP服务
            fastmcp_server_id = await self.fastmcp_integration.deploy_mcp_service(service_config)
            
            # 4. 注册服务到注册中心
            service_url = container_info.get("service_url")
            if service_url:
                registration_id = await self.service_registry.register_service(
                    service_config, service_url
                )
                
                # 5. 更新数据库中的服务信息
                await self._update_service_deployment_info(
                    service_id, container_info, fastmcp_server_id, registration_id
                )
                
                # 6. 更新服务状态为运行中
                await self._update_service_status(service_id, MCPServiceStatus.ACTIVE)
                
                logger.info(f"Successfully deployed MCP service: {service_config.name}")
            else:
                raise Exception("Failed to get service URL from container")
                
        except Exception as e:
            logger.error(f"Failed to deploy MCP service {service_id}: {e}")
            await self._update_service_status(service_id, MCPServiceStatus.ERROR)
            raise
    
    async def redeploy_service_async(self, service_id: str, service_config: MCPServiceConfig):
        """异步重新部署MCP服务"""
        try:
            # 停止现有服务
            await self.stop_service_async(service_id)
            
            # 等待停止完成
            await asyncio.sleep(2)
            
            # 重新部署
            await self.deploy_service_async(service_id, service_config)
            
        except Exception as e:
            logger.error(f"Failed to redeploy MCP service {service_id}: {e}")
            await self._update_service_status(service_id, MCPServiceStatus.ERROR)
            raise
    
    async def start_service_async(self, service_id: str):
        """异步启动MCP服务"""
        try:
            # 更新状态为启动中
            await self._update_service_status(service_id, MCPServiceStatus.STARTING)
            
            # 启动Docker容器
            success = await self.docker_service.start_container(service_id)
            if not success:
                raise Exception("Failed to start Docker container")
            
            # 启动FastMCP服务
            service_info = await self.get_service_by_id(service_id)
            if service_info:
                fastmcp_server_id = service_info.metadata.get("fastmcp_server_id")
                if fastmcp_server_id:
                    success = await self.fastmcp_integration.server_manager.start_server(
                        fastmcp_server_id
                    )
                    if not success:
                        raise Exception("Failed to start FastMCP server")
            
            # 更新状态为运行中
            await self._update_service_status(service_id, MCPServiceStatus.ACTIVE)
            
            logger.info(f"Successfully started MCP service: {service_id}")
            
        except Exception as e:
            logger.error(f"Failed to start MCP service {service_id}: {e}")
            await self._update_service_status(service_id, MCPServiceStatus.ERROR)
            raise
    
    async def stop_service_async(self, service_id: str):
        """异步停止MCP服务"""
        try:
            # 更新状态为停止中
            await self._update_service_status(service_id, MCPServiceStatus.STOPPING)
            
            # 从注册中心注销
            service_info = await self.get_service_by_id(service_id)
            if service_info:
                registration_id = service_info.metadata.get("registration_id")
                if registration_id:
                    await self.service_registry.unregister_service(registration_id)
            
            # 停止FastMCP服务
            fastmcp_server_id = service_info.metadata.get("fastmcp_server_id")
            if fastmcp_server_id:
                await self.fastmcp_integration.server_manager.stop_server(fastmcp_server_id)
            
            # 停止Docker容器
            await self.docker_service.stop_container(service_id)
            
            # 更新状态为已停止
            await self._update_service_status(service_id, MCPServiceStatus.STOPPED)
            
            logger.info(f"Successfully stopped MCP service: {service_id}")
            
        except Exception as e:
            logger.error(f"Failed to stop MCP service {service_id}: {e}")
            await self._update_service_status(service_id, MCPServiceStatus.ERROR)
            raise
    
    async def restart_service_async(self, service_id: str):
        """异步重启MCP服务"""
        try:
            # 停止服务
            await self.stop_service_async(service_id)
            
            # 等待停止完成
            await asyncio.sleep(2)
            
            # 启动服务
            await self.start_service_async(service_id)
            
        except Exception as e:
            logger.error(f"Failed to restart MCP service {service_id}: {e}")
            raise
    
    async def delete_service_async(self, service_id: str, force: bool = False):
        """异步删除MCP服务"""
        try:
            # 停止服务
            if not force:
                await self.stop_service_async(service_id)
            
            # 删除Docker容器
            await self.docker_service.remove_container(service_id, force=force)
            
            # 从FastMCP集成中移除
            service_info = await self.get_service_by_id(service_id)
            if service_info:
                fastmcp_server_id = service_info.metadata.get("fastmcp_server_id")
                if fastmcp_server_id:
                    await self.fastmcp_integration.server_manager.remove_server(fastmcp_server_id)
            
            # 从数据库删除
            await self._delete_service_from_db(service_id)
            
            # 清理缓存
            self.service_cache.pop(service_id, None)
            
            logger.info(f"Successfully deleted MCP service: {service_id}")
            
        except Exception as e:
            logger.error(f"Failed to delete MCP service {service_id}: {e}")
            raise
    
    async def get_services(
        self,
        category: Optional[str] = None,
        status: Optional[MCPServiceStatus] = None,
        search: Optional[str] = None,
        page: int = 1,
        size: int = 20
    ) -> List[MCPServiceInfo]:
        """获取MCP服务列表"""
        try:
            # 从数据库查询服务
            services = await self._query_services_from_db(
                category=category,
                status=status,
                search=search,
                page=page,
                size=size
            )
            
            # 更新缓存
            for service in services:
                self.service_cache[service.id] = service
            
            return services
            
        except Exception as e:
            logger.error(f"Failed to get MCP services: {e}")
            return []
    
    async def get_service_by_id(self, service_id: str) -> Optional[MCPServiceInfo]:
        """根据ID获取MCP服务"""
        try:
            # 检查缓存
            if service_id in self.service_cache:
                cached_service = self.service_cache[service_id]
                # 检查缓存是否过期
                if (datetime.now() - cached_service.updated_at).total_seconds() < self.cache_ttl:
                    return cached_service
            
            # 从数据库查询
            service = await self._query_service_from_db(service_id)
            
            # 更新缓存
            if service:
                self.service_cache[service_id] = service
            
            return service
            
        except Exception as e:
            logger.error(f"Failed to get MCP service {service_id}: {e}")
            return None
    
    async def get_service_by_name(self, service_name: str) -> Optional[MCPServiceInfo]:
        """根据名称获取MCP服务"""
        try:
            service = await self._query_service_by_name_from_db(service_name)
            return service
            
        except Exception as e:
            logger.error(f"Failed to get MCP service by name {service_name}: {e}")
            return None
    
    async def update_service(self, service_id: str, service_config: MCPServiceConfig) -> bool:
        """更新MCP服务配置"""
        try:
            # 验证配置
            await self._validate_service_config(service_config)
            
            # 更新数据库
            success = await self._update_service_in_db(service_id, service_config)
            
            # 清理缓存
            self.service_cache.pop(service_id, None)
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to update MCP service {service_id}: {e}")
            return False
    
    async def check_service_health(self, service_id: str) -> Dict[str, Any]:
        """检查服务健康状态"""
        try:
            # 从注册中心获取服务信息
            registrations = await self.service_registry.discover_services(healthy_only=False)
            
            for reg in registrations:
                if reg.service_id == service_id:
                    return {
                        "service_id": service_id,
                        "healthy": reg.health_status.value == "healthy",
                        "health_status": reg.health_status.value,
                        "last_check": reg.last_health_check.isoformat() if reg.last_health_check else None,
                        "service_url": reg.service_url
                    }
            
            return {
                "service_id": service_id,
                "healthy": False,
                "error": "Service not found in registry"
            }
            
        except Exception as e:
            logger.error(f"Failed to check service health {service_id}: {e}")
            return {
                "service_id": service_id,
                "healthy": False,
                "error": str(e)
            }
    
    async def get_service_tools(self, service_id: str, enabled_only: bool = False) -> List[MCPToolInfo]:
        """获取服务的工具列表"""
        try:
            tools = await self._query_tools_from_db(service_id, enabled_only)
            return tools
            
        except Exception as e:
            logger.error(f"Failed to get service tools {service_id}: {e}")
            return []
    
    async def toggle_tool_status(self, service_id: str, tool_name: str, enabled: bool) -> bool:
        """切换工具启用状态"""
        try:
            success = await self._update_tool_status_in_db(service_id, tool_name, enabled)
            return success
            
        except Exception as e:
            logger.error(f"Failed to toggle tool status {service_id}/{tool_name}: {e}")
            return False
    
    async def batch_toggle_tools(self, service_id: str, tool_updates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量切换工具状态"""
        results = []
        
        for update in tool_updates:
            try:
                tool_name = update.get("tool_name")
                enabled = update.get("enabled", True)
                
                success = await self.toggle_tool_status(service_id, tool_name, enabled)
                
                results.append({
                    "tool_name": tool_name,
                    "enabled": enabled,
                    "success": success
                })
                
            except Exception as e:
                results.append({
                    "tool_name": update.get("tool_name"),
                    "success": False,
                    "error": str(e)
                })
        
        return results
    
    async def execute_tool(self, request: MCPToolExecuteRequest) -> MCPToolExecuteResponse:
        """执行MCP工具"""
        try:
            # 通过FastMCP集成执行工具
            service_info = await self.get_service_by_id(request.service_id)
            if not service_info:
                raise Exception(f"Service {request.service_id} not found")
            
            result = await self.fastmcp_integration.execute_tool(
                service_info.name, request
            )
            
            # 记录使用情况
            await self._record_tool_usage(request, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to execute tool {request.tool_name}: {e}")
            # 返回错误响应
            return MCPToolExecuteResponse(
                success=False,
                result=None,
                execution_time_ms=0,
                error_message=str(e),
                usage_id=""
            )
    
    async def execute_tool_streaming_async(self, request: MCPToolExecuteRequest, stream_id: str):
        """异步执行流式工具"""
        try:
            # 通过SSE服务发送开始事件
            await self.sse_service.send_event(stream_id, {
                "type": "start",
                "tool_name": request.tool_name,
                "parameters": request.parameters
            })
            
            # 执行工具
            result = await self.execute_tool(request)
            
            # 发送结果事件
            await self.sse_service.send_event(stream_id, {
                "type": "result",
                "data": result.dict()
            })
            
            # 发送完成事件
            await self.sse_service.send_event(stream_id, {
                "type": "complete"
            })
            
        except Exception as e:
            logger.error(f"Failed to execute tool streaming {request.tool_name}: {e}")
            # 发送错误事件
            await self.sse_service.send_event(stream_id, {
                "type": "error",
                "error": str(e)
            })
    
    async def validate_service_config(self, service_config: MCPServiceConfig):
        """验证服务配置"""
        await self._validate_service_config(service_config)
    
    async def get_dashboard_stats(self) -> Dict[str, Any]:
        """获取仪表板统计信息"""
        try:
            # 从注册中心获取统计信息
            registry_stats = await self.service_registry.get_service_stats()
            
            # 从数据库获取额外统计信息
            db_stats = await self._get_db_stats()
            
            # 合并统计信息
            stats = {
                **registry_stats,
                **db_stats,
                "timestamp": datetime.now().isoformat()
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get dashboard stats: {e}")
            return {}
    
    async def get_service_stats(self, service_id: str, days: int = 30) -> Dict[str, Any]:
        """获取服务统计信息"""
        try:
            stats = await self._get_service_stats_from_db(service_id, days)
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get service stats {service_id}: {e}")
            return {}
    
    # 私有方法（数据库操作相关）
    async def _validate_service_config(self, service_config: MCPServiceConfig):
        """验证服务配置"""
        # 验证服务名称
        if not service_config.name or len(service_config.name) < 2:
            raise ValueError("Service name must be at least 2 characters")
        
        # 验证Docker镜像
        if not service_config.image_name:
            raise ValueError("Docker image name is required")
        
        # 验证端口
        if not (1 <= service_config.port <= 65535):
            raise ValueError("Port must be between 1 and 65535")
        
        # 验证工具配置
        if not service_config.tools:
            raise ValueError("At least one tool must be configured")
        
        for tool in service_config.tools:
            if not tool.get("name"):
                raise ValueError("Tool name is required")
            if not tool.get("schema"):
                raise ValueError("Tool schema is required")
    
    async def _save_service_to_db(self, service_id: str, service_config: MCPServiceConfig):
        """保存服务到数据库"""
        # 这里应该实现数据库保存逻辑
        # 暂时使用模拟实现
        pass
    
    async def _update_service_status(self, service_id: str, status: MCPServiceStatus):
        """更新服务状态"""
        # 这里应该实现数据库更新逻辑
        # 暂时使用模拟实现
        pass
    
    async def _update_service_deployment_info(self, service_id: str, container_info: Dict, fastmcp_server_id: str, registration_id: str):
        """更新服务部署信息"""
        # 这里应该实现数据库更新逻辑
        # 暂时使用模拟实现
        pass
    
    async def _query_services_from_db(self, **kwargs) -> List[MCPServiceInfo]:
        """从数据库查询服务"""
        # 这里应该实现数据库查询逻辑
        # 暂时返回空列表
        return []
    
    async def _query_service_from_db(self, service_id: str) -> Optional[MCPServiceInfo]:
        """从数据库查询单个服务"""
        # 这里应该实现数据库查询逻辑
        # 暂时返回None
        return None
    
    async def _query_service_by_name_from_db(self, service_name: str) -> Optional[MCPServiceInfo]:
        """从数据库根据名称查询服务"""
        # 这里应该实现数据库查询逻辑
        # 暂时返回None
        return None
    
    async def _update_service_in_db(self, service_id: str, service_config: MCPServiceConfig) -> bool:
        """更新数据库中的服务"""
        # 这里应该实现数据库更新逻辑
        # 暂时返回True
        return True
    
    async def _delete_service_from_db(self, service_id: str):
        """从数据库删除服务"""
        # 这里应该实现数据库删除逻辑
        # 暂时使用模拟实现
        pass
    
    async def _query_tools_from_db(self, service_id: str, enabled_only: bool) -> List[MCPToolInfo]:
        """从数据库查询工具"""
        # 这里应该实现数据库查询逻辑
        # 暂时返回空列表
        return []
    
    async def _update_tool_status_in_db(self, service_id: str, tool_name: str, enabled: bool) -> bool:
        """更新数据库中的工具状态"""
        # 这里应该实现数据库更新逻辑
        # 暂时返回True
        return True
    
    async def _record_tool_usage(self, request: MCPToolExecuteRequest, result: MCPToolExecuteResponse):
        """记录工具使用情况"""
        # 这里应该实现使用记录逻辑
        # 暂时使用模拟实现
        pass
    
    async def _get_db_stats(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        # 这里应该实现数据库统计查询
        # 暂时返回空字典
        return {}
    
    async def _get_service_stats_from_db(self, service_id: str, days: int) -> Dict[str, Any]:
        """从数据库获取服务统计信息"""
        # 这里应该实现数据库统计查询
        # 暂时返回空字典
        return {}