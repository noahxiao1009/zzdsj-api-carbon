"""
通用模式定义
包含分页、响应等通用的Pydantic模式
"""

from typing import Any, Dict, List, Optional, Generic, TypeVar
from pydantic import BaseModel, Field
from datetime import datetime

T = TypeVar('T')


class PaginationParams(BaseModel):
    """分页参数"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
    sort_by: Optional[str] = Field(default=None, description="排序字段")
    sort_order: Optional[str] = Field(default="desc", regex="^(asc|desc)$", description="排序方向")


class PaginationResponse(BaseModel, Generic[T]):
    """分页响应"""
    items: List[T] = Field(description="数据项")
    total: int = Field(description="总数量")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页数量")
    total_pages: int = Field(description="总页数")
    has_next: bool = Field(description="是否有下一页")
    has_prev: bool = Field(description="是否有上一页")


class BaseResponse(BaseModel):
    """基础响应模式"""
    success: bool = Field(description="是否成功")
    message: Optional[str] = Field(default=None, description="响应消息")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="响应时间")


class ErrorResponse(BaseResponse):
    """错误响应模式"""
    success: bool = Field(default=False, description="是否成功")
    error_code: Optional[str] = Field(default=None, description="错误代码")
    error_details: Optional[Dict[str, Any]] = Field(default=None, description="错误详情")


class SuccessResponse(BaseResponse, Generic[T]):
    """成功响应模式"""
    success: bool = Field(default=True, description="是否成功")
    data: Optional[T] = Field(default=None, description="响应数据")


class HealthCheckResponse(BaseModel):
    """健康检查响应"""
    status: str = Field(description="健康状态")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="检查时间")
    version: Optional[str] = Field(default=None, description="服务版本")
    uptime: Optional[float] = Field(default=None, description="运行时间（秒）")
    details: Optional[Dict[str, Any]] = Field(default=None, description="详细信息")


class StatusResponse(BaseModel):
    """状态响应"""
    service_name: str = Field(description="服务名称")
    status: str = Field(description="服务状态")
    is_healthy: bool = Field(description="是否健康")
    last_check: datetime = Field(description="最后检查时间")
    response_time: Optional[float] = Field(default=None, description="响应时间（毫秒）")
    error_message: Optional[str] = Field(default=None, description="错误信息")


class SearchParams(BaseModel):
    """搜索参数"""
    query: Optional[str] = Field(default=None, description="搜索关键词")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="过滤条件")
    sort_by: Optional[str] = Field(default=None, description="排序字段")
    sort_order: Optional[str] = Field(default="desc", regex="^(asc|desc)$", description="排序方向")


class BulkOperationRequest(BaseModel):
    """批量操作请求"""
    operation: str = Field(description="操作类型")
    ids: List[str] = Field(description="ID列表")
    data: Optional[Dict[str, Any]] = Field(default=None, description="操作数据")


class BulkOperationResponse(BaseModel):
    """批量操作响应"""
    success_count: int = Field(description="成功数量")
    failure_count: int = Field(description="失败数量")
    total_count: int = Field(description="总数量")
    errors: Optional[List[Dict[str, Any]]] = Field(default=None, description="错误列表")


class FileUploadResponse(BaseModel):
    """文件上传响应"""
    file_id: str = Field(description="文件ID")
    file_name: str = Field(description="文件名")
    file_size: int = Field(description="文件大小")
    file_type: str = Field(description="文件类型")
    upload_url: Optional[str] = Field(default=None, description="上传URL")
    download_url: Optional[str] = Field(default=None, description="下载URL")


class ExportRequest(BaseModel):
    """导出请求"""
    format: str = Field(description="导出格式", regex="^(json|csv|xlsx)$")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="过滤条件")
    fields: Optional[List[str]] = Field(default=None, description="导出字段")


class ImportRequest(BaseModel):
    """导入请求"""
    file_url: str = Field(description="文件URL")
    format: str = Field(description="文件格式", regex="^(json|csv|xlsx)$")
    options: Optional[Dict[str, Any]] = Field(default=None, description="导入选项")


class ValidationError(BaseModel):
    """验证错误"""
    field: str = Field(description="字段名")
    message: str = Field(description="错误消息")
    value: Optional[Any] = Field(default=None, description="错误值")


class ConfigUpdate(BaseModel):
    """配置更新"""
    key: str = Field(description="配置键")
    value: Any = Field(description="配置值")
    description: Optional[str] = Field(default=None, description="配置描述")


class MetricsResponse(BaseModel):
    """指标响应"""
    metrics: Dict[str, Any] = Field(description="指标数据")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="采集时间")
    period: Optional[str] = Field(default=None, description="统计周期")


class LogEntry(BaseModel):
    """日志条目"""
    timestamp: datetime = Field(description="时间戳")
    level: str = Field(description="日志级别")
    message: str = Field(description="日志消息")
    source: Optional[str] = Field(default=None, description="日志来源")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="元数据")


class AuditLog(BaseModel):
    """审计日志"""
    user_id: str = Field(description="用户ID")
    action: str = Field(description="操作")
    resource_type: str = Field(description="资源类型")
    resource_id: str = Field(description="资源ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="时间戳")
    ip_address: Optional[str] = Field(default=None, description="IP地址")
    user_agent: Optional[str] = Field(default=None, description="用户代理")
    details: Optional[Dict[str, Any]] = Field(default=None, description="详细信息")