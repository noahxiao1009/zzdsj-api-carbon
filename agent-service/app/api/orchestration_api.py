"""
智能体编排API - 对应前端画布编排功能
基于前端FlowDesigner和AgentBuilder的需求实现
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import logging
import json
import asyncio
from datetime import datetime
from enum import Enum

from ..core.dag_orchestrator import dag_orchestrator
from ..core.agno_manager import agno_manager
from ..core.workflow_v2_manager import workflow_v2_manager
from ..schemas.flow_builder_schemas import (
    BaseDataResponse, 
    ExecutionStatus,
    StreamingMessage
)
from ..schemas.workflow_v2_schemas import (
    WorkflowV2Config,
    WorkflowV2ExecutionRequest,
    WorkflowV2ExecutionResult,
    WorkflowV2CodeGenerationRequest,
    WorkflowV2CodeGenerationResult,
    WorkflowV2ListRequest,
    WorkflowV2ListResponse,
    WorkflowV2Summary,
    WorkflowV2CreateResponse,
    WorkflowV2DetailResponse,
    WorkflowV2ExecutionResponse,
    WorkflowV2CodeResponse,
    WorkflowV2StreamingResponse,
    WorkflowExecutionMode
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/orchestration", tags=["orchestration"])

# 画布编排相关Schema
class NodeType(str, Enum):
    """节点类型"""
    MODEL = "model"
    TOOL = "tool"
    AGENT = "agent"
    CONDITION = "condition"
    OUTPUT = "output"
    INPUT = "input"
    KNOWLEDGE = "knowledge"

class ConnectionType(str, Enum):
    """连接类型"""
    SEQUENCE = "sequence"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"
    LOOP = "loop"

class FlowNode(BaseModel):
    """流程节点"""
    id: str = Field(..., description="节点ID")
    type: NodeType = Field(..., description="节点类型")
    name: str = Field(..., description="节点名称")
    description: str = Field("", description="节点描述")
    position: Dict[str, float] = Field(..., description="节点位置坐标")
    config: Dict[str, Any] = Field(default_factory=dict, description="节点配置")
    
    # 扩展属性
    enabled: bool = Field(True, description="节点是否启用")
    timeout: int = Field(60, description="节点超时时间(秒)")
    retry_count: int = Field(3, description="重试次数")

class FlowConnection(BaseModel):
    """流程连接"""
    id: str = Field(..., description="连接ID")
    source: str = Field(..., description="源节点ID")
    target: str = Field(..., description="目标节点ID")
    type: ConnectionType = Field(ConnectionType.SEQUENCE, description="连接类型")
    condition: Optional[str] = Field(None, description="条件表达式")
    label: Optional[str] = Field(None, description="连接标签")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="连接元数据")

class FlowDefinition(BaseModel):
    """流程定义"""
    id: str = Field(..., description="流程ID")
    name: str = Field(..., description="流程名称")
    description: str = Field("", description="流程描述")
    version: str = Field("1.0", description="版本号")
    
    # 核心结构
    nodes: List[FlowNode] = Field(..., description="节点列表")
    connections: List[FlowConnection] = Field(..., description="连接列表")
    
    # 全局配置
    variables: Dict[str, Any] = Field(default_factory=dict, description="全局变量")
    timeout: int = Field(300, description="总超时时间(秒)")
    
    # 元数据
    tags: List[str] = Field(default_factory=list, description="标签")
    created_by: Optional[str] = Field(None, description="创建者")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

class FlowExecutionRequest(BaseModel):
    """流程执行请求"""
    flow_id: str = Field(..., description="流程ID")
    input_data: Dict[str, Any] = Field(default_factory=dict, description="输入数据")
    variables: Dict[str, Any] = Field(default_factory=dict, description="变量覆盖")
    stream: bool = Field(False, description="是否流式执行")
    
    # 执行选项
    timeout: Optional[int] = Field(None, description="超时时间覆盖")
    debug: bool = Field(False, description="调试模式")
    track_metrics: bool = Field(True, description="是否跟踪指标")

class FlowExecutionStatus(BaseModel):
    """流程执行状态"""
    execution_id: str
    flow_id: str
    status: ExecutionStatus
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    # 执行路径
    execution_path: List[str] = Field(default_factory=list)
    current_node: Optional[str] = None
    
    # 节点状态
    node_statuses: Dict[str, str] = Field(default_factory=dict)
    node_results: Dict[str, Any] = Field(default_factory=dict)
    
    # 结果和错误
    final_result: Optional[Any] = None
    error_message: Optional[str] = None
    
    # 性能指标
    execution_time: Optional[float] = None
    total_nodes: int = 0
    completed_nodes: int = 0
    progress_percentage: float = 0.0

class NodeTemplate(BaseModel):
    """节点模板"""
    id: str
    type: NodeType
    name: str
    description: str
    category: str
    icon: str
    
    # 配置Schema
    config_schema: Dict[str, Any] = Field(default_factory=dict)
    default_config: Dict[str, Any] = Field(default_factory=dict)
    
    # 连接点
    input_ports: List[str] = Field(default_factory=list)
    output_ports: List[str] = Field(default_factory=list)
    
    # 扩展属性
    color: str = "#64748b"
    requires_auth: bool = False
    estimated_cost: str = "low"

# 依赖函数
async def get_current_user_id() -> str:
    """获取当前用户ID"""
    return "user_123"

# 画布编排API
@router.get("/node-templates", response_model=BaseDataResponse)
async def get_node_templates():
    """获取节点模板列表"""
    try:
        templates = [
            NodeTemplate(
                id="llm_node",
                type=NodeType.MODEL,
                name="大语言模型",
                description="调用大语言模型进行文本生成",
                category="model",
                icon="🤖",
                config_schema={
                    "model_name": {"type": "select", "options": ["claude-3-5-sonnet", "gpt-4o"], "required": True},
                    "temperature": {"type": "slider", "min": 0, "max": 2, "step": 0.1},
                    "max_tokens": {"type": "number", "min": 1, "max": 4000}
                },
                default_config={
                    "model_name": "claude-3-5-sonnet",
                    "temperature": 0.7,
                    "max_tokens": 1000
                },
                input_ports=["prompt"],
                output_ports=["response"],
                color="#6366f1"
            ),
            NodeTemplate(
                id="knowledge_search",
                type=NodeType.TOOL,
                name="知识库检索",
                description="在知识库中搜索相关信息",
                category="knowledge",
                icon="🔍",
                config_schema={
                    "knowledge_base_id": {"type": "select", "required": True},
                    "top_k": {"type": "number", "min": 1, "max": 20},
                    "similarity_threshold": {"type": "slider", "min": 0, "max": 1, "step": 0.01}
                },
                default_config={
                    "top_k": 5,
                    "similarity_threshold": 0.7
                },
                input_ports=["query"],
                output_ports=["results"],
                color="#10b981"
            ),
            NodeTemplate(
                id="web_search",
                type=NodeType.TOOL,
                name="网络搜索",
                description="搜索互联网信息",
                category="search",
                icon="🌐",
                config_schema={
                    "search_engine": {"type": "select", "options": ["google", "bing"], "required": True},
                    "max_results": {"type": "number", "min": 1, "max": 10}
                },
                default_config={
                    "search_engine": "google",
                    "max_results": 5
                },
                input_ports=["query"],
                output_ports=["results"],
                color="#f59e0b"
            ),
            NodeTemplate(
                id="condition_node",
                type=NodeType.CONDITION,
                name="条件判断",
                description="根据条件决定执行路径",
                category="logic",
                icon="⚡",
                config_schema={
                    "condition": {"type": "text", "required": True},
                    "operator": {"type": "select", "options": ["==", "!=", ">", "<", ">=", "<=", "contains"]}
                },
                default_config={
                    "operator": "=="
                },
                input_ports=["input"],
                output_ports=["true", "false"],
                color="#8b5cf6"
            ),
            NodeTemplate(
                id="output_node",
                type=NodeType.OUTPUT,
                name="输出节点",
                description="输出最终结果",
                category="output",
                icon="📤",
                config_schema={
                    "format": {"type": "select", "options": ["text", "json", "markdown"]},
                    "template": {"type": "textarea"}
                },
                default_config={
                    "format": "text"
                },
                input_ports=["data"],
                output_ports=[],
                color="#ef4444"
            ),
            NodeTemplate(
                id="agent_node",
                type=NodeType.AGENT,
                name="智能体",
                description="调用预定义的智能体",
                category="agent",
                icon="🤖",
                config_schema={
                    "agent_id": {"type": "select", "required": True},
                    "context": {"type": "textarea"}
                },
                default_config={},
                input_ports=["message"],
                output_ports=["response"],
                color="#ec4899"
            )
        ]
        
        return BaseDataResponse(
            success=True,
            data=templates,
            message="Successfully retrieved node templates"
        )
        
    except Exception as e:
        logger.error(f"Failed to get node templates: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/flows", response_model=BaseDataResponse)
async def create_flow(
    flow: FlowDefinition,
    user_id: str = Depends(get_current_user_id)
):
    """创建新的流程"""
    try:
        # 验证流程结构
        _validate_flow_structure(flow)
        
        # 设置创建者
        flow.created_by = user_id
        flow.created_at = datetime.now()
        flow.updated_at = datetime.now()
        
        # 保存流程定义（这里简化为内存存储）
        if not hasattr(dag_orchestrator, 'flow_definitions'):
            dag_orchestrator.flow_definitions = {}
        
        dag_orchestrator.flow_definitions[flow.id] = flow
        
        logger.info(f"Created flow {flow.id} by user {user_id}")
        
        return BaseDataResponse(
            success=True,
            data=flow.dict(),
            message="Flow created successfully"
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create flow: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/flows/{flow_id}", response_model=BaseDataResponse)
async def get_flow(flow_id: str):
    """获取流程定义"""
    try:
        if not hasattr(dag_orchestrator, 'flow_definitions'):
            dag_orchestrator.flow_definitions = {}
        
        if flow_id not in dag_orchestrator.flow_definitions:
            raise HTTPException(status_code=404, detail="Flow not found")
        
        flow = dag_orchestrator.flow_definitions[flow_id]
        
        return BaseDataResponse(
            success=True,
            data=flow.dict(),
            message="Successfully retrieved flow"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get flow: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/flows/{flow_id}", response_model=BaseDataResponse)
async def update_flow(
    flow_id: str,
    flow: FlowDefinition,
    user_id: str = Depends(get_current_user_id)
):
    """更新流程定义"""
    try:
        if not hasattr(dag_orchestrator, 'flow_definitions'):
            dag_orchestrator.flow_definitions = {}
        
        if flow_id not in dag_orchestrator.flow_definitions:
            raise HTTPException(status_code=404, detail="Flow not found")
        
        # 验证流程结构
        _validate_flow_structure(flow)
        
        # 更新时间
        flow.updated_at = datetime.now()
        flow.id = flow_id  # 确保ID一致
        
        # 保存更新
        dag_orchestrator.flow_definitions[flow_id] = flow
        
        logger.info(f"Updated flow {flow_id} by user {user_id}")
        
        return BaseDataResponse(
            success=True,
            data=flow.dict(),
            message="Flow updated successfully"
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update flow: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/flows/{flow_id}")
async def delete_flow(
    flow_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """删除流程"""
    try:
        if not hasattr(dag_orchestrator, 'flow_definitions'):
            dag_orchestrator.flow_definitions = {}
        
        if flow_id not in dag_orchestrator.flow_definitions:
            raise HTTPException(status_code=404, detail="Flow not found")
        
        # 删除流程
        del dag_orchestrator.flow_definitions[flow_id]
        
        logger.info(f"Deleted flow {flow_id} by user {user_id}")
        
        return BaseDataResponse(
            success=True,
            data=None,
            message="Flow deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete flow: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/flows", response_model=BaseDataResponse)
async def list_flows(
    user_id: str = Depends(get_current_user_id),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """获取流程列表"""
    try:
        if not hasattr(dag_orchestrator, 'flow_definitions'):
            dag_orchestrator.flow_definitions = {}
        
        flows = list(dag_orchestrator.flow_definitions.values())
        
        # 分页
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_flows = flows[start_idx:end_idx]
        
        # 简化响应数据
        flow_summaries = []
        for flow in paginated_flows:
            summary = {
                "id": flow.id,
                "name": flow.name,
                "description": flow.description,
                "version": flow.version,
                "node_count": len(flow.nodes),
                "connection_count": len(flow.connections),
                "tags": flow.tags,
                "created_by": flow.created_by,
                "created_at": flow.created_at.isoformat(),
                "updated_at": flow.updated_at.isoformat()
            }
            flow_summaries.append(summary)
        
        return BaseDataResponse(
            success=True,
            data={
                "flows": flow_summaries,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": len(flows),
                    "total_pages": (len(flows) + page_size - 1) // page_size
                }
            },
            message="Successfully retrieved flows"
        )
        
    except Exception as e:
        logger.error(f"Failed to list flows: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/flows/{flow_id}/execute", response_model=BaseDataResponse)
async def execute_flow(
    flow_id: str,
    request: FlowExecutionRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id)
):
    """执行流程"""
    try:
        if not hasattr(dag_orchestrator, 'flow_definitions'):
            dag_orchestrator.flow_definitions = {}
        
        if flow_id not in dag_orchestrator.flow_definitions:
            raise HTTPException(status_code=404, detail="Flow not found")
        
        flow = dag_orchestrator.flow_definitions[flow_id]
        
        # 创建执行实例
        execution_id = f"exec_{flow_id}_{int(datetime.now().timestamp())}"
        
        # 转换为DAG执行格式
        dag_template = _convert_flow_to_dag_template(flow)
        
        # 创建执行
        execution = await dag_orchestrator.create_execution(
            template_id=f"flow_{flow_id}",
            user_id=user_id,
            input_data=request.input_data,
            config_overrides=request.variables,
            custom_template=dag_template
        )
        
        if request.stream:
            # 后台执行
            background_tasks.add_task(_execute_flow_background, execution_id, flow_id)
            
            return BaseDataResponse(
                success=True,
                data={
                    "execution_id": execution_id,
                    "flow_id": flow_id,
                    "status": "started",
                    "stream": True,
                    "stream_url": f"/api/v1/orchestration/executions/{execution_id}/stream"
                },
                message="Flow execution started"
            )
        else:
            # 同步执行
            result = await dag_orchestrator.execute_dag(execution)
            
            status = FlowExecutionStatus(
                execution_id=execution_id,
                flow_id=flow_id,
                status=result.status,
                start_time=result.start_time,
                end_time=result.end_time,
                execution_path=result.execution_path,
                node_statuses=result.node_statuses,
                node_results=result.node_results,
                final_result=result.final_result,
                execution_time=(result.end_time - result.start_time).total_seconds() if result.end_time and result.start_time else None,
                total_nodes=len(flow.nodes),
                completed_nodes=len([s for s in result.node_statuses.values() if s == "completed"]),
                progress_percentage=100.0 if result.status == ExecutionStatus.COMPLETED else 0.0
            )
            
            return BaseDataResponse(
                success=True,
                data=status.dict(),
                message="Flow execution completed"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute flow: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/executions/{execution_id}/status", response_model=BaseDataResponse)
async def get_execution_status(execution_id: str):
    """获取执行状态"""
    try:
        if execution_id not in dag_orchestrator.executions:
            raise HTTPException(status_code=404, detail="Execution not found")
        
        execution = dag_orchestrator.executions[execution_id]
        
        # 计算进度
        total_nodes = len(execution.template.nodes) if hasattr(execution, 'template') else 0
        completed_nodes = len([s for s in execution.node_statuses.values() if s == "completed"])
        progress = (completed_nodes / total_nodes * 100) if total_nodes > 0 else 0
        
        status = FlowExecutionStatus(
            execution_id=execution_id,
            flow_id=getattr(execution, 'flow_id', 'unknown'),
            status=execution.status,
            start_time=execution.start_time,
            end_time=execution.end_time,
            execution_path=execution.execution_path,
            current_node=execution.current_node if hasattr(execution, 'current_node') else None,
            node_statuses=execution.node_statuses,
            node_results=execution.node_results,
            final_result=execution.final_result,
            error_message=execution.error_message if hasattr(execution, 'error_message') else None,
            execution_time=(execution.end_time - execution.start_time).total_seconds() if execution.end_time and execution.start_time else None,
            total_nodes=total_nodes,
            completed_nodes=completed_nodes,
            progress_percentage=progress
        )
        
        return BaseDataResponse(
            success=True,
            data=status.dict(),
            message="Successfully retrieved execution status"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get execution status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/executions/{execution_id}/stream")
async def stream_execution_results(execution_id: str):
    """流式获取执行结果"""
    async def generate_stream():
        try:
            if execution_id not in dag_orchestrator.executions:
                yield f"data: {json.dumps({'type': 'error', 'error': 'Execution not found'})}\n\n"
                return
            
            execution = dag_orchestrator.executions[execution_id]
            
            # 发送初始状态
            yield f"data: {json.dumps({'type': 'status', 'status': execution.status.value})}\n\n"
            
            # 监控执行过程
            last_path_length = 0
            
            while execution.status in [ExecutionStatus.PENDING, ExecutionStatus.RUNNING]:
                # 检查执行路径更新
                if len(execution.execution_path) > last_path_length:
                    new_nodes = execution.execution_path[last_path_length:]
                    for node_id in new_nodes:
                        message = StreamingMessage(
                            type="node_started",
                            data={"node_id": node_id}
                        )
                        yield f"data: {json.dumps(message.dict())}\n\n"
                    last_path_length = len(execution.execution_path)
                
                # 检查节点完成
                for node_id, status in execution.node_statuses.items():
                    if status == "completed" and node_id in execution.node_results:
                        message = StreamingMessage(
                            type="node_completed",
                            data={
                                "node_id": node_id,
                                "result": execution.node_results[node_id]
                            }
                        )
                        yield f"data: {json.dumps(message.dict())}\n\n"
                
                await asyncio.sleep(0.5)
            
            # 发送最终结果
            final_message = StreamingMessage(
                type="final_result",
                data={
                    "status": execution.status.value,
                    "result": execution.final_result,
                    "execution_path": execution.execution_path
                }
            )
            yield f"data: {json.dumps(final_message.dict())}\n\n"
            
        except Exception as e:
            error_message = StreamingMessage(
                type="error",
                data={"error": str(e)}
            )
            yield f"data: {json.dumps(error_message.dict())}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )

# 辅助函数
def _validate_flow_structure(flow: FlowDefinition):
    """验证流程结构"""
    if not flow.nodes:
        raise ValueError("Flow must have at least one node")
    
    node_ids = {node.id for node in flow.nodes}
    
    # 验证连接
    for conn in flow.connections:
        if conn.source not in node_ids:
            raise ValueError(f"Connection source node {conn.source} not found")
        if conn.target not in node_ids:
            raise ValueError(f"Connection target node {conn.target} not found")
    
    # 检查是否有输入和输出节点
    has_input = any(node.type == NodeType.INPUT for node in flow.nodes)
    has_output = any(node.type == NodeType.OUTPUT for node in flow.nodes)
    
    if not has_input and not has_output:
        logger.warning(f"Flow {flow.id} has no input or output nodes")

def _convert_flow_to_dag_template(flow: FlowDefinition) -> Dict[str, Any]:
    """将流程定义转换为DAG模板"""
    # 简化的转换逻辑
    nodes = []
    edges = []
    
    for node in flow.nodes:
        dag_node = {
            "id": node.id,
            "type": node.type.value,
            "name": node.name,
            "description": node.description,
            "config": node.config,
            "dependencies": [],
            "dependents": []
        }
        nodes.append(dag_node)
    
    for conn in flow.connections:
        edge = {
            "from_node": conn.source,
            "to_node": conn.target,
            "condition": conn.condition,
            "metadata": conn.metadata
        }
        edges.append(edge)
    
    return {
        "template_id": f"flow_{flow.id}",
        "name": flow.name,
        "description": flow.description,
        "nodes": nodes,
        "edges": edges,
        "variables": flow.variables,
        "version": flow.version
    }

async def _execute_flow_background(execution_id: str, flow_id: str):
    """后台执行流程"""
    try:
        await dag_orchestrator.execute_dag(execution_id)
    except Exception as e:
        logger.error(f"Background flow execution failed: {str(e)}")


# ====================== Workflow v2 API Routes ======================

def _get_current_user_id() -> str:
    """获取当前用户ID（模拟实现）"""
    # TODO: 从JWT token或session中获取真实用户ID
    return "system_user"


@router.post("/workflows-v2", response_model=WorkflowV2CreateResponse, tags=["workflow-v2"])
async def create_workflow_v2(
    config: WorkflowV2Config,
    user_id: str = Depends(_get_current_user_id)
):
    """
    创建Workflow v2工作流
    
    基于硅基流动API的新一代工作流系统，支持：
    - 纯Python配置式工作流
    - 硅基流动模型集成
    - 智能体协作编排
    - 实时代码生成
    """
    try:
        logger.info(f"Creating Workflow v2: {config.name} by user {user_id}")
        
        # 确保workflow_v2_manager已初始化
        if not workflow_v2_manager._initialized:
            await workflow_v2_manager.initialize()
        
        # 创建工作流
        workflow_id = await workflow_v2_manager.create_workflow_from_config(config)
        
        logger.info(f"Workflow v2 created successfully: {workflow_id}")
        
        return WorkflowV2CreateResponse(
            success=True,
            message="工作流创建成功",
            data={
                "workflow_id": workflow_id,
                "message": f"工作流 '{config.name}' 创建成功，使用硅基流动API"
            }
        )
        
    except ValueError as e:
        logger.error(f"Workflow v2 creation validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Workflow v2 creation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建工作流失败: {str(e)}")


@router.get("/workflows-v2/{workflow_id}", response_model=WorkflowV2DetailResponse, tags=["workflow-v2"])
async def get_workflow_v2(
    workflow_id: str,
    user_id: str = Depends(_get_current_user_id)
):
    """
    获取Workflow v2工作流详情
    """
    try:
        logger.info(f"Getting Workflow v2 details: {workflow_id}")
        
        config = await workflow_v2_manager.get_workflow_config(workflow_id)
        if not config:
            raise HTTPException(status_code=404, detail=f"工作流 {workflow_id} 不存在")
        
        return WorkflowV2DetailResponse(
            success=True,
            message="获取工作流详情成功",
            data=config
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get Workflow v2 failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取工作流详情失败: {str(e)}")


@router.put("/workflows-v2/{workflow_id}", response_model=WorkflowV2DetailResponse, tags=["workflow-v2"])
async def update_workflow_v2(
    workflow_id: str,
    updates: Dict[str, Any],
    user_id: str = Depends(_get_current_user_id)
):
    """
    更新Workflow v2工作流配置
    """
    try:
        logger.info(f"Updating Workflow v2: {workflow_id}")
        
        updated_config = await workflow_v2_manager.update_workflow_config(workflow_id, updates)
        
        return WorkflowV2DetailResponse(
            success=True,
            message="工作流更新成功",
            data=updated_config
        )
        
    except ValueError as e:
        logger.error(f"Workflow v2 update validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Update Workflow v2 failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"更新工作流失败: {str(e)}")


@router.delete("/workflows-v2/{workflow_id}", response_model=BaseDataResponse, tags=["workflow-v2"])
async def delete_workflow_v2(
    workflow_id: str,
    user_id: str = Depends(_get_current_user_id)
):
    """
    删除Workflow v2工作流
    """
    try:
        logger.info(f"Deleting Workflow v2: {workflow_id}")
        
        result = await workflow_v2_manager.delete_workflow(workflow_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"工作流 {workflow_id} 不存在")
        
        return BaseDataResponse(
            success=True,
            message="工作流删除成功",
            data={"workflow_id": workflow_id}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete Workflow v2 failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除工作流失败: {str(e)}")


@router.get("/workflows-v2", response_model=WorkflowV2ListResponse, tags=["workflow-v2"])
async def list_workflows_v2(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页大小"),
    category: Optional[str] = Query(None, description="分类筛选"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    user_id: str = Depends(_get_current_user_id)
):
    """
    获取Workflow v2工作流列表
    """
    try:
        logger.info(f"Listing Workflow v2s - page: {page}, size: {size}")
        
        workflows = await workflow_v2_manager.list_workflows()
        
        # 简单的搜索过滤
        if search:
            search_lower = search.lower()
            workflows = [
                w for w in workflows 
                if search_lower in w.name.lower() or search_lower in w.description.lower()
            ]
        
        # 分类过滤
        if category:
            workflows = [w for w in workflows if w.category == category]
        
        # 分页
        total = len(workflows)
        start_idx = (page - 1) * size
        end_idx = start_idx + size
        paginated_workflows = workflows[start_idx:end_idx]
        
        # 转换为摘要格式
        workflow_summaries = []
        for w in paginated_workflows:
            summary = WorkflowV2Summary(
                id=w.id or "",
                name=w.name,
                description=w.description,
                version=w.version,
                category=w.category,
                tags=w.tags,
                agent_count=len(w.components.agents),
                step_count=len(w.logic.steps),
                status="active",
                created_at=w.created_at,
                updated_at=w.updated_at
            )
            workflow_summaries.append(summary.dict())
        
        pages = (total + size - 1) // size
        
        return WorkflowV2ListResponse(
            success=True,
            message="获取工作流列表成功",
            data={
                "workflows": workflow_summaries,
                "total": total,
                "page": page,
                "size": size,
                "pages": pages
            }
        )
        
    except Exception as e:
        logger.error(f"List Workflow v2s failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取工作流列表失败: {str(e)}")


@router.post("/workflows-v2/{workflow_id}/execute", response_model=WorkflowV2ExecutionResponse, tags=["workflow-v2"])
async def execute_workflow_v2(
    workflow_id: str,
    request: WorkflowV2ExecutionRequest,
    user_id: str = Depends(_get_current_user_id)
):
    """
    执行Workflow v2工作流
    
    支持同步、异步和流式执行模式
    """
    try:
        logger.info(f"Executing Workflow v2: {workflow_id} with mode: {request.execution_mode}")
        
        # 执行工作流
        result = await workflow_v2_manager.execute_workflow(
            workflow_id=workflow_id,
            input_data=request.input_data,
            stream=request.stream
        )
        
        return WorkflowV2ExecutionResponse(
            success=True,
            message="工作流执行成功",
            data=result
        )
        
    except ValueError as e:
        logger.error(f"Workflow v2 execution validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Execute Workflow v2 failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"执行工作流失败: {str(e)}")


@router.get("/workflows-v2/{workflow_id}/execute/{execution_id}", response_model=WorkflowV2ExecutionResponse, tags=["workflow-v2"])
async def get_execution_result_v2(
    workflow_id: str,
    execution_id: str,
    user_id: str = Depends(_get_current_user_id)
):
    """
    获取Workflow v2执行结果
    """
    try:
        logger.info(f"Getting execution result: {execution_id}")
        
        # 从管理器中获取执行结果
        result = workflow_v2_manager.execution_results.get(execution_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"执行记录 {execution_id} 不存在")
        
        return WorkflowV2ExecutionResponse(
            success=True,
            message="获取执行结果成功",
            data=result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get execution result failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取执行结果失败: {str(e)}")


@router.get("/workflows-v2/{workflow_id}/execute/{execution_id}/stream", tags=["workflow-v2"])
async def stream_execution_v2(
    workflow_id: str,
    execution_id: str,
    user_id: str = Depends(_get_current_user_id)
):
    """
    流式获取Workflow v2执行过程
    """
    async def generate_stream():
        """生成执行流数据"""
        try:
            # 模拟流式输出
            yield f"data: {json.dumps({'event_type': 'execution_start', 'execution_id': execution_id, 'timestamp': datetime.now().isoformat()})}\n\n"
            
            # 获取执行结果
            result = workflow_v2_manager.execution_results.get(execution_id)
            if result:
                # 输出步骤结果
                for step_id, step_result in result.steps_results.items():
                    yield f"data: {json.dumps({'event_type': 'step_completed', 'step_id': step_id, 'result': str(step_result), 'timestamp': datetime.now().isoformat()})}\n\n"
                
                # 输出最终结果
                yield f"data: {json.dumps({'event_type': 'execution_completed', 'status': result.status, 'result': str(result.result), 'timestamp': datetime.now().isoformat()})}\n\n"
            else:
                yield f"data: {json.dumps({'event_type': 'error', 'message': 'Execution not found', 'timestamp': datetime.now().isoformat()})}\n\n"
            
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error(f"Stream execution failed: {str(e)}")
            yield f"data: {json.dumps({'event_type': 'error', 'message': str(e), 'timestamp': datetime.now().isoformat()})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )


@router.get("/workflows-v2/{workflow_id}/code", response_model=WorkflowV2CodeResponse, tags=["workflow-v2"])
async def get_workflow_code_v2(
    workflow_id: str,
    include_comments: bool = Query(True, description="是否包含注释"),
    user_id: str = Depends(_get_current_user_id)
):
    """
    获取Workflow v2生成的Python代码
    """
    try:
        logger.info(f"Getting Workflow v2 code: {workflow_id}")
        
        # 生成Python代码
        python_code = await workflow_v2_manager.generate_workflow_code(workflow_id)
        
        # 验证代码
        validation_result = workflow_v2_manager.code_generator.validate_generated_code(python_code)
        
        result = WorkflowV2CodeGenerationResult(
            workflow_id=workflow_id,
            generated_code=python_code,
            validation_result=validation_result,
            file_path=f"workflow_{workflow_id}.py"
        )
        
        return WorkflowV2CodeResponse(
            success=True,
            message="获取工作流代码成功",
            data=result
        )
        
    except ValueError as e:
        logger.error(f"Workflow v2 code generation validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Get Workflow v2 code failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取工作流代码失败: {str(e)}")


@router.post("/workflows-v2/{workflow_id}/code/regenerate", response_model=WorkflowV2CodeResponse, tags=["workflow-v2"])
async def regenerate_workflow_code_v2(
    workflow_id: str,
    request: WorkflowV2CodeGenerationRequest,
    user_id: str = Depends(_get_current_user_id)
):
    """
    重新生成Workflow v2的Python代码
    """
    try:
        logger.info(f"Regenerating Workflow v2 code: {workflow_id}")
        
        # 获取工作流配置
        config = await workflow_v2_manager.get_workflow_config(workflow_id)
        if not config:
            raise HTTPException(status_code=404, detail=f"工作流 {workflow_id} 不存在")
        
        # 重新生成代码
        python_code = workflow_v2_manager.code_generator.generate_workflow_code(config)
        
        # 验证代码
        validation_result = workflow_v2_manager.code_generator.validate_generated_code(python_code)
        
        # 保存更新的代码
        await workflow_v2_manager._save_workflow_config(config, python_code)
        
        result = WorkflowV2CodeGenerationResult(
            workflow_id=workflow_id,
            generated_code=python_code,
            validation_result=validation_result,
            file_path=f"workflow_{workflow_id}.py"
        )
        
        return WorkflowV2CodeResponse(
            success=True,
            message="重新生成工作流代码成功",
            data=result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Regenerate Workflow v2 code failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"重新生成工作流代码失败: {str(e)}")


# 配置相关接口
@router.get("/workflows-v2/models/available", response_model=BaseDataResponse, tags=["workflow-v2"])
async def get_available_models_v2():
    """
    获取可用的硅基流动模型列表
    """
    try:
        from ..config.siliconflow_config import siliconflow_config
        
        models = []
        for model_config in siliconflow_config.available_models:
            models.append({
                "model_id": model_config.model_id,
                "model_name": model_config.model_name,
                "model_type": model_config.model_type.value,
                "description": model_config.description,
                "max_tokens": model_config.max_tokens,
                "context_window": model_config.context_window,
                "supports_streaming": model_config.supports_streaming,
                "supports_function_calling": model_config.supports_function_calling,
                "pricing": model_config.pricing
            })
        
        return BaseDataResponse(
            success=True,
            message="获取可用模型列表成功",
            data={
                "models": models,
                "default_chat_model": siliconflow_config.default_chat_model,
                "default_embedding_model": siliconflow_config.default_embedding_model,
                "default_rerank_model": siliconflow_config.default_rerank_model
            }
        )
        
    except Exception as e:
        logger.error(f"Get available models failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取可用模型失败: {str(e)}")


@router.get("/workflows-v2/tools/available", response_model=BaseDataResponse, tags=["workflow-v2"])
async def get_available_tools_v2():
    """
    获取可用的工具列表
    """
    try:
        tools = [
            {
                "id": "reasoning",
                "name": "推理工具",
                "description": "提供逻辑推理和分析能力",
                "type": "builtin"
            },
            {
                "id": "search",
                "name": "搜索工具",
                "description": "提供信息检索和搜索能力",
                "type": "builtin"
            },
            {
                "id": "calculator",
                "name": "计算器工具",
                "description": "提供数学计算能力",
                "type": "builtin"
            },
            {
                "id": "file",
                "name": "文件工具",
                "description": "提供文件读写和管理能力",
                "type": "builtin"
            },
            {
                "id": "web_search",
                "name": "网络搜索工具",
                "description": "提供网络信息搜索能力",
                "type": "builtin"
            }
        ]
        
        return BaseDataResponse(
            success=True,
            message="获取可用工具列表成功",
            data={"tools": tools}
        )
        
    except Exception as e:
        logger.error(f"Get available tools failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取可用工具失败: {str(e)}")