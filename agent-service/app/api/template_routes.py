"""
智能体模板相关的API路由
完全基于原ZZDSJ项目的三种智能体模板设计
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
import logging

from app.core.template_manager import (
    get_template_manager, get_template, list_available_templates,
    get_available_templates, recommend_templates
)
from app.schemas.agent_schemas import TemplateType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("/list")
async def get_template_list(
    agno_level: Optional[int] = Query(None, description="按Agno级别过滤"),
    use_case: Optional[str] = Query(None, description="按使用场景过滤")
):
    """
    获取智能体模板列表
    
    支持按Agno级别和使用场景过滤：
    - Level 1: 基础对话助手 (basic_conversation)
    - Level 2-3: 知识库问答专家 (knowledge_base) 
    - Level 4-5: 深度思考分析师 (deep_thinking)
    """
    try:
        manager = get_template_manager()
        
        if agno_level:
            templates = manager.get_template_by_agno_level(agno_level)
            template_info = []
            for template in templates:
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
        elif use_case:
            templates = manager.get_template_by_use_case(use_case)
            template_info = []
            for template in templates:
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
        else:
            template_info = manager.get_available_templates()
        
        return {
            "success": True,
            "data": {
                "templates": template_info,
                "total": len(template_info)
            }
        }
        
    except Exception as e:
        logger.error(f"获取模板列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取模板列表失败: {str(e)}")


@router.get("/{template_id}")
async def get_template_details(template_id: str):
    """
    获取指定模板的详细信息，包含完整的DAG执行图
    
    支持的模板ID:
    - basic_conversation: 基础对话助手
    - knowledge_base: 知识库问答专家
    - deep_thinking: 深度思考分析师
    """
    try:
        # 验证模板ID
        try:
            TemplateType(template_id)
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail=f"无效的模板ID: {template_id}。支持的模板: {[t.value for t in TemplateType]}"
            )
        
        manager = get_template_manager()
        template_details = manager.get_template_details(template_id)
        
        if not template_details:
            raise HTTPException(status_code=404, detail=f"未找到模板: {template_id}")
        
        return {
            "success": True,
            "data": template_details
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取模板详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取模板详情失败: {str(e)}")


@router.get("/{template_id}/tools")
async def get_template_tools(template_id: str):
    """
    获取指定模板的默认工具配置
    
    返回该模板推荐使用的工具列表和配置
    """
    try:
        # 验证模板ID
        try:
            TemplateType(template_id)
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail=f"无效的模板ID: {template_id}。支持的模板: {[t.value for t in TemplateType]}"
            )
        
        manager = get_template_manager()
        template = manager.get_template(template_id)
        
        if not template:
            raise HTTPException(status_code=404, detail=f"未找到模板: {template_id}")
        
        # 获取工具详细配置
        tools_config = []
        for tool_name in template.default_tools:
            tool_config = {
                "name": tool_name,
                "display_name": _get_tool_display_name(tool_name),
                "description": _get_tool_description(tool_name),
                "category": _get_tool_category(tool_name),
                "enabled": True,
                "config": _get_tool_default_config(tool_name)
            }
            tools_config.append(tool_config)
        
        return {
            "success": True,
            "data": {
                "template_id": template_id,
                "template_name": template.name,
                "tools": tools_config,
                "total_tools": len(tools_config)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取模板工具配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取模板工具配置失败: {str(e)}")


@router.get("/{template_id}/execution-graph")
async def get_template_execution_graph(template_id: str):
    """
    获取指定模板的DAG执行图可视化数据
    
    返回可用于前端流程图渲染的节点和边数据
    """
    try:
        # 验证模板ID
        try:
            TemplateType(template_id)
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail=f"无效的模板ID: {template_id}。支持的模板: {[t.value for t in TemplateType]}"
            )
        
        manager = get_template_manager()
        execution_engine = manager.create_execution_engine(template_id)
        
        if not execution_engine:
            raise HTTPException(status_code=404, detail=f"未找到模板: {template_id}")
        
        # 获取执行图可视化数据
        visualization_data = execution_engine.visualize_graph()
        
        # 为前端添加布局和样式信息
        for i, node in enumerate(visualization_data["nodes"]):
            node["position"] = {
                "x": 100 + (i % 3) * 200,
                "y": 100 + (i // 3) * 150
            }
            node["style"] = _get_node_style(node["type"])
        
        return {
            "success": True,
            "data": {
            "template_id": template_id,
                "execution_graph": visualization_data,
                "layout_type": "hierarchical",
                "is_dag": True
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取执行图失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取执行图失败: {str(e)}")


@router.get("/{template_id}/validate")
async def validate_template_config(template_id: str, config: dict):
    """
    验证模板配置的有效性
    """
    try:
        # 验证模板ID
        try:
            TemplateType(template_id)
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail=f"无效的模板ID: {template_id}。支持的模板: {[t.value for t in TemplateType]}"
            )
        
        manager = get_template_manager()
        validation_result = manager.validate_template_config(template_id, config)
        
        return {
            "success": True,
            "data": validation_result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"验证模板配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"验证模板配置失败: {str(e)}")


# 辅助函数

def _get_tool_display_name(tool_name: str) -> str:
    """获取工具显示名称"""
    tool_names = {
        "search": "网络搜索",
        "calculator": "计算器",
        "datetime": "日期时间",
        "weather": "天气查询",
        "knowledge_search": "知识库搜索",
        "document_analyzer": "文档分析",
        "citation_generator": "引用生成",
        "fact_checker": "事实检查",
        "reasoning": "推理工具",
        "research": "研究工具",
        "data_analysis": "数据分析",
        "collaboration": "协作工具",
        "planning": "规划工具"
    }
    return tool_names.get(tool_name, tool_name.replace("_", " ").title())


def _get_tool_description(tool_name: str) -> str:
    """获取工具描述"""
    descriptions = {
        "search": "在互联网上搜索实时信息",
        "calculator": "执行数学计算和公式求解",
        "datetime": "获取当前时间和日期信息",
        "weather": "查询天气预报和气象信息",
        "knowledge_search": "在知识库中搜索相关文档",
        "document_analyzer": "分析和提取文档内容",
        "citation_generator": "生成标准格式的引用",
        "fact_checker": "验证信息的准确性",
        "reasoning": "进行逻辑推理和分析",
        "research": "执行深度研究和信息收集",
        "data_analysis": "分析数据并生成洞察",
        "collaboration": "协调多个智能体协作",
        "planning": "制定执行计划和策略"
    }
    return descriptions.get(tool_name, f"{tool_name}工具")


def _get_tool_category(tool_name: str) -> str:
    """获取工具分类"""
    categories = {
        "search": "信息检索",
        "calculator": "计算工具",
        "datetime": "系统工具",
        "weather": "信息服务",
        "knowledge_search": "知识管理",
        "document_analyzer": "文档处理",
        "citation_generator": "格式化工具",
        "fact_checker": "验证工具",
        "reasoning": "分析工具",
        "research": "信息收集",
        "data_analysis": "数据处理",
        "collaboration": "协作工具",
        "planning": "规划工具"
    }
    return categories.get(tool_name, "通用工具")


def _get_tool_default_config(tool_name: str) -> dict:
    """获取工具默认配置"""
    configs = {
        "search": {
            "max_results": 5,
            "timeout": 10,
            "safe_search": True
        },
        "calculator": {
            "precision": 10,
            "allow_complex": False
        },
        "datetime": {
            "timezone": "Asia/Shanghai",
            "format": "ISO"
        },
        "weather": {
            "units": "metric",
            "include_forecast": True
        },
        "knowledge_search": {
            "top_k": 5,
            "similarity_threshold": 0.8,
            "rerank": True
        },
        "document_analyzer": {
            "extract_metadata": True,
            "chunk_size": 1000,
            "overlap": 200
        },
        "reasoning": {
            "enable_chain_of_thought": True,
            "max_steps": 10,
            "show_reasoning": True
        }
    }
    return configs.get(tool_name, {})


def _get_node_style(node_type: str) -> dict:
    """获取节点样式"""
    styles = {
        "processor": {
            "backgroundColor": "#e3f2fd",
            "borderColor": "#2196f3",
            "color": "#1976d2"
        },
        "classifier": {
            "backgroundColor": "#f3e5f5",
            "borderColor": "#9c27b0",
            "color": "#7b1fa2"
        },
        "retriever": {
            "backgroundColor": "#e8f5e8",
            "borderColor": "#4caf50",
            "color": "#388e3c"
        },
        "generator": {
            "backgroundColor": "#fff3e0",
            "borderColor": "#ff9800",
            "color": "#f57c00"
        },
        "formatter": {
            "backgroundColor": "#fce4ec",
            "borderColor": "#e91e63",
            "color": "#c2185b"
        },
        "analyzer": {
            "backgroundColor": "#e0f2f1",
            "borderColor": "#009688",
            "color": "#00695c"
        },
        "scorer": {
            "backgroundColor": "#f1f8e9",
            "borderColor": "#8bc34a",
            "color": "#558b2f"
        },
        "synthesizer": {
            "backgroundColor": "#e1f5fe",
            "borderColor": "#03a9f4",
            "color": "#0277bd"
        },
        "coordinator": {
            "backgroundColor": "#fafafa",
            "borderColor": "#607d8b",
            "color": "#455a64"
        }
    }
    return styles.get(node_type, {
        "backgroundColor": "#f5f5f5",
        "borderColor": "#9e9e9e",
        "color": "#616161"
    })
