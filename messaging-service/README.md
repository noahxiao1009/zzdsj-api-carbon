# Messaging Service

微服务间通信和实时消息服务，提供WebSocket实时通信、事件驱动架构、服务发现等核心功能。

## 功能特性

### 核心功能
- **事件驱动架构**：基于RabbitMQ的消息队列系统
- **WebSocket实时通信**：支持实时消息推送和双向通信
- **服务注册与发现**：动态服务注册、健康检查、负载均衡
- **消息广播**：支持全员、房间、用户的精确消息推送
- **连接管理**：WebSocket连接池管理、心跳检测、自动重连

### 技术特点
- **高性能**：异步处理、连接池管理、批量处理
- **高可用**：健康检查、自动故障转移、服务发现
- **可扩展**：微服务架构、水平扩展、负载均衡
- **安全性**：JWT认证、权限控制、安全传输

## 技术栈

- **Framework**: FastAPI 0.104.1
- **Message Queue**: RabbitMQ (aio-pika)
- **Cache**: Redis
- **WebSocket**: FastAPI WebSocket
- **Authentication**: JWT
- **Monitoring**: 自定义指标系统

## 项目结构

```
messaging-service/
├── main.py                 # 应用入口文件
├── Dockerfile             # Docker构建文件
├── requirements.txt       # Python依赖
├── README.md             # 项目文档
└── app/
    ├── core/             # 核心模块
    │   ├── config.py     # 配置管理
    │   ├── messaging.py  # 消息代理和事件分发器
    │   └── websocket_manager.py  # WebSocket管理器
    ├── api/              # API接口
    │   └── routes.py     # 路由定义
    ├── schemas/          # 数据模型
    │   └── messaging_schemas.py  # Pydantic模型
    ├── services/         # 业务服务
    │   └── service_registry.py  # 服务注册发现
    └── middleware/       # 中间件
        └── auth_middleware.py  # 认证中间件
```

## 快速开始

### 1. 环境要求

- Python 3.11+
- RabbitMQ 3.8+
- Redis 6.0+
- PostgreSQL 13+ (可选)

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 环境配置

创建 `.env` 文件：

```env
# 基础配置
DEBUG=false
HOST=0.0.0.0
PORT=8008

# 数据库配置
REDIS_URL=redis://localhost:6379/0
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# WebSocket配置
WEBSOCKET_MAX_CONNECTIONS=1000
WEBSOCKET_PING_INTERVAL=30

# 认证配置
JWT_SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440

# 网关配置
GATEWAY_URL=http://localhost:8080
```

### 4. 启动服务

```bash
python main.py
```

### 5. Docker部署

```bash
# 构建镜像
docker build -t messaging-service .

# 运行容器
docker run -p 8008:8008 messaging-service
```

## API文档

### 事件发布

```http
POST /api/v1/events/publish
Content-Type: application/json
Authorization: Bearer <token>

{
  "type": "user_action",
  "source_service": "chat-service",
  "target_service": "knowledge-service",
  "data": {
    "action": "create_conversation",
    "user_id": "user123"
  },
  "priority": 2
}
```

### 消息广播

```http
POST /api/v1/broadcast
Content-Type: application/json
Authorization: Bearer <token>

{
  "message_type": "notification",
  "data": {
    "title": "系统通知",
    "content": "服务维护将在30分钟后开始"
  },
  "target_type": "all"
}
```

### 服务注册

```http
POST /api/v1/services/register
Content-Type: application/json
Authorization: Bearer <token>

{
  "service_name": "user-service",
  "service_url": "http://localhost:8010",
  "health_check_url": "http://localhost:8010/health",
  "metadata": {
    "version": "1.0.0"
  }
}
```

### WebSocket连接

```javascript
// 连接WebSocket
const ws = new WebSocket('ws://localhost:8008/ws/client123');

// 发送消息
ws.send(JSON.stringify({
  type: 'chat',
  data: {
    message: 'Hello, world!',
    room: 'general'
  }
}));

// 接收消息
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log('收到消息:', message);
};
```

## 房间管理

### 加入房间

```http
POST /api/v1/rooms/general/join?client_id=client123
Authorization: Bearer <token>
```

### 离开房间

```http
POST /api/v1/rooms/general/leave?client_id=client123
Authorization: Bearer <token>
```

### 查看房间信息

