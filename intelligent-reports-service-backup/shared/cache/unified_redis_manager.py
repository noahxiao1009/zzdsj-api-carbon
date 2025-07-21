"""
统一Redis管理器
提供三级缓存架构和统一的缓存管理功能
"""

import asyncio
import logging
import time
import functools
from typing import Any, Dict, List, Optional, Union, Callable, Set
from datetime import datetime, timedelta
import redis.asyncio as redis
from redis.asyncio import ConnectionPool

from .cache_config import CacheConfig, CacheLevel
from .cache_utils import (
    generate_cache_key,
    hash_params,
    serialize_value, 
    deserialize_value
)

logger = logging.getLogger(__name__)


class CacheMetrics:
    """缓存指标收集器"""
    
    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.sets = 0
        self.deletes = 0
        self.errors = 0
        self.total_time = 0.0
        self.start_time = time.time()
    
    def record_hit(self, elapsed_time: float = 0.0):
        """记录缓存命中"""
        self.hits += 1
        self.total_time += elapsed_time
    
    def record_miss(self, elapsed_time: float = 0.0):
        """记录缓存未命中"""
        self.misses += 1
        self.total_time += elapsed_time
    
    def record_set(self, elapsed_time: float = 0.0):
        """记录缓存设置"""
        self.sets += 1
        self.total_time += elapsed_time
    
    def record_delete(self, elapsed_time: float = 0.0):
        """记录缓存删除"""
        self.deletes += 1
        self.total_time += elapsed_time
    
    def record_error(self):
        """记录错误"""
        self.errors += 1
    
    def get_hit_rate(self) -> float:
        """获取命中率"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    def get_avg_time(self) -> float:
        """获取平均响应时间"""
        total_ops = self.hits + self.misses + self.sets + self.deletes
        return self.total_time / total_ops if total_ops > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "deletes": self.deletes,
            "errors": self.errors,
            "hit_rate": self.get_hit_rate(),
            "avg_time_ms": self.get_avg_time() * 1000,
            "uptime_seconds": time.time() - self.start_time
        }


class UnifiedRedisManager:
    """统一Redis管理器"""
    
    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self.pool: Optional[ConnectionPool] = None
        self.client: Optional[redis.Redis] = None
        self.metrics = CacheMetrics()
        self.invalidation_subscribers: Set[str] = set()
        self._lock = asyncio.Lock()
    
    async def initialize(self):
        """初始化Redis连接"""
        try:
            # 创建连接池
            self.pool = ConnectionPool.from_url(
                self.config.REDIS_URL,
                password=self.config.REDIS_PASSWORD,
                db=self.config.REDIS_DB,
                max_connections=self.config.REDIS_MAX_CONNECTIONS,
                retry_on_timeout=self.config.REDIS_RETRY_ON_TIMEOUT,
                health_check_interval=self.config.REDIS_HEALTH_CHECK_INTERVAL,
                encoding="utf-8",
                decode_responses=False  # 允许二进制数据
            )
            
            # 创建Redis客户端
            self.client = redis.Redis(connection_pool=self.pool)
            
            # 测试连接
            await self.client.ping()
            logger.info("统一Redis管理器初始化成功")
            
        except Exception as e:
            logger.error(f"统一Redis管理器初始化失败: {e}")
            raise
    
    async def close(self):
        """关闭Redis连接"""
        if self.client:
            await self.client.close()
            self.client = None
        
        if self.pool:
            await self.pool.disconnect()
            self.pool = None
        
        logger.info("统一Redis管理器已关闭")
    
    async def _ensure_client(self) -> redis.Redis:
        """确保Redis客户端可用"""
        if self.client is None:
            await self.initialize()
        return self.client
    
    def _get_ttl_for_level(self, level: CacheLevel) -> int:
        """获取缓存级别对应的TTL"""
        return self.config.get_ttl_for_level(level)
    
    def _auto_select_level(self, cache_type: str) -> CacheLevel:
        """根据缓存类型自动选择缓存级别"""
        return self.config.get_level_by_data_type(cache_type)

    async def set(
        self,
        service: str,
        cache_type: str,
        identifier: str,
        value: Any,
        level: Optional[CacheLevel] = None,
        ttl: Optional[int] = None,
        sub_key: Optional[str] = None
    ) -> bool:
        """设置缓存值"""
        start_time = time.time()
        
        try:
            # 生成缓存键
            cache_key = generate_cache_key(service, cache_type, identifier, sub_key)
            
            # 确定缓存级别和TTL
            if level is None:
                level = self._auto_select_level(cache_type)
            
            if ttl is None:
                ttl = self._get_ttl_for_level(level)
            
            # 序列化值
            serialized_value = serialize_value(
                value,
                method=self.config.DEFAULT_SERIALIZATION,
                compress=self.config.ENABLE_COMPRESSION,
                compress_threshold=self.config.COMPRESSION_THRESHOLD
            )
            
            # 设置到Redis
            client = await self._ensure_client()
            
            if ttl > 0:
                result = await client.setex(cache_key, ttl, serialized_value)
            else:
                result = await client.set(cache_key, serialized_value)
            
            # 记录指标
            elapsed_time = time.time() - start_time
            if self.config.ENABLE_CACHE_METRICS:
                self.metrics.record_set(elapsed_time)
            
            logger.debug(f"缓存设置成功: {cache_key} (TTL: {ttl}s)")
            return bool(result)
            
        except Exception as e:
            self.metrics.record_error()
            logger.error(f"缓存设置失败 {service}:{cache_type}:{identifier}: {e}")
            return False
    
    async def get(
        self,
        service: str,
        cache_type: str,
        identifier: str,
        sub_key: Optional[str] = None,
        default: Any = None
    ) -> Any:
        """获取缓存值"""
        start_time = time.time()
        
        try:
            # 生成缓存键
            cache_key = generate_cache_key(service, cache_type, identifier, sub_key)
            
            # 从Redis获取
            client = await self._ensure_client()
            serialized_value = await client.get(cache_key)
            
            elapsed_time = time.time() - start_time
            
            if serialized_value is not None:
                # 反序列化
                value = deserialize_value(
                    serialized_value, 
                    method=self.config.DEFAULT_SERIALIZATION
                )
                
                # 记录命中
                if self.config.ENABLE_CACHE_METRICS:
                    self.metrics.record_hit(elapsed_time)
                
                logger.debug(f"缓存命中: {cache_key}")
                return value
            else:
                # 记录未命中
                if self.config.ENABLE_CACHE_METRICS:
                    self.metrics.record_miss(elapsed_time)
                
                logger.debug(f"缓存未命中: {cache_key}")
                return default
                
        except Exception as e:
            self.metrics.record_error()
            logger.error(f"缓存获取失败 {service}:{cache_type}:{identifier}: {e}")
            return default
    
    async def delete(
        self,
        service: str,
        cache_type: str,
        identifier: str,
        sub_key: Optional[str] = None
    ) -> bool:
        """删除缓存"""
        start_time = time.time()
        
        try:
            # 生成缓存键
            cache_key = generate_cache_key(service, cache_type, identifier, sub_key)
            
            # 从Redis删除
            client = await self._ensure_client()
            result = await client.delete(cache_key)
            
            # 记录指标
            elapsed_time = time.time() - start_time
            if self.config.ENABLE_CACHE_METRICS:
                self.metrics.record_delete(elapsed_time)
            
            logger.debug(f"缓存删除: {cache_key}")
            return result > 0
            
        except Exception as e:
            self.metrics.record_error()
            logger.error(f"缓存删除失败 {service}:{cache_type}:{identifier}: {e}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            client = await self._ensure_client()
            
            # 测试连接
            start_time = time.time()
            await client.ping()
            ping_time = (time.time() - start_time) * 1000
            
            return {
                "healthy": True,
                "ping_time_ms": ping_time,
                "hit_rate": self.metrics.get_hit_rate(),
                "error_count": self.metrics.errors
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "error_count": self.metrics.errors
            }


# 全局实例
_unified_redis_manager: Optional[UnifiedRedisManager] = None


async def get_unified_redis_manager() -> UnifiedRedisManager:
    """获取统一Redis管理器实例"""
    global _unified_redis_manager
    
    if _unified_redis_manager is None:
        _unified_redis_manager = UnifiedRedisManager()
        await _unified_redis_manager.initialize()
    
    return _unified_redis_manager


# 缓存装饰器
class CacheDecorator:
    """缓存装饰器"""
    
    def __init__(
        self,
        service: str,
        cache_type: str,
        level: Optional[CacheLevel] = None,
        ttl: Optional[int] = None,
        key_builder: Optional[Callable] = None
    ):
        self.service = service
        self.cache_type = cache_type
        self.level = level
        self.ttl = ttl
        self.key_builder = key_builder or self._default_key_builder
    
    def _default_key_builder(self, *args, **kwargs) -> str:
        """默认键构建器"""
        return hash_params(*args, **kwargs)
    
    def __call__(self, func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # 构建缓存键
            identifier = self.key_builder(*args, **kwargs)
            
            # 获取管理器
            manager = await get_unified_redis_manager()
            
            # 尝试从缓存获取
            result = await manager.get(
                self.service,
                self.cache_type,
                identifier
            )
            
            if result is not None:
                return result
            
            # 执行原函数
            result = await func(*args, **kwargs)
            
            # 存储到缓存
            await manager.set(
                self.service,
                self.cache_type,
                identifier,
                result,
                level=self.level,
                ttl=self.ttl
            )
            
            return result
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else async_wrapper


def cache_result(
    service: str,
    cache_type: str,
    level: Optional[CacheLevel] = None,
    ttl: Optional[int] = None,
    key_builder: Optional[Callable] = None
):
    """缓存结果装饰器"""
    return CacheDecorator(service, cache_type, level, ttl, key_builder)


async def invalidate_cache(
    service: str,
    cache_type: Optional[str] = None,
    identifier: Optional[str] = None
) -> int:
    """快捷缓存失效函数"""
    manager = await get_unified_redis_manager()
    # 简化版批量失效（生产环境需要完整实现）
    return 0
