"""
Message Push Service - SSE消息推送微服务
为整个微服务架构提供统一的实时消息推送能力

服务端口: 8089
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
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.core.connection_manager import connection_manager
from app.core.message_queue import message_queue
from app.api.sse_routes import router as sse_router

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("message_push_service.log")
    ]
)

logger = logging.getLogger(__name__)

# 服务配置
SERVICE_PORT = 8089
SERVICE_NAME = "message-push-service"
SERVICE_VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info(f"[STARTUP] 正在初始化{SERVICE_NAME}...")
    
    try:
        # 启动连接管理器
        logger.info("[INIT] 正在启动连接管理器...")
        await connection_manager.start()
        logger.info("[SUCCESS] 连接管理器启动成功")
        
        # 连接消息队列
        logger.info("[INIT] 正在连接消息队列...")
        await message_queue.connect()
        logger.info("[SUCCESS] 消息队列连接成功")
        
        # 启动消息消费者
        logger.info("[INIT] 正在启动消息消费者...")
        await message_queue.start_consumer("message-push-consumer")
        logger.info("[SUCCESS] 消息消费者启动成功")
        
        # 注册服务到网关（可选）
        await register_to_gateway()
        
        logger.info(f"[READY] {SERVICE_NAME}已就绪，监听端口: {SERVICE_PORT}")
        logger.info(f"[READY] 文档地址: http://localhost:{SERVICE_PORT}/docs")
        
    except Exception as e:
        logger.error(f"[ERROR] 服务初始化失败: {e}")
        raise
    
    yield
    
    # 关闭时执行
    logger.info(f"[SHUTDOWN] 正在关闭{SERVICE_NAME}...")
    
    try:
        # 停止连接管理器
        await connection_manager.stop()
        logger.info("[SUCCESS] 连接管理器已停止")
        
        # 断开消息队列
        await message_queue.disconnect()
        logger.info("[SUCCESS] 消息队列已断开")
        
    except Exception as e:
        logger.error(f"[ERROR] 服务关闭失败: {e}")
    
    logger.info(f"[SHUTDOWN] {SERVICE_NAME}已安全关闭")


# 创建FastAPI应用
app = FastAPI(
    title="Message Push Service",
    description="""
    SSE消息推送微服务 - 为整个微服务架构提供统一的实时消息推送能力
    
    ## 核心功能
    
    ### 🚀 实时消息推送
    - **SSE连接**: 支持Server-Sent Events长连接
    - **多频道订阅**: 基于频道的消息分发
    - **用户专用连接**: 基于用户ID的消息推送
    - **任务进度推送**: 实时任务进度和状态更新
    
    ### 📡 消息类型支持
    - **进度消息**: 任务处理进度（0-100%）
    - **状态变更**: 任务状态变化通知
    - **错误通知**: 异常和错误信息推送
    - **成功通知**: 任务完成结果推送
    - **自定义消息**: 业务特定消息类型
    
    ### 🔧 高级特性
    - **消息持久化**: 基于Redis的消息队列
    - **连接管理**: 高效的客户端连接池管理
    - **负载均衡**: 支持多实例部署
    - **故障转移**: 自动重连和故障恢复
    
    ### 🛡️ 可靠性保障
    - **心跳机制**: 自动检测连接状态
    - **消息确认**: 确保消息送达
    - **重试机制**: 失败消息自动重试
    - **监控告警**: 完整的监控指标
    
    ## 连接端点
    
    - `/sse/stream` - 通用SSE连接
    - `/sse/user/{user_id}` - 用户专用连接
    - `/sse/service/{service_name}` - 服务专用连接
    - `/sse/task/{task_id}` - 任务专用连接
    
    ## 使用示例
    
    ### JavaScript客户端
    ```javascript
    // 建立用户连接
    const eventSource = new EventSource('/sse/user/123');
    
    // 监听进度消息
    eventSource.addEventListener('progress', function(event) {
        const data = JSON.parse(event.data);
        console.log('Progress:', data.data.progress + '%');
    });
    
    // 监听错误消息
    eventSource.addEventListener('error', function(event) {
        const data = JSON.parse(event.data);
        console.error('Error:', data.data.error_message);
    });
    ```
    
    ### 发送消息（其他服务）
    ```python
    import httpx
    
    # 发送进度消息
    async def send_progress(user_id: str, task_id: str, progress: int):
        message = {
            "type": "progress",
            "service": "knowledge-service", 
            "source": "document_processing",
            "target": {"user_id": user_id, "task_id": task_id},
            "data": {
                "task_id": task_id,
                "progress": progress,
                "stage": "processing",
                "message": f"处理进度: {progress}%"
            }
        }
        
        async with httpx.AsyncClient() as client:
            await client.post(
                "http://localhost:8089/sse/api/v1/messages/send",
                json=message
            )
    ```
    """,
    version=SERVICE_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173", 
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)


# 请求中间件
@app.middleware("http")
async def request_middleware(request: Request, call_next):
    """请求中间件：日志记录和性能监控"""
    start_time = time.time()
    request_id = f"req_{int(start_time * 1000)}"
    
    # 记录请求开始
    logger.info(f"[REQUEST] [{request_id}] {request.method} {request.url.path}")
    
    try:
        response = await call_next(request)
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
            "service": SERVICE_NAME,
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
            "service": SERVICE_NAME,
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
            "service": SERVICE_NAME,
            "path": str(request.url),
            "timestamp": time.time()
        }
    )


# 根端点
@app.get("/", tags=["系统"])
async def root():
    """根端点"""
    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "status": "running",
        "port": SERVICE_PORT,
        "docs_url": "/docs",
        "description": "SSE消息推送微服务",
        "features": [
            "Server-Sent Events (SSE)",
            "实时消息推送",
            "多频道订阅",
            "连接池管理",
            "Redis消息队列",
            "负载均衡支持"
        ],
        "endpoints": {
            "sse_stream": "/sse/stream",
            "user_stream": "/sse/user/{user_id}",
            "service_stream": "/sse/service/{service_name}",
            "task_stream": "/sse/task/{task_id}",
            "send_message": "/sse/api/v1/messages/send",
            "broadcast": "/sse/api/v1/messages/broadcast"
        }
    }


# 服务注册到网关
async def register_to_gateway():
    """注册服务到API网关"""
    try:
        import httpx
        
        registration_data = {
            "service_name": SERVICE_NAME,
            "service_port": SERVICE_PORT,
            "service_url": f"http://localhost:{SERVICE_PORT}",
            "health_check_url": f"http://localhost:{SERVICE_PORT}/sse/health",
            "service_type": "message_push",
            "version": SERVICE_VERSION,
            "endpoints": [
                {"path": "/sse/*", "methods": ["GET", "POST"]},
                {"path": "/sse/api/v1/*", "methods": ["GET", "POST", "PUT", "DELETE"]}
            ]
        }
        
        # 尝试注册到网关
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                "http://localhost:8080/api/gateway/services/register",
                json=registration_data
            )
            
            if response.status_code == 200:
                logger.info("[GATEWAY] 服务注册成功")
            else:
                logger.warning(f"[GATEWAY] 服务注册失败: {response.status_code}")
                
    except Exception as e:
        logger.warning(f"[GATEWAY] 无法连接到网关服务: {e}")


# 注册路由
app.include_router(sse_router)


def print_startup_banner():
    """打印服务启动横幅"""
    banner = f"""
{'='*80}
    Message Push Service - SSE消息推送微服务
{'='*80}
    服务版本: v{SERVICE_VERSION}
    运行端口: {SERVICE_PORT}
    环境配置: development
    
    核心功能:
    • Server-Sent Events (SSE) 长连接
    • 实时消息推送和广播
    • 多频道订阅和路由
    • Redis消息队列支持
    • 连接池和负载均衡
    
    连接端点:
    • 通用连接: /sse/stream
    • 用户连接: /sse/user/{{user_id}}
    • 服务连接: /sse/service/{{service_name}}
    • 任务连接: /sse/task/{{task_id}}
    
    管理接口:
    • 健康检查: /sse/health
    • 发送消息: /sse/api/v1/messages/send
    • 广播消息: /sse/api/v1/messages/broadcast
    • 连接管理: /sse/api/v1/connections
{'='*80}
"""
    print(banner)


if __name__ == "__main__":
    # 打印启动横幅
    print_startup_banner()
    
    # 日志启动信息
    logger.info(f"[STARTUP] 正在启动{SERVICE_NAME}...")
    logger.info(f"[CONFIG] 服务端口: {SERVICE_PORT}")
    
    try:
        logger.info("[STARTUP] 服务启动中...")
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=SERVICE_PORT,
            log_level="info",
            access_log=True,
            use_colors=True,
            reload=True,
            reload_dirs=["app"],
            reload_excludes=["*.log", "*.tmp", "__pycache__"]
        )
    except KeyboardInterrupt:
        logger.info(f"[SHUTDOWN] {SERVICE_NAME}已被用户停止")
        print(f"\n{'='*80}")
        print(f"    {SERVICE_NAME}已安全关闭")
        print(f"{'='*80}")
    except Exception as e:
        logger.error(f"[ERROR] {SERVICE_NAME}启动失败: {e}")
        print(f"\n错误: 服务启动失败 - {e}")
        sys.exit(1)