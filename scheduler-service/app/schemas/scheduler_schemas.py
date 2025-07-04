"""
Scheduler-Service Schema定义
定义任务调度、定时任务、作业管理等相关的Pydantic Schema
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timedelta
from enum import Enum
from pydantic import BaseModel, Field, validator
import uuid


# ===== 枚举类型定义 =====

class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    TIMEOUT = "timeout"


class TaskType(str, Enum):
    """任务类型枚举"""
    IMMEDIATE = "immediate"
    SCHEDULED = "scheduled"
    RECURRING = "recurring"
    CRON = "cron"
    PERIODIC = "periodic"


class TaskPriority(str, Enum):
    """任务优先级枚举"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class JobStatus(str, Enum):
    """作业状态枚举"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    ERROR = "error"


class RecurrenceType(str, Enum):
    """重复类型枚举"""
    ONCE = "once"
    MINUTELY = "minutely"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    CRON = "cron"


class ExecutorType(str, Enum):
    """执行器类型枚举"""
    THREAD = "thread"
    PROCESS = "process"
    CELERY = "celery"
    ASYNCIO = "asyncio"
    KUBERNETES = "kubernetes"


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


class TaskFilterParams(BaseSchema):
    """任务过滤参数"""
    status: Optional[TaskStatus] = Field(None, description="任务状态过滤")
    task_type: Optional[TaskType] = Field(None, description="任务类型过滤")
    priority: Optional[TaskPriority] = Field(None, description="优先级过滤")
    user_id: Optional[str] = Field(None, description="用户ID过滤")
    job_id: Optional[str] = Field(None, description="作业ID过滤")
    search: Optional[str] = Field(None, description="搜索关键词")
    created_start: Optional[datetime] = Field(None, description="创建时间起")
    created_end: Optional[datetime] = Field(None, description="创建时间止")
    scheduled_start: Optional[datetime] = Field(None, description="计划时间起")
    scheduled_end: Optional[datetime] = Field(None, description="计划时间止")


class JobFilterParams(BaseSchema):
    """作业过滤参数"""
    status: Optional[JobStatus] = Field(None, description="作业状态过滤")
    user_id: Optional[str] = Field(None, description="用户ID过滤")
    search: Optional[str] = Field(None, description="搜索关键词")
    created_start: Optional[datetime] = Field(None, description="创建时间起")
    created_end: Optional[datetime] = Field(None, description="创建时间止")


# ===== 任务调度相关Schema =====

class TaskCreate(BaseSchema):
    """任务创建请求"""
    name: str = Field(..., min_length=1, max_length=200, description="任务名称")
    description: Optional[str] = Field(None, description="任务描述")
    task_type: TaskType = Field(..., description="任务类型")
    priority: Optional[TaskPriority] = Field(TaskPriority.NORMAL, description="任务优先级")
    
    # 执行配置
    function_name: str = Field(..., description="执行函数名称")
    module_path: Optional[str] = Field(None, description="模块路径")
    args: Optional[List[Any]] = Field(default_factory=list, description="位置参数")
    kwargs: Optional[Dict[str, Any]] = Field(default_factory=dict, description="关键字参数")
    
    # 调度配置
    scheduled_time: Optional[datetime] = Field(None, description="计划执行时间")
    recurrence_type: Optional[RecurrenceType] = Field(None, description="重复类型")
    cron_expression: Optional[str] = Field(None, description="Cron表达式")
    interval_seconds: Optional[int] = Field(None, ge=1, description="间隔秒数")
    
    # 执行配置
    executor_type: Optional[ExecutorType] = Field(ExecutorType.THREAD, description="执行器类型")
    timeout_seconds: Optional[int] = Field(None, ge=1, description="超时时间(秒)")
    max_retries: Optional[int] = Field(0, ge=0, description="最大重试次数")
    retry_delay_seconds: Optional[int] = Field(60, ge=1, description="重试延迟(秒)")
    
    # 其他配置
    tags: Optional[List[str]] = Field(default_factory=list, description="标签列表")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")
    depends_on: Optional[List[str]] = Field(default_factory=list, description="依赖任务ID列表")
    
    # 用户配置
    user_id: Optional[str] = Field(None, description="创建用户ID")
    job_id: Optional[str] = Field(None, description="所属作业ID")
    
    @validator('cron_expression')
    def validate_cron_expression(cls, v, values):
        """验证Cron表达式"""
        if values.get('recurrence_type') == RecurrenceType.CRON and not v:
            raise ValueError('使用CRON重复类型时必须提供cron_expression')
        return v

    @validator('interval_seconds')
    def validate_interval_seconds(cls, v, values):
        """验证间隔时间"""
        if values.get('recurrence_type') == RecurrenceType.PERIODIC and not v:
            raise ValueError('使用PERIODIC重复类型时必须提供interval_seconds')
        return v

    @validator('scheduled_time')
    def validate_scheduled_time(cls, v, values):
        """验证计划时间"""
        task_type = values.get('task_type')
        if task_type == TaskType.SCHEDULED and not v:
            raise ValueError('计划任务必须提供scheduled_time')
        if v and v <= datetime.now():
            raise ValueError('计划时间必须在未来')
        return v


class TaskUpdate(BaseSchema):
    """任务更新请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=200, description="任务名称")
    description: Optional[str] = Field(None, description="任务描述")
    priority: Optional[TaskPriority] = Field(None, description="任务优先级")
    
    # 调度配置
    scheduled_time: Optional[datetime] = Field(None, description="计划执行时间")
    recurrence_type: Optional[RecurrenceType] = Field(None, description="重复类型")
    cron_expression: Optional[str] = Field(None, description="Cron表达式")
    interval_seconds: Optional[int] = Field(None, ge=1, description="间隔秒数")
    
    # 执行配置
    timeout_seconds: Optional[int] = Field(None, ge=1, description="超时时间(秒)")
    max_retries: Optional[int] = Field(None, ge=0, description="最大重试次数")
    retry_delay_seconds: Optional[int] = Field(None, ge=1, description="重试延迟(秒)")
    
    # 其他配置
    tags: Optional[List[str]] = Field(None, description="标签列表")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")
    depends_on: Optional[List[str]] = Field(None, description="依赖任务ID列表")


