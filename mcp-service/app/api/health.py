"""
MCP Service 健康检查API
提供服务状态检查、详细检查、就绪性检查等接口
"""

import logging
from typing import Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db, check_database_health, get_database_info
from app.core.redis import check_redis_health, get_redis_info
from app.frameworks.fastmcp.server import get_server_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["健康检查"])


@router.get("/")
async def basic_health_check():
    """
    基础健康检查
    
    返回服务的基本状态信息
    """
    return {
        "status": "healthy",
        "service": "mcp-service",
        "version": settings.service_version,
        "timestamp": datetime.now().isoformat(),
        "environment": settings.environment
    }


@router.get("/detailed")
async def detailed_health_check(db: Session = Depends(get_db)):
    """
    详细健康检查
    
    检查各个组件的健康状态
    """
    health_status = {
        "status": "healthy",
        "service": "mcp-service", 
        "version": settings.service_version,
        "timestamp": datetime.now().isoformat(),
        "environment": settings.environment,
        "components": {}
    }
    
    overall_healthy = True
    
    try:
        # 数据库健康检查
        db_healthy = check_database_health()
        db_info = get_database_info()
        
        health_status["components"]["database"] = {
            "status": "healthy" if db_healthy else "unhealthy",
            "connected": db_info.get("connected", False),
            "version": db_info.get("version"),
            "pool_status": db_info.get("pool_status")
        }
        
        if not db_healthy:
            overall_healthy = False
            
    except Exception as e:
        logger.error(f"数据库健康检查失败: {e}")
        health_status["components"]["database"] = {
            "status": "error",
            "error": str(e)
        }
        overall_healthy = False
    
    try:
        # Redis健康检查
        redis_healthy = await check_redis_health()
        redis_info = await get_redis_info()
        
        health_status["components"]["redis"] = {
            "status": "healthy" if redis_healthy else "unhealthy",
            "connected": redis_info.get("connected", False),
            "version": redis_info.get("version"),
            "memory_used": redis_info.get("memory_used"),
            "connected_clients": redis_info.get("connected_clients")
        }
        
        if not redis_healthy:
            overall_healthy = False
            
    except Exception as e:
        logger.error(f"Redis健康检查失败: {e}")
        health_status["components"]["redis"] = {
            "status": "error",
            "error": str(e)
        }
        overall_healthy = False
    
    try:
        # MCP服务器健康检查
        mcp_status = get_server_status()
        
        health_status["components"]["mcp_server"] = {
            "status": "healthy" if mcp_status.get("is_running") else "unhealthy",
            "name": mcp_status.get("name"),
            "version": mcp_status.get("version"),
            "tools_count": mcp_status.get("tools_count", 0),
            "resources_count": mcp_status.get("resources_count", 0),
            "prompts_count": mcp_status.get("prompts_count", 0)
        }
        
        if not mcp_status.get("is_running"):
            overall_healthy = False
            
    except Exception as e:
        logger.error(f"MCP服务器健康检查失败: {e}")
        health_status["components"]["mcp_server"] = {
            "status": "error",
            "error": str(e)
        }
        overall_healthy = False
    
    # 设置总体状态
    health_status["status"] = "healthy" if overall_healthy else "unhealthy"
    
    # 如果不健康，返回503状态码
    if not overall_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=health_status
        )
    
    return health_status


@router.get("/ready")
async def readiness_check(db: Session = Depends(get_db)):
    """
    就绪性检查
    
    检查服务是否准备好接收请求
    """
    ready_checks = {
        "database": False,
        "redis": False,
        "mcp_server": False
    }
    
    try:
        # 检查数据库连接
        ready_checks["database"] = check_database_health()
    except Exception:
        pass
    
    try:
        # 检查Redis连接
        ready_checks["redis"] = await check_redis_health()
    except Exception:
        pass
    
    try:
        # 检查MCP服务器
        mcp_status = get_server_status()
        ready_checks["mcp_server"] = mcp_status.get("is_running", False)
    except Exception:
        pass
    
    all_ready = all(ready_checks.values())
    
    response = {
        "ready": all_ready,
        "checks": ready_checks,
        "timestamp": datetime.now().isoformat()
    }
    
    if not all_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=response
        )
    
    return response


@router.get("/live")
async def liveness_check():
    """
    存活检查
    
    检查服务进程是否存活
    """
    return {
        "alive": True,
        "service": "mcp-service",
        "timestamp": datetime.now().isoformat(),
        "uptime_seconds": 0  # 可以添加实际的运行时间计算
    }


@router.get("/metrics")
async def get_metrics(db: Session = Depends(get_db)):
    """
    获取服务指标
    
    返回服务的性能和使用指标
    """
    try:
        # 数据库指标
        db_info = get_database_info()
        
        # Redis指标
        redis_info = await get_redis_info()
        
        # MCP服务器指标
        mcp_status = get_server_status()
        
        # 系统指标（这里可以添加CPU、内存等系统指标）
        import psutil
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "system": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_used_gb": round(memory.used / (1024**3), 2),
                "memory_total_gb": round(memory.total / (1024**3), 2),
                "disk_percent": disk.percent,
                "disk_used_gb": round(disk.used / (1024**3), 2),
                "disk_total_gb": round(disk.total / (1024**3), 2)
            },
            "database": {
                "connected": db_info.get("connected", False),
                "pool_size": db_info.get("pool_status", {}).get("pool_size", 0),
                "checked_out": db_info.get("pool_status", {}).get("checked_out", 0),
                "overflow": db_info.get("pool_status", {}).get("overflow", 0)
            },
            "redis": {
                "connected": redis_info.get("connected", False),
                "memory_used": redis_info.get("memory_used"),
                "connected_clients": redis_info.get("connected_clients", 0),
                "total_commands_processed": redis_info.get("total_commands_processed", 0)
            },
            "mcp_server": {
                "running": mcp_status.get("is_running", False),
                "tools_count": mcp_status.get("tools_count", 0),
                "resources_count": mcp_status.get("resources_count", 0),
                "prompts_count": mcp_status.get("prompts_count", 0)
            }
        }
        
        return metrics
        
    except Exception as e:
        logger.error(f"获取指标失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取指标失败: {str(e)}"
        )


@router.get("/config")
async def get_service_config():
    """
    获取服务配置信息（脱敏后）
    
    返回当前服务的主要配置信息
    """
    config_info = {
        "service_name": settings.service_name,
        "service_version": settings.service_version,
        "environment": settings.environment,
        "debug": settings.debug,
        "host": settings.host,
        "port": settings.port,
        "database_connected": True,  # 简化处理
        "redis_connected": True,     # 简化处理
        "fastmcp": {
            "name": settings.fastmcp_name,
            "version": settings.fastmcp_version,
            "description": settings.fastmcp_description
        },
        "features": {
            "metrics_enabled": settings.metrics_enabled,
            "websocket_enabled": settings.websocket_enabled,
            "enable_docs": settings.enable_docs
        },
        "limits": {
            "max_concurrent_requests": settings.max_concurrent_requests,
            "request_rate_limit": settings.request_rate_limit,
            "cache_ttl_seconds": settings.cache_ttl_seconds
        }
    }
    
    return config_info


# 导出路由
__all__ = ["router"] 