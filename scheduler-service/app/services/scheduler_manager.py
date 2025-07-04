"""
调度器管理器 - 替代Celery的任务调度核心
支持定时任务、异步任务、任务队列和分布式调度
"""

import asyncio
import logging
import json
import uuid
from typing import Dict, List, Any, Optional, Callable, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
import heapq
import cron_descriptor
import redis.asyncio as redis

from app.core.config import settings
from app.services.task_executor import TaskExecutor

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """任务类型"""
    IMMEDIATE = "immediate"      # 立即执行
    DELAYED = "delayed"          # 延迟执行
    SCHEDULED = "scheduled"      # 定时执行
    RECURRING = "recurring"      # 周期性执行
    CONDITIONAL = "conditional"  # 条件触发


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class TaskPriority(Enum):
    """任务优先级"""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4


@dataclass
class Task:
    """任务定义"""
    task_id: str
    name: str
    task_type: TaskType
    function_name: str
    args: List[Any]
    kwargs: Dict[str, Any]
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    scheduled_time: Optional[datetime] = None
    cron_expression: Optional[str] = None
    max_retries: int = 3
    retry_count: int = 0
    timeout: int = 300
    created_at: datetime = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.metadata is None:
            self.metadata = {}

    def __lt__(self, other):
        """用于优先队列排序"""
        if self.priority != other.priority:
            return self.priority.value < other.priority.value
        return self.created_at < other.created_at


@dataclass
class Schedule:
    """调度定义"""
    schedule_id: str
    name: str
    task_name: str
    cron_expression: str
    function_name: str
    args: List[Any]
    kwargs: Dict[str, Any]
    enabled: bool = True
    next_run_time: Optional[datetime] = None
    last_run_time: Optional[datetime] = None
    created_at: datetime = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.metadata is None:
            self.metadata = {}


