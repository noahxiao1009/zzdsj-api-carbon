"""
MCP-Service Schema定义
定义MCP服务管理、工具注册、执行记录等相关的Pydantic Schema
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator
import uuid


# ===== 枚举类型定义 =====

class ServiceStatus(str, Enum):
    """服务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    RESTARTING = "restarting"
    TERMINATING = "terminating"


class ServiceType(str, Enum):
    """服务类型枚举"""
    DOCKER = "docker"
    KUBERNETES = "kubernetes"
    CLOUD = "cloud"
    LOCAL = "local"


class ToolStatus(str, Enum):
    """工具状态枚举"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"
    ERROR = "error"


class ExecutionStatus(str, Enum):
    """执行状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class HealthStatus(str, Enum):
    """健康状态枚举"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


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


class ServiceFilterParams(BaseSchema):
    """服务过滤参数"""
    status: Optional[ServiceStatus] = Field(None, description="服务状态过滤")
    service_type: Optional[ServiceType] = Field(None, description="服务类型过滤")
    search: Optional[str] = Field(None, description="搜索关键词")
    created_start: Optional[datetime] = Field(None, description="创建时间起")
    created_end: Optional[datetime] = Field(None, description="创建时间止")


class ToolFilterParams(BaseSchema):
    """工具过滤参数"""
    category: Optional[str] = Field(None, description="工具分类过滤")
    status: Optional[ToolStatus] = Field(None, description="工具状态过滤")
    service_id: Optional[str] = Field(None, description="服务ID过滤")
    search: Optional[str] = Field(None, description="搜索关键词")


# ===== MCP服务配置相关Schema =====

class MCPServiceConfigCreate(BaseSchema):
    """MCP服务配置创建请求"""
    name: str = Field(..., min_length=1, max_length=100, description="服务名称")
    description: Optional[str] = Field(None, description="服务描述")
    service_type: ServiceType = Field(ServiceType.DOCKER, description="服务类型")
    
    # Docker相关配置
    image: Optional[str] = Field(None, description="Docker镜像")
    service_port: Optional[int] = Field(None, ge=1, le=65535, description="服务端口")
    host_port: Optional[int] = Field(None, ge=1, le=65535, description="主机端口")
    deploy_directory: Optional[str] = Field(None, description="部署目录")
    
    # 网络配置
    network_name: Optional[str] = Field(None, description="网络名称")
    ip_address: Optional[str] = Field(None, description="IP地址")
    
    # 配置信息
    settings: Optional[Dict[str, Any]] = Field(default_factory=dict, description="配置设置")
    environment_vars: Optional[Dict[str, str]] = Field(default_factory=dict, description="环境变量")
    
    # 资源限制
    cpu_limit: Optional[str] = Field(None, description="CPU限制")
    memory_limit: Optional[str] = Field(None, description="内存限制")
    disk_limit: Optional[str] = Field(None, description="磁盘限制")
    
    # 健康检查配置
    health_check_url: Optional[str] = Field(None, description="健康检查URL")
    health_check_interval: Optional[int] = Field(30, ge=5, description="健康检查间隔(秒)")
    health_check_timeout: Optional[int] = Field(10, ge=1, description="健康检查超时(秒)")
    health_check_retries: Optional[int] = Field(3, ge=1, description="健康检查重试次数")


class MCPServiceConfigUpdate(BaseSchema):
    """MCP服务配置更新请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="服务名称")
    description: Optional[str] = Field(None, description="服务描述")
    settings: Optional[Dict[str, Any]] = Field(None, description="配置设置")
    environment_vars: Optional[Dict[str, str]] = Field(None, description="环境变量")
    cpu_limit: Optional[str] = Field(None, description="CPU限制")
    memory_limit: Optional[str] = Field(None, description="内存限制")
    health_check_interval: Optional[int] = Field(None, ge=5, description="健康检查间隔(秒)")
    health_check_timeout: Optional[int] = Field(None, ge=1, description="健康检查超时(秒)")
    health_check_retries: Optional[int] = Field(None, ge=1, description="健康检查重试次数")


class ServiceControlRequest(BaseSchema):
    """服务控制请求"""
    action: str = Field(..., regex="^(start|stop|restart|terminate)$", description="控制动作")
    force: Optional[bool] = Field(False, description="强制执行")
    timeout: Optional[int] = Field(60, ge=1, description="超时时间(秒)")


# ===== MCP工具相关Schema =====

