"""
智能体管理API - 对应前端AgentBuilder的完整功能
实现智能体的创建、配置、管理和执行
"""
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import logging
import json
import asyncio
from datetime import datetime
from enum import Enum
import uuid

from ..core.agno_manager import agno_manager
from ..core.dag_orchestrator import dag_orchestrator
from ..core.dynamic_dag_generator import DAGGenerationRequest, UserPreferences, DAGGenerationMode
from ..core.tool_injection_manager import ToolCategory, ToolType
from ..schemas.flow_builder_schemas import BaseDataResponse, ExecutionStatus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/agents", tags=["agent-management"])

# 智能体管理Schema
class AgentStatus(str, Enum):
    """智能体状态"""
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    DELETED = "deleted"

class TemplateCategory(str, Enum):
    """模板类别"""
    CONVERSATION = "conversation"
    KNOWLEDGE = "knowledge"
    ANALYSIS = "analysis"
    WORKFLOW = "workflow"
    CUSTOM = "custom"

class AgentTemplate(BaseModel):
    """智能体模板"""
    id: str = Field(..., description="模板ID")
    name: str = Field(..., description="模板名称")
    description: str = Field(..., description="模板描述")
    category: TemplateCategory = Field(..., description="模板类别")
    icon: str = Field("🤖", description="模板图标")
    
    # 前端展示属性
    tags: List[str] = Field(default_factory=list, description="标签")
    use_cases: List[str] = Field(default_factory=list, description="使用场景")
    features: List[str] = Field(default_factory=list, description="功能特性")
    estimated_cost: str = Field("medium", description="预估成本")
    complexity: str = Field("medium", description="复杂度")
    recommended: bool = Field(False, description="是否推荐")
    
    # 样式属性
    color: str = Field("#64748b", description="主题色")
    gradient: Optional[str] = Field(None, description="渐变色")
    
    # 配置模板
    default_config: Dict[str, Any] = Field(default_factory=dict, description="默认配置")
    config_schema: Dict[str, Any] = Field(default_factory=dict, description="配置schema")
    
    # 元数据
    version: str = Field("1.0", description="版本")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")

class BasicConfiguration(BaseModel):
    """基础配置"""
    agent_name: str = Field(..., min_length=1, max_length=100, description="智能体名称")
    agent_description: str = Field("", max_length=500, description="智能体描述")
    system_prompt: str = Field("", max_length=2000, description="系统提示词")
    language: str = Field("zh-CN", description="语言")
    response_style: str = Field("balanced", description="回复风格")
    max_context_length: int = Field(8000, ge=1000, le=32000, description="最大上下文长度")
    
    # 扩展配置
    avatar: Optional[str] = Field(None, description="头像URL")
    personality: Optional[str] = Field(None, description="个性设置")
    greeting_message: Optional[str] = Field(None, description="问候语")

class ModelConfiguration(BaseModel):
    """模型配置"""
    provider: str = Field("zhipu", description="模型提供商")
    model: str = Field("", description="模型名称")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="温度参数")
    max_tokens: int = Field(1000, ge=1, le=8192, description="最大令牌数")
    top_p: float = Field(1.0, ge=0.0, le=1.0, description="Top-p参数")
    frequency_penalty: float = Field(0.0, ge=-2.0, le=2.0, description="频率惩罚")
    presence_penalty: float = Field(0.0, ge=-2.0, le=2.0, description="存在惩罚")
    
    # 高级配置
    stop_sequences: List[str] = Field(default_factory=list, description="停止序列")
    response_format: str = Field("text", description="响应格式")

class CapabilityConfiguration(BaseModel):
    """能力配置"""
    tools: List[str] = Field(default_factory=list, description="启用的工具")
    integrations: List[str] = Field(default_factory=list, description="集成服务")
    knowledge_base_ids: List[str] = Field(default_factory=list, description="知识库ID")
    custom_instructions: str = Field("", description="自定义指令")
    
    # 功能开关
    memory_enabled: bool = Field(True, description="是否启用记忆")
    web_search_enabled: bool = Field(False, description="是否启用网络搜索")
    file_access_enabled: bool = Field(False, description="是否启用文件访问")
    image_generation_enabled: bool = Field(False, description="是否启用图像生成")
    code_execution_enabled: bool = Field(False, description="是否启用代码执行")

