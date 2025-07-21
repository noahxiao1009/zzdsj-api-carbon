"""
统一微服务调用客户端SDK
提供简单、高效、可靠的服务间通信接口
"""

import asyncio
import aiohttp
import json
import logging
import time
from typing import Dict, Any, Optional, List, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import uuid

logger = logging.getLogger(__name__)


class CallMethod(str, Enum):
    """HTTP调用方法"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


class RetryStrategy(str, Enum):
    """重试策略"""
    NONE = "none"
    FIXED = "fixed"
    EXPONENTIAL = "exponential"
    LINEAR = "linear"


@dataclass
class ServiceEndpoint:
    """服务端点信息"""
    service_name: str
    host: str
    port: int
    version: str = "v1"
    protocol: str = "http"
    weight: int = 1
    healthy: bool = True
    last_check: datetime = field(default_factory=datetime.now)
    
    @property
    def base_url(self) -> str:
        return f"{self.protocol}://{self.host}:{self.port}"


@dataclass
class CallConfig:
    """调用配置"""
    timeout: int = 30
    retry_times: int = 3
    retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    retry_delay: float = 1.0
    circuit_breaker_enabled: bool = True
    cache_enabled: bool = False
    cache_ttl: int = 300  # 5分钟


class CircuitBreaker:
    """熔断器"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def can_call(self) -> bool:
        """检查是否可以调用"""
        if self.state == "CLOSED":
            return True
        elif self.state == "OPEN":
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = "HALF_OPEN"
                return True
            return False
        else:  # HALF_OPEN
            return True
    
    def record_success(self):
        """记录成功调用"""
        self.failure_count = 0
        self.state = "CLOSED"
    
    def record_failure(self):
        """记录失败调用"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"


class ServiceRegistry:
    """服务注册表本地缓存"""
    
    def __init__(self, gateway_url: str):
        self.gateway_url = gateway_url
        self.services: Dict[str, List[ServiceEndpoint]] = {}
        self.last_update = {}
        self.cache_ttl = 60  # 1分钟缓存
        
    async def get_service_endpoints(self, service_name: str) -> List[ServiceEndpoint]:
        """获取服务端点列表"""
        now = time.time()
        
        # 检查缓存是否过期
        if (service_name not in self.last_update or 
            now - self.last_update[service_name] > self.cache_ttl):
            await self._refresh_service_cache(service_name)
        
        return self.services.get(service_name, [])
    
    async def _refresh_service_cache(self, service_name: str):
        """刷新服务缓存"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.gateway_url}/api/gateway/services/{service_name}",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        endpoints = []
                        
                        for instance in data.get("instances", []):
                            endpoints.append(ServiceEndpoint(
                                service_name=service_name,
                                host=instance["host"],
                                port=instance["port"],
                                version=instance.get("version", "v1"),
                                healthy=instance.get("status") == "healthy"
                            ))
                        
                        self.services[service_name] = [ep for ep in endpoints if ep.healthy]
                        self.last_update[service_name] = time.time()
                        
        except Exception as e:
            logger.error(f"刷新服务缓存失败 {service_name}: {e}")


class LoadBalancer:
    """负载均衡器"""
    
    def __init__(self):
        self.round_robin_index = {}
    
    def select_endpoint(self, endpoints: List[ServiceEndpoint], strategy: str = "round_robin") -> Optional[ServiceEndpoint]:
        """选择服务端点"""
        if not endpoints:
            return None
        
        healthy_endpoints = [ep for ep in endpoints if ep.healthy]
        if not healthy_endpoints:
            return None
        
        if strategy == "round_robin":
            service_name = healthy_endpoints[0].service_name
            index = self.round_robin_index.get(service_name, 0)
            endpoint = healthy_endpoints[index % len(healthy_endpoints)]
            self.round_robin_index[service_name] = (index + 1) % len(healthy_endpoints)
            return endpoint
        
        elif strategy == "random":
            import random
            return random.choice(healthy_endpoints)
        
        elif strategy == "weighted":
            # 基于权重的随机选择
            import random
            total_weight = sum(ep.weight for ep in healthy_endpoints)
            if total_weight == 0:
                return healthy_endpoints[0]
            
            rand = random.randint(1, total_weight)
            for ep in healthy_endpoints:
                rand -= ep.weight
                if rand <= 0:
                    return ep
        
        return healthy_endpoints[0]


