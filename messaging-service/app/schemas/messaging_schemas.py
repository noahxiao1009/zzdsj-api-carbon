"""
Messaging-Service Schema定义
定义消息队列、通知管理、事件处理等相关的Pydantic Schema
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timedelta
from enum import Enum
from pydantic import BaseModel, Field, validator
import uuid


# ===== 枚举类型定义 =====

class MessageStatus(str, Enum):
    """消息状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class MessageType(str, Enum):
    """消息类型枚举"""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    WEBSOCKET = "websocket"
    WEBHOOK = "webhook"
    INTERNAL = "internal"
    BROADCAST = "broadcast"


class MessagePriority(str, Enum):
    """消息优先级枚举"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationType(str, Enum):
    """通知类型枚举"""
    SYSTEM = "system"
    USER = "user"
    TASK = "task"
    ALERT = "alert"
    REMINDER = "reminder"
    MARKETING = "marketing"


class EventType(str, Enum):
    """事件类型枚举"""
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    TASK_CREATED = "task_created"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    CHAT_MESSAGE = "chat_message"
    FILE_UPLOADED = "file_uploaded"
    SYSTEM_ERROR = "system_error"
    CUSTOM = "custom"


class SubscriptionStatus(str, Enum):
    """订阅状态枚举"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"


class QueueType(str, Enum):
    """队列类型枚举"""
    NORMAL = "normal"
    PRIORITY = "priority"
    DELAYED = "delayed"
    DEAD_LETTER = "dead_letter"
    TOPIC = "topic"
    FANOUT = "fanout"


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


class MessageFilterParams(BaseSchema):
    """消息过滤参数"""
    status: Optional[MessageStatus] = Field(None, description="消息状态过滤")
    message_type: Optional[MessageType] = Field(None, description="消息类型过滤")
    priority: Optional[MessagePriority] = Field(None, description="优先级过滤")
    sender_id: Optional[str] = Field(None, description="发送者ID过滤")
    recipient_id: Optional[str] = Field(None, description="接收者ID过滤")
    search: Optional[str] = Field(None, description="搜索关键词")
    created_start: Optional[datetime] = Field(None, description="创建时间起")
    created_end: Optional[datetime] = Field(None, description="创建时间止")


class NotificationFilterParams(BaseSchema):
    """通知过滤参数"""
    notification_type: Optional[NotificationType] = Field(None, description="通知类型过滤")
    user_id: Optional[str] = Field(None, description="用户ID过滤")
    is_read: Optional[bool] = Field(None, description="是否已读过滤")
    search: Optional[str] = Field(None, description="搜索关键词")
    created_start: Optional[datetime] = Field(None, description="创建时间起")
    created_end: Optional[datetime] = Field(None, description="创建时间止")


class EventFilterParams(BaseSchema):
    """事件过滤参数"""
    event_type: Optional[EventType] = Field(None, description="事件类型过滤")
    source_service: Optional[str] = Field(None, description="来源服务过滤")
    user_id: Optional[str] = Field(None, description="用户ID过滤")
    search: Optional[str] = Field(None, description="搜索关键词")
    created_start: Optional[datetime] = Field(None, description="创建时间起")
    created_end: Optional[datetime] = Field(None, description="创建时间止")


# ===== 消息相关Schema =====

class MessageCreate(BaseSchema):
    """消息创建请求"""
    message_type: MessageType = Field(..., description="消息类型")
    priority: Optional[MessagePriority] = Field(MessagePriority.NORMAL, description="优先级")
    
    # 发送方信息
    sender_id: Optional[str] = Field(None, description="发送者ID")
    sender_type: Optional[str] = Field("user", description="发送者类型")
    
    # 接收方信息
    recipient_id: Optional[str] = Field(None, description="接收者ID")
    recipient_type: Optional[str] = Field("user", description="接收者类型")
    recipient_list: Optional[List[str]] = Field(default_factory=list, description="接收者列表")
    
    # 消息内容
    subject: Optional[str] = Field(None, max_length=200, description="消息主题")
    content: str = Field(..., description="消息内容")
    html_content: Optional[str] = Field(None, description="HTML内容")
    attachments: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="附件列表")
    
    # 调度配置
    scheduled_time: Optional[datetime] = Field(None, description="计划发送时间")
    expires_at: Optional[datetime] = Field(None, description="过期时间")
    
    # 消息配置
    template_id: Optional[str] = Field(None, description="模板ID")
    template_variables: Optional[Dict[str, Any]] = Field(default_factory=dict, description="模板变量")
    
    # 其他配置
    tags: Optional[List[str]] = Field(default_factory=list, description="标签列表")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")
    
    # 发送配置
    max_retries: Optional[int] = Field(3, ge=0, description="最大重试次数")
    retry_delay_seconds: Optional[int] = Field(60, ge=1, description="重试延迟(秒)")

    @validator('expires_at')
    def validate_expires_at(cls, v):
        """验证过期时间"""
        if v and v <= datetime.now():
            raise ValueError('过期时间必须在未来')
        return v

    @validator('scheduled_time')
    def validate_scheduled_time(cls, v):
        """验证计划时间"""
        if v and v <= datetime.now():
            raise ValueError('计划时间必须在未来')
        return v


class MessageUpdate(BaseSchema):
    """消息更新请求"""
    status: Optional[MessageStatus] = Field(None, description="消息状态")
    priority: Optional[MessagePriority] = Field(None, description="优先级")
    scheduled_time: Optional[datetime] = Field(None, description="计划发送时间")
    expires_at: Optional[datetime] = Field(None, description="过期时间")
    content: Optional[str] = Field(None, description="消息内容")
    html_content: Optional[str] = Field(None, description="HTML内容")
    attachments: Optional[List[Dict[str, Any]]] = Field(None, description="附件列表")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


class MessageSend(BaseSchema):
    """消息发送请求"""
    message_id: str = Field(..., description="消息ID")
    force: Optional[bool] = Field(False, description="强制发送")
    immediate: Optional[bool] = Field(False, description="立即发送")


class BulkMessageCreate(BaseSchema):
    """批量消息创建请求"""
    message_type: MessageType = Field(..., description="消息类型")
    priority: Optional[MessagePriority] = Field(MessagePriority.NORMAL, description="优先级")
    sender_id: Optional[str] = Field(None, description="发送者ID")
    
    # 批量接收者
    recipient_list: List[str] = Field(..., min_items=1, description="接收者列表")
    
    # 消息内容
    subject: Optional[str] = Field(None, max_length=200, description="消息主题")
    content: str = Field(..., description="消息内容")
    html_content: Optional[str] = Field(None, description="HTML内容")
    
    # 模板配置
    template_id: Optional[str] = Field(None, description="模板ID")
    template_variables: Optional[Dict[str, Any]] = Field(default_factory=dict, description="模板变量")
    
    # 调度配置
    scheduled_time: Optional[datetime] = Field(None, description="计划发送时间")
    
    # 其他配置
    tags: Optional[List[str]] = Field(default_factory=list, description="标签列表")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")


# ===== 通知相关Schema =====

class NotificationCreate(BaseSchema):
    """通知创建请求"""
    notification_type: NotificationType = Field(..., description="通知类型")
    user_id: str = Field(..., description="用户ID")
    
    # 通知内容
    title: str = Field(..., max_length=200, description="通知标题")
    content: str = Field(..., description="通知内容")
    action_url: Optional[str] = Field(None, description="操作链接")
    icon: Optional[str] = Field(None, description="图标")
    
    # 通知配置
    is_persistent: Optional[bool] = Field(True, description="是否持久化")
    auto_read_seconds: Optional[int] = Field(None, ge=1, description="自动标记已读时间(秒)")
    
    # 发送配置
    send_email: Optional[bool] = Field(False, description="是否发送邮件")
    send_sms: Optional[bool] = Field(False, description="是否发送短信")
    send_push: Optional[bool] = Field(True, description="是否发送推送")
    
    # 其他配置
    tags: Optional[List[str]] = Field(default_factory=list, description="标签列表")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")


class NotificationUpdate(BaseSchema):
    """通知更新请求"""
    is_read: Optional[bool] = Field(None, description="是否已读")
    read_at: Optional[datetime] = Field(None, description="阅读时间")
    action_url: Optional[str] = Field(None, description="操作链接")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


class NotificationMarkRead(BaseSchema):
    """通知标记已读请求"""
    notification_ids: List[str] = Field(..., min_items=1, description="通知ID列表")
    mark_all: Optional[bool] = Field(False, description="标记所有通知")
    user_id: Optional[str] = Field(None, description="用户ID（标记所有时需要）")