class AdvancedConfiguration(BaseModel):
    """高级配置"""
    execution_timeout: int = Field(300, ge=30, le=1800, description="执行超时(秒)")
    max_iterations: int = Field(10, ge=1, le=50, description="最大迭代次数")
    enable_streaming: bool = Field(True, description="是否启用流式响应")
    enable_citations: bool = Field(True, description="是否启用引用")
    privacy_level: str = Field("private", description="隐私级别")
    
    # 安全配置
    content_filter_enabled: bool = Field(True, description="是否启用内容过滤")
    rate_limit_enabled: bool = Field(True, description="是否启用速率限制")
    audit_enabled: bool = Field(True, description="是否启用审计")
    
    # 性能配置
    cache_enabled: bool = Field(True, description="是否启用缓存")
    parallel_processing: bool = Field(False, description="是否并行处理")
    auto_retry: bool = Field(True, description="是否自动重试")

class AgentConfiguration(BaseModel):
    """智能体完整配置"""
    template_selection: Dict[str, Any] = Field(default_factory=dict, description="模板选择")
    basic_configuration: BasicConfiguration = Field(..., description="基础配置")
    model_configuration: ModelConfiguration = Field(..., description="模型配置")
    capability_configuration: CapabilityConfiguration = Field(default_factory=CapabilityConfiguration, description="能力配置")
    advanced_configuration: AdvancedConfiguration = Field(default_factory=AdvancedConfiguration, description="高级配置")

class Agent(BaseModel):
    """智能体实体"""
    id: str = Field(..., description="智能体ID")
    name: str = Field(..., description="智能体名称")
    description: str = Field("", description="智能体描述")
    template_id: str = Field(..., description="模板ID")
    status: AgentStatus = Field(AgentStatus.DRAFT, description="状态")
    
    # 配置
    configuration: AgentConfiguration = Field(..., description="智能体配置")
    
    # 统计信息
    total_conversations: int = Field(0, description="总对话数")
    total_tokens_used: int = Field(0, description="总消耗令牌数")
    average_response_time: float = Field(0.0, description="平均响应时间")
    success_rate: float = Field(0.0, description="成功率")
    
    # 元数据
    created_by: str = Field(..., description="创建者")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    last_active_at: Optional[datetime] = Field(None, description="最后活跃时间")
    
    # 扩展信息
    tags: List[str] = Field(default_factory=list, description="标签")
    version: str = Field("1.0", description="版本")
    is_public: bool = Field(False, description="是否公开")

class AgentCreateRequest(BaseModel):
    """智能体创建请求"""
    template_id: str = Field(..., description="模板ID")
    configuration: AgentConfiguration = Field(..., description="智能体配置")
    
    # 可选字段
    tags: List[str] = Field(default_factory=list, description="标签")
    is_public: bool = Field(False, description="是否公开")

class AgentUpdateRequest(BaseModel):
    """智能体更新请求"""
    name: Optional[str] = Field(None, description="智能体名称")
    description: Optional[str] = Field(None, description="智能体描述")
    configuration: Optional[AgentConfiguration] = Field(None, description="智能体配置")
    status: Optional[AgentStatus] = Field(None, description="状态")
    tags: Optional[List[str]] = Field(None, description="标签")
    is_public: Optional[bool] = Field(None, description="是否公开")

class AgentExecutionRequest(BaseModel):
    """智能体执行请求"""
    message: str = Field(..., description="用户消息")
    session_id: Optional[str] = Field(None, description="会话ID")
    stream: bool = Field(False, description="是否流式响应")
    context: Dict[str, Any] = Field(default_factory=dict, description="上下文")
    
    # 执行选项
    timeout: Optional[int] = Field(None, description="超时时间")
    debug: bool = Field(False, description="调试模式")

class AgentExecutionResponse(BaseModel):
    """智能体执行响应"""
    execution_id: str = Field(..., description="执行ID")
    agent_id: str = Field(..., description="智能体ID")
    message: str = Field(..., description="用户消息")
    response: str = Field(..., description="智能体响应")
    session_id: Optional[str] = Field(None, description="会话ID")
    
    # 执行信息
    execution_time: float = Field(..., description="执行时间")
    tokens_used: int = Field(0, description="消耗令牌数")
    model_used: str = Field(..., description="使用的模型")
    
    # 元数据
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")
    debug_info: Optional[Dict[str, Any]] = Field(None, description="调试信息")

