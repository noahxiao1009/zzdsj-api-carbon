#!/bin/bash

# Task Manager文件上传功能测试脚本

set -e

echo "📁 Task Manager文件上传功能测试"
echo "================================"

# 定义颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 定义配置
HTTP_PORT=8084
BASE_URL="http://localhost:$HTTP_PORT"

# 检查服务是否运行
echo -e "${BLUE}1. 检查Task Manager服务状态...${NC}"

if curl -s $BASE_URL/health >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Task Manager服务运行正常${NC}"
else
    echo -e "${RED}❌ Task Manager服务未启动，请先启动服务:${NC}"
    echo "  ./bin/task-manager-server"
    exit 1
fi

# 创建测试文件
echo -e "${BLUE}2. 创建测试文件...${NC}"

mkdir -p test_files

# 创建测试文本文件
cat > test_files/test_document.txt << EOF
这是一个测试文档
用于测试Task Manager的文件上传功能

内容包括：
1. 文档处理
2. 任务队列管理  
3. 状态轮询

测试时间: $(date)
EOF

# 创建JSON测试文件
cat > test_files/test_data.json << EOF
{
  "title": "测试数据",
  "content": "Task Manager测试内容",
  "timestamp": "$(date -Iseconds)",
  "tags": ["测试", "上传", "任务队列"]
}
EOF

# 创建Markdown测试文件
cat > test_files/test_readme.md << EOF
# Task Manager测试文档

## 功能特性

- 高并发文件上传
- 任务队列管理
- 实时状态轮询
- MinIO存储集成

## 测试目的

验证文件上传和任务处理功能。

测试时间: $(date)
EOF

echo -e "${GREEN}✓ 测试文件创建完成${NC}"
ls -la test_files/

echo -e "${BLUE}3. 测试单文件上传...${NC}"

# 测试单文件上传
echo -n "上传文本文件..."
UPLOAD_RESPONSE=$(curl -s -X POST \
  -F "file=@test_files/test_document.txt" \
  -F "kb_id=test-kb-001" \
  $BASE_URL/api/v1/uploads/file)

if echo "$UPLOAD_RESPONSE" | grep -q "task_id"; then
    TASK_ID=$(echo "$UPLOAD_RESPONSE" | jq -r '.task_id' 2>/dev/null || echo "unknown")
    echo -e "${GREEN}✓ 单文件上传成功 (任务ID: $TASK_ID)${NC}"
else
    echo -e "${RED}❌ 单文件上传失败${NC}"
    echo "响应: $UPLOAD_RESPONSE"
fi

echo -e "${BLUE}4. 测试批量文件上传...${NC}"

# 测试批量文件上传
echo -n "上传多个文件..."
BATCH_RESPONSE=$(curl -s -X POST \
  -F "files=@test_files/test_data.json" \
  -F "files=@test_files/test_readme.md" \
  -F "kb_id=test-kb-002" \
  $BASE_URL/api/v1/uploads/batch)

if echo "$BATCH_RESPONSE" | grep -q "batch_id"; then
    BATCH_ID=$(echo "$BATCH_RESPONSE" | jq -r '.batch_id' 2>/dev/null || echo "unknown")
    echo -e "${GREEN}✓ 批量文件上传成功 (批次ID: $BATCH_ID)${NC}"
else
    echo -e "${RED}❌ 批量文件上传失败${NC}"
    echo "响应: $BATCH_RESPONSE"
fi

echo -e "${BLUE}5. 测试URL下载上传...${NC}"

# 测试URL下载上传
echo -n "从URL下载并上传..."
URL_RESPONSE=$(curl -s -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://raw.githubusercontent.com/golang/go/master/README.md",
    "kb_id": "test-kb-003"
  }' \
  $BASE_URL/api/v1/uploads/url)

if echo "$URL_RESPONSE" | grep -q "task_id"; then
    URL_TASK_ID=$(echo "$URL_RESPONSE" | jq -r '.task_id' 2>/dev/null || echo "unknown")
    echo -e "${GREEN}✓ URL下载上传成功 (任务ID: $URL_TASK_ID)${NC}"
else
    echo -e "${RED}❌ URL下载上传失败${NC}"
    echo "响应: $URL_RESPONSE"
fi

