"""
工具管理API接口
Tools Management API Routes
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional
import logging

from ..core.dag_orchestrator import dag_orchestrator
from ..core.tool_injection_manager import tool_injection_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tools", tags=["工具管理"])


@router.get("/list", response_model=Dict[str, Any])
async def list_available_tools():
    """获取可用工具列表"""
    try:
        if not dag_orchestrator._initialized:
            await dag_orchestrator.initialize()
        
        tools = []
        for tool in tool_injection_manager.tools.values():
            tools.append({
                "id": tool.id,
                "name": tool.name,
                "display_name": tool.display_name,
                "description": tool.description,
                "type": tool.type.value,
                "category": tool.category.value,
                "service_name": tool.service_name,
                "is_enabled": tool.is_enabled,
                "is_available": tool.is_available,
                "health_status": tool.health_status,
                "version": tool.version,
                "tags": tool.tags
            })
        
        return {
            "success": True,
            "tools": tools,
            "total": len(tools)
        }
        
    except Exception as e:
        logger.error(f"获取工具列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics", response_model=Dict[str, Any])
async def get_tools_statistics():
    """获取工具统计信息"""
    try:
        stats = dag_orchestrator.get_tools_statistics()
        return {
            "success": True,
            "statistics": stats
        }
        
    except Exception as e:
        logger.error(f"获取工具统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh", response_model=Dict[str, Any])
async def refresh_tools():
    """刷新工具列表"""
    try:
        result = await dag_orchestrator.refresh_tools()
        return result
        
    except Exception as e:
        logger.error(f"刷新工具列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories", response_model=Dict[str, Any])
async def get_tool_categories():
    """获取工具分类"""
    try:
        if not dag_orchestrator._initialized:
            await dag_orchestrator.initialize()
        
        categories = {}
        for tool in tool_injection_manager.tools.values():
            category = tool.category.value
            if category not in categories:
                categories[category] = {
                    "name": category,
                    "tools": [],
                    "count": 0
                }
            categories[category]["tools"].append({
                "id": tool.id,
                "name": tool.name,
                "display_name": tool.display_name
            })
            categories[category]["count"] += 1
        
        return {
            "success": True,
            "categories": list(categories.values())
        }
        
    except Exception as e:
        logger.error(f"获取工具分类失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/services", response_model=Dict[str, Any])
async def get_tools_by_service():
    """按服务分组获取工具"""
    try:
        if not dag_orchestrator._initialized:
            await dag_orchestrator.initialize()
        
        services = {}
        for tool in tool_injection_manager.tools.values():
            service = tool.service_name
            if service not in services:
                services[service] = {
                    "service_name": service,
                    "tools": [],
                    "count": 0,
                    "healthy_count": 0
                }
            
            tool_info = {
                "id": tool.id,
                "name": tool.name,
                "display_name": tool.display_name,
                "category": tool.category.value,
                "type": tool.type.value,
                "is_available": tool.is_available,
                "health_status": tool.health_status
            }
            
            services[service]["tools"].append(tool_info)
            services[service]["count"] += 1
            
            if tool.health_status == "healthy":
                services[service]["healthy_count"] += 1
        
        return {
            "success": True,
            "services": list(services.values())
        }
        
    except Exception as e:
        logger.error(f"按服务获取工具失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=Dict[str, Any])
async def check_tools_health():
    """检查工具健康状态"""
    try:
        if not dag_orchestrator._initialized:
            await dag_orchestrator.initialize()
        
        # 获取各服务的工具健康状态
        service_health = {}
        total_tools = 0
        healthy_tools = 0
        
        for tool in tool_injection_manager.tools.values():
            service = tool.service_name
            if service not in service_health:
                service_health[service] = {
                    "service_name": service,
                    "total": 0,
                    "healthy": 0,
                    "unhealthy": 0,
                    "unknown": 0
                }
            
            service_health[service]["total"] += 1
            total_tools += 1
            
            if tool.health_status == "healthy":
                service_health[service]["healthy"] += 1
                healthy_tools += 1
            elif tool.health_status == "unhealthy":
                service_health[service]["unhealthy"] += 1
            else:
                service_health[service]["unknown"] += 1
        
        overall_healthy = healthy_tools / total_tools if total_tools > 0 else 0
        
        return {
            "success": True,
            "overall_health": {
                "status": "healthy" if overall_healthy > 0.8 else "degraded" if overall_healthy > 0.5 else "unhealthy",
                "healthy_percentage": round(overall_healthy * 100, 2),
                "total_tools": total_tools,
                "healthy_tools": healthy_tools
            },
            "services": list(service_health.values())
        }
        
    except Exception as e:
        logger.error(f"检查工具健康状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{tool_id}/details", response_model=Dict[str, Any])
async def get_tool_details(tool_id: str):
    """获取工具详细信息"""
    try:
        if not dag_orchestrator._initialized:
            await dag_orchestrator.initialize()
        
        tool = tool_injection_manager.tools.get(tool_id)
        if not tool:
            raise HTTPException(status_code=404, detail=f"工具 {tool_id} 未找到")
        
        return {
            "success": True,
            "tool": {
                "id": tool.id,
                "name": tool.name,
                "display_name": tool.display_name,
                "description": tool.description,
                "type": tool.type.value,
                "category": tool.category.value,
                "version": tool.version,
                "service_name": tool.service_name,
                "service_url": tool.service_url,
                "endpoint": tool.endpoint,
                "permission_level": tool.permission_level,
                "rate_limit": tool.rate_limit,
                "timeout": tool.timeout,
                "is_enabled": tool.is_enabled,
                "is_available": tool.is_available,
                "health_status": tool.health_status,
                "total_calls": tool.total_calls,
                "success_rate": tool.success_rate,
                "avg_response_time": tool.avg_response_time,
                "tags": tool.tags,
                "schema": tool.schema,
                "parameters": tool.parameters,
                "config": tool.config,
                "created_at": tool.created_at.isoformat(),
                "updated_at": tool.updated_at.isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取工具详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 