"""
Redis队列管理器
实现基于Redis的异步任务队列
"""

import json
import logging
import redis
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable
from app.config.settings import settings
from .task_models import TaskModel, TaskStatus, TaskUpdateModel, TaskQueryModel

logger = logging.getLogger(__name__)


class RedisQueue:
    """Redis队列管理器"""
    
    def __init__(self, redis_url: Optional[str] = None):
        """初始化Redis连接"""
        self.redis_url = redis_url or settings.get_redis_url()
        self.redis_client: Optional[redis.Redis] = None
        self.task_prefix = "task:"
        self.queue_prefix = "queue:"
        self.status_prefix = "status:"
        self.notification_channel = "task_notifications"
        
    def connect(self) -> bool:
        """连接Redis"""
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=35
            )
            # 测试连接
            self.redis_client.ping()
            logger.info("Redis连接成功")
            return True
        except Exception as e:
            logger.error(f"Redis连接失败: {e}")
            return False
    
    def disconnect(self):
        """断开Redis连接"""
        if self.redis_client:
            self.redis_client.close()
            logger.info("Redis连接已断开")
    
    def _ensure_connected(self):
        """确保Redis连接"""
        if not self.redis_client:
            if not self.connect():
                raise ConnectionError("无法连接到Redis")
    
    def _get_task_key(self, task_id: str) -> str:
        """获取任务键名"""
        return f"{self.task_prefix}{task_id}"
    
    def _get_queue_key(self, queue_name: str) -> str:
        """获取队列键名"""
        return f"{self.queue_prefix}{queue_name}"
    
    def _get_status_key(self, task_id: str) -> str:
        """获取状态键名"""
        return f"{self.status_prefix}{task_id}"
    
    async def enqueue_task(self, task: TaskModel, queue_name: str = "default") -> bool:
        """将任务加入队列"""
        try:
            self._ensure_connected()
            
            task_key = self._get_task_key(task.task_id)
            queue_key = self._get_queue_key(queue_name)
            status_key = self._get_status_key(task.task_id)
            
            # 存储任务数据
            task_data = task.dict()
            self.redis_client.setex(
                task_key, 
                timedelta(days=7),  # 任务数据保存7天
                json.dumps(task_data, default=str)
            )
            
            # 任务加入队列
            self.redis_client.lpush(queue_key, task.task_id)
            
            # 设置任务状态
            self.redis_client.setex(
                status_key,
                timedelta(days=7),
                TaskStatus.PENDING.value
            )
            
            # 发送通知
            await self._notify_task_update(task.task_id, task.status, "任务已入队")
            
            logger.info(f"任务 {task.task_id} 已加入队列 {queue_name}")
            return True
            
        except Exception as e:
            logger.error(f"任务入队失败: {e}")
            return False
    
    async def dequeue_task(self, queue_name: str = "default", timeout: int = 30) -> Optional[TaskModel]:
        """从队列中取出任务"""
        try:
            self._ensure_connected()
            
            queue_key = self._get_queue_key(queue_name)
            
            # 阻塞式取出任务
            result = self.redis_client.brpop(queue_key, timeout=timeout)
            if not result:
                return None
            
            _, task_id = result
            
            # 获取任务数据
            task_data = await self.get_task(task_id)
            if task_data:
                # 更新任务状态为处理中
                await self.update_task_status(
                    task_id, 
                    TaskStatus.PROCESSING,
                    "开始处理任务"
                )
                return task_data
            
            return None
            
        except Exception as e:
            logger.error(f"任务出队失败: {e}")
            return None
    
    async def get_task(self, task_id: str) -> Optional[TaskModel]:
        """获取任务信息"""
        try:
            self._ensure_connected()
            
            task_key = self._get_task_key(task_id)
            task_data = self.redis_client.get(task_key)
            
            if task_data:
                data = json.loads(task_data)
                return TaskModel(**data)
            
            return None
            
        except Exception as e:
            logger.error(f"获取任务失败: {e}")
            return None
    
    async def update_task(self, task_id: str, update_data: TaskUpdateModel) -> bool:
        """更新任务信息"""
        try:
            self._ensure_connected()
            
            # 获取现有任务
            task = await self.get_task(task_id)
            if not task:
                logger.warning(f"任务 {task_id} 不存在")
                return False
            
            # 更新字段
            update_dict = update_data.dict(exclude_none=True)
            for key, value in update_dict.items():
                setattr(task, key, value)
            
            # 更新时间戳
            if update_data.status == TaskStatus.PROCESSING and not task.started_at:
                task.started_at = datetime.now()
            elif update_data.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                task.completed_at = datetime.now()
            
            # 保存更新后的任务
            task_key = self._get_task_key(task_id)
            self.redis_client.setex(
                task_key,
                timedelta(days=7),
                json.dumps(task.dict(), default=str)
            )
            
            # 更新状态键
            if update_data.status:
                status_key = self._get_status_key(task_id)
                self.redis_client.setex(
                    status_key,
                    timedelta(days=7),
                    update_data.status.value
                )
            
            # 发送通知
            await self._notify_task_update(
                task_id, 
                update_data.status or task.status,
                update_data.message or task.message
            )
            
            logger.info(f"任务 {task_id} 已更新")
            return True
            
        except Exception as e:
            logger.error(f"更新任务失败: {e}")
            return False
    
    async def update_task_status(self, task_id: str, status: TaskStatus, message: str = "") -> bool:
        """更新任务状态"""
        return await self.update_task(
            task_id,
            TaskUpdateModel(status=status, message=message)
        )
    
    async def update_task_progress(self, task_id: str, progress: int, message: str = "") -> bool:
        """更新任务进度"""
        return await self.update_task(
            task_id,
            TaskUpdateModel(progress=progress, message=message)
        )
    
    async def cancel_task(self, task_id: str, reason: str = "用户取消") -> bool:
        """取消任务"""
        return await self.update_task(
            task_id,
            TaskUpdateModel(status=TaskStatus.CANCELLED, message=reason)
        )
    
    async def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """获取任务状态"""
        try:
            self._ensure_connected()
            
            status_key = self._get_status_key(task_id)
            status_value = self.redis_client.get(status_key)
            
            if status_value:
                return TaskStatus(status_value)
            
            return None
            
        except Exception as e:
            logger.error(f"获取任务状态失败: {e}")
            return None
    
    async def query_tasks(self, query: TaskQueryModel) -> List[TaskModel]:
        """查询任务列表"""
        try:
            self._ensure_connected()
            
            # 简单实现：扫描所有任务键
            pattern = f"{self.task_prefix}*"
            task_keys = self.redis_client.keys(pattern)
            
            tasks = []
            for task_key in task_keys:
                task_data = self.redis_client.get(task_key)
                if task_data:
                    try:
                        task = TaskModel(**json.loads(task_data))
                        
                        # 应用过滤条件
                        if query.task_ids and task.task_id not in query.task_ids:
                            continue
                        if query.task_types and task.task_type not in query.task_types:
                            continue
                        if query.statuses and task.status not in query.statuses:
                            continue
                        if query.created_after and task.created_at < query.created_after:
                            continue
                        if query.created_before and task.created_at > query.created_before:
                            continue
                        
                        tasks.append(task)
                    except Exception as e:
                        logger.warning(f"解析任务数据失败: {e}")
                        continue
            
            # 排序和分页
            tasks.sort(key=lambda x: x.created_at, reverse=True)
            start = query.offset
            end = start + query.limit
            
            return tasks[start:end]
            
        except Exception as e:
            logger.error(f"查询任务失败: {e}")
            return []
    
    async def get_queue_length(self, queue_name: str = "default") -> int:
        """获取队列长度"""
        try:
            self._ensure_connected()
            
            queue_key = self._get_queue_key(queue_name)
            return self.redis_client.llen(queue_key)
            
        except Exception as e:
            logger.error(f"获取队列长度失败: {e}")
            return 0
    
    async def clear_queue(self, queue_name: str = "default") -> bool:
        """清空队列"""
        try:
            self._ensure_connected()
            
            queue_key = self._get_queue_key(queue_name)
            self.redis_client.delete(queue_key)
            
            logger.info(f"队列 {queue_name} 已清空")
            return True
            
        except Exception as e:
            logger.error(f"清空队列失败: {e}")
            return False
    
    async def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        try:
            self._ensure_connected()
            
            task_key = self._get_task_key(task_id)
            status_key = self._get_status_key(task_id)
            
            # 删除任务数据和状态
            self.redis_client.delete(task_key, status_key)
            
            logger.info(f"任务 {task_id} 已删除")
            return True
            
        except Exception as e:
            logger.error(f"删除任务失败: {e}")
            return False
    
    async def _notify_task_update(self, task_id: str, status: TaskStatus, message: str):
        """发送任务更新通知"""
        try:
            notification = {
                "task_id": task_id,
                "status": status.value,
                "message": message,
                "timestamp": datetime.now().isoformat()
            }
            
            self.redis_client.publish(
                self.notification_channel,
                json.dumps(notification)
            )
            
        except Exception as e:
            logger.warning(f"发送通知失败: {e}")
    
    async def subscribe_task_updates(self, callback: Callable[[Dict[str, Any]], None]):
        """订阅任务更新通知"""
        try:
            self._ensure_connected()
            
            pubsub = self.redis_client.pubsub()
            pubsub.subscribe(self.notification_channel)
            
            logger.info("开始监听任务更新通知")
            
            for message in pubsub.listen():
                if message['type'] == 'message':
                    try:
                        notification = json.loads(message['data'])
                        await callback(notification)
                    except Exception as e:
                        logger.error(f"处理通知失败: {e}")
                        
        except Exception as e:
            logger.error(f"订阅通知失败: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            self._ensure_connected()
            
            # 测试Redis连接
            ping_result = self.redis_client.ping()
            
            # 获取队列统计
            default_queue_length = await self.get_queue_length("default")
            
            # 获取任务统计
            pattern = f"{self.task_prefix}*"
            total_tasks = len(self.redis_client.keys(pattern))
            
            return {
                "status": "healthy",
                "redis_ping": ping_result,
                "default_queue_length": default_queue_length,
                "total_tasks": total_tasks,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


# 全局Redis队列实例
_redis_queue: Optional[RedisQueue] = None


def get_redis_queue() -> RedisQueue:
    """获取Redis队列实例"""
    global _redis_queue
    if _redis_queue is None:
        _redis_queue = RedisQueue()
        if not _redis_queue.connect():
            raise ConnectionError("无法连接到Redis队列")
    return _redis_queue