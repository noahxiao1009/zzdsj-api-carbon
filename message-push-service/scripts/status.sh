#!/bin/bash

# Message Push Service 状态检查脚本
# SSE消息推送微服务状态监控脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 配置
SERVICE_NAME="message-push-service"
SERVICE_PORT=8089
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# 函数定义
print_banner() {
    echo -e "${PURPLE}"
    echo "================================================================"
    echo "    Message Push Service - 状态监控"
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

log_section() {
    echo -e "${BLUE}[SECTION]${NC} $1"
}

check_service_health() {
    log_section "服务健康检查"
    
    # 检查服务是否响应
    if curl -f -s "http://localhost:$SERVICE_PORT/sse/health" >/dev/null 2>&1; then
        echo -e "  ✅ ${GREEN}HTTP健康检查${NC}: 通过"
        
        # 获取详细健康信息
        HEALTH_INFO=$(curl -s "http://localhost:$SERVICE_PORT/sse/health" 2>/dev/null || echo "{}")
        
        if command -v jq &> /dev/null; then
            echo "     状态: $(echo "$HEALTH_INFO" | jq -r '.status // "unknown"')"
            echo "     运行时间: $(echo "$HEALTH_INFO" | jq -r '.uptime // "unknown"')"
            echo "     版本: $(echo "$HEALTH_INFO" | jq -r '.version // "unknown"')"
        fi
    else
        echo -e "  ❌ ${RED}HTTP健康检查${NC}: 失败"
        return 1
    fi
    
    # 检查根端点
    if curl -f -s "http://localhost:$SERVICE_PORT/" >/dev/null 2>&1; then
        echo -e "  ✅ ${GREEN}根端点${NC}: 可访问"
    else
        echo -e "  ❌ ${RED}根端点${NC}: 不可访问"
    fi
    
    # 检查API文档
    if curl -f -s "http://localhost:$SERVICE_PORT/docs" >/dev/null 2>&1; then
        echo -e "  ✅ ${GREEN}API文档${NC}: 可访问"
    else
        echo -e "  ⚠️  ${YELLOW}API文档${NC}: 不可访问"
    fi
}

check_port_status() {
    log_section "端口状态检查"
    
    # 检查端口占用
    if lsof -Pi :$SERVICE_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "  ✅ ${GREEN}端口 $SERVICE_PORT${NC}: 已监听"
        
        # 获取进程信息
        PID=$(lsof -Pi :$SERVICE_PORT -sTCP:LISTEN -t 2>/dev/null | head -1)
        if [ -n "$PID" ]; then
            PROCESS_INFO=$(ps -p "$PID" -o pid,ppid,user,cmd --no-headers 2>/dev/null || echo "")
            if [ -n "$PROCESS_INFO" ]; then
                echo "     进程信息: $PROCESS_INFO"
            fi
        fi
    else
        echo -e "  ❌ ${RED}端口 $SERVICE_PORT${NC}: 未监听"
        return 1
    fi
    
    # 检查网络连接
    CONNECTIONS=$(netstat -an 2>/dev/null | grep ":$SERVICE_PORT " | wc -l || echo "0")
    echo "     活跃连接数: $CONNECTIONS"
}

check_pm2_status() {
    log_section "PM2状态检查"
    
    if command -v pm2 &> /dev/null; then
        if pm2 list | grep -q "$SERVICE_NAME"; then
            echo -e "  ✅ ${GREEN}PM2服务${NC}: 已注册"
            
            # 获取PM2状态
            PM2_STATUS=$(pm2 jlist | jq -r ".[] | select(.name==\"$SERVICE_NAME\") | .pm2_env.status" 2>/dev/null || echo "unknown")
            echo "     状态: $PM2_STATUS"
            
            # 获取运行时间
            PM2_UPTIME=$(pm2 jlist | jq -r ".[] | select(.name==\"$SERVICE_NAME\") | .pm2_env.pm_uptime" 2>/dev/null || echo "0")
            if [ "$PM2_UPTIME" != "0" ] && [ "$PM2_UPTIME" != "null" ]; then
                UPTIME_SEC=$(( ($(date +%s) * 1000 - $PM2_UPTIME) / 1000 ))
                UPTIME_HUMAN=$(date -d "@$UPTIME_SEC" +"%H:%M:%S" 2>/dev/null || echo "unknown")
                echo "     运行时间: $UPTIME_HUMAN"
            fi
            
            # 获取内存使用
            PM2_MEMORY=$(pm2 jlist | jq -r ".[] | select(.name==\"$SERVICE_NAME\") | .monit.memory" 2>/dev/null || echo "0")
            if [ "$PM2_MEMORY" != "0" ] && [ "$PM2_MEMORY" != "null" ]; then
                MEMORY_MB=$(( $PM2_MEMORY / 1024 / 1024 ))
                echo "     内存使用: ${MEMORY_MB}MB"
            fi
            
            # 获取CPU使用
            PM2_CPU=$(pm2 jlist | jq -r ".[] | select(.name==\"$SERVICE_NAME\") | .monit.cpu" 2>/dev/null || echo "0")
            if [ "$PM2_CPU" != "null" ]; then
                echo "     CPU使用: ${PM2_CPU}%"
            fi
            
        else
            echo -e "  ❌ ${RED}PM2服务${NC}: 未注册"
        fi
    else
        echo -e "  ⚠️  ${YELLOW}PM2${NC}: 未安装"
    fi
}

check_docker_status() {
    log_section "Docker状态检查"
    
    if command -v docker &> /dev/null; then
        # 检查Docker容器
        CONTAINERS=$(docker ps --filter "name=$SERVICE_NAME" --format "{{.Names}}" 2>/dev/null || echo "")
        
        if [ -n "$CONTAINERS" ]; then
            echo -e "  ✅ ${GREEN}Docker容器${NC}: 运行中"
            
            for container in $CONTAINERS; do
                echo "     容器名称: $container"
                
                # 获取容器状态
                STATUS=$(docker inspect "$container" --format "{{.State.Status}}" 2>/dev/null || echo "unknown")
                echo "     状态: $STATUS"
                
                # 获取运行时间
                STARTED=$(docker inspect "$container" --format "{{.State.StartedAt}}" 2>/dev/null || echo "unknown")
                echo "     启动时间: $STARTED"
                
                # 获取端口映射
                PORTS=$(docker port "$container" 2>/dev/null || echo "none")
                if [ "$PORTS" != "none" ]; then
                    echo "     端口映射: $PORTS"
                fi
            done
        else
            echo -e "  ❌ ${RED}Docker容器${NC}: 未运行"
        fi
        
        # 检查Docker Compose
        if [ -f "$PROJECT_ROOT/docker-compose.yml" ]; then
            cd "$PROJECT_ROOT"
            COMPOSE_STATUS=$(docker-compose ps --services --filter "status=running" 2>/dev/null | grep -c "$SERVICE_NAME" || echo "0")
            if [ "$COMPOSE_STATUS" -gt 0 ]; then
                echo -e "  ✅ ${GREEN}Docker Compose${NC}: 运行中"
            else
                echo -e "  ❌ ${RED}Docker Compose${NC}: 未运行"
            fi
        fi
    else
        echo -e "  ⚠️  ${YELLOW}Docker${NC}: 未安装"
    fi
}

check_redis_status() {
    log_section "Redis状态检查"
    
    if command -v redis-cli &> /dev/null; then
        if redis-cli ping >/dev/null 2>&1; then
            echo -e "  ✅ ${GREEN}Redis连接${NC}: 正常"
            
            # 获取Redis信息
            REDIS_INFO=$(redis-cli info server 2>/dev/null | grep -E "redis_version|uptime_in_seconds" || echo "")
            if [ -n "$REDIS_INFO" ]; then
                VERSION=$(echo "$REDIS_INFO" | grep redis_version | cut -d: -f2 | tr -d '\r')
                UPTIME=$(echo "$REDIS_INFO" | grep uptime_in_seconds | cut -d: -f2 | tr -d '\r')
                
                echo "     版本: $VERSION"
                
                if [ -n "$UPTIME" ] && [ "$UPTIME" -gt 0 ]; then
                    UPTIME_HUMAN=$(date -d "@$UPTIME" +"%H:%M:%S" 2>/dev/null || echo "$UPTIME seconds")
                    echo "     运行时间: $UPTIME_HUMAN"
                fi
            fi
            
            # 检查连接数
            CONNECTED_CLIENTS=$(redis-cli info clients 2>/dev/null | grep connected_clients | cut -d: -f2 | tr -d '\r' || echo "unknown")
            if [ "$CONNECTED_CLIENTS" != "unknown" ]; then
                echo "     连接客户端: $CONNECTED_CLIENTS"
            fi
            
        else
            echo -e "  ❌ ${RED}Redis连接${NC}: 失败"
            echo "     请检查Redis服务是否启动"
        fi
    else
        echo -e "  ⚠️  ${YELLOW}Redis CLI${NC}: 未安装"
    fi
}

check_system_resources() {
    log_section "系统资源检查"
    
    # 检查CPU使用率
    if command -v top &> /dev/null; then
        CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1 || echo "unknown")
        echo "  CPU使用率: ${CPU_USAGE}%"
    fi
    
    # 检查内存使用
    if command -v free &> /dev/null; then
        MEMORY_INFO=$(free -h | grep Mem:)
        MEMORY_USED=$(echo "$MEMORY_INFO" | awk '{print $3}')
        MEMORY_TOTAL=$(echo "$MEMORY_INFO" | awk '{print $2}')
        echo "  内存使用: $MEMORY_USED / $MEMORY_TOTAL"
    fi
    
    # 检查磁盘使用
    DISK_USAGE=$(df -h . | awk 'NR==2 {print $5}' 2>/dev/null || echo "unknown")
    echo "  磁盘使用: $DISK_USAGE"
    
    # 检查负载平均值
    if [ -f "/proc/loadavg" ]; then
        LOAD_AVG=$(cat /proc/loadavg | cut -d' ' -f1-3)
        echo "  系统负载: $LOAD_AVG"
    fi
}

