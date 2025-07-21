"""
DAG智能体编排器
基于有向无环图的智能体执行流程管理
"""
import asyncio
import json
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
import logging
from collections import defaultdict, deque

from .agno_api_manager import agno_manager, AgentConfig, AgentExecutionResult
from .tool_injection_manager import (
    tool_injection_manager, ToolDefinition, ToolExecutionRequest, 
    ToolCategory, ToolType
)
from .dynamic_dag_generator import (
    dynamic_dag_generator, DAGGenerationRequest, UserPreferences, DAGGenerationMode
)
from .dag_to_agno_converter import (
    dag_to_agno_converter, AgnoAgentInstance, ConversionResult
)

logger = logging.getLogger(__name__)

class NodeType(str, Enum):
    """节点类型"""
    AGENT = "agent"              # 智能体节点
    CONDITION = "condition"      # 条件判断节点
    MERGE = "merge"             # 结果合并节点
    PARALLEL = "parallel"       # 并行执行节点
    SEQUENTIAL = "sequential"   # 顺序执行节点
    INPUT = "input"             # 输入节点
    OUTPUT = "output"           # 输出节点

class ExecutionStatus(str, Enum):
    """执行状态"""
    PENDING = "pending"
    RUNNING = "running"  
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class DAGNode:
    """DAG节点"""
    id: str
    type: NodeType
    name: str
    description: str = ""
    
    # 节点配置
    config: Dict[str, Any] = field(default_factory=dict)
    
    # 依赖关系
    dependencies: List[str] = field(default_factory=list)  # 前置依赖
    dependents: List[str] = field(default_factory=list)    # 后续依赖
    
    # 执行状态
    status: ExecutionStatus = ExecutionStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    execution_time: float = 0.0
    
    # 执行结果
    result: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DAGEdge:
    """DAG边"""
    from_node: str
    to_node: str
    condition: Optional[str] = None  # 条件表达式
    weight: float = 1.0             # 权重
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DAGTemplate:
    """DAG模版"""
    template_id: str
    name: str
    description: str
    category: str
    nodes: List[DAGNode]
    edges: List[DAGEdge]
    
    # 模版配置
    default_config: Dict[str, Any] = field(default_factory=dict)
    variables: Dict[str, Any] = field(default_factory=dict)
    
    # 元数据
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = "1.0"
    tags: List[str] = field(default_factory=list)

@dataclass
class DAGExecution:
    """DAG执行实例"""
    execution_id: str
    template_id: str
    user_id: str
    
    # 执行配置
    input_data: Dict[str, Any] = field(default_factory=dict)
    config_overrides: Dict[str, Any] = field(default_factory=dict)
    
    # 执行状态
    status: ExecutionStatus = ExecutionStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    # 节点执行状态
    node_statuses: Dict[str, ExecutionStatus] = field(default_factory=dict)
    node_results: Dict[str, Any] = field(default_factory=dict)
    node_errors: Dict[str, str] = field(default_factory=dict)
    
    # 执行结果
    final_result: Any = None
    execution_path: List[str] = field(default_factory=list)
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