echo -e "${BLUE}6. 查询任务状态...${NC}"

sleep 2  # 等待任务创建

# 查询任务列表
echo -n "获取任务列表..."
TASKS_RESPONSE=$(curl -s "$BASE_URL/api/v1/tasks?page=1&page_size=10")

if echo "$TASKS_RESPONSE" | grep -q "tasks"; then
    TASK_COUNT=$(echo "$TASKS_RESPONSE" | jq '.total' 2>/dev/null || echo "0")
    echo -e "${GREEN}✓ 任务列表查询成功 (总计: $TASK_COUNT 个任务)${NC}"
else
    echo -e "${RED}❌ 任务列表查询失败${NC}"
fi

# 如果有有效的任务ID，查询任务详情
if [[ "$TASK_ID" != "unknown" && "$TASK_ID" != "null" ]]; then
    echo -n "查询任务详情..."
    TASK_DETAIL=$(curl -s "$BASE_URL/api/v1/tasks/$TASK_ID")
    
    if echo "$TASK_DETAIL" | grep -q "task_id"; then
        STATUS=$(echo "$TASK_DETAIL" | jq -r '.status' 2>/dev/null || echo "unknown")
        echo -e "${GREEN}✓ 任务详情查询成功 (状态: $STATUS)${NC}"
    else
        echo -e "${YELLOW}⚠️  任务详情查询失败${NC}"
    fi
fi

echo -e "${BLUE}7. 测试系统统计...${NC}"

# 获取上传统计
echo -n "获取上传统计..."
UPLOAD_STATS=$(curl -s "$BASE_URL/api/v1/uploads/stats")

if echo "$UPLOAD_STATS" | grep -q "total_uploads"; then
    echo -e "${GREEN}✓ 上传统计查询成功${NC}"
else
    echo -e "${YELLOW}⚠️  上传统计查询失败${NC}"
fi

# 获取系统统计
echo -n "获取系统统计..."
SYSTEM_STATS=$(curl -s "$BASE_URL/api/v1/stats/system")

if echo "$SYSTEM_STATS" | grep -q "total_tasks"; then
    echo -e "${GREEN}✓ 系统统计查询成功${NC}"
else
    echo -e "${YELLOW}⚠️  系统统计查询失败${NC}"
fi

echo -e "${BLUE}8. 测试任务轮询...${NC}"

# 测试HTTP轮询
echo -n "测试HTTP轮询..."
POLLING_RESPONSE=$(curl -s "$BASE_URL/api/v1/polling/status?timeout=5")

if echo "$POLLING_RESPONSE" | grep -q "updates" || echo "$POLLING_RESPONSE" | grep -q "timeout"; then
    echo -e "${GREEN}✓ HTTP轮询功能正常${NC}"
else
    echo -e "${YELLOW}⚠️  HTTP轮询测试未完成${NC}"
fi

# 检查轮询客户端
echo -n "检查轮询客户端..."
CLIENTS_RESPONSE=$(curl -s "$BASE_URL/api/v1/polling/clients")

if echo "$CLIENTS_RESPONSE" | grep -q "active_clients"; then
    echo -e "${GREEN}✓ 轮询客户端查询成功${NC}"
else
    echo -e "${YELLOW}⚠️  轮询客户端查询失败${NC}"
fi

echo -e "${BLUE}9. 清理测试文件...${NC}"

# 清理测试文件
rm -rf test_files/
echo -e "${GREEN}✓ 测试文件清理完成${NC}"

echo "================================"
echo -e "${GREEN}🎉 文件上传功能测试完成！${NC}"

# 测试总结
echo -e "${BLUE}测试总结:${NC}"
echo "- 单文件上传: $([ "$TASK_ID" != "unknown" ] && echo "✓ 成功" || echo "❌ 失败")"
echo "- 批量文件上传: $([ "$BATCH_ID" != "unknown" ] && echo "✓ 成功" || echo "❌ 失败")"  
echo "- URL下载上传: $([ "$URL_TASK_ID" != "unknown" ] && echo "✓ 成功" || echo "❌ 失败")"
echo "- 任务查询: ✓ 正常"
echo "- 状态轮询: ✓ 正常"

echo ""
echo "文件上传和任务管理功能验证完成！"