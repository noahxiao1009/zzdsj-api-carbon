"""
主文档处理器
协调文件上传、文本提取、分块和存储的完整流程
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.repositories import (
    DocumentRepository, 
    DocumentChunkRepository, 
    ProcessingJobRepository
)
from .file_uploader import FileUploader
from .text_extractor import TextExtractor
from .document_chunker import DocumentChunker, ChunkConfig
from app.schemas.knowledge_schemas import DocumentCreate

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """主文档处理器"""
    
    def __init__(self, db: Session):
        self.db = db
        self.file_uploader = FileUploader()
        self.text_extractor = TextExtractor()
        self.document_chunker = DocumentChunker()
        
        # Repository
        self.doc_repo = DocumentRepository(db)
        self.chunk_repo = DocumentChunkRepository(db)
        self.job_repo = ProcessingJobRepository(db)
    
    async def process_upload(
        self, 
        files: List[Any],  # UploadFile列表
        kb_id: UUID,
        chunk_config: Optional[ChunkConfig] = None
    ) -> Dict[str, Any]:
        """
        处理文件上传并开始文档处理流程
        
        Args:
            files: 上传的文件列表
            kb_id: 知识库ID
            chunk_config: 分块配置
            
        Returns:
            处理结果
        """
        try:
            if chunk_config is None:
                chunk_config = ChunkConfig()
            
            results = []
            
            for file in files:
                try:
                    # 上传文件
                    upload_result = await self.file_uploader.upload_file(
                        file=file,
                        kb_id=str(kb_id)
                    )
                    
                    if not upload_result['success']:
                        results.append({
                            'filename': file.filename,
                            'success': False,
                            'error': upload_result['error']
                        })
                        continue
                    
                    # 创建文档记录
                    doc_data = {
                        'kb_id': kb_id,
                        'filename': upload_result['filename'],
                        'original_filename': upload_result['original_filename'],
                        'file_type': upload_result['file_type'],
                        'file_size': upload_result['file_size'],
                        'file_path': upload_result['file_path'],
                        'file_hash': upload_result['file_hash'],
                        'status': 'pending',
                        'processing_stage': 'upload'
                    }
                    
                    document = await self.doc_repo.create(doc_data)
                    
                    # 创建处理任务
                    job_data = {
                        'kb_id': kb_id,
                        'doc_id': document.id,
                        'job_type': 'document_processing',
                        'status': 'pending',
                        'config': {
                            'chunk_config': {
                                'chunk_size': chunk_config.chunk_size,
                                'chunk_overlap': chunk_config.chunk_overlap,
                                'strategy': chunk_config.strategy,
                                'preserve_structure': chunk_config.preserve_structure
                            }
                        }
                    }
                    
                    job = await self.job_repo.create(job_data)
                    
                    # 异步开始处理文档
                    asyncio.create_task(
                        self._process_document_async(document.id, chunk_config, job.id)
                    )
                    
                    results.append({
                        'filename': file.filename,
                        'success': True,
                        'document_id': str(document.id),
                        'job_id': str(job.id),
                        'status': 'processing_started'
                    })
                    
                except Exception as e:
                    logger.error(f"Error processing file {file.filename}: {e}")
                    results.append({
                        'filename': file.filename,
                        'success': False,
                        'error': str(e)
                    })
            
            return {
                'success': True,
                'processed_files': len([r for r in results if r['success']]),
                'failed_files': len([r for r in results if not r['success']]),
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Error in process_upload: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _process_document_async(
        self, 
        doc_id: UUID, 
        chunk_config: ChunkConfig,
        job_id: UUID
    ) -> None:
        """异步处理单个文档"""
        try:
            # 更新任务状态
            await self.job_repo.update_job_status(job_id, "running")
            
            # 获取文档信息
            document = await self.doc_repo.get_by_id(doc_id)
            if not document:
                await self.job_repo.update_job_status(
                    job_id, "failed", 
                    error_message="Document not found"
                )
                return
            
            # 阶段1: 文本提取
            await self.doc_repo.update_processing_status(
                doc_id, "processing", "extract"
            )
            await self.job_repo.update_job_progress(job_id, 1, 4)
            
            extract_result = await self.text_extractor.extract_text(
                document.file_path, document.file_type
            )
            
            if not extract_result['success']:
                await self.doc_repo.update_processing_status(
                    doc_id, "failed", "extract", extract_result['error']
                )
                await self.job_repo.update_job_status(
                    job_id, "failed",
                    error_message=f"Text extraction failed: {extract_result['error']}"
                )
                return
            
            # 更新文档内容
            content = extract_result['content']
            content_preview = extract_result.get('content_preview', '')
            metadata = extract_result.get('metadata', {})
            
            await self.doc_repo.update(doc_id, {
                'content': content,
                'content_preview': content_preview,
                'metadata': metadata
            })
            
            # 阶段2: 文档分块
            await self.doc_repo.update_processing_status(
                doc_id, "processing", "chunk"
            )
            await self.job_repo.update_job_progress(job_id, 2, 4)
            
            chunks = await self.document_chunker.chunk_document(
                content=content,
                config=chunk_config,
                document_metadata={
                    'filename': document.filename,
                    'file_type': document.file_type,
                    'extraction_metadata': metadata
                }
            )
            
            if not chunks:
                await self.doc_repo.update_processing_status(
                    doc_id, "failed", "chunk", "No chunks generated"
                )
                await self.job_repo.update_job_status(
                    job_id, "failed",
                    error_message="Document chunking produced no results"
                )
                return
            
            # 阶段3: 保存分块
            await self.doc_repo.update_processing_status(
                doc_id, "processing", "save_chunks"
            )
            await self.job_repo.update_job_progress(job_id, 3, 4)
            
            chunk_data_list = []
            for chunk in chunks:
                chunk_data = {
                    'doc_id': doc_id,
                    'chunk_index': chunk.index,
                    'content': chunk.content,
                    'content_hash': chunk.content_hash,
                    'start_char': chunk.start_char,
                    'end_char': chunk.end_char,
                    'token_count': chunk.token_count,
                    'char_count': chunk.char_count,
                    'metadata': chunk.metadata,
                    'section_title': chunk.section_title,
                    'embedding_status': 'pending'
                }
                chunk_data_list.append(chunk_data)
            
            # 批量保存分块
            saved_chunks = await self.chunk_repo.batch_create(chunk_data_list)
            
            # 阶段4: 完成处理
            await self.job_repo.update_job_progress(job_id, 4, 4)
            
            # 更新文档统计信息
            total_tokens = sum(chunk.token_count for chunk in chunks)
            await self.doc_repo.update(doc_id, {
                'status': 'completed',
                'processing_stage': 'completed',
                'chunk_count': len(saved_chunks),
                'token_count': total_tokens,
                'processed_at': datetime.now()
            })
            
            # 获取分块统计信息
            chunk_stats = await self.document_chunker.get_chunk_statistics(chunks)
            
            # 完成任务
            await self.job_repo.update_job_status(
                job_id, "completed",
                result={
                    'chunks_created': len(saved_chunks),
                    'total_tokens': total_tokens,
                    'chunk_statistics': chunk_stats
                }
            )
            
            logger.info(f"Document {doc_id} processed successfully: {len(saved_chunks)} chunks created")
            
        except Exception as e:
            logger.error(f"Error processing document {doc_id}: {e}")
            
            # 更新失败状态
            await self.doc_repo.update_processing_status(
                doc_id, "failed", None, str(e)
            )
            await self.job_repo.update_job_status(
                job_id, "failed",
                error_message=str(e)
            )
    
    async def reprocess_document(
        self, 
        doc_id: UUID, 
        chunk_config: Optional[ChunkConfig] = None
    ) -> Dict[str, Any]:
        """重新处理文档"""
        try:
            document = await self.doc_repo.get_by_id(doc_id)
            if not document:
                return {
                    'success': False,
                    'error': 'Document not found'
                }
            
            if chunk_config is None:
                chunk_config = ChunkConfig()
            
            # 删除现有分块
            await self.chunk_repo.delete_by_document(doc_id)
            
            # 创建新的处理任务
            job_data = {
                'kb_id': document.kb_id,
                'doc_id': doc_id,
                'job_type': 'document_reprocessing',
                'status': 'pending',
                'config': {
                    'chunk_config': {
                        'chunk_size': chunk_config.chunk_size,
                        'chunk_overlap': chunk_config.chunk_overlap,
                        'strategy': chunk_config.strategy,
                        'preserve_structure': chunk_config.preserve_structure
                    }
                }
            }
            
            job = await self.job_repo.create(job_data)
            
            # 重置文档状态
            await self.doc_repo.update(doc_id, {
                'status': 'pending',
                'processing_stage': 'reprocess',
                'chunk_count': 0,
                'error_message': None
            })
            
            # 异步开始重新处理
            asyncio.create_task(
                self._process_document_async(doc_id, chunk_config, job.id)
            )
            
            return {
                'success': True,
                'job_id': str(job.id),
                'message': 'Document reprocessing started'
            }
            
        except Exception as e:
            logger.error(f"Error reprocessing document {doc_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_processing_status(self, doc_id: UUID) -> Dict[str, Any]:
        """获取文档处理状态"""
        try:
            document = await self.doc_repo.get_by_id(doc_id)
            if not document:
                return {
                    'success': False,
                    'error': 'Document not found'
                }
            
            # 获取最新的处理任务
            jobs = await self.job_repo.get_by_document(doc_id)
            latest_job = jobs[0] if jobs else None
            
            # 获取分块统计
            chunk_stats = await self.chunk_repo.get_statistics_by_document(doc_id)
            
            return {
                'success': True,
                'document_id': str(doc_id),
                'filename': document.filename,
                'status': document.status,
                'processing_stage': document.processing_stage,
                'error_message': document.error_message,
                'chunk_count': document.chunk_count,
                'token_count': document.token_count,
                'processed_at': document.processed_at.isoformat() if document.processed_at else None,
                'job_info': {
                    'job_id': str(latest_job.id) if latest_job else None,
                    'status': latest_job.status if latest_job else None,
                    'progress': latest_job.progress if latest_job else 0,
                    'started_at': latest_job.started_at.isoformat() if latest_job and latest_job.started_at else None,
                    'completed_at': latest_job.completed_at.isoformat() if latest_job and latest_job.completed_at else None
                } if latest_job else None,
                'chunk_statistics': chunk_stats
            }
            
        except Exception as e:
            logger.error(f"Error getting processing status for {doc_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def cancel_processing(self, doc_id: UUID) -> Dict[str, Any]:
        """取消文档处理"""
        try:
            # 取消待处理的任务
            document = await self.doc_repo.get_by_id(doc_id)
            if not document:
                return {
                    'success': False,
                    'error': 'Document not found'
                }
            
            cancelled_jobs = await self.job_repo.cancel_pending_jobs(
                document.kb_id, "document_processing"
            )
            
            # 更新文档状态
            if document.status in ['pending', 'processing']:
                await self.doc_repo.update_processing_status(
                    doc_id, "cancelled", None, "Processing cancelled by user"
                )
            
            return {
                'success': True,
                'cancelled_jobs': len(cancelled_jobs),
                'message': 'Document processing cancelled'
            }
            
        except Exception as e:
            logger.error(f"Error cancelling processing for {doc_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }