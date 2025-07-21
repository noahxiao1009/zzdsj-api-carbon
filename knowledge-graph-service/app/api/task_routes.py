"""
任务管理API路由
提供异步任务状态查询和管理的REST API接口
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
import logging

from ..models.graph import ProcessingProgress
from ..core.task_manager import TaskManager, TaskInfo, get_task_manager
from ..utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("/{task_id}/status")
async def get_task_status(
    task_id: str,
    current_user: dict = Depends(get_current_user),
    task_manager: TaskManager = Depends(get_task_manager)
):
    """获取任务状态"""
    try:
        task_info = await task_manager.get_task_status(task_id)
        if not task_info:
            raise HTTPException(status_code=404, detail="任务未找到")
        
        # 权限检查
        user_id = current_user["user_id"]
        if task_info.user_id != user_id:
            raise HTTPException(status_code=403, detail="无权限访问此任务")
        
        return {
            "task_id": task_info.task_id,
            "task_type": task_info.task_type,
            "status": task_info.status,
            "progress": task_info.progress,
            "message": task_info.message,
            "graph_id": task_info.graph_id,
            "project_id": task_info.project_id,
            "created_at": task_info.created_at,
            "started_at": task_info.started_at,
            "completed_at": task_info.completed_at,
            "result": task_info.result,
            "error": task_info.error
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task status: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{task_id}/progress", response_model=ProcessingProgress)
async def get_task_progress(
    task_id: str,
    current_user: dict = Depends(get_current_user),
    task_manager: TaskManager = Depends(get_task_manager)
):
    """获取任务进度"""
    try:
        progress = await task_manager.get_task_progress(task_id)
        if not progress:
            raise HTTPException(status_code=404, detail="任务未找到")
        
        # 权限检查
        task_info = await task_manager.get_task_status(task_id)
        user_id = current_user["user_id"]
        if task_info and task_info.user_id != user_id:
            raise HTTPException(status_code=403, detail="无权限访问此任务")
        
        return progress
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task progress: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    current_user: dict = Depends(get_current_user),
    task_manager: TaskManager = Depends(get_task_manager)
):
    """取消任务"""
    try:
        # 权限检查
        task_info = await task_manager.get_task_status(task_id)
        if not task_info:
            raise HTTPException(status_code=404, detail="任务未找到")
        
        user_id = current_user["user_id"]
        if task_info.user_id != user_id:
            raise HTTPException(status_code=403, detail="无权限取消此任务")
        
        success = await task_manager.cancel_task(task_id)
        if not success:
            raise HTTPException(status_code=400, detail="任务取消失败")
        
        return {"message": "任务已取消"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel task: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/")
async def get_user_tasks(
    limit: int = Query(100, ge=1, le=1000, description="返回任务数量限制"),
    current_user: dict = Depends(get_current_user),
    task_manager: TaskManager = Depends(get_task_manager)
):
    """获取用户任务列表"""
    try:
        user_id = current_user["user_id"]
        tasks = await task_manager.get_user_tasks(user_id, limit)
        
        # 转换为响应格式
        task_list = []
        for task_info in tasks:
            task_list.append({
                "task_id": task_info.task_id,
                "task_type": task_info.task_type,
                "status": task_info.status,
                "progress": task_info.progress,
                "message": task_info.message,
                "graph_id": task_info.graph_id,
                "project_id": task_info.project_id,
                "created_at": task_info.created_at,
                "started_at": task_info.started_at,
                "completed_at": task_info.completed_at,
                "stage": task_info.stage,
                "error": task_info.error
            })
        
        return {
            "tasks": task_list,
            "total": len(task_list)
        }
    except Exception as e:
        logger.error(f"Failed to get user tasks: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{task_id}/result")
async def get_task_result(
    task_id: str,
    current_user: dict = Depends(get_current_user),
    task_manager: TaskManager = Depends(get_task_manager)
):
    """获取任务结果"""
    try:
        task_info = await task_manager.get_task_status(task_id)
        if not task_info:
            raise HTTPException(status_code=404, detail="任务未找到")
        
        # 权限检查
        user_id = current_user["user_id"]
        if task_info.user_id != user_id:
            raise HTTPException(status_code=403, detail="无权限访问此任务")
        
        # 检查任务是否完成
        if task_info.status != "completed":
            raise HTTPException(status_code=400, detail="任务尚未完成")
        
        return {
            "task_id": task_id,
            "status": task_info.status,
            "result": task_info.result,
            "completed_at": task_info.completed_at
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task result: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    current_user: dict = Depends(get_current_user),
    task_manager: TaskManager = Depends(get_task_manager)
):
    """删除任务记录"""
    try:
        # 权限检查
        task_info = await task_manager.get_task_status(task_id)
        if not task_info:
            raise HTTPException(status_code=404, detail="任务未找到")
        
        user_id = current_user["user_id"]
        if task_info.user_id != user_id:
            raise HTTPException(status_code=403, detail="无权限删除此任务")
        
        # 只能删除已完成、失败或取消的任务
        if task_info.status in ["pending", "running"]:
            raise HTTPException(status_code=400, detail="无法删除正在执行的任务")
        
        # 从任务管理器中删除
        if task_id in task_manager.tasks:
            del task_manager.tasks[task_id]
            await task_manager._delete_task_file(task_id)
        
        return {"message": "任务删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete task: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/cleanup")
async def cleanup_old_tasks(
    days: int = Query(7, ge=1, le=365, description="清理多少天前的任务"),
    current_user: dict = Depends(get_current_user),
    task_manager: TaskManager = Depends(get_task_manager)
):
    """清理旧任务"""
    try:
        # 只有管理员可以执行清理操作
        user_role = current_user.get("role", "user")
        if user_role != "admin":
            raise HTTPException(status_code=403, detail="需要管理员权限")
        
        await task_manager.cleanup_old_tasks(days)
        return {"message": f"已清理{days}天前的旧任务"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cleanup old tasks: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/stats")
async def get_task_stats(
    current_user: dict = Depends(get_current_user),
    task_manager: TaskManager = Depends(get_task_manager)
):
    """获取任务统计信息"""
    try:
        user_id = current_user["user_id"]
        user_tasks = await task_manager.get_user_tasks(user_id, 1000)
        
        # 统计各状态任务数量
        stats = {
            "total": len(user_tasks),
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0
        }
        
        for task in user_tasks:
            stats[task.status] += 1
        
        return stats
    except Exception as e:
        logger.error(f"Failed to get task stats: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/health")
async def health_check(
    task_manager: TaskManager = Depends(get_task_manager)
):
    """健康检查"""
    try:
        health_status = await task_manager.health_check()
        return health_status
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))