# 知识库服务 - 快速启动指南

## 5分钟快速部署

### 前置条件
- Python 3.11+
- PostgreSQL 12+
- Redis 6+

### 第一步：环境配置

```bash
# 1. 进入项目目录
cd zzdsl-api-carbon/knowledge-service

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，至少设置数据库连接信息
```

### 第二步：最小配置

编辑 `.env` 文件，设置必要配置：

```bash
# 基础配置
ENVIRONMENT=development
SERVICE_PORT=8082
LOG_LEVEL=INFO

# 数据库配置（必须）
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_DB=knowledge_db

# Redis配置（必须）
REDIS_HOST=localhost
REDIS_PORT=6379

# OpenAI配置（可选，用于嵌入模型）
MODEL_API_KEY=your_api_key
```

### 第三步：启动服务

```bash
# 直接启动
python main.py

# 或使用uvicorn（推荐）
uvicorn main:app --host 0.0.0.0 --port 8082 --reload
```

### 第四步：验证部署

```bash
# 健康检查
curl http://localhost:8082/health

# 查看API文档
open http://localhost:8082/docs

# 测试基本功能
curl -X POST "http://localhost:8082/api/v1/knowledge-bases/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "测试知识库",
    "description": "快速启动测试",
    "embedding_provider": "openai",
    "embedding_model": "text-embedding-3-small"
  }'
```

## Docker 快速部署

### 使用 Docker

```bash
# 1. 构建镜像
docker build -t knowledge-service .

# 2. 启动容器
docker run -d \
  --name knowledge-service \
  -p 8082:8082 \
  -e POSTGRES_HOST=host.docker.internal \
  -e REDIS_HOST=host.docker.internal \
  -e OPENAI_API_KEY=your_key \
  knowledge-service
```

### 使用 Docker Compose

创建 `docker-compose.yml`：

```yaml
version: '3.8'
services:
  knowledge-service:
    build: .
    ports:
      - "8082:8082"
    environment:
      - ENVIRONMENT=development
      - POSTGRES_HOST=postgres
      - REDIS_HOST=redis
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=knowledge_db
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

启动：
```bash
docker-compose up -d
```

## 常见问题解决

### 1. 端口冲突
```bash
# 检查端口占用
lsof -i :8082

# 修改端口
export SERVICE_PORT=8083
```

### 2. 数据库连接失败
```bash
# 测试PostgreSQL连接
pg_isready -h localhost -p 5432

# 测试Redis连接
redis-cli ping
```

### 3. 依赖安装失败
```bash
# 升级pip
pip install --upgrade pip

# 清理缓存
pip cache purge

# 重新安装
pip install -r requirements.txt --no-cache-dir
```

### 4. 权限问题（Docker）
```bash
# 检查目录权限
ls -la /app

# 修复权限
sudo chown -R 1000:1000 /app
```

## 验证检查清单

### ✅ 服务状态检查

- [ ] 服务成功启动在8082端口
- [ ] 健康检查返回200状态
- [ ] API文档页面可访问
- [ ] 日志输出正常

### ✅ 功能检查

- [ ] 可以创建知识库
- [ ] 可以获取知识库列表
- [ ] 可以获取嵌入模型列表
- [ ] 错误处理正常

### ✅ 集成检查

- [ ] PostgreSQL连接正常
- [ ] Redis连接正常
- [ ] 外部API调用正常（如OpenAI）
