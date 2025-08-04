#!/bin/bash

# Message Push Service 停止脚本
# SSE消息推送微服务停止脚本

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

# 函数定义
print_banner() {
    echo -e "${BLUE}"
    echo "================================================================"
    echo "    Message Push Service - 服务停止脚本"
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

stop_pm2_service() {
    log_info "停止PM2服务..."
    
    if command -v pm2 &> /dev/null; then
        # 检查PM2服务是否运行
        if pm2 list | grep -q "$SERVICE_NAME"; then
            log_info "发现PM2服务，正在停止..."
            pm2 stop "$SERVICE_NAME" || true
            pm2 delete "$SERVICE_NAME" || true
            log_info "PM2服务已停止"
        else
            log_info "未找到PM2服务实例"
        fi
    else
        log_info "PM2未安装，跳过PM2服务检查"
    fi
}

stop_port_process() {
    log_info "检查端口 $SERVICE_PORT 上的进程..."
    
    # 查找占用端口的进程
    PIDS=$(lsof -ti:$SERVICE_PORT 2>/dev/null || true)
    
    if [ -n "$PIDS" ]; then
        log_info "发现占用端口的进程: $PIDS"
        
        # 尝试优雅停止
        for PID in $PIDS; do
            if kill -TERM "$PID" 2>/dev/null; then
                log_info "已向进程 $PID 发送TERM信号"
            fi
        done
        
        # 等待进程停止
        sleep 5
        
        # 检查进程是否仍在运行
        REMAINING_PIDS=$(lsof -ti:$SERVICE_PORT 2>/dev/null || true)
        
        if [ -n "$REMAINING_PIDS" ]; then
            log_warn "进程未响应TERM信号，强制停止..."
            for PID in $REMAINING_PIDS; do
                if kill -KILL "$PID" 2>/dev/null; then
                    log_info "已强制停止进程 $PID"
                fi
            done
        fi
        
        # 最终检查
        sleep 2
        FINAL_PIDS=$(lsof -ti:$SERVICE_PORT 2>/dev/null || true)
        
        if [ -z "$FINAL_PIDS" ]; then
            log_info "端口 $SERVICE_PORT 已释放"
        else
            log_error "无法停止端口 $SERVICE_PORT 上的进程"
            return 1
        fi
    else
        log_info "端口 $SERVICE_PORT 未被占用"
    fi
}

stop_docker_service() {
    log_info "检查Docker容器..."
    
    if command -v docker &> /dev/null; then
        # 检查并停止相关容器
        CONTAINERS=$(docker ps -q --filter "name=$SERVICE_NAME" 2>/dev/null || true)
        
        if [ -n "$CONTAINERS" ]; then
            log_info "发现Docker容器，正在停止..."
            echo "$CONTAINERS" | xargs docker stop
            log_info "Docker容器已停止"
        else
            log_info "未找到相关Docker容器"
        fi
        
        # 检查docker-compose
        if [ -f "$PROJECT_ROOT/docker-compose.yml" ]; then
            cd "$PROJECT_ROOT"
            if docker-compose ps | grep -q "$SERVICE_NAME"; then
                log_info "停止docker-compose服务..."
                docker-compose down
                log_info "docker-compose服务已停止"
            fi
        fi
    else
        log_info "Docker未安装，跳过Docker检查"
    fi
}

stop_background_processes() {
    log_info "检查后台Python进程..."
    
    # 查找可能的Python进程
    PYTHON_PIDS=$(pgrep -f "main.py" 2>/dev/null || true)
    
    if [ -n "$PYTHON_PIDS" ]; then
        log_info "发现Python进程: $PYTHON_PIDS"
        
        for PID in $PYTHON_PIDS; do
            # 检查进程命令行是否包含我们的服务
            if ps -p "$PID" -o args= | grep -q "$SERVICE_NAME\|message.*push"; then
                log_info "停止Python进程 $PID"
                if kill -TERM "$PID" 2>/dev/null; then
                    log_info "已向进程 $PID 发送停止信号"
                fi
            fi
        done
        
        # 等待进程停止
        sleep 3
        
        # 检查是否需要强制停止
        for PID in $PYTHON_PIDS; do
            if ps -p "$PID" > /dev/null 2>&1; then
                if ps -p "$PID" -o args= | grep -q "$SERVICE_NAME\|message.*push"; then
                    log_warn "强制停止进程 $PID"
                    kill -KILL "$PID" 2>/dev/null || true
                fi
            fi
        done
    else
        log_info "未找到相关Python进程"
    fi
}

cleanup_resources() {
    log_info "清理资源..."
    
    # 清理临时文件
    if [ -d "$PROJECT_ROOT/temp" ]; then
        rm -rf "$PROJECT_ROOT/temp"
        log_info "已清理临时文件"
    fi
    
    # 清理PID文件
    if [ -f "$PROJECT_ROOT/$SERVICE_NAME.pid" ]; then
        rm -f "$PROJECT_ROOT/$SERVICE_NAME.pid"
        log_info "已清理PID文件"
    fi
    
    # 清理锁文件
    if [ -f "$PROJECT_ROOT/.service.lock" ]; then
        rm -f "$PROJECT_ROOT/.service.lock"
        log_info "已清理锁文件"
    fi
}

check_service_status() {
    log_info "检查服务状态..."
    
    # 检查端口
    if lsof -Pi :$SERVICE_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        log_error "服务可能仍在运行，端口 $SERVICE_PORT 仍被占用"
        return 1
    fi
    
    # 检查PM2
    if command -v pm2 &> /dev/null; then
        if pm2 list | grep -q "$SERVICE_NAME" | grep -q "online"; then
            log_error "PM2中的服务仍在运行"
            return 1
        fi
    fi
    
    log_info "服务已完全停止"
    return 0
}

print_status() {
    echo -e "${GREEN}"
    echo "================================================================"
    echo "    $SERVICE_NAME 停止完成"
    echo "================================================================"
    echo -e "${NC}"
    echo "服务状态: 已停止"
    echo "端口状态: 已释放"
    echo ""
    echo "如需重新启动服务，请运行:"
    echo "  scripts/start.sh"
    echo ""
}

# 主函数
main() {
    print_banner
    
    # 解析参数
    case "$1" in
        --help|-h)
            echo "用法: $0 [OPTIONS]"
            echo ""
            echo "选项:"
            echo "  --force     强制停止所有相关进程"
            echo "  --clean     停止后清理所有资源"
            echo "  -h, --help  显示帮助信息"
            echo ""
            echo "示例:"
            echo "  $0          # 正常停止服务"
            echo "  $0 --force  # 强制停止服务"
            echo "  $0 --clean  # 停止并清理资源"
            exit 0
            ;;
        --force)
            log_info "使用强制停止模式"
            FORCE_MODE=true
            ;;
        --clean)
            log_info "使用清理模式"
            CLEAN_MODE=true
            ;;
        "")
            log_info "使用正常停止模式"
            ;;
        *)
            log_error "未知参数: $1"
            echo "使用 --help 查看帮助信息"
            exit 1
            ;;
    esac
    
    # 执行停止流程
    cd "$PROJECT_ROOT"
    
    # 停止各种形式的服务
    stop_pm2_service
    stop_docker_service
    stop_port_process
    stop_background_processes
    
    # 清理资源（如果指定）
    if [ "$CLEAN_MODE" = true ]; then
        cleanup_resources
    fi
    
    # 检查停止状态
    if check_service_status; then
        print_status
    else
        log_error "服务停止可能不完整，请手动检查"
        exit 1
    fi
}

# 错误处理
trap 'log_error "停止过程中发生错误"; exit 1' ERR

# 运行主函数
main "$@"