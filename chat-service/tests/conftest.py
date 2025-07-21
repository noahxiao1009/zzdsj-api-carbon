"""
测试配置文件 - 提供共享的测试装置和配置
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, List

# 测试数据库配置
TEST_DATABASE_URL = "sqlite:///./test.db"
TEST_REDIS_URL = "redis://localhost:6379/15"  # 使用测试数据库


@pytest.fixture(scope="session")
def event_loop():
    """提供事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_redis():
    """Mock Redis管理器"""
    mock_redis = Mock()
    mock_redis.ping.return_value = True
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True
    mock_redis.delete.return_value = True
    mock_redis.llen.return_value = 0
    mock_redis.sadd.return_value = True
    mock_redis.srem.return_value = True
    mock_redis.expire.return_value = True
    mock_redis.set_json.return_value = True
    mock_redis.get_json.return_value = None
    return mock_redis


@pytest.fixture
def mock_call_service():
    """Mock服务调用"""
    async def mock_call(*args, **kwargs):
        return {"success": True, "data": "mock_response"}
    return mock_call


@pytest.fixture
def sample_agent_instance():
    """示例智能体实例"""
    from app.services.agent_pool_manager import AgentInstance, AgentStatus
    
    instance = AgentInstance(
        instance_id="test-instance-001",
        agent_id="test-agent",
        service_url="http://test-service:8081"
    )
    instance.status = AgentStatus.IDLE
    instance.active_sessions = 0
    instance.max_concurrent_sessions = 50
    instance.weight = 1.0
    instance.health_score = 100.0
    instance.cpu_usage = 30.0
    instance.memory_usage = 40.0
    instance.error_rate = 0.01
    instance.average_response_time = 1200.0
    
    return instance


@pytest.fixture
def sample_agent_instances():
    """示例智能体实例列表"""
    from app.services.agent_pool_manager import AgentInstance, AgentStatus
    
    instances = []
    for i in range(3):
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


@pytest.fixture
def sample_health_check_result():
    """示例健康检查结果"""
    from app.services.agent_health_monitor import HealthCheckResult, HealthCheckType, HealthStatus, HealthMetric
    
    result = HealthCheckResult(
        instance_id="test-instance-001",
        agent_id="test-agent",
        check_type=HealthCheckType.BASIC,
        status=HealthStatus.HEALTHY,
        check_duration=150.5,
        timestamp=time.time()
    )
    
    result.metrics = [
        HealthMetric("response_time", 1200.0, 2000, 5000, "ms", "响应时间"),
        HealthMetric("connectivity", 1.0, 0.5, 0.1, "", "连通性"),
        HealthMetric("cpu_usage", 45.0, 70, 90, "%", "CPU使用率")
    ]
    
    return result


@pytest.fixture
def sample_scaling_rule():
    """示例伸缩规则"""
    from app.services.resource_optimizer import ScalingRule, ScalingTrigger
    
    return ScalingRule(
        rule_id="test-rule-001",
        agent_id="test-agent",
        trigger=ScalingTrigger.LOAD_BASED,
        metric_name="load_ratio",
        threshold_up=0.8,
        threshold_down=0.3,
        min_instances=1,
        max_instances=5,
        cooldown_period=300,
        enabled=True
    )


@pytest.fixture
def sample_agent_definition():
    """示例智能体定义"""
    from app.services.agent_service_integration import AgentDefinition, AgentCapability
    
    return AgentDefinition(
        agent_id="test-agent-001",
        name="测试智能体",
        description="用于测试的智能体",
        version="1.0.0",
        capabilities=[AgentCapability.CHAT, AgentCapability.VOICE],
        configuration={"max_tokens": 2048, "temperature": 0.7},
        metadata={"domain": "test", "priority": "high"},
        status="active"
    )


@pytest.fixture
def sample_conversation_context():
    """示例对话上下文"""
    from app.services.agent_service_integration import ConversationContext
    
    return ConversationContext(
        conversation_id="conv-001",
        agent_id="test-agent",
        session_id="session-001",
        user_id="user-123",
        messages=[
            {"role": "user", "content": "Hello", "timestamp": time.time()},
            {"role": "assistant", "content": "Hi there!", "timestamp": time.time()}
        ],
        context={"language": "zh-CN", "domain": "customer_service"},
        metadata={"source": "web", "device": "desktop"}
    )


@pytest.fixture
def sample_routing_request():
    """示例路由请求"""
    from app.services.load_balancer import RoutingRequest
    
    return RoutingRequest(
        session_id="session-001",
        user_id="user-123",
        client_ip="192.168.1.100",
        request_type="chat",
        priority=5,
        headers={"X-Custom": "value"},
        metadata={"source": "test"}
    )


@pytest.fixture
def sample_user():
    """示例用户"""
    return {
        "user_id": "test-user-123",
        "username": "testuser",
        "email": "test@example.com",
        "roles": ["user"]
    }


@pytest.fixture
def mock_background_tasks():
    """Mock后台任务"""
    mock_tasks = Mock()
    mock_tasks.add_task = Mock()
    return mock_tasks


