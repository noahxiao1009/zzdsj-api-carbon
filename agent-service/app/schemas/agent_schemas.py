"""
智能体相关的数据模型定义
完全基于Agno官方API规范，确保与Agno框架兼容
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


# 枚举定义
class TemplateType(str, Enum):
    """智能体模板类型"""
    basic_conversation = "basic_conversation"  # 基础对话助手
    knowledge_base = "knowledge_base"         # 知识库问答专家
    deep_thinking = "deep_thinking"           # 深度思考分析师


# 基础配置
class BasicConfiguration(BaseModel):
    """基础配置"""
    agent_name: str = Field(..., min_length=1, max_length=100, description="智能体名称")
    agent_description: str = Field(..., max_length=500, description="智能体描述")
    system_prompt: str = Field(..., description="系统提示词")
    language: str = Field(default="zh-CN", description="主要语言")
    response_style: str = Field(default="balanced", description="响应风格")
    max_context_length: int = Field(default=8000, ge=1000, le=32000, description="最大上下文长度")


class ModelConfig(BaseModel):
    """模型配置"""
    provider: str = Field(..., description="模型提供商")
    model: str = Field(..., description="模型名称")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="温度")
    max_tokens: int = Field(1000, ge=1, le=8000, description="最大token数")
    top_p: float = Field(1.0, ge=0.0, le=1.0, description="Top-p")
    frequency_penalty: float = Field(0.0, ge=-2.0, le=2.0, description="频率惩罚")


class ToolConfiguration(BaseModel):
    """工具配置"""
    type: str = Field(..., description="工具类型")
    name: str = Field(..., description="工具名称")
    enabled: bool = Field(True, description="是否启用")
    config: Dict[str, Any] = Field(default_factory=dict, description="工具特定配置")


class CapabilityConfiguration(BaseModel):
    """能力配置"""
    tools: List[ToolConfiguration] = Field(default_factory=list, description="工具配置")
    integrations: List[str] = Field(default_factory=list, description="集成列表")
    custom_instructions: str = Field("", description="自定义指令")


class AdvancedConfiguration(BaseModel):
    """高级配置"""
    execution_timeout: int = Field(300, ge=10, le=3600, description="执行超时时间(秒)")
    max_iterations: int = Field(10, ge=1, le=50, description="最大迭代次数")
    enable_streaming: bool = Field(True, description="启用流式响应")
    enable_citations: bool = Field(True, description="启用引用")
    privacy_level: str = Field("private", description="隐私级别")


# 智能体配置
class AgentConfig(BaseModel):
    """完整的智能体配置"""
    template_selection: Dict[str, Any] = Field(..., description="模板选择")
    basic_configuration: BasicConfiguration = Field(..., description="基础配置")
    model_configuration: ModelConfig = Field(..., description="模型配置")
    capability_configuration: CapabilityConfiguration = Field(..., description="能力配置")
    advanced_configuration: AdvancedConfiguration = Field(..., description="高级配置")


# API请求模型
class AgentCreateRequest(BaseModel):
    """创建智能体请求"""
    template_id: TemplateType = Field(..., description="模板ID")
    basic_configuration: BasicConfiguration
    model_configuration: ModelConfig
    capability_configuration: CapabilityConfiguration
    advanced_configuration: AdvancedConfiguration = Field(default_factory=AdvancedConfiguration)
    
    class Config:
        schema_extra = {
            "example": {
                "template_id": "basic_conversation",
                "basic_configuration": {
                    "agent_name": "AI助手",
                    "agent_description": "一个友好的AI助手",
                    "system_prompt": "你是一个专业的AI助手...",
                    "language": "zh-CN",
                    "response_style": "friendly"
                },
                "model_configuration": {
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "temperature": 0.7,
                    "max_tokens": 1000
                },
                "capability_configuration": {
                    "tools": [
                        {
                            "type": "web_search",
                            "name": "网络搜索",
                            "enabled": True
                        }
                    ]
                }
            }
        }


class ChatRequest(BaseModel):
    """对话请求"""
    message: str = Field(..., description="用户消息")
    session_id: Optional[str] = Field(None, description="会话ID")
    stream: bool = Field(default=False, description="是否流式响应")


class ChatResponse(BaseModel):
    """对话响应"""
    response: str = Field(..., description="AI响应")
    session_id: Optional[str] = Field(None, description="会话ID")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(None, description="工具调用记录")
    execution_time: float = Field(..., description="执行时间(秒)")


# 智能体响应模型
class AgentResponse(BaseModel):
    """智能体响应"""
    agent_id: str = Field(..., description="智能体ID")
    name: str = Field(..., description="智能体名称")
    description: str = Field(..., description="智能体描述")
    template_type: TemplateType = Field(..., description="模板类型")
    status: str = Field(..., description="状态")
    created_at: datetime = Field(..., description="创建时间")
    capabilities: List[str] = Field(default_factory=list, description="能力列表")


class AgentListResponse(BaseModel):
    """智能体列表响应"""
    agents: List[AgentResponse] = Field(..., description="智能体列表")
    total: int = Field(..., description="总数")
    page: int = Field(default=1, description="页码")
    size: int = Field(default=10, description="每页大小")


# 模板相关
class TemplateInfo(BaseModel):
    """模板信息"""
    template_id: TemplateType = Field(..., description="模板ID")
    name: str = Field(..., description="模板名称")
    description: str = Field(..., description="模板描述")
    use_cases: List[str] = Field(..., description="使用场景")
    estimated_cost: str = Field(..., description="预估成本")
    capabilities: List[str] = Field(..., description="支持的能力")
    default_tools: List[str] = Field(..., description="默认工具")
    level: int = Field(..., description="Agno框架级别 (1-5)")


class TemplateListResponse(BaseModel):
    """模板列表响应"""
    templates: List[TemplateInfo] = Field(..., description="模板列表")


# 模型提供商相关
class ModelProvider(BaseModel):
    """模型提供商"""
    id: str = Field(..., description="提供商ID")
    name: str = Field(..., description="提供商名称")
    type: str = Field(..., description="提供商类型")
    base_url: Optional[str] = Field(None, description="API基础URL")
    api_key_required: bool = Field(True, description="是否需要API密钥")
    supported_models: List[str] = Field(default_factory=list, description="支持的模型列表")
    status: str = Field("active", description="状态")


# 团队相关
class TeamMember(BaseModel):
    """团队成员"""
    agent_id: str = Field(..., description="智能体ID")
    role: str = Field(..., description="角色")
    priority: int = Field(1, ge=1, le=10, description="优先级")
    capabilities: List[str] = Field(default_factory=list, description="能力列表")


class TeamCreateRequest(BaseModel):
    """创建团队请求"""
    name: str = Field(..., min_length=1, max_length=100, description="团队名称")
    description: Optional[str] = Field(None, max_length=500, description="团队描述")
    members: List[TeamMember] = Field(..., min_items=2, description="团队成员列表")
    collaboration_mode: str = Field("sequential", description="协作模式")
    max_iterations: int = Field(5, ge=1, le=20, description="最大迭代次数")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "数据分析团队",
                "description": "专门处理数据分析和可视化任务的智能体团队",
                "members": [
                    {
                        "agent_id": "agent_001",
                        "role": "data_analyst",
                        "priority": 1,
                        "capabilities": ["数据清洗", "统计分析"]
                    },
                    {
                        "agent_id": "agent_002", 
                        "role": "visualizer",
                        "priority": 2,
                        "capabilities": ["数据可视化", "图表生成"]
                    }
                ],
                "collaboration_mode": "sequential",
                "max_iterations": 5
            }
        }


class TeamResponse(BaseModel):
    """团队响应"""
    id: str = Field(..., description="团队ID")
    name: str = Field(..., description="团队名称")
    description: Optional[str] = Field(None, description="团队描述")
    members: List[TeamMember] = Field(..., description="团队成员")
    collaboration_mode: str = Field(..., description="协作模式")
    max_iterations: int = Field(..., description="最大迭代次数")
    status: str = Field("active", description="状态")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    created_by: Optional[str] = Field(None, description="创建者")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "team_001",
                "name": "数据分析团队",
                "description": "专门处理数据分析和可视化任务的智能体团队",
                "members": [
                    {
                        "agent_id": "agent_001",
                        "role": "data_analyst", 
                        "priority": 1,
                        "capabilities": ["数据清洗", "统计分析"]
                    }
                ],
                "collaboration_mode": "sequential",
                "max_iterations": 5,
                "status": "active",
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:30:00Z",
                "created_by": "user_001"
            }
        }


# 工具相关的数据模型
class ToolInfo(BaseModel):
    """工具信息"""
    id: str = Field(..., description="工具ID")
    name: str = Field(..., description="工具名称")
    description: str = Field(..., description="工具描述")
    category: str = Field(..., description="工具分类")
    type: str = Field(..., description="工具类型")
    parameters: List[Dict[str, Any]] = Field(default_factory=list, description="参数定义")
    usage_examples: List[str] = Field(default_factory=list, description="使用示例")
    required_permissions: List[str] = Field(default_factory=list, description="所需权限")
    is_available: bool = Field(True, description="是否可用")


class ExecutionStep(BaseModel):
    """执行步骤"""
    id: str = Field(..., description="步骤ID")
    name: str = Field(..., description="步骤名称")
    type: str = Field(..., description="步骤类型")
    description: str = Field(..., description="步骤描述")
    inputs: List[str] = Field(default_factory=list, description="输入参数")
    outputs: List[str] = Field(default_factory=list, description="输出参数")
    dependencies: List[str] = Field(default_factory=list, description="依赖步骤")


class ExecutionGraph(BaseModel):
    """执行图"""
    agent_id: str = Field(..., description="智能体ID")
    steps: List[ExecutionStep] = Field(..., description="执行步骤")
    connections: List[Dict[str, str]] = Field(default_factory=list, description="步骤连接")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")


# 通用响应
class BaseResponse(BaseModel):
    """基础响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    data: Optional[Any] = Field(None, description="响应数据")


