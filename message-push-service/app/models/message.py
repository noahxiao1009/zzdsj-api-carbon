"""
消息数据模型
定义SSE消息的标准格式和数据结构
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
import uuid
import json


class MessageType(str, Enum):
    """消息类型枚举"""
    PROGRESS = "progress"           # 进度更新
    STATUS = "status"              # 状态变更  
    ERROR = "error"                # 错误通知
    SUCCESS = "success"            # 成功通知
    WARNING = "warning"            # 警告消息
    INFO = "info"                  # 信息通知
    CUSTOM = "custom"              # 自定义消息


class MessagePriority(str, Enum):
    """消息优先级"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class MessageTarget(BaseModel):
    """消息目标定义"""
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    connection_id: Optional[str] = None
    channel: Optional[str] = None
    service: Optional[str] = None
    
    # 业务相关目标
    kb_id: Optional[str] = None
    task_id: Optional[str] = None
    agent_id: Optional[str] = None
    
    def to_channels(self) -> List[str]:
        """转换为频道列表"""
        channels = []
        
        if self.user_id:
            channels.append(f"user:{self.user_id}")
        if self.session_id:
            channels.append(f"session:{self.session_id}")
        if self.connection_id:
            channels.append(f"connection:{self.connection_id}")
        if self.channel:
            channels.append(f"channel:{self.channel}")
        if self.service:
            channels.append(f"service:{self.service}")
        if self.kb_id:
            channels.append(f"kb:{self.kb_id}")
        if self.task_id:
            channels.append(f"task:{self.task_id}")
        if self.agent_id:
            channels.append(f"agent:{self.agent_id}")
            
        return channels


class MessageMetadata(BaseModel):
    """消息元数据"""
    priority: MessagePriority = MessagePriority.NORMAL
    ttl: int = Field(default=3600, description="消息生存时间（秒）")
    retry_count: int = Field(default=0, description="重试次数")
    max_retries: int = Field(default=3, description="最大重试次数")
    correlation_id: Optional[str] = Field(None, description="关联ID")
    reply_to: Optional[str] = Field(None, description="回复目标")
    
    # 业务元数据
    service_version: Optional[str] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None


class SSEMessage(BaseModel):
    """SSE消息标准格式"""
    id: str = Field(default_factory=lambda: f"msg_{int(datetime.now().timestamp() * 1000)}_{uuid.uuid4().hex[:8]}")
    timestamp: datetime = Field(default_factory=datetime.now)
    type: MessageType
    service: str = Field(..., description="发送服务名称")
    source: str = Field(..., description="消息源（如：document_processing）")
    target: MessageTarget
    data: Dict[str, Any] = Field(..., description="消息数据")
    metadata: MessageMetadata = Field(default_factory=MessageMetadata)
    
    def to_sse_format(self) -> str:
        """转换为SSE格式字符串"""
        lines = []
        
        # 消息ID
        lines.append(f"id: {self.id}")
        
        # 消息类型作为事件类型
        lines.append(f"event: {self.type}")
        
        # 消息数据
        message_data = {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "type": self.type,
            "service": self.service,
            "source": self.source,
            "target": self.target.dict(),
            "data": self.data,
            "metadata": self.metadata.dict()
        }
        
        # 将数据序列化为JSON，支持多行
        data_json = json.dumps(message_data, ensure_ascii=False, separators=(',', ':'))
        for line in data_json.split('\n'):
            lines.append(f"data: {line}")
        
        # SSE消息结束标记
        lines.append("")
        
        return "\n".join(lines)
    
    def is_expired(self) -> bool:
        """检查消息是否过期"""
        if self.metadata.ttl <= 0:
            return False
        
        expiry_time = self.timestamp.timestamp() + self.metadata.ttl
        return datetime.now().timestamp() > expiry_time
    
    def can_retry(self) -> bool:
        """检查是否可以重试"""
        return self.metadata.retry_count < self.metadata.max_retries
    
    def increment_retry(self) -> None:
        """增加重试次数"""
        self.metadata.retry_count += 1


class ProgressMessage(SSEMessage):
    """进度消息特定格式"""
    type: MessageType = MessageType.PROGRESS
    
    @classmethod
    def create(
        cls,
        service: str,
        source: str,
        target: MessageTarget,
        task_id: str,
        progress: int,
        stage: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """创建进度消息"""
        return cls(
            service=service,
            source=source,
            target=target,
            data={
                "task_id": task_id,
                "progress": max(0, min(100, progress)),  # 确保在0-100范围内
                "stage": stage,
                "message": message,
                "details": details or {}
            }
        )


class StatusMessage(SSEMessage):
    """状态消息特定格式"""
    type: MessageType = MessageType.STATUS
    
    @classmethod
    def create(
        cls,
        service: str,
        source: str,
        target: MessageTarget,
        task_id: str,
        old_status: str,
        new_status: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """创建状态变更消息"""
        return cls(
            service=service,
            source=source,
            target=target,
            data={
                "task_id": task_id,
                "old_status": old_status,
                "new_status": new_status,
                "message": message,
                "details": details or {}
            }
        )


class ErrorMessage(SSEMessage):
    """错误消息特定格式"""
    type: MessageType = MessageType.ERROR
    
    @classmethod
    def create(
        cls,
        service: str,
        source: str,
        target: MessageTarget,
        error_code: str,
        error_message: str,
        task_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """创建错误消息"""
        data = {
            "error_code": error_code,
            "error_message": error_message,
            "details": details or {}
        }
        
        if task_id:
            data["task_id"] = task_id
            
        return cls(
            service=service,
            source=source,
            target=target,
            data=data,
            metadata=MessageMetadata(priority=MessagePriority.HIGH)
        )


class SuccessMessage(SSEMessage):
    """成功消息特定格式"""
    type: MessageType = MessageType.SUCCESS
    
    @classmethod
    def create(
        cls,
        service: str,
        source: str,
        target: MessageTarget,
        task_id: str,
        message: str,
        result: Optional[Dict[str, Any]] = None
    ):
        """创建成功消息"""
        return cls(
            service=service,
            source=source,
            target=target,
            data={
                "task_id": task_id,
                "message": message,
                "result": result or {}
            }
        )


# 消息工厂函数
def create_progress_message(
    service: str,
    task_id: str,
    progress: int,
    stage: str,
    message: str,
    user_id: Optional[str] = None,
    kb_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> ProgressMessage:
    """创建进度消息的便捷函数"""
    target = MessageTarget(
        user_id=user_id,
        kb_id=kb_id,
        task_id=task_id
    )
    
    return ProgressMessage.create(
        service=service,
        source="task_processing",
        target=target,
        task_id=task_id,
        progress=progress,
        stage=stage,
        message=message,
        details=details
    )


def create_error_message(
    service: str,
    error_code: str,
    error_message: str,
    user_id: Optional[str] = None,
    task_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> ErrorMessage:
    """创建错误消息的便捷函数"""
    target = MessageTarget(
        user_id=user_id,
        task_id=task_id
    )
    
    return ErrorMessage.create(
        service=service,
        source="error_handler",
        target=target,
        error_code=error_code,
        error_message=error_message,
        task_id=task_id,
        details=details
    )