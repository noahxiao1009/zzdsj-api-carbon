"""
NextAgent - 知识库服务
基于LlamaIndex和Agno框架的知识库管理和检索服务

服务端口: 8082
微服务架构组件: 知识库服务 (Knowledge Service)

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
from app.api.splitter_routes import router as splitter_router
from app.core.enhanced_knowledge_manager import get_unified_knowledge_manager

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
    logger.info("[STARTUP] 正在初始化知识库服务应用...")
    
    # 环境初始化和验证
    try:
        logger.info("[INIT] 正在进行环境初始化验证...")
        from app.utils.environment_initializer import initialize_environment
        
        init_result = await initialize_environment()
        if init_result['overall_status'] == 'failed':
            logger.error("[ERROR] 环境初始化失败，服务无法启动")
            logger.error(f"[ERROR] 错误详情: {[err.message for err in init_result['errors']]}")
            for rec in init_result['recommendations']:
                logger.error(f"[RECOMMENDATION] {rec}")
            raise RuntimeError("环境初始化失败")
        elif init_result['overall_status'] == 'partial':
            logger.warning(f"[WARNING] 环境初始化部分成功: {init_result['summary']}")
            for err in init_result['errors']:
                logger.warning(f"[WARNING] {err.component}: {err.message}")
        else:
            logger.info(f"[SUCCESS] 环境初始化完成: {init_result['summary']}")
        
        # 记录各组件状态
        for component, result in init_result['components'].items():
            status_icon = "✓" if result.status == 'success' else "⚠" if result.status == 'skipped' else "✗"
            logger.info(f"[COMPONENT] {status_icon} {component}: {result.message}")
            
    except Exception as e:
        logger.error(f"[ERROR] 环境初始化异常: {e}")
        raise
    
    # 使用快速管理器进行轻量级初始化
    try:
        logger.info("[INIT] 正在初始化快速知识库管理器...")
        from app.models.database import get_db
        from app.core.fast_knowledge_manager import get_fast_knowledge_manager
        
        db = next(get_db())
        try:
            fast_manager = get_fast_knowledge_manager(db)
            total_count = fast_manager.count_knowledge_bases()
            logger.info("[SUCCESS] 快速知识库管理器初始化成功")
            
            # 获取快速统计信息
            logger.info("[STATS] 正在获取服务统计信息...")
            logger.info(f"[STATS] 服务统计: 知识库数量={total_count}, 文档数量=0")
        finally:
            db.close()
        
    except Exception as e:
        logger.error(f"[ERROR] 知识库服务初始化失败: {e}")
        # 不抛出异常，允许服务继续启动
        logger.warning("[WARNING] 使用降级模式启动服务")
    
    # 启动任务监听器
    try:
        logger.info("[TASK_LISTENER] 正在启动任务监听器...")
        from app.services.task_listener import start_task_listener
        asyncio.create_task(start_task_listener())
        logger.info("[SUCCESS] 任务监听器启动成功")
    except Exception as e:
        logger.error(f"[ERROR] 任务监听器启动失败: {e}")
        logger.info("[WORKER] 任务监听器启动失败，但服务将继续运行")
    
    logger.info(f"[READY] 知识库服务已就绪，监听端口: {settings.port}")
    logger.info("[READY] 服务文档地址: http://localhost:{}/docs".format(settings.port))

    
    yield
    
    # 关闭时执行
    logger.info("[SHUTDOWN] 正在关闭知识库服务...")
    
    # 停止任务监听器
    try:
        logger.info("[SHUTDOWN] 正在停止任务监听器...")
        from app.services.task_listener import stop_task_listener
        await stop_task_listener()
        logger.info("[SUCCESS] 任务监听器已停止")
    except Exception as e:
        logger.error(f"[ERROR] 任务监听器停止失败: {e}")
    
    logger.info("[SHUTDOWN] 知识库服务已安全关闭")


# 创建FastAPI应用
app = FastAPI(
    title="NextAgent - 知识库服务",
    lifespan=lifespan,
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
    openapi_url="/openapi.json"
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
    logger.info(f"[REQUEST] [{request_id}] {request.method} {request.url.path}")
    
    try:
        # 处理请求
        response = await call_next(request)
        
        # 计算处理时间
        process_time = time.time() - start_time
        
        # 根据状态码确定日志级别
        if response.status_code >= 400:
            logger.warning(f"[RESPONSE] [{request_id}] 状态码: {response.status_code}, 耗时: {process_time:.3f}s")
        else:
            logger.info(f"[RESPONSE] [{request_id}] 状态码: {response.status_code}, 耗时: {process_time:.3f}s")
        
        # 添加响应头
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(process_time)
        
        return response
        
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"[ERROR] [{request_id}] 请求处理异常: {e}, 耗时: {process_time:.3f}s")
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
    logger.error(f"[EXCEPTION] 未预期的错误: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "status_code": 500,
            "message": "内部服务器错误",
            "path": str(request.url),
            "timestamp": time.time()
        }
    )


# 健康检查端点
@app.get("/health", tags=["系统"])
async def health_check():
    """健康检查"""
    try:
        # 使用快速管理器进行健康检查
        from app.models.database import get_db
        from app.core.fast_knowledge_manager import get_fast_knowledge_manager
        
        db = next(get_db())
        try:
            fast_manager = get_fast_knowledge_manager(db)
            total_count = fast_manager.count_knowledge_bases()
            
            return {
                "status": "healthy",
                "service": "knowledge-service",
                "version": "1.0.0",
                "port": settings.port,
                "timestamp": time.time(),
                "stats": {
                    "total_knowledge_bases": total_count,
                    "performance_mode": "optimized",
                    "fast_api": True
                }
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"[HEALTH] 健康检查失败: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "service": "knowledge-service",
                "error": str(e),
                "timestamp": time.time()
            }
        )


@app.get("/", tags=["系统"])
async def root():
    """根端点"""
    return {
        "message": "NextAgent - 知识库服务",
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
app.include_router(knowledge_router, prefix="/api/v1")  # 启用完整知识库路由
app.include_router(splitter_router, prefix="/api/v1")

# 注册快速知识库路由（优化性能）- 替换原始路由
from app.api.fast_knowledge_routes import router as fast_knowledge_router
app.include_router(fast_knowledge_router, prefix="/api/v1/fast")
# app.include_router(fast_knowledge_router, prefix="/api/v1")  # 注释掉，避免与完整路由冲突

# 注册前端专用路由（为前端BFF层优化）
from app.api.frontend_routes import router as frontend_router
app.include_router(frontend_router, prefix="/api")

# 注册新的异步上传路由
from app.api.upload_routes import router as upload_router
app.include_router(upload_router, prefix="/api/v1")

# 注册知识库检索模式管理路由
from app.api.knowledge_search_routes import router as knowledge_search_router
app.include_router(knowledge_search_router, prefix="/api/v1")

# 注册文件夹管理路由
from app.api.folder_management_routes import router as folder_management_router
app.include_router(folder_management_router, prefix="/api/v1")

# 注册切分策略管理路由
from app.api.splitter_strategy_routes import router as splitter_strategy_router
app.include_router(splitter_strategy_router, prefix="/api/v1")

# 注册知识库配置管理路由
from app.api.knowledge_base_config_routes import router as kb_config_router
app.include_router(kb_config_router, prefix="/api/v1")


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
            "knowledge_service": {
                "manager_type": "enhanced",
                "database_integrated": True,
                "document_processing": True,
                "embedding_service": True
            },
            "frameworks": {
                "llamaindex": "integrated",
                "agno": "integrated"
            }
        }
    except Exception as e:
        return {
            "error": str(e),
            "message": "Debug info collection failed"
        }


def print_startup_banner():
    """打印服务启动横幅"""
    banner = f"""
{'='*80}
    NextAgent - 知识库服务 (Knowledge Service)
{'='*80}
    服务版本: v1.0.0
    运行端口: {settings.port}
    环境配置: {getattr(settings, 'environment', 'development')}
    日志级别: {settings.log_level.upper()}
    
    核心功能:
    • 双框架支持: LlamaIndex + Agno
    • 多模型集成: OpenAI, Azure, HuggingFace
    • 多向量存储: PGVector, Milvus, ElasticSearch
    • 检索模式: llamaindex, agno, hybrid
{'='*80}
"""
    print(banner)


if __name__ == "__main__":
    # 打印启动横幅
    print_startup_banner()
    
    # 日志启动信息
    logger.info("[STARTUP] 正在启动知识库服务...")
    logger.info(f"[CONFIG] 服务端口: {settings.port}")
    logger.info(f"[CONFIG] 运行环境: {getattr(settings, 'environment', 'development')}")
    
    try:
        # 确定是否启用热重载
        enable_reload = (
            settings.environment == "development" and 
            getattr(settings, 'enable_reload', True)
        )
        
        # 热重载配置
        reload_config = {}
        if enable_reload:
            reload_config.update({
                "reload": True,
                "reload_dirs": getattr(settings, 'reload_dirs', ["app", "config"]),
                "reload_excludes": getattr(settings, 'reload_excludes', ["*.log", "*.tmp", "__pycache__"])
            })
            logger.info(f"[RELOAD] 热重载已启用，监控目录: {reload_config['reload_dirs']}")
        else:
            reload_config["reload"] = False
            logger.info("[RELOAD] 热重载已禁用")
        
        logger.info("[STARTUP] 服务启动中...")
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=settings.port,
            log_level=settings.log_level.lower(),
            access_log=True,
            use_colors=True,
            **reload_config
        )
    except KeyboardInterrupt:
        logger.info("[SHUTDOWN] 知识库服务已被用户停止")
        print("\n" + "="*80)
        print("    知识库服务已安全关闭")
        print("="*80)
    except Exception as e:
        logger.error(f"[ERROR] 知识库服务启动失败: {e}")
        print(f"\n错误: 服务启动失败 - {e}")
        sys.exit(1) 