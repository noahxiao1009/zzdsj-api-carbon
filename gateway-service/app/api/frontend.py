"""
前端接口路由模块
涵盖所有前端功能接口，转发到相应的微服务
"""

import aiohttp
import asyncio
import logging
from fastapi import APIRouter, HTTPException, Depends, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Any, Dict, Optional
import json
import time

from ..discovery import service_registry, LoadBalanceStrategy
from ..middleware.request_tracker import track_request
from ..middleware.auth_middleware import verify_token
from ..utils.proxy import ProxyUtils

logger = logging.getLogger(__name__)

# 创建前端路由器
frontend_router = APIRouter(prefix="/frontend", tags=["Frontend"])

# 前端功能到微服务的映射
FRONTEND_SERVICE_MAPPING = {
    # 智能体相关接口
    "agent": {
        "service": "agent-service",
        "paths": [
            "/agents",
            "/agents/templates", 
            "/agents/execute",
            "/agents/teams",
            "/agents/tools",
            "/agents/models"
        ]
    },
    # 知识库相关接口
    "knowledge": {
        "service": "knowledge-service", 
        "paths": [
            "/knowledge",
            "/knowledge/upload",
            "/knowledge/documents",
            "/knowledge/chunks", 
            "/knowledge/search",
            "/knowledge/embedding"
        ]
    },
    # 模型配置相关接口
    "model": {
        "service": "model-service",
        "paths": [
            "/models",
            "/models/providers",
            "/models/config",
            "/models/test"
        ]
    },
    # 系统基础服务
    "base": {
        "service": "base-service",
        "paths": [
            "/users",
            "/auth",
            "/permissions",
            "/resources"
        ]
    },
    # 系统服务
    "system": {
        "service": "system-service", 
        "paths": [
            "/upload",
            "/files",
            "/sensitive-words",
            "/policy-search",
            "/system-config"
        ]
    }
}


class FrontendProxy:
    """前端代理类"""
    
    def __init__(self):
        self.proxy_utils = ProxyUtils()
    
    async def route_request(
        self,
        request: Request,
        target_service: str,
        path: str,
        auth_required: bool = True
    ) -> Response:
        """路由前端请求到目标微服务"""
        try:
            # 获取服务实例
            instance = await service_registry.get_service_instance(
                target_service,
                LoadBalanceStrategy.ROUND_ROBIN
            )
            
            if not instance:
                raise HTTPException(
                    status_code=503,
                    detail=f"服务 {target_service} 暂时不可用"
                )
            
            # 构建目标URL
            target_url = f"{instance.base_url}{path}"
            
            # 转发请求
            response = await self.proxy_utils.forward_request(
                request=request,
                target_url=target_url,
                auth_required=auth_required
            )
            
            return response
            
        except Exception as e:
            logger.error(f"前端请求路由失败: {str(e)}")
            raise HTTPException(status_code=500, detail="内部服务错误")


# 创建代理实例
frontend_proxy = FrontendProxy()


# ==================== 智能体相关接口 ====================

@frontend_router.get("/agents")
@track_request
async def get_agents(request: Request, current_user: dict = Depends(verify_token)):
    """获取智能体列表"""
    return await frontend_proxy.route_request(
        request, "agent-service", "/api/agents"
    )


@frontend_router.post("/agents")
@track_request
async def create_agent(request: Request, current_user: dict = Depends(verify_token)):
    """创建智能体"""
    return await frontend_proxy.route_request(
        request, "agent-service", "/api/agents"
    )


@frontend_router.get("/agents/{agent_id}")
@track_request
async def get_agent(agent_id: str, request: Request, current_user: dict = Depends(verify_token)):
    """获取智能体详情"""
    return await frontend_proxy.route_request(
        request, "agent-service", f"/api/agents/{agent_id}"
    )


@frontend_router.put("/agents/{agent_id}")
@track_request
async def update_agent(agent_id: str, request: Request, current_user: dict = Depends(verify_token)):
    """更新智能体"""
    return await frontend_proxy.route_request(
        request, "agent-service", f"/api/agents/{agent_id}"
    )


