"""
微服务Redis适配器
封装统一Redis管理器，为各微服务提供便捷的缓存接口
"""

from typing import Any, Dict, List, Optional, Union
from .unified_redis_manager import get_unified_redis_manager, CacheLevel
from .cache_utils import hash_params


class MCPServiceCacheAdapter:
    """MCP服务缓存适配器"""
    
    def __init__(self):
        self.service_name = "mcp-service"
    
    async def set_service_config(self, service_id: str, config: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """存储MCP服务配置"""
        manager = await get_unified_redis_manager()
        return await manager.set(
            self.service_name,
            "service_config",
            service_id,
            config,
            level=CacheLevel.L3_PERSISTENT,
            ttl=ttl
        )
    
    async def get_service_config(self, service_id: str) -> Optional[Dict[str, Any]]:
        """获取MCP服务配置"""
        manager = await get_unified_redis_manager()
        return await manager.get(
            self.service_name,
            "service_config", 
            service_id
        )
    
    async def set_service_status(self, service_id: str, status: str, ttl: Optional[int] = None) -> bool:
        """设置MCP服务状态"""
        manager = await get_unified_redis_manager()
        return await manager.set(
            self.service_name,
            "service_status",
            service_id,
            status,
            level=CacheLevel.L1_APPLICATION,
            ttl=ttl
        )
    
    async def get_service_status(self, service_id: str) -> Optional[str]:
        """获取MCP服务状态"""
        manager = await get_unified_redis_manager()
        return await manager.get(
            self.service_name,
            "service_status",
            service_id
        )


class SystemServiceCacheAdapter:
    """系统服务缓存适配器"""
    
    def __init__(self):
        self.service_name = "system-service"
    
    async def cache_sensitive_result(self, text_hash: str, result: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """缓存敏感词检测结果"""
        manager = await get_unified_redis_manager()
        return await manager.set(
            self.service_name,
            "sensitive_words",
            text_hash,
            result,
            level=CacheLevel.L2_SERVICE,
            ttl=ttl
        )
    
    async def get_cached_sensitive_result(self, text_hash: str) -> Optional[Dict[str, Any]]:
        """获取缓存的敏感词检测结果"""
        manager = await get_unified_redis_manager()
        return await manager.get(
            self.service_name,
            "sensitive_words",
            text_hash
        )
    
    async def cache_system_config(self, config_key: str, config_value: Any, ttl: Optional[int] = None) -> bool:
        """缓存系统配置"""
        manager = await get_unified_redis_manager()
        return await manager.set(
            self.service_name,
            "system_config",
            config_key,
            config_value,
            level=CacheLevel.L3_PERSISTENT,
            ttl=ttl
        )
    
    async def get_cached_system_config(self, config_key: str) -> Optional[Any]:
        """获取缓存的系统配置"""
        manager = await get_unified_redis_manager()
        return await manager.get(
            self.service_name,
            "system_config",
            config_key
        )


class ChatServiceCacheAdapter:
    """聊天服务缓存适配器"""
    
    def __init__(self):
        self.service_name = "chat-service"
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话数据"""
        manager = await get_unified_redis_manager()
        return await manager.get(
            self.service_name,
            "user_session",
            session_id
        )
    
    async def set_session(self, session_id: str, session_data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """设置会话数据"""
        manager = await get_unified_redis_manager()
        return await manager.set(
            self.service_name,
            "user_session",
            session_id,
            session_data,
            level=CacheLevel.L1_APPLICATION,
            ttl=ttl or 86400  # 默认24小时
        )


class AgentServiceCacheAdapter:
    """智能体服务缓存适配器"""
    
    def __init__(self):
        self.service_name = "agent-service"
    
    async def cache_agent_config(self, agent_id: str, config: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """缓存智能体配置"""
        manager = await get_unified_redis_manager()
        return await manager.set(
            self.service_name,
            "agent_config",
            agent_id,
            config,
            level=CacheLevel.L2_SERVICE,
            ttl=ttl
        )
    
    async def get_agent_config(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """获取智能体配置"""
        manager = await get_unified_redis_manager()
        return await manager.get(
            self.service_name,
            "agent_config",
            agent_id
        )


class KnowledgeServiceCacheAdapter:
    """知识库服务缓存适配器"""
    
    def __init__(self):
        self.service_name = "knowledge-service"
    
    async def cache_search_result(self, query_hash: str, results: List[Dict[str, Any]], ttl: Optional[int] = None) -> bool:
        """缓存搜索结果"""
        manager = await get_unified_redis_manager()
        return await manager.set(
            self.service_name,
            "search_result",
            query_hash,
            results,
            level=CacheLevel.L1_APPLICATION,
            ttl=ttl
        )
    
    async def get_search_result(self, query_hash: str) -> Optional[List[Dict[str, Any]]]:
        """获取搜索结果"""
        manager = await get_unified_redis_manager()
        return await manager.get(
            self.service_name,
            "search_result",
            query_hash
        )


# 适配器工厂函数
def get_mcp_cache_adapter() -> MCPServiceCacheAdapter:
    """获取MCP服务缓存适配器"""
    return MCPServiceCacheAdapter()


def get_system_cache_adapter() -> SystemServiceCacheAdapter:
    """获取系统服务缓存适配器"""
    return SystemServiceCacheAdapter()


def get_chat_cache_adapter() -> ChatServiceCacheAdapter:
    """获取聊天服务缓存适配器"""
    return ChatServiceCacheAdapter()


def get_agent_cache_adapter() -> AgentServiceCacheAdapter:
    """获取智能体服务缓存适配器"""
    return AgentServiceCacheAdapter()


def get_knowledge_cache_adapter() -> KnowledgeServiceCacheAdapter:
    """获取知识库服务缓存适配器"""
    return KnowledgeServiceCacheAdapter()
