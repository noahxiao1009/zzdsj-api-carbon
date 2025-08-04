"""
SSE连接管理器
管理所有客户端连接、消息路由和连接生命周期
"""

import asyncio
import logging
import json
from typing import Dict, Set, Optional, List, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from fastapi import Request
from fastapi.responses import StreamingResponse
import uuid

from app.models.message import SSEMessage, MessageTarget

logger = logging.getLogger(__name__)


@dataclass
class ConnectionInfo:
    """连接信息"""
    connection_id: str
    user_id: Optional[str]
    session_id: Optional[str]
    channels: Set[str]
    connected_at: datetime
    last_heartbeat: datetime
    client_ip: str
    user_agent: Optional[str]
    queue: asyncio.Queue
    is_active: bool = True


class SSEConnectionManager:
    """SSE连接管理器"""
    
    def __init__(self, heartbeat_interval: int = 30, max_queue_size: int = 1000):
        self.connections: Dict[str, ConnectionInfo] = {}
        self.channel_subscriptions: Dict[str, Set[str]] = {}  # channel -> connection_ids
        self.user_connections: Dict[str, Set[str]] = {}  # user_id -> connection_ids
        self.heartbeat_interval = heartbeat_interval
        self.max_queue_size = max_queue_size
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # 统计信息
        self.stats = {
            "total_connections": 0,
            "active_connections": 0,
            "messages_sent": 0,
            "messages_failed": 0,
            "connections_created": 0,
            "connections_closed": 0
        }
    
    async def start(self):
        """启动连接管理器"""
        logger.info("启动SSE连接管理器")
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def stop(self):
        """停止连接管理器"""
        logger.info("停止SSE连接管理器")
        
        # 停止后台任务
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._cleanup_task:
            self._cleanup_task.cancel()
        
        # 关闭所有连接
        for conn_id in list(self.connections.keys()):
            await self.disconnect(conn_id)
    
    async def connect(
        self,
        request: Request,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        channels: Optional[List[str]] = None
    ) -> str:
        """建立新连接"""
        connection_id = str(uuid.uuid4())
        channels_set = set(channels or [])
        
        # 自动添加默认频道
        if user_id:
            channels_set.add(f"user:{user_id}")
        if session_id:
            channels_set.add(f"session:{session_id}")
        
        # 创建连接信息
        conn_info = ConnectionInfo(
            connection_id=connection_id,
            user_id=user_id,
            session_id=session_id,
            channels=channels_set,
            connected_at=datetime.now(),
            last_heartbeat=datetime.now(),
            client_ip=request.client.host if request.client else "unknown",
            user_agent=request.headers.get("user-agent"),
            queue=asyncio.Queue(maxsize=self.max_queue_size)
        )
        
        # 保存连接
        self.connections[connection_id] = conn_info
        
        # 更新频道订阅
        for channel in channels_set:
            if channel not in self.channel_subscriptions:
                self.channel_subscriptions[channel] = set()
            self.channel_subscriptions[channel].add(connection_id)
        
        # 更新用户连接映射
        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(connection_id)
        
        # 更新统计
        self.stats["connections_created"] += 1
        self.stats["active_connections"] += 1
        
        logger.info(f"新SSE连接建立: {connection_id}, 用户: {user_id}, 频道: {channels_set}")
        
        return connection_id
    
    async def disconnect(self, connection_id: str):
        """断开连接"""
        if connection_id not in self.connections:
            return
        
        conn_info = self.connections[connection_id]
        
        # 标记为非活跃
        conn_info.is_active = False
        
        # 从频道订阅中移除
        for channel in conn_info.channels:
            if channel in self.channel_subscriptions:
                self.channel_subscriptions[channel].discard(connection_id)
                if not self.channel_subscriptions[channel]:
                    del self.channel_subscriptions[channel]
        
        # 从用户连接映射中移除
        if conn_info.user_id:
            if conn_info.user_id in self.user_connections:
                self.user_connections[conn_info.user_id].discard(connection_id)
                if not self.user_connections[conn_info.user_id]:
                    del self.user_connections[conn_info.user_id]
        
        # 清空消息队列
        while not conn_info.queue.empty():
            try:
                conn_info.queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        
        # 移除连接
        del self.connections[connection_id]
        
        # 更新统计
        self.stats["connections_closed"] += 1
        self.stats["active_connections"] -= 1
        
        logger.info(f"SSE连接断开: {connection_id}")
    
    async def send_message(self, message: SSEMessage) -> int:
        """发送消息到目标连接"""
        if message.is_expired():
            logger.warning(f"消息已过期，跳过发送: {message.id}")
            return 0
        
        # 获取目标频道
        target_channels = message.target.to_channels()
        target_connections = set()
        
        # 收集所有目标连接
        for channel in target_channels:
            if channel in self.channel_subscriptions:
                target_connections.update(self.channel_subscriptions[channel])
        
        # 如果没有指定频道，检查直接连接ID
        if not target_connections and message.target.connection_id:
            if message.target.connection_id in self.connections:
                target_connections.add(message.target.connection_id)
        
        if not target_connections:
            logger.warning(f"没有找到消息目标连接: {target_channels}")
            return 0
        
        # 发送消息到所有目标连接
        sent_count = 0
        failed_count = 0
        
        for conn_id in target_connections:
            if conn_id in self.connections:
                conn_info = self.connections[conn_id]
                if conn_info.is_active:
                    try:
                        # 非阻塞方式添加消息到队列
                        conn_info.queue.put_nowait(message)
                        sent_count += 1
                    except asyncio.QueueFull:
                        logger.warning(f"连接消息队列已满: {conn_id}")
                        failed_count += 1
                else:
                    failed_count += 1
        
        # 更新统计
        self.stats["messages_sent"] += sent_count
        self.stats["messages_failed"] += failed_count
        
        logger.debug(f"消息发送完成: {message.id}, 成功: {sent_count}, 失败: {failed_count}")
        
        return sent_count
    
    async def broadcast_message(self, message: SSEMessage, exclude_connections: Optional[Set[str]] = None) -> int:
        """广播消息到所有连接"""
        exclude_set = exclude_connections or set()
        sent_count = 0
        
        for conn_id, conn_info in self.connections.items():
            if conn_id not in exclude_set and conn_info.is_active:
                try:
                    conn_info.queue.put_nowait(message)
                    sent_count += 1
                except asyncio.QueueFull:
                    logger.warning(f"连接消息队列已满: {conn_id}")
        
        self.stats["messages_sent"] += sent_count
        logger.info(f"广播消息完成: {message.id}, 发送到 {sent_count} 个连接")
        
        return sent_count
    
    async def create_sse_stream(self, connection_id: str):
        """创建SSE数据流"""
        if connection_id not in self.connections:
            raise ValueError(f"连接不存在: {connection_id}")
        
        conn_info = self.connections[connection_id]
        
        async def event_stream():
            try:
                # 发送连接建立消息
                welcome_message = {
                    "id": f"welcome_{connection_id}",
                    "timestamp": datetime.now().isoformat(),
                    "type": "connection",
                    "data": {
                        "connection_id": connection_id,
                        "message": "SSE连接建立成功",
                        "channels": list(conn_info.channels)
                    }
                }
                
                yield f"data: {json.dumps(welcome_message, ensure_ascii=False)}\n\n"
                
                # 持续发送消息
                while conn_info.is_active:
                    try:
                        # 等待消息，带超时
                        message = await asyncio.wait_for(
                            conn_info.queue.get(),
                            timeout=self.heartbeat_interval
                        )
                        
                        # 发送消息
                        yield message.to_sse_format() + "\n"
                        
                        # 更新心跳时间
                        conn_info.last_heartbeat = datetime.now()
                        
                    except asyncio.TimeoutError:
                        # 发送心跳消息
                        heartbeat = f"event: heartbeat\ndata: {json.dumps({'timestamp': datetime.now().isoformat()})}\n\n"
                        yield heartbeat
                        conn_info.last_heartbeat = datetime.now()
                        
                    except Exception as e:
                        logger.error(f"发送消息出错: {e}")
                        break
                        
            except asyncio.CancelledError:
                logger.info(f"SSE流被取消: {connection_id}")
            except Exception as e:
                logger.error(f"SSE流出错: {connection_id}, {e}")
            finally:
                await self.disconnect(connection_id)
        
        return event_stream()
    
    async def update_heartbeat(self, connection_id: str):
        """更新连接心跳"""
        if connection_id in self.connections:
            self.connections[connection_id].last_heartbeat = datetime.now()
    
    def get_connection_info(self, connection_id: str) -> Optional[ConnectionInfo]:
        """获取连接信息"""
        return self.connections.get(connection_id)
    
    def get_user_connections(self, user_id: str) -> List[str]:
        """获取用户的所有连接"""
        return list(self.user_connections.get(user_id, set()))
    
    def get_channel_connections(self, channel: str) -> List[str]:
        """获取频道的所有连接"""
        return list(self.channel_subscriptions.get(channel, set()))
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        now = datetime.now()
        active_connections = sum(1 for conn in self.connections.values() if conn.is_active)
        
        return {
            **self.stats,
            "active_connections": active_connections,
            "total_channels": len(self.channel_subscriptions),
            "connections_by_user": len(self.user_connections),
            "uptime_seconds": (now - datetime.now()).total_seconds(),
            "average_queue_size": sum(conn.queue.qsize() for conn in self.connections.values()) / max(len(self.connections), 1)
        }
    
    async def _heartbeat_loop(self):
        """心跳检查循环"""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                await self._check_heartbeats()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"心跳检查出错: {e}")
    
    async def _check_heartbeats(self):
        """检查连接心跳"""
        now = datetime.now()
        timeout_threshold = timedelta(seconds=self.heartbeat_interval * 3)  # 3倍心跳间隔
        
        disconnected_connections = []
        
        for conn_id, conn_info in self.connections.items():
            if now - conn_info.last_heartbeat > timeout_threshold:
                logger.warning(f"连接心跳超时: {conn_id}")
                disconnected_connections.append(conn_id)
        
        # 断开超时连接
        for conn_id in disconnected_connections:
            await self.disconnect(conn_id)
    
    async def _cleanup_loop(self):
        """清理循环"""
        while True:
            try:
                await asyncio.sleep(300)  # 每5分钟清理一次
                await self._cleanup_expired_data()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"清理任务出错: {e}")
    
    async def _cleanup_expired_data(self):
        """清理过期数据"""
        # 清理空的频道订阅
        empty_channels = [
            channel for channel, connections in self.channel_subscriptions.items()
            if not connections
        ]
        
        for channel in empty_channels:
            del self.channel_subscriptions[channel]
        
        # 清理空的用户连接映射
        empty_users = [
            user_id for user_id, connections in self.user_connections.items()
            if not connections
        ]
        
        for user_id in empty_users:
            del self.user_connections[user_id]
        
        logger.debug(f"清理完成: 移除 {len(empty_channels)} 个空频道, {len(empty_users)} 个空用户映射")


# 全局连接管理器实例
connection_manager = SSEConnectionManager()