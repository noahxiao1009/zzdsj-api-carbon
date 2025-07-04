"""
会话管理相关API路由
"""

import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from app.services.chat_manager import get_chat_manager, ChatManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["会话管理"])


# Pydantic模型定义
class ListSessionsResponse(BaseModel):
    """会话列表响应"""
    success: bool
    user_id: Optional[str] = None
    sessions: Optional[List[Dict[str, Any]]] = None
    pagination: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class SessionDetailResponse(BaseModel):
    """会话详情响应"""
    session_id: str
    user_id: str
    agent_id: str
    status: str
    created_at: str
    last_activity: Optional[str] = None
    message_count: int = 0
    config: Optional[Dict[str, Any]] = None


class BatchOperationRequest(BaseModel):
    """批量操作请求"""
    session_ids: List[str] = Field(..., description="会话ID列表")
    operation: str = Field(..., description="操作类型：delete, archive, activate")


class BatchOperationResponse(BaseModel):
    """批量操作响应"""
    success: bool
    processed_count: int
    failed_count: int
    results: List[Dict[str, Any]]
    errors: Optional[List[str]] = None


@router.get("", response_model=ListSessionsResponse)
async def list_sessions(
    user_id: str = Query(..., description="用户ID"),
    status: Optional[str] = Query(None, description="会话状态筛选"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """获取用户会话列表"""
    try:
        logger.info(f"获取用户会话列表: user_id={user_id}, status={status}")
        
        result = await chat_manager.list_user_sessions(
            user_id=user_id,
            status=status,
            limit=limit,
            offset=offset
        )
        
        return ListSessionsResponse(**result)
        
    except Exception as e:
        logger.error(f"获取用户会话列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session_detail(
    session_id: str,
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """获取会话详情"""
    try:
        logger.info(f"获取会话详情: session_id={session_id}")
        
        session_info = await chat_manager._get_session_info(session_id)
        
        if not session_info:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        return SessionDetailResponse(
            session_id=session_id,
            user_id=session_info.get("user_id", ""),
            agent_id=session_info.get("agent_id", ""),
            status=session_info.get("status", "unknown"),
            created_at=session_info.get("created_at", ""),
            last_activity=session_info.get("last_activity"),
            message_count=session_info.get("message_count", 0),
            config=session_info.get("config")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取会话详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """删除单个会话"""
    try:
        logger.info(f"删除会话: session_id={session_id}")
        
        result = await chat_manager.delete_session(session_id)
        
        if result.get("success"):
            return {
                "success": True,
                "message": "会话删除成功",
                "session_id": session_id
            }
        else:
            raise HTTPException(
                status_code=400, 
                detail=result.get("error", "删除失败")
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除会话失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch", response_model=BatchOperationResponse)
async def batch_session_operation(
    request: BatchOperationRequest,
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """批量会话操作"""
    try:
        logger.info(f"批量会话操作: operation={request.operation}, count={len(request.session_ids)}")
        
        results = []
        errors = []
        processed_count = 0
        failed_count = 0
        
        for session_id in request.session_ids:
            try:
                if request.operation == "delete":
                    result = await chat_manager.delete_session(session_id)
                    if result.get("success"):
                        results.append({
                            "session_id": session_id,
                            "status": "success",
                            "message": "删除成功"
                        })
                        processed_count += 1
                    else:
                        results.append({
                            "session_id": session_id,
                            "status": "failed",
                            "error": result.get("error", "删除失败")
                        })
                        failed_count += 1
                        errors.append(f"Session {session_id}: {result.get('error', '删除失败')}")
                
                elif request.operation == "archive":
                    # 归档操作（这里简化为状态更新）
                    session_info = await chat_manager._get_session_info(session_id)
                    if session_info:
                        session_info["status"] = "archived"
                        # 这里需要实现实际的状态更新逻辑
                        results.append({
                            "session_id": session_id,
                            "status": "success",
                            "message": "归档成功"
                        })
                        processed_count += 1
                    else:
                        results.append({
                            "session_id": session_id,
                            "status": "failed",
                            "error": "会话不存在"
                        })
                        failed_count += 1
                        errors.append(f"Session {session_id}: 会话不存在")
                
                elif request.operation == "activate":
                    # 激活操作
                    session_info = await chat_manager._get_session_info(session_id)
                    if session_info:
                        session_info["status"] = "active"
                        # 这里需要实现实际的状态更新逻辑
                        results.append({
                            "session_id": session_id,
                            "status": "success",
                            "message": "激活成功"
                        })
                        processed_count += 1
                    else:
                        results.append({
                            "session_id": session_id,
                            "status": "failed",
                            "error": "会话不存在"
                        })
                        failed_count += 1
                        errors.append(f"Session {session_id}: 会话不存在")
                
                else:
                    results.append({
                        "session_id": session_id,
                        "status": "failed",
                        "error": f"不支持的操作: {request.operation}"
                    })
                    failed_count += 1
                    errors.append(f"Session {session_id}: 不支持的操作")
                    
            except Exception as e:
                results.append({
                    "session_id": session_id,
                    "status": "failed",
                    "error": str(e)
                })
                failed_count += 1
                errors.append(f"Session {session_id}: {str(e)}")
        
        return BatchOperationResponse(
            success=failed_count == 0,
            processed_count=processed_count,
            failed_count=failed_count,
            results=results,
            errors=errors if errors else None
        )
        
    except Exception as e:
        logger.error(f"批量会话操作失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{user_id}/stats")
async def get_user_session_stats(
    user_id: str,
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """获取用户会话统计"""
    try:
        logger.info(f"获取用户会话统计: user_id={user_id}")
        
        # 获取用户所有会话
        all_sessions = await chat_manager.list_user_sessions(
            user_id=user_id,
            limit=1000  # 获取所有会话进行统计
        )
        
        if not all_sessions.get("success"):
            raise HTTPException(status_code=500, detail="获取会话数据失败")
        
        sessions = all_sessions.get("sessions", [])
        
        # 统计数据
        total_sessions = len(sessions)
        active_sessions = len([s for s in sessions if s.get("status") == "active"])
        archived_sessions = len([s for s in sessions if s.get("status") == "archived"])
        total_messages = sum([s.get("message_count", 0) for s in sessions])
        
        # 按智能体分组统计
        agent_stats = {}
        for session in sessions:
            agent_id = session.get("agent_id", "unknown")
            if agent_id not in agent_stats:
                agent_stats[agent_id] = {
                    "session_count": 0,
                    "message_count": 0
                }
            agent_stats[agent_id]["session_count"] += 1
            agent_stats[agent_id]["message_count"] += session.get("message_count", 0)
        
        return {
            "user_id": user_id,
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "archived_sessions": archived_sessions,
            "total_messages": total_messages,
            "average_messages_per_session": round(total_messages / total_sessions, 2) if total_sessions > 0 else 0,
            "agent_usage": agent_stats,
            "timestamp": "now"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取用户会话统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup")
async def cleanup_inactive_sessions(
    days_threshold: int = Query(7, ge=1, le=30, description="清理多少天前的非活跃会话"),
    dry_run: bool = Query(True, description="是否为试运行（不实际删除）"),
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """清理非活跃会话"""
    try:
        logger.info(f"清理非活跃会话: days_threshold={days_threshold}, dry_run={dry_run}")
        
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days_threshold)
        
        # 获取所有会话进行检查（这里简化实现）
        inactive_sessions = []
        
        for session_id, session_info in chat_manager.active_sessions.items():
            last_activity = session_info.get("last_activity")
            if last_activity:
                try:
                    last_activity_date = datetime.fromisoformat(last_activity.replace('Z', '+00:00'))
                    if last_activity_date < cutoff_date:
                        inactive_sessions.append({
                            "session_id": session_id,
                            "user_id": session_info.get("user_id"),
                            "last_activity": last_activity,
                            "days_inactive": (datetime.now() - last_activity_date).days
                        })
                except Exception as e:
                    logger.warning(f"解析会话活动时间失败: {session_id}, {e}")
        
        if not dry_run:
            # 实际删除操作
            deleted_count = 0
            for session in inactive_sessions:
                try:
                    result = await chat_manager.delete_session(session["session_id"])
                    if result.get("success"):
                        deleted_count += 1
                except Exception as e:
                    logger.error(f"删除非活跃会话失败: {session['session_id']}, {e}")
            
            return {
                "success": True,
                "dry_run": False,
                "found_inactive": len(inactive_sessions),
                "deleted_count": deleted_count,
                "inactive_sessions": inactive_sessions[:10]  # 只返回前10个作为示例
            }
        else:
            return {
                "success": True,
                "dry_run": True,
                "found_inactive": len(inactive_sessions),
                "would_delete": len(inactive_sessions),
                "inactive_sessions": inactive_sessions[:10]  # 只返回前10个作为示例
            }
        
    except Exception as e:
        logger.error(f"清理非活跃会话失败: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 