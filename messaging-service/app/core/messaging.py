"""
消息代理和事件分发器核心模块
实现RabbitMQ消息队列、Redis缓存和事件驱动架构
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, asdict
from enum import Enum

import aio_pika
import redis.asyncio as redis
from aio_pika import Message, DeliveryMode
from aio_pika.abc import AbstractIncomingMessage

from .config import settings

logger = logging.getLogger(__name__)


class EventType(Enum):
    """事件类型枚举"""
    USER_ACTION = "user_action"
    SERVICE_REQUEST = "service_request"
    SERVICE_RESPONSE = "service_response"
    SYSTEM_EVENT = "system_event"
    ERROR_EVENT = "error_event"
    NOTIFICATION = "notification"
    WEBSOCKET_MESSAGE = "websocket_message"


class MessagePriority(Enum):
    """消息优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Event:
    """事件数据结构"""
    id: str
    type: EventType
    source_service: str
    target_service: Optional[str]
    data: Dict[str, Any]
    timestamp: datetime
    priority: MessagePriority = MessagePriority.NORMAL
    retry_count: int = 0
    correlation_id: Optional[str] = None
    user_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """从字典创建事件"""
        return cls(**data)


class MessageBroker:
    """消息代理 - 基于RabbitMQ"""
    
    def __init__(self):
        self.connection: Optional[aio_pika.Connection] = None
        self.channel: Optional[aio_pika.Channel] = None
        self.exchange: Optional[aio_pika.Exchange] = None
        self.redis_client: Optional[redis.Redis] = None
        self.message_handlers: Dict[str, Callable] = {}
        self.metrics = {
            "messages_sent": 0,
            "messages_received": 0,
            "messages_failed": 0,
            "connection_errors": 0
        }
        
    async def initialize(self):
        """初始化消息代理"""
        try:
            # 连接RabbitMQ
            self.connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
            self.channel = await self.connection.channel()
            
            # 创建交换机
            self.exchange = await self.channel.declare_exchange(
                settings.MESSAGE_QUEUE_EXCHANGE,
                aio_pika.ExchangeType.TOPIC,
                durable=True
            )
            
            # 连接Redis
            self.redis_client = redis.from_url(settings.REDIS_URL)
            await self.redis_client.ping()
            
            logger.info("消息代理初始化成功")
            
        except Exception as e:
            logger.error(f"消息代理初始化失败: {str(e)}")
            self.metrics["connection_errors"] += 1
            raise
    
    async def publish_event(self, event: Event, routing_key: Optional[str] = None) -> bool:
        """发布事件"""
        try:
            if not self.exchange:
                raise RuntimeError("消息代理未初始化")
            
            # 序列化事件
            message_body = json.dumps(event.to_dict(), default=str)
            
            # 创建消息
            message = Message(
                message_body.encode(),
                delivery_mode=DeliveryMode.PERSISTENT,
                priority=event.priority.value,
                correlation_id=event.correlation_id,
                timestamp=time.time()
            )
            
            # 确定路由键
            if not routing_key:
                routing_key = f"{event.source_service}.{event.type.value}"
            
            # 发布消息
            await self.exchange.publish(
                message,
                routing_key=routing_key
            )
            
            # 缓存到Redis（用于消息追踪）
            if self.redis_client:
                await self.redis_client.setex(
                    f"message:{event.id}",
                    settings.MESSAGE_TIMEOUT,
                    message_body
                )
            
            self.metrics["messages_sent"] += 1
            logger.debug(f"事件发布成功: {event.id}")
            return True
            
        except Exception as e:
            logger.error(f"事件发布失败: {str(e)}")
            self.metrics["messages_failed"] += 1
            return False
    
    async def subscribe_to_events(self, routing_key: str, handler: Callable) -> None:
        """订阅事件"""
        try:
            if not self.channel or not self.exchange:
                raise RuntimeError("消息代理未初始化")
            
            # 创建队列
            queue_name = f"{settings.SERVICE_NAME}.{routing_key}"
            queue = await self.channel.declare_queue(
                queue_name,
                durable=True,
                arguments={"x-max-priority": 4}  # 支持优先级
            )
            
            # 绑定队列到交换机
            await queue.bind(self.exchange, routing_key)
            
            # 注册处理器
            self.message_handlers[routing_key] = handler
            
            # 开始消费
            await queue.consume(self._handle_message)
            
            logger.info(f"订阅事件成功: {routing_key}")
            
        except Exception as e:
            logger.error(f"订阅事件失败: {str(e)}")
            raise
    
    async def _handle_message(self, message: AbstractIncomingMessage) -> None:
        """处理接收到的消息"""
        try:
            # 解析消息
            event_data = json.loads(message.body.decode())
            event = Event.from_dict(event_data)
            
            # 查找处理器
            routing_key = message.routing_key
            handler = self.message_handlers.get(routing_key)
            
            if handler:
                # 执行处理器
                await handler(event)
                await message.ack()
                self.metrics["messages_received"] += 1
                logger.debug(f"消息处理成功: {event.id}")
            else:
                logger.warning(f"未找到处理器: {routing_key}")
                await message.reject(requeue=False)
                
        except Exception as e:
            logger.error(f"消息处理失败: {str(e)}")
            await message.reject(requeue=True)
            self.metrics["messages_failed"] += 1
    
    async def start_consuming(self):
        """开始消费消息"""
        try:
            if self.connection:
                await asyncio.Future()  # 保持运行
        except Exception as e:
            logger.error(f"消息消费错误: {str(e)}")
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            # 检查RabbitMQ连接
            rabbitmq_status = "healthy" if self.connection and not self.connection.is_closed else "unhealthy"
            
            # 检查Redis连接
            redis_status = "healthy"
            if self.redis_client:
                await self.redis_client.ping()
            else:
                redis_status = "unhealthy"
            
            return {
                "rabbitmq": rabbitmq_status,
                "redis": redis_status,
                "metrics": self.metrics
            }
            
        except Exception as e:
            logger.error(f"健康检查失败: {str(e)}")
            return {"status": "unhealthy", "error": str(e)}
    
    async def get_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        return self.metrics.copy()
    
    async def close(self):
        """关闭连接"""
        try:
            if self.connection:
                await self.connection.close()
            if self.redis_client:
                await self.redis_client.close()
            logger.info("消息代理连接已关闭")
        except Exception as e:
            logger.error(f"关闭消息代理失败: {str(e)}")


