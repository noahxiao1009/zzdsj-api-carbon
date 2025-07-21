#!/bin/bash

# Kaiban Service 启动脚本

echo "🚀 启动 Kaiban Service..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 检查依赖
echo "📦 检查依赖..."
if ! command -v python &> /dev/null; then
    echo "❌ Python 未安装"
    exit 1
fi

if ! python -c "import fastapi" &> /dev/null; then
    echo "❌ FastAPI 未安装，请运行: pip install -r requirements.txt"
    exit 1
fi

# 创建日志目录
mkdir -p logs

# 检测端口是否被占用
if lsof -Pi :8003 -sTCP:LISTEN -t >/dev/null; then
    echo "⚠️  端口 8003 被占用，正在停止现有服务..."
    pkill -f "uvicorn.*kaiban" || true
    sleep 2
fi

# 启动服务
echo "▶️  启动 Kaiban Service..."
python -m uvicorn main_simple:app --host 0.0.0.0 --port 8003 --reload &

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 3

# 检查服务状态
if curl -s http://localhost:8003/health > /dev/null 2>&1; then
    echo "✅ Kaiban Service 启动成功！"
    echo ""
    echo "📍 服务访问地址："
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🌐 API文档:     http://localhost:8003/docs"
    echo "📋 看板界面:     http://localhost:8003/frontend/board"
    echo "ℹ️  服务信息:     http://localhost:8003/info"
    echo "✅ 健康检查:     http://localhost:8003/health"
    echo ""
    echo "🔗 API端点："
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📊 工作流管理:   http://localhost:8003/api/v1/workflows"
    echo "📋 看板管理:     http://localhost:8003/api/v1/boards"
    echo "📝 任务管理:     http://localhost:8003/api/v1/tasks"
    echo "⚡ 事件系统:     http://localhost:8003/api/v1/events"
    echo ""
    echo "🛠️  管理命令："
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "停止服务:       ./stop.sh"
    echo "查看日志:       tail -f logs/kaiban-service.log"
    echo "重启服务:       ./restart.sh"
    echo ""
    echo "💡 提示: 使用 Ctrl+C 停止此脚本但保持服务运行"
else
    echo "❌ 服务启动失败，请检查日志: logs/kaiban-service.log"
    exit 1
fi 