class MCPToolCreate(BaseSchema):
    """MCP工具创建请求"""
    service_id: str = Field(..., description="所属服务ID")
    name: str = Field(..., min_length=1, max_length=100, description="工具名称")
    description: Optional[str] = Field(None, description="工具描述")
    category: Optional[str] = Field("general", description="工具分类")
    version: Optional[str] = Field("1.0.0", description="工具版本")
    
    # 工具Schema配置
    parameters_schema: Optional[Dict[str, Any]] = Field(None, description="参数Schema")
    return_schema: Optional[Dict[str, Any]] = Field(None, description="返回值Schema")
    tags: Optional[List[str]] = Field(default_factory=list, description="标签列表")
    
    # 工具状态配置
    is_enabled: Optional[bool] = Field(True, description="是否启用")
    is_deprecated: Optional[bool] = Field(False, description="是否废弃")
    
    # 缓存配置
    cache_enabled: Optional[bool] = Field(True, description="是否启用缓存")
    cache_ttl: Optional[int] = Field(1800, ge=60, description="缓存TTL(秒)")
    
    # 性能配置
    timeout_seconds: Optional[int] = Field(30, ge=1, description="执行超时(秒)")
    max_retries: Optional[int] = Field(3, ge=0, description="最大重试次数")
    rate_limit_per_minute: Optional[int] = Field(None, ge=1, description="每分钟调用限制")


