# Message Push Service 部署指南

## 概述

Message Push Service 是ZZDSJ智政科技AI智能办公助手微服务架构中的SSE消息推送微服务，为整个系统提供统一的实时消息推送能力。

## 服务信息

- **服务名称**: message-push-service
- **默认端口**: 8089
- **协议**: HTTP/SSE (Server-Sent Events)
- **依赖**: Redis, Python 3.11+

## 部署方式

### 1. 快速启动 (开发环境)

```bash
# 进入服务目录
cd /Users/wxn/Desktop/carbon/zzdsl-api-carbon/message-push-service

# 启动服务 (开发模式)
./scripts/start.sh --development

# 或者使用Python直接启动
python main.py
```

### 2. PM2 部署 (推荐)

```bash
# 使用PM2启动
./scripts/start.sh --pm2

# 或者直接使用PM2
pm2 start ecosystem.config.js --env production

# 查看服务状态
pm2 status message-push-service

# 查看日志
pm2 logs message-push-service
```

### 3. Docker 部署

```bash
# 构建并启动服务
docker-compose up -d

# 仅启动核心服务
docker-compose up -d message-push-service redis

# 查看容器状态
docker-compose ps

# 查看日志
docker-compose logs -f message-push-service
```

### 4. 完整自动化部署

```bash
# 完整部署脚本 (PM2模式)
./scripts/deploy.sh --env production --pm2

# Docker部署模式
./scripts/deploy.sh --env production --docker

# 包含Nginx反向代理
./scripts/deploy.sh --env production --pm2 --with-nginx
```

## 环境配置

### 开发环境

复制并编辑开发环境配置：
```bash
cp config/development.env.example config/development.env
# 根据需要修改配置参数
```

### 生产环境

复制并编辑生产环境配置：
```bash
cp config/production.env.example config/production.env
# 重要：修改以下配置项
# - REDIS_PASSWORD: Redis密码
# - ALLOWED_ORIGINS: 允许的域名
# - 其他安全相关配置
```

## 核心配置参数

### 服务配置
```bash
SERVICE_NAME=message-push-service
SERVICE_PORT=8089
SERVICE_VERSION=1.0.0
ENVIRONMENT=production
```

### Redis配置
```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=5
REDIS_PASSWORD=your_secure_password
REDIS_MAX_CONNECTIONS=50
```

### 性能配置
```bash
MAX_CONNECTIONS=1000
CONNECTION_TIMEOUT=300
HEARTBEAT_INTERVAL=30
MESSAGE_QUEUE_SIZE=10000
```

### 安全配置
```bash
ALLOWED_ORIGINS=https://yourdomain.com
CORS_CREDENTIALS=true
RATE_LIMIT_PER_MINUTE=1000
```

## 服务管理

### 状态检查
```bash
# 完整状态检查
./scripts/status.sh

# 仅健康检查
./scripts/status.sh --health

# 查看最近日志
./scripts/status.sh --logs
```

### 服务控制
```bash
# 停止服务
./scripts/stop.sh

# 强制停止
./scripts/stop.sh --force

# 停止并清理资源
./scripts/stop.sh --clean
```

### 日志管理
```bash
# 查看实时日志
tail -f logs/message-push-service.log

# PM2日志
pm2 logs message-push-service

# Docker日志
docker-compose logs -f message-push-service
```

## 反向代理配置

### Nginx配置

服务提供了完整的Nginx配置文件 `config/nginx.conf`，包含：

- SSE长连接优化
- 负载均衡配置
- SSL/TLS支持
- 健康检查

```nginx
# 关键SSE配置
location /sse/ {
    proxy_pass http://message_push_backend;
    proxy_set_header Connection '';
    proxy_http_version 1.1;
    chunked_transfer_encoding off;
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 86400s; # 24小时长连接
}
```

### 负载均衡

对于高可用部署，可以配置多个服务实例：

```nginx
upstream message_push_backend {
    least_conn;
    server message-push-service-1:8089;
    server message-push-service-2:8089;
    server message-push-service-3:8089;
    keepalive 32;
}
```

