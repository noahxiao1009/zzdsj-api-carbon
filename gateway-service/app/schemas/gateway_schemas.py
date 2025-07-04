"""
Gateway-Service Schema定义
定义网关服务、路由管理、服务注册、负载均衡等相关的Pydantic Schema
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timedelta
from enum import Enum
from pydantic import BaseModel, Field, validator
import uuid


# ===== 枚举类型定义 =====

class ServiceStatus(str, Enum):
    """服务状态枚举"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"


class RouteStatus(str, Enum):
    """路由状态枚举"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    ERROR = "error"


class LoadBalanceType(str, Enum):
    """负载均衡类型枚举"""
    ROUND_ROBIN = "round_robin"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    LEAST_CONNECTIONS = "least_connections"
    IP_HASH = "ip_hash"
    RANDOM = "random"
    CONSISTENT_HASH = "consistent_hash"


class ProtocolType(str, Enum):
    """协议类型枚举"""
    HTTP = "http"
    HTTPS = "https"
    WEBSOCKET = "websocket"
    GRPC = "grpc"
    TCP = "tcp"
    UDP = "udp"


class AuthType(str, Enum):
    """认证类型枚举"""
    NONE = "none"
    BASIC = "basic"
    BEARER = "bearer"
    JWT = "jwt"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    CUSTOM = "custom"


class RateLimitType(str, Enum):
    """限流类型枚举"""
    REQUESTS_PER_SECOND = "requests_per_second"
    REQUESTS_PER_MINUTE = "requests_per_minute"
    REQUESTS_PER_HOUR = "requests_per_hour"
    CONCURRENT_REQUESTS = "concurrent_requests"


class CircuitBreakerState(str, Enum):
    """熔断器状态枚举"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


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
    protocol: Optional[ProtocolType] = Field(None, description="协议类型过滤")
    search: Optional[str] = Field(None, description="搜索关键词")
    tags: Optional[List[str]] = Field(default_factory=list, description="标签过滤")


class RouteFilterParams(BaseSchema):
    """路由过滤参数"""
    status: Optional[RouteStatus] = Field(None, description="路由状态过滤")
    service_name: Optional[str] = Field(None, description="服务名称过滤")
    protocol: Optional[ProtocolType] = Field(None, description="协议类型过滤")
    search: Optional[str] = Field(None, description="搜索关键词")


# ===== 服务注册相关Schema =====

class ServiceRegistration(BaseSchema):
    """服务注册请求"""
    service_name: str = Field(..., min_length=1, max_length=100, description="服务名称")
    service_version: str = Field(..., description="服务版本")
    
    # 服务地址
    host: str = Field(..., description="服务主机")
    port: int = Field(..., ge=1, le=65535, description="服务端口")
    protocol: ProtocolType = Field(..., description="协议类型")
    
    # 健康检查
    health_check_url: Optional[str] = Field(None, description="健康检查URL")
    health_check_interval: Optional[int] = Field(30, ge=5, description="健康检查间隔(秒)")
    health_check_timeout: Optional[int] = Field(10, ge=1, description="健康检查超时(秒)")
    
    # 负载均衡
    weight: Optional[int] = Field(100, ge=1, le=1000, description="权重")
    load_balance_group: Optional[str] = Field(None, description="负载均衡组")
    
    # 元数据
    tags: Optional[List[str]] = Field(default_factory=list, description="标签列表")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")
    
    # 其他配置
    enable_ssl: Optional[bool] = Field(False, description="是否启用SSL")
    timeout_seconds: Optional[int] = Field(30, ge=1, description="超时时间(秒)")
    
    @validator('health_check_url')
    def validate_health_check_url(cls, v, values):
        """验证健康检查URL"""
        if v and not v.startswith(('http://', 'https://')):
            protocol = values.get('protocol')
            if protocol in [ProtocolType.HTTP, ProtocolType.HTTPS]:
                raise ValueError('健康检查URL必须以http://或https://开头')
        return v


class ServiceUpdate(BaseSchema):
    """服务更新请求"""
    service_version: Optional[str] = Field(None, description="服务版本")
    host: Optional[str] = Field(None, description="服务主机")
    port: Optional[int] = Field(None, ge=1, le=65535, description="服务端口")
    health_check_url: Optional[str] = Field(None, description="健康检查URL")
    health_check_interval: Optional[int] = Field(None, ge=5, description="健康检查间隔(秒)")
    health_check_timeout: Optional[int] = Field(None, ge=1, description="健康检查超时(秒)")
    weight: Optional[int] = Field(None, ge=1, le=1000, description="权重")
    load_balance_group: Optional[str] = Field(None, description="负载均衡组")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")
    enable_ssl: Optional[bool] = Field(None, description="是否启用SSL")
    timeout_seconds: Optional[int] = Field(None, ge=1, description="超时时间(秒)")