class TaskControl(BaseSchema):
    """任务控制请求"""
    action: str = Field(..., regex="^(start|pause|resume|cancel|restart)$", description="控制动作")
    force: Optional[bool] = Field(False, description="强制执行")
    reason: Optional[str] = Field(None, description="操作原因")


# ===== 作业管理相关Schema =====

class JobCreate(BaseSchema):
    """作业创建请求"""
    name: str = Field(..., min_length=1, max_length=200, description="作业名称")
    description: Optional[str] = Field(None, description="作业描述")
    user_id: str = Field(..., description="创建用户ID")
    
    # 作业配置
    max_concurrent_tasks: Optional[int] = Field(5, ge=1, description="最大并发任务数")
    timeout_minutes: Optional[int] = Field(None, ge=1, description="作业超时时间(分钟)")
    
    # 失败策略
    failure_strategy: Optional[str] = Field("abort", description="失败策略(abort/continue/retry)")
    max_failures: Optional[int] = Field(None, ge=1, description="最大失败次数")
    
    # 其他配置
    tags: Optional[List[str]] = Field(default_factory=list, description="标签列表")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")


class JobUpdate(BaseSchema):
    """作业更新请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=200, description="作业名称")
    description: Optional[str] = Field(None, description="作业描述")
    status: Optional[JobStatus] = Field(None, description="作业状态")
    max_concurrent_tasks: Optional[int] = Field(None, ge=1, description="最大并发任务数")
    timeout_minutes: Optional[int] = Field(None, ge=1, description="作业超时时间(分钟)")
    failure_strategy: Optional[str] = Field(None, description="失败策略")
    max_failures: Optional[int] = Field(None, ge=1, description="最大失败次数")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


# ===== 执行记录相关Schema =====

class ExecutionCreate(BaseSchema):
    """执行记录创建请求"""
    task_id: str = Field(..., description="任务ID")
    status: ExecutionStatus = Field(..., description="执行状态")
    started_at: datetime = Field(..., description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    result: Optional[Dict[str, Any]] = Field(None, description="执行结果")
    error_message: Optional[str] = Field(None, description="错误信息")
    execution_time_seconds: Optional[float] = Field(None, ge=0, description="执行时间(秒)")
    retry_count: Optional[int] = Field(0, ge=0, description="重试次数")


# ===== 批量操作Schema =====

class TaskBatchOperation(BaseSchema):
    """任务批量操作请求"""
    task_ids: List[str] = Field(..., min_items=1, description="任务ID列表")
    action: str = Field(..., regex="^(start|pause|resume|cancel|delete)$", description="操作动作")
    force: Optional[bool] = Field(False, description="强制执行")
    reason: Optional[str] = Field(None, description="操作原因")


class JobBatchOperation(BaseSchema):
    """作业批量操作请求"""
    job_ids: List[str] = Field(..., min_items=1, description="作业ID列表")
    action: str = Field(..., regex="^(activate|suspend|complete|delete)$", description="操作动作")
    force: Optional[bool] = Field(False, description="强制执行")
    reason: Optional[str] = Field(None, description="操作原因")


# ===== 响应Schema =====

class TaskResponse(BaseSchema):
    """任务响应"""
    id: str = Field(..., description="任务ID")
    name: str = Field(..., description="任务名称")
    description: Optional[str] = Field(None, description="任务描述")
    task_type: TaskType = Field(..., description="任务类型")
    status: TaskStatus = Field(..., description="任务状态")
    priority: TaskPriority = Field(..., description="任务优先级")
    
    # 执行配置
    function_name: str = Field(..., description="执行函数名称")
    module_path: Optional[str] = Field(None, description="模块路径")
    args: List[Any] = Field(..., description="位置参数")
    kwargs: Dict[str, Any] = Field(..., description="关键字参数")
    
    # 调度配置
    scheduled_time: Optional[datetime] = Field(None, description="计划执行时间")
    recurrence_type: Optional[RecurrenceType] = Field(None, description="重复类型")
    cron_expression: Optional[str] = Field(None, description="Cron表达式")
    interval_seconds: Optional[int] = Field(None, description="间隔秒数")
    
    # 执行配置
    executor_type: ExecutorType = Field(..., description="执行器类型")
    timeout_seconds: Optional[int] = Field(None, description="超时时间(秒)")
    max_retries: int = Field(..., description="最大重试次数")
    retry_delay_seconds: int = Field(..., description="重试延迟(秒)")
    
    # 统计信息
    execution_count: int = Field(..., description="执行次数")
    success_count: int = Field(..., description="成功次数")
    failure_count: int = Field(..., description="失败次数")
    avg_execution_time: Optional[float] = Field(None, description="平均执行时间(秒)")
    
    # 时间信息
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    last_executed_at: Optional[datetime] = Field(None, description="最后执行时间")
    next_run_time: Optional[datetime] = Field(None, description="下次运行时间")
    
    # 其他信息
    tags: List[str] = Field(..., description="标签列表")
    metadata: Dict[str, Any] = Field(..., description="元数据")
    depends_on: List[str] = Field(..., description="依赖任务ID列表")
    
    # 关联信息
    user_id: Optional[str] = Field(None, description="创建用户ID")
    job_id: Optional[str] = Field(None, description="所属作业ID")
    job_name: Optional[str] = Field(None, description="作业名称")
    user_name: Optional[str] = Field(None, description="用户名称")


class JobResponse(BaseSchema):
    """作业响应"""
    id: str = Field(..., description="作业ID")
    name: str = Field(..., description="作业名称")
    description: Optional[str] = Field(None, description="作业描述")
    status: JobStatus = Field(..., description="作业状态")
    user_id: str = Field(..., description="创建用户ID")
    
    # 作业配置
    max_concurrent_tasks: int = Field(..., description="最大并发任务数")
    timeout_minutes: Optional[int] = Field(None, description="作业超时时间(分钟)")
    failure_strategy: str = Field(..., description="失败策略")
    max_failures: Optional[int] = Field(None, description="最大失败次数")
    
    # 统计信息
    task_count: int = Field(..., description="任务总数")
    pending_tasks: int = Field(..., description="待执行任务数")
    running_tasks: int = Field(..., description="运行中任务数")
    completed_tasks: int = Field(..., description="已完成任务数")
    failed_tasks: int = Field(..., description="失败任务数")
    
    # 时间信息
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    started_at: Optional[datetime] = Field(None, description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    
    # 其他信息
    tags: List[str] = Field(..., description="标签列表")
    metadata: Dict[str, Any] = Field(..., description="元数据")
    
    # 关联信息
    user_name: Optional[str] = Field(None, description="用户名称")
    progress_percentage: Optional[float] = Field(None, description="进度百分比")


class ExecutionResponse(BaseSchema):
    """执行记录响应"""
    id: str = Field(..., description="执行记录ID")
    task_id: str = Field(..., description="任务ID")
    status: ExecutionStatus = Field(..., description="执行状态")
    started_at: datetime = Field(..., description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    result: Optional[Dict[str, Any]] = Field(None, description="执行结果")
    error_message: Optional[str] = Field(None, description="错误信息")
    execution_time_seconds: Optional[float] = Field(None, description="执行时间(秒)")
    retry_count: int = Field(..., description="重试次数")
    
    # 关联信息
    task_name: Optional[str] = Field(None, description="任务名称")
    function_name: Optional[str] = Field(None, description="函数名称")
    
    # 时间信息
    created_at: datetime = Field(..., description="创建时间")


# ===== 统计和监控Schema =====

class TaskStatistics(BaseSchema):
    """任务统计信息"""
    total_tasks: int = Field(..., description="任务总数")
    pending_tasks: int = Field(..., description="待执行任务数")
    running_tasks: int = Field(..., description="运行中任务数")
    completed_tasks: int = Field(..., description="已完成任务数")
    failed_tasks: int = Field(..., description="失败任务数")
    
    # 按类型统计
    task_by_type: Dict[str, int] = Field(..., description="按类型统计")
    task_by_priority: Dict[str, int] = Field(..., description="按优先级统计")
    task_by_status: Dict[str, int] = Field(..., description="按状态统计")
    
    # 执行统计
    executions_today: int = Field(..., description="今日执行次数")
    executions_this_week: int = Field(..., description="本周执行次数")
    avg_execution_time: Optional[float] = Field(None, description="平均执行时间(秒)")
    success_rate: Optional[float] = Field(None, description="成功率")


class SystemMetrics(BaseSchema):
    """系统指标"""
    cpu_usage: float = Field(..., description="CPU使用率")
    memory_usage: float = Field(..., description="内存使用率")
    disk_usage: float = Field(..., description="磁盘使用率")
    active_executors: int = Field(..., description="活跃执行器数")
    queue_size: int = Field(..., description="队列大小")
    
    # 调度器状态
    scheduler_status: str = Field(..., description="调度器状态")
    last_heartbeat: datetime = Field(..., description="最后心跳时间")
    uptime_seconds: float = Field(..., description="运行时间(秒)")


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
    scheduler: bool = Field(..., description="调度器状态")
    
    # 系统指标
    cpu_usage: float = Field(..., description="CPU使用率")
    memory_usage: float = Field(..., description="内存使用率")
    disk_usage: float = Field(..., description="磁盘使用率")
    
    # 服务统计
    total_tasks: int = Field(..., description="任务总数")
    running_tasks: int = Field(..., description="运行中任务数")
    total_jobs: int = Field(..., description="作业总数")
    active_jobs: int = Field(..., description="活跃作业数")
    queue_size: int = Field(..., description="队列大小")
