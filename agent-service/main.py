#!/usr/bin/env python3
"""
智能体服务主启动文件
基于Agno框架的智能体管理服务
支持动态Agent创建、模板管理和多Agent协作
"""

import asyncio
import logging
import os
import sys
import uvicorn
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

# 添加app目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

# 导入配置
from app.config.settings import settings, init_settings

# 导入API路由
from app.api import agent_routes, template_routes, team_routes, model_routes

# 导入中间件
from app.middleware.logging_middleware import LoggingMiddleware
from app.middleware.error_handler import ErrorHandlerMiddleware
from app.middleware.request_id_middleware import RequestIDMiddleware

# 导入日志配置
from app.utils.logging_config import setup_logging

# 全局变量
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("启动智能体服务...")
    
    try:
        # 初始化配置
        await init_settings()
        logger.info("智能体服务启动成功")
        
        yield
        
    except Exception as e:
        logger.error(f"服务启动失败: {str(e)}")
        raise
    finally:
        logger.info("智能体服务已关闭")

def create_app() -> FastAPI:
    """创建FastAPI应用实例"""
    
    # 设置日志
    setup_logging(settings.LOG_LEVEL)
    
    # 创建FastAPI实例
    app = FastAPI(
        title="智能体管理服务",
        description="基于Agno框架的智能体创建、管理和编排服务",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan
    )

    # 添加中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(ErrorHandlerMiddleware)

    # 注册路由
    app.include_router(
        agent_routes.router,
        prefix="/api/v1/agents",
        tags=["智能体管理"]
    )
    
    app.include_router(
        template_routes.router,
        prefix="/api/v1/templates",
        tags=["模板管理"]
    )
    
    app.include_router(
        team_routes.router,
        prefix="/api/v1/teams",
        tags=["团队管理"]
    )
    
    app.include_router(
        model_routes.router,
        prefix="/api/v1/models",
        tags=["模型管理"]
    )

    # 健康检查端点
    @app.get("/health", tags=["系统"])
    async def health_check():
        """健康检查端点"""
        return {
            "status": "healthy",
            "service": "agent-service",
            "version": "1.0.0"
        }

    # 根路径
    @app.get("/", tags=["系统"])
    async def root():
        """根路径信息"""
        return {
            "service": "智能体管理服务",
            "description": "基于Agno框架的智能体创建、管理和编排服务",
            "version": "1.0.0",
            "docs_url": "/docs",
            "health_url": "/health",
            "api_prefix": "/api/v1"
        }

    # 服务信息端点
    @app.get("/api/v1/info", tags=["系统"])
    async def service_info():
        """获取服务详细信息"""
        return {
            "service_name": "agent-service",
            "version": "1.0.0",
            "framework": "Agno",
            "features": {
                "agent_creation": True,
                "template_management": True,
                "team_coordination": True,
                "model_management": True
            },
            "supported_models": [
                "openai/gpt-4o",
                "openai/gpt-4o-mini",
                "openai/o3-mini",
                "anthropic/claude-3-5-sonnet",
                "anthropic/claude-3-haiku"
            ],
            "available_templates": [
                "basic_conversation",
                "knowledge_base", 
                "deep_thinking",
                "research_analyst",
                "code_assistant"
            ]
        }

    return app

# 创建应用实例
app = create_app()

if __name__ == "__main__":
    # 开发模式启动
    try:
        uvicorn.run(
            "main:app",
            host=settings.HOST,
            port=settings.PORT,
            reload=settings.DEBUG,
            workers=1,
            log_level=settings.LOG_LEVEL.lower(),
            access_log=True
        )
    except KeyboardInterrupt:
        logger.info("收到停止信号，正在关闭服务...")
    except Exception as e:
        logger.error(f"服务启动失败: {str(e)}")
        sys.exit(1)