# ===== 事件相关Schema =====

class EventCreate(BaseSchema):
    """事件创建请求"""
    event_type: EventType = Field(..., description="事件类型")
    source_service: str = Field(..., description="来源服务")
    
    # 事件内容
    event_data: Dict[str, Any] = Field(..., description="事件数据")
    user_id: Optional[str] = Field(None, description="关联用户ID")
    resource_id: Optional[str] = Field(None, description="关联资源ID")
    resource_type: Optional[str] = Field(None, description="资源类型")
    
    # 事件配置
    correlation_id: Optional[str] = Field(None, description="关联ID")
    trace_id: Optional[str] = Field(None, description="追踪ID")
    
    # 其他配置
    tags: Optional[List[str]] = Field(default_factory=list, description="标签列表")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")


class EventPublish(BaseSchema):
    """事件发布请求"""
    event_type: EventType = Field(..., description="事件类型")
    event_data: Dict[str, Any] = Field(..., description="事件数据")
    target_services: Optional[List[str]] = Field(default_factory=list, description="目标服务列表")
    async_processing: Optional[bool] = Field(True, description="异步处理")


# ===== 订阅相关Schema =====

class SubscriptionCreate(BaseSchema):
    """订阅创建请求"""
    user_id: str = Field(..., description="用户ID")
    service_name: str = Field(..., description="服务名称")
    
    # 订阅配置
    event_types: List[EventType] = Field(..., min_items=1, description="订阅事件类型列表")
    notification_types: List[NotificationType] = Field(..., min_items=1, description="通知类型列表")
    
    # 过滤配置
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="过滤条件")
    
    # 发送配置
    delivery_methods: List[MessageType] = Field(..., min_items=1, description="投递方式列表")
    
    # 其他配置
    is_active: Optional[bool] = Field(True, description="是否激活")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")


class SubscriptionUpdate(BaseSchema):
    """订阅更新请求"""
    event_types: Optional[List[EventType]] = Field(None, description="订阅事件类型列表")
    notification_types: Optional[List[NotificationType]] = Field(None, description="通知类型列表")
    filters: Optional[Dict[str, Any]] = Field(None, description="过滤条件")
    delivery_methods: Optional[List[MessageType]] = Field(None, description="投递方式列表")
    is_active: Optional[bool] = Field(None, description="是否激活")
    status: Optional[SubscriptionStatus] = Field(None, description="订阅状态")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


# ===== 队列相关Schema =====

class QueueCreate(BaseSchema):
    """队列创建请求"""
    name: str = Field(..., min_length=1, max_length=100, description="队列名称")
    queue_type: QueueType = Field(..., description="队列类型")
    description: Optional[str] = Field(None, description="队列描述")
    
    # 队列配置
    max_size: Optional[int] = Field(None, ge=1, description="最大队列大小")
    message_ttl: Optional[int] = Field(None, ge=1, description="消息TTL(秒)")
    max_retries: Optional[int] = Field(3, ge=0, description="最大重试次数")
    
    # 其他配置
    auto_delete: Optional[bool] = Field(False, description="自动删除")
    durable: Optional[bool] = Field(True, description="持久化")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")


class QueueUpdate(BaseSchema):
    """队列更新请求"""
    description: Optional[str] = Field(None, description="队列描述")
    max_size: Optional[int] = Field(None, ge=1, description="最大队列大小")
    message_ttl: Optional[int] = Field(None, ge=1, description="消息TTL(秒)")
    max_retries: Optional[int] = Field(None, ge=0, description="最大重试次数")
    auto_delete: Optional[bool] = Field(None, description="自动删除")
    durable: Optional[bool] = Field(None, description="持久化")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


# ===== 响应Schema =====

