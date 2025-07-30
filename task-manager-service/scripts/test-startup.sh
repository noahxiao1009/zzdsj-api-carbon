#!/bin/bash

# Task Manager服务启动测试脚本

set -e

echo "🚀 Task Manager服务启动测试"
echo "================================"

# 定义颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 定义配置
HTTP_PORT=8084
GRPC_PORT=8085
POSTGRES_HOST="localhost"
POSTGRES_PORT=5434
REDIS_HOST="localhost"
REDIS_PORT=6379

echo -e "${BLUE}1. 检查环境依赖...${NC}"

# 检查Go版本
if ! command -v go &> /dev/null; then
    echo -e "${RED}❌ Go未安装${NC}"
    exit 1
fi

GO_VERSION=$(go version | cut -d' ' -f3)
echo -e "${GREEN}✓ Go版本: $GO_VERSION${NC}"

# 检查可执行文件
if [[ ! -f "./bin/task-manager-server" ]]; then
    echo -e "${YELLOW}⚠️  未找到可执行文件，开始构建...${NC}"
    go build -o ./bin/task-manager-server ./cmd/server
    echo -e "${GREEN}✓ 构建完成${NC}"
else
    echo -e "${GREEN}✓ 可执行文件存在${NC}"
fi

echo -e "${BLUE}2. 检查依赖服务连接...${NC}"

# 检查PostgreSQL连接
echo -n "检查PostgreSQL连接..."
if pg_isready -h $POSTGRES_HOST -p $POSTGRES_PORT >/dev/null 2>&1; then
    echo -e "${GREEN}✓ PostgreSQL连接正常${NC}"
else
    echo -e "${YELLOW}⚠️  PostgreSQL未启动或无法连接${NC}"
    echo "请确保PostgreSQL服务运行在 $POSTGRES_HOST:$POSTGRES_PORT"
fi

# 检查Redis连接
echo -n "检查Redis连接..."
if redis-cli -h $REDIS_HOST -p $REDIS_PORT ping >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Redis连接正常${NC}"
else
    echo -e "${YELLOW}⚠️  Redis未启动或无法连接${NC}"
    echo "请确保Redis服务运行在 $REDIS_HOST:$REDIS_PORT"
fi

echo -e "${BLUE}3. 检查端口占用...${NC}"

# 检查HTTP端口
if lsof -i :$HTTP_PORT >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  端口 $HTTP_PORT 已被占用${NC}"
    lsof -i :$HTTP_PORT
else
    echo -e "${GREEN}✓ HTTP端口 $HTTP_PORT 可用${NC}"
fi

# 检查gRPC端口
if lsof -i :$GRPC_PORT >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  端口 $GRPC_PORT 已被占用${NC}"
    lsof -i :$GRPC_PORT
else
    echo -e "${GREEN}✓ gRPC端口 $GRPC_PORT 可用${NC}"
fi

echo -e "${BLUE}4. 启动Task Manager服务...${NC}"

# 设置环境变量
export ENVIRONMENT=development
export LOG_LEVEL=info

# 启动服务
echo "启动Task Manager服务..."
./bin/task-manager-server &
SERVER_PID=$!

echo -e "${GREEN}✓ 服务已启动，PID: $SERVER_PID${NC}"

# 等待服务启动
echo "等待服务初始化..."
sleep 5

echo -e "${BLUE}5. 测试服务可用性...${NC}"

# 测试HTTP健康检查
echo -n "测试HTTP健康检查..."
HTTP_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$HTTP_PORT/health 2>/dev/null || echo "000")

if [[ "$HTTP_RESPONSE" == "200" ]]; then
    echo -e "${GREEN}✓ HTTP健康检查通过${NC}"
else
    echo -e "${RED}❌ HTTP健康检查失败 (状态码: $HTTP_RESPONSE)${NC}"
fi

# 测试gRPC连接
echo -n "测试gRPC连接..."
if command -v grpc_health_probe &> /dev/null; then
    if grpc_health_probe -addr localhost:$GRPC_PORT >/dev/null 2>&1; then
        echo -e "${GREEN}✓ gRPC连接正常${NC}"
    else
        echo -e "${YELLOW}⚠️  gRPC健康检查失败${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  grpc_health_probe未安装，跳过gRPC测试${NC}"
fi

echo -e "${BLUE}6. 测试API端点...${NC}"

# 测试系统统计
echo -n "测试系统统计API..."
STATS_RESPONSE=$(curl -s http://localhost:$HTTP_PORT/api/v1/stats/system 2>/dev/null)
if [[ $? -eq 0 ]] && [[ -n "$STATS_RESPONSE" ]]; then
    echo -e "${GREEN}✓ 系统统计API正常${NC}"
else
    echo -e "${RED}❌ 系统统计API失败${NC}"
fi

# 测试任务列表
echo -n "测试任务列表API..."
TASKS_RESPONSE=$(curl -s http://localhost:$HTTP_PORT/api/v1/tasks 2>/dev/null)
if [[ $? -eq 0 ]] && [[ -n "$TASKS_RESPONSE" ]]; then
    echo -e "${GREEN}✓ 任务列表API正常${NC}"
else
    echo -e "${RED}❌ 任务列表API失败${NC}"
fi

echo -e "${BLUE}7. 服务日志检查...${NC}"

# 检查服务是否仍在运行
if kill -0 $SERVER_PID 2>/dev/null; then
    echo -e "${GREEN}✓ 服务运行正常${NC}"
else
    echo -e "${RED}❌ 服务已退出${NC}"
fi

echo -e "${BLUE}8. 清理...${NC}"

# 停止服务
echo "停止服务..."
kill $SERVER_PID 2>/dev/null || true
sleep 2

# 强制杀死服务（如果仍在运行）
if kill -0 $SERVER_PID 2>/dev/null; then
    echo "强制停止服务..."
    kill -9 $SERVER_PID 2>/dev/null || true
fi

echo -e "${GREEN}✓ 清理完成${NC}"

echo "================================"
echo -e "${GREEN}🎉 Task Manager服务启动测试完成！${NC}"

# 总结
echo -e "${BLUE}测试总结:${NC}"
echo "- HTTP服务: http://localhost:$HTTP_PORT"
echo "- gRPC服务: localhost:$GRPC_PORT"
echo "- 健康检查: http://localhost:$HTTP_PORT/health"
echo "- API文档: http://localhost:$HTTP_PORT/docs (如果启用)"

echo ""
echo "如需持续运行服务，请使用:"
echo "  ./bin/task-manager-server"