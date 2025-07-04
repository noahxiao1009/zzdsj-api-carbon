"""
System Service Redis连接管理
"""

import logging
import json
import pickle
from typing import Any, Optional, Dict, List, Union
import redis.asyncio as redis
from redis.asyncio import ConnectionPool

from app.core.config import settings

logger = logging.getLogger(__name__)

# Redis连接池
redis_pool: Optional[ConnectionPool] = None
redis_client: Optional[redis.Redis] = None


async def init_redis() -> None:
    """初始化Redis连接"""
    global redis_pool, redis_client
    
    try:
        # 创建连接池
        redis_pool = ConnectionPool.from_url(
            settings.redis_url,
            password=settings.redis_password,
            max_connections=settings.redis_max_connections,
            retry_on_timeout=True,
            health_check_interval=30,
            encoding="utf-8",
            decode_responses=True
        )
        
        # 创建Redis客户端
        redis_client = redis.Redis(connection_pool=redis_pool)
        
        # 测试连接
        await redis_client.ping()
        logger.info("Redis连接初始化成功")
        
    except Exception as e:
        logger.error(f"Redis连接初始化失败: {e}")
        raise


async def get_redis() -> redis.Redis:
    """获取Redis客户端"""
    if redis_client is None:
        await init_redis()
    return redis_client


async def close_redis() -> None:
    """关闭Redis连接"""
    global redis_pool, redis_client
    
    if redis_client:
        await redis_client.close()
        redis_client = None
    
    if redis_pool:
        await redis_pool.disconnect()
        redis_pool = None
    
    logger.info("Redis连接已关闭")


async def check_redis_health() -> bool:
    """检查Redis健康状态"""
    try:
        client = await get_redis()
        await client.ping()
        return True
    except Exception as e:
        logger.error(f"Redis健康检查失败: {e}")
        return False


async def get_redis_info() -> Dict[str, Any]:
    """获取Redis信息"""
    try:
        client = await get_redis()
        info = await client.info()
        
        return {
            "connected": True,
            "version": info.get("redis_version"),
            "memory_used": info.get("used_memory_human"),
            "connected_clients": info.get("connected_clients"),
            "total_commands_processed": info.get("total_commands_processed"),
            "keyspace": {k: v for k, v in info.items() if k.startswith("db")}
        }
    except Exception as e:
        logger.error(f"获取Redis信息失败: {e}")
        return {
            "connected": False,
            "error": str(e)
        }


