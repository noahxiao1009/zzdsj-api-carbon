# 任务管理服务 (Task Manager Service)

## 服务概述

独立的Golang任务管理服务，专门处理知识库相关的异步任务，与主API服务完全解耦。

## 架构设计

### 核心组件
```
┌─────────────────────────────────────────────────────────────┐
│                    Task Manager Service                     │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   API层     │  │  任务调度器  │  │     工作进程池      │  │
│  │ (REST/gRPC) │  │ (Scheduler) │  │   (Worker Pool)     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  队列管理   │  │  任务存储   │  │    监控&日志        │  │
│  │ (Redis)     │  │(PostgreSQL)│  │   (Metrics)         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 服务职责

#### 1. 任务队列管理
- 接收来自API服务的任务请求
- 任务优先级排序和调度
- 失败任务重试机制
- 任务状态追踪

#### 2. 文档处理流水线
```
文档上传 → 预处理 → 分块 → 向量化 → 存储 → 索引更新
    ↓         ↓       ↓       ↓        ↓        ↓
  验证      格式转换   智能切分  嵌入生成  入库    搜索准备
```

#### 3. 并发处理
- Goroutine池管理
- 任务并发控制
- 资源限制和背压
- 优雅关闭

### 技术栈

#### Golang核心库
- **Web框架**: Gin/Echo (轻量级API)
- **数据库**: `database/sql` + `lib/pq` (PostgreSQL)
- **Redis**: `go-redis/redis`
- **配置管理**: Viper
- **日志**: Logrus/Zap
- **监控**: Prometheus + Grafana

#### 任务处理
- **并发**: Goroutines + Channels  
- **队列**: Redis Streams / RabbitMQ
- **重试**: 指数退避算法
- **限流**: Token Bucket

## 服务接口设计

### 1. 任务提交API
```go
POST /api/v1/tasks
{
    "task_type": "document_processing",
    "kb_id": "kb_123",
    "payload": {
        "file_path": "/tmp/uploads/doc.pdf",
        "chunk_size": 1000,
        "chunk_overlap": 200
    },
    "priority": "high",
    "retry_limit": 3
}

Response:
{
    "task_id": "task_456",
    "status": "queued",
    "created_at": "2025-07-28T14:20:00Z"
}
```

### 2. 任务状态查询
```go
GET /api/v1/tasks/{task_id}

Response:
{
    "task_id": "task_456",
    "status": "processing", // queued, processing, completed, failed
    "progress": 65,
    "started_at": "2025-07-28T14:20:05Z",
    "estimated_completion": "2025-07-28T14:22:00Z",
    "result": null
}
```

### 3. 批量任务管理
```go
POST /api/v1/tasks/batch
GET /api/v1/tasks?kb_id=kb_123&status=processing
DELETE /api/v1/tasks/{task_id}
```

### 4. 健康检查和监控
```go
GET /health
GET /metrics
GET /api/v1/stats/workers
GET /api/v1/stats/queues
```

## 部署配置

### Docker配置
```dockerfile
FROM golang:1.21-alpine AS builder
WORKDIR /app
COPY . .
RUN go mod download
RUN CGO_ENABLED=0 GOOS=linux go build -o task-manager ./cmd/server

FROM alpine:latest
RUN apk --no-cache add ca-certificates
WORKDIR /root/
COPY --from=builder /app/task-manager .
EXPOSE 8084
CMD ["./task-manager"]
```

### 环境变量
```env
# 服务配置
PORT=8084
LOG_LEVEL=info
ENVIRONMENT=production

# 数据库配置
POSTGRES_HOST=localhost
POSTGRES_PORT=5434
POSTGRES_DB=zzdsj_demo
POSTGRES_USER=zzdsj_demo
POSTGRES_PASSWORD=zzdsj123

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=1

# 工作进程配置
WORKER_POOL_SIZE=10
MAX_CONCURRENT_TASKS=50
TASK_TIMEOUT=300

# 重试配置
MAX_RETRY_ATTEMPTS=3
RETRY_BACKOFF_FACTOR=2
```

## 性能特性

### 并发处理能力
- **工作进程**: 10-50个Goroutine
- **任务吞吐**: 100+ tasks/second
- **内存使用**: < 100MB
- **启动时间**: < 2秒

### 可靠性保证
- **任务持久化**: PostgreSQL事务保证
- **失败重试**: 指数退避 + 死信队列
- **优雅关闭**: 等待任务完成或超时
- **健康检查**: 自动故障检测

### 监控指标
```go
// Prometheus指标
task_queue_size{queue="document_processing"}
task_processing_duration_seconds{task_type="chunking"}
task_success_total{task_type="embedding"}
task_failure_total{task_type="vectorization"}
worker_pool_active_count
worker_pool_idle_count
```

## 与知识库服务集成

### 1. 服务间通信
```go
// 知识库服务调用任务服务
func (s *KnowledgeService) ProcessDocument(kbID, filePath string) {
    taskRequest := TaskRequest{
        TaskType: "document_processing",
        KbID:     kbID,
        Payload: map[string]interface{}{
            "file_path": filePath,
            "chunk_size": 1000,
        },
    }
    
    // 调用任务服务
    taskID, err := s.taskClient.SubmitTask(taskRequest)
    if err != nil {
        return err
    }
    
    // 返回任务ID给前端
    return taskID
}
```

### 2. 任务状态同步
```go
// 任务完成后回调知识库服务
func (w *Worker) OnTaskComplete(task *Task) {
    if task.TaskType == "document_processing" {
        // 更新知识库状态
        callback := CallbackRequest{
            KbID: task.KbID,
            Status: "completed",
            Result: task.Result,
        }
        
        w.knowledgeClient.UpdateKnowledgeBase(callback)
    }
}
```

### 3. 错误处理和恢复
```go
func (w *Worker) HandleFailedTask(task *Task, err error) {
    if task.RetryCount < task.MaxRetries {
        // 重新入队
        w.queue.Requeue(task, calculateBackoff(task.RetryCount))
    } else {
        // 标记为失败，通知知识库服务
        w.knowledgeClient.NotifyTaskFailed(task.ID, err)
    }
}
```

## 开发和测试

### 快速启动
```bash
# 克隆代码
git clone <task-manager-repo>
cd task-manager-service

# 启动依赖服务
docker-compose up -d postgres redis

# 运行服务
go run cmd/server/main.go

# 测试API
curl -X POST http://localhost:8084/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{"task_type":"test","payload":{"message":"hello"}}'
```

### 性能测试
```bash
# 并发任务提交测试
hey -n 1000 -c 10 -m POST \
  -H "Content-Type: application/json" \
  -d '{"task_type":"benchmark","payload":{}}' \
  http://localhost:8084/api/v1/tasks
```

## 扩展计划

### Phase 1: 基础功能 (当前)
- ✅ 任务队列管理
- ✅ 基础工作进程
- ✅ PostgreSQL集成
- ✅ REST API

### Phase 2: 高级特性
- 🔄 任务优先级队列
- 🔄 分布式任务锁
- 🔄 任务依赖管理
- 🔄 实时任务监控

### Phase 3: 生产特性
- ⏳ 集群部署支持
- ⏳ 任务分片处理
- ⏳ 自动扩缩容
- ⏳ 故障转移机制

## 总结

独立的Golang任务管理服务能够：

1. **解决性能问题**: API服务专注响应，任务服务专注处理
2. **提高可靠性**: 服务隔离，故障不互相影响  
3. **便于扩展**: 独立部署，按需扩容
4. **优化资源**: Golang高并发处理能力
5. **简化运维**: 独立监控和日志管理

这是解决当前任务轮询问题的最佳方案！