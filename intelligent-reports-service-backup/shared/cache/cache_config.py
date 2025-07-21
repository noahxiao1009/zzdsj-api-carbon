"""
缓存配置管理
定义三级TTL策略和缓存相关配置
"""

from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass


class CacheLevel(str, Enum):
    """缓存级别枚举"""
    L1_APPLICATION = "L1"  # 应用层缓存 - 5分钟，热点数据
    L2_SERVICE = "L2"      # 服务层缓存 - 30分钟，业务数据
    L3_PERSISTENT = "L3"   # 持久层缓存 - 2小时，配置数据


@dataclass
class CacheConfig:
    """缓存配置类"""
    
    # 三级TTL策略 (秒)
    L1_CACHE_TTL: int = 300      # 5分钟 - 应用层缓存
    L2_CACHE_TTL: int = 1800     # 30分钟 - 服务层缓存  
    L3_CACHE_TTL: int = 7200     # 2小时 - 持久层缓存
    
    # Redis连接配置
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    REDIS_MAX_CONNECTIONS: int = 10
    REDIS_RETRY_ON_TIMEOUT: bool = True
    REDIS_HEALTH_CHECK_INTERVAL: int = 30
    
    # 键命名配置
    KEY_SEPARATOR: str = ":"
    KEY_PREFIX: str = "unified"
    
    # 缓存策略配置
    DEFAULT_SERIALIZATION: str = "json"  # json, pickle, msgpack
    ENABLE_COMPRESSION: bool = False
    COMPRESSION_THRESHOLD: int = 1024    # 大于1KB启用压缩
    
    # 失效策略配置
    ENABLE_CACHE_INVALIDATION: bool = True
    INVALIDATION_PATTERN_PREFIX: str = "invalidate"
    BATCH_INVALIDATION_SIZE: int = 100
    
    # 监控配置
    ENABLE_CACHE_METRICS: bool = True
    METRICS_SAMPLE_RATE: float = 0.1     # 10%采样率
    
    @classmethod
    def get_ttl_for_level(cls, level: CacheLevel) -> int:
        """根据缓存级别获取TTL"""
        ttl_mapping = {
            CacheLevel.L1_APPLICATION: cls.L1_CACHE_TTL,
            CacheLevel.L2_SERVICE: cls.L2_CACHE_TTL,
            CacheLevel.L3_PERSISTENT: cls.L3_CACHE_TTL
        }
        return ttl_mapping.get(level, cls.L2_CACHE_TTL)
    
    @classmethod
    def get_level_by_data_type(cls, data_type: str) -> CacheLevel:
        """根据数据类型自动选择缓存级别"""
        level_mapping = {
            # L1 - 应用层缓存 (5分钟)
            "search_result": CacheLevel.L1_APPLICATION,
            "api_response": CacheLevel.L1_APPLICATION,
            "user_session": CacheLevel.L1_APPLICATION,
            "chat_context": CacheLevel.L1_APPLICATION,
            
            # L2 - 服务层缓存 (30分钟)  
            "agent_config": CacheLevel.L2_SERVICE,
            "knowledge_base": CacheLevel.L2_SERVICE,
            "document_chunk": CacheLevel.L2_SERVICE,
            "tool_result": CacheLevel.L2_SERVICE,
            "model_response": CacheLevel.L2_SERVICE,
            
            # L3 - 持久层缓存 (2小时)
            "system_config": CacheLevel.L3_PERSISTENT,
            "user_profile": CacheLevel.L3_PERSISTENT,
            "service_config": CacheLevel.L3_PERSISTENT,
            "model_config": CacheLevel.L3_PERSISTENT,
            "permission": CacheLevel.L3_PERSISTENT
        }
        return level_mapping.get(data_type, CacheLevel.L2_SERVICE)


# 服务名称映射
SERVICE_NAME_MAPPING = {
    "agent-service": "agent",
    "knowledge-service": "knowledge", 
    "chat-service": "chat",
    "system-service": "system",
    "mcp-service": "mcp",
    "base-service": "base",
    "model-service": "model",
    "database-service": "database"
}


# 缓存类型定义
CACHE_TYPE_MAPPING = {
    # Agent相关
    "agent_config": "config",
    "agent_status": "status", 
    "agent_memory": "memory",
    "conversation": "conv",
    "message": "msg",
    
    # Knowledge相关
    "knowledge_base": "kb",
    "document": "doc",
    "document_chunk": "chunk",
    "search_result": "search",
    "embedding": "embed",
    
    # System相关
    "system_config": "config",
    "sensitive_words": "sensitive",
    "policy_search": "policy",
    "file_info": "file",
    "tool_result": "tool",
    
    # MCP相关
    "service_config": "config",
    "service_status": "status",
    "tool_cache": "tool",
    "call_stats": "stats",
    
    # User相关
    "user_session": "session",
    "user_profile": "profile",
    "permission": "perm",
    "auth_token": "token"
}