check_log_files() {
    log_section "日志文件检查"
    
    cd "$PROJECT_ROOT"
    
    # 检查服务日志
    if [ -f "logs/$SERVICE_NAME.log" ]; then
        LOG_SIZE=$(du -h "logs/$SERVICE_NAME.log" | cut -f1)
        LOG_LINES=$(wc -l < "logs/$SERVICE_NAME.log" 2>/dev/null || echo "0")
        echo -e "  ✅ ${GREEN}服务日志${NC}: 存在 ($LOG_SIZE, $LOG_LINES 行)"
        
        # 检查最近的错误
        ERROR_COUNT=$(grep -i error "logs/$SERVICE_NAME.log" 2>/dev/null | tail -n 10 | wc -l || echo "0")
        if [ "$ERROR_COUNT" -gt 0 ]; then
            echo -e "     ⚠️  ${YELLOW}最近错误${NC}: $ERROR_COUNT 条"
        fi
    else
        echo -e "  ❌ ${RED}服务日志${NC}: 不存在"
    fi
    
    # 检查PM2日志
    if [ -f "logs/pm2-$SERVICE_NAME-combined.log" ]; then
        PM2_LOG_SIZE=$(du -h "logs/pm2-$SERVICE_NAME-combined.log" | cut -f1)
        echo -e "  ✅ ${GREEN}PM2日志${NC}: 存在 ($PM2_LOG_SIZE)"
    fi
    
    # 检查错误日志
    if [ -f "logs/error.log" ]; then
        ERROR_LOG_SIZE=$(du -h "logs/error.log" | cut -f1)
        echo -e "  ⚠️  ${YELLOW}错误日志${NC}: 存在 ($ERROR_LOG_SIZE)"
    fi
}