# ===== 路由配置相关Schema =====

class RouteCreate(BaseSchema):
    """路由创建请求"""
    route_name: str = Field(..., min_length=1, max_length=100, description="路由名称")
    path_pattern: str = Field(..., description="路径模式")
    service_name: str = Field(..., description="目标服务名称")
    
    # 路由配置
    method: Optional[str] = Field("*", description="HTTP方法")
    priority: Optional[int] = Field(100, ge=1, le=1000, description="路由优先级")
    
    # 重写规则
    path_rewrite: Optional[str] = Field(None, description="路径重写")
    add_prefix: Optional[str] = Field(None, description="添加前缀")
    remove_prefix: Optional[str] = Field(None, description="移除前缀")
    
    # 负载均衡
    load_balance_type: Optional[LoadBalanceType] = Field(LoadBalanceType.ROUND_ROBIN, description="负载均衡类型")
    
    # 认证授权
    auth_type: Optional[AuthType] = Field(AuthType.NONE, description="认证类型")
    auth_config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="认证配置")
    
    # 限流配置
    rate_limit_enabled: Optional[bool] = Field(False, description="是否启用限流")
    rate_limit_type: Optional[RateLimitType] = Field(None, description="限流类型")
    rate_limit_value: Optional[int] = Field(None, ge=1, description="限流值")
    
    # 熔断配置
    circuit_breaker_enabled: Optional[bool] = Field(False, description="是否启用熔断")
    circuit_breaker_config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="熔断配置")
    
    # 缓存配置
    cache_enabled: Optional[bool] = Field(False, description="是否启用缓存")
    cache_ttl: Optional[int] = Field(300, ge=60, description="缓存TTL(秒)")
    
    # 其他配置
    timeout_seconds: Optional[int] = Field(30, ge=1, description="超时时间(秒)")
    retry_attempts: Optional[int] = Field(0, ge=0, description="重试次数")
    tags: Optional[List[str]] = Field(default_factory=list, description="标签列表")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")
    
    @validator('path_pattern')
    def validate_path_pattern(cls, v):
        """验证路径模式"""
        if not v.startswith('/'):
            raise ValueError('路径模式必须以/开头')
        return v


class RouteUpdate(BaseSchema):
    """路由更新请求"""
    route_name: Optional[str] = Field(None, min_length=1, max_length=100, description="路由名称")
    path_pattern: Optional[str] = Field(None, description="路径模式")
    service_name: Optional[str] = Field(None, description="目标服务名称")
    method: Optional[str] = Field(None, description="HTTP方法")
    priority: Optional[int] = Field(None, ge=1, le=1000, description="路由优先级")
    path_rewrite: Optional[str] = Field(None, description="路径重写")
    add_prefix: Optional[str] = Field(None, description="添加前缀")
    remove_prefix: Optional[str] = Field(None, description="移除前缀")
    load_balance_type: Optional[LoadBalanceType] = Field(None, description="负载均衡类型")
    auth_type: Optional[AuthType] = Field(None, description="认证类型")
    auth_config: Optional[Dict[str, Any]] = Field(None, description="认证配置")
    rate_limit_enabled: Optional[bool] = Field(None, description="是否启用限流")
    rate_limit_type: Optional[RateLimitType] = Field(None, description="限流类型")
    rate_limit_value: Optional[int] = Field(None, ge=1, description="限流值")
    circuit_breaker_enabled: Optional[bool] = Field(None, description="是否启用熔断")
    circuit_breaker_config: Optional[Dict[str, Any]] = Field(None, description="熔断配置")
    cache_enabled: Optional[bool] = Field(None, description="是否启用缓存")
    cache_ttl: Optional[int] = Field(None, ge=60, description="缓存TTL(秒)")
    timeout_seconds: Optional[int] = Field(None, ge=1, description="超时时间(秒)")
    retry_attempts: Optional[int] = Field(None, ge=0, description="重试次数")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


# ===== 中间件相关Schema =====

class MiddlewareConfig(BaseSchema):
    """中间件配置"""
    name: str = Field(..., description="中间件名称")
    enabled: bool = Field(..., description="是否启用")
    priority: Optional[int] = Field(100, ge=1, le=1000, description="优先级")
    config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="中间件配置")


