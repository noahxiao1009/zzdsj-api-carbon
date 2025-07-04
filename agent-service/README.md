# 智能体服务 (Agent Service)

基于 Agno 框架的微服务化智能体管理系统，提供完整的智能体创建、管理、对话和协作功能。

## 项目结构

```
agent-service/
├── app/
│   ├── __init__.py
│   ├── api/                    # API路由层
│   │   ├── __init__.py
│   │   ├── agent_api.py        # 智能体API实现
│   │   ├── agent_routes.py     # 智能体路由
│   │   ├── agents.py           # 智能体管理接口
│   │   ├── template_routes.py  # 模板管理路由
│   │   ├── team_routes.py      # 团队管理路由
│   │   └── model_routes.py     # 模型管理路由
│   ├── core/                   # 核心业务逻辑
│   │   ├── __init__.py
│   │   ├── agno_manager.py     # Agno框架管理器
│   │   ├── template_manager.py # 模板管理器
│   │   ├── execution_graph.py  # 执行图管理
│   │   └── execution_engine.py # 执行引擎
│   ├── services/               # 服务层
│   │   ├── __init__.py
│   │   ├── agent_service.py    # 智能体服务
│   │   ├── team_service.py     # 团队服务
│   │   └── model_service.py    # 模型服务
│   ├── models/                 # 数据模型
│   ├── schemas/                # Pydantic模式
│   ├── repositories/           # 数据访问层
│   ├── middleware/             # 中间件
│   ├── utils/                  # 工具函数
│   └── config/                 # 配置管理
├── config/                     # 配置文件
├── docker/                     # Docker相关文件
├── scripts/                    # 脚本文件
├── tests/                      # 测试文件
├── uploads/                    # 上传文件目录
├── main.py                     # 应用入口文件
├── requirements.txt            # Python依赖
├── Dockerfile                  # Docker构建文件
├── README.md                   # 项目文档
└── QUICK_START.md             # 快速开始指南
```

## 功能特性

### 核心功能
- **智能体管理**: 创建、配置、管理和删除智能体
- **模板系统**: 提供基础对话、知识库、深度思考等多种模板
- **对话引擎**: 支持多轮对话、流式响应和上下文保持
- **工具集成**: 支持多种外部工具和API集成
- **团队协作**: 支持多智能体协作和团队管理
- **执行图**: 基于DAG的智能体执行流程可视化

### 技术特点
- **Agno框架**: 基于官方Agno 1.7.0框架构建，确保兼容性
- **模块化设计**: 清晰的模块划分和职责分离
- **高性能**: 支持异步处理和并发执行
- **可扩展**: 支持自定义工具和扩展集成
- **监控完善**: 提供详细的统计和监控功能

## 依赖项说明

### 核心依赖
- **Agno 1.7.0**: 智能体框架核心库
- **FastAPI 0.104.1**: Web框架
- **Pydantic 2.5.0**: 数据验证
- **SQLAlchemy 2.0.23**: 数据库ORM

### 特殊依赖
- **duckduckgo-search**: DuckDuckGo搜索工具
- **yfinance**: 金融数据工具
- **googlesearch-python**: Google搜索工具

### AI模型提供商
- **openai**: OpenAI API客户端
- **anthropic**: Anthropic API客户端

## 快速开始

### 环境要求
- Python 3.9+
- PostgreSQL 13+
- Redis 6+
- Nacos (服务发现)

### 安装依赖
```bash
pip install -r requirements.txt
```

### 环境配置
```bash
# 复制配置文件
cp config/config.example.yaml config/config.yaml

# 编辑配置文件
vim config/config.yaml
```

### 启动服务
```bash
# 开发模式
python main.py

# 生产模式
uvicorn main:app --host 0.0.0.0 --port 8001
```

## API文档

### 服务信息
- **服务地址**: http://localhost:8001
- **API文档**: http://localhost:8001/docs
- **健康检查**: http://localhost:8001/health

