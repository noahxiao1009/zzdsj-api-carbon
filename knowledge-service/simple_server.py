#!/usr/bin/env python3
"""
简化版知识库服务器 - 仅用于测试快速API
跳过复杂的初始化，专注于快速知识库API测试
"""

import sys
import time
import logging
from pathlib import Path
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 配置简单日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 创建简化的FastAPI应用
app = FastAPI(
    title="Knowledge Service - Fast API Test",
    description="简化版知识库服务，专门测试快速API性能",
    version="test-1.0.0"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# 请求中间件
@app.middleware("http")
async def request_middleware(request: Request, call_next):
    """简化的请求中间件"""
    start_time = time.time()
    request_id = f"req_{int(start_time * 1000)}"
    
    logger.info(f"[REQUEST] [{request_id}] {request.method} {request.url.path}")
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        logger.info(f"[RESPONSE] [{request_id}] 状态码: {response.status_code}, 耗时: {process_time:.3f}s")
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(process_time)
        
        return response
        
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"[ERROR] [{request_id}] 请求处理异常: {e}, 耗时: {process_time:.3f}s")
        raise

# 健康检查
@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "knowledge-service-fast-test",
        "timestamp": time.time()
    }

@app.get("/")
async def root():
    """根端点"""
    return {
        "message": "Knowledge Service - Fast API Test",
        "service": "knowledge-service-fast-test",
        "version": "test-1.0.0"
    }

# 注册快速知识库路由
from app.api.fast_knowledge_routes import router as fast_knowledge_router
app.include_router(fast_knowledge_router, prefix="/api/v1/fast")

# 注册前端专用路由
from app.api.frontend_routes import router as frontend_router
app.include_router(frontend_router, prefix="/api")

# 也注册到标准路径用于比较
app.include_router(fast_knowledge_router, prefix="/api/v1", tags=["知识库管理 - 标准路径"])

if __name__ == "__main__":
    print("=" * 60)
    print("Knowledge Service - Fast API 测试服务器")
    print("=" * 60)
    print("端口: 8083")
    print("API文档: http://localhost:8083/docs")
    print("快速API: http://localhost:8083/api/v1/fast/knowledge-bases/")
    print("标准API: http://localhost:8083/api/v1/knowledge-bases/")
    print("=" * 60)
    
    logger.info("启动快速API测试服务器...")
    
    try:
        uvicorn.run(
            "simple_server:app",
            host="0.0.0.0",
            port=8083,
            log_level="info",
            reload=False
        )
    except KeyboardInterrupt:
        logger.info("服务器已被用户停止")
        print("\n服务器已安全关闭")
    except Exception as e:
        logger.error(f"服务器启动失败: {e}")
        sys.exit(1)