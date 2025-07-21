"""
任务管理器核心组件
管理异步图谱生成任务和任务状态
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import asyncio
import json
from enum import Enum
from dataclasses import dataclass, asdict
from pathlib import Path
import uuid

from ..config.settings import settings
from ..models.graph import ProcessingConfig, ProcessingStage, ProcessingProgress

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    """任务类型"""
    GRAPH_GENERATION = "graph_generation"
    GRAPH_UPDATE = "graph_update"
    GRAPH_EXPORT = "graph_export"
    BATCH_PROCESSING = "batch_processing"


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskInfo:
    """任务信息"""
    task_id: str
    task_type: TaskType
    status: TaskStatus
    progress: float = 0.0
    message: str = ""
    
    # 任务参数
    graph_id: Optional[str] = None
    user_id: Optional[str] = None
    project_id: Optional[str] = None
    parameters: Dict[str, Any] = None
    
    # 时间信息
    created_at: datetime = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # 结果信息
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    # 处理详情
    stage: Optional[ProcessingStage] = None
    stage_details: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.parameters is None:
            self.parameters = {}
        if self.stage_details is None:
            self.stage_details = {}


class TaskManager:
    """任务管理器
    
    管理异步图谱生成任务的创建、执行和状态跟踪
    """
    
    def __init__(self):
        """初始化任务管理器"""
        self.tasks: Dict[str, TaskInfo] = {}
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self.workers: List[asyncio.Task] = []
        self.max_workers = 3
        self.task_timeout = settings.TASK_TIMEOUT
        self.retry_times = settings.TASK_RETRY_TIMES
        self.retry_delay = settings.TASK_RETRY_DELAY
        
        # 任务持久化
        self.task_storage_path = Path(settings.UPLOAD_DIR) / "tasks"
        self.task_storage_path.mkdir(parents=True, exist_ok=True)
        
        # 启动工作线程
        self._start_workers()
        
        # 加载已存在的任务
        self._load_existing_tasks()
        
        logger.info(f"Task manager initialized with {self.max_workers} workers")
    
    def _start_workers(self):
        """启动工作线程"""
        try:
            for i in range(self.max_workers):
                worker = asyncio.create_task(self._worker(f"worker-{i}"))
                self.workers.append(worker)
                logger.info(f"Started worker: worker-{i}")
                
        except Exception as e:
            logger.error(f"Failed to start workers: {e}")
            raise
    
    async def _worker(self, worker_name: str):
        """工作线程"""
        logger.info(f"Worker {worker_name} started")
        
        while True:
            try:
                # 获取任务
                task_id = await self.task_queue.get()
                
                if task_id not in self.tasks:
                    logger.warning(f"Task {task_id} not found in tasks")
                    continue
                
                task_info = self.tasks[task_id]
                
                # 检查任务状态
                if task_info.status != TaskStatus.PENDING:
                    logger.info(f"Task {task_id} status is {task_info.status}, skipping")
                    continue
                
                logger.info(f"Worker {worker_name} processing task {task_id}")
                
                # 执行任务
                await self._execute_task(task_info)
                
                # 标记任务队列完成
                self.task_queue.task_done()
                
            except asyncio.CancelledError:
                logger.info(f"Worker {worker_name} cancelled")
                break
            except Exception as e:
                logger.error(f"Worker {worker_name} error: {e}")
                # 继续处理下一个任务
                continue
    
    async def _execute_task(self, task_info: TaskInfo):
        """执行任务"""
        try:
            # 更新任务状态
            task_info.status = TaskStatus.RUNNING
            task_info.started_at = datetime.now()
            task_info.progress = 0.0
            task_info.message = "任务开始执行"
            
            # 保存任务状态
            await self._save_task(task_info)
            
            # 根据任务类型执行不同的处理逻辑
            if task_info.task_type == TaskType.GRAPH_GENERATION:
                await self._execute_graph_generation_task(task_info)
            elif task_info.task_type == TaskType.GRAPH_UPDATE:
                await self._execute_graph_update_task(task_info)
            elif task_info.task_type == TaskType.GRAPH_EXPORT:
                await self._execute_graph_export_task(task_info)
            elif task_info.task_type == TaskType.BATCH_PROCESSING:
                await self._execute_batch_processing_task(task_info)
            else:
                raise ValueError(f"Unknown task type: {task_info.task_type}")
            
            # 任务完成
            task_info.status = TaskStatus.COMPLETED
            task_info.completed_at = datetime.now()
            task_info.progress = 100.0
            task_info.message = "任务执行完成"
            
            await self._save_task(task_info)
            
            logger.info(f"Task {task_info.task_id} completed successfully")
            
        except Exception as e:
            # 任务失败
            task_info.status = TaskStatus.FAILED
            task_info.completed_at = datetime.now()
            task_info.error = str(e)
            task_info.message = f"任务执行失败: {str(e)}"
            
            await self._save_task(task_info)
            
            logger.error(f"Task {task_info.task_id} failed: {e}")
    
    async def _execute_graph_generation_task(self, task_info: TaskInfo):
        """执行图谱生成任务"""
        try:
            from ..core.graph_generator import get_graph_generator
            from ..services.graph_service import get_graph_service
            
            # 获取服务实例
            graph_generator = await get_graph_generator()
            graph_service = await get_graph_service()
            
            # 获取任务参数
            parameters = task_info.parameters
            graph_id = task_info.graph_id
            user_id = task_info.user_id
            project_id = task_info.project_id
            
            # 创建进度回调
            async def progress_callback(message: str, progress: float):
                task_info.progress = progress
                task_info.message = message
                await self._save_task(task_info)
            
            # 获取图谱元数据
            graph = await graph_service.get_graph(graph_id, user_id, project_id)
            if not graph:
                raise ValueError(f"Graph {graph_id} not found")
            
            # 根据数据源类型处理
            entities = []
            relations = []
            
            if parameters.get('text_content'):
                # 处理文本内容
                task_info.stage = ProcessingStage.EXTRACTING
                await self._save_task(task_info)
                
                entities, relations = await graph_generator.process_text(
                    text_content=parameters['text_content'],
                    config=parameters.get('processing_config'),
                    progress_callback=progress_callback
                )
            
            elif parameters.get('knowledge_base_ids'):
                # 处理知识库
                task_info.stage = ProcessingStage.EXTRACTING
                await self._save_task(task_info)
                
                entities, relations = await graph_generator.process_knowledge_bases(
                    knowledge_base_ids=parameters['knowledge_base_ids'],
                    config=parameters.get('processing_config'),
                    progress_callback=progress_callback
                )
            
            elif parameters.get('document_ids'):
                # 处理文档
                task_info.stage = ProcessingStage.EXTRACTING
                await self._save_task(task_info)
                
                entities, relations = await graph_generator.process_documents(
                    document_ids=parameters['document_ids'],
                    config=parameters.get('processing_config'),
                    progress_callback=progress_callback
                )
            
            else:
                raise ValueError("No valid data source provided")
            
            # 保存图谱数据
            task_info.stage = ProcessingStage.VISUALIZING
            task_info.progress = 80.0
            task_info.message = "保存图谱数据"
            await self._save_task(task_info)
            
            # 使用图谱服务保存数据
            from ..repositories.arangodb_repository import get_arangodb_repository
            arangodb_repo = await get_arangodb_repository()
            await arangodb_repo.save_graph_data(graph_id, entities, relations, user_id, project_id)
            
            # 更新图谱统计
            statistics = await arangodb_repo.get_graph_statistics(graph_id, user_id, project_id)
            graph.statistics = statistics
            graph.status = "completed"
            graph.completed_at = datetime.now()
            
            await arangodb_repo.save_graph_metadata(graph)
            
            # 生成可视化
            task_info.stage = ProcessingStage.VISUALIZING
            task_info.progress = 90.0
            task_info.message = "生成可视化"
            await self._save_task(task_info)
            
            from ..core.visualization_engine import get_visualization_engine
            visualization_engine = await get_visualization_engine()
            
            html_content = await visualization_engine.generate_html_visualization(
                entities=entities,
                relations=relations,
                config=graph.visualization_config,
                graph_title=graph.name
            )
            
            # 保存可视化文件
            visualization_dir = Path(settings.VISUALIZATION_DIR)
            visualization_dir.mkdir(parents=True, exist_ok=True)
            
            visualization_file = visualization_dir / f"{graph_id}.html"
            visualization_file.write_text(html_content, encoding='utf-8')
            
            # 更新图谱元数据
            graph.visualization_url = str(visualization_file)
            await arangodb_repo.save_graph_metadata(graph)
            
            # 设置任务结果
            task_info.result = {
                'graph_id': graph_id,
                'entity_count': len(entities),
                'relation_count': len(relations),
                'visualization_url': str(visualization_file)
            }
            
            logger.info(f"Graph generation task {task_info.task_id} completed: {len(entities)} entities, {len(relations)} relations")
            
        except Exception as e:
            logger.error(f"Graph generation task failed: {e}")
            raise
    
    async def _execute_graph_update_task(self, task_info: TaskInfo):
        """执行图谱更新任务"""
        try:
            # TODO: 实现图谱更新逻辑
            task_info.result = {'status': 'updated'}
            logger.info(f"Graph update task {task_info.task_id} completed")
            
        except Exception as e:
            logger.error(f"Graph update task failed: {e}")
            raise
    
    async def _execute_graph_export_task(self, task_info: TaskInfo):
        """执行图谱导出任务"""
        try:
            # TODO: 实现图谱导出逻辑
            task_info.result = {'status': 'exported'}
            logger.info(f"Graph export task {task_info.task_id} completed")
            
        except Exception as e:
            logger.error(f"Graph export task failed: {e}")
            raise
    
    async def _execute_batch_processing_task(self, task_info: TaskInfo):
        """执行批量处理任务"""
        try:
            # TODO: 实现批量处理逻辑
            task_info.result = {'status': 'batch_processed'}
            logger.info(f"Batch processing task {task_info.task_id} completed")
            
        except Exception as e:
            logger.error(f"Batch processing task failed: {e}")
            raise
    
    async def create_graph_generation_task(self, graph_id: str, user_id: str, 
                                         data_source: List[str] = None, text_content: str = None,
                                         processing_config: ProcessingConfig = None) -> str:
        """创建图谱生成任务"""
        try:
            task_id = str(uuid.uuid4())
            
            # 准备任务参数
            parameters = {}
            if text_content:
                parameters['text_content'] = text_content
            if data_source:
                if any(ds.startswith('kb_') for ds in data_source):
                    parameters['knowledge_base_ids'] = data_source
                else:
                    parameters['document_ids'] = data_source
            if processing_config:
                parameters['processing_config'] = processing_config
            
            # 创建任务信息
            task_info = TaskInfo(
                task_id=task_id,
                task_type=TaskType.GRAPH_GENERATION,
                status=TaskStatus.PENDING,
                graph_id=graph_id,
                user_id=user_id,
                parameters=parameters,
                stage=ProcessingStage.INITIALIZED
            )
            
            # 保存任务
            self.tasks[task_id] = task_info
            await self._save_task(task_info)
            
            # 添加到队列
            await self.task_queue.put(task_id)
            
            logger.info(f"Created graph generation task {task_id} for graph {graph_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to create graph generation task: {e}")
            raise
    
    async def create_graph_update_task(self, graph_id: str, user_id: str, 
                                     update_params: Dict[str, Any]) -> str:
        """创建图谱更新任务"""
        try:
            task_id = str(uuid.uuid4())
            
            task_info = TaskInfo(
                task_id=task_id,
                task_type=TaskType.GRAPH_UPDATE,
                status=TaskStatus.PENDING,
                graph_id=graph_id,
                user_id=user_id,
                parameters=update_params
            )
            
            self.tasks[task_id] = task_info
            await self._save_task(task_info)
            await self.task_queue.put(task_id)
            
            logger.info(f"Created graph update task {task_id} for graph {graph_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to create graph update task: {e}")
            raise
    
    async def create_graph_export_task(self, graph_id: str, user_id: str, 
                                     export_params: Dict[str, Any]) -> str:
        """创建图谱导出任务"""
        try:
            task_id = str(uuid.uuid4())
            
            task_info = TaskInfo(
                task_id=task_id,
                task_type=TaskType.GRAPH_EXPORT,
                status=TaskStatus.PENDING,
                graph_id=graph_id,
                user_id=user_id,
                parameters=export_params
            )
            
            self.tasks[task_id] = task_info
            await self._save_task(task_info)
            await self.task_queue.put(task_id)
            
            logger.info(f"Created graph export task {task_id} for graph {graph_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to create graph export task: {e}")
            raise
    
    async def get_task_status(self, task_id: str) -> Optional[TaskInfo]:
        """获取任务状态"""
        try:
            return self.tasks.get(task_id)
            
        except Exception as e:
            logger.error(f"Failed to get task status: {e}")
            return None
    
    async def get_task_progress(self, task_id: str) -> Optional[ProcessingProgress]:
        """获取任务进度"""
        try:
            task_info = self.tasks.get(task_id)
            if not task_info:
                return None
            
            return ProcessingProgress(
                stage=task_info.stage or ProcessingStage.INITIALIZED,
                progress=task_info.progress,
                message=task_info.message,
                stage_details=task_info.stage_details,
                started_at=task_info.started_at,
                error=task_info.error
            )
            
        except Exception as e:
            logger.error(f"Failed to get task progress: {e}")
            return None
    
    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        try:
            task_info = self.tasks.get(task_id)
            if not task_info:
                return False
            
            if task_info.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                task_info.status = TaskStatus.CANCELLED
                task_info.completed_at = datetime.now()
                task_info.message = "任务已取消"
                
                await self._save_task(task_info)
                
                logger.info(f"Task {task_id} cancelled")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to cancel task: {e}")
            return False
    
    async def get_user_tasks(self, user_id: str, limit: int = 100) -> List[TaskInfo]:
        """获取用户任务列表"""
        try:
            user_tasks = []
            for task_info in self.tasks.values():
                if task_info.user_id == user_id:
                    user_tasks.append(task_info)
            
            # 按创建时间排序
            user_tasks.sort(key=lambda x: x.created_at, reverse=True)
            
            return user_tasks[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get user tasks: {e}")
            return []
    
    async def cleanup_old_tasks(self, days: int = 7):
        """清理旧任务"""
        try:
            cutoff_time = datetime.now() - timedelta(days=days)
            
            tasks_to_remove = []
            for task_id, task_info in self.tasks.items():
                if task_info.created_at < cutoff_time and task_info.status in [
                    TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED
                ]:
                    tasks_to_remove.append(task_id)
            
            for task_id in tasks_to_remove:
                # 删除任务文件
                await self._delete_task_file(task_id)
                # 从内存中删除
                del self.tasks[task_id]
            
            logger.info(f"Cleaned up {len(tasks_to_remove)} old tasks")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old tasks: {e}")
    
    async def _save_task(self, task_info: TaskInfo):
        """保存任务到文件"""
        try:
            task_file = self.task_storage_path / f"{task_info.task_id}.json"
            
            # 转换为字典
            task_dict = asdict(task_info)
            
            # 处理datetime对象
            for key, value in task_dict.items():
                if isinstance(value, datetime):
                    task_dict[key] = value.isoformat()
            
            # 保存到文件
            with open(task_file, 'w', encoding='utf-8') as f:
                json.dump(task_dict, f, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"Failed to save task {task_info.task_id}: {e}")
    
    async def _delete_task_file(self, task_id: str):
        """删除任务文件"""
        try:
            task_file = self.task_storage_path / f"{task_id}.json"
            if task_file.exists():
                task_file.unlink()
                
        except Exception as e:
            logger.error(f"Failed to delete task file {task_id}: {e}")
    
    def _load_existing_tasks(self):
        """加载已存在的任务"""
        try:
            if not self.task_storage_path.exists():
                return
            
            for task_file in self.task_storage_path.glob("*.json"):
                try:
                    with open(task_file, 'r', encoding='utf-8') as f:
                        task_dict = json.load(f)
                    
                    # 转换datetime字段
                    for key in ['created_at', 'started_at', 'completed_at']:
                        if task_dict.get(key):
                            task_dict[key] = datetime.fromisoformat(task_dict[key])
                    
                    # 转换枚举类型
                    task_dict['task_type'] = TaskType(task_dict['task_type'])
                    task_dict['status'] = TaskStatus(task_dict['status'])
                    if task_dict.get('stage'):
                        task_dict['stage'] = ProcessingStage(task_dict['stage'])
                    
                    task_info = TaskInfo(**task_dict)
                    self.tasks[task_info.task_id] = task_info
                    
                except Exception as e:
                    logger.error(f"Failed to load task from {task_file}: {e}")
                    continue
            
            logger.info(f"Loaded {len(self.tasks)} existing tasks")
            
        except Exception as e:
            logger.error(f"Failed to load existing tasks: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            total_tasks = len(self.tasks)
            pending_tasks = sum(1 for task in self.tasks.values() if task.status == TaskStatus.PENDING)
            running_tasks = sum(1 for task in self.tasks.values() if task.status == TaskStatus.RUNNING)
            completed_tasks = sum(1 for task in self.tasks.values() if task.status == TaskStatus.COMPLETED)
            failed_tasks = sum(1 for task in self.tasks.values() if task.status == TaskStatus.FAILED)
            
            queue_size = self.task_queue.qsize()
            active_workers = sum(1 for worker in self.workers if not worker.done())
            
            return {
                'status': 'healthy',
                'total_tasks': total_tasks,
                'pending_tasks': pending_tasks,
                'running_tasks': running_tasks,
                'completed_tasks': completed_tasks,
                'failed_tasks': failed_tasks,
                'queue_size': queue_size,
                'active_workers': active_workers,
                'max_workers': self.max_workers,
                'task_storage_path': str(self.task_storage_path),
                'checked_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'checked_at': datetime.now().isoformat()
            }
    
    async def shutdown(self):
        """关闭任务管理器"""
        try:
            # 取消所有工作线程
            for worker in self.workers:
                worker.cancel()
            
            # 等待所有工作线程完成
            await asyncio.gather(*self.workers, return_exceptions=True)
            
            logger.info("Task manager shut down successfully")
            
        except Exception as e:
            logger.error(f"Failed to shutdown task manager: {e}")


# 全局任务管理器实例
task_manager = TaskManager()


async def get_task_manager() -> TaskManager:
    """获取任务管理器实例"""
    return task_manager