@frontend_router.delete("/agents/{agent_id}")
@track_request
async def delete_agent(agent_id: str, request: Request, current_user: dict = Depends(verify_token)):
    """删除智能体"""
    return await frontend_proxy.route_request(
        request, "agent-service", f"/api/agents/{agent_id}"
    )


@frontend_router.get("/agents/templates")
@track_request
async def get_agent_templates(request: Request, current_user: dict = Depends(verify_token)):
    """获取智能体模板"""
    return await frontend_proxy.route_request(
        request, "agent-service", "/api/agents/templates"
    )


@frontend_router.post("/agents/{agent_id}/execute")
@track_request
async def execute_agent(agent_id: str, request: Request, current_user: dict = Depends(verify_token)):
    """执行智能体任务"""
    return await frontend_proxy.route_request(
        request, "agent-service", f"/api/agents/{agent_id}/execute"
    )


@frontend_router.get("/agents/teams")
@track_request
async def get_teams(request: Request, current_user: dict = Depends(verify_token)):
    """获取团队列表"""
    return await frontend_proxy.route_request(
        request, "agent-service", "/api/teams"
    )


@frontend_router.post("/agents/teams")
@track_request
async def create_team(request: Request, current_user: dict = Depends(verify_token)):
    """创建团队"""
    return await frontend_proxy.route_request(
        request, "agent-service", "/api/teams"
    )


# ==================== 知识库相关接口 ====================

@frontend_router.get("/knowledge")
@track_request
async def get_knowledge_bases(request: Request, current_user: dict = Depends(verify_token)):
    """获取知识库列表"""
    return await frontend_proxy.route_request(
        request, "knowledge-service", "/api/knowledge"
    )


@frontend_router.post("/knowledge")
@track_request
async def create_knowledge_base(request: Request, current_user: dict = Depends(verify_token)):
    """创建知识库"""
    return await frontend_proxy.route_request(
        request, "knowledge-service", "/api/knowledge"
    )


@frontend_router.get("/knowledge/{kb_id}")
@track_request
async def get_knowledge_base(kb_id: str, request: Request, current_user: dict = Depends(verify_token)):
    """获取知识库详情"""
    return await frontend_proxy.route_request(
        request, "knowledge-service", f"/api/knowledge/{kb_id}"
    )


@frontend_router.put("/knowledge/{kb_id}")
@track_request
async def update_knowledge_base(kb_id: str, request: Request, current_user: dict = Depends(verify_token)):
    """更新知识库"""
    return await frontend_proxy.route_request(
        request, "knowledge-service", f"/api/knowledge/{kb_id}"
    )


@frontend_router.delete("/knowledge/{kb_id}")
@track_request
async def delete_knowledge_base(kb_id: str, request: Request, current_user: dict = Depends(verify_token)):
    """删除知识库"""
    return await frontend_proxy.route_request(
        request, "knowledge-service", f"/api/knowledge/{kb_id}"
    )


@frontend_router.post("/knowledge/{kb_id}/upload")
@track_request
async def upload_document(kb_id: str, request: Request, current_user: dict = Depends(verify_token)):
    """上传文档到知识库"""
    return await frontend_proxy.route_request(
        request, "knowledge-service", f"/api/knowledge/{kb_id}/upload"
    )


@frontend_router.get("/knowledge/{kb_id}/documents")
@track_request
async def get_documents(kb_id: str, request: Request, current_user: dict = Depends(verify_token)):
    """获取知识库文档列表"""
    return await frontend_proxy.route_request(
        request, "knowledge-service", f"/api/knowledge/{kb_id}/documents"
    )


@frontend_router.post("/knowledge/{kb_id}/search")
@track_request
async def search_knowledge(kb_id: str, request: Request, current_user: dict = Depends(verify_token)):
    """搜索知识库"""
    return await frontend_proxy.route_request(
        request, "knowledge-service", f"/api/knowledge/{kb_id}/search"
    )


# ==================== 模型配置相关接口 ====================

@frontend_router.get("/models")
@track_request
async def get_models(request: Request, current_user: dict = Depends(verify_token)):
    """获取模型列表"""
    return await frontend_proxy.route_request(
        request, "model-service", "/api/models"
    )


