"""
Flow Builder API Schema定义
对应前端智能体编排页面的数据结构
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from enum import Enum

class TemplateCategory(str, Enum):
    """模版分类"""
    CONVERSATION = "conversation"
    KNOWLEDGE = "knowledge"
    ANALYSIS = "analysis"
    CUSTOM = "custom"

class AgentType(str, Enum):
    """智能体类型"""
    SIMPLE_QA = "simple-qa"
    KNOWLEDGE_QA = "knowledge-qa"
    DEEP_THINKING = "deep-thinking"
    CUSTOM = "custom"

class ExecutionStatus(str, Enum):
    """执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

# 基础响应模型
class BaseResponse(BaseModel):
    """基础响应模型"""
    success: bool
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)

class BaseDataResponse(BaseResponse):
    """带数据的基础响应"""
    data: Any

# 模版相关Schema
class TemplateInfo(BaseModel):
    """模版信息"""
    template_id: str
    name: str
    description: str
    category: TemplateCategory
    agent_type: Optional[AgentType] = None
    node_count: int
    tags: List[str] = Field(default_factory=list)
    version: str = "1.0"
    
    # 前端展示属性
    recommended: bool = False
    use_cases: List[str] = Field(default_factory=list)
    estimated_cost: str = "中"
    features: List[str] = Field(default_factory=list)
    color: Optional[str] = None
    gradient: Optional[str] = None

class NodeInfo(BaseModel):
    """节点信息"""
    id: str
    type: str
    name: str
    description: str
    dependencies: List[str] = Field(default_factory=list)
    dependents: List[str] = Field(default_factory=list)
    config: Dict[str, Any] = Field(default_factory=dict)

class EdgeInfo(BaseModel):
    """边信息"""
    from_node: str
    to_node: str
    condition: Optional[str] = None
    weight: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)

class TemplateDetail(BaseModel):
    """模版详细信息"""
    template_id: str
    name: str
    description: str
    category: TemplateCategory
    agent_type: Optional[AgentType] = None
    
    # DAG结构
    nodes: List[NodeInfo]
    edges: List[EdgeInfo]
    
    # 配置和变量
    variables: Dict[str, Any] = Field(default_factory=dict)
    default_config: Dict[str, Any] = Field(default_factory=dict)
    
    # 前端展示属性
    features: List[str] = Field(default_factory=list)
    use_cases: List[str] = Field(default_factory=list)
    estimated_cost: str = "中"
    color: Optional[str] = None
    gradient: Optional[str] = None
    
    # 元数据
    tags: List[str] = Field(default_factory=list)
    version: str = "1.0"
    created_at: datetime

class TemplateListResponse(BaseDataResponse):
    """模版列表响应"""
    data: List[TemplateInfo]

class TemplateDetailResponse(BaseDataResponse):
    """模版详情响应"""
    data: TemplateDetail

# 智能体创建相关Schema
class BasicConfiguration(BaseModel):
    """基础配置"""
    agent_name: str = Field(..., description="智能体名称")
    description: Optional[str] = Field(None, description="智能体描述")
    avatar: Optional[str] = Field(None, description="头像URL")
    
class ModelConfiguration(BaseModel):
    """模型配置"""
    model_name: str = Field("claude-3-5-sonnet", description="模型名称")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="温度参数")
    max_tokens: int = Field(1000, ge=1, le=8192, description="最大令牌数")
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0, description="Top-p参数")
    frequency_penalty: Optional[float] = Field(None, ge=-2.0, le=2.0, description="频率惩罚")
    presence_penalty: Optional[float] = Field(None, ge=-2.0, le=2.0, description="存在惩罚")

class CapabilityConfiguration(BaseModel):
    """能力配置"""
    enabled_tools: List[str] = Field(default_factory=list, description="启用的工具")
    knowledge_base_ids: List[str] = Field(default_factory=list, description="知识库ID列表")
    memory_enabled: bool = Field(True, description="是否启用记忆")
    web_search_enabled: bool = Field(False, description="是否启用网络搜索")
    file_access_enabled: bool = Field(False, description="是否启用文件访问")

class AdvancedConfiguration(BaseModel):
    """高级配置"""
    system_prompt: Optional[str] = Field(None, description="系统提示词")
    response_format: str = Field("text", description="响应格式")
    timeout: int = Field(30, ge=1, le=300, description="超时时间(秒)")
    retry_attempts: int = Field(3, ge=0, le=10, description="重试次数")
    custom_instructions: Optional[str] = Field(None, description="自定义指令")
    safety_settings: Dict[str, Any] = Field(default_factory=dict, description="安全设置")

class AgentConfiguration(BaseModel):
    """智能体配置"""
    basic_configuration: BasicConfiguration
    model_configuration: ModelConfiguration = Field(default_factory=ModelConfiguration)
    capability_configuration: CapabilityConfiguration = Field(default_factory=CapabilityConfiguration)
    advanced_configuration: AdvancedConfiguration = Field(default_factory=AdvancedConfiguration)

class AgentCreationRequest(BaseModel):
    """智能体创建请求"""
    template_id: str = Field(..., description="模版ID")
    configuration: Dict[str, Any] = Field(..., description="配置信息")
    
    class Config:
        schema_extra = {
            "example": {
                "template_id": "basic_conversation",
                "configuration": {
                    "basic_configuration": {
                        "agent_name": "客服助手",
                        "description": "专业的客服对话助手"
                    },
                    "model_configuration": {
                        "model_name": "claude-3-5-sonnet",
                        "temperature": 0.7,
                        "max_tokens": 1000
                    },
                    "capability_configuration": {
                        "enabled_tools": ["search", "calculator"],
                        "knowledge_base_ids": [],
                        "memory_enabled": True
                    },
                    "advanced_configuration": {
                        "timeout": 30,
                        "retry_attempts": 3
                    }
                }
            }
        }