class GlobalMiddleware(BaseSchema):
    """全局中间件配置"""
    cors_enabled: Optional[bool] = Field(True, description="是否启用CORS")
    cors_config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="CORS配置")
    
    # 日志中间件
    access_log_enabled: Optional[bool] = Field(True, description="是否启用访问日志")
    access_log_format: Optional[str] = Field(None, description="访问日志格式")
    
    # 安全中间件
    security_headers_enabled: Optional[bool] = Field(True, description="是否启用安全头")
    security_headers_config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="安全头配置")
    
    # 压缩中间件
    compression_enabled: Optional[bool] = Field(True, description="是否启用压缩")
    compression_types: Optional[List[str]] = Field(default_factory=list, description="压缩类型")
    
    # 其他中间件
    custom_middlewares: Optional[List[MiddlewareConfig]] = Field(default_factory=list, description="自定义中间件")


# ===== 健康检查相关Schema =====

class HealthCheckConfig(BaseSchema):
    """健康检查配置"""
    enabled: bool = Field(..., description="是否启用健康检查")
    check_interval: int = Field(..., ge=5, description="检查间隔(秒)")
    timeout: int = Field(..., ge=1, description="超时时间(秒)")
    failure_threshold: int = Field(..., ge=1, description="失败阈值")
    success_threshold: int = Field(..., ge=1, description="成功阈值")
    
    # 检查类型
    check_types: List[str] = Field(..., description="检查类型列表")
    
    # 自定义检查
    custom_checks: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="自定义检查")


# ===== 监控告警相关Schema =====

class MetricConfig(BaseSchema):
    """指标配置"""
    enabled: bool = Field(..., description="是否启用指标收集")
    metrics: List[str] = Field(..., description="指标列表")
    export_interval: int = Field(..., ge=5, description="导出间隔(秒)")
    retention_days: int = Field(..., ge=1, description="保留天数")


class AlertRule(BaseSchema):
    """告警规则"""
    name: str = Field(..., description="规则名称")
    metric: str = Field(..., description="监控指标")
    condition: str = Field(..., description="告警条件")
    threshold: float = Field(..., description="告警阈值")
    duration: int = Field(..., ge=60, description="持续时间(秒)")
    severity: str = Field(..., description="告警级别")
    enabled: bool = Field(..., description="是否启用")
    
    # 通知配置
    notification_channels: List[str] = Field(..., description="通知渠道")
    notification_template: Optional[str] = Field(None, description="通知模板")


# ===== 响应Schema =====

