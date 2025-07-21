"""
Workflow v2 API Schema定义
支持Agno Workflow v2配置界面的数据结构
基于硅基流动API的智能体编排系统
"""
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from enum import Enum

from .flow_builder_schemas import BaseResponse, BaseDataResponse, ExecutionStatus


class ModelProviderType(str, Enum):
    """模型提供商类型"""
    SILICONFLOW = "siliconflow"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    CUSTOM = "custom"


class WorkflowComponentType(str, Enum):
    """工作流组件类型"""
    AGENT = "agent"
    MODEL = "model"
    TOOL = "tool"
    KNOWLEDGE_BASE = "knowledge_base"


class WorkflowStepType(str, Enum):
    """工作流步骤类型"""
    AGENT_RUN = "agent_run"
    CONDITION_CHECK = "condition_check"
    DATA_TRANSFORM = "data_transform"
    PARALLEL_EXECUTION = "parallel_execution"
    LOOP = "loop"
    DELAY = "delay"


class WorkflowExecutionMode(str, Enum):
    """工作流执行模式"""
    SYNC = "sync"
    ASYNC = "async"
    STREAM = "stream"


# ================ 组件定义 ================

class WorkflowV2AgentConfig(BaseModel):
    """Workflow v2智能体配置"""
    id: str = Field(..., description="智能体ID")
    name: str = Field(..., description="智能体名称")
    description: str = Field("", description="智能体描述")
    model_name: str = Field(..., description="使用的模型名称")
    instructions: str = Field(..., description="智能体指令")
    tools: List[str] = Field(default_factory=list, description="可用工具列表")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="温度参数")
    max_tokens: int = Field(4096, gt=0, description="最大Token数")
    top_p: float = Field(0.9, ge=0.0, le=1.0, description="Top-p参数")
    
    @validator('tools')
    def validate_tools(cls, v):
        """验证工具列表"""
        valid_tools = ['reasoning', 'search', 'calculator', 'file', 'web_search']
        for tool in v:
            if tool not in valid_tools:
                raise ValueError(f"Invalid tool: {tool}. Valid tools: {valid_tools}")
        return v


class WorkflowV2ModelConfig(BaseModel):
    """Workflow v2模型配置"""
    id: str = Field(..., description="模型ID")
    name: str = Field(..., description="模型名称")
    provider: ModelProviderType = Field(..., description="模型提供商")
    model_id: str = Field(..., description="实际模型标识")
    config: Dict[str, Any] = Field(default_factory=dict, description="模型配置参数")


class WorkflowV2ToolConfig(BaseModel):
    """Workflow v2工具配置"""
    id: str = Field(..., description="工具ID")
    name: str = Field(..., description="工具名称")
    type: str = Field(..., description="工具类型")
    config: Dict[str, Any] = Field(default_factory=dict, description="工具配置参数")


class WorkflowV2Components(BaseModel):
    """Workflow v2组件集合"""
    agents: List[WorkflowV2AgentConfig] = Field(default_factory=list, description="智能体列表")
    models: List[WorkflowV2ModelConfig] = Field(default_factory=list, description="模型列表")
    tools: List[WorkflowV2ToolConfig] = Field(default_factory=list, description="工具列表")
    knowledge_bases: List[str] = Field(default_factory=list, description="知识库ID列表")


# ================ 逻辑定义 ================

class WorkflowV2Step(BaseModel):
    """Workflow v2步骤定义"""
    id: str = Field(..., description="步骤ID")
    name: str = Field(..., description="步骤名称")
    type: WorkflowStepType = Field(..., description="步骤类型")
    component_ref: Optional[str] = Field(None, description="关联的组件ID")
    config: Dict[str, Any] = Field(default_factory=dict, description="步骤配置")
    dependencies: List[str] = Field(default_factory=list, description="依赖的步骤ID列表")
    
    # 前端显示属性
    position: Optional[Dict[str, float]] = Field(None, description="在前端的位置坐标")
    enabled: bool = Field(True, description="是否启用")


class WorkflowV2ConditionalBranch(BaseModel):
    """Workflow v2条件分支"""
    id: str = Field(..., description="分支ID")
    condition: str = Field(..., description="条件表达式")
    true_path: List[str] = Field(default_factory=list, description="条件为真时的步骤路径")
    false_path: List[str] = Field(default_factory=list, description="条件为假时的步骤路径")
    description: str = Field("", description="分支描述")


class WorkflowV2Logic(BaseModel):
    """Workflow v2逻辑定义"""
    steps: List[WorkflowV2Step] = Field(default_factory=list, description="步骤列表")
    conditions: List[WorkflowV2ConditionalBranch] = Field(default_factory=list, description="条件分支列表")
    variables: Dict[str, Any] = Field(default_factory=dict, description="工作流变量")
    
    # 执行配置
    max_concurrent_steps: int = Field(5, ge=1, description="最大并发步骤数")
    timeout: int = Field(300, gt=0, description="超时时间(秒)")


# ================ 工作流配置 ================

