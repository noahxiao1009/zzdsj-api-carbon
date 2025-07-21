"""
智能负载均衡器测试用例
"""

import pytest
import asyncio
import time
import hashlib
from unittest.mock import Mock, AsyncMock, patch
from collections import deque

from app.services.load_balancer import (
    SmartLoadBalancer, LoadBalanceConfig, LoadBalanceAlgorithm, 
    SessionAffinityType, RoutingRequest, RoutingResult, LoadBalanceMetrics,
    get_smart_load_balancer
)
from app.services.agent_pool_manager import AgentInstance, AgentStatus


class TestLoadBalanceConfig:
    """负载均衡配置测试"""
    
    def test_load_balance_config_defaults(self):
        """测试负载均衡配置默认值"""
        config = LoadBalanceConfig()
        
        assert config.algorithm == LoadBalanceAlgorithm.WEIGHTED_LEAST_CONNECTIONS
        assert config.session_affinity == SessionAffinityType.SESSION_ID
        assert config.health_check_weight == 0.3
        assert config.response_time_weight == 0.3
        assert config.load_weight == 0.4
        assert config.sticky_session_timeout == 3600
        assert config.failover_retries == 3
        assert config.circuit_breaker_enabled is True
        assert config.adaptive_weights is True
    
    def test_load_balance_config_custom(self):
        """测试自定义负载均衡配置"""
        config = LoadBalanceConfig(
            algorithm=LoadBalanceAlgorithm.ROUND_ROBIN,
            session_affinity=SessionAffinityType.CLIENT_IP,
            health_check_weight=0.5,
            response_time_weight=0.3,
            load_weight=0.2,
            sticky_session_timeout=7200,
            failover_retries=5,
            circuit_breaker_enabled=False,
            adaptive_weights=False
        )
        
        assert config.algorithm == LoadBalanceAlgorithm.ROUND_ROBIN
        assert config.session_affinity == SessionAffinityType.CLIENT_IP
        assert config.health_check_weight == 0.5
        assert config.response_time_weight == 0.3
        assert config.load_weight == 0.2


class TestRoutingRequest:
    """路由请求测试"""
    
    def test_routing_request_creation(self):
        """测试路由请求创建"""
        request = RoutingRequest(
            session_id="session-001",
            user_id="user-123",
            client_ip="192.168.1.100",
            request_type="chat",
            priority=5,
            headers={"X-Custom": "value"},
            metadata={"source": "test"}
        )
        
        assert request.session_id == "session-001"
        assert request.user_id == "user-123"
        assert request.client_ip == "192.168.1.100"
        assert request.request_type == "chat"
        assert request.priority == 5
        assert request.headers["X-Custom"] == "value"
        assert request.metadata["source"] == "test"


class TestRoutingResult:
    """路由结果测试"""
    
    def test_routing_result_success(self):
        """测试成功的路由结果"""
        instance = AgentInstance(
            instance_id="test-instance-001",
            agent_id="test-agent",
            service_url="http://test-service:8081"
        )
        
        result = RoutingResult(
            instance=instance,
            success=True,
            routing_time=25.5,
            algorithm_used=LoadBalanceAlgorithm.LEAST_CONNECTIONS,
            affinity_hit=True
        )
        
        assert result.instance == instance
        assert result.success is True
        assert result.routing_time == 25.5
        assert result.algorithm_used == LoadBalanceAlgorithm.LEAST_CONNECTIONS
        assert result.affinity_hit is True
        assert result.fallback_used is False
        assert result.error_message is None
    
    def test_routing_result_failure(self):
        """测试失败的路由结果"""
        result = RoutingResult(
            success=False,
            error_message="没有可用的实例",
            routing_time=5.2
        )
        
        assert result.instance is None
        assert result.success is False
        assert result.error_message == "没有可用的实例"
        assert result.routing_time == 5.2


