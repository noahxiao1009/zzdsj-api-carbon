"""
MCP服务管理API接口
MCP Service Management API Routes
"""

import asyncio
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks, Request
from fastapi.responses import StreamingResponse, JSONResponse
import logging

from ..models.mcp_models import (
    MCPServiceConfig, MCPServiceInfo, MCPToolInfo, MCPServiceStatus,
    MCPToolExecuteRequest, MCPToolExecuteResponse, MCPStreamInfo,
    MCPNetworkConfig, MCPServiceStats, MCPContainerStats, MCPDashboardStats
)
from ..core.fastmcp_integration import FastMCPIntegration
from ..services.mcp_service import MCPService
from ..services.docker_service import DockerService
from ..services.sse_service import SSEService
from shared.service_client import call_service, CallMethod, CallConfig

logger = logging.getLogger(__name__)

# 创建API路由器
router = APIRouter(prefix="/api/v1/mcp", tags=["MCP服务管理"])

# 依赖注入
def get_mcp_service() -> MCPService:
    """获取MCP服务实例"""
    return MCPService()

def get_docker_service() -> DockerService:
    """获取Docker服务实例"""
    return DockerService()

def get_sse_service() -> SSEService:
    """获取SSE服务实例"""
    return SSEService()

# ==================== MCP服务管理接口 ====================

