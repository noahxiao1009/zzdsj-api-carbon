"""
任务 API 路由
"""

from fastapi import APIRouter, HTTPException, Query, Body
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/tasks")
async def list_tasks(
    workflow_id: Optional[str] = Query(None, description="工作流ID过滤"),
    board_id: Optional[str] = Query(None, description="看板ID过滤"),
    status: Optional[str] = Query(None, description="状态过滤"),
    assignee: Optional[str] = Query(None, description="负责人过滤"),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0)
):
    """获取任务列表"""
    try:
        tasks = [
            {
                "id": "task-1",
                "title": "处理客户咨询",
                "description": "回复客户关于产品功能的咨询",
                "status": "in_progress",
                "priority": "high",
                "assignee": "user-1",
                "workflow_id": "workflow-1",
                "board_id": "board-1",
                "column_id": "col-2",
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "due_date": None,
                "tags": ["客服", "咨询"],
                "metadata": {}
            }
        ]
        return tasks
    except Exception as e:
        logger.error(f"获取任务列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取任务列表失败")


@router.post("/tasks")
async def create_task(task_data: Dict[str, Any] = Body(...)):
    """创建新任务"""
    try:
        new_task = {
            "id": f"task-{datetime.now().timestamp()}",
            "title": task_data.get("title"),
            "description": task_data.get("description", ""),
            "status": "pending",
            "priority": task_data.get("priority", "medium"),
            "assignee": task_data.get("assignee"),
            "workflow_id": task_data.get("workflow_id"),
            "board_id": task_data.get("board_id"),
            "column_id": task_data.get("column_id"),
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "due_date": task_data.get("due_date"),
            "tags": task_data.get("tags", []),
            "metadata": task_data.get("metadata", {})
        }
        
        logger.info(f"任务创建成功: {new_task['id']}")
        return new_task
    except Exception as e:
        logger.error(f"创建任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail="创建任务失败")


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """获取任务详情"""
    try:
        task = {
            "id": task_id,
            "title": "示例任务",
            "description": "这是一个示例任务",
            "status": "in_progress",
            "priority": "medium",
            "assignee": "user-1",
            "workflow_id": "workflow-1",
            "board_id": "board-1",
            "column_id": "col-2",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "due_date": None,
            "tags": [],
            "comments": [],
            "activities": [],
            "metadata": {}
        }
        
        return task
    except Exception as e:
        logger.error(f"获取任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取任务失败")


@router.put("/tasks/{task_id}")
async def update_task(task_id: str, task_data: Dict[str, Any] = Body(...)):
    """更新任务"""
    try:
        updated_task = {
            "id": task_id,
            "title": task_data.get("title"),
            "description": task_data.get("description"),
            "status": task_data.get("status"),
            "priority": task_data.get("priority"),
            "assignee": task_data.get("assignee"),
            "workflow_id": task_data.get("workflow_id"),
            "board_id": task_data.get("board_id"),
            "column_id": task_data.get("column_id"),
            "updated_at": datetime.now(),
            "due_date": task_data.get("due_date"),
            "tags": task_data.get("tags", []),
            "metadata": task_data.get("metadata", {})
        }
        
        logger.info(f"任务更新成功: {task_id}")
        return updated_task
    except Exception as e:
        logger.error(f"更新任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail="更新任务失败")


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """删除任务"""
    try:
        logger.info(f"任务删除成功: {task_id}")
        return {"message": "任务删除成功", "task_id": task_id}
    except Exception as e:
        logger.error(f"删除任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail="删除任务失败")


@router.post("/tasks/{task_id}/move")
async def move_task(task_id: str, move_data: Dict[str, Any] = Body(...)):
    """移动任务到不同列"""
    try:
        result = {
            "task_id": task_id,
            "old_column_id": move_data.get("old_column_id"),
            "new_column_id": move_data.get("new_column_id"),
            "position": move_data.get("position", 0),
            "moved_at": datetime.now()
        }
        
        logger.info(f"任务移动成功: {task_id}")
        return result
    except Exception as e:
        logger.error(f"移动任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail="移动任务失败")


@router.post("/tasks/{task_id}/comments")
async def add_comment(task_id: str, comment_data: Dict[str, Any] = Body(...)):
    """添加任务评论"""
    try:
        new_comment = {
            "id": f"comment-{datetime.now().timestamp()}",
            "task_id": task_id,
            "author": comment_data.get("author"),
            "content": comment_data.get("content"),
            "created_at": datetime.now()
        }
        
        logger.info(f"任务评论添加成功: {new_comment['id']}")
        return new_comment
    except Exception as e:
        logger.error(f"添加任务评论失败: {str(e)}")
        raise HTTPException(status_code=500, detail="添加任务评论失败") 