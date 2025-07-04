"""
V1外部接口路由模块
主要提供给外部其他系统对本系统内置服务的调用
例如：文件上传，知识库管理等非前端的接口
"""

import aiohttp
import asyncio
import logging
from fastapi import APIRouter, HTTPException, Depends, Request, Response, Header
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPBearer
from typing import Any, Dict, Optional
import json
import time

from ..discovery import service_registry, LoadBalanceStrategy
from ..middleware.request_tracker import track_request
from ..middleware.api_key_middleware import verify_api_key
from ..utils.proxy import ProxyUtils

logger = logging.getLogger(__name__)

# 创建V1路由器
v1_router = APIRouter(prefix="/v1", tags=["External API v1"])

# V1接口到微服务的映射
V1_SERVICE_MAPPING = {
    # 知识库管理接口
    "knowledge": {
        "service": "knowledge-service",
        "endpoints": [
            "/knowledge-bases",
            "/documents", 
            "/search",
            "/embedding"
        ]
    },
    # 文件上传和管理接口
    "files": {
        "service": "system-service",
        "endpoints": [
            "/upload",
            "/files",
            "/file-manager"
        ]
    },
    # 智能体调用接口
    "agents": {
        "service": "agent-service", 
        "endpoints": [
            "/agents",
            "/execute",
            "/chat"
        ]
    },
    # 模型调用接口
    "models": {
        "service": "model-service",
        "endpoints": [
            "/completions",
            "/embeddings",
            "/models"
        ]
    },
    # 系统工具接口
    "tools": {
        "service": "system-service",
        "endpoints": [
            "/sensitive-words",
            "/policy-search",
            "/text-analysis"
        ]
    }
}


class V1Proxy:
    """V1外部接口代理类"""
    
    def __init__(self):
        self.proxy_utils = ProxyUtils()
    
    async def route_request(
        self,
        request: Request,
        target_service: str,
        path: str,
        require_auth: bool = True
    ) -> Response:
        """路由V1外部请求到目标微服务"""
        try:
            # 获取服务实例
            instance = await service_registry.get_service_instance(
                target_service,
                LoadBalanceStrategy.LEAST_CONNECTIONS
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
                auth_required=require_auth
            )
            
            return response
            
        except Exception as e:
            logger.error(f"V1外部请求路由失败: {str(e)}")
            raise HTTPException(status_code=500, detail="内部服务错误")


# 创建代理实例
v1_proxy = V1Proxy()


# ==================== 知识库管理接口 ====================