@frontend_router.get("/models/providers")
@track_request
async def get_providers(request: Request, current_user: dict = Depends(verify_token)):
    """获取模型提供商列表"""
    return await frontend_proxy.route_request(
        request, "model-service", "/api/providers"
    )


@frontend_router.post("/models/config")
@track_request
async def update_model_config(request: Request, current_user: dict = Depends(verify_token)):
    """更新模型配置"""
    return await frontend_proxy.route_request(
        request, "model-service", "/api/config"
    )


@frontend_router.post("/models/test")
@track_request
async def test_model(request: Request, current_user: dict = Depends(verify_token)):
    """测试模型连接"""
    return await frontend_proxy.route_request(
        request, "model-service", "/api/test"
    )


# ==================== 用户和权限相关接口 ====================

@frontend_router.post("/auth/login")
@track_request
async def login(request: Request):
    """用户登录"""
    return await frontend_proxy.route_request(
        request, "base-service", "/api/auth/login", auth_required=False
    )


@frontend_router.post("/auth/register")
@track_request
async def register(request: Request):
    """用户注册"""
    return await frontend_proxy.route_request(
        request, "base-service", "/api/auth/register", auth_required=False
    )


@frontend_router.post("/auth/logout")
@track_request
async def logout(request: Request, current_user: dict = Depends(verify_token)):
    """用户登出"""
    return await frontend_proxy.route_request(
        request, "base-service", "/api/auth/logout"
    )


@frontend_router.get("/users/profile")
@track_request
async def get_profile(request: Request, current_user: dict = Depends(verify_token)):
    """获取用户信息"""
    return await frontend_proxy.route_request(
        request, "base-service", "/api/users/profile"
    )


@frontend_router.put("/users/profile")
@track_request
async def update_profile(request: Request, current_user: dict = Depends(verify_token)):
    """更新用户信息"""
    return await frontend_proxy.route_request(
        request, "base-service", "/api/users/profile"
    )


# ==================== 文件上传相关接口 ====================

@frontend_router.post("/upload")
@track_request
async def upload_file(request: Request, current_user: dict = Depends(verify_token)):
    """文件上传"""
    return await frontend_proxy.route_request(
        request, "system-service", "/api/upload"
    )


@frontend_router.get("/files")
@track_request
async def get_files(request: Request, current_user: dict = Depends(verify_token)):
    """获取文件列表"""
    return await frontend_proxy.route_request(
        request, "system-service", "/api/files"
    )


@frontend_router.delete("/files/{file_id}")
@track_request
async def delete_file(file_id: str, request: Request, current_user: dict = Depends(verify_token)):
    """删除文件"""
    return await frontend_proxy.route_request(
        request, "system-service", f"/api/files/{file_id}"
    )


# ==================== 系统配置相关接口 ====================

@frontend_router.get("/system-config")
@track_request
async def get_system_config(request: Request, current_user: dict = Depends(verify_token)):
    """获取系统配置"""
    return await frontend_proxy.route_request(
        request, "system-service", "/api/system-config"
    )


@frontend_router.put("/system-config")
@track_request
async def update_system_config(request: Request, current_user: dict = Depends(verify_token)):
    """更新系统配置"""
    return await frontend_proxy.route_request(
        request, "system-service", "/api/system-config"
    )


# ==================== 通用路由处理 ====================

@frontend_router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
@track_request
async def catch_all_frontend(path: str, request: Request, current_user: dict = Depends(verify_token)):
    """捕获所有前端请求的通用路由"""
    
    # 根据路径确定目标服务
    target_service = None
    for service_key, service_config in FRONTEND_SERVICE_MAPPING.items():
        for service_path in service_config["paths"]:
            if path.startswith(service_path.lstrip("/")):
                target_service = service_config["service"]
                break
        if target_service:
            break
    
    if not target_service:
        raise HTTPException(status_code=404, detail="接口路径未找到")
    
    return await frontend_proxy.route_request(
        request, target_service, f"/api/{path}"
    ) 