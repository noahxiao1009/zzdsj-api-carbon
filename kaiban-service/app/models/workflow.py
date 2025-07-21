"""
工作流模型 - 事件驱动工作流的核心数据模型
"""

from sqlalchemy import Column, String, Text, DateTime, JSON, Boolean, Integer, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
import uuid

Base = declarative_base()


class WorkflowStatus(str, Enum):
    """工作流状态枚举"""
    DRAFT = "draft"           # 草稿
    ACTIVE = "active"         # 激活
    PAUSED = "paused"         # 暂停
    COMPLETED = "completed"   # 完成
    FAILED = "failed"         # 失败
    ARCHIVED = "archived"     # 归档


class WorkflowTriggerType(str, Enum):
    """工作流触发类型"""
    MANUAL = "manual"         # 手动触发
    EVENT = "event"           # 事件触发
    SCHEDULE = "schedule"     # 定时触发
    API = "api"              # API触发
    WEBHOOK = "webhook"       # Webhook触发


class Workflow(Base):
    """工作流主表"""
    __tablename__ = "workflows"
    
    # 基础字段
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, comment="工作流名称")
    description = Column(Text, comment="工作流描述")
    version = Column(String(50), default="1.0.0", comment="版本号")
    
    # 状态字段
    status = Column(String(50), default=WorkflowStatus.DRAFT, comment="工作流状态")
    trigger_type = Column(String(50), default=WorkflowTriggerType.MANUAL, comment="触发类型")
    
    # 配置字段
    config = Column(JSONB, comment="工作流配置")
    meta_data = Column(JSONB, comment="元数据")
    
    # 执行统计
    execution_count = Column(Integer, default=0, comment="执行次数")
    success_count = Column(Integer, default=0, comment="成功次数")
    failure_count = Column(Integer, default=0, comment="失败次数")
    
    # 时间字段
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
    last_executed_at = Column(DateTime, comment="最后执行时间")
    
    # 关联关系
    stages = relationship("WorkflowStage", back_populates="workflow", cascade="all, delete-orphan")
    roles = relationship("WorkflowRole", back_populates="workflow", cascade="all, delete-orphan")
    executions = relationship("WorkflowExecution", back_populates="workflow")
    boards = relationship("Board", back_populates="workflow")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "status": self.status,
            "trigger_type": self.trigger_type,
            "config": self.config,
            "metadata": self.meta_data,
            "execution_count": self.execution_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_executed_at": self.last_executed_at.isoformat() if self.last_executed_at else None,
            "stages": [stage.to_dict() for stage in self.stages or []],
            "roles": [role.to_dict() for role in self.roles or []]
        }


