"""
SSE API路由
提供SSE连接、消息推送和管理接口
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Request, Query, Path, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.connection_manager import connection_manager
from app.core.message_queue import message_queue
from app.models.message import SSEMessage, MessageTarget, MessageType, MessagePriority

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sse", tags=["SSE推送"])


class SSEConnectionRequest(BaseModel):
    """SSE连接请求"""
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    channels: Optional[List[str]] = None


class MessageSendRequest(BaseModel):
    """消息发送请求"""
    type: MessageType
    service: str
    source: str
    target: MessageTarget
    data: Dict[str, Any]
    priority: MessagePriority = MessagePriority.NORMAL
    ttl: int = 3600


class BroadcastRequest(BaseModel):
    """广播消息请求"""
    type: MessageType
    service: str
    source: str
    data: Dict[str, Any]
    exclude_connections: Optional[List[str]] = None


# ================================
# SSE连接端点
# ================================

@router.get("/stream",
           summary="建立SSE连接",
           description="建立通用SSE连接，支持多频道订阅")
async def create_sse_stream(
    request: Request,
    user_id: Optional[str] = Query(None, description="用户ID"),
    session_id: Optional[str] = Query(None, description="会话ID"),
    channels: Optional[str] = Query(None, description="订阅频道，逗号分隔")
):
    """建立SSE连接"""
    try:
        # 解析频道列表
        channel_list = []
        if channels:
            channel_list = [ch.strip() for ch in channels.split(",") if ch.strip()]
        
        # 建立连接
        connection_id = await connection_manager.connect(
            request=request,
            user_id=user_id,
            session_id=session_id,
            channels=channel_list
        )
        
        # 创建SSE流
        event_stream = await connection_manager.create_sse_stream(connection_id)
        
        return StreamingResponse(
            event_stream,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control",
                "X-Connection-ID": connection_id
            }
        )
        
    except Exception as e:
        logger.error(f"建立SSE连接失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{user_id}",
           summary="用户专用SSE连接",
           description="为指定用户建立SSE连接")
async def create_user_sse_stream(
    request: Request,
    user_id: str = Path(..., description="用户ID"),
    session_id: Optional[str] = Query(None, description="会话ID")
):
    """用户专用SSE连接"""
    try:
        connection_id = await connection_manager.connect(
            request=request,
            user_id=user_id,
            session_id=session_id,
            channels=[f"user:{user_id}"]
        )
        
        event_stream = await connection_manager.create_sse_stream(connection_id)
        
        return StreamingResponse(
            event_stream,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control",
                "X-Connection-ID": connection_id,
                "X-User-ID": user_id
            }
        )
        
    except Exception as e:
        logger.error(f"建立用户SSE连接失败: {user_id}, {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/service/{service_name}",
           summary="服务专用SSE连接",
           description="监听指定服务的消息")
async def create_service_sse_stream(
    request: Request,
    service_name: str = Path(..., description="服务名称"),
    user_id: Optional[str] = Query(None, description="用户ID")
):
    """服务专用SSE连接"""
    try:
        channels = [f"service:{service_name}"]
        if user_id:
            channels.append(f"user:{user_id}")
        
        connection_id = await connection_manager.connect(
            request=request,
            user_id=user_id,
            channels=channels
        )
        
        event_stream = await connection_manager.create_sse_stream(connection_id)
        
        return StreamingResponse(
            event_stream,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control",
                "X-Connection-ID": connection_id,
                "X-Service": service_name
            }
        )
        
    except Exception as e:
        logger.error(f"建立服务SSE连接失败: {service_name}, {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/task/{task_id}",
           summary="任务专用SSE连接",
           description="监听指定任务的进度和状态")
async def create_task_sse_stream(
    request: Request,
    task_id: str = Path(..., description="任务ID"),
    user_id: Optional[str] = Query(None, description="用户ID")
):
    """任务专用SSE连接"""
    try:
        channels = [f"task:{task_id}"]
        if user_id:
            channels.append(f"user:{user_id}")
        
        connection_id = await connection_manager.connect(
            request=request,
            user_id=user_id,
            channels=channels
        )
        
        event_stream = await connection_manager.create_sse_stream(connection_id)
        
        return StreamingResponse(
            event_stream,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control",
                "X-Connection-ID": connection_id,
                "X-Task-ID": task_id
            }
        )
        
    except Exception as e:
        logger.error(f"建立任务SSE连接失败: {task_id}, {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ================================
# 消息推送API
# ================================

@router.post("/api/v1/messages/send",
            summary="发送消息",
            description="发送消息到指定目标")
async def send_message(request: MessageSendRequest):
    """发送消息"""
    try:
        # 创建SSE消息
        message = SSEMessage(
            type=request.type,
            service=request.service,
            source=request.source,
            target=request.target,
            data=request.data,
            metadata={
                "priority": request.priority,
                "ttl": request.ttl
            }
        )
        
        # 发送消息
        sent_count = await connection_manager.send_message(message)
        
        # 也发布到消息队列（用于持久化和集群支持）
        await message_queue.publish_message(message)
        
        return {
            "success": True,
            "message_id": message.id,
            "sent_to_connections": sent_count,
            "timestamp": message.timestamp.isoformat()
        }
        
    except Exception as e:
        logger.error(f"发送消息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/v1/messages/broadcast",
            summary="广播消息",
            description="广播消息到所有连接")
async def broadcast_message(request: BroadcastRequest):
    """广播消息"""
    try:
        # 创建广播消息
        message = SSEMessage(
            type=request.type,
            service=request.service,
            source=request.source,
            target=MessageTarget(),  # 空目标表示广播
            data=request.data
        )
        
        # 广播消息
        exclude_set = set(request.exclude_connections or [])
        sent_count = await connection_manager.broadcast_message(message, exclude_set)
        
        # 发布到消息队列
        await message_queue.broadcast_message(message)
        
        return {
            "success": True,
            "message_id": message.id,
            "sent_to_connections": sent_count,
            "timestamp": message.timestamp.isoformat()
        }
        
    except Exception as e:
        logger.error(f"广播消息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/v1/messages/batch",
            summary="批量发送消息",
            description="批量发送多条消息")
async def send_batch_messages(messages: List[MessageSendRequest]):
    """批量发送消息"""
    try:
        results = []
        
        for req in messages:
            try:
                message = SSEMessage(
                    type=req.type,
                    service=req.service,
                    source=req.source,
                    target=req.target,
                    data=req.data,
                    metadata={
                        "priority": req.priority,
                        "ttl": req.ttl
                    }
                )
                
                sent_count = await connection_manager.send_message(message)
                await message_queue.publish_message(message)
                
                results.append({
                    "success": True,
                    "message_id": message.id,
                    "sent_to_connections": sent_count
                })
                
            except Exception as e:
                results.append({
                    "success": False,
                    "error": str(e)
                })
        
        successful_count = sum(1 for r in results if r.get("success"))
        
        return {
            "success": True,
            "total_messages": len(messages),
            "successful_count": successful_count,
            "failed_count": len(messages) - successful_count,
            "results": results
        }
        
    except Exception as e:
        logger.error(f"批量发送消息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ================================
# 连接管理API
# ================================

@router.get("/api/v1/connections",
           summary="获取活跃连接",
           description="获取当前所有活跃的SSE连接")
async def get_connections(
    user_id: Optional[str] = Query(None, description="过滤用户ID"),
    limit: int = Query(100, description="返回数量限制")
):
    """获取活跃连接列表"""
    try:
        connections = []
        count = 0
        
        for conn_id, conn_info in connection_manager.connections.items():
            if count >= limit:
                break
                
            if user_id and conn_info.user_id != user_id:
                continue
                
            if conn_info.is_active:
                connections.append({
                    "connection_id": conn_id,
                    "user_id": conn_info.user_id,
                    "session_id": conn_info.session_id,
                    "channels": list(conn_info.channels),
                    "connected_at": conn_info.connected_at.isoformat(),
                    "last_heartbeat": conn_info.last_heartbeat.isoformat(),
                    "client_ip": conn_info.client_ip,
                    "queue_size": conn_info.queue.qsize()
                })
                count += 1
        
        return {
            "success": True,
            "total_connections": len(connections),
            "connections": connections
        }
        
    except Exception as e:
        logger.error(f"获取连接列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/v1/connections/stats",
           summary="连接统计",
           description="获取连接统计信息")
async def get_connection_stats():
    """获取连接统计信息"""
    try:
        stats = connection_manager.get_stats()
        return {
            "success": True,
            "stats": stats
        }
        
    except Exception as e:
        logger.error(f"获取连接统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/v1/connections/{connection_id}",
              summary="断开连接",
              description="强制断开指定连接")
async def disconnect_connection(connection_id: str = Path(..., description="连接ID")):
    """断开指定连接"""
    try:
        if connection_id not in connection_manager.connections:
            raise HTTPException(status_code=404, detail="连接不存在")
        
        await connection_manager.disconnect(connection_id)
        
        return {
            "success": True,
            "message": f"连接 {connection_id} 已断开"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"断开连接失败: {connection_id}, {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/v1/channels/{channel}/connections",
           summary="获取频道连接",
           description="获取订阅指定频道的连接")
async def get_channel_connections(channel: str = Path(..., description="频道名称")):
    """获取频道连接"""
    try:
        connection_ids = connection_manager.get_channel_connections(channel)
        
        connections = []
        for conn_id in connection_ids:
            conn_info = connection_manager.get_connection_info(conn_id)
            if conn_info and conn_info.is_active:
                connections.append({
                    "connection_id": conn_id,
                    "user_id": conn_info.user_id,
                    "connected_at": conn_info.connected_at.isoformat(),
                    "queue_size": conn_info.queue.qsize()
                })
        
        return {
            "success": True,
            "channel": channel,
            "connection_count": len(connections),
            "connections": connections
        }
        
    except Exception as e:
        logger.error(f"获取频道连接失败: {channel}, {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ================================
# 健康检查和监控
# ================================

@router.get("/health",
           summary="健康检查",
           description="检查SSE服务健康状态")
async def health_check():
    """健康检查"""
    try:
        # 检查连接管理器状态
        conn_stats = connection_manager.get_stats()
        
        # 检查消息队列状态
        queue_health = await message_queue.health_check()
        
        return {
            "status": "healthy" if queue_health.get("status") == "healthy" else "degraded",
            "service": "message-push-service",
            "version": "1.0.0",
            "timestamp": asyncio.get_event_loop().time(),
            "connection_manager": {
                "status": "healthy",
                "active_connections": conn_stats.get("active_connections", 0),
                "total_channels": conn_stats.get("total_channels", 0)
            },
            "message_queue": queue_health
        }
        
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": asyncio.get_event_loop().time()
        }