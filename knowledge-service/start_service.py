#!/usr/bin/env python3
"""
知识库服务启动脚本
禁用ffmpeg/pydub相关警告
"""

import warnings
import os
import sys

# 禁用pydub相关的RuntimeWarning
warnings.filterwarnings('ignore', category=RuntimeWarning, module='pydub')

# 设置环境变量禁用音频处理警告
os.environ['PYTHONWARNINGS'] = 'ignore::RuntimeWarning:pydub.utils'

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

if __name__ == "__main__":
    # 导入并启动服务
    try:
        # 先导入必要模块
        import uvicorn
        from main import app, print_startup_banner, settings, logger
        
        # 打印启动横幅
        print_startup_banner()
        
        # 日志启动信息
        logger.info("[STARTUP] 正在启动知识库服务...")
        logger.info(f"[CONFIG] 服务端口: {settings.port}")
        logger.info(f"[CONFIG] 运行环境: {getattr(settings, 'environment', 'development')}")
        
        # 确定是否启用热重载
        enable_reload = (
            getattr(settings, 'environment', 'development') == "development" and 
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
        
        # 启动服务
        uvicorn.run(
            app,  # 直接传递app对象而不是字符串
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
        import traceback
        traceback.print_exc()
        sys.exit(1)