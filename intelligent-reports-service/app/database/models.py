"""
数据模型定义
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageType(str, Enum):
    CHAT = "chat"
    PLAN = "plan"
    EXECUTION = "execution"
    RESULT = "result"


class PlanStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ConversationModel(BaseModel):
    """会话模型"""
    id: str
    user_id: str
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    is_active: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MessageModel(BaseModel):
    """消息模型"""
    id: str
    conversation_id: str
    content: str
    role: MessageRole
    message_type: MessageType = MessageType.CHAT
    timestamp: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PlanModel(BaseModel):
    """计划模型"""
    id: str
    conversation_id: Optional[str] = None
    user_id: str
    question: str
    plan_data: Dict[str, Any]
    status: PlanStatus = PlanStatus.ACTIVE
    created_at: datetime
    updated_at: datetime


class UserSessionModel(BaseModel):
    """用户会话模型"""
    id: str
    user_id: str
    session_data: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    expires_at: Optional[datetime] = None
    is_active: bool = True


class ChatHistoryRequest(BaseModel):
    """聊天历史请求模型"""
    conversation_id: Optional[str] = None
    user_id: str
    limit: int = Field(default=50, ge=1, le=200)


class ChatHistoryResponse(BaseModel):
    """聊天历史响应模型"""
    conversation_id: str
    messages: List[MessageModel]
    total_count: int


class ConversationListResponse(BaseModel):
    """会话列表响应模型"""
    conversations: List[ConversationModel]
    total_count: int


class SaveMessageRequest(BaseModel):
    """保存消息请求模型"""
    conversation_id: Optional[str] = None
    user_id: str
    content: str
    role: MessageRole
    message_type: MessageType = MessageType.CHAT
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CreateConversationRequest(BaseModel):
    """创建会话请求模型"""
    user_id: str
    title: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UpdateConversationRequest(BaseModel):
    """更新会话请求模型"""
    title: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    is_active: Optional[bool] = None