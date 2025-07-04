"""
智能体管理API路由
完全基于原ZZDSJ项目的智能体设计和Agno官方API接口
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query, Path, BackgroundTasks
from fastapi.responses import StreamingResponse

from app.schemas.agent_schemas import (
    AgentCreateRequest, AgentResponse, 
    ChatRequest, ChatResponse, TemplateType,
    TeamCreateRequest, TeamResponse,
    ModelProvider
)
from app.core.agno_manager import get_agno_manager

router = APIRouter(prefix="/agents", tags=["智能体管理"])
logger = logging.getLogger(__name__)

# ===== 智能体模板相关 =====

@router.get("/templates", 
           summary="获取智能体模板列表",
           description="获取所有可用的智能体模板，包括基础对话、知识库、深度思考等类型")
async def get_agent_templates():
    """
    获取智能体模板列表
    
    返回三种主要模板类型：
    - basic_conversation: 基础对话助手，适用于日常对话和客服场景
    - knowledge_base: 知识库问答专家，基于文档库回答专业问题  
    - deep_thinking: 深度思考分析师，进行复杂推理和分析
    """
    try:
        agno_manager = get_agno_manager()
        templates = agno_manager.get_available_templates()
        
        return {
            "success": True,
            "data": {
                "templates": templates,
                "total": len(templates)
            }
        }
        
    except Exception as e:
        logger.error(f"获取智能体模板列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取智能体模板列表失败: {str(e)}")


@router.get("/templates/{template_id}",
           summary="获取模板详情",
           description="根据模板ID获取模板的详细配置信息")
async def get_template_details(template_id: str):
    """获取模板详情"""
    try:
        agno_manager = get_agno_manager()
        template = agno_manager.get_template_details(template_id)
        
        if not template:
            raise HTTPException(status_code=404, detail=f"未找到模板: {template_id}")
        
        return {
            "success": True,
            "data": template
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取模板详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取模板详情失败: {str(e)}")


# ===== 智能体创建和管理 =====

@router.post("/", 
            summary="创建智能体",
            description="基于模板和配置创建新的智能体实例")
async def create_agent(request: AgentCreateRequest):
    """
    创建智能体
    
    基于三种智能体模板创建智能体实例：
    - basic_conversation: 基础对话助手 
    - knowledge_base: 知识库问答专家
    - deep_thinking: 深度思考分析师
    """
    try:
        # 验证模板ID
        try:
            TemplateType(request.template_id)
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail=f"无效的模板ID: {request.template_id}。支持的模板: {[t.value for t in TemplateType]}"
            )
        
        # 获取Agno管理器
        agno_manager = get_agno_manager()
        if not agno_manager.is_ready():
            await agno_manager.initialize()
        
        # 创建智能体
        agent_response = await agno_manager.create_agent(request)
        
        return {
            "success": True,
            "message": "智能体创建成功",
            "data": agent_response
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建智能体失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建智能体失败: {str(e)}")


@router.get("/", 
           summary="获取智能体列表",
           description="分页获取智能体列表，支持筛选和搜索")
async def list_agents(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页大小"),
    template_type: Optional[str] = Query(None, description="按模板类型筛选"),
    status: Optional[str] = Query(None, description="按状态筛选"),
    search: Optional[str] = Query(None, description="搜索关键词")
):
    """
    获取智能体列表
    
    支持的筛选条件：
    - template_type: 模板类型筛选
    - status: 状态筛选（active, inactive）
    - search: 按名称和描述搜索
    """
    try:
        agno_manager = get_agno_manager()
        if not agno_manager.is_ready():
            await agno_manager.initialize()
        
        # 获取筛选后的智能体列表
        result = agno_manager.list_agents_paginated(
            page=page,
            page_size=page_size,
            template_type=template_type,
            status=status,
            search=search
        )
        
        return {
            "success": True,
            "data": {
                "agents": result["agents"],
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": result["total"],
                    "total_pages": (result["total"] + page_size - 1) // page_size
                }
            }
        }
        
    except Exception as e:
        logger.error(f"获取智能体列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取智能体列表失败: {str(e)}")


@router.get("/{agent_id}",
           summary="获取智能体详情",
           description="根据ID获取智能体的详细信息和配置")
async def get_agent_details(agent_id: str):
    """获取智能体详情"""
    try:
        agno_manager = get_agno_manager()
        if not agno_manager.is_ready():
            await agno_manager.initialize()
        
        agent_info = agno_manager.get_agent(agent_id)
        if not agent_info:
            raise HTTPException(status_code=404, detail=f"未找到智能体: {agent_id}")
        
        return {
            "success": True,
            "data": agent_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取智能体详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取智能体详情失败: {str(e)}")


@router.put("/{agent_id}",
           summary="更新智能体",
           description="更新智能体的配置信息")
async def update_agent(agent_id: str, request: AgentCreateRequest):
    """更新智能体配置"""
    try:
        agno_manager = get_agno_manager()
        if not agno_manager.is_ready():
            await agno_manager.initialize()
        
        # 检查智能体是否存在
        if not agno_manager.get_agent(agent_id):
            raise HTTPException(status_code=404, detail=f"未找到智能体: {agent_id}")
        
        # 更新智能体
        result = await agno_manager.update_agent(agent_id, request)
        
        return {
            "success": True,
            "message": "智能体更新成功",
            "data": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新智能体失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"更新智能体失败: {str(e)}")


@router.delete("/{agent_id}",
              summary="删除智能体",
              description="删除指定的智能体")
async def delete_agent(agent_id: str):
    """删除智能体"""
    try:
        agno_manager = get_agno_manager()
        if not agno_manager.is_ready():
            await agno_manager.initialize()
        
        success = await agno_manager.delete_agent(agent_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"未找到智能体: {agent_id}")
        
        return {
            "success": True,
            "message": f"智能体 {agent_id} 已删除"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除智能体失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除智能体失败: {str(e)}")


# ===== 智能体对话 =====

@router.post("/{agent_id}/chat",
            summary="与智能体对话",
            description="发送消息给智能体并获取回复，支持流式和非流式响应")
async def chat_with_agent(agent_id: str, request: ChatRequest):
    """
    与智能体对话
    
    使用DAG执行图处理用户消息，支持：
    - 多轮对话历史
    - 流式响应
    - 上下文保持
    - 工具调用
    """
    try:
        agno_manager = get_agno_manager()
        if not agno_manager.is_ready():
            await agno_manager.initialize()
        
        # 检查智能体是否存在
        agent_info = agno_manager.get_agent(agent_id)
        if not agent_info:
            raise HTTPException(status_code=404, detail=f"未找到智能体: {agent_id}")
        
        # 处理对话
        chat_response = await agno_manager.chat_with_agent(agent_id, request)
        
        return {
            "success": True,
            "data": chat_response
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"智能体对话失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"智能体对话失败: {str(e)}")


@router.get("/{agent_id}/chat/history",
           summary="获取对话历史",
           description="获取与智能体的对话历史记录")
async def get_chat_history(
    agent_id: str,
    session_id: str = Query(..., description="会话ID"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小")
):
    """获取对话历史"""
    try:
        agno_manager = get_agno_manager()
        if not agno_manager.is_ready():
            await agno_manager.initialize()
        
        history = await agno_manager.get_chat_history(agent_id, session_id, page, page_size)
        
        return {
            "success": True,
            "data": history
        }
        
    except Exception as e:
        logger.error(f"获取对话历史失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取对话历史失败: {str(e)}")


# ===== 工具管理 =====

@router.get("/tools",
           summary="获取可用工具列表",
           description="获取系统中所有可用的工具和集成")
async def get_available_tools():
    """
    获取可用工具列表
    
    返回所有可集成的工具，包括：
    - 搜索工具
    - 计算工具
    - 文件处理工具
    - API集成工具
    - 自定义工具
    """
    try:
        agno_manager = get_agno_manager()
        tools = agno_manager.get_available_tools()
        
        return {
            "success": True,
            "data": {
                "tools": tools,
                "categories": agno_manager.get_tool_categories()
            }
        }
        
    except Exception as e:
        logger.error(f"获取可用工具列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取可用工具列表失败: {str(e)}")


@router.get("/tools/{tool_id}",
           summary="获取工具详情",
           description="获取指定工具的详细信息和配置参数")
async def get_tool_details(tool_id: str):
    """获取工具详情"""
    try:
        agno_manager = get_agno_manager()
        tool_info = agno_manager.get_tool_details(tool_id)
        
        if not tool_info:
            raise HTTPException(status_code=404, detail=f"未找到工具: {tool_id}")
        
        return {
            "success": True,
            "data": tool_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取工具详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取工具详情失败: {str(e)}")


# ===== 模型配置 =====

@router.get("/models/providers",
           summary="获取模型提供商列表",
           description="获取所有支持的AI模型提供商和模型列表")
async def get_model_providers():
    """
    获取模型提供商列表
    
    返回支持的模型提供商：
    - OpenAI: GPT-4o, GPT-4o-mini, o3-mini
    - Anthropic: Claude 3.5 Sonnet, Claude 3 Haiku
    - 智谱AI: GLM-4 系列
    - 月之暗面: Moonshot 系列
    """
    try:
        agno_manager = get_agno_manager()
        providers = agno_manager.get_model_providers()
        
        return {
            "success": True,
            "data": {
                "providers": providers,
                "total": len(providers)
            }
        }
        
    except Exception as e:
        logger.error(f"获取模型提供商列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取模型提供商列表失败: {str(e)}")


@router.get("/models/{provider}/models",
           summary="获取提供商模型列表",
           description="获取指定提供商的可用模型列表")
async def get_provider_models(provider: str):
    """获取提供商的模型列表"""
    try:
        agno_manager = get_agno_manager()
        models = agno_manager.get_provider_models(provider)
        
        return {
            "success": True,
            "data": {
                "provider": provider,
                "models": models
            }
        }
        
    except Exception as e:
        logger.error(f"获取提供商模型列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取提供商模型列表失败: {str(e)}")


# ===== 团队管理 =====

@router.post("/teams",
            summary="创建智能体团队",
            description="创建多智能体协作团队")
async def create_agent_team(request: TeamCreateRequest):
    """
    创建智能体团队
    
    支持创建多智能体协作团队，实现：
    - 任务分工
    - 协作决策
    - 结果整合
    """
    try:
        agno_manager = get_agno_manager()
        if not agno_manager.is_ready():
            await agno_manager.initialize()
        
        team_response = await agno_manager.create_team(request)
        
        return {
            "success": True,
            "message": "智能体团队创建成功",
            "data": team_response
        }
        
    except Exception as e:
        logger.error(f"创建智能体团队失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建智能体团队失败: {str(e)}")


@router.get("/teams",
           summary="获取团队列表",
           description="获取所有智能体团队")
async def list_teams():
    """获取团队列表"""
    try:
        agno_manager = get_agno_manager()
        if not agno_manager.is_ready():
            await agno_manager.initialize()
        
        teams = agno_manager.list_teams()
        
        return {
            "success": True,
            "data": {
                "teams": teams,
                "total": len(teams)
            }
        }
        
    except Exception as e:
        logger.error(f"获取团队列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取团队列表失败: {str(e)}")


@router.get("/teams/{team_id}",
           summary="获取团队详情",
           description="获取团队的详细信息和成员列表")
async def get_team_details(team_id: str):
    """获取团队详情"""
    try:
        agno_manager = get_agno_manager()
        if not agno_manager.is_ready():
            await agno_manager.initialize()
        
        team_info = agno_manager.get_team(team_id)
        if not team_info:
            raise HTTPException(status_code=404, detail=f"未找到团队: {team_id}")
        
        return {
            "success": True,
            "data": team_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取团队详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取团队详情失败: {str(e)}")


# ===== 执行图管理 =====

@router.get("/{agent_id}/execution-graph",
           summary="获取智能体执行图",
           description="获取智能体的DAG执行图可视化数据")
async def get_agent_execution_graph(agent_id: str):
    """获取智能体的DAG执行图可视化数据"""
    try:
        agno_manager = get_agno_manager()
        if not agno_manager.is_ready():
            await agno_manager.initialize()
        
        execution_graph = await agno_manager.get_agent_execution_graph(agent_id)
        if not execution_graph:
            raise HTTPException(status_code=404, detail=f"未找到智能体或执行图: {agent_id}")
        
        return {
            "success": True,
            "data": {
                "agent_id": agent_id,
                "execution_graph": execution_graph
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取执行图失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取执行图失败: {str(e)}")


# ===== 系统状态 =====

@router.get("/health",
           summary="服务健康检查",
           description="检查智能体服务的健康状态")
async def health_check():
    """服务健康检查"""
    try:
        agno_manager = get_agno_manager()
        
        # 检查服务状态
        health_status = {
            "service": "agent-service",
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "agno_manager_ready": agno_manager.is_ready() if hasattr(agno_manager, 'is_ready') else True,
            "total_agents": len(agno_manager.list_agents()),
            "total_teams": len(agno_manager.list_teams())
        }
        
        return {
            "success": True,
            "data": health_status
        }
        
    except Exception as e:
        logger.error(f"健康检查失败: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "status": "unhealthy"
        }


@router.get("/stats",
           summary="获取服务统计信息",
           description="获取智能体服务的详细统计数据")
async def get_service_stats():
    """获取服务统计信息"""
    try:
        agno_manager = get_agno_manager()
        if not agno_manager.is_ready():
            await agno_manager.initialize()
        
        stats = agno_manager.get_service_stats()
        
        return {
            "success": True,
            "data": stats
        }
        
    except Exception as e:
        logger.error(f"获取服务统计信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取服务统计信息失败: {str(e)}")
