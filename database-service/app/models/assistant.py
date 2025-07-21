"""
助手模型模块: AI助手、对话和消息的数据库模型
现已扩展支持Agno框架特有功能
"""

from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, JSON, Table, Boolean, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from typing import List, Dict, Any, Optional

from .database import Base

# 助手和知识库之间多对多关系的关联表
assistant_knowledge_base = Table(
    'assistant_knowledge_base',
    Base.metadata,
    Column('assistant_id', String(36), ForeignKey('assistants.id'), primary_key=True),
    Column('knowledge_base_id', String(36), ForeignKey('knowledge_bases.id'), primary_key=True)
)


class Assistant(Base):
    """
    助手模型，表示具有特定能力和知识库连接的AI助手
    现已扩展支持Agno框架配置
    """
    __tablename__ = "assistants"
    
    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="助手名称")
    description = Column(Text, nullable=True, comment="助手描述")
    model = Column(String(100), nullable=False, comment="使用的模型")
    capabilities = Column(JSON, nullable=False, default=list, comment="能力列表")
    configuration = Column(JSON, nullable=True, comment="助手配置")
    system_prompt = Column(Text, nullable=True, comment="系统提示词")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), comment="更新时间")
    access_url = Column(String(255), nullable=True, comment="访问URL")
    
    # Agno框架特有字段
    framework = Column(String(50), nullable=False, default='general', comment="框架类型")
    agno_config = Column(JSON, nullable=True, comment="Agno配置")
    agno_agent_id = Column(String(255), nullable=True, comment="Agno Agent ID")
    is_agno_managed = Column(Boolean, default=False, comment="是否由Agno管理")
    
    # 用户关联
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, comment="创建用户ID")
    is_public = Column(Boolean, default=False, comment="是否公开")
    is_active = Column(Boolean, default=True, comment="是否激活")
    
    # 统计信息
    usage_count = Column(Integer, default=0, comment="使用次数")
    rating = Column(Float, default=0.0, comment="评分")
    
    # 关系
    conversations = relationship("Conversation", back_populates="assistant", cascade="all, delete-orphan")
    agno_sessions = relationship("AgnoSession", back_populates="assistant", cascade="all, delete-orphan")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为API响应的字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "model": self.model,
            "capabilities": self.capabilities,
            "configuration": self.configuration,
            "system_prompt": self.system_prompt,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "access_url": self.access_url,
            "framework": self.framework,
            "agno_config": self.agno_config,
            "agno_agent_id": self.agno_agent_id,
            "is_agno_managed": self.is_agno_managed,
            "user_id": self.user_id,
            "is_public": self.is_public,
            "is_active": self.is_active,
            "usage_count": self.usage_count,
            "rating": self.rating
        }


class Conversation(Base):
    """
    对话模型，表示与助手的聊天会话
    """
    __tablename__ = "conversations"
    
    id = Column(String(36), primary_key=True, index=True)
    assistant_id = Column(String(36), ForeignKey("assistants.id"), nullable=False, comment="助手ID")
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, comment="用户ID")
    title = Column(String(255), nullable=False, comment="对话标题")
    metadata = Column(JSON, nullable=True, comment="对话元数据")
    is_active = Column(Boolean, default=True, comment="是否活跃")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), comment="更新时间")
    
    # 统计信息
    message_count = Column(Integer, default=0, comment="消息数量")
    last_message_at = Column(DateTime(timezone=True), comment="最后消息时间")
    
    # 关系
    assistant = relationship("Assistant", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为API响应的字典"""
        return {
            "id": self.id,
            "assistant_id": self.assistant_id,
            "user_id": self.user_id,
            "title": self.title,
            "metadata": self.metadata,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "message_count": self.message_count,
            "last_message_at": self.last_message_at.isoformat() if self.last_message_at else None
        }


class Message(Base):
    """
    消息模型，表示对话中的单条消息
    """
    __tablename__ = "messages"
    
    id = Column(String(36), primary_key=True, index=True)
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=False, comment="对话ID")
    role = Column(String(50), nullable=False, comment="角色")  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False, comment="消息内容")
    metadata = Column(JSON, nullable=True, comment="消息元数据")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    
    # 消息状态
    is_deleted = Column(Boolean, default=False, comment="是否删除")
    edited_at = Column(DateTime(timezone=True), comment="编辑时间")
    
    # 统计信息
    token_count = Column(Integer, comment="Token数量")
    processing_time = Column(Float, comment="处理时间（秒）")
    
    # 关系
    conversation = relationship("Conversation", back_populates="messages")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为API响应的字典"""
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_deleted": self.is_deleted,
            "edited_at": self.edited_at.isoformat() if self.edited_at else None,
            "token_count": self.token_count,
            "processing_time": self.processing_time
        }


