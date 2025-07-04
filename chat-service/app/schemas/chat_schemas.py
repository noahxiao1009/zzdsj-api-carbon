"""
Chat-Service Schema定义
定义聊天会话、消息管理、智能体交互等相关的Pydantic Schema
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator
import uuid


# ===== 枚举类型定义 =====

class SessionStatus(str, Enum):
    """会话状态枚举"""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    TIMEOUT = "timeout"
    ERROR = "error"


class MessageType(str, Enum):
    """消息类型枚举"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    FUNCTION = "function"
    TOOL = "tool"


class MessageStatus(str, Enum):
    """消息状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ChatMode(str, Enum):
    """聊天模式枚举"""
    NORMAL = "normal"
    STREAM = "stream"
    RAG = "rag"
    AGENT = "agent"
    FUNCTION_CALLING = "function_calling"


class AgentStatus(str, Enum):
    """智能体状态枚举"""
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    WAITING = "waiting"
    ERROR = "error"


# ===== 基础Schema类 =====

class BaseSchema(BaseModel):
    """基础Schema类"""
    class Config:
        from_attributes = True
        use_enum_values = True
        arbitrary_types_allowed = True


# ===== 分页和过滤Schema =====

class PaginationParams(BaseSchema):
    """分页参数"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页大小")
    
    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class SessionFilterParams(BaseSchema):
    """会话过滤参数"""
    user_id: Optional[str] = Field(None, description="用户ID过滤")
    agent_id: Optional[str] = Field(None, description="智能体ID过滤")
    status: Optional[SessionStatus] = Field(None, description="会话状态过滤")
    search: Optional[str] = Field(None, description="搜索关键词")
    created_start: Optional[datetime] = Field(None, description="创建时间起")
    created_end: Optional[datetime] = Field(None, description="创建时间止")


class MessageFilterParams(BaseSchema):
    """消息过滤参数"""
    session_id: Optional[str] = Field(None, description="会话ID过滤")
    message_type: Optional[MessageType] = Field(None, description="消息类型过滤")
    status: Optional[MessageStatus] = Field(None, description="消息状态过滤")
    search: Optional[str] = Field(None, description="搜索关键词")


# ===== 聊天会话相关Schema =====

class ChatSessionCreate(BaseSchema):
    """聊天会话创建请求"""
    title: Optional[str] = Field(None, max_length=200, description="会话标题")
    agent_id: Optional[str] = Field(None, description="智能体ID")
    user_id: str = Field(..., description="用户ID")
    mode: Optional[ChatMode] = Field(ChatMode.NORMAL, description="聊天模式")
    
    # 会话配置
    max_messages: Optional[int] = Field(100, ge=1, le=1000, description="最大消息数")
    timeout_minutes: Optional[int] = Field(60, ge=5, le=480, description="超时时间(分钟)")
    
    # 模型配置
    model_config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="模型配置")
    system_prompt: Optional[str] = Field(None, description="系统提示词")
    
    # 知识库配置
    knowledge_base_ids: Optional[List[str]] = Field(default_factory=list, description="知识库ID列表")
    
    # 其他配置
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")


class ChatSessionUpdate(BaseSchema):
    """聊天会话更新请求"""
    title: Optional[str] = Field(None, max_length=200, description="会话标题")
    status: Optional[SessionStatus] = Field(None, description="会话状态")
    max_messages: Optional[int] = Field(None, ge=1, le=1000, description="最大消息数")
    timeout_minutes: Optional[int] = Field(None, ge=5, le=480, description="超时时间(分钟)")
    model_config: Optional[Dict[str, Any]] = Field(None, description="模型配置")
    system_prompt: Optional[str] = Field(None, description="系统提示词")
    knowledge_base_ids: Optional[List[str]] = Field(None, description="知识库ID列表")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


# ===== 聊天消息相关Schema =====

class ChatMessageCreate(BaseSchema):
    """聊天消息创建请求"""
    session_id: str = Field(..., description="会话ID")
    content: str = Field(..., min_length=1, description="消息内容")
    message_type: MessageType = Field(MessageType.USER, description="消息类型")
    
    # 附件信息
    attachments: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="附件列表")
    
    # 工具调用信息
    tool_calls: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="工具调用列表")
    
    # 元数据
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")