class WorkflowV2Config(BaseModel):
    """Workflow v2完整配置"""
    id: Optional[str] = Field(None, description="工作流ID")
    name: str = Field(..., description="工作流名称")
    description: str = Field("", description="工作流描述")
    version: str = Field("1.0", description="版本号")
    
    # 核心组件
    components: WorkflowV2Components = Field(..., description="组件定义")
    logic: WorkflowV2Logic = Field(..., description="逻辑定义")
    
    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    tags: List[str] = Field(default_factory=list, description="标签")
    category: str = Field("custom", description="工作流分类")
    
    # 执行配置
    execution_mode: WorkflowExecutionMode = Field(WorkflowExecutionMode.ASYNC, description="执行模式")
    
    # 时间戳
    created_at: Optional[datetime] = Field(None, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")
    
    @validator('name')
    def validate_name(cls, v):
        """验证工作流名称"""
        if not v.strip():
            raise ValueError("Workflow name cannot be empty")
        if len(v) > 100:
            raise ValueError("Workflow name too long (max 100 characters)")
        return v.strip()


# ================ 执行相关 ================

class WorkflowV2ExecutionRequest(BaseModel):
    """Workflow v2执行请求"""
    input_data: Dict[str, Any] = Field(..., description="输入数据")
    execution_mode: WorkflowExecutionMode = Field(WorkflowExecutionMode.ASYNC, description="执行模式")
    stream: bool = Field(False, description="是否启用流式响应")
    timeout: Optional[int] = Field(None, description="执行超时时间(秒)")
    callback_url: Optional[str] = Field(None, description="回调URL")


class WorkflowV2ExecutionResult(BaseModel):
    """Workflow v2执行结果"""
    execution_id: str = Field(..., description="执行ID")
    workflow_id: str = Field(..., description="工作流ID")
    status: ExecutionStatus = Field(..., description="执行状态")
    result: Any = Field(None, description="执行结果")
    error: Optional[str] = Field(None, description="错误信息")
    
    # 时间信息
    start_time: Optional[datetime] = Field(None, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    duration: Optional[float] = Field(None, description="执行时长(秒)")
    
    # 执行详情
    steps_results: Dict[str, Any] = Field(default_factory=dict, description="各步骤执行结果")
    execution_log: List[str] = Field(default_factory=list, description="执行日志")
    
    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict, description="执行元数据")


class WorkflowV2StreamingResponse(BaseModel):
    """Workflow v2流式响应"""
    event_type: str = Field(..., description="事件类型")
    step_id: Optional[str] = Field(None, description="当前步骤ID")
    content: Any = Field(None, description="响应内容")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="事件元数据")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")


# ================ 代码生成相关 ================

class WorkflowV2CodeGenerationRequest(BaseModel):
    """Workflow v2代码生成请求"""
    include_comments: bool = Field(True, description="是否包含注释")
    include_validation: bool = Field(True, description="是否包含验证代码")
    format_style: str = Field("black", description="代码格式化风格")


class WorkflowV2CodeGenerationResult(BaseModel):
    """Workflow v2代码生成结果"""
    workflow_id: str = Field(..., description="工作流ID")
    generated_code: str = Field(..., description="生成的Python代码")
    validation_result: Dict[str, Any] = Field(..., description="代码验证结果")
    file_path: Optional[str] = Field(None, description="代码文件路径")
    generated_at: datetime = Field(default_factory=datetime.now, description="生成时间")


# ================ 管理相关 ================

class WorkflowV2ListRequest(BaseModel):
    """Workflow v2列表请求"""
    page: int = Field(1, ge=1, description="页码")
    size: int = Field(20, ge=1, le=100, description="每页大小")
    category: Optional[str] = Field(None, description="分类筛选")
    tags: Optional[List[str]] = Field(None, description="标签筛选")
    search: Optional[str] = Field(None, description="搜索关键词")
    sort_by: str = Field("updated_at", description="排序字段")
    sort_order: str = Field("desc", description="排序顺序")


class WorkflowV2ListResponse(BaseDataResponse):
    """Workflow v2列表响应"""
    data: Dict[str, Any] = Field(
        default_factory=lambda: {
            "workflows": [],
            "total": 0,
            "page": 1,
            "size": 20,
            "pages": 0
        }
    )


class WorkflowV2Summary(BaseModel):
    """Workflow v2摘要信息"""
    id: str = Field(..., description="工作流ID")
    name: str = Field(..., description="工作流名称")
    description: str = Field("", description="工作流描述")
    version: str = Field(..., description="版本号")
    category: str = Field(..., description="分类")
    tags: List[str] = Field(default_factory=list, description="标签")
    
    # 统计信息
    agent_count: int = Field(0, description="智能体数量")
    step_count: int = Field(0, description="步骤数量")
    
    # 状态信息
    status: str = Field("draft", description="工作流状态")
    last_execution_time: Optional[datetime] = Field(None, description="最后执行时间")
    
    # 时间戳
    created_at: Optional[datetime] = Field(None, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")


# ================ 响应模型 ================

class WorkflowV2CreateResponse(BaseDataResponse):
    """创建工作流响应"""
    data: Dict[str, str] = Field(
        default_factory=lambda: {"workflow_id": "", "message": ""}
    )


class WorkflowV2DetailResponse(BaseDataResponse):
    """工作流详情响应"""
    data: Optional[WorkflowV2Config] = None


class WorkflowV2ExecutionResponse(BaseDataResponse):
    """工作流执行响应"""
    data: Optional[WorkflowV2ExecutionResult] = None


class WorkflowV2CodeResponse(BaseDataResponse):
    """工作流代码响应"""
    data: Optional[WorkflowV2CodeGenerationResult] = None 