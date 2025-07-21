"""
Agent-Service集成测试用例
"""

import pytest
import asyncio
import time
import json
from unittest.mock import Mock, AsyncMock, patch
from collections import deque

from app.services.agent_service_integration import (
    AgentServiceIntegration, AgentDefinition, AgentCapability, 
    ConversationContext, ConversationRequest, ConversationResponse,
    IntegrationLevel, get_agent_service_integration
)


class TestAgentDefinition:
    """智能体定义测试"""
    
    def test_agent_definition_creation(self):
        """测试智能体定义创建"""
        agent_def = AgentDefinition(
            agent_id="test-agent-001",
            name="测试智能体",
            description="用于测试的智能体",
            version="1.2.0",
            capabilities=[AgentCapability.CHAT, AgentCapability.VOICE],
            configuration={"max_tokens": 2048, "temperature": 0.7},
            metadata={"domain": "test", "priority": "high"}
        )
        
        assert agent_def.agent_id == "test-agent-001"
        assert agent_def.name == "测试智能体"
        assert agent_def.description == "用于测试的智能体"
        assert agent_def.version == "1.2.0"
        assert AgentCapability.CHAT in agent_def.capabilities
        assert AgentCapability.VOICE in agent_def.capabilities
        assert agent_def.configuration["max_tokens"] == 2048
        assert agent_def.metadata["domain"] == "test"
        assert agent_def.status == "active"
    
    def test_agent_definition_to_dict(self):
        """测试智能体定义序列化"""
        agent_def = AgentDefinition(
            agent_id="test-agent-001",
            name="测试智能体",
            description="用于测试的智能体",
            capabilities=[AgentCapability.CHAT, AgentCapability.MULTIMODAL]
        )
        
        data = agent_def.to_dict()
        
        assert data["agent_id"] == "test-agent-001"
        assert data["name"] == "测试智能体"
        assert data["capabilities"] == ["chat", "multimodal"]
        assert "created_at" in data
        assert "updated_at" in data


class TestConversationContext:
    """对话上下文测试"""
    
    def test_conversation_context_creation(self):
        """测试对话上下文创建"""
        context = ConversationContext(
            conversation_id="conv-001",
            agent_id="agent-001",
            session_id="session-001",
            user_id="user-123",
            messages=[
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"}
            ],
            context={"language": "zh-CN", "domain": "customer_service"},
            metadata={"source": "web", "device": "desktop"}
        )
        
        assert context.conversation_id == "conv-001"
        assert context.agent_id == "agent-001"
        assert context.session_id == "session-001"
        assert context.user_id == "user-123"
        assert len(context.messages) == 2
        assert context.context["language"] == "zh-CN"
        assert context.metadata["source"] == "web"


class TestConversationRequest:
    """对话请求测试"""
    
    def test_conversation_request_creation(self):
        """测试对话请求创建"""
        request = ConversationRequest(
            agent_id="agent-001",
            session_id="session-001",
            user_id="user-123",
            message="你好，请帮我解决问题",
            message_type="text",
            context={"history_length": 10},
            options={"max_tokens": 1024, "temperature": 0.8},
            stream=True,
            priority=5
        )
        
        assert request.agent_id == "agent-001"
        assert request.session_id == "session-001"
        assert request.user_id == "user-123"
        assert request.message == "你好，请帮我解决问题"
        assert request.message_type == "text"
        assert request.context["history_length"] == 10
        assert request.options["max_tokens"] == 1024
        assert request.stream is True
        assert request.priority == 5


class TestConversationResponse:
    """对话响应测试"""
    
    def test_conversation_response_success(self):
        """测试成功的对话响应"""
        response = ConversationResponse(
            success=True,
            response="很高兴为您服务！",
            response_type="text",
            metadata={"model": "gpt-4", "tokens_used": 150},
            usage={"prompt_tokens": 50, "completion_tokens": 100},
            processing_time=1.25
        )
        
        assert response.success is True
        assert response.response == "很高兴为您服务！"
        assert response.response_type == "text"
        assert response.metadata["model"] == "gpt-4"
        assert response.usage["prompt_tokens"] == 50
        assert response.processing_time == 1.25
        assert response.error is None
    
    def test_conversation_response_failure(self):
        """测试失败的对话响应"""
        response = ConversationResponse(
            success=False,
            error="智能体服务不可用",
            processing_time=0.5
        )
        
        assert response.success is False
        assert response.response == ""
        assert response.error == "智能体服务不可用"
        assert response.processing_time == 0.5


