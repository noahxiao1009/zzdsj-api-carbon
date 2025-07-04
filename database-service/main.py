"""
数据库管理微服务主应用
统一管理ES、PostgreSQL、Milvus、Redis、Nacos、RabbitMQ等基础数据库服务
"""

import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.api.database_api import router as database_router
from app.config.database_config import get_database_config
from app.core.connections.database_manager import get_database_manager, close_database_manager
from app.core.health.health_checker import get_health_checker, stop_health_checker
from app.services.gateway_registry import start_gateway_registration, stop_gateway_registration

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('database_service.log')
    ]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("启动数据库管理微服务...")
    
    try:
        # 初始化数据库连接管理器
        logger.info("正在初始化数据库连接...")
        db_manager = await get_database_manager()
        
        # 启动健康检查
        logger.info("正在启动健康检查服务...")
        health_checker = await get_health_checker()
        
        # 启动网关注册
        logger.info("正在启动网关注册服务...")
        await start_gateway_registration()
        
        logger.info("数据库管理微服务启动完成")
        
        yield
        
    except Exception as e:
        logger.error(f"服务启动失败: {e}")
        raise
    
    finally:
        # 关闭服务
        logger.info("正在关闭数据库管理微服务...")
        
        # 停止网关注册
        await stop_gateway_registration()
        
        # 停止健康检查
        await stop_health_checker()
        
        # 关闭数据库连接
        await close_database_manager()
        
        logger.info("数据库管理微服务已关闭")


def create_app() -> FastAPI:
    """创建FastAPI应用"""
    config = get_database_config()
    
    app = FastAPI(
        title="数据库管理微服务",
        description="统一管理ES、PostgreSQL、Milvus、Redis、Nacos、RabbitMQ等基础数据库服务",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # 配置CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 注册路由
    app.include_router(database_router)
    
    # 根路径健康检查
    @app.get("/")
    async def root():
        return {
            "service": "数据库管理微服务",
            "version": "1.0.0",
            "status": "running",
            "supported_databases": [
                "postgresql",
                "elasticsearch",
                "milvus", 
                "redis",
                "nacos",
                "rabbitmq"
            ]
        }
    
    # 简单健康检查
    @app.get("/health")
    async def simple_health():
        return {"status": "healthy"}
    
    return app


# 创建应用实例
app = create_app()


def setup_signal_handlers():
    """设置信号处理器"""
    def signal_handler(signum, frame):
        logger.info(f"接收到信号 {signum}，开始优雅关闭...")
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)


def main():
    """主函数"""
    setup_signal_handlers()
    
    config = get_database_config()
    
    logger.info(f"启动数据库管理微服务，端口: {config.service_port}")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=config.service_port,
        reload=config.debug,
        log_level="info" if not config.debug else "debug",
        workers=1,  # 数据库连接管理器需要单进程
        access_log=True
    )


if __name__ == "__main__":
    main() 