@pytest.fixture
def mock_dependencies():
    """Mock所有主要依赖"""
    with patch('app.services.agent_pool_manager.redis_manager') as mock_redis:
        with patch('app.services.agent_pool_manager.call_service') as mock_call:
            with patch('app.services.agent_health_monitor.redis_manager'):
                with patch('app.services.agent_health_monitor.call_service'):
                    with patch('app.services.load_balancer.redis_manager'):
                        with patch('app.services.agent_service_integration.redis_manager'):
                            with patch('app.services.agent_service_integration.call_service'):
                                mock_redis.ping.return_value = True
                                mock_call.return_value = {"success": True}
                                yield {
                                    "redis": mock_redis,
                                    "call_service": mock_call
                                }


@pytest.fixture(autouse=True)
def cleanup_singletons():
    """自动清理单例实例"""
    yield
    
    # 清理单例实例以避免测试间的状态污染
    import app.services.agent_pool_manager as pool_module
    import app.services.agent_health_monitor as health_module
    import app.services.load_balancer as balancer_module
    import app.services.agent_service_integration as integration_module
    import app.services.resource_optimizer as optimizer_module
    
    pool_module._agent_pool_manager = None
    health_module._agent_health_monitor = None
    balancer_module._smart_load_balancer = None
    integration_module._agent_service_integration = None
    optimizer_module._resource_optimizer = None


class AsyncContextManager:
    """异步上下文管理器助手"""
    
    def __init__(self, async_func):
        self.async_func = async_func
    
    async def __aenter__(self):
        return await self.async_func()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
def async_context_manager():
    """异步上下文管理器工厂"""
    return AsyncContextManager


# 测试标记
pytest_marks = {
    "unit": pytest.mark.unit,        # 单元测试
    "integration": pytest.mark.integration,  # 集成测试
    "slow": pytest.mark.slow,        # 慢速测试
    "network": pytest.mark.network,  # 需要网络的测试
}


def pytest_configure(config):
    """Pytest配置"""
    # 注册自定义标记
    for mark_name, mark in pytest_marks.items():
        config.addinivalue_line("markers", f"{mark_name}: {mark_name} tests")
    
    # 设置测试环境变量
    import os
    os.environ["TESTING"] = "true"
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    os.environ["REDIS_URL"] = TEST_REDIS_URL


def pytest_collection_modifyitems(config, items):
    """修改测试项目收集"""
    # 为异步测试添加asyncio标记
    for item in items:
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.asyncio)


# 性能测试辅助函数
@pytest.fixture
def performance_timer():
    """性能计时器"""
    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None
        
        def start(self):
            self.start_time = time.time()
        
        def stop(self):
            self.end_time = time.time()
        
        @property
        def elapsed(self):
            if self.start_time and self.end_time:
                return self.end_time - self.start_time
            return None
    
    return Timer()


# 测试数据生成器
class TestDataGenerator:
    """测试数据生成器"""
    
    @staticmethod
    def generate_agent_instances(count: int = 3) -> List:
        """生成测试智能体实例"""
        from app.services.agent_pool_manager import AgentInstance, AgentStatus
        
        instances = []
        for i in range(count):
            instance = AgentInstance(
                instance_id=f"generated-instance-{i:03d}",
                agent_id=f"generated-agent-{i:03d}",
                service_url=f"http://generated-service-{i}:8081"
            )
            instance.status = AgentStatus.IDLE
            instance.active_sessions = i
            instance.weight = i + 1
            instances.append(instance)
        
        return instances
    
    @staticmethod
    def generate_health_metrics(count: int = 5) -> List:
        """生成测试健康指标"""
        from app.services.agent_health_monitor import HealthMetric
        
        metrics = []
        metric_names = ["cpu_usage", "memory_usage", "response_time", "error_rate", "disk_usage"]
        
        for i in range(min(count, len(metric_names))):
            metric = HealthMetric(
                name=metric_names[i],
                value=float(i * 10 + 20),
                threshold_warning=70.0,
                threshold_critical=90.0,
                unit="%" if i < 2 else ("ms" if i == 2 else ("ratio" if i == 3 else "%")),
                description=f"测试指标 {metric_names[i]}"
            )
            metrics.append(metric)
        
        return metrics


@pytest.fixture
def test_data_generator():
    """测试数据生成器实例"""
    return TestDataGenerator()


# 断言辅助函数
class TestAssertions:
    """测试断言辅助类"""
    
    @staticmethod
    def assert_agent_instance_valid(instance):
        """断言智能体实例有效"""
        assert instance is not None
        assert hasattr(instance, 'instance_id')
        assert hasattr(instance, 'agent_id')
        assert hasattr(instance, 'service_url')
        assert hasattr(instance, 'status')
        assert instance.instance_id != ""
        assert instance.agent_id != ""
    
    @staticmethod
    def assert_health_result_valid(result):
        """断言健康检查结果有效"""
        assert result is not None
        assert hasattr(result, 'instance_id')
        assert hasattr(result, 'status')
        assert hasattr(result, 'check_type')
        assert hasattr(result, 'metrics')
        assert result.instance_id != ""
    
    @staticmethod
    def assert_api_response_success(response_data):
        """断言API响应成功"""
        assert "success" in response_data
        assert response_data["success"] is True
        assert "timestamp" in response_data


@pytest.fixture
def test_assertions():
    """测试断言辅助实例"""
    return TestAssertions()