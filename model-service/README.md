# 模型服务 (Model Service)

模型服务是微服务架构中的核心组件，负责统一管理和配置各种AI模型提供商，支持中国国内主要的大语言模型厂商。

## ✨ 核心特性

### 🏭 多厂商模型管理
- **国内主流厂商**: 智谱AI、百度文心、讯飞星火、阿里通义、腾讯混元等
- **新兴厂商**: 月之暗面、深度求索、MiniMax等
- **本地部署**: Ollama、vLLM等本地推理服务
- **国际厂商**: OpenAI、Anthropic等（兼容接口）

### 🎯 统一调用接口
- **Chat Completions**: 兼容OpenAI格式的聊天接口
- **Text Embeddings**: 统一的文本嵌入接口
- **Text Completions**: 文本补全接口
- **Multimodal**: 多模态模型调用
- **Document Rerank**: 文档重排接口
- **Batch Processing**: 批量调用支持

### ⚙️ 智能配置管理
- **系统级默认**: 全局默认模型配置
- **用户级偏好**: 个人定制化模型设置
- **配置模板**: 预设的配置模板（保守、均衡、创意等）
- **动态切换**: 前端实时切换模型配置

### 📊 完整监控体系
- **实时指标**: 调用次数、延迟、错误率等
- **使用统计**: 按用户、模型、时间维度的详细统计
- **性能分析**: 延迟分析、吞吐量监控
- **告警机制**: 自定义告警规则和通知

### 🔐 安全与权限
- **权限控制**: 基于用户的模型访问权限
- **配额管理**: 用户调用配额和限制
- **API密钥管理**: 安全的密钥存储和访问控制
- **审计日志**: 完整的调用审计记录

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
