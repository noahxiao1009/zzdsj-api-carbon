"""
MCP Service 主应用入口
FastAPI应用配置和生命周期管理
"""

import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import uvicorn

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.database import init_database, close_database
from app.core.redis import init_redis, close_redis
from app.frameworks.fastmcp.server import init_mcp_server, close_mcp_server
from app.api import health

# 设置日志
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    logger.info("MCP Service 正在启动...")
    
    try:
        # 初始化数据库
        logger.info("初始化数据库连接...")
        await init_database()
        
        # 初始化Redis
        logger.info("初始化Redis连接...")
        await init_redis()
        
        # 初始化MCP服务器
        logger.info("初始化FastMCP服务器...")
        await init_mcp_server()
        
        # 注册默认MCP工具
        from app.frameworks.fastmcp.tools.default_tools import register_default_tools
        await register_default_tools()
        
        logger.info("MCP Service 启动完成!")
        
        yield
        
    except Exception as e:
        logger.error(f"MCP Service 启动失败: {e}")
        raise
    
    finally:
        # 关闭时清理资源
        logger.info("MCP Service 正在关闭...")
        
        try:
            # 关闭MCP服务器
            await close_mcp_server()
            
            # 关闭Redis连接
            await close_redis()
            
            # 关闭数据库连接
            await close_database()
            
            logger.info("MCP Service 已关闭")
            
        except Exception as e:
            logger.error(f"MCP Service 关闭时出错: {e}")


# 创建FastAPI应用
app = FastAPI(
    title="MCP Service",
    description="统一管理系统定义的MCP服务，使用docker部署，并指定固定网段",
    version=settings.service_version,
    docs_url="/docs" if settings.enable_docs else None,
    redoc_url="/redoc" if settings.enable_docs else None,
    openapi_url="/openapi.json" if settings.enable_docs else None,
    lifespan=lifespan
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# 添加受信主机中间件
if settings.environment == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_hosts
    )


# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录请求日志"""
    start_time = asyncio.get_event_loop().time()
    
    # 记录请求开始
    logger.info(
        f"请求开始: {request.method} {request.url.path} "
        f"- 客户端: {request.client.host if request.client else 'unknown'}"
    )
    
    try:
        response = await call_next(request)
        
        # 计算处理时间
        process_time = asyncio.get_event_loop().time() - start_time
        
        # 记录响应
        logger.info(
            f"请求完成: {request.method} {request.url.path} "
            f"- 状态码: {response.status_code} "
            f"- 耗时: {process_time:.3f}s"
        )
        
        # 添加响应头
        response.headers["X-Process-Time"] = str(process_time)
        response.headers["X-Service-Name"] = settings.service_name
        response.headers["X-Service-Version"] = settings.service_version
        
        return response
        
    except Exception as e:
        # 计算处理时间
        process_time = asyncio.get_event_loop().time() - start_time
        
        # 记录错误
        logger.error(
            f"请求失败: {request.method} {request.url.path} "
            f"- 错误: {str(e)} "
            f"- 耗时: {process_time:.3f}s"
        )
        
        # 返回错误响应
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "内部服务器错误",
                "error": str(e) if settings.debug else "服务暂时不可用",
                "timestamp": asyncio.get_event_loop().time()
            }
        )


# 全局异常处理器
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """HTTP异常处理器"""
    logger.warning(
        f"HTTP异常: {request.method} {request.url.path} "
        f"- 状态码: {exc.status_code} "
        f"- 详情: {exc.detail}"
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
            "timestamp": asyncio.get_event_loop().time()
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """请求验证异常处理器"""
    logger.warning(
        f"请求验证失败: {request.method} {request.url.path} "
        f"- 错误: {exc.errors()}"
    )
    
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "请求参数验证失败",
            "errors": exc.errors(),
            "timestamp": asyncio.get_event_loop().time()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """通用异常处理器"""
    logger.error(
        f"未处理异常: {request.method} {request.url.path} "
        f"- 错误: {str(exc)}",
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "内部服务器错误",
            "error": str(exc) if settings.debug else "服务暂时不可用",
            "timestamp": asyncio.get_event_loop().time()
        }
    )


# 根路径
@app.get("/")
async def root():
    """根路径响应"""
    return {
        "service": "mcp-service",
        "version": settings.service_version,
        "status": "running",
        "description": "MCP服务统一管理系统",
        "docs_url": "/docs" if settings.enable_docs else None,
        "timestamp": asyncio.get_event_loop().time()
    }


# 注册路由
app.include_router(health.router)

# 条件性注册其他路由（如果模块存在）
try:
    from app.api import services
    app.include_router(services.router)
    logger.info("注册服务管理路由")
except ImportError:
    logger.warning("服务管理路由模块不存在，跳过注册")

try:
    from app.api import tools
    app.include_router(tools.router)
    logger.info("注册工具管理路由")
except ImportError:
    logger.warning("工具管理路由模块不存在，跳过注册")

try:
    from app.api import deployments
    app.include_router(deployments.router)
    logger.info("注册部署管理路由")
except ImportError:
    logger.warning("部署管理路由模块不存在，跳过注册")


# 自定义OpenAPI配置
def custom_openapi():
    """自定义OpenAPI文档"""
    if app.openapi_schema:
        return app.openapi_schema
    
    from fastapi.openapi.utils import get_openapi
    
    openapi_schema = get_openapi(
        title="MCP Service API",
        version=settings.service_version,
        description="""
        MCP (Model Context Protocol) 服务管理系统
        
        ## 功能特性
        
        - 🚀 **服务管理**: 创建、配置、部署MCP服务
        - 🛠️ **工具管理**: 注册和管理MCP工具
        - 📊 **监控管理**: 服务健康检查和性能监控
        - 🔧 **部署管理**: Docker容器化部署和管理
        - 📝 **日志管理**: 服务日志查看和分析
        
        ## 技术栈
        
        - **框架**: FastMCP V2、FastAPI
        - **数据库**: PostgreSQL
        - **缓存**: Redis
        - **容器**: Docker
        - **监控**: 自定义健康检查
        
        ## 认证说明
        
        本服务通过网关层进行统一认证和路由管理。
        """,
        routes=app.routes,
    )
    
    openapi_schema["info"]["x-logo"] = {
        "url": "https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png"
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


if __name__ == "__main__":
    # 开发模式运行
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info" if not settings.debug else "debug",
        access_log=settings.debug
    ) 