"""
智能负载均衡器 - 高级负载均衡策略和流量分配
"""

import asyncio
import logging
import time
import random
import hashlib
from typing import Dict, Any, Optional, List, Tuple, Set, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from collections import deque, defaultdict
import statistics
import json

from shared.service_client import call_service, CallMethod, CallConfig, RetryStrategy
from app.core.redis import redis_manager
from app.core.config import settings
from app.services.agent_pool_manager import AgentInstance, AgentStatus, get_agent_pool_manager
from app.services.agent_health_monitor import get_agent_health_monitor, HealthStatus

logger = logging.getLogger(__name__)


class LoadBalanceAlgorithm(str, Enum):
    """负载均衡算法"""
    ROUND_ROBIN = "round_robin"                    # 轮询
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"  # 加权轮询
    LEAST_CONNECTIONS = "least_connections"        # 最少连接
    WEIGHTED_LEAST_CONNECTIONS = "weighted_least_connections"  # 加权最少连接
    FASTEST_RESPONSE = "fastest_response"          # 最快响应
    RESOURCE_BASED = "resource_based"              # 基于资源
    ADAPTIVE_RANDOM = "adaptive_random"            # 自适应随机
    CONSISTENT_HASH = "consistent_hash"            # 一致性哈希
    GEOGRAPHIC = "geographic"                      # 地理位置
    PREDICTIVE = "predictive"                      # 预测性负载均衡


class SessionAffinityType(str, Enum):
    """会话亲和性类型"""
    NONE = "none"                    # 无亲和性
    CLIENT_IP = "client_ip"          # 基于客户端IP
    SESSION_ID = "session_id"        # 基于会话ID
    USER_ID = "user_id"             # 基于用户ID
    CUSTOM_HEADER = "custom_header"  # 基于自定义头


@dataclass
class LoadBalanceConfig:
    """负载均衡配置"""
    algorithm: LoadBalanceAlgorithm = LoadBalanceAlgorithm.WEIGHTED_LEAST_CONNECTIONS
    session_affinity: SessionAffinityType = SessionAffinityType.SESSION_ID
    health_check_weight: float = 0.3     # 健康检查权重
    response_time_weight: float = 0.3     # 响应时间权重
    load_weight: float = 0.4              # 负载权重
    sticky_session_timeout: int = 3600    # 粘性会话超时(秒)
    failover_retries: int = 3             # 故障转移重试次数
    circuit_breaker_enabled: bool = True  # 熔断器启用
    adaptive_weights: bool = True          # 自适应权重调整


@dataclass
class RoutingRequest:
    """路由请求"""
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    client_ip: Optional[str] = None
    request_type: str = "chat"
    priority: int = 1  # 1-10, 10最高
    headers: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RoutingResult:
    """路由结果"""
    instance: Optional[AgentInstance] = None
    success: bool = False
    error_message: Optional[str] = None
    routing_time: float = 0.0
    algorithm_used: Optional[LoadBalanceAlgorithm] = None
    fallback_used: bool = False
    affinity_hit: bool = False


@dataclass
class LoadBalanceMetrics:
    """负载均衡指标"""
    total_requests: int = 0
    successful_routes: int = 0
    failed_routes: int = 0
    average_routing_time: float = 0.0
    affinity_hits: int = 0
    fallback_routes: int = 0
    algorithm_usage: Dict[str, int] = field(default_factory=dict)
    instance_usage: Dict[str, int] = field(default_factory=dict)


