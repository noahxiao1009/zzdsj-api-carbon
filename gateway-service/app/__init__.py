"""
Gateway Service - 网关服务主模块

提供微服务网关的核心功能：
- 服务注册与发现
- 多层API接口（frontend/v1/system）
- 统一认证与授权
- 多线程任务调度
- 请求路由与代理
- 监控与统计
"""

from .discovery import ServiceRegistry
from .auth import AuthManager, JWTHandler, PermissionManager
from .tasks import TaskScheduler, ThreadPoolManager
from .middleware import (
    RequestTracker, 
    AuthMiddleware, 
    APIKeyMiddleware, 
    InternalAuthMiddleware
)
from .routing import RouteManager
from .utils.proxy import ProxyManager
from .utils.response_handler import ResponseHandler

__version__ = "1.0.0"
__author__ = "ZZDSJ Team"
__description__ = "微服务API网关"

__all__ = [
    # 服务发现
    "ServiceRegistry",
    
    # 认证模块
    "AuthManager",
    "JWTHandler", 
    "PermissionManager",
    
    # 任务调度
    "TaskScheduler",
    "ThreadPoolManager",
    
    # 中间件
    "RequestTracker",
    "AuthMiddleware",
    "APIKeyMiddleware", 
    "InternalAuthMiddleware",
    
    # 路由管理
    "RouteManager",
    
    # 工具组件
    "ProxyManager",
    "ResponseHandler",
]
