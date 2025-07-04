"""
Gateway Service - 网关服务主启动文件
基于原ZZDSJ Backend API架构改造的网关层
集成服务注册、路由管理、认证和任务调度功能
"""

import uvicorn
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles
import atexit
import os
import logging
import json
import time
import asyncio
from pathlib import Path
from typing import Dict, Any

# 导入配置系统（基于原有架构）
from app.config.settings import get_settings, GatewaySettings
from app.utils.common.logging_config import get_logger

# 导入服务注册和发现
from app.discovery.service_registry import ServiceRegistry

# 导入任务调度系统
from app.tasks.task_scheduler import TaskScheduler
from app.tasks.thread_pool import ThreadPoolManager

# 导入中间件
from app.middleware.request_tracker import RequestTracker
from app.middleware.auth_middleware import AuthMiddleware
from app.middleware.api_key_middleware import APIKeyMiddleware
from app.middleware.internal_auth import InternalAuthMiddleware

# 导入路由器
from app.api.frontend import router as frontend_router
from app.api.v1 import router as v1_router
from app.api.system import router as system_router
from app.api.gateway import router as gateway_router

def pre_startup_config_check():
    """启动前配置检查"""
    print("🔍 执行网关服务启动前配置检查...")
    
    # 检查环境变量
    app_env = os.getenv("APP_ENV", "development")
    service_name = os.getenv("SERVICE_NAME", "gateway-service")
    
    print(f"   服务名称: {service_name}")
    print(f"   当前环境: {app_env}")
    
    print("✅ 网关服务配置检查通过")

def validate_startup_config() -> Dict[str, Any]:
    """验证启动配置"""
    print("🔍 验证网关服务启动配置...")
    
    try:
        settings = get_settings()
        
        config = {
            "app": {
                "name": "ZZDSJ Gateway Service",
                "version": "1.0.0",
                "environment": os.getenv("APP_ENV", "development"),
                "debug": settings.DEBUG
            },
            "service": {
                "name": settings.SERVICE_NAME,
                "ip": settings.SERVICE_IP,
                "port": settings.SERVICE_PORT,
            },
            "api": {
                "title": "ZZDSJ API Gateway",
                "description": "智政科技AI办公助手 - API网关服务",
            },
            "security": {
                "cors": {
                    "enabled": True,
                    "origins": settings.CORS_ORIGINS,
                    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                    "headers": ["*"]
                }
            }
        }
        
        print("✅ 网关服务配置验证通过")
        print(f"   服务端口: {config['service']['port']}")
        
        return config
        
    except Exception as e:
        print(f"❌ 配置验证失败: {str(e)}")
        return {
            "app": {"name": "Gateway Service", "version": "1.0.0", "debug": True},
            "service": {"name": "gateway-service", "ip": "0.0.0.0", "port": 8080},
            "api": {"title": "Gateway API", "description": "API Gateway Service"}
        }

def setup_application_config(config: Dict[str, Any]) -> FastAPI:
    """根据配置设置应用"""
    
    app_config = config.get("app", {})
    api_config = config.get("api", {})
    
    app_title = api_config.get("title", app_config.get("name", "Gateway Service"))
    app_description = api_config.get("description", "API网关服务")
    app_version = app_config.get("version", "1.0.0")
    
    app = FastAPI(
        title=app_title,
        description=app_description,
        version=app_version,
        docs_url=None,
        redoc_url=None,
    )
    
    return app

def setup_cors_middleware(app: FastAPI, config: Dict[str, Any]):
    """设置CORS中间件"""
    
    security_config = config.get("security", {})
    cors_config = security_config.get("cors", {})
    
    if cors_config.get("enabled", True):
        origins = cors_config.get("origins", ["*"])
        methods = cors_config.get("methods", ["GET", "POST", "PUT", "DELETE", "OPTIONS"])
        headers = cors_config.get("headers", ["*"])
        
        if isinstance(origins, str):
            try:
                origins = json.loads(origins)
            except json.JSONDecodeError:
                origins = [origins]
        
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=methods,
            allow_headers=headers,
        )
        print(f"✅ CORS已启用")

def setup_custom_middleware(app: FastAPI):
    """设置自定义中间件"""
    
    # 请求跟踪中间件
    request_tracker = RequestTracker()
    app.add_middleware(
        type(request_tracker).__class__,
        tracker=request_tracker
    )
    
    print("✅ 自定义中间件已注册")

def setup_routers(app: FastAPI):
    """设置路由器"""
    
    # 注册各层API路由
    app.include_router(
        frontend_router,
        prefix="/frontend",
        tags=["Frontend API"]
    )
    
    app.include_router(
        v1_router,
        prefix="/v1",
        tags=["External API"]
    )
    
    app.include_router(
        system_router,
        prefix="/system",
        tags=["System API"]
    )
    
    app.include_router(
        gateway_router,
        prefix="/gateway",
        tags=["Gateway Management"]
    )
    
    print("✅ 所有路由器已注册")

# 全局组件
service_registry: ServiceRegistry = None
task_scheduler: TaskScheduler = None
thread_pool_manager: ThreadPoolManager = None

# 应用初始化
pre_startup_config_check()
startup_config = validate_startup_config()
app = setup_application_config(startup_config)
setup_cors_middleware(app, startup_config)
setup_custom_middleware(app)
setup_routers(app)

# 初始化默认日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = get_logger(__name__)

# 静态文件
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# 基础路由
@app.get("/", include_in_schema=False)
def root():
    return {
        "message": "欢迎使用ZZDSJ API网关服务", 
        "service": "gateway-service",
        "version": startup_config.get("app", {}).get("version", "1.0.0"),
        "docs": "/docs",
        "features": [
            "服务注册与发现",
            "多层API接口（frontend/v1/system）",
            "统一认证中间件",
            "多线程任务调度",
            "负载均衡",
            "健康检查",
            "请求监控"
        ]
    }

