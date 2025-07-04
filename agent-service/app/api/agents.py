"""
智能体服务API接口
支持智能体的创建、管理、配置和对话功能
"""

from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any, Optional
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/agents", tags=["智能体管理"])

# ==================== 智能体模板相关接口 ====================

@router.get("/templates")
async def get_agent_templates(category: Optional[str] = None):
    """
    获取智能体模板列表
    支持按分类筛选：simple-qa, deep-thinking, intelligent-planning
    """
    try:
        # 模拟模板数据
        templates = [
            {
                "template_id": "simple-qa",
                "name": "简单问答助手",
                "description": "适用于基础问答场景",
                "category": "simple-qa",
                "agentType": "simple-qa",
                "useCases": ["客服", "FAQ", "简单咨询"],
                "tags": ["快速", "高效", "基础"],
                "estimated_cost": "低"
            },
            {
                "template_id": "deep-thinking",
                "name": "深度思考分析师",
                "description": "适用于复杂分析和推理",
                "category": "deep-thinking",
                "agentType": "deep-thinking",
                "useCases": ["研究分析", "决策支持", "复杂推理"],
                "tags": ["深度", "分析", "推理"],
                "estimated_cost": "中"
            },
            {
                "template_id": "intelligent-planning",
                "name": "智能规划专家",
                "description": "适用于任务规划和协调",
                "category": "intelligent-planning",
                "agentType": "intelligent-planning",
                "useCases": ["项目规划", "任务分解", "流程优化"],
                "tags": ["规划", "协调", "优化"],
                "estimated_cost": "高"
            }
        ]
        
        if category:
            templates = [t for t in templates if t["category"] == category]
        
        return {"templates": templates}
    except Exception as e:
        logger.error(f"获取模板列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取模板列表失败: {str(e)}"
        )

@router.get("/templates/{template_id}")
async def get_agent_template(template_id: str):
    """获取指定模板详情"""
    try:
        # 模拟模板详情
        template_details = {
            "simple-qa": {
                "template_id": "simple-qa",
                "name": "简单问答助手",
                "description": "适用于基础问答场景的轻量级智能体",
                "category": "simple-qa",
                "agentType": "simple-qa",
                "useCases": ["客服", "FAQ", "简单咨询"],
                "tags": ["快速", "高效", "基础"],
                "estimated_cost": "低",
                "steps": [
                    {"id": "model", "title": "基础模型", "description": "选择轻量级快速响应模型"},
                    {"id": "instructions", "title": "指令配置", "description": "设置系统提示词和响应模式"},
                    {"id": "tools", "title": "基础工具", "description": "配置查询和信息检索工具"},
                    {"id": "optimization", "title": "性能优化", "description": "配置响应速度和并发参数"}
                ]
            },
            "deep-thinking": {
                "template_id": "deep-thinking",
                "name": "深度思考分析师",
                "description": "适用于复杂分析和推理的高级智能体",
                "category": "deep-thinking",
                "agentType": "deep-thinking",
                "useCases": ["研究分析", "决策支持", "复杂推理"],
                "tags": ["深度", "分析", "推理"],
                "estimated_cost": "中",
                "steps": [
                    {"id": "model", "title": "推理模型", "description": "选择支持复杂推理的模型"},
                    {"id": "reasoning", "title": "推理配置", "description": "配置思维链和分析策略"},
                    {"id": "knowledge", "title": "知识系统", "description": "配置知识库和检索增强"},
                    {"id": "memory", "title": "记忆系统", "description": "配置上下文记忆和学习能力"},
                    {"id": "tools", "title": "分析工具", "description": "配置数据分析和推理工具"}
                ]
            }
        }
        
        template = template_details.get(template_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"模板 {template_id} 不存在"
            )
        return template
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取模板详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取模板详情失败: {str(e)}"
        )


# ==================== 智能体CRUD接口 ====================

@router.post("/create")
async def create_agent(request: dict):
    """
    创建智能体
    支持基于模板的快速创建和自定义配置
    """
    try:
        # 生成智能体ID
        agent_id = f"agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 模拟创建智能体
        agent = {
            "agent_id": agent_id,
            "name": request.get("basic_configuration", {}).get("agent_name", "新智能体"),
            "description": request.get("basic_configuration", {}).get("agent_description", ""),
            "template_id": request.get("template_selection", {}).get("template_id", ""),
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "config": request
        }
        
        return agent
    except Exception as e:
        logger.error(f"创建智能体失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建智能体失败: {str(e)}"
        )

@router.get("/")
async def get_agents(
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    status_filter: Optional[str] = None
):
    """获取智能体列表"""
    try:
        # 模拟智能体列表
        agents = [
            {
                "agent_id": "agent_001",
                "name": "客服助手",
                "description": "处理客户咨询的智能助手",
                "template_id": "simple-qa",
                "status": "active",
                "created_at": "2024-01-15T10:00:00Z",
                "updated_at": "2024-01-15T10:00:00Z",
                "last_used": "2024-01-16T09:30:00Z",
                "usage_count": 156
            },
            {
                "agent_id": "agent_002",
                "name": "研究分析师",
                "description": "深度分析和研究的专业助手",
                "template_id": "deep-thinking",
                "status": "active",
                "created_at": "2024-01-14T14:20:00Z",
                "updated_at": "2024-01-15T16:45:00Z",
                "last_used": "2024-01-16T08:15:00Z",
                "usage_count": 89
            }
        ]
        
        # 应用筛选
        if search:
            agents = [a for a in agents if search.lower() in a["name"].lower() or search.lower() in a["description"].lower()]
        
        if status_filter:
            agents = [a for a in agents if a["status"] == status_filter]
        
        # 分页
        total = len(agents)
        start = (page - 1) * page_size
        end = start + page_size
        agents_page = agents[start:end]
        
        return {
            "agents": agents_page,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }
    except Exception as e:
        logger.error(f"获取智能体列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取智能体列表失败: {str(e)}"
        )

@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    """获取智能体详情"""
    try:
        # 模拟智能体详情
        agent = {
            "agent_id": agent_id,
            "name": "客服助手",
            "description": "处理客户咨询的智能助手",
            "template_id": "simple-qa",
            "status": "active",
            "created_at": "2024-01-15T10:00:00Z",
            "updated_at": "2024-01-15T10:00:00Z",
            "last_used": "2024-01-16T09:30:00Z",
            "usage_count": 156,
            "config": {
                "template_selection": {
                    "template_id": "simple-qa",
                    "template_name": "简单问答助手"
                },
                "basic_configuration": {
                    "agent_name": "客服助手",
                    "agent_description": "处理客户咨询的智能助手",
                    "system_prompt": "你是一个专业的客服助手，请友好、准确地回答用户问题。",
                    "language": "zh-CN",
                    "response_style": "friendly"
                },
                "model_configuration": {
                    "provider": "zhipu",
                    "model": "glm-4",
                    "temperature": 0.7,
                    "max_tokens": 1000
                }
            }
        }
        return agent
    except Exception as e:
        logger.error(f"获取智能体详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取智能体详情失败: {str(e)}"
        )

@router.put("/{agent_id}")
async def update_agent(agent_id: str, request: dict):
    """更新智能体配置"""
    try:
        # 模拟更新智能体
        updated_agent = {
            "agent_id": agent_id,
            "name": request.get("name", "更新的智能体"),
            "description": request.get("description", ""),
            "status": request.get("status", "active"),
            "updated_at": datetime.now().isoformat(),
            "config": request
        }
        
        return updated_agent
    except Exception as e:
        logger.error(f"更新智能体失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新智能体失败: {str(e)}"
        )

@router.delete("/{agent_id}")
async def delete_agent(agent_id: str):
    """删除智能体"""
    try:
        return {"message": f"智能体 {agent_id} 删除成功"}
    except Exception as e:
        logger.error(f"删除智能体失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除智能体失败: {str(e)}"
        )


# ==================== 智能体对话接口 ====================

@router.post("/{agent_id}/chat")
async def chat_with_agent(agent_id: str, request: dict):
    """与智能体对话（非流式）"""
    try:
        message = request.get("message", "")
        session_id = request.get("session_id", "default")
        
        # 模拟对话响应
        response = {
            "response": f"这是智能体 {agent_id} 对 '{message}' 的回复。我理解了您的问题，让我为您详细解答...",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "agent_id": agent_id,
            "message_id": f"msg_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "sources": [
                {
                    "type": "knowledge_base",
                    "title": "相关文档",
                    "content": "相关知识库内容...",
                    "score": 0.95
                }
            ]
        }
        
        return response
    except Exception as e:
        logger.error(f"对话失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"对话失败: {str(e)}"
        )

@router.post("/{agent_id}/chat/stream")
async def stream_chat_with_agent(agent_id: str, request: dict):
    """与智能体对话（流式）"""
    try:
        message = request.get("message", "")
        
        async def generate_stream():
            # 模拟流式响应
            response_parts = [
                "这是",
                "智能体",
                f" {agent_id} ",
                "对您问题的",
                "流式回复。",
                "我正在",
                "逐步",
                "生成",
                "完整的",
                "回答内容..."
            ]
            
            for i, part in enumerate(response_parts):
                chunk = {
                    "delta": {"content": part},
                    "index": i,
                    "agent_id": agent_id,
                    "timestamp": datetime.now().isoformat()
                }
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.1)  # 模拟延迟
            
            yield "data: [DONE]\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/plain",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )
    except Exception as e:
        logger.error(f"流式对话失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"流式对话失败: {str(e)}"
        )


# ==================== 智能体配置接口 ====================

@router.post("/{agent_id}/config")
async def update_agent_config(agent_id: str, request: dict):
    """更新智能体详细配置"""
    try:
        config = {
            "agent_id": agent_id,
            "model_config": request.get("model_config", {}),
            "capability_config": request.get("capability_config", {}),
            "advanced_config": request.get("advanced_config", {}),
            "updated_at": datetime.now().isoformat()
        }
        
        return config
    except Exception as e:
        logger.error(f"更新配置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新配置失败: {str(e)}"
        )

