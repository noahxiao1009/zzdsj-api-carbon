"""
动态DAG生成器
Dynamic DAG Generator

根据用户的选择、工具启用状态和配置，动态生成个性化的DAG执行图
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import copy
import json

from .dag_orchestrator import (
    DAGNode, DAGEdge, DAGTemplate, NodeType, ExecutionStatus
)
from .tool_injection_manager import (
    tool_injection_manager, ToolDefinition, ToolCategory, ToolType
)

logger = logging.getLogger(__name__)

class DAGGenerationMode(str, Enum):
    """DAG生成模式"""
    FULL = "full"           # 完整模式 - 加载所有默认节点
    MINIMAL = "minimal"     # 最小模式 - 只加载必需节点
    CUSTOM = "custom"       # 自定义模式 - 根据用户选择生成
    OPTIMIZED = "optimized" # 优化模式 - 根据性能和用户偏好优化

class NodeOptimization(str, Enum):
    """节点优化策略"""
    PERFORMANCE = "performance"   # 性能优先 - 选择最快的工具
    ACCURACY = "accuracy"        # 准确性优先 - 选择最准确的工具
    COST = "cost"               # 成本优先 - 选择最便宜的工具
    BALANCED = "balanced"       # 平衡模式 - 综合考虑

@dataclass
class UserPreferences:
    """用户偏好设置"""
    # 工具偏好
    preferred_tool_types: List[ToolType] = field(default_factory=lambda: [ToolType.BUILTIN])
    preferred_categories: List[ToolCategory] = field(default_factory=lambda: [ToolCategory.REASONING])
    excluded_tools: List[str] = field(default_factory=list)
    max_tools_per_agent: int = 5
    
    # 性能偏好
    optimization_strategy: NodeOptimization = NodeOptimization.BALANCED
    max_execution_time: int = 300  # 最大执行时间(秒)
    timeout_tolerance: float = 0.8  # 超时容忍度
    
    # 成本偏好
    max_cost_per_execution: float = 1.0  # 最大单次执行成本
    cost_weight: float = 0.3            # 成本权重
    
    # 准确性偏好
    min_success_rate: float = 0.8       # 最小成功率要求
    accuracy_weight: float = 0.5        # 准确性权重
    
    # 自定义配置
    custom_node_configs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    enable_parallel_execution: bool = True
    enable_fallback_nodes: bool = True

@dataclass
class DAGGenerationRequest:
    """DAG生成请求"""
    template_id: str
    user_id: str
    generation_mode: DAGGenerationMode = DAGGenerationMode.CUSTOM
    user_preferences: UserPreferences = field(default_factory=UserPreferences)
    
    # 用户选择的配置
    selected_capabilities: List[str] = field(default_factory=list)
    enabled_tools: List[str] = field(default_factory=list)
    disabled_tools: List[str] = field(default_factory=list)
    
    # 模型和知识库配置
    model_config: Dict[str, Any] = field(default_factory=dict)
    knowledge_config: Dict[str, Any] = field(default_factory=dict)
    
    # 高级配置
    custom_instructions: str = ""
    environment_variables: Dict[str, Any] = field(default_factory=dict)

@dataclass
class GeneratedDAG:
    """生成的DAG"""
    dag_id: str
    template_id: str
    user_id: str
    
    # DAG配置
    nodes: List[DAGNode]
    edges: List[DAGEdge]
    execution_order: List[str]
    
    # 工具配置
    selected_tools: List[ToolDefinition]
    tool_mappings: Dict[str, List[str]]  # node_id -> tool_ids
    
    # 元数据
    generation_mode: DAGGenerationMode
    optimization_score: float
    estimated_cost: float
    estimated_time: float
    
    # 生成信息
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

class DynamicDAGGenerator:
    """动态DAG生成器"""
    
    def __init__(self):
        self.tool_manager = tool_injection_manager
        self._template_cache = {}
        self._optimization_cache = {}
        
        # 节点权重配置
        self.node_weights = {
            NodeType.AGENT: 1.0,
            NodeType.CONDITION: 0.1,
            NodeType.MERGE: 0.2,
            NodeType.PARALLEL: 0.3,
            NodeType.INPUT: 0.0,
            NodeType.OUTPUT: 0.0
        }
        
        # 优化策略配置
        self.optimization_strategies = {
            NodeOptimization.PERFORMANCE: self._optimize_for_performance,
            NodeOptimization.ACCURACY: self._optimize_for_accuracy,
            NodeOptimization.COST: self._optimize_for_cost,
            NodeOptimization.BALANCED: self._optimize_balanced
        }
    
    async def generate_dag(self, request: DAGGenerationRequest) -> GeneratedDAG:
        """生成动态DAG"""
        logger.info(f"开始生成DAG: template={request.template_id}, mode={request.generation_mode}")
        
        try:
            # 1. 获取基础模板
            base_template = await self._get_base_template(request.template_id)
            
            # 2. 根据生成模式处理
            if request.generation_mode == DAGGenerationMode.FULL:
                dag = await self._generate_full_dag(base_template, request)
            elif request.generation_mode == DAGGenerationMode.MINIMAL:
                dag = await self._generate_minimal_dag(base_template, request)
            elif request.generation_mode == DAGGenerationMode.CUSTOM:
                dag = await self._generate_custom_dag(base_template, request)
            elif request.generation_mode == DAGGenerationMode.OPTIMIZED:
                dag = await self._generate_optimized_dag(base_template, request)
            else:
                raise ValueError(f"Unsupported generation mode: {request.generation_mode}")
            
            # 3. 验证DAG有效性
            await self._validate_dag(dag)
            
            # 4. 计算优化分数
            dag.optimization_score = await self._calculate_optimization_score(dag, request)
            
            logger.info(f"DAG生成完成: nodes={len(dag.nodes)}, edges={len(dag.edges)}, score={dag.optimization_score:.2f}")
            
            return dag
            
        except Exception as e:
            logger.error(f"DAG生成失败: {e}")
            raise
    
    async def _get_base_template(self, template_id: str) -> DAGTemplate:
        """获取基础模板"""
        # 从DAG编排器获取模板
        from .dag_orchestrator import dag_orchestrator
        
        if not dag_orchestrator._initialized:
            await dag_orchestrator.initialize()
        
        if template_id not in dag_orchestrator.templates:
            raise ValueError(f"Template {template_id} not found")
        
        return dag_orchestrator.templates[template_id]
    
    async def _generate_full_dag(self, template: DAGTemplate, request: DAGGenerationRequest) -> GeneratedDAG:
        """生成完整DAG - 加载所有默认节点和工具"""
        logger.info("生成完整DAG")
        
        # 复制模板节点和边
        nodes = copy.deepcopy(template.nodes)
        edges = copy.deepcopy(template.edges)
        
        # 为每个智能体节点加载所有可用工具
        selected_tools = []
        tool_mappings = {}
        
        for node in nodes:
            if node.type == NodeType.AGENT:
                # 获取所有可用工具
                available_tools = self.tool_manager.get_tools_for_agent(
                    categories=None,  # 不限制分类
                    tool_types=None,  # 不限制类型
                    max_tools=None    # 不限制数量
                )
                
                node_tools = []
                for tool in available_tools:
                    if tool.is_enabled and tool.is_available:
                        node_tools.append(tool.id)
                        if tool not in selected_tools:
                            selected_tools.append(tool)
                
                tool_mappings[node.id] = node_tools
                
                # 更新节点配置
                agent_config = node.config.get("agent_config", {})
                agent_config["tool_categories"] = [cat.value for cat in ToolCategory]
                agent_config["tool_types"] = [typ.value for typ in ToolType]
                agent_config["max_tools"] = len(node_tools)
        
        return GeneratedDAG(
            dag_id=f"full_{template.template_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            template_id=template.template_id,
            user_id=request.user_id,
            nodes=nodes,
            edges=edges,
            execution_order=self._calculate_execution_order(nodes, edges),
            selected_tools=selected_tools,
            tool_mappings=tool_mappings,
            generation_mode=request.generation_mode,
            optimization_score=0.0,
            estimated_cost=self._estimate_cost(selected_tools),
            estimated_time=self._estimate_execution_time(nodes)
        )
    
    async def _generate_minimal_dag(self, template: DAGTemplate, request: DAGGenerationRequest) -> GeneratedDAG:
        """生成最小DAG - 只保留必需节点"""
        logger.info("生成最小DAG")
        
        # 筛选必需节点
        essential_nodes = []
        for node in template.nodes:
            if node.type in [NodeType.INPUT, NodeType.OUTPUT]:
                essential_nodes.append(copy.deepcopy(node))
            elif node.type == NodeType.AGENT:
                # 只保留第一个智能体节点
                if not any(n.type == NodeType.AGENT for n in essential_nodes):
                    minimal_node = copy.deepcopy(node)
                    # 配置最少工具
                    agent_config = minimal_node.config.get("agent_config", {})
                    agent_config["tool_categories"] = ["reasoning"]
                    agent_config["tool_types"] = ["builtin"]
                    agent_config["max_tools"] = 1
                    essential_nodes.append(minimal_node)
        
        # 重建边连接
        minimal_edges = []
        node_ids = {node.id for node in essential_nodes}
        
        for edge in template.edges:
            if edge.from_node in node_ids and edge.to_node in node_ids:
                minimal_edges.append(copy.deepcopy(edge))
        
        # 获取最少工具
        minimal_tools = self.tool_manager.get_tools_for_agent(
            categories=[ToolCategory.REASONING],
            tool_types=[ToolType.BUILTIN],
            max_tools=1
        )
        
        tool_mappings = {}
        for node in essential_nodes:
            if node.type == NodeType.AGENT:
                tool_mappings[node.id] = [tool.id for tool in minimal_tools]
        
        return GeneratedDAG(
            dag_id=f"minimal_{template.template_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            template_id=template.template_id,
            user_id=request.user_id,
            nodes=essential_nodes,
            edges=minimal_edges,
            execution_order=self._calculate_execution_order(essential_nodes, minimal_edges),
            selected_tools=minimal_tools,
            tool_mappings=tool_mappings,
            generation_mode=request.generation_mode,
            optimization_score=0.0,
            estimated_cost=self._estimate_cost(minimal_tools),
            estimated_time=self._estimate_execution_time(essential_nodes)
        )
    
    async def _generate_custom_dag(self, template: DAGTemplate, request: DAGGenerationRequest) -> GeneratedDAG:
        """生成自定义DAG - 根据用户选择和偏好"""
        logger.info("生成自定义DAG")
        
        # 根据用户偏好筛选节点
        custom_nodes = []
        for node in template.nodes:
            if self._should_include_node(node, request):
                custom_node = copy.deepcopy(node)
                await self._customize_node(custom_node, request)
                custom_nodes.append(custom_node)
        
        # 重建边连接
        custom_edges = self._rebuild_edges(template.edges, custom_nodes)
        
        # 根据用户选择获取工具
        selected_tools = await self._select_tools_for_request(request)
        tool_mappings = await self._map_tools_to_nodes(custom_nodes, selected_tools, request)
        
        return GeneratedDAG(
            dag_id=f"custom_{template.template_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            template_id=template.template_id,
            user_id=request.user_id,
            nodes=custom_nodes,
            edges=custom_edges,
            execution_order=self._calculate_execution_order(custom_nodes, custom_edges),
            selected_tools=selected_tools,
            tool_mappings=tool_mappings,
            generation_mode=request.generation_mode,
            optimization_score=0.0,
            estimated_cost=self._estimate_cost(selected_tools),
            estimated_time=self._estimate_execution_time(custom_nodes)
        )
    
    async def _generate_optimized_dag(self, template: DAGTemplate, request: DAGGenerationRequest) -> GeneratedDAG:
        """生成优化DAG - 根据性能和用户偏好优化"""
        logger.info("生成优化DAG")
        
        # 先生成自定义DAG作为基础
        base_dag = await self._generate_custom_dag(template, request)
        
        # 应用优化策略
        optimization_strategy = request.user_preferences.optimization_strategy
        optimizer = self.optimization_strategies.get(optimization_strategy, self._optimize_balanced)
        
        optimized_dag = await optimizer(base_dag, request)
        optimized_dag.generation_mode = DAGGenerationMode.OPTIMIZED
        
        return optimized_dag
    
    def _should_include_node(self, node: DAGNode, request: DAGGenerationRequest) -> bool:
        """判断是否应该包含节点"""
        # 输入输出节点必须包含
        if node.type in [NodeType.INPUT, NodeType.OUTPUT]:
            return True
        
        # 检查用户选择的能力
        if request.selected_capabilities:
            node_capabilities = node.config.get("capabilities", [])
            if not any(cap in request.selected_capabilities for cap in node_capabilities):
                return False
        
        # 检查节点类型偏好
        if node.type == NodeType.AGENT:
            agent_config = node.config.get("agent_config", {})
            tool_categories = agent_config.get("tool_categories", [])
            
            # 检查用户偏好的工具分类
            preferred_categories = [cat.value for cat in request.user_preferences.preferred_categories]
            if preferred_categories and not any(cat in preferred_categories for cat in tool_categories):
                return False
        
        return True
    
    async def _customize_node(self, node: DAGNode, request: DAGGenerationRequest):
        """自定义节点配置"""
        if node.type == NodeType.AGENT:
            agent_config = node.config.get("agent_config", {})
            
            # 应用用户偏好
            preferences = request.user_preferences
            
            # 设置工具类型和分类
            agent_config["tool_types"] = [typ.value for typ in preferences.preferred_tool_types]
            agent_config["tool_categories"] = [cat.value for cat in preferences.preferred_categories]
            agent_config["max_tools"] = preferences.max_tools_per_agent
            
            # 应用模型配置
            if request.model_config:
                agent_config["model_config"].update(request.model_config)
            
            # 应用自定义指令
            if request.custom_instructions:
                original_instructions = agent_config.get("instructions", "")
                agent_config["instructions"] = f"{original_instructions}\n\n{request.custom_instructions}"
            
            # 应用自定义节点配置
            if node.id in preferences.custom_node_configs:
                agent_config.update(preferences.custom_node_configs[node.id])
    
    async def _select_tools_for_request(self, request: DAGGenerationRequest) -> List[ToolDefinition]:
        """根据请求选择工具"""
        selected_tools = []
        
        # 获取用户偏好的工具
        available_tools = self.tool_manager.get_tools_for_agent(
            categories=request.user_preferences.preferred_categories,
            tool_types=request.user_preferences.preferred_tool_types,
            max_tools=None
        )
        
        for tool in available_tools:
            # 检查工具是否被启用
            if request.enabled_tools and tool.id not in request.enabled_tools:
                continue
            
            # 检查工具是否被禁用
            if tool.id in request.disabled_tools:
                continue
            
            # 检查工具是否在排除列表中
            if tool.id in request.user_preferences.excluded_tools:
                continue
            
            selected_tools.append(tool)
        
        return selected_tools
    
    async def _map_tools_to_nodes(
        self, 
        nodes: List[DAGNode], 
        tools: List[ToolDefinition], 
        request: DAGGenerationRequest
    ) -> Dict[str, List[str]]:
        """将工具映射到节点"""
        tool_mappings = {}
        
        for node in nodes:
            if node.type == NodeType.AGENT:
                node_tools = []
                agent_config = node.config.get("agent_config", {})
                
                # 获取节点偏好的工具分类
                preferred_categories = agent_config.get("tool_categories", [])
                max_tools = agent_config.get("max_tools", request.user_preferences.max_tools_per_agent)
                
                # 为节点选择合适的工具
                suitable_tools = []
                for tool in tools:
                    if not preferred_categories or tool.category.value in preferred_categories:
                        suitable_tools.append(tool)
                
                # 根据优化策略排序
                suitable_tools = await self._sort_tools_by_strategy(
                    suitable_tools, 
                    request.user_preferences.optimization_strategy
                )
                
                # 限制工具数量
                node_tools = [tool.id for tool in suitable_tools[:max_tools]]
                tool_mappings[node.id] = node_tools
        
        return tool_mappings
    
    async def _sort_tools_by_strategy(
        self, 
        tools: List[ToolDefinition], 
        strategy: NodeOptimization
    ) -> List[ToolDefinition]:
        """根据策略对工具排序"""
        if strategy == NodeOptimization.PERFORMANCE:
            return sorted(tools, key=lambda t: t.avg_response_time)
        elif strategy == NodeOptimization.ACCURACY:
            return sorted(tools, key=lambda t: t.success_rate, reverse=True)
        elif strategy == NodeOptimization.COST:
            # 假设内置工具成本最低
            return sorted(tools, key=lambda t: (0 if t.type == ToolType.BUILTIN else 1, t.avg_response_time))
        else:  # BALANCED
            return sorted(tools, key=lambda t: (t.success_rate * 0.5 - t.avg_response_time * 0.3), reverse=True)
    
    def _rebuild_edges(self, original_edges: List[DAGEdge], nodes: List[DAGNode]) -> List[DAGEdge]:
        """重建边连接"""
        node_ids = {node.id for node in nodes}
        rebuilt_edges = []
        
        for edge in original_edges:
            if edge.from_node in node_ids and edge.to_node in node_ids:
                rebuilt_edges.append(copy.deepcopy(edge))
        
        return rebuilt_edges
    
    def _calculate_execution_order(self, nodes: List[DAGNode], edges: List[DAGEdge]) -> List[str]:
        """计算执行顺序（拓扑排序）"""
        # 构建邻接表和入度
        adj_list = {node.id: [] for node in nodes}
        in_degree = {node.id: 0 for node in nodes}
        
        for edge in edges:
            adj_list[edge.from_node].append(edge.to_node)
            in_degree[edge.to_node] += 1
        
        # 拓扑排序
        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        execution_order = []
        
        while queue:
            current = queue.pop(0)
            execution_order.append(current)
            
            for neighbor in adj_list[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        return execution_order
    
    def _estimate_cost(self, tools: List[ToolDefinition]) -> float:
        """估算执行成本"""
        base_cost = 0.1  # 基础成本
        tool_cost = len(tools) * 0.02  # 每个工具增加成本
        
        # 根据工具类型调整成本
        for tool in tools:
            if tool.type == ToolType.MCP:
                tool_cost += 0.05
            elif tool.type == ToolType.EXTERNAL:
                tool_cost += 0.03
        
        return base_cost + tool_cost
    
    def _estimate_execution_time(self, nodes: List[DAGNode]) -> float:
        """估算执行时间"""
        base_time = 5.0  # 基础时间（秒）
        
        for node in nodes:
            if node.type == NodeType.AGENT:
                base_time += 10.0  # 每个智能体节点增加时间
            else:
                base_time += self.node_weights.get(node.type, 0.5)
        
        return base_time
    
    async def _optimize_for_performance(self, dag: GeneratedDAG, request: DAGGenerationRequest) -> GeneratedDAG:
        """性能优化"""
        # 选择最快的工具
        optimized_tools = []
        for tool in dag.selected_tools:
            if tool.avg_response_time <= 5.0:  # 5秒内的快速工具
                optimized_tools.append(tool)
        
        dag.selected_tools = optimized_tools
        dag.estimated_time *= 0.8  # 预计时间减少20%
        return dag
    
    async def _optimize_for_accuracy(self, dag: GeneratedDAG, request: DAGGenerationRequest) -> GeneratedDAG:
        """准确性优化"""
        # 选择成功率高的工具
        high_accuracy_tools = []
        for tool in dag.selected_tools:
            if tool.success_rate >= 0.9:  # 90%以上成功率
                high_accuracy_tools.append(tool)
        
        dag.selected_tools = high_accuracy_tools
        return dag
    
    async def _optimize_for_cost(self, dag: GeneratedDAG, request: DAGGenerationRequest) -> GeneratedDAG:
        """成本优化"""
        # 优先选择内置工具
        cost_effective_tools = []
        for tool in dag.selected_tools:
            if tool.type == ToolType.BUILTIN:
                cost_effective_tools.append(tool)
        
        dag.selected_tools = cost_effective_tools
        dag.estimated_cost *= 0.5  # 预计成本减少50%
        return dag
    
    async def _optimize_balanced(self, dag: GeneratedDAG, request: DAGGenerationRequest) -> GeneratedDAG:
        """平衡优化"""
        # 综合考虑性能、准确性和成本
        balanced_tools = []
        for tool in dag.selected_tools:
            score = (tool.success_rate * 0.4 + 
                    (5.0 - min(tool.avg_response_time, 5.0)) / 5.0 * 0.3 + 
                    (1 if tool.type == ToolType.BUILTIN else 0.5) * 0.3)
            
            if score >= 0.6:  # 综合分数阈值
                balanced_tools.append(tool)
        
        dag.selected_tools = balanced_tools
        return dag
    
    async def _calculate_optimization_score(self, dag: GeneratedDAG, request: DAGGenerationRequest) -> float:
        """计算优化分数"""
        score = 0.0
        
        # 工具质量分数
        if dag.selected_tools:
            avg_success_rate = sum(tool.success_rate for tool in dag.selected_tools) / len(dag.selected_tools)
            score += avg_success_rate * 0.4
        
        # 执行效率分数
        if dag.estimated_time <= 30:
            score += 0.3
        elif dag.estimated_time <= 60:
            score += 0.2
        else:
            score += 0.1
        
        # 成本效率分数
        if dag.estimated_cost <= 0.5:
            score += 0.3
        elif dag.estimated_cost <= 1.0:
            score += 0.2
        else:
            score += 0.1
        
        return min(score, 1.0)
    
    async def _validate_dag(self, dag: GeneratedDAG):
        """验证DAG有效性"""
        # 检查是否有输入和输出节点
        has_input = any(node.type == NodeType.INPUT for node in dag.nodes)
        has_output = any(node.type == NodeType.OUTPUT for node in dag.nodes)
        
        if not has_input:
            raise ValueError("DAG必须包含输入节点")
        if not has_output:
            raise ValueError("DAG必须包含输出节点")
        
        # 检查是否有孤立节点
        node_ids = {node.id for node in dag.nodes}
        connected_nodes = set()
        
        for edge in dag.edges:
            connected_nodes.add(edge.from_node)
            connected_nodes.add(edge.to_node)
        
        isolated_nodes = node_ids - connected_nodes
        if isolated_nodes and len(isolated_nodes) > 2:  # 输入输出节点可能孤立
            logger.warning(f"发现孤立节点: {isolated_nodes}")
        
        # 检查是否有环路
        if self._has_cycle(dag.nodes, dag.edges):
            raise ValueError("DAG不能包含环路")
    
    def _has_cycle(self, nodes: List[DAGNode], edges: List[DAGEdge]) -> bool:
        """检查是否有环路"""
        # 使用DFS检测环路
        adj_list = {node.id: [] for node in nodes}
        for edge in edges:
            adj_list[edge.from_node].append(edge.to_node)
        
        color = {node.id: 0 for node in nodes}  # 0: 白色, 1: 灰色, 2: 黑色
        
        def dfs(node_id):
            if color[node_id] == 1:  # 灰色，发现后向边
                return True
            if color[node_id] == 2:  # 黑色，已访问
                return False
            
            color[node_id] = 1  # 标记为灰色
            
            for neighbor in adj_list[node_id]:
                if dfs(neighbor):
                    return True
            
            color[node_id] = 2  # 标记为黑色
            return False
        
        for node in nodes:
            if color[node.id] == 0:
                if dfs(node.id):
                    return True
        
        return False

# 全局动态DAG生成器实例
dynamic_dag_generator = DynamicDAGGenerator() 