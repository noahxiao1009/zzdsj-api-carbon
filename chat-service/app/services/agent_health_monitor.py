"""
智能体健康检查监控系统 - 全面监控智能体实例健康状态
"""

import asyncio
import logging
import time
import psutil
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from collections import deque, defaultdict
import statistics

from shared.service_client import call_service, CallMethod, CallConfig, RetryStrategy
from app.core.redis import redis_manager
from app.core.config import settings
from app.services.agent_pool_manager import AgentInstance, AgentStatus, get_agent_pool_manager
from app.services.agent_sync_manager import get_agent_sync_manager, SyncEvent, SyncEventType

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """健康状态"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class HealthCheckType(str, Enum):
    """健康检查类型"""
    BASIC = "basic"                 # 基础连通性检查
    PERFORMANCE = "performance"     # 性能指标检查
    RESOURCE = "resource"          # 资源使用检查
    FUNCTIONALITY = "functionality" # 功能性检查
    COMPREHENSIVE = "comprehensive" # 综合检查


@dataclass
class HealthMetric:
    """健康指标"""
    name: str
    value: float
    threshold_warning: float
    threshold_critical: float
    unit: str = ""
    description: str = ""
    
    def get_status(self) -> HealthStatus:
        """获取状态"""
        if self.value >= self.threshold_critical:
            return HealthStatus.CRITICAL
        elif self.value >= self.threshold_warning:
            return HealthStatus.WARNING
        else:
            return HealthStatus.HEALTHY
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "threshold_warning": self.threshold_warning,
            "threshold_critical": self.threshold_critical,
            "unit": self.unit,
            "description": self.description,
            "status": self.get_status().value
        }


@dataclass
class HealthCheckResult:
    """健康检查结果"""
    instance_id: str
    agent_id: str
    check_type: HealthCheckType
    status: HealthStatus
    metrics: List[HealthMetric] = field(default_factory=list)
    error_message: Optional[str] = None
    check_duration: float = 0.0
    timestamp: float = field(default_factory=time.time)
    
    def get_overall_score(self) -> float:
        """获取总体健康分数 (0-100)"""
        if self.status == HealthStatus.UNKNOWN:
            return 0.0
        
        if not self.metrics:
            return 100.0 if self.status == HealthStatus.HEALTHY else 0.0
        
        total_score = 0.0
        for metric in self.metrics:
            if metric.get_status() == HealthStatus.HEALTHY:
                total_score += 100.0
            elif metric.get_status() == HealthStatus.WARNING:
                total_score += 60.0
            else:  # CRITICAL
                total_score += 20.0
        
        return total_score / len(self.metrics)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "agent_id": self.agent_id,
            "check_type": self.check_type.value,
            "status": self.status.value,
            "overall_score": self.get_overall_score(),
            "metrics": [metric.to_dict() for metric in self.metrics],
            "error_message": self.error_message,
            "check_duration": self.check_duration,
            "timestamp": self.timestamp
        }


class AgentHealthMonitor:
    """智能体健康监控器"""
    
    def __init__(self):
        self.health_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.alert_rules: List[Dict[str, Any]] = []
        self.check_intervals = {
            HealthCheckType.BASIC: 30,           # 30秒
            HealthCheckType.PERFORMANCE: 60,     # 1分钟
            HealthCheckType.RESOURCE: 120,       # 2分钟
            HealthCheckType.FUNCTIONALITY: 300,  # 5分钟
            HealthCheckType.COMPREHENSIVE: 600   # 10分钟
        }
        
        # 健康检查配置
        self.health_thresholds = {
            "response_time": {"warning": 2000, "critical": 5000},  # 毫秒
            "error_rate": {"warning": 0.05, "critical": 0.1},      # 5% 和 10%
            "cpu_usage": {"warning": 70, "critical": 90},          # 百分比
            "memory_usage": {"warning": 80, "critical": 95},       # 百分比
            "active_sessions": {"warning": 0.8, "critical": 0.95}, # 相对于最大值
            "queue_length": {"warning": 50, "critical": 100}       # 队列长度
        }
        
        # 监控统计
        self.monitor_stats = {
            "total_checks": 0,
            "successful_checks": 0,
            "failed_checks": 0,
            "alerts_triggered": 0,
            "unhealthy_instances": 0
        }
        
        # 启动监控任务
        self._monitoring_tasks: Dict[HealthCheckType, Optional[asyncio.Task]] = {}
        self._start_monitoring_tasks()
    
    async def perform_health_check(
        self, 
        instance_id: str, 
        check_type: HealthCheckType = HealthCheckType.BASIC
    ) -> HealthCheckResult:
        """执行健康检查"""
        start_time = time.time()
        pool_manager = get_agent_pool_manager()
        instance = pool_manager.instances.get(instance_id)
        
        if not instance:
            return HealthCheckResult(
                instance_id=instance_id,
                agent_id="unknown",
                check_type=check_type,
                status=HealthStatus.UNKNOWN,
                error_message="实例不存在"
            )
        
        try:
            if check_type == HealthCheckType.BASIC:
                result = await self._perform_basic_check(instance)
            elif check_type == HealthCheckType.PERFORMANCE:
                result = await self._perform_performance_check(instance)
            elif check_type == HealthCheckType.RESOURCE:
                result = await self._perform_resource_check(instance)
            elif check_type == HealthCheckType.FUNCTIONALITY:
                result = await self._perform_functionality_check(instance)
            elif check_type == HealthCheckType.COMPREHENSIVE:
                result = await self._perform_comprehensive_check(instance)
            else:
                result = await self._perform_basic_check(instance)
            
            # 计算检查耗时
            result.check_duration = (time.time() - start_time) * 1000
            
            # 记录检查历史
            self.health_history[instance_id].append(result)
            
            # 更新统计
            self.monitor_stats["total_checks"] += 1
            if result.status != HealthStatus.UNKNOWN:
                self.monitor_stats["successful_checks"] += 1
            else:
                self.monitor_stats["failed_checks"] += 1
            
            # 检查是否需要触发告警
            await self._check_alert_rules(result)
            
            # 更新实例健康分数
            instance.health_score = result.get_overall_score()
            
            return result
            
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            self.monitor_stats["failed_checks"] += 1
            
            return HealthCheckResult(
                instance_id=instance_id,
                agent_id=instance.agent_id,
                check_type=check_type,
                status=HealthStatus.UNKNOWN,
                error_message=str(e),
                check_duration=(time.time() - start_time) * 1000
            )
    
    async def _perform_basic_check(self, instance: AgentInstance) -> HealthCheckResult:
        """执行基础健康检查"""
        metrics = []
        
        try:
            # 检查服务连通性
            connectivity_config = CallConfig(timeout=5, retry_times=1)
            
            response = await call_service(
                service_name="agent-service",
                method=CallMethod.GET,
                path=f"/api/v1/agents/{instance.agent_id}/instances/{instance.instance_id}/ping",
                config=connectivity_config
            )
            
            # 响应时间指标
            response_time = response.get("response_time", 0)
            metrics.append(HealthMetric(
                name="response_time",
                value=response_time,
                threshold_warning=self.health_thresholds["response_time"]["warning"],
                threshold_critical=self.health_thresholds["response_time"]["critical"],
                unit="ms",
                description="响应时间"
            ))
            
            # 连通性指标
            is_available = response.get("success", False)
            metrics.append(HealthMetric(
                name="connectivity",
                value=1.0 if is_available else 0.0,
                threshold_warning=0.5,
                threshold_critical=0.1,
                description="连通性"
            ))
            
            # 确定整体状态
            if not is_available:
                status = HealthStatus.CRITICAL
            elif response_time > self.health_thresholds["response_time"]["critical"]:
                status = HealthStatus.CRITICAL
            elif response_time > self.health_thresholds["response_time"]["warning"]:
                status = HealthStatus.WARNING
            else:
                status = HealthStatus.HEALTHY
            
            return HealthCheckResult(
                instance_id=instance.instance_id,
                agent_id=instance.agent_id,
                check_type=HealthCheckType.BASIC,
                status=status,
                metrics=metrics
            )
            
        except Exception as e:
            return HealthCheckResult(
                instance_id=instance.instance_id,
                agent_id=instance.agent_id,
                check_type=HealthCheckType.BASIC,
                status=HealthStatus.CRITICAL,
                error_message=str(e)
            )
    
    async def _perform_performance_check(self, instance: AgentInstance) -> HealthCheckResult:
        """执行性能检查"""
        metrics = []
        
        try:
            # 错误率指标
            error_rate = instance.error_rate
            metrics.append(HealthMetric(
                name="error_rate",
                value=error_rate,
                threshold_warning=self.health_thresholds["error_rate"]["warning"],
                threshold_critical=self.health_thresholds["error_rate"]["critical"],
                unit="%",
                description="错误率"
            ))
            
            # 平均响应时间指标
            avg_response_time = instance.average_response_time
            metrics.append(HealthMetric(
                name="avg_response_time",
                value=avg_response_time,
                threshold_warning=self.health_thresholds["response_time"]["warning"],
                threshold_critical=self.health_thresholds["response_time"]["critical"],
                unit="ms",
                description="平均响应时间"
            ))
            
            # 活跃会话指标
            session_ratio = instance.active_sessions / max(instance.max_concurrent_sessions, 1)
            metrics.append(HealthMetric(
                name="session_load",
                value=session_ratio,
                threshold_warning=self.health_thresholds["active_sessions"]["warning"],
                threshold_critical=self.health_thresholds["active_sessions"]["critical"],
                unit="ratio",
                description="会话负载比"
            ))
            
            # 确定状态
            critical_metrics = [m for m in metrics if m.get_status() == HealthStatus.CRITICAL]
            warning_metrics = [m for m in metrics if m.get_status() == HealthStatus.WARNING]
            
            if critical_metrics:
                status = HealthStatus.CRITICAL
            elif warning_metrics:
                status = HealthStatus.WARNING
            else:
                status = HealthStatus.HEALTHY
            
            return HealthCheckResult(
                instance_id=instance.instance_id,
                agent_id=instance.agent_id,
                check_type=HealthCheckType.PERFORMANCE,
                status=status,
                metrics=metrics
            )
            
        except Exception as e:
            return HealthCheckResult(
                instance_id=instance.instance_id,
                agent_id=instance.agent_id,
                check_type=HealthCheckType.PERFORMANCE,
                status=HealthStatus.UNKNOWN,
                error_message=str(e)
            )
    
    async def _perform_resource_check(self, instance: AgentInstance) -> HealthCheckResult:
        """执行资源使用检查"""
        metrics = []
        
        try:
            # CPU使用率
            cpu_usage = instance.cpu_usage
            metrics.append(HealthMetric(
                name="cpu_usage",
                value=cpu_usage,
                threshold_warning=self.health_thresholds["cpu_usage"]["warning"],
                threshold_critical=self.health_thresholds["cpu_usage"]["critical"],
                unit="%",
                description="CPU使用率"
            ))
            
            # 内存使用率
            memory_usage = instance.memory_usage
            metrics.append(HealthMetric(
                name="memory_usage",
                value=memory_usage,
                threshold_warning=self.health_thresholds["memory_usage"]["warning"],
                threshold_critical=self.health_thresholds["memory_usage"]["critical"],
                unit="%",
                description="内存使用率"
            ))
            
            # 如果能获取系统资源信息，添加更多指标
            try:
                # 磁盘使用率
                disk_usage = psutil.disk_usage('/').percent
                metrics.append(HealthMetric(
                    name="disk_usage",
                    value=disk_usage,
                    threshold_warning=80,
                    threshold_critical=95,
                    unit="%",
                    description="磁盘使用率"
                ))
                
                # 网络连接数
                net_connections = len(psutil.net_connections())
                metrics.append(HealthMetric(
                    name="network_connections",
                    value=net_connections,
                    threshold_warning=1000,
                    threshold_critical=2000,
                    description="网络连接数"
                ))
                
            except Exception:
                pass  # 系统资源信息获取失败，跳过
            
            # 确定状态
            critical_metrics = [m for m in metrics if m.get_status() == HealthStatus.CRITICAL]
            warning_metrics = [m for m in metrics if m.get_status() == HealthStatus.WARNING]
            
            if critical_metrics:
                status = HealthStatus.CRITICAL
            elif warning_metrics:
                status = HealthStatus.WARNING
            else:
                status = HealthStatus.HEALTHY
            
            return HealthCheckResult(
                instance_id=instance.instance_id,
                agent_id=instance.agent_id,
                check_type=HealthCheckType.RESOURCE,
                status=status,
                metrics=metrics
            )
            
        except Exception as e:
            return HealthCheckResult(
                instance_id=instance.instance_id,
                agent_id=instance.agent_id,
                check_type=HealthCheckType.RESOURCE,
                status=HealthStatus.UNKNOWN,
                error_message=str(e)
            )
    
    async def _perform_functionality_check(self, instance: AgentInstance) -> HealthCheckResult:
        """执行功能性检查"""
        metrics = []
        
        try:
            # 发送测试消息检查功能
            test_config = CallConfig(timeout=30, retry_times=1)
            
            test_message = {
                "message": "健康检查测试消息",
                "test_mode": True
            }
            
            start_time = time.time()
            response = await call_service(
                service_name="agent-service",
                method=CallMethod.POST,
                path=f"/api/v1/agents/{instance.agent_id}/instances/{instance.instance_id}/test",
                config=test_config,
                json=test_message
            )
            
            response_time = (time.time() - start_time) * 1000
            
            # 功能响应时间
            metrics.append(HealthMetric(
                name="function_response_time",
                value=response_time,
                threshold_warning=10000,  # 10秒
                threshold_critical=30000,  # 30秒
                unit="ms",
                description="功能响应时间"
            ))
            
            # 功能可用性
            is_functional = response.get("success", False)
            metrics.append(HealthMetric(
                name="functionality",
                value=1.0 if is_functional else 0.0,
                threshold_warning=0.5,
                threshold_critical=0.1,
                description="功能可用性"
            ))
            
            # 响应质量（如果有返回内容）
            response_content = response.get("response", "")
            response_quality = 1.0 if len(response_content) > 10 else 0.5
            metrics.append(HealthMetric(
                name="response_quality",
                value=response_quality,
                threshold_warning=0.7,
                threshold_critical=0.3,
                description="响应质量"
            ))
            
            # 确定状态
            if not is_functional:
                status = HealthStatus.CRITICAL
            elif response_time > 30000:
                status = HealthStatus.CRITICAL
            elif response_time > 10000 or response_quality < 0.7:
                status = HealthStatus.WARNING
            else:
                status = HealthStatus.HEALTHY
            
            return HealthCheckResult(
                instance_id=instance.instance_id,
                agent_id=instance.agent_id,
                check_type=HealthCheckType.FUNCTIONALITY,
                status=status,
                metrics=metrics
            )
            
        except Exception as e:
            return HealthCheckResult(
                instance_id=instance.instance_id,
                agent_id=instance.agent_id,
                check_type=HealthCheckType.FUNCTIONALITY,
                status=HealthStatus.CRITICAL,
                error_message=str(e)
            )
    
    async def _perform_comprehensive_check(self, instance: AgentInstance) -> HealthCheckResult:
        """执行综合检查"""
        try:
            # 执行所有类型的检查
            basic_result = await self._perform_basic_check(instance)
            performance_result = await self._perform_performance_check(instance)
            resource_result = await self._perform_resource_check(instance)
            functionality_result = await self._perform_functionality_check(instance)
            
            # 合并所有指标
            all_metrics = (
                basic_result.metrics + 
                performance_result.metrics + 
                resource_result.metrics + 
                functionality_result.metrics
            )
            
            # 确定综合状态
            results = [basic_result, performance_result, resource_result, functionality_result]
            critical_count = sum(1 for r in results if r.status == HealthStatus.CRITICAL)
            warning_count = sum(1 for r in results if r.status == HealthStatus.WARNING)
            
            if critical_count > 0:
                status = HealthStatus.CRITICAL
            elif warning_count > 1:  # 多个警告视为严重
                status = HealthStatus.CRITICAL
            elif warning_count > 0:
                status = HealthStatus.WARNING
            else:
                status = HealthStatus.HEALTHY
            
            return HealthCheckResult(
                instance_id=instance.instance_id,
                agent_id=instance.agent_id,
                check_type=HealthCheckType.COMPREHENSIVE,
                status=status,
                metrics=all_metrics
            )
            
        except Exception as e:
            return HealthCheckResult(
                instance_id=instance.instance_id,
                agent_id=instance.agent_id,
                check_type=HealthCheckType.COMPREHENSIVE,
                status=HealthStatus.UNKNOWN,
                error_message=str(e)
            )
    
    async def _check_alert_rules(self, result: HealthCheckResult):
        """检查告警规则"""
        try:
            for rule in self.alert_rules:
                if self._should_trigger_alert(result, rule):
                    await self._trigger_alert(result, rule)
        except Exception as e:
            logger.error(f"检查告警规则失败: {e}")
    
    def _should_trigger_alert(self, result: HealthCheckResult, rule: Dict[str, Any]) -> bool:
        """判断是否应该触发告警"""
        # 检查状态条件
        status_condition = rule.get("status_condition")
        if status_condition and result.status.value not in status_condition:
            return False
        
        # 检查指标条件
        metric_conditions = rule.get("metric_conditions", [])
        for condition in metric_conditions:
            metric_name = condition.get("metric_name")
            threshold = condition.get("threshold")
            operator = condition.get("operator", ">=")
            
            # 查找对应指标
            metric = next((m for m in result.metrics if m.name == metric_name), None)
            if not metric:
                continue
            
            # 检查条件
            if operator == ">=" and metric.value >= threshold:
                return True
            elif operator == ">" and metric.value > threshold:
                return True
            elif operator == "<=" and metric.value <= threshold:
                return True
            elif operator == "<" and metric.value < threshold:
                return True
            elif operator == "==" and metric.value == threshold:
                return True
        
        return False
    
    async def _trigger_alert(self, result: HealthCheckResult, rule: Dict[str, Any]):
        """触发告警"""
        try:
            alert_data = {
                "alert_type": rule.get("alert_type", "health_check"),
                "severity": rule.get("severity", "warning"),
                "instance_id": result.instance_id,
                "agent_id": result.agent_id,
                "status": result.status.value,
                "message": rule.get("message", f"实例 {result.instance_id} 健康检查异常"),
                "metrics": [m.to_dict() for m in result.metrics],
                "timestamp": time.time()
            }
            
            # 发送告警通知（可以集成到通知系统）
            logger.warning(f"健康检查告警: {alert_data}")
            
            # 更新统计
            self.monitor_stats["alerts_triggered"] += 1
            
            # 如果配置了同步管理器，发送状态变更事件
            sync_manager = get_agent_sync_manager()
            await sync_manager.add_sync_event(SyncEvent(
                event_type=SyncEventType.STATUS_CHANGED,
                agent_id=result.agent_id,
                instance_id=result.instance_id,
                data={"status": result.status.value, "alert": alert_data}
            ))
            
        except Exception as e:
            logger.error(f"触发告警失败: {e}")
    
    def _start_monitoring_tasks(self):
        """启动监控任务"""
        for check_type, interval in self.check_intervals.items():
            task = asyncio.create_task(self._monitoring_loop(check_type, interval))
            self._monitoring_tasks[check_type] = task
    
    async def _monitoring_loop(self, check_type: HealthCheckType, interval: int):
        """监控循环"""
        while True:
            try:
                await asyncio.sleep(interval)
                
                # 获取所有实例并执行健康检查
                pool_manager = get_agent_pool_manager()
                
                # 并发执行健康检查
                check_tasks = []
                for instance_id in pool_manager.instances.keys():
                    task = asyncio.create_task(
                        self.perform_health_check(instance_id, check_type)
                    )
                    check_tasks.append(task)
                
                if check_tasks:
                    results = await asyncio.gather(*check_tasks, return_exceptions=True)
                    
                    # 统计不健康的实例
                    unhealthy_count = 0
                    for result in results:
                        if isinstance(result, HealthCheckResult):
                            if result.status in [HealthStatus.CRITICAL, HealthStatus.WARNING]:
                                unhealthy_count += 1
                    
                    self.monitor_stats["unhealthy_instances"] = unhealthy_count
                
            except Exception as e:
                logger.error(f"监控循环错误 ({check_type.value}): {e}")
    
    def add_alert_rule(self, rule: Dict[str, Any]):
        """添加告警规则"""
        self.alert_rules.append(rule)
    
    def remove_alert_rule(self, rule_id: str):
        """移除告警规则"""
        self.alert_rules = [rule for rule in self.alert_rules if rule.get("id") != rule_id]
    
    def get_health_summary(self, instance_id: Optional[str] = None) -> Dict[str, Any]:
        """获取健康状态摘要"""
        if instance_id:
            # 获取特定实例的健康状态
            history = self.health_history.get(instance_id, deque())
            if not history:
                return {"instance_id": instance_id, "status": "no_data"}
            
            latest_result = history[-1]
            return {
                "instance_id": instance_id,
                "current_status": latest_result.status.value,
                "health_score": latest_result.get_overall_score(),
                "last_check": latest_result.timestamp,
                "check_count": len(history)
            }
        else:
            # 获取全部实例的健康状态摘要
            pool_manager = get_agent_pool_manager()
            summary = {
                "total_instances": len(pool_manager.instances),
                "healthy_instances": 0,
                "warning_instances": 0,
                "critical_instances": 0,
                "unknown_instances": 0,
                "monitor_stats": self.monitor_stats,
                "instances": {}
            }
            
            for instance_id in pool_manager.instances.keys():
                instance_summary = self.get_health_summary(instance_id)
                status = instance_summary.get("current_status", "unknown")
                
                if status == "healthy":
                    summary["healthy_instances"] += 1
                elif status == "warning":
                    summary["warning_instances"] += 1
                elif status == "critical":
                    summary["critical_instances"] += 1
                else:
                    summary["unknown_instances"] += 1
                
                summary["instances"][instance_id] = instance_summary
            
            return summary
    
    def get_health_trends(self, instance_id: str, hours: int = 24) -> Dict[str, Any]:
        """获取健康趋势"""
        history = self.health_history.get(instance_id, deque())
        if not history:
            return {"instance_id": instance_id, "message": "无历史数据"}
        
        # 过滤指定时间段的数据
        cutoff_time = time.time() - (hours * 3600)
        recent_history = [r for r in history if r.timestamp > cutoff_time]
        
        if not recent_history:
            return {"instance_id": instance_id, "message": "指定时间段内无数据"}
        
        # 计算趋势
        health_scores = [r.get_overall_score() for r in recent_history]
        avg_score = statistics.mean(health_scores) if health_scores else 0
        
        status_counts = defaultdict(int)
        for result in recent_history:
            status_counts[result.status.value] += 1
        
        return {
            "instance_id": instance_id,
            "time_period_hours": hours,
            "check_count": len(recent_history),
            "average_health_score": avg_score,
            "min_health_score": min(health_scores) if health_scores else 0,
            "max_health_score": max(health_scores) if health_scores else 0,
            "status_distribution": dict(status_counts),
            "trend": "improving" if len(health_scores) > 1 and health_scores[-1] > health_scores[0] else "stable"
        }
    
    async def cleanup(self):
        """清理资源"""
        try:
            # 取消所有监控任务
            for task in self._monitoring_tasks.values():
                if task:
                    task.cancel()
            
            logger.info("智能体健康监控器清理完成")
        except Exception as e:
            logger.error(f"清理智能体健康监控器失败: {e}")


# 全局实例
_agent_health_monitor: Optional[AgentHealthMonitor] = None


def get_agent_health_monitor() -> AgentHealthMonitor:
    """获取智能体健康监控器实例"""
    global _agent_health_monitor
    if _agent_health_monitor is None:
        _agent_health_monitor = AgentHealthMonitor()
    return _agent_health_monitor