class UserAgnoConfig(Base):
    """
    用户级Agno配置模型
    存储每个用户的个性化Agno配置
    """
    __tablename__ = "user_agno_configs"
    
    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, unique=True, index=True, comment="用户ID")
    config_data = Column(JSON, nullable=False, comment="配置数据")
    is_active = Column(Boolean, default=True, comment="是否激活")
    version = Column(String(20), default="1.0", comment="配置版本")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), comment="更新时间")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为API响应的字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "config_data": self.config_data,
            "is_active": self.is_active,
            "version": self.version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class AgnoSession(Base):
    """
    Agno会话模型
    跟踪Agno Agent的会话状态和内存
    """
    __tablename__ = "agno_sessions"
    
    id = Column(String(36), primary_key=True, index=True)
    session_id = Column(String(255), nullable=False, unique=True, index=True, comment="会话ID")
    assistant_id = Column(String(36), ForeignKey("assistants.id"), nullable=False, comment="助手ID")
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True, comment="用户ID")
    agent_name = Column(String(255), nullable=False, comment="Agent名称")
    
    # Agno特有状态
    memory_data = Column(JSON, nullable=True, comment="内存数据")
    tool_states = Column(JSON, nullable=True, comment="工具状态")
    session_metadata = Column(JSON, nullable=True, comment="会话元数据")
    
    # 状态管理
    is_active = Column(Boolean, default=True, comment="是否活跃")
    last_activity = Column(DateTime(timezone=True), server_default=func.now(), comment="最后活动时间")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    
    # 统计信息
    interaction_count = Column(Integer, default=0, comment="交互次数")
    total_tokens = Column(Integer, default=0, comment="总Token数")
    
    # 关系
    assistant = relationship("Assistant", back_populates="agno_sessions")
    tool_executions = relationship("AgnoToolExecution", back_populates="session", cascade="all, delete-orphan")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为API响应的字典"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "assistant_id": self.assistant_id,
            "user_id": self.user_id,
            "agent_name": self.agent_name,
            "memory_data": self.memory_data,
            "tool_states": self.tool_states,
            "session_metadata": self.session_metadata,
            "is_active": self.is_active,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "interaction_count": self.interaction_count,
            "total_tokens": self.total_tokens
        }


class AgnoToolExecution(Base):
    """
    Agno工具执行记录模型
    跟踪工具调用历史和性能
    """
    __tablename__ = "agno_tool_executions"
    
    id = Column(String(36), primary_key=True, index=True)
    session_id = Column(String(255), ForeignKey("agno_sessions.session_id"), nullable=False, comment="会话ID")
    tool_name = Column(String(255), nullable=False, comment="工具名称")
    tool_id = Column(String(255), nullable=False, comment="工具ID")
    
    # 执行详情
    input_data = Column(JSON, nullable=True, comment="输入数据")
    output_data = Column(JSON, nullable=True, comment="输出数据")
    execution_time_ms = Column(Integer, nullable=True, comment="执行时间（毫秒）")
    success = Column(Boolean, default=False, comment="是否成功")
    error_message = Column(Text, nullable=True, comment="错误信息")
    
    # 时间戳
    started_at = Column(DateTime(timezone=True), server_default=func.now(), comment="开始时间")
    completed_at = Column(DateTime(timezone=True), nullable=True, comment="完成时间")
    
    # 统计信息
    token_usage = Column(Integer, comment="Token使用量")
    cost = Column(Float, comment="成本")
    
    # 关系
    session = relationship("AgnoSession", back_populates="tool_executions")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为API响应的字典"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "tool_name": self.tool_name,
            "tool_id": self.tool_id,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "execution_time_ms": self.execution_time_ms,
            "success": self.success,
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "token_usage": self.token_usage,
            "cost": self.cost
        }


class AssistantRating(Base):
    """助手评分模型"""
    __tablename__ = "assistant_ratings"
    
    id = Column(String(36), primary_key=True, index=True)
    assistant_id = Column(String(36), ForeignKey("assistants.id"), nullable=False, comment="助手ID")
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment="用户ID")
    rating = Column(Integer, nullable=False, comment="评分（1-5）")
    comment = Column(Text, comment="评价内容")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), comment="更新时间")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为API响应的字典"""
        return {
            "id": self.id,
            "assistant_id": self.assistant_id,
            "user_id": self.user_id,
            "rating": self.rating,
            "comment": self.comment,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }