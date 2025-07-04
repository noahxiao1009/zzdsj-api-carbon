"""
消息服务API路由
提供RESTful API接口和WebSocket路由
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, status, Request, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..core.messaging import Event, EventType, MessagePriority
from ..core.websocket_manager import WebSocketMessage, MessageType
from ..middleware.auth_middleware import get_current_user, require_auth, require_permission
from ..schemas.messaging_schemas import (
    EventRequest, EventResponse, BroadcastRequest, BroadcastResponse,
    ServiceRegistrationRequest, ServiceRegistrationResponse,
    WebSocketMessageRequest, WebSocketMessageResponse
)

logger = logging.getLogger(__name__)

# 创建路由器
messaging_router = APIRouter()
websocket_router = APIRouter()


@messaging_router.post("/events/publish", response_model=EventResponse)
async def publish_event(
    event_request: EventRequest,
    request: Request,
    user: dict = Depends(require_auth)
):
    """发布事件"""
    try:
        from main import message_broker
        
        # 创建事件
        event = Event(
            id=event_request.id or f"event_{int(datetime.now().timestamp())}",
            type=EventType(event_request.type),
            source_service=event_request.source_service,
            target_service=event_request.target_service,
            data=event_request.data,
            timestamp=datetime.now(),
            priority=MessagePriority(event_request.priority),
            correlation_id=event_request.correlation_id,
            user_id=user.get("user_id")
        )
        
        # 发布事件
        success = await message_broker.publish_event(event, event_request.routing_key)
        
        if success:
            return EventResponse(
                success=True,
                message="事件发布成功",
                event_id=event.id
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="事件发布失败"
            )
            
    except Exception as e:
        logger.error(f"发布事件失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@messaging_router.post("/broadcast", response_model=BroadcastResponse)
async def broadcast_message(
    broadcast_request: BroadcastRequest,
    request: Request,
    user: dict = Depends(require_auth)
):
    """广播消息"""
    try:
        from main import websocket_manager
        
        # 创建WebSocket消息
        message = WebSocketMessage(
            type=MessageType(broadcast_request.message_type),
            data=broadcast_request.data,
            sender_id=user.get("user_id"),
            room=broadcast_request.room
        )
        
        # 根据广播类型发送
        sent_count = 0
        if broadcast_request.target_type == "all":
            sent_count = await websocket_manager.broadcast_to_all(message)
        elif broadcast_request.target_type == "room" and broadcast_request.room:
            sent_count = await websocket_manager.broadcast_to_room(broadcast_request.room, message)
        elif broadcast_request.target_type == "user" and broadcast_request.target_user_id:
            sent_count = await websocket_manager.send_to_user(broadcast_request.target_user_id, message)
        
        return BroadcastResponse(
            success=True,
            message="消息广播成功",
            sent_count=sent_count
        )
        
    except Exception as e:
        logger.error(f"广播消息失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@messaging_router.get("/connections")
async def get_connections(
    request: Request,
    user: dict = Depends(require_permission("messaging.view"))
):
    """获取当前连接信息"""
    try:
        from main import websocket_manager
        
        connections = []
        for client_id, connection in websocket_manager.active_connections.items():
            connections.append(connection.to_dict())
        
        return {
            "total_connections": len(connections),
            "connections": connections
        }
        
    except Exception as e:
        logger.error(f"获取连接信息失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@messaging_router.get("/rooms")
async def get_rooms(
    request: Request,
    user: dict = Depends(require_permission("messaging.view"))
):
    """获取房间信息"""
    try:
        from main import websocket_manager
        
        rooms_info = []
        for room_name, client_ids in websocket_manager.rooms.items():
            rooms_info.append({
                "room_name": room_name,
                "member_count": len(client_ids),
                "members": list(client_ids)
            })
        
        return {
            "total_rooms": len(rooms_info),
            "rooms": rooms_info
        }
        
    except Exception as e:
        logger.error(f"获取房间信息失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@messaging_router.post("/rooms/{room_name}/join")
async def join_room(
    room_name: str,
    client_id: str = Query(..., description="客户端ID"),
    request: Request = None,
    user: dict = Depends(require_auth)
):
    """加入房间"""
    try:
        from main import websocket_manager
        
        success = await websocket_manager.join_room(client_id, room_name)
        
        if success:
            return {"success": True, "message": f"成功加入房间 {room_name}"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="加入房间失败"
            )
            
    except Exception as e:
        logger.error(f"加入房间失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@messaging_router.post("/rooms/{room_name}/leave")
async def leave_room(
    room_name: str,
    client_id: str = Query(..., description="客户端ID"),
    request: Request = None,
    user: dict = Depends(require_auth)
):
    """离开房间"""
    try:
        from main import websocket_manager
        
        success = await websocket_manager.leave_room(client_id, room_name)
        
        if success:
            return {"success": True, "message": f"成功离开房间 {room_name}"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="离开房间失败"
            )
            
    except Exception as e:
        logger.error(f"离开房间失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@messaging_router.get("/services")
async def get_registered_services(
    request: Request,
    user: dict = Depends(require_permission("services.view"))
):
    """获取已注册的服务"""
    try:
        from main import service_registry
        
        services = await service_registry.list_services()
        
        return {
            "total_services": len(services),
            "services": [service.to_dict() for service in services]
        }
        
    except Exception as e:
        logger.error(f"获取服务列表失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@messaging_router.post("/services/register", response_model=ServiceRegistrationResponse)
async def register_service(
    registration: ServiceRegistrationRequest,
    request: Request,
    user: dict = Depends(require_permission("services.register"))
):
    """注册新服务"""
    try:
        from main import service_registry
        
        success = await service_registry.register_service(
            service_name=registration.service_name,
            service_url=registration.service_url,
            health_check_url=registration.health_check_url,
            metadata=registration.metadata
        )
        
        if success:
            return ServiceRegistrationResponse(
                success=True,
                message="服务注册成功",
                service_name=registration.service_name
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="服务注册失败"
            )
            
    except Exception as e:
        logger.error(f"服务注册失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@messaging_router.delete("/services/{service_name}")
async def unregister_service(
    service_name: str,
    request: Request,
    user: dict = Depends(require_permission("services.unregister"))
):
    """注销服务"""
    try:
        from main import service_registry
        
        success = await service_registry.unregister_service(service_name)
        
        if success:
            return {"success": True, "message": f"服务 {service_name} 注销成功"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="服务注销失败"
            )
            
    except Exception as e:
        logger.error(f"服务注销失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@messaging_router.get("/services/{service_name}/discover")
async def discover_service(
    service_name: str,
    request: Request,
    user: dict = Depends(require_auth)
):
    """发现服务"""
    try:
        from main import service_registry
        
        service_info = await service_registry.discover_service(service_name)
        
        if service_info:
            return service_info.to_dict()
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"服务 {service_name} 未找到"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"服务发现失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@messaging_router.get("/events/history")
async def get_event_history(
    request: Request,
    limit: int = Query(100, description="返回记录数量"),
    offset: int = Query(0, description="偏移量"),
    event_type: Optional[str] = Query(None, description="事件类型过滤"),
    user: dict = Depends(require_permission("events.view"))
):
    """获取事件历史（从Redis获取）"""
    try:
        from main import message_broker
        
        # 这里应该从Redis或数据库获取历史事件
        # 暂时返回空列表，实际实现需要根据存储方案调整
        return {
            "total": 0,
            "events": [],
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"获取事件历史失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# WebSocket路由
@websocket_router.get("/info")
async def websocket_info(
    request: Request,
    user: dict = Depends(require_auth)
):
    """获取WebSocket信息"""
    try:
        from main import websocket_manager
        
        return {
            "status": websocket_manager.get_status(),
            "metrics": websocket_manager.get_metrics(),
            "endpoint": f"ws://localhost:{8008}/ws/{{client_id}}"
        }
        
    except Exception as e:
        logger.error(f"获取WebSocket信息失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        ) 