"""
消息服务的服务间通信集成
提供WebSocket实时通信、事件驱动架构、服务发现、消息广播等核心功能
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Union, Set, Tuple
from datetime import datetime, timedelta
import json
import sys
import os
import uuid
from collections import defaultdict
from enum import Enum
import websockets
import aioredis

# 添加shared模块到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), "../../../shared"))

from service_client import (
    ServiceClient, 
    AsyncServiceClient,
    CallMethod, 
    CallConfig, 
    RetryStrategy,
    ServiceCallError,
    call_service,
    publish_event
)

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """消息类型枚举"""
    CHAT = "chat"
    NOTIFICATION = "notification"
    SYSTEM = "system"
    EVENT = "event"
    BROADCAST = "broadcast"
    PRIVATE = "private"


class BroadcastTarget(Enum):
    """广播目标类型"""
    ALL = "all"              # 全员广播
    ROOM = "room"            # 房间广播
    USER = "user"            # 用户广播
    SERVICE = "service"      # 服务广播


class ConnectionStatus(Enum):
    """连接状态"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"


class MessagePriority(Enum):
    """消息优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class MessageServiceIntegration:
    """消息服务集成类 - WebSocket实时通信和事件驱动架构"""
    
    def __init__(self):
        self.service_client = None
        self.async_client = None
        
        # 配置不同服务的调用参数
        self.auth_config = CallConfig(
            timeout=5,    # 认证要快
            retry_times=2,
            retry_strategy=RetryStrategy.LINEAR
        )
        
        self.base_config = CallConfig(
            timeout=10,   # 基础服务调用
            retry_times=2,
            retry_strategy=RetryStrategy.LINEAR
        )
        
        self.database_config = CallConfig(
            timeout=15,   # 数据库操作
            retry_times=3,
            retry_strategy=RetryStrategy.LINEAR
        )
        
        # 消息服务功能
        self.messaging_capabilities = {
            "websocket_realtime": {
                "description": "WebSocket实时通信",
                "features": ["real_time_chat", "live_notifications", "bidirectional_communication"]
            },
            "event_driven": {
                "description": "事件驱动架构",
                "features": ["publish_subscribe", "event_routing", "async_processing"]
            },
            "service_discovery": {
                "description": "服务注册发现",
                "features": ["dynamic_registration", "health_check", "load_balancing"]
            },
            "message_broadcast": {
                "description": "消息广播",
                "features": ["global_broadcast", "room_broadcast", "targeted_messaging"]
            },
            "connection_management": {
                "description": "连接管理",
                "features": ["connection_pool", "heartbeat", "auto_reconnect"]
            }
        }
        
        # 连接状态和统计
        self.active_connections: Dict[str, Dict[str, Any]] = {}
        self.room_members: Dict[str, Set[str]] = defaultdict(set)
        self.service_registry: Dict[str, Dict[str, Any]] = {}
        
        # 处理统计
        self.messaging_stats = {
            "total_connections": 0,
            "active_connections": 0,
            "messages_sent": 0,
            "messages_received": 0,
            "events_published": 0,
            "broadcasts_sent": 0,
            "uptime_start": datetime.now()
        }
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.service_client = ServiceClient()
        self.async_client = AsyncServiceClient()
        await self.service_client.__aenter__()
        await self.async_client.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.service_client:
            await self.service_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.async_client:
            await self.async_client.__aexit__(exc_type, exc_val, exc_tb)
    
    # ==================== 权限验证 ====================
    
    async def _verify_user_permission(self, user_id: str, action: str) -> Dict[str, Any]:
        """验证用户权限"""
        try:
            result = await self.service_client.call(
                service_name="base-service",
                method=CallMethod.POST,
                path="/api/v1/auth/check-permission",
                config=self.auth_config,
                json={
                    "user_id": user_id,
                    "resource_type": "MESSAGING",
                    "action": action,
                    "context": {
                        "service": "messaging-service",
                        "operation": action
                    }
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(f"权限验证失败: {e}")
            return {"allowed": False, "error": str(e)}
    
    # ==================== WebSocket连接管理 ====================
    
    async def handle_websocket_connection_workflow(
        self, 
        client_id: str, 
        websocket, 
        user_id: Optional[str] = None,
        additional_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """处理WebSocket连接的完整工作流"""
        try:
            start_time = datetime.now()
            logger.info(f"开始处理WebSocket连接: {client_id} (用户: {user_id})")
            
            # 1. 权限验证
            if user_id:
                auth_result = await self._verify_user_permission(user_id, "websocket_connect")
                if not auth_result.get("allowed"):
                    return {
                        "success": False,
                        "error": "权限不足",
                        "required_permission": "messaging:websocket_connect"
                    }
            
            # 2. 检查连接限制
            if len(self.active_connections) >= 1000:  # 最大连接数限制
                return {
                    "success": False,
                    "error": "服务器连接数已达上限",
                    "max_connections": 1000
                }
            
            # 3. 注册连接
            connection_info = {
                "client_id": client_id,
                "user_id": user_id,
                "websocket": websocket,
                "connected_at": start_time,
                "status": ConnectionStatus.CONNECTED.value,
                "rooms": set(),
                "last_ping": start_time,
                "metadata": additional_metadata or {},
                "message_count": 0
            }
            
            self.active_connections[client_id] = connection_info
            
            # 4. 更新统计
            self.messaging_stats["total_connections"] += 1
            self.messaging_stats["active_connections"] = len(self.active_connections)
            
            # 5. 发布连接事件
            await publish_event(
                "websocket.connected",
                {
                    "client_id": client_id,
                    "user_id": user_id,
                    "connection_time": (datetime.now() - start_time).total_seconds(),
                    "total_connections": self.messaging_stats["active_connections"],
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            # 6. 发送欢迎消息
            welcome_message = {
                "type": "system",
                "message": "连接成功",
                "client_id": client_id,
                "server_time": datetime.now().isoformat(),
                "capabilities": list(self.messaging_capabilities.keys())
            }
            
            await self.send_message_to_client(client_id, welcome_message, MessageType.SYSTEM)
            
            logger.info(f"WebSocket连接建立成功: {client_id} (总连接数: {len(self.active_connections)})")
            
            return {
                "success": True,
                "client_id": client_id,
                "connection_status": ConnectionStatus.CONNECTED.value,
                "active_connections": len(self.active_connections)
            }
            
        except Exception as e:
            logger.error(f"WebSocket连接处理失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "client_id": client_id
            }
    
    async def disconnect_websocket_workflow(self, client_id: str) -> Dict[str, Any]:
        """断开WebSocket连接的完整工作流"""
        try:
            if client_id not in self.active_connections:
                return {
                    "success": False,
                    "error": "连接不存在",
                    "client_id": client_id
                }
            
            connection_info = self.active_connections[client_id]
            user_id = connection_info.get("user_id")
            connected_duration = datetime.now() - connection_info.get("connected_at", datetime.now())
            
            # 1. 离开所有房间
            for room_name in list(connection_info.get("rooms", [])):
                await self.leave_room(room_name, client_id)
            
            # 2. 移除连接
            del self.active_connections[client_id]
            self.messaging_stats["active_connections"] = len(self.active_connections)
            
            # 3. 发布断开事件
            await publish_event(
                "websocket.disconnected",
                {
                    "client_id": client_id,
                    "user_id": user_id,
                    "connected_duration_seconds": connected_duration.total_seconds(),
                    "message_count": connection_info.get("message_count", 0),
                    "remaining_connections": self.messaging_stats["active_connections"],
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            logger.info(f"WebSocket连接断开: {client_id} (连接时长: {connected_duration.total_seconds():.1f}秒)")
            
            return {
                "success": True,
                "client_id": client_id,
                "connection_status": ConnectionStatus.DISCONNECTED.value,
                "connected_duration_seconds": connected_duration.total_seconds()
            }
            
        except Exception as e:
            logger.error(f"WebSocket断开处理失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "client_id": client_id
            }
    
    # ==================== 消息发送和接收 ====================
    
    async def send_message_to_client(
        self, 
        client_id: str, 
        message: Dict[str, Any],
        message_type: MessageType = MessageType.CHAT,
        priority: MessagePriority = MessagePriority.NORMAL
    ) -> Dict[str, Any]:
        """发送消息到指定客户端"""
        try:
            if client_id not in self.active_connections:
                return {
                    "success": False,
                    "error": "客户端连接不存在",
                    "client_id": client_id
                }
            
            connection_info = self.active_connections[client_id]
            websocket = connection_info.get("websocket")
            
            if not websocket:
                return {
                    "success": False,
                    "error": "WebSocket连接无效",
                    "client_id": client_id
                }
            
            # 构造消息
            formatted_message = {
                "id": str(uuid.uuid4()),
                "type": message_type.value,
                "priority": priority.value,
                "timestamp": datetime.now().isoformat(),
                "data": message
            }
            
            # 发送消息
            await websocket.send(json.dumps(formatted_message))
            
            # 更新统计
            self.messaging_stats["messages_sent"] += 1
            self.active_connections[client_id]["message_count"] += 1
            
            logger.debug(f"消息发送成功: {client_id} -> {message_type.value} (优先级: {priority.value})")
            
            return {
                "success": True,
                "message_id": formatted_message["id"],
                "client_id": client_id,
                "message_type": message_type.value,
                "priority": priority.value
            }
            
        except Exception as e:
            logger.error(f"消息发送失败: {e}")
            
            # 如果发送失败，可能是连接已断开，清理连接
            if "Connection is closed" in str(e) or "WebSocket" in str(e):
                await self.disconnect_websocket_workflow(client_id)
            
            return {
                "success": False,
                "error": str(e),
                "client_id": client_id
            }
    
    async def receive_message_from_client(
        self, 
        client_id: str, 
        raw_message: str
    ) -> Dict[str, Any]:
        """接收来自客户端的消息"""
        try:
            if client_id not in self.active_connections:
                return {
                    "success": False,
                    "error": "客户端连接不存在"
                }
            
            # 解析消息
            try:
                message = json.loads(raw_message)
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "error": "消息格式错误",
                    "raw_message": raw_message[:100]  # 只记录前100字符
                }
            
            message_type = message.get("type", MessageType.CHAT.value)
            message_data = message.get("data", {})
            
            # 更新连接状态
            self.active_connections[client_id]["last_ping"] = datetime.now()
            self.messaging_stats["messages_received"] += 1
            
            # 处理不同类型的消息
            if message_type == MessageType.CHAT.value:
                result = await self._handle_chat_message(client_id, message_data)
            elif message_type == MessageType.NOTIFICATION.value:
                result = await self._handle_notification_message(client_id, message_data)
            elif message_type == "ping":
                result = await self._handle_ping_message(client_id)
            else:
                result = await self._handle_generic_message(client_id, message_type, message_data)
            
            return result
            
        except Exception as e:
            logger.error(f"消息接收处理失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "client_id": client_id
            }
    
    # ==================== 房间管理 ====================
    
    async def join_room(self, room_name: str, client_id: str) -> Dict[str, Any]:
        """加入房间"""
        try:
            if client_id not in self.active_connections:
                return {
                    "success": False,
                    "error": "客户端连接不存在"
                }
            
            # 权限检查
            connection_info = self.active_connections[client_id]
            user_id = connection_info.get("user_id")
            
            if user_id:
                auth_result = await self._verify_user_permission(user_id, "join_room")
                if not auth_result.get("allowed"):
                    return {
                        "success": False,
                        "error": "权限不足"
                    }
            
            # 加入房间
            self.room_members[room_name].add(client_id)
            self.active_connections[client_id]["rooms"].add(room_name)
            
            # 通知房间其他成员
            join_notification = {
                "type": "room_event",
                "action": "user_joined",
                "room": room_name,
                "client_id": client_id,
                "user_id": user_id,
                "timestamp": datetime.now().isoformat()
            }
            
            await self.broadcast_to_room(room_name, join_notification, exclude=[client_id])
            
            logger.info(f"用户加入房间: {client_id} -> {room_name}")
            
            return {
                "success": True,
                "room_name": room_name,
                "client_id": client_id,
                "room_members_count": len(self.room_members[room_name])
            }
            
        except Exception as e:
            logger.error(f"加入房间失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "room_name": room_name,
                "client_id": client_id
            }
    
    async def leave_room(self, room_name: str, client_id: str) -> Dict[str, Any]:
        """离开房间"""
        try:
            if client_id not in self.active_connections:
                return {
                    "success": False,
                    "error": "客户端连接不存在"
                }
            
            # 离开房间
            if room_name in self.room_members:
                self.room_members[room_name].discard(client_id)
                
                # 如果房间为空，删除房间
                if not self.room_members[room_name]:
                    del self.room_members[room_name]
            
            if "rooms" in self.active_connections[client_id]:
                self.active_connections[client_id]["rooms"].discard(room_name)
            
            # 通知房间其他成员
            if room_name in self.room_members:
                connection_info = self.active_connections[client_id]
                user_id = connection_info.get("user_id")
                
                leave_notification = {
                    "type": "room_event",
                    "action": "user_left",
                    "room": room_name,
                    "client_id": client_id,
                    "user_id": user_id,
                    "timestamp": datetime.now().isoformat()
                }
                
                await self.broadcast_to_room(room_name, leave_notification)
            
            logger.info(f"用户离开房间: {client_id} <- {room_name}")
            
            return {
                "success": True,
                "room_name": room_name,
                "client_id": client_id,
                "room_members_count": len(self.room_members.get(room_name, []))
            }
            
        except Exception as e:
            logger.error(f"离开房间失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "room_name": room_name,
                "client_id": client_id
            }
    
    # ==================== 消息广播 ====================
    
    async def broadcast_to_all(
        self, 
        message: Dict[str, Any],
        message_type: MessageType = MessageType.BROADCAST
    ) -> Dict[str, Any]:
        """全员广播消息"""
        try:
            success_count = 0
            failed_count = 0
            
            for client_id in list(self.active_connections.keys()):
                result = await self.send_message_to_client(client_id, message, message_type)
                if result.get("success"):
                    success_count += 1
                else:
                    failed_count += 1
            
            self.messaging_stats["broadcasts_sent"] += 1
            
            logger.info(f"全员广播完成: 成功={success_count}, 失败={failed_count}")
            
            return {
                "success": True,
                "broadcast_type": BroadcastTarget.ALL.value,
                "success_count": success_count,
                "failed_count": failed_count,
                "total_connections": len(self.active_connections)
            }
            
        except Exception as e:
            logger.error(f"全员广播失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "broadcast_type": BroadcastTarget.ALL.value
            }
    
    async def broadcast_to_room(
        self, 
        room_name: str, 
        message: Dict[str, Any],
        message_type: MessageType = MessageType.BROADCAST,
        exclude: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """房间广播消息"""
        try:
            exclude = exclude or []
            
            if room_name not in self.room_members:
                return {
                    "success": False,
                    "error": "房间不存在",
                    "room_name": room_name
                }
            
            success_count = 0
            failed_count = 0
            
            for client_id in self.room_members[room_name]:
                if client_id not in exclude:
                    result = await self.send_message_to_client(client_id, message, message_type)
                    if result.get("success"):
                        success_count += 1
                    else:
                        failed_count += 1
            
            logger.info(f"房间广播完成 [{room_name}]: 成功={success_count}, 失败={failed_count}")
            
            return {
                "success": True,
                "broadcast_type": BroadcastTarget.ROOM.value,
                "room_name": room_name,
                "success_count": success_count,
                "failed_count": failed_count,
                "room_members_count": len(self.room_members[room_name])
            }
            
        except Exception as e:
            logger.error(f"房间广播失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "room_name": room_name
            }
    
    async def broadcast_to_user(
        self, 
        user_id: str, 
        message: Dict[str, Any],
        message_type: MessageType = MessageType.PRIVATE
    ) -> Dict[str, Any]:
        """向指定用户的所有连接广播消息"""
        try:
            user_connections = [
                client_id for client_id, info in self.active_connections.items()
                if info.get("user_id") == user_id
            ]
            
            if not user_connections:
                return {
                    "success": False,
                    "error": "用户未连接",
                    "user_id": user_id
                }
            
            success_count = 0
            failed_count = 0
            
            for client_id in user_connections:
                result = await self.send_message_to_client(client_id, message, message_type)
                if result.get("success"):
                    success_count += 1
                else:
                    failed_count += 1
            
            logger.info(f"用户广播完成 [{user_id}]: 成功={success_count}, 失败={failed_count}")
            
            return {
                "success": True,
                "broadcast_type": BroadcastTarget.USER.value,
                "user_id": user_id,
                "success_count": success_count,
                "failed_count": failed_count,
                "user_connections_count": len(user_connections)
            }
            
        except Exception as e:
            logger.error(f"用户广播失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "user_id": user_id
            }
    
    # ==================== 消息处理器 ====================
    
    async def _handle_chat_message(self, client_id: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """处理聊天消息"""
        try:
            room = message_data.get("room")
            message_content = message_data.get("message", "")
            
            if not message_content.strip():
                return {"success": False, "error": "消息内容不能为空"}
            
            connection_info = self.active_connections[client_id]
            user_id = connection_info.get("user_id")
            
            # 构造聊天消息
            chat_message = {
                "client_id": client_id,
                "user_id": user_id,
                "message": message_content,
                "timestamp": datetime.now().isoformat()
            }
            
            # 如果指定了房间，向房间广播
            if room:
                if room in connection_info.get("rooms", set()):
                    result = await self.broadcast_to_room(room, chat_message, MessageType.CHAT, exclude=[client_id])
                    return result
                else:
                    return {"success": False, "error": "您不在指定房间中"}
            else:
                # 没有指定房间，只记录消息
                return {
                    "success": True,
                    "message": "消息已接收",
                    "message_id": str(uuid.uuid4())
                }
            
        except Exception as e:
            logger.error(f"聊天消息处理失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _handle_notification_message(self, client_id: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """处理通知消息"""
        try:
            # 通知消息通常需要权限验证
            connection_info = self.active_connections[client_id]
            user_id = connection_info.get("user_id")
            
            if user_id:
                auth_result = await self._verify_user_permission(user_id, "send_notification")
                if not auth_result.get("allowed"):
                    return {"success": False, "error": "权限不足"}
            
            # 处理通知逻辑
            notification_type = message_data.get("notification_type", "general")
            content = message_data.get("content", "")
            
            # 可以在这里添加通知持久化逻辑
            
            return {
                "success": True,
                "notification_type": notification_type,
                "message": "通知已处理"
            }
            
        except Exception as e:
            logger.error(f"通知消息处理失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _handle_ping_message(self, client_id: str) -> Dict[str, Any]:
        """处理心跳消息"""
        try:
            # 更新最后心跳时间
            self.active_connections[client_id]["last_ping"] = datetime.now()
            
            # 发送pong响应
            pong_message = {
                "type": "pong",
                "timestamp": datetime.now().isoformat(),
                "server_status": "healthy"
            }
            
            await self.send_message_to_client(client_id, pong_message, MessageType.SYSTEM)
            
            return {
                "success": True,
                "message": "心跳响应已发送"
            }
            
        except Exception as e:
            logger.error(f"心跳消息处理失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _handle_generic_message(self, client_id: str, message_type: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """处理通用消息"""
        try:
            logger.info(f"收到通用消息: {client_id} -> {message_type}")
            
            return {
                "success": True,
                "message_type": message_type,
                "message": "消息已接收并处理"
            }
            
        except Exception as e:
            logger.error(f"通用消息处理失败: {e}")
            return {"success": False, "error": str(e)}
    
    # ==================== 房间管理 ====================
    
    async def join_room(self, room_name: str, client_id: str) -> Dict[str, Any]:
        """加入房间"""
        try:
            if client_id not in self.active_connections:
                return {
                    "success": False,
                    "error": "客户端连接不存在"
                }
            
            # 权限检查
            connection_info = self.active_connections[client_id]
            user_id = connection_info.get("user_id")
            
            if user_id:
                auth_result = await self._verify_user_permission(user_id, "join_room")
                if not auth_result.get("allowed"):
                    return {
                        "success": False,
                        "error": "权限不足"
                    }
            
            # 检查是否已在房间中
            if room_name in connection_info.get("rooms", set()):
                return {
                    "success": False,
                    "error": "已在房间中",
                    "room_name": room_name
                }
            
            # 加入房间
            self.room_members[room_name].add(client_id)
            self.active_connections[client_id]["rooms"].add(room_name)
            
            # 通知房间其他成员
            join_notification = {
                "type": "room_event",
                "action": "user_joined",
                "room": room_name,
                "client_id": client_id,
                "user_id": user_id,
                "timestamp": datetime.now().isoformat()
            }
            
            await self.broadcast_to_room(room_name, join_notification, MessageType.SYSTEM, exclude=[client_id])
            
            # 发布加入房间事件
            await publish_event(
                "room.user_joined",
                {
                    "room_name": room_name,
                    "client_id": client_id,
                    "user_id": user_id,
                    "room_members_count": len(self.room_members[room_name]),
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            logger.info(f"用户加入房间: {client_id} -> {room_name}")
            
            return {
                "success": True,
                "room_name": room_name,
                "client_id": client_id,
                "room_members_count": len(self.room_members[room_name])
            }
            
        except Exception as e:
            logger.error(f"加入房间失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "room_name": room_name,
                "client_id": client_id
            }
    
    async def leave_room(self, room_name: str, client_id: str) -> Dict[str, Any]:
        """离开房间"""
        try:
            if client_id not in self.active_connections:
                return {
                    "success": False,
                    "error": "客户端连接不存在"
                }
            
            connection_info = self.active_connections[client_id]
            user_id = connection_info.get("user_id")
            
            # 检查是否在房间中
            if room_name not in connection_info.get("rooms", set()):
                return {
                    "success": False,
                    "error": "不在指定房间中",
                    "room_name": room_name
                }
            
            # 离开房间
            if room_name in self.room_members:
                self.room_members[room_name].discard(client_id)
                
                # 通知房间其他成员
                leave_notification = {
                    "type": "room_event",
                    "action": "user_left",
                    "room": room_name,
                    "client_id": client_id,
                    "user_id": user_id,
                    "timestamp": datetime.now().isoformat()
                }
                
                await self.broadcast_to_room(room_name, leave_notification, MessageType.SYSTEM)
                
                # 如果房间为空，删除房间
                if not self.room_members[room_name]:
                    del self.room_members[room_name]
                    logger.info(f"房间已删除（无成员）: {room_name}")
            
            self.active_connections[client_id]["rooms"].discard(room_name)
            
            # 发布离开房间事件
            await publish_event(
                "room.user_left",
                {
                    "room_name": room_name,
                    "client_id": client_id,
                    "user_id": user_id,
                    "room_members_count": len(self.room_members.get(room_name, [])),
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            logger.info(f"用户离开房间: {client_id} <- {room_name}")
            
            return {
                "success": True,
                "room_name": room_name,
                "client_id": client_id,
                "room_members_count": len(self.room_members.get(room_name, []))
            }
            
        except Exception as e:
            logger.error(f"离开房间失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "room_name": room_name,
                "client_id": client_id
            }
    
    async def get_room_members(self, room_name: str) -> Dict[str, Any]:
        """获取房间成员列表"""
        try:
            if room_name not in self.room_members:
                return {
                    "success": False,
                    "error": "房间不存在",
                    "room_name": room_name
                }
            
            members = []
            for client_id in self.room_members[room_name]:
                if client_id in self.active_connections:
                    connection_info = self.active_connections[client_id]
                    members.append({
                        "client_id": client_id,
                        "user_id": connection_info.get("user_id"),
                        "connected_at": connection_info.get("connected_at", datetime.now()).isoformat(),
                        "last_ping": connection_info.get("last_ping", datetime.now()).isoformat()
                    })
            
            return {
                "success": True,
                "room_name": room_name,
                "members": members,
                "member_count": len(members)
            }
            
        except Exception as e:
            logger.error(f"获取房间成员失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "room_name": room_name
            }
    
    # ==================== 消息广播 ====================
    
    async def broadcast_to_all(
        self, 
        message: Dict[str, Any],
        message_type: MessageType = MessageType.BROADCAST,
        priority: MessagePriority = MessagePriority.NORMAL
    ) -> Dict[str, Any]:
        """全员广播消息"""
        try:
            success_count = 0
            failed_count = 0
            failed_clients = []
            
            for client_id in list(self.active_connections.keys()):
                result = await self.send_message_to_client(client_id, message, message_type, priority)
                if result.get("success"):
                    success_count += 1
                else:
                    failed_count += 1
                    failed_clients.append({
                        "client_id": client_id,
                        "error": result.get("error")
                    })
            
            self.messaging_stats["broadcasts_sent"] += 1
            
            # 发布广播事件
            await publish_event(
                "broadcast.sent",
                {
                    "broadcast_type": BroadcastTarget.ALL.value,
                    "message_type": message_type.value,
                    "priority": priority.value,
                    "success_count": success_count,
                    "failed_count": failed_count,
                    "total_connections": len(self.active_connections),
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            logger.info(f"全员广播完成: 成功={success_count}, 失败={failed_count}")
            
            return {
                "success": True,
                "broadcast_type": BroadcastTarget.ALL.value,
                "success_count": success_count,
                "failed_count": failed_count,
                "total_connections": len(self.active_connections),
                "failed_clients": failed_clients[:10]  # 只返回前10个失败的客户端
            }
            
        except Exception as e:
            logger.error(f"全员广播失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "broadcast_type": BroadcastTarget.ALL.value
            }
    
    async def broadcast_to_room(
        self, 
        room_name: str, 
        message: Dict[str, Any],
        message_type: MessageType = MessageType.BROADCAST,
        exclude: Optional[List[str]] = None,
        priority: MessagePriority = MessagePriority.NORMAL
    ) -> Dict[str, Any]:
        """房间广播消息"""
        try:
            exclude = exclude or []
            
            if room_name not in self.room_members:
                return {
                    "success": False,
                    "error": "房间不存在",
                    "room_name": room_name
                }
            
            success_count = 0
            failed_count = 0
            failed_clients = []
            
            for client_id in self.room_members[room_name]:
                if client_id not in exclude:
                    result = await self.send_message_to_client(client_id, message, message_type, priority)
                    if result.get("success"):
                        success_count += 1
                    else:
                        failed_count += 1
                        failed_clients.append({
                            "client_id": client_id,
                            "error": result.get("error")
                        })
            
            logger.info(f"房间广播完成 [{room_name}]: 成功={success_count}, 失败={failed_count}")
            
            return {
                "success": True,
                "broadcast_type": BroadcastTarget.ROOM.value,
                "room_name": room_name,
                "success_count": success_count,
                "failed_count": failed_count,
                "room_members_count": len(self.room_members[room_name]),
                "failed_clients": failed_clients
            }
            
        except Exception as e:
            logger.error(f"房间广播失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "room_name": room_name
            }
    
    async def broadcast_to_user(
        self, 
        user_id: str, 
        message: Dict[str, Any],
        message_type: MessageType = MessageType.PRIVATE,
        priority: MessagePriority = MessagePriority.NORMAL
    ) -> Dict[str, Any]:
        """向指定用户的所有连接广播消息"""
        try:
            user_connections = [
                client_id for client_id, info in self.active_connections.items()
                if info.get("user_id") == user_id
            ]
            
            if not user_connections:
                return {
                    "success": False,
                    "error": "用户未连接",
                    "user_id": user_id
                }
            
            success_count = 0
            failed_count = 0
            failed_clients = []
            
            for client_id in user_connections:
                result = await self.send_message_to_client(client_id, message, message_type, priority)
                if result.get("success"):
                    success_count += 1
                else:
                    failed_count += 1
                    failed_clients.append({
                        "client_id": client_id,
                        "error": result.get("error")
                    })
            
            logger.info(f"用户广播完成 [{user_id}]: 成功={success_count}, 失败={failed_count}")
            
            return {
                "success": True,
                "broadcast_type": BroadcastTarget.USER.value,
                "user_id": user_id,
                "success_count": success_count,
                "failed_count": failed_count,
                "user_connections_count": len(user_connections),
                "failed_clients": failed_clients
            }
            
        except Exception as e:
            logger.error(f"用户广播失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "user_id": user_id
            }
    
    # ==================== 事件发布和订阅 ====================
    
    async def publish_service_event(
        self,
        event_type: str,
        source_service: str,
        target_service: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        priority: MessagePriority = MessagePriority.NORMAL
    ) -> Dict[str, Any]:
        """发布服务间事件"""
        try:
            event_data = {
                "event_id": str(uuid.uuid4()),
                "type": event_type,
                "source_service": source_service,
                "target_service": target_service,
                "data": data or {},
                "priority": priority.value,
                "timestamp": datetime.now().isoformat()
            }
            
            # 发布到消息队列
            await publish_event(f"service.{event_type}", event_data)
            
            # 更新统计
            self.messaging_stats["events_published"] += 1
            
            logger.info(f"服务事件发布: {source_service} -> {target_service} ({event_type})")
            
            return {
                "success": True,
                "event_id": event_data["event_id"],
                "event_type": event_type,
                "source_service": source_service,
                "target_service": target_service
            }
            
        except Exception as e:
            logger.error(f"事件发布失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "event_type": event_type
            }
    
    async def broadcast_system_notification(
        self,
        notification_type: str,
        title: str,
        content: str,
        target_type: BroadcastTarget = BroadcastTarget.ALL,
        target_id: Optional[str] = None,
        priority: MessagePriority = MessagePriority.NORMAL
    ) -> Dict[str, Any]:
        """广播系统通知"""
        try:
            notification_data = {
                "notification_id": str(uuid.uuid4()),
                "type": notification_type,
                "title": title,
                "content": content,
                "priority": priority.value,
                "timestamp": datetime.now().isoformat()
            }
            
            if target_type == BroadcastTarget.ALL:
                result = await self.broadcast_to_all(notification_data, MessageType.NOTIFICATION, priority)
            elif target_type == BroadcastTarget.ROOM and target_id:
                result = await self.broadcast_to_room(target_id, notification_data, MessageType.NOTIFICATION, priority=priority)
            elif target_type == BroadcastTarget.USER and target_id:
                result = await self.broadcast_to_user(target_id, notification_data, MessageType.NOTIFICATION, priority)
            else:
                return {
                    "success": False,
                    "error": "无效的目标类型或缺少目标ID"
                }
            
            return result
            
        except Exception as e:
            logger.error(f"系统通知广播失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # ==================== 服务注册发现 ====================
    
    async def register_service(
        self,
        service_name: str,
        service_url: str,
        health_check_url: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """注册服务"""
        try:
            service_info = {
                "service_name": service_name,
                "service_url": service_url,
                "health_check_url": health_check_url,
                "metadata": metadata or {},
                "registered_at": datetime.now(),
                "last_health_check": None,
                "status": "registered"
            }
            
            self.service_registry[service_name] = service_info
            
            # 发布服务注册事件
            await publish_event(
                "service.registered",
                {
                    "service_name": service_name,
                    "service_url": service_url,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            logger.info(f"服务注册成功: {service_name} -> {service_url}")
            
            return {
                "success": True,
                "service_name": service_name,
                "status": "registered"
            }
            
        except Exception as e:
            logger.error(f"服务注册失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "service_name": service_name
            }
    
    async def get_service_stats(self) -> Dict[str, Any]:
        """获取消息服务统计信息"""
        try:
            current_time = datetime.now()
            uptime_seconds = (current_time - self.messaging_stats["uptime_start"]).total_seconds()
            
            # 按用户ID分组统计
            user_connections = defaultdict(int)
            for connection_info in self.active_connections.values():
                user_id = connection_info.get("user_id")
                if user_id:
                    user_connections[user_id] += 1
            
            stats = {
                "current_connections": len(self.active_connections),
                "total_connections_ever": self.messaging_stats["total_connections"],
                "active_rooms": len(self.room_members),
                "unique_users": len(user_connections),
                "messages_sent": self.messaging_stats["messages_sent"],
                "messages_received": self.messaging_stats["messages_received"],
                "events_published": self.messaging_stats["events_published"],
                "broadcasts_sent": self.messaging_stats["broadcasts_sent"],
                "registered_services": len(self.service_registry),
                "uptime_seconds": uptime_seconds,
                "server_status": "healthy" if len(self.active_connections) < 1000 else "busy",
                "timestamp": current_time.isoformat()
            }
            
            return {
                "success": True,
                "stats": stats,
                "capabilities": self.messaging_capabilities
            }
            
        except Exception as e:
            logger.error(f"获取服务统计失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# ==================== 便捷的全局函数 ====================

async def send_realtime_message(client_id: str, message: Dict[str, Any], message_type: str = "chat") -> Dict[str, Any]:
    """便捷的实时消息发送函数"""
    async with MessageServiceIntegration() as msg_service:
        return await msg_service.send_message_to_client(
            client_id, message, MessageType(message_type)
        )


async def broadcast_notification(title: str, content: str, target_type: str = "all", target_id: Optional[str] = None) -> Dict[str, Any]:
    """便捷的通知广播函数"""
    async with MessageServiceIntegration() as msg_service:
        return await msg_service.broadcast_system_notification(
            "general", title, content, BroadcastTarget(target_type), target_id
        )


async def join_chat_room(room_name: str, client_id: str) -> Dict[str, Any]:
    """便捷的加入聊天室函数"""
    async with MessageServiceIntegration() as msg_service:
        return await msg_service.join_room(room_name, client_id)


async def publish_event_to_services(event_type: str, source_service: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """便捷的服务间事件发布函数"""
    async with MessageServiceIntegration() as msg_service:
        return await msg_service.publish_service_event(event_type, source_service, data=data)


# ==================== 使用示例 ====================

async def messaging_service_demo():
    """消息服务集成模块"""
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    async with MessageServiceIntegration() as msg_service:
        
        # 1. 服务统计
        logger.info("=== 📊 服务统计信息 ===")
        stats_result = await msg_service.get_service_stats()
        if stats_result.get("success"):
            stats = stats_result["stats"]
            print(f"当前连接数: {stats['current_connections']}")
            print(f"活跃房间数: {stats['active_rooms']}")
            print(f"发送消息数: {stats['messages_sent']}")
            print(f"接收消息数: {stats['messages_received']}")
            print(f"运行时间: {stats['uptime_seconds']:.1f}秒")
        
        # 2. 模拟WebSocket连接
        logger.info("\n=== 🔌 模拟WebSocket连接 ===")
        class MockWebSocket:
            async def send(self, data): 
                print(f"发送: {data}")
        
        mock_ws = MockWebSocket()
        connect_result = await msg_service.handle_websocket_connection_workflow(
            "client_001", mock_ws, "user_123"
        )
        print(f"连接结果: {connect_result}")
        
        # 3. 房间操作
        logger.info("\n=== 🏠 房间管理 ===")
        join_result = await msg_service.join_room("general", "client_001")
        print(f"加入房间: {join_result}")
        
        members_result = await msg_service.get_room_members("general")
        print(f"房间成员: {members_result}")
        
        # 4. 消息发送
        logger.info("\n=== 💬 消息发送 ===")
        message_data = {
            "content": "Hello, messaging service!",
            "sender": "user_123"
        }
        
        send_result = await msg_service.send_message_to_client(
            "client_001", message_data, MessageType.CHAT, MessagePriority.NORMAL
        )
        print(f"消息发送: {send_result}")
        
        # 5. 广播测试
        logger.info("\n=== 📢 广播测试 ===")
        notification_result = await msg_service.broadcast_system_notification(
            "maintenance", 
            "系统维护通知", 
            "系统将在30分钟后进行维护，请及时保存工作。",
            BroadcastTarget.ALL
        )
        print(f"系统通知广播: {notification_result}")
        
        # 6. 事件发布
        logger.info("\n=== 📡 事件发布 ===")
        event_result = await msg_service.publish_service_event(
            "user_action",
            "messaging-service",
            "base-service",
            {"action": "user_login", "user_id": "user_123"}
        )
        print(f"事件发布: {event_result}")
        
        # 7. 服务注册
        logger.info("\n=== 🏗️ 服务注册 ===")
        register_result = await msg_service.register_service(
            "test-service",
            "http://localhost:8999",
            "http://localhost:8999/health",
            {"version": "1.0.0", "description": "测试服务"}
        )
        print(f"服务注册: {register_result}")
        
        # 8. 清理连接
        logger.info("\n=== 🧹 清理连接 ===")
        disconnect_result = await msg_service.disconnect_websocket_workflow("client_001")
        print(f"断开连接: {disconnect_result}")
        
        # 9. 最终统计
        logger.info("\n=== 📈 最终统计 ===")
        final_stats = await msg_service.get_service_stats()
        if final_stats.get("success"):
            print(f"最终统计: {final_stats['stats']}")


# 简单的单用途函数示例
async def simple_messaging_examples():
    """简单使用示例"""
    
    # 发送实时消息
    result1 = await send_realtime_message("client_123", {"message": "Hello!"})
    print(f"发送消息: {result1}")
    
    # 广播通知
    result2 = await broadcast_notification("系统通知", "欢迎使用消息服务")
    print(f"广播通知: {result2}")
    
    # 加入聊天室
    result3 = await join_chat_room("tech_discuss", "client_123")
    print(f"加入聊天室: {result3}")
    
    # 发布事件
    result4 = await publish_event_to_services("data_updated", "messaging-service", {"table": "messages"})
    print(f"发布事件: {result4}")


if __name__ == "__main__":
    print("🚀 消息服务集成启动")
    print("=" * 50)
    asyncio.run(messaging_service_demo())