class MCPToolUpdate(BaseSchema):
    """MCP工具更新请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="工具名称")
    description: Optional[str] = Field(None, description="工具描述")
    category: Optional[str] = Field(None, description="工具分类")
    version: Optional[str] = Field(None, description="工具版本")
    parameters_schema: Optional[Dict[str, Any]] = Field(None, description="参数Schema")
    return_schema: Optional[Dict[str, Any]] = Field(None, description="返回值Schema")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    is_enabled: Optional[bool] = Field(None, description="是否启用")
    is_deprecated: Optional[bool] = Field(None, description="是否废弃")
    cache_enabled: Optional[bool] = Field(None, description="是否启用缓存")
    cache_ttl: Optional[int] = Field(None, ge=60, description="缓存TTL(秒)")
    timeout_seconds: Optional[int] = Field(None, ge=1, description="执行超时(秒)")
    max_retries: Optional[int] = Field(None, ge=0, description="最大重试次数")
    rate_limit_per_minute: Optional[int] = Field(None, ge=1, description="每分钟调用限制")


class ToolExecutionRequest(BaseSchema):
    """工具执行请求"""
    tool_id: str = Field(..., description="工具ID")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="执行参数")
    user_id: Optional[str] = Field(None, description="用户ID")
    session_id: Optional[str] = Field(None, description="会话ID")
    timeout: Optional[int] = Field(None, ge=1, description="执行超时(秒)")
    use_cache: Optional[bool] = Field(True, description="是否使用缓存")


# ===== 工具执行记录相关Schema =====

class ExecutionLogCreate(BaseSchema):
    """执行日志创建请求"""
    tool_id: str = Field(..., description="工具ID")
    execution_id: str = Field(..., description="执行ID")
    user_id: Optional[str] = Field(None, description="用户ID")
    session_id: Optional[str] = Field(None, description="会话ID")
    parameters: Optional[Dict[str, Any]] = Field(None, description="执行参数")
    status: ExecutionStatus = Field(..., description="执行状态")
    result: Optional[Dict[str, Any]] = Field(None, description="执行结果")
    error_message: Optional[str] = Field(None, description="错误信息")
    execution_time_ms: Optional[int] = Field(None, ge=0, description="执行时间(毫秒)")
    cache_hit: Optional[bool] = Field(False, description="是否命中缓存")


# ===== 响应Schema =====

class MCPServiceConfigResponse(BaseSchema):
    """MCP服务配置响应"""
    id: int = Field(..., description="配置ID")
    deployment_id: str = Field(..., description="部署ID")
    name: str = Field(..., description="服务名称")
    description: Optional[str] = Field(None, description="服务描述")
    service_type: ServiceType = Field(..., description="服务类型")
    status: ServiceStatus = Field(..., description="服务状态")
    
    # Docker相关信息
    image: Optional[str] = Field(None, description="Docker镜像")
    container_id: Optional[str] = Field(None, description="容器ID")
    service_port: Optional[int] = Field(None, description="服务端口")
    host_port: Optional[int] = Field(None, description="主机端口")
    deploy_directory: Optional[str] = Field(None, description="部署目录")
    
    # 网络配置
    network_name: Optional[str] = Field(None, description="网络名称")
    ip_address: Optional[str] = Field(None, description="IP地址")
    
    # 配置信息
    settings: Optional[Dict[str, Any]] = Field(None, description="配置设置")
    environment_vars: Optional[Dict[str, str]] = Field(None, description="环境变量")
    
    # 资源限制
    cpu_limit: Optional[str] = Field(None, description="CPU限制")
    memory_limit: Optional[str] = Field(None, description="内存限制")
    disk_limit: Optional[str] = Field(None, description="磁盘限制")
    
    # 健康检查
    health_check_url: Optional[str] = Field(None, description="健康检查URL")
    health_check_interval: int = Field(..., description="健康检查间隔(秒)")
    health_check_timeout: int = Field(..., description="健康检查超时(秒)")
    health_check_retries: int = Field(..., description="健康检查重试次数")
    
    # 时间信息
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    started_at: Optional[datetime] = Field(None, description="启动时间")
    stopped_at: Optional[datetime] = Field(None, description="停止时间")
    
    # 关联信息
    tools_count: Optional[int] = Field(None, description="工具数量")
    execution_count: Optional[int] = Field(None, description="执行次数")


class MCPToolResponse(BaseSchema):
    """MCP工具响应"""
    id: int = Field(..., description="工具ID")
    service_id: int = Field(..., description="所属服务ID")
    name: str = Field(..., description="工具名称")
    description: Optional[str] = Field(None, description="工具描述")
    category: str = Field(..., description="工具分类")
    version: Optional[str] = Field(None, description="工具版本")
    
    # 工具Schema配置
    parameters_schema: Optional[Dict[str, Any]] = Field(None, description="参数Schema")
    return_schema: Optional[Dict[str, Any]] = Field(None, description="返回值Schema")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    
    # 工具状态
    is_enabled: bool = Field(..., description="是否启用")
    is_deprecated: bool = Field(..., description="是否废弃")
    
    # 缓存配置
    cache_enabled: bool = Field(..., description="是否启用缓存")
    cache_ttl: int = Field(..., description="缓存TTL(秒)")
    
    # 性能配置
    timeout_seconds: int = Field(..., description="执行超时(秒)")
    max_retries: int = Field(..., description="最大重试次数")
    rate_limit_per_minute: Optional[int] = Field(None, description="每分钟调用限制")
    
    # 统计信息
    total_calls: int = Field(..., description="总调用次数")
    success_calls: int = Field(..., description="成功调用次数")
    error_calls: int = Field(..., description="错误调用次数")
    avg_response_time: Optional[float] = Field(None, description="平均响应时间(毫秒)")
    
    # 时间信息
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    last_used_at: Optional[datetime] = Field(None, description="最后使用时间")


class ExecutionLogResponse(BaseSchema):
    """执行日志响应"""
    id: int = Field(..., description="日志ID")
    tool_id: int = Field(..., description="工具ID")
    execution_id: str = Field(..., description="执行ID")
    user_id: Optional[str] = Field(None, description="用户ID")
    session_id: Optional[str] = Field(None, description="会话ID")
    parameters: Optional[Dict[str, Any]] = Field(None, description="执行参数")
    status: ExecutionStatus = Field(..., description="执行状态")
    result: Optional[Dict[str, Any]] = Field(None, description="执行结果")
    error_message: Optional[str] = Field(None, description="错误信息")
    execution_time_ms: Optional[int] = Field(None, description="执行时间(毫秒)")
    cache_hit: bool = Field(..., description="是否命中缓存")
    created_at: datetime = Field(..., description="创建时间")
    
    # 关联信息
    tool_name: Optional[str] = Field(None, description="工具名称")
    service_name: Optional[str] = Field(None, description="服务名称")


class ToolExecutionResponse(BaseSchema):
    """工具执行响应"""
    execution_id: str = Field(..., description="执行ID")
    tool_id: int = Field(..., description="工具ID")
    tool_name: str = Field(..., description="工具名称")
    status: ExecutionStatus = Field(..., description="执行状态")
    result: Optional[Dict[str, Any]] = Field(None, description="执行结果")
    error_message: Optional[str] = Field(None, description="错误信息")
    execution_time_ms: int = Field(..., description="执行时间(毫秒)")
    cache_hit: bool = Field(..., description="是否命中缓存")
    started_at: datetime = Field(..., description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")


# ===== 健康检查相关Schema =====

class ServiceHealthCheckResponse(BaseSchema):
    """服务健康检查响应"""
    service_id: int = Field(..., description="服务ID")
    service_name: str = Field(..., description="服务名称")
    status: HealthStatus = Field(..., description="健康状态")
    last_check_at: datetime = Field(..., description="最后检查时间")
    response_time_ms: Optional[int] = Field(None, description="响应时间(毫秒)")
    error_message: Optional[str] = Field(None, description="错误信息")
    
    # 详细指标
    cpu_usage: Optional[float] = Field(None, description="CPU使用率")
    memory_usage: Optional[float] = Field(None, description="内存使用率")
    disk_usage: Optional[float] = Field(None, description="磁盘使用率")
    
    # 服务统计
    active_tools: int = Field(..., description="活跃工具数")
    total_executions: int = Field(..., description="总执行次数")
    recent_errors: int = Field(..., description="近期错误数")


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


# ===== 整体健康检查Schema =====

class HealthCheckResponse(BaseSchema):
    """健康检查响应"""
    status: str = Field(..., description="服务状态")
    version: str = Field(..., description="服务版本")
    uptime: float = Field(..., description="运行时间(秒)")
    timestamp: datetime = Field(..., description="检查时间")
    
    # 组件状态
    database: bool = Field(..., description="数据库连接状态")
    redis: bool = Field(..., description="Redis连接状态")
    
    # 系统指标
    cpu_usage: float = Field(..., description="CPU使用率")
    memory_usage: float = Field(..., description="内存使用率")
    disk_usage: float = Field(..., description="磁盘使用率")
    
    # 服务统计
    total_services: int = Field(..., description="服务总数")
    running_services: int = Field(..., description="运行中服务数")
    total_tools: int = Field(..., description="工具总数")
    active_tools: int = Field(..., description="活跃工具数")
    total_executions: int = Field(..., description="总执行次数")
