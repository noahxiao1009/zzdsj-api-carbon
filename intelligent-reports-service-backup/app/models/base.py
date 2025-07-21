"""
基础数据模型
"""
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import as_declarative, declared_attr
from sqlalchemy.sql import func
from pydantic import BaseModel, Field


@as_declarative()
class Base:
    """基础数据库模型"""
    
    id: uuid.UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now())
    updated_at: datetime = Column(DateTime(timezone=True), onupdate=func.now())
    is_deleted: bool = Column(Boolean, default=False)
    
    @declared_attr
    def __tablename__(cls) -> str:
        return cls.__name__.lower()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                result[column.name] = value.isoformat()
            elif isinstance(value, uuid.UUID):
                result[column.name] = str(value)
            else:
                result[column.name] = value
        return result
    
    def update_from_dict(self, data: Dict[str, Any]):
        """从字典更新"""
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)


class BaseResponse(BaseModel):
    """基础响应模型"""
    
    code: int = Field(200, description="状态码")
    message: str = Field("success", description="消息")
    data: Optional[Any] = Field(None, description="数据")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            uuid.UUID: lambda v: str(v),
        }


class PaginationBase(BaseModel):
    """分页基础模型"""
    
    page: int = Field(1, ge=1, description="页码")
    size: int = Field(10, ge=1, le=100, description="每页数量")
    total: int = Field(0, ge=0, description="总数")
    pages: int = Field(0, ge=0, description="总页数")
    
    @property
    def offset(self) -> int:
        """偏移量"""
        return (self.page - 1) * self.size
    
    def calculate_pages(self, total: int) -> int:
        """计算总页数"""
        self.total = total
        self.pages = (total + self.size - 1) // self.size
        return self.pages


class PaginatedResponse(BaseResponse):
    """分页响应模型"""
    
    pagination: PaginationBase = Field(..., description="分页信息")
    
    def __init__(self, data: Any, pagination: PaginationBase, **kwargs):
        super().__init__(data=data, **kwargs)
        self.pagination = pagination


class CreateRequestBase(BaseModel):
    """创建请求基础模型"""
    
    class Config:
        # 允许额外字段
        extra = "forbid"
        # 使用枚举值
        use_enum_values = True
        # 验证赋值
        validate_assignment = True


class UpdateRequestBase(BaseModel):
    """更新请求基础模型"""
    
    class Config:
        # 允许额外字段
        extra = "forbid"
        # 使用枚举值
        use_enum_values = True
        # 验证赋值
        validate_assignment = True


class ErrorResponse(BaseModel):
    """错误响应模型"""
    
    code: int = Field(..., description="错误码")
    message: str = Field(..., description="错误消息")
    detail: Optional[str] = Field(None, description="错误详情")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class StatusEnum:
    """状态枚举基类"""
    
    @classmethod
    def values(cls) -> list:
        """获取所有值"""
        return [getattr(cls, attr) for attr in dir(cls) if not attr.startswith('_') and attr != 'values']
    
    @classmethod
    def is_valid(cls, value: str) -> bool:
        """验证值是否有效"""
        return value in cls.values()


class AuditMixin:
    """审计混入"""
    
    created_by: Optional[str] = Column(String(255), comment="创建者")
    updated_by: Optional[str] = Column(String(255), comment="更新者")
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at: datetime = Column(DateTime(timezone=True), onupdate=func.now(), comment="更新时间")


class SoftDeleteMixin:
    """软删除混入"""
    
    is_deleted: bool = Column(Boolean, default=False, comment="是否删除")
    deleted_at: Optional[datetime] = Column(DateTime(timezone=True), comment="删除时间")
    deleted_by: Optional[str] = Column(String(255), comment="删除者")
    
    def soft_delete(self, deleted_by: str = None):
        """软删除"""
        self.is_deleted = True
        self.deleted_at = datetime.now()
        self.deleted_by = deleted_by
    
    def restore(self):
        """恢复"""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None


class MetadataMixin:
    """元数据混入"""
    
    metadata: Dict[str, Any] = Column(JSON, default=dict, comment="元数据")
    tags: Optional[str] = Column(Text, comment="标签")
    
    def add_metadata(self, key: str, value: Any):
        """添加元数据"""
        if not self.metadata:
            self.metadata = {}
        self.metadata[key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """获取元数据"""
        if not self.metadata:
            return default
        return self.metadata.get(key, default)
    
    def remove_metadata(self, key: str):
        """移除元数据"""
        if self.metadata and key in self.metadata:
            del self.metadata[key]


class VersionMixin:
    """版本混入"""
    
    version: int = Column(Integer, default=1, comment="版本号")
    
    def increment_version(self):
        """递增版本"""
        self.version += 1


class CommonFilters:
    """通用过滤器"""
    
    @staticmethod
    def not_deleted():
        """非删除过滤器"""
        return lambda query: query.filter(Base.is_deleted == False)
    
    @staticmethod
    def created_between(start: datetime, end: datetime):
        """创建时间范围过滤器"""
        return lambda query: query.filter(Base.created_at.between(start, end))
    
    @staticmethod
    def updated_after(after: datetime):
        """更新时间后过滤器"""
        return lambda query: query.filter(Base.updated_at > after)


class BaseRepository:
    """基础仓储模式"""
    
    def __init__(self, model_class, session):
        self.model_class = model_class
        self.session = session
    
    async def create(self, **kwargs):
        """创建"""
        obj = self.model_class(**kwargs)
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj
    
    async def get_by_id(self, id: uuid.UUID):
        """根据ID获取"""
        return await self.session.get(self.model_class, id)
    
    async def update(self, id: uuid.UUID, **kwargs):
        """更新"""
        obj = await self.get_by_id(id)
        if obj:
            obj.update_from_dict(kwargs)
            await self.session.commit()
            await self.session.refresh(obj)
        return obj
    
    async def delete(self, id: uuid.UUID):
        """删除"""
        obj = await self.get_by_id(id)
        if obj:
            await self.session.delete(obj)
            await self.session.commit()
        return obj
    
    async def soft_delete(self, id: uuid.UUID, deleted_by: str = None):
        """软删除"""
        obj = await self.get_by_id(id)
        if obj and hasattr(obj, 'soft_delete'):
            obj.soft_delete(deleted_by)
            await self.session.commit()
        return obj
    
    async def list(self, filters: list = None, page: int = 1, size: int = 10):
        """列表"""
        query = self.session.query(self.model_class)
        
        # 应用过滤器
        if filters:
            for filter_func in filters:
                query = filter_func(query)
        
        # 分页
        offset = (page - 1) * size
        items = await query.offset(offset).limit(size).all()
        total = await query.count()
        
        return items, total