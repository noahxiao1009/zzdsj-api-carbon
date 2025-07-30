#!/bin/bash

# 任务管理服务API测试脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 服务配置
BASE_URL="http://localhost:8084"
API_VERSION="v1"
API_BASE="$BASE_URL/api/$API_VERSION"

# 测试计数器
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

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

log_test() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

# 测试函数
run_test() {
    local test_name="$1"
    local test_command="$2"
    local expected_status="$3"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    log_test "Running: $test_name"
    
    # 执行测试命令
    response=$(eval "$test_command" 2>&1)
    status=$?
    
    if [ $status -eq ${expected_status:-0} ]; then
        log_info "✓ PASSED: $test_name"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        echo "$response" | jq . 2>/dev/null || echo "$response"
    else
        log_error "✗ FAILED: $test_name"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        echo "Expected status: ${expected_status:-0}, Got: $status"
        echo "$response"
    fi
    
    echo "----------------------------------------"
}

# 检查服务是否可用
check_service() {
    log_info "检查服务可用性..."
    
    if ! curl -s --connect-timeout 5 "$BASE_URL/health" > /dev/null; then
        log_error "服务不可用: $BASE_URL"
        log_info "请先启动服务: ./scripts/start.sh dev"
        exit 1
    fi
    
    log_info "✓ 服务可用"
}

# 健康检查测试
test_health_check() {
    log_info "=== 健康检查测试 ==="
    
    run_test "健康检查" \
        "curl -s $BASE_URL/health" \
        0
    
    run_test "监控指标" \
        "curl -s $BASE_URL/metrics | head -5" \
        0
}

# 任务管理测试
test_task_management() {
    log_info "=== 任务管理测试 ==="
    
    # 创建测试任务
    run_test "创建健康检查任务" \
        "curl -s -X POST $API_BASE/tasks -H 'Content-Type: application/json' -d '{\"task_type\":\"health_check\",\"kb_id\":\"test_kb_001\",\"priority\":\"normal\",\"payload\":{\"message\":\"test\"}}'" \
        0
    
    # 获取任务ID (从上一个测试的响应中提取)
    TASK_ID=$(curl -s -X POST $API_BASE/tasks \
        -H 'Content-Type: application/json' \
        -d '{"task_type":"health_check","kb_id":"test_kb_002","priority":"normal","payload":{"message":"test"}}' | \
        jq -r '.id')
    
    if [ "$TASK_ID" != "null" ] && [ -n "$TASK_ID" ]; then
        log_info "创建的任务ID: $TASK_ID"
        
        # 查询任务详情
        run_test "查询任务详情" \
            "curl -s $API_BASE/tasks/$TASK_ID" \
            0
        
        # 等待任务处理
        log_info "等待任务处理..."
        sleep 3
        
        # 再次查询任务状态
        run_test "查询任务状态(处理后)" \
            "curl -s $API_BASE/tasks/$TASK_ID" \
            0
        
        # 尝试重试任务 (如果失败的话)
        run_test "尝试重试任务" \
            "curl -s -X POST $API_BASE/tasks/$TASK_ID/retry" \
            0
        
    else
        log_error "无法创建测试任务"
    fi
    
    # 获取任务列表
    run_test "获取任务列表" \
        "curl -s '$API_BASE/tasks?page=1&page_size=10'" \
        0
    
    # 按知识库ID过滤
    run_test "按知识库ID过滤任务" \
        "curl -s '$API_BASE/tasks?kb_id=test_kb_001'" \
        0
    
    # 按状态过滤
    run_test "按状态过滤任务" \
        "curl -s '$API_BASE/tasks?status=completed'" \
        0
}

# 批量任务测试
test_batch_tasks() {
    log_info "=== 批量任务测试 ==="
    
    run_test "批量创建任务" \
        "curl -s -X POST $API_BASE/tasks/batch -H 'Content-Type: application/json' -d '[{\"task_type\":\"health_check\",\"kb_id\":\"batch_kb_001\",\"payload\":{\"message\":\"batch1\"}},{\"task_type\":\"health_check\",\"kb_id\":\"batch_kb_001\",\"payload\":{\"message\":\"batch2\"}}]'" \
        0
}

