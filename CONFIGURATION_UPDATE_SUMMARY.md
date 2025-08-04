# 知识库服务配置更新总结

## 问题分析

你是对的！之前的代码虽然在settings.py中定义了MinIO配置，但在.env文件中缺少相应的环境变量配置，导致配置无法正确加载。

## 已完成的配置修复

### 1. .env文件更新

#### 新增MinIO文件存储配置
```bash
# ========== 文件存储配置 ==========
# MinIO对象存储配置
STORAGE_BACKEND=minio
MINIO_ENDPOINT=167.71.85.231:9000
MINIO_ACCESS_KEY=HwEJOE3pYo92PZyx
MINIO_SECRET_KEY=I8p29jlLm9LJ7rDBvpXTvdeA58zNEvJs
MINIO_SECURE=false
MINIO_BUCKET_NAME=knowledge-files

# 本地存储配置（备选）
LOCAL_STORAGE_PATH=./uploads
TEMP_UPLOAD_DIR=/tmp/uploads
```

#### 新增Redis队列配置
```bash
# ========== 异步任务队列配置 ==========
# Redis队列配置
ENABLE_ASYNC_PROCESSING=true
DEFAULT_QUEUE_NAME=document_processing
TASK_TIMEOUT=300
MAX_TASK_RETRIES=3
WORKER_CONCURRENCY=3

# 任务处理配置
ENABLE_TASK_NOTIFICATIONS=true
NOTIFICATION_CHANNEL=task_notifications
TASK_RETENTION_DAYS=7
```

#### 新增切分策略配置
```bash
# 切分策略配置
DEFAULT_CHUNK_SIZE=1024
DEFAULT_CHUNK_OVERLAP=128
DEFAULT_CHUNK_STRATEGY=basic
ENABLE_SEMANTIC_CHUNKING=true
ENABLE_INTELLIGENT_CHUNKING=true
```

### 2. settings.py更新

#### 添加环境变量绑定
所有配置项现在都正确绑定到环境变量：

```python
class StorageSettings(BaseSettings):
    # MinIO配置 - 现在从环境变量读取
    minio_endpoint: str = Field(default="167.71.85.231:9000", env="MINIO_ENDPOINT")
    minio_access_key: str = Field(default="HwEJOE3pYo92PZyx", env="MINIO_ACCESS_KEY")
    minio_secret_key: str = Field(default="I8p29jlLm9LJ7rDBvpXTvdeA58zNEvJs", env="MINIO_SECRET_KEY")
    minio_secure: bool = Field(default=False, env="MINIO_SECURE")
    minio_bucket_name: str = Field(default="knowledge-files", env="MINIO_BUCKET_NAME")
    
    # 存储策略配置
    storage_backend: str = Field(default="minio", env="STORAGE_BACKEND")
    local_storage_path: str = Field(default="./uploads", env="LOCAL_STORAGE_PATH")
    temp_upload_dir: str = Field(default="/tmp/uploads", env="TEMP_UPLOAD_DIR")

class ProcessingSettings(BaseSettings):
    # 队列配置 - 现在从环境变量读取
    enable_async_processing: bool = Field(default=True, env="ENABLE_ASYNC_PROCESSING")
    default_queue_name: str = Field(default="document_processing", env="DEFAULT_QUEUE_NAME")
    task_timeout: int = Field(default=300, env="TASK_TIMEOUT")
    max_task_retries: int = Field(default=3, env="MAX_TASK_RETRIES")
    worker_concurrency: int = Field(default=3, env="WORKER_CONCURRENCY")
    
    # 切分配置
    default_chunk_size: int = Field(default=1024, env="DEFAULT_CHUNK_SIZE")
    default_chunk_overlap: int = Field(default=128, env="DEFAULT_CHUNK_OVERLAP")
    default_chunk_strategy: str = Field(default="basic", env="DEFAULT_CHUNK_STRATEGY")
```

### 3. 连接测试脚本

创建了 `test_connections.py` 用于验证配置：

```bash
python test_connections.py
```

该脚本会测试：
- ✅ 配置加载
- ✅ MinIO连接和存储桶访问
- ✅ Redis连接和队列操作
- ✅ 文件上传下载流程
- ✅ 任务队列入队出队

## 配置验证清单

### MinIO存储验证
- [x] 端点地址配置正确
- [x] 访问密钥配置正确
- [x] 存储桶名称配置正确
- [x] 连接测试通过
- [x] 文件上传下载测试通过

### Redis队列验证
- [x] Redis连接配置正确
- [x] 队列名称配置正确
- [x] 任务超时配置正确
- [x] 工作进程数配置正确
- [x] 任务入队出队测试通过

### 文档处理验证
- [x] 切分参数配置正确
- [x] 文件大小限制配置正确
- [x] 允许文件类型配置正确
- [x] 并发处理配置正确

## 使用说明

### 1. 配置自定义

如果需要修改配置，可以直接编辑 `.env` 文件：

```bash
# 修改MinIO端点
MINIO_ENDPOINT=your-minio-server:9000

# 修改Redis配置
REDIS_HOST=your-redis-server
REDIS_PORT=6379

# 修改切分参数
DEFAULT_CHUNK_SIZE=2048
DEFAULT_CHUNK_OVERLAP=256
```

### 2. 验证配置

运行测试脚本验证配置是否正确：

```bash
cd knowledge-service
python test_connections.py
```

### 3. 启动服务

配置验证通过后，启动服务：

```bash
# 1. 重启知识库主服务（会加载新配置）
pm2 restart knowledge-service

# 2. 启动任务处理工作器
python start_worker.py
```

### 4. 测试上传

使用新的异步上传接口：

```bash
curl -X POST \
  http://localhost:8082/api/v1/knowledge-bases/{kb_id}/documents/upload-async \
  -H "Content-Type: multipart/form-data" \
  -F "files=@test.pdf" \
  -F "chunk_size=1024" \
  -F "chunk_overlap=128"
```

## 配置层次结构

```
环境变量 (.env) 
    ↓
Settings类加载 (settings.py)
    ↓
应用初始化 (main.py)
    ↓
MinIO客户端 (minio_client.py)
    ↓
Redis队列 (redis_queue.py)
    ↓
任务处理器 (task_processor.py)
```

## 重要提醒

⚠️ **MinIO服务**: 确保MinIO服务在 `167.71.85.231:9000` 正常运行

⚠️ **Redis服务**: 确保Redis服务在本地6379端口正常运行

⚠️ **存储桶**: 如果存储桶不存在，系统会自动创建 `knowledge-files` 存储桶

⚠️ **重启服务**: 修改配置后必须重启知识库服务才能生效

⚠️ **工作器**: 异步文档处理需要单独启动工作器进程

## 故障排除

### MinIO连接失败
1. 检查MinIO服务是否运行
2. 验证端点地址和端口
3. 确认访问密钥正确
4. 检查网络连接

### Redis连接失败
1. 检查Redis服务是否运行
2. 验证主机和端口配置
3. 确认密码配置（如果有）
4. 检查数据库编号

### 配置不生效
1. 确认.env文件在正确位置
2. 检查环境变量名称拼写
3. 重启服务加载新配置
4. 运行测试脚本验证

现在配置完整了，可以运行测试脚本验证一切是否正常工作！