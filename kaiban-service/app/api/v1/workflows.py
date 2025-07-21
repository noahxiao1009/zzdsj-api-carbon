"""
工作流 API 路由 - 集成Agno桥接层实现智能化工作流执行
"""

from fastapi import APIRouter, HTTPException, Query, Body, Header
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
import uuid

from app.models.workflow import WorkflowCreateRequest, WorkflowResponse, WorkflowStatus
from app.core.workflow_engine import WorkflowEngine
from app.services.agno_bridge import agno_bridge

router = APIRouter()
logger = logging.getLogger(__name__)

# 模拟用户ID头部（生产环境中应从JWT或其他认证机制获取）
def get_user_id(user_id: Optional[str] = Header(None, alias="X-User-ID")):
    return user_id or "default_user"

@router.get("/workflows", response_model=List[WorkflowResponse])
async def list_workflows(
    status: Optional[WorkflowStatus] = Query(None, description="按状态过滤"),
    limit: int = Query(20, le=100, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
    user_id: str = Header(..., alias="X-User-ID")
):
    """获取工作流列表"""
    try:
        # 这里应该调用 workflow_engine 实例
        # 暂时返回示例数据
        workflows = [
            {
                "id": "workflow-1",
                "name": "客户服务工作流",
                "description": "处理客户咨询和问题解决",
                "version": "1.0.0",
                "status": "active",
                "trigger_type": "manual",
                "config": {
                    "agent_enabled": True,
                    "agent_id": "agent_001",
                    "auto_execution": False
                },
                "metadata": {"created_by": user_id},
                "execution_count": 5,
                "success_count": 4,
                "failure_count": 1,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "last_executed_at": datetime.now(),
                "stages": [],
                "roles": []
            }
        ]
        return workflows
    except Exception as e:
        logger.error(f"获取工作流列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取工作流列表失败")


@router.post("/workflows", response_model=WorkflowResponse)
async def create_workflow(
    workflow_data: WorkflowCreateRequest = Body(...),
    user_id: str = Header(..., alias="X-User-ID")
):
    """创建新工作流并可选择创建对应的智能体"""
    try:
        # 创建工作流
        workflow_id = f"workflow-{uuid.uuid4()}"
        new_workflow = {
            "id": workflow_id,
            "name": workflow_data.name,
            "description": workflow_data.description,
            "version": "1.0.0",
            "status": "draft",
            "trigger_type": workflow_data.trigger_type,
            "config": workflow_data.config,
            "metadata": {**workflow_data.metadata, "created_by": user_id},
            "execution_count": 0,
            "success_count": 0,
            "failure_count": 0,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "last_executed_at": None,
            "stages": [stage.dict() for stage in workflow_data.stages],
            "roles": [role.dict() for role in workflow_data.roles]
        }
        
        # 如果启用智能体，创建对应的智能体
        if workflow_data.config.get("agent_enabled", False):
            try:
                # 模拟workflow对象用于桥接层
                class MockWorkflow:
                    def __init__(self, data):
                        self.id = data["id"]
                        self.name = data["name"]
                        self.description = data["description"]
                        self.version = data["version"]
                        self.status = data["status"]
                        self.trigger_type = data["trigger_type"]
                        self.config = data["config"]
                
                mock_workflow = MockWorkflow(new_workflow)
                
                # 通过Agno桥接层创建智能体
                agent = await agno_bridge.create_agent_from_workflow(mock_workflow, user_id)
                
                # 更新工作流配置，保存智能体ID
                new_workflow["config"]["agent_id"] = agent.get("agent_id")
                new_workflow["config"]["agent_created"] = True
                
                logger.info(f"工作流 {workflow_id} 对应的智能体创建成功: {agent.get('agent_id')}")
                
            except Exception as agent_error:
                logger.warning(f"创建智能体失败，但工作流创建成功: {str(agent_error)}")
                new_workflow["config"]["agent_error"] = str(agent_error)
        
        logger.info(f"工作流创建成功: {new_workflow['id']}")
        return new_workflow
    except Exception as e:
        logger.error(f"创建工作流失败: {str(e)}")
        raise HTTPException(status_code=500, detail="创建工作流失败")


@router.get("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(workflow_id: str, user_id: str = Header(..., alias="X-User-ID")):
    """获取工作流详情"""
    try:
        # 这里应该调用 workflow_engine.get_workflow()
        workflow = {
            "id": workflow_id,
            "name": "示例工作流",
            "description": "这是一个示例工作流",
            "version": "1.0.0",
            "status": "active",
            "trigger_type": "manual",
            "config": {
                "agent_enabled": True,
                "agent_id": "agent_001",
                "auto_execution": False
            },
            "metadata": {"created_by": user_id},
            "execution_count": 3,
            "success_count": 2,
            "failure_count": 1,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "last_executed_at": datetime.now(),
            "stages": [],
            "roles": []
        }
        
        if not workflow:
            raise HTTPException(status_code=404, detail="工作流不存在")
        
        return workflow
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取工作流失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取工作流失败")


@router.put("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: str,
    workflow_data: WorkflowCreateRequest = Body(...),
    user_id: str = Header(..., alias="X-User-ID")
):
    """更新工作流"""
    try:
        # 这里应该调用 workflow_engine.update_workflow()
        updated_workflow = {
            "id": workflow_id,
            "name": workflow_data.name,
            "description": workflow_data.description,
            "version": "1.0.0",
            "status": "active",
            "trigger_type": workflow_data.trigger_type,
            "config": workflow_data.config,
            "metadata": {**workflow_data.metadata, "updated_by": user_id},
            "execution_count": 5,
            "success_count": 4,
            "failure_count": 1,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "last_executed_at": datetime.now(),
            "stages": [stage.dict() for stage in workflow_data.stages],
            "roles": [role.dict() for role in workflow_data.roles]
        }
        
        # 如果工作流有关联的智能体，同步更新智能体配置
        agent_id = updated_workflow["config"].get("agent_id")
        if agent_id:
            try:
                class MockWorkflow:
                    def __init__(self, data):
                        self.id = data["id"]
                        self.name = data["name"]
                        self.description = data["description"]
                        self.version = data["version"]
                        self.status = data["status"]
                        self.trigger_type = data["trigger_type"]
                        self.config = data["config"]
                
                mock_workflow = MockWorkflow(updated_workflow)
                await agno_bridge.update_agent_workflow_design(agent_id, mock_workflow, user_id)
                logger.info(f"智能体 {agent_id} 工作流设计已同步更新")
                
            except Exception as sync_error:
                logger.warning(f"同步智能体配置失败: {str(sync_error)}")
        
        logger.info(f"工作流更新成功: {workflow_id}")
        return updated_workflow
    except Exception as e:
        logger.error(f"更新工作流失败: {str(e)}")
        raise HTTPException(status_code=500, detail="更新工作流失败")


@router.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str, user_id: str = Header(..., alias="X-User-ID")):
    """删除工作流"""
    try:
        # 这里应该调用 workflow_engine.delete_workflow()
        # 注意：实际实现中应该先检查工作流是否有关联的智能体，并进行相应处理
        logger.info(f"工作流删除成功: {workflow_id}")
        return {"message": "工作流删除成功", "workflow_id": workflow_id}
    except Exception as e:
        logger.error(f"删除工作流失败: {str(e)}")
        raise HTTPException(status_code=500, detail="删除工作流失败")


@router.post("/workflows/{workflow_id}/execute")
async def execute_workflow(
    workflow_id: str,
    input_data: Dict[str, Any] = Body(...),
    user_id: str = Header(..., alias="X-User-ID")
):
    """执行工作流 - 支持智能体自动执行"""
    try:
        execution_id = f"exec-{uuid.uuid4()}"
        
        # 检查工作流是否启用智能体
        # 这里应该从数据库获取真实的工作流配置
        workflow_config = {
            "agent_enabled": True,
            "agent_id": "agent_001",
            "auto_execution": True
        }
        
        if workflow_config.get("agent_enabled", False):
            agent_id = workflow_config.get("agent_id")
            if agent_id:
                try:
                    # 使用Agno桥接层执行智能化工作流
                    execution_result = await agno_bridge.execute_workflow_with_agent(
                        agent_id=agent_id,
                        workflow_id=workflow_id,
                        tasks=[],  # 这里应该传入实际的任务列表
                        user_id=user_id
                    )
                    
                    logger.info(f"智能体工作流执行启动: {workflow_id}, 智能体: {agent_id}, 执行ID: {execution_id}")
                    return {
                        "message": "智能体工作流执行已启动",
                        "workflow_id": workflow_id,
                        "execution_id": execution_id,
                        "agent_id": agent_id,
                        "execution_type": "agent_automated",
                        "status": "running",
                        "agent_execution_id": execution_result.get("execution_id")
                    }
                    
                except Exception as agent_error:
                    logger.error(f"智能体执行失败，回退到普通执行: {str(agent_error)}")
                    # 智能体执行失败时，回退到普通工作流执行
                    pass
        
        # 普通工作流执行（无智能体或智能体执行失败时的回退方案）
        logger.info(f"工作流执行启动: {workflow_id}, 执行ID: {execution_id}")
        return {
            "message": "工作流执行已启动",
            "workflow_id": workflow_id,
            "execution_id": execution_id,
            "execution_type": "manual",
            "status": "running"
        }
    except Exception as e:
        logger.error(f"执行工作流失败: {str(e)}")
        raise HTTPException(status_code=500, detail="执行工作流失败")


@router.get("/workflows/{workflow_id}/executions")
async def get_workflow_executions(workflow_id: str, user_id: str = Header(..., alias="X-User-ID")):
    """获取工作流执行历史"""
    try:
        # 这里应该调用 workflow_engine.get_executions()
        executions = [
            {
                "id": f"exec-{uuid.uuid4()}",
                "workflow_id": workflow_id,
                "status": "completed",
                "execution_type": "agent_automated",
                "agent_id": "agent_001",
                "started_at": datetime.now(),
                "completed_at": datetime.now(),
                "input_data": {},
                "output_data": {
                    "agent_summary": "智能体已成功完成工作流执行",
                    "tasks_completed": 3,
                    "total_time": "2.5分钟"
                },
                "error_message": None
            }
        ]
        
        return executions
    except Exception as e:
        logger.error(f"获取执行历史失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取执行历史失败")


# ========== 新增：Agno桥接层相关接口 ==========

@router.post("/workflows/{workflow_id}/create-agent")
async def create_workflow_agent(
    workflow_id: str,
    agent_config: Dict[str, Any] = Body(...),
    user_id: str = Header(..., alias="X-User-ID")
):
    """为现有工作流创建智能体"""
    try:
        # 获取工作流信息
        # 这里应该从数据库获取真实的工作流数据
        workflow_data = {
            "id": workflow_id,
            "name": "示例工作流",
            "description": "这是一个示例工作流",
            "version": "1.0.0",
            "status": "active",
            "trigger_type": "manual",
            "config": agent_config
        }
        
        class MockWorkflow:
            def __init__(self, data):
                self.id = data["id"]
                self.name = data["name"]
                self.description = data["description"]
                self.version = data["version"]
                self.status = data["status"]
                self.trigger_type = data["trigger_type"]
                self.config = data["config"]
        
        mock_workflow = MockWorkflow(workflow_data)
        
        # 创建智能体
        agent = await agno_bridge.create_agent_from_workflow(mock_workflow, user_id)
        
        logger.info(f"工作流 {workflow_id} 的智能体创建成功: {agent.get('agent_id')}")
        return {
            "message": "智能体创建成功",
            "workflow_id": workflow_id,
            "agent_id": agent.get("agent_id"),
            "agent_info": agent
        }
        
    except Exception as e:
        logger.error(f"创建工作流智能体失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建智能体失败: {str(e)}")


@router.post("/workflows/{workflow_id}/chat")
async def chat_with_workflow_agent(
    workflow_id: str,
    message: str = Body(..., embed=True),
    user_id: str = Header(..., alias="X-User-ID")
):
    """与工作流智能体对话"""
    try:
        # 获取工作流的智能体ID
        # 这里应该从数据库获取真实的智能体ID
        agent_id = "agent_001"
        
        if not agent_id:
            raise HTTPException(status_code=404, detail="该工作流未关联智能体")
        
        # 与智能体对话
        chat_result = await agno_bridge.chat_with_workflow_agent(
            agent_id=agent_id,
            message=message,
            user_id=user_id,
            stream=False
        )
        
        return {
            "message": "对话成功",
            "workflow_id": workflow_id,
            "agent_id": agent_id,
            "response": chat_result
        }
        
    except Exception as e:
        logger.error(f"与工作流智能体对话失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"对话失败: {str(e)}")


@router.get("/workflows/{workflow_id}/agent-stats")
async def get_workflow_agent_stats(
    workflow_id: str,
    period: str = Query("7d", description="统计周期：1d, 7d, 30d"),
    user_id: str = Header(..., alias="X-User-ID")
):
    """获取工作流智能体统计信息"""
    try:
        # 获取工作流的智能体ID
        agent_id = "agent_001"
        
        if not agent_id:
            raise HTTPException(status_code=404, detail="该工作流未关联智能体")
        
        # 获取智能体统计信息
        stats = await agno_bridge.get_agent_workflow_stats(agent_id, user_id, period)
        
        return {
            "workflow_id": workflow_id,
            "agent_id": agent_id,
            "period": period,
            "stats": stats
        }
        
    except Exception as e:
        logger.error(f"获取智能体统计信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")


@router.get("/agno-bridge/health")
async def check_agno_bridge_health():
    """检查Agno桥接层健康状态"""
    try:
        is_healthy = await agno_bridge.test_agent_connection()
        
        return {
            "service": "agno-bridge",
            "healthy": is_healthy,
            "timestamp": datetime.now().isoformat(),
            "agent_service_url": agno_bridge.agent_service_url
        }
        
    except Exception as e:
        logger.error(f"Agno桥接层健康检查失败: {str(e)}")
        return {
            "service": "agno-bridge",
            "healthy": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        } 