class ErrorResponse(BaseModel):
    """错误响应"""
    error: str = Field(..., description="错误类型")
    message: str = Field(..., description="错误消息")
    details: Optional[Dict[str, Any]] = Field(None, description="错误详情")


# 监控相关
class AgentMetrics(BaseModel):
    """智能体指标"""
    agent_id: str = Field(..., description="智能体ID")
    total_conversations: int = Field(..., description="总对话数")
    avg_response_time: float = Field(..., description="平均响应时间")
    success_rate: float = Field(..., description="成功率")
    tool_usage: Dict[str, int] = Field(..., description="工具使用统计")
    last_active: datetime = Field(..., description="最后活跃时间")


class ServiceMetrics(BaseModel):
    """服务指标"""
    total_agents: int = Field(..., description="总智能体数")
    active_agents: int = Field(..., description="活跃智能体数")
    total_teams: int = Field(..., description="总团队数")
    total_conversations: int = Field(..., description="总对话数")
    avg_response_time: float = Field(..., description="平均响应时间")
    system_load: float = Field(..., description="系统负载")


# 统计和监控相关的数据模型
class AgentStats(BaseModel):
    """智能体统计"""
    total_agents: int = Field(0, description="总智能体数")
    active_agents: int = Field(0, description="活跃智能体数")
    by_template: Dict[str, int] = Field(default_factory=dict, description="按模板分组统计")
    by_status: Dict[str, int] = Field(default_factory=dict, description="按状态分组统计")
    total_conversations: int = Field(0, description="总对话数")
    total_messages: int = Field(0, description="总消息数")


class ServiceStats(BaseModel):
    """服务统计"""
    agent_stats: AgentStats = Field(..., description="智能体统计")
    team_stats: Dict[str, int] = Field(default_factory=dict, description="团队统计")
    model_usage: Dict[str, int] = Field(default_factory=dict, description="模型使用统计")
    tool_usage: Dict[str, int] = Field(default_factory=dict, description="工具使用统计")
    uptime: float = Field(0.0, description="运行时间（秒）")
    last_updated: datetime = Field(..., description="最后更新时间")
