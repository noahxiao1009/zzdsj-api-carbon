"""
LlamaIndex知识库管理器
基于原始ZZDSJ项目的LlamaIndex框架实现
支持完整的知识库创建、文档处理和检索功能
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
from dataclasses import dataclass, asdict

# 模拟LlamaIndex组件，实际部署时需要安装LlamaIndex
try:
    # LlamaIndex核心组件 - 实际环境中取消注释
    # from llama_index.core import VectorStoreIndex, ServiceContext, StorageContext, Settings
    # from llama_index.core.schema import Document, TextNode
    # from llama_index.core.node_parser import SentenceSplitter
    # from llama_index.embeddings.openai import OpenAIEmbedding
    # from llama_index.vector_stores.postgres import PGVectorStore
    # from llama_index.vector_stores.simple import SimpleVectorStore
    LLAMAINDEX_AVAILABLE = False  # 设为True当LlamaIndex可用时
except ImportError:
    LLAMAINDEX_AVAILABLE = False

from app.config.settings import settings
from app.schemas.knowledge_schemas import (
    KnowledgeBaseCreate,
    EmbeddingProviderType,
    VectorStoreType
)

logger = logging.getLogger(__name__)


@dataclass
class LlamaIndexConfig:
    """LlamaIndex配置"""
    kb_id: str
    collection_name: str
    embedding_provider: str
    embedding_model: str
    embedding_dimension: int
    vector_store_type: str
    chunk_size: int
    chunk_overlap: int
    similarity_threshold: float
    enable_hybrid_search: bool
    enable_reranking: bool
    api_key: Optional[str] = None
    base_url: Optional[str] = None


class MockEmbeddingModel:
    """模拟嵌入模型用于开发测试"""
    
    def __init__(self, model_name: str = "mock-embedding"):
        self.model_name = model_name
        self.dimension = 1536
    
    def get_text_embedding(self, text: str) -> List[float]:
        """生成模拟向量嵌入"""
        import random
        import hashlib
        
        # 基于文本内容生成一致的随机种子
        seed = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
        random.seed(seed)
        
        # 生成固定维度的向量
        return [random.random() for _ in range(self.dimension)]
    
    def get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        """批量生成向量嵌入"""
        return [self.get_text_embedding(text) for text in texts]


class MockVectorStore:
    """模拟向量存储用于开发测试"""
    
    def __init__(self, collection_name: str):
        self.collection_name = collection_name
        self.vectors: Dict[str, Dict[str, Any]] = {}
        self.metadata: Dict[str, Dict[str, Any]] = {}
    
    def add(self, node_id: str, embedding: List[float], metadata: Dict[str, Any]):
        """添加向量"""
        self.vectors[node_id] = {
            "id": node_id,
            "embedding": embedding,
            "metadata": metadata
        }
        self.metadata[node_id] = metadata
    
    def query(self, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """查询相似向量"""
        if not self.vectors:
            return []
        
        # 计算余弦相似度
        similarities = []
        for node_id, data in self.vectors.items():
            similarity = self._cosine_similarity(query_embedding, data["embedding"])
            similarities.append({
                "node_id": node_id,
                "similarity": similarity,
                "metadata": data["metadata"]
            })
        
        # 按相似度排序
        similarities.sort(key=lambda x: x["similarity"], reverse=True)
        return similarities[:top_k]
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        import math
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(a * a for a in vec2))
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)


class MockTextSplitter:
    """模拟文本分割器"""
    
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def split_text(self, text: str) -> List[str]:
        """分割文本"""
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]
            
            # 尝试在句号处断开
            if end < len(text) and '。' in chunk[-100:]:
                last_period = chunk.rfind('。')
                if last_period > len(chunk) // 2:
                    chunk = chunk[:last_period + 1]
                    end = start + len(chunk)
            
            chunks.append(chunk)
            start = end - self.chunk_overlap
            
            if start >= len(text):
                break
        
        return chunks


class LlamaIndexKnowledgeBase:
    """LlamaIndex知识库实例（模拟实现）"""
    
    def __init__(self, config: LlamaIndexConfig):
        self.config = config
        self.kb_id = config.kb_id
        
        # 模拟组件
        self.embedding_model = MockEmbeddingModel(config.embedding_model)
        self.vector_store = MockVectorStore(config.collection_name)
        self.text_splitter = MockTextSplitter(config.chunk_size, config.chunk_overlap)
        
        # 文档存储
        self.documents: Dict[str, Dict[str, Any]] = {}
        self.chunks: Dict[str, Dict[str, Any]] = {}
        
        logger.info(f"LlamaIndex知识库初始化完成: {self.kb_id}")
    
    async def add_documents(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """添加文档到知识库"""
        try:
            added_count = 0
            total_chunks = 0
            
            for doc in documents:
                doc_id = doc.get("id", str(uuid.uuid4()))
                content = doc.get("content", "")
                
                if not content.strip():
                    continue
                
                # 存储原始文档
                self.documents[doc_id] = {
                    "id": doc_id,
                    "name": doc.get("name", ""),
                    "content": content,
                    "metadata": doc.get("metadata", {}),
                    "document_type": doc.get("document_type", ""),
                    "created_at": time.time()
                }
                
                # 分割文档
                chunks = self.text_splitter.split_text(content)
                
                # 处理每个分块
                for i, chunk_text in enumerate(chunks):
                    chunk_id = f"{doc_id}_chunk_{i}"
                    
                    # 生成嵌入
                    embedding = self.embedding_model.get_text_embedding(chunk_text)
                    
                    # 存储分块
                    chunk_metadata = {
                        "document_id": doc_id,
                        "document_name": doc.get("name", ""),
                        "chunk_index": i,
                        "chunk_id": chunk_id,
                        "start_char": i * (self.config.chunk_size - self.config.chunk_overlap),
                        "end_char": (i + 1) * (self.config.chunk_size - self.config.chunk_overlap),
                        **doc.get("metadata", {})
                    }
                    
                    self.chunks[chunk_id] = {
                        "id": chunk_id,
                        "content": chunk_text,
                        "embedding": embedding,
                        "metadata": chunk_metadata
                    }
                    
                    # 添加到向量存储
                    self.vector_store.add(chunk_id, embedding, chunk_metadata)
                    total_chunks += 1
                
                added_count += 1
            
            logger.info(f"Added {added_count} documents, {total_chunks} chunks to KB: {self.kb_id}")
            
            return {
                "success": True,
                "added_count": added_count,
                "chunk_count": total_chunks,
                "kb_id": self.kb_id
            }
            
        except Exception as e:
            logger.error(f"Failed to add documents to KB {self.kb_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "added_count": 0
            }
    
    async def search(self, query: str, top_k: int = 5, **kwargs) -> Dict[str, Any]:
        """在知识库中搜索"""
        try:
            start_time = time.time()
            
            # 生成查询嵌入
            query_embedding = self.embedding_model.get_text_embedding(query)
            
            # 在向量存储中搜索
            similar_chunks = self.vector_store.query(query_embedding, top_k * 2)
            
            # 应用相似度阈值过滤
            threshold = kwargs.get("similarity_threshold", self.config.similarity_threshold)
            filtered_chunks = [
                chunk for chunk in similar_chunks 
                if chunk["similarity"] >= threshold
            ]
            
            # 转换结果格式
            results = []
            for chunk in filtered_chunks[:top_k]:
                chunk_id = chunk["node_id"]
                chunk_data = self.chunks.get(chunk_id, {})
                
                result = {
                    "chunk_id": chunk_id,
                    "document_id": chunk["metadata"].get("document_id", ""),
                    "document_name": chunk["metadata"].get("document_name", ""),
                    "content": chunk_data.get("content", ""),
                    "score": chunk["similarity"],
                    "metadata": chunk["metadata"],
                    "chunk_index": chunk["metadata"].get("chunk_index", 0)
                }
                results.append(result)
            
            search_time = time.time() - start_time
            
            logger.info(f"LlamaIndex search completed: {len(results)} results in {search_time:.3f}s")
            
            return {
                "success": True,
                "results": results,
                "total_results": len(results),
                "search_time": search_time,
                "framework": "llamaindex"
            }
            
        except Exception as e:
            logger.error(f"Failed to search in KB {self.kb_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "results": []
            }
    
    async def query(self, query: str, **kwargs) -> Dict[str, Any]:
        """查询知识库并生成回答"""
        try:
            # 首先进行搜索
            search_result = await self.search(query, top_k=5, **kwargs)
            
            if not search_result["success"]:
                return {
                    "success": False,
                    "error": search_result["error"],
                    "response": ""
                }
            
            # 简单的回答生成（实际应该调用LLM）
            context_chunks = search_result["results"]
            if not context_chunks:
                response = "抱歉，在知识库中没有找到相关信息。"
            else:
                # 组合上下文
                context_text = "\n\n".join([
                    f"片段{i+1}: {chunk['content'][:200]}..."
                    for i, chunk in enumerate(context_chunks[:3])
                ])
                
                response = f"基于知识库内容回答：\n\n根据相关文档，{query}\n\n参考内容：\n{context_text}"
            
            return {
                "success": True,
                "response": response,
                "source_nodes": context_chunks,
                "framework": "llamaindex"
            }
            
        except Exception as e:
            logger.error(f"Failed to query KB {self.kb_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "response": ""
            }
    
    async def delete_documents(self, document_ids: List[str]) -> Dict[str, Any]:
        """删除文档"""
        try:
            deleted_count = 0
            
            for doc_id in document_ids:
                if doc_id in self.documents:
                    # 删除文档
                    del self.documents[doc_id]
                    deleted_count += 1
                    
                    # 删除相关分块
                    chunks_to_delete = [
                        chunk_id for chunk_id, chunk in self.chunks.items()
                        if chunk["metadata"].get("document_id") == doc_id
                    ]
                    
                    for chunk_id in chunks_to_delete:
                        del self.chunks[chunk_id]
                        if chunk_id in self.vector_store.vectors:
                            del self.vector_store.vectors[chunk_id]
                        if chunk_id in self.vector_store.metadata:
                            del self.vector_store.metadata[chunk_id]
            
            return {
                "success": True,
                "deleted_count": deleted_count,
                "kb_id": self.kb_id
            }
            
        except Exception as e:
            logger.error(f"Failed to delete documents from KB {self.kb_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "deleted_count": 0
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取知识库统计信息"""
        return {
            "kb_id": self.kb_id,
            "total_documents": len(self.documents),
            "total_chunks": len(self.chunks),
            "total_vectors": len(self.vector_store.vectors),
            "vector_store_type": self.config.vector_store_type,
            "embedding_model": self.config.embedding_model,
            "chunk_size": self.config.chunk_size,
            "chunk_overlap": self.config.chunk_overlap,
            "similarity_threshold": self.config.similarity_threshold
        }


