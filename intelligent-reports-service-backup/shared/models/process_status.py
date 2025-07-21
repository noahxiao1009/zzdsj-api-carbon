"""
统一状态管理标准
提供一致的状态枚举、状态转换逻辑和重试机制，替代各服务分散的状态定义
"""

import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Type, Union
from dataclasses import dataclass, field
import json
import uuid

logger = logging.getLogger(__name__)


class ProcessStatus(str, Enum):
    """统一的处理状态枚举
    
    标准化所有微服务的状态管理，提供一致的状态转换逻辑
    """
    # 初始状态
    PENDING = "pending"           # 等待处理
    
    # 处理中状态  
    PROCESSING = "processing"     # 正在处理
    RETRYING = "retrying"         # 重试中
    
    # 终态
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败
    CANCELLED = "cancelled"       # 已取消
    TIMEOUT = "timeout"           # 超时
    SKIPPED = "skipped"           # 跳过
    
    @classmethod
    def is_pending_state(cls, status: str) -> bool:
        """判断是否为待处理状态"""
        return status in [cls.PENDING]
    
    @classmethod
    def is_active_state(cls, status: str) -> bool:
        """判断是否为活跃状态"""
        return status in [cls.PROCESSING, cls.RETRYING]
    
    @classmethod
    def is_terminal_state(cls, status: str) -> bool:
        """判断是否为终态"""
        return status in [cls.COMPLETED, cls.FAILED, cls.CANCELLED, cls.TIMEOUT, cls.SKIPPED]
    
    @classmethod
    def is_success_state(cls, status: str) -> bool:
        """判断是否为成功状态"""
        return status in [cls.COMPLETED]
    
    @classmethod
    def is_failure_state(cls, status: str) -> bool:
        """判断是否为失败状态"""
        return status in [cls.FAILED, cls.TIMEOUT]
    
    @classmethod
    def can_transition_to(cls, from_status: str, to_status: str) -> bool:
        """检查状态转换是否有效"""
        # 终态不能转换到其他状态
        if cls.is_terminal_state(from_status):
            return False
        
        # 状态转换规则
        transitions = {
            cls.PENDING: [cls.PROCESSING, cls.CANCELLED, cls.SKIPPED],
            cls.PROCESSING: [cls.COMPLETED, cls.FAILED, cls.RETRYING, cls.CANCELLED, cls.TIMEOUT],
            cls.RETRYING: [cls.PROCESSING, cls.COMPLETED, cls.FAILED, cls.CANCELLED, cls.TIMEOUT]
        }
        
        return to_status in transitions.get(from_status, [])


class RetryStrategy(str, Enum):
    """重试策略枚举"""
    FIXED = "fixed"              # 固定间隔
    EXPONENTIAL = "exponential"  # 指数退避
    LINEAR = "linear"            # 线性增长
    NONE = "none"               # 不重试


@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    base_delay: float = 1.0      # 基础延迟(秒)
    max_delay: float = 60.0      # 最大延迟(秒)
    backoff_factor: float = 2.0  # 退避因子
    jitter: bool = True          # 是否添加随机抖动
    
    def calculate_delay(self, retry_count: int) -> float:
        """计算重试延迟时间"""
        if self.strategy == RetryStrategy.NONE:
            return 0.0
        elif self.strategy == RetryStrategy.FIXED:
            delay = self.base_delay
        elif self.strategy == RetryStrategy.LINEAR:
            delay = self.base_delay * (retry_count + 1)
        elif self.strategy == RetryStrategy.EXPONENTIAL:
            delay = self.base_delay * (self.backoff_factor ** retry_count)
        else:
            delay = self.base_delay
        
        # 限制最大延迟
        delay = min(delay, self.max_delay)
        
        # 添加随机抖动
        if self.jitter:
            import random
            delay *= (0.5 + random.random() * 0.5)
        
        return delay


@dataclass
class ErrorInfo:
    """错误信息"""
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    stack_trace: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "error_type": self.error_type,
            "error_message": self.error_message,
            "error_code": self.error_code,
            "stack_trace": self.stack_trace,
            "context": self.context,
            "occurred_at": self.occurred_at.isoformat()
        }


