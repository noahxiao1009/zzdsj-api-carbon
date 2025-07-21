"""
API包初始化模块
"""

from fastapi import APIRouter
from .project_routes import router as project_router
from .graph_routes import router as graph_router
from .task_routes import router as task_router
from .auth_routes import router as auth_router

# 创建API路由器
api_router = APIRouter(prefix="/api/v1")

# 包含各个模块的路由
api_router.include_router(auth_router)
api_router.include_router(project_router)
api_router.include_router(graph_router)
api_router.include_router(task_router)

__all__ = ["api_router"]