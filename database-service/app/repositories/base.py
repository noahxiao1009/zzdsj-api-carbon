"""
基础仓库类
提供通用的数据库操作方法
"""

from typing import Generic, TypeVar, Type, List, Optional, Dict, Any, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from ..models.database import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """基础仓库类，提供通用的CRUD操作"""
    
    def __init__(self, model: Type[ModelType]):
        """
        初始化仓库
        Args:
            model: SQLAlchemy模型类
        """
        self.model = model
    
    async def create(self, db: AsyncSession, *, obj_in: CreateSchemaType) -> ModelType:
        """
        创建记录
        Args:
            db: 数据库会话
            obj_in: 创建数据
        Returns:
            创建的记录
        """
        obj_data = obj_in.dict() if hasattr(obj_in, 'dict') else obj_in
        db_obj = self.model(**obj_data)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    
    async def get(self, db: AsyncSession, id: Union[str, int]) -> Optional[ModelType]:
        """
        根据ID获取记录
        Args:
            db: 数据库会话
            id: 记录ID
        Returns:
            记录对象或None
        """
        result = await db.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()
    
    async def get_multi(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        order_desc: bool = True
    ) -> List[ModelType]:
        """
        获取多条记录
        Args:
            db: 数据库会话
            skip: 跳过记录数
            limit: 限制记录数
            filters: 过滤条件
            order_by: 排序字段
            order_desc: 是否降序
        Returns:
            记录列表
        """
        query = select(self.model)
        
        # 应用过滤条件
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    if isinstance(value, list):
                        query = query.where(getattr(self.model, key).in_(value))
                    else:
                        query = query.where(getattr(self.model, key) == value)
        
        # 应用排序
        if order_by and hasattr(self.model, order_by):
            order_column = getattr(self.model, order_by)
            if order_desc:
                query = query.order_by(order_column.desc())
            else:
                query = query.order_by(order_column.asc())
        
        # 应用分页
        query = query.offset(skip).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        """
        更新记录
        Args:
            db: 数据库会话
            db_obj: 数据库对象
            obj_in: 更新数据
        Returns:
            更新后的记录
        """
        obj_data = obj_in.dict(exclude_unset=True) if hasattr(obj_in, 'dict') else obj_in
        
        for field, value in obj_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    
    async def delete(self, db: AsyncSession, *, id: Union[str, int]) -> Optional[ModelType]:
        """
        删除记录
        Args:
            db: 数据库会话
            id: 记录ID
        Returns:
            删除的记录或None
        """
        db_obj = await self.get(db, id)
        if db_obj:
            await db.delete(db_obj)
            await db.commit()
        return db_obj
    
    async def count(
        self,
        db: AsyncSession,
        *,
        filters: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        统计记录数量
        Args:
            db: 数据库会话
            filters: 过滤条件
        Returns:
            记录数量
        """
        query = select(func.count(self.model.id))
        
        # 应用过滤条件
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    if isinstance(value, list):
                        query = query.where(getattr(self.model, key).in_(value))
                    else:
                        query = query.where(getattr(self.model, key) == value)
        
        result = await db.execute(query)
        return result.scalar()
    
    async def exists(
        self,
        db: AsyncSession,
        *,
        filters: Dict[str, Any]
    ) -> bool:
        """
        检查记录是否存在
        Args:
            db: 数据库会话
            filters: 过滤条件
        Returns:
            是否存在
        """
        query = select(self.model.id)
        
        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.where(getattr(self.model, key) == value)
        
        query = query.limit(1)
        result = await db.execute(query)
        return result.scalar() is not None
    
    async def bulk_create(
        self,
        db: AsyncSession,
        *,
        objs_in: List[CreateSchemaType]
    ) -> List[ModelType]:
        """
        批量创建记录
        Args:
            db: 数据库会话
            objs_in: 创建数据列表
        Returns:
            创建的记录列表
        """
        db_objs = []
        for obj_in in objs_in:
            obj_data = obj_in.dict() if hasattr(obj_in, 'dict') else obj_in
            db_obj = self.model(**obj_data)
            db_objs.append(db_obj)
        
        db.add_all(db_objs)
        await db.commit()
        
        for db_obj in db_objs:
            await db.refresh(db_obj)
        
        return db_objs
    
    async def bulk_update(
        self,
        db: AsyncSession,
        *,
        updates: List[Dict[str, Any]]
    ) -> int:
        """
        批量更新记录
        Args:
            db: 数据库会话
            updates: 更新数据列表，每个字典必须包含id字段
        Returns:
            更新的记录数量
        """
        updated_count = 0
        
        for update_data in updates:
            if 'id' not in update_data:
                continue
            
            record_id = update_data.pop('id')
            
            stmt = update(self.model).where(self.model.id == record_id).values(**update_data)
            result = await db.execute(stmt)
            updated_count += result.rowcount
        
        await db.commit()
        return updated_count
    
    async def bulk_delete(
        self,
        db: AsyncSession,
        *,
        ids: List[Union[str, int]]
    ) -> int:
        """
        批量删除记录
        Args:
            db: 数据库会话
            ids: ID列表
        Returns:
            删除的记录数量
        """
        stmt = delete(self.model).where(self.model.id.in_(ids))
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount
    
    async def search(
        self,
        db: AsyncSession,
        *,
        query: str,
        search_fields: List[str],
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ModelType]:
        """
        搜索记录
        Args:
            db: 数据库会话
            query: 搜索关键词
            search_fields: 搜索字段列表
            skip: 跳过记录数
            limit: 限制记录数
            filters: 额外过滤条件
        Returns:
            搜索结果列表
        """
        stmt = select(self.model)
        
        # 构建搜索条件
        if query and search_fields:
            search_conditions = []
            for field in search_fields:
                if hasattr(self.model, field):
                    column = getattr(self.model, field)
                    search_conditions.append(column.ilike(f"%{query}%"))
            
            if search_conditions:
                stmt = stmt.where(or_(*search_conditions))
        
        # 应用额外过滤条件
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    if isinstance(value, list):
                        stmt = stmt.where(getattr(self.model, key).in_(value))
                    else:
                        stmt = stmt.where(getattr(self.model, key) == value)
        
        # 应用分页
        stmt = stmt.offset(skip).limit(limit)
        
        result = await db.execute(stmt)
        return result.scalars().all()
    
    async def get_with_relations(
        self,
        db: AsyncSession,
        id: Union[str, int],
        relations: List[str]
    ) -> Optional[ModelType]:
        """
        获取记录及其关联数据
        Args:
            db: 数据库会话
            id: 记录ID
            relations: 关联字段列表
        Returns:
            记录对象或None
        """
        query = select(self.model).where(self.model.id == id)
        
        # 添加关联加载
        for relation in relations:
            if hasattr(self.model, relation):
                query = query.options(selectinload(getattr(self.model, relation)))
        
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_field(
        self,
        db: AsyncSession,
        field: str,
        value: Any
    ) -> Optional[ModelType]:
        """
        根据字段值获取记录
        Args:
            db: 数据库会话
            field: 字段名
            value: 字段值
        Returns:
            记录对象或None
        """
        if not hasattr(self.model, field):
            return None
        
        query = select(self.model).where(getattr(self.model, field) == value)
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_multi_by_field(
        self,
        db: AsyncSession,
        field: str,
        values: List[Any]
    ) -> List[ModelType]:
        """
        根据字段值列表获取多条记录
        Args:
            db: 数据库会话
            field: 字段名
            values: 字段值列表
        Returns:
            记录列表
        """
        if not hasattr(self.model, field):
            return []
        
        query = select(self.model).where(getattr(self.model, field).in_(values))
        result = await db.execute(query)
        return result.scalars().all()