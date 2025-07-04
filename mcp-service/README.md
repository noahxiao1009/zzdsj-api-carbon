# MCP Service

统一管理系统定义的MCP服务，使用Docker部署，并指定固定网段，向网关层进行服务注册，提供给全局调用。

## 功能特性

- **服务管理**: 创建、配置、部署、监控MCP服务
- **工具管理**: 注册和管理MCP工具，支持动态加载
- **健康监控**: 实时健康检查和性能指标监控
- **容器化部署**: 基于Docker的自动化部署和管理
- **日志管理**: 完整的日志记录和查询功能
- **网关集成**: 与网关服务的无缝集成和服务注册
- **安全保障**: 完善的认证授权和访问控制

## 技术架构

### 核心技术栈

- **Web框架**: FastAPI + Uvicorn
- **MCP框架**: FastMCP V2
- **数据库**: PostgreSQL + SQLAlchemy
- **缓存**: Redis
- **容器化**: Docker + Docker Compose
- **服务发现**: Nacos
- **消息队列**: RabbitMQ

### 系统架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Gateway       │    │   MCP Service   │    │   MCP Tools     │
│   Service       │◄──►│   Manager       │◄──►│   Container     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Nacos         │    │   PostgreSQL    │    │   Docker        │
│   Registry      │    │   Database      │    │   Network       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 快速开始

### 环境要求

- Python 3.11+
- Docker 20.0+
- PostgreSQL 13+
- Redis 6.0+
- Docker Compose 2.0+

### 安装部署

1. **克隆项目**
```bash
git clone <repository-url>
cd mcp-service
```

2. **配置环境**
```bash
# 复制配置文件
cp config.example.yaml config.yaml

# 编辑配置文件
vim config.yaml
```

3. **安装依赖**
```bash
pip install -r requirements.txt
```

4. **数据库初始化**
```bash
# 创建数据库
createdb mcp_service_db

# 运行数据库迁移
alembic upgrade head
```

5. **启动服务**
```bash
# 开发模式
python app/main.py

# 生产模式
uvicorn app.main:app --host 0.0.0.0 --port 8008
```

### Docker部署

1. **构建镜像**
```bash
docker build -t mcp-service:latest .
```

2. **运行容器**
```bash
docker run -d \
  --name mcp-service \
  -p 8008:8008 \
  -v $(pwd)/config.yaml:/app/config.yaml \
  -v $(pwd)/logs:/app/logs \
  mcp-service:latest
```

3. **Docker Compose部署**
```bash
docker-compose up -d
```

## API文档

服务启动后，访问以下URL查看API文档：

- Swagger UI: http://localhost:8008/docs
- ReDoc: http://localhost:8008/redoc
- OpenAPI JSON: http://localhost:8008/openapi.json

### 主要API端点

#### 健康检查
- `GET /health` - 基础健康检查
- `GET /health/detailed` - 详细健康检查
- `GET /health/ready` - 就绪性检查
- `GET /health/live` - 存活检查
- `GET /health/metrics` - 性能指标

#### 服务管理
- `POST /services` - 创建MCP服务
- `GET /services` - 获取服务列表
- `GET /services/{id}` - 获取服务详情
- `PUT /services/{id}` - 更新服务配置
- `DELETE /services/{id}` - 删除服务
- `POST /services/{id}/start` - 启动服务
- `POST /services/{id}/stop` - 停止服务
- `POST /services/{id}/restart` - 重启服务

#### 工具管理
- `GET /tools` - 获取工具列表
- `GET /tools/{name}` - 获取工具详情
- `POST /tools/{name}/execute` - 执行工具
- `GET /tools/categories` - 获取工具分类
- `GET /tools/stats` - 获取工具统计

## 配置说明

### 主要配置项

```yaml
# 服务配置
service:
  name: "mcp-service"
  version: "1.0.0"
  environment: "development"
  debug: true
  host: "0.0.0.0"
  port: 8008

# 数据库配置
database:
  url: "postgresql://user:pass@localhost:5432/db"
  pool_size: 10
  max_overflow: 20

# Redis配置
redis:
  url: "redis://localhost:6379/5"
  max_connections: 100

# Docker配置
docker:
  network_name: "mcp-network"
  network_subnet: "172.20.0.0/16"
  default_cpu_limit: "1.0"
  default_memory_limit: "512Mi"

# 网关配置
gateway:
  url: "http://localhost:8000"
  register_endpoint: "/api/v1/services/register"
  auth_token: "your-auth-token"
```

