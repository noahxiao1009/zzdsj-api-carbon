"""
微服务注册与发现机制
支持动态服务注册、健康检查、负载均衡
"""

import asyncio
import aiohttp
import time
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import random
import json
from datetime import datetime, timedelta
import threading
from concurrent.futures import ThreadPoolExecutor
import weakref

logger = logging.getLogger(__name__)


class ServiceStatus(str, Enum):
    """服务状态枚举"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    STARTING = "starting"
    STOPPING = "stopping"
    DOWN = "down"


class LoadBalanceStrategy(str, Enum):
    """负载均衡策略"""
    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"


@dataclass
class ServiceInstance:
    """服务实例"""
    service_name: str
    instance_id: str
    host: str
    port: int
    endpoints: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: ServiceStatus = ServiceStatus.HEALTHY
    weight: int = 1
    connections: int = 0
    last_health_check: Optional[datetime] = None
    health_check_url: Optional[str] = None
    register_time: datetime = field(default_factory=datetime.now)
    
    @property
    def base_url(self) -> str:
        """获取服务基础URL"""
        return f"http://{self.host}:{self.port}"
    
    @property
    def health_url(self) -> str:
        """获取健康检查URL"""
        if self.health_check_url:
            return f"{self.base_url}{self.health_check_url}"
        return f"{self.base_url}/health"


class ServiceRegistry:
    """服务注册中心"""
    
    def __init__(self, health_check_interval: int = 30):
        self.services: Dict[str, List[ServiceInstance]] = {}
        self.health_check_interval = health_check_interval
        self.load_balancers: Dict[str, 'LoadBalancer'] = {}
        self._health_check_task: Optional[asyncio.Task] = None
        self._running = False
        self._lock = asyncio.Lock()
        self._thread_pool = ThreadPoolExecutor(max_workers=10, thread_name_prefix="health_check")
        
        # 服务状态变更回调
        self._status_change_callbacks: List[Callable] = []
        
        logger.info("服务注册中心初始化完成")
    
    async def register_service(
        self,
        service_name: str,
        instance_id: str,
        host: str,
        port: int,
        endpoints: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        health_check_url: Optional[str] = None,
        weight: int = 1
    ) -> bool:
        """注册服务实例"""
        async with self._lock:
            try:
                instance = ServiceInstance(
                    service_name=service_name,
                    instance_id=instance_id,
                    host=host,
                    port=port,
                    endpoints=endpoints or {},
                    metadata=metadata or {},
                    health_check_url=health_check_url,
                    weight=weight
                )
                
                if service_name not in self.services:
                    self.services[service_name] = []
                    self.load_balancers[service_name] = LoadBalancer(service_name)
                
                # 检查是否已存在相同实例
                existing_instance = self._find_instance(service_name, instance_id)
                if existing_instance:
                    # 更新现有实例
                    self._update_instance(existing_instance, instance)
                    logger.info(f"更新服务实例: {service_name}/{instance_id}")
                else:
                    # 添加新实例
                    self.services[service_name].append(instance)
                    logger.info(f"注册新服务实例: {service_name}/{instance_id} - {host}:{port}")
                
                # 更新负载均衡器
                self.load_balancers[service_name].update_instances(self.services[service_name])
                
                # 立即进行健康检查
                await self._health_check_instance(instance)
                
                # 触发状态变更回调
                self._notify_status_change("register", service_name, instance)
                
                return True
                
            except Exception as e:
                logger.error(f"注册服务实例失败: {service_name}/{instance_id} - {str(e)}")
                return False
    
    async def deregister_service(self, service_name: str, instance_id: str) -> bool:
        """注销服务实例"""
        async with self._lock:
            try:
                if service_name not in self.services:
                    return False
                
                instance = self._find_instance(service_name, instance_id)
                if not instance:
                    return False
                
                self.services[service_name].remove(instance)
                logger.info(f"注销服务实例: {service_name}/{instance_id}")
                
                # 更新负载均衡器
                if self.services[service_name]:
                    self.load_balancers[service_name].update_instances(self.services[service_name])
                else:
                    # 如果没有实例了，删除服务
                    del self.services[service_name]
                    del self.load_balancers[service_name]
                
                # 触发状态变更回调
                self._notify_status_change("deregister", service_name, instance)
                
                return True
                
            except Exception as e:
                logger.error(f"注销服务实例失败: {service_name}/{instance_id} - {str(e)}")
                return False
    
    async def get_service_instance(
        self,
        service_name: str,
        strategy: LoadBalanceStrategy = LoadBalanceStrategy.ROUND_ROBIN
    ) -> Optional[ServiceInstance]:
        """获取服务实例（负载均衡）"""
        if service_name not in self.services:
            return None
        
        healthy_instances = [
            instance for instance in self.services[service_name]
            if instance.status == ServiceStatus.HEALTHY
        ]
        
        if not healthy_instances:
            logger.warning(f"服务 {service_name} 没有健康的实例")
            return None
        
        load_balancer = self.load_balancers[service_name]
        return load_balancer.select_instance(strategy)
    
    def get_all_services(self) -> Dict[str, List[ServiceInstance]]:
        """获取所有服务列表"""
        return self.services.copy()
    
    def get_service_info(self, service_name: str) -> Optional[Dict[str, Any]]:
        """获取服务信息"""
        if service_name not in self.services:
            return None
        
        instances = self.services[service_name]
        healthy_count = sum(1 for inst in instances if inst.status == ServiceStatus.HEALTHY)
        
        return {
            "service_name": service_name,
            "instance_count": len(instances),
            "healthy_count": healthy_count,
            "instances": [
                {
                    "instance_id": inst.instance_id,
                    "host": inst.host,
                    "port": inst.port,
                    "status": inst.status.value,
                    "weight": inst.weight,
                    "connections": inst.connections,
                    "last_health_check": inst.last_health_check.isoformat() if inst.last_health_check else None,
                    "register_time": inst.register_time.isoformat()
                }
                for inst in instances
            ]
        }
    
    async def start_health_check(self):
        """启动健康检查任务"""
        if self._running:
            return
        
        self._running = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info("健康检查任务已启动")
    
    async def stop_health_check(self):
        """停止健康检查任务"""
        if not self._running:
            return
        
        self._running = False
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        self._thread_pool.shutdown(wait=True)
        logger.info("健康检查任务已停止")
    
    def add_status_change_callback(self, callback: Callable):
        """添加状态变更回调"""
        self._status_change_callbacks.append(callback)
    
    def _find_instance(self, service_name: str, instance_id: str) -> Optional[ServiceInstance]:
        """查找服务实例"""
        if service_name not in self.services:
            return None
        
        for instance in self.services[service_name]:
            if instance.instance_id == instance_id:
                return instance
        
        return None
    
    def _update_instance(self, existing: ServiceInstance, new: ServiceInstance):
        """更新实例信息"""
        existing.host = new.host
        existing.port = new.port
        existing.endpoints = new.endpoints
        existing.metadata = new.metadata
        existing.health_check_url = new.health_check_url
        existing.weight = new.weight
        existing.status = ServiceStatus.HEALTHY  # 重新注册时重置状态
    
    def _notify_status_change(self, action: str, service_name: str, instance: ServiceInstance):
        """通知状态变更"""
        for callback in self._status_change_callbacks:
            try:
                callback(action, service_name, instance)
            except Exception as e:
                logger.error(f"状态变更回调执行失败: {str(e)}")
    
    async def _health_check_loop(self):
        """健康检查循环"""
        while self._running:
            try:
                await self._perform_health_checks()
                await asyncio.sleep(self.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"健康检查循环异常: {str(e)}")
                await asyncio.sleep(5)
    
    async def _perform_health_checks(self):
        """执行健康检查"""
        tasks = []
        
        for service_name, instances in self.services.items():
            for instance in instances:
                task = asyncio.create_task(self._health_check_instance(instance))
                tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _health_check_instance(self, instance: ServiceInstance):
        """健康检查单个实例"""
        try:
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(instance.health_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("status") == "healthy":
                            if instance.status != ServiceStatus.HEALTHY:
                                logger.info(f"服务实例恢复健康: {instance.service_name}/{instance.instance_id}")
                                self._notify_status_change("health_restored", instance.service_name, instance)
                            
                            instance.status = ServiceStatus.HEALTHY
                            instance.last_health_check = datetime.now()
                        else:
                            self._mark_instance_unhealthy(instance, "健康检查返回非健康状态")
                    else:
                        self._mark_instance_unhealthy(instance, f"健康检查返回状态码: {response.status}")
                        
        except Exception as e:
            self._mark_instance_unhealthy(instance, f"健康检查异常: {str(e)}")
    
    def _mark_instance_unhealthy(self, instance: ServiceInstance, reason: str):
        """标记实例为不健康"""
        if instance.status == ServiceStatus.HEALTHY:
            logger.warning(f"服务实例变为不健康: {instance.service_name}/{instance.instance_id} - {reason}")
            self._notify_status_change("health_lost", instance.service_name, instance)
        
        instance.status = ServiceStatus.UNHEALTHY
        instance.last_health_check = datetime.now()


class LoadBalancer:
    """负载均衡器"""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.instances: List[ServiceInstance] = []
        self.round_robin_index = 0
        self._lock = threading.Lock()
    
    def update_instances(self, instances: List[ServiceInstance]):
        """更新实例列表"""
        with self._lock:
            self.instances = [inst for inst in instances if inst.status == ServiceStatus.HEALTHY]
    
    def select_instance(self, strategy: LoadBalanceStrategy) -> Optional[ServiceInstance]:
        """选择实例"""
        with self._lock:
            if not self.instances:
                return None
            
            if strategy == LoadBalanceStrategy.ROUND_ROBIN:
                return self._round_robin()
            elif strategy == LoadBalanceStrategy.RANDOM:
                return self._random()
            elif strategy == LoadBalanceStrategy.LEAST_CONNECTIONS:
                return self._least_connections()
            elif strategy == LoadBalanceStrategy.WEIGHTED_ROUND_ROBIN:
                return self._weighted_round_robin()
            else:
                return self._round_robin()
    
    def _round_robin(self) -> ServiceInstance:
        """轮询算法"""
        instance = self.instances[self.round_robin_index]
        self.round_robin_index = (self.round_robin_index + 1) % len(self.instances)
        return instance
    
    def _random(self) -> ServiceInstance:
        """随机算法"""
        return random.choice(self.instances)
    
    def _least_connections(self) -> ServiceInstance:
        """最少连接算法"""
        return min(self.instances, key=lambda x: x.connections)
    
    def _weighted_round_robin(self) -> ServiceInstance:
        """加权轮询算法"""
        total_weight = sum(inst.weight for inst in self.instances)
        if total_weight == 0:
            return self._round_robin()
        
        # 简化的加权轮询实现
        weights = []
        for instance in self.instances:
            weights.extend([instance] * instance.weight)
        
        if weights:
            selected = weights[self.round_robin_index % len(weights)]
            self.round_robin_index = (self.round_robin_index + 1) % len(weights)
            return selected
        
        return self._round_robin()


# 全局服务注册实例
service_registry = ServiceRegistry()


async def get_service_registry() -> ServiceRegistry:
    """获取服务注册实例"""
    return service_registry


def register_service_on_startup():
    """启动时注册服务的装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            await service_registry.start_health_check()
            return result
        return wrapper
    return decorator


def deregister_service_on_shutdown():
    """关闭时注销服务的装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            await service_registry.stop_health_check()
            return result
        return wrapper
    return decorator 