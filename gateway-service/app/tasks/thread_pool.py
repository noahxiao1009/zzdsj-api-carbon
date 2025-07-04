"""
线程池管理器
用于管理网关的线程池，支持不同类型的任务分类处理
"""

import threading
import logging
import time
from typing import Dict, Any, Optional, List, Callable
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class PoolType(str, Enum):
    """线程池类型枚举"""
    IO_BOUND = "io_bound"        # IO密集型任务（网络请求、文件操作等）
    CPU_BOUND = "cpu_bound"      # CPU密集型任务（计算任务等）
    PROXY = "proxy"              # 代理请求专用
    HEALTH_CHECK = "health_check" # 健康检查专用


@dataclass
class PoolConfig:
    """线程池配置"""
    max_workers: int = 10
    thread_name_prefix: str = ""
    queue_size: int = 1000
    keep_alive_time: int = 60  # 线程空闲时间（秒）


@dataclass
class PoolStats:
    """线程池统计信息"""
    pool_type: PoolType
    max_workers: int
    active_threads: int = 0
    pending_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    total_submitted: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: Optional[datetime] = None


class ThreadPoolManager:
    """线程池管理器"""
    
    def __init__(self):
        self.pools: Dict[PoolType, ThreadPoolExecutor] = {}
        self.stats: Dict[PoolType, PoolStats] = {}
        self.configs: Dict[PoolType, PoolConfig] = {}
        self._lock = threading.Lock()
        self._futures: Dict[str, Future] = {}
        self._init_default_pools()
    
    def _init_default_pools(self):
        """初始化默认线程池"""
        default_configs = {
            PoolType.IO_BOUND: PoolConfig(
                max_workers=20,
                thread_name_prefix="GatewayIO",
                queue_size=2000
            ),
            PoolType.CPU_BOUND: PoolConfig(
                max_workers=4,
                thread_name_prefix="GatewayCPU",
                queue_size=500
            ),
            PoolType.PROXY: PoolConfig(
                max_workers=50,
                thread_name_prefix="GatewayProxy",
                queue_size=5000
            ),
            PoolType.HEALTH_CHECK: PoolConfig(
                max_workers=5,
                thread_name_prefix="GatewayHealth",
                queue_size=100
            )
        }
        
        for pool_type, config in default_configs.items():
            self.create_pool(pool_type, config)
    
    def create_pool(self, pool_type: PoolType, config: PoolConfig):
        """创建线程池"""
        with self._lock:
            if pool_type in self.pools:
                logger.warning(f"线程池 {pool_type} 已存在，将关闭现有池")
                self.shutdown_pool(pool_type)
            
            # 创建线程池
            pool = ThreadPoolExecutor(
                max_workers=config.max_workers,
                thread_name_prefix=config.thread_name_prefix
            )
            
            self.pools[pool_type] = pool
            self.configs[pool_type] = config
            self.stats[pool_type] = PoolStats(
                pool_type=pool_type,
                max_workers=config.max_workers
            )
            
            logger.info(f"创建线程池 {pool_type}，最大工作线程数: {config.max_workers}")
    
    def submit_task(
        self,
        pool_type: PoolType,
        func: Callable,
        *args,
        task_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """提交任务到指定线程池"""
        if pool_type not in self.pools:
            raise ValueError(f"线程池 {pool_type} 不存在")
        
        pool = self.pools[pool_type]
        stats = self.stats[pool_type]
        
        # 生成任务ID
        if task_id is None:
            task_id = f"{pool_type}_{int(time.time() * 1000000)}"
        
        try:
            # 提交任务
            future = pool.submit(func, *args, **kwargs)
            
            # 记录Future
            with self._lock:
                self._futures[task_id] = future
                stats.total_submitted += 1
                stats.pending_tasks += 1
                stats.last_activity = datetime.now()
            
            # 添加完成回调
            future.add_done_callback(lambda f: self._task_completed_callback(task_id, pool_type, f))
            
            logger.debug(f"任务 {task_id} 已提交到线程池 {pool_type}")
            return task_id
            
        except Exception as e:
            logger.error(f"提交任务到线程池 {pool_type} 失败: {str(e)}")
            with self._lock:
                stats.failed_tasks += 1
            raise
    
    def _task_completed_callback(self, task_id: str, pool_type: PoolType, future: Future):
        """任务完成回调"""
        stats = self.stats[pool_type]
        
        with self._lock:
            # 移除Future记录
            self._futures.pop(task_id, None)
            
            # 更新统计
            stats.pending_tasks = max(0, stats.pending_tasks - 1)
            
            if future.exception() is None:
                stats.completed_tasks += 1
                logger.debug(f"任务 {task_id} 在线程池 {pool_type} 中执行成功")
            else:
                stats.failed_tasks += 1
                logger.warning(f"任务 {task_id} 在线程池 {pool_type} 中执行失败: {future.exception()}")
    
    def get_pool_stats(self, pool_type: PoolType) -> Optional[Dict[str, Any]]:
        """获取指定线程池的统计信息"""
        if pool_type not in self.pools:
            return None
        
        pool = self.pools[pool_type]
        stats = self.stats[pool_type]
        
        with self._lock:
            # 获取线程池内部信息
            try:
                active_threads = pool._threads if hasattr(pool, '_threads') else 0
                if hasattr(active_threads, '__len__'):
                    active_threads = len(active_threads)
                else:
                    active_threads = 0
            except:
                active_threads = 0
            
            stats.active_threads = active_threads
            
            return {
                "pool_type": stats.pool_type.value,
                "max_workers": stats.max_workers,
                "active_threads": stats.active_threads,
                "pending_tasks": stats.pending_tasks,
                "completed_tasks": stats.completed_tasks,
                "failed_tasks": stats.failed_tasks,
                "total_submitted": stats.total_submitted,
                "success_rate": (
                    stats.completed_tasks / stats.total_submitted * 100
                    if stats.total_submitted > 0 else 0
                ),
                "created_at": stats.created_at.isoformat(),
                "last_activity": stats.last_activity.isoformat() if stats.last_activity else None,
                "queue_utilization": (
                    stats.pending_tasks / self.configs[pool_type].queue_size * 100
                    if pool_type in self.configs else 0
                )
            }
    
    def get_all_stats(self) -> Dict[str, Any]:
        """获取所有线程池的统计信息"""
        all_stats = {}
        total_stats = {
            "total_pools": len(self.pools),
            "total_threads": 0,
            "total_pending": 0,
            "total_completed": 0,
            "total_failed": 0,
            "total_submitted": 0
        }
        
        for pool_type in self.pools.keys():
            pool_stats = self.get_pool_stats(pool_type)
            if pool_stats:
                all_stats[pool_type.value] = pool_stats
                
                # 累计总统计
                total_stats["total_threads"] += pool_stats["active_threads"]
                total_stats["total_pending"] += pool_stats["pending_tasks"]
                total_stats["total_completed"] += pool_stats["completed_tasks"]
                total_stats["total_failed"] += pool_stats["failed_tasks"]
                total_stats["total_submitted"] += pool_stats["total_submitted"]
        
        # 计算总成功率
        if total_stats["total_submitted"] > 0:
            total_stats["overall_success_rate"] = (
                total_stats["total_completed"] / total_stats["total_submitted"] * 100
            )
        else:
            total_stats["overall_success_rate"] = 0
        
        return {
            "pools": all_stats,
            "summary": total_stats,
            "timestamp": datetime.now().isoformat()
        }
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        with self._lock:
            future = self._futures.get(task_id)
            if future and not future.done():
                success = future.cancel()
                if success:
                    self._futures.pop(task_id, None)
                    logger.info(f"任务 {task_id} 已取消")
                return success
            return False
    
    def get_task_status(self, task_id: str) -> Optional[str]:
        """获取任务状态"""
        with self._lock:
            future = self._futures.get(task_id)
            if future:
                if future.done():
                    if future.cancelled():
                        return "cancelled"
                    elif future.exception():
                        return "failed"
                    else:
                        return "completed"
                else:
                    return "running"
            return None
    
    def shutdown_pool(self, pool_type: PoolType, wait: bool = True, timeout: float = 30.0):
        """关闭指定线程池"""
        with self._lock:
            if pool_type in self.pools:
                pool = self.pools[pool_type]
                logger.info(f"正在关闭线程池 {pool_type}")
                
                pool.shutdown(wait=wait)
                if wait:
                    # 等待所有任务完成，但有超时限制
                    try:
                        if hasattr(pool, '_shutdown_lock'):
                            # 这是一个简单的超时等待实现
                            start_time = time.time()
                            while not pool._shutdown and (time.time() - start_time) < timeout:
                                time.sleep(0.1)
                    except:
                        pass
                
                del self.pools[pool_type]
                del self.stats[pool_type]
                del self.configs[pool_type]
                
                # 清理相关的Future记录
                futures_to_remove = [
                    tid for tid, future in self._futures.items()
                    if tid.startswith(f"{pool_type}_")
                ]
                for tid in futures_to_remove:
                    self._futures.pop(tid, None)
                
                logger.info(f"线程池 {pool_type} 已关闭")
    
    def shutdown_all(self, wait: bool = True, timeout: float = 30.0):
        """关闭所有线程池"""
        logger.info("正在关闭所有线程池...")
        
        pool_types = list(self.pools.keys())
        for pool_type in pool_types:
            try:
                self.shutdown_pool(pool_type, wait=False)
            except Exception as e:
                logger.error(f"关闭线程池 {pool_type} 时出错: {str(e)}")
        
        if wait:
            # 等待所有线程池关闭
            start_time = time.time()
            while self.pools and (time.time() - start_time) < timeout:
                time.sleep(0.1)
        
        with self._lock:
            self._futures.clear()
        
        logger.info("所有线程池已关闭")
    
    def resize_pool(self, pool_type: PoolType, new_max_workers: int):
        """调整线程池大小"""
        if pool_type not in self.pools:
            raise ValueError(f"线程池 {pool_type} 不存在")
        
        config = self.configs[pool_type]
        old_max_workers = config.max_workers
        
        # 更新配置
        config.max_workers = new_max_workers
        
        # 重新创建线程池（ThreadPoolExecutor不支持动态调整大小）
        self.create_pool(pool_type, config)
        
        logger.info(f"线程池 {pool_type} 大小从 {old_max_workers} 调整为 {new_max_workers}")
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        health_status = {
            "healthy": True,
            "pools": {},
            "issues": []
        }
        
        for pool_type in self.pools.keys():
            pool_stats = self.get_pool_stats(pool_type)
            if pool_stats:
                pool_health = {
                    "healthy": True,
                    "issues": []
                }
                
                # 检查队列利用率
                queue_util = pool_stats.get("queue_utilization", 0)
                if queue_util > 90:
                    pool_health["healthy"] = False
                    pool_health["issues"].append(f"队列利用率过高: {queue_util:.1f}%")
                
                # 检查成功率
                success_rate = pool_stats.get("success_rate", 0)
                if success_rate < 95 and pool_stats["total_submitted"] > 10:
                    pool_health["healthy"] = False
                    pool_health["issues"].append(f"成功率过低: {success_rate:.1f}%")
                
                # 检查是否有任务积压
                if pool_stats["pending_tasks"] > pool_stats["max_workers"] * 2:
                    pool_health["healthy"] = False
                    pool_health["issues"].append(f"任务积压严重: {pool_stats['pending_tasks']} 个待处理任务")
                
                health_status["pools"][pool_type.value] = pool_health
                
                if not pool_health["healthy"]:
                    health_status["healthy"] = False
                    health_status["issues"].extend([
                        f"{pool_type.value}: {issue}" for issue in pool_health["issues"]
                    ])
        
        return health_status


# 全局线程池管理器实例
thread_pool_manager = ThreadPoolManager()


def get_thread_pool_manager() -> ThreadPoolManager:
    """获取全局线程池管理器"""
    return thread_pool_manager


# 便捷的任务提交函数
def submit_io_task(func: Callable, *args, **kwargs) -> str:
    """提交IO密集型任务"""
    return thread_pool_manager.submit_task(PoolType.IO_BOUND, func, *args, **kwargs)


def submit_cpu_task(func: Callable, *args, **kwargs) -> str:
    """提交CPU密集型任务"""
    return thread_pool_manager.submit_task(PoolType.CPU_BOUND, func, *args, **kwargs)


def submit_proxy_task(func: Callable, *args, **kwargs) -> str:
    """提交代理任务"""
    return thread_pool_manager.submit_task(PoolType.PROXY, func, *args, **kwargs)


def submit_health_check_task(func: Callable, *args, **kwargs) -> str:
    """提交健康检查任务"""
    return thread_pool_manager.submit_task(PoolType.HEALTH_CHECK, func, *args, **kwargs) 