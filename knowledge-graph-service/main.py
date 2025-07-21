#!/usr/bin/env python3
"""
知识图谱微服务主应用入口
"""

import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

from app.config.settings import settings, init_settings
from app.api import api_router
from app.utils.auth import authenticate_user, create_jwt_token

# 初始化设置
init_settings()

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="Knowledge Graph Service",
    description="知识图谱微服务 - 提供AI驱动的知识图谱生成、管理和可视化功能",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 添加CORS中间件 - 支持前端直接访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173", 
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "*"  # 开发环境允许所有来源
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 包含API路由
app.include_router(api_router)


@app.get("/")
async def root():
    """根路径"""
    return {
        "service": "Knowledge Graph Service",
        "version": "1.0.0",
        "status": "running",
        "description": "AI驱动的知识图谱生成、管理和可视化微服务"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"service": "healthy", "version": "1.0.0"}


# 移除重复的登录路由，使用api_router中的auth_routes


@app.get("/info")
async def service_info():
    """服务信息"""
    return {
        "service_name": settings.SERVICE_NAME,
        "version": "1.0.0",
        "features": [
            "ai_knowledge_graph_generation",
            "project_based_management",
            "async_task_processing",
            "interactive_visualization"
        ]
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )