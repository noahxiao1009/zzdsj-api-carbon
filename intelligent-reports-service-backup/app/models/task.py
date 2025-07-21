"""
任务数据模型
"""
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
from sqlalchemy import Column, String, DateTime, Boolean, Text, JSON, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field
from app.models.base import Base, CreateRequestBase, UpdateRequestBase


class TaskStatus(str, Enum):
    """任务状态"""
    NOT_STARTED = "not_started"     # 未开始
    IN_PROGRESS = "in_progress"     # 进行中
    COMPLETED = "completed"         # 已完成
    BLOCKED = "blocked"             # 被阻塞
    CANCELLED = "cancelled"         # 已取消
    FAILED = "failed"               # 失败


class TaskPriority(str, Enum):
    """任务优先级"""
    LOW = "low"          # 低
    MEDIUM = "medium"    # 中
    HIGH = "high"        # 高
    URGENT = "urgent"    # 紧急


class TaskType(str, Enum):
    """任务类型"""
    REPORT_GENERATION = "report_generation"   # 报告生成
    DATA_ANALYSIS = "data_analysis"          # 数据分析
    CONTENT_CREATION = "content_creation"    # 内容创建
    RESEARCH = "research"                    # 研究
    CUSTOM = "custom"                        # 自定义


class TaskModel(Base):
    """任务数据模型"""
    
    __tablename__ = "tasks"
    
    title = Column(String(500), nullable=False, comment="任务标题")
    description = Column(Text, comment="任务描述")
    type = Column(String(50), default=TaskType.CUSTOM, comment="任务类型")
    status = Column(String(50), default=TaskStatus.NOT_STARTED, comment="任务状态")
    priority = Column(String(50), default=TaskPriority.MEDIUM, comment="优先级")
    
    # 计划信息
    steps = Column(JSON, default=list, comment="执行步骤")
    step_statuses = Column(JSON, default=dict, comment="步骤状态")
    step_notes = Column(JSON, default=dict, comment="步骤备注")
    step_details = Column(JSON, default=dict, comment="步骤详情")
    step_files = Column(JSON, default=dict, comment="步骤文件")
    dependencies = Column(JSON, default=dict, comment="依赖关系")
    
    # 执行信息
    input_data = Column(JSON, comment="输入数据")
    output_data = Column(JSON, comment="输出数据")
    result = Column(Text, comment="执行结果")
    error_message = Column(Text, comment="错误信息")
    
    # 时间信息
    started_at = Column(DateTime, comment="开始时间")
    completed_at = Column(DateTime, comment="完成时间")
    estimated_duration = Column(Integer, comment="预估时长(分钟)")
    actual_duration = Column(Integer, comment="实际时长(分钟)")
    
    # 关联信息
    user_id = Column(String(255), nullable=False, comment="用户ID")
    report_id = Column(UUID(as_uuid=True), comment="报告ID")
    agent_id = Column(UUID(as_uuid=True), comment="智能体ID")
    workspace_path = Column(String(500), comment="工作空间路径")
    
    # 配置信息
    configuration = Column(JSON, default=dict, comment="任务配置")
    tags = Column(JSON, default=list, comment="标签")
    
    def __repr__(self):
        return f"<Task {self.title}({self.status})>"
    
    def get_progress(self) -> Dict[str, int]:
        """获取进度统计"""
        if not self.step_statuses:
            return {"total": 0, "completed": 0, "in_progress": 0, "blocked": 0, "not_started": 0}
        
        total = len(self.steps) if self.steps else 0
        statuses = list(self.step_statuses.values()) if self.step_statuses else []
        
        return {
            "total": total,
            "completed": statuses.count("completed"),
            "in_progress": statuses.count("in_progress"),
            "blocked": statuses.count("blocked"),
            "not_started": statuses.count("not_started")
        }
    
    def get_progress_percentage(self) -> float:
        """获取进度百分比"""
        progress = self.get_progress()
        if progress["total"] == 0:
            return 0.0
        return (progress["completed"] / progress["total"]) * 100
    
    def get_ready_steps(self) -> List[int]:
        """获取可执行的步骤索引"""
        if not self.steps or not self.dependencies:
            return []
        
        ready_steps = []
        for step_index in range(len(self.steps)):
            # 获取依赖
            deps = self.dependencies.get(str(step_index), [])
            
            # 检查依赖是否完成
            deps_completed = all(
                self.step_statuses.get(self.steps[int(dep)], "not_started") == "completed"
                for dep in deps
            )
            
            # 检查步骤状态
            step_status = self.step_statuses.get(self.steps[step_index], "not_started")
            
            if deps_completed and step_status == "not_started":
                ready_steps.append(step_index)
        
        return ready_steps
    
    def mark_step(self, step_index: int, status: str, notes: str = None, details: str = None, files: str = None):
        """标记步骤状态"""
        if step_index < 0 or step_index >= len(self.steps):
            raise ValueError(f"步骤索引超出范围: {step_index}")
        
        step = self.steps[step_index]
        
        # 更新状态
        if not self.step_statuses:
            self.step_statuses = {}
        self.step_statuses[step] = status
        
        # 更新备注
        if notes:
            if not self.step_notes:
                self.step_notes = {}
            self.step_notes[step] = notes
        
        # 更新详情
        if details:
            if not self.step_details:
                self.step_details = {}
            self.step_details[step] = details
        
        # 更新文件
        if files:
            if not self.step_files:
                self.step_files = {}
            self.step_files[step] = files
        
        # 更新时间
        self.updated_at = datetime.now()
        
        # 如果是开始执行，设置开始时间
        if status == TaskStatus.IN_PROGRESS and not self.started_at:
            self.started_at = datetime.now()
        
        # 如果是完成，检查是否所有步骤都完成
        if status == TaskStatus.COMPLETED:
            progress = self.get_progress()
            if progress["completed"] == progress["total"]:
                self.status = TaskStatus.COMPLETED
                self.completed_at = datetime.now()
                if self.started_at:
                    duration = (self.completed_at - self.started_at).total_seconds() / 60
                    self.actual_duration = int(duration)
    
    def update_steps(self, steps: List[str], dependencies: Dict[str, List[int]] = None):
        """更新步骤"""
        old_statuses = self.step_statuses or {}
        old_notes = self.step_notes or {}
        old_details = self.step_details or {}
        old_files = self.step_files or {}
        
        # 更新步骤
        self.steps = steps
        
        # 保留已有状态
        new_statuses = {}
        new_notes = {}
        new_details = {}
        new_files = {}
        
        for step in steps:
            new_statuses[step] = old_statuses.get(step, "not_started")
            new_notes[step] = old_notes.get(step, "")
            new_details[step] = old_details.get(step, "")
            new_files[step] = old_files.get(step, "")
        
        self.step_statuses = new_statuses
        self.step_notes = new_notes
        self.step_details = new_details
        self.step_files = new_files
        
        # 更新依赖关系
        if dependencies:
            self.dependencies = dependencies
        else:
            # 默认依赖关系：每个步骤依赖前一个步骤
            self.dependencies = {
                str(i): [i - 1] for i in range(1, len(steps))
            } if len(steps) > 1 else {}
    
    def has_blocked_steps(self) -> bool:
        """检查是否有被阻塞的步骤"""
        if not self.step_statuses:
            return False
        return "blocked" in self.step_statuses.values()
    
    def format_plan(self) -> str:
        """格式化计划显示"""
        output = f"Task: {self.title}\n"
        output += "=" * len(output) + "\n\n"
        
        progress = self.get_progress()
        output += f"Progress: {progress['completed']}/{progress['total']} steps completed "
        if progress['total'] > 0:
            percentage = (progress['completed'] / progress['total']) * 100
            output += f"({percentage:.1f}%)\n"
        else:
            output += "(0%)\n"
        
        output += f"Status: {progress['completed']} completed, {progress['in_progress']} in progress, "
        output += f"{progress['blocked']} blocked, {progress['not_started']} not started\n\n"
        output += "Steps:\n"
        
        for i, step in enumerate(self.steps):
            status_symbol = {
                "not_started": "[ ]",
                "in_progress": "[→]",
                "completed": "[✓]",
                "blocked": "[!]",
            }.get(self.step_statuses.get(step), "[ ]")
            
            # 显示依赖关系
            deps = self.dependencies.get(str(i), [])
            dep_str = f" (depends on: {', '.join(map(str, deps))})" if deps else ""
            output += f"Step{i}: {status_symbol} {step}{dep_str}\n"
            
            if self.step_notes and self.step_notes.get(step):
                output += f"   Notes: {self.step_notes.get(step)}\n"
        
        return output


