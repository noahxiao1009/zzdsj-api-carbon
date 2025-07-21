#!/bin/bash
# 演示环境快速启动脚本
# Quick Start Script for Demo Environment

echo "🚀 启动ZZDSJ AI智能办公助手演示环境..."
echo "Starting ZZDSJ AI Office Assistant Demo Environment..."

# 设置基础目录
BASE_DIR="/Users/wxn/Desktop/carbon/zzdsl-api-carbon"
cd "$BASE_DIR"

# 启动函数
start_service() {
    local service_name=$1
    local port=$2
    local service_dir="$BASE_DIR/$service_name"
    
    echo "📦 启动 $service_name (端口: $port)..."
    
    if [ -d "$service_dir" ]; then
        cd "$service_dir"
        
        # 检查是否有main.py
        if [ -f "main.py" ]; then
            # 后台启动服务
            nohup python main.py > "$service_name.log" 2>&1 &
            echo "$!" > "$service_name.pid"
            echo "✅ $service_name 已启动 (PID: $(cat $service_name.pid))"
        else
            echo "❌ $service_name 缺少main.py文件"
        fi
        
        cd "$BASE_DIR"
    else
        echo "❌ $service_name 目录不存在"
    fi
    
    sleep 2
}

# 检查端口占用
check_port() {
    local port=$1
    if lsof -i :$port > /dev/null 2>&1; then
        echo "⚠️ 端口 $port 已被占用"
        return 1
    fi
    return 0
}

echo ""
echo "🔍 检查端口占用情况..."

# 核心微服务启动顺序
echo ""
echo "📋 启动核心微服务..."

# 1. 知识库服务
start_service "knowledge-service" 8082

# 2. 智能体服务
start_service "agent-service" 8081

# 3. 知识图谱服务
start_service "knowledge-graph-service" 8087

# 4. 智能报告服务
start_service "intelligent-reports-service" 8090

# 5. 聊天服务
start_service "chat-service" 8083

echo ""
echo "🤖 启动CommonGround多智能体服务..."

# CommonGround服务
cd "$BASE_DIR/CommonGround-main/core"
if [ -f ".env.siliconflow" ]; then
    cp ".env.siliconflow" ".env"
    echo "✅ 已应用硅基流动配置"
fi

echo "📦 启动CommonGround后端 (端口: 8000)..."
nohup python run_server.py --host 0.0.0.0 --port 8000 > "commonground.log" 2>&1 &
echo "$!" > "commonground.pid"
echo "✅ CommonGround已启动 (PID: $(cat commonground.pid))"

cd "$BASE_DIR"

echo ""
echo "⏱️ 等待服务启动完成..."
sleep 10

echo ""
echo "🔍 检查服务状态..."

# 检查服务状态
check_service_status() {
    local service_name=$1
    local port=$2
    local url="http://localhost:$port/health"
    
    echo -n "检查 $service_name ($port): "
    
    if curl -s "$url" > /dev/null 2>&1; then
        echo "✅ 运行正常"
    else
        echo "❌ 无响应"
    fi
}

check_service_status "knowledge-service" 8082
check_service_status "agent-service" 8081
check_service_status "knowledge-graph-service" 8087
check_service_status "chat-service" 8083
check_service_status "CommonGround" 8000

echo ""
echo "📊 服务访问地址:"
echo "  • Knowledge Service: http://localhost:8082"
echo "  • Agent Service: http://localhost:8081" 
echo "  • Knowledge Graph Service: http://localhost:8087"
echo "  • Chat Service: http://localhost:8083"
echo "  • CommonGround: http://localhost:8000"

echo ""
echo "📖 API文档地址:"
echo "  • Knowledge Service: http://localhost:8082/docs"
echo "  • Agent Service: http://localhost:8081/docs"
echo "  • Knowledge Graph Service: http://localhost:8087/docs"
echo "  • CommonGround: http://localhost:8000 (Web界面)"

echo ""
echo "🎯 演示环境启动完成!"
echo "Demo Environment Ready!"

echo ""
echo "💡 提示: 使用 stop_demo_services.sh 脚本停止所有服务"