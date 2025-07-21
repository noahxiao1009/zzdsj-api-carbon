"""
Chat Service - 主应用程序入口
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
import uvicorn

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.database import init_database
from app.core.redis import redis_manager
from app.services.chat_manager import get_chat_manager
from app.api import chat, sessions, health

# 设置日志
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    logger.info("Chat Service 启动中...")
    
    try:
        # 初始化数据库
        logger.info("初始化数据库连接...")
        init_database()
        
        # 检查Redis连接
        logger.info("检查Redis连接...")
        if not redis_manager.ping():
            logger.warning("Redis连接不可用，某些功能可能受限")
        else:
            logger.info("Redis连接正常")
        
        # 初始化聊天管理器
        logger.info("初始化聊天管理器...")
        chat_manager = await get_chat_manager()
        logger.info("聊天管理器初始化完成")
        
        # 启动完成
        logger.info("Chat Service 启动完成")
        
        yield
        
    except Exception as e:
        logger.error(f"Chat Service 启动失败: {e}")
        raise
    
    # 关闭时清理
    logger.info("Chat Service 关闭中...")
    
    try:
        # 清理聊天管理器
        chat_manager = await get_chat_manager()
        await chat_manager.cleanup()
        logger.info("聊天管理器清理完成")
        
        logger.info("Chat Service 关闭完成")
        
    except Exception as e:
        logger.error(f"Chat Service 关闭时发生错误: {e}")


# 创建FastAPI应用
app = FastAPI(
    title="Chat Service",
    description="聊天服务 - 提供智能对话、会话管理和语音交互功能",
    version=settings.service_version,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
    openapi_url="/openapi.json" if settings.environment != "production" else None,
    lifespan=lifespan
)

# 中间件配置
if settings.environment != "production":
    # 开发环境允许所有来源
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    # 生产环境限制CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )

# 信任的主机中间件
if settings.allowed_hosts:
    app.add_middleware(
        TrustedHostMiddleware, 
        allowed_hosts=settings.allowed_hosts
    )


# 自定义中间件
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """请求日志中间件"""
    start_time = asyncio.get_event_loop().time()
    
    # 记录请求
    logger.info(f"请求开始: {request.method} {request.url}")
    
    try:
        response = await call_next(request)
        
        # 计算处理时间
        process_time = asyncio.get_event_loop().time() - start_time
        
        # 记录响应
        logger.info(
            f"请求完成: {request.method} {request.url} "
            f"状态码: {response.status_code} "
            f"处理时间: {process_time:.3f}s"
        )
        
        # 添加响应头
        response.headers["X-Process-Time"] = str(process_time)
        response.headers["X-Service"] = "chat-service"
        
        return response
        
    except Exception as e:
        # 记录错误
        process_time = asyncio.get_event_loop().time() - start_time
        logger.error(
            f"请求失败: {request.method} {request.url} "
            f"错误: {str(e)} "
            f"处理时间: {process_time:.3f}s"
        )
        raise


# 异常处理器
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP异常处理"""
    logger.warning(f"HTTP异常: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
                "type": "http_error"
            },
            "timestamp": "now",
            "path": str(request.url)
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """通用异常处理"""
    logger.error(f"未处理的异常: {type(exc).__name__}: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": 500,
                "message": "内部服务器错误",
                "type": "internal_error"
            },
            "timestamp": "now",
            "path": str(request.url)
        }
    )


# 注册路由
app.include_router(health.router)  # 健康检查路由
app.include_router(chat.router)    # 聊天路由
app.include_router(sessions.router)  # 会话管理路由

# 注册增强的聊天路由
try:
    from app.api.routers.enhanced_chat_router import router as enhanced_chat_router
    app.include_router(enhanced_chat_router)  # 增强聊天路由
    logger.info("增强聊天路由注册成功")
except ImportError as e:
    logger.warning(f"增强聊天路由导入失败: {e}")
except Exception as e:
    logger.error(f"增强聊天路由注册失败: {e}")

# 注册WebSocket路由
try:
    from app.api.routers.websocket_router import router as websocket_router
    app.include_router(websocket_router)  # WebSocket路由
    logger.info("WebSocket路由注册成功")
except ImportError as e:
    logger.warning(f"WebSocket路由导入失败: {e}")
except Exception as e:
    logger.error(f"WebSocket路由注册失败: {e}")