class TestAgentServiceIntegration:
    """Agent-Service集成管理器测试"""
    
    def setup_method(self):
        """测试前置设置"""
        self.integration = AgentServiceIntegration(IntegrationLevel.FULL)
        # 停止后台任务避免干扰测试
        if hasattr(self.integration, '_request_processor_task') and self.integration._request_processor_task:
            self.integration._request_processor_task.cancel()
        if hasattr(self.integration, '_context_cleanup_task') and self.integration._context_cleanup_task:
            self.integration._context_cleanup_task.cancel()
        if hasattr(self.integration, '_registry_sync_task') and self.integration._registry_sync_task:
            self.integration._registry_sync_task.cancel()
    
    def test_integration_initialization(self):
        """测试集成管理器初始化"""
        assert self.integration.integration_level == IntegrationLevel.FULL
        assert isinstance(self.integration.agent_registry, dict)
        assert isinstance(self.integration.conversation_contexts, dict)
        assert isinstance(self.integration.request_queue, asyncio.Queue)
        assert isinstance(self.integration.integration_metrics, dict)
        assert isinstance(self.integration.response_cache, dict)
        
        # 检查默认配置
        assert self.integration.default_timeout == 30
        assert self.integration.max_retries == 3
        assert self.integration.context_ttl == 3600
        assert self.integration.cache_ttl == 300
    
    @pytest.mark.asyncio
    async def test_initialize_integration(self):
        """测试集成初始化"""
        with patch.object(self.integration, '_sync_agent_registry') as mock_sync:
            with patch.object(self.integration, '_initialize_load_balancer') as mock_lb:
                with patch.object(self.integration, '_initialize_resource_optimizer') as mock_ro:
                    mock_sync.return_value = None
                    mock_lb.return_value = None
                    mock_ro.return_value = None
                    
                    result = await self.integration.initialize_integration()
                    
                    assert result is True
                    mock_sync.assert_called_once()
                    mock_lb.assert_called_once()
                    mock_ro.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_register_agent_success(self):
        """测试智能体注册成功"""
        agent_def = AgentDefinition(
            agent_id="test-agent-001",
            name="测试智能体",
            description="用于测试的智能体",
            capabilities=[AgentCapability.CHAT]
        )
        
        with patch('app.services.agent_service_integration.call_service') as mock_call:
            with patch('app.services.agent_service_integration.redis_manager') as mock_redis:
                mock_call.return_value = {"success": True}
                
                result = await self.integration.register_agent(agent_def)
                
                assert result is True
                assert agent_def.agent_id in self.integration.agent_registry
                assert self.integration.agent_registry[agent_def.agent_id] == agent_def
                
                # 验证API调用
                mock_call.assert_called_once()
                call_args = mock_call.call_args
                assert call_args[1]["service_name"] == "agent-service"
                assert call_args[1]["method"].value == "POST"
                assert "/api/v1/agents/register" in call_args[1]["path"]
    
    @pytest.mark.asyncio
    async def test_register_agent_failure(self):
        """测试智能体注册失败"""
        agent_def = AgentDefinition(
            agent_id="test-agent-001",
            name="测试智能体",
            description="用于测试的智能体"
        )
        
        with patch('app.services.agent_service_integration.call_service') as mock_call:
            mock_call.return_value = {"success": False, "error": "注册失败"}
            
            result = await self.integration.register_agent(agent_def)
            
            assert result is False
            assert agent_def.agent_id not in self.integration.agent_registry
    
    @pytest.mark.asyncio
    async def test_get_agent_definition_from_cache(self):
        """测试从缓存获取智能体定义"""
        agent_def = AgentDefinition(
            agent_id="test-agent-001",
            name="测试智能体",
            description="用于测试的智能体"
        )
        
        # 添加到本地缓存
        self.integration.agent_registry[agent_def.agent_id] = agent_def
        
        result = await self.integration.get_agent_definition(agent_def.agent_id)
        
        assert result == agent_def
    
    @pytest.mark.asyncio
    async def test_get_agent_definition_from_service(self):
        """测试从服务获取智能体定义"""
        with patch('app.services.agent_service_integration.call_service') as mock_call:
            mock_call.return_value = {
                "success": True,
                "agent": {
                    "agent_id": "test-agent-001",
                    "name": "测试智能体",
                    "description": "用于测试的智能体",
                    "version": "1.0.0",
                    "capabilities": ["chat", "voice"],
                    "configuration": {"max_tokens": 2048},
                    "metadata": {"domain": "test"},
                    "status": "active",
                    "created_at": time.time(),
                    "updated_at": time.time()
                }
            }
            
            result = await self.integration.get_agent_definition("test-agent-001")
            
            assert result is not None
            assert result.agent_id == "test-agent-001"
            assert result.name == "测试智能体"
            assert AgentCapability.CHAT in result.capabilities
            assert AgentCapability.VOICE in result.capabilities
            
            # 应该添加到本地缓存
            assert "test-agent-001" in self.integration.agent_registry
    
    @pytest.mark.asyncio
    async def test_start_conversation(self):
        """测试开始对话"""
        with patch('app.services.agent_service_integration.call_service') as mock_call:
            with patch('app.services.agent_service_integration.redis_manager') as mock_redis:
                mock_call.return_value = {"success": True}
                
                conversation_id = await self.integration.start_conversation(
                    agent_id="test-agent-001",
                    session_id="session-001",
                    user_id="user-123",
                    initial_context={"language": "zh-CN"}
                )
                
                assert conversation_id is not None
                assert conversation_id in self.integration.conversation_contexts
                
                context = self.integration.conversation_contexts[conversation_id]
                assert context.agent_id == "test-agent-001"
                assert context.session_id == "session-001"
                assert context.user_id == "user-123"
                assert context.context["language"] == "zh-CN"
                
                # 验证指标更新
                assert self.integration.integration_metrics["total_conversations"] == 1
                assert self.integration.integration_metrics["active_conversations"] == 1
    
    def test_generate_cache_key(self):
        """测试缓存键生成"""
        request = ConversationRequest(
            agent_id="test-agent",
            session_id="session-001",
            user_id="user-123",
            message="Hello",
            context={"key": "value"}
        )
        
        key = self.integration._generate_cache_key(request)
        
        assert isinstance(key, str)
        assert len(key) == 32  # MD5哈希长度
        
        # 相同请求应该生成相同的键
        key2 = self.integration._generate_cache_key(request)
        assert key == key2
    
    def test_cache_operations(self):
        """测试缓存操作"""
        cache_key = "test_cache_key"
        response_data = {
            "response": "测试响应",
            "response_type": "text",
            "metadata": {"model": "test"}
        }
        
        # 缓存响应
        self.integration._cache_response(cache_key, response_data)
        
        # 获取缓存响应
        cached_data = self.integration._get_cached_response(cache_key)
        assert cached_data == response_data
        
        # 模拟过期
        self.integration.response_cache[cache_key]["timestamp"] = time.time() - 400  # 超过TTL
        cached_data = self.integration._get_cached_response(cache_key)
        assert cached_data is None
    
    @pytest.mark.asyncio
    async def test_send_message_with_cache_hit(self):
        """测试发送消息 - 缓存命中"""
        request = ConversationRequest(
            agent_id="test-agent",
            session_id="session-001",
            user_id="user-123",
            message="Hello"
        )
        
        # 预设缓存
        cache_key = self.integration._generate_cache_key(request)
        cached_response = {
            "response": "Hello! How can I help you?",
            "response_type": "text",
            "metadata": {"cached": True}
        }
        self.integration._cache_response(cache_key, cached_response)
        
        response = await self.integration.send_message(request)
        
        assert response.success is True
        assert response.response == "Hello! How can I help you?"
        assert response.metadata["cached"] is True
        assert self.integration.integration_metrics["cache_hits"] == 1
    
    @pytest.mark.asyncio
    async def test_send_message_success(self):
        """测试发送消息成功"""
        request = ConversationRequest(
            agent_id="test-agent",
            session_id="session-001",
            user_id="user-123",
            message="Hello"
        )
        
        # 创建对话上下文
        conversation_id = "conv-001"
        self.integration.conversation_contexts[conversation_id] = ConversationContext(
            conversation_id=conversation_id,
            agent_id="test-agent",
            session_id="session-001",
            user_id="user-123"
        )
        
        with patch.object(self.integration, '_get_optimal_agent_instance') as mock_get_instance:
            with patch('app.services.agent_service_integration.call_service') as mock_call:
                from app.services.agent_pool_manager import AgentInstance, AgentStatus
                
                # Mock实例
                test_instance = AgentInstance(
                    instance_id="test-instance-001",
                    agent_id="test-agent",
                    service_url="http://test-service:8081"
                )
                mock_get_instance.return_value = test_instance
                
                # Mock服务响应
                mock_call.return_value = {
                    "success": True,
                    "response": "Hello! How can I help you?",
                    "response_type": "text",
                    "metadata": {"model": "test-model"},
                    "usage": {"tokens": 50}
                }
                
                response = await self.integration.send_message(request)
                
                assert response.success is True
                assert response.response == "Hello! How can I help you?"
                assert response.response_type == "text"
                assert response.metadata["model"] == "test-model"
                assert response.usage["tokens"] == 50
                assert response.processing_time > 0
                
                # 验证指标更新
                assert self.integration.integration_metrics["total_requests"] == 1
                assert self.integration.integration_metrics["successful_requests"] == 1
                assert self.integration.integration_metrics["cache_misses"] == 1
    
    @pytest.mark.asyncio
    async def test_send_message_no_instance(self):
        """测试发送消息 - 无可用实例"""
        request = ConversationRequest(
            agent_id="test-agent",
            session_id="session-001",
            user_id="user-123",
            message="Hello"
        )
        
        with patch.object(self.integration, '_get_optimal_agent_instance') as mock_get_instance:
            mock_get_instance.return_value = None
            
            response = await self.integration.send_message(request)
            
            assert response.success is False
            assert response.error == "没有可用的智能体实例"
            assert self.integration.integration_metrics["failed_requests"] == 1
    
    @pytest.mark.asyncio
    async def test_update_conversation_context(self):
        """测试更新对话上下文"""
        # 创建对话上下文
        conversation_id = "conv-001"
        context = ConversationContext(
            conversation_id=conversation_id,
            agent_id="test-agent",
            session_id="session-001",
            user_id="user-123"
        )
        self.integration.conversation_contexts[conversation_id] = context
        
        request = ConversationRequest(
            agent_id="test-agent",
            session_id="session-001",
            user_id="user-123",
            message="Hello"
        )
        
        response = ConversationResponse(
            success=True,
            response="Hi there!",
            timestamp=time.time()
        )
        
        with patch('app.services.agent_service_integration.redis_manager'):
            await self.integration._update_conversation_context(request, response)
            
            # 检查消息历史
            assert len(context.messages) == 2
            assert context.messages[0]["role"] == "user"
            assert context.messages[0]["content"] == "Hello"
            assert context.messages[1]["role"] == "assistant"
            assert context.messages[1]["content"] == "Hi there!"
    
    @pytest.mark.asyncio
    async def test_sync_agent_registry(self):
        """测试同步智能体注册表"""
        with patch('app.services.agent_service_integration.call_service') as mock_call:
            mock_call.return_value = {
                "success": True,
                "agents": [
                    {
                        "agent_id": "agent-001",
                        "name": "智能体1",
                        "description": "测试智能体1",
                        "capabilities": ["chat"],
                        "configuration": {},
                        "metadata": {},
                        "status": "active"
                    },
                    {
                        "agent_id": "agent-002",
                        "name": "智能体2",
                        "description": "测试智能体2",
                        "capabilities": ["voice", "multimodal"],
                        "configuration": {},
                        "metadata": {},
                        "status": "active"
                    }
                ]
            }
            
            await self.integration._sync_agent_registry()
            
            assert len(self.integration.agent_registry) == 2
            assert "agent-001" in self.integration.agent_registry
            assert "agent-002" in self.integration.agent_registry
            
            agent1 = self.integration.agent_registry["agent-001"]
            assert agent1.name == "智能体1"
            assert AgentCapability.CHAT in agent1.capabilities
            
            agent2 = self.integration.agent_registry["agent-002"]
            assert agent2.name == "智能体2"
            assert AgentCapability.VOICE in agent2.capabilities
            assert AgentCapability.MULTIMODAL in agent2.capabilities
    
    def test_get_integration_stats(self):
        """测试获取集成统计"""
        # 添加一些测试数据
        self.integration.integration_metrics["total_requests"] = 100
        self.integration.integration_metrics["successful_requests"] = 95
        
        agent_def = AgentDefinition(
            agent_id="test-agent",
            name="测试智能体",
            description="测试"
        )
        self.integration.agent_registry["test-agent"] = agent_def
        
        context = ConversationContext(
            conversation_id="conv-001",
            agent_id="test-agent",
            session_id="session-001",
            user_id="user-123"
        )
        self.integration.conversation_contexts["conv-001"] = context
        
        stats = self.integration.get_integration_stats()
        
        assert stats["integration_level"] == IntegrationLevel.FULL.value
        assert stats["metrics"]["total_requests"] == 100
        assert stats["metrics"]["successful_requests"] == 95
        assert stats["agent_registry"]["total_agents"] == 1
        assert stats["active_conversations"] == 1
        assert "configuration" in stats
        assert "timestamp" in stats
    
    def test_singleton_pattern(self):
        """测试单例模式"""
        integration1 = get_agent_service_integration()
        integration2 = get_agent_service_integration()
        
        assert integration1 is integration2


