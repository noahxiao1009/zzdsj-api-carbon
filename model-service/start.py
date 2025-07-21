#!/usr/bin/env python3
"""
模型服务启动脚本
支持开发和生产环境的启动配置
"""

import os
import sys
import argparse
import asyncio
import logging
from pathlib import Path
import yaml
import uvicorn

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from main import create_app


def load_config(config_path: str = "config.yaml") -> dict:
    """加载配置文件"""
    config_file = Path(config_path)
    
    if not config_file.exists():
        print(f"配置文件不存在: {config_path}")
        return {}
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        print(f"配置文件加载成功: {config_path}")
        return config
    except Exception as e:
        print(f"配置文件加载失败: {e}")
        return {}


def setup_logging(config: dict):
    """设置日志配置"""
    log_config = config.get("logging", {})
    
    # 创建日志目录
    log_file = log_config.get("file", "logs/model-service.log")
    log_dir = Path(log_file).parent
    log_dir.mkdir(exist_ok=True)
    
    # 配置日志
    logging.basicConfig(
        level=getattr(logging, log_config.get("level", "INFO")),
        format=log_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    print(f"日志配置完成，日志文件: {log_file}")


def setup_environment(config: dict):
    """设置环境变量"""
    # 设置服务配置环境变量
    service_config = config.get("service", {})
    os.environ["SERVICE_NAME"] = service_config.get("name", "model-service")
    os.environ["SERVICE_VERSION"] = service_config.get("version", "1.0.0")
    
    # 设置数据库配置
    db_config = config.get("database", {})
    if db_config.get("url"):
        os.environ["DATABASE_URL"] = db_config["url"]
    
    # 设置Redis配置
    redis_config = config.get("redis", {})
    if redis_config.get("url"):
        os.environ["REDIS_URL"] = redis_config["url"]
    
    print("环境变量设置完成")


async def register_with_gateway(config: dict):
    """向网关注册服务"""
    try:
        integration_config = config.get("integration", {})
        gateway_config = integration_config.get("gateway", {})
        
        if not gateway_config.get("register_on_startup", False):
            return
        
        from app.services.service_integration import ModelServiceIntegration
        
        service_info = {
            "url": f"http://localhost:{config.get('service', {}).get('port', 8003)}",
            "version": config.get('service', {}).get('version', '1.0.0'),
            "supported_providers": [
                "zhipu", "baidu", "iflytek", "alibaba", "tencent", 
                "moonshot", "deepseek", "ollama", "vllm"
            ]
        }
        
        async with ModelServiceIntegration() as integration:
            success = await integration.register_with_gateway(service_info)
            if success:
                print("✅ 服务注册成功")
            else:
                print("⚠️ 服务注册失败")
                
    except Exception as e:
        print(f"⚠️ 服务注册异常: {e}")


def create_directories():
    """创建必要的目录"""
    directories = [
        "logs",
        "data",
        "cache",
        "temp"
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
    
    print("目录结构创建完成")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="模型服务启动脚本")
    parser.add_argument(
        "--config", 
        default="config.yaml", 
        help="配置文件路径"
    )
    parser.add_argument(
        "--host", 
        default=None, 
        help="服务主机地址"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=None, 
        help="服务端口"
    )
    parser.add_argument(
        "--workers", 
        type=int, 
        default=1, 
        help="工作进程数"
    )
    parser.add_argument(
        "--reload", 
        action="store_true", 
        help="启用自动重载（开发模式）"
    )
    parser.add_argument(
        "--debug", 
        action="store_true", 
        help="启用调试模式"
    )
    parser.add_argument(
        "--log-level", 
        default=None, 
        choices=["DEBUG", "INFO", "WARNING", "ERROR"], 
        help="日志级别"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🚀 模型服务启动中...")
    print("=" * 60)
    
    # 加载配置
    config = load_config(args.config)
    service_config = config.get("service", {})
    
    # 创建目录
    create_directories()
    
    # 设置日志
    setup_logging(config)
    
    # 设置环境变量
    setup_environment(config)
    
    # 确定启动参数
    host = args.host or service_config.get("host", "0.0.0.0")
    port = args.port or service_config.get("port", 8003)
    reload = args.reload or service_config.get("debug", False)
    log_level = args.log_level or config.get("logging", {}).get("level", "info").lower()
    
    print(f"服务配置:")
    print(f"  - 主机: {host}")
    print(f"  - 端口: {port}")
    print(f"  - 工作进程: {args.workers}")
    print(f"  - 自动重载: {reload}")
    print(f"  - 日志级别: {log_level}")
    print(f"  - 配置文件: {args.config}")
    
    # 创建应用
    app = create_app()
    
    # 启动后注册服务
    async def startup_tasks():
        await register_with_gateway(config)
    
    # 添加启动事件
    @app.on_event("startup")
    async def startup_event():
        await startup_tasks()
    
    print("\n🎯 服务启动完成，访问地址:")
    print(f"  - API文档: http://{host}:{port}/docs")
    print(f"  - ReDoc文档: http://{host}:{port}/redoc")
    print(f"  - 健康检查: http://{host}:{port}/health")
    print(f"  - 服务信息: http://{host}:{port}/")
    print("=" * 60)
    
    # 启动服务
    try:
        uvicorn.run(
            app,
            host=host,
            port=port,
            workers=args.workers if not reload else 1,
            reload=reload,
            log_level=log_level,
            access_log=True,
            use_colors=True
        )
    except KeyboardInterrupt:
        print("\n👋 服务正在关闭...")
    except Exception as e:
        print(f"\n❌ 服务启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()