### 主要接口

#### 1. 智能体管理
```http
GET /api/v1/agents          # 获取智能体列表
POST /api/v1/agents         # 创建智能体
GET /api/v1/agents/{id}     # 获取智能体详情
PUT /api/v1/agents/{id}     # 更新智能体
DELETE /api/v1/agents/{id}  # 删除智能体
```

#### 2. 模板管理
```http
GET /api/v1/templates       # 获取模板列表
GET /api/v1/templates/{id}  # 获取模板详情
```

#### 3. 团队管理
```http
GET /api/v1/teams           # 获取团队列表
POST /api/v1/teams          # 创建团队
```

#### 4. 模型管理
```http
GET /api/v1/models          # 获取可用模型列表
```

### 创建智能体示例

```bash
curl -X POST "http://localhost:8001/api/v1/agents" \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "basic_conversation",
    "basic_configuration": {
      "agent_name": "客服助手",
      "agent_description": "专业的客服智能助手",
      "system_prompt": "你是一个专业的客服助手",
      "language": "zh-CN",
      "response_style": "friendly"
    },
    "model_configuration": {
      "provider": "openai",
      "model": "gpt-4o-mini",
      "temperature": 0.7,
      "max_tokens": 1000
    },
    "capability_configuration": {
      "tools": [
        {
          "type": "web_search",
          "name": "网络搜索",
          "enabled": true
        }
      ]
    }
  }'
```

## 配置说明

### 主要配置项
```yaml
# 服务配置
service:
  name: "agent-service"
  host: "0.0.0.0"
  port: 8001
  debug: false

# 数据库配置
database:
  url: "postgresql+asyncpg://user:pass@localhost/agentdb"
  
# Redis配置
redis:
  url: "redis://localhost:6379/0"

# Agno配置
agno:
  api_key: "your-agno-api-key"
  base_url: "https://api.agno.com"
  
# 模型配置
models:
  openai:
    api_key: "your-openai-api-key"
  anthropic:
    api_key: "your-anthropic-api-key"
```

## 开发指南

### 代码规范
- 遵循PEP 8代码规范
- 使用类型注解
- 编写完整的文档字符串
- 单元测试覆盖率 > 80%

### 测试
```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_agent_service.py

# 生成覆盖率报告
pytest --cov=app tests/
```

### 开发工具
```bash
# 代码格式化
black app/

# 导入排序
isort app/

# 代码检查
flake8 app/

# 类型检查
mypy app/
```

## Docker部署

### 构建镜像
```bash
docker build -t agent-service:latest .
```

### 运行容器
```bash
docker run -d \
  --name agent-service \
  -p 8001:8001 \
  -e DATABASE_URL="postgresql+asyncpg://user:pass@host/db" \
  -e REDIS_URL="redis://host:6379/0" \
  agent-service:latest
```

## 监控和日志

### 健康检查
```bash
curl http://localhost:8001/health
```

### 指标监控
- **Prometheus指标**: http://localhost:8001/metrics
- **性能指标**: 响应时间、错误率、并发数
- **业务指标**: 智能体数量、对话次数、工具使用率

### 日志配置
- **日志级别**: DEBUG/INFO/WARNING/ERROR
- **日志格式**: 结构化JSON格式
- **日志文件**: logs/agent-service.log
- **日志轮转**: 按天轮转，保留30天

## 故障排除

### 常见问题

1. **Agno框架连接失败**
   ```bash
   # 检查API密钥配置
   echo $AGNO_API_KEY
   
   # 检查网络连接
   curl -I https://api.agno.com
   ```

2. **数据库连接错误**
   ```bash
   # 检查数据库连接
   psql -h localhost -U user -d agentdb
   
   # 检查数据库迁移
   alembic current
   alembic upgrade head
   ```

3. **Redis连接问题**
   ```bash
   # 检查Redis服务
   redis-cli ping
   
   # 检查Redis配置
   redis-cli info
   ```
