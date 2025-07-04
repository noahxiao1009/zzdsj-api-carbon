# 数据库管理微服务

统一管理ES、PostgreSQL、Milvus、Redis、Nacos、RabbitMQ等基础数据库服务的微服务。

## 功能特性

### 统一连接管理
- **PostgreSQL**: 关系型数据库连接池管理
- **Elasticsearch**: 全文搜索引擎客户端管理
- **Milvus**: 向量数据库连接管理
- **Redis**: 缓存和会话存储管理
- **Nacos**: 服务发现和配置中心管理
- **RabbitMQ**: 消息队列连接管理

### 健康监控
- 实时健康检查
- 性能监控指标
- 连接状态跟踪
- 历史记录查询
- 警报系统

### 网关集成
- 自动服务注册
- 心跳保持机制
- 负载均衡支持
- 服务发现

### 配置管理
- 环境变量配置
- 动态配置更新
- 多环境支持

## 快速开始

### 环境要求
- Python 3.11+
- Docker (可选)
- 基础数据库服务

### 本地开发

1. **克隆项目**
```bash
git clone <repository-url>
cd database-service
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **配置环境变量**
```bash
cp config/development.env .env
# 编辑 .env 文件，配置数据库连接信息
```

4. **启动服务**
```bash
python main.py
```

5. **访问API文档**
- Swagger UI: http://localhost:8089/docs
- ReDoc: http://localhost:8089/redoc

### Docker部署

1. **构建镜像**
```bash
docker build -t database-service:latest .
```

2. **运行容器**
```bash
docker run -d \
  --name database-service \
  -p 8089:8089 \
  --env-file config/production.env \
  database-service:latest
```

## API接口

### 健康检查
```bash
# 简单健康检查
GET /health

# 详细健康状态
GET /api/database/health

# 所有数据库状态
GET /api/database/status

# 单个数据库状态
GET /api/database/status/{database_type}
```

### 连接管理
```bash
# 获取连接信息
GET /api/database/connections

# 测试数据库连接
POST /api/database/connections/test/{database_type}
```

### 配置管理
```bash
# 获取服务配置
GET /api/database/config
```

### 监控指标
```bash
# 获取监控指标
GET /api/database/metrics

# 获取健康历史
GET /api/database/history/{database_type}

# 获取系统警报
GET /api/database/alerts
```

### 网关注册
```bash
# 获取注册状态
GET /api/database/registry/status

# 更新注册元数据
POST /api/database/registry/update
```

## 配置说明

### 环境变量

| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `DB_SERVICE_NAME` | 服务名称 | `database-service` |
| `DB_SERVICE_PORT` | 服务端口 | `8089` |
| `DEBUG` | 调试模式 | `false` |

### PostgreSQL配置
| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `POSTGRES_HOST` | PostgreSQL主机 | `localhost` |
| `POSTGRES_PORT` | PostgreSQL端口 | `5432` |
| `POSTGRES_USER` | 用户名 | `postgres` |
| `POSTGRES_PASSWORD` | 密码 | `password` |
| `POSTGRES_DB` | 数据库名 | `carbon_db` |

### Elasticsearch配置
| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `ELASTICSEARCH_HOSTS` | ES集群地址 | `http://localhost:9200` |
| `ELASTICSEARCH_USERNAME` | 用户名 | - |
| `ELASTICSEARCH_PASSWORD` | 密码 | - |

### Milvus配置
| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `MILVUS_HOST` | Milvus主机 | `localhost` |
| `MILVUS_PORT` | Milvus端口 | `19530` |
| `MILVUS_USERNAME` | 用户名 | - |
| `MILVUS_PASSWORD` | 密码 | - |

### Redis配置
| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `REDIS_HOST` | Redis主机 | `localhost` |
| `REDIS_PORT` | Redis端口 | `6379` |
| `REDIS_PASSWORD` | 密码 | - |
| `REDIS_DB` | 数据库索引 | `0` |

### RabbitMQ配置
| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `RABBITMQ_HOST` | RabbitMQ主机 | `localhost` |
| `RABBITMQ_PORT` | RabbitMQ端口 | `5672` |
| `RABBITMQ_USERNAME` | 用户名 | `guest` |
| `RABBITMQ_PASSWORD` | 密码 | `guest` |

### Nacos配置
| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `NACOS_SERVERS` | Nacos服务器地址 | `localhost:8848` |
| `NACOS_NAMESPACE` | 命名空间 | `public` |
| `NACOS_GROUP` | 分组 | `DEFAULT_GROUP` |

## 架构设计

### 组件架构
```
┌─────────────────┐
│   FastAPI App   │
├─────────────────┤
│   API Router    │
├─────────────────┤
│ Gateway Registry│
├─────────────────┤
│ Health Checker  │
├─────────────────┤
│Connection Manager│
├─────────────────┤
│   Databases     │
│ PG|ES|MV|RD|... │
└─────────────────┘
```

### 核心组件

1. **数据库连接管理器**: 统一管理所有数据库连接池
2. **健康检查器**: 定期检查数据库健康状态
3. **网关注册器**: 向网关注册服务并保持心跳
4. **API路由器**: 提供RESTful API接口

## 监控和日志

### 健康监控
- 连接状态监控
- 响应时间统计
- 错误率统计
- 历史趋势分析

### 日志记录
- 结构化日志
- 多级别日志
- 文件和控制台输出
- 日志轮转

### 指标收集
- Prometheus兼容格式
- 自定义业务指标
- 系统性能指标

## 部署指南

### Kubernetes部署

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: database-service
spec:
  replicas: 2
  selector:
    matchLabels:
      app: database-service
  template:
    metadata:
      labels:
        app: database-service
    spec:
      containers:
      - name: database-service
        image: database-service:latest
        ports:
        - containerPort: 8089
        envFrom:
        - configMapRef:
            name: database-service-config
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

### Docker Compose

```yaml
version: '3.8'
services:
  database-service:
    build: .
    ports:
      - "8089:8089"
    environment:
      - DEBUG=false
      - POSTGRES_HOST=postgres
      - REDIS_HOST=redis
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
    depends_on:
      - postgres
      - redis
      - elasticsearch
```

## 开发指南

### 添加新数据库支持

1. 在 `DatabaseType` 枚举中添加新类型
2. 在配置文件中添加新配置类
3. 在连接管理器中实现初始化方法
4. 在健康检查器中添加检查逻辑

### 自定义健康检查

继承 `DatabaseHealthChecker` 类并重写检查方法：

```python
class CustomHealthChecker(DatabaseHealthChecker):
    async def _check_single_database(self, db_type: DatabaseType):
        # 自定义检查逻辑
        pass
```

## 故障排除

### 常见问题

1. **连接超时**: 检查网络连接和防火墙设置
2. **认证失败**: 验证用户名密码配置
3. **服务注册失败**: 检查网关地址和认证令牌

### 调试模式

启用调试模式获得详细日志：
```bash
export DEBUG=true
python main.py
```
