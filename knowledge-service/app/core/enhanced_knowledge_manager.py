"""
统一知识库管理器 - 重构版本
基于新的数据模型和处理流程，协调LlamaIndex和Agno两个框架
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.models.database import get_db
from app.utils.cache import cached
from app.repositories import (
    KnowledgeBaseRepository,
    DocumentRepository, 
    DocumentChunkRepository,
    ProcessingJobRepository
)
from app.schemas.knowledge_schemas import (
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeBaseResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
    SearchMode,
    ProcessingStatus
)
from app.services.document_processing import (
    DocumentProcessor,
    EmbeddingService
)
from app.core.llamaindex_manager import get_llamaindex_manager, LlamaIndexManager
from app.core.agno_manager import get_agno_manager, AgnoManager

logger = logging.getLogger(__name__)


class UnifiedKnowledgeManager:
    """统一知识库管理器 - 重构版本"""
    
    def __init__(self, db: Session = None):
        # 数据库会话
        self.db = db or next(get_db())
        
        # Repository层
        self.kb_repo = KnowledgeBaseRepository(self.db)
        self.doc_repo = DocumentRepository(self.db)
        self.chunk_repo = DocumentChunkRepository(self.db)
        self.job_repo = ProcessingJobRepository(self.db)
        
        # 框架管理器
        self.llamaindex_manager = get_llamaindex_manager()
        self.agno_manager = get_agno_manager()
        
        # 文档处理服务
        self.document_processor = DocumentProcessor(self.db)
        self.embedding_service = EmbeddingService(self.db)
        
        logger.info("Unified Knowledge Manager initialized with enhanced data model")
    
    async def create_knowledge_base(self, request: KnowledgeBaseCreate) -> Dict[str, Any]:
        """创建知识库（基于新数据模型）"""
        try:
            # 检查名称是否已存在
            if await self.kb_repo.check_name_exists(request.name):
                return {
                    "success": False,
                    "error": f"Knowledge base with name '{request.name}' already exists"
                }
            
            # 准备知识库数据
            kb_data = {
                "name": request.name,
                "description": request.description,
                "user_id": "system-user-kb-service",  # 使用系统用户ID
                "embedding_provider": request.embedding_provider,
                "embedding_model": request.embedding_model,
                "embedding_dimension": request.embedding_dimension,
                "vector_store_type": request.vector_store_type,
                "vector_store_config": request.vector_store_config or {},
                "chunk_size": request.chunk_size,
                "chunk_overlap": request.chunk_overlap,
                "chunk_strategy": getattr(request, 'chunk_strategy', 'token_based'),
                "similarity_threshold": request.similarity_threshold,
                "enable_hybrid_search": request.enable_hybrid_search,
                "enable_agno_integration": request.enable_agno_integration,
                "agno_search_type": request.agno_search_type,
                "status": "active",
                "settings": request.settings or {}
            }
            
            # 创建知识库记录
            kb = await self.kb_repo.create(kb_data)
            
            # 在LlamaIndex中创建知识库
            llamaindex_result = await self.llamaindex_manager.create_knowledge_base(request, str(kb.id))
            if not llamaindex_result.get("success"):
                # 回滚数据库记录
                await self.kb_repo.delete(kb.id)
                return {
                    "success": False,
                    "error": f"LlamaIndex creation failed: {llamaindex_result.get('error')}",
                    "kb_id": str(kb.id)
                }
            
            # 在Agno中创建知识库（如果启用）
            agno_result = None
            if request.enable_agno_integration:
                agno_result = await self.agno_manager.create_knowledge_base(request, str(kb.id))
                if not agno_result.get("success"):
                    logger.warning(f"Failed to create Agno KB: {agno_result.get('error')}")
            
            # 创建向量存储配置记录
            vector_store_data = {
                "kb_id": kb.id,
                "store_type": request.vector_store_type,
                "collection_name": f"kb_{str(kb.id).replace('-', '_')}",
                "connection_config": request.vector_store_config or {},
                "dimension": request.embedding_dimension,
                "is_primary": True,
                "status": "active"
            }
            
            # 这里应该创建VectorStore记录，但需要先导入VectorStoreRepository
            # 暂时跳过，在后续版本中完善
            
            # 构建响应
            response = KnowledgeBaseResponse(
                id=str(kb.id),
                name=kb.name,
                description=kb.description,
                embedding_provider=kb.embedding_provider,
                embedding_model=kb.embedding_model,
                embedding_dimension=kb.embedding_dimension,
                vector_store_type=kb.vector_store_type,
                chunk_size=kb.chunk_size,
                chunk_overlap=kb.chunk_overlap,
                similarity_threshold=kb.similarity_threshold,
                status=kb.status,
                document_count=kb.document_count,
                chunk_count=kb.chunk_count,
                created_at=kb.created_at,
                updated_at=kb.updated_at,
                settings=kb.settings
            )
            
            logger.info(f"Created unified knowledge base: {kb.id}")
            
            return {
                "success": True,
                "knowledge_base": response.dict(),
                "llamaindex_enabled": True,
                "agno_enabled": request.enable_agno_integration and agno_result and agno_result.get("success", False)
            }
            
        except Exception as e:
            logger.error(f"Failed to create unified knowledge base: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_knowledge_base(self, kb_id: str) -> Optional[Dict[str, Any]]:
        """获取知识库信息（基于新数据模型）"""
        try:
            kb = await self.kb_repo.get_by_id(kb_id)
            if not kb:
                return None
            
            # 获取统计信息
            doc_stats = await self.doc_repo.get_statistics_by_kb(kb.id)
            chunk_stats = await self.chunk_repo.get_statistics_by_document(kb.id) if kb.document_count > 0 else {}
            
            # 更新统计信息
            if doc_stats['total_documents'] != kb.document_count:
                await self.kb_repo.update_statistics(kb.id)
                kb = await self.kb_repo.get_by_id(kb.id)  # 重新获取更新后的数据
            
            # 构建响应
            kb_data = {
                "id": str(kb.id),
                "name": kb.name,
                "description": kb.description,
                "embedding_provider": kb.embedding_provider,
                "embedding_model": kb.embedding_model,
                "embedding_dimension": kb.embedding_dimension,
                "vector_store_type": kb.vector_store_type,
                "chunk_size": kb.chunk_size,
                "chunk_overlap": kb.chunk_overlap,
                "similarity_threshold": kb.similarity_threshold,
                "status": kb.status,
                "document_count": doc_stats['total_documents'],
                "chunk_count": doc_stats['total_chunks'],
                "total_size": doc_stats['total_size'],
                "created_at": kb.created_at,
                "updated_at": kb.updated_at,
                "settings": kb.settings,
                "statistics": {
                    "documents": doc_stats,
                    "chunks": chunk_stats
                }
            }
            
            return kb_data
            
        except Exception as e:
            logger.error(f"Failed to get knowledge base {kb_id}: {e}")
            return None
    
    @cached(ttl=30, key_prefix="kb_list")  # 30秒缓存
    async def list_knowledge_bases(self, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """获取知识库列表（基于新数据模型）"""
        try:
            skip = (page - 1) * page_size
            
            # 获取知识库列表
            knowledge_bases = await self.kb_repo.get_multi(
                skip=skip,
                limit=page_size,
                order_by="updated_at",
                order_desc=True
            )
            
            # 获取总数
            total = await self.kb_repo.count()
            
            # 构建响应列表
            kb_responses = []
            for kb in knowledge_bases:
                response = KnowledgeBaseResponse(
                    id=str(kb.id),
                    name=kb.name,
                    description=kb.description,
                    embedding_provider=kb.embedding_provider,
                    embedding_model=kb.embedding_model,
                    embedding_dimension=kb.embedding_dimension,
                    vector_store_type=kb.vector_store_type,
                    chunk_size=kb.chunk_size,
                    chunk_overlap=kb.chunk_overlap,
                    similarity_threshold=kb.similarity_threshold,
                    status=kb.status,
                    document_count=kb.document_count,
                    chunk_count=kb.chunk_count,
                    created_at=kb.created_at,
                    updated_at=kb.updated_at,
                    settings=kb.settings
                )
                kb_responses.append(response)
            
            return {
                "success": True,
                "knowledge_bases": [kb.dict() for kb in kb_responses],
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
                "total": 0
            }
    
    async def update_knowledge_base(self, kb_id: str, request: KnowledgeBaseUpdate) -> Dict[str, Any]:
        """更新知识库配置（基于新数据模型）"""
        try:
            # 检查知识库是否存在
            kb = await self.kb_repo.get_by_id(kb_id)
            if not kb:
                return {
                    "success": False,
                    "error": "Knowledge base not found"
                }
            
            # 准备更新数据
            update_data = request.dict(exclude_unset=True)
            
            # 更新数据库记录
            updated_kb = await self.kb_repo.update(kb_id, update_data)
            if not updated_kb:
                return {
                    "success": False,
                    "error": "Failed to update knowledge base"
                }
            
            logger.info(f"Updated knowledge base: {kb_id}")
            
            return {
                "success": True,
                "kb_id": kb_id,
                "updated_fields": list(update_data.keys())
            }
            
        except Exception as e:
            logger.error(f"Failed to update knowledge base {kb_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def delete_knowledge_base(self, kb_id: str) -> Dict[str, Any]:
        """删除知识库（基于新数据模型）"""
        try:
            # 检查知识库是否存在
            kb = await self.kb_repo.get_by_id(kb_id)
            if not kb:
                return {
                    "success": False,
                    "error": "Knowledge base not found"
                }
            
            # 从LlamaIndex删除
            llamaindex_result = await self.llamaindex_manager.delete_knowledge_base(kb_id)
            
            # 从Agno删除（如果启用）
            agno_result = None
            if kb.enable_agno_integration:
                agno_result = await self.agno_manager.delete_knowledge_base(kb_id)
            
            # 删除数据库记录（级联删除相关文档和分块）
            success = await self.kb_repo.delete(kb_id)
            if not success:
                return {
                    "success": False,
                    "error": "Failed to delete knowledge base from database"
                }
            
            logger.info(f"Deleted knowledge base: {kb_id}")
            
            return {
                "success": True,
                "kb_id": kb_id,
                "llamaindex_deleted": llamaindex_result.get("success", False),
                "agno_deleted": agno_result.get("success", False) if agno_result else False
            }
            
        except Exception as e:
            logger.error(f"Failed to delete knowledge base {kb_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def upload_documents(self, kb_id: str, files: List[Any], chunk_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """上传文档到知识库（使用新的处理流程）"""
        try:
            # 检查知识库是否存在
            kb = await self.kb_repo.get_by_id(kb_id)
            if not kb:
                return {
                    "success": False,
                    "error": "Knowledge base not found"
                }
            
            # 准备分块配置
            from app.services.document_processing.document_chunker import ChunkConfig
            
            if chunk_config:
                config = ChunkConfig(
                    chunk_size=chunk_config.get('chunk_size', kb.chunk_size),
                    chunk_overlap=chunk_config.get('chunk_overlap', kb.chunk_overlap),
                    strategy=chunk_config.get('strategy', kb.chunk_strategy or 'token_based'),
                    preserve_structure=chunk_config.get('preserve_structure', True)
                )
            else:
                config = ChunkConfig(
                    chunk_size=kb.chunk_size,
                    chunk_overlap=kb.chunk_overlap,
                    strategy=kb.chunk_strategy or 'token_based',
                    preserve_structure=True
                )
            
            # 使用文档处理器处理上传
            result = await self.document_processor.process_upload(
                files=files,
                kb_id=kb_id,
                chunk_config=config
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to upload documents to KB {kb_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def search(self, request: SearchRequest) -> SearchResponse:
        """统一搜索接口（支持多种检索模式）"""
        try:
            start_time = time.time()
            kb_id = request.knowledge_base_id
            
            # 检查知识库是否存在
            kb = await self.kb_repo.get_by_id(kb_id)
            if not kb:
                return SearchResponse(
                    query=request.query,
                    search_mode=request.search_mode.value,
                    results=[],
                    total_results=0,
                    search_time=0.0,
                    llamaindex_results=0,
                    agno_results=0,
                    error="Knowledge base not found"
                )
            
            llamaindex_results = []
            agno_results = []
            
            # 根据搜索模式执行检索
            if request.search_mode == SearchMode.LLAMAINDEX:
                # 精细化检索 - 仅使用LlamaIndex
                llamaindex_response = await self.llamaindex_manager.search(
                    kb_id=kb_id,
                    query=request.query,
                    top_k=request.top_k,
                    similarity_threshold=request.similarity_threshold,
                    enable_reranking=request.enable_reranking,
                    vector_weight=request.vector_weight,
                    text_weight=request.text_weight
                )
                
                if llamaindex_response.get("success"):
                    llamaindex_results = llamaindex_response.get("results", [])
            
            elif request.search_mode == SearchMode.AGNO:
                # 快速检索 - 仅使用Agno框架
                if kb.enable_agno_integration:
                    agno_response = await self.agno_manager.search(
                        kb_id=kb_id,
                        query=request.query,
                        top_k=request.top_k,
                        confidence_threshold=request.agno_confidence_threshold
                    )
                    
                    if agno_response.get("success"):
                        agno_results = agno_response.get("results", [])
            
            elif request.search_mode == SearchMode.HYBRID:
                # 混合模式 - 同时使用两个框架
                tasks = []
                
                # LlamaIndex搜索任务
                llamaindex_task = self.llamaindex_manager.search(
                    kb_id=kb_id,
                    query=request.query,
                    top_k=request.top_k,
                    similarity_threshold=request.similarity_threshold
                )
                tasks.append(llamaindex_task)
                
                # Agno搜索任务（如果启用）
                if kb.enable_agno_integration:
                    agno_task = self.agno_manager.search(
                        kb_id=kb_id,
                        query=request.query,
                        top_k=request.top_k,
                        confidence_threshold=request.agno_confidence_threshold
                    )
                    tasks.append(agno_task)
                
                # 等待所有任务完成
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 处理LlamaIndex结果
                if len(results) > 0 and isinstance(results[0], dict) and results[0].get("success"):
                    llamaindex_results = results[0].get("results", [])
                
                # 处理Agno结果
                if len(results) > 1 and isinstance(results[1], dict) and results[1].get("success"):
                    agno_results = results[1].get("results", [])
            
            # 合并和去重结果
            combined_results = self._merge_search_results(llamaindex_results, agno_results, request.top_k)
            
            search_time = time.time() - start_time
            
            # 构建搜索响应
            response = SearchResponse(
                query=request.query,
                search_mode=request.search_mode.value,
                results=combined_results,
                total_results=len(combined_results),
                search_time=search_time,
                llamaindex_results=len(llamaindex_results),
                agno_results=len(agno_results),
                reranked=request.enable_reranking and request.search_mode in [SearchMode.LLAMAINDEX, SearchMode.HYBRID],
                cached=False  # 缓存功能待实现
            )
            
            logger.info(f"Search completed: {len(combined_results)} results in {search_time:.3f}s")
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to search KB {request.knowledge_base_id}: {e}")
            return SearchResponse(
                query=request.query,
                search_mode=request.search_mode.value,
                results=[],
                total_results=0,
                search_time=0.0,
                llamaindex_results=0,
                agno_results=0,
                error=str(e)
            )
    
    def _merge_search_results(self, llamaindex_results: List[Dict[str, Any]], 
                             agno_results: List[Dict[str, Any]], 
                             top_k: int) -> List[SearchResult]:
        """合并LlamaIndex和Agno的搜索结果"""
        merged_results = []
        seen_content = set()
        
        # 转换LlamaIndex结果
        for result in llamaindex_results:
            content_key = result.get("content", "")[:100]  # 使用内容前100字符作为去重键
            if content_key not in seen_content:
                search_result = SearchResult(
                    chunk_id=result.get("chunk_id", ""),
                    document_id=result.get("document_id", ""),
                    document_name=result.get("document_name", ""),
                    content=result.get("content", ""),
                    score=result.get("score", 0.0),
                    metadata=result.get("metadata", {}),
                    chunk_index=result.get("chunk_index", 0),
                    highlights=None  # 高亮功能待实现
                )
                merged_results.append(search_result)
                seen_content.add(content_key)
        
        # 转换Agno结果
        for result in agno_results:
            content_key = result.get("content", "")[:100]
            if content_key not in seen_content:
                search_result = SearchResult(
                    chunk_id=result.get("document_id", "") + "_agno",  # Agno结果添加后缀
                    document_id=result.get("document_id", ""),
                    document_name=result.get("document_name", ""),
                    content=result.get("content", ""),
                    score=result.get("score", 0.0),
                    metadata=result.get("metadata", {}),
                    chunk_index=0,  # Agno可能不提供chunk_index
                    highlights=None
                )
                merged_results.append(search_result)
                seen_content.add(content_key)
        
        # 按分数排序并限制结果数量
        merged_results.sort(key=lambda x: x.score, reverse=True)
        return merged_results[:top_k]
    
    async def get_statistics(self) -> Dict[str, Any]:
        """获取统一管理器统计信息"""
        try:
            # 获取知识库统计
            kb_stats = await self.kb_repo.get_statistics()
            
            # 获取全局分块统计
            chunk_stats = await self.chunk_repo.get_chunk_statistics_global()
            
            # 获取处理任务统计
            job_stats = await self.job_repo.get_job_statistics()
            
            # 获取框架统计
            llamaindex_stats = self.llamaindex_manager.get_stats()
            agno_stats = self.agno_manager.get_stats()
            
            return {
                "unified_manager": {
                    "total_knowledge_bases": kb_stats.get('total_knowledge_bases', 0),
                    "active_knowledge_bases": kb_stats.get('active_knowledge_bases', 0),
                    "total_documents": kb_stats.get('total_documents', 0),
                    "total_chunks": kb_stats.get('total_chunks', 0),
                    "frameworks_enabled": ["llamaindex", "agno"]
                },
                "knowledge_bases": kb_stats,
                "chunks": chunk_stats,
                "processing_jobs": job_stats,
                "llamaindex": llamaindex_stats,
                "agno": agno_stats
            }
            
        except Exception as e:
            logger.error(f"Failed to get manager stats: {e}")
            return {
                "error": str(e)
            }
    
    async def get_available_embedding_models(self) -> Dict[str, Any]:
        """获取可用的嵌入模型列表（从模型配置获取）"""
        try:
            # 使用配置加载器获取模型配置
            from app.utils.config_loader import get_config_loader
            config_loader = get_config_loader()
            models_info = config_loader.get_embedding_models()
            
            return models_info
            
        except Exception as e:
            logger.error(f"Failed to get available embedding models: {e}")
            return {
                "success": False,
                "error": str(e),
                "models": []
            }


# 全局统一知识库管理器实例
_unified_manager = None

def get_unified_knowledge_manager(db: Session = None) -> UnifiedKnowledgeManager:
    """获取统一知识库管理器实例"""
    global _unified_manager
    if _unified_manager is None or db is not None:
        _unified_manager = UnifiedKnowledgeManager(db)
    return _unified_manager