@app.get("/health")
def health_check():
    """健康检查接口"""
    global service_registry, task_scheduler, thread_pool_manager
    
    health_status = {
        "status": "healthy",
        "service": "gateway-service",
        "timestamp": time.time(),
        "components": {}
    }
    
    # 检查服务注册器状态
    if service_registry:
        try:
            registry_stats = service_registry.get_stats()
            health_status["components"]["service_registry"] = {
                "status": "healthy",
                "stats": registry_stats
            }
        except Exception as e:
            health_status["components"]["service_registry"] = {
                "status": "unhealthy",
                "error": str(e)
            }
    
    # 检查任务调度器状态
    if task_scheduler:
        try:
            scheduler_stats = task_scheduler.get_stats()
            health_status["components"]["task_scheduler"] = {
                "status": "healthy",
                "stats": scheduler_stats
            }
        except Exception as e:
            health_status["components"]["task_scheduler"] = {
                "status": "unhealthy",
                "error": str(e)
            }
    
    # 检查线程池状态
    if thread_pool_manager:
        try:
            pool_stats = thread_pool_manager.get_stats()
            health_status["components"]["thread_pool"] = {
                "status": "healthy",
                "stats": pool_stats
            }
        except Exception as e:
            health_status["components"]["thread_pool"] = {
                "status": "unhealthy",
                "error": str(e)
            }
    
    return health_status

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    api_config = startup_config.get("api", {})
    title = api_config.get("title", "API网关服务")
    
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=f"{title} - API文档",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
    )

@app.get("/openapi.json", include_in_schema=False)
async def get_open_api_endpoint():
    app_config = startup_config.get("app", {})
    api_config = startup_config.get("api", {})
    
    title = api_config.get("title", app_config.get("name", "API网关服务"))
    version = app_config.get("version", "1.0.0")
    description = api_config.get("description", "智政科技AI办公助手网关服务")
    
    return get_openapi(
        title=title,
        version=version,
        description=f"""
# {title}

## 🎯 网关功能特点
- **统一入口**: 所有API请求的统一入口点
- **路由分发**: 智能路由到后端微服务
- **服务注册**: 自动服务发现与注册机制
- **负载均衡**: 多种负载均衡算法支持
- **认证鉴权**: 三层认证体系（JWT/API Key/内部认证）
- **任务调度**: 多线程任务调度与执行
- **限流熔断**: 防护系统过载和故障传播
- **监控日志**: 完整的请求监控和日志记录

## 📋 API接口分层
- **Frontend层 (/frontend)**: 前端页面相关接口
- **V1层 (/v1)**: 外部系统调用接口
- **System层 (/system)**: 系统内部任务接口
- **Gateway层 (/gateway)**: 网关管理接口

## 🔧 环境信息
- **当前环境**: {os.getenv('APP_ENV', 'development')}
- **服务版本**: {version}
- **网关节点**: gateway-service

{description}
        """,
        routes=app.routes,
    )

# 启动和关闭事件
@app.on_event("startup")
async def startup_event():
    """网关服务启动事件"""
    global service_registry, task_scheduler, thread_pool_manager
    
    logger.info("🚀 ZZDSJ Gateway Service 启动中...")
    
    try:
        # 初始化线程池管理器
        thread_pool_manager = ThreadPoolManager()
        await thread_pool_manager.start()
        logger.info("✅ 线程池管理器已启动")
        
        # 初始化任务调度器
        task_scheduler = TaskScheduler(thread_pool_manager=thread_pool_manager)
        await task_scheduler.start()
        logger.info("✅ 任务调度器已启动")
        
        # 初始化服务注册器
        service_registry = ServiceRegistry()
        await service_registry.start()
        logger.info("✅ 服务注册器已启动")
        
        # 注册网关服务自身
        service_config = startup_config.get("service", {})
        await service_registry.register_service(
            service_name=service_config.get("name", "gateway-service"),
            service_id="gateway-service-1",
            host=service_config.get("ip", "0.0.0.0"),
            port=service_config.get("port", 8080),
            metadata={
                "version": startup_config.get("app", {}).get("version", "1.0.0"),
                "type": "gateway",
                "features": ["routing", "auth", "load_balancing", "task_scheduling"]
            }
        )
        logger.info("✅ 网关服务已自注册")
        
        logger.info("🎉 ZZDSJ Gateway Service 启动完成")
        
    except Exception as e:
        logger.error(f"❌ 网关服务启动失败: {str(e)}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """网关服务关闭事件"""
    global service_registry, task_scheduler, thread_pool_manager
    
    logger.info("🔄 ZZDSJ Gateway Service 关闭中...")
    
    try:
        # 停止服务注册器
        if service_registry:
            await service_registry.stop()
            logger.info("✅ 服务注册器已停止")
        
        # 停止任务调度器
        if task_scheduler:
            await task_scheduler.stop()
            logger.info("✅ 任务调度器已停止")
        
        # 停止线程池管理器
        if thread_pool_manager:
            await thread_pool_manager.stop()
            logger.info("✅ 线程池管理器已停止")
        
        logger.info("👋 ZZDSJ Gateway Service 已安全关闭")
        
    except Exception as e:
        logger.error(f"❌ 网关服务关闭时发生错误: {str(e)}")

if __name__ == "__main__":
    service_config = startup_config.get("service", {})
    host = service_config.get("ip", "0.0.0.0")
    port = service_config.get("port", 8080)
    reload = startup_config.get("app", {}).get("debug", False)
    
    logger.info(f"🚀 启动网关服务: {host}:{port} (重载: {reload})")
    uvicorn.run("main:app", host=host, port=port, reload=reload)
