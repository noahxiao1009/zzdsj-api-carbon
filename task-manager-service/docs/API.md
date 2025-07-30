# 任务管理服务 API 文档

## 📋 API 概览

**Base URL**: `http://localhost:8084`

**Content-Type**: `application/json`

**认证**: 暂无 (后续可添加API Key认证)

## 🔗 核心接口

### 1. 健康检查

**获取服务健康状态**

```http
GET /health
```

**响应示例**:
```json
{
  "status": "healthy",
  "service": "task-manager",
  "version": "1.0.0",
  "details": {
    "database": {"status": "healthy"},
    "redis": {"status": "healthy", "size": 0},
    "queue": {"status": "healthy"}
  }
}
```

### 2. 监控指标

**获取Prometheus指标**

```http
GET /metrics
```

## 📋 任务管理接口

### 1. 创建任务

**提交新任务到队列**

```http
POST /api/v1/tasks
```

**请求体**:
```json
{
  "task_type": "document_processing",
  "kb_id": "kb_123456",
  "priority": "high",
  "payload": {
    "file_path": "/tmp/uploads/document.pdf",
    "chunk_size": 1000,
    "chunk_overlap": 200
  },
  "max_retries": 3,
  "timeout": 300,
  "schedule_for": "2025-07-28T14:30:00Z"
}
```

**参数说明**:
- `task_type` (必需): 任务类型
  - `document_processing`: 文档处理
  - `batch_processing`: 批量处理  
  - `knowledge_indexing`: 知识索引
  - `embedding_generation`: 嵌入生成
  - `vector_storage`: 向量存储
  - `health_check`: 健康检查
- `kb_id` (必需): 知识库ID
- `priority` (可选): 优先级 (`low`, `normal`, `high`, `critical`)
- `payload` (必需): 任务数据
- `max_retries` (可选): 最大重试次数，默认3
- `timeout` (可选): 超时时间(秒)，默认300
- `schedule_for` (可选): 延迟执行时间

**响应示例**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "task_type": "document_processing",
  "status": "queued",
  "priority": "high",
  "kb_id": "kb_123456",
  "payload": {...},
  "progress": 0,
  "retry_count": 0,
  "max_retries": 3,
  "created_at": "2025-07-28T14:20:00Z",
  "estimated_completion": "2025-07-28T14:25:00Z",
  "queue_position": 1
}
```

### 2. 获取任务详情

**查询单个任务的详细信息**

```http
GET /api/v1/tasks/{task_id}
```

**响应示例**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "task_type": "document_processing",
  "status": "processing",
  "priority": "high",
  "kb_id": "kb_123456",
  "payload": {...},
  "result": {...},
  "progress": 65,
  "retry_count": 0,
  "max_retries": 3,
  "error_message": "",
  "worker_id": "worker_001",
  "created_at": "2025-07-28T14:20:00Z",
  "updated_at": "2025-07-28T14:21:30Z",
  "started_at": "2025-07-28T14:20:05Z",
  "estimated_completion": "2025-07-28T14:22:00Z",
  "queue_position": 0
}
```

### 3. 获取任务列表

**查询任务列表，支持过滤和分页**

```http
GET /api/v1/tasks?kb_id=kb_123&status=processing&page=1&page_size=20
```

**查询参数**:
- `kb_id` (可选): 按知识库ID过滤
- `status` (可选): 按状态过滤
- `task_type` (可选): 按任务类型过滤
- `priority` (可选): 按优先级过滤
- `page` (可选): 页码，默认1
- `page_size` (可选): 每页大小，默认20，最大100
- `sort_by` (可选): 排序字段
- `sort_order` (可选): 排序方向 (`asc`, `desc`)

**响应示例**:
```json
{
  "tasks": [...],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 156,
    "total_pages": 8
  }
}
```

### 4. 取消任务

**取消排队中或处理中的任务**

```http
DELETE /api/v1/tasks/{task_id}
```