class LlamaIndexManager:
    """LlamaIndex知识库管理器"""
    
    def __init__(self):
        self.knowledge_bases: Dict[str, LlamaIndexKnowledgeBase] = {}
        logger.info("LlamaIndex Manager initialized")
    
    async def create_knowledge_base(self, request: KnowledgeBaseCreate, kb_id: str) -> Dict[str, Any]:
        """创建知识库"""
        try:
            # 创建LlamaIndex配置
            config = LlamaIndexConfig(
                kb_id=kb_id,
                collection_name=f"kb_{kb_id}",
                embedding_provider=request.embedding_provider,
                embedding_model=request.embedding_model,
                embedding_dimension=request.embedding_dimension,
                vector_store_type=request.vector_store_type,
                chunk_size=request.chunk_size,
                chunk_overlap=request.chunk_overlap,
                similarity_threshold=request.similarity_threshold,
                enable_hybrid_search=request.enable_hybrid_search,
                enable_reranking=True
            )
            
            # 创建知识库实例
            kb = LlamaIndexKnowledgeBase(config)
            
            # 缓存知识库实例
            self.knowledge_bases[kb_id] = kb
            
            logger.info(f"Created LlamaIndex knowledge base: {kb_id}")
            
            return {
                "success": True,
                "kb_id": kb_id,
                "framework": "llamaindex",
                "config": asdict(config)
            }
            
        except Exception as e:
            logger.error(f"Failed to create LlamaIndex knowledge base {kb_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "kb_id": kb_id
            }
    
    async def get_knowledge_base(self, kb_id: str) -> Optional[LlamaIndexKnowledgeBase]:
        """获取知识库实例"""
        return self.knowledge_bases.get(kb_id)
    
    async def delete_knowledge_base(self, kb_id: str) -> Dict[str, Any]:
        """删除知识库"""
        try:
            if kb_id in self.knowledge_bases:
                del self.knowledge_bases[kb_id]
                logger.info(f"Deleted LlamaIndex knowledge base: {kb_id}")
                return {
                    "success": True,
                    "kb_id": kb_id,
                    "framework": "llamaindex"
                }
            else:
                return {
                    "success": False,
                    "error": "Knowledge base not found",
                    "kb_id": kb_id
                }
                
        except Exception as e:
            logger.error(f"Failed to delete LlamaIndex knowledge base {kb_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "kb_id": kb_id
            }
    
    async def add_documents(self, kb_id: str, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """向知识库添加文档"""
        kb = await self.get_knowledge_base(kb_id)
        if not kb:
            return {
                "success": False,
                "error": "Knowledge base not found",
                "kb_id": kb_id
            }
        
        return await kb.add_documents(documents)
    
    async def search(self, kb_id: str, query: str, top_k: int = 5, **kwargs) -> Dict[str, Any]:
        """在知识库中搜索"""
        kb = await self.get_knowledge_base(kb_id)
        if not kb:
            return {
                "success": False,
                "error": "Knowledge base not found",
                "results": []
            }
        
        return await kb.search(query, top_k, **kwargs)
    
    async def query(self, kb_id: str, query: str, **kwargs) -> Dict[str, Any]:
        """查询知识库并生成回答"""
        kb = await self.get_knowledge_base(kb_id)
        if not kb:
            return {
                "success": False,
                "error": "Knowledge base not found",
                "response": ""
            }
        
        return await kb.query(query, **kwargs)
    
    def get_all_knowledge_bases(self) -> List[str]:
        """获取所有知识库ID"""
        return list(self.knowledge_bases.keys())
    
    def get_stats(self) -> Dict[str, Any]:
        """获取管理器统计信息"""
        total_kbs = len(self.knowledge_bases)
        total_documents = 0
        total_chunks = 0
        
        for kb in self.knowledge_bases.values():
            stats = kb.get_stats()
            total_documents += stats.get("total_documents", 0)
            total_chunks += stats.get("total_chunks", 0)
        
        return {
            "framework": "llamaindex",
            "total_knowledge_bases": total_kbs,
            "total_documents": total_documents,
            "total_chunks": total_chunks,
            "available": LLAMAINDEX_AVAILABLE
        }


# 全局LlamaIndex管理器实例
_llamaindex_manager = None

def get_llamaindex_manager() -> LlamaIndexManager:
    """获取LlamaIndex管理器实例"""
    global _llamaindex_manager
    if _llamaindex_manager is None:
        _llamaindex_manager = LlamaIndexManager()
    return _llamaindex_manager 