class ServiceInstanceResponse(BaseSchema):
    """服务实例响应"""
    id: str = Field(..., description="实例ID")
    service_name: str = Field(..., description="服务名称")
    service_version: str = Field(..., description="服务版本")
    host: str = Field(..., description="服务主机")
    port: int = Field(..., description="服务端口")
    protocol: ProtocolType = Field(..., description="协议类型")
    status: ServiceStatus = Field(..., description="服务状态")
    
    # 健康检查
    health_check_url: Optional[str] = Field(None, description="健康检查URL")
    health_check_interval: int = Field(..., description="健康检查间隔(秒)")
    health_check_timeout: int = Field(..., description="健康检查超时(秒)")
    last_health_check: Optional[datetime] = Field(None, description="最后健康检查时间")
    
    # 负载均衡
    weight: int = Field(..., description="权重")
    load_balance_group: Optional[str] = Field(None, description="负载均衡组")
    
    # 统计信息
    request_count: int = Field(..., description="请求次数")
    error_count: int = Field(..., description="错误次数")
    avg_response_time: Optional[float] = Field(None, description="平均响应时间(毫秒)")
    
    # 时间信息
    registered_at: datetime = Field(..., description="注册时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    # 其他信息
    tags: List[str] = Field(..., description="标签列表")
    metadata: Dict[str, Any] = Field(..., description="元数据")
    enable_ssl: bool = Field(..., description="是否启用SSL")
    timeout_seconds: int = Field(..., description="超时时间(秒)")


class RouteResponse(BaseSchema):
    """路由响应"""
    id: str = Field(..., description="路由ID")
    route_name: str = Field(..., description="路由名称")
    path_pattern: str = Field(..., description="路径模式")
    service_name: str = Field(..., description="目标服务名称")
    status: RouteStatus = Field(..., description="路由状态")
    
    # 路由配置
    method: str = Field(..., description="HTTP方法")
    priority: int = Field(..., description="路由优先级")
    
    # 重写规则
    path_rewrite: Optional[str] = Field(None, description="路径重写")
    add_prefix: Optional[str] = Field(None, description="添加前缀")
    remove_prefix: Optional[str] = Field(None, description="移除前缀")
    
    # 负载均衡
    load_balance_type: LoadBalanceType = Field(..., description="负载均衡类型")
    
    # 认证授权
    auth_type: AuthType = Field(..., description="认证类型")
    auth_config: Dict[str, Any] = Field(..., description="认证配置")
    
    # 限流配置
    rate_limit_enabled: bool = Field(..., description="是否启用限流")
    rate_limit_type: Optional[RateLimitType] = Field(None, description="限流类型")
    rate_limit_value: Optional[int] = Field(None, description="限流值")
    
    # 熔断配置
    circuit_breaker_enabled: bool = Field(..., description="是否启用熔断")
    circuit_breaker_state: Optional[CircuitBreakerState] = Field(None, description="熔断器状态")
    circuit_breaker_config: Dict[str, Any] = Field(..., description="熔断配置")
    
    # 缓存配置
    cache_enabled: bool = Field(..., description="是否启用缓存")
    cache_ttl: Optional[int] = Field(None, description="缓存TTL(秒)")
    cache_hit_rate: Optional[float] = Field(None, description="缓存命中率")
    
    # 统计信息
    request_count: int = Field(..., description="请求次数")
    error_count: int = Field(..., description="错误次数")
    avg_response_time: Optional[float] = Field(None, description="平均响应时间(毫秒)")
    
    # 其他配置
    timeout_seconds: int = Field(..., description="超时时间(秒)")
    retry_attempts: int = Field(..., description="重试次数")
    
    # 时间信息
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    # 其他信息
    tags: List[str] = Field(..., description="标签列表")
    metadata: Dict[str, Any] = Field(..., description="元数据")
    
    # 关联信息
    service_instances: Optional[List[str]] = Field(None, description="服务实例列表")


class GatewayMetrics(BaseSchema):
    """网关指标"""
    # 请求统计
    total_requests: int = Field(..., description="总请求数")
    successful_requests: int = Field(..., description="成功请求数")
    failed_requests: int = Field(..., description="失败请求数")
    
    # 响应时间统计
    avg_response_time: float = Field(..., description="平均响应时间(毫秒)")
    p95_response_time: float = Field(..., description="95%响应时间(毫秒)")
    p99_response_time: float = Field(..., description="99%响应时间(毫秒)")
    
    # 服务统计
    total_services: int = Field(..., description="服务总数")
    healthy_services: int = Field(..., description="健康服务数")
    unhealthy_services: int = Field(..., description="不健康服务数")
    
    # 路由统计
    total_routes: int = Field(..., description="路由总数")
    active_routes: int = Field(..., description="活跃路由数")
    
    # 系统指标
    cpu_usage: float = Field(..., description="CPU使用率")
    memory_usage: float = Field(..., description="内存使用率")
    
    # 网络指标
    bytes_in: int = Field(..., description="入流量(字节)")
    bytes_out: int = Field(..., description="出流量(字节)")
    
    # 时间信息
    timestamp: datetime = Field(..., description="指标时间")


# ===== 配置管理Schema =====

class GatewayConfig(BaseSchema):
    """网关配置"""
    # 基础配置
    listen_port: int = Field(..., ge=1, le=65535, description="监听端口")
    admin_port: int = Field(..., ge=1, le=65535, description="管理端口")
    
    # SSL配置
    ssl_enabled: bool = Field(..., description="是否启用SSL")
    ssl_cert_path: Optional[str] = Field(None, description="SSL证书路径")
    ssl_key_path: Optional[str] = Field(None, description="SSL私钥路径")
    
    # 超时配置
    read_timeout: int = Field(..., ge=1, description="读取超时(秒)")
    write_timeout: int = Field(..., ge=1, description="写入超时(秒)")
    idle_timeout: int = Field(..., ge=1, description="空闲超时(秒)")
    
    # 连接池配置
    max_connections: int = Field(..., ge=1, description="最大连接数")
    max_idle_connections: int = Field(..., ge=1, description="最大空闲连接数")
    connection_timeout: int = Field(..., ge=1, description="连接超时(秒)")
    
    # 中间件配置
    global_middleware: GlobalMiddleware = Field(..., description="全局中间件配置")
    
    # 健康检查配置
    health_check: HealthCheckConfig = Field(..., description="健康检查配置")
    
    # 监控配置
    metrics: MetricConfig = Field(..., description="指标配置")
    
    # 告警配置
    alert_rules: List[AlertRule] = Field(..., description="告警规则列表")


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
    
    # 服务发现状态
    service_discovery: bool = Field(..., description="服务发现状态")
    
    # 系统指标
    cpu_usage: float = Field(..., description="CPU使用率")
    memory_usage: float = Field(..., description="内存使用率")
    disk_usage: float = Field(..., description="磁盘使用率")
    
    # 网关统计
    total_services: int = Field(..., description="服务总数")
    healthy_services: int = Field(..., description="健康服务数")
    total_routes: int = Field(..., description="路由总数")
    active_routes: int = Field(..., description="活跃路由数")
    requests_per_second: float = Field(..., description="每秒请求数")
