"""
任务调度器
支持多线程任务调度、任务队列管理、定时任务等功能
"""

import asyncio
import logging
import uuid
import time
import threading
from typing import Dict, Any, Optional, List, Callable, Awaitable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from collections import deque
import json
import traceback

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    """任务优先级枚举"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Task:
    """任务数据类"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    func: Optional[Callable] = None
    args: tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout: Optional[int] = None
    result: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "priority": self.priority.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "timeout": self.timeout,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata
        }


class TaskQueue:
    """任务队列"""
    
    def __init__(self, maxsize: int = 1000):
        self.maxsize = maxsize
        self._queues = {
            TaskPriority.URGENT: deque(),
            TaskPriority.HIGH: deque(),
            TaskPriority.NORMAL: deque(),
            TaskPriority.LOW: deque()
        }
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        self._not_full = threading.Condition(self._lock)
        self._size = 0
    
    def put(self, task: Task, block: bool = True, timeout: Optional[float] = None) -> bool:
        """添加任务到队列"""
        with self._not_full:
            if self._size >= self.maxsize:
                if not block:
                    return False
                if not self._not_full.wait(timeout):
                    return False
            
            self._queues[task.priority].append(task)
            self._size += 1
            self._not_empty.notify()
            return True
    
    def get(self, block: bool = True, timeout: Optional[float] = None) -> Optional[Task]:
        """从队列获取任务（按优先级）"""
        with self._not_empty:
            while self._size == 0:
                if not block:
                    return None
                if not self._not_empty.wait(timeout):
                    return None
            
            # 按优先级获取任务
            for priority in [TaskPriority.URGENT, TaskPriority.HIGH, TaskPriority.NORMAL, TaskPriority.LOW]:
                if self._queues[priority]:
                    task = self._queues[priority].popleft()
                    self._size -= 1
                    self._not_full.notify()
                    return task
            
            return None
    
    def size(self) -> int:
        """获取队列大小"""
        with self._lock:
            return self._size
    
    def empty(self) -> bool:
        """检查队列是否为空"""
        with self._lock:
            return self._size == 0


class TaskWorker(threading.Thread):
    """任务工作线程"""
    
    def __init__(self, worker_id: str, task_queue: TaskQueue, scheduler: 'TaskScheduler'):
        super().__init__(name=f"TaskWorker-{worker_id}", daemon=True)
        self.worker_id = worker_id
        self.task_queue = task_queue
        self.scheduler = scheduler
        self.running = True
        self.current_task: Optional[Task] = None
        self.tasks_processed = 0
        self.last_activity = time.time()
    
    def run(self):
        """工作线程主循环"""
        logger.info(f"任务工作线程 {self.worker_id} 启动")
        
        while self.running:
            try:
                # 获取任务
                task = self.task_queue.get(block=True, timeout=1.0)
                if task is None:
                    continue
                
                self.current_task = task
                self.last_activity = time.time()
                
                # 执行任务
                self._execute_task(task)
                
                self.current_task = None
                self.tasks_processed += 1
                
            except Exception as e:
                logger.error(f"工作线程 {self.worker_id} 异常: {str(e)}")
                if self.current_task:
                    self.current_task.status = TaskStatus.FAILED
                    self.current_task.error = str(e)
                    self.current_task.completed_at = datetime.now()
        
        logger.info(f"任务工作线程 {self.worker_id} 停止")
    
    def _execute_task(self, task: Task):
        """执行单个任务"""
        try:
            # 更新任务状态
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            
            logger.info(f"开始执行任务: {task.name} ({task.id})")
            
            # 执行任务函数
            if asyncio.iscoroutinefunction(task.func):
                # 异步函数
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    if task.timeout:
                        result = loop.run_until_complete(
                            asyncio.wait_for(task.func(*task.args, **task.kwargs), timeout=task.timeout)
                        )
                    else:
                        result = loop.run_until_complete(task.func(*task.args, **task.kwargs))
                finally:
                    loop.close()
            else:
                # 同步函数
                result = task.func(*task.args, **task.kwargs)
            
            # 任务成功完成
            task.status = TaskStatus.COMPLETED
            task.result = result
            task.completed_at = datetime.now()
            
            logger.info(f"任务执行完成: {task.name} ({task.id})")
            
        except asyncio.TimeoutError:
            # 任务超时
            task.status = TaskStatus.FAILED
            task.error = "任务执行超时"
            task.completed_at = datetime.now()
            logger.warning(f"任务执行超时: {task.name} ({task.id})")
            
        except Exception as e:
            # 任务执行失败
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            task.error = error_msg
            task.completed_at = datetime.now()
            
            # 检查是否需要重试
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = TaskStatus.PENDING
                task.started_at = None
                task.error = None
                
                # 重新加入队列
                self.scheduler.submit_task(task)
                logger.info(f"任务重试 ({task.retry_count}/{task.max_retries}): {task.name} ({task.id})")
            else:
                task.status = TaskStatus.FAILED
                logger.error(f"任务执行失败: {task.name} ({task.id}) - {str(e)}")
    
    def stop(self):
        """停止工作线程"""
        self.running = False