class AgentStats(BaseModel):
    """智能体统计信息"""
    agent_id: str
    total_conversations: int
    total_tokens_used: int
    average_response_time: float
    success_rate: float
    daily_usage: Dict[str, int]
    popular_queries: List[str]
    error_count: int
    last_24h_usage: int

# 依赖函数
async def get_current_user_id() -> str:
    """获取当前用户ID"""
    return "user_123"

# 模拟数据存储
agents_db: Dict[str, Agent] = {}
templates_db: Dict[str, AgentTemplate] = {}

# 初始化模板数据
def _initialize_templates():
    """初始化模板数据"""
    templates = [
        AgentTemplate(
            id="simple_qa",
            name="简单问答",
            description="适合快速问答的轻量级智能体",
            category=TemplateCategory.CONVERSATION,
            icon="💬",
            tags=["问答", "快速", "轻量"],
            use_cases=["客户服务", "FAQ", "快速咨询"],
            features=["毫秒级响应", "低成本", "高并发"],
            estimated_cost="low",
            complexity="low",
            recommended=True,
            color="#3b82f6",
            gradient="linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)",
            default_config={
                "basic_configuration": {
                    "system_prompt": "你是一个友好的客服助手，请简洁明了地回答用户问题。",
                    "max_context_length": 4000
                },
                "model_configuration": {
                    "provider": "zhipu",
                    "model": "glm-4-flash",
                    "temperature": 0.3,
                    "max_tokens": 500
                }
            }
        ),
        AgentTemplate(
            id="knowledge_qa",
            name="知识库问答",
            description="基于知识库的专业问答智能体",
            category=TemplateCategory.KNOWLEDGE,
            icon="📚",
            tags=["知识库", "专业", "准确"],
            use_cases=["技术支持", "产品咨询", "专业问答"],
            features=["知识库检索", "引用溯源", "专业准确"],
            estimated_cost="medium",
            complexity="medium",
            recommended=True,
            color="#8b5cf6",
            gradient="linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)",
            default_config={
                "basic_configuration": {
                    "system_prompt": "你是一个专业的技术支持助手，请基于知识库内容准确回答用户问题，并提供相关引用。",
                    "max_context_length": 8000
                },
                "model_configuration": {
                    "provider": "zhipu",
                    "model": "glm-4-plus",
                    "temperature": 0.1,
                    "max_tokens": 1000
                },
                "capability_configuration": {
                    "tools": ["knowledge_search", "citation_generator"]
                }
            }
        ),
        AgentTemplate(
            id="deep_thinking",
            name="深度思考",
            description="多步骤推理的高级智能体",
            category=TemplateCategory.ANALYSIS,
            icon="🧠",
            tags=["推理", "分析", "深度"],
            use_cases=["战略分析", "复杂决策", "研究报告"],
            features=["多步推理", "深度分析", "创新思维"],
            estimated_cost="high",
            complexity="high",
            recommended=False,
            color="#10b981",
            gradient="linear-gradient(135deg, #10b981 0%, #059669 100%)",
            default_config={
                "basic_configuration": {
                    "system_prompt": "你是一个深度思考的分析专家，请进行多步骤推理，提供深入的分析和见解。",
                    "max_context_length": 16000
                },
                "model_configuration": {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "temperature": 0.7,
                    "max_tokens": 2000
                },
                "capability_configuration": {
                    "tools": ["reasoning", "analysis", "web_search"]
                },
                "advanced_configuration": {
                    "max_iterations": 5,
                    "enable_citations": True
                }
            }
        )
    ]
    
    for template in templates:
        templates_db[template.id] = template

# 初始化模板
_initialize_templates()

# API端点
@router.get("/templates", response_model=BaseDataResponse)
async def get_agent_templates():
    """获取智能体模板列表"""
    try:
        templates = list(templates_db.values())
        
        # 按推荐程度和类别排序
        templates.sort(key=lambda x: (not x.recommended, x.category.value, x.name))
        
        return BaseDataResponse(
            success=True,
            data=[t.dict() for t in templates],
            message="Successfully retrieved agent templates"
        )
        
    except Exception as e:
        logger.error(f"Failed to get agent templates: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/templates/{template_id}", response_model=BaseDataResponse)