class ChatRequest(BaseSchema):
    """聊天请求"""
    message: str = Field(..., min_length=1, description="用户消息")
    session_id: Optional[str] = Field(None, description="会话ID，不提供则创建新会话")
    agent_id: Optional[str] = Field(None, description="智能体ID")
    
    # 聊天配置
    mode: Optional[ChatMode] = Field(ChatMode.NORMAL, description="聊天模式")
    stream: Optional[bool] = Field(False, description="是否流式响应")
    
    # 模型配置
    model_config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="模型配置")
    
    # 知识库配置
    knowledge_base_ids: Optional[List[str]] = Field(default_factory=list, description="知识库ID列表")
    
    # 工具配置
    tools: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="可用工具列表")
    
    # 其他配置
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="上下文信息")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")


class ChatStreamRequest(BaseSchema):
    """流式聊天请求"""
    message: str = Field(..., min_length=1, description="用户消息")
    session_id: Optional[str] = Field(None, description="会话ID")
    agent_id: Optional[str] = Field(None, description="智能体ID")
    model_config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="模型配置")


# ===== 智能体相关Schema =====

class AgentCreate(BaseSchema):
    """智能体创建请求"""
    name: str = Field(..., min_length=1, max_length=100, description="智能体名称")
    description: Optional[str] = Field(None, description="智能体描述")
    user_id: str = Field(..., description="创建者用户ID")
    
    # 智能体配置
    system_prompt: Optional[str] = Field(None, description="系统提示词")
    model_config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="模型配置")
    
    # 工具配置
    tools: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="工具列表")
    
    # 知识库配置
    knowledge_base_ids: Optional[List[str]] = Field(default_factory=list, description="知识库ID列表")
    
    # 其他配置
    avatar_url: Optional[str] = Field(None, description="头像URL")
    tags: Optional[List[str]] = Field(default_factory=list, description="标签列表")
    is_public: Optional[bool] = Field(False, description="是否公开")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")


