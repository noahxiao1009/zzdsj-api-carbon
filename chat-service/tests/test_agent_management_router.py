"""
智能体管理路由测试用例
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.api.routers.agent_management_router import router
from app.services.agent_pool_manager import AgentInstance, AgentStatus
from app.services.agent_health_monitor import HealthStatus, HealthCheckType
from app.services.resource_optimizer import ScalingTrigger
from app.services.load_balancer import LoadBalanceAlgorithm
from app.services.agent_service_integration import AgentCapability, IntegrationLevel


# 创建测试应用
app = FastAPI()
app.include_router(router)
client = TestClient(app)


class TestAgentPoolRoutes:
    """智能体池管理路由测试"""
    
    def setup_method(self):
        """测试前置设置"""
        self.mock_user = {"user_id": "test-user-123", "username": "testuser"}
    
    @patch('app.api.routers.agent_management_router.get_current_user')
    @patch('app.api.routers.agent_management_router.get_agent_pool_manager')
    def test_get_pool_status(self, mock_get_pool_manager, mock_get_user):
        """测试获取池状态"""
        mock_get_user.return_value = self.mock_user
        
        # Mock池管理器
        mock_pool_manager = Mock()
        mock_pool_manager.get_pool_status.return_value = {
            "pool_metrics": {"total_instances": 5, "healthy_instances": 4},
            "agent_statistics": {"agent-001": {"total_instances": 2}},
            "configuration": {"load_balance_strategy": "least_connections"},
            "timestamp": "2024-01-01T00:00:00"
        }
        mock_get_pool_manager.return_value = mock_pool_manager
        
        response = client.get("/api/v1/agents/pool/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["pool_metrics"]["total_instances"] == 5
    
    @patch('app.api.routers.agent_management_router.get_current_user')
    @patch('app.api.routers.agent_management_router.get_agent_pool_manager')
    def test_list_agent_instances(self, mock_get_pool_manager, mock_get_user):
        """测试列出智能体实例"""
        mock_get_user.return_value = self.mock_user
        
        # 创建测试实例
        test_instance = AgentInstance(
            instance_id="test-instance-001",
            agent_id="test-agent",
            service_url="http://test-service:8081"
        )
        test_instance.status = AgentStatus.IDLE
        
        mock_pool_manager = Mock()
        mock_pool_manager.instances = {"test-instance-001": test_instance}
        mock_get_pool_manager.return_value = mock_pool_manager
        
        response = client.get("/api/v1/agents/instances")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total"] == 1
        assert len(data["instances"]) == 1
        assert data["instances"][0]["instance_id"] == "test-instance-001"
    
    @patch('app.api.routers.agent_management_router.get_current_user')
    @patch('app.api.routers.agent_management_router.get_agent_pool_manager')
    @patch('app.api.routers.agent_management_router.get_agent_sync_manager')
    @patch('app.api.routers.agent_management_router.BackgroundTasks')
    def test_create_agent_instance(self, mock_bg_tasks, mock_get_sync_manager, 
                                  mock_get_pool_manager, mock_get_user):
        """测试创建智能体实例"""
        mock_get_user.return_value = self.mock_user
        
        # Mock池管理器
        test_instance = AgentInstance(
            instance_id="test-instance-001",
            agent_id="test-agent",
            service_url="http://test-service:8081"
        )
        
        mock_pool_manager = Mock()
        mock_pool_manager._create_agent_instance.return_value = test_instance
        mock_get_pool_manager.return_value = mock_pool_manager
        
        # Mock同步管理器
        mock_sync_manager = Mock()
        mock_get_sync_manager.return_value = mock_sync_manager
        
        # Mock后台任务
        mock_bg_tasks.return_value = Mock()
        
        request_data = {
            "agent_id": "test-agent",
            "max_concurrent_sessions": 50,
            "weight": 1.0,
            "auto_scaling": True
        }
        
        response = client.post("/api/v1/agents/instances", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["instance"]["instance_id"] == "test-instance-001"
        assert data["message"] == "智能体实例创建成功"
    
    @patch('app.api.routers.agent_management_router.get_current_user')
    @patch('app.api.routers.agent_management_router.get_agent_pool_manager')
    def test_get_agent_instance(self, mock_get_pool_manager, mock_get_user):
        """测试获取智能体实例详情"""
        mock_get_user.return_value = self.mock_user
        
        test_instance = AgentInstance(
            instance_id="test-instance-001",
            agent_id="test-agent",
            service_url="http://test-service:8081"
        )
        
        mock_pool_manager = Mock()
        mock_pool_manager.instances = {"test-instance-001": test_instance}
        mock_get_pool_manager.return_value = mock_pool_manager
        
        response = client.get("/api/v1/agents/instances/test-instance-001")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["instance"]["instance_id"] == "test-instance-001"
    
    @patch('app.api.routers.agent_management_router.get_current_user')
    @patch('app.api.routers.agent_management_router.get_agent_pool_manager')
    def test_get_agent_instance_not_found(self, mock_get_pool_manager, mock_get_user):
        """测试获取不存在的智能体实例"""
        mock_get_user.return_value = self.mock_user
        
        mock_pool_manager = Mock()
        mock_pool_manager.instances = {}
        mock_get_pool_manager.return_value = mock_pool_manager
        
        response = client.get("/api/v1/agents/instances/nonexistent-instance")
        
        assert response.status_code == 404
        data = response.json()
        assert "实例 nonexistent-instance 不存在" in data["detail"]


class TestHealthCheckRoutes:
    """健康检查路由测试"""
    
    def setup_method(self):
        """测试前置设置"""
        self.mock_user = {"user_id": "test-user-123", "username": "testuser"}
    
    @patch('app.api.routers.agent_management_router.get_current_user')
    @patch('app.api.routers.agent_management_router.get_agent_health_monitor')
    @patch('app.api.routers.agent_management_router.get_agent_pool_manager')
    def test_perform_health_check(self, mock_get_pool_manager, mock_get_health_monitor, mock_get_user):
        """测试执行健康检查"""
        mock_get_user.return_value = self.mock_user
        
        # Mock池管理器
        mock_pool_manager = Mock()
        mock_pool_manager.instances = {
            "instance-001": Mock(),
            "instance-002": Mock()
        }
        mock_get_pool_manager.return_value = mock_pool_manager
        
        # Mock健康监控器
        from app.services.agent_health_monitor import HealthCheckResult
        
        mock_result1 = Mock(spec=HealthCheckResult)
        mock_result1.to_dict.return_value = {
            "instance_id": "instance-001",
            "status": "healthy",
            "check_type": "basic"
        }
        
        mock_result2 = Mock(spec=HealthCheckResult)
        mock_result2.to_dict.return_value = {
            "instance_id": "instance-002",
            "status": "warning",
            "check_type": "basic"
        }
        
        mock_health_monitor = Mock()
        mock_health_monitor.perform_health_check.side_effect = [mock_result1, mock_result2]
        mock_get_health_monitor.return_value = mock_health_monitor
        
        request_data = {
            "check_type": "basic",
            "instances": ["instance-001", "instance-002"]
        }
        
        response = client.post("/api/v1/agents/health/check", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total_checked"] == 2
        assert len(data["results"]) == 2
    
    @patch('app.api.routers.agent_management_router.get_current_user')
    @patch('app.api.routers.agent_management_router.get_agent_health_monitor')
    def test_get_health_summary(self, mock_get_health_monitor, mock_get_user):
        """测试获取健康状态摘要"""
        mock_get_user.return_value = self.mock_user
        
        mock_health_monitor = Mock()
        mock_health_monitor.get_health_summary.return_value = {
            "total_instances": 3,
            "healthy_instances": 2,
            "warning_instances": 1,
            "critical_instances": 0,
            "monitor_stats": {"total_checks": 100}
        }
        mock_get_health_monitor.return_value = mock_health_monitor
        
        response = client.get("/api/v1/agents/health/summary")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["health_summary"]["total_instances"] == 3
        assert data["health_summary"]["healthy_instances"] == 2


class TestResourceOptimizationRoutes:
    """资源优化路由测试"""
    
    def setup_method(self):
        """测试前置设置"""
        self.mock_user = {"user_id": "test-user-123", "username": "testuser"}
    
    @patch('app.api.routers.agent_management_router.get_current_user')
    @patch('app.api.routers.agent_management_router.get_resource_optimizer')
    def test_add_scaling_rule(self, mock_get_optimizer, mock_get_user):
        """测试添加伸缩规则"""
        mock_get_user.return_value = self.mock_user
        
        mock_optimizer = Mock()
        mock_optimizer.add_scaling_rule.return_value = True
        mock_get_optimizer.return_value = mock_optimizer
        
        request_data = {
            "rule_id": "test-rule-001",
            "agent_id": "test-agent",
            "trigger": "load_based",
            "metric_name": "load_ratio",
            "threshold_up": 0.8,
            "threshold_down": 0.3,
            "min_instances": 1,
            "max_instances": 5,
            "cooldown_period": 300,
            "enabled": True
        }
        
        response = client.post("/api/v1/agents/optimization/scaling-rules", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "伸缩规则添加成功"
    
    @patch('app.api.routers.agent_management_router.get_current_user')
    @patch('app.api.routers.agent_management_router.get_resource_optimizer')
    def test_list_scaling_rules(self, mock_get_optimizer, mock_get_user):
        """测试列出伸缩规则"""
        mock_get_user.return_value = self.mock_user
        
        from app.services.resource_optimizer import ScalingRule, ScalingTrigger
        
        mock_rule = Mock(spec=ScalingRule)
        mock_rule.to_dict.return_value = {
            "rule_id": "test-rule-001",
            "agent_id": "test-agent",
            "trigger": "load_based",
            "metric_name": "load_ratio"
        }
        mock_rule.agent_id = "test-agent"
        
        mock_optimizer = Mock()
        mock_optimizer.scaling_rules = {"test-rule-001": mock_rule}
        mock_get_optimizer.return_value = mock_optimizer
        
        response = client.get("/api/v1/agents/optimization/scaling-rules")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total"] == 1
        assert len(data["scaling_rules"]) == 1


class TestLoadBalanceRoutes:
    """负载均衡路由测试"""
    
    def setup_method(self):
        """测试前置设置"""
        self.mock_user = {"user_id": "test-user-123", "username": "testuser"}
    
    @patch('app.api.routers.agent_management_router.get_current_user')
    @patch('app.api.routers.agent_management_router.get_smart_load_balancer')
    def test_get_load_balance_config(self, mock_get_balancer, mock_get_user):
        """测试获取负载均衡配置"""
        mock_get_user.return_value = self.mock_user
        
        from app.services.load_balancer import LoadBalanceConfig, LoadBalanceAlgorithm, SessionAffinityType
        
        mock_config = LoadBalanceConfig()
        mock_config.algorithm = LoadBalanceAlgorithm.LEAST_CONNECTIONS
        mock_config.session_affinity = SessionAffinityType.SESSION_ID
        
        mock_balancer = Mock()
        mock_balancer.config = mock_config
        mock_get_balancer.return_value = mock_balancer
        
        response = client.get("/api/v1/agents/loadbalance/config")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["config"]["algorithm"] == "least_connections"
        assert data["config"]["session_affinity"] == "session_id"
    
    @patch('app.api.routers.agent_management_router.get_current_user')
    @patch('app.api.routers.agent_management_router.get_smart_load_balancer')
    def test_update_load_balance_config(self, mock_get_balancer, mock_get_user):
        """测试更新负载均衡配置"""
        mock_get_user.return_value = self.mock_user
        
        from app.services.load_balancer import LoadBalanceConfig, LoadBalanceAlgorithm
        
        mock_config = LoadBalanceConfig()
        mock_balancer = Mock()
        mock_balancer.config = mock_config
        mock_get_balancer.return_value = mock_balancer
        
        request_data = {
            "algorithm": "weighted_least_connections",
            "health_check_weight": 0.4,
            "response_time_weight": 0.3,
            "load_weight": 0.3,
            "sticky_session_timeout": 7200,
            "failover_retries": 5,
            "circuit_breaker_enabled": False,
            "adaptive_weights": False
        }
        
        response = client.put("/api/v1/agents/loadbalance/config", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "负载均衡配置已更新"
    
    @patch('app.api.routers.agent_management_router.get_current_user')
    @patch('app.api.routers.agent_management_router.get_smart_load_balancer')
    def test_test_load_balance_routing(self, mock_get_balancer, mock_get_user):
        """测试负载均衡路由测试"""
        mock_get_user.return_value = self.mock_user
        
        from app.services.load_balancer import RoutingResult, LoadBalanceAlgorithm
        from app.services.agent_pool_manager import AgentInstance
        
        # Mock路由结果
        test_instance = AgentInstance(
            instance_id="test-instance-001",
            agent_id="test-agent",
            service_url="http://test-service:8081"
        )
        
        mock_result = RoutingResult(
            instance=test_instance,
            success=True,
            routing_time=25.5,
            algorithm_used=LoadBalanceAlgorithm.LEAST_CONNECTIONS,
            affinity_hit=False,
            fallback_used=False
        )
        
        mock_balancer = Mock()
        mock_balancer.route_request.return_value = mock_result
        mock_get_balancer.return_value = mock_balancer
        
        request_data = {
            "agent_id": "test-agent",
            "session_id": "session-001",
            "user_id": "user-123",
            "test_count": 2
        }
        
        response = client.post("/api/v1/agents/loadbalance/test-routing", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["test_summary"]["total_tests"] == 2
        assert data["test_summary"]["successful_routes"] == 2
        assert len(data["detailed_results"]) == 2


class TestAgentServiceIntegrationRoutes:
    """Agent-Service集成路由测试"""
    
    def setup_method(self):
        """测试前置设置"""
        self.mock_user = {"user_id": "test-user-123", "username": "testuser"}
    
    @patch('app.api.routers.agent_management_router.get_current_user')
    @patch('app.api.routers.agent_management_router.get_agent_service_integration')
    def test_initialize_agent_integration(self, mock_get_integration, mock_get_user):
        """测试初始化Agent-Service集成"""
        mock_get_user.return_value = self.mock_user
        
        mock_integration = Mock()
        mock_integration.initialize_integration.return_value = True
        mock_get_integration.return_value = mock_integration
        
        response = client.post("/api/v1/agents/integration/initialize?integration_level=full")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Agent-Service集成初始化成功"
        assert data["integration_level"] == "full"
    
    @patch('app.api.routers.agent_management_router.get_current_user')
    @patch('app.api.routers.agent_management_router.get_agent_service_integration')
    def test_register_agent_with_service(self, mock_get_integration, mock_get_user):
        """测试向Agent-Service注册智能体"""
        mock_get_user.return_value = self.mock_user
        
        mock_integration = Mock()
        mock_integration.register_agent.return_value = True
        mock_get_integration.return_value = mock_integration
        
        request_data = {
            "agent_id": "test-agent-001",
            "name": "测试智能体",
            "description": "用于测试的智能体",
            "version": "1.0.0",
            "capabilities": ["chat", "voice"],
            "configuration": {"max_tokens": 2048},
            "metadata": {"domain": "test"}
        }
        
        response = client.post("/api/v1/agents/integration/register", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "智能体注册成功"
        assert data["agent"]["agent_id"] == "test-agent-001"
    
    @patch('app.api.routers.agent_management_router.get_current_user')
    @patch('app.api.routers.agent_management_router.get_agent_service_integration')
    def test_start_conversation_with_agent(self, mock_get_integration, mock_get_user):
        """测试开始与智能体的对话"""
        mock_get_user.return_value = self.mock_user
        
        mock_integration = Mock()
        mock_integration.start_conversation.return_value = "conv-001"
        mock_get_integration.return_value = mock_integration
        
        request_data = {
            "agent_id": "test-agent",
            "session_id": "session-001",
            "user_id": "user-123",
            "initial_context": {"language": "zh-CN"}
        }
        
        response = client.post("/api/v1/agents/integration/conversations/start", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["conversation_id"] == "conv-001"
        assert data["message"] == "对话创建成功"
    
    @patch('app.api.routers.agent_management_router.get_current_user')
    @patch('app.api.routers.agent_management_router.get_agent_service_integration')
    def test_send_message_to_agent(self, mock_get_integration, mock_get_user):
        """测试向智能体发送消息"""
        mock_get_user.return_value = self.mock_user
        
        from app.services.agent_service_integration import ConversationResponse
        
        mock_response = ConversationResponse(
            success=True,
            response="你好！我是测试智能体。",
            response_type="text",
            metadata={"model": "test-model"},
            usage={"tokens": 50},
            processing_time=1.25
        )
        
        mock_integration = Mock()
        mock_integration.send_message.return_value = mock_response
        mock_get_integration.return_value = mock_integration
        
        request_data = {
            "agent_id": "test-agent",
            "session_id": "session-001",
            "user_id": "user-123",
            "message": "你好",
            "message_type": "text",
            "context": {},
            "options": {},
            "stream": False,
            "priority": 1
        }
        
        response = client.post("/api/v1/agents/integration/conversations/message", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["response"] == "你好！我是测试智能体。"
        assert data["processing_time"] == 1.25


class TestErrorHandling:
    """错误处理测试"""
    
    def setup_method(self):
        """测试前置设置"""
        self.mock_user = {"user_id": "test-user-123", "username": "testuser"}
    
    @patch('app.api.routers.agent_management_router.get_current_user')
    @patch('app.api.routers.agent_management_router.get_agent_pool_manager')
    def test_pool_status_error(self, mock_get_pool_manager, mock_get_user):
        """测试池状态获取错误"""
        mock_get_user.return_value = self.mock_user
        
        mock_pool_manager = Mock()
        mock_pool_manager.get_pool_status.side_effect = Exception("数据库连接失败")
        mock_get_pool_manager.return_value = mock_pool_manager
        
        response = client.get("/api/v1/agents/pool/status")
        
        assert response.status_code == 500
        data = response.json()
        assert "获取池状态失败" in data["detail"]
    
    @patch('app.api.routers.agent_management_router.get_current_user')
    @patch('app.api.routers.agent_management_router.get_resource_optimizer')
    def test_scaling_rule_validation_error(self, mock_get_optimizer, mock_get_user):
        """测试伸缩规则验证错误"""
        mock_get_user.return_value = self.mock_user
        
        mock_optimizer = Mock()
        mock_optimizer.add_scaling_rule.return_value = False
        mock_get_optimizer.return_value = mock_optimizer
        
        request_data = {
            "rule_id": "test-rule-001",
            "agent_id": "test-agent",
            "trigger": "load_based",
            "metric_name": "load_ratio",
            "threshold_up": 0.3,  # 错误：小于threshold_down
            "threshold_down": 0.8,
            "min_instances": 1,
            "max_instances": 5
        }
        
        response = client.post("/api/v1/agents/optimization/scaling-rules", json=request_data)
        
        assert response.status_code == 400
        data = response.json()
        assert "伸缩规则添加失败" in data["detail"]


@pytest.mark.asyncio
async def test_agent_management_integration():
    """集成测试：智能体管理完整流程"""
    
    # 这个测试需要在实际的异步环境中运行
    # 由于TestClient是同步的，这里只是演示结构
    
    with patch('app.api.routers.agent_management_router.get_current_user') as mock_get_user:
        mock_get_user.return_value = {"user_id": "test-user", "username": "testuser"}
        
        with patch('app.api.routers.agent_management_router.get_agent_pool_manager') as mock_pool:
            with patch('app.api.routers.agent_management_router.get_agent_health_monitor') as mock_health:
                with patch('app.api.routers.agent_management_router.get_resource_optimizer') as mock_optimizer:
                    with patch('app.api.routers.agent_management_router.get_smart_load_balancer') as mock_balancer:
                        with patch('app.api.routers.agent_management_router.get_agent_service_integration') as mock_integration:
                            
                            # Mock所有服务
                            mock_pool.return_value = Mock()
                            mock_health.return_value = Mock()
                            mock_optimizer.return_value = Mock()
                            mock_balancer.return_value = Mock()
                            mock_integration.return_value = Mock()
                            
                            # 1. 获取指标
                            response = client.get("/api/v1/agents/metrics")
                            assert response.status_code == 200
                            
                            # 2. 创建实例
                            # 3. 健康检查
                            # 4. 配置负载均衡
                            # 5. 设置伸缩规则
                            # 6. 集成Agent-Service
                            
                            # 这些步骤在实际集成测试中会按顺序执行


if __name__ == "__main__":
    pytest.main([__file__, "-v"])