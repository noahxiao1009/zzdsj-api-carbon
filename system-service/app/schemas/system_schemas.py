"""
System-Service Pydantic Schema定义
定义API请求和响应的数据验证Schema，支持完整的API文档生成
"""

from typing import Dict, List, Any, Optional, Union, Literal
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator, root_validator
import uuid


# ===== 枚举类型定义 =====

class FileStatus(str, Enum):
    """文件状态枚举"""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DELETED = "deleted"


class FileCategory(str, Enum):
    """文件分类枚举"""
    DOCUMENT = "document"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    OTHER = "other"


class UsageType(str, Enum):
    """文件用途类型枚举"""
    KNOWLEDGE = "knowledge"
    SYSTEM = "system"
    TEMPORARY = "temporary"
    BACKUP = "backup"


class StorageBackend(str, Enum):
    """存储后端枚举"""
    MINIO = "minio"
    LOCAL = "local"
    S3 = "s3"
    AZURE = "azure"


class AccessLevel(str, Enum):
    """访问级别枚举"""
    PUBLIC = "public"
    PRIVATE = "private"
    RESTRICTED = "restricted"


class SensitiveWordCategory(str, Enum):
    """敏感词分类枚举"""
    GENERAL = "general"
    POLITICAL = "political"
    VIOLENCE = "violence"
    ADULT = "adult"
    CUSTOM = "custom"


class SeverityLevel(str, Enum):
    """严重级别枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MatchType(str, Enum):
    """匹配类型枚举"""
    EXACT = "exact"
    PARTIAL = "partial"
    REGEX = "regex"
    FUZZY = "fuzzy"


class ReviewStatus(str, Enum):
    """审核状态枚举"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class SearchEngine(str, Enum):
    """搜索引擎枚举"""
    ELASTIC = "elastic"
    WHOOSH = "whoosh"
    CUSTOM = "custom"


class ValueType(str, Enum):
    """配置值类型枚举"""
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    JSON = "json"
    ENCRYPTED = "encrypted"


class VisibleLevel(str, Enum):
    """可见级别枚举"""
    ADMIN = "admin"
    USER = "user"
    PUBLIC = "public"


class ToolType(str, Enum):
    """工具类型枚举"""
    BUILTIN = "builtin"
    CUSTOM = "custom"
    MCP = "mcp"
    EXTERNAL = "external"
    API = "api"


class SourceType(str, Enum):
    """来源类型枚举"""
    INTERNAL = "internal"
    EXTERNAL = "external"
    PLUGIN = "plugin"
    SERVICE = "service"


class ImplementationType(str, Enum):
    """实现类型枚举"""
    PYTHON = "python"
    API = "api"
    MCP = "mcp"
    SHELL = "shell"


class PermissionLevel(str, Enum):
    """权限级别枚举"""
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"
    SYSTEM = "system"


class HealthStatus(str, Enum):
    """健康状态枚举"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ExecutionStatus(str, Enum):
    """执行状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class ExecutionType(str, Enum):
    """执行类型枚举"""
    TOOL_CALL = "tool_call"
    FILE_UPLOAD = "file_upload"
    SENSITIVE_FILTER = "sensitive_filter"
    POLICY_SEARCH = "policy_search"
    CONFIG_UPDATE = "config_update"


# ===== 基础Schema类 =====

class BaseSchema(BaseModel):
    """基础Schema类"""
    class Config:
        use_enum_values = True
        validate_assignment = True