async def get_agent_template(template_id: str):
    """获取智能体模板详情"""
    try:
        if template_id not in templates_db:
            raise HTTPException(status_code=404, detail="Template not found")
        
        template = templates_db[template_id]
        
        return BaseDataResponse(
            success=True,
            data=template.dict(),
            message="Successfully retrieved agent template"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent template: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/", response_model=BaseDataResponse)
async def create_agent(
    request: AgentCreateRequest,
    user_id: str = Depends(get_current_user_id)
):
    """创建智能体"""
    try:
        # 验证模板存在
        if request.template_id not in templates_db:
            raise HTTPException(status_code=404, detail="Template not found")
        
        template = templates_db[request.template_id]
        
        # 生成智能体ID
        agent_id = str(uuid.uuid4())
        
        # 创建智能体
        agent = Agent(
            id=agent_id,
            name=request.configuration.basic_configuration.agent_name,
            description=request.configuration.basic_configuration.agent_description,
            template_id=request.template_id,
            status=AgentStatus.DRAFT,
            configuration=request.configuration,
            created_by=user_id,
            tags=request.tags,
            is_public=request.is_public
        )
        
        # 保存到数据库
        agents_db[agent_id] = agent
        
        logger.info(f"Created agent {agent_id} from template {request.template_id} by user {user_id}")
        
        return BaseDataResponse(
            success=True,
            data=agent.dict(),
            message="Agent created successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create agent: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=BaseDataResponse)
async def list_agents(
    user_id: str = Depends(get_current_user_id),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[AgentStatus] = Query(None),
    template_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None)
):
    """获取智能体列表"""
    try:
        agents = list(agents_db.values())
        
        # 过滤条件
        if status:
            agents = [a for a in agents if a.status == status]
        if template_id:
            agents = [a for a in agents if a.template_id == template_id]
        if search:
            agents = [a for a in agents if search.lower() in a.name.lower() or search.lower() in a.description.lower()]
        
        # 排序
        agents.sort(key=lambda x: x.updated_at, reverse=True)
        
        # 分页
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_agents = agents[start_idx:end_idx]
        
        return BaseDataResponse(
            success=True,
            data={
                "agents": [agent.dict() for agent in paginated_agents],
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": len(agents),
                    "total_pages": (len(agents) + page_size - 1) // page_size
                }
            },
            message="Successfully retrieved agents"
        )
        
    except Exception as e:
        logger.error(f"Failed to list agents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{agent_id}", response_model=BaseDataResponse)
