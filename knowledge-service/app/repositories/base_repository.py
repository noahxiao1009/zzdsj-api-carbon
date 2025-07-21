"""
基础Repository类
提供通用的数据库操作方法
"""

from typing import TypeVar, Generic, Type, Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import and_, or_, desc, asc

from app.models.database import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """基础Repository类，提供通用CRUD操作"""
    
    def __init__(self, model: Type[ModelType], db: Session):
        self.model = model
        self.db = db
    
    async def create(self, obj_data: Dict[str, Any]) -> ModelType:
        """创建新记录"""
        try:
            db_obj = self.model(**obj_data)
            self.db.add(db_obj)
            self.db.commit()
            self.db.refresh(db_obj)
            return db_obj
        except SQLAlchemyError as e:
            self.db.rollback()
            raise e
    
    async def get_by_id(self, obj_id: UUID) -> Optional[ModelType]:
        """根据ID获取记录"""
        return self.db.query(self.model).filter(self.model.id == obj_id).first()
    
    async def get_by_field(self, field_name: str, value: Any) -> Optional[ModelType]:
        """根据字段值获取记录"""
        return self.db.query(self.model).filter(getattr(self.model, field_name) == value).first()
    
    async def get_multi(
        self, 
        skip: int = 0, 
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        order_desc: bool = False
    ) -> List[ModelType]:
        """获取多条记录"""
        query = self.db.query(self.model)
        
        # 应用过滤器
        if filters:
            for field, value in filters.items():
                if hasattr(self.model, field):
                    if isinstance(value, list):
                        query = query.filter(getattr(self.model, field).in_(value))
                    else:
                        query = query.filter(getattr(self.model, field) == value)
        
        # 应用排序
        if order_by and hasattr(self.model, order_by):
            order_field = getattr(self.model, order_by)
            if order_desc:
                query = query.order_by(desc(order_field))
            else:
                query = query.order_by(asc(order_field))
        
        return query.offset(skip).limit(limit).all()
    
    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """统计记录数量"""
        query = self.db.query(self.model)
        
        if filters:
            for field, value in filters.items():
                if hasattr(self.model, field):
                    if isinstance(value, list):
                        query = query.filter(getattr(self.model, field).in_(value))
                    else:
                        query = query.filter(getattr(self.model, field) == value)
        
        return query.count()
    
    async def update(self, obj_id: UUID, update_data: Dict[str, Any]) -> Optional[ModelType]:
        """更新记录"""
        try:
            db_obj = await self.get_by_id(obj_id)
            if not db_obj:
                return None
            
            for field, value in update_data.items():
                if hasattr(db_obj, field):
                    setattr(db_obj, field, value)
            
            self.db.commit()
            self.db.refresh(db_obj)
            return db_obj
        except SQLAlchemyError as e:
            self.db.rollback()
            raise e
    
    async def delete(self, obj_id: UUID) -> bool:
        """删除记录"""
        try:
            db_obj = await self.get_by_id(obj_id)
            if not db_obj:
                return False
            
            self.db.delete(db_obj)
            self.db.commit()
            return True
        except SQLAlchemyError as e:
            self.db.rollback()
            raise e
    
    async def batch_create(self, objects_data: List[Dict[str, Any]]) -> List[ModelType]:
        """批量创建记录"""
        try:
            db_objects = [self.model(**obj_data) for obj_data in objects_data]
            self.db.add_all(db_objects)
            self.db.commit()
            
            for obj in db_objects:
                self.db.refresh(obj)
            
            return db_objects
        except SQLAlchemyError as e:
            self.db.rollback()
            raise e
    
    async def batch_update(self, updates: List[Dict[str, Any]]) -> List[ModelType]:
        """批量更新记录"""
        try:
            updated_objects = []
            for update_item in updates:
                obj_id = update_item.pop('id')
                db_obj = await self.get_by_id(obj_id)
                if db_obj:
                    for field, value in update_item.items():
                        if hasattr(db_obj, field):
                            setattr(db_obj, field, value)
                    updated_objects.append(db_obj)
            
            self.db.commit()
            
            for obj in updated_objects:
                self.db.refresh(obj)
            
            return updated_objects
        except SQLAlchemyError as e:
            self.db.rollback()
            raise e
    
    async def exists(self, obj_id: UUID) -> bool:
        """检查记录是否存在"""
        return self.db.query(self.model).filter(self.model.id == obj_id).first() is not None
    
    async def search(
        self, 
        search_fields: List[str], 
        search_term: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[ModelType]:
        """搜索记录"""
        if not search_fields or not search_term:
            return []
        
        conditions = []
        for field in search_fields:
            if hasattr(self.model, field):
                field_attr = getattr(self.model, field)
                conditions.append(field_attr.ilike(f"%{search_term}%"))
        
        if not conditions:
            return []
        
        query = self.db.query(self.model).filter(or_(*conditions))
        return query.offset(skip).limit(limit).all()