class PaginationParams(BaseSchema):
    """分页参数"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")


class SortParams(BaseSchema):
    """排序参数"""
    sort_by: str = Field(default="created_at", description="排序字段")
    sort_order: Literal["asc", "desc"] = Field(default="desc", description="排序方向")


class APIResponse(BaseSchema):
    """统一API响应格式"""
    success: bool = Field(..., description="请求是否成功")
    message: str = Field(default="", description="响应消息")
    data: Optional[Any] = Field(default=None, description="响应数据")
    error_code: Optional[str] = Field(default=None, description="错误代码")
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间")


class PaginatedResponse(BaseSchema):
    """分页响应格式"""
    items: List[Any] = Field(..., description="数据列表")
    total: int = Field(..., description="总条数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页条数")
    total_pages: int = Field(..., description="总页数")


# ===== 文件管理相关Schema =====

class FileUploadRequest(BaseSchema):
    """文件上传请求"""
    filename: Optional[str] = Field(None, description="文件名")
    file_category: Optional[FileCategory] = Field(None, description="文件分类")
    usage_type: Optional[UsageType] = Field(None, description="用途类型")
    storage_backend: Optional[StorageBackend] = Field(StorageBackend.MINIO, description="存储后端")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")
    access_level: Optional[AccessLevel] = Field(AccessLevel.PRIVATE, description="访问级别")
    is_public: bool = Field(default=False, description="是否公开")


class FileResponse(BaseSchema):
    """文件响应"""
    id: int = Field(..., description="文件ID")
    file_id: str = Field(..., description="文件UUID")
    filename: str = Field(..., description="文件名")
    original_filename: Optional[str] = Field(None, description="原始文件名")
    content_type: Optional[str] = Field(None, description="内容类型")
    file_size: int = Field(..., description="文件大小")
    file_hash: Optional[str] = Field(None, description="文件哈希")
    storage_backend: str = Field(..., description="存储后端")
    storage_path: Optional[str] = Field(None, description="存储路径")
    bucket_name: Optional[str] = Field(None, description="存储桶名称")
    file_category: Optional[str] = Field(None, description="文件分类")
    usage_type: Optional[str] = Field(None, description="用途类型")
    status: str = Field(..., description="状态")
    upload_progress: int = Field(..., description="上传进度")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    access_level: str = Field(..., description="访问级别")
    is_public: bool = Field(..., description="是否公开")
    download_count: int = Field(..., description="下载次数")
    upload_time: datetime = Field(..., description="上传时间")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class FileUpdateRequest(BaseSchema):
    """文件更新请求"""
    filename: Optional[str] = Field(None, description="文件名")
    file_category: Optional[FileCategory] = Field(None, description="文件分类")
    usage_type: Optional[UsageType] = Field(None, description="用途类型")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")
    access_level: Optional[AccessLevel] = Field(None, description="访问级别")
    is_public: Optional[bool] = Field(None, description="是否公开")


class FileListRequest(BaseSchema):
    """文件列表查询请求"""
    file_category: Optional[FileCategory] = Field(None, description="文件分类")
    usage_type: Optional[UsageType] = Field(None, description="用途类型")
    status: Optional[FileStatus] = Field(None, description="状态")
    storage_backend: Optional[StorageBackend] = Field(None, description="存储后端")
    access_level: Optional[AccessLevel] = Field(None, description="访问级别")
    user_id: Optional[str] = Field(None, description="用户ID")
    search: Optional[str] = Field(None, description="搜索关键词")


class FileListResponse(PaginatedResponse):
    """文件列表响应"""
    items: List[FileResponse] = Field(..., description="文件列表")


# ===== 敏感词过滤相关Schema =====

class SensitiveWordCreate(BaseSchema):
    """添加敏感词请求"""
    word: str = Field(..., min_length=1, max_length=200, description="敏感词")
    category: Optional[SensitiveWordCategory] = Field(SensitiveWordCategory.GENERAL, description="分类")
    severity: Optional[SeverityLevel] = Field(SeverityLevel.MEDIUM, description="严重级别")
    language: Optional[str] = Field("zh-CN", description="语言")
    match_type: Optional[MatchType] = Field(MatchType.EXACT, description="匹配类型")
    replacement_text: Optional[str] = Field(None, description="替换文本")
    source: Optional[str] = Field("manual", description="来源")


class SensitiveWordUpdate(BaseSchema):
    """更新敏感词请求"""
    category: Optional[SensitiveWordCategory] = Field(None, description="分类")
    severity: Optional[SeverityLevel] = Field(None, description="严重级别")
    match_type: Optional[MatchType] = Field(None, description="匹配类型")
    replacement_text: Optional[str] = Field(None, description="替换文本")
    is_enabled: Optional[bool] = Field(None, description="是否启用")


class SensitiveWordResponse(BaseSchema):
    """敏感词响应"""
    id: int = Field(..., description="敏感词ID")
    word: str = Field(..., description="敏感词")
    category: str = Field(..., description="分类")
    severity: str = Field(..., description="严重级别")
    language: str = Field(..., description="语言")
    match_type: str = Field(..., description="匹配类型")
    replacement_text: Optional[str] = Field(None, description="替换文本")
    source: str = Field(..., description="来源")
    is_enabled: bool = Field(..., description="是否启用")
    is_system: bool = Field(..., description="是否系统内置")
    hit_count: int = Field(..., description="命中次数")
    review_status: str = Field(..., description="审核状态")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class SensitiveWordListRequest(BaseSchema):
    """敏感词列表查询请求"""
    category: Optional[SensitiveWordCategory] = Field(None, description="分类")
    severity: Optional[SeverityLevel] = Field(None, description="严重级别")
    is_enabled: Optional[bool] = Field(None, description="是否启用")
    language: Optional[str] = Field(None, description="语言")
    search: Optional[str] = Field(None, description="搜索关键词")


class SensitiveWordListResponse(PaginatedResponse):
    """敏感词列表响应"""
    items: List[SensitiveWordResponse] = Field(..., description="敏感词列表")


class ContentFilterRequest(BaseSchema):
    """内容过滤请求"""
    content: str = Field(..., min_length=1, description="待过滤内容")
    filter_categories: Optional[List[SensitiveWordCategory]] = Field(None, description="过滤分类")
    return_details: bool = Field(default=False, description="是否返回详细信息")


class ContentFilterResponse(BaseSchema):
    """内容过滤响应"""
    is_clean: bool = Field(..., description="内容是否干净")
    filtered_content: str = Field(..., description="过滤后内容")
    hit_words: List[str] = Field(default_factory=list, description="命中的敏感词")
    hit_details: Optional[List[Dict[str, Any]]] = Field(None, description="命中详细信息")
    filter_summary: Dict[str, int] = Field(default_factory=dict, description="过滤统计")


# ===== 政策搜索相关Schema =====

class PolicySearchConfigCreate(BaseSchema):
    """创建政策搜索配置请求"""
    name: str = Field(..., min_length=1, max_length=100, description="配置名称")
    description: Optional[str] = Field(None, description="配置描述")
    search_engine: Optional[SearchEngine] = Field(SearchEngine.ELASTIC, description="搜索引擎")
    index_name: Optional[str] = Field(None, description="索引名称")
    data_sources: List[str] = Field(..., description="数据源列表")
    search_fields: List[str] = Field(..., description="搜索字段")
    max_results: Optional[int] = Field(50, ge=1, le=1000, description="最大结果数")
    enable_fuzzy_search: Optional[bool] = Field(True, description="启用模糊搜索")
    cache_enabled: Optional[bool] = Field(True, description="启用缓存")
    cache_ttl: Optional[int] = Field(1800, ge=60, description="缓存TTL")


class PolicySearchConfigUpdate(BaseSchema):
    """更新政策搜索配置请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="配置名称")
    description: Optional[str] = Field(None, description="配置描述")
    data_sources: Optional[List[str]] = Field(None, description="数据源列表")
    search_fields: Optional[List[str]] = Field(None, description="搜索字段")
    max_results: Optional[int] = Field(None, ge=1, le=1000, description="最大结果数")
    enable_fuzzy_search: Optional[bool] = Field(None, description="启用模糊搜索")
    cache_enabled: Optional[bool] = Field(None, description="启用缓存")
    cache_ttl: Optional[int] = Field(None, ge=60, description="缓存TTL")
    is_active: Optional[bool] = Field(None, description="是否激活")


