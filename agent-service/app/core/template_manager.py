"""
Agno智能体模版管理器
完全迁移自原始ZZDSJ项目的三种智能体模版：基础对话、知识库问答、深度思考
每个模版都基于DAG执行图进行设计，支持减法操作的预设流程
"""

import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

from app.schemas.agent_schemas import TemplateType
from app.core.execution_graph import (
    ExecutionGraph, ExecutionNode, ExecutionEdge, 
    AgnoExecutionEngine, create_execution_engine
)

logger = logging.getLogger(__name__)


class AgentTemplate:
    """智能体模版定义 - 完全对应原ZZDSJ项目结构"""
    
    def __init__(
        self,
        template_id: str,
        name: str,
        role: str,
        description: str,
        use_cases: List[str],
        estimated_cost: str,
        execution_graph: ExecutionGraph,
        default_tools: List[str],
        model_config: Dict[str, Any],
        capabilities: List[str],
        instructions: List[str],
        agno_level: int
    ):
        self.template_id = template_id
        self.name = name
        self.role = role
        self.description = description
        self.use_cases = use_cases
        self.estimated_cost = estimated_cost
        self.execution_graph = execution_graph
        self.default_tools = default_tools
        self.model_config = model_config
        self.capabilities = capabilities
        self.instructions = instructions
        self.agno_level = agno_level


# ==================== 基础对话模版 (Agno Level 1) ====================

BASIC_CONVERSATION_EXECUTION_GRAPH = ExecutionGraph(
    name="基础对话执行图",
    description="简单的线性执行流程，专注于快速响应",
    nodes=[
        ExecutionNode(
            id="input_analysis",
            type="processor",
            name="输入分析器",
            description="分析用户输入的意图和情感",
            config={
                "max_context": 10,
                "extract_intent": True,
                "sentiment_analysis": True,
                "processing_timeout": 5
            }
        ),
        ExecutionNode(
            id="intent_recognition", 
            type="classifier",
            name="意图识别器",
            description="识别用户问题的类型和意图",
            config={
                "categories": ["question", "request", "chat", "task"],
                "confidence_threshold": 0.7,
                "fallback_category": "chat"
            }
        ),
        ExecutionNode(
            id="context_enrichment",
            type="processor",
            name="上下文增强器",
            description="丰富对话上下文信息",
            config={
                "include_history": True,
                "max_history_turns": 5,
                "context_window": 2048
            }
        ),
        ExecutionNode(
            id="response_generation",
            type="generator", 
            name="响应生成器",
            description="生成自然流畅的回复",
            config={
                "style": "friendly",
                "max_tokens": 500,
                "temperature": 0.7,
                "stream": True
            }
        ),
        ExecutionNode(
            id="output_formatting",
            type="formatter",
            name="输出格式化器",
            description="格式化最终输出",
            config={
                "markdown": True,
                "include_citations": False,
                "emoji_support": True
            }
        )
    ],
    edges=[
        ExecutionEdge("input_analysis", "intent_recognition"),
        ExecutionEdge("intent_recognition", "context_enrichment"),
        ExecutionEdge("context_enrichment", "response_generation"),
        ExecutionEdge("response_generation", "output_formatting")
    ]
)

BASIC_CONVERSATION_TEMPLATE = AgentTemplate(
    template_id=TemplateType.BASIC_CONVERSATION.value,
    name="基础对话助手",
    role="assistant",
    description="友好的多轮对话助手，提供自然流畅的交互体验",
    use_cases=["客户服务", "日常聊天", "简单咨询", "信息查询"],
    estimated_cost="低",
    execution_graph=BASIC_CONVERSATION_EXECUTION_GRAPH,
    default_tools=["search", "calculator", "datetime", "weather"],
    model_config={
        "preferred_models": ["gpt-4o-mini", "claude-3-haiku"],
        "temperature": 0.7,
        "max_tokens": 1000,
        "response_format": "text",
        "stream": True
    },
    capabilities=[
        "多轮对话",
        "上下文理解", 
        "个性化回复",
        "情感识别",
        "意图理解"
    ],
    instructions=[
        "你是一个友好、专业的AI助手",
        "保持对话的自然流畅性",
        "准确理解用户意图并提供有帮助的回答",
        "在不确定时主动询问澄清",
        "保持积极正面的沟通态度"
    ],
    agno_level=1
)


# ==================== 知识库问答模版 (Agno Level 2-3) ====================