@pytest.mark.asyncio
async def test_agent_service_integration_full_flow():
    """集成测试：完整的Agent-Service集成流程"""
    integration = AgentServiceIntegration(IntegrationLevel.FULL)
    
    # 1. 注册智能体
    agent_def = AgentDefinition(
        agent_id="test-agent-001",
        name="测试智能体",
        description="用于集成测试的智能体",
        capabilities=[AgentCapability.CHAT, AgentCapability.STREAMING]
    )
    
    with patch('app.services.agent_service_integration.call_service') as mock_call:
        with patch('app.services.agent_service_integration.redis_manager'):
            # Mock注册响应
            mock_call.return_value = {"success": True}
            
            register_result = await integration.register_agent(agent_def)
            assert register_result is True
            
            # 2. 开始对话
            mock_call.return_value = {"success": True}
            
            conversation_id = await integration.start_conversation(
                agent_id="test-agent-001",
                session_id="session-001",
                user_id="user-123",
                initial_context={"language": "zh-CN"}
            )
            assert conversation_id is not None
            
            # 3. 发送消息
            with patch.object(integration, '_get_optimal_agent_instance') as mock_get_instance:
                from app.services.agent_pool_manager import AgentInstance
                
                test_instance = AgentInstance(
                    instance_id="test-instance-001",
                    agent_id="test-agent-001",
                    service_url="http://test-service:8081"
                )
                mock_get_instance.return_value = test_instance
                
                mock_call.return_value = {
                    "success": True,
                    "response": "你好！我是测试智能体，很高兴为您服务。",
                    "response_type": "text",
                    "metadata": {"model": "test-model", "confidence": 0.95},
                    "usage": {"prompt_tokens": 20, "completion_tokens": 30}
                }
                
                request = ConversationRequest(
                    agent_id="test-agent-001",
                    session_id="session-001",
                    user_id="user-123",
                    message="你好，请问你能帮我什么？",
                    context={"history_length": 5}
                )
                
                response = await integration.send_message(request)
                
                assert response.success is True
                assert "测试智能体" in response.response
                assert response.metadata["confidence"] == 0.95
                assert response.usage["prompt_tokens"] == 20
                
                # 4. 验证对话上下文更新
                context = integration.conversation_contexts[conversation_id]
                assert len(context.messages) == 2
                assert context.messages[0]["role"] == "user"
                assert context.messages[1]["role"] == "assistant"
                
                # 5. 检查最终统计
                stats = integration.get_integration_stats()
                assert stats["metrics"]["total_requests"] == 1
                assert stats["metrics"]["successful_requests"] == 1
                assert stats["metrics"]["total_conversations"] == 1
                assert stats["agent_registry"]["total_agents"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])