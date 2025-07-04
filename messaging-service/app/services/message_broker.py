"""
消息代理 - 微服务间消息路由和分发核心
支持点对点消息、发布订阅、消息队列和路由转发
"""

import asyncio
import logging
import json
import uuid
from typing import Dict, List, Any, Optional, Callable, Set
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
import redis.asyncio as redis
import aio_pika
from aio_pika import ExchangeType, DeliveryMode

from app.core.config import settings

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """消息类型"""
    POINT_TO_POINT = "p2p"      # 点对点消息
    BROADCAST = "broadcast"      # 广播消息
    PUBLISH_SUBSCRIBE = "pubsub" # 发布订阅
    REQUEST_REPLY = "request"    # 请求响应
    EVENT = "event"              # 事件消息


class MessagePriority(Enum):
    """消息优先级"""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4


class MessageStatus(Enum):
    """消息状态"""
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class Message:
    """消息定义"""
    message_id: str
    message_type: MessageType
    source_service: str
    target_service: Optional[str] = None
    topic: Optional[str] = None
    content: Dict[str, Any] = None
    headers: Dict[str, str] = None
    priority: MessagePriority = MessagePriority.NORMAL
    status: MessageStatus = MessageStatus.PENDING
    created_at: datetime = None
    expires_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.content is None:
            self.content = {}
        if self.headers is None:
            self.headers = {}
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ServiceEndpoint:
    """服务端点定义"""
    service_name: str
    host: str
    port: int
    status: str = "active"
    last_heartbeat: datetime = None
    capabilities: List[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.last_heartbeat is None:
            self.last_heartbeat = datetime.now()
        if self.capabilities is None:
            self.capabilities = []
        if self.metadata is None:
            self.metadata = {}


class MessageBroker:
    """消息代理"""
    
    def __init__(self):
        # 连接组件
        self.redis_client: Optional[redis.Redis] = None
        self.rabbitmq_connection: Optional[aio_pika.Connection] = None
        self.rabbitmq_channel: Optional[aio_pika.Channel] = None
        
        # 消息管理
        self.pending_messages: Dict[str, Message] = {}
        self.message_handlers: Dict[str, List[Callable]] = {}
        self.topic_subscribers: Dict[str, Set[str]] = {}
        
        # 服务发现
        self.service_registry: Dict[str, ServiceEndpoint] = {}
        self.service_subscriptions: Dict[str, Set[str]] = {}
        
        # 状态管理
        self._initialized = False
        self._running = False
        
        # 统计信息
        self.stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "messages_failed": 0,
            "active_subscriptions": 0
        }
    
    async def initialize(self):
        """初始化消息代理"""
        if self._initialized:
            return
            
        try:
            logger.info("初始化消息代理...")
            
            # 初始化Redis连接
            if settings.redis_url:
                self.redis_client = redis.from_url(
                    settings.redis_url,
                    decode_responses=True
                )
                await self.redis_client.ping()
                logger.info("Redis连接初始化成功")
            
            # 初始化RabbitMQ连接
            if settings.rabbitmq_url:
                self.rabbitmq_connection = await aio_pika.connect_robust(
                    settings.rabbitmq_url
                )
                self.rabbitmq_channel = await self.rabbitmq_connection.channel()
                await self.rabbitmq_channel.set_qos(prefetch_count=100)
                logger.info("RabbitMQ连接初始化成功")
                
                # 创建基础交换机
                await self._setup_exchanges()
            
            # 启动消息处理循环
            await self._start_message_processing()
            
            self._initialized = True
            logger.info("消息代理初始化完成")
            
        except Exception as e:
            logger.error(f"消息代理初始化失败: {e}")
            raise
    
    async def _setup_exchanges(self):
        """设置RabbitMQ交换机"""
        try:
            # 直接交换机（点对点）
            self.direct_exchange = await self.rabbitmq_channel.declare_exchange(
                "microservices_direct",
                ExchangeType.DIRECT,
                durable=True
            )
            
            # 主题交换机（发布订阅）
            self.topic_exchange = await self.rabbitmq_channel.declare_exchange(
                "microservices_topic",
                ExchangeType.TOPIC,
                durable=True
            )
            
            # 广播交换机
            self.fanout_exchange = await self.rabbitmq_channel.declare_exchange(
                "microservices_fanout",
                ExchangeType.FANOUT,
                durable=True
            )
            
            logger.info("RabbitMQ交换机设置完成")
            
        except Exception as e:
            logger.error(f"设置RabbitMQ交换机失败: {e}")
            raise
    
    async def _start_message_processing(self):
        """启动消息处理"""
        self._running = True
        
        # 启动后台任务
        asyncio.create_task(self._message_cleanup_loop())
        asyncio.create_task(self._heartbeat_check_loop())
        
        logger.info("消息处理循环启动")
    
    async def register_service(
        self,
        service_name: str,
        host: str,
        port: int,
        capabilities: List[str] = None
    ) -> bool:
        """注册服务"""
        try:
            endpoint = ServiceEndpoint(
                service_name=service_name,
                host=host,
                port=port,
                capabilities=capabilities or []
            )
            
            self.service_registry[service_name] = endpoint
            
            # 为服务创建专用队列
            if self.rabbitmq_channel:
                queue_name = f"service_{service_name}"
                queue = await self.rabbitmq_channel.declare_queue(
                    queue_name,
                    durable=True
                )
                
                # 绑定到直接交换机
                await queue.bind(self.direct_exchange, routing_key=service_name)
            
            # 在Redis中记录
            if self.redis_client:
                await self.redis_client.setex(
                    f"messaging:service:{service_name}",
                    timedelta(minutes=5),
                    json.dumps(asdict(endpoint), default=str)
                )
            
            logger.info(f"服务 {service_name} 注册成功")
            return True
            
        except Exception as e:
            logger.error(f"注册服务失败: {e}")
            return False
    
    async def send_message(
        self,
        message: Message,
        timeout: Optional[int] = None
    ) -> bool:
        """发送消息"""
        try:
            # 设置过期时间
            if timeout:
                message.expires_at = datetime.now() + timedelta(seconds=timeout)
            
            # 验证目标服务
            if (message.message_type == MessageType.POINT_TO_POINT and 
                message.target_service not in self.service_registry):
                raise ValueError(f"目标服务 {message.target_service} 未注册")
            
            # 根据消息类型选择发送方式
            if message.message_type == MessageType.POINT_TO_POINT:
                success = await self._send_direct_message(message)
            elif message.message_type == MessageType.BROADCAST:
                success = await self._send_broadcast_message(message)
            elif message.message_type == MessageType.PUBLISH_SUBSCRIBE:
                success = await self._send_pubsub_message(message)
            elif message.message_type == MessageType.EVENT:
                success = await self._send_event_message(message)
            else:
                raise ValueError(f"不支持的消息类型: {message.message_type}")
            
            if success:
                message.status = MessageStatus.DELIVERED
                self.stats["messages_sent"] += 1
                logger.debug(f"消息 {message.message_id} 发送成功")
            else:
                message.status = MessageStatus.FAILED
                self.stats["messages_failed"] += 1
                logger.error(f"消息 {message.message_id} 发送失败")
            
            # 记录消息
            self.pending_messages[message.message_id] = message
            
            return success
            
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            message.status = MessageStatus.FAILED
            return False
    
    async def _send_direct_message(self, message: Message) -> bool:
        """发送点对点消息"""
        try:
            if not self.rabbitmq_channel:
                return await self._send_via_redis(message)
            
            # 构建消息体
            message_body = json.dumps(asdict(message), default=str)
            
            # 发送到RabbitMQ
            await self.rabbitmq_channel.default_exchange.publish(
                aio_pika.Message(
                    message_body.encode(),
                    delivery_mode=DeliveryMode.PERSISTENT,
                    priority=message.priority.value,
                    correlation_id=message.correlation_id,
                    reply_to=message.reply_to,
                    headers=message.headers
                ),
                routing_key=f"service_{message.target_service}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"发送直接消息失败: {e}")
            return False
    
    async def _send_broadcast_message(self, message: Message) -> bool:
        """发送广播消息"""
        try:
            if not self.rabbitmq_channel:
                return await self._send_via_redis_broadcast(message)
            
            # 构建消息体
            message_body = json.dumps(asdict(message), default=str)
            
            # 发送到广播交换机
            await self.fanout_exchange.publish(
                aio_pika.Message(
                    message_body.encode(),
                    delivery_mode=DeliveryMode.PERSISTENT,
                    priority=message.priority.value,
                    headers=message.headers
                ),
                routing_key=""
            )
            
            return True
            
        except Exception as e:
            logger.error(f"发送广播消息失败: {e}")
            return False
    
    async def _send_pubsub_message(self, message: Message) -> bool:
        """发送发布订阅消息"""
        try:
            if not self.rabbitmq_channel:
                return await self._send_via_redis_pubsub(message)
            
            # 构建消息体
            message_body = json.dumps(asdict(message), default=str)
            
            # 发送到主题交换机
            await self.topic_exchange.publish(
                aio_pika.Message(
                    message_body.encode(),
                    delivery_mode=DeliveryMode.PERSISTENT,
                    priority=message.priority.value,
                    headers=message.headers
                ),
                routing_key=message.topic or "default"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"发送发布订阅消息失败: {e}")
            return False
    
    async def _send_event_message(self, message: Message) -> bool:
        """发送事件消息"""
        try:
            # 事件消息使用主题模式
            message.message_type = MessageType.PUBLISH_SUBSCRIBE
            if not message.topic:
                message.topic = f"events.{message.source_service}"
            
            return await self._send_pubsub_message(message)
            
        except Exception as e:
            logger.error(f"发送事件消息失败: {e}")
            return False
    
    async def _send_via_redis(self, message: Message) -> bool:
        """通过Redis发送消息（降级方案）"""
        try:
            if not self.redis_client:
                return False
            
            # 推送到目标服务队列
            queue_key = f"messaging:queue:{message.target_service}"
            message_data = json.dumps(asdict(message), default=str)
            
            await self.redis_client.lpush(queue_key, message_data)
            await self.redis_client.expire(queue_key, 3600)  # 1小时过期
            
            return True
            
        except Exception as e:
            logger.error(f"通过Redis发送消息失败: {e}")
            return False
    
    async def _send_via_redis_broadcast(self, message: Message) -> bool:
        """通过Redis发送广播消息"""
        try:
            if not self.redis_client:
                return False
            
            # 发送到所有注册的服务
            for service_name in self.service_registry.keys():
                message.target_service = service_name
                await self._send_via_redis(message)
            
            return True
            
        except Exception as e:
            logger.error(f"通过Redis发送广播消息失败: {e}")
            return False
    
    async def _send_via_redis_pubsub(self, message: Message) -> bool:
        """通过Redis发送发布订阅消息"""
        try:
            if not self.redis_client:
                return False
            
            # 使用Redis的发布订阅功能
            channel = f"messaging:topic:{message.topic}"
            message_data = json.dumps(asdict(message), default=str)
            
            await self.redis_client.publish(channel, message_data)
            
            return True
            
        except Exception as e:
            logger.error(f"通过Redis发送发布订阅消息失败: {e}")
            return False
    
    async def subscribe_to_service(
        self,
        service_name: str,
        callback: Callable[[Message], None]
    ) -> bool:
        """订阅服务消息"""
        try:
            if service_name not in self.message_handlers:
                self.message_handlers[service_name] = []
            
            self.message_handlers[service_name].append(callback)
            
            # 如果使用RabbitMQ，设置消费者
            if self.rabbitmq_channel:
                queue_name = f"service_{service_name}"
                queue = await self.rabbitmq_channel.declare_queue(
                    queue_name,
                    durable=True
                )
                
                async def message_handler(rabbitmq_message):
                    async with rabbitmq_message.process():
                        try:
                            message_data = json.loads(rabbitmq_message.body.decode())
                            message = Message(**message_data)
                            
                            for handler in self.message_handlers.get(service_name, []):
                                await self._safe_call_handler(handler, message)
                                
                        except Exception as e:
                            logger.error(f"处理消息失败: {e}")
                
                await queue.consume(message_handler)
            
            self.stats["active_subscriptions"] += 1
            logger.info(f"服务 {service_name} 订阅成功")
            return True
            
        except Exception as e:
            logger.error(f"订阅服务失败: {e}")
            return False
    
    async def subscribe_to_topic(
        self,
        topic: str,
        service_name: str,
        callback: Callable[[Message], None]
    ) -> bool:
        """订阅主题消息"""
        try:
            if topic not in self.topic_subscribers:
                self.topic_subscribers[topic] = set()
            
            self.topic_subscribers[topic].add(service_name)
            
            if service_name not in self.message_handlers:
                self.message_handlers[service_name] = []
            
            self.message_handlers[service_name].append(callback)
            
            # 如果使用RabbitMQ，设置主题消费者
            if self.rabbitmq_channel:
                queue_name = f"topic_{service_name}_{topic.replace('.', '_')}"
                queue = await self.rabbitmq_channel.declare_queue(
                    queue_name,
                    durable=True
                )
                
                await queue.bind(self.topic_exchange, routing_key=topic)
                
                async def topic_handler(rabbitmq_message):
                    async with rabbitmq_message.process():
                        try:
                            message_data = json.loads(rabbitmq_message.body.decode())
                            message = Message(**message_data)
                            
                            await self._safe_call_handler(callback, message)
                                
                        except Exception as e:
                            logger.error(f"处理主题消息失败: {e}")
                
                await queue.consume(topic_handler)
            
            logger.info(f"服务 {service_name} 订阅主题 {topic} 成功")
            return True
            
        except Exception as e:
            logger.error(f"订阅主题失败: {e}")
            return False
    
    async def _safe_call_handler(self, handler: Callable, message: Message):
        """安全调用处理器"""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(message)
            else:
                handler(message)
        except Exception as e:
            logger.error(f"调用消息处理器失败: {e}")
    
    async def _message_cleanup_loop(self):
        """消息清理循环"""
        while self._running:
            try:
                current_time = datetime.now()
                expired_messages = []
                
                for message_id, message in self.pending_messages.items():
                    if (message.expires_at and 
                        message.expires_at < current_time):
                        expired_messages.append(message_id)
                
                for message_id in expired_messages:
                    message = self.pending_messages.pop(message_id)
                    message.status = MessageStatus.EXPIRED
                    logger.debug(f"消息 {message_id} 已过期")
                
                await asyncio.sleep(60)  # 每分钟清理一次
                
            except Exception as e:
                logger.error(f"消息清理失败: {e}")
                await asyncio.sleep(60)
    
    async def _heartbeat_check_loop(self):
        """心跳检查循环"""
        while self._running:
            try:
                current_time = datetime.now()
                inactive_services = []
                
                for service_name, endpoint in self.service_registry.items():
                    if (current_time - endpoint.last_heartbeat) > timedelta(minutes=5):
                        inactive_services.append(service_name)
                
                for service_name in inactive_services:
                    endpoint = self.service_registry[service_name]
                    endpoint.status = "inactive"
                    logger.warning(f"服务 {service_name} 心跳超时")
                
                await asyncio.sleep(30)  # 每30秒检查一次
                
            except Exception as e:
                logger.error(f"心跳检查失败: {e}")
                await asyncio.sleep(30)
    
    async def heartbeat(self, service_name: str) -> bool:
        """更新服务心跳"""
        try:
            if service_name in self.service_registry:
                self.service_registry[service_name].last_heartbeat = datetime.now()
                self.service_registry[service_name].status = "active"
                return True
            return False
            
        except Exception as e:
            logger.error(f"更新心跳失败: {e}")
            return False
    
    def is_healthy(self) -> bool:
        """检查服务健康状态"""
        return self._initialized and self._running
    
    def get_pending_message_count(self) -> int:
        """获取待处理消息数量"""
        return len(self.pending_messages)
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "pending_messages": len(self.pending_messages),
            "registered_services": len(self.service_registry),
            "active_services": len([s for s in self.service_registry.values() if s.status == "active"]),
            "topics": len(self.topic_subscribers),
            "message_handlers": sum(len(handlers) for handlers in self.message_handlers.values())
        }
    
    async def cleanup(self):
        """清理资源"""
        try:
            logger.info("清理消息代理资源...")
            
            self._running = False
            
            # 关闭RabbitMQ连接
            if self.rabbitmq_connection:
                await self.rabbitmq_connection.close()
            
            # 关闭Redis连接
            if self.redis_client:
                await self.redis_client.close()
            
            # 清理内存数据
            self.pending_messages.clear()
            self.message_handlers.clear()
            self.service_registry.clear()
            
            logger.info("消息代理资源清理完成")
            
        except Exception as e:
            logger.error(f"清理消息代理资源失败: {e}") 