## 监控和告警

### Prometheus监控

服务内置Prometheus指标支持：

```bash
# 启用监控
ENABLE_METRICS=true
METRICS_PORT=9090

# 访问指标
curl http://localhost:9090/sse/metrics
```

### 健康检查端点

```bash
# 基础健康检查
curl http://localhost:8089/sse/health

# 详细状态信息
curl http://localhost:8089/sse/api/v1/connections/stats
```

### 日志监控

关键日志指标：
- 连接建立/断开
- 消息发送成功/失败
- Redis连接状态
- 内存使用情况

## 性能优化

### Redis优化

```bash
# Redis配置优化
maxmemory 256mb
maxmemory-policy allkeys-lru
notify-keyspace-events Ex
client-output-buffer-limit pubsub 32mb 8mb 60
```

### 系统级优化

```bash
# 增加文件描述符限制
ulimit -n 65536

# 内核参数优化
echo 'net.core.somaxconn = 65535' >> /etc/sysctl.conf
echo 'net.ipv4.tcp_max_syn_backlog = 65535' >> /etc/sysctl.conf
sysctl -p
```

### 应用层优化

```python
# 连接池配置
MAX_CONNECTIONS=1000
CONNECTION_TIMEOUT=300
MESSAGE_QUEUE_SIZE=10000

# 异步处理
WORKER_THREADS=4
ENABLE_ASYNC_PROCESSING=true
```

## 安全配置

### HTTPS/SSL

```bash
# 启用SSL
ENABLE_SSL=true
SSL_CERT_PATH=/app/ssl/cert.pem
SSL_KEY_PATH=/app/ssl/key.pem
```

### 访问控制

```bash
# CORS配置
ALLOWED_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
CORS_CREDENTIALS=true

# 速率限制
RATE_LIMIT_PER_MINUTE=1000
ENABLE_RATE_LIMITING=true
```

### API密钥认证

```bash
# 启用API密钥
ENABLE_API_KEY_AUTH=true
API_KEY=your_secure_api_key_here
```

## 故障排除

### 常见问题

1. **端口占用**
   ```bash
   # 检查端口占用
   lsof -i :8089
   # 停止占用进程
   ./scripts/stop.sh --force
   ```

2. **Redis连接失败**
   ```bash
   # 检查Redis状态
   redis-cli ping
   # 启动Redis
   redis-server --daemonize yes
   ```

3. **内存不足**
   ```bash
   # 检查内存使用
   free -h
   # 调整配置
   MAX_CONNECTIONS=500
   MESSAGE_QUEUE_SIZE=5000
   ```

4. **SSE连接断开**
   - 检查Nginx配置
   - 验证防火墙设置
   - 检查客户端网络

### 调试模式

```bash
# 启用调试日志
LOG_LEVEL=DEBUG
DEBUG=true

# 查看详细日志
./scripts/status.sh --logs
```

### 性能调试

```bash
# 启用性能分析
PROFILING=true
ENABLE_TRACING=true

# 查看性能指标
curl http://localhost:9090/sse/metrics
```

## 升级和维护

### 版本升级

```bash
# 备份当前版本
cp -r . ../message-push-service-backup

# 停止服务
./scripts/stop.sh

# 更新代码
git pull origin main

# 更新依赖
pip install -r requirements.txt

# 重新部署
./scripts/deploy.sh --env production --pm2
```

### 定期维护

```bash
# 日志轮转
logrotate /etc/logrotate.d/message-push-service

# 清理旧日志
find logs/ -name "*.log.*" -mtime +7 -delete

# 数据库优化
redis-cli BGSAVE
```

## API使用示例

### JavaScript客户端

```javascript
// 建立SSE连接
const eventSource = new EventSource('http://localhost:8089/sse/user/123');

// 监听进度消息
eventSource.addEventListener('progress', function(event) {
    const data = JSON.parse(event.data);
    console.log('Progress:', data.data.progress + '%');
});

// 监听错误消息
eventSource.addEventListener('error', function(event) {
    const data = JSON.parse(event.data);
    console.error('Error:', data.data.error_message);
});

// 连接状态监听
eventSource.onopen = function(event) {
    console.log('Connection opened');
};

eventSource.onerror = function(event) {
    console.log('Connection error:', event);
};
```

