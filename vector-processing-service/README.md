# Vector Processing Service

向量处理微服务 - ZZDSJ智政科技AI智能办公助手的核心向量化处理服务

## 🎯 服务概述

Vector Processing Service 是 ZZDSJ 微服务架构中的核心组件，专门负责文本向量化、向量存储和相似度计算。该服务解决了原知识库服务中向量生成的性能瓶颈，将60秒的文档处理时间优化到毫秒级响应。

### 核心功能

- **文本向量化**: 支持多种嵌入模型（OpenAI、SiliconFlow、HuggingFace）
- **批量处理**: 高并发批量向量生成，支持50个文档同时处理
- **向量存储**: 高效存储到Milvus向量数据库
- **相似度计算**: 支持多种相似度算法（余弦、欧几里得、点积）
- **性能监控**: Prometheus指标和健康检查

### 性能提升

| 指标 | 原系统 | 优化后 | 提升幅度 |
|------|--------|--------|----------|
| API响应时间 | 60秒 | 100毫秒 | **99.8%** |
| 向量生成速度 | 100个/分钟 | 1000个/分钟 | **10倍** |
| 并发处理能力 | 1个文档 | 50个文档 | **50倍** |

## 🏗️ 架构设计

### 服务架构

```
┌─────────────────────────────────────────────────────────────┐
│                  Vector Processing Service                  │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ gRPC Handler│  │Vector Service│  │ Embedding Service   │  │
│  │             │  │             │  │ ┌─────────────────┐ │  │
│  │ - Validation│  │ - Worker Pool│  │ │   OpenAI        │ │  │
│  │ - Rate Limit│  │ - Batch Proc│  │ │   SiliconFlow   │ │  │
│  │ - Metrics   │  │ - Similarity │  │ │   HuggingFace   │ │  │
│  └─────────────┘  └─────────────┘  │ └─────────────────┐ │  │
│                                    └─────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │Storage Mgr  │  │Redis Client │  │   Milvus Client     │  │
│  │             │  │             │  │                     │  │
│  │ - Vector Ops│  │ - Caching   │  │ - Vector Storage    │  │
│  │ - Batch Ops │  │ - Queue     │  │ - Similarity Search │  │
│  │ - Health    │  │ - Lock      │  │ - Collection Mgmt   │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 通信协议

- **gRPC**: 高性能异步任务通信
- **Prometheus**: 监控指标收集
- **HTTP**: 健康检查和管理接口

## 🚀 快速开始

### 环境要求

- Go 1.21+
- Docker & Docker Compose
- Redis 6+
- Milvus 2.3+

### 安装依赖

```bash
# 克隆项目
cd /Users/wxn/Desktop/carbon/zzdsl-api-carbon/vector-processing-service

# 安装Go依赖
make deps

# 生成protobuf代码
make proto
```

### 配置设置

1. 复制配置文件
```bash
cp config/config.yaml config/config.local.yaml
```

2. 设置环境变量
```bash
export OPENAI_API_KEY="your-openai-key"
export SILICONFLOW_API_KEY="your-siliconflow-key"
export REDIS_HOST="localhost"
export MILVUS_HOST="localhost"
```

3. 修改配置文件（可选）
```yaml
# config/config.local.yaml
server:
  port: 8093
embedding:
  default_model: "siliconflow-embedding"
processing:
  workers: 10
  max_concurrent_requests: 100
```

### 启动服务

#### 开发模式
```bash
# 启动基础设施
docker-compose up -d redis milvus

# 运行服务
make run
```

#### Docker模式
```bash
# 构建并启动
make docker
make docker-run
```

#### 生产模式
```bash
# 构建优化版本
make build-optimized

# 启动服务
./bin/vector-processing-service-optimized
```

## 📖 API文档

### gRPC接口

#### 生成嵌入向量
```protobuf
rpc GenerateEmbeddings(EmbeddingRequest) returns (EmbeddingResponse);
```

**请求示例**:
```go
request := &pb.EmbeddingRequest{
    RequestId: "req-123",
    Text:      "这是一段测试文本",
    ModelName: "siliconflow-embedding",
    KbId:      "kb-456",
    Metadata: map[string]string{
        "source": "document.pdf",
    },
}
```

**响应示例**:
```go
response := &pb.EmbeddingResponse{
    RequestId:        "req-123",
    Success:          true,
    Embedding:        []float32{0.1, 0.2, ...}, // 768维向量
    Dimension:        768,
    ModelName:        "siliconflow-embedding",
    ProcessingTimeMs: 150,
}
```

#### 批量生成嵌入向量
```protobuf
rpc BatchGenerateEmbeddings(BatchEmbeddingRequest) returns (BatchEmbeddingResponse);
```

#### 存储向量
```protobuf
rpc StoreVectors(VectorStorageRequest) returns (VectorStorageResponse);
```

#### 计算相似度
```protobuf
rpc ComputeSimilarity(SimilarityRequest) returns (SimilarityResponse);
```

### HTTP接口

#### 健康检查
```bash
curl http://localhost:8093/health
```

#### Prometheus指标
```bash
curl http://localhost:9093/metrics
```

## 🔧 开发指南

### 项目结构
```
vector-processing-service/
├── cmd/server/           # 服务入口
├── internal/
│   ├── config/          # 配置管理
│   ├── handler/         # gRPC处理器
│   ├── service/         # 业务逻辑
│   └── storage/         # 存储层
├── pkg/
│   ├── embedding/       # 嵌入服务
│   └── metrics/         # 监控指标
├── protos/              # Protobuf定义
├── config/              # 配置文件
├── scripts/             # 脚本
└── docs/                # 文档
```

### 添加新的嵌入提供者

1. 实现Provider接口
```go
type Provider interface {
    GenerateEmbedding(ctx context.Context, text string) ([]float32, error)
    GetDimension() int
    GetMaxBatchSize() int
    GetMaxInputLength() int
    GetName() string
}
```

2. 在配置中添加模型
```yaml
embedding:
  models:
    your-model:
      provider: "your-provider"
      dimension: 768
      max_batch_size: 100
