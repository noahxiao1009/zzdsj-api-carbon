#!/bin/bash

# PM2微服务管理脚本 - NextAgent
# 用于管理所有微服务的启动、停止、重启等操作

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 微服务列表配置 - 使用函数替代关联数组以提高兼容性
get_service_info() {
    local service_key=$1
    case $service_key in
        "gateway") echo "gateway-service:8080" ;;
        "agent") echo "agent-service:8081" ;;
        "knowledge") echo "knowledge-service:8082" ;;
        "chat") echo "chat-service:8083" ;;
        "database") echo "database-service:8084" ;;
        "base") echo "base-service:8085" ;;
        "system") echo "system-service:8086" ;;
        "kg") echo "knowledge-graph-service:8087" ;;
        "model") echo "model-service:8088" ;;
        "mcp") echo "mcp-service:8089" ;;
        "tools") echo "tools-service:8090" ;;
        "reports") echo "intelligent-reports-service:8091" ;;
        "kaiban") echo "kaiban-service:8092" ;;
        "messaging") echo "messaging-service:8093" ;;
        "scheduler") echo "scheduler-service:8094" ;;
        *) echo "" ;;
    esac
}

# 所有服务键列表
ALL_SERVICE_KEYS=("gateway" "agent" "knowledge" "chat" "database" "base" "system" "kg" "model" "mcp" "tools" "reports" "kaiban" "messaging" "scheduler")

# 核心服务（必须启动的服务）
CORE_SERVICES=("gateway" "knowledge" "agent" "model" "database")

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

log_success() {
    echo -e "${CYAN}[SUCCESS]${NC} $1"
}

log_header() {
    echo -e "${PURPLE}$1${NC}"
}

# 打印服务状态横幅
print_banner() {
    echo -e "${BLUE}========================================================================${NC}"
    echo -e "${BLUE}    NextAgent - 微服务管理工具${NC}"
    echo -e "${BLUE}========================================================================${NC}"
    echo -e "${CYAN}    微服务总数: ${#ALL_SERVICE_KEYS[@]}${NC}"
    echo -e "${CYAN}    核心服务: ${#CORE_SERVICES[@]} (gateway, knowledge, agent, model, database)${NC}"
    echo -e "${CYAN}    管理模式: 单独服务启动/集群管理${NC}"
    echo -e "${BLUE}========================================================================${NC}"
    echo ""
}

# 检查PM2是否安装
check_pm2() {
    if ! command -v pm2 &> /dev/null; then
        log_error "PM2 未安装，请先安装 PM2: npm install -g pm2"
        exit 1
    fi
    log_info "PM2 版本: $(pm2 --version)"
}

# 创建日志目录
create_log_dirs() {
    for service_key in "${ALL_SERVICE_KEYS[@]}"; do
        local service_info=$(get_service_info "$service_key")
        if [ -n "$service_info" ]; then
            IFS=':' read -r service_name port <<< "$service_info"
            if [ -d "$service_name" ]; then
                mkdir -p "$service_name/logs"
                log_info "创建 $service_name 日志目录"
            fi
        fi
    done
}

# 检查服务目录是否存在
check_service_exists() {
    local service_key=$1
    local service_info=$(get_service_info "$service_key")
    if [ -z "$service_info" ]; then
        log_error "未知服务: $service_key"
        echo "可用服务: ${ALL_SERVICE_KEYS[*]}"
        return 1
    fi
    
    IFS=':' read -r service_name port <<< "$service_info"
    if [ ! -d "$service_name" ]; then
        log_error "服务目录不存在: $service_name"
        return 1
    fi
    
    if [ ! -f "$service_name/ecosystem.config.js" ]; then
        log_error "PM2配置文件不存在: $service_name/ecosystem.config.js"
        return 1
    fi
    
    return 0
}

