#!/bin/bash

# 数据库管理微服务启动脚本

set -e

# 获取脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "数据库管理微服务启动脚本"
echo "项目目录: $PROJECT_DIR"

# 进入项目目录
cd "$PROJECT_DIR"

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3 命令"
    exit 1
fi

# 检查环境配置文件
ENV_FILE="${1:-config/development.env}"
if [ ! -f "$ENV_FILE" ]; then
    echo "错误: 环境配置文件不存在: $ENV_FILE"
    echo "使用方法: $0 [环境配置文件路径]"
    exit 1
fi

echo "使用环境配置: $ENV_FILE"

# 导出环境变量
set -a
source "$ENV_FILE"
set +a

# 检查依赖
echo "检查依赖..."
if [ ! -f "requirements.txt" ]; then
    echo "错误: requirements.txt 文件不存在"
    exit 1
fi

# 安装依赖（如果需要）
if [ "$INSTALL_DEPS" = "true" ]; then
    echo "安装依赖..."
    pip install -r requirements.txt
fi

# 检查必要的环境变量
required_vars=("DB_SERVICE_PORT")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "错误: 必需的环境变量 $var 未设置"
        exit 1
    fi
done

echo "启动数据库管理微服务..."
echo "服务端口: $DB_SERVICE_PORT"
echo "调试模式: ${DEBUG:-false}"

# 启动服务
exec python main.py 