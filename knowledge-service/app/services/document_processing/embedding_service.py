"""
嵌入服务
处理文档分块的向量化
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
import httpx

from app.repositories import DocumentChunkRepository, ProcessingJobRepository
from app.config.settings import settings
# from shared.service_client import call_service, CallMethod, CallConfig
# TODO: Fix shared module import - using dummy implementations for now

class CallMethod:
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"

class CallConfig:
    def __init__(self, timeout=30, retry_times=3, circuit_breaker_enabled=True):
        self.timeout = timeout
        self.retry_times = retry_times
        self.circuit_breaker_enabled = circuit_breaker_enabled

async def call_service(service_name: str, method: str, path: str, json=None, config=None):
    """Dummy service call implementation"""
    return {"success": False, "error": "Service client not available"}

logger = logging.getLogger(__name__)


class EmbeddingService:
    """嵌入向量化服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.chunk_repo = DocumentChunkRepository(db)
        self.job_repo = ProcessingJobRepository(db)
        
        # 服务调用配置
        self.call_config = CallConfig(
            timeout=300,  # 5分钟超时
            retry_times=3,
            circuit_breaker_enabled=True
        )
    
    async def process_pending_embeddings(
        self, 
        kb_id: Optional[UUID] = None,
        batch_size: int = 50
    ) -> Dict[str, Any]:
        """
        处理待嵌入的分块
        
        Args:
            kb_id: 知识库ID（可选，用于限制范围）
            batch_size: 批处理大小
            
        Returns:
            处理结果
        """
        try:
            # 获取待处理的分块
            pending_chunks = await self.chunk_repo.get_pending_embedding_chunks(
                limit=batch_size
            )
            
            if kb_id:
                # 筛选指定知识库的分块
                pending_chunks = [
                    chunk for chunk in pending_chunks 
                    if str(chunk.document.kb_id) == str(kb_id)
                ]
            
            if not pending_chunks:
                return {
                    'success': True,
                    'message': 'No pending chunks to process',
                    'processed_count': 0
                }
            
            # 按文档分组处理
            chunks_by_kb = {}
            for chunk in pending_chunks:
                kb_id_str = str(chunk.document.kb_id)
                if kb_id_str not in chunks_by_kb:
                    chunks_by_kb[kb_id_str] = []
                chunks_by_kb[kb_id_str].append(chunk)
            
            total_processed = 0
            results = {}
            
            # 为每个知识库创建嵌入任务
            for kb_id_str, kb_chunks in chunks_by_kb.items():
                # 创建嵌入任务
                job_data = {
                    'kb_id': UUID(kb_id_str),
                    'job_type': 'embedding_processing',
                    'status': 'pending',
                    'total_items': len(kb_chunks),
                    'config': {
                        'chunk_ids': [str(chunk.id) for chunk in kb_chunks],
                        'batch_size': batch_size
                    }
                }
                
                job = await self.job_repo.create(job_data)
                
                # 异步处理嵌入
                asyncio.create_task(
                    self._process_embedding_batch(kb_chunks, job.id)
                )
                
                results[kb_id_str] = {
                    'job_id': str(job.id),
                    'chunk_count': len(kb_chunks)
                }
                total_processed += len(kb_chunks)
            
            return {
                'success': True,
                'total_processed': total_processed,
                'knowledge_bases': len(chunks_by_kb),
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Error processing pending embeddings: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _process_embedding_batch(
        self, 
        chunks: List[Any], 
        job_id: UUID
    ) -> None:
        """处理一批分块的嵌入"""
        try:
            # 更新任务状态
            await self.job_repo.update_job_status(job_id, "running")
            
            processed_count = 0
            failed_count = 0
            
            # 获取知识库配置（从第一个分块）
            if not chunks:
                await self.job_repo.update_job_status(
                    job_id, "completed",
                    result={'processed': 0, 'failed': 0}
                )
                return
            
            first_chunk = chunks[0]
            kb_id = first_chunk.document.kb_id
            
            # 获取知识库的嵌入配置
            embedding_config = await self._get_knowledge_base_config(kb_id)
            
            # 分批处理
            batch_size = 10  # 每次处理10个分块
            for i in range(0, len(chunks), batch_size):
                batch_chunks = chunks[i:i + batch_size]
                
                try:
                    # 准备文本数据
                    texts = [chunk.content for chunk in batch_chunks]
                    chunk_ids = [str(chunk.id) for chunk in batch_chunks]
                    
                    # 调用模型服务进行嵌入
                    embedding_result = await self._call_embedding_service(
                        texts=texts,
                        model=embedding_config['embedding_model'],
                        chunk_ids=chunk_ids
                    )
                    
                    if embedding_result['success']:
                        # 更新分块嵌入状态
                        embeddings = embedding_result['embeddings']
                        
                        for j, chunk in enumerate(batch_chunks):
                            if j < len(embeddings):
                                embedding_data = embeddings[j]
                                
                                # 存储到向量数据库
                                vector_result = await self._store_vector(
                                    chunk=chunk,
                                    embedding=embedding_data['embedding'],
                                    embedding_config=embedding_config
                                )
                                
                                if vector_result['success']:
                                    # 更新分块状态
                                    await self.chunk_repo.update_embedding_status(
                                        chunk.id,
                                        status="completed",
                                        embedding_id=vector_result['embedding_id'],
                                        embedding_model=embedding_config['embedding_model']
                                    )
                                    processed_count += 1
                                else:
                                    await self.chunk_repo.update_embedding_status(
                                        chunk.id,
                                        status="failed"
                                    )
                                    failed_count += 1
                            else:
                                failed_count += 1
                    else:
                        # 整个批次失败
                        for chunk in batch_chunks:
                            await self.chunk_repo.update_embedding_status(
                                chunk.id,
                                status="failed"
                            )
                        failed_count += len(batch_chunks)
                    
                    # 更新任务进度
                    await self.job_repo.update_job_progress(
                        job_id, 
                        processed_count + failed_count,
                        len(chunks)
                    )
                    
                except Exception as e:
                    logger.error(f"Error processing embedding batch: {e}")
                    # 标记批次中的所有分块为失败
                    for chunk in batch_chunks:
                        await self.chunk_repo.update_embedding_status(
                            chunk.id,
                            status="failed"
                        )
                    failed_count += len(batch_chunks)
            
            # 完成任务
            await self.job_repo.update_job_status(
                job_id, "completed",
                result={
                    'processed': processed_count,
                    'failed': failed_count,
                    'total': len(chunks)
                }
            )
            
            logger.info(f"Embedding batch completed: {processed_count} processed, {failed_count} failed")
            
        except Exception as e:
            logger.error(f"Error in embedding batch processing: {e}")
            await self.job_repo.update_job_status(
                job_id, "failed",
                error_message=str(e)
            )
    
    async def _get_knowledge_base_config(self, kb_id: UUID) -> Dict[str, Any]:
        """获取知识库的嵌入配置"""
        try:
            # 调用知识库服务获取配置
            result = await call_service(
                service_name="knowledge-service",
                method=CallMethod.GET,
                path=f"/api/v1/knowledge-bases/{kb_id}",
                config=self.call_config
            )
            
            if result.get('success'):
                kb_data = result['data']
                return {
                    'embedding_model': kb_data.get('embedding_model', 'text-embedding-3-small'),
                    'embedding_provider': kb_data.get('embedding_provider', 'openai'),
                    'vector_store_type': kb_data.get('vector_store_type', 'milvus'),
                    'vector_store_config': kb_data.get('vector_store_config', {})
                }
            else:
                # 使用默认配置
                return {
                    'embedding_model': 'text-embedding-3-small',
                    'embedding_provider': 'openai',
                    'vector_store_type': 'milvus',
                    'vector_store_config': {}
                }
                
        except Exception as e:
            logger.warning(f"Error getting KB config, using defaults: {e}")
            return {
                'embedding_model': 'text-embedding-3-small',
                'embedding_provider': 'openai',
                'vector_store_type': 'milvus',
                'vector_store_config': {}
            }
    
    async def _call_embedding_service(
        self, 
        texts: List[str], 
        model: str,
        chunk_ids: List[str]
    ) -> Dict[str, Any]:
        """调用模型服务进行嵌入"""
        try:
            request_data = {
                'texts': texts,
                'model': model,
                'chunk_ids': chunk_ids
            }
            
            result = await call_service(
                service_name="model-service",
                method=CallMethod.POST,
                path="/api/v1/embeddings/batch",
                json=request_data,
                config=self.call_config
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error calling embedding service: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _store_vector(
        self, 
        chunk: Any, 
        embedding: List[float],
        embedding_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """存储向量到向量数据库"""
        try:
            # 准备向量数据
            vector_data = {
                'id': str(chunk.id),
                'vector': embedding,
                'metadata': {
                    'chunk_id': str(chunk.id),
                    'doc_id': str(chunk.doc_id),
                    'kb_id': str(chunk.document.kb_id),
                    'content': chunk.content,
                    'chunk_index': chunk.chunk_index,
                    'token_count': chunk.token_count,
                    'section_title': chunk.section_title,
                    **chunk.metadata
                }
            }
            
            # 根据向量存储类型调用相应服务
            if embedding_config['vector_store_type'] == 'milvus':
                result = await self._store_to_milvus(vector_data, embedding_config)
            else:
                # 其他向量存储类型的实现
                result = {'success': False, 'error': 'Unsupported vector store type'}
            
            return result
            
        except Exception as e:
            logger.error(f"Error storing vector: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _store_to_milvus(
        self, 
        vector_data: Dict[str, Any],
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """存储向量到Milvus"""
        try:
            # 这里应该调用向量存储服务或直接操作Milvus
            # 暂时模拟成功响应
            embedding_id = f"milvus_{vector_data['id']}"
            
            # 实际实现中，这里会调用Milvus API或相关服务
            
            return {
                'success': True,
                'embedding_id': embedding_id,
                'vector_store': 'milvus'
            }
            
        except Exception as e:
            logger.error(f"Error storing to Milvus: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_embedding_statistics(self, kb_id: Optional[UUID] = None) -> Dict[str, Any]:
        """获取嵌入统计信息"""
        try:
            if kb_id:
                # 获取特定知识库的统计
                # 这里需要实现按知识库筛选的逻辑
                stats = await self.chunk_repo.get_chunk_statistics_global()
            else:
                stats = await self.chunk_repo.get_chunk_statistics_global()
            
            return {
                'success': True,
                'statistics': stats
            }
            
        except Exception as e:
            logger.error(f"Error getting embedding statistics: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def retry_failed_embeddings(self, kb_id: Optional[UUID] = None) -> Dict[str, Any]:
        """重试失败的嵌入"""
        try:
            # 获取失败的分块
            failed_chunks = await self.chunk_repo.get_by_embedding_status("failed")
            
            if kb_id:
                failed_chunks = [
                    chunk for chunk in failed_chunks 
                    if str(chunk.document.kb_id) == str(kb_id)
                ]
            
            if not failed_chunks:
                return {
                    'success': True,
                    'message': 'No failed embeddings to retry',
                    'retry_count': 0
                }
            
            # 重置状态为pending
            chunk_ids = [chunk.id for chunk in failed_chunks]
            await self.chunk_repo.batch_update_embedding_status(
                chunk_ids, "pending"
            )
            
            # 启动重新处理
            result = await self.process_pending_embeddings(kb_id)
            
            return {
                'success': True,
                'retry_count': len(failed_chunks),
                'processing_result': result
            }
            
        except Exception as e:
            logger.error(f"Error retrying failed embeddings: {e}")
            return {
                'success': False,
                'error': str(e)
            }