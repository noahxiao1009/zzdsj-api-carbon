#!/usr/bin/env python3
"""
智能报告服务启动脚本
"""

import os
import sys
import subprocess
import time
import signal
from pathlib import Path

def setup_environment():
    """设置环境变量"""
    # 添加项目根目录到Python路径
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))
    
    # 设置工作目录
    os.chdir(project_root)
    
    # 检查.env文件
    env_file = project_root / ".env"
    if not env_file.exists():
        print("警告: .env文件不存在，将使用默认配置")
        print("请参考README.md创建.env文件以配置LLM和搜索引擎")
    
    # 创建必要的目录
    directories = ["work_space", "upload_files", "logs"]
    for directory in directories:
        dir_path = project_root / directory
        dir_path.mkdir(exist_ok=True)
        print(f"确保目录存在: {dir_path}")

def check_dependencies():
    """检查依赖"""
    try:
        import fastapi
        import uvicorn
        print("✓ 基础依赖检查通过")
        return True
    except ImportError as e:
        print(f"✗ 依赖检查失败: {e}")
        print("请运行: pip install -r requirements.txt")
        return False

def start_service():
    """启动服务"""
    print("启动智能报告服务...")
    print("服务将在 http://localhost:7788 启动")
    print("Co-Sight界面: http://localhost:7788/cosight/")
    print("按 Ctrl+C 停止服务")
    
    try:
        # 启动服务
        process = subprocess.Popen([
            sys.executable, "main.py"
        ])
        
        # 等待进程结束
        process.wait()
        
    except KeyboardInterrupt:
        print("\n正在停止服务...")
        process.terminate()
        time.sleep(2)
        if process.poll() is None:
            process.kill()
        print("服务已停止")

def main():
    """主函数"""
    print("=== 智能报告服务启动器 ===")
    
    # 设置环境
    setup_environment()
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 启动服务
    start_service()

if __name__ == "__main__":
    main()