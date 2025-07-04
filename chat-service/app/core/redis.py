"""
Chat Service Redis连接管理
"""

import json
import redis
from typing import Optional, Any, Dict
from app.core.config import settings

# Redis连接池
redis_pool = redis.ConnectionPool.from_url(
    settings.redis_url,
    password=settings.redis_password,
    db=settings.redis_db,
    decode_responses=True
)

# Redis客户端
redis_client = redis.Redis(connection_pool=redis_pool)


class RedisManager:
    """Redis管理器"""
    
    def __init__(self):
        self.client = redis_client
    
    def get(self, key: str) -> Optional[str]:
        """获取键值"""
        try:
            return self.client.get(key)
        except Exception:
            return None
    
    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """设置键值"""
        try:
            return self.client.set(key, value, ex=ex)
        except Exception:
            return False
    
    def delete(self, *keys: str) -> int:
        """删除键"""
        try:
            return self.client.delete(*keys)
        except Exception:
            return 0
    
    def exists(self, *keys: str) -> int:
        """检查键是否存在"""
        try:
            return self.client.exists(*keys)
        except Exception:
            return 0
    
    def expire(self, key: str, time: int) -> bool:
        """设置过期时间"""
        try:
            return self.client.expire(key, time)
        except Exception:
            return False
    
    def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        """获取JSON值"""
        data = self.get(key)
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return None
        return None
    
    def set_json(self, key: str, value: Dict[str, Any], ex: Optional[int] = None) -> bool:
        """设置JSON值"""
        try:
            json_str = json.dumps(value, ensure_ascii=False)
            return self.set(key, json_str, ex=ex)
        except Exception:
            return False
    
    def ping(self) -> bool:
        """检查连接"""
        try:
            return self.client.ping()
        except Exception:
            return False


# 全局Redis管理器实例
redis_manager = RedisManager()


def get_redis() -> RedisManager:
    """获取Redis管理器实例"""
    return redis_manager


# 会话相关的Redis操作
class SessionStore:
    """会话存储"""
    
    def __init__(self, redis_manager: RedisManager):
        self.redis = redis_manager
        self.prefix = "chat_session:"
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话数据"""
        key = f"{self.prefix}{session_id}"
        return self.redis.get_json(key)
    
    def set_session(self, session_id: str, session_data: Dict[str, Any], ttl: int = 86400) -> bool:
        """设置会话数据"""
        key = f"{self.prefix}{session_id}"
        return self.redis.set_json(key, session_data, ex=ttl)
    
    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        key = f"{self.prefix}{session_id}"
        return self.redis.delete(key) > 0
    
    def extend_session(self, session_id: str, ttl: int = 86400) -> bool:
        """延长会话有效期"""
        key = f"{self.prefix}{session_id}"
        return self.redis.expire(key, ttl)


# 全局会话存储实例
session_store = SessionStore(redis_manager) 