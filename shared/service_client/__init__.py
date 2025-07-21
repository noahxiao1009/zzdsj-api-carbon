"""
微服务间通信SDK
提供统一、简单、可靠的服务调用接口
"""

from .client import (
    ServiceClient,
    AsyncServiceClient,
    CallMethod,
    CallConfig,
    RetryStrategy,
    ServiceCallError,
    get_service_client,
    get_async_client,
    call_service,
    publish_event
)

__version__ = "1.0.0"
__author__ = "ZZDSJ Team"

__all__ = [
    "ServiceClient",
    "AsyncServiceClient", 
    "CallMethod",
    "CallConfig",
    "RetryStrategy",
    "ServiceCallError",
    "get_service_client",
    "get_async_client",
    "call_service",
    "publish_event"
] 