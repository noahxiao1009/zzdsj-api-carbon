"""
助手相关的Pydantic模式定义
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class AssistantBase(BaseModel):
    """助手基础模式"""
    name: str = Field(..., min_length=1, max_length=100, description="助手名称")
    description: Optional[str] = Field(None, description="助手描述")
    model: str = Field(..., description="使用的模型")
    capabilities: List[str] = Field(default=[], description="能力列表")
    configuration: Optional[Dict[str, Any]] = Field(None, description="助手配置")
    system_prompt: Optional[str] = Field(None, description="系统提示词")
    framework: str = Field(default="general", description="框架类型")
    agno_config: Optional[Dict[str, Any]] = Field(None, description="Agno配置")
    is_public: bool = Field(default=False, description="是否公开")
    is_active: bool = Field(default=True, description="是否激活")


class AssistantCreate(AssistantBase):
    """助手创建模式"""
    user_id: Optional[str] = Field(None, description="创建用户ID")


class AssistantUpdate(BaseModel):
    """助手更新模式"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="助手名称")
    description: Optional[str] = Field(None, description="助手描述")
    model: Optional[str] = Field(None, description="使用的模型")
    capabilities: Optional[List[str]] = Field(None, description="能力列表")
    configuration: Optional[Dict[str, Any]] = Field(None, description="助手配置")
    system_prompt: Optional[str] = Field(None, description="系统提示词")
    framework: Optional[str] = Field(None, description="框架类型")
    agno_config: Optional[Dict[str, Any]] = Field(None, description="Agno配置")
    is_public: Optional[bool] = Field(None, description="是否公开")
    is_active: Optional[bool] = Field(None, description="是否激活")


class AssistantResponse(AssistantBase):
    """助手响应模式"""
    id: str = Field(..., description="助手ID")
    user_id: Optional[str] = Field(None, description="创建用户ID")
    agno_agent_id: Optional[str] = Field(None, description="Agno Agent ID")
    is_agno_managed: bool = Field(default=False, description="是否由Agno管理")
    usage_count: int = Field(default=0, description="使用次数")
    rating: float = Field(default=0.0, description="评分")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    class Config:
        from_attributes = True


# 对话相关模式
class ConversationBase(BaseModel):
    """对话基础模式"""
    title: str = Field(..., min_length=1, max_length=255, description="对话标题")
    metadata: Optional[Dict[str, Any]] = Field(None, description="对话元数据")
    is_active: bool = Field(default=True, description="是否活跃")


class ConversationCreate(ConversationBase):
    """对话创建模式"""
    assistant_id: str = Field(..., description="助手ID")
    user_id: Optional[str] = Field(None, description="用户ID")


class ConversationUpdate(BaseModel):
    """对话更新模式"""
    title: Optional[str] = Field(None, min_length=1, max_length=255, description="对话标题")
    metadata: Optional[Dict[str, Any]] = Field(None, description="对话元数据")
    is_active: Optional[bool] = Field(None, description="是否活跃")


class ConversationResponse(ConversationBase):
    """对话响应模式"""
    id: str = Field(..., description="对话ID")
    assistant_id: str = Field(..., description="助手ID")
    user_id: Optional[str] = Field(None, description="用户ID")
    message_count: int = Field(default=0, description="消息数量")
    last_message_at: Optional[datetime] = Field(None, description="最后消息时间")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    class Config:
        from_attributes = True


# 消息相关模式
class MessageBase(BaseModel):
    """消息基础模式"""
    role: str = Field(..., description="角色")
    content: str = Field(..., description="消息内容")
    metadata: Optional[Dict[str, Any]] = Field(None, description="消息元数据")


class MessageCreate(MessageBase):
    """消息创建模式"""
    conversation_id: str = Field(..., description="对话ID")


class MessageUpdate(BaseModel):
    """消息更新模式"""
    content: Optional[str] = Field(None, description="消息内容")
    metadata: Optional[Dict[str, Any]] = Field(None, description="消息元数据")
    is_deleted: Optional[bool] = Field(None, description="是否删除")


class MessageResponse(MessageBase):
    """消息响应模式"""
    id: str = Field(..., description="消息ID")
    conversation_id: str = Field(..., description="对话ID")
    is_deleted: bool = Field(default=False, description="是否删除")
    edited_at: Optional[datetime] = Field(None, description="编辑时间")
    token_count: Optional[int] = Field(None, description="Token数量")
    processing_time: Optional[float] = Field(None, description="处理时间（秒）")
    created_at: datetime = Field(..., description="创建时间")
    
    class Config:
        from_attributes = True


# Agno会话相关模式
class AgnoSessionBase(BaseModel):
    """Agno会话基础模式"""
    session_id: str = Field(..., description="会话ID")
    agent_name: str = Field(..., description="Agent名称")
    memory_data: Optional[Dict[str, Any]] = Field(None, description="内存数据")
    tool_states: Optional[Dict[str, Any]] = Field(None, description="工具状态")
    session_metadata: Optional[Dict[str, Any]] = Field(None, description="会话元数据")
    is_active: bool = Field(default=True, description="是否活跃")


class AgnoSessionCreate(AgnoSessionBase):
    """Agno会话创建模式"""
    assistant_id: str = Field(..., description="助手ID")
    user_id: str = Field(..., description="用户ID")


class AgnoSessionUpdate(BaseModel):
    """Agno会话更新模式"""
    memory_data: Optional[Dict[str, Any]] = Field(None, description="内存数据")
    tool_states: Optional[Dict[str, Any]] = Field(None, description="工具状态")
    session_metadata: Optional[Dict[str, Any]] = Field(None, description="会话元数据")
    is_active: Optional[bool] = Field(None, description="是否活跃")


class AgnoSessionResponse(AgnoSessionBase):
    """Agno会话响应模式"""
    id: str = Field(..., description="会话ID")
    assistant_id: str = Field(..., description="助手ID")
    user_id: str = Field(..., description="用户ID")
    interaction_count: int = Field(default=0, description="交互次数")
    total_tokens: int = Field(default=0, description="总Token数")
    last_activity: datetime = Field(..., description="最后活动时间")
    created_at: datetime = Field(..., description="创建时间")
    
    class Config:
        from_attributes = True