class PolicySearchConfigResponse(BaseSchema):
    """政策搜索配置响应"""
    id: int = Field(..., description="配置ID")
    config_id: str = Field(..., description="配置UUID")
    name: str = Field(..., description="配置名称")
    description: Optional[str] = Field(None, description="配置描述")
    search_engine: str = Field(..., description="搜索引擎")
    index_name: Optional[str] = Field(None, description="索引名称")
    data_sources: List[str] = Field(..., description="数据源列表")
    search_fields: List[str] = Field(..., description="搜索字段")
    max_results: int = Field(..., description="最大结果数")
    enable_fuzzy_search: bool = Field(..., description="启用模糊搜索")
    cache_enabled: bool = Field(..., description="启用缓存")
    cache_ttl: int = Field(..., description="缓存TTL")
    is_active: bool = Field(..., description="是否激活")
    is_default: bool = Field(..., description="是否默认")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class PolicySearchRequest(BaseSchema):
    """政策搜索请求"""
    query: str = Field(..., min_length=1, description="搜索查询")
    config_id: Optional[str] = Field(None, description="配置ID")
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="过滤条件")
    sort_by: Optional[str] = Field(None, description="排序字段")
    sort_order: Optional[Literal["asc", "desc"]] = Field("desc", description="排序方向")
    page: Optional[int] = Field(1, ge=1, description="页码")
    page_size: Optional[int] = Field(20, ge=1, le=100, description="每页条数")


