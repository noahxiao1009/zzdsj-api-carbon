"""
Agno框架官方API管理器
直接使用Agno官方API，不进行二次封装
"""
import asyncio
import json
from typing import Dict, List, Any, Optional, AsyncGenerator
from datetime import datetime, timezone
import logging
from dataclasses import dataclass, field

try:
    from agno import Agent, Model
    from agno.models import Claude, OpenAI, Anthropic
    from agno.tools import (
        ReasoningTools, SearchTools, YFinanceTools, 
        WebSearchTools, CalculatorTools, FileTools
    )
    from agno.knowledge import VectorKnowledge
    from agno.memory import AgentMemory
    AGNO_AVAILABLE = True
except ImportError:
    # 如果Agno包未安装，使用模拟实现
    logging.warning("Agno package not installed, using mock implementation")
    AGNO_AVAILABLE = False
    Agent = None
    Model = None

logger = logging.getLogger(__name__)

@dataclass
class AgentExecutionResult:
    """智能体执行结果"""
    success: bool
    response: str
    execution_time: float
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass 
class AgentConfig:
    """智能体配置"""
    name: str
    description: str
    instructions: str
    model_config: Dict[str, Any]
    tools: List[str] = field(default_factory=list)
    knowledge_bases: List[str] = field(default_factory=list)
    memory_enabled: bool = True
    markdown_enabled: bool = True
    max_retries: int = 3
    temperature: float = 0.7
    max_tokens: int = 2000

