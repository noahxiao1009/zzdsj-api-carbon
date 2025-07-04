# Chat Service

智能聊天服务，提供对话交互、会话管理和语音交互功能。

## 功能特性

### 核心功能
- **智能对话**: 基于 Agno 框架的多智能体对话系统
- **会话管理**: 创建、查询、删除和管理用户聊天会话
- **语音支持**: 语音转文字和文字转语音功能
- **流式响应**: 支持实时流式消息传输
- **历史记录**: 完整的会话历史存储和查询

### 技术特性
- **异步架构**: 基于 FastAPI 的高性能异步服务
- **Redis缓存**: 会话和消息的高速缓存
- **数据库持久化**: PostgreSQL 数据存储
- **健康检查**: 完整的服务健康监控
- **API文档**: 自动生成的 Swagger/OpenAPI 文档

## 项目结构

```
chat-service/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 应用入口
│   ├── core/                # 核心配置和基础设施
│   │   ├── config.py        # 配置管理
│   │   ├── database.py      # 数据库连接
│   │   ├── redis.py         # Redis连接管理
│   │   └── logging.py       # 日志配置
│   ├── services/            # 业务服务层
│   │   ├── agno_integration.py    # Agno框架集成
│   │   └── chat_manager.py        # 聊天管理器
│   └── api/                 # API路由
│       ├── chat.py          # 聊天相关接口
│       ├── sessions.py      # 会话管理接口
│       └── health.py        # 健康检查接口
├── requirements.txt         # Python依赖
├── Dockerfile              # Docker配置
├── config.example.yaml     # 配置文件示例
└── README.md              # 项目文档
```

## 快速开始

### 环境要求
- Python 3.11+
- PostgreSQL 12+
- Redis 6+
- Agno Framework

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置环境

1. 复制配置文件模板：
```bash
cp config.example.yaml config.yaml
```

2. 编辑配置文件，设置数据库、Redis、Agno等连接信息

3. 设置环境变量：
```bash
export DATABASE_URL="postgresql://user:pass@localhost/chatdb"
export REDIS_URL="redis://localhost:6379/0"
export AGNO_API_URL="http://localhost:8080"
```

### 启动服务

```bash
# 开发模式
python -m app.main

# 或使用uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### Docker部署

```bash
# 构建镜像
docker build -t chat-service .

# 运行容器
docker run -d \
  --name chat-service \
  -p 8001:8001 \
  -e DATABASE_URL="postgresql://user:pass@host/db" \
  -e REDIS_URL="redis://host:6379/0" \
  chat-service
```

## API接口

### 健康检查
- `GET /health` - 基础健康检查
- `GET /health/detailed` - 详细健康状态
- `GET /health/readiness` - 就绪状态检查
- `GET /health/liveness` - 存活状态检查

### 聊天功能
- `POST /chat/session` - 创建聊天会话
- `POST /chat/message` - 发送消息
- `POST /chat/message/stream` - 流式发送消息
- `POST /chat/voice` - 发送语音消息
- `GET /chat/history/{session_id}` - 获取会话历史
- `GET /chat/agents` - 获取可用智能体

### 会话管理
- `GET /sessions` - 列出用户会话
- `GET /sessions/{session_id}` - 获取会话详情
- `DELETE /sessions/{session_id}` - 删除会话
- `POST /sessions/batch` - 批量会话操作
- `GET /sessions/user/{user_id}/stats` - 用户会话统计

## 配置说明

### 数据库配置
```yaml
database:
  url: "postgresql://user:pass@host:5432/dbname"
  pool_size: 10
  max_overflow: 20
```

### Redis配置
```yaml
redis:
  url: "redis://host:6379/0"
  max_connections: 10
```

### Agno框架配置
```yaml
agno:
  api_url: "http://agno-service:8080"
  api_key: "your_api_key"
  timeout: 30
```

## 开发指南

### 代码规范
- 遵循 PEP 8 代码风格
- 使用 black 进行代码格式化
- 使用 isort 进行导入排序
- 使用 mypy 进行类型检查

### 测试
```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_chat_manager.py

# 测试覆盖率
pytest --cov=app tests/
```

### 日志
服务使用结构化日志，支持多种输出格式：
- 控制台输出（开发环境）
- 文件输出（生产环境）
- JSON格式（用于日志收集）

## 监控和运维

### 健康检查
服务提供多层次的健康检查：
- `/health` - 基础存活检查
- `/health/readiness` - 服务就绪检查
- `/health/detailed` - 详细组件状态

### 指标监控
- 活跃会话数量
- 消息处理速度
- 错误率统计
- 响应时间分布

### 日志监控
- 结构化日志输出
- 错误和异常追踪
- 性能指标记录

## 与其他服务的集成

### Gateway Service
- 自动服务注册
- 统一路由管理
- 负载均衡支持

### Base Service
- 用户认证集成
- 权限验证
- 用户会话关联

### Model Service
- 模型调用接口
- 模型选择和配置
- 性能优化

## 故障排除

### 常见问题

1. **服务启动失败**
   - 检查数据库连接
   - 验证Redis连接
   - 确认Agno服务可用

2. **消息发送失败**
   - 检查会话是否存在
   - 验证智能体配置
   - 查看Agno服务日志

3. **语音功能异常**
   - 确认语音服务启用
   - 检查音频文件格式
   - 验证API密钥配置

### 日志位置
- 应用日志: `/app/logs/chat-service.log`
- 错误日志: `/app/logs/error.log`
- 访问日志: 通过中间件记录

