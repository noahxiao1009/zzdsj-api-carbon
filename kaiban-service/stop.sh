#!/bin/bash

# Kaiban Service 停止脚本

echo "🛑 停止 Kaiban Service..."

# 查找并停止uvicorn进程
PIDS=$(pgrep -f "uvicorn.*kaiban" 2>/dev/null)

if [ -z "$PIDS" ]; then
    echo "ℹ️  没有找到运行中的 Kaiban Service"
else
    echo "📝 找到进程: $PIDS"
    for PID in $PIDS; do
        echo "⏹️  停止进程 $PID..."
        kill $PID
    done
    
    # 等待进程停止
    sleep 2
    
    # 检查是否还有残留进程
    REMAINING=$(pgrep -f "uvicorn.*kaiban" 2>/dev/null)
    if [ ! -z "$REMAINING" ]; then
        echo "⚠️  强制停止残留进程..."
        pkill -9 -f "uvicorn.*kaiban"
    fi
    
    echo "✅ Kaiban Service 已停止"
fi

# 检查端口是否释放
if ! lsof -Pi :8003 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "✅ 端口 8003 已释放"
else
    echo "⚠️  端口 8003 仍被占用"
fi 