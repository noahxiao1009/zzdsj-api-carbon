"""
智能体服务的服务间通信集成
基于统一ServiceClient SDK实现智能体服务的高效微服务间通信与协作
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import sys
import os

# 添加shared模块到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), "../../../shared"))

from service_client import (
    ServiceClient, 
    AsyncServiceClient,
    CallMethod, 
    CallConfig, 
    RetryStrategy,
    ServiceCallError,
    call_service,
    publish_event
)

logger = logging.getLogger(__name__)


class AgentServiceIntegration:
    """智能体服务集成类 - 高频调用优化"""
    
    def __init__(self):
        self.service_client = None
        self.async_client = None
        
        # 针对不同服务类型的优化配置
        self.model_config = CallConfig(
            timeout=120,  # 模型推理需要较长时间
            retry_times=2,  # 减少重试次数，避免累积延迟
            retry_strategy=RetryStrategy.EXPONENTIAL,
            circuit_breaker_enabled=True
        )
        
        self.base_config = CallConfig(
            timeout=10,   # 用户信息查询要快
            retry_times=3,
            retry_strategy=RetryStrategy.LINEAR,
            circuit_breaker_enabled=True
        )
        
        self.knowledge_config = CallConfig(
            timeout=30,   # 知识库检索中等时间
            retry_times=2,
            retry_strategy=RetryStrategy.EXPONENTIAL
        )
        
        self.database_config = CallConfig(
            timeout=15,   # 数据库操作要快
            retry_times=3,
            retry_strategy=RetryStrategy.LINEAR
        )
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.service_client = ServiceClient()
        self.async_client = AsyncServiceClient()
        await self.service_client.__aenter__()
        await self.async_client.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.service_client:
            await self.service_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.async_client:
            await self.async_client.__aexit__(exc_type, exc_val, exc_tb)
    
    # ==================== 用户和权限管理 ====================
    
    async def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """获取用户信息和权限（调用base-service）"""
        try:
            logger.info(f"获取用户信息: {user_id}")
            
            result = await self.service_client.call(
                service_name="base-service",
                method=CallMethod.GET,
                path=f"/api/v1/users/{user_id}",
                config=self.base_config
            )
            
            return result
            
        except ServiceCallError as e:
            logger.error(f"获取用户信息失败: {e}")
            if e.status_code == 404:
                return {"error": "用户不存在", "user_id": user_id}
            elif e.status_code == 503:
                # 服务不可用，返回基础信息
                return {
                    "user_id": user_id,
                    "username": f"user_{user_id[:8]}",
                    "role": "user",
                    "fallback": True
                }
            raise
        except Exception as e:
            logger.error(f"获取用户信息异常: {e}")
            raise
    
    async def check_agent_permission(self, user_id: str, agent_id: str, action: str) -> bool:
        """检查用户对智能体的操作权限"""
        try:
            result = await self.service_client.call(
                service_name="base-service",
                method=CallMethod.POST,
                path="/api/v1/permissions/check",
                config=self.base_config,
                json={
                    "user_id": user_id,
                    "resource_type": "agent",
                    "resource_id": agent_id,
                    "action": action
                }
            )
            
            return result.get("allowed", False)
            
        except ServiceCallError as e:
            logger.error(f"权限检查失败: {e}")
            if e.status_code == 503:
                # 服务不可用，默认允许
                logger.warning("权限服务不可用，默认允许操作")
                return True
            return False
        except Exception as e:
            logger.error(f"权限检查异常: {e}")
            return False
    
    # ==================== 智能体数据管理 ====================
    
    async def save_agent_config(self, agent_id: str, config: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """保存智能体配置到数据库"""
        try:
            logger.info(f"保存智能体配置: {agent_id}")
            
            result = await self.service_client.call(
                service_name="database-service",
                method=CallMethod.POST,
                path="/api/v1/agents",
                config=self.database_config,
                json={
                    "agent_id": agent_id,
                    "config": config,
                    "user_id": user_id,
                    "created_at": datetime.now().isoformat(),
                    "status": "active"
                }
            )
            
            return result
            
        except ServiceCallError as e:
            logger.error(f"保存智能体配置失败: {e}")
            raise
        except Exception as e:
            logger.error(f"保存智能体配置异常: {e}")
            raise
    
    async def get_agent_config(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """从数据库获取智能体配置"""
        try:
            result = await self.service_client.call(
                service_name="database-service",
                method=CallMethod.GET,
                path=f"/api/v1/agents/{agent_id}",
                config=self.database_config
            )
            
            return result
            
        except ServiceCallError as e:
            if e.status_code == 404:
                return None
            logger.error(f"获取智能体配置失败: {e}")
            raise
        except Exception as e:
            logger.error(f"获取智能体配置异常: {e}")
            raise
    
    async def update_agent_config(self, agent_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """更新智能体配置"""
        try:
            result = await self.service_client.call(
                service_name="database-service",
                method=CallMethod.PUT,
                path=f"/api/v1/agents/{agent_id}",
                config=self.database_config,
                json={
                    "config": config,
                    "updated_at": datetime.now().isoformat()
                }
            )
            
            return result
            
        except ServiceCallError as e:
            logger.error(f"更新智能体配置失败: {e}")
            raise
        except Exception as e:
            logger.error(f"更新智能体配置异常: {e}")
            raise
    
    # ==================== 模型服务调用 ====================
    
    async def generate_chat_response(
        self, 
        messages: List[Dict[str, str]], 
        model_config: Dict[str, Any],
        user_id: str,
        stream: bool = False
    ) -> Dict[str, Any]:
        """调用模型服务生成聊天回复"""
        try:
            logger.info(f"调用模型服务生成回复: {model_config.get('model', 'default')}")
            
            # 准备请求数据
            request_data = {
                "messages": messages,
                "model": model_config.get("model", "gpt-3.5-turbo"),
                "temperature": model_config.get("temperature", 0.7),
                "max_tokens": model_config.get("max_tokens", 1000),
                "user_id": user_id,
                "stream": stream
            }
            
            # 添加模型提供商特定参数
            if "provider" in model_config:
                request_data["provider"] = model_config["provider"]
            
            result = await self.service_client.call(
                service_name="model-service",
                method=CallMethod.POST,
                path="/api/v1/chat/completions",
                config=self.model_config,
                json=request_data
            )
            
            return result
            
        except ServiceCallError as e:
            logger.error(f"模型服务调用失败: {e}")
            if e.status_code == 503:
                # 服务不可用，返回降级响应
                return {
                    "content": "抱歉，AI服务暂时不可用，请稍后再试。",
                    "model": "fallback",
                    "usage": {"total_tokens": 0},
                    "fallback": True
                }
            raise
        except Exception as e:
            logger.error(f"模型服务调用异常: {e}")
            raise
    
    async def get_embeddings(self, texts: List[str], model: str = "text-embedding-ada-002") -> List[List[float]]:
        """获取文本向量"""
        try:
            result = await self.service_client.call(
                service_name="model-service",
                method=CallMethod.POST,
                path="/api/v1/embeddings",
                config=self.model_config,
                json={
                    "texts": texts,
                    "model": model
                }
            )
            
            return result.get("embeddings", [])
            
        except ServiceCallError as e:
            logger.error(f"获取向量失败: {e}")
            if e.status_code == 503:
                # 返回空向量
                return [[0.0] * 1536] * len(texts)
            raise
        except Exception as e:
            logger.error(f"获取向量异常: {e}")
            raise
    
    # ==================== 知识库集成 ====================
    
    async def search_knowledge_base(
        self, 
        query: str, 
        user_id: str, 
        knowledge_base_ids: Optional[List[str]] = None,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """搜索知识库"""
        try:
            logger.info(f"搜索知识库: {query[:50]}...")
            
            request_data = {
                "query": query,
                "user_id": user_id,
                "top_k": top_k,
                "search_type": "semantic"
            }
            
            if knowledge_base_ids:
                request_data["knowledge_base_ids"] = knowledge_base_ids
            
            result = await self.service_client.call(
                service_name="knowledge-service",
                method=CallMethod.POST,
                path="/api/v1/search",
                config=self.knowledge_config,
                json=request_data
            )
            
            return result
            
        except ServiceCallError as e:
            logger.error(f"知识库搜索失败: {e}")
            if e.status_code == 503:
                # 服务不可用，返回空结果
                return {
                    "documents": [],
                    "total": 0,
                    "context": "",
                    "fallback": True
                }
            raise
        except Exception as e:
            logger.error(f"知识库搜索异常: {e}")
            raise
    
    async def get_user_knowledge_bases(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户的知识库列表"""
        try:
            result = await self.service_client.call(
                service_name="knowledge-service",
                method=CallMethod.GET,
                path="/api/v1/knowledge",
                config=self.knowledge_config,
                params={"user_id": user_id}
            )
            
            return result.get("data", [])
            
        except ServiceCallError as e:
            logger.error(f"获取用户知识库失败: {e}")
            if e.status_code == 503:
                return []
            raise
        except Exception as e:
            logger.error(f"获取用户知识库异常: {e}")
            raise
    
    # ==================== 智能体对话核心逻辑 ====================
    
    async def process_agent_chat(
        self, 
        agent_id: str, 
        message: str, 
        session_id: str,
        user_id: str,
        history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """处理智能体对话的完整流程"""
        try:
            logger.info(f"处理智能体对话: {agent_id} - {message[:50]}...")
            
            # 1. 并发获取基础信息
            basic_info_tasks = [
                self.get_user_info(user_id),
                self.get_agent_config(agent_id),
                self.check_agent_permission(user_id, agent_id, "chat")
            ]
            
            user_info, agent_config, has_permission = await asyncio.gather(*basic_info_tasks)
            
            # 2. 权限检查
            if not has_permission:
                return {
                    "error": "没有与该智能体对话的权限",
                    "code": "PERMISSION_DENIED"
                }
            
            if not agent_config:
                return {
                    "error": f"智能体 {agent_id} 不存在",
                    "code": "AGENT_NOT_FOUND"
                }
            
            # 3. 准备消息历史
            messages = []
            
            # 添加系统提示
            system_prompt = agent_config.get("system_prompt", "你是一个有用的AI助手。")
            messages.append({"role": "system", "content": system_prompt})
            
            # 添加历史消息
            if history:
                messages.extend(history[-10:])  # 限制历史长度
            
            # 4. 知识库增强（如果启用）
            context = ""
            if agent_config.get("knowledge_enabled", False):
                knowledge_base_ids = agent_config.get("knowledge_base_ids", [])
                try:
                    knowledge_result = await self.search_knowledge_base(
                        query=message,
                        user_id=user_id,
                        knowledge_base_ids=knowledge_base_ids,
                        top_k=3
                    )
                    context = knowledge_result.get("context", "")
                    
                    # 如果有知识库内容，添加到系统消息
                    if context:
                        context_message = f"相关知识库内容：\n{context}\n\n请基于以上内容回答用户问题。"
                        messages.append({"role": "system", "content": context_message})
                        
                except Exception as e:
                    logger.warning(f"知识库搜索失败，继续对话: {e}")
            
            # 添加当前用户消息
            messages.append({"role": "user", "content": message})
            
            # 5. 调用模型生成回复
            model_config = agent_config.get("model_config", {
                "model": "gpt-3.5-turbo",
                "temperature": 0.7,
                "max_tokens": 1000
            })
            
            chat_result = await self.generate_chat_response(
                messages=messages,
                model_config=model_config,
                user_id=user_id,
                stream=False
            )
            
            response_content = chat_result.get("content", "抱歉，我无法生成回复。")
            
            # 6. 发布对话事件
            await self.async_client.publish_event(
                event_type="agent_chat_completed",
                data={
                    "agent_id": agent_id,
                    "user_id": user_id,
                    "session_id": session_id,
                    "message": message,
                    "response": response_content,
                    "knowledge_used": bool(context),
                    "model_used": model_config.get("model"),
                    "timestamp": datetime.now().isoformat()
                },
                priority="normal"
            )
            
            # 7. 返回完整响应
            return {
                "response": response_content,
                "session_id": session_id,
                "agent_id": agent_id,
                "metadata": {
                    "knowledge_used": bool(context),
                    "model": model_config.get("model"),
                    "tokens_used": chat_result.get("usage", {}).get("total_tokens", 0),
                    "response_time": 0  # TODO: 添加实际响应时间
                }
            }
            
        except Exception as e:
            logger.error(f"处理智能体对话失败: {e}")
            
            # 发布错误事件
            await self.async_client.publish_event(
                event_type="agent_chat_failed",
                data={
                    "agent_id": agent_id,
                    "user_id": user_id,
                    "session_id": session_id,
                    "message": message,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                },
                priority="high"
            )
            
            raise
    
    # ==================== 批量操作和性能优化 ====================
    
    async def batch_create_agents(
        self, 
        agent_configs: List[Dict[str, Any]], 
        user_id: str
    ) -> Dict[str, Any]:
        """批量创建智能体"""
        try:
            logger.info(f"批量创建 {len(agent_configs)} 个智能体")
            
            # 并发创建智能体
            tasks = []
            for config in agent_configs:
                task = asyncio.create_task(
                    self.save_agent_config(
                        agent_id=config["agent_id"],
                        config=config,
                        user_id=user_id
                    )
                )
                tasks.append(task)
            
            # 等待所有任务完成
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            success_count = 0
            failed_count = 0
            failed_agents = []
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    failed_count += 1
                    failed_agents.append({
                        "agent_id": agent_configs[i]["agent_id"],
                        "error": str(result)
                    })
                    logger.error(f"智能体 {agent_configs[i]['agent_id']} 创建失败: {result}")
                else:
                    success_count += 1
                    logger.info(f"智能体 {agent_configs[i]['agent_id']} 创建成功")
            
            # 发布批量创建完成事件
            await self.async_client.publish_event(
                event_type="agents_batch_created",
                data={
                    "user_id": user_id,
                    "total_agents": len(agent_configs),
                    "success_count": success_count,
                    "failed_count": failed_count,
                    "failed_agents": failed_agents,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            return {
                "total_agents": len(agent_configs),
                "success_count": success_count,
                "failed_count": failed_count,
                "failed_agents": failed_agents
            }
            
        except Exception as e:
            logger.error(f"批量创建智能体失败: {e}")
            raise
    
    async def health_check_dependencies(self) -> Dict[str, bool]:
        """检查所有依赖服务的健康状态"""
        services = ["base-service", "model-service", "knowledge-service", "database-service"]
        
        health_status = {}
        for service in services:
            try:
                is_healthy = await self.service_client.health_check(service)
                health_status[service] = is_healthy
                logger.info(f"服务 {service} 健康状态: {'正常' if is_healthy else '异常'}")
            except Exception as e:
                health_status[service] = False
                logger.error(f"检查服务 {service} 健康状态失败: {e}")
        
        return health_status
    
    async def get_service_metrics(self) -> Dict[str, Any]:
        """获取服务调用指标"""
        return await self.service_client.get_metrics()


# ==================== 便捷的全局函数 ====================

async def create_agent_with_integration(config: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """便捷的智能体创建函数"""
    async with AgentServiceIntegration() as agent_integration:
        return await agent_integration.save_agent_config(
            agent_id=config["agent_id"],
            config=config,
            user_id=user_id
        )


async def chat_with_agent_integrated(
    agent_id: str, 
    message: str, 
    session_id: str,
    user_id: str,
    history: Optional[List[Dict[str, str]]] = None
) -> Dict[str, Any]:
    """便捷的智能体对话函数"""
    async with AgentServiceIntegration() as agent_integration:
        return await agent_integration.process_agent_chat(
            agent_id=agent_id,
            message=message,
            session_id=session_id,
            user_id=user_id,
            history=history
        ) 