# 启动单个服务
start_service() {
    local service_key=$1
    local environment=${2:-development}
    
    if ! check_service_exists "$service_key"; then
        return 1
    fi
    
    local service_info=$(get_service_info "$service_key")
    IFS=':' read -r service_name port <<< "$service_info"
    
    log_info "启动服务: $service_name (端口: $port, 环境: $environment)"
    
    # 处理conda环境
    if [ -n "$CONDA_ENV" ] && [ -z "$PYTHON_INTERPRETER" ]; then
        if command -v conda &> /dev/null; then
            local conda_prefix=$(conda info --envs | grep "^$CONDA_ENV " | awk '{print $NF}')
            if [ -n "$conda_prefix" ] && [ -f "$conda_prefix/bin/python" ]; then
                export PYTHON_INTERPRETER="$conda_prefix/bin/python"
                log_info "使用Conda环境: $CONDA_ENV -> $PYTHON_INTERPRETER"
            else
                log_warn "Conda环境 '$CONDA_ENV' 不存在或无效，使用默认Python"
            fi
        else
            log_warn "未找到conda命令，忽略CONDA_ENV设置"
        fi
    fi
    
    # 检查是否指定了Python解释器
    local python_info=""
    if [ -n "$PYTHON_INTERPRETER" ]; then
        python_info=" (Python: $PYTHON_INTERPRETER)"
    fi
    
    cd "$service_name" || return 1
    
    # 传递Python解释器环境变量
    if PYTHON_INTERPRETER="$PYTHON_INTERPRETER" pm2 start ecosystem.config.js --env "$environment"; then
        log_success "$service_name 启动成功$python_info"
        cd ..
        return 0
    else
        log_error "$service_name 启动失败"
        cd ..
        return 1
    fi
}

# 停止单个服务
stop_service() {
    local service_key=$1
    
    if ! check_service_exists "$service_key"; then
        return 1
    fi
    
    local service_info=$(get_service_info "$service_key")
    IFS=':' read -r service_name port <<< "$service_info"
    
    log_info "停止服务: $service_name"
    
    if pm2 stop "$service_name"; then
        log_success "$service_name 停止成功"
        return 0
    else
        log_error "$service_name 停止失败"
        return 1
    fi
}

# 重启单个服务
restart_service() {
    local service_key=$1
    local environment=${2:-development}
    
    if ! check_service_exists "$service_key"; then
        return 1
    fi
    
    local service_info=$(get_service_info "$service_key")
    IFS=':' read -r service_name port <<< "$service_info"
    
    log_info "重启服务: $service_name"
    
    cd "$service_name" || return 1
    
    if pm2 restart "$service_name"; then
        log_success "$service_name 重启成功"
        cd ..
        return 0
    else
        log_error "$service_name 重启失败"
        cd ..
        return 1
    fi
}

# 删除单个服务
delete_service() {
    local service_key=$1
    
    if ! check_service_exists "$service_key"; then
        return 1
    fi
    
    local service_info=$(get_service_info "$service_key")
    IFS=':' read -r service_name port <<< "$service_info"
    
    log_warn "删除服务: $service_name"
    
    if pm2 delete "$service_name"; then
        log_success "$service_name 删除成功"
        return 0
    else
        log_error "$service_name 删除失败"
        return 1
    fi
}