# 统计信息测试
test_statistics() {
    log_info "=== 统计信息测试 ==="
    
    run_test "获取任务统计" \
        "curl -s $API_BASE/stats/tasks" \
        0
    
    run_test "获取系统统计" \
        "curl -s $API_BASE/stats/system" \
        0
    
    run_test "获取特定知识库统计" \
        "curl -s '$API_BASE/stats/tasks?kb_id=test_kb_001'" \
        0
}

# 队列信息测试
test_queue_info() {
    log_info "=== 队列信息测试 ==="
    
    run_test "获取队列信息" \
        "curl -s $API_BASE/queues/info" \
        0
    
    run_test "获取高优先级队列信息" \
        "curl -s '$API_BASE/queues/info?priority=high'" \
        0
}

# 错误处理测试
test_error_handling() {
    log_info "=== 错误处理测试 ==="
    
    run_test "查询不存在的任务" \
        "curl -s $API_BASE/tasks/nonexistent-task-id" \
        0
    
    run_test "无效的任务类型" \
        "curl -s -X POST $API_BASE/tasks -H 'Content-Type: application/json' -d '{\"task_type\":\"invalid_type\",\"kb_id\":\"test\",\"payload\":{}}'" \
        0
    
    run_test "缺少必需字段" \
        "curl -s -X POST $API_BASE/tasks -H 'Content-Type: application/json' -d '{\"task_type\":\"health_check\"}'" \
        0
    
    run_test "无效的优先级" \
        "curl -s -X POST $API_BASE/tasks -H 'Content-Type: application/json' -d '{\"task_type\":\"health_check\",\"kb_id\":\"test\",\"priority\":\"invalid\",\"payload\":{}}'" \
        0
}

# 性能测试
test_performance() {
    log_info "=== 性能测试 ==="
    
    # 检查是否安装了性能测试工具
    if command -v hey &> /dev/null; then
        log_info "使用hey进行性能测试..."
        
        run_test "并发健康检查测试" \
            "hey -n 100 -c 10 -q 5 $BASE_URL/health" \
            0
        
        run_test "并发任务创建测试" \
            "hey -n 50 -c 5 -m POST -H 'Content-Type: application/json' -d '{\"task_type\":\"health_check\",\"kb_id\":\"perf_test\",\"payload\":{\"message\":\"perf\"}}' $API_BASE/tasks" \
            0
            
    elif command -v ab &> /dev/null; then
        log_info "使用ab进行性能测试..."
        
        run_test "Apache Bench健康检查测试" \
            "ab -n 100 -c 10 $BASE_URL/health" \
            0
            
    else
        log_warn "未找到性能测试工具 (hey或ab)，跳过性能测试"
    fi
}

# 集成测试
test_integration() {
    log_info "=== 集成测试 ==="
    
    # 完整的任务生命周期测试
    log_info "测试完整任务生命周期..."
    
    # 1. 创建文档处理任务
    TASK_RESPONSE=$(curl -s -X POST $API_BASE/tasks \
        -H 'Content-Type: application/json' \
        -d '{
            "task_type": "document_processing",
            "kb_id": "integration_test_kb",
            "priority": "high",
            "payload": {
                "file_path": "/tmp/test.pdf",
                "chunk_size": 1000
            },
            "max_retries": 2,
            "timeout": 60
        }')
    
    TASK_ID=$(echo "$TASK_RESPONSE" | jq -r '.id')
    
    if [ "$TASK_ID" != "null" ] && [ -n "$TASK_ID" ]; then
        log_info "创建集成测试任务: $TASK_ID"
        
        # 2. 监控任务状态直到完成
        for i in {1..30}; do
            TASK_STATUS=$(curl -s $API_BASE/tasks/$TASK_ID | jq -r '.status')
            PROGRESS=$(curl -s $API_BASE/tasks/$TASK_ID | jq -r '.progress')
            
            log_info "任务状态: $TASK_STATUS, 进度: $PROGRESS%"
            
            if [ "$TASK_STATUS" = "completed" ] || [ "$TASK_STATUS" = "failed" ]; then
                break
            fi
            
            sleep 2
        done
        
        # 3. 获取最终结果
        FINAL_RESULT=$(curl -s $API_BASE/tasks/$TASK_ID)
        log_info "最终任务结果:"
        echo "$FINAL_RESULT" | jq .
        
        # 4. 验证任务在统计中
        STATS=$(curl -s "$API_BASE/stats/tasks?kb_id=integration_test_kb")
        TOTAL_TASKS=$(echo "$STATS" | jq -r '.total_tasks')
        log_info "知识库任务总数: $TOTAL_TASKS"
        
    else
        log_error "集成测试任务创建失败"
    fi
}

