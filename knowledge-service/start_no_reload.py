#!/usr/bin/env python3
"""
知识库服务启动脚本 - 无热重载版本
用于生产环境或需要禁用热重载的场景
"""

import os
import sys
from pathlib import Path

# 设置环境变量禁用热重载
os.environ["ENABLE_RELOAD"] = "false"
os.environ["ENVIRONMENT"] = "production"

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 导入并运行主应用
if __name__ == "__main__":
    from main import app, settings, logger
    import uvicorn
    
    logger.info("🚀 Starting Knowledge Service (Production Mode - No Reload)")
    logger.info(f"   Environment: {settings.environment}")
    logger.info(f"   Enable Reload: {getattr(settings, 'enable_reload', False)}")
    
    try:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=settings.port,
            log_level=settings.log_level.lower(),
            reload=False,  # 强制禁用热重载
            access_log=True,
            use_colors=True
        )
    except KeyboardInterrupt:
        logger.info("👋 Knowledge Service stopped by user")
    except Exception as e:
        logger.error(f"❌ Failed to start Knowledge Service: {e}")
        sys.exit(1)