class MessageResponse(BaseSchema):
    """消息响应"""
    id: str = Field(..., description="消息ID")
    message_type: MessageType = Field(..., description="消息类型")
    status: MessageStatus = Field(..., description="消息状态")
    priority: MessagePriority = Field(..., description="优先级")
    
    # 发送方信息
    sender_id: Optional[str] = Field(None, description="发送者ID")
    sender_type: str = Field(..., description="发送者类型")
    
    # 接收方信息
    recipient_id: Optional[str] = Field(None, description="接收者ID")
    recipient_type: str = Field(..., description="接收者类型")
    recipient_list: List[str] = Field(..., description="接收者列表")
    
    # 消息内容
    subject: Optional[str] = Field(None, description="消息主题")
    content: str = Field(..., description="消息内容")
    html_content: Optional[str] = Field(None, description="HTML内容")
    attachments: List[Dict[str, Any]] = Field(..., description="附件列表")
    
    # 调度信息
    scheduled_time: Optional[datetime] = Field(None, description="计划发送时间")
    expires_at: Optional[datetime] = Field(None, description="过期时间")
    sent_at: Optional[datetime] = Field(None, description="发送时间")
    delivered_at: Optional[datetime] = Field(None, description="投递时间")
    
    # 消息配置
    template_id: Optional[str] = Field(None, description="模板ID")
    template_variables: Dict[str, Any] = Field(..., description="模板变量")
    
    # 重试信息
    retry_count: int = Field(..., description="重试次数")
    max_retries: int = Field(..., description="最大重试次数")
    last_error: Optional[str] = Field(None, description="最后错误")
    
    # 时间信息
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    # 其他信息
    tags: List[str] = Field(..., description="标签列表")
    metadata: Dict[str, Any] = Field(..., description="元数据")


class NotificationResponse(BaseSchema):
    """通知响应"""
    id: str = Field(..., description="通知ID")
    notification_type: NotificationType = Field(..., description="通知类型")
    user_id: str = Field(..., description="用户ID")
    
    # 通知内容
    title: str = Field(..., description="通知标题")
    content: str = Field(..., description="通知内容")
    action_url: Optional[str] = Field(None, description="操作链接")
    icon: Optional[str] = Field(None, description="图标")
    
    # 通知状态
    is_read: bool = Field(..., description="是否已读")
    read_at: Optional[datetime] = Field(None, description="阅读时间")
    
    # 通知配置
    is_persistent: bool = Field(..., description="是否持久化")
    auto_read_seconds: Optional[int] = Field(None, description="自动标记已读时间(秒)")
    
    # 发送状态
    sent_email: bool = Field(..., description="是否已发送邮件")
    sent_sms: bool = Field(..., description="是否已发送短信")
    sent_push: bool = Field(..., description="是否已发送推送")
    
    # 时间信息
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    # 关联信息
    user_name: Optional[str] = Field(None, description="用户名称")
    
    # 其他信息
    tags: List[str] = Field(..., description="标签列表")
    metadata: Dict[str, Any] = Field(..., description="元数据")


class EventResponse(BaseSchema):
    """事件响应"""
    id: str = Field(..., description="事件ID")
    event_type: EventType = Field(..., description="事件类型")
    source_service: str = Field(..., description="来源服务")
    
    # 事件内容
    event_data: Dict[str, Any] = Field(..., description="事件数据")
    user_id: Optional[str] = Field(None, description="关联用户ID")
    resource_id: Optional[str] = Field(None, description="关联资源ID")
    resource_type: Optional[str] = Field(None, description="资源类型")
    
    # 事件配置
    correlation_id: Optional[str] = Field(None, description="关联ID")
    trace_id: Optional[str] = Field(None, description="追踪ID")
    
    # 处理状态
    processed: bool = Field(..., description="是否已处理")
    processed_at: Optional[datetime] = Field(None, description="处理时间")
    processor_count: int = Field(..., description="处理器数量")
    
    # 时间信息
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    # 关联信息
    user_name: Optional[str] = Field(None, description="用户名称")
    
    # 其他信息
    tags: List[str] = Field(..., description="标签列表")
    metadata: Dict[str, Any] = Field(..., description="元数据")


class SubscriptionResponse(BaseSchema):
    """订阅响应"""
    id: str = Field(..., description="订阅ID")
    user_id: str = Field(..., description="用户ID")
    service_name: str = Field(..., description="服务名称")
    status: SubscriptionStatus = Field(..., description="订阅状态")
    
    # 订阅配置
    event_types: List[EventType] = Field(..., description="订阅事件类型列表")
    notification_types: List[NotificationType] = Field(..., description="通知类型列表")
    
    # 过滤配置
    filters: Dict[str, Any] = Field(..., description="过滤条件")
    
    # 发送配置
    delivery_methods: List[MessageType] = Field(..., description="投递方式列表")
    
    # 统计信息
    message_count: int = Field(..., description="消息数量")
    last_message_at: Optional[datetime] = Field(None, description="最后消息时间")
    
    # 其他配置
    is_active: bool = Field(..., description="是否激活")
    
    # 时间信息
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    # 关联信息
    user_name: Optional[str] = Field(None, description="用户名称")
    
    # 元数据
    metadata: Dict[str, Any] = Field(..., description="元数据")