class AgentUpdate(BaseSchema):
    """智能体更新请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="智能体名称")
    description: Optional[str] = Field(None, description="智能体描述")
    system_prompt: Optional[str] = Field(None, description="系统提示词")
    model_config: Optional[Dict[str, Any]] = Field(None, description="模型配置")
    tools: Optional[List[Dict[str, Any]]] = Field(None, description="工具列表")
    knowledge_base_ids: Optional[List[str]] = Field(None, description="知识库ID列表")
    avatar_url: Optional[str] = Field(None, description="头像URL")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    is_public: Optional[bool] = Field(None, description="是否公开")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


# ===== 响应Schema =====

class ChatSessionResponse(BaseSchema):
    """聊天会话响应"""
    id: str = Field(..., description="会话ID")
    title: Optional[str] = Field(None, description="会话标题")
    user_id: str = Field(..., description="用户ID")
    agent_id: Optional[str] = Field(None, description="智能体ID")
    status: SessionStatus = Field(..., description="会话状态")
    mode: ChatMode = Field(..., description="聊天模式")
    
    # 会话配置
    max_messages: int = Field(..., description="最大消息数")
    timeout_minutes: int = Field(..., description="超时时间(分钟)")
    
    # 模型配置
    model_config: Optional[Dict[str, Any]] = Field(None, description="模型配置")
    system_prompt: Optional[str] = Field(None, description="系统提示词")
    
    # 知识库配置
    knowledge_base_ids: List[str] = Field(..., description="知识库ID列表")
    
    # 统计信息
    message_count: int = Field(..., description="消息数量")
    
    # 时间信息
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    last_message_at: Optional[datetime] = Field(None, description="最后消息时间")
    
    # 关联信息
    agent_name: Optional[str] = Field(None, description="智能体名称")
    user_name: Optional[str] = Field(None, description="用户名称")
    
    # 其他信息
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


class ChatMessageResponse(BaseSchema):
    """聊天消息响应"""
    id: str = Field(..., description="消息ID")
    session_id: str = Field(..., description="会话ID")
    content: str = Field(..., description="消息内容")
    message_type: MessageType = Field(..., description="消息类型")
    status: MessageStatus = Field(..., description="消息状态")
    
    # 附件信息
    attachments: List[Dict[str, Any]] = Field(..., description="附件列表")
    
    # 工具调用信息
    tool_calls: List[Dict[str, Any]] = Field(..., description="工具调用列表")
    
    # 统计信息
    token_count: Optional[int] = Field(None, description="Token数量")
    processing_time_ms: Optional[int] = Field(None, description="处理时间(毫秒)")
    
    # 时间信息
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    # 元数据
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


class ChatResponse(BaseSchema):
    """聊天响应"""
    session_id: str = Field(..., description="会话ID")
    message_id: str = Field(..., description="消息ID")
    content: str = Field(..., description="回复内容")
    message_type: MessageType = Field(..., description="消息类型")
    
    # 工具调用信息
    tool_calls: List[Dict[str, Any]] = Field(..., description="工具调用列表")
    
    # 统计信息
    input_tokens: int = Field(..., description="输入Token数")
    output_tokens: int = Field(..., description="输出Token数")
    total_tokens: int = Field(..., description="总Token数")
    processing_time_ms: int = Field(..., description="处理时间(毫秒)")
    
    # 时间信息
    timestamp: datetime = Field(..., description="响应时间")
    
    # 其他信息
    model_info: Optional[Dict[str, Any]] = Field(None, description="模型信息")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


class ChatStreamResponse(BaseSchema):
    """流式聊天响应"""
    session_id: str = Field(..., description="会话ID")
    message_id: str = Field(..., description="消息ID")
    delta: str = Field(..., description="增量内容")
    is_finished: bool = Field(..., description="是否完成")
    
    # 工具调用信息
    tool_calls: Optional[List[Dict[str, Any]]] = Field(None, description="工具调用列表")
    
    # 统计信息（仅在完成时提供）
    total_tokens: Optional[int] = Field(None, description="总Token数")
    processing_time_ms: Optional[int] = Field(None, description="处理时间(毫秒)")
    
    # 时间信息
    timestamp: datetime = Field(..., description="响应时间")


class AgentResponse(BaseSchema):
    """智能体响应"""
    id: str = Field(..., description="智能体ID")
    name: str = Field(..., description="智能体名称")
    description: Optional[str] = Field(None, description="智能体描述")
    user_id: str = Field(..., description="创建者用户ID")
    status: AgentStatus = Field(..., description="智能体状态")
    
    # 智能体配置
    system_prompt: Optional[str] = Field(None, description="系统提示词")
    model_config: Optional[Dict[str, Any]] = Field(None, description="模型配置")
    
    # 工具配置
    tools: List[Dict[str, Any]] = Field(..., description="工具列表")
    
    # 知识库配置
    knowledge_base_ids: List[str] = Field(..., description="知识库ID列表")
    
    # 其他配置
    avatar_url: Optional[str] = Field(None, description="头像URL")
    tags: List[str] = Field(..., description="标签列表")
    is_public: bool = Field(..., description="是否公开")
    
    # 统计信息
    session_count: int = Field(..., description="会话数量")
    message_count: int = Field(..., description="消息数量")
    
    # 时间信息
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    last_used_at: Optional[datetime] = Field(None, description="最后使用时间")
    
    # 关联信息
    creator_name: Optional[str] = Field(None, description="创建者名称")
    
    # 元数据
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


# ===== 统一API响应Schema =====

class APIResponse(BaseSchema):
    """统一API响应格式"""
    success: bool = Field(..., description="请求是否成功")
    message: str = Field(default="", description="响应消息")
    data: Optional[Any] = Field(default=None, description="响应数据")
    error_code: Optional[str] = Field(default=None, description="错误代码")
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间")


class PaginatedResponse(BaseSchema):
    """分页响应格式"""
    success: bool = Field(..., description="请求是否成功")
    message: str = Field(default="", description="响应消息")
    data: List[Any] = Field(..., description="数据列表")
    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页大小")
    total_pages: int = Field(..., description="总页数")
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间")


# ===== 健康检查Schema =====

class HealthCheckResponse(BaseSchema):
    """健康检查响应"""
    status: str = Field(..., description="服务状态")
    version: str = Field(..., description="服务版本")
    uptime: float = Field(..., description="运行时间(秒)")
    timestamp: datetime = Field(..., description="检查时间")
    
    # 组件状态
    database: bool = Field(..., description="数据库连接状态")
    redis: bool = Field(..., description="Redis连接状态")
    agno_service: bool = Field(..., description="Agno服务状态")
    
    # 系统指标
    cpu_usage: float = Field(..., description="CPU使用率")
    memory_usage: float = Field(..., description="内存使用率")
    disk_usage: float = Field(..., description="磁盘使用率")
    
    # 服务统计
    total_sessions: int = Field(..., description="会话总数")
    active_sessions: int = Field(..., description="活跃会话数")
    total_messages: int = Field(..., description="消息总数")
    total_agents: int = Field(..., description="智能体总数")
