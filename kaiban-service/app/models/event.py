"""
事件模型 - 事件驱动系统的核心数据模型
"""

from sqlalchemy import Column, String, Text, DateTime, JSON, Boolean, Integer, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
import uuid

from .workflow import Base


class EventType(str, Enum):
    """事件类型枚举"""
    WORKFLOW_CREATED = "workflow_created"         # 工作流创建
    WORKFLOW_STARTED = "workflow_started"         # 工作流开始
    WORKFLOW_COMPLETED = "workflow_completed"     # 工作流完成
    WORKFLOW_FAILED = "workflow_failed"           # 工作流失败
    WORKFLOW_PAUSED = "workflow_paused"           # 工作流暂停
    WORKFLOW_RESUMED = "workflow_resumed"         # 工作流恢复
    
    TASK_CREATED = "task_created"                 # 任务创建
    TASK_STARTED = "task_started"                 # 任务开始
    TASK_COMPLETED = "task_completed"             # 任务完成
    TASK_FAILED = "task_failed"                   # 任务失败
    TASK_MOVED = "task_moved"                     # 任务移动
    TASK_ASSIGNED = "task_assigned"               # 任务分配
    TASK_UPDATED = "task_updated"                 # 任务更新
    
    USER_INPUT = "user_input"                     # 用户输入
    SYSTEM_NOTIFICATION = "system_notification"   # 系统通知
    INTEGRATION_EVENT = "integration_event"       # 集成事件
    CUSTOM_EVENT = "custom_event"                 # 自定义事件


class EventStatus(str, Enum):
    """事件状态枚举"""
    PENDING = "pending"           # 待处理
    PROCESSING = "processing"     # 处理中
    PROCESSED = "processed"       # 已处理
    FAILED = "failed"            # 处理失败
    CANCELLED = "cancelled"       # 已取消


class EventPriority(str, Enum):
    """事件优先级枚举"""
    LOW = "low"                  # 低
    MEDIUM = "medium"            # 中
    HIGH = "high"               # 高
    URGENT = "urgent"           # 紧急


class Event(Base):
    """事件主表"""
    __tablename__ = "events"
    
    # 基础字段
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 事件属性
    event_type = Column(String(100), nullable=False, comment="事件类型")
    event_name = Column(String(255), comment="事件名称")
    description = Column(Text, comment="事件描述")
    
    # 关联信息
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=True)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True)
    board_id = Column(UUID(as_uuid=True), ForeignKey("boards.id"), nullable=True)
    
    # 事件数据
    event_data = Column(JSONB, comment="事件数据")
    context = Column(JSONB, comment="事件上下文")
    meta_data = Column(JSONB, comment="事件元数据")
    
    # 状态管理
    status = Column(String(50), default=EventStatus.PENDING, comment="事件状态")
    priority = Column(String(50), default=EventPriority.MEDIUM, comment="事件优先级")
    
    # 处理信息
    processed_at = Column(DateTime, comment="处理时间")
    processed_by = Column(String(255), comment="处理者")
    processing_duration = Column(Float, comment="处理时长(秒)")
    result = Column(JSONB, comment="处理结果")
    error_info = Column(JSONB, comment="错误信息")
    
    # 重试信息
    retry_count = Column(Integer, default=0, comment="重试次数")
    max_retries = Column(Integer, default=3, comment="最大重试次数")
    next_retry_at = Column(DateTime, comment="下次重试时间")
    
    # 来源信息
    source = Column(String(255), comment="事件来源")
    source_type = Column(String(50), comment="来源类型")
    correlation_id = Column(String(255), comment="关联ID")
    
    # 传播信息
    is_propagated = Column(Boolean, default=False, comment="是否已传播")
    propagated_to = Column(JSONB, comment="传播目标列表")
    
    # 时间字段
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    scheduled_at = Column(DateTime, comment="计划处理时间")
    expires_at = Column(DateTime, comment="过期时间")
    
    # 关联关系
    workflow = relationship("Workflow")
    task = relationship("Task")
    board = relationship("Board")
    handlers = relationship("EventHandler", back_populates="event")
    subscriptions = relationship("EventSubscription", back_populates="event")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": str(self.id),
            "event_type": self.event_type,
            "event_name": self.event_name,
            "description": self.description,
            "workflow_id": str(self.workflow_id) if self.workflow_id else None,
            "task_id": str(self.task_id) if self.task_id else None,
            "board_id": str(self.board_id) if self.board_id else None,
            "event_data": self.event_data,
            "context": self.context,
            "metadata": self.meta_data,
            "status": self.status,
            "priority": self.priority,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "processed_by": self.processed_by,
            "processing_duration": self.processing_duration,
            "result": self.result,
            "error_info": self.error_info,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "next_retry_at": self.next_retry_at.isoformat() if self.next_retry_at else None,
            "source": self.source,
            "source_type": self.source_type,
            "correlation_id": self.correlation_id,
            "is_propagated": self.is_propagated,
            "propagated_to": self.propagated_to,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None
        }
    
    def is_expired(self) -> bool:
        """检查事件是否已过期"""
        if self.expires_at:
            return datetime.utcnow() > self.expires_at
        return False
    
    def should_retry(self) -> bool:
        """检查是否应该重试"""
        return (self.status == EventStatus.FAILED and 
                self.retry_count < self.max_retries and
                not self.is_expired())


