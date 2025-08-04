"""
任务处理器
处理队列中的异步任务
"""

import asyncio
import logging
import traceback
from datetime import datetime
from typing import Optional, Dict, Any, Callable, List
from app.config.settings import settings
from app.utils.minio_client import upload_to_minio, test_minio_connection
from app.core.enhanced_knowledge_manager import get_unified_knowledge_manager
from .redis_queue import RedisQueue, get_redis_queue
from .task_models import TaskModel, TaskStatus, ProcessingTaskModel, TaskUpdateModel, TaskTypes

logger = logging.getLogger(__name__)


class TaskProcessor:
    """任务处理器"""
    
    def __init__(self, redis_queue: Optional[RedisQueue] = None):
        """初始化任务处理器"""
        self.redis_queue = redis_queue or get_redis_queue()
        self.knowledge_manager = None
        self.is_running = False
        self.worker_tasks = []
        self.task_handlers: Dict[str, Callable] = {}
        
        # 注册任务处理器
        self._register_handlers()
    
    def _register_handlers(self):
        """注册任务处理器"""
        self.task_handlers[TaskTypes.DOCUMENT_PROCESSING] = self._process_document_task
        self.task_handlers[TaskTypes.BATCH_PROCESSING] = self._process_batch_task
        self.task_handlers[TaskTypes.KNOWLEDGE_INDEXING] = self._process_indexing_task
        self.task_handlers[TaskTypes.EMBEDDING_GENERATION] = self._process_embedding_task
        self.task_handlers[TaskTypes.VECTOR_STORAGE] = self._process_vector_storage_task
    
    async def initialize(self):
        """初始化处理器"""
        try:
            # 初始化知识库管理器
            self.knowledge_manager = get_unified_knowledge_manager()
            
            # 测试MinIO连接
            if not test_minio_connection():
                raise ConnectionError("MinIO连接失败")
            
            logger.info("任务处理器初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"任务处理器初始化失败: {e}")
            return False
    
    async def start_processing(self, queue_name: str = "default", max_workers: int = 3):
        """开始处理任务"""
        if self.is_running:
            logger.warning("任务处理器已在运行")
            return
        
        self.is_running = True
        logger.info(f"开始处理队列 {queue_name}，工作进程数: {max_workers}")
        
        # 创建工作进程
        self.worker_tasks = []
        for i in range(max_workers):
            worker = asyncio.create_task(
                self._worker_loop(queue_name, f"worker-{i}")
            )
            self.worker_tasks.append(worker)
        
        try:
            # 等待所有工作进程
            await asyncio.gather(*self.worker_tasks)
        except Exception as e:
            logger.error(f"任务处理出错: {e}")
        finally:
            self.is_running = False
            logger.info("任务处理器已停止")
    
    async def stop_processing(self):
        """停止处理任务"""
        self.is_running = False
        logger.info("正在停止任务处理器...")
        
        # 取消所有工作任务
        for task in self.worker_tasks:
            if not task.done():
                task.cancel()
        
        # 等待任务取消完成
        if self.worker_tasks:
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)
            self.worker_tasks = []
        
        logger.info("任务处理器已停止")
    
    async def _worker_loop(self, queue_name: str, worker_name: str):
        """工作进程循环"""
        logger.info(f"工作进程 {worker_name} 开始")
        
        try:
            while self.is_running:
                try:
                    # 从队列获取任务
                    task = await self.redis_queue.dequeue_task(queue_name, timeout=5)
                    
                    if task:
                        logger.info(f"工作进程 {worker_name} 开始处理任务 {task.task_id}")
                        await self._process_task(task)
                        logger.info(f"工作进程 {worker_name} 完成任务 {task.task_id}")
                    
                except asyncio.CancelledError:
                    logger.info(f"工作进程 {worker_name} 收到取消信号")
                    break
                except Exception as e:
                    logger.error(f"工作进程 {worker_name} 出错: {e}")
                    await asyncio.sleep(1)  # 出错后稍等再继续
        except asyncio.CancelledError:
            logger.info(f"工作进程 {worker_name} 被取消")
        finally:
            logger.info(f"工作进程 {worker_name} 结束")
    
    async def _process_task(self, task: TaskModel):
        """处理单个任务"""
        try:
            # 获取任务处理器
            handler = self.task_handlers.get(task.task_type)
            if not handler:
                raise ValueError(f"不支持的任务类型: {task.task_type}")
            
            # 更新任务状态为处理中
            await self.redis_queue.update_task_status(
                task.task_id,
                TaskStatus.PROCESSING,
                f"开始处理 {task.task_type} 任务"
            )
            
            # 执行任务处理
            await handler(task)
            
            # 更新任务状态为完成
            await self.redis_queue.update_task_status(
                task.task_id,
                TaskStatus.COMPLETED,
                "任务处理完成"
            )
            
        except Exception as e:
            error_msg = f"任务处理失败: {str(e)}"
            logger.error(f"任务 {task.task_id} 处理失败: {e}")
            logger.error(traceback.format_exc())
            
            # 更新任务状态为失败
            await self.redis_queue.update_task(
                task.task_id,
                TaskUpdateModel(
                    status=TaskStatus.FAILED,
                    error_message=error_msg,
                    message="任务处理失败"
                )
            )
    
    async def _process_document_task(self, task: TaskModel):
        """处理文档处理任务"""
        if not isinstance(task, ProcessingTaskModel):
            # 尝试转换为ProcessingTaskModel
            task_data = task.dict()
            task = ProcessingTaskModel(**task_data)
        
        logger.info(f"开始处理文档: {task.original_filename}")
        
        # 更新进度: 10%
        await self.redis_queue.update_task_progress(
            task.task_id, 10, "开始文档处理"
        )
        
        try:
            # 使用增强的文档处理器，支持SSE推送
            from app.services.enhanced_document_processor import EnhancedDocumentProcessor
            from app.models.database import get_db
            
            db = next(get_db())
            processor = EnhancedDocumentProcessor(db)
            
            # 构建文件路径（从MinIO存储）
            file_path = task.file_path
            
            # 准备处理参数
            metadata = {
                "task_id": task.task_id,
                "processing_options": task.processing_options,
                "splitter_strategy_id": task.splitter_strategy_id,
                "custom_config": task.custom_splitter_config
            }
            
            # 调用增强的文档处理器（包含SSE推送）
            result = await processor.process_uploaded_document(
                kb_id=task.kb_id,
                file_path=file_path,
                filename=task.original_filename,
                title=task.original_filename,
                metadata=metadata,
                user_id=task.user_id  # 传递user_id用于SSE推送
            )
            
            if result.get("success"):
                # 更新任务状态
                task.chunks_count = result.get("document", {}).get("chunk_count", 0)
                await self.redis_queue.update_task_progress(
                    task.task_id, 100, "文档处理完成"
                )
                logger.info(f"文档处理成功: {task.original_filename}")
            else:
                raise Exception(result.get("message", "文档处理失败"))
                
            db.close()
            
            # 更新任务元数据
            await self.redis_queue.update_task(
                task.task_id,
                TaskUpdateModel(
                    metadata={
                        "chunks_count": task.chunks_count,
                        "embedding_count": task.embedding_count,
                        "processing_duration": task.processing_duration,
                        "file_size": task.file_size,
                        "completed_at": datetime.now().isoformat()
                    }
                )
            )
            
            logger.info(f"文档处理完成: {task.original_filename}")
            
        except Exception as e:
            logger.error(f"文档处理失败: {e}")
            raise
    
    async def _process_batch_task(self, task: TaskModel):
        """处理批量处理任务"""
        logger.info(f"开始批量处理任务: {task.task_id}")
        # TODO: 实现批量处理逻辑
        await asyncio.sleep(1)  # 模拟处理
        logger.info(f"批量处理完成: {task.task_id}")
    
    async def _process_indexing_task(self, task: TaskModel):
        """处理知识索引任务"""
        logger.info(f"开始知识索引任务: {task.task_id}")
        # TODO: 实现知识索引逻辑
        await asyncio.sleep(1)  # 模拟处理
        logger.info(f"知识索引完成: {task.task_id}")
    
    async def _process_embedding_task(self, task: TaskModel):
        """处理嵌入生成任务"""
        logger.info(f"开始嵌入生成任务: {task.task_id}")
        # TODO: 实现嵌入生成逻辑
        await asyncio.sleep(1)  # 模拟处理
        logger.info(f"嵌入生成完成: {task.task_id}")
    
    async def _process_vector_storage_task(self, task: TaskModel):
        """处理向量存储任务"""
        logger.info(f"开始向量存储任务: {task.task_id}")
        # TODO: 实现向量存储逻辑
        await asyncio.sleep(1)  # 模拟处理
        logger.info(f"向量存储完成: {task.task_id}")
    
    async def _validate_document(self, task: ProcessingTaskModel):
        """验证文档"""
        # 检查文件是否存在
        if not task.file_path:
            raise ValueError("文件路径为空")
        
        # 检查文件类型
        allowed_types = ['.pdf', '.txt', '.docx', '.md', '.html']
        file_ext = task.original_filename.lower().split('.')[-1]
        if f'.{file_ext}' not in allowed_types:
            raise ValueError(f"不支持的文件类型: {file_ext}")
        
        # 检查文件大小
        max_size = 100 * 1024 * 1024  # 100MB
        if task.file_size > max_size:
            raise ValueError(f"文件过大: {task.file_size} bytes")
        
        logger.info(f"文档验证通过: {task.original_filename}")
    
    async def _split_document(self, task: ProcessingTaskModel) -> List[Dict[str, Any]]:
        """切分文档"""
        try:
            # 使用知识库管理器进行文档切分
            if not self.knowledge_manager:
                raise ValueError("知识库管理器未初始化")
            
            # 根据切分策略进行处理
            splitter_config = task.custom_splitter_config or {
                "chunk_size": 1024,
                "chunk_overlap": 128,
                "chunk_strategy": "basic"
            }
            
            # 模拟文档切分
            # TODO: 实际的文档切分逻辑
            chunks = [
                {
                    "content": f"文档块 {i}",
                    "metadata": {
                        "chunk_id": i,
                        "start_pos": i * 500,
                        "end_pos": (i + 1) * 500,
                        "source": task.original_filename
                    }
                }
                for i in range(5)  # 模拟生成5个块
            ]
            
            logger.info(f"文档切分完成，生成 {len(chunks)} 个分块")
            return chunks
            
        except Exception as e:
            logger.error(f"文档切分失败: {e}")
            raise
    
    async def _generate_embeddings(self, task: ProcessingTaskModel, chunks: List[Dict[str, Any]]) -> List[List[float]]:
        """生成嵌入向量"""
        try:
            # 模拟嵌入向量生成
            # TODO: 实际的嵌入向量生成逻辑
            embeddings = []
            for i, chunk in enumerate(chunks):
                # 模拟生成768维向量
                embedding = [0.1] * 768
                embeddings.append(embedding)
                
                # 更新进度
                progress = 60 + int((i + 1) / len(chunks) * 20)
                await self.redis_queue.update_task_progress(
                    task.task_id, 
                    progress, 
                    f"生成嵌入向量 {i + 1}/{len(chunks)}"
                )
            
            logger.info(f"嵌入向量生成完成，共 {len(embeddings)} 个")
            return embeddings
            
        except Exception as e:
            logger.error(f"嵌入向量生成失败: {e}")
            raise
    
    async def _store_vectors(self, task: ProcessingTaskModel, chunks: List[Dict[str, Any]], embeddings: List[List[float]]):
        """存储向量到数据库"""
        try:
            # 模拟向量存储
            # TODO: 实际的向量存储逻辑
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                # 模拟存储操作
                await asyncio.sleep(0.1)
                
                # 更新进度
                progress = 80 + int((i + 1) / len(chunks) * 20)
                await self.redis_queue.update_task_progress(
                    task.task_id,
                    progress,
                    f"存储向量 {i + 1}/{len(chunks)}"
                )
            
            logger.info(f"向量存储完成，共存储 {len(embeddings)} 个向量")
            
        except Exception as e:
            logger.error(f"向量存储失败: {e}")
            raise
    
    async def process_single_task(self, task: TaskModel) -> bool:
        """处理单个任务（用于测试）"""
        try:
            await self._process_task(task)
            return True
        except Exception as e:
            logger.error(f"任务处理失败: {e}")
            return False
    
    async def get_processing_stats(self) -> Dict[str, Any]:
        """获取处理统计"""
        try:
            # 获取队列统计
            queue_length = await self.redis_queue.get_queue_length()
            
            # 获取任务统计
            from .task_models import TaskQueryModel
            tasks = await self.redis_queue.query_tasks(TaskQueryModel(limit=1000))
            
            stats = {
                "queue_length": queue_length,
                "total_tasks": len(tasks),
                "completed_tasks": len([t for t in tasks if t.status == TaskStatus.COMPLETED]),
                "failed_tasks": len([t for t in tasks if t.status == TaskStatus.FAILED]),
                "processing_tasks": len([t for t in tasks if t.status == TaskStatus.PROCESSING]),
                "pending_tasks": len([t for t in tasks if t.status == TaskStatus.PENDING]),
                "is_running": self.is_running,
                "timestamp": datetime.now().isoformat()
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"获取处理统计失败: {e}")
            return {}


# 全局任务处理器实例
_task_processor: Optional[TaskProcessor] = None


async def get_task_processor() -> TaskProcessor:
    """获取任务处理器实例"""
    global _task_processor
    if _task_processor is None:
        _task_processor = TaskProcessor()
        await _task_processor.initialize()
    return _task_processor