@v1_router.get("/knowledge-bases")
@track_request
async def list_knowledge_bases(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """获取知识库列表"""
    return await v1_proxy.route_request(
        request, "knowledge-service", "/api/v1/knowledge-bases"
    )


@v1_router.post("/knowledge-bases")
@track_request
async def create_knowledge_base(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """创建知识库"""
    return await v1_proxy.route_request(
        request, "knowledge-service", "/api/v1/knowledge-bases"
    )


@v1_router.get("/knowledge-bases/{kb_id}")
@track_request
async def get_knowledge_base(
    kb_id: str,
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """获取知识库详情"""
    return await v1_proxy.route_request(
        request, "knowledge-service", f"/api/v1/knowledge-bases/{kb_id}"
    )


@v1_router.put("/knowledge-bases/{kb_id}")
@track_request
async def update_knowledge_base(
    kb_id: str,
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """更新知识库"""
    return await v1_proxy.route_request(
        request, "knowledge-service", f"/api/v1/knowledge-bases/{kb_id}"
    )


@v1_router.delete("/knowledge-bases/{kb_id}")
@track_request
async def delete_knowledge_base(
    kb_id: str,
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """删除知识库"""
    return await v1_proxy.route_request(
        request, "knowledge-service", f"/api/v1/knowledge-bases/{kb_id}"
    )


@v1_router.post("/knowledge-bases/{kb_id}/documents")
@track_request
async def upload_document(
    kb_id: str,
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """上传文档到知识库"""
    return await v1_proxy.route_request(
        request, "knowledge-service", f"/api/v1/knowledge-bases/{kb_id}/documents"
    )


@v1_router.get("/knowledge-bases/{kb_id}/documents")
@track_request
async def list_documents(
    kb_id: str,
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """获取知识库文档列表"""
    return await v1_proxy.route_request(
        request, "knowledge-service", f"/api/v1/knowledge-bases/{kb_id}/documents"
    )


@v1_router.delete("/knowledge-bases/{kb_id}/documents/{doc_id}")
@track_request
async def delete_document(
    kb_id: str,
    doc_id: str,
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """删除文档"""
    return await v1_proxy.route_request(
        request, "knowledge-service", f"/api/v1/knowledge-bases/{kb_id}/documents/{doc_id}"
    )


@v1_router.post("/knowledge-bases/{kb_id}/search")
@track_request
async def search_knowledge_base(
    kb_id: str,
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """搜索知识库"""
    return await v1_proxy.route_request(
        request, "knowledge-service", f"/api/v1/knowledge-bases/{kb_id}/search"
    )


# ==================== 文件管理接口 ====================

@v1_router.post("/upload")
@track_request
async def upload_file(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """文件上传"""
    return await v1_proxy.route_request(
        request, "system-service", "/api/v1/upload"
    )


@v1_router.get("/files")
@track_request
async def list_files(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """获取文件列表"""
    return await v1_proxy.route_request(
        request, "system-service", "/api/v1/files"
    )


@v1_router.get("/files/{file_id}")
@track_request
async def get_file(
    file_id: str,
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """获取文件详情"""
    return await v1_proxy.route_request(
        request, "system-service", f"/api/v1/files/{file_id}"
    )


@v1_router.delete("/files/{file_id}")
@track_request
async def delete_file(
    file_id: str,
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """删除文件"""
    return await v1_proxy.route_request(
        request, "system-service", f"/api/v1/files/{file_id}"
    )


# ==================== 智能体调用接口 ====================

@v1_router.get("/agents")
@track_request
async def list_agents(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """获取智能体列表"""
    return await v1_proxy.route_request(
        request, "agent-service", "/api/v1/agents"
    )


@v1_router.get("/agents/{agent_id}")
@track_request
async def get_agent(
    agent_id: str,
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """获取智能体详情"""
    return await v1_proxy.route_request(
        request, "agent-service", f"/api/v1/agents/{agent_id}"
    )


@v1_router.post("/agents/{agent_id}/execute")
@track_request
async def execute_agent(
    agent_id: str,
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """执行智能体任务"""
    return await v1_proxy.route_request(
        request, "agent-service", f"/api/v1/agents/{agent_id}/execute"
    )


@v1_router.post("/agents/{agent_id}/chat")
@track_request
async def chat_with_agent(
    agent_id: str,
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """与智能体对话"""
    return await v1_proxy.route_request(
        request, "agent-service", f"/api/v1/agents/{agent_id}/chat"
    )


# ==================== 模型调用接口 ====================

@v1_router.get("/models")
@track_request
async def list_models(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """获取可用模型列表"""
    return await v1_proxy.route_request(
        request, "model-service", "/api/v1/models"
    )


@v1_router.post("/completions")
@track_request
async def create_completion(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """创建文本补全"""
    return await v1_proxy.route_request(
        request, "model-service", "/api/v1/completions"
    )


@v1_router.post("/embeddings")
@track_request
async def create_embeddings(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """创建文本嵌入"""
    return await v1_proxy.route_request(
        request, "model-service", "/api/v1/embeddings"
    )


# ==================== 系统工具接口 ====================

@v1_router.post("/sensitive-words/check")
@track_request
async def check_sensitive_words(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """敏感词检测"""
    return await v1_proxy.route_request(
        request, "system-service", "/api/v1/sensitive-words/check"
    )


@v1_router.post("/policy-search")
@track_request
async def policy_search(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """政策搜索"""
    return await v1_proxy.route_request(
        request, "system-service", "/api/v1/policy-search"
    )


@v1_router.post("/text-analysis")
@track_request
async def text_analysis(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """文本分析"""
    return await v1_proxy.route_request(
        request, "system-service", "/api/v1/text-analysis"
    )


# ==================== 批量操作接口 ====================

@v1_router.post("/batch/knowledge-bases")
@track_request
async def batch_create_knowledge_bases(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """批量创建知识库"""
    return await v1_proxy.route_request(
        request, "knowledge-service", "/api/v1/batch/knowledge-bases"
    )


@v1_router.post("/batch/documents")
@track_request
async def batch_upload_documents(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """批量上传文档"""
    return await v1_proxy.route_request(
        request, "knowledge-service", "/api/v1/batch/documents"
    )


@v1_router.post("/batch/agents/execute")
@track_request
async def batch_execute_agents(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """批量执行智能体"""
    return await v1_proxy.route_request(
        request, "agent-service", "/api/v1/batch/execute"
    )


# ==================== 状态和监控接口 ====================

@v1_router.get("/status")
@track_request
async def get_system_status(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """获取系统状态"""
    services_status = {}
    
    for service_name in ["agent-service", "knowledge-service", "model-service", "system-service"]:
        service_info = service_registry.get_service_info(service_name)
        if service_info:
            services_status[service_name] = {
                "status": "healthy" if service_info["healthy_count"] > 0 else "unhealthy",
                "instance_count": service_info["instance_count"],
                "healthy_count": service_info["healthy_count"]
            }
        else:
            services_status[service_name] = {
                "status": "not_registered",
                "instance_count": 0,
                "healthy_count": 0
            }
    
    return JSONResponse({
        "status": "ok",
        "timestamp": int(time.time()),
        "services": services_status
    })


@v1_router.get("/metrics")
@track_request
async def get_metrics(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """获取系统指标"""
    # 这里可以集成Prometheus等监控系统
    return JSONResponse({
        "timestamp": int(time.time()),
        "metrics": {
            "total_requests": 0,  # 从请求跟踪器获取
            "active_connections": 0,
            "error_rate": 0.0,
            "response_time_avg": 0.0
        }
    })


# ==================== 通用路由处理 ====================

@v1_router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
@track_request
async def catch_all_v1(
    path: str,
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """捕获所有V1请求的通用路由"""
    
    # 根据路径确定目标服务
    target_service = None
    for service_key, service_config in V1_SERVICE_MAPPING.items():
        for endpoint in service_config["endpoints"]:
            if path.startswith(endpoint.lstrip("/")):
                target_service = service_config["service"]
                break
        if target_service:
            break
    
    if not target_service:
        raise HTTPException(status_code=404, detail="API端点未找到")
    
    return await v1_proxy.route_request(
        request, target_service, f"/api/v1/{path}"
    ) 