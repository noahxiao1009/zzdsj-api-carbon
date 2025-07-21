#!/bin/bash
# 演示环境服务停止脚本
# Stop Script for Demo Environment

echo "🛑 停止ZZDSJ AI智能办公助手演示环境..."
echo "Stopping ZZDSJ AI Office Assistant Demo Environment..."

# 设置基础目录
BASE_DIR="/Users/wxn/Desktop/carbon/zzdsl-api-carbon"
cd "$BASE_DIR"

# 停止服务函数
stop_service() {
    local service_name=$1
    local service_dir="$BASE_DIR/$service_name"
    
    echo "🔻 停止 $service_name..."
    
    if [ -d "$service_dir" ]; then
        cd "$service_dir"
        
        # 检查是否有PID文件
        if [ -f "$service_name.pid" ]; then
            local pid=$(cat "$service_name.pid")
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid"
                echo "✅ $service_name 已停止 (PID: $pid)"
            else
                echo "⚠️ $service_name 进程不存在"
            fi
            rm -f "$service_name.pid"
        else
            echo "⚠️ $service_name 没有PID文件"
        fi
        
        cd "$BASE_DIR"
    fi
}

# 停止CommonGround服务
echo "🔻 停止CommonGround服务..."
cd "$BASE_DIR/CommonGround-main/core"
if [ -f "commonground.pid" ]; then
    local pid=$(cat "commonground.pid")
    if kill -0 "$pid" 2>/dev/null; then
        kill "$pid"
        echo "✅ CommonGround已停止 (PID: $pid)"
    else
        echo "⚠️ CommonGround进程不存在"
    fi
    rm -f "commonground.pid"
else
    echo "⚠️ CommonGround没有PID文件"
fi

cd "$BASE_DIR"

echo ""
echo "📋 停止微服务..."

# 停止各个微服务
stop_service "knowledge-service"
stop_service "agent-service"
stop_service "knowledge-graph-service"
stop_service "intelligent-reports-service"
stop_service "chat-service"

echo ""
echo "🔍 清理残留进程..."

# 清理可能的残留进程
echo "检查端口占用..."
for port in 8000 8081 8082 8083 8087 8090; do
    pid=$(lsof -ti :$port 2>/dev/null)
    if [ ! -z "$pid" ]; then
        echo "发现端口 $port 被进程 $pid 占用，正在清理..."
        kill -9 "$pid" 2>/dev/null
        echo "✅ 已清理端口 $port"
    fi
done

echo ""
echo "🧹 清理日志文件..."

# 可选：清理日志文件 (注释掉以保留日志)
# find "$BASE_DIR" -name "*.log" -type f -delete
# echo "✅ 日志文件已清理"

echo "💡 日志文件已保留，位于各服务目录下"

echo ""
echo "✅ 演示环境已完全停止!"
echo "Demo Environment Stopped!"