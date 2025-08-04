#!/bin/bash

# Message Push Service 启动脚本
# SSE消息推送微服务快速启动脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
SERVICE_NAME="message-push-service"
SERVICE_PORT=8089
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_ROOT/logs"

# 函数定义
print_banner() {
    echo -e "${BLUE}"
    echo "================================================================"
    echo "    Message Push Service - SSE消息推送微服务"
    echo "================================================================"
    echo -e "${NC}"
}

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_dependencies() {
    log_info "检查系统依赖..."
    
    # 检查Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 未安装"
        exit 1
    fi
    
    # 检查pip
    if ! command -v pip3 &> /dev/null; then
        log_error "pip 未安装"
        exit 1
    fi
    
    # 检查Redis
    if ! command -v redis-cli &> /dev/null; then
        log_warn "Redis CLI 未安装，请确保Redis服务可用"
    fi
    
    log_info "依赖检查完成"
}

check_port() {
    log_info "检查端口 $SERVICE_PORT 是否可用..."
    
    if lsof -Pi :$SERVICE_PORT -sTCP:LISTEN -t >/dev/null ; then
        log_warn "端口 $SERVICE_PORT 已被占用"
        read -p "是否停止现有服务并继续? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "停止占用端口的进程..."
            lsof -ti:$SERVICE_PORT | xargs kill -9 2>/dev/null || true
            sleep 2
        else
            log_error "启动中止"
            exit 1
        fi
    fi
    
    log_info "端口检查完成"
}

setup_environment() {
    log_info "设置运行环境..."
    
    cd "$PROJECT_ROOT"
    
    # 创建日志目录
    mkdir -p "$LOG_DIR"
    
    # 检查虚拟环境
    if [ ! -d "venv" ]; then
        log_info "创建Python虚拟环境..."
        python3 -m venv venv
    fi
    
    # 激活虚拟环境
    source venv/bin/activate
    
    # 安装依赖
    log_info "安装Python依赖..."
    pip install -r requirements.txt
    
    log_info "环境设置完成"
}

check_redis() {
    log_info "检查Redis连接..."
    
    # 尝试连接Redis
    if redis-cli ping >/dev/null 2>&1; then
        log_info "Redis连接正常"
    else
        log_warn "无法连接到Redis，正在尝试启动本地Redis..."
        
        # 尝试启动Redis
        if command -v redis-server &> /dev/null; then
            redis-server --daemonize yes --port 6379 &
            sleep 3
            
            if redis-cli ping >/dev/null 2>&1; then
                log_info "Redis启动成功"
            else
                log_error "Redis启动失败，请手动启动Redis服务"
                exit 1
            fi
        else
            log_error "Redis未安装，请安装Redis服务"
            exit 1
        fi
    fi
}

start_service() {
    log_info "启动 $SERVICE_NAME..."
    
    cd "$PROJECT_ROOT"
    
    # 检查环境配置
    if [ -f "config/development.env" ]; then
        log_info "加载开发环境配置..."
        export $(cat config/development.env | grep -v '^#' | xargs)
    fi
    
    # 启动服务
    if [ "$1" = "--development" ] || [ "$1" = "-d" ]; then
        log_info "以开发模式启动服务..."
        python main.py
    elif [ "$1" = "--pm2" ]; then
        log_info "使用PM2启动服务..."
        if ! command -v pm2 &> /dev/null; then
            log_error "PM2未安装，请先安装PM2: npm install -g pm2"
            exit 1
        fi
        pm2 start ecosystem.config.js --env development
        log_info "服务已通过PM2启动"
        pm2 status
    else
        log_info "以生产模式启动服务..."
        if [ -f "config/production.env" ]; then
            export $(cat config/production.env | grep -v '^#' | xargs)
        fi
        gunicorn main:app -w 1 -k uvicorn.workers.UvicornWorker \
            --bind 0.0.0.0:$SERVICE_PORT \
            --access-logfile "$LOG_DIR/access.log" \
            --error-logfile "$LOG_DIR/error.log" \
            --log-level info \
            --daemon
        log_info "服务已在后台启动"
    fi
}

print_service_info() {
    echo -e "${GREEN}"
    echo "================================================================"
    echo "    $SERVICE_NAME 启动完成"
    echo "================================================================"
    echo -e "${NC}"
    echo "服务地址: http://localhost:$SERVICE_PORT"
    echo "API文档: http://localhost:$SERVICE_PORT/docs"
    echo "健康检查: http://localhost:$SERVICE_PORT/sse/health"
    echo ""
    echo "SSE连接端点:"
    echo "  • 用户连接: /sse/user/{user_id}"
    echo "  • 服务连接: /sse/service/{service_name}"
    echo "  • 任务连接: /sse/task/{task_id}"
    echo ""
    echo "日志文件: $LOG_DIR/"
    echo ""
    echo -e "${YELLOW}按 Ctrl+C 停止服务${NC}"
}

# 主函数
main() {
    print_banner
    
    # 解析参数
    MODE="$1"
    case $MODE in
        --help|-h)
            echo "用法: $0 [OPTIONS]"
            echo ""
            echo "选项:"
            echo "  -d, --development    开发模式启动"
            echo "  --pm2               使用PM2启动"
            echo "  --production        生产模式启动（默认）"
            echo "  -h, --help          显示帮助信息"
            echo ""
            echo "示例:"
            echo "  $0                  # 生产模式启动"
            echo "  $0 --development    # 开发模式启动"
            echo "  $0 --pm2            # PM2启动"
            exit 0
            ;;
        --development|-d)
            log_info "使用开发模式"
            ;;
        --pm2)
            log_info "使用PM2模式"
            ;;
        --production|"")
            log_info "使用生产模式"
            ;;
        *)
            log_error "未知参数: $MODE"
            echo "使用 --help 查看帮助信息"
            exit 1
            ;;
    esac
    
    # 执行启动流程
    check_dependencies
    check_port
    setup_environment
    check_redis
    start_service "$MODE"
    
    if [ "$MODE" = "--development" ] || [ "$MODE" = "-d" ]; then
        print_service_info
    else
        log_info "$SERVICE_NAME 已启动"
        log_info "使用 'scripts/status.sh' 检查服务状态"
        log_info "使用 'scripts/stop.sh' 停止服务"
    fi
}

# 错误处理
trap 'log_error "启动过程中发生错误，正在清理..."; exit 1' ERR

# 运行主函数
main "$@"