@router.post("/services", response_model=Dict[str, Any])
async def create_mcp_service(
    service_config: MCPServiceConfig,
    background_tasks: BackgroundTasks,
    mcp_service: MCPService = Depends(get_mcp_service)
):
    """
    创建MCP服务
    """
    try:
        # 验证服务配置
        await mcp_service.validate_service_config(service_config)
        
        # 检查服务名称是否已存在
        existing_service = await mcp_service.get_service_by_name(service_config.name)
        if existing_service:
            raise HTTPException(status_code=400, detail=f"Service {service_config.name} already exists")
        
        # 创建服务
        service_id = await mcp_service.create_service(service_config)
        
        # 后台部署服务
        background_tasks.add_task(
            mcp_service.deploy_service_async,
            service_id,
            service_config
        )
        
        return {
            "success": True,
            "message": "MCP服务创建成功",
            "data": {
                "service_id": service_id,
                "service_name": service_config.name,
                "status": "deploying"
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to create MCP service: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/services", response_model=List[MCPServiceInfo])
async def get_mcp_services(
    category: Optional[str] = Query(None, description="服务分类筛选"),
    status: Optional[MCPServiceStatus] = Query(None, description="状态筛选"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页大小"),
    mcp_service: MCPService = Depends(get_mcp_service)
):
    """
    获取MCP服务列表
    """
    try:
        services = await mcp_service.get_services(
            category=category,
            status=status,
            search=search,
            page=page,
            size=size
        )
        
        return services
        
    except Exception as e:
        logger.error(f"Failed to get MCP services: {e}")
        raise HTTPException(status_code=500, detail="获取服务列表失败")

@router.get("/services/{service_id}", response_model=MCPServiceInfo)
async def get_mcp_service_details(
    service_id: str,
    mcp_service: MCPService = Depends(get_mcp_service)
):
    """
    获取MCP服务详情
    """
    try:
        service = await mcp_service.get_service_by_id(service_id)
        if not service:
            raise HTTPException(status_code=404, detail="服务不存在")
        
        return service
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get MCP service details: {e}")
        raise HTTPException(status_code=500, detail="获取服务详情失败")

@router.put("/services/{service_id}", response_model=Dict[str, Any])
async def update_mcp_service(
    service_id: str,
    service_config: MCPServiceConfig,
    background_tasks: BackgroundTasks,
    mcp_service: MCPService = Depends(get_mcp_service)
):
    """
    更新MCP服务配置
    """
    try:
        # 检查服务是否存在
        existing_service = await mcp_service.get_service_by_id(service_id)
        if not existing_service:
            raise HTTPException(status_code=404, detail="服务不存在")
        
        # 更新服务配置
        success = await mcp_service.update_service(service_id, service_config)
        if not success:
            raise HTTPException(status_code=500, detail="更新服务配置失败")
        
        # 后台重新部署服务
        background_tasks.add_task(
            mcp_service.redeploy_service_async,
            service_id,
            service_config
        )
        
        return {
            "success": True,
            "message": "服务配置更新成功",
            "data": {
                "service_id": service_id,
                "status": "redeploying"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update MCP service: {e}")
        raise HTTPException(status_code=500, detail="更新服务失败")

@router.delete("/services/{service_id}", response_model=Dict[str, Any])
async def delete_mcp_service(
    service_id: str,
    force: bool = Query(False, description="强制删除"),
    background_tasks: BackgroundTasks,
    mcp_service: MCPService = Depends(get_mcp_service)
):
    """
    删除MCP服务
    """
    try:
        # 检查服务是否存在
        existing_service = await mcp_service.get_service_by_id(service_id)
        if not existing_service:
            raise HTTPException(status_code=404, detail="服务不存在")
        
        # 后台删除服务
        background_tasks.add_task(
            mcp_service.delete_service_async,
            service_id,
            force
        )
        
        return {
            "success": True,
            "message": "服务删除中",
            "data": {
                "service_id": service_id,
                "status": "deleting"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete MCP service: {e}")
        raise HTTPException(status_code=500, detail="删除服务失败")

# ==================== 服务控制接口 ====================

@router.post("/services/{service_id}/start", response_model=Dict[str, Any])
async def start_mcp_service(
    service_id: str,
    background_tasks: BackgroundTasks,
    mcp_service: MCPService = Depends(get_mcp_service)
):
    """
    启动MCP服务
    """
    try:
        # 检查服务是否存在
        service = await mcp_service.get_service_by_id(service_id)
        if not service:
            raise HTTPException(status_code=404, detail="服务不存在")
        
        if service.status == MCPServiceStatus.ACTIVE:
            return {
                "success": True,
                "message": "服务已在运行中",
                "data": {"service_id": service_id, "status": "active"}
            }
        
        # 后台启动服务
        background_tasks.add_task(mcp_service.start_service_async, service_id)
        
        return {
            "success": True,
            "message": "服务启动中",
            "data": {"service_id": service_id, "status": "starting"}
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start MCP service: {e}")
        raise HTTPException(status_code=500, detail="启动服务失败")

@router.post("/services/{service_id}/stop", response_model=Dict[str, Any])
async def stop_mcp_service(
    service_id: str,
    background_tasks: BackgroundTasks,
    mcp_service: MCPService = Depends(get_mcp_service)
):
    """
    停止MCP服务
    """
    try:
        # 检查服务是否存在
        service = await mcp_service.get_service_by_id(service_id)
        if not service:
            raise HTTPException(status_code=404, detail="服务不存在")
        
        if service.status == MCPServiceStatus.INACTIVE:
            return {
                "success": True,
                "message": "服务已停止",
                "data": {"service_id": service_id, "status": "inactive"}
            }
        
        # 后台停止服务
        background_tasks.add_task(mcp_service.stop_service_async, service_id)
        
        return {
            "success": True,
            "message": "服务停止中",
            "data": {"service_id": service_id, "status": "stopping"}
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop MCP service: {e}")
        raise HTTPException(status_code=500, detail="停止服务失败")

@router.post("/services/{service_id}/restart", response_model=Dict[str, Any])
async def restart_mcp_service(
    service_id: str,
    background_tasks: BackgroundTasks,
    mcp_service: MCPService = Depends(get_mcp_service)
):
    """
    重启MCP服务
    """
    try:
        # 检查服务是否存在
        service = await mcp_service.get_service_by_id(service_id)
        if not service:
            raise HTTPException(status_code=404, detail="服务不存在")
        
        # 后台重启服务
        background_tasks.add_task(mcp_service.restart_service_async, service_id)
        
        return {
            "success": True,
            "message": "服务重启中",
            "data": {"service_id": service_id, "status": "restarting"}
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to restart MCP service: {e}")
        raise HTTPException(status_code=500, detail="重启服务失败")

@router.get("/services/{service_id}/health", response_model=Dict[str, Any])
async def check_service_health(
    service_id: str,
    mcp_service: MCPService = Depends(get_mcp_service)
):
    """
    检查服务健康状态
    """
    try:
        health_info = await mcp_service.check_service_health(service_id)
        
        return {
            "success": True,
            "data": health_info
        }
        
    except Exception as e:
        logger.error(f"Failed to check service health: {e}")
        return {
            "success": False,
            "error": str(e),
            "data": {
                "service_id": service_id,
                "healthy": False,
                "error": str(e)
            }
        }

@router.get("/services/{service_id}/logs", response_model=Dict[str, Any])
async def get_service_logs(
    service_id: str,
    lines: int = Query(100, ge=1, le=1000, description="日志行数"),
    since: Optional[str] = Query(None, description="起始时间"),
    docker_service: DockerService = Depends(get_docker_service)
):
    """
    获取服务日志
    """
    try:
        logs = await docker_service.get_container_logs(service_id, lines=lines, since=since)
        
        return {
            "success": True,
            "data": {
                "service_id": service_id,
                "logs": logs,
                "lines": len(logs) if isinstance(logs, list) else logs.count('\n')
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get service logs: {e}")
        raise HTTPException(status_code=500, detail="获取服务日志失败")

# ==================== 工具管理接口 ====================

@router.get("/services/{service_id}/tools", response_model=List[MCPToolInfo])
async def get_service_tools(
    service_id: str,
    enabled_only: bool = Query(False, description="仅显示启用的工具"),
    mcp_service: MCPService = Depends(get_mcp_service)
):
    """
    获取服务的工具列表
    """
    try:
        tools = await mcp_service.get_service_tools(service_id, enabled_only=enabled_only)
        return tools
        
    except Exception as e:
        logger.error(f"Failed to get service tools: {e}")
        raise HTTPException(status_code=500, detail="获取工具列表失败")

@router.put("/services/{service_id}/tools/{tool_name}/toggle", response_model=Dict[str, Any])
async def toggle_tool_status(
    service_id: str,
    tool_name: str,
    enabled: bool = Query(..., description="是否启用"),
    mcp_service: MCPService = Depends(get_mcp_service)
):
    """
    切换工具启用状态
    """
    try:
        success = await mcp_service.toggle_tool_status(service_id, tool_name, enabled)
        
        if not success:
            raise HTTPException(status_code=404, detail="工具不存在")
        
        return {
            "success": True,
            "message": f"工具{tool_name}已{'启用' if enabled else '禁用'}",
            "data": {
                "service_id": service_id,
                "tool_name": tool_name,
                "enabled": enabled
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to toggle tool status: {e}")
        raise HTTPException(status_code=500, detail="切换工具状态失败")

@router.post("/services/{service_id}/tools/batch-toggle", response_model=Dict[str, Any])
async def batch_toggle_tools(
    service_id: str,
    tool_updates: List[Dict[str, Any]],
    mcp_service: MCPService = Depends(get_mcp_service)
):
    """
    批量切换工具状态
    """
    try:
        results = await mcp_service.batch_toggle_tools(service_id, tool_updates)
        
        success_count = sum(1 for r in results if r.get("success"))
        total_count = len(results)
        
        return {
            "success": success_count == total_count,
            "message": f"批量操作完成，成功: {success_count}/{total_count}",
            "data": {
                "service_id": service_id,
                "results": results,
                "success_count": success_count,
                "total_count": total_count
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to batch toggle tools: {e}")
        raise HTTPException(status_code=500, detail="批量操作失败")

# ==================== 工具执行接口 ====================

@router.post("/services/{service_id}/tools/{tool_name}/execute", response_model=MCPToolExecuteResponse)
async def execute_tool(
    service_id: str,
    tool_name: str,
    request: MCPToolExecuteRequest,
    mcp_service: MCPService = Depends(get_mcp_service)
):
    """
    执行MCP工具
    """
    try:
        # 验证服务和工具是否存在
        service = await mcp_service.get_service_by_id(service_id)
        if not service:
            raise HTTPException(status_code=404, detail="服务不存在")
        
        if service.status != MCPServiceStatus.ACTIVE:
            raise HTTPException(status_code=400, detail="服务未运行")
        
        # 执行工具
        request.service_id = service_id
        request.tool_name = tool_name
        
        result = await mcp_service.execute_tool(request)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute tool: {e}")
        raise HTTPException(status_code=500, detail="工具执行失败")

@router.post("/services/{service_id}/tools/{tool_name}/stream", response_model=Dict[str, Any])
async def execute_tool_streaming(
    service_id: str,
    tool_name: str,
    request: MCPToolExecuteRequest,
    background_tasks: BackgroundTasks,
    mcp_service: MCPService = Depends(get_mcp_service),
    sse_service: SSEService = Depends(get_sse_service)
):
    """
    流式执行MCP工具
    """
    try:
        # 验证服务和工具
        service = await mcp_service.get_service_by_id(service_id)
        if not service:
            raise HTTPException(status_code=404, detail="服务不存在")
        
        if service.status != MCPServiceStatus.ACTIVE:
            raise HTTPException(status_code=400, detail="服务未运行")
        
        # 创建流
        stream_id = await sse_service.create_stream(
            service_id=service_id,
            tool_name=tool_name,
            user_id=request.user_id
        )
        
        # 后台执行流式工具
        request.service_id = service_id
        request.tool_name = tool_name
        request.stream = True
        
        background_tasks.add_task(
            mcp_service.execute_tool_streaming_async,
            request,
            stream_id
        )
        
        return {
            "success": True,
            "message": "流式执行已开始",
            "data": {
                "stream_id": stream_id,
                "stream_url": f"/api/v1/mcp/streams/{stream_id}/events",
                "service_id": service_id,
                "tool_name": tool_name
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute tool streaming: {e}")
        raise HTTPException(status_code=500, detail="流式执行失败")

# ==================== 流式通信接口 ====================

@router.get("/streams/{stream_id}/events")
async def stream_events(
    stream_id: str,
    request: Request,
    sse_service: SSEService = Depends(get_sse_service)
):
    """
    SSE事件流端点
    """
    try:
        # 验证流是否存在
        stream_info = await sse_service.get_stream_info(stream_id)
        if not stream_info:
            raise HTTPException(status_code=404, detail="流不存在")
        
        # 创建SSE响应
        async def event_generator():
            try:
                async for event in sse_service.stream_events(stream_id):
                    # 检查客户端是否断开连接
                    if await request.is_disconnected():
                        break
                    yield event
            except Exception as e:
                logger.error(f"Stream error: {e}")
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create event stream: {e}")
        raise HTTPException(status_code=500, detail="创建事件流失败")

@router.delete("/streams/{stream_id}", response_model=Dict[str, Any])
async def close_stream(
    stream_id: str,
    sse_service: SSEService = Depends(get_sse_service)
):
    """
    关闭流
    """
    try:
        success = await sse_service.close_stream(stream_id)
        
        return {
            "success": success,
            "message": "流已关闭" if success else "流不存在",
            "data": {"stream_id": stream_id}
        }
        
    except Exception as e:
        logger.error(f"Failed to close stream: {e}")
        raise HTTPException(status_code=500, detail="关闭流失败")

@router.get("/streams", response_model=List[MCPStreamInfo])
async def get_active_streams(
    user_id: Optional[str] = Query(None, description="用户ID筛选"),
    service_id: Optional[str] = Query(None, description="服务ID筛选"),
    sse_service: SSEService = Depends(get_sse_service)
):
    """
    获取活跃流列表
    """
    try:
        streams = await sse_service.get_active_streams(user_id=user_id, service_id=service_id)
        return streams
        
    except Exception as e:
        logger.error(f"Failed to get active streams: {e}")
        raise HTTPException(status_code=500, detail="获取流列表失败")

# ==================== 统计和监控接口 ====================

@router.get("/dashboard/stats", response_model=MCPDashboardStats)
async def get_dashboard_stats(
    mcp_service: MCPService = Depends(get_mcp_service)
):
    """
    获取仪表板统计信息
    """
    try:
        stats = await mcp_service.get_dashboard_stats()
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get dashboard stats: {e}")
        raise HTTPException(status_code=500, detail="获取统计信息失败")

@router.get("/services/{service_id}/stats", response_model=MCPServiceStats)
async def get_service_stats(
    service_id: str,
    days: int = Query(30, ge=1, le=365, description="统计天数"),
    mcp_service: MCPService = Depends(get_mcp_service)
):
    """
    获取服务统计信息
    """
    try:
        stats = await mcp_service.get_service_stats(service_id, days=days)
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get service stats: {e}")
        raise HTTPException(status_code=500, detail="获取服务统计失败")

@router.get("/containers", response_model=List[MCPContainerStats])
async def get_container_stats(
    running_only: bool = Query(True, description="仅显示运行中的容器"),
    docker_service: DockerService = Depends(get_docker_service)
):
    """
    获取容器统计信息
    """
    try:
        stats = await docker_service.get_containers_stats(running_only=running_only)
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get container stats: {e}")
        raise HTTPException(status_code=500, detail="获取容器统计失败")

@router.get("/containers/{container_id}/stats", response_model=MCPContainerStats)
async def get_single_container_stats(
    container_id: str,
    docker_service: DockerService = Depends(get_docker_service)
):
    """
    获取单个容器统计信息
    """
    try:
        stats = await docker_service.get_container_stats(container_id)
        if not stats:
            raise HTTPException(status_code=404, detail="容器不存在")
        
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get container stats: {e}")
        raise HTTPException(status_code=500, detail="获取容器统计失败")

# ==================== 网络管理接口 ====================

@router.get("/networks", response_model=List[Dict[str, Any]])
async def get_mcp_networks(
    docker_service: DockerService = Depends(get_docker_service)
):
    """
    获取MCP网络列表
    """
    try:
        networks = await docker_service.get_mcp_networks()
        return networks
        
    except Exception as e:
        logger.error(f"Failed to get MCP networks: {e}")
        raise HTTPException(status_code=500, detail="获取网络列表失败")

@router.post("/networks", response_model=Dict[str, Any])
async def create_mcp_network(
    network_config: MCPNetworkConfig,
    docker_service: DockerService = Depends(get_docker_service)
):
    """
    创建MCP网络
    """
    try:
        network_id = await docker_service.create_mcp_network(network_config)
        
        return {
            "success": True,
            "message": "网络创建成功",
            "data": {
                "network_id": network_id,
                "network_name": network_config.name,
                "vlan_id": network_config.vlan_id
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to create MCP network: {e}")
        raise HTTPException(status_code=500, detail="创建网络失败")

# ==================== 健康检查接口 ====================

@router.get("/health", response_model=Dict[str, Any])
async def mcp_service_health():
    """
    MCP服务健康检查
    """
    try:
        return {
            "service": "mcp-service",
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0"
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "service": "mcp-service",
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )