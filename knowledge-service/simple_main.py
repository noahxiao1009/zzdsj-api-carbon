#!/usr/bin/env python3
"""
简化的知识库服务启动脚本
用于快速启动和测试基本功能
"""

import asyncio
import logging
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 基础配置
from app.config.settings import settings

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
    
    try:
        # 基础服务检查
        logger.info("✅ Settings loaded successfully")
        logger.info(f"📊 Database URL: {settings.get_database_url()}")
        logger.info(f"📊 Redis URL: {settings.get_redis_url()}")
        
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
    
    - **知识库管理**: 创建、配置、管理和删除知识库
    - **文档处理**: 支持多种文档格式的上传、解析和处理
    - **智能检索**: 支持向量检索、关键词检索和混合检索
    - **框架集成**: 同时支持 LlamaIndex 和 Agno 框架的检索
    
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

# 请求中间件 - 日志和监控
@app.middleware("http")
async def request_middleware(request, call_next):
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


# 基础端点
@app.get("/health", tags=["系统"])
async def health_check():
    """健康检查"""
    try:
        return {
            "status": "healthy",
            "service": "knowledge-service",
            "version": "1.0.0",
            "port": settings.port,
            "timestamp": time.time(),
            "database": {
                "url": settings.get_database_url() is not None,
                "redis": settings.get_redis_url() is not None
            }
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
            "知识库管理",
            "文档处理", 
            "智能检索",
            "多框架支持",
            "向量化存储"
        ]
    }


# 简化的知识库管理端点
@app.get("/api/v1/knowledge-bases/", tags=["知识库"])
async def list_knowledge_bases():
    """获取知识库列表（简化版）"""
    return {
        "success": True,
        "data": {
            "knowledge_bases": [],
            "pagination": {
                "page": 1,
                "page_size": 10,
                "total": 0,
                "total_pages": 0
            }
        },
        "message": "知识库服务已启动，暂无知识库数据"
    }


@app.post("/api/v1/knowledge-bases/", tags=["知识库"])
async def create_knowledge_base(request: Dict[str, Any]):
    """创建知识库（简化版）"""
    logger.info(f"Received create knowledge base request: {request}")
    
    return {
        "success": True,
        "message": "知识库创建功能尚未完全初始化",
        "data": {
            "id": "demo-kb-001",
            "name": request.get("name", "演示知识库"),
            "status": "pending",
            "created_at": time.time()
        }
    }


@app.get("/api/v1/models/embedding", tags=["模型"])
async def get_embedding_models():
    """获取可用嵌入模型（简化版）"""
    return {
        "success": True,
        "data": {
            "models": [
                {
                    "provider": "siliconflow",
                    "model": "Qwen/Qwen3-Embedding-8B",
                    "dimension": 8192,
                    "description": "硅基流动嵌入模型"
                }
            ],
            "total": 1,
            "provider_counts": {
                "siliconflow": 1
            }
        }
    }


@app.get("/debug", tags=["调试"], include_in_schema=False)
async def debug_info():
    """调试信息"""
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
        "vector_store": {
            "type": settings.vector_store.vector_db_type,
            "milvus_host": settings.vector_store.milvus_host,
            "milvus_port": settings.vector_store.milvus_port
        },
        "embedding": {
            "provider": settings.embedding.default_embedding_provider,
            "model": settings.embedding.default_embedding_model,
            "dimension": settings.embedding.default_embedding_dimension
        }
    }


if __name__ == "__main__":
    # 直接运行时的配置
    logger.info(f"🚀 Starting Simple Knowledge Service on port {settings.port}")
    
    try:
        uvicorn.run(
            "simple_main:app",
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
