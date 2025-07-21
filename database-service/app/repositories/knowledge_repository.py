"""
知识库相关的仓库实现
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepository
from ..models.knowledge import KnowledgeBase, Document, DocumentChunk, KnowledgeGraph, SearchHistory


class KnowledgeBaseRepository(BaseRepository[KnowledgeBase, Dict[str, Any], Dict[str, Any]]):
    """知识库仓库"""
    
    def __init__(self):
        super().__init__(KnowledgeBase)
    
    async def get_by_user_id(self, db: AsyncSession, user_id: str) -> List[KnowledgeBase]:
        """根据用户ID获取知识库列表"""
        return await self.get_multi(db, filters={"user_id": user_id})
    
    async def get_public_knowledge_bases(self, db: AsyncSession) -> List[KnowledgeBase]:
        """获取公开知识库列表"""
        return await self.get_multi(db, filters={"is_public": True, "is_active": True})


class DocumentRepository(BaseRepository[Document, Dict[str, Any], Dict[str, Any]]):
    """文档仓库"""
    
    def __init__(self):
        super().__init__(Document)
    
    async def get_by_kb_id(self, db: AsyncSession, kb_id: str) -> List[Document]:
        """根据知识库ID获取文档列表"""
        return await self.get_multi(db, filters={"kb_id": kb_id})


class DocumentChunkRepository(BaseRepository[DocumentChunk, Dict[str, Any], Dict[str, Any]]):
    """文档分块仓库"""
    
    def __init__(self):
        super().__init__(DocumentChunk)
    
    async def get_by_document_id(self, db: AsyncSession, document_id: str) -> List[DocumentChunk]:
        """根据文档ID获取分块列表"""
        return await self.get_multi(db, filters={"document_id": document_id})