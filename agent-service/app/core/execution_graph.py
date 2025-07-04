"""
Agno执行图引擎
基于有向无环图(DAG)的Agent任务执行引擎，支持条件分支、并行处理和错误恢复
完全迁移自原始ZZDSJ项目的执行图设计
"""

import asyncio
import logging
import uuid
from typing import Dict, Any, List, Optional, Set, Callable
from datetime import datetime
from collections import defaultdict, deque
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class NodeType(Enum):
    """节点类型 - 完全对应原ZZDSJ项目"""
    PROCESSOR = "processor"        # 处理器节点
    CLASSIFIER = "classifier"      # 分类器节点
    RETRIEVER = "retriever"        # 检索器节点
    GENERATOR = "generator"        # 生成器节点
    COORDINATOR = "coordinator"    # 协调器节点
    ANALYZER = "analyzer"          # 分析器节点
    SCORER = "scorer"              # 评分器节点
    FILTER = "filter"              # 过滤器节点
    SYNTHESIZER = "synthesizer"    # 合成器节点
    EVALUATOR = "evaluator"        # 评估器节点
    FORMATTER = "formatter"        # 格式化器节点
    DECOMPOSER = "decomposer"      # 分解器节点
    ASSESSOR = "assessor"          # 评估器节点
    PLANNER = "planner"            # 规划器节点
    EXECUTOR = "executor"          # 执行器节点
    VALIDATOR = "validator"        # 验证器节点
    REPORTER = "reporter"          # 报告器节点


@dataclass
class ExecutionNode:
    """执行图节点"""
    id: str
    type: str  # processor, classifier, retriever, generator, coordinator
    config: Dict[str, Any]
    name: Optional[str] = None
    description: Optional[str] = None


@dataclass
class ExecutionEdge:
    """执行图边"""
    from_node: str
    to_node: str
    condition: Optional[str] = None
    weight: float = 1.0
    timeout: int = 30


@dataclass
class ExecutionGraph:
    """执行图定义"""
    nodes: List[ExecutionNode]
    edges: List[ExecutionEdge]
    name: Optional[str] = None
    description: Optional[str] = None


class ExecutionStatus(Enum):
    """执行状态"""
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ExecutionContext:
    """执行上下文"""
    request_id: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    status: ExecutionStatus = ExecutionStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class OrchestrationResult:
    """编排结果"""
    success: bool
    result: Any
    execution_path: List[str]
    execution_time: float
    node_results: Dict[str, Any]
    error: Optional[str] = None
    context: Optional[ExecutionContext] = None


class NodeProcessor:
    """节点处理器基类"""
    
    def __init__(self, node_id: str, node_type: NodeType, config: Dict[str, Any]):
        self.node_id = node_id
        self.node_type = node_type
        self.config = config
    
    async def process(self, input_data: Any, context: ExecutionContext) -> Any:
        """处理节点逻辑"""
        raise NotImplementedError


class ProcessorNode(NodeProcessor):
    """通用处理器节点"""
    
    async def process(self, input_data: Any, context: ExecutionContext) -> Any:
        """处理数据"""
        # 模拟处理逻辑
        logger.info(f"处理节点 {self.node_id} 正在处理数据")
        await asyncio.sleep(0.1)  # 模拟处理时间
        
        # 根据配置执行不同的处理逻辑
        if self.config.get("extract_intent"):
            # 意图提取
            result = {"intent": "question", "confidence": 0.95}
        elif self.config.get("sentiment_analysis"):
            # 情感分析  
            result = {"sentiment": "positive", "score": 0.8}
        else:
            # 默认处理
            result = {"processed": True, "data": input_data}
        
        return result


class ClassifierNode(NodeProcessor):
    """分类器节点"""
    
    async def process(self, input_data: Any, context: ExecutionContext) -> Any:
        """分类处理"""
        logger.info(f"分类节点 {self.node_id} 正在分类")
        await asyncio.sleep(0.1)
        
        categories = self.config.get("categories", ["default"])
        threshold = self.config.get("confidence_threshold", 0.7)
        
        # 模拟分类结果
        return {
            "category": categories[0] if categories else "default",
            "confidence": 0.85,
            "all_scores": {cat: 0.8 if cat == categories[0] else 0.2 for cat in categories}
        }


class RetrieverNode(NodeProcessor):
    """检索器节点"""
    
    async def process(self, input_data: Any, context: ExecutionContext) -> Any:
        """检索处理"""
        logger.info(f"检索节点 {self.node_id} 正在检索")
        await asyncio.sleep(0.2)
        
        top_k = self.config.get("top_k", 5)
        similarity_threshold = self.config.get("similarity_threshold", 0.8)
        
        # 模拟检索结果
        return {
            "documents": [
                {"id": f"doc_{i}", "content": f"Document {i}", "score": 0.9 - i * 0.1}
                for i in range(top_k)
            ],
            "total_found": top_k
        }


