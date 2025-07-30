"""
快速知识库管理器 - 性能优化版本
专门针对知识库列表查询进行优化，避免初始化过程中的外部依赖超时
"""

import logging
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.models.knowledge_models import KnowledgeBase
from app.schemas.knowledge_schemas import KnowledgeBaseResponse

logger = logging.getLogger(__name__)


class FastKnowledgeManager:
    """快速知识库管理器 - 仅用于高频查询操作"""
    
    def __init__(self, db: Session):
        self.db = db
        logger.info("Fast Knowledge Manager initialized")
    
    def list_knowledge_bases(self, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """快速获取知识库列表（同步版本，避免async开销）"""
        try:
            skip = (page - 1) * page_size
            
            # 直接查询，不依赖Repository层
            knowledge_bases = self.db.query(KnowledgeBase)\
                .order_by(desc(KnowledgeBase.updated_at))\
                .offset(skip)\
                .limit(page_size)\
                .all()
            
            # 快速统计总数
            total = self.db.query(func.count(KnowledgeBase.id)).scalar() or 0
            
            # 构建响应列表（直接构建dict，避免Pydantic开销）
            kb_responses = []
            for kb in knowledge_bases:
                response = {
                    "id": str(kb.id),
                    "name": kb.name,
                    "description": kb.description or "",
                    "embedding_provider": kb.embedding_provider or "openai",
                    "embedding_model": kb.embedding_model or "text-embedding-ada-002",
                    "embedding_dimension": kb.embedding_dimension or 1536,
                    "vector_store_type": kb.vector_store_type or "milvus",
                    "chunk_size": kb.chunk_size or 1000,
                    "chunk_overlap": kb.chunk_overlap or 200,
                    "similarity_threshold": kb.similarity_threshold or 0.7,
                    "status": kb.status or "active",
                    "document_count": kb.document_count or 0,
                    "chunk_count": kb.chunk_count or 0,
                    "total_size": getattr(kb, 'total_size', 0) or 0,
                    "created_at": kb.created_at.isoformat() if kb.created_at else None,
                    "updated_at": kb.updated_at.isoformat() if kb.updated_at else None,
                    "settings": kb.settings or {}
                }
                kb_responses.append(response)
            
            return {
                "success": True,
                "knowledge_bases": kb_responses,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size
            }
            
        except Exception as e:
            logger.error(f"Failed to list knowledge bases: {e}")
            return {
                "success": False,
                "error": str(e),
                "knowledge_bases": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "total_pages": 0
            }
    
    def get_knowledge_base(self, kb_id: str) -> Optional[Dict[str, Any]]:
        """快速获取知识库详情"""
        try:
            kb = self.db.query(KnowledgeBase)\
                .filter(KnowledgeBase.id == kb_id)\
                .first()
            
            if not kb:
                return None
            
            return {
                "id": str(kb.id),
                "name": kb.name,
                "description": kb.description or "",
                "embedding_provider": kb.embedding_provider or "openai",
                "embedding_model": kb.embedding_model or "text-embedding-ada-002",
                "embedding_dimension": kb.embedding_dimension or 1536,
                "vector_store_type": kb.vector_store_type or "milvus",
                "chunk_size": kb.chunk_size or 1000,
                "chunk_overlap": kb.chunk_overlap or 200,
                "similarity_threshold": kb.similarity_threshold or 0.7,
                "status": kb.status or "active",
                "document_count": kb.document_count or 0,
                "chunk_count": kb.chunk_count or 0,
                "total_size": getattr(kb, 'total_size', 0) or 0,
                "created_at": kb.created_at.isoformat() if kb.created_at else None,
                "updated_at": kb.updated_at.isoformat() if kb.updated_at else None,
                "settings": kb.settings or {}
            }
            
        except Exception as e:
            logger.error(f"Failed to get knowledge base {kb_id}: {e}")
            return None
    
    def create_knowledge_base(
        self,
        name: str,
        description: Optional[str] = None,
        user_id: str = "system",
        embedding_provider: str = "openai",
        embedding_model: str = "text-embedding-ada-002",
        vector_store_type: str = "milvus",
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ) -> Dict[str, Any]:
        """快速创建知识库（同步版本）"""
        try:
            # 检查名称是否已存在
            existing = self.db.query(KnowledgeBase).filter(KnowledgeBase.name == name).first()
            if existing:
                return {
                    "success": False,
                    "error": f"知识库名称 '{name}' 已存在"
                }
            
            # 创建知识库对象
            kb = KnowledgeBase(
                name=name,
                description=description,
                user_id=user_id,
                embedding_provider=embedding_provider,
                embedding_model=embedding_model,
                embedding_dimension=1536,  # 默认OpenAI维度
                vector_store_type=vector_store_type,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                status="active"
            )
            
            # 保存到数据库
            self.db.add(kb)
            self.db.commit()
            self.db.refresh(kb)
            
            # 构建响应
            kb_response = {
                "id": str(kb.id),
                "name": kb.name,
                "description": kb.description or "",
                "user_id": kb.user_id,
                "embedding_provider": kb.embedding_provider,
                "embedding_model": kb.embedding_model,
                "embedding_dimension": kb.embedding_dimension,
                "vector_store_type": kb.vector_store_type,
                "chunk_size": kb.chunk_size,
                "chunk_overlap": kb.chunk_overlap,
                "status": kb.status,
                "document_count": 0,
                "created_at": kb.created_at.isoformat() if kb.created_at else None,
                "updated_at": kb.updated_at.isoformat() if kb.updated_at else None
            }
            
            return {
                "success": True,
                "knowledge_base": kb_response
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create knowledge base: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def count_knowledge_bases(self) -> int:
        """快速统计知识库数量"""
        try:
            return self.db.query(func.count(KnowledgeBase.id)).scalar() or 0
        except Exception as e:
            logger.error(f"Failed to count knowledge bases: {e}")
            return 0
    
    def search_knowledge_bases(
        self, 
        search_term: str = None,
        status: str = None,
        page: int = 1,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """快速搜索知识库"""
        try:
            query = self.db.query(KnowledgeBase)
            
            # 添加搜索条件
            if search_term:
                query = query.filter(
                    (KnowledgeBase.name.ilike(f"%{search_term}%")) |
                    (KnowledgeBase.description.ilike(f"%{search_term}%"))
                )
            
            if status:
                query = query.filter(KnowledgeBase.status == status)
            
            # 分页
            skip = (page - 1) * page_size
            knowledge_bases = query.order_by(desc(KnowledgeBase.updated_at))\
                .offset(skip)\
                .limit(page_size)\
                .all()
            
            # 统计符合条件的总数
            total = query.count()
            
            # 构建响应
            kb_responses = []
            for kb in knowledge_bases:
                response = {
                    "id": str(kb.id),
                    "name": kb.name,
                    "description": kb.description or "",
                    "status": kb.status or "active",
                    "document_count": kb.document_count or 0,
                    "chunk_count": kb.chunk_count or 0,
                    "created_at": kb.created_at.isoformat() if kb.created_at else None,
                    "updated_at": kb.updated_at.isoformat() if kb.updated_at else None
                }
                kb_responses.append(response)
            
            return {
                "success": True,
                "knowledge_bases": kb_responses,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size
            }
            
        except Exception as e:
            logger.error(f"Failed to search knowledge bases: {e}")
            return {
                "success": False,
                "error": str(e),
                "knowledge_bases": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "total_pages": 0
            }


# 全局实例
_fast_manager = None

def get_fast_knowledge_manager(db: Session) -> FastKnowledgeManager:
    """获取快速知识库管理器实例"""
    return FastKnowledgeManager(db)