@router.get("/{agent_id}/config")
async def get_agent_config(agent_id: str):
    """获取智能体详细配置"""
    try:
        config = {
            "agent_id": agent_id,
            "model_config": {
                "provider": "zhipu",
                "model": "glm-4",
                "temperature": 0.7,
                "max_tokens": 1000,
                "top_p": 1.0
            },
            "capability_config": {
                "tools": ["web_search", "knowledge_retrieval"],
                "integrations": ["knowledge_base_001"],
                "custom_instructions": "始终保持友好和专业的语调"
            },
            "advanced_config": {
                "execution_timeout": 300,
                "max_iterations": 10,
                "enable_streaming": True,
                "enable_citations": True,
                "privacy_level": "standard"
            }
        }
        
        return config
    except Exception as e:
        logger.error(f"获取配置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取配置失败: {str(e)}"
        )


# ==================== 工作流设计接口 ====================

@router.post("/{agent_id}/flow/design")
async def design_agent_flow(agent_id: str, request: dict):
    """设计智能体工作流"""
    try:
        flow = {
            "agent_id": agent_id,
            "flow_id": f"flow_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "name": request.get("name", "新工作流"),
            "description": request.get("description", ""),
            "nodes": request.get("nodes", []),
            "edges": request.get("edges", []),
            "created_at": datetime.now().isoformat()
        }
        
        return flow
    except Exception as e:
        logger.error(f"设计工作流失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"设计工作流失败: {str(e)}"
        )

@router.get("/{agent_id}/flow")
async def get_agent_flow(agent_id: str):
    """获取智能体工作流设计"""
    try:
        flow = {
            "agent_id": agent_id,
            "flow_id": "flow_001",
            "name": "客服处理流程",
            "description": "标准客服问题处理工作流",
            "nodes": [
                {
                    "id": "1",
                    "type": "input",
                    "data": {"label": "用户输入"},
                    "position": {"x": 100, "y": 100}
                },
                {
                    "id": "2", 
                    "type": "agent",
                    "data": {"label": "理解分析"},
                    "position": {"x": 300, "y": 100}
                },
                {
                    "id": "3",
                    "type": "output",
                    "data": {"label": "回复输出"},
                    "position": {"x": 500, "y": 100}
                }
            ],
            "edges": [
                {"id": "e1-2", "source": "1", "target": "2"},
                {"id": "e2-3", "source": "2", "target": "3"}
            ]
        }
        
        return flow
    except Exception as e:
        logger.error(f"获取工作流失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取工作流失败: {str(e)}"
        )


# ==================== 统计和监控接口 ====================

@router.get("/{agent_id}/stats")
async def get_agent_stats(agent_id: str, period: str = "7d"):
    """获取智能体使用统计"""
    try:
        stats = {
            "agent_id": agent_id,
            "period": period,
            "total_conversations": 156,
            "total_messages": 423,
            "average_response_time": 1.2,
            "satisfaction_rate": 4.6,
            "usage_trend": [
                {"date": "2024-01-10", "conversations": 12, "messages": 34},
                {"date": "2024-01-11", "conversations": 18, "messages": 42},
                {"date": "2024-01-12", "conversations": 15, "messages": 38},
                {"date": "2024-01-13", "conversations": 22, "messages": 56},
                {"date": "2024-01-14", "conversations": 19, "messages": 48},
                {"date": "2024-01-15", "conversations": 25, "messages": 67},
                {"date": "2024-01-16", "conversations": 28, "messages": 72}
            ],
            "top_topics": [
                {"topic": "产品咨询", "count": 67},
                {"topic": "技术支持", "count": 45},
                {"topic": "订单查询", "count": 32},
                {"topic": "退换货", "count": 28}
            ]
        }
        
        return stats
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取统计信息失败: {str(e)}"
        )

@router.post("/{agent_id}/test")
async def test_agent(agent_id: str, request: dict):
    """测试智能体"""
    try:
        test_message = request.get("test_message", "")
        
        result = {
            "agent_id": agent_id,
            "test_message": test_message,
            "response": f"测试响应：智能体 {agent_id} 正常工作，对测试消息 '{test_message}' 的回复。",
            "response_time": 0.85,
            "status": "success",
            "timestamp": datetime.now().isoformat()
        }
        
        return result
    except Exception as e:
        logger.error(f"测试智能体失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"测试智能体失败: {str(e)}"
        )

@router.post("/{agent_id}/status/{action}")
async def change_agent_status(agent_id: str, action: str):
    """更改智能体状态"""
    try:
        if action not in ["activate", "deactivate", "pause", "resume"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无效的操作类型"
            )
        
        status_map = {
            "activate": "active",
            "deactivate": "inactive", 
            "pause": "paused",
            "resume": "active"
        }
        
        result = {
            "agent_id": agent_id,
            "action": action,
            "new_status": status_map[action],
            "message": f"智能体 {agent_id} 状态已更改为 {status_map[action]}",
            "timestamp": datetime.now().isoformat()
        }
        
        return result
    except Exception as e:
        logger.error(f"更改智能体状态失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更改智能体状态失败: {str(e)}"
        ) 