class PolicySearchResultItem(BaseSchema):
    """政策搜索结果项"""
    id: str = Field(..., description="文档ID")
    title: str = Field(..., description="标题")
    content: str = Field(..., description="内容")
    source: str = Field(..., description="来源")
    category: Optional[str] = Field(None, description="分类")
    publish_date: Optional[datetime] = Field(None, description="发布日期")
    score: float = Field(..., description="相关度分数")
    highlights: List[str] = Field(default_factory=list, description="高亮片段")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")


class PolicySearchResponse(BaseSchema):
    """政策搜索响应"""
    query: str = Field(..., description="搜索查询")
    results: List[PolicySearchResultItem] = Field(..., description="搜索结果")
    total: int = Field(..., description="总结果数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页条数")
    search_time: float = Field(..., description="搜索耗时(秒)")
    cached: bool = Field(..., description="是否来自缓存")


# ===== 系统配置相关Schema =====

class SystemConfigCreate(BaseSchema):
    """创建系统配置请求"""
    key: str = Field(..., min_length=1, max_length=255, description="配置键")
    name: str = Field(..., min_length=1, max_length=200, description="配置名称")
    value: Optional[str] = Field(None, description="配置值")
    value_type: Optional[ValueType] = Field(ValueType.STRING, description="值类型")
    default_value: Optional[str] = Field(None, description="默认值")
    category: Optional[str] = Field("general", description="配置分类")
    description: Optional[str] = Field(None, description="配置描述")
    validation_rules: Optional[Dict[str, Any]] = Field(None, description="验证规则")
    is_sensitive: Optional[bool] = Field(False, description="是否敏感")
    is_readonly: Optional[bool] = Field(False, description="是否只读")
    visible_level: Optional[VisibleLevel] = Field(VisibleLevel.ADMIN, description="可见级别")
    requires_restart: Optional[bool] = Field(False, description="是否需要重启")


