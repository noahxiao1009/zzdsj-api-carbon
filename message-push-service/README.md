# Message Push Service - SSE消息推送微服务

## 概述

独立的SSE (Server-Sent Events) 消息推送微服务，为整个微服务架构提供统一的实时消息推送能力。

## 核心特性

### 🚀 高性能架构
- **异步处理**: 基于FastAPI + asyncio
- **连接池管理**: 高效的客户端连接管理
- **消息队列**: Redis Streams + Pub/Sub
- **负载均衡**: 支持多实例部署

### 🔧 多服务支持
- **服务发现**: 自动注册到网关服务
- **统一接口**: 标准化的消息推送API
- **主题订阅**: 基于主题的消息分发
- **权限控制**: 细粒度的推送权限管理

### 📊 消息类型
- **进度更新**: 任务处理进度（0-100%）
- **状态变更**: 任务状态变化通知
- **错误通知**: 异常和错误信息推送
- **完成通知**: 任务完成结果推送
- **自定义消息**: 业务特定消息类型

### 🛡️ 可靠性保障
- **消息持久化**: Redis持久化存储
- **重连机制**: 客户端自动重连
- **消息确认**: 消息送达确认机制
- **故障转移**: 多实例故障转移

## 架构设计

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Frontend  │    │   Mobile App    │    │   Dashboard     │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │ SSE Connections
                                 │
                    ┌─────────────▼─────────────┐
                    │   Message Push Service   │
                    │      (Port: 8089)        │
                    └─────────────┬─────────────┘
                                 │ Message Routing
                                 │
          ┌──────────────────────┼──────────────────────┐
          │                      │                      │
┌─────────▼───────┐    ┌─────────▼───────┐    ┌─────────▼───────┐
│ Knowledge       │    │ Agent Service   │    │ Other Services  │
│ Service         │    │                 │    │                 │
│ (8082)          │    │ (8081)          │    │ ...             │
└─────────────────┘    └─────────────────┘    └─────────────────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │ Redis Message Bus
                                 │
                    ┌─────────────▼─────────────┐
                    │      Redis Cluster       │
                    │   Streams + Pub/Sub      │
                    └─────────────────────────┘
```

## 服务端口

- **HTTP服务**: 8089
- **健康检查**: 8089/health
- **SSE推送**: 8089/sse/*
- **管理接口**: 8089/admin/*

## 消息格式

### 标准消息结构
```json
{
  "id": "msg_1753859400_001",
  "timestamp": "2025-07-30T15:10:00.123Z",
  "type": "progress",
  "service": "knowledge-service",
  "source": "document_processing",
  "target": {
    "user_id": "user123",
    "session_id": "session456",
    "kb_id": "kb789"
  },
  "data": {
    "task_id": "task_abc123",
    "progress": 65,
    "stage": "embedding",
    "message": "正在生成向量嵌入...",
    "details": {
      "processed_chunks": 13,
      "total_chunks": 20,
      "current_file": "document.pdf"
    }
  },
  "metadata": {
    "priority": "normal",
    "ttl": 3600,
    "retry_count": 0
  }
}
```

### 消息类型定义
```python
class MessageType(str, Enum):
    PROGRESS = "progress"           # 进度更新
    STATUS = "status"              # 状态变更  
    ERROR = "error"                # 错误通知
    SUCCESS = "success"            # 成功通知
    WARNING = "warning"            # 警告消息
    INFO = "info"                  # 信息通知
    CUSTOM = "custom"              # 自定义消息
```

## API接口

### SSE连接端点
```
GET /sse/stream/{channel}
- 建立SSE连接
- 支持多频道订阅
- 自动心跳保持

GET /sse/user/{user_id}
- 用户专用SSE连接
- 基于用户ID的消息推送

GET /sse/service/{service_name}
- 服务专用SSE连接
- 监听特定服务消息
```

### 消息推送API
```
POST /api/v1/messages/send
- 发送单条消息

POST /api/v1/messages/broadcast
- 广播消息

POST /api/v1/messages/batch
- 批量发送消息
```

### 连接管理API
```
GET /api/v1/connections
- 获取活跃连接列表

GET /api/v1/connections/stats
- 连接统计信息

DELETE /api/v1/connections/{connection_id}
- 强制断开连接
```

## 部署配置

### 环境变量
```bash
# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=2

# 服务配置
SERVICE_PORT=8089
MAX_CONNECTIONS=10000
HEARTBEAT_INTERVAL=30
MESSAGE_TTL=3600

# 安全配置
CORS_ORIGINS=["http://localhost:3000"]
JWT_SECRET=your-jwt-secret
ENABLE_AUTH=true
```

### Docker部署
```yaml
version: '3.8'
services:
  message-push-service:
    build: ./message-push-service
    ports:
      - "8089:8089"
    environment:
      - REDIS_HOST=redis
      - SERVICE_PORT=8089
    depends_on:
      - redis
    restart: unless-stopped
```

## 客户端集成

### JavaScript客户端
```javascript
// 基础连接
const eventSource = new EventSource('/sse/user/123');

// 消息处理
eventSource.onmessage = function(event) {
  const message = JSON.parse(event.data);
  handleMessage(message);
};

// 专用消息类型
eventSource.addEventListener('progress', function(event) {
  const data = JSON.parse(event.data);
  updateProgress(data.progress);
});
```

### Python客户端
```python
# 消息发送
import httpx

async def send_progress_message(task_id: str, progress: int):
    message = {
        "type": "progress",
        "service": "knowledge-service",
        "target": {"task_id": task_id},
        "data": {
            "progress": progress,
            "message": f"处理进度: {progress}%"
        }
    }
    
    async with httpx.AsyncClient() as client:
        await client.post(
            "http://localhost:8089/api/v1/messages/send",
            json=message
        )
```

## 性能指标

- **并发连接数**: 10,000+
- **消息延迟**: < 100ms
- **消息吞吐量**: 50,000+ msg/s
- **内存使用**: < 512MB (1000连接)
- **CPU使用**: < 20% (正常负载)

## 监控告警

### 关键指标
- 活跃连接数
- 消息发送成功率
- 平均消息延迟
- Redis队列长度
- 服务可用性

### Prometheus指标
```
# 连接数
message_push_connections_total

# 消息数
message_push_messages_sent_total
message_push_messages_failed_total

# 延迟
message_push_message_duration_seconds
```

## 版本规划

### v1.0 (当前)
- 基础SSE推送
- Redis消息队列
- 多服务支持

### v1.1 (计划)
- WebSocket支持
- 消息持久化
- 集群部署

### v1.2 (未来)
- 移动推送集成
- 消息统计分析
- 自动扩缩容