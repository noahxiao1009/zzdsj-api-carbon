"""
智能体基础类
"""
import asyncio
import json
import inspect
import time
from typing import List, Dict, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor
from abc import ABC, abstractmethod
from app.models.agent import AgentModel, AgentStatus, AgentType
from app.config.settings import settings
from app.utils.logging import get_logger


logger = get_logger(__name__)


class ToolCall:
    """工具调用"""
    
    def __init__(self, id: str, function_name: str, arguments: str):
        self.id = id
        self.function_name = function_name
        self.arguments = arguments


class LLMResponse:
    """LLM响应"""
    
    def __init__(self, content: str, tool_calls: List[ToolCall] = None):
        self.content = content
        self.tool_calls = tool_calls or []


class BaseAgent(ABC):
    """基础智能体类"""
    
    def __init__(self, agent_model: AgentModel, llm_client, functions: Dict[str, Callable] = None):
        self.agent_model = agent_model
        self.llm_client = llm_client
        self.functions = functions or {}
        self.tools = []
        self.history = []
        self.execution_stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "total_time": 0,
        }
        
        # 初始化工具
        self._initialize_tools()
    
    def _initialize_tools(self):
        """初始化工具"""
        if self.agent_model.tools:
            for tool_config in self.agent_model.tools:
                self.tools.append(self._create_tool_definition(tool_config))
    
    def _create_tool_definition(self, tool_config: Dict[str, Any]) -> Dict[str, Any]:
        """创建工具定义"""
        return {
            "type": "function",
            "function": {
                "name": tool_config.get("name"),
                "description": tool_config.get("description", ""),
                "parameters": tool_config.get("parameters", {}),
            }
        }
    
    def add_function(self, name: str, func: Callable, description: str = "", parameters: Dict[str, Any] = None):
        """添加函数"""
        self.functions[name] = func
        
        # 创建工具定义
        tool_def = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters or {},
            }
        }
        
        # 检查是否已存在，如果存在则替换
        for i, tool in enumerate(self.tools):
            if tool["function"]["name"] == name:
                self.tools[i] = tool_def
                return
        
        self.tools.append(tool_def)
    
    def remove_function(self, name: str):
        """移除函数"""
        if name in self.functions:
            del self.functions[name]
        
        # 移除工具定义
        self.tools = [tool for tool in self.tools if tool["function"]["name"] != name]
    
    async def execute(self, messages: List[Dict[str, Any]], max_iteration: int = None, **kwargs) -> str:
        """执行智能体"""
        if max_iteration is None:
            max_iteration = self.agent_model.max_iteration
        
        self.agent_model.update_status(AgentStatus.BUSY)
        start_time = time.time()
        
        try:
            result = await self._execute_with_tools(messages, max_iteration, **kwargs)
            
            # 更新统计信息
            execution_time = int((time.time() - start_time) * 1000)
            self.execution_stats["total_calls"] += 1
            self.execution_stats["successful_calls"] += 1
            self.execution_stats["total_time"] += execution_time
            
            self.agent_model.increment_execution(success=True)
            self.agent_model.update_status(AgentStatus.IDLE)
            
            return result
            
        except Exception as e:
            # 更新统计信息
            execution_time = int((time.time() - start_time) * 1000)
            self.execution_stats["total_calls"] += 1
            self.execution_stats["failed_calls"] += 1
            self.execution_stats["total_time"] += execution_time
            
            self.agent_model.increment_execution(success=False)
            self.agent_model.update_status(AgentStatus.ERROR)
            
            logger.error(f"智能体执行失败: {str(e)}", exc_info=True)
            raise
    
    async def _execute_with_tools(self, messages: List[Dict[str, Any]], max_iteration: int, **kwargs) -> str:
        """使用工具执行"""
        for iteration in range(max_iteration):
            logger.info(f"智能体 {self.agent_model.name} 第 {iteration + 1} 次迭代")
            
            # 调用LLM
            response = await self._call_llm(messages, self.tools)
            
            # 处理响应
            result = await self._process_response(response, messages, **kwargs)
            
            if result:
                return result
        
        # 达到最大迭代次数
        return await self._handle_max_iteration(messages, **kwargs)
    
    async def _call_llm(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> LLMResponse:
        """调用LLM"""
        try:
            # 这里需要根据具体的LLM客户端实现
            # 假设返回LLMResponse对象
            response = await self.llm_client.create_completion(
                messages=messages,
                tools=tools,
                **self.agent_model.model_config
            )
            return response
        except Exception as e:
            logger.error(f"调用LLM失败: {str(e)}")
            raise
    
    async def _process_response(self, response: LLMResponse, messages: List[Dict[str, Any]], **kwargs) -> Optional[str]:
        """处理响应"""
        if not response.tool_calls:
            # 没有工具调用，直接返回内容
            messages.append({"role": "assistant", "content": response.content})
            return response.content
        
        # 有工具调用，处理工具调用
        messages.append({
            "role": "assistant",
            "content": response.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function_name,
                        "arguments": tc.arguments
                    }
                } for tc in response.tool_calls
            ]
        })
        
        # 执行工具调用
        tool_results = await self._execute_tool_calls(response.tool_calls, **kwargs)
        messages.extend(tool_results)
        
        # 检查终止条件
        for result in tool_results:
            if result.get("name") in self.get_termination_tools():
                return result["content"]
        
        return None
    
    async def _execute_tool_calls(self, tool_calls: List[ToolCall], **kwargs) -> List[Dict[str, Any]]:
        """执行工具调用"""
        results = []
        
        # 使用线程池执行工具调用
        with ThreadPoolExecutor(max_workers=settings.max_concurrent_tasks) as executor:
            futures = []
            
            for tool_call in tool_calls:
                future = executor.submit(
                    self._execute_single_tool_call,
                    tool_call,
                    **kwargs
                )
                futures.append(future)
            
            # 等待所有工具调用完成
            for future in futures:
                try:
                    result = future.result(timeout=settings.task_timeout)
                    results.append(result)
                except Exception as e:
                    logger.error(f"工具调用失败: {str(e)}")
                    results.append({
                        "role": "tool",
                        "name": tool_call.function_name,
                        "tool_call_id": tool_call.id,
                        "content": f"执行错误: {str(e)}"
                    })
        
        return results
    
    def _execute_single_tool_call(self, tool_call: ToolCall, **kwargs) -> Dict[str, Any]:
        """执行单个工具调用"""
        try:
            # 解析参数
            args_dict = json.loads(tool_call.arguments or "{}")
            
            # 添加额外参数
            for key, value in kwargs.items():
                if key not in args_dict:
                    args_dict[key] = value
            
            # 检查函数是否存在
            if tool_call.function_name not in self.functions:
                return {
                    "role": "tool",
                    "name": tool_call.function_name,
                    "tool_call_id": tool_call.id,
                    "content": f"函数 {tool_call.function_name} 不存在"
                }
            
            function_to_call = self.functions[tool_call.function_name]
            
            # 执行函数
            if inspect.iscoroutinefunction(function_to_call):
                # 异步函数
                loop = asyncio.new_event_loop()
                try:
                    asyncio.set_event_loop(loop)
                    result = loop.run_until_complete(function_to_call(**args_dict))
                finally:
                    loop.close()
            else:
                # 同步函数
                result = function_to_call(**args_dict)
            
            return {
                "role": "tool",
                "name": tool_call.function_name,
                "tool_call_id": tool_call.id,
                "content": str(result)
            }
            
        except Exception as e:
            logger.error(f"工具 {tool_call.function_name} 执行失败: {str(e)}")
            return {
                "role": "tool",
                "name": tool_call.function_name,
                "tool_call_id": tool_call.id,
                "content": f"执行错误: {str(e)}"
            }
    
    async def _handle_max_iteration(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """处理最大迭代次数"""
        # 添加总结提示
        messages.append({
            "role": "user",
            "content": "请总结上述对话内容，并提供最终结果。"
        })
        
        # 只使用终止工具
        termination_tools = [
            tool for tool in self.tools 
            if tool["function"]["name"] in self.get_termination_tools()
        ]
        
        response = await self._call_llm(messages, termination_tools)
        result = await self._process_response(response, messages, **kwargs)
        
        if result:
            return result
        
        return messages[-1].get("content", "执行完成")
    
    def get_termination_tools(self) -> List[str]:
        """获取终止工具列表"""
        return ["terminate", "mark_step", "finalize"]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.execution_stats,
            "average_time": (
                self.execution_stats["total_time"] / self.execution_stats["total_calls"]
                if self.execution_stats["total_calls"] > 0 else 0
            ),
            "success_rate": (
                self.execution_stats["successful_calls"] / self.execution_stats["total_calls"]
                if self.execution_stats["total_calls"] > 0 else 0
            )
        }
    
    def reset_stats(self):
        """重置统计信息"""
        self.execution_stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "total_time": 0,
        }
    
    def clear_history(self):
        """清除历史记录"""
        self.history = []
    
    def add_to_history(self, role: str, content: str):
        """添加到历史记录"""
        self.history.append({"role": role, "content": content})
    
    def get_history(self) -> List[Dict[str, Any]]:
        """获取历史记录"""
        return self.history.copy()
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        """获取系统提示词"""
        pass
    
    @abstractmethod
    def prepare_messages(self, input_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """准备消息"""
        pass
    
    def __repr__(self):
        return f"<BaseAgent {self.agent_model.name}({self.agent_model.type})>"


class AgentRegistry:
    """智能体注册表"""
    
    _instances = {}
    
    @classmethod
    def register(cls, agent_id: str, agent: BaseAgent):
        """注册智能体"""
        cls._instances[agent_id] = agent
    
    @classmethod
    def unregister(cls, agent_id: str):
        """注销智能体"""
        if agent_id in cls._instances:
            del cls._instances[agent_id]
    
    @classmethod
    def get(cls, agent_id: str) -> Optional[BaseAgent]:
        """获取智能体"""
        return cls._instances.get(agent_id)
    
    @classmethod
    def get_all(cls) -> Dict[str, BaseAgent]:
        """获取所有智能体"""
        return cls._instances.copy()
    
    @classmethod
    def clear(cls):
        """清除所有智能体"""
        cls._instances.clear()


class AgentManager:
    """智能体管理器"""
    
    def __init__(self):
        self.registry = AgentRegistry()
    
    def create_agent(self, agent_model: AgentModel, llm_client, agent_class: type = None) -> BaseAgent:
        """创建智能体"""
        if agent_class is None:
            # 根据类型选择默认的智能体类
            agent_class = self._get_default_agent_class(agent_model.type)
        
        agent = agent_class(agent_model, llm_client)
        self.registry.register(str(agent_model.id), agent)
        
        return agent
    
    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """获取智能体"""
        return self.registry.get(agent_id)
    
    def destroy_agent(self, agent_id: str):
        """销毁智能体"""
        agent = self.registry.get(agent_id)
        if agent:
            agent.agent_model.update_status(AgentStatus.OFFLINE)
            self.registry.unregister(agent_id)
    
    def _get_default_agent_class(self, agent_type: str) -> type:
        """获取默认智能体类"""
        if agent_type == AgentType.PLANNER:
            from app.core.agents.planner import TaskPlannerAgent
            return TaskPlannerAgent
        elif agent_type == AgentType.ACTOR:
            from app.core.agents.actor import TaskActorAgent
            return TaskActorAgent
        else:
            return BaseAgent
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        agents = self.registry.get_all()
        return {
            "total_agents": len(agents),
            "active_agents": len([a for a in agents.values() if a.agent_model.status == AgentStatus.BUSY]),
            "idle_agents": len([a for a in agents.values() if a.agent_model.status == AgentStatus.IDLE]),
            "error_agents": len([a for a in agents.values() if a.agent_model.status == AgentStatus.ERROR]),
            "offline_agents": len([a for a in agents.values() if a.agent_model.status == AgentStatus.OFFLINE]),
        }


# 全局智能体管理器
agent_manager = AgentManager()