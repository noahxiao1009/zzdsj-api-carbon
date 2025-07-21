"""
SSE服务管理器
SSE (Server-Sent Events) Service Manager for MCP Streaming
"""

import asyncio
import json
import logging
import uuid
from typing import Dict, List, Optional, Any, AsyncGenerator
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

from ..models.mcp_models import MCPStreamInfo, StreamType, StreamStatus

logger = logging.getLogger(__name__)

class SSEEventType(str, Enum):
    """SSE事件类型"""
    KEEPALIVE = "keepalive"
    START = "start"
    CHUNK = "chunk"
    RESULT = "result"
    ERROR = "error"
    COMPLETE = "complete"
    PROGRESS = "progress"
    STATUS = "status"

@dataclass
class SSEEvent:
    """SSE事件数据结构"""
    event_type: SSEEventType
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_sse_format(self) -> str:
        """转换为SSE格式"""
        event_data = {
            **self.data,
            "timestamp": self.timestamp.isoformat(),
            "event_id": self.event_id
        }
        
        return f"event: {self.event_type.value}\ndata: {json.dumps(event_data)}\n\n"

@dataclass
class StreamConnection:
    """流连接信息"""
    stream_id: str
    service_id: str
    user_id: Optional[str]
    tool_id: Optional[str]
    tool_name: Optional[str]
    stream_type: StreamType
    status: StreamStatus
    created_at: datetime
    last_event_at: Optional[datetime] = None
    events_sent: int = 0
    keepalive_interval: int = 30
    timeout_seconds: int = 300
    event_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    connected_clients: int = 0
    
    def is_expired(self) -> bool:
        """检查流是否过期"""
        if self.status != StreamStatus.ACTIVE:
            return True
        
        if self.last_event_at:
            return (datetime.now() - self.last_event_at).total_seconds() > self.timeout_seconds
        
        return (datetime.now() - self.created_at).total_seconds() > self.timeout_seconds
    
    def to_stream_info(self) -> MCPStreamInfo:
        """转换为流信息"""
        return MCPStreamInfo(
            stream_id=self.stream_id,
            service_id=self.service_id,
            tool_id=self.tool_id,
            user_id=self.user_id,
            stream_type=self.stream_type,
            status=self.status,
            events_sent=self.events_sent,
            created_at=self.created_at
        )

