"""
智能体健康监控系统测试用例
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch
from collections import deque

from app.services.agent_health_monitor import (
    AgentHealthMonitor, HealthStatus, HealthCheckType, HealthMetric, 
    HealthCheckResult, get_agent_health_monitor
)
from app.services.agent_pool_manager import AgentInstance, AgentStatus


class TestHealthMetric:
    """健康指标测试"""
    
    def test_health_metric_creation(self):
        """测试健康指标创建"""
        metric = HealthMetric(
            name="response_time",
            value=1500.0,
            threshold_warning=2000.0,
            threshold_critical=5000.0,
            unit="ms",
            description="平均响应时间"
        )
        
        assert metric.name == "response_time"
        assert metric.value == 1500.0
        assert metric.threshold_warning == 2000.0
        assert metric.threshold_critical == 5000.0
        assert metric.unit == "ms"
        assert metric.description == "平均响应时间"
    
    def test_health_metric_status(self):
        """测试健康指标状态判断"""
        metric = HealthMetric("cpu_usage", 0, 70, 90)
        
        # 健康状态
        metric.value = 50.0
        assert metric.get_status() == HealthStatus.HEALTHY
        
        # 警告状态
        metric.value = 80.0
        assert metric.get_status() == HealthStatus.WARNING
        
        # 严重状态
        metric.value = 95.0
        assert metric.get_status() == HealthStatus.CRITICAL
    
    def test_health_metric_to_dict(self):
        """测试健康指标序列化"""
        metric = HealthMetric("memory_usage", 75.0, 80, 95, "MB", "内存使用量")
        data = metric.to_dict()
        
        assert data["name"] == "memory_usage"
        assert data["value"] == 75.0
        assert data["status"] == HealthStatus.HEALTHY.value
        assert data["unit"] == "MB"
        assert data["description"] == "内存使用量"


class TestHealthCheckResult:
    """健康检查结果测试"""
    
    def test_health_check_result_creation(self):
        """测试健康检查结果创建"""
        result = HealthCheckResult(
            instance_id="test-instance-001",
            agent_id="test-agent",
            check_type=HealthCheckType.BASIC,
            status=HealthStatus.HEALTHY
        )
        
        assert result.instance_id == "test-instance-001"
        assert result.agent_id == "test-agent"
        assert result.check_type == HealthCheckType.BASIC
        assert result.status == HealthStatus.HEALTHY
        assert result.metrics == []
        assert result.error_message is None
    
    def test_health_check_result_score_calculation(self):
        """测试健康分数计算"""
        result = HealthCheckResult(
            instance_id="test-instance-001",
            agent_id="test-agent",
            check_type=HealthCheckType.COMPREHENSIVE,
            status=HealthStatus.HEALTHY
        )
        
        # 无指标时的分数
        assert result.get_overall_score() == 100.0
        
        # 添加混合状态的指标
        result.metrics = [
            HealthMetric("cpu", 50, 70, 90),      # HEALTHY -> 100分
            HealthMetric("memory", 80, 70, 90),   # WARNING -> 60分
            HealthMetric("disk", 95, 70, 90)      # CRITICAL -> 20分
        ]
        
        expected_score = (100.0 + 60.0 + 20.0) / 3
        assert abs(result.get_overall_score() - expected_score) < 0.01
    
    def test_health_check_result_to_dict(self):
        """测试健康检查结果序列化"""
        result = HealthCheckResult(
            instance_id="test-instance-001",
            agent_id="test-agent",
            check_type=HealthCheckType.PERFORMANCE,
            status=HealthStatus.WARNING,
            check_duration=250.5
        )
        
        result.metrics = [
            HealthMetric("response_time", 2500, 2000, 5000)
        ]
        
        data = result.to_dict()
        
        assert data["instance_id"] == "test-instance-001"
        assert data["agent_id"] == "test-agent"
        assert data["check_type"] == HealthCheckType.PERFORMANCE.value
        assert data["status"] == HealthStatus.WARNING.value
        assert data["check_duration"] == 250.5
        assert len(data["metrics"]) == 1
        assert "overall_score" in data


class TestAgentHealthMonitor:
    """智能体健康监控器测试"""
    
    def setup_method(self):
        """测试前置设置"""
        self.health_monitor = AgentHealthMonitor()
        # 停止后台任务避免干扰测试
        if self.health_monitor._monitoring_tasks:
            for task in self.health_monitor._monitoring_tasks.values():
                if task:
                    task.cancel()
    
    def test_health_monitor_initialization(self):
        """测试健康监控器初始化"""
        assert isinstance(self.health_monitor.health_history, dict)
        assert isinstance(self.health_monitor.alert_rules, list)
        assert isinstance(self.health_monitor.check_intervals, dict)
        assert isinstance(self.health_monitor.health_thresholds, dict)
        assert isinstance(self.health_monitor.monitor_stats, dict)
        
        # 检查默认配置
        assert self.health_monitor.check_intervals[HealthCheckType.BASIC] == 30
        assert self.health_monitor.health_thresholds["response_time"]["warning"] == 2000
        assert self.health_monitor.monitor_stats["total_checks"] == 0
    
    @pytest.mark.asyncio
    async def test_perform_basic_health_check(self):
        """测试基础健康检查"""
        # 创建测试实例
        instance = AgentInstance(
            instance_id="test-instance-001",
            agent_id="test-agent",
            service_url="http://test-service:8081"
        )
        
        # Mock get_agent_pool_manager
        with patch('app.services.agent_health_monitor.get_agent_pool_manager') as mock_pool:
            mock_pool.return_value.instances = {"test-instance-001": instance}
            
            # Mock call_service
            with patch('app.services.agent_health_monitor.call_service') as mock_call:
                mock_call.return_value = {
                    "success": True,
                    "response_time": 1200.0
                }
                
                result = await self.health_monitor.perform_health_check(
                    "test-instance-001", 
                    HealthCheckType.BASIC
                )
                
                assert result.instance_id == "test-instance-001"
                assert result.agent_id == "test-agent"
                assert result.check_type == HealthCheckType.BASIC
                assert result.status == HealthStatus.HEALTHY
                assert len(result.metrics) == 2  # response_time 和 connectivity
                assert result.error_message is None
    
    @pytest.mark.asyncio
    async def test_perform_health_check_instance_not_found(self):
        """测试健康检查 - 实例不存在"""
        with patch('app.services.agent_health_monitor.get_agent_pool_manager') as mock_pool:
            mock_pool.return_value.instances = {}
            
            result = await self.health_monitor.perform_health_check(
                "nonexistent-instance", 
                HealthCheckType.BASIC
            )
            
            assert result.instance_id == "nonexistent-instance"
            assert result.agent_id == "unknown"
            assert result.status == HealthStatus.UNKNOWN
            assert result.error_message == "实例不存在"
    
    @pytest.mark.asyncio
    async def test_perform_performance_health_check(self):
        """测试性能健康检查"""
        # 创建测试实例
        instance = AgentInstance(
            instance_id="test-instance-001",
            agent_id="test-agent",
            service_url="http://test-service:8081",
            max_concurrent_sessions=100
        )
        instance.error_rate = 0.02
        instance.average_response_time = 1500.0
        instance.active_sessions = 30
        
        with patch('app.services.agent_health_monitor.get_agent_pool_manager') as mock_pool:
            mock_pool.return_value.instances = {"test-instance-001": instance}
            
            result = await self.health_monitor._perform_performance_check(instance)
            
            assert result.check_type == HealthCheckType.PERFORMANCE
            assert len(result.metrics) == 3  # error_rate, avg_response_time, session_load
            
            # 检查指标值
            error_metric = next(m for m in result.metrics if m.name == "error_rate")
            assert error_metric.value == 0.02
            
            response_metric = next(m for m in result.metrics if m.name == "avg_response_time")
            assert response_metric.value == 1500.0
            
            session_metric = next(m for m in result.metrics if m.name == "session_load")
            assert session_metric.value == 0.3  # 30/100
    
    @pytest.mark.asyncio
    async def test_perform_resource_health_check(self):
        """测试资源健康检查"""
        instance = AgentInstance(
            instance_id="test-instance-001",
            agent_id="test-agent",
            service_url="http://test-service:8081"
        )
        instance.cpu_usage = 65.0
        instance.memory_usage = 75.0
        
        with patch('app.services.agent_health_monitor.get_agent_pool_manager') as mock_pool:
            mock_pool.return_value.instances = {"test-instance-001": instance}
            
            with patch('psutil.disk_usage') as mock_disk:
                with patch('psutil.net_connections') as mock_net:
                    mock_disk.return_value.percent = 80.0
                    mock_net.return_value = ['conn1', 'conn2', 'conn3']  # 3个连接
                    
                    result = await self.health_monitor._perform_resource_check(instance)
                    
                    assert result.check_type == HealthCheckType.RESOURCE
                    assert len(result.metrics) >= 2  # 至少cpu和memory
                    
                    cpu_metric = next(m for m in result.metrics if m.name == "cpu_usage")
                    assert cpu_metric.value == 65.0
                    
                    memory_metric = next(m for m in result.metrics if m.name == "memory_usage")
                    assert memory_metric.value == 75.0
    
    @pytest.mark.asyncio
    async def test_perform_functionality_health_check(self):
        """测试功能性健康检查"""
        instance = AgentInstance(
            instance_id="test-instance-001",
            agent_id="test-agent",
            service_url="http://test-service:8081"
        )
        
        with patch('app.services.agent_health_monitor.get_agent_pool_manager') as mock_pool:
            mock_pool.return_value.instances = {"test-instance-001": instance}
            
            with patch('app.services.agent_health_monitor.call_service') as mock_call:
                mock_call.return_value = {
                    "success": True,
                    "response": "这是一个测试响应，用于验证功能正常"
                }
                
                result = await self.health_monitor._perform_functionality_check(instance)
                
                assert result.check_type == HealthCheckType.FUNCTIONALITY
                assert len(result.metrics) == 3  # function_response_time, functionality, response_quality
                
                functionality_metric = next(m for m in result.metrics if m.name == "functionality")
                assert functionality_metric.value == 1.0
                
                quality_metric = next(m for m in result.metrics if m.name == "response_quality")
                assert quality_metric.value == 1.0  # 响应内容长度 > 10
    
    @pytest.mark.asyncio
    async def test_perform_comprehensive_health_check(self):
        """测试综合健康检查"""
        instance = AgentInstance(
            instance_id="test-instance-001",
            agent_id="test-agent",
            service_url="http://test-service:8081"
        )
        
        with patch('app.services.agent_health_monitor.get_agent_pool_manager') as mock_pool:
            mock_pool.return_value.instances = {"test-instance-001": instance}
            
            with patch.object(self.health_monitor, '_perform_basic_check') as mock_basic:
                with patch.object(self.health_monitor, '_perform_performance_check') as mock_perf:
                    with patch.object(self.health_monitor, '_perform_resource_check') as mock_resource:
                        with patch.object(self.health_monitor, '_perform_functionality_check') as mock_func:
                            # Mock各种检查的结果
                            mock_basic.return_value = HealthCheckResult(
                                "test-instance-001", "test-agent", 
                                HealthCheckType.BASIC, HealthStatus.HEALTHY
                            )
                            mock_perf.return_value = HealthCheckResult(
                                "test-instance-001", "test-agent", 
                                HealthCheckType.PERFORMANCE, HealthStatus.WARNING
                            )
                            mock_resource.return_value = HealthCheckResult(
                                "test-instance-001", "test-agent", 
                                HealthCheckType.RESOURCE, HealthStatus.HEALTHY
                            )
                            mock_func.return_value = HealthCheckResult(
                                "test-instance-001", "test-agent", 
                                HealthCheckType.FUNCTIONALITY, HealthStatus.HEALTHY
                            )
                            
                            result = await self.health_monitor._perform_comprehensive_check(instance)
                            
                            assert result.check_type == HealthCheckType.COMPREHENSIVE
                            assert result.status == HealthStatus.WARNING  # 有一个警告
    
    def test_alert_rule_management(self):
        """测试告警规则管理"""
        # 添加告警规则
        rule = {
            "id": "test-rule-001",
            "alert_type": "performance",
            "severity": "warning",
            "status_condition": ["warning", "critical"],
            "metric_conditions": [
                {"metric_name": "response_time", "threshold": 3000, "operator": ">="}
            ],
            "message": "响应时间过高"
        }
        
        self.health_monitor.add_alert_rule(rule)
        assert len(self.health_monitor.alert_rules) == 1
        assert self.health_monitor.alert_rules[0] == rule
        
        # 移除告警规则
        self.health_monitor.remove_alert_rule("test-rule-001")
        assert len(self.health_monitor.alert_rules) == 0
    
    def test_should_trigger_alert(self):
        """测试告警触发判断"""
        # 创建测试结果
        result = HealthCheckResult(
            "test-instance-001", "test-agent",
            HealthCheckType.PERFORMANCE, HealthStatus.WARNING
        )
        result.metrics = [
            HealthMetric("response_time", 3500, 2000, 5000),
            HealthMetric("error_rate", 0.08, 0.05, 0.1)
        ]
        
        # 创建告警规则
        rule = {
            "status_condition": ["warning", "critical"],
            "metric_conditions": [
                {"metric_name": "response_time", "threshold": 3000, "operator": ">="}
            ]
        }
        
        # 应该触发告警
        should_trigger = self.health_monitor._should_trigger_alert(result, rule)
        assert should_trigger is True
        
        # 修改规则，不应该触发
        rule["metric_conditions"][0]["threshold"] = 4000
        should_trigger = self.health_monitor._should_trigger_alert(result, rule)
        assert should_trigger is False
    
    def test_get_health_summary(self):
        """测试健康状态摘要"""
        # 添加测试历史数据
        result1 = HealthCheckResult(
            "test-instance-001", "test-agent",
            HealthCheckType.BASIC, HealthStatus.HEALTHY
        )
        result2 = HealthCheckResult(
            "test-instance-002", "test-agent",
            HealthCheckType.BASIC, HealthStatus.WARNING
        )
        
        self.health_monitor.health_history["test-instance-001"].append(result1)
        self.health_monitor.health_history["test-instance-002"].append(result2)
        
        with patch('app.services.agent_health_monitor.get_agent_pool_manager') as mock_pool:
            mock_pool.return_value.instances = {
                "test-instance-001": Mock(),
                "test-instance-002": Mock()
            }
            
            # 获取特定实例摘要
            summary = self.health_monitor.get_health_summary("test-instance-001")
            assert summary["instance_id"] == "test-instance-001"
            assert summary["current_status"] == "healthy"
            
            # 获取全部实例摘要
            all_summary = self.health_monitor.get_health_summary()
            assert all_summary["total_instances"] == 2
            assert all_summary["healthy_instances"] == 1
            assert all_summary["warning_instances"] == 1
    
    def test_get_health_trends(self):
        """测试健康趋势分析"""
        # 添加测试历史数据
        base_time = time.time()
        for i in range(5):
            result = HealthCheckResult(
                "test-instance-001", "test-agent",
                HealthCheckType.BASIC, HealthStatus.HEALTHY
            )
            result.timestamp = base_time - (i * 3600)  # 每小时一个记录
            result.metrics = [HealthMetric("cpu", 50 + i * 5, 70, 90)]  # 递增的CPU使用率
            
            self.health_monitor.health_history["test-instance-001"].append(result)
        
        trends = self.health_monitor.get_health_trends("test-instance-001", 24)
        
        assert trends["instance_id"] == "test-instance-001"
        assert trends["time_period_hours"] == 24
        assert trends["check_count"] == 5
        assert "average_health_score" in trends
        assert "status_distribution" in trends
    
    def test_singleton_pattern(self):
        """测试单例模式"""
        monitor1 = get_agent_health_monitor()
        monitor2 = get_agent_health_monitor()
        
        assert monitor1 is monitor2


@pytest.mark.asyncio
async def test_agent_health_monitor_integration():
    """集成测试：完整的健康监控流程"""
    health_monitor = AgentHealthMonitor()
    
    # 创建测试实例
    instance = AgentInstance(
        instance_id="test-instance-001",
        agent_id="test-agent",
        service_url="http://test-service:8081"
    )
    instance.error_rate = 0.03
    instance.average_response_time = 1800.0
    instance.cpu_usage = 60.0
    instance.memory_usage = 70.0
    
    with patch('app.services.agent_health_monitor.get_agent_pool_manager') as mock_pool:
        mock_pool.return_value.instances = {"test-instance-001": instance}
        
        with patch('app.services.agent_health_monitor.call_service') as mock_call:
            # Mock服务调用
            mock_call.side_effect = [
                # 基础检查调用
                {"success": True, "response_time": 1800.0},
                # 功能检查调用
                {"success": True, "response": "测试响应内容正常"}
            ]
            
            with patch('app.services.agent_health_monitor.get_agent_sync_manager'):
                # 1. 执行综合健康检查
                result = await health_monitor.perform_health_check(
                    "test-instance-001", 
                    HealthCheckType.COMPREHENSIVE
                )
                
                assert result.success is not None
                assert result.instance_id == "test-instance-001"
                assert len(result.metrics) > 0
                
                # 2. 检查历史记录
                assert len(health_monitor.health_history["test-instance-001"]) == 1
                
                # 3. 验证统计更新
                assert health_monitor.monitor_stats["total_checks"] == 1
                assert health_monitor.monitor_stats["successful_checks"] == 1
                
                # 4. 获取健康摘要
                summary = health_monitor.get_health_summary("test-instance-001")
                assert summary["instance_id"] == "test-instance-001"
                assert "current_status" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])