class SchedulerManager:
    """调度器管理器"""
    
    def __init__(self, task_executor: TaskExecutor):
        self.task_executor = task_executor
        self.redis_client: Optional[redis.Redis] = None
        
        # 任务队列 - 按优先级排序
        self.task_queue: List[Task] = []
        self.scheduled_tasks: Dict[str, Task] = {}
        self.running_tasks: Dict[str, Task] = {}
        self.completed_tasks: Dict[str, Task] = {}
        
        # 调度定义
        self.schedules: Dict[str, Schedule] = {}
        
        # 注册的任务函数
        self.registered_functions: Dict[str, Callable] = {}
        
        # 调度器状态
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._initialized = False
        
        # 统计信息
        self.stats = {
            "tasks_processed": 0,
            "tasks_failed": 0,
            "tasks_retried": 0,
            "schedules_executed": 0
        }
    
    async def initialize(self):
        """初始化调度器"""
        if self._initialized:
            return
            
        try:
            logger.info("初始化调度器管理器...")
            
            # 初始化Redis连接
            if settings.redis_url:
                self.redis_client = redis.from_url(
                    settings.redis_url,
                    decode_responses=True
                )
                await self.redis_client.ping()
                logger.info("Redis连接初始化成功")
                
                # 从Redis恢复持久化的任务和调度
                await self._restore_from_redis()
            
            # 注册默认任务函数
            await self._register_default_functions()
            
            self._initialized = True
            logger.info("调度器管理器初始化完成")
            
        except Exception as e:
            logger.error(f"调度器管理器初始化失败: {e}")
            raise
    
    async def _register_default_functions(self):
        """注册默认任务函数"""
        try:
            # 系统维护任务
            self.register_function("system_cleanup", self._system_cleanup)
            self.register_function("health_check", self._health_check)
            self.register_function("backup_data", self._backup_data)
            
            # 通用工具任务
            self.register_function("send_notification", self._send_notification)
            self.register_function("process_batch", self._process_batch)
            self.register_function("sync_data", self._sync_data)
            
            logger.info("默认任务函数注册完成")
            
        except Exception as e:
            logger.error(f"注册默认任务函数失败: {e}")
    
    def register_function(self, name: str, func: Callable):
        """注册任务函数"""
        self.registered_functions[name] = func
        logger.info(f"任务函数 '{name}' 注册成功")
    
    async def submit_task(
        self,
        name: str,
        function_name: str,
        args: List[Any] = None,
        kwargs: Dict[str, Any] = None,
        task_type: TaskType = TaskType.IMMEDIATE,
        priority: TaskPriority = TaskPriority.NORMAL,
        scheduled_time: Optional[datetime] = None,
        cron_expression: Optional[str] = None,
        max_retries: int = 3,
        timeout: int = 300,
        metadata: Dict[str, Any] = None
    ) -> str:
        """提交任务"""
        try:
            task_id = str(uuid.uuid4())
            
            task = Task(
                task_id=task_id,
                name=name,
                task_type=task_type,
                function_name=function_name,
                args=args or [],
                kwargs=kwargs or {},
                priority=priority,
                scheduled_time=scheduled_time,
                cron_expression=cron_expression,
                max_retries=max_retries,
                timeout=timeout,
                metadata=metadata or {}
            )
            
            # 根据任务类型处理
            if task_type == TaskType.IMMEDIATE:
                heapq.heappush(self.task_queue, task)
            elif task_type in [TaskType.DELAYED, TaskType.SCHEDULED]:
                self.scheduled_tasks[task_id] = task
            elif task_type == TaskType.RECURRING:
                if not cron_expression:
                    raise ValueError("周期性任务需要cron表达式")
                # 添加到调度中
                schedule = Schedule(
                    schedule_id=str(uuid.uuid4()),
                    name=f"recurring_{name}",
                    task_name=name,
                    cron_expression=cron_expression,
                    function_name=function_name,
                    args=args or [],
                    kwargs=kwargs or {}
                )
                await self.add_schedule(schedule)
            
            # 持久化到Redis
            if self.redis_client:
                await self.redis_client.setex(
                    f"scheduler:task:{task_id}",
                    timedelta(days=7),
                    json.dumps(asdict(task), default=str)
                )
            
            logger.info(f"任务 {task_id} 提交成功")
            return task_id
            
        except Exception as e:
            logger.error(f"提交任务失败: {e}")
            raise
    
    async def add_schedule(self, schedule: Schedule) -> str:
        """添加调度"""
        try:
            # 计算下次执行时间
            schedule.next_run_time = self._calculate_next_run_time(schedule.cron_expression)
            
            self.schedules[schedule.schedule_id] = schedule
            
            # 持久化到Redis
            if self.redis_client:
                await self.redis_client.setex(
                    f"scheduler:schedule:{schedule.schedule_id}",
                    timedelta(days=30),
                    json.dumps(asdict(schedule), default=str)
                )
            
            logger.info(f"调度 {schedule.schedule_id} 添加成功")
            return schedule.schedule_id
            
        except Exception as e:
            logger.error(f"添加调度失败: {e}")
            raise
    
    async def start(self):
        """启动调度器"""
        if self._running:
            return
            
        try:
            self._running = True
            
            # 启动主调度循环
            self._scheduler_task = asyncio.create_task(self._scheduler_loop())
            
            logger.info("调度器启动成功")
            
        except Exception as e:
            logger.error(f"启动调度器失败: {e}")
            self._running = False
            raise
    
    async def stop(self):
        """停止调度器"""
        if not self._running:
            return
            
        try:
            self._running = False
            
            if self._scheduler_task:
                self._scheduler_task.cancel()
                try:
                    await self._scheduler_task
                except asyncio.CancelledError:
                    pass
            
            # 等待正在执行的任务完成
            await self._wait_for_running_tasks()
            
            logger.info("调度器已停止")
            
        except Exception as e:
            logger.error(f"停止调度器失败: {e}")
    
    async def _scheduler_loop(self):
        """主调度循环"""
        logger.info("调度器主循环启动")
        
        while self._running:
            try:
                # 处理立即执行的任务
                await self._process_immediate_tasks()
                
                # 处理定时任务
                await self._process_scheduled_tasks()
                
                # 处理周期性调度
                await self._process_recurring_schedules()
                
                # 清理已完成的任务
                await self._cleanup_completed_tasks()
                
                # 休眠一秒
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"调度循环出错: {e}")
                await asyncio.sleep(5)  # 错误时休眠5秒
        
        logger.info("调度器主循环结束")
    
    async def _process_immediate_tasks(self):
        """处理立即执行的任务"""
        while self.task_queue and len(self.running_tasks) < settings.max_concurrent_tasks:
            task = heapq.heappop(self.task_queue)
            
            if task.status == TaskStatus.PENDING:
                await self._execute_task(task)
    
    async def _process_scheduled_tasks(self):
        """处理定时任务"""
        current_time = datetime.now()
        tasks_to_execute = []
        
        for task_id, task in self.scheduled_tasks.items():
            if (task.scheduled_time and 
                task.scheduled_time <= current_time and 
                task.status == TaskStatus.PENDING):
                tasks_to_execute.append(task_id)
        
        for task_id in tasks_to_execute:
            task = self.scheduled_tasks.pop(task_id)
            await self._execute_task(task)
    
    async def _process_recurring_schedules(self):
        """处理周期性调度"""
        current_time = datetime.now()
        
        for schedule in self.schedules.values():
            if (schedule.enabled and 
                schedule.next_run_time and 
                schedule.next_run_time <= current_time):
                
                # 创建任务实例
                task_id = await self.submit_task(
                    name=schedule.task_name,
                    function_name=schedule.function_name,
                    args=schedule.args,
                    kwargs=schedule.kwargs,
                    task_type=TaskType.IMMEDIATE,
                    metadata={"from_schedule": schedule.schedule_id}
                )
                
                # 更新调度信息
                schedule.last_run_time = current_time
                schedule.next_run_time = self._calculate_next_run_time(schedule.cron_expression)
                
                self.stats["schedules_executed"] += 1
                
                logger.info(f"调度 {schedule.schedule_id} 执行，创建任务 {task_id}")
    
    async def _execute_task(self, task: Task):
        """执行任务"""
        try:
            if task.function_name not in self.registered_functions:
                raise ValueError(f"未注册的任务函数: {task.function_name}")
            
            # 更新任务状态
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            self.running_tasks[task.task_id] = task
            
            # 获取任务函数
            func = self.registered_functions[task.function_name]
            
            # 执行任务
            logger.info(f"开始执行任务 {task.task_id}: {task.name}")
            
            # 提交到任务执行器
            result = await self.task_executor.execute_task(
                task_id=task.task_id,
                func=func,
                args=task.args,
                kwargs=task.kwargs,
                timeout=task.timeout
            )
            
            # 处理执行结果
            if result["success"]:
                task.status = TaskStatus.COMPLETED
                task.result = result["result"]
                self.stats["tasks_processed"] += 1
                logger.info(f"任务 {task.task_id} 执行成功")
            else:
                await self._handle_task_failure(task, result["error"])
            
        except Exception as e:
            await self._handle_task_failure(task, str(e))
        finally:
            task.completed_at = datetime.now()
            
            # 移动到已完成任务
            if task.task_id in self.running_tasks:
                del self.running_tasks[task.task_id]
            self.completed_tasks[task.task_id] = task
            
            # 更新Redis
            if self.redis_client:
                await self.redis_client.setex(
                    f"scheduler:task:{task.task_id}",
                    timedelta(days=7),
                    json.dumps(asdict(task), default=str)
                )
    
    async def _handle_task_failure(self, task: Task, error: str):
        """处理任务失败"""
        task.error = error
        task.retry_count += 1
        
        if task.retry_count <= task.max_retries:
            # 重试任务
            task.status = TaskStatus.RETRYING
            
            # 延迟重试（指数退避）
            delay = min(2 ** task.retry_count, 300)  # 最大5分钟
            task.scheduled_time = datetime.now() + timedelta(seconds=delay)
            task.task_type = TaskType.DELAYED
            
            self.scheduled_tasks[task.task_id] = task
            self.stats["tasks_retried"] += 1
            
            logger.warning(f"任务 {task.task_id} 失败，{delay}秒后重试 (第{task.retry_count}次)")
        else:
            # 最终失败
            task.status = TaskStatus.FAILED
            self.stats["tasks_failed"] += 1
            
            logger.error(f"任务 {task.task_id} 最终失败: {error}")
    
    def _calculate_next_run_time(self, cron_expression: str) -> datetime:
        """计算下次执行时间"""
        try:
            from croniter import croniter
            base_time = datetime.now()
            cron = croniter(cron_expression, base_time)
            return cron.get_next(datetime)
        except Exception as e:
            logger.error(f"解析cron表达式失败: {e}")
            # 默认1小时后
            return datetime.now() + timedelta(hours=1)
    
    async def _cleanup_completed_tasks(self):
        """清理已完成的任务"""
        cutoff_time = datetime.now() - timedelta(hours=24)
        tasks_to_remove = []
        
        for task_id, task in self.completed_tasks.items():
            if task.completed_at and task.completed_at < cutoff_time:
                tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            del self.completed_tasks[task_id]
            
            # 从Redis删除
            if self.redis_client:
                await self.redis_client.delete(f"scheduler:task:{task_id}")
    
    async def _wait_for_running_tasks(self, timeout: int = 60):
        """等待正在执行的任务完成"""
        start_time = datetime.now()
        
        while self.running_tasks and (datetime.now() - start_time).seconds < timeout:
            await asyncio.sleep(1)
        
        if self.running_tasks:
            logger.warning(f"仍有 {len(self.running_tasks)} 个任务正在执行")
    
    async def _restore_from_redis(self):
        """从Redis恢复持久化数据"""
        try:
            # 恢复任务
            task_keys = await self.redis_client.keys("scheduler:task:*")
            for key in task_keys:
                task_data = await self.redis_client.get(key)
                if task_data:
                    task_dict = json.loads(task_data)
                    task = Task(**task_dict)
                    
                    if task.status == TaskStatus.PENDING:
                        if task.task_type == TaskType.IMMEDIATE:
                            heapq.heappush(self.task_queue, task)
                        else:
                            self.scheduled_tasks[task.task_id] = task
                    elif task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                        self.completed_tasks[task.task_id] = task
            
            # 恢复调度
            schedule_keys = await self.redis_client.keys("scheduler:schedule:*")
            for key in schedule_keys:
                schedule_data = await self.redis_client.get(key)
                if schedule_data:
                    schedule_dict = json.loads(schedule_data)
                    schedule = Schedule(**schedule_dict)
                    self.schedules[schedule.schedule_id] = schedule
            
            logger.info(f"从Redis恢复 {len(task_keys)} 个任务和 {len(schedule_keys)} 个调度")
            
        except Exception as e:
            logger.error(f"从Redis恢复数据失败: {e}")
    
    # 默认任务函数实现
    async def _system_cleanup(self, *args, **kwargs):
        """系统清理任务"""
        logger.info("执行系统清理任务")
        # 这里可以实现具体的清理逻辑
        return {"message": "系统清理完成", "timestamp": datetime.now().isoformat()}
    
    async def _health_check(self, *args, **kwargs):
        """健康检查任务"""
        logger.info("执行健康检查任务")
        # 这里可以实现具体的健康检查逻辑
        return {"status": "healthy", "timestamp": datetime.now().isoformat()}
    
    async def _backup_data(self, *args, **kwargs):
        """数据备份任务"""
        logger.info("执行数据备份任务")
        # 这里可以实现具体的备份逻辑
        return {"message": "数据备份完成", "timestamp": datetime.now().isoformat()}
    
    async def _send_notification(self, message: str, recipients: List[str], *args, **kwargs):
        """发送通知任务"""
        logger.info(f"发送通知: {message} 到 {recipients}")
        # 这里可以实现具体的通知逻辑
        return {"message": "通知已发送", "recipients": recipients}
    
    async def _process_batch(self, items: List[Any], *args, **kwargs):
        """批处理任务"""
        logger.info(f"处理批量数据: {len(items)} 项")
        # 这里可以实现具体的批处理逻辑
        return {"processed": len(items), "timestamp": datetime.now().isoformat()}
    
    async def _sync_data(self, source: str, target: str, *args, **kwargs):
        """数据同步任务"""
        logger.info(f"同步数据从 {source} 到 {target}")
        # 这里可以实现具体的同步逻辑
        return {"source": source, "target": target, "synced": True}
    
    # 公共接口方法
    def is_running(self) -> bool:
        """检查调度器是否运行"""
        return self._running
    
    def get_pending_task_count(self) -> int:
        """获取待处理任务数量"""
        return len(self.task_queue) + len(self.scheduled_tasks)
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取调度器统计信息"""
        return {
            **self.stats,
            "pending_tasks": len(self.task_queue),
            "scheduled_tasks": len(self.scheduled_tasks),
            "running_tasks": len(self.running_tasks),
            "completed_tasks": len(self.completed_tasks),
            "active_schedules": len([s for s in self.schedules.values() if s.enabled]),
            "total_schedules": len(self.schedules),
            "registered_functions": len(self.registered_functions)
        } 