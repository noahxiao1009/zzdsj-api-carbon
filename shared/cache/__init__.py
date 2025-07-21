"""
统一缓存管理模块
提供三级缓存架构和统一的Redis管理
"""

from .unified_redis_manager import (
    UnifiedRedisManager,
    CacheLevel,
    CacheDecorator,
    cache_result,
    invalidate_cache,
    get_unified_redis_manager
)
from .cache_config import CacheConfig
from .cache_utils import (
    generate_cache_key,
    hash_params,
    serialize_value,
    deserialize_value
)
from .adapters import (
    get_mcp_cache_adapter,
    get_system_cache_adapter, 
    get_chat_cache_adapter,
    get_agent_cache_adapter,
    get_knowledge_cache_adapter
)

__all__ = [
    'UnifiedRedisManager',
    'CacheLevel', 
    'CacheDecorator',
    'CacheConfig',
    'cache_result',
    'invalidate_cache',
    'get_unified_redis_manager',
    'generate_cache_key',
    'hash_params',
    'serialize_value',
    'deserialize_value',
    'get_mcp_cache_adapter',
    'get_system_cache_adapter',
    'get_chat_cache_adapter', 
    'get_agent_cache_adapter',
    'get_knowledge_cache_adapter'
]
