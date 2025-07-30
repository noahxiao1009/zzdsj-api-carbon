"""
异步任务处理器
与Task Manager (Go)协作，专注AI处理逻辑
保持Python生态优势
"""

import asyncio
import logging
import traceback
from datetime import datetime
from typing import Optional, Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import multiprocessing as mp

from app.config.settings import settings
from app.core.enhanced_knowledge_manager import get_unified_knowledge_manager
from app.services.document_processing.embedding_service import EmbeddingService
from app.services.document_processing.document_processor import DocumentProcessor
from app.services.document_processing.text_extractor import TextExtractor
from app.queues.task_models import TaskModel, TaskStatus, ProcessingTaskModel
from app.utils.grpc_client import TaskManagerGRPCClient

logger = logging.getLogger(__name__)


class AsyncTaskProcessor:
    """
    异步任务处理器
    专门处理从Task Manager分发过来的AI处理任务
    """
    
    def __init__(self, max_workers: int = None):
        """初始化异步任务处理器"""
        self.max_workers = max_workers or min(32, (mp.cpu_count() or 1) + 4)
        
        # 线程池用于IO密集型任务（API调用、数据库操作）
        self.thread_executor = ThreadPoolExecutor(max_workers=self.max_workers)
        
        # 进程池用于CPU密集型任务（文档解析、向量计算）
        self.process_executor = ProcessPoolExecutor(max_workers=mp.cpu_count())
        
        # 核心服务组件
        self.knowledge_manager = None
        self.embedding_service = None
        self.document_processor = None
        self.text_extractor = None
        
        # Task Manager gRPC客户端
        self.task_manager_client = TaskManagerGRPCClient()
        
        # 运行状态
        self.is_running = False
        self.active_tasks = {}
        
        logger.info(f"异步任务处理器初始化完成，线程池: {self.max_workers}, 进程池: {mp.cpu_count()}")
    
    async def initialize(self):
        """初始化处理器组件"""
        try:
            logger.info("初始化异步任务处理器组件")
            
            # 初始化知识库管理器
            self.knowledge_manager = get_unified_knowledge_manager()
            
            # 初始化嵌入服务
            self.embedding_service = EmbeddingService()
            
            # 初始化文档处理器
            self.document_processor = DocumentProcessor()
            self.text_extractor = TextExtractor()
            
            # 初始化Task Manager客户端
            await self.task_manager_client.initialize()
            
            logger.info("异步任务处理器组件初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"异步任务处理器初始化失败: {e}")
            logger.error(traceback.format_exc())
            return False
    
    async def start_processing(self):
        """开始处理任务"""
        if self.is_running:
            logger.warning("异步任务处理器已在运行")
            return
        
        self.is_running = True
        logger.info("启动异步任务处理器")
        
        # 启动任务监听器
        asyncio.create_task(self._task_listener())
        
        # 启动状态报告器
        asyncio.create_task(self._status_reporter())
        
        logger.info("异步任务处理器启动完成")
    
    async def stop_processing(self):
        """停止处理任务"""
        self.is_running = False
        logger.info("正在停止异步任务处理器...")
        
        # 等待活跃任务完成
        if self.active_tasks:
            logger.info(f"等待 {len(self.active_tasks)} 个活跃任务完成")
            await asyncio.gather(*self.active_tasks.values(), return_exceptions=True)
        
        # 关闭执行器
        self.thread_executor.shutdown(wait=True)
        self.process_executor.shutdown(wait=True)
        
        # 关闭gRPC连接
        await self.task_manager_client.close()
        
        logger.info("异步任务处理器已停止")
    
    async def _task_listener(self):
        """监听Task Manager分发的任务"""
        logger.info("启动任务监听器")
        
        while self.is_running:
            try:
                # 从Task Manager获取待处理任务
                tasks = await self.task_manager_client.get_pending_tasks(
                    service_name="knowledge-service",
                    limit=10
                )
                
                if tasks:
                    logger.info(f"接收到 {len(tasks)} 个待处理任务")
                    
                    for task in tasks:
                        # 异步处理每个任务
                        task_future = asyncio.create_task(self._process_task(task))
                        self.active_tasks[task.task_id] = task_future
                        
                        # 清理已完成的任务
                        self._cleanup_completed_tasks()
                
                await asyncio.sleep(2)  # 每2秒轮询一次
                
            except Exception as e:
                logger.error(f"任务监听器出错: {e}")
                await asyncio.sleep(5)  # 出错后等待5秒
    
    async def _process_task(self, task: TaskModel):
        """处理单个任务"""
        start_time = datetime.now()
        
        try:
            logger.info(f"开始处理任务: {task.task_id}, 类型: {task.task_type}")
            
            # 更新任务状态为处理中
            await self.task_manager_client.update_task_status(
                task.task_id,
                TaskStatus.PROCESSING,
                "开始AI处理",
                progress=10
            )
            
            # 根据任务类型分发处理
            if task.task_type == "document_processing":
                result = await self._process_document_task(task)
            elif task.task_type == "embedding_generation":
                result = await self._process_embedding_task(task)
            elif task.task_type == "vector_storage":
                result = await self._process_vector_storage_task(task)
            elif task.task_type == "batch_processing":
                result = await self._process_batch_task(task)
            else:
                raise ValueError(f"不支持的任务类型: {task.task_type}")
            
            # 计算处理时间
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # 更新任务状态为完成
            await self.task_manager_client.update_task_status(
                task.task_id,
                TaskStatus.COMPLETED,
                "AI处理完成",
                progress=100,
                result_data=result,
                metadata={
                    "processing_time": processing_time,
                    "completed_at": datetime.now().isoformat()
                }
            )
            
            logger.info(f"任务处理完成: {task.task_id}, 耗时: {processing_time:.2f}s")
            
        except Exception as e:
            error_msg = f"任务处理失败: {str(e)}"
            logger.error(f"任务 {task.task_id} 处理失败: {e}")
            logger.error(traceback.format_exc())
            
            # 更新任务状态为失败
            await self.task_manager_client.update_task_status(
                task.task_id,
                TaskStatus.FAILED,
                error_msg,
                error_details=traceback.format_exc()
            )
        
        finally:
            # 从活跃任务中移除
            self.active_tasks.pop(task.task_id, None)
    
    async def _process_document_task(self, task: TaskModel) -> Dict[str, Any]:
        """处理文档处理任务（利用Python AI生态优势）"""
        if not isinstance(task, ProcessingTaskModel):
            task_data = task.dict()
            task = ProcessingTaskModel(**task_data)
        
        logger.info(f"开始文档处理: {task.original_filename}")
        
        # 进度更新：20% - 文档解析
        await self.task_manager_client.update_task_status(
            task.task_id, TaskStatus.PROCESSING, "文档解析中", progress=20
        )
        
        # 使用进程池进行CPU密集型的文档解析
        loop = asyncio.get_event_loop()
        extracted_text = await loop.run_in_executor(
            self.process_executor,
            self._extract_document_text,
            task.file_path,
            task.original_filename
        )
        
        # 进度更新：40% - 文本切分
        await self.task_manager_client.update_task_status(
            task.task_id, TaskStatus.PROCESSING, "文本切分中", progress=40
        )
        
        # 文本切分（利用Python丰富的NLP库）
        chunks = await loop.run_in_executor(
            self.thread_executor,
            self._split_text_chunks,
            extracted_text,
            task.custom_splitter_config
        )
        
        # 进度更新：60% - 向量生成
        await self.task_manager_client.update_task_status(
            task.task_id, TaskStatus.PROCESSING, f"向量生成中 (共{len(chunks)}个分块)", progress=60
        )
        
        # 批量生成嵌入向量（利用Python AI模型生态）
        embeddings = await self._generate_embeddings_batch(
            chunks, task.task_id
        )
        
        # 进度更新：80% - 向量存储
        await self.task_manager_client.update_task_status(
            task.task_id, TaskStatus.PROCESSING, "向量存储中", progress=80
        )
        
        # 批量存储向量到Milvus
        vector_ids = await loop.run_in_executor(
            self.thread_executor,
            self._store_vectors_batch,
            task.kb_id,
            chunks,
            embeddings,
            task.file_info
        )
        
        return {
            "document_id": task.file_info.get("file_id"),
            "chunks_count": len(chunks),
            "embeddings_count": len(embeddings),
            "vector_ids": vector_ids[:10],  # 只返回前10个ID作为示例
            "total_vectors": len(vector_ids)
        }
    
    async def _process_embedding_task(self, task: TaskModel) -> Dict[str, Any]:
        """处理嵌入生成任务"""
        logger.info(f"开始嵌入生成: {task.task_id}")
        
        # 从任务载荷中获取文本
        texts = task.payload.get("texts", [])
        model_name = task.payload.get("model_name", "siliconflow-embedding")
        
        # 批量生成嵌入向量
        embeddings = await self._generate_embeddings_batch(
            texts, task.task_id, model_name
        )
        
        return {
            "embeddings_count": len(embeddings),
            "model_name": model_name,
            "dimension": len(embeddings[0]) if embeddings else 0
        }
    
    async def _process_vector_storage_task(self, task: TaskModel) -> Dict[str, Any]:
        """处理向量存储任务"""
        logger.info(f"开始向量存储: {task.task_id}")
        
        # 从任务载荷中获取向量数据
        vectors_data = task.payload.get("vectors", [])
        kb_id = task.payload.get("kb_id")
        
        # 批量存储向量
        loop = asyncio.get_event_loop()
        vector_ids = await loop.run_in_executor(
            self.thread_executor,
            self._store_vectors_from_payload,
            kb_id,
            vectors_data
        )
        
        return {
            "stored_vectors": len(vector_ids),
            "vector_ids": vector_ids[:10]  # 示例
        }
    
    async def _process_batch_task(self, task: TaskModel) -> Dict[str, Any]:
        """处理批量任务"""
        logger.info(f"开始批量处理: {task.task_id}")
        
        # 批量任务的具体实现
        batch_items = task.payload.get("batch_items", [])
        results = []
        
        # 并发处理批量项目
        semaphore = asyncio.Semaphore(5)  # 限制并发数
        
        async def process_item(item):
            async with semaphore:
                # 处理单个批量项目
                return await self._process_single_batch_item(item)
        
        tasks = [process_item(item) for item in batch_items]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = sum(1 for r in results if not isinstance(r, Exception))
        
        return {
            "batch_size": len(batch_items),
            "success_count": success_count,
            "failed_count": len(batch_items) - success_count
        }
    
    def _extract_document_text(self, file_path: str, filename: str) -> str:
        """提取文档文本（CPU密集型，使用进程池）"""
        try:
            # 利用Python丰富的文档处理库
            return self.text_extractor.extract_text(file_path, filename)
        except Exception as e:
            logger.error(f"文档文本提取失败: {e}")
            raise
    
    def _split_text_chunks(self, text: str, splitter_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """文本切分（利用Python NLP生态）"""
        try:
            # 使用现有的切分器
            from app.core.chunkers.chunker_factory import ChunkerFactory
            
            chunker = ChunkerFactory.create_chunker(
                strategy=splitter_config.get("chunk_strategy", "basic"),
                config=splitter_config
            )
            
            return chunker.chunk_text(text)
        except Exception as e:
            logger.error(f"文本切分失败: {e}")
            raise
    
    async def _generate_embeddings_batch(
        self, 
        texts: List[str], 
        task_id: str, 
        model_name: str = "siliconflow-embedding"
    ) -> List[List[float]]:
        """批量生成嵌入向量（利用Python AI生态）"""
        try:
            embeddings = []
            batch_size = 10  # 批次大小
            
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                
                # 使用线程池进行API调用
                loop = asyncio.get_event_loop()
                batch_embeddings = await loop.run_in_executor(
                    self.thread_executor,
                    self.embedding_service.generate_embeddings_batch,
                    batch_texts,
                    model_name
                )
                
                embeddings.extend(batch_embeddings)
                
                # 更新进度
                progress = 60 + int((i + batch_size) / len(texts) * 20)
                await self.task_manager_client.update_task_status(
                    task_id, 
                    TaskStatus.PROCESSING, 
                    f"向量生成进度: {i + batch_size}/{len(texts)}", 
                    progress=min(progress, 80)
                )
            
            return embeddings
        except Exception as e:
            logger.error(f"批量嵌入生成失败: {e}")
            raise
    
    def _store_vectors_batch(
        self, 
        kb_id: str, 
        chunks: List[Dict[str, Any]], 
        embeddings: List[List[float]], 
        file_info: Dict[str, Any]
    ) -> List[str]:
        """批量存储向量（利用Python向量数据库生态）"""
        try:
            # 使用现有的Milvus存储逻辑
            vector_ids = []
            
            for chunk, embedding in zip(chunks, embeddings):
                vector_id = self.knowledge_manager.store_vector(
                    kb_id=kb_id,
                    document_id=file_info.get("file_id"),
                    chunk_id=chunk.get("chunk_id"),
                    text=chunk.get("content"),
                    embedding=embedding,
                    metadata=chunk.get("metadata", {})
                )
                vector_ids.append(vector_id)
            
            return vector_ids
        except Exception as e:
            logger.error(f"批量向量存储失败: {e}")
            raise
    
    def _store_vectors_from_payload(self, kb_id: str, vectors_data: List[Dict[str, Any]]) -> List[str]:
        """从载荷存储向量"""
        try:
            vector_ids = []
            
            for vector_item in vectors_data:
                vector_id = self.knowledge_manager.store_vector(
                    kb_id=kb_id,
                    document_id=vector_item.get("document_id"),
                    chunk_id=vector_item.get("chunk_id"),
                    text=vector_item.get("text"),
                    embedding=vector_item.get("embedding"),
                    metadata=vector_item.get("metadata", {})
                )
                vector_ids.append(vector_id)
            
            return vector_ids
        except Exception as e:
            logger.error(f"向量存储失败: {e}")
            raise
    
    async def _process_single_batch_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """处理单个批量项目"""
        try:
            # 根据项目类型处理
            item_type = item.get("type")
            
            if item_type == "document":
                # 处理文档项目
                return await self._process_document_item(item)
            elif item_type == "text":
                # 处理文本项目
                return await self._process_text_item(item)
            else:
                raise ValueError(f"不支持的批量项目类型: {item_type}")
                
        except Exception as e:
            logger.error(f"批量项目处理失败: {e}")
            raise
    
    async def _process_document_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """处理文档项目"""
        # 简化的文档处理逻辑
        document_path = item.get("path")
        filename = item.get("filename")
        
        # 提取文本
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(
            self.process_executor,
            self._extract_document_text,
            document_path,
            filename
        )
        
        return {
            "filename": filename,
            "text_length": len(text),
            "status": "processed"
        }
    
    async def _process_text_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """处理文本项目"""
        text = item.get("text")
        model_name = item.get("model_name", "siliconflow-embedding")
        
        # 生成嵌入
        embeddings = await self._generate_embeddings_batch([text], "", model_name)
        
        return {
            "text_length": len(text),
            "embedding_dimension": len(embeddings[0]) if embeddings else 0,
            "status": "processed"
        }
    
    def _cleanup_completed_tasks(self):
        """清理已完成的任务"""
        completed_tasks = [
            task_id for task_id, future in self.active_tasks.items()
            if future.done()
        ]
        
        for task_id in completed_tasks:
            self.active_tasks.pop(task_id, None)
    
    async def _status_reporter(self):
        """定期向Task Manager报告处理器状态"""
        while self.is_running:
            try:
                status = {
                    "service_name": "knowledge-service",
                    "active_tasks": len(self.active_tasks),
                    "thread_pool_size": self.max_workers,
                    "process_pool_size": mp.cpu_count(),
                    "is_healthy": True,
                    "timestamp": datetime.now().isoformat()
                }
                
                await self.task_manager_client.report_service_status(status)
                
                await asyncio.sleep(30)  # 每30秒报告一次状态
                
            except Exception as e:
                logger.error(f"状态报告失败: {e}")
                await asyncio.sleep(60)  # 出错后等待更长时间


# 全局异步任务处理器实例
_async_task_processor: Optional[AsyncTaskProcessor] = None


async def get_async_task_processor() -> AsyncTaskProcessor:
    """获取异步任务处理器实例"""
    global _async_task_processor
    if _async_task_processor is None:
        _async_task_processor = AsyncTaskProcessor()
        await _async_task_processor.initialize()
    return _async_task_processor


async def start_async_task_processing():
    """启动异步任务处理"""
    processor = await get_async_task_processor()
    await processor.start_processing()


async def stop_async_task_processing():
    """停止异步任务处理"""
    global _async_task_processor
    if _async_task_processor:
        await _async_task_processor.stop_processing()
        _async_task_processor = None