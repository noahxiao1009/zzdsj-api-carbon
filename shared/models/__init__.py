"""
共享数据模型模块
提供统一的状态管理、重试机制等通用组件
"""

from .process_status import (
    ProcessStatus,
    RetryStrategy,
    RetryConfig,
    RetryMixin,
    ErrorInfo,
    StatusTransitionValidator,
    StatusMigration,
    validate_status_transition,
    create_standard_response,
    get_status_priority
)

__all__ = [
    "ProcessStatus",
    "RetryStrategy", 
    "RetryConfig",
    "RetryMixin",
    "ErrorInfo",
    "StatusTransitionValidator",
    "StatusMigration",
    "validate_status_transition",
    "create_standard_response",
    "get_status_priority"
] 