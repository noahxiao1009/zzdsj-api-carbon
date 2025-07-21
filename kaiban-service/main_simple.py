"""
Kaiban Service - 简化版本（无生命周期事件）
用于测试基本功能
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import logging
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.append(str(project_root))

# 导入应用模块
from app.api.v1 import workflows, boards, tasks, events
from app.api.frontend import frontend_router
from app.utils.logging_config import setup_logging

# 设置日志
setup_logging()
logger = logging.getLogger(__name__)

def create_app() -> FastAPI:
    """创建简化版FastAPI应用实例"""
    
    app = FastAPI(
        title="Kaiban Service (Simple)",
        description="事件驱动工作流服务 - 简化版本",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )
    
    # 配置CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境应配置具体域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 注册API路由
    app.include_router(workflows.router, prefix="/api/v1", tags=["工作流"])
    app.include_router(boards.router, prefix="/api/v1", tags=["看板"])
    app.include_router(tasks.router, prefix="/api/v1", tags=["任务"])
    app.include_router(events.router, prefix="/api/v1", tags=["事件"])
    
    # 注册前端路由
    app.include_router(frontend_router, prefix="/frontend", tags=["前端"])
    
    # 根路径 - 重定向到看板界面
    @app.get("/", tags=["根路径"])
    async def root():
        return RedirectResponse(url="/board")
    
    # 看板界面路由
    @app.get("/board", tags=["看板界面"])
    async def board_page():
        return {
            "message": "Kaiban Workflow Board",
            "service": "kaiban-service",
            "version": "1.0.0",
            "board_url": "/frontend/board",
            "api_docs": "/docs"
        }
    
    # 服务信息
    @app.get("/info", tags=["服务信息"])
    async def service_info():
        return {
            "service": "kaiban-service",
            "version": "1.0.0",
            "description": "事件驱动工作流服务（简化版）",
            "framework": "KaibanJS",
            "status": "running",
            "endpoints": {
                "workflows": "/api/v1/workflows",
                "boards": "/api/v1/boards", 
                "tasks": "/api/v1/tasks",
                "events": "/api/v1/events",
                "frontend": "/frontend",
                "board": "/board",
                "docs": "/docs"
            },
            "features": [
                "事件驱动工作流",
                "可视化看板界面",
                "多角色协作",
                "RESTful API"
            ]
        }
    
    # 健康检查
    @app.get("/health", tags=["健康检查"])
    async def health_check():
        return {
            "status": "healthy",
            "service": "kaiban-service",
            "version": "1.0.0",
            "timestamp": "2024-01-15T10:30:00Z"
        }
    
    logger.info("🎉 Kaiban Service (Simple) 创建完成")
    return app

# 创建应用实例
app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003) 