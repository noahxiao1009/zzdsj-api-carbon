#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具微服务主入口
统一管理WebAgent搜索和Scraperr爬虫工具
"""

import os
import sys
import asyncio
from datetime import datetime
from typing import Dict, Any, List
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.api.tools_api import router as tools_router
from app.api.integrations_api import router as integrations_router
from app.core.tool_manager import ToolManager
from app.core.logger import logger
from shared.service_client import call_service, CallMethod


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    logger.info("正在启动工具微服务...")
    
    # 初始化工具管理器
    tool_manager = ToolManager()
    await tool_manager.initialize()
    app.state.tool_manager = tool_manager
    
    # 向网关注册服务
    await register_to_gateway()
    
    logger.info("工具微服务启动完成")
    
    yield
    
    # 关闭时清理
    logger.info("正在关闭工具微服务...")
    if hasattr(app.state, 'tool_manager'):
        await app.state.tool_manager.cleanup()
    logger.info("工具微服务关闭完成")


# 初始化FastAPI应用
app = FastAPI(
    title="工具微服务",
    description="统一管理WebAgent搜索和Scraperr爬虫工具",
    version="1.0.0",
    lifespan=lifespan
)

# 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(tools_router, prefix="/api/v1")
app.include_router(integrations_router, prefix="/api/v1")

# 健康检查
@app.get("/health")
async def health_check():
    """健康检查端点"""
    tool_manager = getattr(app.state, 'tool_manager', None)
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "tools-service",
        "version": "1.0.0"
    }
    
    if tool_manager:
        tools_status = await tool_manager.get_tools_status()
        health_status["tools"] = tools_status
    
    return health_status


# 服务信息
@app.get("/info")
async def service_info():
    """获取服务信息"""
    return {
        "service_name": "tools-service",
        "version": "1.0.0",
        "description": "统一工具管理微服务",
        "supported_tools": ["webagent", "scraperr"],
        "endpoints": {
            "tools": "/api/v1/tools",
            "integrations": "/api/v1/integrations",
            "websailor": "/api/v1/tools/websailor",
            "scraperr": "/api/v1/tools/scraperr", 
            "health": "/health"
        }
    }


async def register_to_gateway():
    """向网关服务注册"""
    try:
        registration_data = {
            "service_name": "tools-service",
            "service_url": f"http://localhost:{os.getenv('PORT', '8090')}",
            "health_check_path": "/health",
            "routes": [
                {
                    "path": "/api/v1/tools/*",
                    "methods": ["GET", "POST", "PUT", "DELETE"]
                },
                {
                    "path": "/api/v1/integrations/*",
                    "methods": ["GET", "POST", "PUT", "DELETE"]
                }
            ]
        }
        
        await call_service(
            service_name="gateway-service",
            method=CallMethod.POST,
            path="/api/v1/services/register",
            json=registration_data
        )
        
        logger.info("工具服务已注册到网关")
        
    except Exception as e:
        logger.warning(f"网关注册失败: {e}")


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"全局异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"message": "服务器内部错误", "detail": str(exc)}
    )


if __name__ == "__main__":
    logger.info("启动工具微服务...")
    
    port = int(os.getenv("PORT", "8090"))
    logger.info(f"服务将在端口 {port} 上启动")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=True
    )