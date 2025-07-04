#!/usr/bin/env python3
"""
消息服务 - 微服务间通信核心服务
提供WebSocket实时通信、事件驱动架构、服务发现等功能
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Dict, List

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.messaging import MessageBroker, EventDispatcher
from app.core.websocket_manager import WebSocketManager
from app.api.routes import messaging_router, websocket_router
from app.services.service_registry import ServiceRegistry
from app.middleware.auth_middleware import AuthMiddleware

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 全局管理器实例
message_broker = MessageBroker()
event_dispatcher = EventDispatcher()
websocket_manager = WebSocketManager()
service_registry = ServiceRegistry()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("启动 Messaging Service...")
    
    try:
        # 初始化消息代理
        await message_broker.initialize()
        logger.info("消息代理初始化完成")
        
        # 初始化事件分发器
        await event_dispatcher.initialize()
        logger.info("事件分发器初始化完成")
        
        # 启动服务注册
        await service_registry.register_service(
            service_name="messaging-service",
            service_url=f"http://localhost:{settings.PORT}",
            health_check_url=f"http://localhost:{settings.PORT}/health"
        )
        logger.info("服务注册完成")
        
        # 启动后台任务
        asyncio.create_task(message_broker.start_consuming())
        asyncio.create_task(event_dispatcher.start_processing())
        
        logger.info("Messaging Service 启动成功")
        yield
        
    except Exception as e:
        logger.error(f"启动失败: {str(e)}")
        raise
    finally:
        # 清理资源
        logger.info("关闭 Messaging Service...")
        await message_broker.close()
        await event_dispatcher.close()
        await websocket_manager.disconnect_all()
        await service_registry.unregister_service("messaging-service")
        logger.info("Messaging Service 已关闭")


# 创建FastAPI应用
app = FastAPI(
    title="Messaging Service",
    description="微服务间通信和实时消息服务",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加认证中间件
app.add_middleware(AuthMiddleware)

# 注册路由
app.include_router(messaging_router, prefix="/api/v1", tags=["消息服务"])
app.include_router(websocket_router, prefix="/ws", tags=["WebSocket"])


@app.get("/")
async def root():
    """根路径"""
    return {
        "service": "messaging-service",
        "version": "1.0.0",
        "status": "running",
        "description": "微服务间通信和实时消息服务"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    try:
        # 检查消息代理状态
        broker_status = await message_broker.health_check()
        
        # 检查WebSocket连接状态
        ws_status = websocket_manager.get_status()
        
        # 检查服务注册状态
        registry_status = await service_registry.health_check()
        
        return {
            "status": "healthy",
            "timestamp": asyncio.get_event_loop().time(),
            "components": {
                "message_broker": broker_status,
                "websocket_manager": ws_status,
                "service_registry": registry_status
            },
            "active_connections": len(websocket_manager.active_connections),
            "registered_services": len(service_registry.services)
        }
    except Exception as e:
        logger.error(f"健康检查失败: {str(e)}")
        raise HTTPException(status_code=503, detail="Service unhealthy")


@app.get("/metrics")
async def metrics():
    """性能指标"""
    return {
        "message_broker": await message_broker.get_metrics(),
        "websocket_manager": websocket_manager.get_metrics(),
        "event_dispatcher": await event_dispatcher.get_metrics(),
        "service_registry": await service_registry.get_metrics()
    }


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket连接端点"""
    try:
        await websocket_manager.connect(websocket, client_id)
        logger.info(f"客户端 {client_id} 已连接")
        
        try:
            while True:
                # 接收客户端消息
                data = await websocket.receive_text()
                
                # 处理消息
                await websocket_manager.handle_message(client_id, data)
                
        except WebSocketDisconnect:
            logger.info(f"客户端 {client_id} 断开连接")
        except Exception as e:
            logger.error(f"WebSocket处理错误: {str(e)}")
            
    finally:
        await websocket_manager.disconnect(client_id)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理"""
    logger.error(f"未处理的异常: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    # 运行服务
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    ) 