"""
数据访问层 - Repository模式实现
"""

from .base_repository import BaseRepository
from .knowledge_repository import KnowledgeBaseRepository
from .document_repository import DocumentRepository
from .chunk_repository import DocumentChunkRepository
from .processing_repository import ProcessingJobRepository

__all__ = [
    "BaseRepository",
    "KnowledgeBaseRepository", 
    "DocumentRepository",
    "DocumentChunkRepository",
    "ProcessingJobRepository"
]