class RetryMixin:
    """重试机制混入类
    
    为任何需要重试机制的类提供统一的重试逻辑
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.retry_count: int = 0
        self.max_retries: int = 3
        self.retry_config: RetryConfig = RetryConfig()
        self.last_retry_at: Optional[datetime] = None
        self.next_retry_at: Optional[datetime] = None
        self.error_history: List[ErrorInfo] = []
        self.status: str = ProcessStatus.PENDING
        
    def can_retry(self) -> bool:
        """检查是否可以重试"""
        return (
            self.retry_count < self.max_retries and
            self.status in [ProcessStatus.FAILED, ProcessStatus.TIMEOUT]
        )
    
    def should_retry_now(self) -> bool:
        """检查是否应该立即重试"""
        if not self.can_retry():
            return False
        
        if self.next_retry_at is None:
            return True
        
        return datetime.now() >= self.next_retry_at
    
    def schedule_retry(self) -> datetime:
        """调度下次重试"""
        if not self.can_retry():
            raise ValueError("无法调度重试：已达到最大重试次数或处于终态")
        
        delay = self.retry_config.calculate_delay(self.retry_count)
        self.next_retry_at = datetime.now() + timedelta(seconds=delay)
        self.last_retry_at = datetime.now()
        
        logger.info(f"调度重试: {self.retry_count + 1}/{self.max_retries}, 延迟: {delay:.2f}s")
        
        return self.next_retry_at
    
    def start_retry(self) -> None:
        """开始重试"""
        if not self.can_retry():
            raise ValueError("无法开始重试：已达到最大重试次数或处于终态")
        
        self.retry_count += 1
        self.status = ProcessStatus.RETRYING
        self.last_retry_at = datetime.now()
        
        logger.info(f"开始重试: {self.retry_count}/{self.max_retries}")
    
    def add_error(self, error: Union[Exception, ErrorInfo, str]) -> None:
        """添加错误信息"""
        if isinstance(error, Exception):
            error_info = ErrorInfo(
                error_type=type(error).__name__,
                error_message=str(error),
                stack_trace=str(error.__traceback__) if error.__traceback__ else None
            )
        elif isinstance(error, str):
            error_info = ErrorInfo(error_message=error)
        else:
            error_info = error
        
        self.error_history.append(error_info)
        
        # 保持最近的错误记录
        if len(self.error_history) > 10:
            self.error_history = self.error_history[-10:]
    
    def get_retry_stats(self) -> Dict[str, Any]:
        """获取重试统计信息"""
        return {
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "can_retry": self.can_retry(),
            "last_retry_at": self.last_retry_at.isoformat() if self.last_retry_at else None,
            "next_retry_at": self.next_retry_at.isoformat() if self.next_retry_at else None,
            "error_count": len(self.error_history),
            "retry_config": {
                "strategy": self.retry_config.strategy.value,
                "base_delay": self.retry_config.base_delay,
                "max_delay": self.retry_config.max_delay
            }
        }


class StatusTransitionValidator:
    """状态转换验证器"""
    
    @staticmethod
    def validate_transition(from_status: str, to_status: str) -> bool:
        """验证状态转换"""
        return ProcessStatus.can_transition_to(from_status, to_status)
    
    @staticmethod
    def enforce_transition(obj: Any, to_status: str) -> None:
        """强制执行状态转换验证"""
        current_status = getattr(obj, 'status', None)
        if current_status and not ProcessStatus.can_transition_to(current_status, to_status):
            raise ValueError(f"无效的状态转换: {current_status} -> {to_status}")
        
        setattr(obj, 'status', to_status)


# 与现有状态枚举的映射函数
class StatusMigration:
    """状态迁移映射"""
    
    # 各服务现有状态到统一状态的映射
    TASK_STATUS_MAPPING = {
        "todo": ProcessStatus.PENDING,
        "pending": ProcessStatus.PENDING,
        "in_progress": ProcessStatus.PROCESSING,
        "processing": ProcessStatus.PROCESSING,
        "running": ProcessStatus.PROCESSING,
        "completed": ProcessStatus.COMPLETED,
        "done": ProcessStatus.COMPLETED,
        "success": ProcessStatus.COMPLETED,
        "failed": ProcessStatus.FAILED,
        "error": ProcessStatus.FAILED,
        "cancelled": ProcessStatus.CANCELLED,
        "canceled": ProcessStatus.CANCELLED,
        "timeout": ProcessStatus.TIMEOUT,
        "retrying": ProcessStatus.RETRYING,
        "retry": ProcessStatus.RETRYING,
        "skipped": ProcessStatus.SKIPPED,
        "blocked": ProcessStatus.PENDING,  # 阻塞状态映射为待处理
        "paused": ProcessStatus.PENDING,   # 暂停状态映射为待处理
        "review": ProcessStatus.PROCESSING, # 审核状态映射为处理中
        "scheduled": ProcessStatus.PENDING, # 已调度映射为待处理
        "revoked": ProcessStatus.CANCELLED  # 撤销映射为取消
    }
    
    @classmethod
    def migrate_status(cls, old_status: str) -> str:
        """将旧状态迁移到新状态"""
        return cls.TASK_STATUS_MAPPING.get(old_status.lower(), ProcessStatus.PENDING)
    
    @classmethod
    def is_compatible_status(cls, status: str) -> bool:
        """检查状态是否兼容"""
        return status in ProcessStatus.__members__.values() or status.lower() in cls.TASK_STATUS_MAPPING


# 装饰器：自动状态转换验证
def validate_status_transition(func: Callable) -> Callable:
    """状态转换验证装饰器"""
    def wrapper(self, *args, **kwargs):
        # 获取新状态
        new_status = None
        if 'status' in kwargs:
            new_status = kwargs['status']
        elif args and isinstance(args[0], str):
            new_status = args[0]
        
        # 验证状态转换
        if new_status and hasattr(self, 'status'):
            StatusTransitionValidator.enforce_transition(self, new_status)
        
        return func(self, *args, **kwargs)
    
    return wrapper


# 实用函数
def create_standard_response(
    success: bool,
    message: str = "",
    data: Any = None,
    error_info: Optional[ErrorInfo] = None,
    status: str = ProcessStatus.COMPLETED
) -> Dict[str, Any]:
    """创建标准响应格式"""
    response = {
        "success": success,
        "status": status,
        "message": message,
        "timestamp": datetime.now().isoformat()
    }
    
    if data is not None:
        response["data"] = data
    
    if error_info:
        response["error"] = error_info.to_dict()
    
    return response


def get_status_priority(status: str) -> int:
    """获取状态优先级（用于排序）"""
    priority_map = {
        ProcessStatus.FAILED: 1,
        ProcessStatus.TIMEOUT: 2,
        ProcessStatus.RETRYING: 3,
        ProcessStatus.PROCESSING: 4,
        ProcessStatus.PENDING: 5,
        ProcessStatus.COMPLETED: 6,
        ProcessStatus.CANCELLED: 7,
        ProcessStatus.SKIPPED: 8
    }
    return priority_map.get(status, 999)


# 导出的主要类和函数
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