# 启动核心服务
start_core() {
    local environment=${1:-development}
    log_header "启动核心服务 (环境: $environment)"
    
    local failed_services=()
    
    for service_key in "${CORE_SERVICES[@]}"; do
        if ! start_service "$service_key" "$environment"; then
            failed_services+=("$service_key")
        fi
        sleep 2  # 给服务一些启动时间
    done
    
    if [ ${#failed_services[@]} -eq 0 ]; then
        log_success "所有核心服务启动成功"
    else
        log_error "以下核心服务启动失败: ${failed_services[*]}"
    fi
    
    show_status
}

# 启动所有服务
start_all() {
    local environment=${1:-development}
    log_header "启动所有微服务 (环境: $environment)"
    
    create_log_dirs
    
    local failed_services=()
    
    for service_key in "${ALL_SERVICE_KEYS[@]}"; do
        if ! start_service "$service_key" "$environment"; then
            failed_services+=("$service_key")
        fi
        sleep 1  # 给服务一些启动时间
    done
    
    if [ ${#failed_services[@]} -eq 0 ]; then
        log_success "所有服务启动成功"
    else
        log_error "以下服务启动失败: ${failed_services[*]}"
    fi
    
    show_status
}

# 停止所有服务
stop_all() {
    log_header "停止所有微服务"
    
    local failed_services=()
    
    for service_key in "${ALL_SERVICE_KEYS[@]}"; do
        if ! stop_service "$service_key"; then
            failed_services+=("$service_key")
        fi
    done
    
    if [ ${#failed_services[@]} -eq 0 ]; then
        log_success "所有服务停止成功"
    else
        log_error "以下服务停止失败: ${failed_services[*]}"
    fi
}

# 重启所有服务
restart_all() {
    local environment=${1:-development}
    log_header "重启所有微服务 (环境: $environment)"
    
    local failed_services=()
    
    for service_key in "${ALL_SERVICE_KEYS[@]}"; do
        if ! restart_service "$service_key" "$environment"; then
            failed_services+=("$service_key")
        fi
        sleep 1
    done
    
    if [ ${#failed_services[@]} -eq 0 ]; then
        log_success "所有服务重启成功"
    else
        log_error "以下服务重启失败: ${failed_services[*]}"
    fi
    
    show_status
}

# 删除所有服务
delete_all() {
    log_warn "删除所有微服务"
    read -p "确认删除所有PM2服务? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        pm2 delete all
        log_success "所有PM2服务已删除"
    else
        log_info "操作已取消"
    fi
}

# 显示服务状态
show_status() {
    log_header "微服务状态"
    pm2 status
    echo ""
    log_info "服务端口映射:"
    for service_key in "${ALL_SERVICE_KEYS[@]}"; do
        local service_info=$(get_service_info "$service_key")
    IFS=':' read -r service_name port <<< "$service_info"
        echo "  $service_name -> http://localhost:$port"
    done
}

# 显示服务日志
show_logs() {
    local service_key=$1
    
    if [ -z "$service_key" ]; then
        log_info "显示所有服务日志"
        pm2 logs
    else
        if ! check_service_exists "$service_key"; then
            return 1
        fi
        
        local service_info=$(get_service_info "$service_key")
    IFS=':' read -r service_name port <<< "$service_info"
        log_info "显示 $service_name 服务日志"
        pm2 logs "$service_name"
    fi
}

# 监控服务
monitor() {
    log_header "启动PM2监控界面"
    pm2 monit
}

# 获取服务当前状态
get_service_status() {
    local service_key=$1
    local service_info=$(get_service_info "$service_key")
    IFS=':' read -r service_name port <<< "$service_info"
    
    if pm2 list | grep -q "$service_name.*online"; then
        echo "online"
    elif pm2 list | grep -q "$service_name.*stopped"; then
        echo "stopped"
    else
        echo "offline"
    fi
}

# 交互式服务选择
interactive_service_selection() {
    local action=${1:-start}
    local environment=${2:-development}
    
    print_banner
    
    log_header "交互式服务管理 - $action 模式 (环境: $environment)"
    echo ""
    
    # 显示服务列表和状态
    echo -e "${CYAN}可用服务列表:${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    printf "%-4s %-12s %-28s %-8s %-10s %s\n" "序号" "简称" "服务名称" "端口" "状态" "描述"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    local index=1
    local service_keys=()
    
    for service_key in "${ALL_SERVICE_KEYS[@]}"; do
        local service_info=$(get_service_info "$service_key")
        IFS=':' read -r service_name port <<< "$service_info"
        local status=$(get_service_status "$service_key")
        local is_core=""
        
        # 检查是否为核心服务
        for core_service in "${CORE_SERVICES[@]}"; do
            if [ "$core_service" == "$service_key" ]; then
                is_core=" [核心]"
                break
            fi
        done
        
        # 状态文本（无颜色）
        local status_text=""
        case $status in
            "online") status_text="运行中" ;;
            "stopped") status_text="已停止" ;;
            *) status_text="离线" ;;
        esac
        
        printf "%-4d %-12s %-28s %-8s %-10s %s\n" \
            "$index" "$service_key" "$service_name" "$port" "$status_text" "$is_core"
        
        service_keys[$index]=$service_key
        ((index++))
    done
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # 显示快捷选项
    echo -e "${YELLOW}快捷选项:${NC}"
    echo "  a/all   - 所有服务"
    echo "  c/core  - 核心服务 ($(echo "${CORE_SERVICES[@]}" | tr ' ' ', '))"
    echo "  q/quit  - 退出"
    echo ""
    
    # 获取用户输入
    echo -e "${BLUE}请选择要${action}的服务:${NC}"
    echo "• 单个服务: 输入序号 (如: 1)"
    echo "• 多个服务: 输入序号，用空格或逗号分隔 (如: 1 2 3 或 1,2,3)"
    echo "• 快捷选项: 输入 a/all, c/core, 或 q/quit"
    echo ""
    
    read -p "请输入选择: " -r selection
    
    # 处理用户输入
    case "$selection" in
        "q"|"quit"|"exit")
            log_info "操作已取消"
            return 0
            ;;
        "a"|"all")
            log_info "选择所有服务..."
            case $action in
                "start") start_all "$environment" ;;
                "stop") stop_all ;;
                "restart") restart_all "$environment" ;;
                "delete") delete_all ;;
            esac
            ;;
        "c"|"core")
            log_info "选择核心服务..."
            case $action in
                "start") start_core "$environment" ;;
                "stop") 
                    for service_key in "${CORE_SERVICES[@]}"; do
                        stop_service "$service_key"
                    done
                    ;;
                "restart")
                    for service_key in "${CORE_SERVICES[@]}"; do
                        restart_service "$service_key" "$environment"
                    done
                    ;;
                "delete")
                    for service_key in "${CORE_SERVICES[@]}"; do
                        delete_service "$service_key"
                    done
                    ;;
            esac
            ;;
        *)
            # 处理数字选择
            # 将逗号替换为空格，处理多种分隔符
            selection=$(echo "$selection" | tr ',' ' ')
            local selected_services=()
            local failed_selections=()
            
            for num in $selection; do
                # 验证是否为数字
                if [[ "$num" =~ ^[0-9]+$ ]] && [ "$num" -ge 1 ] && [ "$num" -lt "$index" ]; then
                    selected_services+=(${service_keys[$num]})
                else
                    failed_selections+=("$num")
                fi
            done
            
            if [ ${#failed_selections[@]} -gt 0 ]; then
                log_warn "无效选择: ${failed_selections[*]}"
            fi
            
            if [ ${#selected_services[@]} -eq 0 ]; then
                log_error "没有有效的服务选择"
                return 1
            fi
            
            # 执行选中服务的操作
            log_info "对选中的服务执行 $action 操作: ${selected_services[*]}"
            local failed_services=()
            
            for service_key in "${selected_services[@]}"; do
                case $action in
                    "start")
                        if ! start_service "$service_key" "$environment"; then
                            failed_services+=("$service_key")
                        fi
                        ;;
                    "stop")
                        if ! stop_service "$service_key"; then
                            failed_services+=("$service_key")
                        fi
                        ;;
                    "restart")
                        if ! restart_service "$service_key" "$environment"; then
                            failed_services+=("$service_key")
                        fi
                        ;;
                    "delete")
                        if ! delete_service "$service_key"; then
                            failed_services+=("$service_key")
                        fi
                        ;;
                esac
                sleep 1  # 给服务一些处理时间
            done
            
            if [ ${#failed_services[@]} -eq 0 ]; then
                log_success "所有选中的服务操作完成"
            else
                log_error "以下服务操作失败: ${failed_services[*]}"
            fi
            ;;
    esac
    
    echo ""
    show_status
}

# 显示帮助信息
show_help() {
    print_banner
    echo -e "${BLUE}用法: ./pm2-manager.sh [命令] [服务名] [环境]${NC}"
    echo ""
    echo -e "${YELLOW}交互式命令 (推荐):${NC}"
    echo "  interactive [env]        交互式服务管理界面 (默认: development)"
    echo "  i [env]                  交互式服务管理界面 (简写)"
    echo "  select:start [env]       交互选择服务启动"
    echo "  select:stop              交互选择服务停止"
    echo "  select:restart [env]     交互选择服务重启"
    echo "  select:delete            交互选择服务删除"
    echo ""
    echo -e "${YELLOW}全局命令:${NC}"
    echo "  start:all [env]          启动所有服务 (默认: development)"
    echo "  start:core [env]         启动核心服务 (默认: development)"
    echo "  stop:all                 停止所有服务"
    echo "  restart:all [env]        重启所有服务 (默认: development)"
    echo "  delete:all               删除所有服务"
    echo "  status                   显示服务状态"
    echo "  logs [service]           显示日志（可选指定服务）"
    echo "  monitor                  启动监控界面"
    echo ""
    echo -e "${YELLOW}单服务命令:${NC}"
    echo "  start <service> [env]    启动指定服务 (默认: development)"
    echo "  stop <service>           停止指定服务"
    echo "  restart <service> [env]  重启指定服务 (默认: development)"
    echo "  delete <service>         删除指定服务"
    echo ""
    echo -e "${YELLOW}可用服务:${NC}"
    for service_key in "${ALL_SERVICE_KEYS[@]}"; do
        local service_info=$(get_service_info "$service_key")
        IFS=':' read -r service_name port <<< "$service_info"
        printf "  %-12s -> %-25s (端口: %s)\n" "$service_key" "$service_name" "$port"
    done
    echo ""
    echo -e "${YELLOW}环境选项:${NC}"
    echo "  development (默认)   开发环境"
    echo "  production          生产环境"
    echo ""
    echo -e "${YELLOW}Python环境配置:${NC}"
    echo "  自动检测             使用 which python 检测当前Python环境"
    echo "  手动指定             PYTHON_INTERPRETER=/path/to/python ./pm2-manager.sh ..."
    echo "  Conda环境示例        PYTHON_INTERPRETER=/opt/anaconda3/envs/myenv/bin/python"
    echo ""
    echo -e "${YELLOW}示例:${NC}"
    echo "  ./pm2-manager.sh interactive              # 交互式管理界面"
    echo "  ./pm2-manager.sh i production             # 生产环境交互管理"
    echo "  ./pm2-manager.sh select:start             # 交互选择启动服务"
    echo "  ./pm2-manager.sh start:core               # 启动核心服务"
    echo "  ./pm2-manager.sh start knowledge production  # 启动知识库服务"
    echo "  ./pm2-manager.sh restart:all development # 重启所有服务"
    echo "  ./pm2-manager.sh logs gateway             # 查看网关日志"
    echo ""
    echo -e "${YELLOW}Python环境示例:${NC}"
    echo "  PYTHON_INTERPRETER=/opt/anaconda3/bin/python ./pm2-manager.sh start:core"
    echo "  PYTHON_INTERPRETER=\$(which python3) ./pm2-manager.sh start knowledge"
    echo "  CONDA_ENV=myenv ./pm2-manager.sh start:core  # 使用conda环境"
    echo "  ./start-with-conda.sh myenv core             # 专用conda启动脚本"
    echo ""
}

# 交互式管理界面主菜单
interactive_main_menu() {
    local environment=${1:-development}
    
    while true; do
        print_banner
        log_header "交互式微services管理界面 (环境: $environment)"
        echo ""
        
        # 显示当前运行的服务统计
        local online_count=0
        local total_count=${#ALL_SERVICE_KEYS[@]}
        
        for service_key in "${ALL_SERVICE_KEYS[@]}"; do
            local status=$(get_service_status "$service_key")
            if [ "$status" == "online" ]; then
                ((online_count++))
            fi
        done
        
        echo -e "${CYAN}服务状态概览: ${GREEN}$online_count${NC}/${CYAN}$total_count${NC} 服务在线"
        echo ""
        
        echo -e "${YELLOW}请选择操作:${NC}"
        echo "  1. 启动服务 (交互选择)"
        echo "  2. 停止服务 (交互选择)"  
        echo "  3. 重启服务 (交互选择)"
        echo "  4. 删除服务 (交互选择)"
        echo "  5. 查看服务状态"
        echo "  6. 查看服务日志"
        echo "  7. 启动监控界面"
        echo "  8. 切换环境 (当前: $environment)"
        echo "  9. 显示帮助"
        echo "  0. 退出"
        echo ""
        
        read -p "请输入选择 (0-9): " -r choice
        
        case $choice in
            1)
                interactive_service_selection "start" "$environment"
                read -p "按任意键继续..." -n 1 -r
                ;;
            2)
                interactive_service_selection "stop" "$environment"
                read -p "按任意键继续..." -n 1 -r
                ;;
            3)
                interactive_service_selection "restart" "$environment"
                read -p "按任意键继续..." -n 1 -r
                ;;
            4)
                echo -e "${RED}警告: 删除操作将完全移除PM2中的服务配置${NC}"
                read -p "确定要继续吗? (y/N): " -n 1 -r confirm
                echo ""
                if [[ $confirm =~ ^[Yy]$ ]]; then
                    interactive_service_selection "delete" "$environment"
                fi
                read -p "按任意键继续..." -n 1 -r
                ;;
            5)
                show_status
                read -p "按任意键继续..." -n 1 -r
                ;;
            6)
                echo ""
                echo "输入服务简称查看日志 (留空查看所有服务日志):"
                printf "可用服务: "
                printf "%s " "${ALL_SERVICE_KEYS[@]}"
                echo ""
                read -p "请输入服务简称: " -r service_choice
                show_logs "$service_choice"
                read -p "按Ctrl+C停止日志查看，然后按任意键继续..." -n 1 -r
                ;;
            7)
                log_info "启动PM2监控界面..."
                log_info "按 'q' 退出监控界面"
                sleep 2
                monitor
                ;;
            8)
                echo ""
                echo "当前环境: $environment"
                echo "1. development"
                echo "2. production"
                read -p "选择新环境 (1-2): " -r env_choice
                case $env_choice in
                    1) environment="development" ;;
                    2) environment="production" ;;
                    *) log_warn "无效选择，保持当前环境" ;;
                esac
                ;;
            9)
                show_help
                read -p "按任意键继续..." -n 1 -r
                ;;
            0|"q"|"quit"|"exit")
                log_info "退出交互式管理界面"
                break
                ;;
            *)
                log_warn "无效选择，请输入 0-9"
                sleep 1
                ;;
        esac
        
        echo ""
    done
}

