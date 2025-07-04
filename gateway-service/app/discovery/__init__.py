"""
服务发现模块
包含服务注册、发现、健康检查和负载均衡功能
"""

from .service_registry import (
    ServiceRegistry,
    ServiceInstance,
    ServiceStatus,
    LoadBalanceStrategy,
    LoadBalancer,
    service_registry,
    get_service_registry
)

__all__ = [
    "ServiceRegistry",
    "ServiceInstance", 
    "ServiceStatus",
    "LoadBalanceStrategy",
    "LoadBalancer",
    "service_registry",
    "get_service_registry"
] 