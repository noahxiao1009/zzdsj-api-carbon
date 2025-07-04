#!/usr/bin/env python3
"""
网关服务启动脚本

提供开发和生产环境的启动选项
"""

import os
import sys
import subprocess
import argparse
import signal
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def setup_environment():
    """设置环境变量"""
    # 设置默认环境变量
    os.environ.setdefault("APP_ENV", "development")
    os.environ.setdefault("SERVICE_NAME", "gateway-service")
    os.environ.setdefault("SERVICE_IP", "0.0.0.0")
    os.environ.setdefault("SERVICE_PORT", "8080")
    os.environ.setdefault("DEBUG", "True")
    
    # 日志配置
    os.environ.setdefault("LOG_LEVEL", "INFO")
    os.environ.setdefault("LOG_FILE", "gateway_service.log")
    
    print("🔧 环境变量配置完成")

def check_dependencies():
    """检查依赖"""
    try:
        import fastapi
        import uvicorn
        import pydantic
        import jwt
        import redis
        print("✅ 核心依赖检查通过")
        return True
    except ImportError as e:
        print(f"❌ 依赖检查失败: {e}")
        print("请运行: pip install -r requirements.txt")
        return False

def start_development_server(host="0.0.0.0", port=8080, reload=True):
    """启动开发服务器"""
    print(f"🚀 启动开发服务器: {host}:{port}")
    
    cmd = [
        "uvicorn",
        "main:app",
        "--host", host,
        "--port", str(port),
        "--log-level", "info"
    ]
    
    if reload:
        cmd.append("--reload")
    
    try:
        subprocess.run(cmd, cwd=project_root)
    except KeyboardInterrupt:
        print("\n👋 服务已停止")

def start_production_server(host="0.0.0.0", port=8080, workers=4):
    """启动生产服务器"""
    print(f"🚀 启动生产服务器: {host}:{port} (workers: {workers})")
    
    cmd = [
        "uvicorn",
        "main:app",
        "--host", host,
        "--port", str(port),
        "--workers", str(workers),
        "--log-level", "warning",
        "--access-log",
        "--no-server-header"
    ]
    
    try:
        subprocess.run(cmd, cwd=project_root)
    except KeyboardInterrupt:
        print("\n👋 服务已停止")

def main():
    parser = argparse.ArgumentParser(description="网关服务启动器")
    parser.add_argument("--env", choices=["dev", "prod"], default="dev",
                        help="运行环境 (dev/prod)")
    parser.add_argument("--host", default="0.0.0.0",
                        help="绑定主机地址")
    parser.add_argument("--port", type=int, default=8080,
                        help="端口号")
    parser.add_argument("--workers", type=int, default=4,
                        help="生产环境工作进程数")
    parser.add_argument("--no-reload", action="store_true",
                        help="禁用自动重载")
    parser.add_argument("--check", action="store_true",
                        help="仅检查依赖和配置")
    
    args = parser.parse_args()
    
    print("🔍 网关服务启动器")
    print("=" * 50)
    
    # 设置环境
    setup_environment()
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    if args.check:
        print("✅ 检查完成，服务可以启动")
        return
    
    # 更新环境变量
    os.environ["SERVICE_IP"] = args.host
    os.environ["SERVICE_PORT"] = str(args.port)
    
    if args.env == "dev":
        os.environ["APP_ENV"] = "development"
        os.environ["DEBUG"] = "True"
        start_development_server(
            host=args.host,
            port=args.port,
            reload=not args.no_reload
        )
    else:
        os.environ["APP_ENV"] = "production"
        os.environ["DEBUG"] = "False"
        start_production_server(
            host=args.host,
            port=args.port,
            workers=args.workers
        )

if __name__ == "__main__":
    main() 