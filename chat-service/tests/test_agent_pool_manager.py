"""
智能体实例池管理器测试用例
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from app.services.agent_pool_manager import (
    AgentPoolManager, AgentInstance, AgentStatus, LoadBalanceStrategy,
    get_agent_pool_manager
)


class TestAgentInstance:
    """智能体实例测试"""
    
    def test_agent_instance_creation(self):
        """测试智能体实例创建"""
        instance = AgentInstance(
            instance_id="test-instance-001",
            agent_id="test-agent",
            service_url="http://test-service:8081"
        )
        
        assert instance.instance_id == "test-instance-001"
        assert instance.agent_id == "test-agent"
        assert instance.service_url == "http://test-service:8081"
        assert instance.status == AgentStatus.INITIALIZING
        assert instance.active_sessions == 0
        assert instance.health_score == 100.0
    
    def test_update_performance_metrics(self):
        """测试性能指标更新"""
        instance = AgentInstance(
            instance_id="test-instance-001",
            agent_id="test-agent",
            service_url="http://test-service:8081"
        )
        
        # 模拟成功请求
        instance.update_performance_metrics(1000.0, True)
        
        assert instance.total_requests == 1
        assert instance.successful_requests == 1
        assert instance.failed_requests == 0
        assert instance.average_response_time == 1000.0
        assert instance.error_rate == 0.0
        
        # 模拟失败请求
        instance.update_performance_metrics(2000.0, False)
        
        assert instance.total_requests == 2
        assert instance.successful_requests == 1
        assert instance.failed_requests == 1
        assert instance.average_response_time == 1500.0  # (1000 + 2000) / 2
        assert instance.error_rate == 0.5  # 1/2
    
    def test_calculate_health_score(self):
        """测试健康分数计算"""
        instance = AgentInstance(
            instance_id="test-instance-001",
            agent_id="test-agent",
            service_url="http://test-service:8081",
            max_concurrent_sessions=100
        )
        
        # 基础健康分数
        score = instance.calculate_health_score()
        assert score == 100.0
        
        # 高响应时间惩罚
        instance.average_response_time = 2000.0  # 2秒
        score = instance.calculate_health_score()
        assert score < 100.0
        
        # 高错误率惩罚
        instance.error_rate = 0.1  # 10%
        score = instance.calculate_health_score()
        assert score < 95.0
        
        # 高负载惩罚
        instance.active_sessions = 90  # 90%负载
        score = instance.calculate_health_score()
        assert score < 90.0
    
    def test_is_available(self):
        """测试实例可用性检查"""
        instance = AgentInstance(
            instance_id="test-instance-001",
            agent_id="test-agent",
            service_url="http://test-service:8081",
            max_concurrent_sessions=10
        )
        
        # 初始状态不可用（INITIALIZING）
        assert not instance.is_available()
        
        # 空闲状态可用
        instance.status = AgentStatus.IDLE
        assert instance.is_available()
        
        # 忙碌但未超载
        instance.status = AgentStatus.BUSY
        instance.active_sessions = 5
        assert instance.is_available()
        
        # 超载不可用
        instance.active_sessions = 10
        assert not instance.is_available()
        
        # 不健康不可用
        instance.active_sessions = 0
        instance.health_score = 10.0
        assert not instance.is_available()
    
    def test_get_load_score(self):
        """测试负载分数计算"""
        instance = AgentInstance(
            instance_id="test-instance-001",
            agent_id="test-agent",
            service_url="http://test-service:8081",
            max_concurrent_sessions=10
        )
        
        instance.status = AgentStatus.IDLE
        instance.active_sessions = 2
        instance.average_response_time = 1000.0
        instance.error_rate = 0.05
        
        score = instance.get_load_score()
        expected_score = (2/10) + (1000.0/1000) + (0.05*10)  # 0.2 + 1.0 + 0.5 = 1.7
        assert abs(score - expected_score) < 0.01
    
    def test_to_dict(self):
        """测试实例序列化"""
        instance = AgentInstance(
            instance_id="test-instance-001",
            agent_id="test-agent",
            service_url="http://test-service:8081"
        )
        
        data = instance.to_dict()
        
        assert data["instance_id"] == "test-instance-001"
        assert data["agent_id"] == "test-agent"
        assert data["service_url"] == "http://test-service:8081"
        assert data["status"] == AgentStatus.INITIALIZING.value
        assert "performance" in data
        assert "health" in data
        assert "config" in data


class TestAgentPoolManager:
    """智能体池管理器测试"""
    
    def setup_method(self):
        """测试前置设置"""
        self.pool_manager = AgentPoolManager()
    
    def test_pool_manager_initialization(self):
        """测试池管理器初始化"""
        assert self.pool_manager.instances == {}
        assert self.pool_manager.agent_instances == {}
        assert self.pool_manager.load_balance_strategy == LoadBalanceStrategy.LEAST_CONNECTIONS
        assert self.pool_manager.min_instances_per_agent == 1
        assert self.pool_manager.max_instances_per_agent == 5
    
    @pytest.mark.asyncio
    async def test_get_agent_instance_no_instances(self):
        """测试获取智能体实例 - 无可用实例"""
        with patch.object(self.pool_manager, '_create_agent_instance', return_value=None):
            instance = await self.pool_manager.get_agent_instance("test-agent")
            assert instance is None
    
    @pytest.mark.asyncio
    async def test_get_agent_instance_with_available(self):
        """测试获取智能体实例 - 有可用实例"""
        # 创建测试实例
        test_instance = AgentInstance(
            instance_id="test-instance-001",
            agent_id="test-agent",
            service_url="http://test-service:8081"
        )
        test_instance.status = AgentStatus.IDLE
        
        # 添加到池中
        self.pool_manager.instances["test-instance-001"] = test_instance
        self.pool_manager.agent_instances["test-agent"] = ["test-instance-001"]
        
        with patch.object(self.pool_manager, '_update_instance_status') as mock_update:
            with patch.object(self.pool_manager, '_associate_session_instance') as mock_associate:
                instance = await self.pool_manager.get_agent_instance("test-agent", "session-001")
                
                assert instance == test_instance
                assert instance.active_sessions == 1
                mock_update.assert_called_once_with(test_instance)
                mock_associate.assert_called_once_with("session-001", "test-instance-001")
    
    @pytest.mark.asyncio
    async def test_release_agent_instance(self):
        """测试释放智能体实例"""
        # 创建测试实例
        test_instance = AgentInstance(
            instance_id="test-instance-001",
            agent_id="test-agent",
            service_url="http://test-service:8081"
        )
        test_instance.active_sessions = 2
        
        self.pool_manager.instances["test-instance-001"] = test_instance
        
        performance_metrics = {
            "response_time": 1500.0,
            "success": True
        }
        
        with patch.object(self.pool_manager, '_update_instance_status') as mock_update:
            with patch.object(self.pool_manager, '_disassociate_session_instance') as mock_disassociate:
                await self.pool_manager.release_agent_instance(
                    "test-instance-001", 
                    "session-001", 
                    performance_metrics
                )
                
                assert test_instance.active_sessions == 1
                assert test_instance.total_requests == 1
                assert test_instance.successful_requests == 1
                mock_update.assert_called_once_with(test_instance)
                mock_disassociate.assert_called_once_with("session-001")
    
    def test_get_available_instances(self):
        """测试获取可用实例列表"""
        # 创建测试实例
        instance1 = AgentInstance(
            instance_id="test-instance-001",
            agent_id="test-agent",
            service_url="http://test-service:8081"
        )
        instance1.status = AgentStatus.IDLE
        
        instance2 = AgentInstance(
            instance_id="test-instance-002",
            agent_id="test-agent",
            service_url="http://test-service:8081"
        )
        instance2.status = AgentStatus.UNHEALTHY
        
        instance3 = AgentInstance(
            instance_id="test-instance-003",
            agent_id="test-agent",
            service_url="http://test-service:8081"
        )
        instance3.status = AgentStatus.BUSY
        instance3.active_sessions = 5
        instance3.max_concurrent_sessions = 10
        
        # 添加到池中
        self.pool_manager.instances.update({
            "test-instance-001": instance1,
            "test-instance-002": instance2,
            "test-instance-003": instance3
        })
        self.pool_manager.agent_instances["test-agent"] = [
            "test-instance-001", "test-instance-002", "test-instance-003"
        ]
        
        available_instances = self.pool_manager._get_available_instances("test-agent")
        
        # 只有instance1和instance3可用
        assert len(available_instances) == 2
        assert instance1 in available_instances
        assert instance3 in available_instances
        assert instance2 not in available_instances
    
    def test_load_balance_strategies(self):
        """测试负载均衡策略"""
        # 创建测试实例
        instances = []
        for i in range(3):
            instance = AgentInstance(
                instance_id=f"test-instance-{i:03d}",
                agent_id="test-agent",
                service_url="http://test-service:8081"
            )
            instance.status = AgentStatus.IDLE
            instance.active_sessions = i  # 0, 1, 2
            instance.weight = i + 1  # 1, 2, 3
            instance.average_response_time = (i + 1) * 1000  # 1000, 2000, 3000
            instances.append(instance)
        
        # 测试轮询
        self.pool_manager.load_balance_strategy = LoadBalanceStrategy.ROUND_ROBIN
        selected1 = self.pool_manager._round_robin_select(instances)
        selected2 = self.pool_manager._round_robin_select(instances)
        assert selected1 != selected2  # 应该选择不同的实例
        
        # 测试最少连接
        selected = self.pool_manager._least_connections_select(instances)
        assert selected == instances[0]  # 连接数最少的实例
        
        # 测试最快响应
        selected = self.pool_manager._fastest_response_select(instances)
        assert selected == instances[0]  # 响应时间最快的实例
    
    @pytest.mark.asyncio
    async def test_update_instance_status(self):
        """测试实例状态更新"""
        instance = AgentInstance(
            instance_id="test-instance-001",
            agent_id="test-agent",
            service_url="http://test-service:8081",
            max_concurrent_sessions=10
        )
        
        with patch.object(self.pool_manager, '_persist_instance') as mock_persist:
            # 测试空闲状态
            instance.active_sessions = 2
            await self.pool_manager._update_instance_status(instance)
            assert instance.status == AgentStatus.IDLE
            mock_persist.assert_called_once_with(instance)
            
            # 测试忙碌状态
            mock_persist.reset_mock()
            instance.active_sessions = 8
            await self.pool_manager._update_instance_status(instance)
            assert instance.status == AgentStatus.BUSY
            
            # 测试过载状态
            mock_persist.reset_mock()
            instance.active_sessions = 10
            await self.pool_manager._update_instance_status(instance)
            assert instance.status == AgentStatus.OVERLOADED
    
    @pytest.mark.asyncio
    async def test_perform_health_check(self):
        """测试健康检查"""
        # 创建测试实例
        test_instance = AgentInstance(
            instance_id="test-instance-001",
            agent_id="test-agent",
            service_url="http://test-service:8081"
        )
        
        self.pool_manager.instances["test-instance-001"] = test_instance
        
        # Mock call_service
        with patch('app.services.agent_pool_manager.call_service') as mock_call:
            mock_call.return_value = {
                "success": True,
                "health": {
                    "cpu_usage": 50.0,
                    "memory_usage": 60.0
                }
            }
            
            await self.pool_manager.perform_health_check()
            
            assert test_instance.cpu_usage == 50.0
            assert test_instance.memory_usage == 60.0
            assert test_instance.last_health_check > 0
    
    @pytest.mark.asyncio
    async def test_scale_agent_instances(self):
        """测试智能体实例伸缩"""
        # 创建初始实例
        test_instance = AgentInstance(
            instance_id="test-instance-001",
            agent_id="test-agent",
            service_url="http://test-service:8081"
        )
        
        self.pool_manager.instances["test-instance-001"] = test_instance
        self.pool_manager.agent_instances["test-agent"] = ["test-instance-001"]
        
        # 测试扩容
        with patch.object(self.pool_manager, '_create_agent_instance') as mock_create:
            new_instance = AgentInstance(
                instance_id="test-instance-002",
                agent_id="test-agent",
                service_url="http://test-service:8081"
            )
            mock_create.return_value = new_instance
            
            result = await self.pool_manager.scale_agent_instances("test-agent", 2)
            
            assert result["success"] is True
            assert result["action"] == "scale_up"
            assert result["previous_count"] == 1
            assert result["target_count"] == 2
            assert len(result["created_instances"]) == 1
        
        # 测试缩容
        self.pool_manager.instances["test-instance-002"] = new_instance
        self.pool_manager.agent_instances["test-agent"].append("test-instance-002")
        
        with patch.object(self.pool_manager, '_remove_instance') as mock_remove:
            result = await self.pool_manager.scale_agent_instances("test-agent", 1)
            
            assert result["success"] is True
            assert result["action"] == "scale_down"
            assert result["previous_count"] == 2
            assert result["target_count"] == 1
            assert len(result["removed_instances"]) == 1
    
    @pytest.mark.asyncio
    async def test_get_pool_status(self):
        """测试获取池状态"""
        # 创建测试实例
        test_instance = AgentInstance(
            instance_id="test-instance-001",
            agent_id="test-agent",
            service_url="http://test-service:8081"
        )
        
        self.pool_manager.instances["test-instance-001"] = test_instance
        self.pool_manager.agent_instances["test-agent"] = ["test-instance-001"]
        
        status = await self.pool_manager.get_pool_status()
        
        assert "pool_metrics" in status
        assert "agent_statistics" in status
        assert "configuration" in status
        assert "timestamp" in status
        
        assert "test-agent" in status["agent_statistics"]
        assert status["agent_statistics"]["test-agent"]["total_instances"] == 1
    
    def test_singleton_pattern(self):
        """测试单例模式"""
        pool_manager1 = get_agent_pool_manager()
        pool_manager2 = get_agent_pool_manager()
        
        assert pool_manager1 is pool_manager2


@pytest.mark.asyncio
async def test_agent_pool_manager_integration():
    """集成测试：完整的实例生命周期"""
    pool_manager = AgentPoolManager()
    
    # Mock外部依赖
    with patch('app.services.agent_pool_manager.call_service') as mock_call:
        with patch('app.services.agent_pool_manager.redis_manager'):
            # 模拟创建实例成功
            mock_call.return_value = {
                "success": True,
                "instance": {
                    "instance_id": "test-instance-001",
                    "service_url": "http://test-service:8081",
                    "max_concurrent_sessions": 50,
                    "weight": 1.0
                }
            }
            
            # 1. 获取实例（会自动创建）
            instance = await pool_manager.get_agent_instance("test-agent", "session-001")
            assert instance is not None
            assert instance.agent_id == "test-agent"
            assert instance.active_sessions == 1
            
            # 2. 模拟使用
            performance_metrics = {"response_time": 1200.0, "success": True}
            await pool_manager.release_agent_instance(
                instance.instance_id, 
                "session-001", 
                performance_metrics
            )
            assert instance.active_sessions == 0
            assert instance.total_requests == 1
            
            # 3. 健康检查
            mock_call.return_value = {
                "success": True,
                "health": {"cpu_usage": 45.0, "memory_usage": 55.0}
            }
            await pool_manager.perform_health_check()
            assert instance.cpu_usage == 45.0
            
            # 4. 伸缩测试
            mock_call.return_value = {
                "success": True,
                "instance": {
                    "instance_id": "test-instance-002",
                    "service_url": "http://test-service:8081",
                    "max_concurrent_sessions": 50,
                    "weight": 1.0
                }
            }
            
            scale_result = await pool_manager.scale_agent_instances("test-agent", 2)
            assert scale_result["success"] is True
            assert scale_result["action"] == "scale_up"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])