class SSEService:
    """SSE服务管理器"""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self.streams: Dict[str, StreamConnection] = {}
        self.cleanup_task: Optional[asyncio.Task] = None
        
        # 配置
        self.cleanup_interval = 60  # 清理间隔（秒）
        self.max_event_queue_size = 1000
        self.default_keepalive_interval = 30
        self.default_timeout = 300
        
        # 启动清理任务
        self._start_cleanup_task()
    
    async def create_stream(
        self,
        service_id: str,
        user_id: Optional[str] = None,
        tool_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        stream_type: StreamType = StreamType.SSE,
        keepalive_interval: int = None,
        timeout_seconds: int = None
    ) -> str:
        """创建SSE流"""
        try:
            stream_id = str(uuid.uuid4())
            
            # 创建流连接
            stream_connection = StreamConnection(
                stream_id=stream_id,
                service_id=service_id,
                user_id=user_id,
                tool_id=tool_id,
                tool_name=tool_name,
                stream_type=stream_type,
                status=StreamStatus.ACTIVE,
                created_at=datetime.now(),
                keepalive_interval=keepalive_interval or self.default_keepalive_interval,
                timeout_seconds=timeout_seconds or self.default_timeout,
                event_queue=asyncio.Queue(maxsize=self.max_event_queue_size)
            )
            
            # 存储流连接
            self.streams[stream_id] = stream_connection
            
            # 存储到Redis（如果可用）
            if self.redis_client:
                await self._store_stream_to_redis(stream_connection)
            
            # 发送初始事件
            await self.send_event(stream_id, {
                "type": "stream_created",
                "stream_id": stream_id,
                "service_id": service_id,
                "message": "Stream created successfully"
            })
            
            logger.info(f"Created SSE stream: {stream_id} for service {service_id}")
            return stream_id
            
        except Exception as e:
            logger.error(f"Failed to create SSE stream: {e}")
            raise
    
    async def stream_events(self, stream_id: str) -> AsyncGenerator[str, None]:
        """SSE事件流生成器"""
        if stream_id not in self.streams:
            yield f"event: error\ndata: {json.dumps({'error': 'Stream not found'})}\n\n"
            return
        
        stream_connection = self.streams[stream_id]
        stream_connection.connected_clients += 1
        
        try:
            last_keepalive = datetime.now()
            
            while stream_connection.status == StreamStatus.ACTIVE:
                try:
                    # 检查是否需要发送keepalive
                    now = datetime.now()
                    if (now - last_keepalive).total_seconds() >= stream_connection.keepalive_interval:
                        keepalive_event = SSEEvent(
                            event_type=SSEEventType.KEEPALIVE,
                            data={"timestamp": now.isoformat()}
                        )
                        yield keepalive_event.to_sse_format()
                        last_keepalive = now
                    
                    # 等待事件
                    try:
                        event = await asyncio.wait_for(
                            stream_connection.event_queue.get(),
                            timeout=stream_connection.keepalive_interval
                        )
                        
                        # 更新流状态
                        stream_connection.last_event_at = datetime.now()
                        stream_connection.events_sent += 1
                        
                        # 发送事件
                        if isinstance(event, SSEEvent):
                            yield event.to_sse_format()
                        else:
                            # 兼容旧格式
                            sse_event = SSEEvent(
                                event_type=SSEEventType(event.get("type", "chunk")),
                                data=event
                            )
                            yield sse_event.to_sse_format()
                        
                        # 检查是否为完成事件
                        if event.get("type") == "complete":
                            stream_connection.status = StreamStatus.COMPLETED
                            break
                        elif event.get("type") == "error":
                            stream_connection.status = StreamStatus.ERROR
                            break
                            
                    except asyncio.TimeoutError:
                        # 超时，继续循环发送keepalive
                        continue
                    
                except Exception as e:
                    logger.error(f"Error in stream {stream_id}: {e}")
                    error_event = SSEEvent(
                        event_type=SSEEventType.ERROR,
                        data={"error": str(e)}
                    )
                    yield error_event.to_sse_format()
                    stream_connection.status = StreamStatus.ERROR
                    break
            
            # 发送流结束事件
            if stream_connection.status == StreamStatus.COMPLETED:
                end_event = SSEEvent(
                    event_type=SSEEventType.COMPLETE,
                    data={"message": "Stream completed"}
                )
                yield end_event.to_sse_format()
                
        except Exception as e:
            logger.error(f"Stream {stream_id} error: {e}")
            error_event = SSEEvent(
                event_type=SSEEventType.ERROR,
                data={"error": str(e)}
            )
            yield error_event.to_sse_format()
        
        finally:
            # 减少连接计数
            stream_connection.connected_clients -= 1
            
            # 如果没有连接客户端，标记为完成
            if stream_connection.connected_clients <= 0:
                stream_connection.status = StreamStatus.COMPLETED
    
    async def send_event(self, stream_id: str, event_data: Dict[str, Any]) -> bool:
        """发送事件到指定流"""
        try:
            if stream_id not in self.streams:
                logger.warning(f"Stream {stream_id} not found for sending event")
                return False
            
            stream_connection = self.streams[stream_id]
            
            # 检查流状态
            if stream_connection.status != StreamStatus.ACTIVE:
                logger.warning(f"Stream {stream_id} is not active, status: {stream_connection.status}")
                return False
            
            # 创建SSE事件
            event = SSEEvent(
                event_type=SSEEventType(event_data.get("type", "chunk")),
                data=event_data
            )
            
            # 发送到事件队列
            try:
                await asyncio.wait_for(
                    stream_connection.event_queue.put(event),
                    timeout=5.0  # 5秒超时
                )
                return True
            except asyncio.TimeoutError:
                logger.error(f"Event queue full for stream {stream_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send event to stream {stream_id}: {e}")
            return False
    
    async def send_progress_event(self, stream_id: str, progress: int, message: str = "") -> bool:
        """发送进度事件"""
        return await self.send_event(stream_id, {
            "type": "progress",
            "progress": progress,
            "message": message
        })
    
    async def send_status_event(self, stream_id: str, status: str, message: str = "") -> bool:
        """发送状态事件"""
        return await self.send_event(stream_id, {
            "type": "status",
            "status": status,
            "message": message
        })
    
    async def send_error_event(self, stream_id: str, error: str) -> bool:
        """发送错误事件"""
        return await self.send_event(stream_id, {
            "type": "error",
            "error": error
        })
    
    async def send_complete_event(self, stream_id: str, result: Any = None) -> bool:
        """发送完成事件"""
        return await self.send_event(stream_id, {
            "type": "complete",
            "result": result
        })
    
    async def close_stream(self, stream_id: str) -> bool:
        """关闭流"""
        try:
            if stream_id not in self.streams:
                logger.warning(f"Stream {stream_id} not found for closing")
                return False
            
            stream_connection = self.streams[stream_id]
            
            # 发送完成事件
            await self.send_complete_event(stream_id)
            
            # 更新状态
            stream_connection.status = StreamStatus.COMPLETED
            
            # 从Redis移除
            if self.redis_client:
                await self._remove_stream_from_redis(stream_id)
            
            logger.info(f"Closed stream: {stream_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to close stream {stream_id}: {e}")
            return False
    
    async def get_stream_info(self, stream_id: str) -> Optional[MCPStreamInfo]:
        """获取流信息"""
        try:
            if stream_id in self.streams:
                return self.streams[stream_id].to_stream_info()
            
            # 尝试从Redis加载
            if self.redis_client:
                stream_connection = await self._load_stream_from_redis(stream_id)
                if stream_connection:
                    return stream_connection.to_stream_info()
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get stream info {stream_id}: {e}")
            return None
    
    async def get_active_streams(
        self,
        user_id: Optional[str] = None,
        service_id: Optional[str] = None
    ) -> List[MCPStreamInfo]:
        """获取活跃流列表"""
        try:
            # 从Redis恢复流（如果可用）
            if self.redis_client:
                await self._load_streams_from_redis()
            
            streams = []
            
            for stream_connection in self.streams.values():
                # 过滤条件
                if user_id and stream_connection.user_id != user_id:
                    continue
                
                if service_id and stream_connection.service_id != service_id:
                    continue
                
                # 只返回活跃的流
                if stream_connection.status == StreamStatus.ACTIVE:
                    streams.append(stream_connection.to_stream_info())
            
            return streams
            
        except Exception as e:
            logger.error(f"Failed to get active streams: {e}")
            return []
    
    async def get_stream_stats(self) -> Dict[str, Any]:
        """获取流统计信息"""
        try:
            total_streams = len(self.streams)
            active_streams = sum(1 for s in self.streams.values() if s.status == StreamStatus.ACTIVE)
            completed_streams = sum(1 for s in self.streams.values() if s.status == StreamStatus.COMPLETED)
            error_streams = sum(1 for s in self.streams.values() if s.status == StreamStatus.ERROR)
            
            total_events = sum(s.events_sent for s in self.streams.values())
            total_clients = sum(s.connected_clients for s in self.streams.values())
            
            return {
                "total_streams": total_streams,
                "active_streams": active_streams,
                "completed_streams": completed_streams,
                "error_streams": error_streams,
                "total_events_sent": total_events,
                "connected_clients": total_clients,
                "cleanup_interval": self.cleanup_interval
            }
            
        except Exception as e:
            logger.error(f"Failed to get stream stats: {e}")
            return {}
    
    async def _store_stream_to_redis(self, stream_connection: StreamConnection):
        """存储流到Redis"""
        try:
            key = f"mcp:streams:{stream_connection.stream_id}"
            
            # 构建要存储的数据
            stream_data = {
                "stream_id": stream_connection.stream_id,
                "service_id": stream_connection.service_id,
                "user_id": stream_connection.user_id,
                "tool_id": stream_connection.tool_id,
                "tool_name": stream_connection.tool_name,
                "stream_type": stream_connection.stream_type.value,
                "status": stream_connection.status.value,
                "created_at": stream_connection.created_at.isoformat(),
                "last_event_at": stream_connection.last_event_at.isoformat() if stream_connection.last_event_at else None,
                "events_sent": stream_connection.events_sent,
                "keepalive_interval": stream_connection.keepalive_interval,
                "timeout_seconds": stream_connection.timeout_seconds
            }
            
            # 存储到Redis
            await self.redis_client.set(key, json.dumps(stream_data))
            
            # 设置过期时间
            await self.redis_client.expire(key, stream_connection.timeout_seconds)
            
            # 添加到流列表
            await self.redis_client.sadd("mcp:streams:list", stream_connection.stream_id)
            
        except Exception as e:
            logger.error(f"Failed to store stream to Redis: {e}")
    
    async def _remove_stream_from_redis(self, stream_id: str):
        """从Redis移除流"""
        try:
            key = f"mcp:streams:{stream_id}"
            
            # 删除流数据
            await self.redis_client.delete(key)
            
            # 从流列表移除
            await self.redis_client.srem("mcp:streams:list", stream_id)
            
        except Exception as e:
            logger.error(f"Failed to remove stream from Redis: {e}")
    
    async def _load_streams_from_redis(self):
        """从Redis加载所有流"""
        try:
            stream_ids = await self.redis_client.smembers("mcp:streams:list")
            
            for stream_id in stream_ids:
                await self._load_stream_from_redis(stream_id)
                
        except Exception as e:
            logger.error(f"Failed to load streams from Redis: {e}")
    
    async def _load_stream_from_redis(self, stream_id: str) -> Optional[StreamConnection]:
        """从Redis加载单个流"""
        try:
            key = f"mcp:streams:{stream_id}"
            data = await self.redis_client.get(key)
            
            if data:
                stream_data = json.loads(data)
                
                # 重建流连接
                stream_connection = StreamConnection(
                    stream_id=stream_data["stream_id"],
                    service_id=stream_data["service_id"],
                    user_id=stream_data["user_id"],
                    tool_id=stream_data["tool_id"],
                    tool_name=stream_data["tool_name"],
                    stream_type=StreamType(stream_data["stream_type"]),
                    status=StreamStatus(stream_data["status"]),
                    created_at=datetime.fromisoformat(stream_data["created_at"]),
                    last_event_at=datetime.fromisoformat(stream_data["last_event_at"]) if stream_data["last_event_at"] else None,
                    events_sent=stream_data["events_sent"],
                    keepalive_interval=stream_data["keepalive_interval"],
                    timeout_seconds=stream_data["timeout_seconds"],
                    event_queue=asyncio.Queue(maxsize=self.max_event_queue_size)
                )
                
                # 只恢复活跃的流
                if stream_connection.status == StreamStatus.ACTIVE and not stream_connection.is_expired():
                    self.streams[stream_id] = stream_connection
                    return stream_connection
                    
            return None
            
        except Exception as e:
            logger.error(f"Failed to load stream from Redis: {e}")
            return None
    
    def _start_cleanup_task(self):
        """启动清理任务"""
        if self.cleanup_task is None:
            self.cleanup_task = asyncio.create_task(self._cleanup_worker())
    
    async def _cleanup_worker(self):
        """清理过期流的工作任务"""
        while True:
            try:
                expired_streams = []
                
                for stream_id, stream_connection in self.streams.items():
                    if stream_connection.is_expired():
                        expired_streams.append(stream_id)
                
                # 清理过期流
                for stream_id in expired_streams:
                    logger.info(f"Cleaning up expired stream: {stream_id}")
                    await self.close_stream(stream_id)
                    
                    # 从内存中移除
                    self.streams.pop(stream_id, None)
                
                await asyncio.sleep(self.cleanup_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup worker error: {e}")
                await asyncio.sleep(60)
    
    async def shutdown(self):
        """关闭SSE服务"""
        logger.info("Shutting down SSE service...")
        
        # 停止清理任务
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # 关闭所有流
        for stream_id in list(self.streams.keys()):
            await self.close_stream(stream_id)
        
        logger.info("SSE service shutdown complete")

# 全局SSE服务实例
_sse_service: Optional[SSEService] = None

def get_sse_service(redis_client=None) -> SSEService:
    """获取SSE服务实例"""
    global _sse_service
    if _sse_service is None:
        _sse_service = SSEService(redis_client)
    return _sse_service

async def initialize_sse_service(redis_client=None):
    """初始化SSE服务"""
    global _sse_service
    if _sse_service is None:
        _sse_service = SSEService(redis_client)
    return _sse_service