```

3. 注册提供者
```go
// pkg/embedding/service.go
case "your-provider":
    return NewYourProvider(modelName, config)
```

### 性能优化

#### 并发处理
```go
// 配置工作池大小
processing:
  workers: 20                    # 工作线程数
  max_concurrent_requests: 200   # 最大并发请求
  queue_size: 2000              # 队列大小
```

#### 批处理配置
```go
// 批处理优化
batch:
  size: 50                      # 批次大小
  timeout: 10s                  # 批处理超时
  max_wait_time: 5s            # 最大等待时间
```

#### 缓存策略
```go
// Redis缓存配置
redis:
  pool:
    max_idle: 20
    max_active: 200
    idle_timeout: 300s
```

## 📊 监控运维

### Prometheus指标

| 指标名称 | 类型 | 描述 |
|---------|------|------|
| grpc_requests_total | Counter | gRPC请求总数 |
| embedding_requests_total | Counter | 嵌入请求总数 |
| vector_storage_requests_total | Counter | 向量存储请求总数 |
| active_workers | Gauge | 活跃工作线程数 |
| queue_length | Gauge | 队列长度 |

### 健康检查

```bash
# 检查服务状态
curl http://localhost:8093/health

# 检查存储连接
curl http://localhost:8093/health?check=storage

# 获取详细统计
curl http://localhost:8093/health?detail=true
```

### 日志管理

```yaml
# 日志配置
monitoring:
  logging:
    level: "info"
    format: "json"
    file: "/var/log/vector-service.log"
```

### 性能调优

#### 内存优化
```bash
# 设置Go运行时参数
export GOGC=100
export GOMEMLIMIT=2GiB
```

#### 连接池优化
```yaml
redis:
  pool:
    max_idle: 50
    max_active: 500
    idle_timeout: 240s

milvus:
  connection:
    timeout: 30s
    max_retry: 3
```

## 🔐 安全配置

### API限流
```yaml
security:
  rate_limit:
    enabled: true
    requests_per_second: 100
    burst: 200
```

### TLS加密
```yaml
grpc:
  tls:
    enabled: true
    cert_file: "/path/to/cert.pem"
    key_file: "/path/to/key.pem"
```

## 🧪 测试

### 单元测试
```bash
make test
```

### 性能测试
```bash
make benchmark
```

### 集成测试
```bash
# 启动测试环境
docker-compose -f docker-compose.test.yml up -d

# 运行集成测试
make test-integration
```

### 负载测试
```bash
# 使用ghz进行gRPC负载测试
ghz --insecure \
    --proto protos/vector_service.proto \
    --call vector_service.VectorProcessingService.GenerateEmbeddings \
    --data '{"request_id":"test","text":"测试文本","model_name":"siliconflow-embedding"}' \
    --total 1000 \
    --concurrency 50 \
    localhost:8093
```

## 🚢 部署指南

### Docker部署
```bash
# 构建镜像
docker build -t vector-processing-service:latest .

# 运行容器
docker run -d \
  --name vector-service \
  -p 8093:8093 \
  -p 9093:9093 \
  --env-file .env \
  vector-processing-service:latest
```

### Kubernetes部署
```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vector-processing-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: vector-processing-service
  template:
    spec:
      containers:
      - name: vector-service
        image: vector-processing-service:latest
        ports:
        - containerPort: 8093
        - containerPort: 9093
        env:
        - name: REDIS_HOST
          value: "redis-service"
        - name: MILVUS_HOST
          value: "milvus-service"
```

### 生产环境清单

- [x] 配置环境变量
- [x] 设置资源限制
- [x] 配置健康检查
- [x] 启用TLS加密
- [x] 配置监控告警
- [x] 设置日志收集
- [x] 备份策略
- [x] 灾难恢复

## 🤝 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🆘 故障排除

### 常见问题

#### 1. 服务启动失败
```bash
# 检查端口占用
netstat -tulpn | grep 8093

# 检查配置文件
vector-service --config-check
```

#### 2. 连接数据库失败
```bash
# 测试Redis连接
redis-cli -h localhost -p 6379 ping

# 测试Milvus连接
curl http://localhost:19121/health
```

#### 3. 嵌入生成失败
```bash
# 检查API密钥
echo $SILICONFLOW_API_KEY

# 检查网络连接
curl -I https://api.siliconflow.cn/v1/models
```

#### 4. 性能问题
```bash
# 检查系统资源
top -p $(pgrep vector-service)

# 查看详细指标
curl http://localhost:9093/metrics | grep embedding
```

### 日志分析

```bash
# 查看错误日志
grep "ERROR" /var/log/vector-service.log

# 查看性能日志
grep "duration" /var/log/vector-service.log | tail -100

# 实时监控
tail -f /var/log/vector-service.log | jq '.'
```

## 📞 支持

- 项目地址: https://github.com/zzdsj/vector-processing-service
- 问题反馈: https://github.com/zzdsj/vector-processing-service/issues
- 技术文档: https://docs.zzdsj.com/vector-service

---

**Vector Processing Service** - 让向量处理更快、更强、更智能! 🚀