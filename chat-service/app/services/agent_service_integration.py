"""
Agent-Service深度集成 - 与智能体服务的全面对接
"""

import asyncio
import logging
import time
import json
import hashlib
import uuid
from typing import Dict, Any, Optional, List, Tuple, Set, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from collections import deque, defaultdict

from shared.service_client import call_service, CallMethod, CallConfig, RetryStrategy
from app.core.redis import redis_manager
from app.core.config import settings
from app.services.agent_pool_manager import AgentInstance, AgentStatus, get_agent_pool_manager
from app.services.agent_health_monitor import get_agent_health_monitor, HealthStatus
from app.services.agent_sync_manager import get_agent_sync_manager, SyncEvent, SyncEventType

logger = logging.getLogger(__name__)


class IntegrationLevel(str, Enum):
    """集成级别"""
    BASIC = "basic"           # 基础集成
    STANDARD = "standard"     # 标准集成
    ADVANCED = "advanced"     # 高级集成
    FULL = "full"            # 完全集成


class AgentCapability(str, Enum):
    """智能体能力"""
    CHAT = "chat"                   # 聊天对话
    VOICE = "voice"                 # 语音交互
    MULTIMODAL = "multimodal"       # 多模态
    KNOWLEDGE_BASE = "knowledge_base"  # 知识库
    FUNCTION_CALLING = "function_calling"  # 函数调用
    STREAMING = "streaming"         # 流式响应
    CUSTOM = "custom"              # 自定义能力


@dataclass
class AgentDefinition:
    """智能体定义"""
    agent_id: str
    name: str
    description: str
    version: str = "1.0.0"
    capabilities: List[AgentCapability] = field(default_factory=list)
    configuration: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: str = "active"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "capabilities": [cap.value for cap in self.capabilities],
            "configuration": self.configuration,
            "metadata": self.metadata,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


@dataclass
class ConversationContext:
    """对话上下文"""
    conversation_id: str
    agent_id: str
    session_id: str
    user_id: str
    messages: List[Dict[str, Any]] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class ConversationRequest:
    """对话请求"""
    agent_id: str
    session_id: str
    user_id: str
    message: str
    message_type: str = "text"
    context: Dict[str, Any] = field(default_factory=dict)
    options: Dict[str, Any] = field(default_factory=dict)
    stream: bool = False
    priority: int = 1


@dataclass
class ConversationResponse:
    """对话响应"""
    success: bool = False
    response: str = ""
    response_type: str = "text"
    metadata: Dict[str, Any] = field(default_factory=dict)
    usage: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    processing_time: float = 0.0
    timestamp: float = field(default_factory=time.time)


