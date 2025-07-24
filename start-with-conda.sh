#!/bin/bash

# 使用Conda环境启动微服务的便捷脚本

# 默认conda环境名（可以修改）
DEFAULT_CONDA_ENV="base"

# 从命令行参数获取环境名，如果没有则使用默认值
CONDA_ENV=${1:-$DEFAULT_CONDA_ENV}

echo "正在使用Conda环境: $CONDA_ENV"

# 检查conda是否可用
if ! command -v conda &> /dev/null; then
    echo "错误: 未找到conda命令，请确保已安装Anaconda/Miniconda"
    exit 1
fi

# 检查环境是否存在
if ! conda info --envs | grep -q "^$CONDA_ENV "; then
    echo "错误: Conda环境 '$CONDA_ENV' 不存在"
    echo "可用的环境："
    conda info --envs
    exit 1
fi

# 获取conda环境的Python路径
CONDA_PREFIX=$(conda info --envs | grep "^$CONDA_ENV " | awk '{print $NF}')
PYTHON_PATH="$CONDA_PREFIX/bin/python"

echo "Python解释器路径: $PYTHON_PATH"

# 验证Python路径是否存在
if [ ! -f "$PYTHON_PATH" ]; then
    echo "错误: Python解释器不存在: $PYTHON_PATH"
    exit 1
fi

# 设置环境变量并启动服务
export PYTHON_INTERPRETER="$PYTHON_PATH"

# 根据参数决定启动哪些服务
case "${2:-interactive}" in
    "core")
        echo "启动核心服务..."
        ./pm2-manager.sh start:core
        ;;
    "all")
        echo "启动所有服务..."
        ./pm2-manager.sh start:all
        ;;
    "interactive"|"")
        echo "启动交互式管理界面..."
        ./pm2-manager.sh interactive
        ;;
    *)
        echo "启动指定服务: $2"
        ./pm2-manager.sh start "$2"
        ;;
esac