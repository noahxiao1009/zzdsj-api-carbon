"""
智能体服务API接口
支持智能体的创建、管理、配置和对话功能
"""

from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any, Optional
import logging
import json
import asyncio
from datetime import datetime

from app.schemas.agent_schemas import (
    AgentCreateRequest,
    AgentUpdateRequest,
    AgentResponse,
    AgentListResponse,
    ChatRequest,
    ChatResponse,
    StreamChatResponse,
    FlowDesignRequest,
    FlowDesignResponse,
    AgentConfigRequest,
    AgentConfigResponse,
    AgentStatsResponse,
    TemplateResponse,
    WorkflowExecutionRequest,
    WorkflowExecutionResponse
)
from app.services.agent_service import AgentService
from app.services.template_service import TemplateService
from app.services.workflow_service import WorkflowService
from app.core.auth_dependencies import get_current_user
from app.core.exceptions import AgentNotFoundError, InvalidConfigurationError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/agents", tags=["智能体管理"])

# 依赖注入
def get_agent_service() -> AgentService:
    return AgentService()

def get_template_service() -> TemplateService:
    return TemplateService()

def get_workflow_service() -> WorkflowService:
    return WorkflowService()


# ==================== 智能体模板相关接口 ====================

@router.get("/templates", response_model=List[TemplateResponse])
async def get_agent_templates(
    category: Optional[str] = None,
    template_service: TemplateService = Depends(get_template_service)
):
    """
    获取智能体模板列表
    支持按分类筛选：simple-qa, deep-thinking, intelligent-planning
    """
    try:
        templates = await template_service.get_templates(category=category)
        return templates
    except Exception as e:
        logger.error(f"获取模板列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取模板列表失败: {str(e)}"
        )

@router.get("/templates/{template_id}", response_model=TemplateResponse)
async def get_agent_template(
    template_id: str,
    template_service: TemplateService = Depends(get_template_service)
):
    """获取指定模板详情"""
    try:
        template = await template_service.get_template(template_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"模板 {template_id} 不存在"
            )
        return template
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取模板详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取模板详情失败: {str(e)}"
        )


# ==================== 智能体CRUD接口 ====================

@router.post("/create", response_model=AgentResponse)
async def create_agent(
    request: AgentCreateRequest,
    background_tasks: BackgroundTasks,
    agent_service: AgentService = Depends(get_agent_service),
    current_user: dict = Depends(get_current_user)
):
    """
    创建智能体
    支持基于模板的快速创建和自定义配置
    """
    try:
        # 验证配置
        await agent_service.validate_agent_config(request)
        
        # 创建智能体
        agent = await agent_service.create_agent(
            config=request.dict(),
            user_id=current_user["user_id"]
        )
        
        # 后台任务：初始化智能体
        background_tasks.add_task(
            agent_service.initialize_agent,
            agent["agent_id"]
        )
        
        return agent
        
    except InvalidConfigurationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"配置无效: {str(e)}"
        )
    except Exception as e:
        logger.error(f"创建智能体失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建智能体失败: {str(e)}"
        )

@router.get("/", response_model=AgentListResponse)
async def get_agents(
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    status_filter: Optional[str] = None,
    agent_service: AgentService = Depends(get_agent_service),
    current_user: dict = Depends(get_current_user)
):
    """获取智能体列表"""
    try:
        agents_data = await agent_service.get_agents(
            user_id=current_user["user_id"],
            page=page,
            page_size=page_size,
            search=search,
            status_filter=status_filter
        )
        return agents_data
    except Exception as e:
        logger.error(f"获取智能体列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取智能体列表失败: {str(e)}"
        )

@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    agent_service: AgentService = Depends(get_agent_service),
    current_user: dict = Depends(get_current_user)
):
    """获取智能体详情"""
    try:
        agent = await agent_service.get_agent(agent_id, current_user["user_id"])
        if not agent:
            raise AgentNotFoundError(f"智能体 {agent_id} 不存在")
        return agent
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"智能体 {agent_id} 不存在"
        )
    except Exception as e:
        logger.error(f"获取智能体详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取智能体详情失败: {str(e)}"
        )

@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    request: AgentUpdateRequest,
    agent_service: AgentService = Depends(get_agent_service),
    current_user: dict = Depends(get_current_user)
):
    """更新智能体配置"""
    try:
        agent = await agent_service.update_agent(
            agent_id=agent_id,
            config=request.dict(exclude_unset=True),
            user_id=current_user["user_id"]
        )
        return agent
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"智能体 {agent_id} 不存在"
        )
    except Exception as e:
        logger.error(f"更新智能体失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新智能体失败: {str(e)}"
        )

@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    agent_service: AgentService = Depends(get_agent_service),
    current_user: dict = Depends(get_current_user)
):
    """删除智能体"""
    try:
        success = await agent_service.delete_agent(agent_id, current_user["user_id"])
        if not success:
            raise AgentNotFoundError(f"智能体 {agent_id} 不存在")
        return {"message": "智能体删除成功"}
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"智能体 {agent_id} 不存在"
        )
    except Exception as e:
        logger.error(f"删除智能体失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除智能体失败: {str(e)}"
        )


# ==================== 智能体对话接口 ====================

@router.post("/{agent_id}/chat", response_model=ChatResponse)
async def chat_with_agent(
    agent_id: str,
    request: ChatRequest,
    agent_service: AgentService = Depends(get_agent_service),
    current_user: dict = Depends(get_current_user)
):
    """与智能体对话（非流式）"""
    try:
        response = await agent_service.chat(
            agent_id=agent_id,
            message=request.message,
            session_id=request.session_id,
            context=request.context,
            user_id=current_user["user_id"]
        )
        return response
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"智能体 {agent_id} 不存在"
        )
    except Exception as e:
        logger.error(f"对话失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"对话失败: {str(e)}"
        )

