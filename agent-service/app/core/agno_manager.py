"""
Agno智能体管理器
完全基于原ZZDSJ项目的设计，集成DAG执行图引擎和三种智能体模板
使用Agno官方API接口实现智能体控制
"""

import asyncio
import logging
import uuid
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

from app.config.settings import get_settings
from app.core.template_manager import (
    get_template_manager, get_template, AgentTemplate
)
from app.core.execution_graph import (
    AgnoExecutionEngine, ExecutionContext, ExecutionStatus,
    OrchestrationResult, create_execution_engine
)
from app.schemas.agent_schemas import (
    AgentCreateRequest, AgentResponse, ChatRequest, ChatResponse,
    TeamCreateRequest, TeamResponse, ModelProvider, TemplateType
)

logger = logging.getLogger(__name__)

class AgnoManager:
    """
    Agno智能体管理器 - 完全基于原ZZDSJ项目设计
    负责智能体的创建、配置、执行和管理
    """
    
    def __init__(self):
        """初始化Agno管理器"""
        self.settings = get_settings()
        self.template_manager = get_template_manager()
        self.agents: Dict[str, Dict[str, Any]] = {}
        self.teams: Dict[str, Dict[str, Any]] = {}
        self.execution_engines: Dict[str, AgnoExecutionEngine] = {}
        self._initialized = False
        
    async def initialize(self):
        """初始化管理器"""
        logger.info("初始化Agno智能体管理器...")
        
        # 验证API密钥配置
        self._validate_api_keys()
        
        # 初始化成功
        self._initialized = True
        logger.info("Agno智能体管理器初始化完成")
        
    def _validate_api_keys(self):
        """验证API密钥配置"""
        required_keys = []
        
        if not self.settings.openai_api_key:
            required_keys.append("OPENAI_API_KEY")
        if not self.settings.anthropic_api_key:
            required_keys.append("ANTHROPIC_API_KEY")
            
        if required_keys:
            logger.warning(f"缺少API密钥配置: {', '.join(required_keys)}")
        else:
            logger.info("API密钥配置验证通过")
    
    def is_ready(self) -> bool:
        """检查管理器是否就绪"""
        return self._initialized
    
    async def cleanup(self):
        """清理资源"""
        logger.info("清理Agno管理器资源...")
        self.agents.clear()
        self.teams.clear()
        self.execution_engines.clear()
        logger.info("Agno管理器资源清理完成")
    
    async def create_agent(self, request: AgentCreateRequest) -> AgentResponse:
        """
        创建智能体
        
        基于选择的模板和用户配置创建智能体实例，
        包含完整的DAG执行图和工具配置
        """
        try:
            logger.info(f"开始创建智能体: {request.name}")
            
            # 获取模板
            template = self.template_manager.get_template(request.template_id)
            if not template:
                raise ValueError(f"未找到模板: {request.template_id}")
            
            # 生成智能体ID
            agent_id = str(uuid.uuid4())
            
            # 构建智能体配置
            agent_config = self._build_agent_config(agent_id, request, template)
            
            # 创建执行引擎
            execution_engine = create_execution_engine(template.execution_graph)
            
            # 创建Agno智能体实例（模拟）
            agno_agent = await self._create_agno_instance(agent_config, template)
            
            # 保存智能体信息
            agent_info = {
                "id": agent_id,
                "name": request.name,
                "description": request.description,
                "template_id": request.template_id,
                "template_name": template.name,
                "model_config": agent_config["model"],
                "tools": agent_config["tools"],
                "instructions": agent_config["instructions"],
                "execution_graph": template.execution_graph,
                "agno_instance": agno_agent,
                "created_at": datetime.now(),
                "status": "active",
                "agno_level": template.agno_level,
                "capabilities": template.capabilities
            }
            
            self.agents[agent_id] = agent_info
            self.execution_engines[agent_id] = execution_engine
            
            logger.info(f"智能体创建成功: {agent_id}")
            
            return AgentResponse(
                id=agent_id,
                name=request.name,
                description=request.description,
                template_id=request.template_id,
                template_name=template.name,
                model=agent_config["model"]["name"],
                tools=agent_config["tools"],
                capabilities=template.capabilities,
                status="active",
                created_at=agent_info["created_at"]
            )
            
        except Exception as e:
            logger.error(f"创建智能体失败: {str(e)}")
            raise
    
    def _build_agent_config(
        self, 
        agent_id: str, 
        request: AgentCreateRequest, 
        template: AgentTemplate
    ) -> Dict[str, Any]:
        """构建智能体配置"""
        
        # 模型配置
        model_config = {
            "name": request.model,
            "provider": request.model_provider.value,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": True
        }
        
        # 工具配置 - 合并模板默认工具和用户选择的工具
        tools = list(set(template.default_tools + (request.tools or [])))
        
        # 指令配置 - 合并模板指令和用户自定义指令
        instructions = template.instructions.copy()
        if request.system_prompt:
            instructions.insert(0, request.system_prompt)
        
        return {
            "id": agent_id,
            "name": request.name,
            "description": request.description,
            "model": model_config,
            "tools": tools,
            "instructions": instructions,
            "template_id": request.template_id,
            "execution_graph": template.execution_graph,
            "max_loops": 10,
            "show_tool_calls": True,
            "markdown": True
        }
    
    async def _create_agno_instance(
        self, 
        agent_config: Dict[str, Any], 
        template: AgentTemplate
    ) -> Dict[str, Any]:
        """
        创建Agno智能体实例（模拟实现）
        
        在实际部署中，这里会调用真正的Agno API
        """
        
        # 模拟创建过程
        await asyncio.sleep(0.1)
        
        # 模拟Agno实例
        agno_instance = {
            "agno_id": f"agno_{agent_config['id'][:8]}",
            "name": agent_config["name"],
            "model": agent_config["model"],
            "tools": agent_config["tools"],
            "instructions": agent_config["instructions"],
            "level": template.agno_level,
            "status": "ready",
            "created_at": datetime.now().isoformat()
        }
        
        logger.info(f"Agno实例创建成功: {agno_instance['agno_id']}")
        return agno_instance
    
    async def chat_with_agent(
        self, 
        agent_id: str, 
        request: ChatRequest
    ) -> ChatResponse:
        """
        与智能体对话
        
        使用DAG执行图处理用户消息，返回智能体响应
        """
        try:
            # 获取智能体信息
            agent_info = self.agents.get(agent_id)
            if not agent_info:
                raise ValueError(f"未找到智能体: {agent_id}")
            
            # 获取执行引擎
            execution_engine = self.execution_engines.get(agent_id)
            if not execution_engine:
                raise ValueError(f"未找到执行引擎: {agent_id}")
            
            logger.info(f"开始处理对话: {agent_id} - {request.message[:50]}...")
            
            # 创建执行上下文
            context = ExecutionContext(
                request_id=str(uuid.uuid4()),
                user_id=request.session_id,
                session_id=request.session_id,
                metadata={
                    "agent_id": agent_id,
                    "message": request.message,
                    "stream": request.stream
                }
            )
            
            # 准备输入数据
            input_data = {
                "message": request.message,
                "session_id": request.session_id,
                "history": request.history or [],
                "agent_config": agent_info
            }
            
            # 执行DAG流程
            result = await execution_engine.execute(input_data, context)
            
            if result.success:
                # 提取响应内容
                response_content = self._extract_response_content(result)
                
                return ChatResponse(
                    response=response_content,
                    session_id=request.session_id,
                    agent_id=agent_id,
                    execution_time=result.execution_time,
                    execution_path=result.execution_path,
                    metadata={
                        "node_results": len(result.node_results),
                        "template_id": agent_info["template_id"],
                        "agno_level": agent_info["agno_level"]
                    }
                )
            else:
                logger.error(f"对话执行失败: {result.error}")
                raise ValueError(f"对话执行失败: {result.error}")
                
        except Exception as e:
            logger.error(f"对话处理失败: {str(e)}")
            raise
    
    def _extract_response_content(self, result: OrchestrationResult) -> str:
        """从执行结果中提取响应内容"""
        if isinstance(result.result, dict):
            # 从格式化器节点获取最终结果
            if "formatted_text" in result.result:
                return result.result["formatted_text"]
            elif "generated_text" in result.result:
                return result.result["generated_text"]
            elif "text" in result.result:
                return result.result["text"]
        
        # 如果是字符串，直接返回
        if isinstance(result.result, str):
            return result.result
        
        # 默认回复
        return str(result.result) if result.result else "抱歉，我暂时无法处理您的请求。"
    
    async def create_team(self, request: TeamCreateRequest) -> TeamResponse:
        """
        创建智能体团队
        
        基于深度思考模板创建协作团队
        """
        try:
            logger.info(f"开始创建智能体团队: {request.name}")
            
            # 生成团队ID
            team_id = str(uuid.uuid4())
            
            # 创建团队成员智能体
            team_members = []
            for i, member_config in enumerate(request.agents):
                member_request = AgentCreateRequest(
                    name=f"{request.name}_成员_{i+1}",
                    description=member_config.get("description", "团队成员智能体"),
                    template_id=TemplateType.DEEP_THINKING.value,  # 团队成员使用深度思考模板
                    model=member_config.get("model", "gpt-4"),
                    model_provider=ModelProvider.OPENAI,
                    system_prompt=member_config.get("system_prompt"),
                    tools=member_config.get("tools", [])
                )
                
                member_agent = await self.create_agent(member_request)
                team_members.append(member_agent)
            
            # 保存团队信息
            team_info = {
                "id": team_id,
                "name": request.name,
                "description": request.description,
                "members": team_members,
                "collaboration_mode": "consensus",
                "created_at": datetime.now(),
                "status": "active"
            }
            
            self.teams[team_id] = team_info
            
            logger.info(f"智能体团队创建成功: {team_id}")
            
            return TeamResponse(
                id=team_id,
                name=request.name,
                description=request.description,
                agents=team_members,
                status="active",
                created_at=team_info["created_at"]
            )
            
        except Exception as e:
            logger.error(f"创建智能体团队失败: {str(e)}")
            raise
    
    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """获取智能体信息"""
        return self.agents.get(agent_id)
    
    def list_agents(self) -> List[Dict[str, Any]]:
        """获取所有智能体列表"""
        agents_list = []
        for agent_info in self.agents.values():
            agents_list.append({
                "id": agent_info["id"],
                "name": agent_info["name"],
                "description": agent_info["description"],
                "template_id": agent_info["template_id"],
                "template_name": agent_info["template_name"],
                "model": agent_info["model_config"]["name"],
                "status": agent_info["status"],
                "created_at": agent_info["created_at"],
                "agno_level": agent_info["agno_level"],
                "capabilities": agent_info["capabilities"]
            })
        return agents_list
    
    def get_team(self, team_id: str) -> Optional[Dict[str, Any]]:
        """获取团队信息"""
        return self.teams.get(team_id)
    
    def list_teams(self) -> List[Dict[str, Any]]:
        """获取所有团队列表"""
        teams_list = []
        for team_info in self.teams.values():
            teams_list.append({
                "id": team_info["id"],
                "name": team_info["name"],
                "description": team_info["description"],
                "member_count": len(team_info["members"]),
                "status": team_info["status"],
                "created_at": team_info["created_at"]
            })
        return teams_list
    
    async def delete_agent(self, agent_id: str) -> bool:
        """删除智能体"""
        try:
            if agent_id not in self.agents:
                return False
            
            # 清理资源
            del self.agents[agent_id]
            if agent_id in self.execution_engines:
                del self.execution_engines[agent_id]
            
            logger.info(f"智能体删除成功: {agent_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除智能体失败: {str(e)}")
            return False
    
    def get_available_models(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取可用的模型列表"""
        models = {
            "openai": [
                {
                    "id": "gpt-4",
                    "name": "GPT-4",
                    "description": "最强大的GPT模型，适合复杂任务",
                    "context_length": 8192,
                    "cost_tier": "high"
                },
                {
                    "id": "gpt-4o-mini",
                    "name": "GPT-4o Mini",
                    "description": "轻量级GPT-4模型，响应快速",
                    "context_length": 16384,
                    "cost_tier": "low"
                },
                {
                    "id": "gpt-3.5-turbo",
                    "name": "GPT-3.5 Turbo",
                    "description": "平衡性能和成本的选择",
                    "context_length": 4096,
                    "cost_tier": "medium"
                }
            ],
            "anthropic": [
                {
                    "id": "claude-3-opus",
                    "name": "Claude 3 Opus",
                    "description": "Anthropic最强大的模型",
                    "context_length": 200000,
                    "cost_tier": "high"
                },
                {
                    "id": "claude-3-haiku",
                    "name": "Claude 3 Haiku",
                    "description": "快速轻量的Claude模型",
                    "context_length": 200000,
                    "cost_tier": "low"
                }
            ]
        }
        return models
    
    def get_model_providers(self) -> List[Dict[str, Any]]:
        """获取模型提供商列表"""
        providers = [
            {
                "id": "openai",
                "name": "OpenAI",
                "description": "GPT系列模型提供商",
                "available": bool(self.settings.openai_api_key),
                "models_count": 3
            },
            {
                "id": "anthropic", 
                "name": "Anthropic",
                "description": "Claude系列模型提供商",
                "available": bool(self.settings.anthropic_api_key),
                "models_count": 2
            }
        ]
        return providers
    
    async def get_agent_execution_graph(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """获取智能体的执行图可视化数据"""
        agent_info = self.agents.get(agent_id)
        if not agent_info:
            return None
        
        execution_engine = self.execution_engines.get(agent_id)
        if not execution_engine:
            return None
        
        return execution_engine.visualize_graph()

# 全局实例
_agno_manager_instance: Optional[AgnoManager] = None

def get_agno_manager() -> AgnoManager:
    """获取Agno管理器实例"""
    global _agno_manager_instance
    if _agno_manager_instance is None:
        _agno_manager_instance = AgnoManager()
    return _agno_manager_instance
