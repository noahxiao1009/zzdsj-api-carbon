"""
知识库Repository
处理知识库的数据库操作
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_

from app.models.knowledge_models import KnowledgeBase
from .base_repository import BaseRepository


class KnowledgeBaseRepository(BaseRepository[KnowledgeBase]):
    """知识库数据访问层"""
    
    def __init__(self, db: Session):
        super().__init__(KnowledgeBase, db)
    
    async def get_with_stats(self, kb_id: UUID) -> Optional[KnowledgeBase]:
        """获取知识库及其统计信息"""
        return self.db.query(KnowledgeBase)\
            .options(joinedload(KnowledgeBase.documents))\
            .filter(KnowledgeBase.id == kb_id)\
            .first()
    
    async def get_by_name(self, name: str) -> Optional[KnowledgeBase]:
        """根据名称获取知识库"""
        return self.db.query(KnowledgeBase)\
            .filter(KnowledgeBase.name == name)\
            .first()
    
    async def get_active_knowledge_bases(
        self, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[KnowledgeBase]:
        """获取活跃的知识库列表"""
        return self.db.query(KnowledgeBase)\
            .filter(KnowledgeBase.status == "active")\
            .order_by(KnowledgeBase.updated_at.desc())\
            .offset(skip)\
            .limit(limit)\
            .all()
    
    async def search_knowledge_bases(
        self,
        search_term: str,
        status: Optional[str] = None,
        embedding_model: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[KnowledgeBase]:
        """搜索知识库"""
        query = self.db.query(KnowledgeBase)
        
        # 名称和描述搜索
        if search_term:
            query = query.filter(
                (KnowledgeBase.name.ilike(f"%{search_term}%")) |
                (KnowledgeBase.description.ilike(f"%{search_term}%"))
            )
        
        # 状态过滤
        if status:
            query = query.filter(KnowledgeBase.status == status)
        
        # 嵌入模型过滤
        if embedding_model:
            query = query.filter(KnowledgeBase.embedding_model == embedding_model)
        
        return query.order_by(KnowledgeBase.updated_at.desc())\
            .offset(skip)\
            .limit(limit)\
            .all()
    
    async def get_statistics(self) -> Dict[str, Any]:
        """获取知识库统计信息"""
        stats = self.db.query(
            func.count(KnowledgeBase.id).label('total_count'),
            func.count(
                KnowledgeBase.id
            ).filter(KnowledgeBase.status == "active").label('active_count'),
            func.sum(KnowledgeBase.document_count).label('total_documents'),
            func.sum(KnowledgeBase.chunk_count).label('total_chunks'),
            func.sum(KnowledgeBase.total_size).label('total_size')
        ).first()
        
        # 按嵌入模型统计
        model_stats = self.db.query(
            KnowledgeBase.embedding_model,
            func.count(KnowledgeBase.id).label('count')
        ).group_by(KnowledgeBase.embedding_model).all()
        
        return {
            'total_knowledge_bases': stats.total_count or 0,
            'active_knowledge_bases': stats.active_count or 0,
            'total_documents': stats.total_documents or 0,
            'total_chunks': stats.total_chunks or 0,
            'total_size': stats.total_size or 0,
            'models_distribution': {
                model: count for model, count in model_stats
            }
        }
    
    async def update_statistics(self, kb_id: UUID) -> Optional[KnowledgeBase]:
        """更新知识库统计信息"""
        kb = await self.get_by_id(kb_id)
        if not kb:
            return None
        
        # 统计文档数量
        doc_count = self.db.query(func.count())\
            .select_from(self.db.query(KnowledgeBase)\
                        .join(KnowledgeBase.documents)\
                        .filter(KnowledgeBase.id == kb_id)\
                        .subquery())\
            .scalar() or 0
        
        # 统计分块数量
        chunk_count = self.db.query(func.count())\
            .select_from(
                self.db.query(KnowledgeBase)\
                .join(KnowledgeBase.documents)\
                .join('chunks')\
                .filter(KnowledgeBase.id == kb_id)\
                .subquery()
            ).scalar() or 0
        
        # 统计总大小
        total_size = self.db.query(func.sum('file_size'))\
            .select_from(
                self.db.query(KnowledgeBase)\
                .join(KnowledgeBase.documents)\
                .filter(KnowledgeBase.id == kb_id)\
                .subquery()
            ).scalar() or 0
        
        # 更新统计信息
        kb.document_count = doc_count
        kb.chunk_count = chunk_count
        kb.total_size = total_size
        
        self.db.commit()
        self.db.refresh(kb)
        
        return kb
    
    async def get_by_embedding_model(self, embedding_model: str) -> List[KnowledgeBase]:
        """根据嵌入模型获取知识库"""
        return self.db.query(KnowledgeBase)\
            .filter(KnowledgeBase.embedding_model == embedding_model)\
            .order_by(KnowledgeBase.name)\
            .all()
    
    async def check_name_exists(self, name: str, exclude_id: Optional[UUID] = None) -> bool:
        """检查知识库名称是否已存在"""
        query = self.db.query(KnowledgeBase).filter(KnowledgeBase.name == name)
        
        if exclude_id:
            query = query.filter(KnowledgeBase.id != exclude_id)
        
        return query.first() is not None
    
    async def get_recent_activity(self, limit: int = 10) -> List[KnowledgeBase]:
        """获取最近活动的知识库"""
        return self.db.query(KnowledgeBase)\
            .filter(KnowledgeBase.status == "active")\
            .order_by(KnowledgeBase.updated_at.desc())\
            .limit(limit)\
            .all()