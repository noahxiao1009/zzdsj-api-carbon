"""
Flow Builder API路由
支持前端智能体编排页面的所有功能
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import logging
from datetime import datetime

from ..core.dag_orchestrator import dag_orchestrator, DAGExecution, ExecutionStatus
from ..core.agno_api_manager import agno_manager
from ..schemas.flow_builder_schemas import (
    TemplateListResponse,
    TemplateDetailResponse,
    AgentCreationRequest,
    AgentCreationResponse,
    ExecutionRequest,
    ExecutionResponse,
    ExecutionStatusResponse,
    StreamingExecutionResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/flow-builder", tags=["flow-builder"])

# 依赖注入函数
async def get_current_user_id() -> str:
    """获取当前用户ID（简化实现）"""
    # 在实际应用中，这里应该从JWT token或session中获取用户ID
    return "user_123"

@router.get("/templates", response_model=TemplateListResponse)
async def list_templates():
    """获取可用的智能体模版列表"""
    try:
        templates = dag_orchestrator.get_available_templates()
        
        # 添加推荐信息
        for template in templates:
            if template["template_id"] == "basic_conversation":
                template["recommended"] = True
                template["use_cases"] = ["客户服务", "日常咨询", "快速问答"]
                template["estimated_cost"] = "低"
            elif template["template_id"] == "knowledge_base":
                template["recommended"] = False
                template["use_cases"] = ["技术支持", "产品咨询", "政策解读"]
                template["estimated_cost"] = "中"
            elif template["template_id"] == "deep_thinking":
                template["recommended"] = False
                template["use_cases"] = ["战略分析", "复杂决策", "研究报告"]
                template["estimated_cost"] = "高"
        
        return TemplateListResponse(
            success=True,
            data=templates,
            message="Successfully retrieved templates"
        )
        
    except Exception as e:
        logger.error(f"Failed to list templates: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/templates/{template_id}", response_model=TemplateDetailResponse)
async def get_template_detail(template_id: str):
    """获取模版详细信息"""
    try:
        template_detail = dag_orchestrator.get_template_detail(template_id)
        
        # 添加前端需要的额外信息
        if template_id == "basic_conversation":
            template_detail["features"] = [
                "毫秒级响应速度",
                "直接准确回答", 
                "轻量化架构",
                "高并发支持",
                "成本效益优化"
            ]
            template_detail["agentType"] = "simple-qa"
            template_detail["color"] = "#3b82f6"
            template_detail["gradient"] = "linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)"
            
        elif template_id == "knowledge_base":
            template_detail["features"] = [
                "知识库检索增强",
                "引用和溯源",
                "多格式文档支持",
                "智能相关性评分",
                "专业准确回答"
            ]
            template_detail["agentType"] = "knowledge-qa"
            template_detail["color"] = "#8b5cf6"
            template_detail["gradient"] = "linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)"
            
        elif template_id == "deep_thinking":
            template_detail["features"] = [
                "多步骤推理链",
                "团队协作能力",
                "深度分析洞察",
                "创新解决方案",
                "质量检查机制"
            ]
            template_detail["agentType"] = "deep-thinking"
            template_detail["color"] = "#10b981"
            template_detail["gradient"] = "linear-gradient(135deg, #10b981 0%, #059669 100%)"
        
        return TemplateDetailResponse(
            success=True,
            data=template_detail,
            message="Successfully retrieved template detail"
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get template detail: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/agents", response_model=AgentCreationResponse)
async def create_agent_from_template(
    request: AgentCreationRequest,
    user_id: str = Depends(get_current_user_id)
):
    """基于模版创建智能体"""
    try:
        # 验证模版存在
        if request.template_id not in dag_orchestrator.templates:
            raise HTTPException(status_code=404, detail=f"Template {request.template_id} not found")
        
        template = dag_orchestrator.templates[request.template_id]
        
        # 解析前端配置
        basic_config = request.configuration.get("basic_configuration", {})
        model_config = request.configuration.get("model_configuration", {})
        capability_config = request.configuration.get("capability_configuration", {})
        advanced_config = request.configuration.get("advanced_configuration", {})
        
        # 构建智能体配置
        agent_name = basic_config.get("agent_name", template.name)
        agent_description = basic_config.get("description", template.description)
        
        # 模型配置
        model_name = model_config.get("model_name", "claude-3-5-sonnet")
        temperature = model_config.get("temperature", 0.7)
        max_tokens = model_config.get("max_tokens", 1000)
        
        # 工具配置
        enabled_tools = capability_config.get("enabled_tools", [])
        knowledge_base_ids = capability_config.get("knowledge_base_ids", [])
        
        # 创建DAG执行配置
        input_data = {
            "agent_name": agent_name,
            "agent_description": agent_description,
            "model_config": {
                "model_name": model_name,
                "temperature": temperature,
                "max_tokens": max_tokens
            },
            "tools": enabled_tools,
            "knowledge_base_ids": knowledge_base_ids,
            "user_preferences": advanced_config
        }
        
        # 配置覆盖
        config_overrides = {
            "model_name": model_name,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "enabled_tools": enabled_tools
        }
        
        # 创建执行实例
        execution_id = await dag_orchestrator.create_execution(
            template_id=request.template_id,
            user_id=user_id,
            input_data=input_data,
            config_overrides=config_overrides
        )
        
        # 生成智能体ID（基于执行ID）
        agent_id = f"agent_{execution_id}"
        
        logger.info(f"Created agent {agent_id} from template {request.template_id}")
        
        return AgentCreationResponse(
            success=True,
            data={
                "agent_id": agent_id,
                "execution_id": execution_id,
                "template_id": request.template_id,
                "name": agent_name,
                "description": agent_description,
                "status": "created",
                "created_at": datetime.now().isoformat()
            },
            message="Agent created successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create agent: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/agents/{agent_id}/execute", response_model=ExecutionResponse)
async def execute_agent(
    agent_id: str,
    request: ExecutionRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id)
):
    """执行智能体"""
    try:
        # 从agent_id提取execution_id
        if not agent_id.startswith("agent_"):
            raise HTTPException(status_code=400, detail="Invalid agent ID format")
        
        execution_id = agent_id.replace("agent_", "")
        
        if execution_id not in dag_orchestrator.executions:
            raise HTTPException(status_code=404, detail="Agent execution not found")
        
        execution = dag_orchestrator.executions[execution_id]
        
        # 更新输入数据
        if request.message:
            execution.input_data["message"] = request.message
            execution.input_data["user_id"] = user_id
        
        if request.additional_context:
            execution.input_data.update(request.additional_context)
        
        # 检查是否需要流式响应
        if request.stream:
            # 启动后台任务执行DAG
            background_tasks.add_task(_execute_dag_background, execution_id)
            
            return ExecutionResponse(
                success=True,
                data={
                    "execution_id": execution_id,
                    "status": "started",
                    "stream": True,
                    "stream_url": f"/api/v1/flow-builder/executions/{execution_id}/stream"
                },
                message="Execution started in streaming mode"
            )
        else:
            # 同步执行
            result = await dag_orchestrator.execute_dag(execution_id)
            
            return ExecutionResponse(
                success=True,
                data={
                    "execution_id": execution_id,
                    "status": result.status.value,
                    "result": result.final_result,
                    "execution_path": result.execution_path,
                    "execution_time": (result.end_time - result.start_time).total_seconds() if result.end_time and result.start_time else None
                },
                message="Execution completed"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute agent: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def _execute_dag_background(execution_id: str):
    """后台执行DAG"""
    try:
        await dag_orchestrator.execute_dag(execution_id)
    except Exception as e:
        logger.error(f"Background DAG execution failed: {str(e)}")

@router.get("/executions/{execution_id}/status", response_model=ExecutionStatusResponse)
async def get_execution_status(execution_id: str):
    """获取执行状态"""
    try:
        status = await dag_orchestrator.get_execution_status(execution_id)
        
        return ExecutionStatusResponse(
            success=True,
            data=status,
            message="Successfully retrieved execution status"
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get execution status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/executions/{execution_id}/stream")
async def stream_execution_results(execution_id: str):
    """流式获取执行结果"""
    from fastapi.responses import StreamingResponse
    import json
    import asyncio
    
    async def generate_stream():
        """生成流式响应"""
        try:
            if execution_id not in dag_orchestrator.executions:
                yield f"data: {json.dumps({'error': 'Execution not found'})}\n\n"
                return
            
            execution = dag_orchestrator.executions[execution_id]
            
            # 发送初始状态
            yield f"data: {json.dumps({'type': 'status', 'status': execution.status.value})}\n\n"
            
            # 等待执行开始
            while execution.status == ExecutionStatus.PENDING:
                await asyncio.sleep(0.1)
            
            # 流式发送执行过程
            last_path_length = 0
            
            while execution.status == ExecutionStatus.RUNNING:
                # 检查执行路径更新
                if len(execution.execution_path) > last_path_length:
                    new_nodes = execution.execution_path[last_path_length:]
                    for node_id in new_nodes:
                        yield f"data: {json.dumps({'type': 'node_completed', 'node_id': node_id})}\n\n"
                    last_path_length = len(execution.execution_path)
                
                # 检查节点状态更新
                for node_id, status in execution.node_statuses.items():
                    if status == ExecutionStatus.COMPLETED and node_id in execution.node_results:
                        result = execution.node_results[node_id]
                        if isinstance(result, dict) and "response" in result:
                            yield f"data: {json.dumps({'type': 'node_result', 'node_id': node_id, 'result': result['response']})}\n\n"
                
                await asyncio.sleep(0.5)
            
            # 发送最终结果
            final_status = {
                'type': 'final_result',
                'status': execution.status.value,
                'result': execution.final_result,
                'execution_path': execution.execution_path
            }
            
            yield f"data: {json.dumps(final_status)}\n\n"
            
        except Exception as e:
            error_msg = {'type': 'error', 'error': str(e)}
            yield f"data: {json.dumps(error_msg)}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )

@router.get("/agents/{agent_id}/chat/history")
async def get_chat_history(
    agent_id: str,
    limit: int = 50,
    user_id: str = Depends(get_current_user_id)
):
    """获取智能体对话历史"""
    try:
        # 从agent_id提取execution_id
        execution_id = agent_id.replace("agent_", "")
        
        if execution_id not in dag_orchestrator.executions:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        execution = dag_orchestrator.executions[execution_id]
        
        # 构建对话历史
        chat_history = []
        
        # 添加输入消息
        if "message" in execution.input_data:
            chat_history.append({
                "role": "user",
                "content": execution.input_data["message"],
                "timestamp": execution.start_time.isoformat() if execution.start_time else datetime.now().isoformat()
            })
        
        # 添加最终回复
        if execution.final_result:
            content = execution.final_result
            if isinstance(content, dict):
                content = content.get("response", str(content))
            
            chat_history.append({
                "role": "assistant", 
                "content": str(content),
                "timestamp": execution.end_time.isoformat() if execution.end_time else datetime.now().isoformat()
            })
        
        return {
            "success": True,
            "data": {
                "agent_id": agent_id,
                "chat_history": chat_history[-limit:],  # 限制返回数量
                "total_messages": len(chat_history)
            },
            "message": "Successfully retrieved chat history"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get chat history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/agents/{agent_id}")
async def delete_agent(
    agent_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """删除智能体"""
    try:
        # 从agent_id提取execution_id
        execution_id = agent_id.replace("agent_", "")
        
        if execution_id not in dag_orchestrator.executions:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        # 删除执行实例
        del dag_orchestrator.executions[execution_id]
        
        # 从运行列表中移除（如果存在）
        dag_orchestrator.running_executions.discard(execution_id)
        
        logger.info(f"Deleted agent {agent_id}")
        
        return {
            "success": True,
            "message": "Agent deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete agent: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models")
async def get_available_models():
    """获取可用模型列表"""
    try:
        models = agno_manager.get_available_models()
        
        # 添加前端需要的模型信息
        enhanced_models = []
        for model in models:
            enhanced_model = {
                **model,
                "recommended": model["name"] in ["claude-3-5-sonnet", "gpt-4o"],
                "capabilities": ["text", "reasoning"],
                "context_length": 128000 if "claude" in model["name"] else 8192,
                "cost_tier": "medium"
            }
            
            if "claude-3-5-sonnet" == model["name"]:
                enhanced_model["recommended"] = True
                enhanced_model["cost_tier"] = "high"
                enhanced_model["description"] = "最新的Claude模型，平衡性能与成本"
            elif "claude-3-haiku" == model["name"]:
                enhanced_model["cost_tier"] = "low"
                enhanced_model["description"] = "快速响应的轻量级模型"
            elif "gpt-4o" == model["name"]:
                enhanced_model["recommended"] = True
                enhanced_model["cost_tier"] = "high"
                enhanced_model["description"] = "OpenAI最新的多模态模型"
            elif "gpt-4o-mini" == model["name"]:
                enhanced_model["cost_tier"] = "low"
                enhanced_model["description"] = "成本优化的GPT-4模型"
            
            enhanced_models.append(enhanced_model)
        
        return {
            "success": True,
            "data": enhanced_models,
            "message": "Successfully retrieved available models"
        }
        
    except Exception as e:
        logger.error(f"Failed to get available models: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tools")
async def get_available_tools():
    """获取可用工具列表"""
    try:
        tools = agno_manager.get_available_tools()
        
        # 添加工具分类和描述
        enhanced_tools = []
        for tool in tools:
            enhanced_tool = {
                **tool,
                "enabled": True,
                "required": False
            }
            
            # 根据工具名称添加详细信息
            if tool["name"] == "reasoning":
                enhanced_tool.update({
                    "display_name": "推理工具",
                    "description": "提供逻辑推理和分析能力",
                    "category": "reasoning",
                    "icon": "🧠"
                })
            elif tool["name"] == "search":
                enhanced_tool.update({
                    "display_name": "搜索工具",
                    "description": "搜索和检索信息",
                    "category": "search",
                    "icon": "🔍"
                })
            elif tool["name"] == "calculator":
                enhanced_tool.update({
                    "display_name": "计算器",
                    "description": "执行数学计算",
                    "category": "calculation",
                    "icon": "🧮"
                })
            elif tool["name"] == "web_search":
                enhanced_tool.update({
                    "display_name": "网络搜索",
                    "description": "搜索互联网信息",
                    "category": "search",
                    "icon": "🌐"
                })
            elif tool["name"] == "file_tools":
                enhanced_tool.update({
                    "display_name": "文件工具",
                    "description": "文件读取和处理",
                    "category": "file",
                    "icon": "📁"
                })
            
            enhanced_tools.append(enhanced_tool)
        
        return {
            "success": True,
            "data": enhanced_tools,
            "message": "Successfully retrieved available tools"
        }
        
    except Exception as e:
        logger.error(f"Failed to get available tools: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "flow-builder",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "dag_orchestrator": "active",
            "agno_manager": "active",
            "templates_count": len(dag_orchestrator.templates),
            "active_executions": len(dag_orchestrator.running_executions)
        }
    }