class AgnoAPIManager:
    """Agno官方API管理器"""
    
    def __init__(self):
        self.agents: Dict[str, Agent] = {}
        self._tool_registry = self._init_tool_registry()
        self._model_registry = self._init_model_registry()
    
    def _init_tool_registry(self) -> Dict[str, Any]:
        """初始化工具注册表"""
        if not AGNO_AVAILABLE:
            return {}
        
        return {
            # 推理工具
            "reasoning": ReasoningTools,
            "search": SearchTools,
            "web_search": WebSearchTools,
            "calculator": CalculatorTools,
            "file_tools": FileTools,
            
            # 专业工具
            "yfinance": YFinanceTools,
            
            # 自定义工具配置
            "reasoning_advanced": lambda: ReasoningTools(
                add_instructions=True,
                enable_caching=True
            ),
            "search_comprehensive": lambda: SearchTools(
                search_type="comprehensive",
                max_results=10
            ),
            "yfinance_stock": lambda: YFinanceTools(
                stock_price=True,
                analyst_recommendations=True,
                company_info=True
            )
        }
    
    def _init_model_registry(self) -> Dict[str, Any]:
        """初始化模型注册表"""
        if not AGNO_AVAILABLE:
            return {}
        
        return {
            # Claude模型
            "claude-3-5-sonnet": lambda: Claude(id="claude-3-5-sonnet-20241022"),
            "claude-3-opus": lambda: Claude(id="claude-3-opus-20240229"),
            "claude-3-haiku": lambda: Claude(id="claude-3-haiku-20240307"),
            "claude-sonnet-4": lambda: Claude(id="claude-sonnet-4-20250514"),
            
            # OpenAI模型
            "gpt-4": lambda: OpenAI(id="gpt-4"),
            "gpt-4o": lambda: OpenAI(id="gpt-4o"),
            "gpt-4o-mini": lambda: OpenAI(id="gpt-4o-mini"),
            
            # Anthropic模型
            "anthropic-claude": lambda: Anthropic(id="claude-3-5-sonnet-20241022")
        }
    
    async def create_agent(self, config: AgentConfig) -> str:
        """创建智能体"""
        if not AGNO_AVAILABLE:
            logger.warning("Agno not available, returning mock agent ID")
            agent_id = f"mock_agent_{len(self.agents)}"
            self.agents[agent_id] = None
            return agent_id
        
        try:
            # 配置模型
            model_name = config.model_config.get("model_name", "claude-3-5-sonnet")
            if model_name not in self._model_registry:
                raise ValueError(f"Unsupported model: {model_name}")
            
            model = self._model_registry[model_name]()
            
            # 配置工具
            tools = []
            for tool_name in config.tools:
                if tool_name in self._tool_registry:
                    tool = self._tool_registry[tool_name]
                    if callable(tool):
                        tools.append(tool())
                    else:
                        tools.append(tool)
                else:
                    logger.warning(f"Unknown tool: {tool_name}")
            
            # 配置知识库
            knowledge = None
            if config.knowledge_bases:
                # 简化版知识库配置，实际应用中需要根据知识库ID获取具体配置
                knowledge = VectorKnowledge(
                    vector_db="milvus",  # 或其他向量数据库
                    collection_name=config.knowledge_bases[0] if config.knowledge_bases else "default"
                )
            
            # 配置内存
            memory = None
            if config.memory_enabled:
                memory = AgentMemory()
            
            # 创建智能体
            agent = Agent(
                name=config.name,
                description=config.description,
                instructions=config.instructions,
                model=model,
                tools=tools,
                knowledge=knowledge,
                memory=memory,
                markdown=config.markdown_enabled
            )
            
            agent_id = f"agent_{len(self.agents)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.agents[agent_id] = agent
            
            logger.info(f"Created agent {agent_id} with model {model_name}")
            return agent_id
            
        except Exception as e:
            logger.error(f"Failed to create agent: {str(e)}")
            raise
    
    async def run_agent(
        self, 
        agent_id: str, 
        message: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        stream: bool = False
    ) -> AgentExecutionResult:
        """运行智能体"""
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not found")
        
        if not AGNO_AVAILABLE:
            # 模拟执行
            await asyncio.sleep(0.1)  # 模拟执行时间
            return AgentExecutionResult(
                success=True,
                response=f"Mock response for: {message}",
                execution_time=0.1,
                session_id=session_id,
                user_id=user_id,
                metadata={"mock": True}
            )
        
        agent = self.agents[agent_id]
        start_time = datetime.now()
        
        try:
            # 使用Agno官方API执行
            if stream:
                # 流式执行
                response_chunks = []
                async for chunk in agent.arun(
                    message, 
                    user_id=user_id,
                    session_id=session_id,
                    stream=True
                ):
                    response_chunks.append(chunk)
                response = "".join(response_chunks)
            else:
                # 普通执行
                response = await agent.arun(
                    message,
                    user_id=user_id,
                    session_id=session_id
                )
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return AgentExecutionResult(
                success=True,
                response=response,
                execution_time=execution_time,
                session_id=session_id,
                user_id=user_id,
                metadata={
                    "agent_id": agent_id,
                    "stream": stream,
                    "tools_used": len(agent.tools) if hasattr(agent, 'tools') else 0
                }
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Agent execution failed: {str(e)}")
            
            return AgentExecutionResult(
                success=False,
                response="",
                execution_time=execution_time,
                session_id=session_id,
                user_id=user_id,
                error=str(e),
                metadata={"agent_id": agent_id}
            )
    
    async def run_agent_stream(
        self,
        agent_id: str,
        message: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """流式运行智能体"""
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not found")
        
        if not AGNO_AVAILABLE:
            # 模拟流式响应
            mock_response = f"Mock streaming response for: {message}"
            for i, char in enumerate(mock_response):
                yield char
                if i % 10 == 0:  # 每10个字符暂停一下
                    await asyncio.sleep(0.01)
            return
        
        agent = self.agents[agent_id]
        
        try:
            async for chunk in agent.arun(
                message,
                user_id=user_id,
                session_id=session_id,
                stream=True
            ):
                yield chunk
                
        except Exception as e:
            logger.error(f"Streaming execution failed: {str(e)}")
            yield f"Error: {str(e)}"
    
    async def update_agent_tools(self, agent_id: str, tools: List[str]) -> bool:
        """更新智能体工具"""
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not found")
        
        if not AGNO_AVAILABLE:
            return True
        
        agent = self.agents[agent_id]
        
        try:
            # 配置新工具
            new_tools = []
            for tool_name in tools:
                if tool_name in self._tool_registry:
                    tool = self._tool_registry[tool_name]
                    if callable(tool):
                        new_tools.append(tool())
                    else:
                        new_tools.append(tool)
            
            # 使用Agno API更新工具
            agent.set_tools(new_tools)
            
            logger.info(f"Updated tools for agent {agent_id}: {tools}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update agent tools: {str(e)}")
            return False
    
    async def add_agent_tool(self, agent_id: str, tool_name: str) -> bool:
        """添加单个工具到智能体"""
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not found")
        
        if not AGNO_AVAILABLE:
            return True
        
        agent = self.agents[agent_id]
        
        try:
            if tool_name in self._tool_registry:
                tool = self._tool_registry[tool_name]
                if callable(tool):
                    agent.add_tool(tool())
                else:
                    agent.add_tool(tool)
                
                logger.info(f"Added tool {tool_name} to agent {agent_id}")
                return True
            else:
                logger.warning(f"Unknown tool: {tool_name}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to add tool: {str(e)}")
            return False
    
    async def get_agent_info(self, agent_id: str) -> Dict[str, Any]:
        """获取智能体信息"""
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not found")
        
        if not AGNO_AVAILABLE:
            return {
                "agent_id": agent_id,
                "name": "Mock Agent",
                "status": "active",
                "mock": True
            }
        
        agent = self.agents[agent_id]
        
        return {
            "agent_id": agent_id,
            "name": getattr(agent, 'name', 'Unknown'),
            "description": getattr(agent, 'description', ''),
            "model": str(getattr(agent, 'model', 'Unknown')),
            "tools_count": len(getattr(agent, 'tools', [])),
            "memory_enabled": hasattr(agent, 'memory') and agent.memory is not None,
            "knowledge_enabled": hasattr(agent, 'knowledge') and agent.knowledge is not None,
            "status": "active"
        }
    
    async def delete_agent(self, agent_id: str) -> bool:
        """删除智能体"""
        if agent_id not in self.agents:
            return False
        
        del self.agents[agent_id]
        logger.info(f"Deleted agent {agent_id}")
        return True
    
    async def list_agents(self) -> List[Dict[str, Any]]:
        """列出所有智能体"""
        agents_info = []
        for agent_id in self.agents.keys():
            try:
                info = await self.get_agent_info(agent_id)
                agents_info.append(info)
            except Exception as e:
                logger.warning(f"Failed to get info for agent {agent_id}: {str(e)}")
        
        return agents_info
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """获取可用工具列表"""
        tools = []
        for tool_name, tool_class in self._tool_registry.items():
            tools.append({
                "name": tool_name,
                "description": f"Tool: {tool_name}",
                "category": "general",  # 可以根据实际情况分类
                "available": AGNO_AVAILABLE
            })
        
        return tools
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """获取可用模型列表"""
        models = []
        for model_name, model_class in self._model_registry.items():
            models.append({
                "name": model_name,
                "provider": model_name.split('-')[0],
                "description": f"Model: {model_name}",
                "available": AGNO_AVAILABLE
            })
        
        return models

# 全局实例
agno_manager = AgnoAPIManager()