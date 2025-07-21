"""
资源优化器 - 智能体实例资源自动优化和伸缩
"""

import asyncio
import logging
import time
import statistics
from typing import Dict, Any, Optional, List, Tuple, Set
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from collections import deque, defaultdict
import json

from shared.service_client import call_service, CallMethod, CallConfig, RetryStrategy
from app.core.redis import redis_manager
from app.core.config import settings
from app.services.agent_pool_manager import AgentInstance, AgentStatus, get_agent_pool_manager
from app.services.agent_health_monitor import get_agent_health_monitor, HealthStatus
from app.services.agent_sync_manager import get_agent_sync_manager, SyncEvent, SyncEventType

logger = logging.getLogger(__name__)


class ScalingTrigger(str, Enum):
    """伸缩触发器类型"""
    LOAD_BASED = "load_based"           # 基于负载
    RESPONSE_TIME = "response_time"     # 基于响应时间
    ERROR_RATE = "error_rate"          # 基于错误率
    QUEUE_LENGTH = "queue_length"      # 基于队列长度
    SCHEDULED = "scheduled"            # 定时触发
    MANUAL = "manual"                  # 手动触发


class ScalingAction(str, Enum):
    """伸缩操作类型"""
    SCALE_UP = "scale_up"      # 扩容
    SCALE_DOWN = "scale_down"  # 缩容
    NO_ACTION = "no_action"    # 无操作


@dataclass
class ScalingRule:
    """伸缩规则"""
    rule_id: str
    agent_id: str
    trigger: ScalingTrigger
    metric_name: str
    threshold_up: float        # 扩容阈值
    threshold_down: float      # 缩容阈值
    min_instances: int = 1
    max_instances: int = 10
    cooldown_period: int = 300  # 冷却期(秒)
    enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "agent_id": self.agent_id,
            "trigger": self.trigger.value,
            "metric_name": self.metric_name,
            "threshold_up": self.threshold_up,
            "threshold_down": self.threshold_down,
            "min_instances": self.min_instances,
            "max_instances": self.max_instances,
            "cooldown_period": self.cooldown_period,
            "enabled": self.enabled
        }


@dataclass
class ScalingEvent:
    """伸缩事件"""
    event_id: str
    agent_id: str
    action: ScalingAction
    trigger: ScalingTrigger
    rule_id: Optional[str] = None
    current_instances: int = 0
    target_instances: int = 0
    metric_value: float = 0.0
    threshold: float = 0.0
    timestamp: float = field(default_factory=time.time)
    success: bool = False
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "agent_id": self.agent_id,
            "action": self.action.value,
            "trigger": self.trigger.value,
            "rule_id": self.rule_id,
            "current_instances": self.current_instances,
            "target_instances": self.target_instances,
            "metric_value": self.metric_value,
            "threshold": self.threshold,
            "timestamp": self.timestamp,
            "success": self.success,
            "error_message": self.error_message
        }


@dataclass
class ResourceMetrics:
    """资源指标"""
    agent_id: str
    timestamp: float = field(default_factory=time.time)
    
    # 负载指标
    active_sessions: int = 0
    total_capacity: int = 0
    load_ratio: float = 0.0
    
    # 性能指标
    average_response_time: float = 0.0
    error_rate: float = 0.0
    throughput: float = 0.0
    
    # 资源指标
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    
    # 健康指标
    healthy_instances: int = 0
    total_instances: int = 0
    health_ratio: float = 0.0
    
    # 队列指标
    pending_requests: int = 0
    queue_wait_time: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "timestamp": self.timestamp,
            "load": {
                "active_sessions": self.active_sessions,
                "total_capacity": self.total_capacity,
                "load_ratio": self.load_ratio
            },
            "performance": {
                "average_response_time": self.average_response_time,
                "error_rate": self.error_rate,
                "throughput": self.throughput
            },
            "resources": {
                "cpu_usage": self.cpu_usage,
                "memory_usage": self.memory_usage
            },
            "health": {
                "healthy_instances": self.healthy_instances,
                "total_instances": self.total_instances,
                "health_ratio": self.health_ratio
            },
            "queue": {
                "pending_requests": self.pending_requests,
                "queue_wait_time": self.queue_wait_time
            }
        }