@router.post("/{agent_id}/chat/stream")
async def stream_chat_with_agent(
    agent_id: str,
    request: ChatRequest,
    agent_service: AgentService = Depends(get_agent_service),
    current_user: dict = Depends(get_current_user)
):
    """与智能体对话（流式）"""
    try:
        async def generate_stream():
            async for chunk in agent_service.stream_chat(
                agent_id=agent_id,
                message=request.message,
                session_id=request.session_id,
                context=request.context,
                user_id=current_user["user_id"]
            ):
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/plain",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"智能体 {agent_id} 不存在"
        )
    except Exception as e:
        logger.error(f"流式对话失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"流式对话失败: {str(e)}"
        )


# ==================== 智能体配置接口 ====================

@router.post("/{agent_id}/config", response_model=AgentConfigResponse)
async def update_agent_config(
    agent_id: str,
    request: AgentConfigRequest,
    agent_service: AgentService = Depends(get_agent_service),
    current_user: dict = Depends(get_current_user)
):
    """更新智能体详细配置"""
    try:
        config = await agent_service.update_agent_config(
            agent_id=agent_id,
            config=request.dict(),
            user_id=current_user["user_id"]
        )
        return config
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"智能体 {agent_id} 不存在"
        )
    except Exception as e:
        logger.error(f"更新配置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新配置失败: {str(e)}"
        )

@router.get("/{agent_id}/config", response_model=AgentConfigResponse)
async def get_agent_config(
    agent_id: str,
    agent_service: AgentService = Depends(get_agent_service),
    current_user: dict = Depends(get_current_user)
):
    """获取智能体详细配置"""
    try:
        config = await agent_service.get_agent_config(agent_id, current_user["user_id"])
        return config
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"智能体 {agent_id} 不存在"
        )
    except Exception as e:
        logger.error(f"获取配置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取配置失败: {str(e)}"
        )


# ==================== 工作流设计接口 ====================

@router.post("/{agent_id}/flow/design", response_model=FlowDesignResponse)
async def design_agent_flow(
    agent_id: str,
    request: FlowDesignRequest,
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_user: dict = Depends(get_current_user)
):
    """设计智能体工作流"""
    try:
        flow = await workflow_service.design_flow(
            agent_id=agent_id,
            flow_config=request.dict(),
            user_id=current_user["user_id"]
        )
        return flow
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"智能体 {agent_id} 不存在"
        )
    except Exception as e:
        logger.error(f"设计工作流失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"设计工作流失败: {str(e)}"
        )

@router.get("/{agent_id}/flow", response_model=FlowDesignResponse)
async def get_agent_flow(
    agent_id: str,
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_user: dict = Depends(get_current_user)
):
    """获取智能体工作流设计"""
    try:
        flow = await workflow_service.get_flow(agent_id, current_user["user_id"])
        return flow
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"智能体 {agent_id} 不存在"
        )
    except Exception as e:
        logger.error(f"获取工作流失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取工作流失败: {str(e)}"
        )

@router.post("/{agent_id}/flow/execute", response_model=WorkflowExecutionResponse)
async def execute_agent_workflow(
    agent_id: str,
    request: WorkflowExecutionRequest,
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_user: dict = Depends(get_current_user)
):
    """执行智能体工作流"""
    try:
        result = await workflow_service.execute_workflow(
            agent_id=agent_id,
            input_data=request.dict(),
            user_id=current_user["user_id"]
        )
        return result
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"智能体 {agent_id} 不存在"
        )
    except Exception as e:
        logger.error(f"执行工作流失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"执行工作流失败: {str(e)}"
        )


# ==================== 统计和监控接口 ====================

@router.get("/{agent_id}/stats", response_model=AgentStatsResponse)
async def get_agent_stats(
    agent_id: str,
    period: str = "7d",  # 1d, 7d, 30d
    agent_service: AgentService = Depends(get_agent_service),
    current_user: dict = Depends(get_current_user)
):
    """获取智能体使用统计"""
    try:
        stats = await agent_service.get_agent_stats(
            agent_id=agent_id,
            period=period,
            user_id=current_user["user_id"]
        )
        return stats
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"智能体 {agent_id} 不存在"
        )
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取统计信息失败: {str(e)}"
        )

@router.post("/{agent_id}/test")
async def test_agent(
    agent_id: str,
    test_message: str,
    agent_service: AgentService = Depends(get_agent_service),
    current_user: dict = Depends(get_current_user)
):
    """测试智能体"""
    try:
        result = await agent_service.test_agent(
            agent_id=agent_id,
            test_message=test_message,
            user_id=current_user["user_id"]
        )
        return result
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"智能体 {agent_id} 不存在"
        )
    except Exception as e:
        logger.error(f"测试智能体失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"测试智能体失败: {str(e)}"
        )

@router.post("/{agent_id}/status/{action}")
async def change_agent_status(
    agent_id: str,
    action: str,  # activate, deactivate, pause, resume
    agent_service: AgentService = Depends(get_agent_service),
    current_user: dict = Depends(get_current_user)
):
    """更改智能体状态"""
    try:
        if action not in ["activate", "deactivate", "pause", "resume"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无效的操作类型"
            )
        
        result = await agent_service.change_agent_status(
            agent_id=agent_id,
            action=action,
            user_id=current_user["user_id"]
        )
        return result
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"智能体 {agent_id} 不存在"
        )
    except Exception as e:
        logger.error(f"更改智能体状态失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更改智能体状态失败: {str(e)}"
        ) 