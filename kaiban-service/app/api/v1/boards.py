"""
看板 API 路由
"""

from fastapi import APIRouter, HTTPException, Query, Body
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/boards")
async def list_boards(
    workflow_id: Optional[str] = Query(None, description="工作流ID过滤"),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0)
):
    """获取看板列表"""
    try:
        boards = [
            {
                "id": "board-1",
                "name": "客户服务看板",
                "workflow_id": "workflow-1",
                "columns": [
                    {"id": "col-1", "name": "待处理", "position": 0},
                    {"id": "col-2", "name": "进行中", "position": 1},
                    {"id": "col-3", "name": "已完成", "position": 2}
                ],
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "metadata": {}
            }
        ]
        return boards
    except Exception as e:
        logger.error(f"获取看板列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取看板列表失败")


@router.post("/boards")
async def create_board(board_data: Dict[str, Any] = Body(...)):
    """创建新看板"""
    try:
        new_board = {
            "id": f"board-{datetime.now().timestamp()}",
            "name": board_data.get("name"),
            "workflow_id": board_data.get("workflow_id"),
            "columns": board_data.get("columns", []),
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "metadata": board_data.get("metadata", {})
        }
        
        logger.info(f"看板创建成功: {new_board['id']}")
        return new_board
    except Exception as e:
        logger.error(f"创建看板失败: {str(e)}")
        raise HTTPException(status_code=500, detail="创建看板失败")


@router.get("/boards/{board_id}")
async def get_board(board_id: str):
    """获取看板详情"""
    try:
        board = {
            "id": board_id,
            "name": "示例看板",
            "workflow_id": "workflow-1",
            "columns": [
                {"id": "col-1", "name": "待处理", "position": 0, "tasks": []},
                {"id": "col-2", "name": "进行中", "position": 1, "tasks": []},
                {"id": "col-3", "name": "已完成", "position": 2, "tasks": []}
            ],
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "metadata": {}
        }
        
        return board
    except Exception as e:
        logger.error(f"获取看板失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取看板失败")


@router.put("/boards/{board_id}")
async def update_board(board_id: str, board_data: Dict[str, Any] = Body(...)):
    """更新看板"""
    try:
        updated_board = {
            "id": board_id,
            "name": board_data.get("name"),
            "workflow_id": board_data.get("workflow_id"),
            "columns": board_data.get("columns", []),
            "updated_at": datetime.now(),
            "metadata": board_data.get("metadata", {})
        }
        
        logger.info(f"看板更新成功: {board_id}")
        return updated_board
    except Exception as e:
        logger.error(f"更新看板失败: {str(e)}")
        raise HTTPException(status_code=500, detail="更新看板失败")


@router.delete("/boards/{board_id}")
async def delete_board(board_id: str):
    """删除看板"""
    try:
        logger.info(f"看板删除成功: {board_id}")
        return {"message": "看板删除成功", "board_id": board_id}
    except Exception as e:
        logger.error(f"删除看板失败: {str(e)}")
        raise HTTPException(status_code=500, detail="删除看板失败")


@router.post("/boards/{board_id}/columns")
async def add_column(board_id: str, column_data: Dict[str, Any] = Body(...)):
    """添加看板列"""
    try:
        new_column = {
            "id": f"col-{datetime.now().timestamp()}",
            "name": column_data.get("name"),
            "position": column_data.get("position", 0),
            "board_id": board_id,
            "tasks": []
        }
        
        logger.info(f"看板列添加成功: {new_column['id']}")
        return new_column
    except Exception as e:
        logger.error(f"添加看板列失败: {str(e)}")
        raise HTTPException(status_code=500, detail="添加看板列失败")


@router.put("/boards/{board_id}/columns/{column_id}")
async def update_column(board_id: str, column_id: str, column_data: Dict[str, Any] = Body(...)):
    """更新看板列"""
    try:
        updated_column = {
            "id": column_id,
            "name": column_data.get("name"),
            "position": column_data.get("position"),
            "board_id": board_id
        }
        
        logger.info(f"看板列更新成功: {column_id}")
        return updated_column
    except Exception as e:
        logger.error(f"更新看板列失败: {str(e)}")
        raise HTTPException(status_code=500, detail="更新看板列失败") 