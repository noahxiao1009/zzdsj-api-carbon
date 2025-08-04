"""
Task Manager任务监听器
定期轮询task-manager获取待处理的文档任务并执行处理
"""

import asyncio
import logging
import httpx
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.config.settings import settings
from app.core.enhanced_knowledge_manager import get_unified_knowledge_manager
from app.core.splitter_strategy_manager import get_splitter_strategy_manager

logger = logging.getLogger(__name__)


class TaskListener:
    """任务监听器"""
    
    def __init__(self):
        self.task_manager_url = "http://localhost:8084"
        self.polling_interval = 5  # 轮询间隔秒数
        self.max_concurrent_tasks = 3  # 最大并发处理任务数
        self.running = False
        self.current_tasks = set()  # 当前正在处理的任务ID
        
        logger.info(f"任务监听器初始化完成，轮询间隔: {self.polling_interval}s")
    
    async def start(self):
        """启动任务监听器"""
        if self.running:
            logger.warning("任务监听器已在运行中")
            return
        
        self.running = True
        logger.info("任务监听器启动")
        
        try:
            while self.running:
                try:
                    await self._poll_and_process_tasks()
                except Exception as e:
                    logger.error(f"任务轮询出错: {e}")
                
                # 等待下次轮询
                await asyncio.sleep(self.polling_interval)
                
        except asyncio.CancelledError:
            logger.info("任务监听器被取消")
        finally:
            self.running = False
    
    async def stop(self):
        """停止任务监听器"""
        logger.info("正在停止任务监听器...")
        self.running = False
        
        # 等待当前任务完成
        while self.current_tasks:
            logger.info(f"等待 {len(self.current_tasks)} 个任务完成...")
            await asyncio.sleep(1)
        
        logger.info("任务监听器已停止")
    
    async def _poll_and_process_tasks(self):
        """轮询并处理任务"""
        try:
            # 如果已达到最大并发数，跳过本次轮询
            if len(self.current_tasks) >= self.max_concurrent_tasks:
                logger.debug(f"已达到最大并发任务数 {self.max_concurrent_tasks}，跳过轮询")
                return
            
            # 获取待处理任务
            pending_tasks = await self._fetch_pending_tasks()
            
            if not pending_tasks:
                logger.debug("没有待处理的文档任务")
                return
            
            logger.info(f"获取到 {len(pending_tasks)} 个待处理任务")
            
            # 处理任务（并发）
            tasks_to_process = []
            for task in pending_tasks:
                if len(self.current_tasks) + len(tasks_to_process) >= self.max_concurrent_tasks:
                    break
                
                if task["id"] not in self.current_tasks:
                    tasks_to_process.append(task)
            
            if tasks_to_process:
                # 启动并发任务处理
                await asyncio.gather(*[
                    self._process_task(task) for task in tasks_to_process
                ], return_exceptions=True)
            
        except Exception as e:
            logger.error(f"轮询任务时出错: {e}")
    
    async def _fetch_pending_tasks(self) -> List[Dict[str, Any]]:
        """从task-manager获取待处理任务"""
        try:
            # 先获取queued状态的任务
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.task_manager_url}/api/v1/tasks",
                    params={
                        "task_type": "document_processing",
                        "status": "queued",
                        "page": 1,
                        "page_size": 10
                    },
                    timeout=10.0
                )
                
                queued_tasks = []
                if response.status_code == 200:
                    data = response.json()
                    queued_tasks = data.get("tasks", []) or []
                
                # 同时获取processing状态但长时间未更新的任务（可能是卡住的任务）
                processing_response = await client.get(
                    f"{self.task_manager_url}/api/v1/tasks",
                    params={
                        "task_type": "document_processing",
                        "status": "processing",
                        "page": 1,
                        "page_size": 10
                    },
                    timeout=10.0
                )
                
                processing_tasks = []
                if processing_response.status_code == 200:
                    processing_data = processing_response.json()
                    processing_tasks = processing_data.get("tasks", []) or []
                
                # 处理processing状态的任务：包括新开始的和卡住的
                import datetime
                now = datetime.datetime.now(datetime.timezone.utc)
                new_processing_tasks = []
                stuck_processing_tasks = []
                
                for task in processing_tasks:
                    try:
                        updated_at_str = task.get("updated_at", "")
                        if updated_at_str:
                            updated_at = datetime.datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
                            time_diff = (now - updated_at).total_seconds()
                            
                            # 如果任务刚开始（1分钟内）且没有worker_id，说明是新任务
                            if time_diff < 60 and not task.get("worker_id"):
                                logger.info(f"发现新开始的任务: {task['id']}")
                                new_processing_tasks.append(task)
                            # 如果任务超过5分钟未更新，可能是卡住的
                            elif time_diff > 300:
                                logger.info(f"发现卡住的任务: {task['id']}, 上次更新: {time_diff:.0f}秒前")
                                stuck_processing_tasks.append(task)
                    except Exception as e:
                        logger.warning(f"解析任务时间失败: {e}")
                
                # 合并所有任务
                all_tasks = queued_tasks + new_processing_tasks + stuck_processing_tasks
                
                if not all_tasks:
                    logger.debug("没有待处理的文档任务")
                    return []
                
                logger.info(f"获取到 {len(queued_tasks)} 个排队任务和 {len(stuck_processing_tasks)} 个卡住的任务")
                return all_tasks
                
        except httpx.RequestError as e:
            logger.error(f"连接task-manager失败: {e}")
            return []
        except Exception as e:
            logger.error(f"获取任务时出错: {e}")
            return []
    
    async def _process_task(self, task: Dict[str, Any]):
        """处理单个任务"""
        task_id = task["id"]
        
        try:
            # 加入当前处理任务集合
            self.current_tasks.add(task_id)
            
            logger.info(f"开始处理任务: {task_id}")
            
            # 更新任务状态为处理中
            await self._update_task_status(task_id, "processing", "开始处理文档", 0)
            
            # 执行文档处理
            result = await self._execute_document_processing(task)
            
            # 更新任务状态为完成
            await self._update_task_status(
                task_id, 
                "completed", 
                "文档处理完成", 
                100, 
                result
            )
            
            logger.info(f"任务处理完成: {task_id}")
            
        except Exception as e:
            logger.error(f"处理任务 {task_id} 时出错: {e}")
            
            # 更新任务状态为失败
            await self._update_task_status(
                task_id, 
                "failed", 
                f"处理失败: {str(e)}", 
                0,
                error_message=str(e)
            )
        finally:
            # 从当前处理任务中移除
            self.current_tasks.discard(task_id)
    
    async def _execute_document_processing(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """执行文档处理逻辑"""
        payload = task.get("payload", {})
        
        # 获取任务信息
        kb_id = payload.get("kb_id")
        file_path = payload.get("file_path")
        original_filename = payload.get("original_filename")
        splitter_strategy_id = payload.get("splitter_strategy_id")
        custom_splitter_config = payload.get("custom_splitter_config", {})
        
        logger.info(f"处理文档: {original_filename}, 知识库: {kb_id}, 策略: {splitter_strategy_id}")
        
        # 更新进度
        await self._update_task_status(task["id"], "processing", "正在读取文档", 10)
        
        # 1. 获取知识库管理器
        knowledge_manager = get_unified_knowledge_manager()
        
        # 2. 验证知识库存在
        kb_info = await knowledge_manager.get_knowledge_base(kb_id)
        if not kb_info:
            raise Exception(f"知识库不存在: {kb_id}")
        
        # 更新进度
        await self._update_task_status(task["id"], "processing", "正在下载文件", 20)
        
        # 3. 从MinIO下载文件内容
        from app.utils.minio_client import download_from_minio
        file_content = download_from_minio(file_path)
        
        if not file_content:
            raise Exception(f"无法从存储中获取文件: {file_path}")
        
        # 更新进度
        await self._update_task_status(task["id"], "processing", "正在切分文档", 40)
        
        # 4. 执行文档切分
        from app.services.document_processing.document_chunker import DocumentChunker, ChunkConfig
        from app.core.splitter_strategy_manager import get_splitter_strategy_manager
        chunker = DocumentChunker()
        
        # 获取切分策略配置
        effective_config = custom_splitter_config.copy() if custom_splitter_config else {}
        
        # 如果指定了策略ID，获取策略配置
        if splitter_strategy_id:
            strategy_manager = get_splitter_strategy_manager()
            strategy = strategy_manager.get_strategy_by_id(splitter_strategy_id)
            if strategy:
                effective_config.update(strategy.get("config", {}))
                logger.info(f"使用策略配置: {splitter_strategy_id} -> {strategy.get('name', 'Unknown')}")
            else:
                logger.warning(f"策略不存在: {splitter_strategy_id}，使用默认配置")
        
        # 准备分块配置
        chunk_config = ChunkConfig(
            chunk_size=effective_config.get("chunk_size", 1000),
            chunk_overlap=effective_config.get("chunk_overlap", 200),
            strategy=effective_config.get("chunk_strategy", "token_based"),
            preserve_structure=effective_config.get("preserve_structure", True)
        )
        
        # 执行切分
        content = file_content.decode('utf-8')
        chunks = await chunker.chunk_document(content, chunk_config)
        
        # 更新进度
        await self._update_task_status(task["id"], "processing", "正在生成向量", 70)
        
        # 5. 创建文档记录和chunks
        from app.models.database import get_db
        from app.repositories import DocumentRepository, DocumentChunkRepository
        
        db = next(get_db())
        try:
            doc_repo = DocumentRepository(db)
            chunk_repo = DocumentChunkRepository(db)
            
            # 创建文档记录
            document_data = {
                "kb_id": kb_id,
                "original_filename": original_filename,
                "file_path": file_path,
                "file_type": payload.get("file_type", ""),
                "file_size": payload.get("file_size", 0),
                "chunk_count": len(chunks),
                "status": "completed",
                "folder_id": payload.get("processing_options", {}).get("folder_id")
            }
            
            doc = await doc_repo.create(document_data)
            doc_id = doc.id
            
            # 创建chunks记录
            for i, chunk in enumerate(chunks):
                chunk_data = {
                    "doc_id": doc_id,
                    "content": chunk.content,
                    "chunk_index": chunk.index,
                    "start_char": chunk.start_char,
                    "end_char": chunk.end_char,
                    "token_count": chunk.token_count,
                    "char_count": chunk.char_count,
                    "content_hash": chunk.content_hash,
                    "chunk_metadata": chunk.metadata
                }
                await chunk_repo.create(chunk_data)
        finally:
            db.close()
        
        # 更新进度
        await self._update_task_status(task["id"], "processing", "正在存储向量", 90)
        
        # 6. 记录策略使用
        if splitter_strategy_id:
            try:
                strategy_manager = get_splitter_strategy_manager()
                strategy_manager.record_strategy_usage(splitter_strategy_id, kb_id)
                logger.info(f"记录策略使用: {splitter_strategy_id} -> {kb_id}")
            except Exception as e:
                logger.warning(f"记录策略使用失败: {e}")
        
        # 返回处理结果
        result = {
            "status": "completed",
            "document_id": doc_id,
            "chunks": len(chunks),
            "processed_at": datetime.now().isoformat(),
            "message": f"成功处理文档 {original_filename}，生成 {len(chunks)} 个分块"
        }
        
        logger.info(f"文档处理完成: {original_filename}, 生成分块: {len(chunks)}")
        return result
    
    async def _update_task_status(
        self, 
        task_id: str, 
        status: str, 
        message: str, 
        progress: int,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ):
        """更新任务状态（使用progress API）"""
        try:
            # 使用form data格式，因为task-manager的API期望form参数
            form_data = {
                "progress": str(progress),
                "message": message
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{self.task_manager_url}/api/v1/tasks/{task_id}/progress",
                    data=form_data,  # 使用data而不是json
                    timeout=10.0
                )
                
                if response.status_code not in [200, 204]:
                    logger.error(f"更新任务进度失败: {response.status_code} - {response.text}")
                else:
                    logger.debug(f"任务进度更新成功: {task_id} -> {progress}% ({message})")
                    
                # 如果任务完成，需要单独更新结果（暂时通过日志记录）
                if status == "completed" and result:
                    logger.info(f"任务 {task_id} 处理完成，结果: {result}")
                elif status == "failed" and error_message:
                    logger.error(f"任务 {task_id} 处理失败: {error_message}")
                    
        except Exception as e:
            logger.error(f"更新任务状态时出错: {e}")


# 全局任务监听器实例
_task_listener = None


def get_task_listener() -> TaskListener:
    """获取任务监听器实例"""
    global _task_listener
    if _task_listener is None:
        _task_listener = TaskListener()
    return _task_listener


async def start_task_listener():
    """启动任务监听器"""
    listener = get_task_listener()
    await listener.start()


async def stop_task_listener():
    """停止任务监听器"""
    if _task_listener:
        await _task_listener.stop()