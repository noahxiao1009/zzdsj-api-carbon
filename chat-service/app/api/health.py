"""
健康检查和服务状态相关API路由
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime

from app.services.chat_manager import get_chat_manager, ChatManager
from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.core.redis import redis_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["健康检查"])


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    timestamp: str
    version: str = "1.0.0"
    service: str = "chat-service"


class DetailedHealthResponse(BaseModel):
    """详细健康检查响应"""
    status: str
    timestamp: str
    version: str = "1.0.0"
    service: str = "chat-service"
    components: Dict[str, Any]
    dependencies: Dict[str, Any]


@router.get("/", response_model=HealthResponse)
async def health_check():
    """基础健康检查"""
    try:
        return HealthResponse(
            status="healthy",
            timestamp=datetime.now().isoformat(),
            version=settings.service_version,
            service="chat-service"
        )
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")


@router.get("/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check(
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """详细健康检查"""
    try:
        # 检查数据库连接
        database_status = "healthy"
        database_details = {}
        try:
            with SessionLocal() as db:
                db.execute("SELECT 1")
                database_details = {
                    "connected": True,
                    "engine": str(engine.url),
                    "pool_size": engine.pool.size(),
                    "checked_out": engine.pool.checkedout()
                }
        except Exception as e:
            database_status = "unhealthy"
            database_details = {
                "connected": False,
                "error": str(e)
            }
        
        # 检查Redis连接
        redis_status = "healthy"
        redis_details = {}
        try:
            if redis_manager.ping():
                redis_details = {
                    "connected": True,
                    "info": redis_manager.redis_client.info("server") if hasattr(redis_manager.redis_client, 'info') else "N/A"
                }
            else:
                redis_status = "unhealthy"
                redis_details = {"connected": False}
        except Exception as e:
            redis_status = "unhealthy"
            redis_details = {
                "connected": False,
                "error": str(e)
            }
        
        # 检查聊天管理器状态
        chat_manager_status = "healthy" if chat_manager.is_healthy() else "unhealthy"
        chat_manager_details = await chat_manager.get_service_status()
        
        # 确定整体状态
        overall_status = "healthy"
        if (database_status != "healthy" or 
            redis_status != "healthy" or 
            chat_manager_status != "healthy"):
            overall_status = "degraded"
        
        return DetailedHealthResponse(
            status=overall_status,
            timestamp=datetime.now().isoformat(),
            version=settings.service_version,
            service="chat-service",
            components={
                "chat_manager": {
                    "status": chat_manager_status,
                    "details": chat_manager_details
                }
            },
            dependencies={
                "database": {
                    "status": database_status,
                    "details": database_details
                },
                "redis": {
                    "status": redis_status,
                    "details": redis_details
                },
                "agno_framework": {
                    "status": "healthy",  # 从chat_manager_details中获取
                    "details": chat_manager_details.get("agno_integration", {})
                }
            }
        )
        
    except Exception as e:
        logger.error(f"详细健康检查失败: {e}")
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/readiness")
async def readiness_check(
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """就绪状态检查"""
    try:
        # 检查关键组件是否就绪
        is_ready = True
        checks = {}
        
        # 检查聊天管理器
        checks["chat_manager"] = chat_manager.is_healthy()
        
        # 检查数据库
        try:
            with SessionLocal() as db:
                db.execute("SELECT 1")
                checks["database"] = True
        except Exception:
            checks["database"] = False
            is_ready = False
        
        # 检查Redis
        checks["redis"] = redis_manager.ping()
        if not checks["redis"]:
            is_ready = False
        
        status_code = 200 if is_ready else 503
        
        return {
            "ready": is_ready,
            "timestamp": datetime.now().isoformat(),
            "checks": checks
        }
        
    except Exception as e:
        logger.error(f"就绪状态检查失败: {e}")
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/liveness")
async def liveness_check():
    """存活状态检查"""
    try:
        # 简单的存活检查
        return {
            "alive": True,
            "timestamp": datetime.now().isoformat(),
            "uptime": "unknown"  # 可以添加实际的运行时间计算
        }
    except Exception as e:
        logger.error(f"存活状态检查失败: {e}")
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/metrics")
async def get_metrics(
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """获取服务指标"""
    try:
        # 获取基础指标
        active_sessions_count = len(chat_manager.active_sessions)
        
        # 计算会话统计
        session_stats = {
            "total_active": active_sessions_count,
            "by_agent": {},
            "by_status": {}
        }
        
        for session_info in chat_manager.active_sessions.values():
            agent_id = session_info.get("agent_id", "unknown")
            status = session_info.get("status", "unknown")
            
            session_stats["by_agent"][agent_id] = session_stats["by_agent"].get(agent_id, 0) + 1
            session_stats["by_status"][status] = session_stats["by_status"].get(status, 0) + 1
        
        return {
            "timestamp": datetime.now().isoformat(),
            "service": "chat-service",
            "version": settings.service_version,
            "sessions": session_stats,
            "system": {
                "redis_connected": redis_manager.ping(),
                "agno_available": True  # 需要从agno服务获取实际状态
            }
        }
        
    except Exception as e:
        logger.error(f"获取服务指标失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
async def get_service_config():
    """获取服务配置信息（非敏感）"""
    try:
        return {
            "service": "chat-service",
            "version": settings.service_version,
            "environment": settings.environment,
            "features": {
                "voice_enabled": settings.voice_enabled,
                "websocket_enabled": settings.websocket_enabled,
                "streaming_enabled": True,
                "agno_integration": True
            },
            "limits": {
                "max_message_length": 10000,  # 可以配置化
                "max_history_length": 100,
                "session_timeout_hours": 24
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"获取服务配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 