# 清理测试数据
cleanup_test_data() {
    log_info "=== 清理测试数据 ==="
    
    # 这里可以添加清理逻辑，比如删除测试任务
    # 由于当前API不支持删除，我们暂时跳过
    log_info "测试数据将由定期清理任务处理"
}

# 显示测试结果摘要
show_test_summary() {
    echo
    log_info "=== 测试结果摘要 ==="
    echo "总测试数: $TOTAL_TESTS"
    echo -e "通过测试: ${GREEN}$PASSED_TESTS${NC}"
    echo -e "失败测试: ${RED}$FAILED_TESTS${NC}"
    
    if [ $FAILED_TESTS -eq 0 ]; then
        echo -e "${GREEN}🎉 所有测试通过！${NC}"
        exit 0
    else
        echo -e "${RED}❌ 有 $FAILED_TESTS 个测试失败${NC}"
        exit 1
    fi
}

# 显示使用说明
show_usage() {
    echo "任务管理服务API测试脚本"
    echo
    echo "使用方法:"
    echo "  $0 [test_type]"
    echo
    echo "测试类型:"
    echo "  all          - 运行所有测试 (默认)"
    echo "  health       - 健康检查测试"
    echo "  task         - 任务管理测试"
    echo "  batch        - 批量任务测试"
    echo "  stats        - 统计信息测试"
    echo "  queue        - 队列信息测试"
    echo "  error        - 错误处理测试"
    echo "  performance  - 性能测试"
    echo "  integration  - 集成测试"
    echo
    echo "示例:"
    echo "  $0           # 运行所有测试"
    echo "  $0 health    # 只运行健康检查测试"
    echo "  $0 task      # 只运行任务管理测试"
}

# 主函数
main() {
    local test_type="${1:-all}"
    
    if [ "$test_type" = "--help" ] || [ "$test_type" = "-h" ]; then
        show_usage
        exit 0
    fi
    
    log_info "=== 任务管理服务API测试 ==="
    log_info "测试类型: $test_type"
    log_info "目标服务: $BASE_URL"
    
    # 检查依赖
    if ! command -v curl &> /dev/null; then
        log_error "curl未安装，请先安装curl"
        exit 1
    fi
    
    if ! command -v jq &> /dev/null; then
        log_error "jq未安装，请先安装jq"
        exit 1
    fi
    
    # 检查服务可用性
    check_service
    
    # 运行测试
    case $test_type in
        "health")
            test_health_check
            ;;
        "task")
            test_task_management
            ;;
        "batch")
            test_batch_tasks
            ;;
        "stats")
            test_statistics
            ;;
        "queue")
            test_queue_info
            ;;
        "error")
            test_error_handling
            ;;
        "performance")
            test_performance
            ;;
        "integration")
            test_integration
            ;;
        "all")
            test_health_check
            test_task_management
            test_batch_tasks
            test_statistics
            test_queue_info
            test_error_handling
            test_performance
            test_integration
            ;;
        *)
            log_error "未知测试类型: $test_type"
            show_usage
            exit 1
            ;;
    esac
    
    # 显示测试结果
    show_test_summary
}

# 如果直接运行脚本
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    main "$@"
fi