class QueueResponse(BaseSchema):
    """队列响应"""
    id: str = Field(..., description="队列ID")
    name: str = Field(..., description="队列名称")
    queue_type: QueueType = Field(..., description="队列类型")
    description: Optional[str] = Field(None, description="队列描述")
    
    # 队列配置
    max_size: Optional[int] = Field(None, description="最大队列大小")
    message_ttl: Optional[int] = Field(None, description="消息TTL(秒)")
    max_retries: int = Field(..., description="最大重试次数")
    auto_delete: bool = Field(..., description="自动删除")
    durable: bool = Field(..., description="持久化")
    
    # 队列状态
    message_count: int = Field(..., description="消息数量")
    consumer_count: int = Field(..., description="消费者数量")
    
    # 时间信息
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    # 元数据
    metadata: Dict[str, Any] = Field(..., description="元数据")


# ===== 统计和监控Schema =====

class MessageStatistics(BaseSchema):
    """消息统计信息"""
    total_messages: int = Field(..., description="消息总数")
    pending_messages: int = Field(..., description="待发送消息数")
    sent_messages: int = Field(..., description="已发送消息数")
    failed_messages: int = Field(..., description="失败消息数")
    
    # 按类型统计
    messages_by_type: Dict[str, int] = Field(..., description="按类型统计")
    messages_by_priority: Dict[str, int] = Field(..., description="按优先级统计")
    messages_by_status: Dict[str, int] = Field(..., description="按状态统计")
    
    # 时间统计
    messages_today: int = Field(..., description="今日消息数")
    messages_this_week: int = Field(..., description="本周消息数")
    avg_processing_time: Optional[float] = Field(None, description="平均处理时间(秒)")
    success_rate: Optional[float] = Field(None, description="成功率")


class NotificationStatistics(BaseSchema):
    """通知统计信息"""
    total_notifications: int = Field(..., description="通知总数")
    unread_notifications: int = Field(..., description="未读通知数")
    read_notifications: int = Field(..., description="已读通知数")
    
    # 按类型统计
    notifications_by_type: Dict[str, int] = Field(..., description="按类型统计")
    
    # 时间统计
    notifications_today: int = Field(..., description="今日通知数")
    notifications_this_week: int = Field(..., description="本周通知数")
    avg_read_time: Optional[float] = Field(None, description="平均阅读时间(小时)")


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
    rabbitmq: bool = Field(..., description="RabbitMQ连接状态")
    
    # 系统指标
    cpu_usage: float = Field(..., description="CPU使用率")
    memory_usage: float = Field(..., description="内存使用率")
    disk_usage: float = Field(..., description="磁盘使用率")
    
    # 服务统计
    total_messages: int = Field(..., description="消息总数")
    pending_messages: int = Field(..., description="待处理消息数")
    total_notifications: int = Field(..., description="通知总数")
    unread_notifications: int = Field(..., description="未读通知数")
    active_subscriptions: int = Field(..., description="活跃订阅数")
    queue_count: int = Field(..., description="队列数量")


class EventTypeEnum(str, Enum):
    """事件类型枚举"""
    USER_ACTION = "user_action"
    SERVICE_REQUEST = "service_request"
    SERVICE_RESPONSE = "service_response"
    SYSTEM_EVENT = "system_event"
    ERROR_EVENT = "error_event"
    NOTIFICATION = "notification"
    WEBSOCKET_MESSAGE = "websocket_message"


