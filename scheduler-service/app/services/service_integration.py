"""
调度服务集成模块
Scheduler Service Integration

该模块负责任务调度、定时任务、作业管理和异步任务执行的服务集成
基于Celery框架，提供分布式任务队列和定时调度功能
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, asdict
from enum import Enum
import json
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

from celery import Celery
from celery.result import AsyncResult
from celery.schedules import crontab
import redis
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.executors.pool import ThreadPoolExecutor as APSThreadPoolExecutor

# 导入共享服务客户端
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../../shared'))

from service_client.client import ServiceClient
from service_client.config import ServiceConfig

logger = logging.getLogger(__name__)

class TaskType(Enum):
    """任务类型枚举"""
    IMMEDIATE = "immediate"          # 立即执行
    DELAYED = "delayed"             # 延时执行
    RECURRING = "recurring"         # 定期重复
    CRON = "cron"                  # Cron表达式
    DEPENDENT = "dependent"         # 依赖任务

class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"             # 等待执行
    RUNNING = "running"             # 正在执行
    SUCCESS = "success"             # 执行成功
    FAILED = "failed"              # 执行失败
    RETRY = "retry"                # 重试中
    REVOKED = "revoked"            # 已撤销
    SCHEDULED = "scheduled"         # 已调度

class TaskPriority(Enum):
    """任务优先级枚举"""
    LOW = 1
    NORMAL = 5
    HIGH = 8
    CRITICAL = 10

@dataclass
class TaskDefinition:
    """任务定义"""
    task_id: str
    name: str
    task_type: TaskType
    priority: TaskPriority
    service_name: str
    endpoint: str
    payload: Dict[str, Any]
    schedule: Optional[str] = None
    retry_count: int = 3
    timeout: int = 300
    depends_on: List[str] = None
    tags: List[str] = None
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
        if self.depends_on is None:
            self.depends_on = []
        if self.tags is None:
            self.tags = []

@dataclass
class TaskResult:
    """任务结果"""
    task_id: str
    status: TaskStatus
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration: Optional[float] = None
    retry_count: int = 0
    worker_id: Optional[str] = None

class SchedulerServiceIntegration:
    """调度服务集成类"""
    
    def __init__(self):
        """初始化调度服务集成"""
        self.service_client = ServiceClient()
        self.config = ServiceConfig()
        
        # Redis连接
        self.redis_client = redis.Redis(
            host=self.config.get('redis.host', 'localhost'),
            port=self.config.get('redis.port', 6379),
            db=self.config.get('redis.scheduler_db', 2),
            decode_responses=True
        )
        
        # 初始化Celery
        self._init_celery()
        
        # 初始化APScheduler
        self._init_scheduler()
        
        # 任务存储
        self.tasks: Dict[str, TaskDefinition] = {}
        self.task_results: Dict[str, TaskResult] = {}
        
        # 线程池
        self.executor = ThreadPoolExecutor(max_workers=10)
        
        # 统计信息
        self.stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'running_tasks': 0,
            'scheduled_tasks': 0
        }
        
        logger.info("调度服务集成初始化完成")
    
    def _init_celery(self):
        """初始化Celery"""
        broker_url = f"redis://{self.config.get('redis.host', 'localhost')}:{self.config.get('redis.port', 6379)}/1"
        result_backend = f"redis://{self.config.get('redis.host', 'localhost')}:{self.config.get('redis.port', 6379)}/2"
        
        self.celery_app = Celery(
            'scheduler-service',
            broker=broker_url,
            backend=result_backend
        )
        
        self.celery_app.conf.update(
            task_serializer='json',
            accept_content=['json'],
            result_serializer='json',
            timezone='UTC',
            enable_utc=True,
            task_track_started=True,
            task_time_limit=1800,  # 30分钟
            task_soft_time_limit=1500,  # 25分钟
            worker_prefetch_multiplier=1,
            task_acks_late=True,
            worker_disable_rate_limits=False,
            task_compression='gzip',
            result_compression='gzip',
            result_expires=3600,  # 1小时
        )
    
    def _init_scheduler(self):
        """初始化APScheduler"""
        jobstores = {
            'default': RedisJobStore(
                host=self.config.get('redis.host', 'localhost'),
                port=self.config.get('redis.port', 6379),
                db=self.config.get('redis.scheduler_db', 3)
            )
        }
        
        executors = {
            'default': APSThreadPoolExecutor(20),
        }
        
        job_defaults = {
            'coalesce': False,
            'max_instances': 3
        }
        
        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults
        )
    
    async def start_scheduler(self):
        """启动调度器"""
        try:
            self.scheduler.start()
            logger.info("APScheduler 启动成功")
        except Exception as e:
            logger.error(f"启动调度器失败: {e}")
            raise
    
    async def stop_scheduler(self):
        """停止调度器"""
        try:
            self.scheduler.shutdown(wait=False)
            logger.info("APScheduler 停止成功")
        except Exception as e:
            logger.error(f"停止调度器失败: {e}")
    
    async def create_task(self, task_def: TaskDefinition) -> str:
        """创建任务"""
        try:
            # 验证任务定义
            await self._validate_task_definition(task_def)
            
            # 存储任务定义
            self.tasks[task_def.task_id] = task_def
            
            # 根据任务类型进行调度
            if task_def.task_type == TaskType.IMMEDIATE:
                await self._schedule_immediate_task(task_def)
            elif task_def.task_type == TaskType.DELAYED:
                await self._schedule_delayed_task(task_def)
            elif task_def.task_type == TaskType.RECURRING:
                await self._schedule_recurring_task(task_def)
            elif task_def.task_type == TaskType.CRON:
                await self._schedule_cron_task(task_def)
            elif task_def.task_type == TaskType.DEPENDENT:
                await self._schedule_dependent_task(task_def)
            
            # 更新统计信息
            self.stats['total_tasks'] += 1
            self.stats['scheduled_tasks'] += 1
            
            # 持久化任务信息
            await self._persist_task(task_def)
            
            logger.info(f"任务创建成功: {task_def.task_id}")
            return task_def.task_id
            
        except Exception as e:
            logger.error(f"创建任务失败: {e}")
            raise
    
    async def _validate_task_definition(self, task_def: TaskDefinition):
        """验证任务定义"""
        if not task_def.task_id:
            raise ValueError("任务ID不能为空")
        
        if not task_def.service_name:
            raise ValueError("服务名称不能为空")
        
        if not task_def.endpoint:
            raise ValueError("服务端点不能为空")
        
        # 验证依赖任务是否存在
        for dep_task_id in task_def.depends_on:
            if dep_task_id not in self.tasks:
                raise ValueError(f"依赖任务不存在: {dep_task_id}")
        
        # 验证定时表达式
        if task_def.task_type in [TaskType.RECURRING, TaskType.CRON] and not task_def.schedule:
            raise ValueError("定时任务必须指定调度表达式")
    
    async def _schedule_immediate_task(self, task_def: TaskDefinition):
        """调度立即执行任务"""
        # 使用Celery异步执行
        result = self.celery_app.send_task(
            'scheduler.execute_task',
            args=[task_def.task_id],
            priority=task_def.priority.value,
            retry=True,
            retry_policy={
                'max_retries': task_def.retry_count,
                'interval_start': 1,
                'interval_step': 1,
                'interval_max': 60,
            }
        )
        
        # 记录任务结果引用
        task_result = TaskResult(
            task_id=task_def.task_id,
            status=TaskStatus.PENDING
        )
        self.task_results[task_def.task_id] = task_result
    
    async def _schedule_delayed_task(self, task_def: TaskDefinition):
        """调度延时执行任务"""
        if not task_def.schedule:
            raise ValueError("延时任务需要指定延时时间")
        
        # 解析延时时间
        delay_seconds = int(task_def.schedule)
        eta = datetime.utcnow() + timedelta(seconds=delay_seconds)
        
        result = self.celery_app.send_task(
            'scheduler.execute_task',
            args=[task_def.task_id],
            eta=eta,
            priority=task_def.priority.value
        )
        
        task_result = TaskResult(
            task_id=task_def.task_id,
            status=TaskStatus.SCHEDULED
        )
        self.task_results[task_def.task_id] = task_result
    
    async def _schedule_recurring_task(self, task_def: TaskDefinition):
        """调度重复执行任务"""
        # 解析间隔时间
        interval_seconds = int(task_def.schedule)
        
        self.scheduler.add_job(
            func=self._execute_scheduled_task,
            trigger='interval',
            seconds=interval_seconds,
            args=[task_def.task_id],
            id=task_def.task_id,
            replace_existing=True,
            max_instances=1
        )
        
        task_result = TaskResult(
            task_id=task_def.task_id,
            status=TaskStatus.SCHEDULED
        )
        self.task_results[task_def.task_id] = task_result
    
    async def _schedule_cron_task(self, task_def: TaskDefinition):
        """调度Cron表达式任务"""
        # 解析Cron表达式
        cron_parts = task_def.schedule.split()
        if len(cron_parts) != 5:
            raise ValueError("Cron表达式格式错误，应为: 分 时 日 月 周")
        
        minute, hour, day, month, day_of_week = cron_parts
        
        self.scheduler.add_job(
            func=self._execute_scheduled_task,
            trigger='cron',
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
            args=[task_def.task_id],
            id=task_def.task_id,
            replace_existing=True
        )
        
        task_result = TaskResult(
            task_id=task_def.task_id,
            status=TaskStatus.SCHEDULED
        )
        self.task_results[task_def.task_id] = task_result
    
    async def _schedule_dependent_task(self, task_def: TaskDefinition):
        """调度依赖任务"""
        # 检查依赖任务状态
        dependencies_met = await self._check_dependencies(task_def.depends_on)
        
        if dependencies_met:
            await self._schedule_immediate_task(task_def)
        else:
            # 等待依赖任务完成
            task_result = TaskResult(
                task_id=task_def.task_id,
                status=TaskStatus.PENDING
            )
            self.task_results[task_def.task_id] = task_result
    
    async def _check_dependencies(self, depends_on: List[str]) -> bool:
        """检查依赖任务是否完成"""
        for dep_task_id in depends_on:
            if dep_task_id in self.task_results:
                result = self.task_results[dep_task_id]
                if result.status not in [TaskStatus.SUCCESS]:
                    return False
            else:
                return False
        return True
    
    async def _execute_scheduled_task(self, task_id: str):
        """执行调度任务"""
        try:
            task_def = self.tasks.get(task_id)
            if not task_def:
                logger.error(f"任务定义未找到: {task_id}")
                return
            
            # 通过Celery执行
            result = self.celery_app.send_task(
                'scheduler.execute_task',
                args=[task_id],
                priority=task_def.priority.value
            )
            
        except Exception as e:
            logger.error(f"执行调度任务失败: {task_id}, 错误: {e}")
    
    async def execute_task(self, task_id: str) -> TaskResult:
        """执行任务"""
        start_time = datetime.utcnow()
        
        try:
            task_def = self.tasks.get(task_id)
            if not task_def:
                raise ValueError(f"任务定义未找到: {task_id}")
            
            # 更新任务状态
            task_result = self.task_results.get(task_id, TaskResult(
                task_id=task_id,
                status=TaskStatus.RUNNING
            ))
            task_result.status = TaskStatus.RUNNING
            task_result.started_at = start_time
            self.task_results[task_id] = task_result
            
            # 更新统计信息
            self.stats['running_tasks'] += 1
            if task_result.status == TaskStatus.SCHEDULED:
                self.stats['scheduled_tasks'] -= 1
            
            # 调用目标服务
            response = await self.service_client.call_service(
                service_name=task_def.service_name,
                endpoint=task_def.endpoint,
                data=task_def.payload,
                timeout=task_def.timeout
            )
            
            # 更新任务结果
            finish_time = datetime.utcnow()
            task_result.status = TaskStatus.SUCCESS
            task_result.result = response
            task_result.finished_at = finish_time
            task_result.duration = (finish_time - start_time).total_seconds()
            
            # 更新统计信息
            self.stats['running_tasks'] -= 1
            self.stats['completed_tasks'] += 1
            
            # 触发依赖任务
            await self._trigger_dependent_tasks(task_id)
            
            logger.info(f"任务执行成功: {task_id}")
            return task_result
            
        except Exception as e:
            # 更新任务结果
            finish_time = datetime.utcnow()
            task_result = self.task_results.get(task_id, TaskResult(task_id=task_id, status=TaskStatus.FAILED))
            task_result.status = TaskStatus.FAILED
            task_result.error = str(e)
            task_result.finished_at = finish_time
            task_result.duration = (finish_time - start_time).total_seconds()
            
            # 更新统计信息
            self.stats['running_tasks'] -= 1
            self.stats['failed_tasks'] += 1
            
            logger.error(f"任务执行失败: {task_id}, 错误: {e}")
            return task_result
        
        finally:
            # 持久化任务结果
            await self._persist_task_result(task_result)
    
    async def _trigger_dependent_tasks(self, completed_task_id: str):
        """触发依赖任务"""
        for task_id, task_def in self.tasks.items():
            if (completed_task_id in task_def.depends_on and 
                task_def.task_type == TaskType.DEPENDENT):
                
                # 检查所有依赖是否完成
                dependencies_met = await self._check_dependencies(task_def.depends_on)
                if dependencies_met:
                    await self._schedule_immediate_task(task_def)
    
    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        try:
            # 取消Celery任务
            result = AsyncResult(task_id, app=self.celery_app)
            result.revoke(terminate=True)
            
            # 取消调度任务
            try:
                self.scheduler.remove_job(task_id)
            except:
                pass  # 任务可能不在调度器中
            
            # 更新任务状态
            if task_id in self.task_results:
                self.task_results[task_id].status = TaskStatus.REVOKED
            
            logger.info(f"任务取消成功: {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"取消任务失败: {task_id}, 错误: {e}")
            return False
    
    async def get_task_status(self, task_id: str) -> Optional[TaskResult]:
        """获取任务状态"""
        return self.task_results.get(task_id)
    
    async def list_tasks(self, status: Optional[TaskStatus] = None, 
                        service_name: Optional[str] = None,
                        page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """列出任务"""
        tasks = []
        
        for task_id, task_def in self.tasks.items():
            task_result = self.task_results.get(task_id, TaskResult(
                task_id=task_id,
                status=TaskStatus.PENDING
            ))
            
            # 过滤条件
            if status and task_result.status != status:
                continue
            if service_name and task_def.service_name != service_name:
                continue
            
            task_info = {
                'task_id': task_id,
                'name': task_def.name,
                'type': task_def.task_type.value,
                'priority': task_def.priority.value,
                'service_name': task_def.service_name,
                'status': task_result.status.value,
                'created_at': task_def.created_at.isoformat(),
                'started_at': task_result.started_at.isoformat() if task_result.started_at else None,
                'finished_at': task_result.finished_at.isoformat() if task_result.finished_at else None,
                'duration': task_result.duration
            }
            tasks.append(task_info)
        
        # 分页
        total = len(tasks)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_tasks = tasks[start_idx:end_idx]
        
        return {
            'tasks': paginated_tasks,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size
        }
    
    async def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'stats': self.stats,
            'active_jobs': len(self.scheduler.get_jobs()),
            'celery_active_tasks': self.celery_app.control.inspect().active(),
            'redis_info': {
                'connections': self.redis_client.info()['connected_clients'],
                'memory_usage': self.redis_client.info()['used_memory_human']
            }
        }
    
    async def _persist_task(self, task_def: TaskDefinition):
        """持久化任务定义"""
        try:
            task_data = asdict(task_def)
            # 转换datetime为字符串
            task_data['created_at'] = task_def.created_at.isoformat()
            task_data['updated_at'] = task_def.updated_at.isoformat()
            task_data['task_type'] = task_def.task_type.value
            task_data['priority'] = task_def.priority.value
            
            self.redis_client.hset(
                'scheduler:tasks',
                task_def.task_id,
                json.dumps(task_data)
            )
        except Exception as e:
            logger.error(f"持久化任务定义失败: {e}")
    
    async def _persist_task_result(self, task_result: TaskResult):
        """持久化任务结果"""
        try:
            result_data = asdict(task_result)
            # 转换datetime为字符串
            if task_result.started_at:
                result_data['started_at'] = task_result.started_at.isoformat()
            if task_result.finished_at:
                result_data['finished_at'] = task_result.finished_at.isoformat()
            result_data['status'] = task_result.status.value
            
            self.redis_client.hset(
                'scheduler:results',
                task_result.task_id,
                json.dumps(result_data)
            )
        except Exception as e:
            logger.error(f"持久化任务结果失败: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            # 检查Redis连接
            redis_ok = self.redis_client.ping()
            
            # 检查Celery状态
            celery_stats = self.celery_app.control.inspect().stats()
            celery_ok = celery_stats is not None
            
            # 检查调度器状态
            scheduler_ok = self.scheduler.running
            
            return {
                'status': 'healthy' if all([redis_ok, celery_ok, scheduler_ok]) else 'unhealthy',
                'components': {
                    'redis': 'ok' if redis_ok else 'error',
                    'celery': 'ok' if celery_ok else 'error',
                    'scheduler': 'ok' if scheduler_ok else 'error'
                },
                'stats': self.stats,
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }

# 创建全局实例
scheduler_integration = SchedulerServiceIntegration()

# 预定义任务模板
PREDEFINED_TASKS = {
    'knowledge_index_refresh': {
        'name': '知识库索引刷新',
        'task_type': TaskType.RECURRING,
        'priority': TaskPriority.NORMAL,
        'service_name': 'knowledge-service',
        'endpoint': '/internal/refresh_index',
        'schedule': '3600',  # 每小时
        'timeout': 1800,
        'tags': ['maintenance', 'knowledge']
    },
    'model_cache_cleanup': {
        'name': '模型缓存清理',
        'task_type': TaskType.CRON,
        'priority': TaskPriority.LOW,
        'service_name': 'model-service',
        'endpoint': '/internal/cleanup_cache',
        'schedule': '0 2 * * *',  # 每天凌晨2点
        'timeout': 600,
        'tags': ['maintenance', 'cleanup']
    },
    'user_activity_summary': {
        'name': '用户活动汇总',
        'task_type': TaskType.CRON,
        'priority': TaskPriority.NORMAL,
        'service_name': 'base-service',
        'endpoint': '/internal/activity_summary',
        'schedule': '0 0 * * 0',  # 每周日午夜
        'timeout': 3600,
        'tags': ['analytics', 'users']
    },
    'system_health_check': {
        'name': '系统健康检查',
        'task_type': TaskType.RECURRING,
        'priority': TaskPriority.HIGH,
        'service_name': 'gateway-service',
        'endpoint': '/health/check_all',
        'schedule': '300',  # 每5分钟
        'timeout': 60,
        'tags': ['monitoring', 'health']
    }
}

async def create_predefined_task(task_key: str, custom_params: Dict[str, Any] = None) -> str:
    """创建预定义任务"""
    if task_key not in PREDEFINED_TASKS:
        raise ValueError(f"预定义任务不存在: {task_key}")
    
    template = PREDEFINED_TASKS[task_key].copy()
    if custom_params:
        template.update(custom_params)
    
    task_id = f"{task_key}_{uuid.uuid4().hex[:8]}"
    
    task_def = TaskDefinition(
        task_id=task_id,
        name=template['name'],
        task_type=template['task_type'],
        priority=template['priority'],
        service_name=template['service_name'],
        endpoint=template['endpoint'],
        payload=template.get('payload', {}),
        schedule=template.get('schedule'),
        retry_count=template.get('retry_count', 3),
        timeout=template.get('timeout', 300),
        depends_on=template.get('depends_on', []),
        tags=template.get('tags', [])
    )
    
    return await scheduler_integration.create_task(task_def)

# 导出主要类和函数
__all__ = [
    'SchedulerServiceIntegration',
    'TaskDefinition',
    'TaskResult',
    'TaskType',
    'TaskStatus',
    'TaskPriority',
    'scheduler_integration',
    'create_predefined_task',
    'PREDEFINED_TASKS'
] 