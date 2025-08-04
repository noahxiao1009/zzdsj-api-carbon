# 统一Redis缓存系统迁移指南

## 概述

本文档提供了将各微服务从现有的分散Redis管理器迁移到统一Redis管理器的详细指导。统一管理器实现了三级缓存架构（L1/L2/L3）、标准化键命名和缓存失效机制。

## 迁移步骤

### 1. MCP Service 迁移

#### 原有代码 (mcp-service/app/core/redis.py)
```python
# 旧的实现
from app.core.redis import MCPRedisManager

redis_manager = MCPRedisManager()
await redis_manager.set_service_config("service_id", config, ttl=3600)
config = await redis_manager.get_service_config("service_id")
```

#### 迁移后代码
```python
# 新的实现
from shared.cache import get_mcp_cache_adapter

cache_adapter = get_mcp_cache_adapter()
await cache_adapter.set_service_config("service_id", config)  # 自动使用L3_PERSISTENT
config = await cache_adapter.get_service_config("service_id")
```

### 2. TTL策略变更

#### 新的三级TTL策略（统一）
```
L1 应用层缓存: 300s (5分钟)
- 搜索结果、API响应、用户会话、对话上下文

L2 服务层缓存: 1800s (30分钟)  
- 智能体配置、知识库信息、文档块、工具结果、模型响应

L3 持久层缓存: 7200s (2小时)
- 系统配置、用户配置、服务配置、模型配置、权限信息
```

### 3. 缓存键命名变更

#### 新的统一键命名格式
```
统一格式: "unified:{service}:{type}:{id}"

MCP: "unified:mcp:config:service_id"
System: "unified:system:sensitive:hash" 
Chat: "unified:chat:session:session_id"
```

## 性能优化建议

### 1. 缓存级别选择
- **L1级别**：用于频繁访问的短期数据（搜索结果、API响应）
- **L2级别**：用于业务核心数据（配置信息、模型响应）
- **L3级别**：用于变化较少的持久数据（系统配置、用户权限）

### 2. 迁移验证清单

- [ ] 所有Redis导入已更新为使用统一管理器
- [ ] 所有同步Redis调用已改为异步
- [ ] TTL硬编码已移除，使用自动级别选择
- [ ] 键命名符合新的统一格式
- [ ] 性能测试验证缓存命中率>80%

## 后续维护

1. **定期监控缓存性能**：
   - 命中率应保持在80%以上
   - 平均响应时间<10ms
   - 错误率<1%

2. **性能优化**：
   - 根据实际使用情况调整TTL
   - 优化热点数据的缓存策略
   - 考虑启用压缩功能