class ResourceOptimizer:
    """资源优化器"""
    
    def __init__(self):
        self.scaling_rules: Dict[str, ScalingRule] = {}
        self.scaling_history: deque = deque(maxlen=1000)
        self.metrics_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.last_scaling_time: Dict[str, float] = {}
        
        # 优化配置
        self.optimization_interval = 60  # 优化检查间隔(秒)
        self.metrics_window = 300       # 指标窗口期(秒)
        self.min_data_points = 3        # 最少数据点
        
        # 优化统计
        self.optimizer_stats = {
            "total_optimizations": 0,
            "successful_scale_ups": 0,
            "successful_scale_downs": 0,
            "failed_optimizations": 0,
            "resource_savings": 0.0,
            "performance_improvements": 0.0
        }
        
        # 启动优化任务
        self._optimization_task = None
        self._metrics_collection_task = None
        self._start_optimization_tasks()
    
    async def collect_agent_metrics(self, agent_id: str) -> Optional[ResourceMetrics]:
        """收集智能体资源指标"""
        try:
            pool_manager = get_agent_pool_manager()
            health_monitor = get_agent_health_monitor()
            
            # 获取智能体实例
            instance_ids = pool_manager.agent_instances.get(agent_id, [])
            if not instance_ids:
                return None
            
            instances = [pool_manager.instances.get(iid) for iid in instance_ids]
            instances = [inst for inst in instances if inst is not None]
            
            if not instances:
                return None
            
            # 计算聚合指标
            metrics = ResourceMetrics(agent_id=agent_id)
            
            # 负载指标
            metrics.active_sessions = sum(inst.active_sessions for inst in instances)
            metrics.total_capacity = sum(inst.max_concurrent_sessions for inst in instances)
            metrics.load_ratio = metrics.active_sessions / max(metrics.total_capacity, 1)
            
            # 性能指标
            response_times = [inst.average_response_time for inst in instances if inst.average_response_time > 0]
            if response_times:
                metrics.average_response_time = statistics.mean(response_times)
            
            error_rates = [inst.error_rate for inst in instances]
            if error_rates:
                metrics.error_rate = statistics.mean(error_rates)
            
            # 计算吞吐量 (每秒成功请求数)
            total_successful = sum(inst.successful_requests for inst in instances)
            total_time = sum(time.time() - inst.created_at for inst in instances)
            if total_time > 0:
                metrics.throughput = total_successful / total_time
            
            # 资源指标
            cpu_usages = [inst.cpu_usage for inst in instances if inst.cpu_usage > 0]
            if cpu_usages:
                metrics.cpu_usage = statistics.mean(cpu_usages)
            
            memory_usages = [inst.memory_usage for inst in instances if inst.memory_usage > 0]
            if memory_usages:
                metrics.memory_usage = statistics.mean(memory_usages)
            
            # 健康指标
            healthy_count = sum(1 for inst in instances if inst.status in [AgentStatus.IDLE, AgentStatus.BUSY])
            metrics.healthy_instances = healthy_count
            metrics.total_instances = len(instances)
            metrics.health_ratio = healthy_count / max(len(instances), 1)
            
            # 队列指标（从Redis获取）
            try:
                queue_key = f"agent_queue:{agent_id}"
                metrics.pending_requests = redis_manager.llen(queue_key) or 0
                
                # 计算平均等待时间
                wait_times_key = f"agent_wait_times:{agent_id}"
                wait_times_str = redis_manager.get(wait_times_key)
                if wait_times_str:
                    wait_times = json.loads(wait_times_str.decode() if isinstance(wait_times_str, bytes) else wait_times_str)
                    if wait_times:
                        metrics.queue_wait_time = statistics.mean(wait_times)
            except Exception:
                pass  # 队列指标获取失败，使用默认值
            
            return metrics
            
        except Exception as e:
            logger.error(f"收集智能体指标失败: {e}")
            return None
    
    async def add_scaling_rule(self, rule: ScalingRule) -> bool:
        """添加伸缩规则"""
        try:
            # 验证规则
            if rule.threshold_up <= rule.threshold_down:
                logger.error("扩容阈值必须大于缩容阈值")
                return False
            
            if rule.min_instances >= rule.max_instances:
                logger.error("最小实例数必须小于最大实例数")
                return False
            
            # 添加规则
            self.scaling_rules[rule.rule_id] = rule
            
            # 持久化规则
            rule_key = f"scaling_rule:{rule.rule_id}"
            redis_manager.set_json(rule_key, rule.to_dict(), ex=86400)
            
            # 维护智能体规则索引
            agent_rules_key = f"agent_scaling_rules:{rule.agent_id}"
            redis_manager.sadd(agent_rules_key, rule.rule_id)
            redis_manager.expire(agent_rules_key, 86400)
            
            logger.info(f"添加伸缩规则: {rule.rule_id}")
            return True
            
        except Exception as e:
            logger.error(f"添加伸缩规则失败: {e}")
            return False
    
    async def remove_scaling_rule(self, rule_id: str) -> bool:
        """移除伸缩规则"""
        try:
            rule = self.scaling_rules.get(rule_id)
            if rule:
                del self.scaling_rules[rule_id]
                
                # 从Redis中移除
                rule_key = f"scaling_rule:{rule_id}"
                redis_manager.delete(rule_key)
                
                agent_rules_key = f"agent_scaling_rules:{rule.agent_id}"
                redis_manager.srem(agent_rules_key, rule_id)
                
                logger.info(f"移除伸缩规则: {rule_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"移除伸缩规则失败: {e}")
            return False
    
    async def evaluate_scaling_decision(
        self, 
        agent_id: str, 
        metrics: ResourceMetrics
    ) -> Optional[Tuple[ScalingAction, ScalingRule, float]]:
        """评估伸缩决策"""
        try:
            # 获取该智能体的伸缩规则
            agent_rules = [rule for rule in self.scaling_rules.values() 
                          if rule.agent_id == agent_id and rule.enabled]
            
            if not agent_rules:
                return None
            
            # 检查冷却期
            last_scaling = self.last_scaling_time.get(agent_id, 0)
            min_cooldown = min(rule.cooldown_period for rule in agent_rules)
            if time.time() - last_scaling < min_cooldown:
                return None
            
            # 评估每个规则
            for rule in agent_rules:
                metric_value = self._get_metric_value(metrics, rule.metric_name)
                if metric_value is None:
                    continue
                
                # 检查是否需要扩容
                if metric_value >= rule.threshold_up:
                    current_instances = metrics.total_instances
                    if current_instances < rule.max_instances:
                        return (ScalingAction.SCALE_UP, rule, metric_value)
                
                # 检查是否需要缩容
                elif metric_value <= rule.threshold_down:
                    current_instances = metrics.total_instances
                    if current_instances > rule.min_instances:
                        return (ScalingAction.SCALE_DOWN, rule, metric_value)
            
            return None
            
        except Exception as e:
            logger.error(f"评估伸缩决策失败: {e}")
            return None
    
    def _get_metric_value(self, metrics: ResourceMetrics, metric_name: str) -> Optional[float]:
        """获取指标值"""
        try:
            if metric_name == "load_ratio":
                return metrics.load_ratio
            elif metric_name == "average_response_time":
                return metrics.average_response_time
            elif metric_name == "error_rate":
                return metrics.error_rate
            elif metric_name == "cpu_usage":
                return metrics.cpu_usage
            elif metric_name == "memory_usage":
                return metrics.memory_usage
            elif metric_name == "health_ratio":
                return 1.0 - metrics.health_ratio  # 转换为不健康比例
            elif metric_name == "queue_length":
                return float(metrics.pending_requests)
            elif metric_name == "queue_wait_time":
                return metrics.queue_wait_time
            else:
                return None
        except Exception:
            return None
    
    async def execute_scaling_action(
        self, 
        agent_id: str, 
        action: ScalingAction, 
        rule: ScalingRule, 
        metric_value: float
    ) -> ScalingEvent:
        """执行伸缩操作"""
        event_id = f"scaling_{agent_id}_{int(time.time())}"
        pool_manager = get_agent_pool_manager()
        
        current_instances = len(pool_manager.agent_instances.get(agent_id, []))
        
        event = ScalingEvent(
            event_id=event_id,
            agent_id=agent_id,
            action=action,
            trigger=rule.trigger,
            rule_id=rule.rule_id,
            current_instances=current_instances,
            metric_value=metric_value,
            threshold=rule.threshold_up if action == ScalingAction.SCALE_UP else rule.threshold_down
        )
        
        try:
            if action == ScalingAction.SCALE_UP:
                # 计算目标实例数
                target_instances = min(current_instances + 1, rule.max_instances)
                event.target_instances = target_instances
                
                # 执行扩容
                result = await pool_manager.scale_agent_instances(agent_id, target_instances)
                
                if result.get("success"):
                    event.success = True
                    self.optimizer_stats["successful_scale_ups"] += 1
                    logger.info(f"扩容成功: {agent_id} {current_instances} -> {target_instances}")
                else:
                    event.error_message = result.get("error", "扩容失败")
                    self.optimizer_stats["failed_optimizations"] += 1
            
            elif action == ScalingAction.SCALE_DOWN:
                # 计算目标实例数
                target_instances = max(current_instances - 1, rule.min_instances)
                event.target_instances = target_instances
                
                # 执行缩容
                result = await pool_manager.scale_agent_instances(agent_id, target_instances)
                
                if result.get("success"):
                    event.success = True
                    self.optimizer_stats["successful_scale_downs"] += 1
                    # 计算资源节省
                    self.optimizer_stats["resource_savings"] += 1.0
                    logger.info(f"缩容成功: {agent_id} {current_instances} -> {target_instances}")
                else:
                    event.error_message = result.get("error", "缩容失败")
                    self.optimizer_stats["failed_optimizations"] += 1
            
            # 更新最后伸缩时间
            self.last_scaling_time[agent_id] = time.time()
            
            # 记录事件
            self.scaling_history.append(event)
            
            # 触发同步事件
            if event.success:
                sync_manager = get_agent_sync_manager()
                await sync_manager.add_sync_event(SyncEvent(
                    event_type=SyncEventType.INSTANCE_UPDATED,
                    agent_id=agent_id,
                    data={"scaling_event": event.to_dict()}
                ))
            
            return event
            
        except Exception as e:
            event.error_message = str(e)
            self.optimizer_stats["failed_optimizations"] += 1
            logger.error(f"执行伸缩操作失败: {e}")
            return event
    
    async def optimize_agent_resources(self, agent_id: str) -> Optional[ScalingEvent]:
        """优化智能体资源"""
        try:
            # 收集指标
            metrics = await self.collect_agent_metrics(agent_id)
            if not metrics:
                return None
            
            # 记录指标历史
            self.metrics_history[agent_id].append(metrics)
            
            # 确保有足够的历史数据
            if len(self.metrics_history[agent_id]) < self.min_data_points:
                return None
            
            # 使用历史数据平滑指标
            smoothed_metrics = self._smooth_metrics(agent_id)
            if not smoothed_metrics:
                return None
            
            # 评估伸缩决策
            decision = await self.evaluate_scaling_decision(agent_id, smoothed_metrics)
            if not decision:
                return None
            
            action, rule, metric_value = decision
            
            # 执行伸缩操作
            event = await self.execute_scaling_action(agent_id, action, rule, metric_value)
            
            self.optimizer_stats["total_optimizations"] += 1
            return event
            
        except Exception as e:
            logger.error(f"优化智能体资源失败: {e}")
            return None
    
    def _smooth_metrics(self, agent_id: str) -> Optional[ResourceMetrics]:
        """平滑历史指标"""
        try:
            history = self.metrics_history[agent_id]
            if len(history) < 2:
                return history[-1] if history else None
            
            # 使用最近几个数据点的平均值
            recent_metrics = list(history)[-3:]  # 最近3个数据点
            
            smoothed = ResourceMetrics(agent_id=agent_id)
            
            # 计算平均值
            smoothed.active_sessions = int(statistics.mean(m.active_sessions for m in recent_metrics))
            smoothed.total_capacity = int(statistics.mean(m.total_capacity for m in recent_metrics))
            smoothed.load_ratio = statistics.mean(m.load_ratio for m in recent_metrics)
            smoothed.average_response_time = statistics.mean(m.average_response_time for m in recent_metrics)
            smoothed.error_rate = statistics.mean(m.error_rate for m in recent_metrics)
            smoothed.throughput = statistics.mean(m.throughput for m in recent_metrics)
            smoothed.cpu_usage = statistics.mean(m.cpu_usage for m in recent_metrics)
            smoothed.memory_usage = statistics.mean(m.memory_usage for m in recent_metrics)
            smoothed.healthy_instances = int(statistics.mean(m.healthy_instances for m in recent_metrics))
            smoothed.total_instances = int(statistics.mean(m.total_instances for m in recent_metrics))
            smoothed.health_ratio = statistics.mean(m.health_ratio for m in recent_metrics)
            smoothed.pending_requests = int(statistics.mean(m.pending_requests for m in recent_metrics))
            smoothed.queue_wait_time = statistics.mean(m.queue_wait_time for m in recent_metrics)
            
            return smoothed
            
        except Exception as e:
            logger.error(f"平滑指标失败: {e}")
            return None
    
    def _start_optimization_tasks(self):
        """启动优化任务"""
        async def optimization_loop():
            """优化循环"""
            while True:
                try:
                    await asyncio.sleep(self.optimization_interval)
                    
                    # 获取所有智能体
                    pool_manager = get_agent_pool_manager()
                    agent_ids = list(pool_manager.agent_instances.keys())
                    
                    # 并发优化所有智能体
                    optimization_tasks = [
                        self.optimize_agent_resources(agent_id)
                        for agent_id in agent_ids
                    ]
                    
                    if optimization_tasks:
                        results = await asyncio.gather(*optimization_tasks, return_exceptions=True)
                        
                        # 统计结果
                        successful_optimizations = sum(1 for r in results if isinstance(r, ScalingEvent) and r.success)
                        if successful_optimizations > 0:
                            logger.info(f"优化周期完成: {successful_optimizations}/{len(agent_ids)} 个智能体完成优化")
                
                except Exception as e:
                    logger.error(f"优化循环错误: {e}")
        
        async def metrics_collection_loop():
            """指标收集循环"""
            while True:
                try:
                    await asyncio.sleep(30)  # 每30秒收集一次指标
                    
                    pool_manager = get_agent_pool_manager()
                    agent_ids = list(pool_manager.agent_instances.keys())
                    
                    # 并发收集所有智能体指标
                    for agent_id in agent_ids:
                        metrics = await self.collect_agent_metrics(agent_id)
                        if metrics:
                            self.metrics_history[agent_id].append(metrics)
                
                except Exception as e:
                    logger.error(f"指标收集循环错误: {e}")
        
        self._optimization_task = asyncio.create_task(optimization_loop())
        self._metrics_collection_task = asyncio.create_task(metrics_collection_loop())
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """获取优化统计"""
        return {
            "optimizer_stats": self.optimizer_stats,
            "active_rules": len(self.scaling_rules),
            "scaling_events": len(self.scaling_history),
            "recent_events": [event.to_dict() for event in list(self.scaling_history)[-10:]],
            "configuration": {
                "optimization_interval": self.optimization_interval,
                "metrics_window": self.metrics_window,
                "min_data_points": self.min_data_points
            },
            "timestamp": time.time()
        }
    
    def get_agent_metrics_history(self, agent_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """获取智能体指标历史"""
        history = self.metrics_history.get(agent_id, deque())
        return [metrics.to_dict() for metrics in list(history)[-limit:]]
    
    async def cleanup(self):
        """清理资源"""
        try:
            # 取消优化任务
            if self._optimization_task:
                self._optimization_task.cancel()
            if self._metrics_collection_task:
                self._metrics_collection_task.cancel()
            
            logger.info("资源优化器清理完成")
        except Exception as e:
            logger.error(f"清理资源优化器失败: {e}")


# 全局实例
_resource_optimizer: Optional[ResourceOptimizer] = None


def get_resource_optimizer() -> ResourceOptimizer:
    """获取资源优化器实例"""
    global _resource_optimizer
    if _resource_optimizer is None:
        _resource_optimizer = ResourceOptimizer()
    return _resource_optimizer