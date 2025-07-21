# 微服务间通信SDK

## 📋 概述

这是一个统一的微服务间通信SDK，旨在简化服务调用、提高系统可靠性和可维护性。

### 🎯 核心目标

- **简单易用**: 统一的API接口，隐藏复杂的服务发现和负载均衡逻辑
- **高可靠性**: 内置熔断器、重试机制、健康检查
- **高性能**: 连接池、本地缓存、批量调用支持
- **易维护**: 配置驱动、监控完善、错误处理统一

## 🏗️ 架构设计

```
┌─────────────────────────────────────────┐
│  业务层: 微服务业务逻辑                  │
├─────────────────────────────────────────┤
│  通信层: ServiceClient SDK               │
│  ├── 同步调用 (HTTP)                    │
│  ├── 异步事件 (RabbitMQ)                │
│  └── 实时通信 (WebSocket)               │
├─────────────────────────────────────────┤
│  路由层: Gateway (负载均衡、监控)        │
├─────────────────────────────────────────┤
│  基础设施: 服务注册、配置中心、监控       │
└─────────────────────────────────────────┘
```

## 🚀 快速开始

### 基础安装

```bash
# 将SDK目录添加到Python路径
export PYTHONPATH="${PYTHONPATH}:/path/to/zzdsl-api-carbon/shared"
```

### 基础使用

```python
from service_client import ServiceClient, CallMethod, call_service

# 方式1: 便捷函数调用
result = await call_service(
    service_name="model-service",
    method=CallMethod.POST,
    path="/api/v1/chat",
    json={"message": "Hello"}
)

# 方式2: 客户端实例
async with ServiceClient() as client:
    result = await client.call(
        service_name="knowledge-service",
        method=CallMethod.GET,
        path="/api/v1/knowledge"
    )
```

## 📚 详细功能

### 1. 同步HTTP调用

支持所有HTTP方法，内置重试和熔断机制：

```python
from service_client import ServiceClient, CallMethod, CallConfig, RetryStrategy

# 自定义配置
config = CallConfig(
    timeout=60,
    retry_times=5,
    retry_strategy=RetryStrategy.EXPONENTIAL,
    circuit_breaker_enabled=True
)

async with ServiceClient() as client:
    # GET请求
    users = await client.call(
        service_name="base-service",
        method=CallMethod.GET,
        path="/api/v1/users",
        params={"page": 1, "size": 10}
    )
    
    # POST请求
    result = await client.call(
        service_name="knowledge-service",
        method=CallMethod.POST,
        path="/api/v1/documents",
        config=config,
        json={"title": "新文档", "content": "内容"}
    )
```

### 2. 异步事件通信

基于RabbitMQ的事件发布/订阅：

```python
from service_client import AsyncServiceClient, publish_event

# 发布事件
success = await publish_event(
    event_type="user_action",
    data={
        "user_id": "12345",
        "action": "create_knowledge_base",
        "timestamp": datetime.now().isoformat()
    },
    target_service="knowledge-service",
    priority="high"
)

# 使用异步客户端
async with AsyncServiceClient() as client:
    await client.publish_event(
        event_type="model_inference_completed",
        data={"result": "推理完成"}
    )
```

### 3. 批量并发调用

高效的并发调用模式：

```python
async with ServiceClient() as client:
    # 并发调用多个服务
    tasks = [
        client.call("base-service", CallMethod.GET, "/api/v1/users/123"),
        client.call("agent-service", CallMethod.GET, "/api/v1/agents"),
        client.call("knowledge-service", CallMethod.GET, "/api/v1/knowledge")
    ]
    
    user_info, agents, knowledge = await asyncio.gather(*tasks)
```

### 4. 错误处理和容错

```python
from service_client import ServiceCallError

async with ServiceClient() as client:
    try:
        result = await client.call(
            service_name="model-service",
            method=CallMethod.POST,
            path="/api/v1/chat",
            json={"message": "Hello"}
        )
    except ServiceCallError as e:
        if e.status_code == 503:
            # 服务不可用，使用降级策略
            result = {"response": "服务暂时不可用"}
        else:
            # 其他错误处理
            logger.error(f"调用失败: {e}")
            raise
    
    # 健康检查
    is_healthy = await client.health_check("model-service")
    if not is_healthy:
        # 实施降级策略
        pass
```

## ⚙️ 配置管理

### 环境变量配置

```bash
# 基础配置
export MICROSERVICE_ENV=production
export GATEWAY_URL=http://gateway.company.com:8080
export MESSAGING_URL=http://messaging.company.com:8008

# 默认调用配置
export DEFAULT_TIMEOUT=30
export DEFAULT_RETRY_TIMES=3
export DEFAULT_RETRY_DELAY=1.0

# 熔断器配置
export CB_FAILURE_THRESHOLD=5
export CB_RECOVERY_TIMEOUT=60

# 服务特定配置
export MODEL_SERVICE_URL=http://model.company.com:8083
export MODEL_SERVICE_TIMEOUT=120
export KNOWLEDGE_SERVICE_URL=http://knowledge.company.com:8082
```

### 代码配置

```python
from service_client.config import get_config_manager

config_manager = get_config_manager()

# 更新服务配置
config_manager.update_service_config(
    "model-service",
    timeout=120,
    retry_times=5,
    api_key="your-api-key"
)
```

## 🔧 集成到现有微服务

### 1. 在Knowledge Service中使用