class WorkflowStage(Base):
    """工作流阶段表"""
    __tablename__ = "workflow_stages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=False)
    
    name = Column(String(255), nullable=False, comment="阶段名称")
    description = Column(Text, comment="阶段描述")
    order_index = Column(Integer, nullable=False, comment="阶段顺序")
    
    # 阶段配置
    config = Column(JSONB, comment="阶段配置")
    constraints = Column(JSONB, comment="约束条件")
    
    # 状态控制
    is_active = Column(Boolean, default=True, comment="是否激活")
    is_parallel = Column(Boolean, default=False, comment="是否并行执行")
    max_tasks = Column(Integer, default=10, comment="最大任务数")
    
    # 时间字段
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联关系
    workflow = relationship("Workflow", back_populates="stages")
    tasks = relationship("Task", back_populates="stage")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": str(self.id),
            "workflow_id": str(self.workflow_id),
            "name": self.name,
            "description": self.description,
            "order_index": self.order_index,
            "config": self.config,
            "constraints": self.constraints,
            "is_active": self.is_active,
            "is_parallel": self.is_parallel,
            "max_tasks": self.max_tasks,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class WorkflowRole(Base):
    """工作流角色表"""
    __tablename__ = "workflow_roles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=False)
    
    name = Column(String(255), nullable=False, comment="角色名称")
    description = Column(Text, comment="角色描述")
    
    # 角色配置
    capabilities = Column(JSONB, comment="角色能力")
    model_config = Column(JSONB, comment="模型配置")
    tools = Column(JSONB, comment="可用工具")
    
    # 状态控制
    is_active = Column(Boolean, default=True, comment="是否激活")
    priority = Column(Integer, default=0, comment="优先级")
    
    # 时间字段
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联关系
    workflow = relationship("Workflow", back_populates="roles")
    tasks = relationship("Task", back_populates="assigned_role")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": str(self.id),
            "workflow_id": str(self.workflow_id),
            "name": self.name,
            "description": self.description,
            "capabilities": self.capabilities,
            "model_config": self.model_config,
            "tools": self.tools,
            "is_active": self.is_active,
            "priority": self.priority,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class WorkflowExecution(Base):
    """工作流执行记录表"""
    __tablename__ = "workflow_executions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=False)
    
    # 执行信息
    status = Column(String(50), default="running", comment="执行状态")
    input_data = Column(JSONB, comment="输入数据")
    output_data = Column(JSONB, comment="输出数据")
    error_info = Column(JSONB, comment="错误信息")
    
    # 执行统计
    total_tasks = Column(Integer, default=0, comment="总任务数")
    completed_tasks = Column(Integer, default=0, comment="完成任务数")
    failed_tasks = Column(Integer, default=0, comment="失败任务数")
    
    # 时间统计
    started_at = Column(DateTime, default=datetime.utcnow, comment="开始时间")
    completed_at = Column(DateTime, comment="完成时间")
    duration = Column(Integer, comment="执行时长(秒)")
    
    # 触发信息
    trigger_type = Column(String(50), comment="触发类型")
    trigger_data = Column(JSONB, comment="触发数据")
    
    # 关联关系
    workflow = relationship("Workflow", back_populates="executions")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": str(self.id),
            "workflow_id": str(self.workflow_id),
            "status": self.status,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "error_info": self.error_info,
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration": self.duration,
            "trigger_type": self.trigger_type,
            "trigger_data": self.trigger_data
        }


# Pydantic 模型用于 API 请求/响应
from pydantic import BaseModel, Field


class WorkflowStageCreate(BaseModel):
    """工作流阶段创建模型"""
    name: str = Field(..., description="阶段名称")
    description: Optional[str] = Field(None, description="阶段描述")
    order_index: int = Field(..., description="阶段顺序")
    config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="阶段配置")
    constraints: Optional[Dict[str, Any]] = Field(default_factory=dict, description="约束条件")
    is_parallel: bool = Field(False, description="是否并行执行")
    max_tasks: int = Field(10, description="最大任务数")


class WorkflowRoleCreate(BaseModel):
    """工作流角色创建模型"""
    name: str = Field(..., description="角色名称")
    description: Optional[str] = Field(None, description="角色描述")
    capabilities: Optional[Dict[str, Any]] = Field(default_factory=dict, description="角色能力")
    llm_config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="模型配置")
    tools: Optional[List[str]] = Field(default_factory=list, description="可用工具")
    priority: int = Field(0, description="优先级")


class WorkflowCreateRequest(BaseModel):
    """工作流创建请求模型"""
    name: str = Field(..., description="工作流名称")
    description: Optional[str] = Field(None, description="工作流描述")
    trigger_type: WorkflowTriggerType = Field(WorkflowTriggerType.MANUAL, description="触发类型")
    config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="工作流配置")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")
    stages: List[WorkflowStageCreate] = Field(default_factory=list, description="工作流阶段")
    roles: List[WorkflowRoleCreate] = Field(default_factory=list, description="工作流角色")


class WorkflowResponse(BaseModel):
    """工作流响应模型"""
    id: str = Field(..., description="工作流ID")
    name: str = Field(..., description="工作流名称")
    description: Optional[str] = Field(None, description="工作流描述")
    version: str = Field(..., description="版本号")
    status: WorkflowStatus = Field(..., description="工作流状态")
    trigger_type: WorkflowTriggerType = Field(..., description="触发类型")
    config: Optional[Dict[str, Any]] = Field(None, description="工作流配置")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")
    execution_count: int = Field(0, description="执行次数")
    success_count: int = Field(0, description="成功次数")
    failure_count: int = Field(0, description="失败次数")
    created_at: Optional[datetime] = Field(None, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")
    last_executed_at: Optional[datetime] = Field(None, description="最后执行时间")
    stages: List[Dict[str, Any]] = Field(default_factory=list, description="工作流阶段")
    roles: List[Dict[str, Any]] = Field(default_factory=list, description="工作流角色")

    class Config:
        from_attributes = True 