KNOWLEDGE_BASE_EXECUTION_GRAPH = ExecutionGraph(
    name="知识库问答执行图",
    description="基于知识检索的复杂推理流程",
    nodes=[
        ExecutionNode(
            id="question_analysis",
            type="analyzer",
            name="问题分析器",
            description="深度分析用户问题",
            config={
                "extract_entities": True,
                "extract_keywords": True,
                "query_expansion": True,
                "semantic_analysis": True
            }
        ),
        ExecutionNode(
            id="kb_retrieval",
            type="retriever",
            name="知识库检索器",
            description="从知识库中检索相关文档",
            config={
                "top_k": 5,
                "similarity_threshold": 0.8,
                "rerank": True,
                "embedding_model": "text-embedding-ada-002"
            }
        ),
        ExecutionNode(
            id="relevance_scoring",
            type="scorer",
            name="相关性评分器",
            description="对检索结果进行相关性评分",
            config={
                "algorithm": "semantic",
                "combine_scores": True,
                "min_relevance": 0.6,
                "score_weights": {"semantic": 0.7, "keyword": 0.3}
            }
        ),
        ExecutionNode(
            id="document_filtering",
            type="filter",
            name="文档过滤器",
            description="过滤和选择最相关的文档",
            config={
                "max_documents": 3,
                "diversity_threshold": 0.3,
                "quality_threshold": 0.7
            }
        ),
        ExecutionNode(
            id="answer_synthesis",
            type="synthesizer",
            name="答案合成器",
            description="基于检索文档合成答案",
            config={
                "include_citations": True,
                "max_synthesis_length": 1000,
                "preserve_sources": True,
                "reasoning_steps": True
            }
        ),
        ExecutionNode(
            id="confidence_evaluation",
            type="evaluator",
            name="置信度评估器",
            description="评估答案的可信度",
            config={
                "min_confidence": 0.7,
                "uncertainty_handling": True,
                "evidence_strength": True
            }
        ),
        ExecutionNode(
            id="citation_formatting",
            type="formatter",
            name="引用格式化器",
            description="格式化引用和来源信息",
            config={
                "citation_style": "numbered",
                "include_urls": True,
                "source_metadata": True
            }
        )
    ],
    edges=[
        ExecutionEdge("question_analysis", "kb_retrieval"),
        ExecutionEdge("kb_retrieval", "relevance_scoring"),
        ExecutionEdge("relevance_scoring", "document_filtering"),
        ExecutionEdge("document_filtering", "answer_synthesis"),
        ExecutionEdge("answer_synthesis", "confidence_evaluation"),
        ExecutionEdge("confidence_evaluation", "citation_formatting")
    ]
)

KNOWLEDGE_BASE_TEMPLATE = AgentTemplate(
    template_id=TemplateType.KNOWLEDGE_BASE.value,
    name="知识库问答专家",
    role="specialist",
    description="基于组织知识库的专业问答助手，提供准确可信的信息",
    use_cases=["技术支持", "产品咨询", "政策解读", "文档查询"],
    estimated_cost="中",
    execution_graph=KNOWLEDGE_BASE_EXECUTION_GRAPH,
    default_tools=["knowledge_search", "document_analyzer", "citation_generator", "fact_checker"],
    model_config={
        "preferred_models": ["gpt-4", "claude-3-opus"],
        "temperature": 0.3,
        "max_tokens": 2000,
        "response_format": "structured"
    },
    capabilities=[
        "知识检索",
        "文档分析",
        "引用生成",
        "可信度评估",
        "多源信息整合"
    ],
    instructions=[
        "你是一个基于知识库的专业问答助手",
        "始终基于检索到的文档内容回答问题",
        "为所有信息提供准确的引用来源",
        "当信息不确定或不完整时，明确说明",
        "优先使用最新、最权威的文档内容"
    ],
    agno_level=2
)


# ==================== 深度思考模版 (Agno Level 4-5) ====================

