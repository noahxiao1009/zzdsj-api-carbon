# 模型服务 (Model Service)

模型服务是微服务架构中的核心组件，负责统一管理和配置各种AI模型提供商，支持中国国内主要的大语言模型厂商。

## 主要功能

### 模型提供商管理
- **支持多厂商**: 智谱AI、百度文心、讯飞星火等中国主要AI厂商
- **API配置**: 统一的API密钥和连接配置管理
- **连接测试**: 自动验证API连接有效性
- **状态监控**: 实时监控提供商连接状态

### 模型管理
- **模型发现**: 自动获取提供商支持的模型列表
- **选择性启用**: 灵活选择需要启用的模型
- **类型分类**: 支持对话、嵌入、重排、多模态等多种模型类型
- **能力标识**: 清晰标识每个模型的具体能力

### 配置管理
- **参数配置**: 温度、最大Token数、Top-p等参数设置
- **预设管理**: 保存和复用常用的模型配置
- **版本控制**: 配置历史和版本管理

### 测试和监控
- **模型测试**: 一键测试模型可用性和响应时间
- **性能监控**: 统计调用次数、延迟、成功率等指标
- **健康检查**: 服务和模型健康状态监控

## 📋 支持的模型提供商

| 提供商 | 类型 | 支持模型 | 状态 |
|--------|------|----------|------|
| 智谱AI | zhipu | GLM-4, GLM-4V, Embedding-2 | ✅ |
| 百度文心 | baidu | ERNIE-4.0-8K, ERNIE-3.5-8K | ✅ |
| 讯飞星火 | iflytek | 星火认知3.5 | ✅ |
| 阿里通义 | dashscope | 通义千问系列 | 🚧 |
| 腾讯混元 | tencent | 混元系列 | 🚧 |
| 月之暗面 | moonshot | Moonshot系列 | 🚧 |
| 深度求索 | deepseek | DeepSeek系列 | 🚧 |
| MiniMax | minimax | abab系列 | 🚧 |

## 快速开始

### 1. 安装依赖

```bash
cd model-service
pip install -r requirements.txt
```

### 2. 启动服务

```bash
python main.py
```

服务将在 `http://localhost:8003` 启动

### 3. 查看API文档

访问 `http://localhost:8003/docs` 查看完整的API文档

## 📖 API接口说明

### 模型提供商相关

#### 获取提供商列表
```http
GET /api/v1/models/providers
```

响应示例：
```json
{
  "success": true,
  "data": [
    {
      "id": "zhipu",
      "name": "智谱AI",
      "display_name": "智谱AI",
      "description": "智谱AI是一家专注于大模型研发的中国人工智能公司",
      "is_configured": true,
      "is_enabled": true,
      "model_count": 3
    }
  ],
  "total": 8
}
```

#### 配置提供商
```http
POST /api/v1/models/providers/{provider_id}/configure
```

请求体：
```json
{
  "api_key": "your_api_key_here",
  "api_base": "https://api.provider.com/v1"
}
```

#### 测试连接
```http
POST /api/v1/models/providers/{provider_id}/test
```

#### 选择启用模型
```http
POST /api/v1/models/providers/{provider_id}/models/select
```

请求体：
```json
{
  "selected_models": ["glm-4", "embedding-2"]
}
```

### 模型相关

#### 获取模型列表
```http
GET /api/v1/models/
```

查询参数：
- `provider`: 提供商筛选
- `model_type`: 模型类型筛选
- `search`: 搜索关键词
- `enabled_only`: 仅显示已启用的模型

#### 获取模型详情
```http
GET /api/v1/models/{provider_id}/{model_id}
```

#### 测试模型
```http
POST /api/v1/models/{provider_id}/{model_id}/test
```

请求体：
```json
{
  "message": "你好，请介绍一下你自己",
  "temperature": 0.7,
  "max_tokens": 100,
  "stream": false
}
```

### 配置管理

#### 创建模型配置
```http
POST /api/v1/models/config
```

