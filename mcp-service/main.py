"""
MCP微服务主入口
MCP Microservice Main Entry Point
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import redis.asyncio as redis
from datetime import datetime

from app.api.mcp_management import router as mcp_router
from app.core.service_registry import initialize_service_registry
from app.services.sse_service import initialize_sse_service

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 全局变量
redis_client = None
service_registry = None
sse_service = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    logger.info("Starting MCP microservice...")
    
    try:
        # 初始化Redis客户端
        global redis_client
        redis_client = redis.Redis(
            host='localhost',
            port=6379,
            decode_responses=True
        )
        
        # 测试Redis连接
        await redis_client.ping()
        logger.info("Redis connection established")
        
        # 初始化服务注册中心
        global service_registry
        service_registry = await initialize_service_registry(redis_client)
        logger.info("Service registry initialized")
        
        # 初始化SSE服务
        global sse_service
        sse_service = await initialize_sse_service(redis_client)
        logger.info("SSE service initialized")
        
        logger.info("MCP microservice started successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize MCP microservice: {e}")
        # 如果Redis不可用，使用内存模式
        service_registry = await initialize_service_registry(None)
        sse_service = await initialize_sse_service(None)
        logger.warning("Running in memory mode without Redis")
    
    yield
    
    # 关闭时清理
    logger.info("Shutting down MCP microservice...")
    
    try:
        if service_registry:
            await service_registry.shutdown()
        
        if sse_service:
            await sse_service.shutdown()
        
        if redis_client:
            await redis_client.close()
        
        logger.info("MCP microservice shutdown complete")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

# 创建FastAPI应用
app = FastAPI(
    title="MCP微服务",
    description="MCP (Model Context Protocol) 微服务 - 基于FastMCP 2.0框架",
    version="1.0.0",
    lifespan=lifespan
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """请求日志中间件"""
    start_time = datetime.now()
    
    # 记录请求信息
    logger.info(f"Request: {request.method} {request.url}")
    
    # 处理请求
    response = await call_next(request)
    
    # 记录响应信息
    process_time = (datetime.now() - start_time).total_seconds()
    logger.info(f"Response: {response.status_code} ({process_time:.3f}s)")
    
    return response

# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc),
            "timestamp": datetime.now().isoformat()
        }
    )

# 注册路由
app.include_router(mcp_router)

# 健康检查端点
@app.get("/health")
async def health_check():
    """健康检查"""
    try:
        # 检查Redis连接
        redis_healthy = False
        if redis_client:
            try:
                await redis_client.ping()
                redis_healthy = True
            except Exception:
                pass
        
        # 检查服务组件
        components = {
            "redis": redis_healthy,
            "service_registry": service_registry is not None,
            "sse_service": sse_service is not None
        }
        
        # 判断整体健康状态
        overall_healthy = all(components.values()) or (
            components["service_registry"] and components["sse_service"]
        )
        
        return {
            "service": "mcp-service",
            "status": "healthy" if overall_healthy else "degraded",
            "components": components,
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0"
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "service": "mcp-service",
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

# 服务信息端点
@app.get("/info")
async def service_info():
    """服务信息"""
    return {
        "service": "mcp-service",
        "description": "MCP (Model Context Protocol) 微服务",
        "version": "1.0.0",
        "framework": "FastAPI",
        "mcp_framework": "FastMCP 2.0",
        "features": [
            "MCP服务管理",
            "Docker容器化部署",
            "VLAN网络隔离",
            "SSE流式通信",
            "服务注册与发现",
            "实时监控和统计"
        ],
        "endpoints": {
            "management": "/api/v1/mcp/services",
            "execution": "/api/v1/mcp/services/{service_id}/tools/{tool_name}",
            "streaming": "/api/v1/mcp/streams",
            "monitoring": "/api/v1/mcp/dashboard/stats"
        },
        "timestamp": datetime.now().isoformat()
    }

# 根路径
@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "MCP微服务运行中",
        "service": "mcp-service",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "links": {
            "health": "/health",
            "info": "/info",
            "docs": "/docs",
            "api": "/api/v1/mcp"
        }
    }

# 开发环境启动
if __name__ == "__main__":
    import os
    
    # 从环境变量获取配置
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8089"))
    log_level = os.getenv("MCP_LOG_LEVEL", "info")
    
    # 启动应用
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        log_level=log_level,
        reload=True,  # 开发环境启用热重载
        workers=1     # 单进程模式（适合开发）
    )