class SystemConfigUpdate(BaseSchema):
    """更新系统配置请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=200, description="配置名称")
    value: Optional[str] = Field(None, description="配置值")
    description: Optional[str] = Field(None, description="配置描述")
    validation_rules: Optional[Dict[str, Any]] = Field(None, description="验证规则")
    is_readonly: Optional[bool] = Field(None, description="是否只读")
    visible_level: Optional[VisibleLevel] = Field(None, description="可见级别")
    requires_restart: Optional[bool] = Field(None, description="是否需要重启")


class SystemConfigResponse(BaseSchema):
    """系统配置响应"""
    id: int = Field(..., description="配置ID")
    config_id: str = Field(..., description="配置UUID")
    key: str = Field(..., description="配置键")
    name: str = Field(..., description="配置名称")
    value: Optional[str] = Field(None, description="配置值")
    value_type: str = Field(..., description="值类型")
    default_value: Optional[str] = Field(None, description="默认值")
    category: str = Field(..., description="配置分类")
    description: Optional[str] = Field(None, description="配置描述")
    is_system: bool = Field(..., description="是否系统配置")
    is_sensitive: bool = Field(..., description="是否敏感")
    is_readonly: bool = Field(..., description="是否只读")
    visible_level: str = Field(..., description="可见级别")
    requires_restart: bool = Field(..., description="是否需要重启")
    is_overridden: bool = Field(..., description="是否被覆盖")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class SystemConfigListRequest(BaseSchema):
    """系统配置列表查询请求"""
    category: Optional[str] = Field(None, description="配置分类")
    value_type: Optional[ValueType] = Field(None, description="值类型")
    is_system: Optional[bool] = Field(None, description="是否系统配置")
    is_sensitive: Optional[bool] = Field(None, description="是否敏感")
    visible_level: Optional[VisibleLevel] = Field(None, description="可见级别")
    search: Optional[str] = Field(None, description="搜索关键词")


class SystemConfigListResponse(PaginatedResponse):
    """系统配置列表响应"""
    items: List[SystemConfigResponse] = Field(..., description="配置列表")


# ===== 工具注册相关Schema =====

class ToolRegistryCreate(BaseSchema):
    """创建工具注册请求"""
    name: str = Field(..., min_length=1, max_length=100, description="工具名称")
    display_name: Optional[str] = Field(None, description="显示名称")
    description: Optional[str] = Field(None, description="工具描述")
    version: Optional[str] = Field("1.0.0", description="工具版本")
    category: Optional[str] = Field("general", description="工具分类")
    tool_type: ToolType = Field(..., description="工具类型")
    source_type: SourceType = Field(..., description="来源类型")
    implementation_type: Optional[ImplementationType] = Field(ImplementationType.PYTHON, description="实现类型")
    function_schema: Dict[str, Any] = Field(..., description="函数Schema")
    provider: Optional[str] = Field(None, description="提供者")
    module_path: Optional[str] = Field(None, description="模块路径")
    class_name: Optional[str] = Field(None, description="类名")
    function_name: Optional[str] = Field(None, description="函数名")
    config_schema: Optional[Dict[str, Any]] = Field(None, description="配置Schema")
    default_config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="默认配置")
    permission_level: Optional[PermissionLevel] = Field(PermissionLevel.USER, description="权限级别")
    execution_timeout: Optional[int] = Field(30, ge=1, description="执行超时时间")


class ToolRegistryUpdate(BaseSchema):
    """更新工具注册请求"""
    display_name: Optional[str] = Field(None, description="显示名称")
    description: Optional[str] = Field(None, description="工具描述")
    version: Optional[str] = Field(None, description="工具版本")
    category: Optional[str] = Field(None, description="工具分类")
    function_schema: Optional[Dict[str, Any]] = Field(None, description="函数Schema")
    config_schema: Optional[Dict[str, Any]] = Field(None, description="配置Schema")
    default_config: Optional[Dict[str, Any]] = Field(None, description="默认配置")
    is_enabled: Optional[bool] = Field(None, description="是否启用")
    execution_timeout: Optional[int] = Field(None, ge=1, description="执行超时时间")


class ToolRegistryResponse(BaseSchema):
    """工具注册响应"""
    id: int = Field(..., description="工具ID")
    tool_id: str = Field(..., description="工具UUID")
    name: str = Field(..., description="工具名称")
    display_name: Optional[str] = Field(None, description="显示名称")
    description: Optional[str] = Field(None, description="工具描述")
    version: str = Field(..., description="工具版本")
    category: str = Field(..., description="工具分类")
    tool_type: str = Field(..., description="工具类型")
    source_type: str = Field(..., description="来源类型")
    implementation_type: str = Field(..., description="实现类型")
    provider: Optional[str] = Field(None, description="提供者")
    permission_level: str = Field(..., description="权限级别")
    access_level: str = Field(..., description="访问级别")
    is_enabled: bool = Field(..., description="是否启用")
    is_system: bool = Field(..., description="是否系统工具")
    health_status: str = Field(..., description="健康状态")
    total_calls: int = Field(..., description="总调用次数")
    success_calls: int = Field(..., description="成功调用次数")
    error_calls: int = Field(..., description="失败调用次数")
    avg_execution_time: Optional[float] = Field(None, description="平均执行时间")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    last_used_at: Optional[datetime] = Field(None, description="最后使用时间")


class ToolRegistryListRequest(BaseSchema):
    """工具注册列表查询请求"""
    category: Optional[str] = Field(None, description="工具分类")
    tool_type: Optional[ToolType] = Field(None, description="工具类型")
    source_type: Optional[SourceType] = Field(None, description="来源类型")
    is_enabled: Optional[bool] = Field(None, description="是否启用")
    health_status: Optional[HealthStatus] = Field(None, description="健康状态")
    provider: Optional[str] = Field(None, description="提供者")
    search: Optional[str] = Field(None, description="搜索关键词")


class ToolRegistryListResponse(PaginatedResponse):
    """工具注册列表响应"""
    items: List[ToolRegistryResponse] = Field(..., description="工具列表")


class ToolExecutionRequest(BaseSchema):
    """工具执行请求"""
    tool_name: str = Field(..., description="工具名称")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="执行参数")
    execution_config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="执行配置")
    timeout: Optional[int] = Field(None, ge=1, description="超时时间")


class ToolExecutionResponse(BaseSchema):
    """工具执行响应"""
    execution_id: str = Field(..., description="执行ID")
    tool_name: str = Field(..., description="工具名称")
    status: str = Field(..., description="执行状态")
    result_data: Optional[Any] = Field(None, description="执行结果")
    error_message: Optional[str] = Field(None, description="错误信息")
    execution_time: Optional[float] = Field(None, description="执行时间")
    start_time: datetime = Field(..., description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")


# ===== 执行日志相关Schema =====

class ExecutionLogResponse(BaseSchema):
    """执行日志响应"""
    id: int = Field(..., description="日志ID")
    execution_id: str = Field(..., description="执行ID")
    tool_name: str = Field(..., description="工具名称")
    execution_type: str = Field(..., description="执行类型")
    status: str = Field(..., description="执行状态")
    start_time: datetime = Field(..., description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    execution_time: Optional[float] = Field(None, description="执行时间")
    error_message: Optional[str] = Field(None, description="错误信息")
    user_id: Optional[str] = Field(None, description="用户ID")
    cache_hit: bool = Field(..., description="是否缓存命中")
    created_at: datetime = Field(..., description="创建时间")


class ExecutionLogListRequest(BaseSchema):
    """执行日志列表查询请求"""
    tool_name: Optional[str] = Field(None, description="工具名称")
    execution_type: Optional[ExecutionType] = Field(None, description="执行类型")
    status: Optional[ExecutionStatus] = Field(None, description="执行状态")
    user_id: Optional[str] = Field(None, description="用户ID")
    start_date: Optional[datetime] = Field(None, description="开始日期")
    end_date: Optional[datetime] = Field(None, description="结束日期")


class ExecutionLogListResponse(PaginatedResponse):
    """执行日志列表响应"""
    items: List[ExecutionLogResponse] = Field(..., description="日志列表")


# ===== 健康检查相关Schema =====

class HealthCheckResponse(BaseSchema):
    """健康检查响应"""
    status: str = Field(..., description="服务状态")
    version: str = Field(..., description="服务版本")
    uptime: float = Field(..., description="运行时间(秒)")
    timestamp: datetime = Field(..., description="检查时间")
    
    # 组件状态
    database: bool = Field(..., description="数据库连接状态")
    redis: bool = Field(..., description="Redis连接状态")
    minio: bool = Field(..., description="MinIO连接状态")
    
    # 系统指标
    cpu_usage: float = Field(..., description="CPU使用率")
    memory_usage: float = Field(..., description="内存使用率")
    disk_usage: float = Field(..., description="磁盘使用率")
    
    # 服务统计
    total_files: int = Field(..., description="文件总数")
    total_configs: int = Field(..., description="配置总数")
    total_tools: int = Field(..., description="工具总数")
    active_executions: int = Field(..., description="活跃执行数")


class ServiceStatsResponse(BaseSchema):
    """服务统计响应"""
    files_stats: Dict[str, int] = Field(..., description="文件统计")
    sensitive_words_stats: Dict[str, int] = Field(..., description="敏感词统计")
    configs_stats: Dict[str, int] = Field(..., description="配置统计")
    tools_stats: Dict[str, int] = Field(..., description="工具统计")
    executions_stats: Dict[str, int] = Field(..., description="执行统计")
    daily_usage: Dict[str, int] = Field(..., description="日使用量")
    performance_metrics: Dict[str, float] = Field(..., description="性能指标")


# ===== 批量操作相关Schema =====

class BatchOperationRequest(BaseSchema):
    """批量操作请求"""
    operation: str = Field(..., description="操作类型")
    target_ids: List[Union[int, str]] = Field(..., description="目标ID列表")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="操作参数")


class BatchOperationResponse(BaseSchema):
    """批量操作响应"""
    operation: str = Field(..., description="操作类型")
    total_items: int = Field(..., description="总项目数")
    success_items: int = Field(..., description="成功项目数")
    failed_items: int = Field(..., description="失败项目数")
    results: List[Dict[str, Any]] = Field(..., description="操作结果")
    errors: List[Dict[str, Any]] = Field(default_factory=list, description="错误列表") 