class AgentInfo(BaseModel):
    """智能体信息"""
    agent_id: str
    execution_id: str
    template_id: str
    name: str
    description: str
    status: str
    created_at: datetime
    
    # 配置信息
    model_name: Optional[str] = None
    tools_count: Optional[int] = 0
    knowledge_bases_count: Optional[int] = 0

class AgentCreationResponse(BaseDataResponse):
    """智能体创建响应"""
    data: AgentInfo

# 执行相关Schema
class ExecutionRequest(BaseModel):
    """执行请求"""
    message: Optional[str] = Field(None, description="用户消息")
    stream: bool = Field(False, description="是否流式响应")
    additional_context: Optional[Dict[str, Any]] = Field(None, description="额外上下文")
    
    class Config:
        schema_extra = {
            "example": {
                "message": "你好，请帮我分析一下这个问题",
                "stream": False,
                "additional_context": {
                    "user_preference": "detailed",
                    "language": "zh-CN"
                }
            }
        }

class ExecutionResult(BaseModel):
    """执行结果"""
    execution_id: str
    status: ExecutionStatus
    result: Optional[Any] = None
    execution_path: List[str] = Field(default_factory=list)
    execution_time: Optional[float] = None
    node_results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    # 流式响应相关
    stream: bool = False
    stream_url: Optional[str] = None

class ExecutionResponse(BaseDataResponse):
    """执行响应"""
    data: ExecutionResult

class ExecutionStatusInfo(BaseModel):
    """执行状态信息"""
    execution_id: str
    template_id: str
    status: ExecutionStatus
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    execution_path: List[str] = Field(default_factory=list)
    node_statuses: Dict[str, str] = Field(default_factory=dict)
    final_result: Optional[Any] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # 进度信息
    progress_percentage: Optional[float] = None
    current_node: Optional[str] = None
    estimated_remaining_time: Optional[float] = None

class ExecutionStatusResponse(BaseDataResponse):
    """执行状态响应"""
    data: ExecutionStatusInfo

# 流式响应Schema
class StreamingMessage(BaseModel):
    """流式消息"""
    type: str  # status, node_completed, node_result, final_result, error
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)

class StreamingExecutionResponse(BaseModel):
    """流式执行响应"""
    execution_id: str
    messages: List[StreamingMessage]

# 对话历史Schema
class ChatMessage(BaseModel):
    """对话消息"""
    role: str  # user, assistant, system
    content: str
    timestamp: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ChatHistory(BaseModel):
    """对话历史"""
    agent_id: str
    chat_history: List[ChatMessage]
    total_messages: int
    
class ChatHistoryResponse(BaseDataResponse):
    """对话历史响应"""
    data: ChatHistory

# 模型和工具Schema
class ModelInfo(BaseModel):
    """模型信息"""
    name: str
    provider: str
    description: str
    available: bool = True
    recommended: bool = False
    capabilities: List[str] = Field(default_factory=list)
    context_length: int = 4096
    cost_tier: str = "medium"  # low, medium, high
    
class ModelListResponse(BaseDataResponse):
    """模型列表响应"""
    data: List[ModelInfo]

class ToolInfo(BaseModel):
    """工具信息"""
    name: str
    display_name: str
    description: str
    category: str
    available: bool = True
    enabled: bool = True
    required: bool = False
    icon: Optional[str] = None
    
class ToolListResponse(BaseDataResponse):
    """工具列表响应"""
    data: List[ToolInfo]

# 推荐Schema
class TemplateRecommendation(BaseModel):
    """模版推荐"""
    template: TemplateInfo
    score: float
    reasons: List[str]
    
class RecommendationRequest(BaseModel):
    """推荐请求"""
    use_case: Optional[str] = Field(None, description="使用场景")
    complexity: str = Field("medium", description="复杂度需求")
    budget: str = Field("medium", description="预算要求")
    preferred_features: List[str] = Field(default_factory=list, description="偏好功能")
    
class RecommendationResponse(BaseDataResponse):
    """推荐响应"""
    data: List[TemplateRecommendation]

# 健康检查Schema
class HealthStatus(BaseModel):
    """健康状态"""
    status: str
    service: str
    timestamp: datetime
    components: Dict[str, Any] = Field(default_factory=dict)

class HealthCheckResponse(BaseModel):
    """健康检查响应"""
    status: str
    service: str
    timestamp: datetime
    components: Dict[str, Any]

# 错误响应Schema
class ErrorDetail(BaseModel):
    """错误详情"""
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None

class ErrorResponse(BaseModel):
    """错误响应"""
    success: bool = False
    error: ErrorDetail
    timestamp: datetime = Field(default_factory=datetime.now)

# 分页Schema
class PaginationParams(BaseModel):
    """分页参数"""
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")
    sort_by: Optional[str] = Field(None, description="排序字段")
    sort_order: str = Field("desc", description="排序方向")

class PaginatedResponse(BaseDataResponse):
    """分页响应"""
    data: List[Any]
    pagination: Dict[str, Any] = Field(default_factory=dict)

# WebSocket消息Schema
class WebSocketMessage(BaseModel):
    """WebSocket消息"""
    type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)

class WebSocketResponse(BaseModel):
    """WebSocket响应"""
    type: str
    data: Any
    timestamp: datetime = Field(default_factory=datetime.now)
    success: bool = True
    error: Optional[str] = None