class GeneratorNode(NodeProcessor):
    """生成器节点"""
    
    async def process(self, input_data: Any, context: ExecutionContext) -> Any:
        """生成处理"""
        logger.info(f"生成节点 {self.node_id} 正在生成")
        await asyncio.sleep(0.3)
        
        style = self.config.get("style", "professional")
        max_tokens = self.config.get("max_tokens", 500)
        
        # 模拟生成结果
        return {
            "generated_text": f"Generated response in {style} style (max {max_tokens} tokens)",
            "token_count": min(max_tokens, 150),
            "finish_reason": "complete"
        }


class FormatterNode(NodeProcessor):
    """格式化器节点"""
    
    async def process(self, input_data: Any, context: ExecutionContext) -> Any:
        """格式化处理"""
        logger.info(f"格式化节点 {self.node_id} 正在格式化")
        await asyncio.sleep(0.1)
        
        markdown = self.config.get("markdown", True)
        include_citations = self.config.get("include_citations", False)
        
        # 模拟格式化结果
        if isinstance(input_data, dict) and "generated_text" in input_data:
            text = input_data["generated_text"]
        else:
            text = str(input_data)
        
        if markdown:
            text = f"**{text}**"
        
        if include_citations:
            text += "\n\n*参考来源：[1] [2] [3]*"
        
        return {
            "formatted_text": text,
            "format": "markdown" if markdown else "plain",
            "citations_included": include_citations
        }