```python
# knowledge-service/app/services/model_integration.py
from shared.service_client import ServiceClient, CallMethod

class ModelIntegration:
    def __init__(self):
        self.client = None
    
    async def __aenter__(self):
        self.client = ServiceClient()
        await self.client.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.__aexit__(exc_type, exc_val, exc_tb)
    
    async def generate_embeddings(self, texts: List[str]):
        """调用模型服务生成向量"""
        try:
            result = await self.client.call(
                service_name="model-service",
                method=CallMethod.POST,
                path="/api/v1/embeddings",
                json={"texts": texts, "model": "text-embedding-ada-002"}
            )
            return result["embeddings"]
        except Exception as e:
            logger.error(f"生成向量失败: {e}")
            raise
```

### 2. 在Agent Service中使用

```python
# agent-service/app/services/chat_orchestrator.py
from shared.service_client import ServiceClient, AsyncServiceClient, CallMethod

class ChatOrchestrator:
    async def process_message(self, user_id: str, message: str):
        async with ServiceClient() as client:
            # 1. 检索知识库
            knowledge_result = await client.call(
                service_name="knowledge-service",
                method=CallMethod.POST,
                path="/api/v1/search",
                json={"query": message, "user_id": user_id}
            )
            
            # 2. 调用模型生成回复
            chat_result = await client.call(
                service_name="model-service",
                method=CallMethod.POST,
                path="/api/v1/chat",
                json={
                    "messages": [{"role": "user", "content": message}],
                    "context": knowledge_result.get("context", "")
                }
            )
            
            # 3. 发布聊天事件
            async with AsyncServiceClient() as async_client:
                await async_client.publish_event(
                    event_type="chat_completed",
                    data={
                        "user_id": user_id,
                        "message": message,
                        "response": chat_result["content"]
                    }
                )
            
            return chat_result["content"]
```

## 📊 监控和调试

### 获取调用指标

```python
async with ServiceClient() as client:
    # 执行一些调用...
    
    # 获取指标
    metrics = await client.get_metrics()
    print(f"总调用次数: {metrics['total_calls']}")
    print(f"成功率: {metrics['successful_calls'] / metrics['total_calls'] * 100:.2f}%")
    print(f"重试次数: {metrics['retry_count']}")
    print(f"熔断次数: {metrics['circuit_breaker_trips']}")
```

### 日志配置

```python
import logging

# 配置SDK日志
logging.getLogger("service_client").setLevel(logging.INFO)

# 启用详细调试日志
logging.getLogger("service_client.client").setLevel(logging.DEBUG)
```

## 🎯 最佳实践

### 1. 服务调用最佳实践

```python
# ✅ 推荐: 使用上下文管理器
async with ServiceClient() as client:
    result = await client.call(...)

# ✅ 推荐: 合理设置超时和重试
config = CallConfig(
    timeout=30,      # 根据业务需求设置
    retry_times=3,   # 避免过多重试
    retry_strategy=RetryStrategy.EXPONENTIAL
)

# ✅ 推荐: 错误处理和降级策略
try:
    result = await client.call(...)
except ServiceCallError as e:
    # 实施降级策略
    result = get_fallback_result()

# ❌ 避免: 阻塞调用
# result = sync_call()  # 不要使用同步调用

# ❌ 避免: 忽略错误
# result = await client.call(...)  # 没有错误处理
```

### 2. 事件发布最佳实践

```python
# ✅ 推荐: 合理的事件粒度
await publish_event(
    event_type="user_knowledge_base_created",  # 具体的业务事件
    data={
        "user_id": "12345",
        "knowledge_base_id": "kb_001",
        "created_at": datetime.now().isoformat()
    }
)

# ✅ 推荐: 事件幂等性
event_id = str(uuid.uuid4())
await publish_event(
    event_type="document_processed",
    data={
        "event_id": event_id,  # 用于去重
        "document_id": "doc_001",
        "status": "completed"
    }
)

# ❌ 避免: 过于频繁的事件
# await publish_event("user_typing", ...)  # 太频繁

# ❌ 避免: 过大的事件负载
# data = {"large_content": "..."}  # 避免大数据
```

### 3. 性能优化建议

```python
# ✅ 并发调用
tasks = [
    client.call("service1", CallMethod.GET, "/api/data1"),
    client.call("service2", CallMethod.GET, "/api/data2"),
    client.call("service3", CallMethod.GET, "/api/data3")
]
results = await asyncio.gather(*tasks)

# ✅ 连接复用
async with ServiceClient() as client:
    # 在一个会话中进行多次调用
    for i in range(10):
        result = await client.call(...)

# ✅ 合理的超时设置
# 快速查询
config_fast = CallConfig(timeout=5)
# 长时间处理
config_slow = CallConfig(timeout=300)
```

## 🔍 故障排查

### 常见问题

1. **服务不可用**
   - 检查服务注册状态
   - 验证网关配置
   - 查看服务健康检查

2. **调用超时**
   - 调整timeout配置
   - 检查网络延迟
   - 优化目标服务性能

3. **熔断器触发**
   - 查看错误日志
   - 检查服务健康状态
   - 调整熔断器阈值

### 调试命令

```python
# 检查服务健康状态
async with ServiceClient() as client:
    health_status = await client.health_check("target-service")
    print(f"服务健康状态: {health_status}")

# 查看调用指标
metrics = await client.get_metrics()
print(f"调用统计: {metrics}")

# 测试服务连通性
try:
    result = await client.call(
        service_name="target-service",
        method=CallMethod.GET,
        path="/health"
    )
    print("服务连通正常")
except Exception as e:
    print(f"服务连通失败: {e}")
```

## 📝 更新日志

### v1.0.0
- 初始版本发布
- 支持HTTP同步调用
- 支持异步事件通信
- 内置熔断器和重试机制
- 配置管理功能

## 🤝 贡献指南

1. Fork项目
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建Pull Request

## 📄 许可证

本项目采用MIT许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

---

**联系我们**: ZZDSJ Development Team 