class DAGOrchestrator:
    """DAG编排器"""
    
    def __init__(self):
        self.templates: Dict[str, DAGTemplate] = {}
        self.executions: Dict[str, DAGExecution] = {}
        self.running_executions: Set[str] = set()
        
        # 工具注入管理器
        self.tool_manager = tool_injection_manager
        self._initialized = False
        
    async def initialize(self):
        """初始化DAG编排器"""
        if self._initialized:
            return
        
        logger.info("初始化DAG编排器...")
        
        try:
            # 初始化工具注入管理器
            await self.tool_manager.initialize()
            
            # 初始化内置模版
            self._init_builtin_templates()
            
            self._initialized = True
            logger.info("DAG编排器初始化完成")
            
        except Exception as e:
            logger.error(f"DAG编排器初始化失败: {e}")
            raise
    
    def _init_builtin_templates(self):
        """初始化内置模版"""
        # 基础对话模版DAG
        basic_template = self._create_basic_conversation_template()
        self.templates[basic_template.template_id] = basic_template
        
        # 知识库问答模版DAG
        knowledge_template = self._create_knowledge_base_template()
        self.templates[knowledge_template.template_id] = knowledge_template
        
        # 深度思考模版DAG
        thinking_template = self._create_deep_thinking_template()
        self.templates[thinking_template.template_id] = thinking_template
    
    def _create_basic_conversation_template(self) -> DAGTemplate:
        """创建基础对话模版DAG"""
        nodes = [
            DAGNode(
                id="input",
                type=NodeType.INPUT,
                name="用户输入",
                description="接收用户输入的消息",
                config={"required_fields": ["message", "user_id"]}
            ),
            DAGNode(
                id="intent_agent",
                type=NodeType.AGENT,
                name="意图识别智能体",
                description="识别用户意图和情感",
                config={
                    "agent_config": {
                        "name": "Intent Recognition Agent",
                        "instructions": "分析用户消息的意图和情感，返回结构化结果",
                        "model_config": {"model_name": "claude-3-haiku"},
                        "tool_categories": ["reasoning"],
                        "tool_types": ["builtin"],
                        "max_tools": 3,
                        "temperature": 0.3,
                        "max_tokens": 500
                    }
                }
            ),
            DAGNode(
                id="response_agent",
                type=NodeType.AGENT,
                name="回复生成智能体",
                description="生成友好的回复",
                config={
                    "agent_config": {
                        "name": "Response Generation Agent", 
                        "instructions": "基于用户意图生成友好、有帮助的回复",
                        "model_config": {"model_name": "claude-3-5-sonnet"},
                        "tool_categories": ["search", "calculation", "reasoning"],
                        "tool_types": ["builtin", "external", "mcp"],
                        "max_tools": 5,
                        "temperature": 0.7,
                        "max_tokens": 1000
                    }
                }
            ),
            DAGNode(
                id="output",
                type=NodeType.OUTPUT,
                name="输出结果",
                description="返回最终结果",
                config={"format": "json"}
            )
        ]
        
        edges = [
            DAGEdge("input", "intent_agent"),
            DAGEdge("intent_agent", "response_agent"),
            DAGEdge("response_agent", "output")
        ]
        
        return DAGTemplate(
            template_id="basic_conversation",
            name="基础对话模版",
            description="快速响应的轻量级对话助手",
            category="conversation",
            nodes=nodes,
            edges=edges,
            default_config={
                "max_execution_time": 30,
                "retry_on_failure": True,
                "max_retries": 2
            },
            tags=["basic", "conversation", "fast"]
        )
    
    def _create_knowledge_base_template(self) -> DAGTemplate:
        """创建知识库问答模版DAG"""
        nodes = [
            DAGNode(
                id="input",
                type=NodeType.INPUT,
                name="问题输入",
                config={"required_fields": ["question", "knowledge_base_ids"]}
            ),
            DAGNode(
                id="query_analysis_agent",
                type=NodeType.AGENT,
                name="查询分析智能体",
                description="分析用户问题，提取关键信息",
                config={
                    "agent_config": {
                        "name": "Query Analysis Agent",
                        "instructions": "分析用户问题，提取关键词和实体，优化检索查询",
                        "model_config": {"model_name": "claude-3-5-sonnet"},
                        "tool_categories": ["reasoning", "analysis"],
                        "tool_types": ["builtin"],
                        "max_tools": 2,
                        "temperature": 0.2
                    }
                }
            ),
            DAGNode(
                id="knowledge_retrieval_agent",
                type=NodeType.AGENT,
                name="知识检索智能体",
                description="从知识库检索相关信息",
                config={
                    "agent_config": {
                        "name": "Knowledge Retrieval Agent",
                        "instructions": "基于分析结果检索相关知识，评估相关性",
                        "model_config": {"model_name": "claude-3-5-sonnet"},
                        "tool_categories": ["search", "reasoning", "data"],
                        "tool_types": ["builtin", "system"],
                        "max_tools": 4,
                        "knowledge_bases": ["default"],  # 将通过变量替换
                        "temperature": 0.1
                    }
                }
            ),
            DAGNode(
                id="answer_synthesis_agent",
                type=NodeType.AGENT,
                name="答案合成智能体",
                description="基于检索结果合成答案",
                config={
                    "agent_config": {
                        "name": "Answer Synthesis Agent",
                        "instructions": "基于检索到的知识合成准确、完整的答案，包含引用",
                        "model_config": {"model_name": "claude-3-5-sonnet"},
                        "tool_categories": ["reasoning", "analysis"],
                        "tool_types": ["builtin"],
                        "max_tools": 3,
                        "temperature": 0.3,
                        "max_tokens": 2000
                    }
                }
            ),
            DAGNode(
                id="confidence_check",
                type=NodeType.CONDITION,
                name="置信度检查",
                description="检查答案置信度",
                config={
                    "condition": "confidence > 0.7",
                    "confidence_threshold": 0.7
                }
            ),
            DAGNode(
                id="output",
                type=NodeType.OUTPUT,
                name="输出答案",
                config={"include_citations": True, "include_confidence": True}
            ),
            DAGNode(
                id="fallback_agent",
                type=NodeType.AGENT,
                name="兜底智能体",
                description="低置信度时的兜底处理",
                config={
                    "agent_config": {
                        "name": "Fallback Agent",
                        "instructions": "当无法找到确切答案时，提供有帮助的建议和相关信息",
                        "model_config": {"model_name": "claude-3-haiku"},
                        "tool_categories": ["search", "reasoning"],
                        "tool_types": ["builtin", "external"],
                        "max_tools": 3,
                        "temperature": 0.5
                    }
                }
            )
        ]
        
        edges = [
            DAGEdge("input", "query_analysis_agent"),
            DAGEdge("query_analysis_agent", "knowledge_retrieval_agent"),
            DAGEdge("knowledge_retrieval_agent", "answer_synthesis_agent"),
            DAGEdge("answer_synthesis_agent", "confidence_check"),
            DAGEdge("confidence_check", "output", condition="confidence >= 0.7"),
            DAGEdge("confidence_check", "fallback_agent", condition="confidence < 0.7"),
            DAGEdge("fallback_agent", "output")
        ]
        
        return DAGTemplate(
            template_id="knowledge_base",
            name="知识库问答模版",
            description="基于知识库的专业问答助手",
            category="knowledge",
            nodes=nodes,
            edges=edges,
            variables={
                "knowledge_base_ids": [],
                "confidence_threshold": 0.7,
                "max_retrieval_results": 5
            },
            tags=["knowledge", "qa", "professional"]
        )
    
    def _create_deep_thinking_template(self) -> DAGTemplate:
        """创建深度思考模版DAG"""
        nodes = [
            DAGNode(
                id="input",
                type=NodeType.INPUT,
                name="任务输入",
                config={"required_fields": ["task", "requirements"]}
            ),
            DAGNode(
                id="task_analysis_agent",
                type=NodeType.AGENT,
                name="任务分析智能体",
                description="分析任务复杂度和要求",
                config={
                    "agent_config": {
                        "name": "Task Analysis Agent",
                        "instructions": "深入分析任务的复杂度、要求和可能的解决方案",
                        "model_config": {"model_name": "claude-3-5-sonnet"},
                        "tool_categories": ["reasoning", "analysis"],
                        "tool_types": ["builtin"],
                        "max_tools": 3,
                        "temperature": 0.3
                    }
                }
            ),
            DAGNode(
                id="complexity_check",
                type=NodeType.CONDITION,
                name="复杂度检查",
                description="判断是否需要团队协作",
                config={
                    "condition": "complexity > 0.8",
                    "complexity_threshold": 0.8
                }
            ),
            DAGNode(
                id="single_agent_solver",
                type=NodeType.AGENT,
                name="单体解决智能体",
                description="处理简单任务",
                config={
                    "agent_config": {
                        "name": "Single Agent Solver",
                        "instructions": "独立分析和解决相对简单的任务",
                        "model_config": {"model_name": "claude-3-5-sonnet"},
                        "tool_categories": ["reasoning", "search", "calculation", "analysis"],
                        "tool_types": ["builtin", "external", "mcp"],
                        "max_tools": 6,
                        "temperature": 0.5,
                        "max_tokens": 3000
                    }
                }
            ),
            DAGNode(
                id="team_coordinator",
                type=NodeType.PARALLEL,
                name="团队协调节点",
                description="协调多个专业智能体",
                config={
                    "max_parallel": 3,
                    "timeout": 120
                }
            ),
            DAGNode(
                id="research_agent",
                type=NodeType.AGENT,
                name="研究智能体",
                description="深度研究和信息收集",
                config={
                    "agent_config": {
                        "name": "Research Agent",
                        "instructions": "进行深入研究，收集和分析相关信息",
                        "model_config": {"model_name": "claude-3-5-sonnet"},
                        "tool_categories": ["search", "reasoning", "content", "data"],
                        "tool_types": ["builtin", "external", "mcp", "system"],
                        "max_tools": 8,
                        "temperature": 0.4
                    }
                }
            ),
            DAGNode(
                id="analysis_agent",
                type=NodeType.AGENT,
                name="分析智能体",
                description="数据分析和洞察发现",
                config={
                    "agent_config": {
                        "name": "Analysis Agent",
                        "instructions": "分析数据，发现模式和洞察",
                        "model_config": {"model_name": "claude-3-5-sonnet"},
                        "tool_categories": ["reasoning", "calculation", "analysis", "data"],
                        "tool_types": ["builtin", "external"],
                        "max_tools": 5,
                        "temperature": 0.3
                    }
                }
            ),
            DAGNode(
                id="planning_agent",
                type=NodeType.AGENT,
                name="规划智能体",
                description="制定解决方案和计划",
                config={
                    "agent_config": {
                        "name": "Planning Agent",
                        "instructions": "基于研究和分析结果制定详细的解决方案",
                        "model_config": {"model_name": "claude-3-5-sonnet"},
                        "tool_categories": ["reasoning", "analysis"],
                        "tool_types": ["builtin"],
                        "max_tools": 3,
                        "temperature": 0.4
                    }
                }
            ),
            DAGNode(
                id="synthesis_agent",
                type=NodeType.AGENT,
                name="综合智能体",
                description="综合所有结果",
                config={
                    "agent_config": {
                        "name": "Synthesis Agent",
                        "instructions": "综合所有智能体的结果，形成最终解决方案",
                        "model_config": {"model_name": "claude-3-5-sonnet"},
                        "tool_categories": ["reasoning", "analysis"],
                        "tool_types": ["builtin"],
                        "max_tools": 3,
                        "temperature": 0.3,
                        "max_tokens": 4000
                    }
                }
            ),
            DAGNode(
                id="output",
                type=NodeType.OUTPUT,
                name="输出结果",
                config={"include_methodology": True, "include_reasoning": True}
            )
        ]
        
        edges = [
            DAGEdge("input", "task_analysis_agent"),
            DAGEdge("task_analysis_agent", "complexity_check"),
            
            # 简单任务路径
            DAGEdge("complexity_check", "single_agent_solver", condition="complexity <= 0.8"),
            DAGEdge("single_agent_solver", "output"),
            
            # 复杂任务路径 - 团队协作
            DAGEdge("complexity_check", "team_coordinator", condition="complexity > 0.8"),
            
            # 并行执行的专业智能体
            DAGEdge("team_coordinator", "research_agent"),
            DAGEdge("team_coordinator", "analysis_agent"),
            DAGEdge("team_coordinator", "planning_agent"),
            
            # 综合结果
            DAGEdge("research_agent", "synthesis_agent"),
            DAGEdge("analysis_agent", "synthesis_agent"),
            DAGEdge("planning_agent", "synthesis_agent"),
            DAGEdge("synthesis_agent", "output")
        ]
        
        return DAGTemplate(
            template_id="deep_thinking",
            name="深度思考模版",
            description="具备复杂推理能力的分析专家",
            category="analysis",
            nodes=nodes,
            edges=edges,
            variables={
                "complexity_threshold": 0.8,
                "max_team_size": 3,
                "analysis_depth": "deep"
            },
            tags=["analysis", "complex", "team"]
        )
    
    async def create_execution(
        self,
        template_id: str,
        user_id: str,
        input_data: Dict[str, Any],
        config_overrides: Optional[Dict[str, Any]] = None
    ) -> str:
        """创建DAG执行实例"""
        # 确保编排器已初始化
        if not self._initialized:
            await self.initialize()
        
        if template_id not in self.templates:
            raise ValueError(f"Template {template_id} not found")
        
        execution_id = f"exec_{template_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(self.executions)}"
        
        execution = DAGExecution(
            execution_id=execution_id,
            template_id=template_id,
            user_id=user_id,
            input_data=input_data,
            config_overrides=config_overrides or {}
        )
        
        self.executions[execution_id] = execution
        
        logger.info(f"Created DAG execution {execution_id} for template {template_id}")
        return execution_id
    
    async def execute_dag(self, execution_id: str) -> DAGExecution:
        """执行DAG"""
        if execution_id not in self.executions:
            raise ValueError(f"Execution {execution_id} not found")
        
        if execution_id in self.running_executions:
            raise ValueError(f"Execution {execution_id} is already running")
        
        execution = self.executions[execution_id]
        template = self.templates[execution.template_id]
        
        self.running_executions.add(execution_id)
        execution.status = ExecutionStatus.RUNNING
        execution.start_time = datetime.now(timezone.utc)
        
        try:
            # 构建执行图
            graph = self._build_execution_graph(template, execution)
            
            # 执行DAG
            await self._execute_graph(graph, execution, template)
            
            execution.status = ExecutionStatus.COMPLETED
            execution.end_time = datetime.now(timezone.utc)
            
            logger.info(f"DAG execution {execution_id} completed successfully")
            
        except Exception as e:
            execution.status = ExecutionStatus.FAILED
            execution.end_time = datetime.now(timezone.utc)
            execution.metadata["error"] = str(e)
            
            logger.error(f"DAG execution {execution_id} failed: {str(e)}")
            
        finally:
            self.running_executions.discard(execution_id)
        
        return execution
    
    def _build_execution_graph(self, template: DAGTemplate, execution: DAGExecution) -> Dict[str, Any]:
        """构建执行图"""
        # 构建邻接表
        graph = {
            "nodes": {node.id: node for node in template.nodes},
            "edges": defaultdict(list),
            "reverse_edges": defaultdict(list)
        }
        
        for edge in template.edges:
            graph["edges"][edge.from_node].append(edge)
            graph["reverse_edges"][edge.to_node].append(edge)
        
        return graph
    
    async def _execute_graph(self, graph: Dict[str, Any], execution: DAGExecution, template: DAGTemplate):
        """执行图"""
        nodes = graph["nodes"]
        edges = graph["edges"]
        reverse_edges = graph["reverse_edges"]
        
        # 计算入度
        in_degree = {node_id: len(reverse_edges[node_id]) for node_id in nodes}
        
        # 找到起始节点（入度为0）
        ready_nodes = deque([node_id for node_id, degree in in_degree.items() if degree == 0])
        completed_nodes = set()
        
        # 存储节点执行结果
        node_results = {}
        
        while ready_nodes:
            current_batch = []
            
            # 收集当前可以并行执行的节点
            while ready_nodes:
                node_id = ready_nodes.popleft()
                current_batch.append(node_id)
            
            # 并行执行当前批次的节点
            batch_tasks = []
            for node_id in current_batch:
                node = nodes[node_id]
                task = self._execute_node(node, node_results, execution, template)
                batch_tasks.append((node_id, task))
            
            # 等待批次完成
            for node_id, task in batch_tasks:
                try:
                    result = await task
                    node_results[node_id] = result
                    execution.node_statuses[node_id] = ExecutionStatus.COMPLETED
                    execution.node_results[node_id] = result
                    execution.execution_path.append(node_id)
                    completed_nodes.add(node_id)
                    
                except Exception as e:
                    execution.node_statuses[node_id] = ExecutionStatus.FAILED
                    execution.node_errors[node_id] = str(e)
                    logger.error(f"Node {node_id} failed: {str(e)}")
                    # 继续执行其他节点，但标记失败的节点
                    continue
            
            # 更新下游节点的入度
            for node_id in current_batch:
                if node_id in completed_nodes:  # 只有成功的节点才能激活下游
                    for edge in edges[node_id]:
                        to_node = edge.to_node
                        
                        # 检查条件
                        if self._check_edge_condition(edge, node_results.get(node_id)):
                            in_degree[to_node] -= 1
                            if in_degree[to_node] == 0:
                                ready_nodes.append(to_node)
        
        # 设置最终结果
        output_nodes = [node_id for node_id, node in nodes.items() if node.type == NodeType.OUTPUT]
        if output_nodes:
            execution.final_result = node_results.get(output_nodes[0])
        else:
            # 如果没有明确的输出节点，使用最后执行的节点结果
            if execution.execution_path:
                last_node = execution.execution_path[-1]
                execution.final_result = node_results.get(last_node)
    
    async def _execute_node(
        self, 
        node: DAGNode, 
        node_results: Dict[str, Any],
        execution: DAGExecution,
        template: DAGTemplate
    ) -> Any:
        """执行单个节点"""
        logger.info(f"Executing node {node.id} of type {node.type}")
        
        execution.node_statuses[node.id] = ExecutionStatus.RUNNING
        
        if node.type == NodeType.INPUT:
            return execution.input_data
        
        elif node.type == NodeType.OUTPUT:
            # 输出节点收集前置节点的结果
            output_data = {}
            for dep in node.dependencies:
                if dep in node_results:
                    output_data[dep] = node_results[dep]
            return output_data
        
        elif node.type == NodeType.AGENT:
            return await self._execute_agent_node(node, node_results, execution)
        
        elif node.type == NodeType.CONDITION:
            return self._execute_condition_node(node, node_results)
        
        elif node.type == NodeType.MERGE:
            return self._execute_merge_node(node, node_results)
        
        elif node.type == NodeType.PARALLEL:
            return await self._execute_parallel_node(node, node_results, execution, template)
        
        else:
            logger.warning(f"Unknown node type: {node.type}")
            return None
    
    async def _execute_agent_node(
        self, 
        node: DAGNode, 
        node_results: Dict[str, Any],
        execution: DAGExecution
    ) -> Any:
        """执行智能体节点"""
        agent_config_data = node.config.get("agent_config", {})
        
        # 应用变量替换
        agent_config_data = self._apply_variable_substitution(agent_config_data, execution.input_data)
        
        # 动态获取工具
        tools = await self._get_agent_tools(agent_config_data)
        
        # 创建AgentConfig
        agent_config = AgentConfig(
            name=agent_config_data.get("name", node.name),
            description=agent_config_data.get("description", node.description),
            instructions=agent_config_data.get("instructions", ""),
            model_config=agent_config_data.get("model_config", {}),
            tools=tools,
            knowledge_bases=agent_config_data.get("knowledge_bases", []),
            temperature=agent_config_data.get("temperature", 0.7),
            max_tokens=agent_config_data.get("max_tokens", 1000)
        )
        
        # 创建智能体
        agent_id = await agno_manager.create_agent(agent_config)
        
        try:
            # 准备输入消息
            input_message = self._prepare_agent_input(node, node_results, execution)
            
            # 执行智能体
            result = await agno_manager.run_agent(
                agent_id=agent_id,
                message=input_message,
                user_id=execution.user_id,
                session_id=execution.execution_id
            )
            
            if result.success:
                return {
                    "response": result.response,
                    "execution_time": result.execution_time,
                    "metadata": result.metadata,
                    "tools_used": tools  # 记录使用的工具
                }
            else:
                raise Exception(f"Agent execution failed: {result.error}")
                
        finally:
            # 清理智能体
            await agno_manager.delete_agent(agent_id)
    
    def _execute_condition_node(self, node: DAGNode, node_results: Dict[str, Any]) -> Any:
        """执行条件节点"""
        condition = node.config.get("condition", "True")
        
        # 简化的条件评估
        if "confidence" in condition:
            # 从前置节点结果中提取置信度
            for result in node_results.values():
                if isinstance(result, dict) and "confidence" in result:
                    confidence = result["confidence"]
                    threshold = node.config.get("confidence_threshold", 0.7)
                    return {"condition_met": confidence >= threshold, "confidence": confidence}
        
        elif "complexity" in condition:
            # 从前置节点结果中提取复杂度
            for result in node_results.values():
                if isinstance(result, dict) and "complexity" in result:
                    complexity = result["complexity"]
                    threshold = node.config.get("complexity_threshold", 0.8)
                    return {"condition_met": complexity > threshold, "complexity": complexity}
                elif isinstance(result, str):
                    # 基于文本长度估算复杂度
                    complexity = min(len(result) / 1000, 1.0)
                    threshold = node.config.get("complexity_threshold", 0.8)
                    return {"condition_met": complexity > threshold, "complexity": complexity}
        
        return {"condition_met": True}
    
    def _execute_merge_node(self, node: DAGNode, node_results: Dict[str, Any]) -> Any:
        """执行合并节点"""
        merge_strategy = node.config.get("strategy", "concat")
        
        if merge_strategy == "concat":
            # 连接所有结果
            merged_result = ""
            for result in node_results.values():
                if isinstance(result, str):
                    merged_result += result + "\n"
                elif isinstance(result, dict) and "response" in result:
                    merged_result += result["response"] + "\n"
            return {"merged_response": merged_result.strip()}
        
        elif merge_strategy == "combine":
            # 组合所有结果
            combined_result = {}
            for key, result in node_results.items():
                combined_result[key] = result
            return combined_result
        
        return node_results
    
    async def _execute_parallel_node(
        self, 
        node: DAGNode, 
        node_results: Dict[str, Any],
        execution: DAGExecution,
        template: DAGTemplate
    ) -> Any:
        """执行并行节点"""
        # 这是一个协调节点，本身不执行具体逻辑
        # 实际的并行执行在图执行层面处理
        return {"parallel_coordinator": True, "node_id": node.id}
    
    def _prepare_agent_input(
        self, 
        node: DAGNode, 
        node_results: Dict[str, Any],
        execution: DAGExecution
    ) -> str:
        """准备智能体输入"""
        # 从依赖节点收集输入
        inputs = []
        
        # 添加原始输入
        if "input" in node_results:
            input_data = node_results["input"]
            if isinstance(input_data, dict):
                for key, value in input_data.items():
                    inputs.append(f"{key}: {value}")
            else:
                inputs.append(str(input_data))
        
        # 添加前置节点的结果
        for dep in node.dependencies:
            if dep in node_results and dep != "input":
                result = node_results[dep]
                if isinstance(result, dict) and "response" in result:
                    inputs.append(f"Previous result from {dep}: {result['response']}")
                elif isinstance(result, str):
                    inputs.append(f"Previous result from {dep}: {result}")
        
        return "\n".join(inputs) if inputs else "Please proceed with the task."
    
    def _check_edge_condition(self, edge: DAGEdge, node_result: Any) -> bool:
        """检查边的条件"""
        if not edge.condition:
            return True
        
        condition = edge.condition
        
        if isinstance(node_result, dict):
            if "condition_met" in node_result:
                return node_result["condition_met"]
            
            if "confidence" in condition and "confidence" in node_result:
                if ">=" in condition:
                    threshold = float(condition.split(">=")[1].strip())
                    return node_result["confidence"] >= threshold
                elif ">" in condition:
                    threshold = float(condition.split(">")[1].strip())
                    return node_result["confidence"] > threshold
                elif "<" in condition:
                    threshold = float(condition.split("<")[1].strip())
                    return node_result["confidence"] < threshold
            
            if "complexity" in condition and "complexity" in node_result:
                if ">" in condition:
                    threshold = float(condition.split(">")[1].strip())
                    return node_result["complexity"] > threshold
                elif "<=" in condition:
                    threshold = float(condition.split("<=")[1].strip())
                    return node_result["complexity"] <= threshold
        
        return True
    
    def _apply_variable_substitution(self, config: Dict[str, Any], variables: Dict[str, Any]) -> Dict[str, Any]:
        """应用变量替换"""
        import copy
        result = copy.deepcopy(config)
        
        def substitute_recursive(obj):
            if isinstance(obj, dict):
                return {k: substitute_recursive(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [substitute_recursive(item) for item in obj]
            elif isinstance(obj, str):
                # 简单的变量替换
                for var_name, var_value in variables.items():
                    placeholder = f"{{{var_name}}}"
                    if placeholder in obj:
                        obj = obj.replace(placeholder, str(var_value))
                return obj
            else:
                return obj
        
        return substitute_recursive(result)
    
    async def _get_agent_tools(self, agent_config_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """动态获取智能体工具"""
        try:
            # 获取工具配置
            tool_categories = agent_config_data.get("tool_categories", ["reasoning"])
            tool_types = agent_config_data.get("tool_types", ["builtin"])
            max_tools = agent_config_data.get("max_tools", 5)
            
            # 转换为枚举类型
            categories = []
            for category in tool_categories:
                try:
                    categories.append(ToolCategory(category))
                except ValueError:
                    logger.warning(f"未知的工具分类: {category}")
            
            types = []
            for tool_type in tool_types:
                try:
                    types.append(ToolType(tool_type))
                except ValueError:
                    logger.warning(f"未知的工具类型: {tool_type}")
            
            # 从工具注入管理器获取工具
            available_tools = self.tool_manager.get_tools_for_agent(
                categories=categories if categories else None,
                tool_types=types if types else None,
                max_tools=max_tools
            )
            
            # 提取工具ID列表
            tool_ids = [tool.id for tool in available_tools]
            
            # 获取Agno格式的工具Schema
            tool_schemas = self.tool_manager.get_tool_schemas_for_agno(tool_ids)
            
            logger.info(f"为智能体分配了 {len(tool_schemas)} 个工具: {[t['function']['name'] for t in tool_schemas]}")
            
            return tool_schemas
            
        except Exception as e:
            logger.error(f"获取智能体工具失败: {e}")
            # 返回基础工具作为兜底
            return [
                {
                    "type": "function",
                    "function": {
                        "name": "reasoning",
                        "description": "进行逻辑推理和分析",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "需要推理的问题或情况"
                                }
                            },
                            "required": ["query"]
                        }
                    }
                }
            ]
    
    async def get_execution_status(self, execution_id: str) -> Dict[str, Any]:
        """获取执行状态"""
        if execution_id not in self.executions:
            raise ValueError(f"Execution {execution_id} not found")
        
        execution = self.executions[execution_id]
        
        return {
            "execution_id": execution_id,
            "template_id": execution.template_id,
            "status": execution.status.value,
            "start_time": execution.start_time.isoformat() if execution.start_time else None,
            "end_time": execution.end_time.isoformat() if execution.end_time else None,
            "execution_path": execution.execution_path,
            "node_statuses": {k: v.value for k, v in execution.node_statuses.items()},
            "final_result": execution.final_result,
            "metadata": execution.metadata
        }
    
    def get_available_templates(self) -> List[Dict[str, Any]]:
        """获取可用模版列表"""
        templates = []
        for template in self.templates.values():
            templates.append({
                "template_id": template.template_id,
                "name": template.name,
                "description": template.description,
                "category": template.category,
                "node_count": len(template.nodes),
                "tags": template.tags,
                "version": template.version
            })
        
        return templates
    
    def get_template_detail(self, template_id: str) -> Dict[str, Any]:
        """获取模版详细信息"""
        if template_id not in self.templates:
            raise ValueError(f"Template {template_id} not found")
        
        template = self.templates[template_id]
        
        return {
            "template_id": template.template_id,
            "name": template.name,
            "description": template.description,
            "category": template.category,
            "nodes": [
                {
                    "id": node.id,
                    "type": node.type.value,
                    "name": node.name,
                    "description": node.description,
                    "dependencies": node.dependencies,
                    "dependents": node.dependents
                }
                for node in template.nodes
            ],
            "edges": [
                {
                    "from_node": edge.from_node,
                    "to_node": edge.to_node,
                    "condition": edge.condition,
                    "weight": edge.weight
                }
                for edge in template.edges
            ],
            "variables": template.variables,
            "default_config": template.default_config,
            "tags": template.tags,
            "version": template.version,
            "created_at": template.created_at.isoformat()
        }
    
    def get_tools_statistics(self) -> Dict[str, Any]:
        """获取工具统计信息"""
        if not self._initialized:
            return {"error": "DAG编排器未初始化"}
        
        return self.tool_manager.get_statistics()
    
    async def refresh_tools(self) -> Dict[str, Any]:
        """刷新工具列表"""
        if not self._initialized:
            await self.initialize()
        
        try:
            discovered_tools = await self.tool_manager.discover_tools()
            return {
                "success": True,
                "message": "工具列表刷新成功",
                "discovered_tools": {
                    service: len(tools) for service, tools in discovered_tools.items()
                },
                "total_tools": len(self.tool_manager.tools)
            }
        except Exception as e:
            logger.error(f"刷新工具列表失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # ==================== 动态DAG生成和智能体实例化 ====================
    
    async def create_custom_agent(
        self,
        template_id: str,
        user_id: str,
        generation_request: DAGGenerationRequest
    ) -> Dict[str, Any]:
        """创建自定义智能体实例"""
        if not self._initialized:
            await self.initialize()
        
        try:
            logger.info(f"开始创建自定义智能体: template={template_id}, user={user_id}")
            
            # 1. 生成动态DAG
            generated_dag = await dynamic_dag_generator.generate_dag(generation_request)
            
            # 2. 转换为Agno智能体实例
            conversion_result = await dag_to_agno_converter.convert_dag_to_agno(
                generated_dag,
                conversion_options={
                    "auto_activate": True,
                    "enable_health_check": True
                }
            )
            
            if not conversion_result.success:
                raise Exception(conversion_result.error_message)
            
            # 3. 保存配置到数据库（TODO: 实现数据库保存逻辑）
            await self._save_agent_configuration(
                generated_dag, 
                conversion_result.agent_instance,
                user_id
            )
            
            return {
                "success": True,
                "agent_instance": {
                    "instance_id": conversion_result.agent_instance.instance_id,
                    "agent_id": conversion_result.agent_instance.agent_id,
                    "dag_id": conversion_result.agent_instance.dag_id,
                    "status": conversion_result.agent_instance.status,
                    "health_status": conversion_result.agent_instance.health_status,
                    "agent_name": conversion_result.agent_instance.agent_config.name,
                    "tools_count": len(conversion_result.agent_instance.tools_config.get("tool_details", {})),
                    "optimization_score": generated_dag.optimization_score,
                    "estimated_cost": generated_dag.estimated_cost,
                    "estimated_time": generated_dag.estimated_time
                },
                "dag_info": {
                    "dag_id": generated_dag.dag_id,
                    "generation_mode": generated_dag.generation_mode.value,
                    "nodes_count": len(generated_dag.nodes),
                    "edges_count": len(generated_dag.edges),
                    "selected_tools": len(generated_dag.selected_tools)
                },
                "conversion_info": {
                    "nodes_converted": conversion_result.nodes_converted,
                    "tools_loaded": conversion_result.tools_loaded,
                    "conversion_time": conversion_result.conversion_time
                }
            }
            
        except Exception as e:
            logger.error(f"创建自定义智能体失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def create_agent_from_user_config(
        self,
        user_id: str,
        agent_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """根据用户配置创建智能体"""
        try:
            # 解析用户配置
            template_id = agent_config.get("template_id", "basic_conversation")
            generation_mode = DAGGenerationMode(agent_config.get("generation_mode", "custom"))
            
            # 构建用户偏好
            user_preferences = UserPreferences(
                preferred_tool_types=[ToolType(t) for t in agent_config.get("preferred_tool_types", ["builtin"])],
                preferred_categories=[ToolCategory(c) for c in agent_config.get("preferred_categories", ["reasoning"])],
                excluded_tools=agent_config.get("excluded_tools", []),
                max_tools_per_agent=agent_config.get("max_tools_per_agent", 5),
                optimization_strategy=agent_config.get("optimization_strategy", "balanced"),
                max_execution_time=agent_config.get("max_execution_time", 300),
                max_cost_per_execution=agent_config.get("max_cost_per_execution", 1.0),
                min_success_rate=agent_config.get("min_success_rate", 0.8),
                enable_parallel_execution=agent_config.get("enable_parallel_execution", True),
                enable_fallback_nodes=agent_config.get("enable_fallback_nodes", True)
            )
            
            # 构建生成请求
            generation_request = DAGGenerationRequest(
                template_id=template_id,
                user_id=user_id,
                generation_mode=generation_mode,
                user_preferences=user_preferences,
                selected_capabilities=agent_config.get("selected_capabilities", []),
                enabled_tools=agent_config.get("enabled_tools", []),
                disabled_tools=agent_config.get("disabled_tools", []),
                model_config=agent_config.get("model_config", {}),
                knowledge_config=agent_config.get("knowledge_config", {}),
                custom_instructions=agent_config.get("custom_instructions", ""),
                environment_variables=agent_config.get("environment_variables", {})
            )
            
            # 创建智能体
            return await self.create_custom_agent(template_id, user_id, generation_request)
            
        except Exception as e:
            logger.error(f"根据用户配置创建智能体失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_agent_instance_status(self, instance_id: str) -> Dict[str, Any]:
        """获取智能体实例状态"""
        try:
            return await dag_to_agno_converter.get_instance_status(instance_id)
        except Exception as e:
            logger.error(f"获取智能体实例状态失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def execute_agent_instance(
        self,
        instance_id: str,
        message: str,
        user_id: str,
        execution_options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """执行智能体实例"""
        try:
            return await dag_to_agno_converter.execute_agent_instance(
                instance_id, message, user_id, execution_options
            )
        except Exception as e:
            logger.error(f"执行智能体实例失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def list_agent_instances(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出智能体实例"""
        try:
            return dag_to_agno_converter.list_instances(user_id)
        except Exception as e:
            logger.error(f"列出智能体实例失败: {e}")
            return []
    
    async def _save_agent_configuration(
        self,
        generated_dag,
        agent_instance: AgnoAgentInstance,
        user_id: str
    ):
        """保存智能体配置到数据库"""
        # TODO: 实现数据库保存逻辑
        # 这里应该调用database-service保存配置
        logger.info(f"保存智能体配置: {agent_instance.instance_id}")
        
        config_data = {
            "instance_id": agent_instance.instance_id,
            "agent_id": agent_instance.agent_id,
            "dag_id": agent_instance.dag_id,
            "user_id": user_id,
            "template_id": generated_dag.template_id,
            "generation_mode": generated_dag.generation_mode.value,
            
            # DAG配置
            "dag_config": {
                "nodes": [{"id": n.id, "type": n.type.value, "name": n.name, "config": n.config} for n in generated_dag.nodes],
                "edges": [{"from": e.from_node, "to": e.to_node, "condition": e.condition} for e in generated_dag.edges],
                "execution_order": generated_dag.execution_order,
                "optimization_score": generated_dag.optimization_score,
                "estimated_cost": generated_dag.estimated_cost,
                "estimated_time": generated_dag.estimated_time
            },
            
            # 智能体配置
            "agent_config": {
                "name": agent_instance.agent_config.name,
                "description": agent_instance.agent_config.description,
                "instructions": agent_instance.agent_config.instructions,
                "model_config": agent_instance.agent_config.model_config,
                "temperature": agent_instance.agent_config.temperature,
                "max_tokens": agent_instance.agent_config.max_tokens,
                "memory_enabled": agent_instance.agent_config.memory_enabled
            },
            
            # 工具配置
            "tools_config": agent_instance.tools_config,
            
            # 元数据
            "metadata": {
                "created_at": agent_instance.created_at.isoformat(),
                "status": agent_instance.status,
                "health_status": agent_instance.health_status
            }
        }
        
        # 这里应该调用database-service的API保存配置
        # 示例代码：
        # from shared.service_client import call_service, CallMethod
        # await call_service(
        #     service_name="database-service",
        #     method=CallMethod.POST,
        #     path="/api/v1/agent_configurations",
        #     json=config_data
        # )
    
    def get_system_statistics(self) -> Dict[str, Any]:
        """获取系统统计信息"""
        try:
            return {
                "dag_orchestrator": {
                    "templates_count": len(self.templates),
                    "active_executions": len(self.running_executions),
                    "total_executions": len(self.executions)
                },
                "tool_manager": self.get_tools_statistics(),
                "dag_generator": {
                    "available_modes": [mode.value for mode in DAGGenerationMode]
                },
                "agent_converter": dag_to_agno_converter.get_converter_statistics()
            }
        except Exception as e:
            logger.error(f"获取系统统计信息失败: {e}")
            return {"error": str(e)}

# 全局实例
dag_orchestrator = DAGOrchestrator()