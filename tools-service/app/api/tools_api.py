"""
统一工具API接口
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List
from app.schemas.tool_schemas import ToolRequest, ToolResponse, ToolListResponse, ToolSchemaResponse
from app.core.tool_manager import ToolManager
from app.core.logger import logger

router = APIRouter(prefix="/tools", tags=["工具管理"])

# 工具管理器实例
tool_manager = ToolManager()


@router.post("/execute", response_model=ToolResponse)
async def execute_tool(request: ToolRequest) -> ToolResponse:
    """
    执行工具调用
    """
    try:
        result = await tool_manager.execute_tool(request)
        return result
    except Exception as e:
        logger.error(f"工具执行失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list", response_model=ToolListResponse)
async def list_tools() -> ToolListResponse:
    """
    获取可用工具列表
    """
    try:
        tools = await tool_manager.list_tools()
        return ToolListResponse(
            success=True,
            tools=tools,
            total=len(tools)
        )
    except Exception as e:
        logger.error(f"获取工具列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schema/{tool_name}", response_model=ToolSchemaResponse)
async def get_tool_schema(tool_name: str) -> ToolSchemaResponse:
    """
    获取工具模式定义
    """
    try:
        schema = await tool_manager.get_tool_schema(tool_name)
        return ToolSchemaResponse(
            success=True,
            schema=schema
        )
    except Exception as e:
        logger.error(f"获取工具模式失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    健康检查
    """
    try:
        health_status = await tool_manager.health_check()
        return {
            "success": True,
            "status": "healthy" if health_status["overall_healthy"] else "unhealthy",
            "tools": health_status["tools"],
            "timestamp": health_status["timestamp"]
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics")
async def get_metrics() -> Dict[str, Any]:
    """
    获取工具使用指标
    """
    try:
        metrics = await tool_manager.get_metrics()
        return {
            "success": True,
            "metrics": metrics
        }
    except Exception as e:
        logger.error(f"获取指标失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# WebSailor特定接口
@router.post("/websailor/search")
async def websailor_search(request: Dict[str, Any]) -> ToolResponse:
    """
    WebSailor搜索接口
    """
    tool_request = ToolRequest(
        tool_name="websailor",
        action="search",
        parameters=request
    )
    return await execute_tool(tool_request)


@router.post("/websailor/visit")
async def websailor_visit(request: Dict[str, Any]) -> ToolResponse:
    """
    WebSailor网页访问接口
    """
    tool_request = ToolRequest(
        tool_name="websailor",
        action="visit",
        parameters=request
    )
    return await execute_tool(tool_request)


# Scraperr特定接口
@router.post("/scraperr/scrape")
async def scraperr_scrape(request: Dict[str, Any]) -> ToolResponse:
    """
    Scraperr爬取接口
    """
    tool_request = ToolRequest(
        tool_name="scraperr",
        action="scrape",
        parameters=request
    )
    return await execute_tool(tool_request)


@router.get("/scraperr/jobs")
async def scraperr_list_jobs(user_email: str = None, limit: int = 50) -> ToolResponse:
    """
    Scraperr任务列表接口
    """
    tool_request = ToolRequest(
        tool_name="scraperr",
        action="list_jobs",
        parameters={
            "user_email": user_email,
            "limit": limit
        }
    )
    return await execute_tool(tool_request)


@router.get("/scraperr/jobs/{job_id}")
async def scraperr_get_job(job_id: str, user_email: str = None) -> ToolResponse:
    """
    Scraperr任务详情接口
    """
    tool_request = ToolRequest(
        tool_name="scraperr",
        action="get_job",
        parameters={
            "job_id": job_id,
            "user_email": user_email
        }
    )
    return await execute_tool(tool_request)


@router.delete("/scraperr/jobs")
async def scraperr_delete_jobs(request: Dict[str, List[str]]) -> ToolResponse:
    """
    Scraperr删除任务接口
    """
    tool_request = ToolRequest(
        tool_name="scraperr",
        action="delete_job",
        parameters=request
    )
    return await execute_tool(tool_request)