#!/bin/bash

# 微服务快速启动脚本
# 提供快速启动核心服务或所有服务的功能

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}========================================================================${NC}"
echo -e "${BLUE}    NextAgent - 微服务快速启动${NC}"
echo -e "${BLUE}========================================================================${NC}"

# 检查PM2
if ! command -v pm2 &> /dev/null; then
    echo -e "${YELLOW}PM2 未安装，正在安装...${NC}"
    npm install -g pm2
fi

# 创建日志目录
echo -e "${GREEN}[INFO]${NC} 创建日志目录..."
for service in gateway-service agent-service knowledge-service chat-service database-service knowledge-graph-service model-service mcp-service tools-service intelligent-reports-service kaiban-service messaging-service scheduler-service; do
    if [ -d "$service" ]; then
        mkdir -p "$service/logs"
    fi
done

case "$1" in
    "core")
        echo -e "${GREEN}[INFO]${NC} 启动核心服务（网关、知识库、智能体、模型、数据库）..."
        ./pm2-manager.sh start:core development
        ;;
    "all")
        echo -e "${GREEN}[INFO]${NC} 启动所有微服务..."
        ./pm2-manager.sh start:all development
        ;;
    "global")
        echo -e "${GREEN}[INFO]${NC} 使用全局配置启动所有服务..."
        pm2 start ecosystem.all.config.js
        pm2 status
        ;;
    "stop")
        echo -e "${YELLOW}[INFO]${NC} 停止所有服务..."
        ./pm2-manager.sh stop:all
        ;;
    "status")
        echo -e "${GREEN}[INFO]${NC} 显示服务状态..."
        ./pm2-manager.sh status
        ;;
    "interactive"|"i"|"")
        echo -e "${GREEN}[INFO]${NC} 启动交互式服务管理界面..."
        ./pm2-manager.sh interactive development
        ;;
    *)
        echo "用法: $0 [interactive|core|all|global|stop|status]"
        echo "  interactive - 交互式服务管理界面（默认，推荐）"
        echo "  i           - 交互式服务管理界面（简写）"
        echo "  core        - 启动核心服务"
        echo "  all         - 启动所有服务"  
        echo "  global      - 使用全局配置启动"
        echo "  stop        - 停止所有服务"
        echo "  status      - 显示状态"
        ;;
esac