class MessagePriorityEnum(int, Enum):
    """消息优先级枚举"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class MessageTypeEnum(str, Enum):
    """WebSocket消息类型枚举"""
    CHAT = "chat"
    NOTIFICATION = "notification"
    STATUS_UPDATE = "status_update"
    HEARTBEAT = "heartbeat"
    ERROR = "error"
    SYSTEM = "system"
    USER_ACTION = "user_action"


class BroadcastTargetEnum(str, Enum):
    """广播目标类型"""
    ALL = "all"
    ROOM = "room"
    USER = "user"


# 事件相关模型
class EventRequest(BaseModel):
    """事件发布请求"""
    id: Optional[str] = Field(None, description="事件ID，如果不提供将自动生成")
    type: EventTypeEnum = Field(..., description="事件类型")
    source_service: str = Field(..., description="源服务名称")
    target_service: Optional[str] = Field(None, description="目标服务名称")
    data: Dict[str, Any] = Field(..., description="事件数据")
    priority: MessagePriorityEnum = Field(MessagePriorityEnum.NORMAL, description="消息优先级")
    correlation_id: Optional[str] = Field(None, description="关联ID")
    routing_key: Optional[str] = Field(None, description="路由键")
    
    class Config:
        schema_extra = {
            "example": {
                "type": "user_action",
                "source_service": "chat-service",
                "target_service": "knowledge-service",
                "data": {
                    "action": "create_conversation",
                    "user_id": "user123",
                    "conversation_id": "conv456"
                },
                "priority": 2,
                "correlation_id": "req789"
            }
        }


class EventResponse(BaseModel):
    """事件发布响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    event_id: Optional[str] = Field(None, description="事件ID")
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间")


# WebSocket相关模型
class WebSocketMessageRequest(BaseModel):
    """WebSocket消息请求"""
    type: MessageTypeEnum = Field(..., description="消息类型")
    data: Dict[str, Any] = Field(..., description="消息数据")
    target_id: Optional[str] = Field(None, description="目标客户端ID")
    room: Optional[str] = Field(None, description="房间名称")
    
    class Config:
        schema_extra = {
            "example": {
                "type": "chat",
                "data": {
                    "message": "Hello, world!",
                    "sender": "user123"
                },
                "room": "general"
            }
        }


class WebSocketMessageResponse(BaseModel):
    """WebSocket消息响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    sent_count: int = Field(0, description="发送成功数量")


class BroadcastRequest(BaseModel):
    """广播消息请求"""
    message_type: MessageTypeEnum = Field(..., description="消息类型")
    data: Dict[str, Any] = Field(..., description="消息数据")
    target_type: BroadcastTargetEnum = Field(..., description="广播目标类型")
    target_user_id: Optional[str] = Field(None, description="目标用户ID（当target_type为user时）")
    room: Optional[str] = Field(None, description="房间名称（当target_type为room时）")
    
    @validator('target_user_id')
    def validate_target_user_id(cls, v, values):
        if values.get('target_type') == BroadcastTargetEnum.USER and not v:
            raise ValueError('target_user_id is required when target_type is user')
        return v
    
    @validator('room')
    def validate_room(cls, v, values):
        if values.get('target_type') == BroadcastTargetEnum.ROOM and not v:
            raise ValueError('room is required when target_type is room')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "message_type": "notification",
                "data": {
                    "title": "系统通知",
                    "content": "服务维护将在30分钟后开始"
                },
                "target_type": "all"
            }
        }


class BroadcastResponse(BaseModel):
    """广播消息响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    sent_count: int = Field(0, description="发送成功数量")
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间")


# 服务注册相关模型
class ServiceRegistrationRequest(BaseModel):
    """服务注册请求"""
    service_name: str = Field(..., description="服务名称")
    service_url: str = Field(..., description="服务URL")
    health_check_url: str = Field(..., description="健康检查URL")
    metadata: Optional[Dict[str, Any]] = Field(None, description="服务元数据")
    
    @validator('service_name')
    def validate_service_name(cls, v):
        if not v or not v.strip():
            raise ValueError('service_name cannot be empty')
        return v.strip()
    
    @validator('service_url', 'health_check_url')
    def validate_url(cls, v):
        if not v or not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "service_name": "user-service",
                "service_url": "http://localhost:8010",
                "health_check_url": "http://localhost:8010/health",
                "metadata": {
                    "version": "1.0.0",
                    "environment": "development"
                }
            }
        }


