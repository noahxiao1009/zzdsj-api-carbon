# 知识库文件上传功能开发计划

## 项目概述

基于当前微服务架构，实现完整的知识库文件上传功能，包括文件存储、Redis队列处理、切分规则选择、实时状态推送等核心功能。

## 技术架构分析

### 当前已有配置
- ✅ **MinIO存储**: 已配置为文件存储后端
- ✅ **Milvus向量库**: 已配置并包含内置MinIO
- ✅ **Redis缓存**: 已配置队列支持
- ✅ **基础API**: 已有文件上传接口框架

### 需要完善的功能
- 🔄 **Redis队列集成**: 异步文档处理
- 🔄 **切分规则管理**: 用户选择和自定义切分逻辑
- 🔄 **实时状态推送**: SSE/WebSocket通信
- 🔄 **前端模态框**: 文件上传UI交互

## 开发计划

### Phase 1: 存储和队列基础设施 (优先级: 高)

#### 1.1 MinIO配置优化
**任务**: 确认MinIO配置和连接
- 检查当前MinIO配置是否使用Milvus内置还是独立部署
- 验证文件上传路径和权限
- 测试文件存储和访问功能

**文件修改**:
- `knowledge-service/app/config/settings.py` - 确认MinIO配置
- `knowledge-service/app/utils/minio_client.py` - 验证客户端连接

#### 1.2 Redis队列集成
**任务**: 实现基于Redis的异步任务队列
- 集成Celery或自定义Redis队列
- 创建文档处理任务定义
- 实现任务状态跟踪和更新

**新增文件**:
- `knowledge-service/app/queues/` - 队列管理模块
  - `__init__.py`
  - `redis_queue.py` - Redis队列客户端
  - `task_processor.py` - 任务处理器
  - `task_models.py` - 任务数据模型

### Phase 2: 切分规则系统 (优先级: 高)

#### 2.1 切分规则数据模型
**任务**: 扩展现有切分规则模型
- 预定义切分策略（系统级）
- 用户自定义切分策略
- 切分参数验证和测试

**文件修改**:
- `knowledge-service/app/models/knowledge_models.py` - 扩展切分规则模型
- `knowledge-service/app/schemas/knowledge_schemas.py` - 切分规则API模式

#### 2.2 切分规则API
**任务**: 实现切分规则管理接口
- 获取可用切分策略列表
- 创建/编辑自定义切分策略
- 切分策略预览和测试

**文件修改**:
- `knowledge-service/app/api/knowledge_routes.py` - 添加切分规则接口
- 或新增 `knowledge-service/app/api/splitter_routes.py` - 专用切分规则接口

#### 2.3 切分逻辑集成
**任务**: 将切分规则与文档处理流程集成
- 文档上传时选择切分策略
- 根据策略执行切分逻辑
- 切分结果存储和索引

**文件修改**:
- `knowledge-service/app/core/enhanced_knowledge_manager.py` - 集成切分逻辑
- `knowledge-service/app/services/enhanced_document_processor.py` - 文档处理流程

### Phase 3: 实时通信系统 (优先级: 高)

#### 3.1 SSE实时推送
**任务**: 实现服务端推送事件
- 文档处理状态推送
- 切分进度推送
- 错误信息推送

**新增文件**:
- `knowledge-service/app/api/sse_routes.py` - SSE推送接口
- `knowledge-service/app/services/notification_service.py` - 通知服务

#### 3.2 WebSocket支持（可选）
**任务**: 实现双向实时通信
- WebSocket连接管理
- 实时状态更新
- 客户端重连机制

**新增文件**:
- `knowledge-service/app/api/websocket_routes.py` - WebSocket接口
- `knowledge-service/app/services/websocket_manager.py` - 连接管理

### Phase 4: 前端集成 (优先级: 中)

#### 4.1 修复模态框功能
**任务**: 修复前端知识库管理页面
- 诊断模态框无法操作的问题
- 修复API请求和响应处理
- 完善错误处理和用户反馈