#### 获取配置列表
```http
GET /api/v1/models/config
```

### 健康检查

#### 获取服务健康状态
```http
GET /api/v1/models/health
```

## 🔗 与前端集成

模型服务与前端的模型设置页面完全对接，支持：

1. **提供商管理**: 对应前端的"第三方模型"标签页
2. **API配置**: 对应前端的配置模态框
3. **模型选择**: 对应前端的模型选择对话框
4. **测试功能**: 对应前端的连接测试按钮

前端调用示例：

```typescript
// 获取提供商列表
const providers = await modelApi.getProviders();

// 配置提供商
await modelApi.configureProvider('zhipu', {
  api_key: 'your_key',
  api_base: 'https://api.zhipu.com/v1'
});

// 测试连接
const testResult = await modelApi.testProvider('zhipu');

// 选择模型
await modelApi.selectModels('zhipu', ['glm-4', 'embedding-2']);
```

## 使用场景

### 1. 多厂商模型管理
```python
# 配置多个提供商
await configure_provider('zhipu', api_key='zhipu_key')
await configure_provider('baidu', api_key='baidu_key')

# 启用不同类型的模型
await select_models('zhipu', ['glm-4'])  # 对话模型
await select_models('baidu', ['embedding-v1'])  # 嵌入模型
```

### 2. 模型能力测试
```python
# 测试对话模型
test_result = await test_model('zhipu', 'glm-4', {
    'message': '请介绍一下人工智能',
    'temperature': 0.7
})

# 测试嵌入模型
embedding_result = await test_model('baidu', 'embedding-v1', {
    'message': '这是一段测试文本',
    'model_type': 'embedding'
})
```

### 3. 配置管理
```python
# 创建生产环境配置
config = await create_config({
    'name': '生产环境GLM-4配置',
    'provider_id': 'zhipu',
    'model_id': 'glm-4',
    'temperature': 0.3,
    'max_tokens': 2048,
    'system_prompt': '你是一个专业的AI助手'
})
```

## 配置说明

### 环境变量

```bash
# 服务端口
MODEL_SERVICE_PORT=8003

# 数据库连接（如果使用真实数据库）
DATABASE_URL=postgresql://user:pass@localhost/modeldb

# Redis连接（用于缓存）
REDIS_URL=redis://localhost:6379

# 日志级别
LOG_LEVEL=INFO
```

### 配置文件

```yaml
# config/config.yaml
service:
  name: "model-service"
  port: 8003
  
providers:
  default_timeout: 30
  max_retries: 3
  
models:
  cache_ttl: 3600
  test_timeout: 10
```

## 监控指标

服务提供以下监控指标：

- **提供商状态**: 配置数量、启用状态
- **模型统计**: 总数量、启用数量、类型分布
- **调用指标**: 请求数、成功率、平均延迟
- **错误统计**: 错误类型、错误率趋势

## 错误处理

服务使用统一的错误响应格式：

```json
{
  "success": false,
  "error": {
    "code": "PROVIDER_NOT_FOUND",
    "message": "提供商不存在",
    "details": {
      "provider_id": "invalid_provider"
    }
  }
}
```

常见错误码：
- `PROVIDER_NOT_FOUND`: 提供商不存在
- `MODEL_NOT_FOUND`: 模型不存在
- `PROVIDER_NOT_CONFIGURED`: 提供商未配置
- `API_CONNECTION_ERROR`: API连接失败
- `INVALID_API_KEY`: API密钥无效

## 与其他服务集成

### 网关服务注册
```python
# 注册到网关服务
gateway_client.register_service({
    'name': 'model-service',
    'url': 'http://localhost:8003',
    'health_check': '/api/v1/models/health'
})
```

### 智能体服务调用
```python
# 智能体服务调用模型服务
model_config = await model_service.get_config('config_id')
response = await llm_client.chat(
    provider=model_config.provider_id,
    model=model_config.model_id,
    messages=messages,
    **model_config.parameters
)
```
