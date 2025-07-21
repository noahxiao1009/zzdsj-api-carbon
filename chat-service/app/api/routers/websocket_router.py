"""
WebSocket路由 - 实时消息传输和渲染
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.websockets import WebSocketState

from app.services.chat_manager import get_chat_manager
from app.services.message_renderer import get_message_renderer
from app.services.stream_renderer import (
    get_stream_manager, get_realtime_renderer, get_stream_event_generator
)
from app.core.dependencies import get_current_user
from app.schemas.enhanced_chat import (
    EnhancedChatRequest, MessageType, VoiceConfig, RenderConfig
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/ws", tags=["websocket"])


class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_sessions: Dict[str, List[str]] = {}
        self.session_users: Dict[str, str] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str, session_id: str):
        """建立WebSocket连接"""
        await websocket.accept()
        
        connection_id = f"{user_id}_{session_id}"
        self.active_connections[connection_id] = websocket
        
        # 记录用户会话映射
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = []
        self.user_sessions[user_id].append(session_id)
        self.session_users[session_id] = user_id
        
        logger.info(f"WebSocket连接建立: {connection_id}")
        
        # 发送连接成功消息
        await self.send_personal_message(
            connection_id,
            {
                "type": "connection_established",
                "user_id": user_id,
                "session_id": session_id,
                "timestamp": datetime.now().isoformat()
            }
        )
    
    def disconnect(self, user_id: str, session_id: str):
        """断开WebSocket连接"""
        connection_id = f"{user_id}_{session_id}"
        
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
        
        if user_id in self.user_sessions:
            if session_id in self.user_sessions[user_id]:
                self.user_sessions[user_id].remove(session_id)
            if not self.user_sessions[user_id]:
                del self.user_sessions[user_id]
        
        if session_id in self.session_users:
            del self.session_users[session_id]
        
        logger.info(f"WebSocket连接断开: {connection_id}")
    
    async def send_personal_message(self, connection_id: str, message: Dict[str, Any]):
        """发送个人消息"""
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            if websocket.client_state == WebSocketState.CONNECTED:
                try:
                    await websocket.send_text(json.dumps(message, ensure_ascii=False))
                except Exception as e:
                    logger.error(f"发送WebSocket消息失败: {e}")
                    # 连接可能已断开，清理连接
                    parts = connection_id.split('_', 1)
                    if len(parts) == 2:
                        self.disconnect(parts[0], parts[1])
    
    async def send_to_session(self, session_id: str, message: Dict[str, Any]):
        """发送消息到会话"""
        if session_id in self.session_users:
            user_id = self.session_users[session_id]
            connection_id = f"{user_id}_{session_id}"
            await self.send_personal_message(connection_id, message)
    
    async def broadcast_to_user(self, user_id: str, message: Dict[str, Any]):
        """广播消息到用户的所有会话"""
        if user_id in self.user_sessions:
            for session_id in self.user_sessions[user_id]:
                await self.send_to_session(session_id, message)
    
    def get_active_connections(self) -> List[str]:
        """获取活跃连接列表"""
        return list(self.active_connections.keys())
    
    def get_user_sessions(self, user_id: str) -> List[str]:
        """获取用户的会话列表"""
        return self.user_sessions.get(user_id, [])


# 全局连接管理器
connection_manager = ConnectionManager()


@router.websocket("/chat/{session_id}")
async def websocket_chat(
    websocket: WebSocket,
    session_id: str,
    user_id: str = "dev_user",  # 在实际应用中应该从token中获取
    chat_manager = Depends(get_chat_manager),
    renderer = Depends(get_message_renderer)
):
    """
    WebSocket聊天端点
    """
    await connection_manager.connect(websocket, user_id, session_id)
    
    # 获取渲染组件
    stream_manager = get_stream_manager(renderer)
    realtime_renderer = get_realtime_renderer(renderer)
    event_generator = get_stream_event_generator(stream_manager, realtime_renderer)
    
    try:
        while True:
            # 接收客户端消息
            try:
                data = await websocket.receive_text()
                message_data = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "error": "无效的JSON格式",
                    "timestamp": datetime.now().isoformat()
                }))
                continue
            
            # 处理不同类型的消息
            message_type = message_data.get("type", "chat")
            
            if message_type == "chat":
                await handle_chat_message(
                    websocket, session_id, user_id, message_data,
                    chat_manager, event_generator
                )
            
            elif message_type == "render_request":
                await handle_render_request(
                    websocket, session_id, message_data, renderer
                )
            
            elif message_type == "format_analysis":
                await handle_format_analysis(
                    websocket, session_id, message_data
                )
            
            elif message_type == "ping":
                await websocket.send_text(json.dumps({
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                }))
            
            else:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "error": f"未知消息类型: {message_type}",
                    "timestamp": datetime.now().isoformat()
                }))
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket客户端断开连接: {user_id}_{session_id}")
    except Exception as e:
        logger.error(f"WebSocket处理错误: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }))
    finally:
        connection_manager.disconnect(user_id, session_id)


async def handle_chat_message(
    websocket: WebSocket,
    session_id: str,
    user_id: str,
    message_data: Dict[str, Any],
    chat_manager,
    event_generator
):
    """处理聊天消息"""
    try:
        # 构造聊天请求
        request = EnhancedChatRequest(
            message=message_data.get("message", ""),
            session_id=session_id,
            agent_id=message_data.get("agent_id"),
            stream=True,
            message_type=MessageType(message_data.get("message_type", "text")),
            enable_rendering=message_data.get("enable_rendering", True),
            analyze_format=message_data.get("analyze_format", True),
            voice_config=VoiceConfig(**message_data["voice_config"]) if message_data.get("voice_config") else None
        )
        
        # 发送用户消息确认
        await websocket.send_text(json.dumps({
            "type": "user_message_received",
            "session_id": session_id,
            "message": request.message,
            "timestamp": datetime.now().isoformat()
        }))
        
        # 获取流式响应
        response_stream = await chat_manager.send_message(
            session_id=session_id,
            message=request.message,
            message_type=request.message_type.value,
            stream=True,
            voice_config=request.voice_config.dict() if request.voice_config else None
        )
        
        # 生成增强的流式事件
        async for event in event_generator.generate_enhanced_stream_events(
            session_id=session_id,
            message_stream=response_stream,
            enable_realtime_render=request.enable_rendering,
            enable_format_analysis=request.analyze_format
        ):
            await websocket.send_text(json.dumps(event.dict(), ensure_ascii=False))
    
    except Exception as e:
        logger.error(f"处理聊天消息失败: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }))


async def handle_render_request(
    websocket: WebSocket,
    session_id: str,
    message_data: Dict[str, Any],
    renderer
):
    """处理渲染请求"""
    try:
        content = message_data.get("content", "")
        render_config = message_data.get("render_config", {})
        
        # 执行渲染
        result = await renderer.auto_render(
            content,
            enable_cache=render_config.get("enable_cache", True)
        )
        
        # 发送渲染结果
        await websocket.send_text(json.dumps({
            "type": "render_result",
            "session_id": session_id,
            "request_id": message_data.get("request_id"),
            "result": result,
            "timestamp": datetime.now().isoformat()
        }))
    
    except Exception as e:
        logger.error(f"处理渲染请求失败: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "error": str(e),
            "request_id": message_data.get("request_id"),
            "timestamp": datetime.now().isoformat()
        }))


async def handle_format_analysis(
    websocket: WebSocket,
    session_id: str,
    message_data: Dict[str, Any]
):
    """处理格式分析请求"""
    try:
        from app.utils.format_detector import FormatDetector
        
        content = message_data.get("content", "")
        detector = FormatDetector()
        
        # 执行格式分析
        analysis = detector.analyze_content(content)
        
        # 发送分析结果
        await websocket.send_text(json.dumps({
            "type": "format_analysis_result",
            "session_id": session_id,
            "request_id": message_data.get("request_id"),
            "analysis": analysis,
            "timestamp": datetime.now().isoformat()
        }))
    
    except Exception as e:
        logger.error(f"处理格式分析失败: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "error": str(e),
            "request_id": message_data.get("request_id"),
            "timestamp": datetime.now().isoformat()
        }))


@router.get("/connections")
async def get_active_connections():
    """获取活跃连接信息"""
    return {
        "active_connections": connection_manager.get_active_connections(),
        "total_connections": len(connection_manager.active_connections),
        "user_sessions": connection_manager.user_sessions,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/broadcast/{user_id}")
async def broadcast_to_user(
    user_id: str,
    message: Dict[str, Any]
):
    """向用户广播消息"""
    try:
        await connection_manager.broadcast_to_user(user_id, message)
        return {
            "success": True,
            "user_id": user_id,
            "message": "消息已发送",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"广播消息失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"广播消息失败: {str(e)}"
        )


@router.post("/send/{session_id}")
async def send_to_session(
    session_id: str,
    message: Dict[str, Any]
):
    """向会话发送消息"""
    try:
        await connection_manager.send_to_session(session_id, message)
        return {
            "success": True,
            "session_id": session_id,
            "message": "消息已发送",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"发送会话消息失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"发送会话消息失败: {str(e)}"
        )


@router.get("/stats")
async def get_websocket_stats():
    """获取WebSocket统计信息"""
    return {
        "total_connections": len(connection_manager.active_connections),
        "total_users": len(connection_manager.user_sessions),
        "total_sessions": len(connection_manager.session_users),
        "average_sessions_per_user": (
            len(connection_manager.session_users) / max(len(connection_manager.user_sessions), 1)
        ),
        "connection_details": {
            "active_connections": connection_manager.get_active_connections(),
            "user_sessions": connection_manager.user_sessions,
            "session_users": connection_manager.session_users
        },
        "timestamp": datetime.now().isoformat()
    }