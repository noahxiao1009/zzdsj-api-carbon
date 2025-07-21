#!/usr/bin/env python3
"""
智能报告服务 - 基于Co-Sight的微服务实现
提供智能报告生成功能，支持通过iframe嵌入到前端系统中
"""

import os
import sys
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 设置工作目录
os.chdir(project_root)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 微服务配置
SERVICE_NAME = "intelligent-reports-service"
SERVICE_PORT = 7788
SERVICE_HOST = "0.0.0.0"

# 创建FastAPI应用
app = FastAPI(
    title="智能报告服务",
    description="基于Co-Sight的智能报告生成微服务",
    version="1.0.0"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境中应该限制为特定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "service": SERVICE_NAME,
        "port": SERVICE_PORT
    }

@app.get("/api/v1/reports/health")
async def reports_health():
    """报告服务健康检查"""
    return {
        "status": "ready",
        "service": "intelligent-reports",
        "version": "1.0.0"
    }

@app.get("/cosight-debug")
async def cosight_debug():
    """调试Co-Sight挂载"""
    return {
        "status": "debug",
        "message": "Co-Sight debug endpoint"
    }

# 导入Co-Sight的原始应用
try:
    # 设置环境变量
    os.environ.setdefault("ENVIRONMENT", "development")
    
    # 导入NextReport应用
    from cosight_server.deep_research.main import app as cosight_app
    
    # 将NextReport应用挂载到根路径，确保API正常工作
    app.mount("/", cosight_app)
    logger.info("NextReport应用已成功挂载到根路径")
    
except Exception as e:
    logger.error(f"加载NextReport应用失败: {e}")
    
    @app.get("/cosight/{path:path}")
    async def cosight_fallback(path: str):
        return {"error": "NextReport服务暂时不可用", "details": str(e)}

def register_with_gateway():
    """向网关注册服务"""
    try:
        import httpx
        gateway_url = os.getenv("GATEWAY_URL", "http://localhost:8080")
        
        registration_data = {
            "service_name": SERVICE_NAME,
            "host": "localhost",
            "port": SERVICE_PORT,
            "health_check_url": f"http://localhost:{SERVICE_PORT}/health",
            "tags": ["reports", "intelligence", "cosight"]
        }
        
        response = httpx.post(
            f"{gateway_url}/api/gateway/register",
            json=registration_data,
            timeout=5.0
        )
        
        if response.status_code == 200:
            logger.info(f"服务已成功注册到网关: {gateway_url}")
        else:
            logger.warning(f"服务注册失败: {response.status_code}")
            
    except Exception as e:
        logger.warning(f"网关注册失败: {e}")

@app.on_event("startup")
async def startup_event():
    """服务启动事件"""
    logger.info(f"智能报告服务启动: {SERVICE_NAME}")
    logger.info(f"服务地址: http://{SERVICE_HOST}:{SERVICE_PORT}")
    logger.info(f"Co-Sight界面: http://{SERVICE_HOST}:{SERVICE_PORT}/cosight/")
    
    # 初始化数据库
    try:
        from app.database.sqlite_db import init_db
        await init_db()
        logger.info("SQLite数据库初始化完成")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
    
    # 向网关注册
    register_with_gateway()

@app.on_event("shutdown")
async def shutdown_event():
    """服务关闭事件"""
    logger.info(f"智能报告服务关闭: {SERVICE_NAME}")

if __name__ == "__main__":
    logger.info("启动智能报告服务...")
    logger.info(f"访问地址: http://localhost:{SERVICE_PORT}/")
    
    uvicorn.run(
        app,
        host=SERVICE_HOST,
        port=SERVICE_PORT,
        log_level="info"
    )