class TestSmartLoadBalancer:
    """智能负载均衡器测试"""
    
    def setup_method(self):
        """测试前置设置"""
        self.config = LoadBalanceConfig()
        self.load_balancer = SmartLoadBalancer(self.config)
        # 停止后台任务避免干扰测试
        if hasattr(self.load_balancer, '_weight_update_task') and self.load_balancer._weight_update_task:
            self.load_balancer._weight_update_task.cancel()
        if hasattr(self.load_balancer, '_metrics_cleanup_task') and self.load_balancer._metrics_cleanup_task:
            self.load_balancer._metrics_cleanup_task.cancel()
    
    def test_load_balancer_initialization(self):
        """测试负载均衡器初始化"""
        assert self.load_balancer.config == self.config
        assert isinstance(self.load_balancer.metrics, LoadBalanceMetrics)
        assert isinstance(self.load_balancer.round_robin_counters, dict)
        assert isinstance(self.load_balancer.session_affinity_map, dict)
        assert isinstance(self.load_balancer.response_time_history, dict)
        assert isinstance(self.load_balancer.hash_ring, dict)
        assert isinstance(self.load_balancer.circuit_breakers, dict)
    
    def _create_test_instances(self, count=3):
        """创建测试实例"""
        instances = []
        for i in range(count):
            instance = AgentInstance(
                instance_id=f"test-instance-{i:03d}",
                agent_id="test-agent",
                service_url=f"http://test-service-{i}:8081"
            )
            instance.status = AgentStatus.IDLE
            instance.active_sessions = i
            instance.weight = i + 1
            instance.average_response_time = (i + 1) * 1000
            instance.health_score = 100 - (i * 10)
            instance.max_concurrent_sessions = 10
            instances.append(instance)
        return instances
    
    @pytest.mark.asyncio
    async def test_get_available_instances(self):
        """测试获取可用实例"""
        instances = self._create_test_instances()
        instances[2].status = AgentStatus.UNHEALTHY  # 第三个实例不健康
        
        with patch('app.services.load_balancer.get_agent_pool_manager') as mock_pool:
            mock_pool.return_value.agent_instances = {
                "test-agent": [inst.instance_id for inst in instances]
            }
            mock_pool.return_value.instances = {
                inst.instance_id: inst for inst in instances
            }
            
            available = await self.load_balancer._get_available_instances("test-agent")
            
            assert len(available) == 2  # 只有前两个可用
            assert instances[0] in available
            assert instances[1] in available
            assert instances[2] not in available
    
    def test_round_robin_select(self):
        """测试轮询选择算法"""
        instances = self._create_test_instances()
        
        # 第一次选择
        selected1 = self.load_balancer._round_robin_select(instances)
        assert selected1 == instances[0]
        
        # 第二次选择
        selected2 = self.load_balancer._round_robin_select(instances)
        assert selected2 == instances[1]
        
        # 第三次选择
        selected3 = self.load_balancer._round_robin_select(instances)
        assert selected3 == instances[2]
        
        # 第四次选择（回到第一个）
        selected4 = self.load_balancer._round_robin_select(instances)
        assert selected4 == instances[0]
    
    def test_least_connections_select(self):
        """测试最少连接选择算法"""
        instances = self._create_test_instances()
        # instances[0].active_sessions = 0
        # instances[1].active_sessions = 1
        # instances[2].active_sessions = 2
        
        selected = self.load_balancer._least_connections_select(instances)
        assert selected == instances[0]  # 连接数最少
    
    def test_weighted_round_robin_select(self):
        """测试加权轮询选择算法"""
        instances = self._create_test_instances()
        # instances[0].weight = 1
        # instances[1].weight = 2
        # instances[2].weight = 3
        
        selections = []
        for _ in range(12):  # 测试多次选择
            selected = self.load_balancer._weighted_round_robin_select(instances)
            selections.append(selected)
        
        # 统计选择次数
        counts = {inst: selections.count(inst) for inst in instances}
        
        # 权重为1:2:3，所以在12次选择中应该大致按这个比例分配
        assert counts[instances[0]] <= counts[instances[1]]
        assert counts[instances[1]] <= counts[instances[2]]
    
    def test_weighted_least_connections_select(self):
        """测试加权最少连接选择算法"""
        instances = self._create_test_instances()
        
        selected = self.load_balancer._weighted_least_connections_select(instances)
        
        # 应该选择连接数/权重比例最小的实例
        # instances[0]: 0/1 = 0
        # instances[1]: 1/2 = 0.5
        # instances[2]: 2/3 = 0.67
        assert selected == instances[0]
    
    def test_fastest_response_select(self):
        """测试最快响应选择算法"""
        instances = self._create_test_instances()
        # instances[0].average_response_time = 1000
        # instances[1].average_response_time = 2000
        # instances[2].average_response_time = 3000
        
        selected = self.load_balancer._fastest_response_select(instances)
        assert selected == instances[0]  # 响应时间最快
    
    def test_resource_based_select(self):
        """测试基于资源的选择算法"""
        instances = self._create_test_instances()
        request = RoutingRequest()
        
        selected = self.load_balancer._resource_based_select(instances, request)
        
        # 应该选择综合资源评分最高的实例
        assert selected in instances
    
    def test_adaptive_random_select(self):
        """测试自适应随机选择算法"""
        instances = self._create_test_instances()
        request = RoutingRequest()
        
        selections = []
        for _ in range(100):  # 多次选择测试随机性
            selected = self.load_balancer._adaptive_random_select(instances, request)
            selections.append(selected)
        
        # 所有实例都应该被选中过
        selected_instances = set(selections)
        assert len(selected_instances) >= 2  # 至少两个不同的实例
    
    def test_consistent_hash_select(self):
        """测试一致性哈希选择算法"""
        instances = self._create_test_instances()
        
        request1 = RoutingRequest(session_id="session-001")
        request2 = RoutingRequest(session_id="session-001")  # 相同session_id
        request3 = RoutingRequest(session_id="session-002")  # 不同session_id
        
        # 相同的session_id应该路由到同一个实例
        selected1 = self.load_balancer._consistent_hash_select(instances, request1)
        selected2 = self.load_balancer._consistent_hash_select(instances, request2)
        assert selected1 == selected2
        
        # 不同的session_id可能路由到不同实例
        selected3 = self.load_balancer._consistent_hash_select(instances, request3)
        assert selected3 in instances
    
    def test_update_hash_ring(self):
        """测试哈希环更新"""
        instances = self._create_test_instances()
        
        # 初始更新
        self.load_balancer._update_hash_ring(instances)
        initial_size = len(self.load_balancer.hash_ring)
        assert initial_size > 0
        
        # 添加实例
        new_instance = AgentInstance(
            instance_id="test-instance-003",
            agent_id="test-agent",
            service_url="http://test-service-3:8081"
        )
        instances.append(new_instance)
        
        self.load_balancer._update_hash_ring(instances)
        updated_size = len(self.load_balancer.hash_ring)
        assert updated_size > initial_size
    
    @pytest.mark.asyncio
    async def test_check_session_affinity(self):
        """测试会话亲和性检查"""
        instances = self._create_test_instances()
        
        # 配置会话亲和性
        self.load_balancer.config.session_affinity = SessionAffinityType.SESSION_ID
        
        request = RoutingRequest(session_id="session-001")
        
        with patch('app.services.load_balancer.redis_manager') as mock_redis:
            # 无现有亲和性
            mock_redis.get.return_value = None
            result = await self.load_balancer._check_session_affinity(request, instances)
            assert result is None
            
            # 有现有亲和性
            mock_redis.get.return_value = b"test-instance-001"
            result = await self.load_balancer._check_session_affinity(request, instances)
            assert result == instances[0]
    
    @pytest.mark.asyncio
    async def test_update_session_affinity(self):
        """测试会话亲和性更新"""
        instance = self._create_test_instances()[0]
        request = RoutingRequest(session_id="session-001")
        
        self.load_balancer.config.session_affinity = SessionAffinityType.SESSION_ID
        
        with patch('app.services.load_balancer.redis_manager') as mock_redis:
            await self.load_balancer._update_session_affinity(request, instance)
            
            mock_redis.set.assert_called_once()
            call_args = mock_redis.set.call_args
            assert "session:session-001" in call_args[0][0]
            assert call_args[0][1] == instance.instance_id
    
    def test_circuit_breaker_operations(self):
        """测试熔断器操作"""
        instance_id = "test-instance-001"
        
        # 初始状态应该是关闭的
        assert not self.load_balancer._is_circuit_breaker_open(instance_id)
        
        # 模拟多次失败
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            for _ in range(6):  # 超过阈值
                loop.run_until_complete(
                    self.load_balancer._update_circuit_breaker(instance_id, False)
                )
            
            # 应该打开熔断器
            assert self.load_balancer._is_circuit_breaker_open(instance_id)
            
            # 模拟成功恢复
            for _ in range(4):  # 超过成功阈值
                loop.run_until_complete(
                    self.load_balancer._update_circuit_breaker(instance_id, True)
                )
            
            # 应该关闭熔断器
            assert not self.load_balancer._is_circuit_breaker_open(instance_id)
        finally:
            loop.close()
    
    @pytest.mark.asyncio
    async def test_update_instance_performance(self):
        """测试实例性能数据更新"""
        instance_id = "test-instance-001"
        
        # 更新成功的性能数据
        await self.load_balancer.update_instance_performance(instance_id, 1500.0, True)
        
        assert len(self.load_balancer.response_time_history[instance_id]) == 1
        assert self.load_balancer.response_time_history[instance_id][0] == 1500.0
        
        # 更新失败的性能数据
        await self.load_balancer.update_instance_performance(instance_id, 3000.0, False)
        
        assert len(self.load_balancer.response_time_history[instance_id]) == 2
    
    @pytest.mark.asyncio
    async def test_route_request_success(self):
        """测试成功的请求路由"""
        instances = self._create_test_instances()
        request = RoutingRequest(session_id="session-001", user_id="user-123")
        
        with patch.object(self.load_balancer, '_get_available_instances') as mock_get_instances:
            mock_get_instances.return_value = instances
            
            with patch.object(self.load_balancer, '_check_session_affinity') as mock_check_affinity:
                mock_check_affinity.return_value = None  # 无亲和性
                
                with patch.object(self.load_balancer, '_apply_load_balance_algorithm') as mock_apply_lb:
                    mock_apply_lb.return_value = instances[0]
                    
                    with patch.object(self.load_balancer, '_update_session_affinity') as mock_update_affinity:
                        result = await self.load_balancer.route_request("test-agent", request)
                        
                        assert result.success is True
                        assert result.instance == instances[0]
                        assert result.affinity_hit is False
                        assert result.algorithm_used == self.load_balancer.config.algorithm
                        assert result.routing_time > 0
    
    @pytest.mark.asyncio
    async def test_route_request_with_affinity(self):
        """测试带亲和性的请求路由"""
        instances = self._create_test_instances()
        request = RoutingRequest(session_id="session-001")
        
        with patch.object(self.load_balancer, '_get_available_instances') as mock_get_instances:
            mock_get_instances.return_value = instances
            
            with patch.object(self.load_balancer, '_check_session_affinity') as mock_check_affinity:
                mock_check_affinity.return_value = instances[1]  # 返回亲和性实例
                
                result = await self.load_balancer.route_request("test-agent", request)
                
                assert result.success is True
                assert result.instance == instances[1]
                assert result.affinity_hit is True
    
    @pytest.mark.asyncio
    async def test_route_request_no_instances(self):
        """测试无可用实例的请求路由"""
        request = RoutingRequest(session_id="session-001")
        
        with patch.object(self.load_balancer, '_get_available_instances') as mock_get_instances:
            mock_get_instances.return_value = []
            
            result = await self.load_balancer.route_request("test-agent", request)
            
            assert result.success is False
            assert result.instance is None
            assert result.error_message == "没有可用的实例"
    
    def test_get_load_balance_stats(self):
        """测试负载均衡统计获取"""
        # 模拟一些指标数据
        self.load_balancer.metrics.total_requests = 100
        self.load_balancer.metrics.successful_routes = 95
        self.load_balancer.metrics.failed_routes = 5
        self.load_balancer.metrics.average_routing_time = 25.5
        self.load_balancer.metrics.affinity_hits = 30
        
        stats = self.load_balancer.get_load_balance_stats()
        
        assert "metrics" in stats
        assert "configuration" in stats
        assert "circuit_breakers" in stats
        assert "timestamp" in stats
        
        assert stats["metrics"]["total_requests"] == 100
        assert stats["metrics"]["successful_routes"] == 95
        assert stats["metrics"]["success_rate"] == 0.95
        assert stats["metrics"]["affinity_hit_rate"] == 0.3
    
    def test_singleton_pattern(self):
        """测试单例模式"""
        balancer1 = get_smart_load_balancer()
        balancer2 = get_smart_load_balancer()
        
        assert balancer1 is balancer2