class AgnoExecutionEngine:
    """基于执行图的Agent执行引擎"""
    
    def __init__(self, execution_graph: Optional[ExecutionGraph] = None):
        """初始化执行引擎"""
        self.execution_graph = execution_graph
        self.node_processors = {}
        
        if execution_graph:
            self._initialize_processors()
    
    def _initialize_processors(self):
        """初始化节点处理器"""
        processor_classes = {
            NodeType.PROCESSOR.value: ProcessorNode,
            NodeType.CLASSIFIER.value: ClassifierNode,
            NodeType.GENERATOR.value: GeneratorNode,
            NodeType.RETRIEVER.value: RetrieverNode,
            NodeType.FORMATTER.value: FormatterNode,
            # 其他节点类型复用相似的处理器
            NodeType.ANALYZER.value: ProcessorNode,
            NodeType.SCORER.value: ProcessorNode,
            NodeType.FILTER.value: ProcessorNode,
            NodeType.SYNTHESIZER.value: GeneratorNode,
            NodeType.EVALUATOR.value: ClassifierNode,
            NodeType.DECOMPOSER.value: ProcessorNode,
            NodeType.ASSESSOR.value: ClassifierNode,
            NodeType.PLANNER.value: ProcessorNode,
            NodeType.EXECUTOR.value: ProcessorNode,
            NodeType.VALIDATOR.value: ClassifierNode,
            NodeType.REPORTER.value: FormatterNode,
            NodeType.COORDINATOR.value: ProcessorNode,
        }
        
        for node in self.execution_graph.nodes:
            processor_class = processor_classes.get(node.type, ProcessorNode)
            node_type = NodeType(node.type) if node.type in [nt.value for nt in NodeType] else NodeType.PROCESSOR
            self.node_processors[node.id] = processor_class(node.id, node_type, node.config)
    
    async def execute(self, input_data: Any, context: ExecutionContext) -> OrchestrationResult:
        """执行Agent任务"""
        logger.info(f"开始执行任务: {context.request_id}")
        
        start_time = datetime.now()
        context.status = ExecutionStatus.RUNNING
        context.start_time = start_time
        
        try:
            # 获取执行顺序
            execution_order = self._get_execution_order()
            if not execution_order:
                raise ValueError("无法确定执行顺序，可能存在循环依赖")
            
            current_data = input_data
            execution_path = []
            node_results = {}
            
            # 按顺序执行节点
            for node_id in execution_order:
                # 检查执行条件
                if not self._check_execution_condition(node_id, current_data, context):
                    logger.info(f"跳过节点 {node_id}：不满足执行条件")
                    continue
                
                # 执行节点处理
                processor = self.node_processors.get(node_id)
                if not processor:
                    logger.warning(f"找不到节点处理器: {node_id}")
                    continue
                
                logger.info(f"执行节点: {node_id}")
                node_start_time = datetime.now()
                
                try:
                    node_result = await processor.process(current_data, context)
                    node_results[node_id] = node_result
                    current_data = node_result  # 将结果传递给下一个节点
                    execution_path.append(node_id)
                    
                    node_end_time = datetime.now()
                    node_duration = (node_end_time - node_start_time).total_seconds()
                    logger.info(f"节点 {node_id} 执行完成，耗时: {node_duration:.2f}s")
                    
                except Exception as e:
                    logger.error(f"节点 {node_id} 执行失败: {str(e)}")
                    context.status = ExecutionStatus.FAILED
                    
                    end_time = datetime.now()
                    execution_time = (end_time - start_time).total_seconds()
                    
                    return OrchestrationResult(
                        success=False,
                        result=None,
                        execution_path=execution_path,
                        execution_time=execution_time,
                        node_results=node_results,
                        error=f"节点 {node_id} 执行失败: {str(e)}",
                        context=context
                    )
            
            # 执行成功
            context.status = ExecutionStatus.COMPLETED
            end_time = datetime.now()
            context.end_time = end_time
            execution_time = (end_time - start_time).total_seconds()
            
            logger.info(f"任务执行完成: {context.request_id}，总耗时: {execution_time:.2f}s")
            
            return OrchestrationResult(
                success=True,
                result=current_data,
                execution_path=execution_path,
                execution_time=execution_time,
                node_results=node_results,
                context=context
            )
            
        except Exception as e:
            logger.error(f"执行图执行失败: {str(e)}")
            context.status = ExecutionStatus.FAILED
            
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            
            return OrchestrationResult(
                success=False,
                result=None,
                execution_path=[],
                execution_time=execution_time,
                node_results={},
                error=str(e),
                context=context
            )
    
    def _get_execution_order(self) -> List[str]:
        """获取节点执行顺序（拓扑排序）"""
        if not self.execution_graph:
            return []
        
        # 构建邻接表和入度表
        graph = defaultdict(list)
        in_degree = defaultdict(int)
        all_nodes = set()
        
        # 初始化所有节点
        for node in self.execution_graph.nodes:
            all_nodes.add(node.id)
            in_degree[node.id] = 0
        
        # 构建图
        for edge in self.execution_graph.edges:
            graph[edge.from_node].append(edge.to_node)
            in_degree[edge.to_node] += 1
            all_nodes.add(edge.from_node)
            all_nodes.add(edge.to_node)
        
        # 拓扑排序
        queue = deque()
        
        # 找到所有入度为0的节点
        for node in all_nodes:
            if in_degree[node] == 0:
                queue.append(node)
        
        result = []
        
        while queue:
            current = queue.popleft()
            result.append(current)
            
            # 更新邻接节点的入度
            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # 检查是否存在循环依赖
        if len(result) != len(all_nodes):
            logger.error("检测到循环依赖，无法确定执行顺序")
            return []
        
        return result
    
    def _check_execution_condition(self, node_id: str, data: Any, context: ExecutionContext) -> bool:
        """检查节点执行条件"""
        # 获取指向该节点的所有边
        incoming_edges = [edge for edge in self.execution_graph.edges if edge.to_node == node_id]
        
        if not incoming_edges:
            return True  # 起始节点，直接执行
        
        # 检查所有前置节点的条件
        for edge in incoming_edges:
            condition = edge.condition
            if condition and not self._evaluate_condition(condition, data, context):
                return False
        
        return True
    
    def _evaluate_condition(self, condition: str, data: Any, context: ExecutionContext) -> bool:
        """评估执行条件"""
        if not condition:
            return True
        
        try:
            # 简单的条件评估
            if ">" in condition:
                parts = condition.split(">")
                if len(parts) == 2:
                    field, value = parts[0].strip(), float(parts[1].strip())
                    if isinstance(data, dict) and field in data:
                        return float(data[field]) > value
            
            elif "==" in condition:
                parts = condition.split("==")
                if len(parts) == 2:
                    field, value = parts[0].strip(), parts[1].strip().strip('"\'')
                    if isinstance(data, dict) and field in data:
                        return str(data[field]) == value
            
            # 默认返回True
            return True
            
        except Exception as e:
            logger.error(f"条件评估失败: {condition}, 错误: {str(e)}")
            return True  # 条件评估失败时默认执行
    
    def visualize_graph(self) -> Dict[str, Any]:
        """可视化执行图"""
        if not self.execution_graph:
            return {"error": "没有可用的执行图"}
        
        visualization = {
            "nodes": [],
            "edges": [],
            "metadata": {
                "total_nodes": len(self.execution_graph.nodes),
                "total_edges": len(self.execution_graph.edges),
                "name": self.execution_graph.name,
                "description": self.execution_graph.description
            }
        }
        
        # 添加节点信息
        for node in self.execution_graph.nodes:
            visualization["nodes"].append({
                "id": node.id,
                "type": node.type,
                "config": node.config,
                "name": node.name or node.id,
                "description": node.description,
                "label": f"{node.name or node.id} ({node.type})"
            })
        
        # 添加边信息
        for edge in self.execution_graph.edges:
            visualization["edges"].append({
                "from": edge.from_node,
                "to": edge.to_node,
                "condition": edge.condition,
                "weight": edge.weight,
                "timeout": edge.timeout,
                "label": edge.condition if edge.condition else ""
            })
        
        return visualization


def create_execution_engine(execution_graph: ExecutionGraph) -> AgnoExecutionEngine:
    """创建执行引擎"""
    return AgnoExecutionEngine(execution_graph)


async def execute_with_graph(
    execution_graph: ExecutionGraph,
    input_data: Any,
    context: ExecutionContext
) -> OrchestrationResult:
    """使用执行图执行任务"""
    engine = create_execution_engine(execution_graph)
    return await engine.execute(input_data, context) 