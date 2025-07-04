"""
Chat Service - 基于Agno框架的聊天服务
负责处理智能体对话、会话管理和语音集成
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
from app.api.routers import chat_router, session_router, voice_router
from app.services.chat_manager import ChatManager
from app.services.agno_integration import AgnoIntegration
from app.middleware.auth_middleware import AuthMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware

# 设置日志
setup_logging()
logger = logging.getLogger(__name__)

# 全局服务实例
chat_manager: ChatManager = None
agno_integration: AgnoIntegration = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global chat_manager, agno_integration
    
    # 启动阶段
    logger.info("启动 Chat Service...")
    
    try:
        # 初始化Agno集成
        agno_integration = AgnoIntegration()
        await agno_integration.initialize()
        
        # 初始化聊天管理器
        chat_manager = ChatManager(agno_integration)
        await chat_manager.initialize()
        
        # 向网关注册服务
        await register_with_gateway()
        
        logger.info("Chat Service 启动完成")
        
        yield
        
    except Exception as e:
        logger.error(f"Chat Service 启动失败: {e}")
        raise
    finally:
        # 关闭阶段
        logger.info("关闭 Chat Service...")
        
        if chat_manager:
            await chat_manager.cleanup()
        
        if agno_integration:
            await agno_integration.cleanup()
        
        logger.info("Chat Service 已关闭")


async def register_with_gateway():
    """向网关注册服务"""
    import aiohttp
    
    registration_data = {
        "service_name": "chat-service",
        "service_type": "chat",
        "version": "1.0.0",
        "host": settings.host,
        "port": settings.port,
        "health_check_path": "/health",
        "endpoints": [
            "/api/v1/chat",
            "/api/v1/sessions",
            "/api/v1/voice"
        ],
        "description": "基于Agno框架的聊天对话服务"
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
        title="Chat Service",
        description="基于Agno框架的聊天对话服务",
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
    app.include_router(chat_router, prefix="/api/v1/chat", tags=["聊天"])
    app.include_router(session_router, prefix="/api/v1/sessions", tags=["会话"])
    app.include_router(voice_router, prefix="/api/v1/voice", tags=["语音"])
    
    # 健康检查
    @app.get("/health")
    async def health_check():
        """健康检查"""
        try:
            # 检查Agno集成状态
            agno_status = await agno_integration.get_status() if agno_integration else False
            
            # 检查聊天管理器状态
            chat_status = chat_manager.is_healthy() if chat_manager else False
            
            return {
                "status": "healthy" if agno_status and chat_status else "unhealthy",
                "timestamp": asyncio.get_event_loop().time(),
                "services": {
                    "agno_integration": agno_status,
                    "chat_manager": chat_status
                }
            }
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            raise HTTPException(status_code=503, detail="Service unhealthy")
    
    # 根路径
    @app.get("/")
    async def root():
        return {
            "service": "chat-service",
            "version": "1.0.0",
            "status": "running",
            "framework": "Agno"
        }
    
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