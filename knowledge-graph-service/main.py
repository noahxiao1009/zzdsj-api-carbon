"""
Knowledge Graph Service - 知识图谱服务

基于ArangoDB的知识图谱构建、管理和查询服务
完全迁移原始项目中的ai_knowledge_graph实现

主要功能：
- 知识图谱构建与管理
- 三元组抽取与实体识别
- 关系推断与图谱扩展
- 图谱可视化与查询
- 与其他微服务的集成
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Any

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from app.core.config import get_settings
from app.core.knowledge_graph_manager import KnowledgeGraphManager
from app.core.service_registry import ServiceRegistry
from app.middleware.auth_middleware import AuthMiddleware
from app.middleware.rate_limit_middleware import RateLimitMiddleware
from app.api.routes import router as api_router
from app.utils.logger import setup_logger

# 配置日志
logger = setup_logger(__name__)

# Prometheus指标
REQUEST_COUNT = Counter(
    'knowledge_graph_requests_total',
    'Total requests',
    ['method', 'endpoint', 'status_code']
)

REQUEST_DURATION = Histogram(
    'knowledge_graph_request_duration_seconds',
    'Request duration',
    ['method', 'endpoint']
)

GRAPH_OPERATIONS = Counter(
    'knowledge_graph_operations_total',
    'Total graph operations',
    ['operation_type', 'status']
)

ACTIVE_GRAPHS = Counter(
    'knowledge_graph_active_graphs_total',
    'Total active graphs'
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("🚀 Knowledge Graph Service 启动中...")
    
    try:
        # 初始化知识图谱管理器
        kg_manager = KnowledgeGraphManager()
        await kg_manager.initialize()
        app.state.kg_manager = kg_manager
        
        # 初始化服务注册器
        service_registry = ServiceRegistry()
        await service_registry.initialize()
        app.state.service_registry = service_registry
        
        # 注册到网关
        if settings.GATEWAY_ENABLED:
            await service_registry.register_to_gateway()
            logger.info("✅ 服务已注册到网关")
        
        # 启动后台任务
        asyncio.create_task(background_tasks())
        
        logger.info("✅ Knowledge Graph Service 启动完成")
        
        yield
        
    except Exception as e:
        logger.error(f"❌ 服务启动失败: {e}")
        raise
    finally:
        # 清理资源
        logger.info("🔄 Knowledge Graph Service 关闭中...")
        
        try:
            if hasattr(app.state, 'kg_manager'):
                await app.state.kg_manager.cleanup()
            if hasattr(app.state, 'service_registry'):
                await app.state.service_registry.cleanup()
                
            logger.info("✅ Knowledge Graph Service 已安全关闭")
        except Exception as e:
            logger.error(f"❌ 服务关闭异常: {e}")


async def background_tasks():
    """后台任务"""
    while True:
        try:
            # 每30秒执行一次健康检查和指标更新
            await asyncio.sleep(30)
            
            # 更新图谱统计
            # 这里可以添加定期的图谱维护任务
            
        except Exception as e:
            logger.error(f"后台任务异常: {e}")
            await asyncio.sleep(10)


# 创建FastAPI应用
app = FastAPI(
    title="Knowledge Graph Service",
    description="知识图谱构建、管理和查询服务",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# 添加中间件
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加认证中间件
app.add_middleware(AuthMiddleware)

# 添加限流中间件
app.add_middleware(RateLimitMiddleware)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """指标收集中间件"""
    start_time = time.time()
    
    # 处理请求
    response = await call_next(request)
    
    # 记录指标
    duration = time.time() - start_time
    method = request.method
    endpoint = request.url.path
    status_code = response.status_code
    
    REQUEST_COUNT.labels(
        method=method,
        endpoint=endpoint,
        status_code=status_code
    ).inc()
    
    REQUEST_DURATION.labels(
        method=method,
        endpoint=endpoint
    ).observe(duration)
    
    # 添加响应头
    response.headers["X-Process-Time"] = str(duration)
    
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器"""
    logger.error(f"未处理的异常: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "内部服务器错误",
            "message": str(exc) if settings.DEBUG else "服务暂时不可用",
            "timestamp": datetime.utcnow().isoformat(),
            "path": request.url.path
        }
    )


# 健康检查端点
@app.get("/health")
async def health_check():
    """健康检查"""
    try:
        kg_manager = app.state.kg_manager
        health_status = await kg_manager.health_check()
        
        return {
            "status": "healthy" if health_status["healthy"] else "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "service": "knowledge-graph-service",
            "checks": health_status
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
        )


# 指标端点
@app.get("/metrics")
async def metrics():
    """Prometheus指标端点"""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


# 服务信息端点
@app.get("/info")
async def service_info():
    """服务信息"""
    try:
        kg_manager = app.state.kg_manager
        stats = await kg_manager.get_statistics()
        
        return {
            "service": "knowledge-graph-service",
            "version": "1.0.0",
            "description": "知识图谱构建、管理和查询服务",
            "timestamp": datetime.utcnow().isoformat(),
            "features": [
                "知识图谱构建与管理",
                "三元组抽取与实体识别", 
                "关系推断与图谱扩展",
                "图谱可视化与查询",
                "ArangoDB图数据库支持",
                "多模型知识图谱"
            ],
            "statistics": stats,
            "configuration": {
                "debug": settings.DEBUG,
                "database_url": settings.ARANGO_URL.split('@')[1] if '@' in settings.ARANGO_URL else settings.ARANGO_URL,
                "max_graphs": settings.MAX_GRAPHS_PER_USER,
                "extraction_enabled": settings.EXTRACTION_ENABLED
            }
        }
    except Exception as e:
        logger.error(f"获取服务信息失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


# 注册API路由
app.include_router(api_router, prefix="/api/v1")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        access_log=settings.DEBUG,
        log_level="info" if not settings.DEBUG else "debug"
    ) 