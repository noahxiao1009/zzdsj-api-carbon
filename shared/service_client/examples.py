"""
微服务SDK使用示例
演示各种服务间通信场景的最佳实践
"""

import asyncio
import logging
from typing import Dict, Any
from datetime import datetime

from . import (
    ServiceClient, 
    AsyncServiceClient,
    CallMethod, 
    CallConfig, 
    RetryStrategy,
    call_service,
    publish_event
)

logger = logging.getLogger(__name__)


# ==================== 基础使用示例 ====================

async def basic_service_call_example():
    """基础服务调用示例"""
    
    # 方式1: 使用便捷函数
    try:
        result = await call_service(
            service_name="model-service",
            method=CallMethod.POST,
            path="/api/v1/chat",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "gpt-3.5-turbo"
            }
        )
        logger.info(f"模型调用结果: {result}")
        
    except Exception as e:
        logger.error(f"调用失败: {e}")
    
    # 方式2: 使用客户端实例
    async with ServiceClient() as client:
        try:
            # 获取知识库列表
            knowledge_list = await client.call(
                service_name="knowledge-service",
                method=CallMethod.GET,
                path="/api/v1/knowledge",
                params={"page": 1, "size": 10}
            )
            logger.info(f"知识库列表: {knowledge_list}")
            
            # 上传文件
            file_result = await client.call(
                service_name="system-service",
                method=CallMethod.POST,
                path="/api/v1/files/upload",
                json={"filename": "test.txt", "content": "测试内容"}
            )
            logger.info(f"文件上传结果: {file_result}")
            
        except Exception as e:
            logger.error(f"服务调用失败: {e}")


# ==================== 高级配置示例 ====================

async def advanced_config_example():
    """高级配置示例"""
    
    # 自定义调用配置
    config = CallConfig(
        timeout=60,                              # 60秒超时
        retry_times=5,                          # 重试5次
        retry_strategy=RetryStrategy.EXPONENTIAL, # 指数退避
        retry_delay=2.0,                        # 基础延迟2秒
        circuit_breaker_enabled=True            # 启用熔断器
    )
    
    async with ServiceClient(gateway_url="http://localhost:8080") as client:
        try:
            # 调用需要长时间处理的服务
            result = await client.call(
                service_name="knowledge-service",
                method=CallMethod.POST,
                path="/api/v1/documents/process",
                config=config,
                json={
                    "document_url": "https://example.com/large-doc.pdf",
                    "processing_type": "full_analysis"
                }
            )
            logger.info(f"文档处理结果: {result}")
            
        except Exception as e:
            logger.error(f"文档处理失败: {e}")


# ==================== 异步事件示例 ====================

async def async_event_example():
    """异步事件通信示例"""
    
    # 发布事件
    success = await publish_event(
        event_type="user_action",
        data={
            "user_id": "12345",
            "action": "create_knowledge_base",
            "knowledge_base_id": "kb_001",
            "timestamp": datetime.now().isoformat()
        },
        target_service="knowledge-service",
        priority="high"
    )
    
    if success:
        logger.info("用户行为事件发布成功")
    else:
        logger.error("事件发布失败")
    
    # 使用异步客户端
    async with AsyncServiceClient() as async_client:
        # 发布模型推理完成事件
        await async_client.publish_event(
            event_type="model_inference_completed",
            data={
                "inference_id": "inf_001",
                "model_name": "gpt-4",
                "result": {"response": "推理结果"},
                "duration_ms": 1500
            },
            target_service="chat-service"
        )
        
        # 订阅知识库更新事件
        await async_client.subscribe_event(
            event_type="knowledge_base_updated",
            handler=handle_knowledge_update,
            service_name="model-service"
        )


async def handle_knowledge_update(event_data: Dict[str, Any]):
    """处理知识库更新事件"""
    knowledge_base_id = event_data.get("knowledge_base_id")
    logger.info(f"知识库 {knowledge_base_id} 已更新，需要刷新模型缓存")
    
    # 执行相应的业务逻辑
    # 例如: 清除模型缓存、重新加载知识库索引等


# ==================== 批量调用示例 ====================

async def batch_call_example():
    """批量服务调用示例"""
    
    async with ServiceClient() as client:
        # 并发调用多个服务
        tasks = []
        
        # 获取用户信息
        tasks.append(
            client.call(
                service_name="base-service",
                method=CallMethod.GET,
                path="/api/v1/users/12345"
            )
        )
        
        # 获取用户的智能体列表
        tasks.append(
            client.call(
                service_name="agent-service",
                method=CallMethod.GET,
                path="/api/v1/agents",
                params={"user_id": "12345"}
            )
        )
        
        # 获取用户的知识库列表
        tasks.append(
            client.call(
                service_name="knowledge-service",
                method=CallMethod.GET,
                path="/api/v1/knowledge",
                params={"user_id": "12345"}
            )
        )
        
        # 并发执行
        try:
            user_info, agent_list, knowledge_list = await asyncio.gather(*tasks)
            
            logger.info("批量调用成功:")
            logger.info(f"用户信息: {user_info}")
            logger.info(f"智能体数量: {len(agent_list.get('data', []))}")
            logger.info(f"知识库数量: {len(knowledge_list.get('data', []))}")
            
        except Exception as e:
            logger.error(f"批量调用失败: {e}")


