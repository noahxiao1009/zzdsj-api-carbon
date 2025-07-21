"""
聊天服务的服务间通信集成
基于Agno框架的智能对话系统，提供会话管理、流式响应、语音交互等功能
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Union, AsyncGenerator
from datetime import datetime, timedelta
import json
import sys
import os
import uuid
from enum import Enum
import aioredis
from collections import defaultdict

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


class ChatSessionStatus(Enum):
    """聊天会话状态"""
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"
    ARCHIVED = "archived"


class MessageType(Enum):
    """消息类型"""
    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"
    FILE = "file"
    SYSTEM = "system"
    AGENT_RESPONSE = "agent_response"


class MessageStatus(Enum):
    """消息状态"""
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class ResponseMode(Enum):
    """响应模式"""
    STANDARD = "standard"
    STREAMING = "streaming"
    VOICE = "voice"
    MULTIMODAL = "multimodal"


class ChatServiceIntegration:
    """聊天服务集成类 - 智能对话和会话管理"""
    
    def __init__(self):
        self.service_client = None
        self.async_client = None
        self.redis_client = None
        
        # 配置不同服务的调用参数
        self.auth_config = CallConfig(
            timeout=5,    # 认证要快
            retry_times=2,
            retry_strategy=RetryStrategy.LINEAR
        )
        
        self.agent_config = CallConfig(
            timeout=60,   # 智能体调用较长
            retry_times=3,
            retry_strategy=RetryStrategy.LINEAR
        )
        
        self.model_config = CallConfig(
            timeout=120,  # 模型调用可能很长
            retry_times=2,
            retry_strategy=RetryStrategy.EXPONENTIAL
        )
        
        # 聊天服务功能
        self.chat_capabilities = {
            "intelligent_conversation": {
                "description": "智能对话",
                "features": ["multi_agent_chat", "context_awareness", "emotion_recognition"]
            },
            "session_management": {
                "description": "会话管理", 
                "features": ["session_creation", "history_tracking", "session_persistence"]
            },
            "streaming_response": {
                "description": "流式响应",
                "features": ["real_time_streaming", "partial_updates", "progressive_generation"]
            },
            "voice_interaction": {
                "description": "语音交互",
                "features": ["speech_to_text", "text_to_speech", "voice_commands"]
            }
        }
        
        # 会话状态和统计
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.user_sessions: Dict[str, List[str]] = defaultdict(list)
        self.available_agents: Dict[str, Dict[str, Any]] = {}
        
        # 处理统计
        self.chat_stats = {
            "total_sessions": 0,
            "active_sessions": 0,
            "messages_processed": 0,
            "voice_interactions": 0,
            "streaming_responses": 0,
            "agent_calls": 0,
            "uptime_start": datetime.now()
        }
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.service_client = ServiceClient()
        self.async_client = AsyncServiceClient()
        await self.service_client.__aenter__()
        await self.async_client.__aenter__()
        
        # 初始化Redis连接
        try:
            self.redis_client = aioredis.from_url(
                "redis://localhost:6379/0",
                encoding="utf-8",
                decode_responses=True
            )
            await self._load_available_agents()
        except Exception as e:
            logger.warning(f"Redis连接失败: {e}")
            
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.service_client:
            await self.service_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.async_client:
            await self.async_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.redis_client:
            await self.redis_client.close()
    
    # ==================== 权限验证 ====================
    
    async def _verify_user_permission(self, user_id: str, action: str) -> Dict[str, Any]:
        """验证用户权限"""
        try:
            result = await self.service_client.call(
                service_name="base-service",
                method=CallMethod.POST,
                path="/api/v1/auth/check-permission",
                config=self.auth_config,
                json={
                    "user_id": user_id,
                    "resource_type": "CHAT",
                    "action": action,
                    "context": {
                        "service": "chat-service",
                        "operation": action
                    }
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(f"权限验证失败: {e}")
            return {"allowed": False, "error": str(e)}
    
    # ==================== 智能体管理 ====================
    
    async def _load_available_agents(self):
        """加载可用的智能体"""
        try:
            result = await self.service_client.call(
                service_name="agent-service",
                method=CallMethod.GET,
                path="/api/v1/agents/available",
                config=self.agent_config
            )
            
            if result.get("success"):
                agents = result.get("agents", [])
                for agent in agents:
                    agent_id = agent.get("agent_id")
                    if agent_id:
                        self.available_agents[agent_id] = {
                            "agent_id": agent_id,
                            "name": agent.get("name"),
                            "capabilities": agent.get("capabilities", []),
                            "status": agent.get("status", "available"),
                            "loaded_at": datetime.now()
                        }
                
                logger.info(f"加载了 {len(self.available_agents)} 个智能体")
            
        except Exception as e:
            logger.error(f"加载智能体失败: {e}")
    
    # ==================== 会话管理 ====================
    
    async def create_chat_session_workflow(
        self,
        user_id: str,
        agent_id: Optional[str] = None,
        session_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """创建聊天会话的完整工作流"""
        try:
            start_time = datetime.now()
            logger.info(f"开始创建聊天会话: 用户={user_id}, 智能体={agent_id}")
            
            # 1. 权限验证
            auth_result = await self._verify_user_permission(user_id, "create_chat_session")
            if not auth_result.get("allowed"):
                return {
                    "success": False,
                    "error": "权限不足",
                    "required_permission": "chat:create_session"
                }
            
            # 2. 验证智能体
            selected_agent = None
            if agent_id:
                if agent_id in self.available_agents:
                    selected_agent = self.available_agents[agent_id]
                else:
                    return {
                        "success": False,
                        "error": "智能体不可用"
                    }
            else:
                # 使用默认智能体
                if self.available_agents:
                    agent_id = list(self.available_agents.keys())[0]
                    selected_agent = self.available_agents[agent_id]
            
            # 3. 生成会话ID和配置
            session_id = str(uuid.uuid4())
            session_metadata = {
                "session_id": session_id,
                "user_id": user_id,
                "agent_id": agent_id,
                "agent_info": selected_agent,
                "status": ChatSessionStatus.ACTIVE.value,
                "created_at": start_time,
                "updated_at": start_time,
                "message_count": 0,
                "config": session_config or {},
                "context": {
                    "conversation_history": [],
                    "user_preferences": {},
                    "session_metadata": {}
                }
            }
            
            # 4. 注册到活跃会话
            self.active_sessions[session_id] = session_metadata
            self.user_sessions[user_id].append(session_id)
            
            # 5. 更新统计
            self.chat_stats["total_sessions"] += 1
            self.chat_stats["active_sessions"] = len(self.active_sessions)
            
            # 6. 发布会话创建事件
            await publish_event(
                "chat_session.created",
                {
                    "session_id": session_id,
                    "user_id": user_id,
                    "agent_id": agent_id,
                    "creation_time": (datetime.now() - start_time).total_seconds(),
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            logger.info(f"聊天会话创建成功: {session_id}")
            
            return {
                "success": True,
                "session_id": session_id,
                "agent_info": selected_agent,
                "status": ChatSessionStatus.ACTIVE.value,
                "creation_time": (datetime.now() - start_time).total_seconds()
            }
            
        except Exception as e:
            logger.error(f"聊天会话创建失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "user_id": user_id
            }
    
    async def send_message_workflow(
        self,
        session_id: str,
        message_content: str,
        user_id: str,
        message_type: MessageType = MessageType.TEXT,
        response_mode: ResponseMode = ResponseMode.STANDARD
    ) -> Dict[str, Any]:
        """发送消息的完整工作流"""
        try:
            start_time = datetime.now()
            logger.info(f"处理消息发送: 会话={session_id}, 用户={user_id}")
            
            # 1. 验证会话
            if session_id not in self.active_sessions:
                return {
                    "success": False,
                    "error": "会话不存在或已失效"
                }
            
            session = self.active_sessions[session_id]
            
            # 2. 权限验证
            if session.get("user_id") != user_id:
                auth_result = await self._verify_user_permission(user_id, "access_chat_session")
                if not auth_result.get("allowed"):
                    return {
                        "success": False,
                        "error": "权限不足"
                    }
            
            # 3. 构造用户消息
            message_id = str(uuid.uuid4())
            user_message = {
                "message_id": message_id,
                "session_id": session_id,
                "user_id": user_id,
                "content": message_content,
                "type": message_type.value,
                "status": MessageStatus.SENT.value,
                "timestamp": datetime.now().isoformat(),
                "metadata": {}
            }
            
            # 4. 调用智能体处理
            agent_id = session.get("agent_id")
            if not agent_id:
                return {
                    "success": False,
                    "error": "会话未绑定智能体"
                }
            
            # 5. 根据响应模式处理
            if response_mode == ResponseMode.STREAMING:
                response_result = await self._handle_streaming_response(session, user_message)
                self.chat_stats["streaming_responses"] += 1
            elif response_mode == ResponseMode.VOICE:
                response_result = await self._handle_voice_response(session, user_message)
                self.chat_stats["voice_interactions"] += 1
            else:
                response_result = await self._handle_standard_response(session, user_message)
            
            # 6. 更新会话状态
            session["message_count"] += 1
            session["updated_at"] = datetime.now()
            
            # 7. 更新统计
            self.chat_stats["messages_processed"] += 1
            self.chat_stats["agent_calls"] += 1
            
            # 8. 发布消息事件
            await publish_event(
                "chat_message.processed",
                {
                    "session_id": session_id,
                    "message_id": message_id,
                    "user_id": user_id,
                    "agent_id": agent_id,
                    "message_type": message_type.value,
                    "response_mode": response_mode.value,
                    "processing_time": (datetime.now() - start_time).total_seconds(),
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            return {
                "success": True,
                "message_id": message_id,
                "response": response_result,
                "processing_time": (datetime.now() - start_time).total_seconds()
            }
            
        except Exception as e:
            logger.error(f"消息发送失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "session_id": session_id
            }
    
    # ==================== 响应处理 ====================
    
    async def _handle_standard_response(self, session: Dict[str, Any], user_message: Dict[str, Any]) -> Dict[str, Any]:
        """处理标准响应"""
        try:
            agent_id = session.get("agent_id")
            
            response = await self.service_client.call(
                service_name="agent-service",
                method=CallMethod.POST,
                path=f"/api/v1/agents/{agent_id}/chat",
                config=self.agent_config,
                json={
                    "session_id": session["session_id"],
                    "message": user_message["content"],
                    "context": session.get("context", {}),
                    "user_id": session["user_id"]
                }
            )
            
            if response.get("success"):
                agent_response = response.get("response", "")
                
                response_message = {
                    "message_id": str(uuid.uuid4()),
                    "session_id": session["session_id"],
                    "agent_id": agent_id,
                    "content": agent_response,
                    "type": MessageType.AGENT_RESPONSE.value,
                    "status": MessageStatus.SENT.value,
                    "timestamp": datetime.now().isoformat(),
                    "metadata": response.get("metadata", {})
                }
                
                return {
                    "success": True,
                    "message": response_message,
                    "response_type": "standard"
                }
            else:
                return {
                    "success": False,
                    "error": response.get("error", "智能体响应失败")
                }
            
        except Exception as e:
            logger.error(f"标准响应处理失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _handle_streaming_response(self, session: Dict[str, Any], user_message: Dict[str, Any]) -> Dict[str, Any]:
        """处理流式响应"""
        try:
            agent_id = session.get("agent_id")
            
            response = await self.service_client.call(
                service_name="agent-service",
                method=CallMethod.POST,
                path=f"/api/v1/agents/{agent_id}/chat/stream",
                config=self.agent_config,
                json={
                    "session_id": session["session_id"],
                    "message": user_message["content"],
                    "context": session.get("context", {}),
                    "user_id": session["user_id"]
                }
            )
            
            return {
                "success": True,
                "stream_id": response.get("stream_id"),
                "response_type": "streaming"
            }
            
        except Exception as e:
            logger.error(f"流式响应处理失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _handle_voice_response(self, session: Dict[str, Any], user_message: Dict[str, Any]) -> Dict[str, Any]:
        """处理语音响应"""
        try:
            # 获取文本响应
            text_response = await self._handle_standard_response(session, user_message)
            
            if not text_response.get("success"):
                return text_response
            
            # 转换为语音 (调用模型服务的TTS)
            response_text = text_response["message"]["content"]
            voice_result = await self.service_client.call(
                service_name="model-service",
                method=CallMethod.POST,
                path="/api/v1/tts/generate",
                config=self.model_config,
                json={
                    "text": response_text,
                    "voice_model": "default",
                    "user_id": session["user_id"]
                }
            )
            
            if voice_result.get("success"):
                text_response["voice_url"] = voice_result["voice_url"]
                text_response["response_type"] = "voice"
            
            return text_response
            
        except Exception as e:
            logger.error(f"语音响应处理失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # ==================== 会话查询和管理 ====================
    
    async def get_session_history(self, session_id: str, user_id: str, limit: int = 50) -> Dict[str, Any]:
        """获取会话历史"""
        try:
            if session_id not in self.active_sessions:
                return {
                    "success": False,
                    "error": "会话不存在"
                }
            
            session = self.active_sessions[session_id]
            
            # 权限验证
            if session.get("user_id") != user_id:
                auth_result = await self._verify_user_permission(user_id, "access_chat_session")
                if not auth_result.get("allowed"):
                    return {
                        "success": False,
                        "error": "权限不足"
                    }
            
            # 从数据库获取消息历史
            history_result = await self.service_client.call(
                service_name="database-service",
                method=CallMethod.POST,
                path="/api/v1/query",
                config=CallConfig(timeout=15),
                json={
                    "db_type": "postgresql",
                    "query": "SELECT * FROM chat_messages WHERE session_id = $1 ORDER BY timestamp DESC LIMIT $2",
                    "params": [session_id, limit],
                    "user_id": user_id
                }
            )
            
            if history_result.get("success"):
                messages = history_result.get("results", [])
                return {
                    "success": True,
                    "session_id": session_id,
                    "messages": messages,
                    "total_count": len(messages)
                }
            else:
                return {
                    "success": False,
                    "error": "获取历史失败"
                }
            
        except Exception as e:
            logger.error(f"获取会话历史失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_chat_stats(self) -> Dict[str, Any]:
        """获取聊天服务统计信息"""
        try:
            current_time = datetime.now()
            uptime_seconds = (current_time - self.chat_stats["uptime_start"]).total_seconds()
            
            stats = {
                "total_sessions": self.chat_stats["total_sessions"],
                "active_sessions": len(self.active_sessions),
                "messages_processed": self.chat_stats["messages_processed"],
                "voice_interactions": self.chat_stats["voice_interactions"],
                "streaming_responses": self.chat_stats["streaming_responses"],
                "agent_calls": self.chat_stats["agent_calls"],
                "available_agents": len(self.available_agents),
                "uptime_seconds": uptime_seconds,
                "server_status": "healthy" if len(self.active_sessions) < 1000 else "busy",
                "timestamp": current_time.isoformat()
            }
            
            return {
                "success": True,
                "stats": stats,
                "capabilities": self.chat_capabilities
            }
            
        except Exception as e:
            logger.error(f"获取聊天统计失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# ==================== 便捷的全局函数 ====================

async def create_chat_session(user_id: str, agent_id: Optional[str] = None) -> Dict[str, Any]:
    """便捷的聊天会话创建函数"""
    async with ChatServiceIntegration() as chat_service:
        return await chat_service.create_chat_session_workflow(user_id, agent_id)


async def send_chat_message(session_id: str, message: str, user_id: str, mode: str = "standard") -> Dict[str, Any]:
    """便捷的聊天消息发送函数"""
    async with ChatServiceIntegration() as chat_service:
        return await chat_service.send_message_workflow(
            session_id, message, user_id, MessageType.TEXT, ResponseMode(mode)
        )


async def get_chat_history(session_id: str, user_id: str, limit: int = 50) -> Dict[str, Any]:
    """便捷的聊天历史获取函数"""
    async with ChatServiceIntegration() as chat_service:
        return await chat_service.get_session_history(session_id, user_id, limit)


# ==================== 使用示例 ====================

async def chat_service_demo():
    """聊天服务集成模块"""
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    async with ChatServiceIntegration() as chat_service:
        
        # 1. 服务统计
        logger.info("=== 📊 聊天服务统计 ===")
        stats_result = await chat_service.get_chat_stats()
        if stats_result.get("success"):
            stats = stats_result["stats"]
            print(f"总会话数: {stats['total_sessions']}")
            print(f"活跃会话数: {stats['active_sessions']}")
            print(f"已处理消息数: {stats['messages_processed']}")
            print(f"可用智能体数: {stats['available_agents']}")
        
        # 2. 创建聊天会话
        logger.info("\n=== 💬 创建聊天会话 ===")
        session_result = await chat_service.create_chat_session_workflow("user_123")
        print(f"会话创建结果: {session_result}")
        
        if session_result.get("success"):
            session_id = session_result["session_id"]
            
            # 3. 发送消息
            logger.info("\n=== 📝 发送消息 ===")
            message_result = await chat_service.send_message_workflow(
                session_id, "你好，我需要一些帮助", "user_123", 
                MessageType.TEXT, ResponseMode.STANDARD
            )
            print(f"消息发送结果: {message_result}")
            
            # 4. 流式响应测试
            logger.info("\n=== 🌊 流式响应测试 ===")
            stream_result = await chat_service.send_message_workflow(
                session_id, "请详细解释人工智能", "user_123",
                MessageType.TEXT, ResponseMode.STREAMING
            )
            print(f"流式响应结果: {stream_result}")
            
            # 5. 获取会话历史
            logger.info("\n=== 📚 获取会话历史 ===")
            history_result = await chat_service.get_session_history(session_id, "user_123")
            print(f"会话历史: {history_result}")
        
        # 6. 最终统计
        logger.info("\n=== 📈 最终统计 ===")
        final_stats = await chat_service.get_chat_stats()
        if final_stats.get("success"):
            print(f"最终统计: {final_stats['stats']}")


if __name__ == "__main__":
    print("🚀 聊天服务集成启动")
    print("=" * 50)
    asyncio.run(chat_service_demo())