@pytest.mark.asyncio
async def test_load_balancer_integration():
    """集成测试：完整的负载均衡流程"""
    config = LoadBalanceConfig(
        algorithm=LoadBalanceAlgorithm.WEIGHTED_LEAST_CONNECTIONS,
        session_affinity=SessionAffinityType.SESSION_ID
    )
    load_balancer = SmartLoadBalancer(config)
    
    # 创建测试实例
    instances = []
    for i in range(3):
        instance = AgentInstance(
            instance_id=f"test-instance-{i:03d}",
            agent_id="test-agent",
            service_url=f"http://test-service-{i}:8081"
        )
        instance.status = AgentStatus.IDLE
        instance.active_sessions = 0
        instance.weight = i + 1
        instances.append(instance)
    
    with patch('app.services.load_balancer.get_agent_pool_manager') as mock_pool:
        mock_pool.return_value.agent_instances = {
            "test-agent": [inst.instance_id for inst in instances]
        }
        mock_pool.return_value.instances = {
            inst.instance_id: inst for inst in instances
        }
        
        with patch('app.services.load_balancer.redis_manager') as mock_redis:
            mock_redis.get.return_value = None  # 无现有亲和性
            
            # 1. 第一次路由请求
            request1 = RoutingRequest(session_id="session-001", user_id="user-123")
            result1 = await load_balancer.route_request("test-agent", request1)
            
            assert result1.success is True
            assert result1.instance in instances
            assert result1.affinity_hit is False
            
            # 2. 模拟会话亲和性
            mock_redis.get.return_value = result1.instance.instance_id.encode()
            
            request2 = RoutingRequest(session_id="session-001")
            result2 = await load_balancer.route_request("test-agent", request2)
            
            assert result2.success is True
            assert result2.instance == result1.instance
            assert result2.affinity_hit is True
            
            # 3. 更新性能数据
            await load_balancer.update_instance_performance(
                result1.instance.instance_id, 1200.0, True
            )
            
            assert len(load_balancer.response_time_history[result1.instance.instance_id]) == 1
            
            # 4. 检查统计
            stats = load_balancer.get_load_balance_stats()
            assert stats["metrics"]["total_requests"] == 2
            assert stats["metrics"]["successful_routes"] == 2
            assert stats["metrics"]["affinity_hits"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])