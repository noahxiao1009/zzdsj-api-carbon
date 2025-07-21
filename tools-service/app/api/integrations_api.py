"""
框架集成API接口
提供Agno和LlamaIndex集成的统一接口
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional
from app.schemas.tool_schemas import ToolRequest, ToolResponse
from app.core.tool_manager import ToolManager
from app.integrations.agno_integration import AgnoToolIntegration, setup_agno_integration, AgnoToolHandler
from app.integrations.llamaindex_integration import LlamaIndexToolIntegration, setup_llamaindex_integration
from app.core.logger import logger

router = APIRouter(prefix="/integrations", tags=["框架集成"])

# 全局集成实例
agno_integration: Optional[AgnoToolIntegration] = None
llamaindex_integration: Optional[LlamaIndexToolIntegration] = None
agno_handler: Optional[AgnoToolHandler] = None


async def get_tool_manager():
    """获取工具管理器实例"""
    # 这里应该从应用状态获取，暂时模拟
    from main import app
    return app.state.tool_manager


@router.post("/agno/setup")
async def setup_agno(tool_manager: ToolManager = Depends(get_tool_manager)):
    """
    设置Agno集成
    """
    global agno_integration, agno_handler
    
    try:
        agno_integration = await setup_agno_integration(tool_manager)
        agno_handler = AgnoToolHandler(agno_integration)
        
        return {
            "success": True,
            "message": "Agno集成设置成功",
            "tools": agno_integration.get_agno_tool_definitions()
        }
    except Exception as e:
        logger.error(f"Agno集成设置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/llamaindex/setup")
async def setup_llamaindex(tool_manager: ToolManager = Depends(get_tool_manager)):
    """
    设置LlamaIndex集成
    """
    global llamaindex_integration
    
    try:
        llamaindex_integration = await setup_llamaindex_integration(tool_manager)
        
        return {
            "success": True,
            "message": "LlamaIndex集成设置成功",
            "tools_count": len(llamaindex_integration.get_all_tools())
        }
    except Exception as e:
        logger.error(f"LlamaIndex集成设置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agno/tools")
async def get_agno_tools():
    """
    获取Agno工具定义
    """
    if not agno_integration:
        raise HTTPException(status_code=404, detail="Agno集成未设置")
    
    return {
        "success": True,
        "tools": agno_integration.get_agno_tool_definitions()
    }


@router.get("/agno/tools/{tool_name}")
async def get_agno_tool(tool_name: str):
    """
    获取特定Agno工具定义
    """
    if not agno_integration:
        raise HTTPException(status_code=404, detail="Agno集成未设置")
    
    tool_def = agno_integration.get_agno_tool_by_name(tool_name)
    if not tool_def:
        raise HTTPException(status_code=404, detail=f"工具 {tool_name} 不存在")
    
    return {
        "success": True,
        "tool": tool_def
    }


@router.post("/agno/execute")
async def execute_agno_tool(request: Dict[str, Any]):
    """
    执行Agno工具调用
    """
    if not agno_handler:
        raise HTTPException(status_code=404, detail="Agno集成未设置")
    
    try:
        result = await agno_handler.handle_tool_call(request)
        return result
    except Exception as e:
        logger.error(f"Agno工具执行失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agno/batch_execute")
async def batch_execute_agno_tools(requests: List[Dict[str, Any]]):
    """
    批量执行Agno工具调用
    """
    if not agno_handler:
        raise HTTPException(status_code=404, detail="Agno集成未设置")
    
    try:
        results = await agno_handler.batch_handle_tool_calls(requests)
        return {
            "success": True,
            "results": results,
            "total": len(results),
            "successful": sum(1 for r in results if r.get("success", False))
        }
    except Exception as e:
        logger.error(f"Agno批量工具执行失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/llamaindex/tools")
async def get_llamaindex_tools():
    """
    获取LlamaIndex工具信息
    """
    if not llamaindex_integration:
        raise HTTPException(status_code=404, detail="LlamaIndex集成未设置")
    
    tools = llamaindex_integration.get_all_tools()
    tool_info = []
    
    for tool in tools:
        if hasattr(tool, 'metadata'):
            tool_info.append({
                "name": tool.metadata.name,
                "description": tool.metadata.description,
            })
        else:
            tool_info.append({
                "name": getattr(tool, 'name', 'unknown'),
                "description": getattr(tool, 'description', 'No description')
            })
    
    return {
        "success": True,
        "tools": tool_info,
        "total": len(tool_info)
    }


@router.post("/llamaindex/create_tool")
async def create_llamaindex_tool(
    tool_name: str,
    action: str,
    tool_manager: ToolManager = Depends(get_tool_manager)
):
    """
    动态创建LlamaIndex工具
    """
    if not llamaindex_integration:
        llamaindex_integration = LlamaIndexToolIntegration(tool_manager)
    
    try:
        tool = await llamaindex_integration.create_llamaindex_tool(tool_name, action)
        
        if tool:
            return {
                "success": True,
                "message": f"工具 {tool_name}_{action} 创建成功",
                "tool_name": f"{tool_name}_{action}"
            }
        else:
            return {
                "success": False,
                "message": "工具创建失败"
            }
    except Exception as e:
        logger.error(f"创建LlamaIndex工具失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_integration_status():
    """
    获取集成状态
    """
    return {
        "success": True,
        "agno": {
            "available": agno_integration is not None,
            "tools_count": len(agno_integration.get_agno_tool_definitions()) if agno_integration else 0
        },
        "llamaindex": {
            "available": llamaindex_integration is not None,
            "tools_count": len(llamaindex_integration.get_all_tools()) if llamaindex_integration else 0
        }
    }


# WebSailor特定集成接口
@router.post("/websailor/agno")
async def setup_websailor_agno(tool_manager: ToolManager = Depends(get_tool_manager)):
    """
    为WebSailor设置Agno集成
    """
    global agno_integration
    
    try:
        if not agno_integration:
            agno_integration = await setup_agno_integration(tool_manager)
        
        websailor_tool = agno_integration.get_agno_tool_by_name("websailor")
        
        return {
            "success": True,
            "message": "WebSailor Agno集成完成",
            "tool": websailor_tool
        }
    except Exception as e:
        logger.error(f"WebSailor Agno集成失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/websailor/llamaindex")
async def setup_websailor_llamaindex(tool_manager: ToolManager = Depends(get_tool_manager)):
    """
    为WebSailor设置LlamaIndex集成
    """
    global llamaindex_integration
    
    try:
        if not llamaindex_integration:
            llamaindex_integration = LlamaIndexToolIntegration(tool_manager)
        
        tools = await llamaindex_integration.create_websailor_tools()
        
        return {
            "success": True,
            "message": "WebSailor LlamaIndex集成完成",
            "tools_count": len(tools)
        }
    except Exception as e:
        logger.error(f"WebSailor LlamaIndex集成失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Scraperr特定集成接口
@router.post("/scraperr/agno")
async def setup_scraperr_agno(tool_manager: ToolManager = Depends(get_tool_manager)):
    """
    为Scraperr设置Agno集成
    """
    global agno_integration
    
    try:
        if not agno_integration:
            agno_integration = await setup_agno_integration(tool_manager)
        
        scraperr_tool = agno_integration.get_agno_tool_by_name("scraperr")
        
        return {
            "success": True,
            "message": "Scraperr Agno集成完成",
            "tool": scraperr_tool
        }
    except Exception as e:
        logger.error(f"Scraperr Agno集成失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scraperr/llamaindex")
async def setup_scraperr_llamaindex(tool_manager: ToolManager = Depends(get_tool_manager)):
    """
    为Scraperr设置LlamaIndex集成
    """
    global llamaindex_integration
    
    try:
        if not llamaindex_integration:
            llamaindex_integration = LlamaIndexToolIntegration(tool_manager)
        
        tools = await llamaindex_integration.create_scraperr_tools()
        
        return {
            "success": True,
            "message": "Scraperr LlamaIndex集成完成",
            "tools_count": len(tools)
        }
    except Exception as e:
        logger.error(f"Scraperr LlamaIndex集成失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))