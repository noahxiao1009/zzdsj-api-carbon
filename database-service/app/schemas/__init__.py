"""
数据库服务模式模块
包含所有Pydantic模式的定义，用于数据验证和序列化
"""

from .user import (
    UserCreate, UserUpdate, UserResponse, UserLogin,
    RoleCreate, RoleUpdate, RoleResponse,
    PermissionCreate, PermissionUpdate, PermissionResponse,
    UserSettingsCreate, UserSettingsUpdate, UserSettingsResponse,
    ApiKeyCreate, ApiKeyUpdate, ApiKeyResponse
)

from .assistant import (
    AssistantCreate, AssistantUpdate, AssistantResponse,
    ConversationCreate, ConversationUpdate, ConversationResponse,
    MessageCreate, MessageUpdate, MessageResponse,
    AgnoSessionCreate, AgnoSessionUpdate, AgnoSessionResponse
)

from .knowledge import (
    KnowledgeBaseCreate, KnowledgeBaseUpdate, KnowledgeBaseResponse,
    DocumentCreate, DocumentUpdate, DocumentResponse,
    DocumentChunkCreate, DocumentChunkUpdate, DocumentChunkResponse,
    KnowledgeGraphCreate, KnowledgeGraphUpdate, KnowledgeGraphResponse
)

from .agent import (
    AgentDefinitionCreate, AgentDefinitionUpdate, AgentDefinitionResponse,
    AgentTemplateCreate, AgentTemplateUpdate, AgentTemplateResponse,
    AgentRunCreate, AgentRunUpdate, AgentRunResponse,
    AgentChainCreate, AgentChainUpdate, AgentChainResponse,
    AgentOrchestrationCreate, AgentOrchestrationUpdate, AgentOrchestrationResponse
)

from .tool import (
    ToolCreate, ToolUpdate, ToolResponse,
    ToolConfigurationCreate, ToolConfigurationUpdate, ToolConfigurationResponse,
    ToolExecutionCreate, ToolExecutionUpdate, ToolExecutionResponse,
    UnifiedToolCreate, UnifiedToolUpdate, UnifiedToolResponse
)

from .system import (
    SystemConfigCreate, SystemConfigUpdate, SystemConfigResponse,
    ModelProviderCreate, ModelProviderUpdate, ModelProviderResponse,
    FrameworkConfigCreate, FrameworkConfigUpdate, FrameworkConfigResponse,
    ServiceRegistryCreate, ServiceRegistryUpdate, ServiceRegistryResponse
)

from .resource_permission import (
    ResourcePermissionCreate, ResourcePermissionUpdate, ResourcePermissionResponse,
    KnowledgeBaseAccessCreate, KnowledgeBaseAccessUpdate, KnowledgeBaseAccessResponse,
    AssistantAccessCreate, AssistantAccessUpdate, AssistantAccessResponse,
    ModelConfigAccessCreate, ModelConfigAccessUpdate, ModelConfigAccessResponse,
    MCPConfigAccessCreate, MCPConfigAccessUpdate, MCPConfigAccessResponse,
    UserResourceQuotaCreate, UserResourceQuotaUpdate, UserResourceQuotaResponse
)

from .common import (
    PaginationParams, PaginationResponse,
    BaseResponse, ErrorResponse,
    HealthCheckResponse, StatusResponse
)

__all__ = [
    # 用户相关
    "UserCreate", "UserUpdate", "UserResponse", "UserLogin",
    "RoleCreate", "RoleUpdate", "RoleResponse",
    "PermissionCreate", "PermissionUpdate", "PermissionResponse",
    "UserSettingsCreate", "UserSettingsUpdate", "UserSettingsResponse",
    "ApiKeyCreate", "ApiKeyUpdate", "ApiKeyResponse",
    
    # 助手相关
    "AssistantCreate", "AssistantUpdate", "AssistantResponse",
    "ConversationCreate", "ConversationUpdate", "ConversationResponse",
    "MessageCreate", "MessageUpdate", "MessageResponse",
    "AgnoSessionCreate", "AgnoSessionUpdate", "AgnoSessionResponse",
    
    # 知识库相关
    "KnowledgeBaseCreate", "KnowledgeBaseUpdate", "KnowledgeBaseResponse",
    "DocumentCreate", "DocumentUpdate", "DocumentResponse",
    "DocumentChunkCreate", "DocumentChunkUpdate", "DocumentChunkResponse",
    "KnowledgeGraphCreate", "KnowledgeGraphUpdate", "KnowledgeGraphResponse",
    
    # 智能体相关
    "AgentDefinitionCreate", "AgentDefinitionUpdate", "AgentDefinitionResponse",
    "AgentTemplateCreate", "AgentTemplateUpdate", "AgentTemplateResponse",
    "AgentRunCreate", "AgentRunUpdate", "AgentRunResponse",
    "AgentChainCreate", "AgentChainUpdate", "AgentChainResponse",
    "AgentOrchestrationCreate", "AgentOrchestrationUpdate", "AgentOrchestrationResponse",
    
    # 工具相关
    "ToolCreate", "ToolUpdate", "ToolResponse",
    "ToolConfigurationCreate", "ToolConfigurationUpdate", "ToolConfigurationResponse",
    "ToolExecutionCreate", "ToolExecutionUpdate", "ToolExecutionResponse",
    "UnifiedToolCreate", "UnifiedToolUpdate", "UnifiedToolResponse",
    
    # 系统配置相关
    "SystemConfigCreate", "SystemConfigUpdate", "SystemConfigResponse",
    "ModelProviderCreate", "ModelProviderUpdate", "ModelProviderResponse",
    "FrameworkConfigCreate", "FrameworkConfigUpdate", "FrameworkConfigResponse",
    "ServiceRegistryCreate", "ServiceRegistryUpdate", "ServiceRegistryResponse",
    
    # 资源权限相关
    "ResourcePermissionCreate", "ResourcePermissionUpdate", "ResourcePermissionResponse",
    "KnowledgeBaseAccessCreate", "KnowledgeBaseAccessUpdate", "KnowledgeBaseAccessResponse",
    "AssistantAccessCreate", "AssistantAccessUpdate", "AssistantAccessResponse",
    "ModelConfigAccessCreate", "ModelConfigAccessUpdate", "ModelConfigAccessResponse",
    "MCPConfigAccessCreate", "MCPConfigAccessUpdate", "MCPConfigAccessResponse",
    "UserResourceQuotaCreate", "UserResourceQuotaUpdate", "UserResourceQuotaResponse",
    
    # 通用模式
    "PaginationParams", "PaginationResponse",
    "BaseResponse", "ErrorResponse",
    "HealthCheckResponse", "StatusResponse",
]