# 主函数
main() {
    check_pm2
    
    case "$1" in
        "interactive"|"i")
            interactive_main_menu "${2:-development}"
            ;;
        "select:start")
            interactive_service_selection "start" "${2:-development}"
            ;;
        "select:stop")
            interactive_service_selection "stop" "${2:-development}"
            ;;
        "select:restart")
            interactive_service_selection "restart" "${2:-development}"
            ;;
        "select:delete")
            interactive_service_selection "delete" "${2:-development}"
            ;;
        "start:all")
            start_all "${2:-development}"
            ;;
        "start:core")
            start_core "${2:-development}"
            ;;
        "start")
            if [ -z "$2" ]; then
                log_error "请指定服务名"
                echo "用法: $0 start <service> [environment]"
                exit 1
            fi
            start_service "$2" "${3:-development}"
            ;;
        "stop:all")
            stop_all
            ;;
        "stop")
            if [ -z "$2" ]; then
                log_error "请指定服务名"
                echo "用法: $0 stop <service>"
                exit 1
            fi
            stop_service "$2"
            ;;
        "restart:all")
            restart_all "${2:-development}"
            ;;
        "restart")
            if [ -z "$2" ]; then
                log_error "请指定服务名"
                echo "用法: $0 restart <service> [environment]"
                exit 1
            fi
            restart_service "$2" "${3:-development}"
            ;;
        "delete:all")
            delete_all
            ;;
        "delete")
            if [ -z "$2" ]; then
                log_error "请指定服务名"
                echo "用法: $0 delete <service>"
                exit 1
            fi
            delete_service "$2"
            ;;
        "status")
            show_status
            ;;
        "logs")
            show_logs "$2"
            ;;
        "monitor")
            monitor
            ;;
        "help"|"--help"|"-h")
            show_help
            ;;
        "")
            # 默认启动交互式界面
            interactive_main_menu "development"
            ;;
        *)
            log_error "未知命令: $1"
            echo "使用 './pm2-manager.sh help' 查看帮助"
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"