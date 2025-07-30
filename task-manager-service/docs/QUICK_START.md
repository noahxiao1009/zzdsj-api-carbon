# 任务管理服务快速启动指南

## 🚀 快速启动

### 方式1: 一键启动脚本 (推荐)

```bash
# 进入项目目录
cd /Users/wxn/Desktop/carbon/zzdsl-api-carbon/task-manager-service

# 开发环境启动
./scripts/start.sh dev

# Docker容器启动
./scripts/start.sh docker

# 生产环境启动
./scripts/start.sh prod
```

### 方式2: Make命令

```bash
# 开发模式
make dev

# Docker启动
make docker-run

# 生产构建
make build && ./build/task-manager
```

### 方式3: Docker Compose

```bash
# 启动所有服务
docker-compose up -d

# 仅启动基础设施
docker-compose up -d postgres redis

# 查看日志
docker-compose logs -f task-manager
```

### 方式4: 手动启动

```bash
# 1. 启动依赖服务
docker-compose up -d postgres redis

# 2. 安装Go依赖
go mod download

# 3. 运行服务
go run cmd/server/main.go
```

## 📋 系统要求

### 必需组件
- **Go**: 1.21+
- **PostgreSQL**: 12+
- **Redis**: 6+

### 可选组件
- **Docker**: 20.10+ (容器部署)
- **Docker Compose**: 2.0+ (一键启动)

## ⚙️ 配置说明

### 环境变量配置

```bash
# 服务配置
export PORT=8084
export ENVIRONMENT=development
export LOG_LEVEL=info

# 数据库配置
export DATABASE_HOST=localhost
export DATABASE_PORT=5434
export DATABASE_USER=zzdsj_demo
export DATABASE_PASSWORD=zzdsj123
export DATABASE_DATABASE=zzdsj_demo

# Redis配置
export REDIS_HOST=localhost
export REDIS_PORT=6379
export REDIS_DB=1

# 工作进程配置
export WORKER_POOL_SIZE=10
export MAX_CONCURRENT_TASKS=50
export TASK_TIMEOUT=5m
```

### 配置文件

编辑 `config/config.yaml`:

```yaml
# 服务配置
port: 8084
environment: development
log_level: info

# 数据库配置
database:
  host: localhost
  port: 5434
  user: zzdsj_demo
  password: zzdsj123
  database: zzdsj_demo
  ssl_mode: disable

# Redis配置
redis:
  host: localhost
  port: 6379
  password: ""
  db: 1

# 工作进程配置
worker:
  pool_size: 10
  max_concurrent_tasks: 50
  task_timeout: "5m"
  poll_interval: "1s"
```

## 🔍 验证启动

### 1. 健康检查

```bash
curl http://localhost:8084/health
```

期望响应:
```json
{
  "status": "healthy",
  "service": "task-manager",
  "version": "1.0.0",
  "details": {
    "database": {"status": "healthy"},
    "redis": {"status": "healthy"},
    "queue": {"status": "healthy", "size": 0}
  }
}
```

### 2. 创建测试任务

```bash
curl -X POST http://localhost:8084/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "health_check",
    "kb_id": "test_kb_001",
    "priority": "normal",
    "payload": {
      "message": "Hello World"
    }
  }'
```

### 3. 查询任务状态

```bash
# 替换为实际的task_id
curl http://localhost:8084/api/v1/tasks/{task_id}
```

### 4. 查看系统统计

```bash
curl http://localhost:8084/api/v1/stats/system
```

## 🐛 常见问题

### 问题1: 端口占用

```bash
# 检查端口占用
lsof -i :8084
lsof -i :5434
lsof -i :6379

# 终止占用进程
kill -9 <PID>
```

### 问题2: 数据库连接失败

```bash
# 检查PostgreSQL状态
docker-compose ps postgres

# 查看数据库日志
docker-compose logs postgres

# 重启数据库
docker-compose restart postgres
```

### 问题3: Redis连接失败

```bash
# 检查Redis状态
docker-compose ps redis

# 测试Redis连接
docker-compose exec redis redis-cli ping

# 重启Redis
docker-compose restart redis
```

### 问题4: Go模块依赖问题

```bash
# 清理模块缓存
go clean -modcache

# 重新下载依赖
go mod download
go mod tidy
```

## 📊 监控面板

启动成功后可访问:

- **API服务**: http://localhost:8084
- **健康检查**: http://localhost:8084/health
- **监控指标**: http://localhost:8084/metrics
- **Grafana**: http://localhost:3000 (admin/admin123)
- **Prometheus**: http://localhost:9090

## 🔧 开发调试

### 启用调试日志

```bash
export LOG_LEVEL=debug
go run cmd/server/main.go
```

### 性能分析

```bash
# 启用pprof
export ENABLE_PPROF=true

# 访问性能分析
go tool pprof http://localhost:6060/debug/pprof/profile
```

### 数据库调试

```bash
# 连接数据库
docker-compose exec postgres psql -U zzdsj_demo -d zzdsj_demo

# 查看任务表
SELECT * FROM tasks ORDER BY created_at DESC LIMIT 10;

# 查看统计信息
SELECT * FROM task_statistics;
```

## 📝 下一步

1. **集成知识库服务**: 参考 `docs/INTEGRATION.md`
2. **生产部署**: 参考 `docs/DEPLOYMENT.md`
3. **API文档**: 访问 `docs/API.md`
4. **故障排除**: 参考 `docs/TROUBLESHOOTING.md`

## 🆘 获取帮助

```bash
# 查看帮助信息
./scripts/start.sh --help

# 查看Make命令
make help

# 查看Docker状态
docker-compose ps
```