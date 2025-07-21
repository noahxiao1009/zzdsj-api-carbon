"""
项目管理API路由
提供数据集项目的REST API接口
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
import logging

from ..models.project import (
    KnowledgeGraphProject,
    ProjectCreateRequest,
    ProjectUpdateRequest,
    ProjectListResponse,
    ProjectMemberManageRequest,
    ProjectBulkOperationRequest,
    ProjectExportRequest,
    ProjectImportRequest,
    ProjectStatus
)
from ..services.project_service import ProjectService, get_project_service
from ..utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post("/", response_model=KnowledgeGraphProject)
async def create_project(
    request: ProjectCreateRequest,
    current_user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service)
):
    """创建项目"""
    try:
        user_id = current_user["user_id"]
        project = await project_service.create_project(request, user_id)
        return project
    except Exception as e:
        logger.error(f"Failed to create project: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=ProjectListResponse)
async def get_projects(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    status: Optional[ProjectStatus] = Query(None, description="项目状态筛选"),
    current_user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service)
):
    """获取项目列表"""
    try:
        user_id = current_user["user_id"]
        projects = await project_service.get_user_projects(user_id, page, page_size, status)
        return projects
    except Exception as e:
        logger.error(f"Failed to get projects: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{project_id}", response_model=KnowledgeGraphProject)
async def get_project(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service)
):
    """获取项目详情"""
    try:
        user_id = current_user["user_id"]
        project = await project_service.get_project(project_id, user_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目未找到")
        return project
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get project: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{project_id}", response_model=KnowledgeGraphProject)
async def update_project(
    project_id: str,
    request: ProjectUpdateRequest,
    current_user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service)
):
    """更新项目"""
    try:
        user_id = current_user["user_id"]
        project = await project_service.update_project(project_id, request, user_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目未找到")
        return project
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update project: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service)
):
    """删除项目"""
    try:
        user_id = current_user["user_id"]
        success = await project_service.delete_project(project_id, user_id)
        if not success:
            raise HTTPException(status_code=404, detail="项目未找到")
        return {"message": "项目删除成功"}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete project: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{project_id}/graphs")
async def get_project_graphs(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service)
):
    """获取项目图谱列表"""
    try:
        user_id = current_user["user_id"]
        graphs = await project_service.get_project_graphs(project_id, user_id)
        return {"graphs": graphs}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get project graphs: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{project_id}/members")
async def manage_project_member(
    project_id: str,
    request: ProjectMemberManageRequest,
    current_user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service)
):
    """管理项目成员"""
    try:
        user_id = current_user["user_id"]
        success = await project_service.manage_project_member(project_id, request, user_id)
        if not success:
            raise HTTPException(status_code=400, detail="成员操作失败")
        return {"message": "成员操作成功"}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to manage project member: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bulk-operation")
async def bulk_operation(
    request: ProjectBulkOperationRequest,
    current_user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service)
):
    """批量操作项目"""
    try:
        user_id = current_user["user_id"]
        result = await project_service.bulk_operation(request, user_id)
        return result
    except Exception as e:
        logger.error(f"Failed to perform bulk operation: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{project_id}/statistics")
async def get_project_statistics(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service)
):
    """获取项目统计信息"""
    try:
        user_id = current_user["user_id"]
        statistics = await project_service.get_project_statistics(project_id, user_id)
        if not statistics:
            raise HTTPException(status_code=404, detail="项目未找到")
        return statistics
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get project statistics: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{project_id}/export")
async def export_project(
    project_id: str,
    request: ProjectExportRequest,
    current_user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service)
):
    """导出项目"""
    try:
        user_id = current_user["user_id"]
        export_data = await project_service.export_project(project_id, user_id, request.export_format)
        return export_data
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to export project: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/import")
async def import_project(
    request: ProjectImportRequest,
    current_user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service)
):
    """导入项目"""
    try:
        user_id = current_user["user_id"]
        project = await project_service.import_project(request.import_data, user_id)
        if not project:
            raise HTTPException(status_code=400, detail="导入失败")
        return project
    except Exception as e:
        logger.error(f"Failed to import project: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/health")
async def health_check(
    project_service: ProjectService = Depends(get_project_service)
):
    """健康检查"""
    try:
        health_status = await project_service.health_check()
        return health_status
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))