# Pydantic 模型
class TaskBase(BaseModel):
    """任务基础模型"""
    
    title: str = Field(..., description="任务标题")
    description: Optional[str] = Field(None, description="任务描述")
    type: TaskType = Field(TaskType.CUSTOM, description="任务类型")
    priority: TaskPriority = Field(TaskPriority.MEDIUM, description="优先级")
    
    class Config:
        use_enum_values = True


class TaskCreate(CreateRequestBase, TaskBase):
    """创建任务请求"""
    
    steps: Optional[List[str]] = Field(default_factory=list, description="执行步骤")
    dependencies: Optional[Dict[str, List[int]]] = Field(default_factory=dict, description="依赖关系")
    input_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="输入数据")
    estimated_duration: Optional[int] = Field(None, description="预估时长(分钟)")
    configuration: Optional[Dict[str, Any]] = Field(default_factory=dict, description="任务配置")
    tags: Optional[List[str]] = Field(default_factory=list, description="标签")
    workspace_path: Optional[str] = Field(None, description="工作空间路径")


class TaskUpdate(UpdateRequestBase):
    """更新任务请求"""
    
    title: Optional[str] = Field(None, description="任务标题")
    description: Optional[str] = Field(None, description="任务描述")
    type: Optional[TaskType] = Field(None, description="任务类型")
    priority: Optional[TaskPriority] = Field(None, description="优先级")
    status: Optional[TaskStatus] = Field(None, description="任务状态")
    steps: Optional[List[str]] = Field(None, description="执行步骤")
    dependencies: Optional[Dict[str, List[int]]] = Field(None, description="依赖关系")
    input_data: Optional[Dict[str, Any]] = Field(None, description="输入数据")
    output_data: Optional[Dict[str, Any]] = Field(None, description="输出数据")
    result: Optional[str] = Field(None, description="执行结果")
    estimated_duration: Optional[int] = Field(None, description="预估时长(分钟)")
    configuration: Optional[Dict[str, Any]] = Field(None, description="任务配置")
    tags: Optional[List[str]] = Field(None, description="标签")


