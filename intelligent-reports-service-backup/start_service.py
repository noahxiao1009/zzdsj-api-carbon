#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能报告服务启动脚本
用于测试和开发环境的服务启动
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 设置环境变量（开发环境默认值）
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/carbon_db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
os.environ.setdefault("MODEL_SERVICE_URL", "http://localhost:8088")
os.environ.setdefault("JWT_SECRET_KEY", "your-secret-key-here")
os.environ.setdefault("WORKSPACE_PATH", str(project_root / "workspace"))
os.environ.setdefault("PORT", "8000")

# API密钥配置（开发环境，实际部署时应该从安全存储获取）
os.environ.setdefault("API_KEY", "your-api-key-here")
os.environ.setdefault("API_BASE_URL", "https://api.openai.com/v1")
os.environ.setdefault("MODEL_NAME", "gpt-3.5-turbo")
os.environ.setdefault("TAVILY_API_KEY", "your-tavily-api-key-here")

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('intelligent-reports-service.log')
    ]
)

logger = logging.getLogger(__name__)


async def check_dependencies():
    """检查服务依赖"""
    logger.info("检查服务依赖...")
    
    dependencies = [
        "postgresql",
        "redis", 
        "model-service",
        "database-service",
        "gateway-service"
    ]
    
    for dep in dependencies:
        logger.info(f"检查依赖: {dep}")
        # 这里可以添加实际的依赖检查逻辑
    
    logger.info("依赖检查完成")


async def setup_workspace():
    """设置工作空间"""
    workspace_path = Path(os.environ.get("WORKSPACE_PATH", "./workspace"))
    workspace_path.mkdir(parents=True, exist_ok=True)
    
    # 创建子目录
    subdirs = ["sessions", "templates", "temp", "logs"]
    for subdir in subdirs:
        (workspace_path / subdir).mkdir(exist_ok=True)
    
    logger.info(f"工作空间设置完成: {workspace_path}")


async def run_database_migration():
    """运行数据库迁移"""
    try:
        logger.info("运行数据库迁移...")
        
        from app.migrations.create_tables import run_migration
        success = await run_migration()
        
        if success:
            logger.info("数据库迁移成功")
        else:
            logger.error("数据库迁移失败")
            return False
            
    except Exception as e:
        logger.error(f"数据库迁移异常: {e}", exc_info=True)
        return False
    
    return True


async def test_model_integration():
    """测试模型集成"""
    try:
        logger.info("测试模型集成...")
        
        from llm import init_models, get_plan_llm
        
        # 初始化模型
        await init_models()
        
        # 测试模型调用
        plan_llm = get_plan_llm()
        if plan_llm:
            logger.info("模型集成测试成功")
        else:
            logger.warning("模型集成测试失败，将使用默认配置")
            
    except Exception as e:
        logger.error(f"模型集成测试异常: {e}", exc_info=True)


async def test_service_communication():
    """测试微服务通信"""
    try:
        logger.info("测试微服务通信...")
        
        from shared.service_client import call_service, CallMethod
        
        # 测试数据库服务
        try:
            result = await call_service(
                service_name="database-service",
                method=CallMethod.GET,
                path="/health"
            )
            logger.info("数据库服务通信正常")
        except Exception as e:
            logger.warning(f"数据库服务通信失败: {e}")
        
        # 测试模型服务
        try:
            result = await call_service(
                service_name="model-service", 
                method=CallMethod.GET,
                path="/health"
            )
            logger.info("模型服务通信正常")
        except Exception as e:
            logger.warning(f"模型服务通信失败: {e}")
            
    except Exception as e:
        logger.error(f"微服务通信测试异常: {e}", exc_info=True)


def print_service_info():
    """打印服务信息"""
    print("\n" + "="*60)
    print("智能报告服务启动信息")
    print("="*60)
    print(f"端口: {os.environ.get('PORT', '8000')}")
    print(f"工作空间: {os.environ.get('WORKSPACE_PATH', './workspace')}")
    print(f"数据库: {os.environ.get('DATABASE_URL', 'N/A')}")
    print(f"Redis: {os.environ.get('REDIS_URL', 'N/A')}")
    print(f"模型服务: {os.environ.get('MODEL_SERVICE_URL', 'N/A')}")
    print("\nAPI端点:")
    print("- 健康检查: GET /health")
    print("- 生成报告: POST /api/reports/generate")
    print("- 报告状态: GET /api/reports/status/{session_id}")
    print("- 获取文件: GET /api/files/{session_id}/{filename}")
    print("- WebSocket: WS /ws/{session_id}")
    print("- 模型状态: GET /api/models/status")
    print("- 服务状态: GET /api/services/status")
    print("="*60)


async def main():
    """主启动函数"""
    try:
        logger.info("开始启动智能报告服务...")
        
        # 1. 检查依赖
        await check_dependencies()
        
        # 2. 设置工作空间
        await setup_workspace()
        
        # 3. 运行数据库迁移
        migration_success = await run_database_migration()
        if not migration_success:
            logger.error("数据库迁移失败，服务可能无法正常运行")
        
        # 4. 测试模型集成
        await test_model_integration()
        
        # 5. 测试微服务通信
        await test_service_communication()
        
        # 6. 打印服务信息
        print_service_info()
        
        # 7. 启动FastAPI服务
        logger.info("启动FastAPI服务...")
        
        import uvicorn
        from main import app
        
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=int(os.environ.get("PORT", "8000")),
            log_level="info",
            access_log=True,
            reload=False  # 生产环境设置为False
        )
        
    except KeyboardInterrupt:
        logger.info("服务被用户中断")
    except Exception as e:
        logger.error(f"服务启动失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())