**响应示例**:
```json
{
  "message": "Task canceled successfully",
  "task_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### 5. 重试任务

**重新执行失败的任务**

```http
POST /api/v1/tasks/{task_id}/retry
```

**响应**: 返回更新后的任务信息

### 6. 更新任务进度

**更新任务执行进度 (通常由Worker调用)**

```http
PUT /api/v1/tasks/{task_id}/progress
```

**请求体**:
```json
{
  "progress": 75,
  "message": "Processing embeddings..."
}
```

### 7. 批量创建任务

**一次性提交多个任务**

```http
POST /api/v1/tasks/batch
```

**请求体**:
```json
[
  {
    "task_type": "document_processing",
    "kb_id": "kb_001",
    "payload": {...}
  },
  {
    "task_type": "embedding_generation", 
    "kb_id": "kb_001",
    "payload": {...}
  }
]
```

**响应示例**:
```json
{
  "tasks": [...],
  "count": 2
}
```

## 📊 统计接口

### 1. 任务统计

**获取任务统计信息**

```http
GET /api/v1/stats/tasks?kb_id=kb_123
```

**响应示例**:
```json
{
  "total_tasks": 1250,
  "queued_tasks": 45,
  "processing_tasks": 12,
  "completed_tasks": 1180,
  "failed_tasks": 13,
  "avg_process_time": 45.6,
  "success_rate": 94.4,
  "status_breakdown": {
    "queued": 45,
    "processing": 12,
    "completed": 1180,
    "failed": 13
  },
  "type_breakdown": {
    "document_processing": 800,
    "embedding_generation": 350,
    "knowledge_indexing": 100
  }
}
```

### 2. 系统统计

**获取系统整体统计信息**

```http
GET /api/v1/stats/system
```

**响应示例**:
```json
{
  "total_workers": 10,
  "active_workers": 8,
  "idle_workers": 2,
  "busy_workers": 6,
  "queue_size": 45,
  "processing_rate": 125.5,
  "workers": [
    {
      "id": "worker_001",
      "status": "busy",
      "current_task_id": "task_123",
      "tasks_processed": 156,
      "tasks_succeeded": 148,
      "tasks_failed": 8,
      "last_heartbeat": "2025-07-28T14:20:00Z",
      "started_at": "2025-07-28T10:00:00Z",
      "average_task_time": 42.3
    }
  ],
  "task_stats": {...}
}
```

## 🔍 队列接口

### 1. 获取队列信息

**查看队列状态**

```http
GET /api/v1/queues/info?task_type=document_processing&priority=high
```

**响应示例**:
```json
{
  "queue_size": 25,
  "queue_key": "task_queue:high"
}
```

## 🚨 错误处理

### HTTP状态码

- `200` - 成功
- `201` - 创建成功  
- `400` - 请求参数错误
- `404` - 资源不存在
- `409` - 操作冲突 (如取消已完成的任务)
- `500` - 服务器内部错误
- `503` - 服务不可用

### 错误响应格式

```json
{
  "error": "Task not found",
  "message": "Task with specified ID does not exist",
  "code": "TASK_NOT_FOUND",
  "details": {
    "task_id": "invalid_id"
  }
}
```

### 常见错误码

- `INVALID_REQUEST` - 请求参数无效
- `TASK_NOT_FOUND` - 任务不存在  
- `TASK_NOT_CANCELABLE` - 任务无法取消
- `TASK_NOT_RETRYABLE` - 任务无法重试
- `QUEUE_FULL` - 队列已满
- `SERVICE_UNAVAILABLE` - 服务不可用

## 📝 使用示例

### 文档处理流程

```bash
# 1. 提交文档处理任务
TASK_ID=$(curl -s -X POST http://localhost:8084/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "document_processing",
    "kb_id": "kb_demo_001", 
    "priority": "high",
    "payload": {
      "file_path": "/tmp/uploads/report.pdf",
      "chunk_size": 1000
    }
  }' | jq -r '.id')

echo "Task ID: $TASK_ID"

# 2. 轮询任务状态
while true; do
  STATUS=$(curl -s http://localhost:8084/api/v1/tasks/$TASK_ID | jq -r '.status')
  PROGRESS=$(curl -s http://localhost:8084/api/v1/tasks/$TASK_ID | jq -r '.progress')
  
  echo "Status: $STATUS, Progress: $PROGRESS%"
  
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    break
  fi
  
  sleep 2
done

# 3. 获取处理结果
curl -s http://localhost:8084/api/v1/tasks/$TASK_ID | jq '.result'
```

### 批量任务处理

```bash
# 批量提交多个文档处理任务
curl -X POST http://localhost:8084/api/v1/tasks/batch \
  -H "Content-Type: application/json" \
  -d '[
    {
      "task_type": "document_processing",
      "kb_id": "kb_001",
      "payload": {"file_path": "/tmp/doc1.pdf"}
    },
    {
      "task_type": "document_processing", 
      "kb_id": "kb_001",
      "payload": {"file_path": "/tmp/doc2.pdf"}
    }
  ]'
```

### 监控和统计

```bash
# 获取实时统计
curl -s http://localhost:8084/api/v1/stats/system | jq '{
  workers: .total_workers,
  queue: .queue_size,
  rate: .processing_rate
}'

# 获取特定知识库的任务统计
curl -s "http://localhost:8084/api/v1/stats/tasks?kb_id=kb_001" | jq '{
  total: .total_tasks,
  success_rate: .success_rate,
  avg_time: .avg_process_time
}'
```

## 🔐 认证授权 (规划中)

未来版本将支持：

- API Key认证
- JWT Token认证  
- 基于角色的访问控制
- 请求频率限制

## 📈 性能说明

- **并发处理**: 最大50个并发任务
- **吞吐量**: 100+ tasks/second
- **响应时间**: API响应 < 50ms
- **任务延迟**: 队列延迟 < 1秒
- **可靠性**: 99.9% 任务成功率