class EventHandler(Base):
    """事件处理器表"""
    __tablename__ = "event_handlers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)
    
    # 处理器信息
    handler_name = Column(String(255), nullable=False, comment="处理器名称")
    handler_type = Column(String(100), comment="处理器类型")
    handler_config = Column(JSONB, comment="处理器配置")
    
    # 执行信息
    execution_order = Column(Integer, default=0, comment="执行顺序")
    status = Column(String(50), default="pending", comment="处理状态")
    started_at = Column(DateTime, comment="开始时间")
    completed_at = Column(DateTime, comment="完成时间")
    duration = Column(Float, comment="执行时长(秒)")
    
    # 结果信息
    result = Column(JSONB, comment="处理结果")
    error_info = Column(JSONB, comment="错误信息")
    
    # 时间字段
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关联关系
    event = relationship("Event", back_populates="handlers")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": str(self.id),
            "event_id": str(self.event_id),
            "handler_name": self.handler_name,
            "handler_type": self.handler_type,
            "handler_config": self.handler_config,
            "execution_order": self.execution_order,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration": self.duration,
            "result": self.result,
            "error_info": self.error_info,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class EventSubscription(Base):
    """事件订阅表"""
    __tablename__ = "event_subscriptions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=True)
    
    # 订阅信息
    subscriber_name = Column(String(255), nullable=False, comment="订阅者名称")
    subscriber_type = Column(String(100), comment="订阅者类型")
    subscription_config = Column(JSONB, comment="订阅配置")
    
    # 过滤条件
    event_type_filter = Column(JSONB, comment="事件类型过滤器")
    data_filter = Column(JSONB, comment="数据过滤器")
    
    # 状态控制
    is_active = Column(Boolean, default=True, comment="是否激活")
    is_paused = Column(Boolean, default=False, comment="是否暂停")
    
    # 统计信息
    events_received = Column(Integer, default=0, comment="接收事件数")
    events_processed = Column(Integer, default=0, comment="处理事件数")
    last_processed_at = Column(DateTime, comment="最后处理时间")
    
    # 时间字段
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, comment="订阅过期时间")
    
    # 关联关系
    event = relationship("Event", back_populates="subscriptions")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": str(self.id),
            "event_id": str(self.event_id) if self.event_id else None,
            "subscriber_name": self.subscriber_name,
            "subscriber_type": self.subscriber_type,
            "subscription_config": self.subscription_config,
            "event_type_filter": self.event_type_filter,
            "data_filter": self.data_filter,
            "is_active": self.is_active,
            "is_paused": self.is_paused,
            "events_received": self.events_received,
            "events_processed": self.events_processed,
            "last_processed_at": self.last_processed_at.isoformat() if self.last_processed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None
        }


class EventRule(Base):
    """事件规则表"""
    __tablename__ = "event_rules"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 规则信息
    name = Column(String(255), nullable=False, comment="规则名称")
    description = Column(Text, comment="规则描述")
    rule_type = Column(String(100), comment="规则类型")
    
    # 触发条件
    trigger_conditions = Column(JSONB, comment="触发条件")
    event_pattern = Column(JSONB, comment="事件模式")
    
    # 执行动作
    actions = Column(JSONB, comment="执行动作")
    action_config = Column(JSONB, comment="动作配置")
    
    # 状态控制
    is_active = Column(Boolean, default=True, comment="是否激活")
    priority = Column(Integer, default=0, comment="优先级")
    
    # 执行统计
    execution_count = Column(Integer, default=0, comment="执行次数")
    success_count = Column(Integer, default=0, comment="成功次数")
    failure_count = Column(Integer, default=0, comment="失败次数")
    last_executed_at = Column(DateTime, comment="最后执行时间")
    
    # 时间字段
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "rule_type": self.rule_type,
            "trigger_conditions": self.trigger_conditions,
            "event_pattern": self.event_pattern,
            "actions": self.actions,
            "action_config": self.action_config,
            "is_active": self.is_active,
            "priority": self.priority,
            "execution_count": self.execution_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "last_executed_at": self.last_executed_at.isoformat() if self.last_executed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class EventLog(Base):
    """事件日志表"""
    __tablename__ = "event_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)
    
    # 日志信息
    log_level = Column(String(20), comment="日志级别")
    message = Column(Text, comment="日志消息")
    details = Column(JSONB, comment="详细信息")
    
    # 来源信息
    source = Column(String(255), comment="日志来源")
    component = Column(String(100), comment="组件名称")
    
    # 时间字段
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关联关系
    event = relationship("Event")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": str(self.id),
            "event_id": str(self.event_id),
            "log_level": self.log_level,
            "message": self.message,
            "details": self.details,
            "source": self.source,
            "component": self.component,
            "created_at": self.created_at.isoformat() if self.created_at else None
        } 