class ServiceClient:
    """统一服务调用客户端"""
    
    def __init__(self, gateway_url: str = "http://localhost:8080", **kwargs):
        self.gateway_url = gateway_url
        self.service_registry = ServiceRegistry(gateway_url)
        self.load_balancer = LoadBalancer()
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.session = None
        self.metrics = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "retry_count": 0,
            "circuit_breaker_trips": 0
        }
        
        # 默认配置
        self.default_config = CallConfig(**kwargs)
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
    
    async def call(
        self,
        service_name: str,
        method: CallMethod,
        path: str,
        config: Optional[CallConfig] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        统一服务调用接口
        
        Args:
            service_name: 目标服务名称
            method: HTTP方法
            path: 请求路径
            config: 调用配置
            **kwargs: 请求参数 (json, params, headers等)
        
        Returns:
            响应数据
        """
        call_config = config or self.default_config
        self.metrics["total_calls"] += 1
        
        # 获取熔断器
        circuit_breaker = self._get_circuit_breaker(service_name)
        
        if not circuit_breaker.can_call():
            self.metrics["circuit_breaker_trips"] += 1
            raise ServiceCallError(f"服务 {service_name} 熔断器开启，暂时不可用")
        
        # 重试逻辑
        last_exception = None
        for attempt in range(call_config.retry_times + 1):
            try:
                result = await self._do_call(service_name, method, path, call_config, **kwargs)
                circuit_breaker.record_success()
                self.metrics["successful_calls"] += 1
                return result
                
            except Exception as e:
                last_exception = e
                circuit_breaker.record_failure()
                
                if attempt < call_config.retry_times:
                    self.metrics["retry_count"] += 1
                    delay = self._calculate_retry_delay(attempt, call_config)
                    logger.warning(f"调用失败，{delay}秒后重试 ({attempt + 1}/{call_config.retry_times}): {e}")
                    await asyncio.sleep(delay)
                else:
                    break
        
        self.metrics["failed_calls"] += 1
        raise ServiceCallError(f"服务调用失败 {service_name}: {last_exception}")
    
    async def _do_call(
        self,
        service_name: str,
        method: CallMethod,
        path: str,
        config: CallConfig,
        **kwargs
    ) -> Dict[str, Any]:
        """执行实际的服务调用"""
        
        # 选择服务端点
        endpoint = await self._select_endpoint(service_name)
        if not endpoint:
            raise ServiceCallError(f"服务 {service_name} 无可用实例")
        
        # 构建请求URL
        url = f"{endpoint.base_url}{path}"
        
        # 设置请求头
        headers = kwargs.get("headers", {})
        headers.setdefault("Content-Type", "application/json")
        headers["X-Service-Name"] = service_name
        headers["X-Request-ID"] = str(uuid.uuid4())
        
        # 执行HTTP请求
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        timeout = aiohttp.ClientTimeout(total=config.timeout)
        
        async with self.session.request(
            method.value,
            url,
            timeout=timeout,
            headers=headers,
            **kwargs
        ) as response:
            
            if response.status >= 400:
                error_text = await response.text()
                raise ServiceCallError(
                    f"HTTP {response.status}: {error_text}",
                    status_code=response.status
                )
            
            return await response.json()
    
    async def _select_endpoint(self, service_name: str) -> Optional[ServiceEndpoint]:
        """选择服务端点"""
        endpoints = await self.service_registry.get_service_endpoints(service_name)
        return self.load_balancer.select_endpoint(endpoints)
    
    def _get_circuit_breaker(self, service_name: str) -> CircuitBreaker:
        """获取熔断器"""
        if service_name not in self.circuit_breakers:
            self.circuit_breakers[service_name] = CircuitBreaker()
        return self.circuit_breakers[service_name]
    
    def _calculate_retry_delay(self, attempt: int, config: CallConfig) -> float:
        """计算重试延迟"""
        if config.retry_strategy == RetryStrategy.FIXED:
            return config.retry_delay
        elif config.retry_strategy == RetryStrategy.EXPONENTIAL:
            return config.retry_delay * (2 ** attempt)
        elif config.retry_strategy == RetryStrategy.LINEAR:
            return config.retry_delay * (attempt + 1)
        else:
            return 0
    
    async def get_metrics(self) -> Dict[str, Any]:
        """获取调用指标"""
        return self.metrics.copy()
    
    async def health_check(self, service_name: str) -> bool:
        """检查服务健康状态"""
        try:
            await self.call(service_name, CallMethod.GET, "/health")
            return True
        except Exception:
            return False


class AsyncServiceClient:
    """异步事件服务客户端"""
    
    def __init__(self, messaging_service_url: str = "http://localhost:8008"):
        self.messaging_url = messaging_service_url
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def publish_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        target_service: Optional[str] = None,
        priority: str = "normal"
    ) -> bool:
        """发布异步事件"""
        try:
            event_data = {
                "event_type": event_type,
                "data": data,
                "target_service": target_service,
                "priority": priority,
                "timestamp": datetime.now().isoformat()
            }
            
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            async with self.session.post(
                f"{self.messaging_url}/api/events/publish",
                json=event_data,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                return response.status == 200
                
        except Exception as e:
            logger.error(f"发布事件失败: {e}")
            return False
    
    async def subscribe_event(
        self,
        event_type: str,
        handler: Callable,
        service_name: str
    ) -> bool:
        """订阅异步事件"""
        try:
            subscription_data = {
                "event_type": event_type,
                "service_name": service_name,
                "callback_url": f"http://{service_name}/internal/events/{event_type}"
            }
            
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            async with self.session.post(
                f"{self.messaging_url}/api/events/subscribe",
                json=subscription_data,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                return response.status == 200
                
        except Exception as e:
            logger.error(f"订阅事件失败: {e}")
            return False


class ServiceCallError(Exception):
    """服务调用异常"""
    
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


# 全局客户端实例
_service_client: Optional[ServiceClient] = None
_async_client: Optional[AsyncServiceClient] = None


async def get_service_client() -> ServiceClient:
    """获取服务客户端实例"""
    global _service_client
    if _service_client is None:
        _service_client = ServiceClient()
    return _service_client


async def get_async_client() -> AsyncServiceClient:
    """获取异步客户端实例"""
    global _async_client
    if _async_client is None:
        _async_client = AsyncServiceClient()
    return _async_client


# 便捷调用函数
async def call_service(
    service_name: str,
    method: CallMethod,
    path: str,
    **kwargs
) -> Dict[str, Any]:
    """便捷的服务调用函数"""
    async with ServiceClient() as client:
        return await client.call(service_name, method, path, **kwargs)


async def publish_event(event_type: str, data: Dict[str, Any], **kwargs) -> bool:
    """便捷的事件发布函数"""
    async with AsyncServiceClient() as client:
        return await client.publish_event(event_type, data, **kwargs) 