show_recent_logs() {
    log_section "最近日志 (最后20行)"
    
    cd "$PROJECT_ROOT"
    
    if [ -f "logs/$SERVICE_NAME.log" ]; then
        echo -e "${CYAN}--- 服务日志 ---${NC}"
        tail -n 20 "logs/$SERVICE_NAME.log" 2>/dev/null || echo "无法读取日志文件"
    elif [ -f "logs/pm2-$SERVICE_NAME-combined.log" ]; then
        echo -e "${CYAN}--- PM2日志 ---${NC}"
        tail -n 20 "logs/pm2-$SERVICE_NAME-combined.log" 2>/dev/null || echo "无法读取日志文件"
    else
        echo "未找到日志文件"
    fi
}

show_sse_connections() {
    log_section "SSE连接统计"
    
    # 尝试从服务API获取连接信息
    if curl -f -s "http://localhost:$SERVICE_PORT/sse/api/v1/connections/stats" >/dev/null 2>&1; then
        CONN_STATS=$(curl -s "http://localhost:$SERVICE_PORT/sse/api/v1/connections/stats" 2>/dev/null || echo "{}")
        
        if command -v jq &> /dev/null; then
            echo "  活跃连接数: $(echo "$CONN_STATS" | jq -r '.active_connections // "unknown"')"
            echo "  总连接数: $(echo "$CONN_STATS" | jq -r '.total_connections // "unknown"')"
            echo "  消息队列大小: $(echo "$CONN_STATS" | jq -r '.queue_size // "unknown"')"
        else
            echo "  连接信息: $CONN_STATS"
        fi
    else
        echo "  无法获取连接统计信息"
    fi
}