DEEP_THINKING_EXECUTION_GRAPH = ExecutionGraph(
    name="深度思考执行图",
    description="复杂的多步推理和团队协作流程",
    nodes=[
        ExecutionNode(
            id="task_decomposition",
            type="decomposer",
            name="任务分解器",
            description="将复杂任务分解为子任务",
            config={
                "max_subtasks": 10,
                "decomposition_strategy": "hierarchical",
                "complexity_analysis": True
            }
        ),
        ExecutionNode(
            id="complexity_assessment",
            type="assessor",
            name="复杂度评估器",
            description="评估任务的复杂程度",
            config={
                "complexity_metrics": ["scope", "uncertainty", "dependencies"],
                "threshold": 0.8,
                "risk_assessment": True
            }
        ),
        ExecutionNode(
            id="planning",
            type="planner",
            name="策略规划器",
            description="制定执行策略和计划",
            config={
                "strategy": "priority_based",
                "resource_allocation": True,
                "contingency_planning": True
            }
        ),
        ExecutionNode(
            id="parallel_execution",
            type="executor",
            name="并行执行器",
            description="并行处理多个子任务",
            config={
                "max_parallel": 3,
                "load_balancing": True,
                "error_recovery": True
            }
        ),
        ExecutionNode(
            id="result_synthesis",
            type="synthesizer",
            name="结果合成器",
            description="整合各个子任务的结果",
            config={
                "method": "weighted_combination",
                "conflict_resolution": True,
                "consistency_check": True
            }
        ),
        ExecutionNode(
            id="quality_check",
            type="validator",
            name="质量检查器",
            description="验证结果的质量和一致性",
            config={
                "validation_criteria": ["completeness", "consistency", "accuracy"],
                "quality_threshold": 0.8
            }
        ),
        ExecutionNode(
            id="team_coordination",
            type="coordinator",
            name="团队协调器",
            description="协调多个智能体的协作",
            config={
                "team_size": 3,
                "collaboration_mode": "consensus",
                "conflict_resolution": "voting"
            }
        ),
        ExecutionNode(
            id="final_reporting",
            type="reporter",
            name="最终报告器",
            description="生成综合分析报告",
            config={
                "report_format": "comprehensive",
                "include_methodology": True,
                "executive_summary": True
            }
        )
    ],
    edges=[
        ExecutionEdge("task_decomposition", "complexity_assessment"),
        ExecutionEdge("complexity_assessment", "planning"),
        ExecutionEdge("planning", "parallel_execution"),
        ExecutionEdge("parallel_execution", "result_synthesis"),
        ExecutionEdge("result_synthesis", "quality_check"),
        ExecutionEdge("quality_check", "team_coordination", condition="complexity > 0.8"),
        ExecutionEdge("quality_check", "final_reporting", condition="complexity <= 0.8"),
        ExecutionEdge("team_coordination", "final_reporting")
    ]
)

DEEP_THINKING_TEMPLATE = AgentTemplate(
    template_id=TemplateType.DEEP_THINKING.value,
    name="深度思考分析师",
    role="analyst",
    description="专业的复杂问题分析师，支持多步推理和团队协作",
    use_cases=["战略分析", "研究报告", "决策支持", "复杂问题解决"],
    estimated_cost="高",
    execution_graph=DEEP_THINKING_EXECUTION_GRAPH,
    default_tools=["reasoning", "research", "data_analysis", "collaboration", "planning"],
    model_config={
        "preferred_models": ["gpt-4", "claude-3-opus"],
        "temperature": 0.5,
        "max_tokens": 4000,
        "response_format": "structured"
    },
    capabilities=[
        "任务分解",
        "多步推理",
        "团队协作",
        "决策支持",
        "系统性分析"
    ],
    instructions=[
        "你是一个专业的深度分析师",
        "对复杂问题进行系统性分解和分析",
        "运用多种推理方法和工具",
        "在必要时协调团队共同解决问题",
        "提供详细的分析过程和结论"
    ],
    agno_level=4
)


# ==================== 模版注册表 ====================

AVAILABLE_TEMPLATES: Dict[str, AgentTemplate] = {
    TemplateType.BASIC_CONVERSATION.value: BASIC_CONVERSATION_TEMPLATE,
    TemplateType.KNOWLEDGE_BASE.value: KNOWLEDGE_BASE_TEMPLATE,
    TemplateType.DEEP_THINKING.value: DEEP_THINKING_TEMPLATE
}


