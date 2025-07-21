"""
文档Repository
处理文档的数据库操作
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_

from app.models.knowledge_models import Document
from .base_repository import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    """文档数据访问层"""
    
    def __init__(self, db: Session):
        super().__init__(Document, db)
    
    async def get_by_knowledge_base(
        self, 
        kb_id: UUID, 
        skip: int = 0, 
        limit: int = 100,
        status: Optional[str] = None
    ) -> List[Document]:
        """获取知识库下的文档列表"""
        query = self.db.query(Document)\
            .filter(Document.kb_id == kb_id)
        
        if status:
            query = query.filter(Document.status == status)
        
        return query.order_by(Document.created_at.desc())\
            .offset(skip)\
            .limit(limit)\
            .all()
    
    async def get_with_chunks(self, doc_id: UUID) -> Optional[Document]:
        """获取文档及其分块信息"""
        return self.db.query(Document)\
            .options(joinedload(Document.chunks))\
            .filter(Document.id == doc_id)\
            .first()
    
    async def get_by_filename(self, kb_id: UUID, filename: str) -> Optional[Document]:
        """根据文件名获取文档"""
        return self.db.query(Document)\
            .filter(
                and_(
                    Document.kb_id == kb_id,
                    Document.filename == filename
                )
            )\
            .first()
    
    async def get_by_file_hash(self, file_hash: str) -> Optional[Document]:
        """根据文件哈希获取文档（用于去重）"""
        return self.db.query(Document)\
            .filter(Document.file_hash == file_hash)\
            .first()
    
    async def get_processing_documents(self, kb_id: Optional[UUID] = None) -> List[Document]:
        """获取正在处理的文档"""
        query = self.db.query(Document)\
            .filter(Document.status.in_(["pending", "processing"]))
        
        if kb_id:
            query = query.filter(Document.kb_id == kb_id)
        
        return query.order_by(Document.created_at).all()
    
    async def get_failed_documents(self, kb_id: Optional[UUID] = None) -> List[Document]:
        """获取处理失败的文档"""
        query = self.db.query(Document)\
            .filter(Document.status == "failed")
        
        if kb_id:
            query = query.filter(Document.kb_id == kb_id)
        
        return query.order_by(Document.updated_at.desc()).all()
    
    async def search_documents(
        self,
        kb_id: UUID,
        search_term: str,
        file_types: Optional[List[str]] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Document]:
        """搜索文档"""
        query = self.db.query(Document)\
            .filter(Document.kb_id == kb_id)
        
        # 文本搜索
        if search_term:
            query = query.filter(
                (Document.filename.ilike(f"%{search_term}%")) |
                (Document.title.ilike(f"%{search_term}%")) |
                (Document.content_preview.ilike(f"%{search_term}%"))
            )
        
        # 文件类型过滤
        if file_types:
            query = query.filter(Document.file_type.in_(file_types))
        
        # 状态过滤
        if status:
            query = query.filter(Document.status == status)
        
        return query.order_by(Document.created_at.desc())\
            .offset(skip)\
            .limit(limit)\
            .all()
    
    async def get_statistics_by_kb(self, kb_id: UUID) -> Dict[str, Any]:
        """获取知识库的文档统计信息"""
        stats = self.db.query(
            func.count(Document.id).label('total_count'),
            func.count(Document.id).filter(Document.status == "completed").label('completed_count'),
            func.count(Document.id).filter(Document.status == "processing").label('processing_count'),
            func.count(Document.id).filter(Document.status == "failed").label('failed_count'),
            func.sum(Document.file_size).label('total_size'),
            func.sum(Document.chunk_count).label('total_chunks'),
            func.sum(Document.token_count).label('total_tokens')
        ).filter(Document.kb_id == kb_id).first()
        
        # 按文件类型统计
        type_stats = self.db.query(
            Document.file_type,
            func.count(Document.id).label('count')
        ).filter(Document.kb_id == kb_id)\
         .group_by(Document.file_type)\
         .all()
        
        return {
            'total_documents': stats.total_count or 0,
            'completed_documents': stats.completed_count or 0,
            'processing_documents': stats.processing_count or 0,
            'failed_documents': stats.failed_count or 0,
            'total_size': stats.total_size or 0,
            'total_chunks': stats.total_chunks or 0,
            'total_tokens': stats.total_tokens or 0,
            'file_types_distribution': {
                file_type: count for file_type, count in type_stats
            }
        }
    
    async def update_processing_status(
        self, 
        doc_id: UUID, 
        status: str, 
        stage: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> Optional[Document]:
        """更新文档处理状态"""
        doc = await self.get_by_id(doc_id)
        if not doc:
            return None
        
        doc.status = status
        if stage:
            doc.processing_stage = stage
        if error_message:
            doc.error_message = error_message
        
        if status == "completed":
            doc.processed_at = func.now()
        
        self.db.commit()
        self.db.refresh(doc)
        
        return doc
    
    async def batch_update_status(
        self, 
        doc_ids: List[UUID], 
        status: str
    ) -> List[Document]:
        """批量更新文档状态"""
        docs = self.db.query(Document)\
            .filter(Document.id.in_(doc_ids))\
            .all()
        
        for doc in docs:
            doc.status = status
            if status == "completed":
                doc.processed_at = func.now()
        
        self.db.commit()
        
        for doc in docs:
            self.db.refresh(doc)
        
        return docs
    
    async def get_documents_by_tags(
        self, 
        kb_id: UUID, 
        tags: List[str]
    ) -> List[Document]:
        """根据标签获取文档"""
        return self.db.query(Document)\
            .filter(
                and_(
                    Document.kb_id == kb_id,
                    Document.tags.overlap(tags)
                )
            )\
            .order_by(Document.created_at.desc())\
            .all()
    
    async def get_large_documents(
        self, 
        kb_id: UUID, 
        size_threshold: int = 10 * 1024 * 1024  # 10MB
    ) -> List[Document]:
        """获取大文件列表"""
        return self.db.query(Document)\
            .filter(
                and_(
                    Document.kb_id == kb_id,
                    Document.file_size > size_threshold
                )
            )\
            .order_by(Document.file_size.desc())\
            .all()