class ServiceRegistrationResponse(BaseModel):
    """服务注册响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    service_name: str = Field(..., description="服务名称")
    timestamp: datetime = Field(default_factory=datetime.now, description="注册时间")


class ServiceInfo(BaseModel):
    """服务信息"""
    name: str = Field(..., description="服务名称")
    url: str = Field(..., description="服务URL")
    health_check_url: str = Field(..., description="健康检查URL")
    registered_at: datetime = Field(..., description="注册时间")
    last_health_check: Optional[datetime] = Field(None, description="最后健康检查时间")
    status: str = Field("unknown", description="服务状态")
    metadata: Optional[Dict[str, Any]] = Field(None, description="服务元数据")


# 连接管理相关模型
class ConnectionInfo(BaseModel):
    """连接信息"""
    client_id: str = Field(..., description="客户端ID")
    user_id: Optional[str] = Field(None, description="用户ID")
    connected_at: datetime = Field(..., description="连接时间")
    last_ping: datetime = Field(..., description="最后心跳时间")
    state: str = Field(..., description="连接状态")
    rooms: List[str] = Field(default_factory=list, description="加入的房间")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="连接元数据")


class RoomInfo(BaseModel):
    """房间信息"""
    room_name: str = Field(..., description="房间名称")
    member_count: int = Field(..., description="成员数量")
    members: List[str] = Field(..., description="成员列表")
    created_at: Optional[datetime] = Field(None, description="创建时间")


class RoomJoinRequest(BaseModel):
    """加入房间请求"""
    client_id: str = Field(..., description="客户端ID")
    room_name: str = Field(..., description="房间名称")
    
    @validator('client_id', 'room_name')
    def validate_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Field cannot be empty')
        return v.strip()


class RoomLeaveRequest(BaseModel):
    """离开房间请求"""
    client_id: str = Field(..., description="客户端ID")
    room_name: str = Field(..., description="房间名称")
    
    @validator('client_id', 'room_name')
    def validate_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Field cannot be empty')
        return v.strip()


# 性能指标相关模型
class MetricsResponse(BaseModel):
    """性能指标响应"""
    message_broker: Dict[str, Any] = Field(..., description="消息代理指标")
    websocket_manager: Dict[str, Any] = Field(..., description="WebSocket管理器指标")
    event_dispatcher: Dict[str, Any] = Field(..., description="事件分发器指标")
    service_registry: Dict[str, Any] = Field(..., description="服务注册器指标")
    timestamp: datetime = Field(default_factory=datetime.now, description="指标时间")


class HealthCheckResponse(BaseModel):
    """健康检查响应"""
    status: str = Field(..., description="健康状态")
    timestamp: float = Field(..., description="检查时间戳")
    components: Dict[str, Any] = Field(..., description="组件状态")
    active_connections: int = Field(..., description="活跃连接数")
    registered_services: int = Field(..., description="已注册服务数")


# 事件历史相关模型
class EventHistoryQuery(BaseModel):
    """事件历史查询"""
    limit: int = Field(100, ge=1, le=1000, description="返回记录数量")
    offset: int = Field(0, ge=0, description="偏移量")
    event_type: Optional[EventTypeEnum] = Field(None, description="事件类型过滤")
    source_service: Optional[str] = Field(None, description="源服务过滤")
    target_service: Optional[str] = Field(None, description="目标服务过滤")
    start_time: Optional[datetime] = Field(None, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    
    @validator('end_time')
    def validate_time_range(cls, v, values):
        start_time = values.get('start_time')
        if start_time and v and v <= start_time:
            raise ValueError('end_time must be after start_time')
        return v


class EventHistoryResponse(BaseModel):
    """事件历史响应"""
    total: int = Field(..., description="总记录数")
    events: List[Dict[str, Any]] = Field(..., description="事件列表")
    limit: int = Field(..., description="返回记录数量")
    offset: int = Field(..., description="偏移量")
    has_more: bool = Field(..., description="是否还有更多记录")


# 错误响应模型
class ErrorResponse(BaseModel):
    """错误响应"""
    detail: str = Field(..., description="错误详情")
    error_code: Optional[str] = Field(None, description="错误代码")
    timestamp: datetime = Field(default_factory=datetime.now, description="错误时间")
    
    class Config:
        schema_extra = {
            "example": {
                "detail": "Service not found",
                "error_code": "SERVICE_NOT_FOUND",
                "timestamp": "2024-01-04T10:30:00Z"
            }
        }