### 服务端发送消息

```python
import httpx
import asyncio

async def send_progress_message(user_id: str, task_id: str, progress: int):
    message = {
        "type": "progress",
        "service": "knowledge-service",
        "source": "document_processing",
        "target": {"user_id": user_id, "task_id": task_id},
        "data": {
            "task_id": task_id,
            "progress": progress,
            "stage": "processing",
            "message": f"处理进度: {progress}%"
        }
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8089/sse/api/v1/messages/send",
            json=message
        )
        return response.json()

# 使用示例
async def main():
    result = await send_progress_message("user_123", "task_456", 50)
    print(f"Message sent: {result}")

asyncio.run(main())
```

## 集成指南

### 与知识库服务集成

```python
# 在知识库服务中集成消息推送
from shared.service_client import call_service, CallMethod

async def send_processing_update(user_id: str, task_id: str, progress: int):
    message = {
        "type": "progress",
        "service": "knowledge-service",
        "target": {"user_id": user_id},
        "data": {
            "task_id": task_id,
            "progress": progress,
            "stage": "vectorization",
            "message": f"向量化进度: {progress}%"
        }
    }
    
    return await call_service(
        service_name="message-push-service",
        method=CallMethod.POST,
        path="/sse/api/v1/messages/send",
        json=message
    )
```

### 前端React Hook集成

```typescript
// useSSEConnection Hook
import { useState, useEffect, useCallback } from 'react';

interface UseSSEConnectionOptions {
  userId: string;
  messageServiceUrl: string;
  onMessage?: (message: any) => void;
}

export const useSSEConnection = (options: UseSSEConnectionOptions) => {
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [messages, setMessages] = useState<any[]>([]);

  useEffect(() => {
    const eventSource = new EventSource(
      `${options.messageServiceUrl}/sse/user/${options.userId}`
    );

    eventSource.onopen = () => {
      setConnectionStatus('connected');
    };

    eventSource.onmessage = (event) => {
      const message = JSON.parse(event.data);
      setMessages(prev => [...prev, message]);
      options.onMessage?.(message);
    };

    eventSource.onerror = () => {
      setConnectionStatus('error');
    };

    return () => {
      eventSource.close();
      setConnectionStatus('disconnected');
    };
  }, [options.userId, options.messageServiceUrl]);

  return { connectionStatus, messages };
};
```

## 支持和联系

- **项目文档**: `/docs`
- **API文档**: `http://localhost:8089/docs`
- **健康检查**: `http://localhost:8089/sse/health`
- **状态监控**: `./scripts/status.sh`

---

## 附录

### 目录结构
```
message-push-service/
├── app/                    # 应用代码
│   ├── api/               # API路由
│   ├── core/              # 核心功能
│   ├── models/            # 数据模型
│   └── utils/             # 工具函数
├── config/                # 配置文件
│   ├── development.env    # 开发环境配置
│   ├── production.env     # 生产环境配置
│   ├── nginx.conf         # Nginx配置
│   ├── redis.conf         # Redis配置
│   └── prometheus.yml     # 监控配置
├── scripts/               # 部署脚本
│   ├── start.sh          # 启动脚本
│   ├── stop.sh           # 停止脚本
│   ├── deploy.sh         # 部署脚本
│   └── status.sh         # 状态检查
├── logs/                  # 日志文件
├── Dockerfile            # Docker配置
├── docker-compose.yml    # Docker Compose配置
├── ecosystem.config.js   # PM2配置
├── requirements.txt      # Python依赖
└── main.py              # 服务入口
```

### 端口映射
- **8089**: 主服务端口
- **9090**: 监控指标端口
- **6379**: Redis端口
- **80/443**: Nginx反向代理端口

### 环境变量参考
详细的环境变量配置请参考 `config/production.env` 文件中的注释说明。