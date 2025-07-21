"""
智能体实例池管理器 - 负载均衡和资源优化
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, List, Set
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict, deque
import hashlib
import json

from shared.service_client import call_service, CallMethod, CallConfig, RetryStrategy
from app.core.redis import redis_manager
from app.core.config import settings

logger = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    """智能体状态枚举"""
    INITIALIZING = "initializing"    # 初始化中
    IDLE = "idle"                   # 空闲
    BUSY = "busy"                   # 忙碌
    OVERLOADED = "overloaded"       # 过载
    UNHEALTHY = "unhealthy"         # 不健康
    OFFLINE = "offline"             # 离线


class LoadBalanceStrategy(str, Enum):
    """负载均衡策略"""
    ROUND_ROBIN = "round_robin"     # 轮询
    LEAST_CONNECTIONS = "least_connections"  # 最少连接
    WEIGHTED_RANDOM = "weighted_random"      # 权重随机
    RESPONSE_TIME = "response_time"          # 响应时间优先


@dataclass
class AgentInstance:
    """智能体实例"""
    instance_id: str
    agent_id: str
    service_url: str
    status: AgentStatus = AgentStatus.INITIALIZING
    created_at: float = field(default_factory=time.time)
    last_health_check: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    
    # 性能指标
    active_sessions: int = 0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_response_time: float = 0.0
    recent_response_times: deque = field(default_factory=lambda: deque(maxlen=100))
    
    # 健康指标
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    error_rate: float = 0.0
    health_score: float = 100.0
    
    # 配置
    max_concurrent_sessions: int = 50
    weight: float = 1.0
    
    def update_performance_metrics(self, response_time: float, success: bool):
        """更新性能指标"""
        self.total_requests += 1
        self.recent_response_times.append(response_time)
        
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
        
        # 更新平均响应时间
        if self.recent_response_times:
            self.average_response_time = sum(self.recent_response_times) / len(self.recent_response_times)
        
        # 更新错误率
        if self.total_requests > 0:
            self.error_rate = self.failed_requests / self.total_requests
        
        # 更新活动时间
        self.last_activity = time.time()
    
    def calculate_health_score(self) -> float:
        """计算健康分数"""
        # 基础分数
        base_score = 100.0
        
        # 响应时间惩罚 (超过1秒开始惩罚)
        if self.average_response_time > 1000:
            time_penalty = min(30, (self.average_response_time - 1000) / 100)
            base_score -= time_penalty
        
        # 错误率惩罚
        error_penalty = self.error_rate * 50
        base_score -= error_penalty
        
        # 负载惩罚
        if self.max_concurrent_sessions > 0:
            load_ratio = self.active_sessions / self.max_concurrent_sessions
            if load_ratio > 0.8:
                load_penalty = (load_ratio - 0.8) * 100
                base_score -= load_penalty
        
        # CPU和内存使用惩罚
        if self.cpu_usage > 80:
            base_score -= (self.cpu_usage - 80) * 0.5
        if self.memory_usage > 80:
            base_score -= (self.memory_usage - 80) * 0.5
        
        self.health_score = max(0.0, min(100.0, base_score))
        return self.health_score
    
    def is_available(self) -> bool:
        """检查实例是否可用"""
        return (
            self.status in [AgentStatus.IDLE, AgentStatus.BUSY] and
            self.active_sessions < self.max_concurrent_sessions and
            self.health_score > 20.0
        )
    
    def get_load_score(self) -> float:
        """获取负载分数 (越低越好)"""
        if not self.is_available():
            return float('inf')
        
        # 综合负载分数
        connection_ratio = self.active_sessions / max(self.max_concurrent_sessions, 1)
        response_time_score = self.average_response_time / 1000  # 转换为秒
        error_score = self.error_rate * 10
        
        return connection_ratio + response_time_score + error_score
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "instance_id": self.instance_id,
            "agent_id": self.agent_id,
            "service_url": self.service_url,
            "status": self.status.value,
            "created_at": self.created_at,
            "last_health_check": self.last_health_check,
            "last_activity": self.last_activity,
            "performance": {
                "active_sessions": self.active_sessions,
                "total_requests": self.total_requests,
                "successful_requests": self.successful_requests,
                "failed_requests": self.failed_requests,
                "average_response_time": self.average_response_time,
                "error_rate": self.error_rate
            },
            "health": {
                "cpu_usage": self.cpu_usage,
                "memory_usage": self.memory_usage,
                "health_score": self.health_score
            },
            "config": {
                "max_concurrent_sessions": self.max_concurrent_sessions,
                "weight": self.weight
            }
        }


class AgentPoolManager:
    """智能体实例池管理器"""
    
    def __init__(self):
        self.instances: Dict[str, AgentInstance] = {}
        self.agent_instances: Dict[str, List[str]] = defaultdict(list)  # agent_id -> instance_ids
        self.load_balance_strategy = LoadBalanceStrategy.LEAST_CONNECTIONS
        self.round_robin_counters: Dict[str, int] = defaultdict(int)
        
        # 配置
        self.min_instances_per_agent = 1
        self.max_instances_per_agent = 5
        self.health_check_interval = 30  # 秒
        self.instance_timeout = 300      # 5分钟无活动视为超时
        
        # 监控
        self.pool_metrics = {
            "total_instances": 0,
            "healthy_instances": 0,
            "busy_instances": 0,
            "idle_instances": 0,
            "failed_health_checks": 0,
            "auto_scaling_events": 0
        }
        
        # 启动后台任务
        self._health_check_task = None
        self._cleanup_task = None
        self._start_background_tasks()
    
    async def get_agent_instance(
        self, 
        agent_id: str, 
        session_id: Optional[str] = None,
        prefer_existing: bool = True
    ) -> Optional[AgentInstance]:
        """获取智能体实例"""
        try:
            # 检查是否有可用实例
            available_instances = self._get_available_instances(agent_id)
            
            if not available_instances:
                # 尝试创建新实例
                instance = await self._create_agent_instance(agent_id)
                if instance:
                    available_instances = [instance]
                else:
                    logger.warning(f"无法为智能体 {agent_id} 创建实例")
                    return None
            
            # 如果指定了会话ID且希望使用现有实例
            if session_id and prefer_existing:
                existing_instance = await self._get_session_instance(session_id)
                if existing_instance and existing_instance in available_instances:
                    return existing_instance
            
            # 根据负载均衡策略选择实例
            selected_instance = self._select_instance(available_instances)
            
            if selected_instance:
                # 增加活跃会话计数
                selected_instance.active_sessions += 1
                await self._update_instance_status(selected_instance)
                
                # 记录会话与实例的关联
                if session_id:
                    await self._associate_session_instance(session_id, selected_instance.instance_id)
            
            return selected_instance
            
        except Exception as e:
            logger.error(f"获取智能体实例失败: {e}")
            return None
    
    async def release_agent_instance(
        self, 
        instance_id: str, 
        session_id: Optional[str] = None,
        performance_metrics: Optional[Dict[str, Any]] = None
    ):
        """释放智能体实例"""
        try:
            instance = self.instances.get(instance_id)
            if not instance:
                return
            
            # 减少活跃会话计数
            instance.active_sessions = max(0, instance.active_sessions - 1)
            
            # 更新性能指标
            if performance_metrics:
                response_time = performance_metrics.get("response_time", 0)
                success = performance_metrics.get("success", True)
                instance.update_performance_metrics(response_time, success)
            
            # 更新实例状态
            await self._update_instance_status(instance)
            
            # 清除会话关联
            if session_id:
                await self._disassociate_session_instance(session_id)
            
            logger.debug(f"释放智能体实例: {instance_id}")
            
        except Exception as e:
            logger.error(f"释放智能体实例失败: {e}")
    
    async def _create_agent_instance(self, agent_id: str) -> Optional[AgentInstance]:
        """创建智能体实例"""
        try:
            # 检查是否超过最大实例数
            current_instances = len(self.agent_instances[agent_id])
            if current_instances >= self.max_instances_per_agent:
                logger.warning(f"智能体 {agent_id} 已达到最大实例数: {self.max_instances_per_agent}")
                return None
            
            # 调用 Agent-Service 创建实例
            create_config = CallConfig(
                timeout=30,
                retry_times=3,
                retry_strategy=RetryStrategy.EXPONENTIAL
            )
            
            response = await call_service(
                service_name="agent-service",
                method=CallMethod.POST,
                path=f"/api/v1/agents/{agent_id}/instances",
                config=create_config,
                json={
                    "max_concurrent_sessions": 50,
                    "auto_scaling": True
                }
            )
            
            if not response.get("success"):
                logger.error(f"创建智能体实例失败: {response.get('error')}")
                return None
            
            # 创建实例对象
            instance_data = response.get("instance", {})
            instance_id = instance_data.get("instance_id") or f"{agent_id}_{int(time.time())}"
            
            instance = AgentInstance(
                instance_id=instance_id,
                agent_id=agent_id,
                service_url=instance_data.get("service_url", f"http://agent-service:8081"),
                max_concurrent_sessions=instance_data.get("max_concurrent_sessions", 50),
                weight=instance_data.get("weight", 1.0)
            )
            
            # 注册实例
            self.instances[instance_id] = instance
            self.agent_instances[agent_id].append(instance_id)
            
            # 更新指标
            self.pool_metrics["total_instances"] += 1
            self.pool_metrics["auto_scaling_events"] += 1
            
            # 持久化到Redis
            await self._persist_instance(instance)
            
            logger.info(f"创建智能体实例成功: {instance_id}")
            return instance
            
        except Exception as e:
            logger.error(f"创建智能体实例失败: {e}")
            return None
    
    def _get_available_instances(self, agent_id: str) -> List[AgentInstance]:
        """获取可用实例列表"""
        instance_ids = self.agent_instances.get(agent_id, [])
        available_instances = []
        
        for instance_id in instance_ids:
            instance = self.instances.get(instance_id)
            if instance and instance.is_available():
                available_instances.append(instance)
        
        return available_instances
    
    def _select_instance(self, instances: List[AgentInstance]) -> Optional[AgentInstance]:
        """根据负载均衡策略选择实例"""
        if not instances:
            return None
        
        if self.load_balance_strategy == LoadBalanceStrategy.ROUND_ROBIN:
            return self._round_robin_select(instances)
        elif self.load_balance_strategy == LoadBalanceStrategy.LEAST_CONNECTIONS:
            return self._least_connections_select(instances)
        elif self.load_balance_strategy == LoadBalanceStrategy.WEIGHTED_RANDOM:
            return self._weighted_random_select(instances)
        elif self.load_balance_strategy == LoadBalanceStrategy.RESPONSE_TIME:
            return self._response_time_select(instances)
        else:
            return instances[0]  # 默认选择第一个
    
    def _round_robin_select(self, instances: List[AgentInstance]) -> AgentInstance:
        """轮询选择"""
        if not instances:
            return None
        
        agent_id = instances[0].agent_id
        counter = self.round_robin_counters[agent_id]
        selected = instances[counter % len(instances)]
        self.round_robin_counters[agent_id] = counter + 1
        
        return selected
    
    def _least_connections_select(self, instances: List[AgentInstance]) -> AgentInstance:
        """最少连接选择"""
        return min(instances, key=lambda x: x.active_sessions)
    
    def _weighted_random_select(self, instances: List[AgentInstance]) -> AgentInstance:
        """权重随机选择"""
        import random
        
        total_weight = sum(instance.weight for instance in instances)
        if total_weight <= 0:
            return random.choice(instances)
        
        random_value = random.uniform(0, total_weight)
        cumulative_weight = 0
        
        for instance in instances:
            cumulative_weight += instance.weight
            if random_value <= cumulative_weight:
                return instance
        
        return instances[-1]  # 后备选择
    
    def _response_time_select(self, instances: List[AgentInstance]) -> AgentInstance:
        """响应时间优先选择"""
        return min(instances, key=lambda x: x.average_response_time)
    
    async def _update_instance_status(self, instance: AgentInstance):
        """更新实例状态"""
        try:
            # 根据负载情况更新状态
            load_ratio = instance.active_sessions / max(instance.max_concurrent_sessions, 1)
            
            if load_ratio >= 1.0:
                instance.status = AgentStatus.OVERLOADED
            elif load_ratio >= 0.7:
                instance.status = AgentStatus.BUSY
            else:
                instance.status = AgentStatus.IDLE
            
            # 计算健康分数
            instance.calculate_health_score()
            
            # 如果健康分数过低，标记为不健康
            if instance.health_score < 20:
                instance.status = AgentStatus.UNHEALTHY
            
            # 持久化状态
            await self._persist_instance(instance)
            
        except Exception as e:
            logger.error(f"更新实例状态失败: {e}")
    
    async def _persist_instance(self, instance: AgentInstance):
        """持久化实例信息到Redis"""
        try:
            instance_key = f"agent_pool:instance:{instance.instance_id}"
            redis_manager.set_json(instance_key, instance.to_dict(), ex=3600)
            
            # 维护智能体实例列表
            agent_instances_key = f"agent_pool:agent:{instance.agent_id}:instances"
            redis_manager.sadd(agent_instances_key, instance.instance_id)
            redis_manager.expire(agent_instances_key, 3600)
            
        except Exception as e:
            logger.error(f"持久化实例信息失败: {e}")
    
    async def _associate_session_instance(self, session_id: str, instance_id: str):
        """关联会话与实例"""
        try:
            session_key = f"agent_pool:session:{session_id}"
            redis_manager.set(session_key, instance_id, ex=86400)  # 24小时
        except Exception as e:
            logger.error(f"关联会话实例失败: {e}")
    
    async def _disassociate_session_instance(self, session_id: str):
        """取消会话与实例的关联"""
        try:
            session_key = f"agent_pool:session:{session_id}"
            redis_manager.delete(session_key)
        except Exception as e:
            logger.error(f"取消会话实例关联失败: {e}")
    
    async def _get_session_instance(self, session_id: str) -> Optional[AgentInstance]:
        """获取会话关联的实例"""
        try:
            session_key = f"agent_pool:session:{session_id}"
            instance_id = redis_manager.get(session_key)
            
            if instance_id:
                return self.instances.get(instance_id.decode() if isinstance(instance_id, bytes) else instance_id)
            
            return None
        except Exception as e:
            logger.error(f"获取会话实例失败: {e}")
            return None
    
    async def perform_health_check(self):
        """执行健康检查"""
        try:
            current_time = time.time()
            unhealthy_instances = []
            
            for instance_id, instance in self.instances.items():
                try:
                    # 调用实例健康检查接口
                    health_config = CallConfig(timeout=10, retry_times=1)
                    
                    response = await call_service(
                        service_name="agent-service",
                        method=CallMethod.GET,
                        path=f"/api/v1/agents/{instance.agent_id}/instances/{instance_id}/health",
                        config=health_config
                    )
                    
                    if response.get("success"):
                        health_data = response.get("health", {})
                        instance.cpu_usage = health_data.get("cpu_usage", 0)
                        instance.memory_usage = health_data.get("memory_usage", 0)
                        instance.last_health_check = current_time
                        
                        # 重新计算健康分数
                        instance.calculate_health_score()
                        
                        # 如果之前不健康但现在恢复了
                        if instance.status == AgentStatus.UNHEALTHY and instance.health_score > 50:
                            instance.status = AgentStatus.IDLE
                    else:
                        # 健康检查失败
                        instance.health_score = max(0, instance.health_score - 10)
                        if instance.health_score < 20:
                            instance.status = AgentStatus.UNHEALTHY
                            unhealthy_instances.append(instance_id)
                
                except Exception as e:
                    logger.warning(f"实例 {instance_id} 健康检查失败: {e}")
                    instance.health_score = max(0, instance.health_score - 20)
                    if instance.health_score < 20:
                        instance.status = AgentStatus.UNHEALTHY
                        unhealthy_instances.append(instance_id)
                    
                    self.pool_metrics["failed_health_checks"] += 1
            
            # 清理不健康的实例
            for instance_id in unhealthy_instances:
                await self._cleanup_unhealthy_instance(instance_id)
            
            # 更新指标
            self._update_pool_metrics()
            
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
    
    async def _cleanup_unhealthy_instance(self, instance_id: str):
        """清理不健康的实例"""
        try:
            instance = self.instances.get(instance_id)
            if not instance:
                return
            
            # 如果实例长时间不健康，将其移除
            if instance.status == AgentStatus.UNHEALTHY:
                unhealthy_duration = time.time() - instance.last_health_check
                if unhealthy_duration > 300:  # 5分钟
                    await self._remove_instance(instance_id)
                    logger.info(f"移除长时间不健康的实例: {instance_id}")
        
        except Exception as e:
            logger.error(f"清理不健康实例失败: {e}")
    
    async def _remove_instance(self, instance_id: str):
        """移除实例"""
        try:
            instance = self.instances.get(instance_id)
            if not instance:
                return
            
            # 从内存中移除
            del self.instances[instance_id]
            if instance_id in self.agent_instances[instance.agent_id]:
                self.agent_instances[instance.agent_id].remove(instance_id)
            
            # 从Redis中移除
            instance_key = f"agent_pool:instance:{instance_id}"
            redis_manager.delete(instance_key)
            
            agent_instances_key = f"agent_pool:agent:{instance.agent_id}:instances"
            redis_manager.srem(agent_instances_key, instance_id)
            
            # 更新指标
            self.pool_metrics["total_instances"] -= 1
            
            logger.info(f"移除实例: {instance_id}")
            
        except Exception as e:
            logger.error(f"移除实例失败: {e}")
    
    def _update_pool_metrics(self):
        """更新池指标"""
        healthy_count = 0
        busy_count = 0
        idle_count = 0
        
        for instance in self.instances.values():
            if instance.status in [AgentStatus.IDLE, AgentStatus.BUSY]:
                healthy_count += 1
                
                if instance.status == AgentStatus.BUSY:
                    busy_count += 1
                else:
                    idle_count += 1
        
        self.pool_metrics["healthy_instances"] = healthy_count
        self.pool_metrics["busy_instances"] = busy_count
        self.pool_metrics["idle_instances"] = idle_count
    
    def _start_background_tasks(self):
        """启动后台任务"""
        async def health_check_loop():
            while True:
                try:
                    await asyncio.sleep(self.health_check_interval)
                    await self.perform_health_check()
                except Exception as e:
                    logger.error(f"健康检查循环错误: {e}")
        
        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(60)  # 每分钟清理一次
                    await self._cleanup_expired_instances()
                except Exception as e:
                    logger.error(f"清理循环错误: {e}")
        
        self._health_check_task = asyncio.create_task(health_check_loop())
        self._cleanup_task = asyncio.create_task(cleanup_loop())
    
    async def _cleanup_expired_instances(self):
        """清理过期实例"""
        try:
            current_time = time.time()
            expired_instances = []
            
            for instance_id, instance in self.instances.items():
                # 检查实例是否长时间无活动
                if current_time - instance.last_activity > self.instance_timeout:
                    if instance.active_sessions == 0:
                        expired_instances.append(instance_id)
            
            for instance_id in expired_instances:
                await self._remove_instance(instance_id)
                logger.info(f"清理过期实例: {instance_id}")
        
        except Exception as e:
            logger.error(f"清理过期实例失败: {e}")
    
    async def get_pool_status(self) -> Dict[str, Any]:
        """获取池状态"""
        try:
            agent_stats = {}
            for agent_id, instance_ids in self.agent_instances.items():
                instances_info = []
                for instance_id in instance_ids:
                    instance = self.instances.get(instance_id)
                    if instance:
                        instances_info.append(instance.to_dict())
                
                agent_stats[agent_id] = {
                    "total_instances": len(instance_ids),
                    "instances": instances_info
                }
            
            return {
                "pool_metrics": self.pool_metrics,
                "agent_statistics": agent_stats,
                "configuration": {
                    "load_balance_strategy": self.load_balance_strategy.value,
                    "min_instances_per_agent": self.min_instances_per_agent,
                    "max_instances_per_agent": self.max_instances_per_agent,
                    "health_check_interval": self.health_check_interval,
                    "instance_timeout": self.instance_timeout
                },
                "timestamp": datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"获取池状态失败: {e}")
            return {"error": str(e)}
    
    async def scale_agent_instances(self, agent_id: str, target_count: int) -> Dict[str, Any]:
        """伸缩智能体实例"""
        try:
            current_count = len(self.agent_instances.get(agent_id, []))
            
            if target_count > current_count:
                # 扩容
                created_instances = []
                for _ in range(target_count - current_count):
                    instance = await self._create_agent_instance(agent_id)
                    if instance:
                        created_instances.append(instance.instance_id)
                
                return {
                    "success": True,
                    "action": "scale_up",
                    "agent_id": agent_id,
                    "previous_count": current_count,
                    "target_count": target_count,
                    "created_instances": created_instances
                }
            
            elif target_count < current_count:
                # 缩容
                removed_instances = []
                instance_ids = self.agent_instances[agent_id].copy()
                
                # 优先移除空闲和不健康的实例
                instances_to_remove = []
                for instance_id in instance_ids:
                    instance = self.instances.get(instance_id)
                    if instance and instance.active_sessions == 0:
                        instances_to_remove.append(instance_id)
                
                # 按健康分数排序，优先移除分数低的
                instances_to_remove.sort(
                    key=lambda x: self.instances[x].health_score if x in self.instances else 0
                )
                
                remove_count = current_count - target_count
                for instance_id in instances_to_remove[:remove_count]:
                    await self._remove_instance(instance_id)
                    removed_instances.append(instance_id)
                
                return {
                    "success": True,
                    "action": "scale_down",
                    "agent_id": agent_id,
                    "previous_count": current_count,
                    "target_count": target_count,
                    "removed_instances": removed_instances
                }
            
            else:
                return {
                    "success": True,
                    "action": "no_change",
                    "agent_id": agent_id,
                    "current_count": current_count
                }
        
        except Exception as e:
            logger.error(f"伸缩智能体实例失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def cleanup(self):
        """清理资源"""
        try:
            # 取消后台任务
            if self._health_check_task:
                self._health_check_task.cancel()
            if self._cleanup_task:
                self._cleanup_task.cancel()
            
            # 清理所有实例
            for instance_id in list(self.instances.keys()):
                await self._remove_instance(instance_id)
            
            logger.info("智能体池管理器清理完成")
        
        except Exception as e:
            logger.error(f"清理智能体池管理器失败: {e}")


# 全局实例
_agent_pool_manager: Optional[AgentPoolManager] = None


def get_agent_pool_manager() -> AgentPoolManager:
    """获取智能体池管理器实例"""
    global _agent_pool_manager
    if _agent_pool_manager is None:
        _agent_pool_manager = AgentPoolManager()
    return _agent_pool_manager