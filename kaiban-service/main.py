"""
Kaiban Service - 事件驱动工作流服务主启动文件
基于KaibanJS框架的工作流编排和执行服务
"""

import asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import logging
import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.append(str(project_root))

# 导入应用模块
from app.api.v1 import workflows, boards, tasks, events
from app.api.frontend import frontend_router
from app.core.workflow_engine import WorkflowEngine
from app.core.event_dispatcher import EventDispatcher
from app.core.state_manager import StateManager
from app.services.integration_service import IntegrationService
from app.utils.logging_config import setup_logging

# 设置日志
setup_logging()
logger = logging.getLogger(__name__)

# 全局服务实例
workflow_engine: WorkflowEngine = None
event_dispatcher: EventDispatcher = None
state_manager: StateManager = None
integration_service: IntegrationService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global workflow_engine, event_dispatcher, state_manager, integration_service
    
    logger.info("🚀 Kaiban Service 启动中...")
    
    try:
        # 初始化核心服务
        state_manager = StateManager()
        await state_manager.initialize()
        logger.info("✅ 状态管理器已初始化")
        
        event_dispatcher = EventDispatcher(state_manager)
        await event_dispatcher.initialize()
        logger.info("✅ 事件分发器已初始化")
        
        workflow_engine = WorkflowEngine(state_manager, event_dispatcher)
        await workflow_engine.initialize()
        logger.info("✅ 工作流引擎已初始化")
        
        integration_service = IntegrationService()
        await integration_service.initialize()
        logger.info("✅ 集成服务已初始化")
        
        # 服务注册到网关
        await register_with_gateway()
        logger.info("✅ 服务已注册到网关")
        
        logger.info("🎉 Kaiban Service 启动完成")
        
        yield
        
    except Exception as e:
        logger.error(f"❌ 服务启动失败: {str(e)}")
        raise
    finally:
        # 清理资源
        logger.info("🔄 Kaiban Service 关闭中...")
        if workflow_engine:
            await workflow_engine.cleanup()
        if event_dispatcher:
            await event_dispatcher.cleanup()
        if state_manager:
            await state_manager.cleanup()
        if integration_service:
            await integration_service.cleanup()
        logger.info("✅ Kaiban Service 已关闭")


async def register_with_gateway():
    """向网关服务注册"""
    try:
        if integration_service:
            await integration_service.register_with_gateway({
                "service_name": "kaiban-service",
                "service_url": f"http://localhost:{get_port()}",
                "health_check_url": "/health",
                "capabilities": [
                    "workflow_management",
                    "event_processing", 
                    "task_orchestration",
                    "kanban_board"
                ],
                "metadata": {
                    "version": "1.0.0",
                    "framework": "KaibanJS",
                    "api_endpoints": [
                        "/api/v1/workflows",
                        "/api/v1/boards",
                        "/api/v1/tasks",
                        "/api/v1/events"
                    ]
                }
            })
    except Exception as e:
        logger.warning(f"⚠️ 网关注册失败: {str(e)}")


def create_app() -> FastAPI:
    """创建FastAPI应用实例"""
    
    app = FastAPI(
        title="Kaiban Service",
        description="事件驱动工作流服务 - 基于KaibanJS框架的工作流编排和执行",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan
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
    
    # 挂载静态文件
    if os.path.exists("frontend/static"):
        app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
    
    # 挂载KaibanJS组件
    if os.path.exists("frontend/kaiban-components"):
        app.mount("/kaiban", StaticFiles(directory="frontend/kaiban-components"), name="kaiban")
    
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
            "description": "事件驱动工作流服务",
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
                "实时状态管理",
                "LLM集成",
                "RESTful API"
            ]
        }
    
    # 健康检查
    @app.get("/health", tags=["健康检查"])
    async def health_check():
        try:
            # 检查核心服务状态
            services_status = {
                "workflow_engine": workflow_engine.is_healthy() if workflow_engine else False,
                "event_dispatcher": event_dispatcher.is_healthy() if event_dispatcher else False,
                "state_manager": state_manager.is_healthy() if state_manager else False,
                "integration_service": integration_service.is_healthy() if integration_service else False
            }
            
            all_healthy = all(services_status.values())
            
            return {
                "status": "healthy" if all_healthy else "unhealthy",
                "service": "kaiban-service",
                "version": "1.0.0",
                "timestamp": "2025-01-16T10:00:00Z",
                "services": services_status,
                "uptime": "running"
            }
        except Exception as e:
            logger.error(f"健康检查失败: {str(e)}")
            return {
                "status": "unhealthy",
                "service": "kaiban-service",
                "error": str(e),
                "timestamp": "2025-01-16T10:00:00Z"
            }
    
    # 全局异常处理
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        logger.error(f"未处理的异常: {str(exc)}")
        return {
            "success": False,
            "error": "内部服务错误",
            "message": str(exc),
            "service": "kaiban-service"
        }
    
    return app


def get_port() -> int:
    """获取服务端口"""
    return int(os.getenv("KAIBAN_SERVICE_PORT", 8005))


def get_host() -> str:
    """获取服务主机"""
    return os.getenv("KAIBAN_SERVICE_HOST", "0.0.0.0")


# 创建应用实例
app = create_app()


if __name__ == "__main__":
    # 启动配置
    host = get_host()
    port = get_port()
    
    logger.info(f"启动 Kaiban Service 在 {host}:{port}")
    
    # 开发环境配置
    reload = os.getenv("APP_ENV", "development") == "development"
    log_level = os.getenv("LOG_LEVEL", "info").lower()
    
    # 启动服务
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
        access_log=True
    ) 