**文件修改**:
- 前端知识库管理相关组件
- API调用逻辑
- 模态框状态管理

#### 4.2 文件上传UI组件
**任务**: 实现完整的文件上传界面
- 文件选择和预览
- 切分规则选择界面
- 上传进度和状态显示
- 实时状态更新集成

**新增/修改前端文件**:
- 文件上传组件
- 切分规则选择组件
- 实时状态显示组件

### Phase 5: 测试和优化 (优先级: 中)

#### 5.1 端到端测试
**任务**: 完整流程测试
- 文件上传到存储测试
- 队列处理测试
- 切分逻辑测试
- 实时推送测试

#### 5.2 性能优化
**任务**: 系统性能调优
- 大文件上传优化
- 队列处理性能优化
- 实时推送性能优化

## 实施细节

### 技术选型

#### 存储方案
- **主存储**: MinIO (已配置)
- **元数据**: PostgreSQL (已配置)
- **向量存储**: Milvus (已配置)

#### 队列方案
```python
# 选项1: Celery + Redis (推荐)
from celery import Celery

# 选项2: 自定义Redis队列 (轻量级)
import redis
import json
```

#### 实时通信方案
```python
# SSE实现
from fastapi.responses import StreamingResponse

# WebSocket实现 (可选)
from fastapi import WebSocket
```

### API接口设计

#### 文件上传接口
```python
POST /api/v1/knowledge-bases/{kb_id}/documents/upload
Content-Type: multipart/form-data

{
  "files": [File, File, ...],
  "splitter_strategy_id": "uuid",
  "custom_splitter_config": {...},
  "processing_options": {...}
}
```

#### 切分规则接口
```python
# 获取切分策略列表
GET /api/v1/splitting-strategies

# 创建自定义切分策略
POST /api/v1/splitting-strategies

# 测试切分策略
POST /api/v1/splitting-strategies/{strategy_id}/test
```

#### 实时状态接口
```python
# SSE状态推送
GET /api/v1/knowledge-bases/{kb_id}/upload-status?stream=true

# WebSocket连接
WS /api/v1/knowledge-bases/{kb_id}/ws
```

### 数据流设计

```
[前端文件选择] 
    ↓
[选择切分策略] 
    ↓
[文件上传到MinIO] 
    ↓
[任务加入Redis队列] 
    ↓
[后台异步处理] 
    ↓
[实时状态推送] 
    ↓
[处理完成通知]
```

### 安全考虑

1. **文件类型验证**: 限制允许的文件类型
2. **文件大小限制**: 防止服务器资源耗尽
3. **权限验证**: 确保用户只能操作自己的知识库
4. **MinIO访问控制**: 配置适当的存储桶权限

### 错误处理

1. **上传失败**: 提供重试机制
2. **处理失败**: 任务错误状态和错误信息
3. **连接断开**: 前端重连机制
4. **存储故障**: 错误恢复和回滚

## 开发优先级

### 立即开始 (本周)
1. ✅ 验证MinIO和Redis配置
2. 🔄 实现Redis队列基础设施
3. 🔄 扩展切分规则数据模型

### 第二阶段 (下周)
1. 实现切分规则管理API
2. 集成文档处理队列
3. 实现SSE状态推送

### 第三阶段 (后续)
1. 修复前端模态框问题
2. 完善文件上传UI
3. 端到端测试和优化

## 注意事项

⚠️ **重要**: 所有代码修改完成后，需要手动重启相关服务，不得自动执行启动命令。

⚠️ **配置检查**: 在开始开发前，必须验证MinIO和Redis连接是否正常。

⚠️ **兼容性**: 确保新功能与现有API保持向后兼容。

## 开发环境准备

```bash
# 1. 确认服务状态
pm2 status

# 2. 检查MinIO连接
curl http://localhost:9000/health

# 3. 检查Redis连接
redis-cli ping

# 4. 准备开发环境
cd knowledge-service
pip install celery redis
```

现在可以开始实施Phase 1的任务了！