class AgnoTemplateManager:
    """智能体模版管理器 - 完全基于原ZZDSJ项目设计"""
    
    def __init__(self):
        """初始化模版管理器"""
        self.templates = AVAILABLE_TEMPLATES
        self._template_cache = {}
    
    def get_available_templates(self) -> List[Dict[str, Any]]:
        """获取所有可用模版的信息"""
        template_info = []
        for template in self.templates.values():
            template_info.append({
                "template_id": template.template_id,
                "name": template.name,
                "description": template.description,
                "role": template.role,
                "use_cases": template.use_cases,
                "estimated_cost": template.estimated_cost,
                "capabilities": template.capabilities,
                "default_tools": template.default_tools,
                "agno_level": template.agno_level,
                "execution_graph_summary": {
                    "total_nodes": len(template.execution_graph.nodes),
                    "total_edges": len(template.execution_graph.edges),
                    "complexity": "low" if template.agno_level == 1 else "medium" if template.agno_level <= 3 else "high"
                }
            })
        return template_info
    
    def get_template_details(self, template_id: str) -> Optional[Dict[str, Any]]:
        """获取指定模版的详细信息"""
        try:
            template = self.get_template(template_id)
            if not template:
                return None
                
            return {
                "template_id": template.template_id,
                "name": template.name,
                "description": template.description,
                "role": template.role,
                "use_cases": template.use_cases,
                "estimated_cost": template.estimated_cost,
                "capabilities": template.capabilities,
                "default_tools": template.default_tools,
                "model_config": template.model_config,
                "instructions": template.instructions,
                "agno_level": template.agno_level,
                "execution_graph": {
                    "name": template.execution_graph.name,
                    "description": template.execution_graph.description,
                    "nodes": [
                        {
                            "id": node.id,
                            "type": node.type,
                            "name": node.name,
                            "description": node.description,
                            "config": node.config
                        } for node in template.execution_graph.nodes
                    ],
                    "edges": [
                        {
                            "from": edge.from_node,
                            "to": edge.to_node,
                            "condition": edge.condition,
                            "weight": edge.weight,
                            "timeout": edge.timeout
                        } for edge in template.execution_graph.edges
                    ]
                }
            }
        except Exception as e:
            logger.error(f"获取模版详情失败: {str(e)}")
            return None
    
    def get_template(self, template_id: str) -> Optional[AgentTemplate]:
        """获取指定的模版"""
        return self.templates.get(template_id)
    
    def list_available_templates(self) -> List[AgentTemplate]:
        """列出所有可用的模版"""
        return list(self.templates.values())
    
    def get_template_by_use_case(self, use_case: str) -> List[AgentTemplate]:
        """根据使用场景推荐模版"""
        matching_templates = []
        for template in self.templates.values():
            if any(use_case.lower() in uc.lower() for uc in template.use_cases):
                matching_templates.append(template)
        return matching_templates
    
    def get_template_by_agno_level(self, level: int) -> List[AgentTemplate]:
        """根据Agno级别获取模版"""
        return [template for template in self.templates.values() if template.agno_level == level]
    
    def create_execution_engine(self, template_id: str) -> Optional[AgnoExecutionEngine]:
        """为指定模版创建执行引擎"""
        template = self.get_template(template_id)
        if not template:
            return None
        
        return create_execution_engine(template.execution_graph)
    
    def get_template_tools(self, template_id: str) -> List[str]:
        """获取模版的默认工具列表"""
        template = self.get_template(template_id)
        return template.default_tools if template else []
    
    def validate_template_config(
        self,
        template_id: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """验证模版配置"""
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        template = self.get_template(template_id)
        if not template:
            validation_result["valid"] = False
            validation_result["errors"].append(f"未找到模版: {template_id}")
            return validation_result
        
        # 验证必要的配置项
        required_fields = ["name", "model"]
        for field in required_fields:
            if field not in config or not config[field]:
                validation_result["errors"].append(f"缺少必要字段: {field}")
        
        if validation_result["errors"]:
            validation_result["valid"] = False
        
        return validation_result


# 单例模式获取模版管理器
_template_manager_instance = None

def get_template_manager() -> AgnoTemplateManager:
    """获取模版管理器实例"""
    global _template_manager_instance
    if _template_manager_instance is None:
        _template_manager_instance = AgnoTemplateManager()
    return _template_manager_instance


def get_template(template_id: str) -> Optional[AgentTemplate]:
    """获取指定的模版"""
    manager = get_template_manager()
    return manager.get_template(template_id)


def list_available_templates() -> List[AgentTemplate]:
    """列出所有可用的模版"""
    manager = get_template_manager()
    return manager.list_available_templates()


def get_available_templates() -> List[Dict[str, Any]]:
    """获取所有可用模版的信息"""
    manager = get_template_manager()
    return manager.get_available_templates()


def recommend_templates(use_case: str = None, agno_level: int = None) -> List[AgentTemplate]:
    """推荐模版"""
    manager = get_template_manager()
    
    if use_case:
        return manager.get_template_by_use_case(use_case)
    elif agno_level:
        return manager.get_template_by_agno_level(agno_level)
    else:
        return manager.list_available_templates()
