"""
消息队列管理器
基于Redis实现高性能消息队列和发布订阅
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
import redis.asyncio as redis
from redis.asyncio import Redis

from app.models.message import SSEMessage, MessageType

logger = logging.getLogger(__name__)


class MessageQueueManager:
    """消息队列管理器"""
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/2",
        stream_name: str = "sse_messages",
        pubsub_channel: str = "sse_broadcast",
        max_stream_length: int = 10000,
        consumer_group: str = "sse_consumers"
    ):
        self.redis_url = redis_url
        self.stream_name = stream_name
        self.pubsub_channel = pubsub_channel
        self.max_stream_length = max_stream_length
        self.consumer_group = consumer_group
        
        self._redis: Optional[Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None
        self._consumer_task: Optional[asyncio.Task] = None
        self._message_handlers: Dict[str, Callable] = {}
        
        # 统计信息
        self.stats = {
            "messages_published": 0,
            "messages_consumed": 0,
            "messages_failed": 0,
            "last_message_time": None
        }
    
    async def connect(self):
        """连接Redis"""
        try:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
            
            # 测试连接
            await self._redis.ping()
            logger.info(f"Redis连接成功: {self.redis_url}")
            
            # 创建消费者组
            try:
                await self._redis.xgroup_create(
                    self.stream_name,
                    self.consumer_group,
                    id="0",
                    mkstream=True
                )
                logger.info(f"创建消费者组: {self.consumer_group}")
            except Exception as e:
                if "BUSYGROUP" in str(e):
                    logger.info(f"消费者组已存在: {self.consumer_group}")
                else:
                    raise
            
            # 设置发布订阅
            self._pubsub = self._redis.pubsub()
            await self._pubsub.subscribe(self.pubsub_channel)
            
            logger.info("消息队列管理器初始化完成")
            
        except Exception as e:
            logger.error(f"Redis连接失败: {e}")
            raise
    
    async def disconnect(self):
        """断开Redis连接"""
        if self._consumer_task:
            self._consumer_task.cancel()
        
        if self._pubsub:
            await self._pubsub.unsubscribe(self.pubsub_channel)
            await self._pubsub.close()
        
        if self._redis:
            await self._redis.close()
        
        logger.info("消息队列管理器已断开")
    
    async def publish_message(self, message: SSEMessage) -> str:
        """发布消息到流"""
        if not self._redis:
            raise RuntimeError("Redis未连接")
        
        try:
            # 序列化消息
            message_data = {
                "id": message.id,
                "timestamp": message.timestamp.isoformat(),
                "type": message.type,
                "service": message.service,
                "source": message.source,
                "target": json.dumps(message.target.dict()),
                "data": json.dumps(message.data),
                "metadata": json.dumps(message.metadata.dict())
            }
            
            # 添加到Redis Stream
            message_id = await self._redis.xadd(
                self.stream_name,
                message_data,
                maxlen=self.max_stream_length,
                approximate=True
            )
            
            # 更新统计
            self.stats["messages_published"] += 1
            self.stats["last_message_time"] = datetime.now().isoformat()
            
            logger.debug(f"消息发布成功: {message.id} -> {message_id}")
            
            return message_id
            
        except Exception as e:
            self.stats["messages_failed"] += 1
            logger.error(f"消息发布失败: {message.id}, {e}")
            raise
    
    async def broadcast_message(self, message: SSEMessage) -> bool:
        """广播消息"""
        if not self._redis:
            raise RuntimeError("Redis未连接")
        
        try:
            # 序列化消息为JSON
            message_json = json.dumps({
                "id": message.id,
                "timestamp": message.timestamp.isoformat(),
                "type": message.type,
                "service": message.service,
                "source": message.source,
                "target": message.target.dict(),
                "data": message.data,
                "metadata": message.metadata.dict()
            }, ensure_ascii=False)
            
            # 发布到频道
            subscriber_count = await self._redis.publish(self.pubsub_channel, message_json)
            
            logger.debug(f"广播消息: {message.id}, 接收者: {subscriber_count}")
            
            return subscriber_count > 0
            
        except Exception as e:
            logger.error(f"广播消息失败: {message.id}, {e}")
            return False
    
    async def consume_messages(self, consumer_name: str = "default", batch_size: int = 10):
        """消费消息"""
        if not self._redis:
            raise RuntimeError("Redis未连接")
        
        logger.info(f"开始消费消息: {consumer_name}")
        
        try:
            while True:
                try:
                    # 从流中读取消息
                    messages = await self._redis.xreadgroup(
                        self.consumer_group,
                        consumer_name,
                        {self.stream_name: ">"},
                        count=batch_size,
                        block=1000  # 1秒超时
                    )
                    
                    if not messages:
                        continue
                    
                    # 处理消息
                    for stream, stream_messages in messages:
                        for message_id, field_dict in stream_messages:
                            await self._process_message(message_id, field_dict)
                            
                            # 确认消息处理完成
                            await self._redis.xack(
                                self.stream_name,
                                self.consumer_group,
                                message_id
                            )
                            
                            self.stats["messages_consumed"] += 1
                
                except asyncio.CancelledError:
                    logger.info("消息消费任务被取消")
                    break
                except Exception as e:
                    logger.error(f"消费消息出错: {e}")
                    await asyncio.sleep(1)
                    
        except Exception as e:
            logger.error(f"消息消费失败: {e}")
            raise
    
    async def start_consumer(self, consumer_name: str = "default"):
        """启动消息消费者"""
        if self._consumer_task:
            logger.warning("消费者任务已在运行")
            return
        
        self._consumer_task = asyncio.create_task(
            self.consume_messages(consumer_name)
        )
        logger.info(f"消息消费者已启动: {consumer_name}")
    
    def register_handler(self, message_type: str, handler: Callable):
        """注册消息处理器"""
        self._message_handlers[message_type] = handler
        logger.info(f"注册消息处理器: {message_type}")
    
    async def _process_message(self, message_id: str, field_dict: Dict[str, str]):
        """处理单个消息"""
        try:
            # 反序列化消息
            message_data = {
                "id": field_dict.get("id"),
                "timestamp": field_dict.get("timestamp"),
                "type": field_dict.get("type"),
                "service": field_dict.get("service"),
                "source": field_dict.get("source"),
                "target": json.loads(field_dict.get("target", "{}")),
                "data": json.loads(field_dict.get("data", "{}")),
                "metadata": json.loads(field_dict.get("metadata", "{}"))
            }
            
            # 调用对应的处理器
            message_type = message_data.get("type")
            if message_type in self._message_handlers:
                handler = self._message_handlers[message_type]
                await handler(message_data)
            else:
                # 默认处理：发送给连接管理器
                await self._default_message_handler(message_data)
                
        except Exception as e:
            logger.error(f"处理消息失败: {message_id}, {e}")
            self.stats["messages_failed"] += 1
    
    async def _default_message_handler(self, message_data: Dict[str, Any]):
        """默认消息处理器"""
        # 这里可以实现默认的消息处理逻辑
        # 比如转发给连接管理器
        logger.debug(f"默认处理消息: {message_data.get('id')}")
    
    async def get_pending_messages(self, consumer_name: str = "default") -> List[Dict]:
        """获取待处理消息"""
        if not self._redis:
            raise RuntimeError("Redis未连接")
        
        try:
            # 获取消费者的待处理消息
            pending_info = await self._redis.xpending_range(
                self.stream_name,
                self.consumer_group,
                min="-",
                max="+",
                count=100
            )
            
            return [
                {
                    "message_id": info["message_id"],
                    "consumer": info["consumer"],
                    "time_since_delivered": info["time_since_delivered"],
                    "delivery_count": info["delivery_count"]
                }
                for info in pending_info
            ]
            
        except Exception as e:
            logger.error(f"获取待处理消息失败: {e}")
            return []
    
    async def claim_abandoned_messages(self, consumer_name: str = "default", min_idle_time: int = 60000):
        """认领被遗弃的消息"""
        if not self._redis:
            raise RuntimeError("Redis未连接")
        
        try:
            # 获取被遗弃的消息（空闲时间超过阈值）
            abandoned_messages = await self._redis.xautoclaim(
                self.stream_name,
                self.consumer_group,
                consumer_name,
                min_idle_time,
                start_id="0-0",
                count=100
            )
            
            if abandoned_messages[1]:  # messages
                logger.info(f"认领了 {len(abandoned_messages[1])} 个被遗弃的消息")
                
                # 处理认领的消息
                for message_id, field_dict in abandoned_messages[1]:
                    await self._process_message(message_id, field_dict)
                    await self._redis.xack(self.stream_name, self.consumer_group, message_id)
            
        except Exception as e:
            logger.error(f"认领被遗弃消息失败: {e}")
    
    async def get_stream_info(self) -> Dict[str, Any]:
        """获取流信息"""
        if not self._redis:
            raise RuntimeError("Redis未连接")
        
        try:
            stream_info = await self._redis.xinfo_stream(self.stream_name)
            group_info = await self._redis.xinfo_groups(self.stream_name)
            
            return {
                "stream": {
                    "length": stream_info.get("length", 0),
                    "first_entry": stream_info.get("first-entry"),
                    "last_entry": stream_info.get("last-entry"),
                    "max_deleted_entry_id": stream_info.get("max-deleted-entry-id"),
                    "entries_added": stream_info.get("entries-added", 0),
                    "recorded_first_entry_id": stream_info.get("recorded-first-entry-id")
                },
                "groups": [
                    {
                        "name": group.get("name"),
                        "consumers": group.get("consumers", 0),
                        "pending": group.get("pending", 0),
                        "last_delivered_id": group.get("last-delivered-id")
                    }
                    for group in group_info
                ],
                "stats": self.stats
            }
            
        except Exception as e:
            logger.error(f"获取流信息失败: {e}")
            return {"error": str(e)}
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            if not self._redis:
                return {"status": "error", "message": "Redis未连接"}
            
            # 检查Redis连接
            await self._redis.ping()
            
            # 获取基本信息
            info = await self.get_stream_info()
            
            return {
                "status": "healthy",
                "redis_connected": True,
                "stream_length": info.get("stream", {}).get("length", 0),
                "consumer_groups": len(info.get("groups", [])),
                "stats": self.stats
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "redis_connected": False
            }


# 全局消息队列管理器实例
message_queue = MessageQueueManager()