class TaskResponse(BaseModel):
    """任务响应模型"""
    
    id: str = Field(..., description="任务ID")
    title: str = Field(..., description="任务标题")
    description: Optional[str] = Field(None, description="任务描述")
    type: TaskType = Field(..., description="任务类型")
    status: TaskStatus = Field(..., description="任务状态")
    priority: TaskPriority = Field(..., description="优先级")
    
    steps: List[str] = Field(default_factory=list, description="执行步骤")
    step_statuses: Dict[str, str] = Field(default_factory=dict, description="步骤状态")
    step_notes: Dict[str, str] = Field(default_factory=dict, description="步骤备注")
    dependencies: Dict[str, List[int]] = Field(default_factory=dict, description="依赖关系")
    
    input_data: Optional[Dict[str, Any]] = Field(None, description="输入数据")
    output_data: Optional[Dict[str, Any]] = Field(None, description="输出数据")
    result: Optional[str] = Field(None, description="执行结果")
    error_message: Optional[str] = Field(None, description="错误信息")
    
    started_at: Optional[datetime] = Field(None, description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    estimated_duration: Optional[int] = Field(None, description="预估时长(分钟)")
    actual_duration: Optional[int] = Field(None, description="实际时长(分钟)")
    
    user_id: str = Field(..., description="用户ID")
    report_id: Optional[str] = Field(None, description="报告ID")
    agent_id: Optional[str] = Field(None, description="智能体ID")
    workspace_path: Optional[str] = Field(None, description="工作空间路径")
    
    configuration: Dict[str, Any] = Field(default_factory=dict, description="任务配置")
    tags: List[str] = Field(default_factory=list, description="标签")
    
    created_at: datetime = Field(..., description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")
    
    @property
    def progress(self) -> Dict[str, int]:
        """进度统计"""
        if not self.step_statuses:
            return {"total": 0, "completed": 0, "in_progress": 0, "blocked": 0, "not_started": 0}
        
        total = len(self.steps)
        statuses = list(self.step_statuses.values())
        
        return {
            "total": total,
            "completed": statuses.count("completed"),
            "in_progress": statuses.count("in_progress"),
            "blocked": statuses.count("blocked"),
            "not_started": statuses.count("not_started")
        }
    
    @property
    def progress_percentage(self) -> float:
        """进度百分比"""
        progress = self.progress
        if progress["total"] == 0:
            return 0.0
        return (progress["completed"] / progress["total"]) * 100
    
    class Config:
        from_attributes = True
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
        }


class TaskExecuteRequest(BaseModel):
    """任务执行请求"""
    
    agent_id: Optional[str] = Field(None, description="指定执行的智能体ID")
    override_config: Optional[Dict[str, Any]] = Field(None, description="覆盖配置")
    async_execution: bool = Field(True, description="是否异步执行")


class TaskExecuteResponse(BaseModel):
    """任务执行响应"""
    
    execution_id: str = Field(..., description="执行ID")
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="执行状态")
    message: str = Field(..., description="消息")


class StepUpdateRequest(BaseModel):
    """步骤更新请求"""
    
    step_index: int = Field(..., description="步骤索引")
    status: TaskStatus = Field(..., description="步骤状态")
    notes: Optional[str] = Field(None, description="步骤备注")
    details: Optional[str] = Field(None, description="步骤详情")
    files: Optional[str] = Field(None, description="步骤文件")


class TaskStatistics(BaseModel):
    """任务统计"""
    
    total_tasks: int = Field(0, description="总任务数")
    completed_tasks: int = Field(0, description="已完成任务数")
    in_progress_tasks: int = Field(0, description="进行中任务数")
    blocked_tasks: int = Field(0, description="被阻塞任务数")
    failed_tasks: int = Field(0, description="失败任务数")
    
    avg_completion_time: Optional[float] = Field(None, description="平均完成时间(分钟)")
    success_rate: float = Field(0.0, description="成功率")
    
    by_type: Dict[str, int] = Field(default_factory=dict, description="按类型统计")
    by_priority: Dict[str, int] = Field(default_factory=dict, description="按优先级统计")
    by_user: Dict[str, int] = Field(default_factory=dict, description="按用户统计")