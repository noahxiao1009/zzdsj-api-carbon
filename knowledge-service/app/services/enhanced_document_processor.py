"""
增强的文档处理服务
集成硅基流动API进行文档向量化和检索
"""

import asyncio
import logging
import hashlib
import os
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.knowledge_models import KnowledgeBase, Document, DocumentChunk
from app.services.siliconflow_client import get_siliconflow_client, create_embeddings, rerank_documents
from app.core.document_splitter import DocumentSplitter
from app.core.enhanced_knowledge_manager import get_unified_knowledge_manager

logger = logging.getLogger(__name__)


class EnhancedDocumentProcessor:
    """增强的文档处理器，集成硅基流动API"""
    
    def __init__(self, db: Session):
        self.db = db
        self.siliconflow_client = get_siliconflow_client()
        self.document_splitter = DocumentSplitter()
    
    async def process_uploaded_document(
        self,
        kb_id: str,
        file_path: str,
        filename: str,
        title: str = None,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        处理上传的文档
        
        Args:
            kb_id: 知识库ID
            file_path: 文件路径
            filename: 文件名
            title: 文档标题
            metadata: 元数据
            
        Returns:
            处理结果
        """
        try:
            # 获取知识库信息
            kb = self.db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
            if not kb:
                raise ValueError(f"知识库 {kb_id} 不存在")
            
            # 读取文件内容
            content = await self._extract_file_content(file_path, filename)
            
            # 计算文件哈希
            file_hash = self._calculate_file_hash(content)
            
            # 检查是否已存在相同文档
            existing_doc = self.db.query(Document).filter(
                and_(Document.kb_id == kb_id, Document.file_hash == file_hash)
            ).first()
            
            if existing_doc:
                logger.warning(f"文档已存在: {filename}")
                return {
                    "success": False,
                    "error": "DOCUMENT_ALREADY_EXISTS",
                    "message": "文档已存在",
                    "document_id": str(existing_doc.id)
                }
            
            # 创建文档记录
            document = Document(
                kb_id=kb_id,
                filename=filename,
                original_filename=filename,
                file_type=self._get_file_type(filename),
                file_size=len(content.encode('utf-8')),
                file_path=file_path,
                file_hash=file_hash,
                title=title or filename,
                content=content,
                content_preview=content[:500] + "..." if len(content) > 500 else content,
                status="processing",
                processing_stage="extract",
                metadata=metadata or {},
                language="zh"
            )
            
            self.db.add(document)
            self.db.commit()
            self.db.refresh(document)
            
            logger.info(f"创建文档记录: {document.id}")
            
            # 异步处理文档分块和向量化
            asyncio.create_task(self._process_document_chunks(document, kb))
            
            return {
                "success": True,
                "message": "文档上传成功，正在后台处理",
                "document": {
                    "id": str(document.id),
                    "title": document.title,
                    "filename": document.filename,
                    "status": document.status,
                    "processing_stage": document.processing_stage
                }
            }
            
        except Exception as e:
            logger.error(f"处理文档失败: {e}")
            return {
                "success": False,
                "error": "DOCUMENT_PROCESSING_FAILED",
                "message": str(e)
            }
    
    async def _process_document_chunks(self, document: Document, kb: KnowledgeBase):
        """处理文档分块和向量化"""
        try:
            # 更新处理状态
            document.processing_stage = "chunk"
            self.db.commit()
            
            # 文档分块
            chunks = await self._split_document_content(
                document.content,
                kb.chunk_size or 1000,
                kb.chunk_overlap or 200,
                kb.chunk_strategy or "token_based"
            )
            
            logger.info(f"文档 {document.id} 分块完成，共 {len(chunks)} 个分块")
            
            # 创建分块记录
            chunk_objects = []
            for i, chunk_content in enumerate(chunks):
                chunk = DocumentChunk(
                    doc_id=document.id,
                    chunk_index=i,
                    content=chunk_content,
                    content_hash=hashlib.md5(chunk_content.encode()).hexdigest(),
                    token_count=len(chunk_content.split()),
                    char_count=len(chunk_content),
                    embedding_status="pending"
                )
                chunk_objects.append(chunk)
            
            self.db.add_all(chunk_objects)
            document.chunk_count = len(chunks)
            document.processing_stage = "embed"
            self.db.commit()
            
            # 批量生成嵌入向量
            await self._generate_embeddings_for_chunks(chunk_objects, document)
            
            # 更新文档状态
            document.status = "completed"
            document.processing_stage = "completed"
            document.processed_at = datetime.utcnow()
            
            # 更新知识库统计
            kb.document_count = self.db.query(Document).filter(Document.kb_id == kb.id).count()
            kb.chunk_count = self.db.query(DocumentChunk).join(Document).filter(Document.kb_id == kb.id).count()
            
            self.db.commit()
            
            logger.info(f"文档 {document.id} 处理完成")
            
        except Exception as e:
            logger.error(f"处理文档分块失败: {e}")
            document.status = "failed"
            document.error_message = str(e)
            self.db.commit()
    
    async def _generate_embeddings_for_chunks(self, chunks: List[DocumentChunk], document: Document):
        """为分块生成嵌入向量"""
        try:
            # 提取分块内容
            chunk_texts = [chunk.content for chunk in chunks]
            
            # 批量生成嵌入向量
            embeddings = await self.siliconflow_client.create_embedding(chunk_texts)
            
            # 存储向量到向量数据库（这里可以集成Milvus）
            await self._store_embeddings_to_vector_db(chunks, embeddings, document)
            
            # 更新分块状态
            for i, chunk in enumerate(chunks):
                chunk.embedding_status = "completed"
                chunk.embedding_model = "Qwen/Qwen3-Embedding-8B"
                chunk.embedding_id = f"chunk_{chunk.id}"
            
            self.db.commit()
            
            logger.info(f"为文档 {document.id} 的 {len(chunks)} 个分块生成嵌入向量完成")
            
        except Exception as e:
            logger.error(f"生成嵌入向量失败: {e}")
            for chunk in chunks:
                chunk.embedding_status = "failed"
            self.db.commit()
            raise
    
    async def _store_embeddings_to_vector_db(
        self, 
        chunks: List[DocumentChunk], 
        embeddings: List[List[float]], 
        document: Document
    ):
        """存储嵌入向量到向量数据库"""
        try:
            # 使用MCP工具存储到Milvus
            collection_name = f"kb_{document.kb_id}"
            
            # 准备向量数据
            vector_data = []
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                vector_data.append({
                    "id": str(chunk.id),
                    "chunk_id": str(chunk.id),
                    "doc_id": str(document.id),
                    "kb_id": str(document.kb_id),
                    "content": chunk.content,
                    "vector": embedding,
                    "metadata": {
                        "chunk_index": chunk.chunk_index,
                        "filename": document.filename,
                        "title": document.title
                    }
                })
            
            # 调用MCP工具插入数据
            await self._insert_vectors_via_mcp(collection_name, vector_data)
            
            logger.info(f"向量数据存储完成: {len(vector_data)} 条记录")
            
        except Exception as e:
            logger.error(f"存储向量数据失败: {e}")
            raise
    
    async def _insert_vectors_via_mcp(self, collection_name: str, vector_data: List[Dict[str, Any]]):
        """通过MCP工具插入向量数据"""
        try:
            # 这里集成MCP工具的向量插入功能
            # 暂时用日志记录，实际应该调用MCP工具
            logger.info(f"准备插入向量数据到集合 {collection_name}: {len(vector_data)} 条记录")
            
            # TODO: 实际调用MCP工具
            # await call_mcp_tool("milvus_insert_data", {
            #     "collection_name": collection_name,
            #     "data": vector_data
            # })
            
        except Exception as e:
            logger.error(f"MCP向量插入失败: {e}")
            raise
    
    async def search_documents(
        self,
        kb_id: str,
        query: str,
        top_k: int = 10,
        similarity_threshold: float = 0.7,
        use_rerank: bool = True
    ) -> List[Dict[str, Any]]:
        """
        搜索文档
        
        Args:
            kb_id: 知识库ID
            query: 查询文本
            top_k: 返回结果数量
            similarity_threshold: 相似度阈值
            use_rerank: 是否使用重排序
            
        Returns:
            搜索结果列表
        """
        try:
            # 生成查询向量
            query_embedding = await self.siliconflow_client.create_embedding([query])
            query_vector = query_embedding[0]
            
            # 从向量数据库检索相似文档
            candidates = await self._search_similar_chunks(kb_id, query_vector, top_k * 2)
            
            if not candidates:
                return []
            
            # 过滤相似度阈值
            filtered_candidates = [
                candidate for candidate in candidates 
                if candidate.get('similarity_score', 0) >= similarity_threshold
            ]
            
            if not filtered_candidates:
                return []
            
            # 使用重排序模型优化结果
            if use_rerank and len(filtered_candidates) > 1:
                documents_text = [candidate['content'] for candidate in filtered_candidates]
                reranked_results = await self.siliconflow_client.rerank_documents(
                    query=query,
                    documents=documents_text,
                    top_n=top_k
                )
                
                # 重新组织结果
                final_results = []
                for rerank_result in reranked_results:
                    original_candidate = filtered_candidates[rerank_result['index']]
                    original_candidate['rerank_score'] = rerank_result['relevance_score']
                    final_results.append(original_candidate)
            else:
                final_results = filtered_candidates[:top_k]
            
            logger.info(f"搜索完成，返回 {len(final_results)} 个结果")
            return final_results
            
        except Exception as e:
            logger.error(f"文档搜索失败: {e}")
            return []
    
    async def _search_similar_chunks(
        self, 
        kb_id: str, 
        query_vector: List[float], 
        top_k: int
    ) -> List[Dict[str, Any]]:
        """从向量数据库搜索相似分块"""
        try:
            # 这里应该调用MCP工具进行向量搜索
            # 暂时返回模拟数据
            logger.info(f"搜索知识库 {kb_id} 中的相似分块，返回前 {top_k} 个结果")
            
            # TODO: 实际调用MCP工具
            # results = await call_mcp_tool("milvus_vector_search", {
            #     "collection_name": f"kb_{kb_id}",
            #     "vector": query_vector,
            #     "limit": top_k,
            #     "output_fields": ["chunk_id", "doc_id", "content", "metadata"]
            # })
            
            # 返回模拟结果
            return []
            
        except Exception as e:
            logger.error(f"向量搜索失败: {e}")
            return []
    
    async def _extract_file_content(self, file_path: str, filename: str) -> str:
        """提取文件内容"""
        try:
            file_ext = Path(filename).suffix.lower()
            
            if file_ext in ['.txt', '.md']:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            elif file_ext == '.pdf':
                # TODO: 实现PDF内容提取
                return "PDF content extraction not implemented yet"
            elif file_ext in ['.doc', '.docx']:
                # TODO: 实现Word文档内容提取
                return "Word document extraction not implemented yet"
            else:
                raise ValueError(f"不支持的文件类型: {file_ext}")
                
        except Exception as e:
            logger.error(f"文件内容提取失败: {e}")
            raise
    
    async def _split_document_content(
        self, 
        content: str, 
        chunk_size: int, 
        chunk_overlap: int, 
        strategy: str
    ) -> List[str]:
        """分割文档内容"""
        try:
            # 使用文档分割器
            chunks = self.document_splitter.split_text(
                content, 
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                strategy=strategy
            )
            return chunks
            
        except Exception as e:
            logger.error(f"文档分块失败: {e}")
            raise
    
    def _calculate_file_hash(self, content: str) -> str:
        """计算文件内容哈希"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def _get_file_type(self, filename: str) -> str:
        """获取文件类型"""
        return Path(filename).suffix.lower().replace('.', '')
    
    async def get_document_status(self, doc_id: str) -> Dict[str, Any]:
        """获取文档处理状态"""
        try:
            document = self.db.query(Document).filter(Document.id == doc_id).first()
            if not document:
                return {"error": "文档不存在"}
            
            return {
                "id": str(document.id),
                "title": document.title,
                "filename": document.filename,
                "status": document.status,
                "processing_stage": document.processing_stage,
                "chunk_count": document.chunk_count,
                "error_message": document.error_message,
                "created_at": document.created_at.isoformat() if document.created_at else None,
                "processed_at": document.processed_at.isoformat() if document.processed_at else None
            }
            
        except Exception as e:
            logger.error(f"获取文档状态失败: {e}")
            return {"error": str(e)}


def get_enhanced_document_processor(db: Session) -> EnhancedDocumentProcessor:
    """获取增强文档处理器实例"""
    return EnhancedDocumentProcessor(db)
