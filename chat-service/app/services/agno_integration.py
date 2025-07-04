"""
Agno框架集成服务
基于原始项目的Agno实现，提供智能体对话和管理功能
"""

import asyncio
import logging
import uuid
import json
from typing import Dict, List, Any, Optional, AsyncGenerator, Union
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

from app.core.config import settings
from app.core.redis import redis_manager

# 动态导入Agno组件
try:
    from agno.agent import Agent as AgnoAgent
    from agno.models.openai import OpenAIChat
    from agno.tools.reasoning import ReasoningTools
    from agno.memory import Memory as AgnoMemory
    from agno.storage import Storage as AgnoStorage
    from agno.team import Team as AgnoTeam
    AGNO_AVAILABLE = True
except ImportError:
    AGNO_AVAILABLE = False
    AgnoAgent = object
    OpenAIChat = object
    ReasoningTools = object
    AgnoMemory = object
    AgnoStorage = object
    AgnoTeam = object

logger = logging.getLogger(__name__)


class MessageRole(str, Enum):
    """消息角色"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ResponseFormat(str, Enum):
    """响应格式"""
    TEXT = "text"
    JSON = "json"
    MARKDOWN = "markdown"


@dataclass
class ChatMessage:
    """聊天消息数据结构"""
    message_id: str
    session_id: str
    role: MessageRole
    content: str
    timestamp: datetime
    agent_id: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "message_id": self.message_id,
            "session_id": self.session_id,
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "agent_id": self.agent_id,
            "metadata": self.metadata or {}
        }


@dataclass
class AgentConfig:
    """智能体配置"""
    agent_id: str
    name: str
    description: str
    model: str
    system_prompt: Optional[str] = None
    tools: List[str] = None
    memory_enabled: bool = True
    storage_enabled: bool = True
    max_loops: int = 10
    timeout: int = 60
    temperature: float = 0.7
    response_format: ResponseFormat = ResponseFormat.TEXT
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class SessionInfo:
    """会话信息"""
    session_id: str
    user_id: str
    agent_id: str
    created_at: datetime
    last_activity: datetime
    message_count: int
    status: str = "active"
    metadata: Dict[str, Any] = None


class ModelAdapter:
    """模型适配器"""
    
    def __init__(self):
        self.model_configs = {
            "gpt-3.5-turbo": {
                "provider": "openai",
                "api_key": settings.agno_api_key,
                "api_base": settings.agno_api_base
            },
            "gpt-4": {
                "provider": "openai", 
                "api_key": settings.agno_api_key,
                "api_base": settings.agno_api_base
            }
        }
    
    def get_agno_model(self, model_name: str, **kwargs):
        """获取Agno模型实例"""
        if not AGNO_AVAILABLE:
            return None
            
        config = self.model_configs.get(model_name, {})
        
        if config.get("provider") == "openai":
            return OpenAIChat(
                id=model_name,
                api_key=config.get("api_key"),
                base_url=config.get("api_base"),
                **kwargs
            )
        
        return None


class AgnoIntegration:
    """Agno框架集成服务"""
    
    def __init__(self):
        self.is_available = AGNO_AVAILABLE
        self.model_adapter = ModelAdapter()
        self.agents: Dict[str, AgnoAgent] = {}
        self.agent_configs: Dict[str, AgentConfig] = {}
        self.teams: Dict[str, AgnoTeam] = {}
        self.sessions: Dict[str, SessionInfo] = {}
        self._initialized = False
        
    async def initialize(self):
        """初始化Agno集成"""
        if self._initialized:
            return
            
        try:
            if not self.is_available:
                logger.warning("Agno框架不可用，使用降级模式")
                self._initialized = True
                return
                
            logger.info("初始化Agno框架集成...")
            
            # 创建默认智能体
            await self._create_default_agents()
            
            # 初始化内存和存储
            await self._setup_memory_storage()
            
            self._initialized = True
            logger.info("Agno框架集成初始化完成")
            
        except Exception as e:
            logger.error(f"Agno框架集成初始化失败: {e}")
            raise
    
    async def _create_default_agents(self):
        """创建默认智能体"""
        try:
            # 通用聊天智能体
            general_config = AgentConfig(
                agent_id="general-chat",
                name="通用聊天助手",
                description="提供通用对话能力的智能助手",
                model=settings.default_model,
                system_prompt="你是一个友好、专业的AI助手，能够回答各种问题并提供帮助。请用中文回复。",
                tools=["reasoning"],
                temperature=0.7
            )
            await self.create_agent(general_config)
            
            # 专业分析智能体
            analyst_config = AgentConfig(
                agent_id="analyst",
                name="专业分析师",
                description="提供深度分析和洞察的专业智能体",
                model=settings.default_model,
                system_prompt="你是一个专业的分析师，擅长数据分析、趋势预测和深度洞察。请用中文回复。",
                tools=["reasoning"],
                temperature=0.3
            )
            await self.create_agent(analyst_config)
            
            # 创意助手
            creative_config = AgentConfig(
                agent_id="creative",
                name="创意助手",
                description="提供创意写作和头脑风暴的智能体",
                model=settings.default_model,
                system_prompt="你是一个富有创造力的AI助手，擅长创意写作、头脑风暴和艺术创作。请用中文回复。",
                tools=["reasoning"],
                temperature=0.9
            )
            await self.create_agent(creative_config)
            
            logger.info("默认智能体创建完成")
            
        except Exception as e:
            logger.error(f"创建默认智能体失败: {e}")
    
    async def _setup_memory_storage(self):
        """设置内存和存储"""
        try:
            # 配置Agno的内存和存储选项
            # 这里可以根据需要配置持久化存储
            logger.info("内存和存储设置完成")
        except Exception as e:
            logger.error(f"设置内存和存储失败: {e}")
    
    async def create_agent(self, config: AgentConfig) -> str:
        """创建智能体"""
        try:
            if not self.is_available:
                return self._create_mock_agent(config)
            
            # 获取模型实例
            model = self.model_adapter.get_agno_model(
                config.model,
                temperature=config.temperature
            )
            
            if not model:
                raise ValueError(f"无法创建模型: {config.model}")
            
            # 准备工具
            tools = []
            if config.tools and "reasoning" in config.tools:
                tools.append(ReasoningTools())
            
            # 创建Agno智能体
            agent = AgnoAgent(
                name=config.name,
                description=config.description,
                model=model,
                instructions=config.system_prompt,
                tools=tools,
                show_tool_calls=True,
                markdown=True
            )
            
            self.agents[config.agent_id] = agent
            self.agent_configs[config.agent_id] = config
            
            logger.info(f"智能体 {config.agent_id} 创建成功")
            return config.agent_id
            
        except Exception as e:
            logger.error(f"创建智能体失败: {e}")
            raise
    
    def _create_mock_agent(self, config: AgentConfig) -> str:
        """创建模拟智能体（降级模式）"""
        mock_agent = {
            "config": config,
            "created_at": datetime.now().isoformat()
        }
        self.agents[config.agent_id] = mock_agent
        self.agent_configs[config.agent_id] = config
        return config.agent_id
    
    async def create_chat_session(
        self, 
        user_id: str,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> str:
        """创建聊天会话"""
        try:
            session_id = session_id or str(uuid.uuid4())
            agent_id = agent_id or "general-chat"
            
            if agent_id not in self.agents:
                raise ValueError(f"智能体 {agent_id} 不存在")
            
            session_info = SessionInfo(
                session_id=session_id,
                user_id=user_id,
                agent_id=agent_id,
                created_at=datetime.now(),
                last_activity=datetime.now(),
                message_count=0,
                status="active"
            )
            
            self.sessions[session_id] = session_info
            
            # 缓存会话信息到Redis
            await self._cache_session(session_info)
            
            logger.info(f"聊天会话 {session_id} 创建成功")
            return session_id
            
        except Exception as e:
            logger.error(f"创建聊天会话失败: {e}")
            raise
    
    async def send_message(
        self,
        session_id: str,
        message: str,
        role: MessageRole = MessageRole.USER,
        stream: bool = False
    ) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        """发送消息并获取响应"""
        try:
            if session_id not in self.sessions:
                raise ValueError(f"会话 {session_id} 不存在")
            
            session_info = self.sessions[session_id]
            agent_id = session_info.agent_id
            
            # 创建用户消息
            user_message = ChatMessage(
                message_id=str(uuid.uuid4()),
                session_id=session_id,
                role=role,
                content=message,
                timestamp=datetime.now(),
                agent_id=agent_id
            )
            
            # 保存用户消息
            await self._save_message(user_message)
            
            # 更新会话信息
            session_info.last_activity = datetime.now()
            session_info.message_count += 1
            await self._cache_session(session_info)
            
            # 获取智能体响应
            if stream:
                return self._stream_agent_response(agent_id, session_id, message)
            else:
                response = await self._get_agent_response(agent_id, session_id, message)
                
                # 创建助手消息
                assistant_message = ChatMessage(
                    message_id=str(uuid.uuid4()),
                    session_id=session_id,
                    role=MessageRole.ASSISTANT,
                    content=response,
                    timestamp=datetime.now(),
                    agent_id=agent_id
                )
                
                # 保存助手消息
                await self._save_message(assistant_message)
                
                return {
                    "success": True,
                    "session_id": session_id,
                    "message_id": assistant_message.message_id,
                    "response": response,
                    "timestamp": assistant_message.timestamp.isoformat(),
                    "agent_id": agent_id
                }
                
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "session_id": session_id
            }
    
    async def _get_agent_response(
        self,
        agent_id: str,
        session_id: str,
        message: str
    ) -> str:
        """获取智能体响应"""
        try:
            if not self.is_available:
                return await self._get_mock_response(message)
            
            agent = self.agents.get(agent_id)
            if not agent:
                raise ValueError(f"智能体 {agent_id} 不存在")
            
            # 构建上下文
            context = await self._build_context(session_id, message)
            
            # 调用Agno智能体
            if hasattr(agent, 'run'):
                response = agent.run(context)
                return str(response) if response else "抱歉，我无法生成回复。"
            else:
                # 降级模式
                return await self._get_mock_response(message)
                
        except Exception as e:
            logger.error(f"获取智能体响应失败: {e}")
            return f"抱歉，处理您的请求时出现错误: {str(e)}"
    
    async def _stream_agent_response(
        self,
        agent_id: str,
        session_id: str,
        message: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """流式获取智能体响应"""
        try:
            if not self.is_available:
                async for chunk in self._get_mock_stream_response(message):
                    yield chunk
                return
            
            agent = self.agents.get(agent_id)
            if not agent:
                yield {
                    "success": False,
                    "error": f"智能体 {agent_id} 不存在",
                    "session_id": session_id
                }
                return
            
            # 构建上下文
            context = await self._build_context(session_id, message)
            
            # 模拟流式响应（需要根据实际Agno API调整）
            response_text = ""
            if hasattr(agent, 'run'):
                full_response = agent.run(context)
                response_text = str(full_response) if full_response else "抱歉，我无法生成回复。"
            else:
                response_text = await self._get_mock_response(message)
            
            # 分块发送响应
            chunk_size = 50
            for i in range(0, len(response_text), chunk_size):
                chunk = response_text[i:i + chunk_size]
                yield {
                    "success": True,
                    "session_id": session_id,
                    "chunk": chunk,
                    "finished": i + chunk_size >= len(response_text),
                    "agent_id": agent_id
                }
                await asyncio.sleep(0.1)  # 模拟网络延迟
                
        except Exception as e:
            logger.error(f"流式响应失败: {e}")
            yield {
                "success": False,
                "error": str(e),
                "session_id": session_id
            }
    
    async def _get_mock_response(self, message: str) -> str:
        """获取模拟响应"""
        return f"这是对 '{message}' 的模拟回复。Agno框架当前不可用。"
    
    async def _get_mock_stream_response(self, message: str) -> AsyncGenerator[Dict[str, Any], None]:
        """获取模拟流式响应"""
        response = await self._get_mock_response(message)
        chunk_size = 20
        
        for i in range(0, len(response), chunk_size):
            chunk = response[i:i + chunk_size]
            yield {
                "success": True,
                "chunk": chunk,
                "finished": i + chunk_size >= len(response)
            }
            await asyncio.sleep(0.1)
    
    async def _build_context(self, session_id: str, current_message: str) -> str:
        """构建对话上下文"""
        try:
            # 从Redis获取历史消息
            history_key = f"chat_history:{session_id}"
            history_data = redis_manager.get(history_key)
            
            if history_data:
                history = json.loads(history_data)
                context_parts = []
                
                # 添加历史对话（最近10条）
                for msg in history[-10:]:
                    if msg["role"] == "user":
                        context_parts.append(f"用户: {msg['content']}")
                    elif msg["role"] == "assistant":
                        context_parts.append(f"助手: {msg['content']}")
                
                # 添加当前消息
                context_parts.append(f"用户: {current_message}")
                
                return "\n".join(context_parts)
            else:
                return current_message
                
        except Exception as e:
            logger.error(f"构建上下文失败: {e}")
            return current_message
    
    async def _save_message(self, message: ChatMessage):
        """保存消息到Redis"""
        try:
            history_key = f"chat_history:{message.session_id}"
            
            # 获取现有历史
            history_data = redis_manager.get(history_key)
            history = json.loads(history_data) if history_data else []
            
            # 添加新消息
            history.append(message.to_dict())
            
            # 保持最多100条消息
            if len(history) > 100:
                history = history[-100:]
            
            # 保存到Redis，TTL为24小时
            redis_manager.set(
                history_key,
                json.dumps(history, ensure_ascii=False),
                ex=86400
            )
            
        except Exception as e:
            logger.error(f"保存消息失败: {e}")
    
    async def _cache_session(self, session_info: SessionInfo):
        """缓存会话信息"""
        try:
            session_key = f"chat_session:{session_info.session_id}"
            session_data = {
                "session_id": session_info.session_id,
                "user_id": session_info.user_id,
                "agent_id": session_info.agent_id,
                "created_at": session_info.created_at.isoformat(),
                "last_activity": session_info.last_activity.isoformat(),
                "message_count": session_info.message_count,
                "status": session_info.status
            }
            
            redis_manager.set(
                session_key,
                json.dumps(session_data, ensure_ascii=False),
                ex=settings.session_timeout
            )
            
        except Exception as e:
            logger.error(f"缓存会话失败: {e}")
    
    async def get_session_history(self, session_id: str) -> List[Dict[str, Any]]:
        """获取会话历史"""
        try:
            history_key = f"chat_history:{session_id}"
            history_data = redis_manager.get(history_key)
            
            if history_data:
                return json.loads(history_data)
            return []
            
        except Exception as e:
            logger.error(f"获取会话历史失败: {e}")
            return []
    
    async def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        try:
            # 从内存中删除
            if session_id in self.sessions:
                del self.sessions[session_id]
            
            # 从Redis中删除
            history_key = f"chat_history:{session_id}"
            session_key = f"chat_session:{session_id}"
            
            redis_manager.delete(history_key, session_key)
            
            logger.info(f"会话 {session_id} 已删除")
            return True
            
        except Exception as e:
            logger.error(f"删除会话失败: {e}")
            return False
    
    async def get_available_agents(self) -> List[Dict[str, Any]]:
        """获取可用智能体列表"""
        agents = []
        for agent_id, config in self.agent_configs.items():
            agents.append({
                "agent_id": agent_id,
                "name": config.name,
                "description": config.description,
                "model": config.model,
                "tools": config.tools or [],
                "metadata": config.metadata or {}
            })
        return agents
    
    async def get_status(self) -> Dict[str, Any]:
        """获取服务状态"""
        return {
            "agno_available": self.is_available,
            "initialized": self._initialized,
            "agents_count": len(self.agents),
            "active_sessions": len(self.sessions),
            "default_model": settings.default_model,
            "timestamp": datetime.now().isoformat()
        }
    
    async def cleanup(self):
        """清理资源"""
        try:
            # 清理智能体
            self.agents.clear()
            self.agent_configs.clear()
            self.teams.clear()
            self.sessions.clear()
            
            logger.info("Agno集成资源清理完成")
            
        except Exception as e:
            logger.error(f"清理资源失败: {e}")


# 全局Agno集成实例
_agno_integration: Optional[AgnoIntegration] = None


async def get_agno_integration() -> AgnoIntegration:
    """获取Agno集成实例"""
    global _agno_integration
    if _agno_integration is None:
        _agno_integration = AgnoIntegration()
        await _agno_integration.initialize()
    return _agno_integration 