class SystemRedisManager:
    """系统服务Redis管理器"""
    
    def __init__(self):
        self.key_prefix = "system:service:"
        
    async def _get_client(self) -> redis.Redis:
        """获取Redis客户端"""
        return await get_redis()
    
    def _make_key(self, key: str) -> str:
        """生成带前缀的键名"""
        return f"{self.key_prefix}{key}"
    
    # 敏感词缓存管理
    async def cache_sensitive_result(self, text_hash: str, result: Dict[str, Any], ttl: int = None) -> bool:
        """缓存敏感词检测结果"""
        try:
            client = await self._get_client()
            key = self._make_key(f"sensitive:{text_hash}")
            value = json.dumps(result, ensure_ascii=False)
            
            cache_ttl = ttl or settings.sensitive_words_cache_ttl
            if cache_ttl > 0:
                return await client.setex(key, cache_ttl, value)
            else:
                return await client.set(key, value)
        except Exception as e:
            logger.error(f"缓存敏感词结果失败 {text_hash}: {e}")
            return False
    
    async def get_cached_sensitive_result(self, text_hash: str) -> Optional[Dict[str, Any]]:
        """获取缓存的敏感词检测结果"""
        try:
            client = await self._get_client()
            key = self._make_key(f"sensitive:{text_hash}")
            value = await client.get(key)
            
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"获取缓存敏感词结果失败 {text_hash}: {e}")
            return None
    
    # 政策搜索缓存管理
    async def cache_policy_search(self, query_hash: str, results: List[Dict[str, Any]], ttl: int = None) -> bool:
        """缓存政策搜索结果"""
        try:
            client = await self._get_client()
            key = self._make_key(f"policy:{query_hash}")
            value = json.dumps(results, ensure_ascii=False)
            
            cache_ttl = ttl or settings.policy_search_cache_ttl
            if cache_ttl > 0:
                return await client.setex(key, cache_ttl, value)
            else:
                return await client.set(key, value)
        except Exception as e:
            logger.error(f"缓存政策搜索结果失败 {query_hash}: {e}")
            return False
    
    async def get_cached_policy_search(self, query_hash: str) -> Optional[List[Dict[str, Any]]]:
        """获取缓存的政策搜索结果"""
        try:
            client = await self._get_client()
            key = self._make_key(f"policy:{query_hash}")
            value = await client.get(key)
            
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"获取缓存政策搜索结果失败 {query_hash}: {e}")
            return None
    
    # 系统配置缓存管理
    async def cache_system_config(self, config_key: str, config_value: Any, ttl: int = None) -> bool:
        """缓存系统配置"""
        try:
            client = await self._get_client()
            key = self._make_key(f"config:{config_key}")
            value = json.dumps(config_value, ensure_ascii=False)
            
            cache_ttl = ttl or settings.system_config_cache_ttl
            if cache_ttl > 0:
                return await client.setex(key, cache_ttl, value)
            else:
                return await client.set(key, value)
        except Exception as e:
            logger.error(f"缓存系统配置失败 {config_key}: {e}")
            return False
    
    async def get_cached_system_config(self, config_key: str) -> Optional[Any]:
        """获取缓存的系统配置"""
        try:
            client = await self._get_client()
            key = self._make_key(f"config:{config_key}")
            value = await client.get(key)
            
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"获取缓存系统配置失败 {config_key}: {e}")
            return None
    
    async def delete_config_cache(self, config_key: str) -> bool:
        """删除配置缓存"""
        try:
            client = await self._get_client()
            key = self._make_key(f"config:{config_key}")
            result = await client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"删除配置缓存失败 {config_key}: {e}")
            return False
    
    # 文件上传缓存管理
    async def cache_file_info(self, file_id: str, file_info: Dict[str, Any], ttl: int = 3600) -> bool:
        """缓存文件信息"""
        try:
            client = await self._get_client()
            key = self._make_key(f"file:{file_id}")
            value = json.dumps(file_info, ensure_ascii=False)
            
            if ttl > 0:
                return await client.setex(key, ttl, value)
            else:
                return await client.set(key, value)
        except Exception as e:
            logger.error(f"缓存文件信息失败 {file_id}: {e}")
            return False
    
    async def get_cached_file_info(self, file_id: str) -> Optional[Dict[str, Any]]:
        """获取缓存的文件信息"""
        try:
            client = await self._get_client()
            key = self._make_key(f"file:{file_id}")
            value = await client.get(key)
            
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"获取缓存文件信息失败 {file_id}: {e}")
            return None
    
    # 工具执行缓存管理
    async def cache_tool_result(self, tool_name: str, params_hash: str, result: Any, ttl: int = 1800) -> bool:
        """缓存工具执行结果"""
        try:
            client = await self._get_client()
            key = self._make_key(f"tool:{tool_name}:{params_hash}")
            value = json.dumps(result, ensure_ascii=False)
            
            if ttl > 0:
                return await client.setex(key, ttl, value)
            else:
                return await client.set(key, value)
        except Exception as e:
            logger.error(f"缓存工具结果失败 {tool_name}: {e}")
            return False
    
    async def get_cached_tool_result(self, tool_name: str, params_hash: str) -> Any:
        """获取缓存的工具执行结果"""
        try:
            client = await self._get_client()
            key = self._make_key(f"tool:{tool_name}:{params_hash}")
            value = await client.get(key)
            
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"获取缓存工具结果失败 {tool_name}: {e}")
            return None
    
    # 统计信息管理
    async def increment_counter(self, counter_name: str, amount: int = 1) -> int:
        """增加计数器"""
        try:
            client = await self._get_client()
            key = self._make_key(f"counter:{counter_name}")
            return await client.incrby(key, amount)
        except Exception as e:
            logger.error(f"增加计数器失败 {counter_name}: {e}")
            return 0
    
    async def get_counter(self, counter_name: str) -> int:
        """获取计数器值"""
        try:
            client = await self._get_client()
            key = self._make_key(f"counter:{counter_name}")
            value = await client.get(key)
            return int(value) if value else 0
        except Exception as e:
            logger.error(f"获取计数器失败 {counter_name}: {e}")
            return 0
    
    async def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        try:
            client = await self._get_client()
            pattern = self._make_key("counter:*")
            keys = await client.keys(pattern)
            
            stats = {}
            prefix_len = len(self._make_key("counter:"))
            
            for key in keys:
                counter_name = key[prefix_len:]
                value = await client.get(key)
                stats[counter_name] = int(value) if value else 0
            
            return stats
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}


# 创建全局Redis管理器实例
system_redis_manager = SystemRedisManager()


# 导出
__all__ = [
    "init_redis",
    "get_redis", 
    "close_redis",
    "check_redis_health",
    "get_redis_info",
    "SystemRedisManager",
    "system_redis_manager"
] 