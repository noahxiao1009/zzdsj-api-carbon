#!/bin/bash

# 任务管理服务启动脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_info "=== 任务管理服务启动脚本 ==="

# 检查Go环境
if ! command -v go &> /dev/null; then
    log_error "Go未安装，请先安装Go 1.21+"
    exit 1
fi

GO_VERSION=$(go version | awk '{print $3}' | sed 's/go//')
log_info "Go版本: $GO_VERSION"

# 检查Docker环境
if ! command -v docker &> /dev/null; then
    log_warn "Docker未安装，将使用本地启动模式"
    USE_DOCKER=false
else
    USE_DOCKER=true
    log_info "Docker已安装: $(docker --version)"
fi

# 获取启动模式
MODE=${1:-"dev"}

case $MODE in
    "dev"|"development")
        log_info "启动模式: 开发环境"
        start_development
        ;;
    "docker")
        log_info "启动模式: Docker容器"
        start_docker
        ;;
    "prod"|"production")
        log_info "启动模式: 生产环境"
        start_production
        ;;
    *)
        log_error "未知启动模式: $MODE"
        show_usage
        exit 1
        ;;
esac

# 开发环境启动
start_development() {
    log_info "正在启动开发环境..."
    
    # 检查依赖服务
    check_dependencies
    
    # 启动基础设施服务
    if [ "$USE_DOCKER" = true ]; then
        log_info "启动PostgreSQL和Redis..."
        docker-compose up -d postgres redis
        
        # 等待服务就绪
        wait_for_postgres
        wait_for_redis
    else
        log_warn "请确保PostgreSQL(端口5434)和Redis(端口6379)已启动"
    fi
    
    # 下载Go依赖
    log_info "下载Go模块依赖..."
    go mod download
    go mod tidy
    
    # 设置环境变量
    export PORT=8084
    export ENVIRONMENT=development
    export LOG_LEVEL=info
    export DATABASE_HOST=localhost
    export DATABASE_PORT=5434
    export DATABASE_USER=zzdsj_demo
    export DATABASE_PASSWORD=zzdsj123
    export DATABASE_DATABASE=zzdsj_demo
    export REDIS_HOST=localhost
    export REDIS_PORT=6379
    export REDIS_DB=1
    
    # 启动服务
    log_info "启动任务管理服务 (开发模式)..."
    go run cmd/server/main.go
}

# Docker容器启动
start_docker() {
    if [ "$USE_DOCKER" = false ]; then
        log_error "Docker未安装，无法使用容器模式"
        exit 1
    fi
    
    log_info "正在使用Docker启动所有服务..."
    
    # 构建镜像
    log_info "构建Docker镜像..."
    docker-compose build task-manager
    
    # 启动所有服务
    log_info "启动Docker服务栈..."
    docker-compose up -d
    
    # 显示服务状态
    sleep 5
    show_docker_status
}

# 生产环境启动
start_production() {
    log_info "正在启动生产环境..."
    
    # 构建生产版本
    log_info "构建生产版本..."
    make build
    
    # 检查配置文件
    if [ ! -f "config/config.yaml" ]; then
        log_error "配置文件不存在: config/config.yaml"
        exit 1
    fi
    
    # 设置生产环境变量
    export ENVIRONMENT=production
    export LOG_LEVEL=info
    
    # 启动服务
    log_info "启动任务管理服务 (生产模式)..."
    ./build/task-manager
}

# 检查依赖
check_dependencies() {
    log_info "检查依赖..."
    
    # 检查端口占用
    if lsof -Pi :8084 -sTCP:LISTEN -t >/dev/null ; then
        log_warn "端口8084已被占用"
    fi
    
    if lsof -Pi :5434 -sTCP:LISTEN -t >/dev/null ; then
        log_info "PostgreSQL端口5434已在使用"
    fi
    
    if lsof -Pi :6379 -sTCP:LISTEN -t >/dev/null ; then
        log_info "Redis端口6379已在使用"
    fi
}

# 等待PostgreSQL就绪
wait_for_postgres() {
    log_info "等待PostgreSQL就绪..."
    
    for i in {1..30}; do
        if docker-compose exec -T postgres pg_isready -U zzdsj_demo -d zzdsj_demo &>/dev/null; then
            log_info "✓ PostgreSQL已就绪"
            return 0
        fi
        sleep 2
        echo -n "."
    done
    
    log_error "PostgreSQL启动超时"
    exit 1
}

# 等待Redis就绪
wait_for_redis() {
    log_info "等待Redis就绪..."
    
    for i in {1..30}; do
        if docker-compose exec -T redis redis-cli ping &>/dev/null; then
            log_info "✓ Redis已就绪"
            return 0
        fi
        sleep 1
        echo -n "."
    done
    
    log_error "Redis启动超时"
    exit 1
}

# 显示Docker服务状态
show_docker_status() {
    log_info "服务状态:"
    docker-compose ps
    
    echo
    log_info "服务地址:"
    echo "  • 任务管理API: http://localhost:8084"
    echo "  • 健康检查:   http://localhost:8084/health"
    echo "  • API文档:    http://localhost:8084/api/v1"
    echo "  • 监控指标:   http://localhost:8084/metrics"
    echo "  • PostgreSQL: localhost:5434"
    echo "  • Redis:      localhost:6379"
    
    if docker-compose ps | grep -q grafana; then
        echo "  • Grafana:    http://localhost:3000 (admin/admin123)"
    fi
    
    if docker-compose ps | grep -q prometheus; then
        echo "  • Prometheus: http://localhost:9090"
    fi
}

# 显示使用说明
show_usage() {
    echo "使用方法:"
    echo "  $0 [mode]"
    echo
    echo "启动模式:"
    echo "  dev        - 开发环境 (默认)"
    echo "  docker     - Docker容器"
    echo "  prod       - 生产环境"
    echo
    echo "示例:"
    echo "  $0 dev      # 开发环境启动"
    echo "  $0 docker   # Docker启动"
    echo "  $0 prod     # 生产环境启动"
}

# 主函数
main() {
    # 检查参数
    if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
        show_usage
        exit 0
    fi
    
    # 设置脚本目录为工作目录
    cd "$(dirname "$0")/.."
    
    # 创建必要目录
    mkdir -p logs build dist
    
    log_info "工作目录: $(pwd)"
}

# 信号处理
cleanup() {
    log_info "正在停止服务..."
    if [ "$USE_DOCKER" = true ] && [ "$MODE" = "docker" ]; then
        docker-compose down
    fi
    exit 0
}

trap cleanup SIGINT SIGTERM

# 如果直接运行脚本
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    main "$@"
fi