class AgentServiceIntegration:
    """Agent-Service集成管理器"""
    
    def __init__(self, integration_level: IntegrationLevel = IntegrationLevel.FULL):
        self.integration_level = integration_level
        self.agent_registry: Dict[str, AgentDefinition] = {}
        self.conversation_contexts: Dict[str, ConversationContext] = {}
        self.request_queue: asyncio.Queue = asyncio.Queue()
        
        # 集成配置
        self.default_timeout = 30
        self.max_retries = 3
        self.batch_size = 10
        self.context_ttl = 3600  # 1小时
        
        # 性能监控
        self.integration_metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "average_response_time": 0.0,
            "total_conversations": 0,
            "active_conversations": 0,
            "agent_registry_size": 0,
            "cache_hits": 0,
            "cache_misses": 0
        }
        
        # 缓存
        self.response_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = 300  # 5分钟
        
        # 启动后台任务
        self._request_processor_task = None
        self._context_cleanup_task = None
        self._registry_sync_task = None
        self._start_background_tasks()
    
    async def initialize_integration(self) -> bool:
        """初始化集成"""
        try:
            logger.info(f"初始化Agent-Service集成 (级别: {self.integration_level.value})")
            
            # 同步智能体注册表
            await self._sync_agent_registry()
            
            # 初始化负载均衡器
            if self.integration_level in [IntegrationLevel.ADVANCED, IntegrationLevel.FULL]:
                await self._initialize_load_balancer()
            
            # 初始化资源优化器
            if self.integration_level == IntegrationLevel.FULL:
                await self._initialize_resource_optimizer()
            
            logger.info("Agent-Service集成初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"Agent-Service集成初始化失败: {e}")
            return False
    
    async def register_agent(self, agent_definition: AgentDefinition) -> bool:
        """注册智能体"""
        try:
            # 向Agent-Service注册
            registration_config = CallConfig(
                timeout=self.default_timeout,
                retry_times=self.max_retries,
                retry_strategy=RetryStrategy.EXPONENTIAL
            )
            
            response = await call_service(
                service_name="agent-service",
                method=CallMethod.POST,
                path="/api/v1/agents/register",
                config=registration_config,
                json=agent_definition.to_dict()
            )
            
            if response.get("success"):
                # 更新本地注册表
                self.agent_registry[agent_definition.agent_id] = agent_definition
                
                # 持久化到Redis
                agent_key = f"agent_integration:agent:{agent_definition.agent_id}"
                redis_manager.set_json(agent_key, agent_definition.to_dict(), ex=86400)
                
                # 更新指标
                self.integration_metrics["agent_registry_size"] = len(self.agent_registry)
                
                logger.info(f"智能体注册成功: {agent_definition.agent_id}")
                return True
            else:
                logger.error(f"智能体注册失败: {response.get('error')}")
                return False
                
        except Exception as e:
            logger.error(f"注册智能体失败: {e}")
            return False
    
    async def get_agent_definition(self, agent_id: str) -> Optional[AgentDefinition]:
        """获取智能体定义"""
        try:
            # 优先从本地缓存获取
            if agent_id in self.agent_registry:
                return self.agent_registry[agent_id]
            
            # 从Agent-Service获取
            response = await call_service(
                service_name="agent-service",
                method=CallMethod.GET,
                path=f"/api/v1/agents/{agent_id}",
                config=CallConfig(timeout=10, retry_times=2)
            )
            
            if response.get("success"):
                agent_data = response.get("agent", {})
                agent_def = AgentDefinition(
                    agent_id=agent_data.get("agent_id"),
                    name=agent_data.get("name", ""),
                    description=agent_data.get("description", ""),
                    version=agent_data.get("version", "1.0.0"),
                    capabilities=[AgentCapability(cap) for cap in agent_data.get("capabilities", [])],
                    configuration=agent_data.get("configuration", {}),
                    metadata=agent_data.get("metadata", {}),
                    status=agent_data.get("status", "active"),
                    created_at=agent_data.get("created_at", time.time()),
                    updated_at=agent_data.get("updated_at", time.time())
                )
                
                # 更新本地缓存
                self.agent_registry[agent_id] = agent_def
                return agent_def
            
            return None
            
        except Exception as e:
            logger.error(f"获取智能体定义失败: {e}")
            return None
    
    async def start_conversation(
        self, 
        agent_id: str, 
        session_id: str, 
        user_id: str,
        initial_context: Dict[str, Any] = None
    ) -> Optional[str]:
        """开始对话"""
        try:
            conversation_id = str(uuid.uuid4())
            
            # 创建对话上下文
            context = ConversationContext(
                conversation_id=conversation_id,
                agent_id=agent_id,
                session_id=session_id,
                user_id=user_id,
                context=initial_context or {}
            )
            
            # 向Agent-Service创建对话会话
            session_config = CallConfig(timeout=15, retry_times=2)
            
            response = await call_service(
                service_name="agent-service",
                method=CallMethod.POST,
                path=f"/api/v1/agents/{agent_id}/conversations",
                config=session_config,
                json={
                    "conversation_id": conversation_id,
                    "session_id": session_id,
                    "user_id": user_id,
                    "context": context.context
                }
            )
            
            if response.get("success"):
                # 保存对话上下文
                self.conversation_contexts[conversation_id] = context
                
                # 持久化到Redis
                context_key = f"agent_integration:conversation:{conversation_id}"
                redis_manager.set_json(context_key, {
                    "conversation_id": conversation_id,
                    "agent_id": agent_id,
                    "session_id": session_id,
                    "user_id": user_id,
                    "context": context.context,
                    "created_at": context.created_at
                }, ex=self.context_ttl)
                
                # 更新指标
                self.integration_metrics["total_conversations"] += 1
                self.integration_metrics["active_conversations"] = len(self.conversation_contexts)
                
                logger.info(f"对话创建成功: {conversation_id}")
                return conversation_id
            else:
                logger.error(f"对话创建失败: {response.get('error')}")
                return None
                
        except Exception as e:
            logger.error(f"开始对话失败: {e}")
            return None
    
    async def send_message(self, request: ConversationRequest) -> ConversationResponse:
        """发送消息"""
        start_time = time.time()
        response = ConversationResponse()
        
        try:
            self.integration_metrics["total_requests"] += 1
            
            # 检查缓存
            cache_key = self._generate_cache_key(request)
            cached_response = self._get_cached_response(cache_key)
            if cached_response:
                self.integration_metrics["cache_hits"] += 1
                response.success = True
                response.response = cached_response["response"]
                response.response_type = cached_response.get("response_type", "text")
                response.metadata = cached_response.get("metadata", {})
                response.processing_time = time.time() - start_time
                return response
            
            self.integration_metrics["cache_misses"] += 1
            
            # 获取智能体实例
            instance = await self._get_optimal_agent_instance(request.agent_id, request)
            if not instance:
                response.error = "没有可用的智能体实例"
                self.integration_metrics["failed_requests"] += 1
                return response
            
            # 准备请求数据
            message_data = {
                "conversation_id": self._get_conversation_id(request.session_id),
                "message": request.message,
                "message_type": request.message_type,
                "context": request.context,
                "options": request.options,
                "stream": request.stream,
                "priority": request.priority
            }
            
            # 发送到Agent-Service
            message_config = CallConfig(
                timeout=self.default_timeout,
                retry_times=self.max_retries,
                retry_strategy=RetryStrategy.EXPONENTIAL
            )
            
            service_response = await call_service(
                service_name="agent-service",
                method=CallMethod.POST,
                path=f"/api/v1/agents/{request.agent_id}/instances/{instance.instance_id}/message",
                config=message_config,
                json=message_data
            )
            
            if service_response.get("success"):
                response.success = True
                response.response = service_response.get("response", "")
                response.response_type = service_response.get("response_type", "text")
                response.metadata = service_response.get("metadata", {})
                response.usage = service_response.get("usage", {})
                
                # 更新对话上下文
                await self._update_conversation_context(request, response)
                
                # 缓存响应
                self._cache_response(cache_key, {
                    "response": response.response,
                    "response_type": response.response_type,
                    "metadata": response.metadata
                })
                
                # 更新负载均衡器性能数据
                if self.integration_level in [IntegrationLevel.ADVANCED, IntegrationLevel.FULL]:
                    try:
                        from app.services.load_balancer import get_smart_load_balancer
                        load_balancer = get_smart_load_balancer()
                        await load_balancer.update_instance_performance(
                            instance.instance_id,
                            response.processing_time * 1000,  # 转换为毫秒
                            True
                        )
                    except ImportError:
                        pass  # 负载均衡器不可用，跳过
                
                self.integration_metrics["successful_requests"] += 1
            else:
                response.error = service_response.get("error", "处理失败")
                self.integration_metrics["failed_requests"] += 1
                
                # 更新负载均衡器性能数据（失败）
                if self.integration_level in [IntegrationLevel.ADVANCED, IntegrationLevel.FULL]:
                    try:
                        from app.services.load_balancer import get_smart_load_balancer
                        load_balancer = get_smart_load_balancer()
                        await load_balancer.update_instance_performance(
                            instance.instance_id,
                            response.processing_time * 1000,
                            False
                        )
                    except ImportError:
                        pass  # 负载均衡器不可用，跳过
            
        except Exception as e:
            response.error = f"发送消息失败: {str(e)}"
            self.integration_metrics["failed_requests"] += 1
            logger.error(f"发送消息失败: {e}")
        
        finally:
            response.processing_time = time.time() - start_time
            
            # 更新平均响应时间
            total_time = (self.integration_metrics["average_response_time"] * 
                         (self.integration_metrics["total_requests"] - 1))
            self.integration_metrics["average_response_time"] = (
                (total_time + response.processing_time) / 
                self.integration_metrics["total_requests"]
            )
        
        return response
    
    async def _get_optimal_agent_instance(
        self, 
        agent_id: str, 
        request: ConversationRequest
    ) -> Optional[AgentInstance]:
        """获取最优智能体实例"""
        try:
            if self.integration_level in [IntegrationLevel.ADVANCED, IntegrationLevel.FULL]:
                # 使用智能负载均衡器
                try:
                    from app.services.load_balancer import get_smart_load_balancer, RoutingRequest
                    
                    load_balancer = get_smart_load_balancer()
                    
                    routing_request = RoutingRequest(
                        session_id=request.session_id,
                        user_id=request.user_id,
                        request_type=request.message_type,
                        priority=request.priority
                    )
                    
                    routing_result = await load_balancer.route_request(agent_id, routing_request)
                    return routing_result.instance if routing_result.success else None
                except ImportError:
                    logger.warning("负载均衡器不可用，使用基础池管理器")
                    # 回退到基础池管理器
                    pass
            else:
                # 使用基础池管理器
                pool_manager = get_agent_pool_manager()
                return await pool_manager.get_agent_instance(agent_id, request.session_id)
                
        except Exception as e:
            logger.error(f"获取最优智能体实例失败: {e}")
            return None
    
    def _get_conversation_id(self, session_id: str) -> Optional[str]:
        """根据会话ID获取对话ID"""
        for conv_id, context in self.conversation_contexts.items():
            if context.session_id == session_id:
                return conv_id
        return None
    
    async def _update_conversation_context(
        self, 
        request: ConversationRequest, 
        response: ConversationResponse
    ):
        """更新对话上下文"""
        try:
            conversation_id = self._get_conversation_id(request.session_id)
            if not conversation_id:
                return
            
            context = self.conversation_contexts.get(conversation_id)
            if context:
                # 添加消息历史
                context.messages.append({
                    "role": "user",
                    "content": request.message,
                    "timestamp": time.time()
                })
                
                if response.success:
                    context.messages.append({
                        "role": "assistant",
                        "content": response.response,
                        "timestamp": response.timestamp
                    })
                
                # 更新上下文
                context.updated_at = time.time()
                
                # 持久化到Redis
                context_key = f"agent_integration:conversation:{conversation_id}"
                redis_manager.set_json(context_key, {
                    "conversation_id": conversation_id,
                    "agent_id": context.agent_id,
                    "session_id": context.session_id,
                    "user_id": context.user_id,
                    "messages": context.messages[-20:],  # 保留最近20条消息
                    "context": context.context,
                    "created_at": context.created_at,
                    "updated_at": context.updated_at
                }, ex=self.context_ttl)
        
        except Exception as e:
            logger.error(f"更新对话上下文失败: {e}")
    
    def _generate_cache_key(self, request: ConversationRequest) -> str:
        """生成缓存键"""
        key_data = f"{request.agent_id}:{request.message}:{json.dumps(request.context, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _get_cached_response(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """获取缓存响应"""
        try:
            cached_data = self.response_cache.get(cache_key)
            if cached_data:
                if time.time() - cached_data["timestamp"] < self.cache_ttl:
                    return cached_data["data"]
                else:
                    del self.response_cache[cache_key]
            return None
        except Exception:
            return None
    
    def _cache_response(self, cache_key: str, response_data: Dict[str, Any]):
        """缓存响应"""
        try:
            self.response_cache[cache_key] = {
                "data": response_data,
                "timestamp": time.time()
            }
            
            # 限制缓存大小
            if len(self.response_cache) > 1000:
                oldest_key = min(self.response_cache.keys(), 
                                key=lambda k: self.response_cache[k]["timestamp"])
                del self.response_cache[oldest_key]
        except Exception as e:
            logger.warning(f"缓存响应失败: {e}")
    
    async def _sync_agent_registry(self):
        """同步智能体注册表"""
        try:
            response = await call_service(
                service_name="agent-service",
                method=CallMethod.GET,
                path="/api/v1/agents",
                config=CallConfig(timeout=20, retry_times=2)
            )
            
            if response.get("success"):
                agents = response.get("agents", [])
                
                for agent_data in agents:
                    agent_def = AgentDefinition(
                        agent_id=agent_data.get("agent_id"),
                        name=agent_data.get("name", ""),
                        description=agent_data.get("description", ""),
                        version=agent_data.get("version", "1.0.0"),
                        capabilities=[AgentCapability(cap) for cap in agent_data.get("capabilities", [])],
                        configuration=agent_data.get("configuration", {}),
                        metadata=agent_data.get("metadata", {}),
                        status=agent_data.get("status", "active"),
                        created_at=agent_data.get("created_at", time.time()),
                        updated_at=agent_data.get("updated_at", time.time())
                    )
                    
                    self.agent_registry[agent_def.agent_id] = agent_def
                
                self.integration_metrics["agent_registry_size"] = len(self.agent_registry)
                logger.info(f"同步智能体注册表完成: {len(agents)} 个智能体")
            
        except Exception as e:
            logger.error(f"同步智能体注册表失败: {e}")
    
    async def _initialize_load_balancer(self):
        """初始化负载均衡器"""
        try:
            from app.services.load_balancer import get_smart_load_balancer
            load_balancer = get_smart_load_balancer()
            logger.info("负载均衡器初始化完成")
        except ImportError:
            logger.warning("负载均衡器模块不可用")
        except Exception as e:
            logger.error(f"负载均衡器初始化失败: {e}")
    
    async def _initialize_resource_optimizer(self):
        """初始化资源优化器"""
        try:
            from app.services.resource_optimizer import get_resource_optimizer, ScalingRule, ScalingTrigger
            
            resource_optimizer = get_resource_optimizer()
            
            # 为每个智能体添加默认伸缩规则
            for agent_id in self.agent_registry.keys():
                default_rule = ScalingRule(
                    rule_id=f"default_load_{agent_id}",
                    agent_id=agent_id,
                    trigger=ScalingTrigger.LOAD_BASED,
                    metric_name="load_ratio",
                    threshold_up=0.8,
                    threshold_down=0.3,
                    min_instances=1,
                    max_instances=5,
                    cooldown_period=300
                )
                
                await resource_optimizer.add_scaling_rule(default_rule)
            
            logger.info("资源优化器初始化完成")
        except ImportError:
            logger.warning("资源优化器模块不可用")
        except Exception as e:
            logger.error(f"资源优化器初始化失败: {e}")
    
    def _start_background_tasks(self):
        """启动后台任务"""
        async def request_processor():
            """请求处理器"""
            while True:
                try:
                    await asyncio.sleep(1)
                    # 处理请求队列中的批量请求
                    # 这里可以实现批量处理逻辑
                except Exception as e:
                    logger.error(f"请求处理器错误: {e}")
        
        async def context_cleanup():
            """上下文清理"""
            while True:
                try:
                    await asyncio.sleep(300)  # 每5分钟清理一次
                    
                    current_time = time.time()
                    expired_contexts = []
                    
                    for conv_id, context in self.conversation_contexts.items():
                        if current_time - context.updated_at > self.context_ttl:
                            expired_contexts.append(conv_id)
                    
                    for conv_id in expired_contexts:
                        del self.conversation_contexts[conv_id]
                    
                    if expired_contexts:
                        logger.info(f"清理过期对话上下文: {len(expired_contexts)} 个")
                
                except Exception as e:
                    logger.error(f"上下文清理错误: {e}")
        
        async def registry_sync():
            """注册表同步"""
            while True:
                try:
                    await asyncio.sleep(600)  # 每10分钟同步一次
                    await self._sync_agent_registry()
                except Exception as e:
                    logger.error(f"注册表同步错误: {e}")
        
        self._request_processor_task = asyncio.create_task(request_processor())
        self._context_cleanup_task = asyncio.create_task(context_cleanup())
        self._registry_sync_task = asyncio.create_task(registry_sync())
    
    def get_integration_stats(self) -> Dict[str, Any]:
        """获取集成统计"""
        return {
            "integration_level": self.integration_level.value,
            "metrics": self.integration_metrics,
            "agent_registry": {
                "total_agents": len(self.agent_registry),
                "agents": [agent.to_dict() for agent in self.agent_registry.values()]
            },
            "active_conversations": len(self.conversation_contexts),
            "cache_size": len(self.response_cache),
            "configuration": {
                "default_timeout": self.default_timeout,
                "max_retries": self.max_retries,
                "batch_size": self.batch_size,
                "context_ttl": self.context_ttl,
                "cache_ttl": self.cache_ttl
            },
            "timestamp": time.time()
        }
    
    async def cleanup(self):
        """清理资源"""
        try:
            # 取消后台任务
            if self._request_processor_task:
                self._request_processor_task.cancel()
            if self._context_cleanup_task:
                self._context_cleanup_task.cancel()
            if self._registry_sync_task:
                self._registry_sync_task.cancel()
            
            logger.info("Agent-Service集成清理完成")
        except Exception as e:
            logger.error(f"清理Agent-Service集成失败: {e}")


# 全局实例
_agent_service_integration: Optional[AgentServiceIntegration] = None


def get_agent_service_integration() -> AgentServiceIntegration:
    """获取Agent-Service集成实例"""
    global _agent_service_integration
    if _agent_service_integration is None:
        _agent_service_integration = AgentServiceIntegration()
    return _agent_service_integration