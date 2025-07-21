"""
数据库服务模型模块
包含所有数据库模型的定义和基础配置
"""

from .database import Base, get_db_session
from .user import User, Role, Permission, UserSettings, ApiKey
from .assistant import Assistant, Conversation, Message, UserAgnoConfig, AgnoSession, AgnoToolExecution
from .knowledge import KnowledgeBase, Document, DocumentChunk, KnowledgeGraph
from .agent import AgentDefinition, AgentTemplate, AgentRun, AgentChain, AgentOrchestration
from .tool import Tool, ToolConfiguration, ToolExecution, UnifiedTool
from .system import SystemConfig, ModelProvider, FrameworkConfig
from .resource_permission import ResourcePermission, KnowledgeBaseAccess, AssistantAccess, ModelConfigAccess, MCPConfigAccess, UserResourceQuota

__all__ = [
    # 基础数据库
    "Base",
    "get_db_session",
    
    # 用户相关
    "User",
    "Role", 
    "Permission",
    "UserSettings",
    "ApiKey",
    
    # 助手相关
    "Assistant",
    "Conversation",
    "Message",
    "UserAgnoConfig",
    "AgnoSession",
    "AgnoToolExecution",
    
    # 知识库相关
    "KnowledgeBase",
    "Document",
    "DocumentChunk",
    "KnowledgeGraph",
    
    # 智能体相关
    "AgentDefinition",
    "AgentTemplate",
    "AgentRun",
    "AgentChain",
    "AgentOrchestration",
    
    # 工具相关
    "Tool",
    "ToolConfiguration",
    "ToolExecution",
    "UnifiedTool",
    
    # 系统配置相关
    "SystemConfig",
    "ModelProvider",
    "FrameworkConfig",
    
    # 资源权限相关
    "ResourcePermission",
    "KnowledgeBaseAccess",
    "AssistantAccess",
    "ModelConfigAccess",
    "MCPConfigAccess",
    "UserResourceQuota",
]