# ==================== 错误处理示例 ====================

async def error_handling_example():
    """错误处理和容错示例"""
    
    async with ServiceClient() as client:
        
        # 示例1: 处理服务不可用
        try:
            result = await client.call(
                service_name="non-existent-service",
                method=CallMethod.GET,
                path="/api/test"
            )
        except Exception as e:
            logger.error(f"服务不存在: {e}")
            # 使用默认值或降级逻辑
            result = {"error": "服务暂时不可用", "fallback": True}
        
        # 示例2: 检查服务健康状态
        services_to_check = ["model-service", "knowledge-service", "agent-service"]
        
        for service_name in services_to_check:
            is_healthy = await client.health_check(service_name)
            if is_healthy:
                logger.info(f"服务 {service_name} 健康")
            else:
                logger.warning(f"服务 {service_name} 不健康，启用降级策略")
                # 实施降级策略
                await implement_fallback_strategy(service_name)
        
        # 示例3: 获取调用指标
        metrics = await client.get_metrics()
        logger.info(f"调用统计: {metrics}")


async def implement_fallback_strategy(service_name: str):
    """实施降级策略"""
    if service_name == "model-service":
        logger.info("模型服务不可用，使用本地缓存响应")
        # 使用缓存的响应或简单规则
    elif service_name == "knowledge-service":
        logger.info("知识库服务不可用，禁用RAG功能")
        # 禁用知识库检索功能
    elif service_name == "agent-service":
        logger.info("智能体服务不可用，使用简单对话模式")
        # 切换到简单对话模式


# ==================== 聊天服务集成示例 ====================

class ChatServiceIntegration:
    """聊天服务集成示例"""
    
    def __init__(self):
        self.client = None
        self.async_client = None
    
    async def __aenter__(self):
        self.client = ServiceClient()
        self.async_client = AsyncServiceClient()
        await self.client.__aenter__()
        await self.async_client.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.__aexit__(exc_type, exc_val, exc_tb)
        if self.async_client:
            await self.async_client.__aexit__(exc_type, exc_val, exc_tb)
    
    async def process_chat_message(self, user_id: str, message: str, session_id: str):
        """处理聊天消息的完整流程"""
        
        try:
            # 1. 获取用户信息和偏好
            user_info = await self.client.call(
                service_name="base-service",
                method=CallMethod.GET,
                path=f"/api/v1/users/{user_id}"
            )
            
            # 2. 获取用户的智能体配置
            agent_config = await self.client.call(
                service_name="agent-service",
                method=CallMethod.GET,
                path=f"/api/v1/agents/config/{user_id}"
            )
            
            # 3. 如果启用了知识库，先进行检索
            context = ""
            if agent_config.get("knowledge_enabled"):
                knowledge_result = await self.client.call(
                    service_name="knowledge-service",
                    method=CallMethod.POST,
                    path="/api/v1/search",
                    json={
                        "query": message,
                        "user_id": user_id,
                        "top_k": 5
                    }
                )
                context = knowledge_result.get("context", "")
            
            # 4. 调用模型服务生成回复
            chat_response = await self.client.call(
                service_name="model-service",
                method=CallMethod.POST,
                path="/api/v1/chat",
                json={
                    "messages": [
                        {"role": "system", "content": f"上下文信息: {context}"},
                        {"role": "user", "content": message}
                    ],
                    "model": agent_config.get("model", "gpt-3.5-turbo"),
                    "user_id": user_id,
                    "session_id": session_id
                }
            )
            
            # 5. 发布聊天事件
            await self.async_client.publish_event(
                event_type="chat_message_processed",
                data={
                    "user_id": user_id,
                    "session_id": session_id,
                    "message": message,
                    "response": chat_response.get("content"),
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            return {
                "response": chat_response.get("content"),
                "context_used": bool(context),
                "model_used": agent_config.get("model")
            }
            
        except Exception as e:
            logger.error(f"处理聊天消息失败: {e}")
            
            # 降级策略: 使用简单回复
            return {
                "response": "抱歉，服务暂时不可用，请稍后再试。",
                "error": True
            }


# ==================== 运行示例 ====================

async def run_all_examples():
    """运行所有示例"""
    
    logger.info("=== 基础服务调用示例 ===")
    await basic_service_call_example()
    
    logger.info("\n=== 高级配置示例 ===")
    await advanced_config_example()
    
    logger.info("\n=== 异步事件示例 ===")
    await async_event_example()
    
    logger.info("\n=== 批量调用示例 ===")
    await batch_call_example()
    
    logger.info("\n=== 错误处理示例 ===")
    await error_handling_example()
    
    logger.info("\n=== 聊天服务集成示例 ===")
    async with ChatServiceIntegration() as chat_service:
        result = await chat_service.process_chat_message(
            user_id="12345",
            message="什么是人工智能？",
            session_id="session_001"
        )
        logger.info(f"聊天处理结果: {result}")


if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 运行示例
    asyncio.run(run_all_examples()) 