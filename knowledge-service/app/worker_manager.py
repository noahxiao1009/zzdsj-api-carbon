"""
简化的Worker管理器
集成到FastAPI应用中，避免信号处理问题
"""

import asyncio
import logging
from typing import Optional

from app.queues.task_processor import get_task_processor
from app.queues.redis_queue import get_redis_queue

logger = logging.getLogger(__name__)


class SimpleWorkerManager:
    """简化的Worker管理器"""
    
    def __init__(self):
        self.task_processor = None
        self.worker_tasks = []
        self.is_running = False
        
    async def start(self):
        """启动worker"""
        if self.is_running:
            logger.warning("Worker已在运行")
            return
            
        try:
            logger.info("正在启动文档处理Worker...")
            
            # 初始化任务处理器
            self.task_processor = await get_task_processor()
            
            # 检查Redis连接
            redis_queue = get_redis_queue()
            health = await redis_queue.health_check()
            
            if health.get("status") != "healthy":
                logger.warning(f"Redis连接不健康: {health}")
                # 不抛出异常，允许服务继续运行
                return
            
            logger.info("Redis连接正常，启动Worker任务")
            
            # 创建3个工作进程
            for i in range(3):
                task = asyncio.create_task(
                    self._worker_loop(f"worker-{i}")
                )
                self.worker_tasks.append(task)
            
            self.is_running = True
            logger.info(f"文档处理Worker已启动，运行 {len(self.worker_tasks)} 个工作进程")
            
        except Exception as e:
            logger.error(f"Worker启动失败: {e}")
            # 不抛出异常，让主服务继续运行
    
    async def stop(self):
        """停止worker"""
        if not self.is_running:
            return
            
        logger.info("正在停止文档处理Worker...")
        self.is_running = False
        
        # 停止任务处理器
        if self.task_processor:
            await self.task_processor.stop_processing()
        
        # 取消所有工作任务
        for task in self.worker_tasks:
            if not task.done():
                task.cancel()
        
        # 等待所有任务完成
        if self.worker_tasks:
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)
            self.worker_tasks.clear()
        
        logger.info("文档处理Worker已停止")
    
    async def _worker_loop(self, worker_name: str):
        """工作进程循环"""
        logger.info(f"工作进程 {worker_name} 开始")
        
        try:
            while self.is_running:
                try:
                    # 获取Redis队列
                    redis_queue = get_redis_queue()
                    
                    # 从队列获取任务（短超时）
                    task = await redis_queue.dequeue_task("document_processing", timeout=2)
                    
                    if task and self.task_processor:
                        logger.info(f"工作进程 {worker_name} 开始处理任务 {task.task_id}")
                        await self.task_processor._process_task(task)
                        logger.info(f"工作进程 {worker_name} 完成任务 {task.task_id}")
                    
                    # 短暂休眠以避免过度CPU使用
                    await asyncio.sleep(0.1)
                    
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


# 全局Worker管理器实例
_worker_manager = None


async def get_worker_manager() -> SimpleWorkerManager:
    """获取Worker管理器实例"""
    global _worker_manager
    if _worker_manager is None:
        _worker_manager = SimpleWorkerManager()
    return _worker_manager


async def start_worker():
    """启动Worker"""
    manager = await get_worker_manager()
    await manager.start()


async def stop_worker():
    """停止Worker"""
    global _worker_manager
    if _worker_manager:
        await _worker_manager.stop()