async def get_agent(agent_id: str):
    """获取智能体详情"""
    try:
        if agent_id not in agents_db:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        agent = agents_db[agent_id]
        
        return BaseDataResponse(
            success=True,
            data=agent.dict(),
            message="Successfully retrieved agent"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{agent_id}", response_model=BaseDataResponse)
async def update_agent(
    agent_id: str,
    request: AgentUpdateRequest,
    user_id: str = Depends(get_current_user_id)
):
    """更新智能体"""
    try:
        if agent_id not in agents_db:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        agent = agents_db[agent_id]
        
        # 检查权限
        if agent.created_by != user_id:
            raise HTTPException(status_code=403, detail="Permission denied")
        
        # 更新字段
        if request.name is not None:
            agent.name = request.name
        if request.description is not None:
            agent.description = request.description
        if request.configuration is not None:
            agent.configuration = request.configuration
        if request.status is not None:
            agent.status = request.status
        if request.tags is not None:
            agent.tags = request.tags
        if request.is_public is not None:
            agent.is_public = request.is_public
        
        # 更新时间
        agent.updated_at = datetime.now()
        
        # 保存更改
        agents_db[agent_id] = agent
        
        logger.info(f"Updated agent {agent_id} by user {user_id}")
        
        return BaseDataResponse(
            success=True,
            data=agent.dict(),
            message="Agent updated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update agent: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """删除智能体"""
    try:
        if agent_id not in agents_db:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        agent = agents_db[agent_id]
        
        # 检查权限
        if agent.created_by != user_id:
            raise HTTPException(status_code=403, detail="Permission denied")
        
        # 软删除
        agent.status = AgentStatus.DELETED
        agent.updated_at = datetime.now()
        
        logger.info(f"Deleted agent {agent_id} by user {user_id}")
        
        return BaseDataResponse(
            success=True,
            data=None,
            message="Agent deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete agent: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{agent_id}/execute", response_model=BaseDataResponse)
async def execute_agent(
    agent_id: str,
    request: AgentExecutionRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id)
):
    """执行智能体"""
    try:
        if agent_id not in agents_db:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        agent = agents_db[agent_id]
        
        # 检查状态
        if agent.status != AgentStatus.ACTIVE:
            raise HTTPException(status_code=400, detail="Agent is not active")
        
        # 生成执行ID
        execution_id = str(uuid.uuid4())
        
        # 准备执行配置
        execution_config = {
            "agent_id": agent_id,
            "user_id": user_id,
            "message": request.message,
            "session_id": request.session_id or str(uuid.uuid4()),
            "context": request.context,
            "model_config": agent.configuration.model_configuration.dict(),
            "timeout": request.timeout or agent.configuration.advanced_configuration.execution_timeout
        }
        
        if request.stream:
            # 流式响应
            background_tasks.add_task(_execute_agent_background, execution_id, execution_config)
            
            return BaseDataResponse(
                success=True,
                data={
                    "execution_id": execution_id,
                    "agent_id": agent_id,
                    "stream": True,
                    "stream_url": f"/api/v1/agents/{agent_id}/executions/{execution_id}/stream"
                },
                message="Agent execution started"
            )
        else:
            # 同步执行
            start_time = datetime.now()
            
            try:
                # 调用Agno管理器执行
                response = await agno_manager.execute_agent(
                    agent_config=agent.configuration.dict(),
                    message=request.message,
                    context=request.context
                )
                
                execution_time = (datetime.now() - start_time).total_seconds()
                
                # 更新统计信息
                agent.total_conversations += 1
                agent.average_response_time = (agent.average_response_time + execution_time) / 2
                agent.last_active_at = datetime.now()
                
                agents_db[agent_id] = agent
                
                execution_response = AgentExecutionResponse(
                    execution_id=execution_id,
                    agent_id=agent_id,
                    message=request.message,
                    response=response.get("response", ""),
                    session_id=request.session_id,
                    execution_time=execution_time,
                    tokens_used=response.get("tokens_used", 0),
                    model_used=agent.configuration.model_configuration.model,
                    debug_info=response.get("debug_info") if request.debug else None
                )
                
                return BaseDataResponse(
                    success=True,
                    data=execution_response.dict(),
                    message="Agent execution completed"
                )
                
            except Exception as e:
                logger.error(f"Agent execution failed: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute agent: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{agent_id}/activate")
async def activate_agent(
    agent_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """激活智能体"""
    try:
        if agent_id not in agents_db:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        agent = agents_db[agent_id]
        
        # 检查权限
        if agent.created_by != user_id:
            raise HTTPException(status_code=403, detail="Permission denied")
        
        # 激活智能体
        agent.status = AgentStatus.ACTIVE
        agent.updated_at = datetime.now()
        
        agents_db[agent_id] = agent
        
        logger.info(f"Activated agent {agent_id} by user {user_id}")
        
        return BaseDataResponse(
            success=True,
            data=None,
            message="Agent activated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to activate agent: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{agent_id}/deactivate")
async def deactivate_agent(
    agent_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """停用智能体"""
    try:
        if agent_id not in agents_db:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        agent = agents_db[agent_id]
        
        # 检查权限
        if agent.created_by != user_id:
            raise HTTPException(status_code=403, detail="Permission denied")
        
        # 停用智能体
        agent.status = AgentStatus.INACTIVE
        agent.updated_at = datetime.now()
        
        agents_db[agent_id] = agent
        
        logger.info(f"Deactivated agent {agent_id} by user {user_id}")
        
        return BaseDataResponse(
            success=True,
            data=None,
            message="Agent deactivated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to deactivate agent: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{agent_id}/stats", response_model=BaseDataResponse)
async def get_agent_stats(agent_id: str):
    """获取智能体统计信息"""
    try:
        if agent_id not in agents_db:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        agent = agents_db[agent_id]
        
        # 模拟统计数据
        stats = AgentStats(
            agent_id=agent_id,
            total_conversations=agent.total_conversations,
            total_tokens_used=agent.total_tokens_used,
            average_response_time=agent.average_response_time,
            success_rate=agent.success_rate,
            daily_usage={"2024-01-01": 10, "2024-01-02": 15},
            popular_queries=["如何使用", "什么是", "帮我分析"],
            error_count=2,
            last_24h_usage=25
        )
        
        return BaseDataResponse(
            success=True,
            data=stats.dict(),
            message="Successfully retrieved agent stats"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{agent_id}/executions/{execution_id}/stream")
async def stream_agent_execution(agent_id: str, execution_id: str):
    """流式获取智能体执行结果"""
    async def generate_stream():
        try:
            # 模拟流式响应
            yield f"data: {json.dumps({'type': 'start', 'execution_id': execution_id})}\n\n"
            
            # 模拟处理过程
            await asyncio.sleep(0.5)
            yield f"data: {json.dumps({'type': 'thinking', 'message': '正在思考...'})}\n\n"
            
            await asyncio.sleep(1.0)
            yield f"data: {json.dumps({'type': 'processing', 'message': '处理中...'})}\n\n"
            
            await asyncio.sleep(0.5)
            yield f"data: {json.dumps({'type': 'response', 'message': '这是智能体的回复内容'})}\n\n"
            
            yield f"data: {json.dumps({'type': 'complete', 'execution_id': execution_id})}\n\n"
            
        except Exception as e:
            error_msg = {'type': 'error', 'error': str(e)}
            yield f"data: {json.dumps(error_msg)}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*"
        }
    )

# 辅助函数
async def _execute_agent_background(execution_id: str, config: Dict[str, Any]):
    """后台执行智能体"""
    try:
        # 模拟后台执行
        await asyncio.sleep(2)
        logger.info(f"Background execution {execution_id} completed")
    except Exception as e:
        logger.error(f"Background execution failed: {str(e)}")

# ==================== 动态智能体创建和管理 ====================

class DynamicAgentCreateRequest(BaseModel):
    """动态智能体创建请求"""
    template_id: str = Field(..., description="模板ID")
    generation_mode: str = Field(default="custom", description="生成模式")
    
    # 用户偏好
    preferred_tool_types: List[str] = Field(default=["builtin"], description="偏好的工具类型")
    preferred_categories: List[str] = Field(default=["reasoning"], description="偏好的工具分类")
    excluded_tools: List[str] = Field(default=[], description="排除的工具")
    max_tools_per_agent: int = Field(default=5, description="每个智能体最大工具数")
    optimization_strategy: str = Field(default="balanced", description="优化策略")
    
    # 用户选择
    selected_capabilities: List[str] = Field(default=[], description="选择的能力")
    enabled_tools: List[str] = Field(default=[], description="启用的工具")
    disabled_tools: List[str] = Field(default=[], description="禁用的工具")
    
    # 配置
    model_config: Dict[str, Any] = Field(default={}, description="模型配置")
    knowledge_config: Dict[str, Any] = Field(default={}, description="知识库配置")
    custom_instructions: str = Field(default="", description="自定义指令")
    
    # 高级配置
    max_execution_time: int = Field(default=300, description="最大执行时间")
    max_cost_per_execution: float = Field(default=1.0, description="最大执行成本")
    min_success_rate: float = Field(default=0.8, description="最小成功率")
    enable_parallel_execution: bool = Field(default=True, description="启用并行执行")
    enable_fallback_nodes: bool = Field(default=True, description="启用备用节点")


@router.post("/dynamic/create", response_model=BaseDataResponse)
async def create_dynamic_agent(
    request: DynamicAgentCreateRequest,
    user_id: str = Depends(get_current_user_id)
):
    """创建动态智能体"""
    try:
        # 构建用户偏好
        user_preferences = UserPreferences(
            preferred_tool_types=[ToolType(t) for t in request.preferred_tool_types],
            preferred_categories=[ToolCategory(c) for c in request.preferred_categories],
            excluded_tools=request.excluded_tools,
            max_tools_per_agent=request.max_tools_per_agent,
            optimization_strategy=request.optimization_strategy,
            max_execution_time=request.max_execution_time,
            max_cost_per_execution=request.max_cost_per_execution,
            min_success_rate=request.min_success_rate,
            enable_parallel_execution=request.enable_parallel_execution,
            enable_fallback_nodes=request.enable_fallback_nodes
        )
        
        # 构建生成请求
        generation_request = DAGGenerationRequest(
            template_id=request.template_id,
            user_id=user_id,
            generation_mode=DAGGenerationMode(request.generation_mode),
            user_preferences=user_preferences,
            selected_capabilities=request.selected_capabilities,
            enabled_tools=request.enabled_tools,
            disabled_tools=request.disabled_tools,
            model_config=request.model_config,
            knowledge_config=request.knowledge_config,
            custom_instructions=request.custom_instructions
        )
        
        # 创建智能体
        result = await dag_orchestrator.create_custom_agent(
            template_id=request.template_id,
            user_id=user_id,
            generation_request=generation_request
        )
        
        if result["success"]:
            return BaseDataResponse(
                success=True,
                data=result,
                message="Dynamic agent created successfully"
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Failed to create dynamic agent")
            )
            
    except Exception as e:
        logger.error(f"Failed to create dynamic agent: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create dynamic agent: {str(e)}"
        )


@router.get("/instances", response_model=BaseDataResponse)
async def list_agent_instances(
    user_id: str = Depends(get_current_user_id)
):
    """列出智能体实例"""
    try:
        instances = await dag_orchestrator.list_agent_instances(user_id)
        
        return BaseDataResponse(
            success=True,
            data={"instances": instances},
            message="Agent instances retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to list agent instances: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list agent instances: {str(e)}"
        )


@router.get("/instances/{instance_id}/status", response_model=BaseDataResponse)
async def get_agent_instance_status(
    instance_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """获取智能体实例状态"""
    try:
        status = await dag_orchestrator.get_agent_instance_status(instance_id)
        
        return BaseDataResponse(
            success=True,
            data=status,
            message="Agent instance status retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to get agent instance status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get agent instance status: {str(e)}"
        )


class AgentExecutionRequest(BaseModel):
    """智能体执行请求"""
    message: str = Field(..., description="用户消息")
    session_id: Optional[str] = Field(None, description="会话ID")
    execution_options: Dict[str, Any] = Field(default={}, description="执行选项")


@router.post("/instances/{instance_id}/execute", response_model=BaseDataResponse)
async def execute_agent_instance(
    instance_id: str,
    request: AgentExecutionRequest,
    user_id: str = Depends(get_current_user_id)
):
    """执行智能体实例"""
    try:
        execution_options = request.execution_options
        if request.session_id:
            execution_options["session_id"] = request.session_id
        
        result = await dag_orchestrator.execute_agent_instance(
            instance_id=instance_id,
            message=request.message,
            user_id=user_id,
            execution_options=execution_options
        )
        
        return BaseDataResponse(
            success=result.get("success", False),
            data=result,
            message="Agent execution completed"
        )
        
    except Exception as e:
        logger.error(f"Failed to execute agent instance: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to execute agent instance: {str(e)}"
        )


@router.delete("/instances/{instance_id}", response_model=BaseDataResponse)
async def remove_agent_instance(
    instance_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """移除智能体实例"""
    try:
        result = await dag_orchestrator.remove_agent_instance(instance_id)
        
        return BaseDataResponse(
            success=result.get("success", False),
            data=result,
            message="Agent instance removed successfully" if result.get("success") else "Failed to remove agent instance"
        )
        
    except Exception as e:
        logger.error(f"Failed to remove agent instance: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to remove agent instance: {str(e)}"
        )


@router.get("/system/statistics", response_model=BaseDataResponse)
async def get_system_statistics():
    """获取系统统计信息"""
    try:
        stats = dag_orchestrator.get_system_statistics()
        
        return BaseDataResponse(
            success=True,
            data=stats,
            message="System statistics retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to get system statistics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get system statistics: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "agent-management",
        "timestamp": datetime.now().isoformat(),
        "stats": {
            "total_agents": len(agents_db),
            "active_agents": len([a for a in agents_db.values() if a.status == AgentStatus.ACTIVE]),
            "templates_available": len(templates_db)
        }
    }