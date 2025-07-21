#!/bin/bash

# Kaiban Service 重启脚本

echo "🔄 重启 Kaiban Service..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 先停止服务
./stop.sh

echo ""
echo "⏳ 等待 2 秒后重新启动..."
sleep 2

# 再启动服务  
./start.sh 