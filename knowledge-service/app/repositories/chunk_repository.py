"""
文档分块Repository
处理文档分块的数据库操作
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models.knowledge_models import DocumentChunk
from .base_repository import BaseRepository


class DocumentChunkRepository(BaseRepository[DocumentChunk]):
    """文档分块数据访问层"""
    
    def __init__(self, db: Session):
        super().__init__(DocumentChunk, db)
    
    async def get_by_document(
        self, 
        doc_id: UUID, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[DocumentChunk]:
        """获取文档的所有分块"""
        return self.db.query(DocumentChunk)\
            .filter(DocumentChunk.doc_id == doc_id)\
            .order_by(DocumentChunk.chunk_index)\
            .offset(skip)\
            .limit(limit)\
            .all()
    
    async def get_by_embedding_status(
        self, 
        status: str,
        doc_id: Optional[UUID] = None
    ) -> List[DocumentChunk]:
        """根据嵌入状态获取分块"""
        query = self.db.query(DocumentChunk)\
            .filter(DocumentChunk.embedding_status == status)
        
        if doc_id:
            query = query.filter(DocumentChunk.doc_id == doc_id)
        
        return query.order_by(DocumentChunk.created_at).all()
    
    async def get_pending_embedding_chunks(self, limit: int = 100) -> List[DocumentChunk]:
        """获取待嵌入的分块"""
        return self.db.query(DocumentChunk)\
            .filter(DocumentChunk.embedding_status == "pending")\
            .order_by(DocumentChunk.created_at)\
            .limit(limit)\
            .all()
    
    async def get_chunk_by_embedding_id(self, embedding_id: str) -> Optional[DocumentChunk]:
        """根据嵌入ID获取分块"""
        return self.db.query(DocumentChunk)\
            .filter(DocumentChunk.embedding_id == embedding_id)\
            .first()
    
    async def get_chunks_by_content_hash(self, content_hash: str) -> List[DocumentChunk]:
        """根据内容哈希获取分块（用于去重）"""
        return self.db.query(DocumentChunk)\
            .filter(DocumentChunk.content_hash == content_hash)\
            .all()
    
    async def search_chunks_by_content(
        self,
        search_term: str,
        doc_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[DocumentChunk]:
        """根据内容搜索分块"""
        query = self.db.query(DocumentChunk)\
            .filter(DocumentChunk.content.ilike(f"%{search_term}%"))
        
        if doc_id:
            query = query.filter(DocumentChunk.doc_id == doc_id)
        
        return query.order_by(DocumentChunk.chunk_index)\
            .offset(skip)\
            .limit(limit)\
            .all()
    
    async def get_statistics_by_document(self, doc_id: UUID) -> Dict[str, Any]:
        """获取文档的分块统计信息"""
        stats = self.db.query(
            func.count(DocumentChunk.id).label('total_chunks'),
            func.count(DocumentChunk.id).filter(
                DocumentChunk.embedding_status == "completed"
            ).label('embedded_chunks'),
            func.count(DocumentChunk.id).filter(
                DocumentChunk.embedding_status == "pending"
            ).label('pending_chunks'),
            func.count(DocumentChunk.id).filter(
                DocumentChunk.embedding_status == "failed"
            ).label('failed_chunks'),
            func.sum(DocumentChunk.token_count).label('total_tokens'),
            func.sum(DocumentChunk.char_count).label('total_chars'),
            func.avg(DocumentChunk.token_count).label('avg_tokens'),
            func.avg(DocumentChunk.char_count).label('avg_chars')
        ).filter(DocumentChunk.doc_id == doc_id).first()
        
        return {
            'total_chunks': stats.total_chunks or 0,
            'embedded_chunks': stats.embedded_chunks or 0,
            'pending_chunks': stats.pending_chunks or 0,
            'failed_chunks': stats.failed_chunks or 0,
            'total_tokens': stats.total_tokens or 0,
            'total_chars': stats.total_chars or 0,
            'avg_tokens': float(stats.avg_tokens or 0),
            'avg_chars': float(stats.avg_chars or 0)
        }
    
    async def update_embedding_status(
        self,
        chunk_id: UUID,
        status: str,
        embedding_id: Optional[str] = None,
        embedding_model: Optional[str] = None
    ) -> Optional[DocumentChunk]:
        """更新分块的嵌入状态"""
        chunk = await self.get_by_id(chunk_id)
        if not chunk:
            return None
        
        chunk.embedding_status = status
        if embedding_id:
            chunk.embedding_id = embedding_id
        if embedding_model:
            chunk.embedding_model = embedding_model
        
        self.db.commit()
        self.db.refresh(chunk)
        
        return chunk
    
    async def batch_update_embedding_status(
        self,
        chunk_ids: List[UUID],
        status: str,
        embedding_model: Optional[str] = None
    ) -> List[DocumentChunk]:
        """批量更新分块嵌入状态"""
        chunks = self.db.query(DocumentChunk)\
            .filter(DocumentChunk.id.in_(chunk_ids))\
            .all()
        
        for chunk in chunks:
            chunk.embedding_status = status
            if embedding_model:
                chunk.embedding_model = embedding_model
        
        self.db.commit()
        
        for chunk in chunks:
            self.db.refresh(chunk)
        
        return chunks
    
    async def get_chunks_by_section(
        self, 
        doc_id: UUID, 
        section_title: str
    ) -> List[DocumentChunk]:
        """根据章节标题获取分块"""
        return self.db.query(DocumentChunk)\
            .filter(
                and_(
                    DocumentChunk.doc_id == doc_id,
                    DocumentChunk.section_title == section_title
                )
            )\
            .order_by(DocumentChunk.chunk_index)\
            .all()
    
    async def get_overlapping_chunks(
        self, 
        doc_id: UUID, 
        start_char: int, 
        end_char: int
    ) -> List[DocumentChunk]:
        """获取与指定字符范围重叠的分块"""
        return self.db.query(DocumentChunk)\
            .filter(
                and_(
                    DocumentChunk.doc_id == doc_id,
                    DocumentChunk.start_char < end_char,
                    DocumentChunk.end_char > start_char
                )
            )\
            .order_by(DocumentChunk.chunk_index)\
            .all()
    
    async def delete_by_document(self, doc_id: UUID) -> int:
        """删除文档的所有分块"""
        deleted_count = self.db.query(DocumentChunk)\
            .filter(DocumentChunk.doc_id == doc_id)\
            .delete()
        
        self.db.commit()
        return deleted_count
    
    async def get_chunk_statistics_global(self) -> Dict[str, Any]:
        """获取全局分块统计信息"""
        stats = self.db.query(
            func.count(DocumentChunk.id).label('total_chunks'),
            func.count(DocumentChunk.id).filter(
                DocumentChunk.embedding_status == "completed"
            ).label('embedded_chunks'),
            func.sum(DocumentChunk.token_count).label('total_tokens'),
            func.avg(DocumentChunk.token_count).label('avg_tokens'),
            func.max(DocumentChunk.token_count).label('max_tokens'),
            func.min(DocumentChunk.token_count).label('min_tokens')
        ).first()
        
        # 按嵌入模型统计
        model_stats = self.db.query(
            DocumentChunk.embedding_model,
            func.count(DocumentChunk.id).label('count')
        ).filter(DocumentChunk.embedding_model.isnot(None))\
         .group_by(DocumentChunk.embedding_model)\
         .all()
        
        return {
            'total_chunks': stats.total_chunks or 0,
            'embedded_chunks': stats.embedded_chunks or 0,
            'total_tokens': stats.total_tokens or 0,
            'avg_tokens': float(stats.avg_tokens or 0),
            'max_tokens': stats.max_tokens or 0,
            'min_tokens': stats.min_tokens or 0,
            'embedding_models_distribution': {
                model: count for model, count in model_stats if model
            }
        }