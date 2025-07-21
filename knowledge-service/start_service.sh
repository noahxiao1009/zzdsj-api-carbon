#!/bin/bash

# 知识库服务启动脚本
echo "🚀 启动知识库服务..."

# 检查端口是否被占用
if lsof -Pi :8082 -sTCP:LISTEN -t >/dev/null ; then
    echo "⚠️  端口 8082 已被占用，正在停止现有进程..."
    lsof -ti :8082 | xargs kill -9
    sleep 2
fi

# 切换到项目目录
cd "$(dirname "$0")"

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装"
    exit 1
fi

# 检查依赖
echo "📦 检查依赖..."
python3 -c "import fastapi, uvicorn; print('✅ 基础依赖已安装')" || {
    echo "❌ 缺少必要依赖，请运行: pip install -r requirements.txt"
    exit 1
}

# 后台启动服务
echo "🎯 在后台启动知识库服务..."
nohup python3 simple_main.py > knowledge_service.log 2>&1 &
PID=$!

echo "📝 服务 PID: $PID"
echo "📄 日志文件: knowledge_service.log"

# 等待服务启动
echo "⏱️  等待服务启动..."
sleep 3

# 检查服务状态
if kill -0 $PID 2>/dev/null; then
    echo "✅ 知识库服务启动成功！"
    echo "🌐 服务地址: http://localhost:8082"
    echo "📚 API文档: http://localhost:8082/docs"
    echo "🔍 健康检查: curl http://localhost:8082/health"
    echo ""
    echo "🛑 停止服务命令: kill $PID"
    echo "📋 查看日志命令: tail -f knowledge_service.log"
else
    echo "❌ 服务启动失败，请检查日志文件"
    exit 1
fi
