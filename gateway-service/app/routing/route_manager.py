"""
路由管理器

负责动态路由注册、配置和管理
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import time
from fastapi import APIRouter, Request, Response
from fastapi.routing import APIRoute

from app.utils.common.logging_config import get_logger

logger = get_logger(__name__)


class RouteType(Enum):
    """路由类型枚举"""
    FRONTEND = "frontend"
    V1_EXTERNAL = "v1"
    SYSTEM = "system"
    GATEWAY = "gateway"


@dataclass
class RouteConfig:
    """路由配置"""
    path: str
    method: str
    handler: Callable
    route_type: RouteType
    service_name: str
    tags: List[str] = field(default_factory=list)
    dependencies: List[Any] = field(default_factory=list)
    middleware: List[Any] = field(default_factory=list)
    timeout: int = 30
    rate_limit: Optional[Dict[str, int]] = None
    auth_required: bool = True
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RouteStats:
    """路由统计信息"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time: float = 0.0
    last_access: Optional[float] = None
    error_rate: float = 0.0


class RouteManager:
    """路由管理器"""
    
    def __init__(self):
        self.routes: Dict[str, RouteConfig] = {}
        self.route_stats: Dict[str, RouteStats] = {}
        self.active_routers: Dict[RouteType, APIRouter] = {}
        self.route_groups: Dict[str, List[str]] = {}
        self._lock = asyncio.Lock()
        self._initialized = False
        
        logger.info("路由管理器已初始化")
    
    async def initialize(self):
        """初始化路由管理器"""
        if self._initialized:
            return
            
        async with self._lock:
            if self._initialized:
                return
                
            # 创建各类型路由器
            for route_type in RouteType:
                self.active_routers[route_type] = APIRouter()
                
            self._initialized = True
            logger.info("路由管理器初始化完成")
    
    async def register_route(self, config: RouteConfig) -> bool:
        """注册路由"""
        await self.initialize()
        
        route_id = f"{config.route_type.value}:{config.method}:{config.path}"
        
        async with self._lock:
            try:
                # 检查路由是否已存在
                if route_id in self.routes:
                    logger.warning(f"路由已存在: {route_id}")
                    return False
                
                # 获取对应的路由器
                router = self.active_routers.get(config.route_type)
                if not router:
                    logger.error(f"未找到路由器类型: {config.route_type}")
                    return False
                
                # 包装处理器以添加统计功能
                wrapped_handler = self._wrap_handler(route_id, config.handler)
                
                # 注册路由到对应的路由器
                if config.method.upper() == "GET":
                    router.get(
                        config.path,
                        dependencies=config.dependencies,
                        tags=config.tags
                    )(wrapped_handler)
                elif config.method.upper() == "POST":
                    router.post(
                        config.path,
                        dependencies=config.dependencies,
                        tags=config.tags
                    )(wrapped_handler)
                elif config.method.upper() == "PUT":
                    router.put(
                        config.path,
                        dependencies=config.dependencies,
                        tags=config.tags
                    )(wrapped_handler)
                elif config.method.upper() == "DELETE":
                    router.delete(
                        config.path,
                        dependencies=config.dependencies,
                        tags=config.tags
                    )(wrapped_handler)
                else:
                    logger.error(f"不支持的HTTP方法: {config.method}")
                    return False
                
                # 保存路由配置
                self.routes[route_id] = config
                self.route_stats[route_id] = RouteStats()
                
                # 添加到路由组
                group_key = f"{config.route_type.value}:{config.service_name}"
                if group_key not in self.route_groups:
                    self.route_groups[group_key] = []
                self.route_groups[group_key].append(route_id)
                
                logger.info(f"路由注册成功: {route_id}")
                return True
                
            except Exception as e:
                logger.error(f"路由注册失败: {route_id}, 错误: {str(e)}")
                return False
    
    def _wrap_handler(self, route_id: str, handler: Callable) -> Callable:
        """包装处理器以添加统计功能"""
        async def wrapped(*args, **kwargs):
            start_time = time.time()
            stats = self.route_stats.get(route_id)
            
            if stats:
                stats.total_requests += 1
                stats.last_access = start_time
            
            try:
                result = await handler(*args, **kwargs) if asyncio.iscoroutinefunction(handler) else handler(*args, **kwargs)
                
                if stats:
                    stats.successful_requests += 1
                    
                return result
                
            except Exception as e:
                if stats:
                    stats.failed_requests += 1
                    
                logger.error(f"路由处理失败: {route_id}, 错误: {str(e)}")
                raise
                
            finally:
                if stats:
                    response_time = time.time() - start_time
                    # 计算平均响应时间
                    if stats.total_requests > 0:
                        stats.avg_response_time = (
                            (stats.avg_response_time * (stats.total_requests - 1) + response_time) / 
                            stats.total_requests
                        )
                    # 计算错误率
                    if stats.total_requests > 0:
                        stats.error_rate = stats.failed_requests / stats.total_requests
        
        return wrapped
    
    async def unregister_route(self, route_type: RouteType, method: str, path: str) -> bool:
        """注销路由"""
        route_id = f"{route_type.value}:{method}:{path}"
        
        async with self._lock:
            if route_id in self.routes:
                del self.routes[route_id]
                if route_id in self.route_stats:
                    del self.route_stats[route_id]
                
                # 从路由组中移除
                for group_routes in self.route_groups.values():
                    if route_id in group_routes:
                        group_routes.remove(route_id)
                
                logger.info(f"路由注销成功: {route_id}")
                return True
            else:
                logger.warning(f"路由不存在: {route_id}")
                return False
    
    def get_router(self, route_type: RouteType) -> Optional[APIRouter]:
        """获取指定类型的路由器"""
        return self.active_routers.get(route_type)
    
    def get_route_config(self, route_type: RouteType, method: str, path: str) -> Optional[RouteConfig]:
        """获取路由配置"""
        route_id = f"{route_type.value}:{method}:{path}"
        return self.routes.get(route_id)
    
    def get_route_stats(self, route_type: RouteType, method: str, path: str) -> Optional[RouteStats]:
        """获取路由统计信息"""
        route_id = f"{route_type.value}:{method}:{path}"
        return self.route_stats.get(route_id)
    
    def list_routes(
        self, 
        route_type: Optional[RouteType] = None,
        service_name: Optional[str] = None
    ) -> List[RouteConfig]:
        """列出路由"""
        routes = []
        
        for route_config in self.routes.values():
            if route_type and route_config.route_type != route_type:
                continue
            if service_name and route_config.service_name != service_name:
                continue
            routes.append(route_config)
        
        return routes
    
    def get_route_groups(self) -> Dict[str, List[str]]:
        """获取路由分组信息"""
        return self.route_groups.copy()
    
    def get_overall_stats(self) -> Dict[str, Any]:
        """获取整体统计信息"""
        total_routes = len(self.routes)
        total_requests = sum(stats.total_requests for stats in self.route_stats.values())
        total_successful = sum(stats.successful_requests for stats in self.route_stats.values())
        total_failed = sum(stats.failed_requests for stats in self.route_stats.values())
        
        avg_response_time = 0.0
        if self.route_stats:
            avg_response_time = sum(stats.avg_response_time for stats in self.route_stats.values()) / len(self.route_stats)
        
        overall_error_rate = 0.0
        if total_requests > 0:
            overall_error_rate = total_failed / total_requests
        
        # 按类型统计
        by_type = {}
        for route_type in RouteType:
            type_routes = [r for r in self.routes.values() if r.route_type == route_type]
            by_type[route_type.value] = {
                "count": len(type_routes),
                "services": list(set(r.service_name for r in type_routes))
            }
        
        return {
            "total_routes": total_routes,
            "total_requests": total_requests,
            "successful_requests": total_successful,
            "failed_requests": total_failed,
            "overall_error_rate": overall_error_rate,
            "avg_response_time": avg_response_time,
            "by_type": by_type,
            "active_groups": len(self.route_groups)
        }
    
    async def batch_register_routes(self, configs: List[RouteConfig]) -> Dict[str, bool]:
        """批量注册路由"""
        results = {}
        
        for config in configs:
            route_id = f"{config.route_type.value}:{config.method}:{config.path}"
            try:
                success = await self.register_route(config)
                results[route_id] = success
            except Exception as e:
                logger.error(f"批量注册路由失败: {route_id}, 错误: {str(e)}")
                results[route_id] = False
        
        return results
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            "status": "healthy" if self._initialized else "initializing",
            "total_routes": len(self.routes),
            "active_routers": len(self.active_routers),
            "route_groups": len(self.route_groups),
            "initialized": self._initialized
        } 