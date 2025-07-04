"""
Scheduler Service - 任务调度服务
替代Celery提供统一的任务调度和管理功能
"""

import asyncio
import logging
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.api.routers import task_router, schedule_router, worker_router
from app.services.scheduler_manager import SchedulerManager
from app.services.task_executor import TaskExecutor
from app.services.worker_pool import WorkerPool
from app.middleware.auth_middleware import AuthMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware

# 设置日志
setup_logging()
logger = logging.getLogger(__name__)

# 全局服务实例
scheduler_manager: SchedulerManager = None
task_executor: TaskExecutor = None
worker_pool: WorkerPool = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global scheduler_manager, task_executor, worker_pool
    
    # 启动阶段
    logger.info("启动 Scheduler Service...")
    
    try:
        # 初始化工作池
        worker_pool = WorkerPool()
        await worker_pool.initialize()
        
        # 初始化任务执行器
        task_executor = TaskExecutor(worker_pool)
        await task_executor.initialize()
        
        # 初始化调度管理器
        scheduler_manager = SchedulerManager(task_executor)
        await scheduler_manager.initialize()
        
        # 启动调度器
        await scheduler_manager.start()
        
        # 向网关注册服务
        await register_with_gateway()
        
        logger.info("Scheduler Service 启动完成")
        
        yield
        
    except Exception as e:
        logger.error(f"Scheduler Service 启动失败: {e}")
        raise
    finally:
        # 关闭阶段
        logger.info("关闭 Scheduler Service...")
        
        if scheduler_manager:
            await scheduler_manager.stop()
        
        if task_executor:
            await task_executor.cleanup()
        
        if worker_pool:
            await worker_pool.cleanup()
        
        logger.info("Scheduler Service 已关闭")


async def register_with_gateway():
    """向网关注册服务"""
    import aiohttp
    
    registration_data = {
        "service_name": "scheduler-service",
        "service_type": "scheduler",
        "version": "1.0.0",
        "host": settings.host,
        "port": settings.port,
        "health_check_path": "/health",
        "endpoints": [
            "/api/v1/tasks",
            "/api/v1/schedules",
            "/api/v1/workers"
        ],
        "description": "统一任务调度和管理服务"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{settings.gateway_url}/internal/register",
                json=registration_data,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    logger.info("成功向网关注册服务")
                else:
                    logger.warning(f"向网关注册服务失败: {response.status}")
    except Exception as e:
        logger.error(f"向网关注册服务时出错: {e}")


def create_app() -> FastAPI:
    """创建FastAPI应用"""
    app = FastAPI(
        title="Scheduler Service",
        description="统一任务调度和管理服务",
        version="1.0.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan
    )
    
    # 添加中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_hosts
    )
    
    app.add_middleware(AuthMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    
    # 注册路由
    app.include_router(task_router, prefix="/api/v1/tasks", tags=["任务"])
    app.include_router(schedule_router, prefix="/api/v1/schedules", tags=["调度"])
    app.include_router(worker_router, prefix="/api/v1/workers", tags=["工作者"])
    
    # 健康检查
    @app.get("/health")
    async def health_check():
        """健康检查"""
        try:
            # 检查调度器状态
            scheduler_status = scheduler_manager.is_running() if scheduler_manager else False
            
            # 检查工作池状态
            worker_status = worker_pool.is_healthy() if worker_pool else False
            
            # 检查任务执行器状态
            executor_status = task_executor.is_healthy() if task_executor else False
            
            return {
                "status": "healthy" if all([scheduler_status, worker_status, executor_status]) else "unhealthy",
                "timestamp": asyncio.get_event_loop().time(),
                "services": {
                    "scheduler": scheduler_status,
                    "worker_pool": worker_status,
                    "task_executor": executor_status
                },
                "metrics": {
                    "active_workers": worker_pool.get_active_worker_count() if worker_pool else 0,
                    "pending_tasks": scheduler_manager.get_pending_task_count() if scheduler_manager else 0,
                    "running_tasks": task_executor.get_running_task_count() if task_executor else 0
                }
            }
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            raise HTTPException(status_code=503, detail="Service unhealthy")
    
    # 根路径
    @app.get("/")
    async def root():
        return {
            "service": "scheduler-service",
            "version": "1.0.0",
            "status": "running",
            "description": "统一任务调度和管理服务"
        }
    
    # 调度器统计信息
    @app.get("/stats")
    async def get_scheduler_stats():
        """获取调度器统计信息"""
        try:
            stats = {}
            
            if scheduler_manager:
                stats["scheduler"] = await scheduler_manager.get_stats()
            
            if worker_pool:
                stats["workers"] = await worker_pool.get_stats()
            
            if task_executor:
                stats["executor"] = await task_executor.get_stats()
            
            return {
                "success": True,
                "stats": stats,
                "timestamp": asyncio.get_event_loop().time()
            }
            
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"获取统计信息失败: {str(e)}"
            )
    
    return app


def main():
    """主函数"""
    app = create_app()
    
    # 启动服务
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        workers=1,
        loop="asyncio",
        access_log=settings.debug,
        reload=settings.debug
    )


if __name__ == "__main__":
    main() 