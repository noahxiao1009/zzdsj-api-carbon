"""
数据库服务仓库模块
包含所有数据访问仓库的定义
"""

from .base import BaseRepository
from .user_repository import UserRepository, RoleRepository, PermissionRepository
from .assistant_repository import AssistantRepository, ConversationRepository, MessageRepository
from .knowledge_repository import KnowledgeBaseRepository, DocumentRepository, DocumentChunkRepository
from .agent_repository import AgentDefinitionRepository, AgentTemplateRepository, AgentRunRepository
from .tool_repository import ToolRepository, ToolConfigurationRepository, ToolExecutionRepository
from .system_repository import SystemConfigRepository, ModelProviderRepository, FrameworkConfigRepository

__all__ = [
    # 基础仓库
    "BaseRepository",
    
    # 用户相关仓库
    "UserRepository",
    "RoleRepository", 
    "PermissionRepository",
    
    # 助手相关仓库
    "AssistantRepository",
    "ConversationRepository",
    "MessageRepository",
    
    # 知识库相关仓库
    "KnowledgeBaseRepository",
    "DocumentRepository",
    "DocumentChunkRepository",
    
    # 智能体相关仓库
    "AgentDefinitionRepository",
    "AgentTemplateRepository",
    "AgentRunRepository",
    
    # 工具相关仓库
    "ToolRepository",
    "ToolConfigurationRepository",
    "ToolExecutionRepository",
    
    # 系统配置相关仓库
    "SystemConfigRepository",
    "ModelProviderRepository",
    "FrameworkConfigRepository",
]