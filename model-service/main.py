"""
模型服务主启动文件
Model Service Main Application
"""

import uvicorn
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import asyncio

# 应用相关导入
from app.api.models import router as models_router
from app.api.defaults import defaults_router
from app.api.config_management import config_router
from app.api.invoke import invoke_router
from app.api.monitoring import monitoring_router

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("模型服务启动中...")
    
    # 启动时执行的代码
    try:
        # 这里可以添加启动时的初始化工作
        # 比如连接数据库、加载模型等
        logger.info("模型服务启动完成")
        yield
    finally:
        # 关闭时执行的代码
        logger.info("模型服务正在关闭...")

def create_app() -> FastAPI:
    """创建FastAPI应用实例"""
    
    app = FastAPI(
        title="模型服务",
        description="统一的模型管理服务，支持中国国内各大模型厂商",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan
    )
    
    # 配置CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境应该配置具体的域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 配置可信主机中间件
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]  # 生产环境应该配置具体的主机
    )
    
    # 注册路由
    app.include_router(models_router)
    app.include_router(defaults_router)
    app.include_router(config_router)
    app.include_router(invoke_router)
    app.include_router(monitoring_router)
    
    # 根路径
    @app.get("/", tags=["根路径"])
    async def root():
        return {
            "service": "model-service",
            "version": "1.0.0",
            "description": "模型管理服务",
            "status": "running",
            "endpoints": {
                "docs": "/docs",
                "redoc": "/redoc",
                "openapi": "/openapi.json",
                "health": "/health"
            }
        }
    
    # 健康检查
    @app.get("/health", tags=["健康检查"])
    async def health_check():
        return {
            "status": "healthy",
            "service": "model-service",
            "timestamp": "2025-01-16T10:00:00Z"
        }
    
    # 全局异常处理
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "message": exc.detail,
                "error_code": exc.status_code
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request, exc):
        logger.error(f"未处理的异常: {str(exc)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "内部服务器错误",
                "error_code": 500
            }
        )
    
    return app

# 创建应用实例
app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8003,  # 模型服务端口
        reload=True,
        log_level="info"
    ) 