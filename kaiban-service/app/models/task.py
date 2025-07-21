"""
任务模型 - 工作流中的基本执行单元模型
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


class TaskStatus(str, Enum):
    """任务状态枚举"""
    TODO = "todo"             # 待办
    IN_PROGRESS = "in_progress"  # 进行中
    REVIEW = "review"         # 审核中
    BLOCKED = "blocked"       # 被阻塞
    DONE = "done"            # 已完成
    CANCELLED = "cancelled"   # 已取消


class TaskPriority(str, Enum):
    """任务优先级枚举"""
    LOW = "low"              # 低
    MEDIUM = "medium"        # 中
    HIGH = "high"           # 高
    URGENT = "urgent"       # 紧急


class TaskType(str, Enum):
    """任务类型枚举"""
    USER_INPUT = "user_input"      # 用户输入
    AI_PROCESS = "ai_process"      # AI处理
    HUMAN_REVIEW = "human_review"  # 人工审核
    SYSTEM_TASK = "system_task"    # 系统任务
    INTEGRATION = "integration"    # 集成任务


class Task(Base):
    """任务主表"""
    __tablename__ = "tasks"
    
    # 基础字段
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=False)
    stage_id = Column(UUID(as_uuid=True), ForeignKey("workflow_stages.id"), nullable=False)
    board_id = Column(UUID(as_uuid=True), ForeignKey("boards.id"), nullable=True)
    column_id = Column(UUID(as_uuid=True), ForeignKey("board_columns.id"), nullable=True)
    parent_task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True)
    
    # 任务属性
    title = Column(String(255), nullable=False, comment="任务标题")
    description = Column(Text, comment="任务描述")
    task_type = Column(String(50), default=TaskType.AI_PROCESS, comment="任务类型")
    
    # 状态管理
    status = Column(String(50), default=TaskStatus.TODO, comment="任务状态")
    priority = Column(String(50), default=TaskPriority.MEDIUM, comment="任务优先级")
    progress = Column(Float, default=0.0, comment="任务进度(0-100)")
    
    # 分配信息
    assigned_role_id = Column(UUID(as_uuid=True), ForeignKey("workflow_roles.id"), nullable=True)
    assignee = Column(String(255), comment="指派人")
    
    # 任务数据
    input_data = Column(JSONB, comment="输入数据")
    output_data = Column(JSONB, comment="输出数据")
    context_data = Column(JSONB, comment="上下文数据")
    config = Column(JSONB, comment="任务配置")
    
    # 执行信息
    execution_info = Column(JSONB, comment="执行信息")
    error_info = Column(JSONB, comment="错误信息")
    retry_count = Column(Integer, default=0, comment="重试次数")
    max_retries = Column(Integer, default=3, comment="最大重试次数")
    
    # 时间管理
    estimated_duration = Column(Integer, comment="预估时长(分钟)")
    actual_duration = Column(Integer, comment="实际时长(分钟)")
    due_date = Column(DateTime, comment="截止时间")
    
    # 位置信息（看板中的位置）
    position_index = Column(Integer, comment="位置索引")
    position_x = Column(Float, comment="X坐标")
    position_y = Column(Float, comment="Y坐标")
    
    # 标签和分类
    tags = Column(JSONB, comment="标签")
    labels = Column(JSONB, comment="标签")
    category = Column(String(100), comment="分类")
    
    # 依赖关系
    dependencies = Column(JSONB, comment="依赖任务ID列表")
    blocking_tasks = Column(JSONB, comment="阻塞的任务ID列表")
    
    # 附件和链接
    attachments = Column(JSONB, comment="附件列表")
    links = Column(JSONB, comment="相关链接")
    
    # 评估信息
    complexity_score = Column(Float, comment="复杂度评分")
    confidence_score = Column(Float, comment="置信度评分")
    quality_score = Column(Float, comment="质量评分")
    
    # 时间字段
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
    started_at = Column(DateTime, comment="开始时间")
    completed_at = Column(DateTime, comment="完成时间")
    
    # 关联关系
    workflow = relationship("Workflow")
    stage = relationship("WorkflowStage", back_populates="tasks")
    board = relationship("Board")
    column = relationship("BoardColumn", back_populates="tasks")
    assigned_role = relationship("WorkflowRole", back_populates="tasks")
    parent_task = relationship("Task", remote_side=[id])
    subtasks = relationship("Task", back_populates="parent_task")
    comments = relationship("TaskComment", back_populates="task", cascade="all, delete-orphan")
    activities = relationship("TaskActivity", back_populates="task", cascade="all, delete-orphan")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": str(self.id),
            "workflow_id": str(self.workflow_id),
            "stage_id": str(self.stage_id),
            "board_id": str(self.board_id) if self.board_id else None,
            "column_id": str(self.column_id) if self.column_id else None,
            "parent_task_id": str(self.parent_task_id) if self.parent_task_id else None,
            "title": self.title,
            "description": self.description,
            "task_type": self.task_type,
            "status": self.status,
            "priority": self.priority,
            "progress": self.progress,
            "assigned_role_id": str(self.assigned_role_id) if self.assigned_role_id else None,
            "assignee": self.assignee,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "context_data": self.context_data,
            "config": self.config,
            "execution_info": self.execution_info,
            "error_info": self.error_info,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "estimated_duration": self.estimated_duration,
            "actual_duration": self.actual_duration,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "position_index": self.position_index,
            "position_x": self.position_x,
            "position_y": self.position_y,
            "tags": self.tags,
            "labels": self.labels,
            "category": self.category,
            "dependencies": self.dependencies,
            "blocking_tasks": self.blocking_tasks,
            "attachments": self.attachments,
            "links": self.links,
            "complexity_score": self.complexity_score,
            "confidence_score": self.confidence_score,
            "quality_score": self.quality_score,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }
    
    def is_ready_to_execute(self) -> bool:
        """检查任务是否可以执行"""
        if self.status != TaskStatus.TODO:
            return False
        
        # 检查依赖任务是否完成
        if self.dependencies:
            # 这里需要查询依赖任务的状态
            # 实际实现中需要在service层处理
            pass
        
        return True
    
    def calculate_duration(self) -> Optional[int]:
        """计算任务实际执行时长"""
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            return int(delta.total_seconds() / 60)  # 返回分钟数
        return None


class TaskComment(Base):
    """任务评论表"""
    __tablename__ = "task_comments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False)
    
    # 评论内容
    content = Column(Text, nullable=False, comment="评论内容")
    comment_type = Column(String(50), default="general", comment="评论类型")
    
    # 作者信息
    author = Column(String(255), comment="作者")
    author_role = Column(String(100), comment="作者角色")
    
    # 状态信息
    is_internal = Column(Boolean, default=False, comment="是否内部评论")
    is_resolved = Column(Boolean, default=False, comment="是否已解决")
    
    # 时间字段
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联关系
    task = relationship("Task", back_populates="comments")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": str(self.id),
            "task_id": str(self.task_id),
            "content": self.content,
            "comment_type": self.comment_type,
            "author": self.author,
            "author_role": self.author_role,
            "is_internal": self.is_internal,
            "is_resolved": self.is_resolved,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class TaskActivity(Base):
    """任务活动记录表"""
    __tablename__ = "task_activities"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False)
    
    # 活动信息
    activity_type = Column(String(50), nullable=False, comment="活动类型")
    action = Column(String(100), nullable=False, comment="动作")
    description = Column(Text, comment="活动描述")
    
    # 变更信息
    old_value = Column(JSONB, comment="旧值")
    new_value = Column(JSONB, comment="新值")
    changes = Column(JSONB, comment="变更内容")
    
    # 操作者信息
    actor = Column(String(255), comment="操作者")
    actor_type = Column(String(50), comment="操作者类型")
    
    # 时间字段
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关联关系
    task = relationship("Task", back_populates="activities")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": str(self.id),
            "task_id": str(self.task_id),
            "activity_type": self.activity_type,
            "action": self.action,
            "description": self.description,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "changes": self.changes,
            "actor": self.actor,
            "actor_type": self.actor_type,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class TaskTemplate(Base):
    """任务模板表"""
    __tablename__ = "task_templates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 模板属性
    name = Column(String(255), nullable=False, comment="模板名称")
    description = Column(Text, comment="模板描述")
    category = Column(String(100), comment="模板分类")
    task_type = Column(String(50), comment="任务类型")
    
    # 模板配置
    template_config = Column(JSONB, comment="模板配置")
    default_config = Column(JSONB, comment="默认配置")
    
    # 预设值
    default_priority = Column(String(50), default=TaskPriority.MEDIUM)
    default_estimated_duration = Column(Integer, comment="默认预估时长")
    
    # 状态控制
    is_public = Column(Boolean, default=True, comment="是否公开")
    is_active = Column(Boolean, default=True, comment="是否激活")
    
    # 使用统计
    usage_count = Column(Integer, default=0, comment="使用次数")
    
    # 时间字段
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "task_type": self.task_type,
            "template_config": self.template_config,
            "default_config": self.default_config,
            "default_priority": self.default_priority,
            "default_estimated_duration": self.default_estimated_duration,
            "is_public": self.is_public,
            "is_active": self.is_active,
            "usage_count": self.usage_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        } 