```http
GET /api/v1/rooms
Authorization: Bearer <token>
```

## 服务发现

### 查看已注册服务

```http
GET /api/v1/services
Authorization: Bearer <token>
```

### 发现特定服务

```http
GET /api/v1/services/user-service/discover
Authorization: Bearer <token>
```

## 监控和指标

### 健康检查

```http
GET /health
```

### 性能指标

```http
GET /metrics
```

### WebSocket信息

```http
GET /ws/info
Authorization: Bearer <token>
```

## 消息类型

### 事件类型
- `user_action` - 用户行为事件
- `service_request` - 服务请求事件
- `service_response` - 服务响应事件
- `system_event` - 系统事件
- `error_event` - 错误事件
- `notification` - 通知事件

### WebSocket消息类型
- `chat` - 聊天消息
- `notification` - 通知消息
- `status_update` - 状态更新
- `heartbeat` - 心跳消息
- `error` - 错误消息
- `system` - 系统消息

## 权限系统

### 所需权限
- `messaging.view` - 查看连接和房间信息
- `services.view` - 查看服务列表
- `services.register` - 注册服务
- `services.unregister` - 注销服务
- `events.view` - 查看事件历史

## 配置说明

### WebSocket配置
- `WEBSOCKET_MAX_CONNECTIONS` - 最大连接数
- `WEBSOCKET_PING_INTERVAL` - 心跳间隔（秒）
- `WEBSOCKET_PING_TIMEOUT` - 心跳超时（秒）

### 消息队列配置
- `MESSAGE_QUEUE_EXCHANGE` - 交换机名称
- `MESSAGE_BATCH_SIZE` - 批处理消息数量
- `MESSAGE_TIMEOUT` - 消息超时时间

### 服务发现配置
- `SERVICE_DISCOVERY_URL` - 服务发现地址
- `HEALTH_CHECK_INTERVAL` - 健康检查间隔
- `SERVICE_REGISTRY_TIMEOUT` - 注册超时时间

## 性能优化

### 连接管理优化
- 连接池管理
- 心跳检测机制
- 自动清理无效连接

### 消息处理优化
- 异步消息处理
- 批量事件处理
- 消息优先级队列

### 内存优化
- 定期清理过期数据
- 连接数限制
- 消息缓存管理

## 故障排除

### 常见问题

1. **连接失败**
   - 检查RabbitMQ和Redis服务状态
   - 验证网络连接和防火墙设置
   - 确认配置参数正确

2. **消息丢失**
   - 检查消息队列状态
   - 验证消息持久化设置
   - 查看错误日志

3. **WebSocket断连**
   - 检查心跳配置
   - 验证网络稳定性
   - 增加重连机制

### 日志查看

```bash
# 查看服务日志
docker logs messaging-service

# 实时日志
docker logs -f messaging-service
```

## 开发指南

### 添加新的事件类型

1. 在 `core/messaging.py` 中添加事件类型
2. 在 `schemas/messaging_schemas.py` 中更新枚举
3. 实现对应的处理逻辑

### 扩展WebSocket功能

1. 在 `core/websocket_manager.py` 中添加新功能
2. 更新路由处理逻辑
3. 添加相应的API接口

### 集成新的微服务

1. 更新服务发现配置
2. 添加服务注册逻辑
3. 实现健康检查接口

## 生产部署

### Docker Compose

```yaml
version: '3.8'
services:
  messaging-service:
    build: .
    ports:
      - "8008:8008"
    environment:
      - REDIS_URL=redis://redis:6379/0
      - RABBITMQ_URL=amqp://rabbitmq:5672/
    depends_on:
      - redis
      - rabbitmq

  redis:
    image: redis:6-alpine
    ports:
      - "6379:6379"

  rabbitmq:
    image: rabbitmq:3-management
    ports:
      - "5672:5672"
      - "15672:15672"
```

### Kubernetes部署

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: messaging-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: messaging-service
  template:
    metadata:
      labels:
        app: messaging-service
    spec:
      containers:
      - name: messaging-service
        image: messaging-service:latest
        ports:
        - containerPort: 8008
        env:
        - name: REDIS_URL
          value: "redis://redis-service:6379/0"
        - name: RABBITMQ_URL
          value: "amqp://rabbitmq-service:5672/"
```

## 贡献指南

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 许可证

MIT License 