generate_summary() {
    echo -e "${GREEN}"
    echo "================================================================"
    echo "    状态检查摘要"
    echo "================================================================"
    echo -e "${NC}"
    
    # 基于检查结果生成摘要
    if curl -f -s "http://localhost:$SERVICE_PORT/sse/health" >/dev/null 2>&1; then
        echo -e "✅ ${GREEN}服务状态${NC}: 正常运行"
    else
        echo -e "❌ ${RED}服务状态${NC}: 异常"
    fi
    
    if lsof -Pi :$SERVICE_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "✅ ${GREEN}端口状态${NC}: 正常监听"
    else
        echo -e "❌ ${RED}端口状态${NC}: 未监听"
    fi
    
    if command -v redis-cli &> /dev/null && redis-cli ping >/dev/null 2>&1; then
        echo -e "✅ ${GREEN}Redis状态${NC}: 连接正常"
    else
        echo -e "❌ ${RED}Redis状态${NC}: 连接异常"
    fi
    
    echo ""
    echo "详细信息请查看上述检查结果"
    echo "日志文件位置: $PROJECT_ROOT/logs/"
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
            echo "  --health     仅检查服务健康状态"
            echo "  --logs       显示最近日志"
            echo "  --full       完整状态检查（默认）"
            echo "  -h, --help   显示帮助信息"
            echo ""
            echo "示例:"
            echo "  $0           # 完整状态检查"
            echo "  $0 --health  # 仅健康检查"
            echo "  $0 --logs    # 显示最近日志"
            exit 0
            ;;
        --health)
            check_service_health
            exit 0
            ;;
        --logs)
            show_recent_logs
            exit 0
            ;;
        --full|"")
            # 执行完整检查
            ;;
        *)
            log_error "未知参数: $1"
            echo "使用 --help 查看帮助信息"
            exit 1
            ;;
    esac
    
    # 执行状态检查
    cd "$PROJECT_ROOT"
    
    echo "检查时间: $(date)"
    echo "项目路径: $PROJECT_ROOT"
    echo ""
    
    # 依次执行各项检查
    check_service_health || true
    check_port_status || true
    check_pm2_status || true
    check_docker_status || true
    check_redis_status || true
    check_system_resources || true
    check_log_files || true
    show_sse_connections || true
    
    echo ""
    generate_summary
}

# 运行主函数
main "$@"