"""
WebSocket连接管理器
实现实时通信、连接管理、消息广播等功能
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass
from enum import Enum

from fastapi import WebSocket, WebSocketDisconnect
from .config import settings

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """连接状态"""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"


class MessageType(Enum):
    """WebSocket消息类型"""
    CHAT = "chat"
    NOTIFICATION = "notification"
    STATUS_UPDATE = "status_update"
    HEARTBEAT = "heartbeat"
    ERROR = "error"
    SYSTEM = "system"
    USER_ACTION = "user_action"


@dataclass
class WebSocketConnection:
    """WebSocket连接信息"""
    client_id: str
    websocket: WebSocket
    user_id: Optional[str]
    connected_at: datetime
    last_ping: datetime
    state: ConnectionState
    rooms: Set[str]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "client_id": self.client_id,
            "user_id": self.user_id,
            "connected_at": self.connected_at.isoformat(),
            "last_ping": self.last_ping.isoformat(),
            "state": self.state.value,
            "rooms": list(self.rooms),
            "metadata": self.metadata
        }


@dataclass
class WebSocketMessage:
    """WebSocket消息结构"""
    type: MessageType
    data: Dict[str, Any]
    sender_id: Optional[str] = None
    target_id: Optional[str] = None
    room: Optional[str] = None
    timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "type": self.type.value,
            "data": self.data,
            "sender_id": self.sender_id,
            "target_id": self.target_id,
            "room": self.room,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WebSocketMessage':
        """从字典创建消息"""
        return cls(
            type=MessageType(data["type"]),
            data=data["data"],
            sender_id=data.get("sender_id"),
            target_id=data.get("target_id"),
            room=data.get("room"),
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else None
        )


class WebSocketManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocketConnection] = {}
        self.user_connections: Dict[str, Set[str]] = {}  # user_id -> client_ids
        self.rooms: Dict[str, Set[str]] = {}  # room_name -> client_ids
        self.message_handlers: Dict[MessageType, List[callable]] = {}
        self.metrics = {
            "total_connections": 0,
            "current_connections": 0,
            "messages_sent": 0,
            "messages_received": 0,
            "connection_errors": 0,
            "heartbeat_failures": 0
        }
        self._heartbeat_task: Optional[asyncio.Task] = None
        
    async def connect(self, websocket: WebSocket, client_id: str, user_id: Optional[str] = None):
        """建立WebSocket连接"""
        try:
            # 检查连接数限制
            if len(self.active_connections) >= settings.WEBSOCKET_MAX_CONNECTIONS:
                await websocket.close(code=1013, reason="Connection limit exceeded")
                raise ValueError("连接数超出限制")
            
            # 接受连接
            await websocket.accept()
            
            # 创建连接对象
            connection = WebSocketConnection(
                client_id=client_id,
                websocket=websocket,
                user_id=user_id,
                connected_at=datetime.now(),
                last_ping=datetime.now(),
                state=ConnectionState.CONNECTED,
                rooms=set(),
                metadata={}
            )
            
            # 存储连接
            self.active_connections[client_id] = connection
            
            # 建立用户映射
            if user_id:
                if user_id not in self.user_connections:
                    self.user_connections[user_id] = set()
                self.user_connections[user_id].add(client_id)
            
            # 更新指标
            self.metrics["total_connections"] += 1
            self.metrics["current_connections"] = len(self.active_connections)
            
            # 启动心跳检测
            if not self._heartbeat_task:
                self._heartbeat_task = asyncio.create_task(self._heartbeat_monitor())
            
            # 发送欢迎消息
            await self.send_to_client(client_id, WebSocketMessage(
                type=MessageType.SYSTEM,
                data={"message": "连接成功", "client_id": client_id}
            ))
            
            logger.info(f"WebSocket连接建立: {client_id}")
            
        except Exception as e:
            logger.error(f"WebSocket连接失败: {str(e)}")
            self.metrics["connection_errors"] += 1
            raise
    
    async def disconnect(self, client_id: str):
        """断开WebSocket连接"""
        try:
            connection = self.active_connections.get(client_id)
            if not connection:
                return
            
            # 更新连接状态
            connection.state = ConnectionState.DISCONNECTING
            
            # 从房间中移除
            for room_name in connection.rooms.copy():
                await self.leave_room(client_id, room_name)
            
            # 移除用户映射
            if connection.user_id and connection.user_id in self.user_connections:
                self.user_connections[connection.user_id].discard(client_id)
                if not self.user_connections[connection.user_id]:
                    del self.user_connections[connection.user_id]
            
            # 关闭WebSocket连接
            try:
                await connection.websocket.close()
            except:
                pass
            
            # 移除连接
            del self.active_connections[client_id]
            
            # 更新指标
            self.metrics["current_connections"] = len(self.active_connections)
            
            logger.info(f"WebSocket连接断开: {client_id}")
            
        except Exception as e:
            logger.error(f"WebSocket断开失败: {str(e)}")
    
    async def send_to_client(self, client_id: str, message: WebSocketMessage) -> bool:
        """发送消息给指定客户端"""
        try:
            connection = self.active_connections.get(client_id)
            if not connection or connection.state != ConnectionState.CONNECTED:
                return False
            
            # 发送消息
            await connection.websocket.send_text(json.dumps(message.to_dict()))
            self.metrics["messages_sent"] += 1
            return True
            
        except WebSocketDisconnect:
            await self.disconnect(client_id)
            return False
        except Exception as e:
            logger.error(f"发送消息失败: {client_id}, 错误: {str(e)}")
            return False
    
    async def send_to_user(self, user_id: str, message: WebSocketMessage) -> int:
        """发送消息给指定用户的所有连接"""
        sent_count = 0
        client_ids = self.user_connections.get(user_id, set())
        
        for client_id in client_ids.copy():
            if await self.send_to_client(client_id, message):
                sent_count += 1
                
        return sent_count
    
    async def broadcast_to_room(self, room_name: str, message: WebSocketMessage, exclude_client: Optional[str] = None) -> int:
        """向房间广播消息"""
        sent_count = 0
        client_ids = self.rooms.get(room_name, set())
        
        for client_id in client_ids.copy():
            if client_id != exclude_client:
                if await self.send_to_client(client_id, message):
                    sent_count += 1
                    
        return sent_count
    
    async def broadcast_to_all(self, message: WebSocketMessage, exclude_client: Optional[str] = None) -> int:
        """向所有连接广播消息"""
        sent_count = 0
        
        for client_id in list(self.active_connections.keys()):
            if client_id != exclude_client:
                if await self.send_to_client(client_id, message):
                    sent_count += 1
                    
        return sent_count
    
    async def join_room(self, client_id: str, room_name: str) -> bool:
        """加入房间"""
        try:
            connection = self.active_connections.get(client_id)
            if not connection:
                return False
            
            # 添加到房间
            if room_name not in self.rooms:
                self.rooms[room_name] = set()
            
            self.rooms[room_name].add(client_id)
            connection.rooms.add(room_name)
            
            # 通知其他房间成员
            await self.broadcast_to_room(room_name, WebSocketMessage(
                type=MessageType.SYSTEM,
                data={"message": f"用户 {client_id} 加入房间", "room": room_name}
            ), exclude_client=client_id)
            
            logger.info(f"客户端 {client_id} 加入房间 {room_name}")
            return True
            
        except Exception as e:
            logger.error(f"加入房间失败: {str(e)}")
            return False
    
    async def leave_room(self, client_id: str, room_name: str) -> bool:
        """离开房间"""
        try:
            connection = self.active_connections.get(client_id)
            if not connection:
                return False
            
            # 从房间移除
            if room_name in self.rooms:
                self.rooms[room_name].discard(client_id)
                if not self.rooms[room_name]:
                    del self.rooms[room_name]
            
            connection.rooms.discard(room_name)
            
            # 通知其他房间成员
            if room_name in self.rooms:
                await self.broadcast_to_room(room_name, WebSocketMessage(
                    type=MessageType.SYSTEM,
                    data={"message": f"用户 {client_id} 离开房间", "room": room_name}
                ))
            
            logger.info(f"客户端 {client_id} 离开房间 {room_name}")
            return True
            
        except Exception as e:
            logger.error(f"离开房间失败: {str(e)}")
            return False
    
    async def handle_message(self, client_id: str, raw_message: str):
        """处理接收到的消息"""
        try:
            # 解析消息
            message_data = json.loads(raw_message)
            message = WebSocketMessage.from_dict(message_data)
            message.sender_id = client_id
            
            self.metrics["messages_received"] += 1
            
            # 更新心跳时间
            if client_id in self.active_connections:
                self.active_connections[client_id].last_ping = datetime.now()
            
            # 处理不同类型的消息
            await self._process_message(message)
            
        except json.JSONDecodeError:
            logger.error(f"无效的JSON消息: {client_id}")
            await self.send_to_client(client_id, WebSocketMessage(
                type=MessageType.ERROR,
                data={"error": "Invalid JSON format"}
            ))
        except Exception as e:
            logger.error(f"处理消息失败: {client_id}, 错误: {str(e)}")
    
    async def _process_message(self, message: WebSocketMessage):
        """处理具体消息"""
        # 心跳消息
        if message.type == MessageType.HEARTBEAT:
            await self.send_to_client(message.sender_id, WebSocketMessage(
                type=MessageType.HEARTBEAT,
                data={"pong": True}
            ))
            return
        
        # 执行注册的处理器
        handlers = self.message_handlers.get(message.type, [])
        for handler in handlers:
            try:
                await handler(message)
            except Exception as e:
                logger.error(f"消息处理器执行失败: {str(e)}")
    
    def register_message_handler(self, message_type: MessageType, handler: callable):
        """注册消息处理器"""
        if message_type not in self.message_handlers:
            self.message_handlers[message_type] = []
        self.message_handlers[message_type].append(handler)
    
    async def _heartbeat_monitor(self):
        """心跳监控"""
        while True:
            try:
                await asyncio.sleep(settings.WEBSOCKET_PING_INTERVAL)
                
                current_time = datetime.now()
                disconnected_clients = []
                
                for client_id, connection in self.active_connections.items():
                    # 检查心跳超时
                    time_diff = (current_time - connection.last_ping).total_seconds()
                    if time_diff > settings.WEBSOCKET_PING_TIMEOUT:
                        disconnected_clients.append(client_id)
                        self.metrics["heartbeat_failures"] += 1
                
                # 断开超时的连接
                for client_id in disconnected_clients:
                    logger.warning(f"心跳超时，断开连接: {client_id}")
                    await self.disconnect(client_id)
                
            except Exception as e:
                logger.error(f"心跳监控错误: {str(e)}")
    
    async def disconnect_all(self):
        """断开所有连接"""
        client_ids = list(self.active_connections.keys())
        for client_id in client_ids:
            await self.disconnect(client_id)
        
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
    
    def get_status(self) -> Dict[str, Any]:
        """获取连接状态"""
        return {
            "active_connections": len(self.active_connections),
            "total_rooms": len(self.rooms),
            "total_users": len(self.user_connections)
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        return self.metrics.copy()
    
    def get_connection_info(self, client_id: str) -> Optional[Dict[str, Any]]:
        """获取连接信息"""
        connection = self.active_connections.get(client_id)
        return connection.to_dict() if connection else None
    
    def get_room_members(self, room_name: str) -> List[str]:
        """获取房间成员列表"""
        return list(self.rooms.get(room_name, set())) 