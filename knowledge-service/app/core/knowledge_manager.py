"""
统一知识库管理器
协调LlamaIndex和Agno两个框架，支持两种检索模式：
1. 精细化检索（LlamaIndex）
2. 快速检索（Agno框架，search_knowledge=true）
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

from app.config.settings import settings
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
from app.core.llamaindex_manager import get_llamaindex_manager, LlamaIndexManager
from app.core.agno_manager import get_agno_manager, AgnoManager

logger = logging.getLogger(__name__)


class UnifiedKnowledgeManager:
    """统一知识库管理器"""
    
    def __init__(self):
        # 框架管理器
        self.llamaindex_manager = get_llamaindex_manager()
        self.agno_manager = get_agno_manager()
        
        # 知识库元数据存储
        self.knowledge_bases: Dict[str, Dict[str, Any]] = {}
        
        # 外部服务客户端
        self.model_service_client = None  # 将来集成模型服务
        
        logger.info("Unified Knowledge Manager initialized")
    
    async def create_knowledge_base(self, request: KnowledgeBaseCreate) -> Dict[str, Any]:
        """创建知识库（同时在LlamaIndex和Agno中创建）"""
        try:
            kb_id = str(uuid.uuid4())
            creation_time = datetime.now()
            
            # 创建知识库元数据
            kb_metadata = {
                "id": kb_id,
                "name": request.name,
                "description": request.description,
                "embedding_provider": request.embedding_provider,
                "embedding_model": request.embedding_model,
                "embedding_dimension": request.embedding_dimension,
                "vector_store_type": request.vector_store_type,
                "chunk_size": request.chunk_size,
                "chunk_overlap": request.chunk_overlap,
                "similarity_threshold": request.similarity_threshold,
                "enable_hybrid_search": request.enable_hybrid_search,
                "enable_agno_integration": request.enable_agno_integration,
                "agno_search_type": request.agno_search_type,
                "status": "active",
                "document_count": 0,
                "chunk_count": 0,
                "created_at": creation_time,
                "updated_at": creation_time,
                "settings": request.settings or {}
            }
            
            # 在LlamaIndex中创建知识库
            llamaindex_result = await self.llamaindex_manager.create_knowledge_base(request, kb_id)
            if not llamaindex_result.get("success"):
                logger.error(f"Failed to create LlamaIndex KB: {llamaindex_result.get('error')}")
                return {
                    "success": False,
                    "error": f"LlamaIndex creation failed: {llamaindex_result.get('error')}",
                    "kb_id": kb_id
                }
            
            # 在Agno中创建知识库（如果启用）
            agno_result = None
            if request.enable_agno_integration:
                agno_result = await self.agno_manager.create_knowledge_base(request, kb_id)
                if not agno_result.get("success"):
                    logger.warning(f"Failed to create Agno KB: {agno_result.get('error')}")
                    # 不完全失败，只是警告
            
            # 存储知识库元数据
            self.knowledge_bases[kb_id] = kb_metadata
            
            # 构建响应
            response = KnowledgeBaseResponse(
                id=kb_id,
                name=request.name,
                description=request.description,
                embedding_provider=request.embedding_provider,
                embedding_model=request.embedding_model,
                embedding_dimension=request.embedding_dimension,
                vector_store_type=request.vector_store_type,
                chunk_size=request.chunk_size,
                chunk_overlap=request.chunk_overlap,
                similarity_threshold=request.similarity_threshold,
                status="active",
                document_count=0,
                chunk_count=0,
                created_at=creation_time,
                updated_at=creation_time,
                settings=request.settings or {}
            )
            
            logger.info(f"Created unified knowledge base: {kb_id}")
            
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
        """获取知识库信息"""
        kb_metadata = self.knowledge_bases.get(kb_id)
        if not kb_metadata:
            return None
        
        # 获取最新统计信息
        try:
            llamaindex_stats = {}
            llamaindex_kb = await self.llamaindex_manager.get_knowledge_base(kb_id)
            if llamaindex_kb:
                llamaindex_stats = llamaindex_kb.get_stats()
            
            agno_stats = {}
            if kb_metadata.get("enable_agno_integration"):
                agno_kb = await self.agno_manager.get_knowledge_base(kb_id)
                if agno_kb:
                    agno_stats = agno_kb.get_stats()
            
            # 更新统计信息
            kb_metadata["document_count"] = llamaindex_stats.get("total_documents", 0)
            kb_metadata["chunk_count"] = llamaindex_stats.get("total_chunks", 0)
            
        except Exception as e:
            logger.warning(f"Failed to update KB stats: {e}")
        
        return kb_metadata
    
    async def list_knowledge_bases(self, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """获取知识库列表"""
        try:
            all_kbs = list(self.knowledge_bases.values())
            total = len(all_kbs)
            
            # 分页
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_kbs = all_kbs[start_idx:end_idx]
            
            # 转换为响应格式
            kb_responses = []
            for kb_data in paginated_kbs:
                response = KnowledgeBaseResponse(
                    id=kb_data["id"],
                    name=kb_data["name"],
                    description=kb_data.get("description"),
                    embedding_provider=kb_data["embedding_provider"],
                    embedding_model=kb_data["embedding_model"],
                    embedding_dimension=kb_data["embedding_dimension"],
                    vector_store_type=kb_data["vector_store_type"],
                    chunk_size=kb_data["chunk_size"],
                    chunk_overlap=kb_data["chunk_overlap"],
                    similarity_threshold=kb_data["similarity_threshold"],
                    status=kb_data["status"],
                    document_count=kb_data["document_count"],
                    chunk_count=kb_data["chunk_count"],
                    created_at=kb_data["created_at"],
                    updated_at=kb_data["updated_at"],
                    settings=kb_data.get("settings", {})
                )
                kb_responses.append(response)
            
            return {
                "success": True,
                "knowledge_bases": [kb.dict() for kb in kb_responses],
                "total": total,
                "page": page,
                "page_size": page_size
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
        """更新知识库配置"""
        try:
            kb_metadata = self.knowledge_bases.get(kb_id)
            if not kb_metadata:
                return {
                    "success": False,
                    "error": "Knowledge base not found"
                }
            
            # 更新元数据
            update_fields = request.dict(exclude_unset=True)
            for field, value in update_fields.items():
                if field in kb_metadata:
                    kb_metadata[field] = value
            
            kb_metadata["updated_at"] = datetime.now()
            
            logger.info(f"Updated knowledge base: {kb_id}")
            
            return {
                "success": True,
                "kb_id": kb_id,
                "updated_fields": list(update_fields.keys())
            }
            
        except Exception as e:
            logger.error(f"Failed to update knowledge base {kb_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def delete_knowledge_base(self, kb_id: str) -> Dict[str, Any]:
        """删除知识库"""
        try:
            if kb_id not in self.knowledge_bases:
                return {
                    "success": False,
                    "error": "Knowledge base not found"
                }
            
            kb_metadata = self.knowledge_bases[kb_id]
            
            # 从LlamaIndex删除
            llamaindex_result = await self.llamaindex_manager.delete_knowledge_base(kb_id)
            
            # 从Agno删除（如果启用）
            agno_result = None
            if kb_metadata.get("enable_agno_integration"):
                agno_result = await self.agno_manager.delete_knowledge_base(kb_id)
            
            # 删除元数据
            del self.knowledge_bases[kb_id]
            
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
    
    async def add_documents(self, kb_id: str, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """向知识库添加文档"""
        try:
            kb_metadata = self.knowledge_bases.get(kb_id)
            if not kb_metadata:
                return {
                    "success": False,
                    "error": "Knowledge base not found"
                }
            
            # 添加到LlamaIndex
            llamaindex_result = await self.llamaindex_manager.add_documents(kb_id, documents)
            
            # 添加到Agno（如果启用）
            agno_result = None
            if kb_metadata.get("enable_agno_integration"):
                agno_result = await self.agno_manager.add_documents(kb_id, documents)
            
            # 更新统计信息
            if llamaindex_result.get("success"):
                kb_metadata["document_count"] += llamaindex_result.get("added_count", 0)
                kb_metadata["chunk_count"] += llamaindex_result.get("chunk_count", 0)
                kb_metadata["updated_at"] = datetime.now()
            
            return {
                "success": True,
                "kb_id": kb_id,
                "llamaindex_result": llamaindex_result,
                "agno_result": agno_result,
                "total_added": llamaindex_result.get("added_count", 0)
            }
            
        except Exception as e:
            logger.error(f"Failed to add documents to KB {kb_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def search(self, request: SearchRequest) -> SearchResponse:
        """统一搜索接口，支持多种检索模式"""
        try:
            start_time = time.time()
            kb_id = request.knowledge_base_id
            
            kb_metadata = self.knowledge_bases.get(kb_id)
            if not kb_metadata:
                return SearchResponse(
                    query=request.query,
                    search_mode=request.search_mode.value,
                    results=[],
                    total_results=0,
                    search_time=0.0,
                    llamaindex_results=0,
                    agno_results=0
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
                if kb_metadata.get("enable_agno_integration"):
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
                # 启动并行搜索
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
                if kb_metadata.get("enable_agno_integration"):
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
                agno_results=0
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
    
    async def get_available_embedding_models(self) -> Dict[str, Any]:
        """获取可用的嵌入模型列表（从模型服务获取）"""
        try:
            # 这里应该调用模型服务API
            # 暂时返回模拟数据
            models = [
                {
                    "provider": "openai",
                    "model_name": "text-embedding-3-small",
                    "dimension": 1536,
                    "description": "OpenAI 最新小型嵌入模型"
                },
                {
                    "provider": "openai", 
                    "model_name": "text-embedding-3-large",
                    "dimension": 3072,
                    "description": "OpenAI 最新大型嵌入模型"
                },
                {
                    "provider": "azure_openai",
                    "model_name": "text-embedding-ada-002",
                    "dimension": 1536,
                    "description": "Azure OpenAI 嵌入模型"
                },
                {
                    "provider": "huggingface",
                    "model_name": "sentence-transformers/all-MiniLM-L6-v2",
                    "dimension": 384,
                    "description": "HuggingFace 轻量级嵌入模型"
                }
            ]
            
            provider_counts = {}
            for model in models:
                provider = model["provider"]
                provider_counts[provider] = provider_counts.get(provider, 0) + 1
            
            return {
                "success": True,
                "models": models,
                "total": len(models),
                "provider_counts": provider_counts
            }
            
        except Exception as e:
            logger.error(f"Failed to get available embedding models: {e}")
            return {
                "success": False,
                "error": str(e),
                "models": []
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统一管理器统计信息"""
        try:
            llamaindex_stats = self.llamaindex_manager.get_stats()
            agno_stats = self.agno_manager.get_stats()
            
            total_kbs = len(self.knowledge_bases)
            active_kbs = len([kb for kb in self.knowledge_bases.values() if kb["status"] == "active"])
            
            return {
                "unified_manager": {
                    "total_knowledge_bases": total_kbs,
                    "active_knowledge_bases": active_kbs,
                    "frameworks_enabled": ["llamaindex", "agno"]
                },
                "llamaindex": llamaindex_stats,
                "agno": agno_stats
            }
            
        except Exception as e:
            logger.error(f"Failed to get manager stats: {e}")
            return {
                "error": str(e)
            }


# 全局统一知识库管理器实例
_unified_manager = None

def get_unified_knowledge_manager() -> UnifiedKnowledgeManager:
    """获取统一知识库管理器实例"""
    global _unified_manager
    if _unified_manager is None:
        _unified_manager = UnifiedKnowledgeManager()
    return _unified_manager 