# 注册流式优化路由
try:
    from app.api.routers.stream_optimization_router import router as stream_optimization_router
    app.include_router(stream_optimization_router)  # 流式优化路由
    logger.info("流式优化路由注册成功")
except ImportError as e:
    logger.warning(f"流式优化路由导入失败: {e}")
except Exception as e:
    logger.error(f"流式优化路由注册失败: {e}")

# 注册智能体管理路由
try:
    from app.api.routers.agent_management_router import router as agent_management_router
    app.include_router(agent_management_router)  # 智能体管理路由
    logger.info("智能体管理路由注册成功")
except ImportError as e:
    logger.warning(f"智能体管理路由导入失败: {e}")
except Exception as e:
    logger.error(f"智能体管理路由注册失败: {e}")


# 根路径
@app.get("/")
async def root():
    """根路径 - 服务信息"""
    return {
        "service": "chat-service",
        "version": settings.service_version,
        "status": "running",
        "description": "聊天服务 - 提供智能对话、会话管理和语音交互功能",
        "docs_url": "/docs" if settings.environment != "production" else None,
        "health_check": "/health",
        "timestamp": "now"
    }


# API信息路径
@app.get("/info")
async def service_info():
    """服务详细信息"""
    return {
        "service": {
            "name": "chat-service",
            "version": settings.service_version,
            "environment": settings.environment,
            "description": "聊天服务 - 提供智能对话、会话管理和语音交互功能"
        },
        "features": {
            "chat": "智能对话功能",
            "voice": "语音消息支持" if settings.voice_enabled else "语音功能未启用",
            "streaming": "流式响应支持",
            "session_management": "会话管理",
            "agent_selection": "智能体选择"
        },
        "endpoints": {
            "chat": {
                "create_session": "/chat/session",
                "send_message": "/chat/message",
                "stream_message": "/chat/message/stream",
                "voice_message": "/chat/voice",
                "get_history": "/chat/history/{session_id}",
                "get_agents": "/chat/agents"
            },
            "sessions": {
                "list_sessions": "/sessions",
                "session_detail": "/sessions/{session_id}",
                "delete_session": "/sessions/{session_id}",
                "batch_operations": "/sessions/batch",
                "user_stats": "/sessions/user/{user_id}/stats"
            },
            "health": {
                "basic": "/health",
                "detailed": "/health/detailed",
                "readiness": "/health/readiness",
                "liveness": "/health/liveness",
                "metrics": "/health/metrics"
            }
        },
        "timestamp": "now"
    }


# 自定义OpenAPI配置（开发环境）
if settings.environment != "production":
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        
        openapi_schema = get_openapi(
            title="Chat Service API",
            version=settings.service_version,
            description="""
            # Chat Service API
            
            聊天服务提供智能对话、会话管理和语音交互功能。
            
            ## 主要功能
            
            - **智能对话**: 支持多种智能体的对话交互
            - **会话管理**: 创建、管理和删除聊天会话
            - **语音支持**: 语音转文字和文字转语音
            - **流式响应**: 实时流式消息传输
            - **历史记录**: 会话历史查询和管理
            
            ## 认证
            
            目前服务处于开发阶段，暂未启用认证机制。
            
            ## 错误处理
            
            所有API都遵循统一的错误响应格式：
            ```json
            {
                "error": {
                    "code": 400,
                    "message": "错误描述",
                    "type": "error_type"
                },
                "timestamp": "2024-01-01T00:00:00",
                "path": "/api/path"
            }
            ```
            """,
            routes=app.routes,
        )
        
        # 添加自定义标签描述
        openapi_schema["tags"] = [
            {
                "name": "聊天",
                "description": "聊天相关的API接口，包括消息发送、语音处理等"
            },
            {
                "name": "会话管理", 
                "description": "会话管理相关的API接口，包括会话创建、查询、删除等"
            },
            {
                "name": "健康检查",
                "description": "服务健康状态检查和监控相关的API接口"
            }
        ]
        
        app.openapi_schema = openapi_schema
        return app.openapi_schema
    
    app.openapi = custom_openapi


# 主程序入口
def main():
    """主程序入口"""
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_config=None,  # 使用自定义日志配置
        access_log=False,  # 禁用uvicorn访问日志，使用自定义中间件
    )


if __name__ == "__main__":
    main() 