class TaskScheduler:
    """任务调度器"""
    
    def __init__(self, max_workers: int = 10, queue_size: int = 1000):
        self.max_workers = max_workers
        self.queue_size = queue_size
        self.task_queue = TaskQueue(queue_size)
        self.workers: List[TaskWorker] = []
        self.tasks: Dict[str, Task] = {}
        self.running = False
        self._lock = threading.Lock()
        
        # 统计信息
        self.stats = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "cancelled_tasks": 0,
            "start_time": None
        }
    
    def start(self):
        """启动任务调度器"""
        if self.running:
            return
        
        logger.info(f"启动任务调度器，工作线程数: {self.max_workers}")
        
        self.running = True
        self.stats["start_time"] = datetime.now()
        
        # 创建并启动工作线程
        for i in range(self.max_workers):
            worker = TaskWorker(f"worker-{i}", self.task_queue, self)
            worker.start()
            self.workers.append(worker)
        
        logger.info("任务调度器启动完成")
    
    def stop(self, timeout: float = 30.0):
        """停止任务调度器"""
        if not self.running:
            return
        
        logger.info("正在停止任务调度器...")
        
        self.running = False
        
        # 停止所有工作线程
        for worker in self.workers:
            worker.stop()
        
        # 等待工作线程结束
        for worker in self.workers:
            worker.join(timeout=timeout / len(self.workers))
            if worker.is_alive():
                logger.warning(f"工作线程 {worker.worker_id} 未能正常停止")
        
        self.workers.clear()
        logger.info("任务调度器已停止")
    
    def submit_task(
        self,
        task: Optional[Task] = None,
        func: Optional[Callable] = None,
        args: tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
        name: str = "",
        priority: TaskPriority = TaskPriority.NORMAL,
        max_retries: int = 3,
        timeout: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """提交任务"""
        if task is None:
            if func is None:
                raise ValueError("task或func必须提供其中之一")
            
            task = Task(
                name=name or func.__name__,
                func=func,
                args=args,
                kwargs=kwargs or {},
                priority=priority,
                max_retries=max_retries,
                timeout=timeout,
                metadata=metadata or {}
            )
        
        with self._lock:
            self.tasks[task.id] = task
            self.stats["total_tasks"] += 1
        
        # 添加到队列
        if not self.task_queue.put(task, block=False):
            raise RuntimeError("任务队列已满")
        
        logger.info(f"提交任务: {task.name} ({task.id})")
        return task.id
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务信息"""
        with self._lock:
            return self.tasks.get(task_id)
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        with self._lock:
            task = self.tasks.get(task_id)
            if task and task.status == TaskStatus.PENDING:
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now()
                self.stats["cancelled_tasks"] += 1
                return True
            return False
    
    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """列出任务"""
        with self._lock:
            tasks = list(self.tasks.values())
        
        # 过滤状态
        if status:
            tasks = [t for t in tasks if t.status == status]
        
        # 排序（按创建时间倒序）
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        
        # 分页
        tasks = tasks[offset:offset + limit]
        
        return [task.to_dict() for task in tasks]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            # 更新统计信息
            completed = sum(1 for t in self.tasks.values() if t.status == TaskStatus.COMPLETED)
            failed = sum(1 for t in self.tasks.values() if t.status == TaskStatus.FAILED)
            cancelled = sum(1 for t in self.tasks.values() if t.status == TaskStatus.CANCELLED)
            
            self.stats.update({
                "completed_tasks": completed,
                "failed_tasks": failed,
                "cancelled_tasks": cancelled
            })
        
        # 工作线程统计
        worker_stats = []
        for worker in self.workers:
            worker_stats.append({
                "worker_id": worker.worker_id,
                "is_alive": worker.is_alive(),
                "tasks_processed": worker.tasks_processed,
                "current_task": worker.current_task.id if worker.current_task else None,
                "last_activity": worker.last_activity
            })
        
        uptime = (datetime.now() - self.stats["start_time"]).total_seconds() if self.stats["start_time"] else 0
        
        return {
            "scheduler": {
                "running": self.running,
                "uptime_seconds": uptime,
                "queue_size": self.task_queue.size(),
                "max_workers": self.max_workers
            },
            "tasks": self.stats.copy(),
            "workers": worker_stats
        }
    
    def cleanup_completed_tasks(self, older_than_hours: int = 24):
        """清理已完成的任务"""
        cutoff_time = datetime.now() - timedelta(hours=older_than_hours)
        
        with self._lock:
            tasks_to_remove = []
            for task_id, task in self.tasks.items():
                if (task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED] and
                    task.completed_at and task.completed_at < cutoff_time):
                    tasks_to_remove.append(task_id)
            
            for task_id in tasks_to_remove:
                del self.tasks[task_id]
            
            logger.info(f"清理了 {len(tasks_to_remove)} 个已完成的任务")
            return len(tasks_to_remove)


# 全局任务调度器实例
task_scheduler = TaskScheduler()


def get_task_scheduler() -> TaskScheduler:
    """获取全局任务调度器"""
    return task_scheduler 