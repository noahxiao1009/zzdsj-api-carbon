#!/bin/bash

# Message Push Service 部署脚本
# SSE消息推送微服务自动化部署脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# 配置
SERVICE_NAME="message-push-service"
SERVICE_PORT=8089
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DEPLOY_ENV="${DEPLOY_ENV:-production}"

# 函数定义
print_banner() {
    echo -e "${PURPLE}"
    echo "================================================================"
    echo "    Message Push Service - 自动化部署脚本"
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

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

check_system() {
    log_step "检查系统环境..."
    
    # 检查操作系统
    OS=$(uname -s)
    log_info "操作系统: $OS"
    
    # 检查架构
    ARCH=$(uname -m)
    log_info "系统架构: $ARCH"
    
    # 检查内存
    if command -v free &> /dev/null; then
        MEMORY=$(free -h | awk '/^Mem:/ {print $2}')
        log_info "系统内存: $MEMORY"
    fi
    
    # 检查磁盘空间
    DISK_SPACE=$(df -h . | awk 'NR==2 {print $4}')
    log_info "可用磁盘空间: $DISK_SPACE"
}

check_dependencies() {
    log_step "检查依赖环境..."
    
    local missing_deps=()
    
    # 检查Python
    if ! command -v python3 &> /dev/null; then
        missing_deps+=("python3")
    else
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
        log_info "Python版本: $PYTHON_VERSION"
    fi
    
    # 检查pip
    if ! command -v pip3 &> /dev/null; then
        missing_deps+=("pip3")
    fi
    
    # 检查Redis
    if ! command -v redis-server &> /dev/null; then
        missing_deps+=("redis-server")
    else
        REDIS_VERSION=$(redis-server --version | head -n1 | cut -d' ' -f3 | cut -d'=' -f2)
        log_info "Redis版本: $REDIS_VERSION"
    fi
    
    # 检查Docker（可选）
    if command -v docker &> /dev/null; then
        DOCKER_VERSION=$(docker --version | cut -d' ' -f3 | cut -d',' -f1)
        log_info "Docker版本: $DOCKER_VERSION"
    else
        log_warn "Docker未安装（容器化部署需要）"
    fi
    
    # 检查Nginx（可选）
    if command -v nginx &> /dev/null; then
        NGINX_VERSION=$(nginx -v 2>&1 | cut -d' ' -f3 | cut -d'/' -f2)
        log_info "Nginx版本: $NGINX_VERSION"
    else
        log_warn "Nginx未安装（反向代理需要）"
    fi
    
    # 报告缺失依赖
    if [ ${#missing_deps[@]} -ne 0 ]; then
        log_error "缺失依赖: ${missing_deps[*]}"
        log_info "请安装缺失的依赖后重试"
        exit 1
    fi
    
    log_info "依赖检查完成"
}

setup_environment() {
    log_step "设置部署环境..."
    
    cd "$PROJECT_ROOT"
    
    # 创建必要目录
    mkdir -p logs
    mkdir -p config
    mkdir -p backups
    mkdir -p ssl
    
    # 设置权限
    chmod +x scripts/*.sh
    
    # 复制环境配置
    if [ ! -f "config/$DEPLOY_ENV.env" ]; then
        log_warn "环境配置文件不存在，创建默认配置..."
        cp "config/development.env" "config/$DEPLOY_ENV.env"
    fi
    
    log_info "环境设置完成"
}

install_python_deps() {
    log_step "安装Python依赖..."
    
    cd "$PROJECT_ROOT"
    
    # 创建虚拟环境
    if [ ! -d "venv" ]; then
        log_info "创建Python虚拟环境..."
        python3 -m venv venv
    fi
    
    # 激活虚拟环境
    source venv/bin/activate
    
    # 升级pip
    pip install --upgrade pip
    
    # 安装依赖
    pip install -r requirements.txt
    
    log_info "Python依赖安装完成"
}

setup_redis() {
    log_step "配置Redis服务..."
    
    # 检查Redis是否运行
    if ! redis-cli ping >/dev/null 2>&1; then
        log_info "启动Redis服务..."
        
        if [ "$DEPLOY_ENV" = "production" ]; then
            # 生产环境使用配置文件启动
            redis-server "$PROJECT_ROOT/config/redis.conf" --daemonize yes
        else
            # 开发环境使用默认配置
            redis-server --daemonize yes
        fi
        
        sleep 3
        
        if redis-cli ping >/dev/null 2>&1; then
            log_info "Redis启动成功"
        else
            log_error "Redis启动失败"
            exit 1
        fi
    else
        log_info "Redis已在运行"
    fi
}

build_docker_image() {
    log_step "构建Docker镜像..."
    
    cd "$PROJECT_ROOT"
    
    # 构建镜像
    docker build -t "$SERVICE_NAME:latest" .
    
    # 标记版本
    VERSION=$(grep "SERVICE_VERSION" config/production.env | cut -d'=' -f2)
    docker tag "$SERVICE_NAME:latest" "$SERVICE_NAME:$VERSION"
    
    log_info "Docker镜像构建完成"
}

deploy_with_docker() {
    log_step "使用Docker部署服务..."
    
    cd "$PROJECT_ROOT"
    
    # 停止现有容器
    docker-compose down 2>/dev/null || true
    
    # 启动服务
    if [ "$DEPLOY_ENV" = "production" ]; then
        docker-compose -f docker-compose.yml up -d
    else
        docker-compose -f docker-compose.yml up -d message-push-service redis
    fi
    
    log_info "Docker部署完成"
}

deploy_with_pm2() {
    log_step "使用PM2部署服务..."
    
    cd "$PROJECT_ROOT"
    
    # 检查PM2
    if ! command -v pm2 &> /dev/null; then
        log_error "PM2未安装，请先安装: npm install -g pm2"
        exit 1
    fi
    
    # 停止现有服务
    pm2 stop "$SERVICE_NAME" 2>/dev/null || true
    pm2 delete "$SERVICE_NAME" 2>/dev/null || true
    
    # 启动服务
    pm2 start ecosystem.config.js --env "$DEPLOY_ENV"
    
    # 保存PM2配置
    pm2 save
    
    # 设置开机启动
    pm2 startup
    
    log_info "PM2部署完成"
}

deploy_with_systemd() {
    log_step "配置Systemd服务..."
    
    # 创建systemd服务文件
    cat > "/tmp/$SERVICE_NAME.service" << EOF
[Unit]
Description=Message Push Service - SSE消息推送微服务
After=network.target redis.service

[Service]
Type=exec
User=$(whoami)
WorkingDirectory=$PROJECT_ROOT
Environment=PATH=$PROJECT_ROOT/venv/bin
ExecStart=$PROJECT_ROOT/venv/bin/python $PROJECT_ROOT/main.py
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=10
StandardOutput=append:$PROJECT_ROOT/logs/systemd-output.log
StandardError=append:$PROJECT_ROOT/logs/systemd-error.log

[Install]
WantedBy=multi-user.target
EOF
    
    # 安装服务文件（需要sudo权限）
    if [ -w "/etc/systemd/system" ]; then
        sudo mv "/tmp/$SERVICE_NAME.service" "/etc/systemd/system/"
        sudo systemctl daemon-reload
        sudo systemctl enable "$SERVICE_NAME"
        sudo systemctl start "$SERVICE_NAME"
        log_info "Systemd服务配置完成"
    else
        log_warn "无权限安装Systemd服务，跳过..."
    fi
}

setup_nginx() {
    log_step "配置Nginx反向代理..."
    
    if ! command -v nginx &> /dev/null; then
        log_warn "Nginx未安装，跳过反向代理配置"
        return 0
    fi
    
    # 创建Nginx配置
    NGINX_CONF="/tmp/$SERVICE_NAME-nginx.conf"
    cp "$PROJECT_ROOT/config/nginx.conf" "$NGINX_CONF"
    
    # 替换配置中的变量
    sed -i "s/localhost:$SERVICE_PORT/127.0.0.1:$SERVICE_PORT/g" "$NGINX_CONF"
    
    # 安装配置文件（需要sudo权限）
    if [ -w "/etc/nginx/sites-available" ]; then
        sudo mv "$NGINX_CONF" "/etc/nginx/sites-available/$SERVICE_NAME"
        sudo ln -sf "/etc/nginx/sites-available/$SERVICE_NAME" "/etc/nginx/sites-enabled/"
        sudo nginx -t && sudo systemctl reload nginx
        log_info "Nginx配置完成"
    else
        log_warn "无权限配置Nginx，请手动配置"
    fi
}

run_health_check() {
    log_step "运行健康检查..."
    
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f "http://localhost:$SERVICE_PORT/sse/health" >/dev/null 2>&1; then
            log_info "健康检查通过 (尝试 $attempt/$max_attempts)"
            return 0
        fi
        
        log_warn "健康检查失败，等待重试... (尝试 $attempt/$max_attempts)"
        sleep 5
        ((attempt++))
    done
    
    log_error "健康检查失败，服务可能未正常启动"
    return 1
}

show_deployment_info() {
    echo -e "${GREEN}"
    echo "================================================================"
    echo "    $SERVICE_NAME 部署完成"
    echo "================================================================"
    echo -e "${NC}"
    echo "部署环境: $DEPLOY_ENV"
    echo "服务地址: http://localhost:$SERVICE_PORT"
    echo "API文档: http://localhost:$SERVICE_PORT/docs"
    echo "健康检查: http://localhost:$SERVICE_PORT/sse/health"
    echo ""
    echo "SSE连接端点:"
    echo "  • 用户连接: /sse/user/{user_id}"
    echo "  • 服务连接: /sse/service/{service_name}"  
    echo "  • 任务连接: /sse/task/{task_id}"
    echo ""
    echo "管理命令:"
    echo "  • 查看状态: scripts/status.sh"
    echo "  • 停止服务: scripts/stop.sh"
    echo "  • 查看日志: scripts/logs.sh"
    echo ""
    echo "配置文件: config/$DEPLOY_ENV.env"
    echo "日志目录: logs/"
    echo ""
}

# 主函数
main() {
    print_banner
    
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --env)
                DEPLOY_ENV="$2"
                shift 2
                ;;
            --docker)
                DEPLOY_METHOD="docker"
                shift
                ;;
            --pm2)
                DEPLOY_METHOD="pm2"
                shift
                ;;
            --systemd)
                DEPLOY_METHOD="systemd"
                shift
                ;;
            --with-nginx)
                SETUP_NGINX=true
                shift
                ;;
            --help|-h)
                echo "用法: $0 [OPTIONS]"
                echo ""
                echo "选项:"
                echo "  --env ENV        部署环境 (development|production)"
                echo "  --docker         使用Docker部署"
                echo "  --pm2            使用PM2部署"
                echo "  --systemd        使用Systemd部署"
                echo "  --with-nginx     配置Nginx反向代理"
                echo "  -h, --help       显示帮助信息"
                echo ""
                echo "示例:"
                echo "  $0 --env production --pm2"
                echo "  $0 --docker --with-nginx"
                echo "  $0 --systemd --env production"
                exit 0
                ;;
            *)
                log_error "未知参数: $1"
                echo "使用 --help 查看帮助信息"
                exit 1
                ;;
        esac
    done
    
    # 设置默认部署方法
    DEPLOY_METHOD=${DEPLOY_METHOD:-pm2}
    
    log_info "部署环境: $DEPLOY_ENV"
    log_info "部署方法: $DEPLOY_METHOD"
    
    # 执行部署流程
    check_system
    check_dependencies
    setup_environment
    
    # 根据部署方法执行不同的部署流程
    case $DEPLOY_METHOD in
        docker)
            build_docker_image
            deploy_with_docker
            ;;
        pm2)
            install_python_deps
            setup_redis
            deploy_with_pm2
            ;;
        systemd)
            install_python_deps
            setup_redis
            deploy_with_systemd
            ;;
        *)
            log_error "未知的部署方法: $DEPLOY_METHOD"
            exit 1
            ;;
    esac
    
    # 可选配置
    if [ "$SETUP_NGINX" = true ]; then
        setup_nginx
    fi
    
    # 健康检查
    if run_health_check; then
        show_deployment_info
    else
        log_error "部署完成但服务未正常启动，请检查日志"
        exit 1
    fi
}

# 错误处理
trap 'log_error "部署过程中发生错误，正在回滚..."; exit 1' ERR

# 运行主函数
main "$@"