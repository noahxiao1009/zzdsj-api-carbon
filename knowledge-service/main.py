"""
智政科技AI智能办公助手 - 知识库服务
基于LlamaIndex和Agno框架的知识库管理和检索服务

服务端口: 8082
微服务架构组件: 知识库服务 (Knowledge Service)

功能特性:
- 双框架支持: LlamaIndex精细化检索 + Agno快速检索
- 多模型集成: 支持OpenAI、Azure、HuggingFace等嵌入模型
- 多向量存储: 支持PGVector、Milvus、ElasticSearch等
- 精细化控制: 每个知识库独立配置嵌入模型和参数
- 检索模式: 支持llamaindex、agno、hybrid三种检索模式
- 企业级架构: 完整的错误处理、日志、监控、配置管理
"""

import asyncio
import logging
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.config.settings import settings
from app.api.knowledge_routes import router as knowledge_router
from app.core.knowledge_manager import get_unified_knowledge_manager

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("knowledge_service.log")
    ]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("🚀 Knowledge Service starting up...")
    
    # 初始化知识库管理器
    try:
        knowledge_manager = get_unified_knowledge_manager()
        logger.info("✅ Knowledge Manager initialized")
        
        # 获取管理器统计信息
        stats = knowledge_manager.get_stats()
        logger.info(f"📊 Knowledge Service Stats: {stats}")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize Knowledge Service: {e}")
        raise
    
    logger.info(f"🎯 Knowledge Service ready on port {settings.port}")
    
    yield
    
    # 关闭时执行
    logger.info("🛑 Knowledge Service shutting down...")


# 创建FastAPI应用
app = FastAPI(
    title="智政科技AI智能办公助手 - 知识库服务",
    description="""
    基于LlamaIndex和Agno框架的知识库管理和检索服务
    
    ## 核心功能
    
    ### 双框架支持
    - **LlamaIndex**: 精细化检索，支持复杂查询和重排序
    - **Agno**: 快速检索，使用search_knowledge=true模式
    - **Hybrid**: 混合模式，同时使用两个框架并合并结果
    
    ### 多模型集成
    - OpenAI: text-embedding-3-small, text-embedding-3-large
    - Azure OpenAI: text-embedding-ada-002
    - HuggingFace: sentence-transformers/all-MiniLM-L6-v2
    - 本地部署模型
    
    ### 向量存储支持
    - PGVector: PostgreSQL向量扩展
    - Milvus: 专业向量数据库
    - ElasticSearch: 全文搜索+向量检索
    - LanceDB: 高性能向量存储
    
    ### 企业级特性
    - 知识库精细化配置
    - 多种检索策略
    - 完整的监控和日志
    - RESTful API设计
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=settings.cors_methods,
    allow_headers=["*"],
    expose_headers=["*"]
)

# 信任主机中间件（暂时跳过，可在生产环境配置）
# if hasattr(settings, 'trusted_hosts') and settings.trusted_hosts:
#     app.add_middleware(
#         TrustedHostMiddleware,
#         allowed_hosts=settings.trusted_hosts
#     )


# 请求中间件 - 日志和监控
@app.middleware("http")
async def request_middleware(request: Request, call_next):
    """请求中间件：日志记录和性能监控"""
    start_time = time.time()
    request_id = f"req_{int(start_time * 1000)}"
    
    # 记录请求开始
    logger.info(f"🔵 [{request_id}] {request.method} {request.url}")
    
    try:
        # 处理请求
        response = await call_next(request)
        
        # 计算处理时间
        process_time = time.time() - start_time
        
        # 记录请求完成
        logger.info(f"🟢 [{request_id}] {response.status_code} - {process_time:.3f}s")
        
        # 添加响应头
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(process_time)
        
        return response
        
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"🔴 [{request_id}] Error: {e} - {process_time:.3f}s")
        raise


# 全局异常处理
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP异常处理器"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "status_code": exc.status_code,
            "message": exc.detail,
            "path": str(request.url)
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """请求验证异常处理器"""
    return JSONResponse(
        status_code=422,
        content={
            "error": True,
            "status_code": 422,
            "message": "请求参数验证失败",
            "details": exc.errors(),
            "path": str(request.url)
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """通用异常处理器"""
    logger.error(f"Unexpected error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "status_code": 500,
            "message": "内部服务器错误",
            "path": str(request.url)
        }
    )


# 健康检查端点
@app.get("/health", tags=["系统"])
async def health_check():
    """健康检查"""
    try:
        # 检查知识库管理器状态
        knowledge_manager = get_unified_knowledge_manager()
        stats = knowledge_manager.get_stats()
        
        return {
            "status": "healthy",
            "service": "knowledge-service",
            "version": "1.0.0",
            "port": settings.port,
            "timestamp": time.time(),
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "service": "knowledge-service",
                "error": str(e)
            }
        )


@app.get("/", tags=["系统"])
async def root():
    """根端点"""
    return {
        "message": "智政科技AI智能办公助手 - 知识库服务",
        "service": "knowledge-service",
        "version": "1.0.0",
        "port": settings.port,
        "docs_url": "/docs",
        "frameworks": ["LlamaIndex", "Agno"],
        "features": [
            "双框架知识库检索",
            "多嵌入模型支持", 
            "多向量存储支持",
            "精细化配置控制",
            "混合检索模式"
        ]
    }


# 注册路由
app.include_router(knowledge_router, prefix="/api/v1")


# 开发环境调试信息
@app.get("/debug", tags=["调试"], include_in_schema=False)
async def debug_info():
    """调试信息（仅开发环境）"""
    if getattr(settings, 'environment', 'development') != "development":
        raise HTTPException(status_code=404, detail="Not found")
    
    try:
        knowledge_manager = get_unified_knowledge_manager()
        
        return {
            "environment": getattr(settings, 'environment', 'development'),
            "log_level": settings.log_level,
            "service_port": settings.port,
            "database": {
                "postgres_host": settings.database.postgres_host,
                "postgres_port": settings.database.postgres_port,
                "postgres_db": settings.database.postgres_db,
                "redis_host": settings.database.redis_host,
                "redis_port": settings.database.redis_port
            },
            "knowledge_bases": list(knowledge_manager.knowledge_bases.keys()),
            "frameworks": {
                "llamaindex": knowledge_manager.llamaindex_manager.get_stats(),
                "agno": knowledge_manager.agno_manager.get_stats()
            }
        }
    except Exception as e:
        return {
            "error": str(e),
            "message": "Debug info collection failed"
        }


if __name__ == "__main__":
    # 直接运行时的配置
    logger.info(f"🚀 Starting Knowledge Service on port {settings.port}")
    
    try:
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=settings.port,
            log_level=settings.log_level.lower(),
            reload=getattr(settings, 'environment', 'development') == "development",
            access_log=True,
            use_colors=True
        )
    except KeyboardInterrupt:
        logger.info("👋 Knowledge Service stopped by user")
    except Exception as e:
        logger.error(f"❌ Failed to start Knowledge Service: {e}")
        sys.exit(1) 