class EventDispatcher:
    """事件分发器"""
    
    def __init__(self):
        self.event_handlers: Dict[EventType, List[Callable]] = {}
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.processing = False
        self.metrics = {
            "events_processed": 0,
            "events_failed": 0,
            "handlers_registered": 0
        }
    
    async def initialize(self):
        """初始化事件分发器"""
        logger.info("事件分发器初始化完成")
    
    def register_handler(self, event_type: EventType, handler: Callable):
        """注册事件处理器"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        
        self.event_handlers[event_type].append(handler)
        self.metrics["handlers_registered"] += 1
        logger.info(f"注册事件处理器: {event_type.value}")
    
    async def dispatch_event(self, event: Event):
        """分发事件"""
        await self.event_queue.put(event)
    
    async def start_processing(self):
        """开始处理事件"""
        self.processing = True
        logger.info("开始处理事件队列")
        
        while self.processing:
            try:
                # 批量处理事件
                events = []
                for _ in range(settings.EVENT_BATCH_SIZE):
                    try:
                        event = await asyncio.wait_for(
                            self.event_queue.get(),
                            timeout=1.0
                        )
                        events.append(event)
                    except asyncio.TimeoutError:
                        break
                
                if events:
                    await self._process_events(events)
                
            except Exception as e:
                logger.error(f"事件处理循环错误: {str(e)}")
                await asyncio.sleep(1)
    
    async def _process_events(self, events: List[Event]):
        """批量处理事件"""
        for event in events:
            try:
                handlers = self.event_handlers.get(event.type, [])
                
                if handlers:
                    # 并行执行所有处理器
                    tasks = [handler(event) for handler in handlers]
                    await asyncio.gather(*tasks, return_exceptions=True)
                    
                self.metrics["events_processed"] += 1
                logger.debug(f"事件处理完成: {event.id}")
                
            except Exception as e:
                logger.error(f"事件处理失败: {event.id}, 错误: {str(e)}")
                self.metrics["events_failed"] += 1
                
                # 重试逻辑
                if event.retry_count < settings.EVENT_RETRY_ATTEMPTS:
                    event.retry_count += 1
                    await asyncio.sleep(settings.EVENT_RETRY_DELAY)
                    await self.event_queue.put(event)
    
    async def get_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        return {
            **self.metrics,
            "queue_size": self.event_queue.qsize(),
            "processing": self.processing
        }
    
    async def close(self):
        """关闭事件分发器"""
        self.processing = False
        logger.info("事件分发器已关闭") 