### 环境变量

支持通过环境变量覆盖配置：

```bash
export SERVICE_NAME="mcp-service"
export SERVICE_PORT=8008
export DATABASE_URL="postgresql://user:pass@localhost:5432/db"
export REDIS_URL="redis://localhost:6379/5"
export GATEWAY_URL="http://localhost:8000"
export DEBUG=true
```

## 开发指南

### 项目结构

```
mcp-service/
├── app/
│   ├── api/                 # API路由层
│   │   ├── health.py       # 健康检查接口
│   │   ├── services.py     # 服务管理接口
│   │   └── tools.py        # 工具管理接口
│   ├── core/               # 核心模块
│   │   ├── config.py       # 配置管理
│   │   ├── database.py     # 数据库连接
│   │   ├── redis.py        # Redis连接
│   │   └── logging.py      # 日志配置
│   ├── frameworks/         # 框架层
│   │   └── fastmcp/        # FastMCP框架实现
│   │       ├── server.py   # MCP服务器
│   │       ├── tools.py    # 工具管理
│   │       └── tools/      # 工具实现
│   ├── models/             # 数据模型
│   │   └── mcp.py          # MCP相关模型
│   ├── schemas/            # Pydantic模式
│   │   └── mcp.py          # MCP相关模式
│   ├── services/           # 业务逻辑层
│   │   ├── mcp_manager.py  # MCP服务管理
│   │   └── deployment_manager.py # 部署管理
│   └── main.py             # 应用入口
├── config.example.yaml     # 配置示例
├── requirements.txt        # Python依赖
├── Dockerfile             # Docker构建文件
└── README.md              # 项目文档
```

### 添加新工具

1. **创建工具文件**
```python
# app/frameworks/fastmcp/tools/my_tool.py
from ..tools import register_tool

@register_tool(
    name="my_tool",
    description="我的自定义工具",
    category="custom",
    tags=["example"]
)
async def my_tool(param1: str, param2: int = 10) -> dict:
    """
    自定义工具实现
    
    参数:
        param1: 字符串参数
        param2: 整数参数，默认为10
        
    返回:
        dict: 处理结果
    """
    return {
        "result": f"处理了参数: {param1}, {param2}",
        "status": "success"
    }
```

2. **注册工具**
```python
# app/frameworks/fastmcp/tools/__init__.py
from .my_tool import my_tool

__all__ = ["my_tool"]
```

### 部署新服务

1. **创建服务配置**
```python
service_config = {
    "name": "my-mcp-service",
    "description": "我的MCP服务",
    "image": "my-registry/my-mcp-service:latest",
    "service_port": 8080,
    "environment_vars": {
        "ENV": "production"
    }
}
```

2. **调用API创建**
```bash
curl -X POST http://localhost:8008/services \
  -H "Content-Type: application/json" \
  -d '服务配置JSON'
```

## 监控和运维

### 健康检查

系统提供多层级的健康检查：

- **基础检查**: 服务是否运行
- **详细检查**: 各组件状态
- **就绪检查**: 是否可接收请求
- **存活检查**: 进程是否存活

### 性能指标

监控以下关键指标：

- **系统指标**: CPU、内存、磁盘使用率
- **应用指标**: 请求量、响应时间、错误率
- **业务指标**: 工具调用次数、服务健康度

### 日志管理

- **结构化日志**: JSON格式，便于解析
- **日志轮转**: 自动清理旧日志文件
- **多级别日志**: DEBUG、INFO、WARNING、ERROR
- **分布式追踪**: 请求链路跟踪

## 故障排除

### 常见问题

1. **服务无法启动**
   - 检查端口是否被占用
   - 验证数据库连接配置
   - 查看启动日志错误信息

2. **数据库连接失败**
   - 确认数据库服务状态
   - 检查连接参数配置
   - 验证网络连通性

3. **Redis连接超时**
   - 检查Redis服务状态
   - 验证连接池配置
   - 排查网络延迟问题

4. **Docker部署失败**
   - 检查镜像构建日志
   - 验证网络配置
   - 查看容器运行状态

### 调试技巧

1. **启用调试模式**
```yaml
service:
  debug: true
  
logging:
  level: "DEBUG"
```

2. **查看详细日志**
```bash
# 查看应用日志
docker logs -f mcp-service

# 查看健康检查
curl http://localhost:8008/health/detailed
```

3. **性能分析**
```bash
# 查看系统指标
curl http://localhost:8008/health/metrics

# 监控资源使用
docker stats mcp-service
```

