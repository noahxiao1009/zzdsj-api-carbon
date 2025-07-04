"""
MCP Service Redis连接管理
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


class MCPRedisManager:
    """MCP Redis管理器"""
    
    def __init__(self):
        self.key_prefix = "mcp:service:"
        
    async def _get_client(self) -> redis.Redis:
        """获取Redis客户端"""
        return await get_redis()
    
    def _make_key(self, key: str) -> str:
        """生成带前缀的键名"""
        return f"{self.key_prefix}{key}"
    
    async def set_service_config(self, service_id: str, config: Dict[str, Any], ttl: int = 3600) -> bool:
        """存储MCP服务配置"""
        try:
            client = await self._get_client()
            key = self._make_key(f"config:{service_id}")
            value = json.dumps(config, ensure_ascii=False)
            
            if ttl > 0:
                return await client.setex(key, ttl, value)
            else:
                return await client.set(key, value)
        except Exception as e:
            logger.error(f"设置服务配置失败 {service_id}: {e}")
            return False
    
    async def get_service_config(self, service_id: str) -> Optional[Dict[str, Any]]:
        """获取MCP服务配置"""
        try:
            client = await self._get_client()
            key = self._make_key(f"config:{service_id}")
            value = await client.get(key)
            
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"获取服务配置失败 {service_id}: {e}")
            return None
    
    async def delete_service_config(self, service_id: str) -> bool:
        """删除MCP服务配置"""
        try:
            client = await self._get_client()
            key = self._make_key(f"config:{service_id}")
            result = await client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"删除服务配置失败 {service_id}: {e}")
            return False
    
    async def set_service_status(self, service_id: str, status: str, ttl: int = 300) -> bool:
        """设置MCP服务状态"""
        try:
            client = await self._get_client()
            key = self._make_key(f"status:{service_id}")
            
            if ttl > 0:
                return await client.setex(key, ttl, status)
            else:
                return await client.set(key, status)
        except Exception as e:
            logger.error(f"设置服务状态失败 {service_id}: {e}")
            return False
    
    async def get_service_status(self, service_id: str) -> Optional[str]:
        """获取MCP服务状态"""
        try:
            client = await self._get_client()
            key = self._make_key(f"status:{service_id}")
            return await client.get(key)
        except Exception as e:
            logger.error(f"获取服务状态失败 {service_id}: {e}")
            return None
    
    async def list_services(self, pattern: str = "*") -> List[str]:
        """列出所有MCP服务"""
        try:
            client = await self._get_client()
            key_pattern = self._make_key(f"config:{pattern}")
            keys = await client.keys(key_pattern)
            
            # 提取服务ID
            service_ids = []
            prefix_len = len(self._make_key("config:"))
            for key in keys:
                service_id = key[prefix_len:]
                service_ids.append(service_id)
            
            return service_ids
        except Exception as e:
            logger.error(f"列出服务失败: {e}")
            return []
    
    async def cache_tool_result(self, tool_name: str, params_hash: str, result: Any, ttl: int = 1800) -> bool:
        """缓存工具执行结果"""
        try:
            client = await self._get_client()
            key = self._make_key(f"tool_cache:{tool_name}:{params_hash}")
            value = pickle.dumps(result)
            
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
            key = self._make_key(f"tool_cache:{tool_name}:{params_hash}")
            value = await client.get(key)
            
            if value:
                return pickle.loads(value)
            return None
        except Exception as e:
            logger.error(f"获取缓存工具结果失败 {tool_name}: {e}")
            return None
    
    async def increment_call_counter(self, service_id: str, tool_name: str) -> int:
        """增加工具调用计数"""
        try:
            client = await self._get_client()
            key = self._make_key(f"stats:{service_id}:{tool_name}")
            return await client.incr(key)
        except Exception as e:
            logger.error(f"增加调用计数失败 {service_id}:{tool_name}: {e}")
            return 0
    
    async def get_call_stats(self, service_id: str, tool_name: Optional[str] = None) -> Dict[str, int]:
        """获取调用统计"""
        try:
            client = await self._get_client()
            if tool_name:
                key = self._make_key(f"stats:{service_id}:{tool_name}")
                count = await client.get(key)
                return {tool_name: int(count) if count else 0}
            else:
                key_pattern = self._make_key(f"stats:{service_id}:*")
                keys = await client.keys(key_pattern)
                
                stats = {}
                prefix_len = len(self._make_key(f"stats:{service_id}:"))
                for key in keys:
                    tool = key[prefix_len:]
                    count = await client.get(key)
                    stats[tool] = int(count) if count else 0
                
                return stats
        except Exception as e:
            logger.error(f"获取调用统计失败 {service_id}: {e}")
            return {}


# 创建全局Redis管理器实例
mcp_redis_manager = MCPRedisManager()


# 导出
__all__ = [
    "init_redis",
    "get_redis", 
    "close_redis",
    "check_redis_health",
    "get_redis_info",
    "MCPRedisManager",
    "mcp_redis_manager"
] 