class SmartLoadBalancer:
    """智能负载均衡器"""
    
    def __init__(self, config: LoadBalanceConfig = None):
        self.config = config or LoadBalanceConfig()
        self.metrics = LoadBalanceMetrics()
        self.round_robin_counters: Dict[str, int] = defaultdict(int)
        self.session_affinity_map: Dict[str, str] = {}  # session -> instance_id
        self.response_time_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=50))
        self.load_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=50))
        
        # 一致性哈希环
        self.hash_ring: Dict[int, str] = {}
        self.virtual_nodes = 150  # 每个实例的虚拟节点数
        
        # 熔断器状态
        self.circuit_breakers: Dict[str, Dict[str, Any]] = {}
        
        # 预测模型参数
        self.prediction_weights: Dict[str, float] = {}
        self.learning_rate = 0.01
        
        # 启动后台任务
        self._weight_update_task = None
        self._metrics_cleanup_task = None
        self._start_background_tasks()
    
    async def route_request(
        self, 
        agent_id: str, 
        request: RoutingRequest
    ) -> RoutingResult:
        """路由请求到最佳实例"""
        start_time = time.time()
        result = RoutingResult()
        
        try:
            self.metrics.total_requests += 1
            
            # 获取可用实例
            available_instances = await self._get_available_instances(agent_id)
            if not available_instances:
                result.error_message = "没有可用的实例"
                return result
            
            # 检查会话亲和性
            if self.config.session_affinity != SessionAffinityType.NONE:
                affinity_instance = await self._check_session_affinity(request, available_instances)
                if affinity_instance:
                    result.instance = affinity_instance
                    result.affinity_hit = True
                    result.success = True
                    self.metrics.affinity_hits += 1
                    return result
            
            # 应用负载均衡算法
            selected_instance = await self._apply_load_balance_algorithm(
                available_instances, request
            )
            
            if selected_instance:
                result.instance = selected_instance
                result.success = True
                result.algorithm_used = self.config.algorithm
                
                # 更新会话亲和性
                await self._update_session_affinity(request, selected_instance)
                
                # 更新使用统计
                self.metrics.instance_usage[selected_instance.instance_id] = \
                    self.metrics.instance_usage.get(selected_instance.instance_id, 0) + 1
                
                self.metrics.successful_routes += 1
            else:
                result.error_message = "负载均衡算法未能选择实例"
                self.metrics.failed_routes += 1
            
        except Exception as e:
            result.error_message = f"路由失败: {str(e)}"
            self.metrics.failed_routes += 1
            logger.error(f"请求路由失败: {e}")
        
        finally:
            result.routing_time = (time.time() - start_time) * 1000  # 毫秒
            
            # 更新平均路由时间
            total_time = self.metrics.average_routing_time * (self.metrics.total_requests - 1)
            self.metrics.average_routing_time = (total_time + result.routing_time) / self.metrics.total_requests
            
            # 更新算法使用统计
            if result.algorithm_used:
                algo_name = result.algorithm_used.value
                self.metrics.algorithm_usage[algo_name] = \
                    self.metrics.algorithm_usage.get(algo_name, 0) + 1
        
        return result
    
    async def _get_available_instances(self, agent_id: str) -> List[AgentInstance]:
        """获取可用实例，过滤熔断器状态"""
        pool_manager = get_agent_pool_manager()
        instance_ids = pool_manager.agent_instances.get(agent_id, [])
        
        available_instances = []
        for instance_id in instance_ids:
            instance = pool_manager.instances.get(instance_id)
            if instance and instance.is_available():
                # 检查熔断器状态
                if self.config.circuit_breaker_enabled:
                    if not self._is_circuit_breaker_open(instance_id):
                        available_instances.append(instance)
                else:
                    available_instances.append(instance)
        
        return available_instances
    
    async def _check_session_affinity(
        self, 
        request: RoutingRequest, 
        instances: List[AgentInstance]
    ) -> Optional[AgentInstance]:
        """检查会话亲和性"""
        try:
            affinity_key = None
            
            if self.config.session_affinity == SessionAffinityType.SESSION_ID and request.session_id:
                affinity_key = f"session:{request.session_id}"
            elif self.config.session_affinity == SessionAffinityType.USER_ID and request.user_id:
                affinity_key = f"user:{request.user_id}"
            elif self.config.session_affinity == SessionAffinityType.CLIENT_IP and request.client_ip:
                affinity_key = f"ip:{request.client_ip}"
            elif self.config.session_affinity == SessionAffinityType.CUSTOM_HEADER:
                header_value = request.headers.get("X-Affinity-Key")
                if header_value:
                    affinity_key = f"header:{header_value}"
            
            if not affinity_key:
                return None
            
            # 从Redis获取亲和性映射
            affinity_map_key = f"load_balance:affinity:{affinity_key}"
            instance_id = redis_manager.get(affinity_map_key)
            
            if instance_id:
                instance_id = instance_id.decode() if isinstance(instance_id, bytes) else instance_id
                # 检查实例是否仍然可用
                for instance in instances:
                    if instance.instance_id == instance_id:
                        return instance
            
            return None
            
        except Exception as e:
            logger.warning(f"检查会话亲和性失败: {e}")
            return None
    
    async def _update_session_affinity(
        self, 
        request: RoutingRequest, 
        instance: AgentInstance
    ):
        """更新会话亲和性"""
        try:
            if self.config.session_affinity == SessionAffinityType.NONE:
                return
            
            affinity_key = None
            
            if self.config.session_affinity == SessionAffinityType.SESSION_ID and request.session_id:
                affinity_key = f"session:{request.session_id}"
            elif self.config.session_affinity == SessionAffinityType.USER_ID and request.user_id:
                affinity_key = f"user:{request.user_id}"
            elif self.config.session_affinity == SessionAffinityType.CLIENT_IP and request.client_ip:
                affinity_key = f"ip:{request.client_ip}"
            elif self.config.session_affinity == SessionAffinityType.CUSTOM_HEADER:
                header_value = request.headers.get("X-Affinity-Key")
                if header_value:
                    affinity_key = f"header:{header_value}"
            
            if affinity_key:
                affinity_map_key = f"load_balance:affinity:{affinity_key}"
                redis_manager.set(
                    affinity_map_key, 
                    instance.instance_id, 
                    ex=self.config.sticky_session_timeout
                )
            
        except Exception as e:
            logger.warning(f"更新会话亲和性失败: {e}")
    
    async def _apply_load_balance_algorithm(
        self, 
        instances: List[AgentInstance], 
        request: RoutingRequest
    ) -> Optional[AgentInstance]:
        """应用负载均衡算法"""
        try:
            algorithm = self.config.algorithm
            
            if algorithm == LoadBalanceAlgorithm.ROUND_ROBIN:
                return self._round_robin_select(instances, request)
            elif algorithm == LoadBalanceAlgorithm.WEIGHTED_ROUND_ROBIN:
                return self._weighted_round_robin_select(instances, request)
            elif algorithm == LoadBalanceAlgorithm.LEAST_CONNECTIONS:
                return self._least_connections_select(instances, request)
            elif algorithm == LoadBalanceAlgorithm.WEIGHTED_LEAST_CONNECTIONS:
                return self._weighted_least_connections_select(instances, request)
            elif algorithm == LoadBalanceAlgorithm.FASTEST_RESPONSE:
                return self._fastest_response_select(instances, request)
            elif algorithm == LoadBalanceAlgorithm.RESOURCE_BASED:
                return self._resource_based_select(instances, request)
            elif algorithm == LoadBalanceAlgorithm.ADAPTIVE_RANDOM:
                return self._adaptive_random_select(instances, request)
            elif algorithm == LoadBalanceAlgorithm.CONSISTENT_HASH:
                return self._consistent_hash_select(instances, request)
            elif algorithm == LoadBalanceAlgorithm.PREDICTIVE:
                return self._predictive_select(instances, request)
            else:
                return self._weighted_least_connections_select(instances, request)
                
        except Exception as e:
            logger.error(f"应用负载均衡算法失败: {e}")
            return None
    
    def _round_robin_select(
        self, 
        instances: List[AgentInstance], 
        request: RoutingRequest
    ) -> Optional[AgentInstance]:
        """轮询选择"""
        if not instances:
            return None
        
        agent_id = instances[0].agent_id
        counter = self.round_robin_counters[agent_id]
        selected = instances[counter % len(instances)]
        self.round_robin_counters[agent_id] = counter + 1
        
        return selected
    
    def _weighted_round_robin_select(
        self, 
        instances: List[AgentInstance], 
        request: RoutingRequest
    ) -> Optional[AgentInstance]:
        """加权轮询选择"""
        if not instances:
            return None
        
        # 构建加权列表
        weighted_instances = []
        for instance in instances:
            weight = max(1, int(instance.weight * 10))  # 确保至少有1个权重
            weighted_instances.extend([instance] * weight)
        
        if not weighted_instances:
            return instances[0]
        
        agent_id = instances[0].agent_id
        counter = self.round_robin_counters[agent_id]
        selected = weighted_instances[counter % len(weighted_instances)]
        self.round_robin_counters[agent_id] = counter + 1
        
        return selected
    
    def _least_connections_select(
        self, 
        instances: List[AgentInstance], 
        request: RoutingRequest
    ) -> Optional[AgentInstance]:
        """最少连接选择"""
        return min(instances, key=lambda x: x.active_sessions)
    
    def _weighted_least_connections_select(
        self, 
        instances: List[AgentInstance], 
        request: RoutingRequest
    ) -> Optional[AgentInstance]:
        """加权最少连接选择"""
        def connection_ratio(instance):
            # 连接数除以权重
            return instance.active_sessions / max(instance.weight, 0.1)
        
        return min(instances, key=connection_ratio)
    
    def _fastest_response_select(
        self, 
        instances: List[AgentInstance], 
        request: RoutingRequest
    ) -> Optional[AgentInstance]:
        """最快响应选择"""
        return min(instances, key=lambda x: x.average_response_time)
    
    def _resource_based_select(
        self, 
        instances: List[AgentInstance], 
        request: RoutingRequest
    ) -> Optional[AgentInstance]:
        """基于资源的选择"""
        def resource_score(instance):
            # 综合考虑健康分数、响应时间、负载
            health_factor = instance.health_score / 100.0
            load_factor = 1.0 - (instance.active_sessions / max(instance.max_concurrent_sessions, 1))
            response_factor = 1.0 / max(instance.average_response_time, 1)
            
            return (
                health_factor * self.config.health_check_weight +
                load_factor * self.config.load_weight +
                response_factor * self.config.response_time_weight
            )
        
        return max(instances, key=resource_score)
    
    def _adaptive_random_select(
        self, 
        instances: List[AgentInstance], 
        request: RoutingRequest
    ) -> Optional[AgentInstance]:
        """自适应随机选择"""
        # 根据实例性能计算权重
        weights = []
        for instance in instances:
            # 基于健康分数和负载计算权重
            health_weight = instance.health_score / 100.0
            load_weight = 1.0 - (instance.active_sessions / max(instance.max_concurrent_sessions, 1))
            weight = (health_weight + load_weight) * instance.weight
            weights.append(max(weight, 0.1))  # 确保最小权重
        
        total_weight = sum(weights)
        random_value = random.uniform(0, total_weight)
        
        cumulative_weight = 0
        for instance, weight in zip(instances, weights):
            cumulative_weight += weight
            if random_value <= cumulative_weight:
                return instance
        
        return instances[-1]  # 后备选择
    
    def _consistent_hash_select(
        self, 
        instances: List[AgentInstance], 
        request: RoutingRequest
    ) -> Optional[AgentInstance]:
        """一致性哈希选择"""
        # 更新哈希环
        self._update_hash_ring(instances)
        
        # 计算请求的哈希值
        hash_key = request.session_id or request.user_id or request.client_ip or "default"
        request_hash = int(hashlib.md5(hash_key.encode()).hexdigest(), 16)
        
        # 在哈希环中查找最近的节点
        if not self.hash_ring:
            return instances[0] if instances else None
        
        # 找到第一个大于等于请求哈希的节点
        sorted_hashes = sorted(self.hash_ring.keys())
        for node_hash in sorted_hashes:
            if node_hash >= request_hash:
                instance_id = self.hash_ring[node_hash]
                for instance in instances:
                    if instance.instance_id == instance_id:
                        return instance
        
        # 如果没找到，返回环上的第一个节点
        first_hash = sorted_hashes[0]
        instance_id = self.hash_ring[first_hash]
        for instance in instances:
            if instance.instance_id == instance_id:
                return instance
        
        return instances[0]  # 后备选择
    
    def _predictive_select(
        self, 
        instances: List[AgentInstance], 
        request: RoutingRequest
    ) -> Optional[AgentInstance]:
        """预测性选择"""
        # 基于历史数据预测最佳实例
        best_score = float('-inf')
        best_instance = None
        
        for instance in instances:
            # 预测分数基于多个因素
            score = self._calculate_predictive_score(instance, request)
            if score > best_score:
                best_score = score
                best_instance = instance
        
        return best_instance or instances[0]
    
    def _calculate_predictive_score(
        self, 
        instance: AgentInstance, 
        request: RoutingRequest
    ) -> float:
        """计算预测分数"""
        try:
            # 基础分数
            base_score = instance.health_score / 100.0
            
            # 负载预测
            load_ratio = instance.active_sessions / max(instance.max_concurrent_sessions, 1)
            load_score = 1.0 - load_ratio
            
            # 响应时间预测
            response_history = self.response_time_history.get(instance.instance_id, deque())
            if len(response_history) > 5:
                avg_response = statistics.mean(response_history)
                response_score = 1.0 / max(avg_response, 1)
            else:
                response_score = 1.0 / max(instance.average_response_time, 1)
            
            # 获取预测权重
            weight_key = f"{instance.instance_id}_{request.request_type}"
            prediction_weight = self.prediction_weights.get(weight_key, 1.0)
            
            # 综合分数
            final_score = (
                base_score * 0.3 +
                load_score * 0.3 +
                response_score * 0.3 +
                prediction_weight * 0.1
            )
            
            return final_score
            
        except Exception as e:
            logger.warning(f"计算预测分数失败: {e}")
            return 0.5  # 默认分数
    
    def _update_hash_ring(self, instances: List[AgentInstance]):
        """更新一致性哈希环"""
        try:
            current_instances = set(instance.instance_id for instance in instances)
            ring_instances = set(self.hash_ring.values())
            
            # 检查是否需要更新
            if current_instances == ring_instances:
                return
            
            # 重建哈希环
            self.hash_ring.clear()
            
            for instance in instances:
                for i in range(self.virtual_nodes):
                    virtual_key = f"{instance.instance_id}:{i}"
                    hash_value = int(hashlib.md5(virtual_key.encode()).hexdigest(), 16)
                    self.hash_ring[hash_value] = instance.instance_id
            
        except Exception as e:
            logger.error(f"更新哈希环失败: {e}")
    
    def _is_circuit_breaker_open(self, instance_id: str) -> bool:
        """检查熔断器是否打开"""
        try:
            cb = self.circuit_breakers.get(instance_id)
            if not cb:
                return False
            
            if cb["state"] == "closed":
                return False
            elif cb["state"] == "open":
                # 检查是否应该进入半开状态
                if time.time() - cb["last_failure"] > cb["timeout"]:
                    cb["state"] = "half_open"
                    return False
                return True
            elif cb["state"] == "half_open":
                return False
            
            return False
            
        except Exception as e:
            logger.warning(f"检查熔断器状态失败: {e}")
            return False
    
    async def update_instance_performance(
        self, 
        instance_id: str, 
        response_time: float, 
        success: bool
    ):
        """更新实例性能数据"""
        try:
            # 更新响应时间历史
            self.response_time_history[instance_id].append(response_time)
            
            # 更新熔断器状态
            await self._update_circuit_breaker(instance_id, success)
            
            # 更新预测权重（强化学习）
            if self.config.adaptive_weights:
                await self._update_prediction_weights(instance_id, response_time, success)
            
        except Exception as e:
            logger.error(f"更新实例性能数据失败: {e}")
    
    async def _update_circuit_breaker(self, instance_id: str, success: bool):
        """更新熔断器状态"""
        try:
            if not self.config.circuit_breaker_enabled:
                return
            
            if instance_id not in self.circuit_breakers:
                self.circuit_breakers[instance_id] = {
                    "state": "closed",
                    "failure_count": 0,
                    "success_count": 0,
                    "last_failure": 0,
                    "timeout": 60,  # 60秒超时
                    "failure_threshold": 5,
                    "success_threshold": 3
                }
            
            cb = self.circuit_breakers[instance_id]
            
            if success:
                cb["success_count"] += 1
                if cb["state"] == "half_open" and cb["success_count"] >= cb["success_threshold"]:
                    cb["state"] = "closed"
                    cb["failure_count"] = 0
                    cb["success_count"] = 0
            else:
                cb["failure_count"] += 1
                cb["last_failure"] = time.time()
                cb["success_count"] = 0
                
                if cb["failure_count"] >= cb["failure_threshold"]:
                    cb["state"] = "open"
            
        except Exception as e:
            logger.error(f"更新熔断器状态失败: {e}")
    
    async def _update_prediction_weights(
        self, 
        instance_id: str, 
        response_time: float, 
        success: bool
    ):
        """更新预测权重（简单的强化学习）"""
        try:
            # 计算奖励/惩罚
            if success:
                reward = 1.0 / max(response_time, 1)  # 响应时间越短奖励越高
            else:
                reward = -1.0  # 失败的惩罚
            
            # 更新权重
            for request_type in ["chat", "voice", "stream"]:
                weight_key = f"{instance_id}_{request_type}"
                current_weight = self.prediction_weights.get(weight_key, 1.0)
                
                # 简单的梯度更新
                new_weight = current_weight + self.learning_rate * reward
                new_weight = max(0.1, min(2.0, new_weight))  # 限制权重范围
                
                self.prediction_weights[weight_key] = new_weight
            
        except Exception as e:
            logger.error(f"更新预测权重失败: {e}")
    
    def _start_background_tasks(self):
        """启动后台任务"""
        async def weight_update_loop():
            """权重更新循环"""
            while True:
                try:
                    await asyncio.sleep(300)  # 每5分钟更新一次
                    
                    if self.config.adaptive_weights:
                        # 衰减所有权重，防止过度拟合
                        for key in self.prediction_weights:
                            self.prediction_weights[key] *= 0.99
                
                except Exception as e:
                    logger.error(f"权重更新循环错误: {e}")
        
        async def metrics_cleanup_loop():
            """指标清理循环"""
            while True:
                try:
                    await asyncio.sleep(3600)  # 每小时清理一次
                    
                    # 清理过期的亲和性映射
                    current_time = time.time()
                    expired_keys = []
                    
                    for key, timestamp in list(self.session_affinity_map.items()):
                        if current_time - timestamp > self.config.sticky_session_timeout:
                            expired_keys.append(key)
                    
                    for key in expired_keys:
                        del self.session_affinity_map[key]
                
                except Exception as e:
                    logger.error(f"指标清理循环错误: {e}")
        
        self._weight_update_task = asyncio.create_task(weight_update_loop())
        self._metrics_cleanup_task = asyncio.create_task(metrics_cleanup_loop())
    
    def get_load_balance_stats(self) -> Dict[str, Any]:
        """获取负载均衡统计"""
        return {
            "metrics": {
                "total_requests": self.metrics.total_requests,
                "successful_routes": self.metrics.successful_routes,
                "failed_routes": self.metrics.failed_routes,
                "success_rate": self.metrics.successful_routes / max(self.metrics.total_requests, 1),
                "average_routing_time": self.metrics.average_routing_time,
                "affinity_hits": self.metrics.affinity_hits,
                "affinity_hit_rate": self.metrics.affinity_hits / max(self.metrics.total_requests, 1),
                "fallback_routes": self.metrics.fallback_routes,
                "algorithm_usage": self.metrics.algorithm_usage,
                "instance_usage": self.metrics.instance_usage
            },
            "configuration": {
                "algorithm": self.config.algorithm.value,
                "session_affinity": self.config.session_affinity.value,
                "circuit_breaker_enabled": self.config.circuit_breaker_enabled,
                "adaptive_weights": self.config.adaptive_weights
            },
            "circuit_breakers": {
                instance_id: {
                    "state": cb["state"],
                    "failure_count": cb["failure_count"],
                    "success_count": cb["success_count"]
                }
                for instance_id, cb in self.circuit_breakers.items()
            },
            "prediction_weights": len(self.prediction_weights),
            "timestamp": time.time()
        }
    
    async def cleanup(self):
        """清理资源"""
        try:
            # 取消后台任务
            if self._weight_update_task:
                self._weight_update_task.cancel()
            if self._metrics_cleanup_task:
                self._metrics_cleanup_task.cancel()
            
            logger.info("智能负载均衡器清理完成")
        except Exception as e:
            logger.error(f"清理智能负载均衡器失败: {e}")


# 全局实例
_smart_load_balancer: Optional[SmartLoadBalancer] = None


def get_smart_load_balancer() -> SmartLoadBalancer:
    """获取智能负载均衡器实例"""
    global _smart_load_balancer
    if _smart_load_balancer is None:
        _smart_load_balancer = SmartLoadBalancer()
    return _smart_load_balancer