# 知识图谱微服务迁移计划

## 1. 项目概述

本项目将原始后端项目 `/Users/wxn/Desktop/carbon/zzdsj-backend-api/app/frameworks/ai_knowledge_graph` 的完整知识图谱功能迁移到微服务架构中，支持数据集项目管理模式和异步处理。

## 2. 架构设计

### 2.1 微服务架构

```
┌─────────────────────────────────────┐
│           Gateway Service           │
│         (端口: 8080)                │
└─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────┐
│    Knowledge Graph Service         │
│         (端口: 8087)                │
├─────────────────────────────────────┤
│  • 图谱生成和提取                    │
│  • 数据集项目管理                    │
│  • 异步任务处理                      │
│  • HTML可视化生成                    │
│  • ArangoDB集成                     │
└─────────────────────────────────────┘
                    │
    ┌───────────────┼───────────────┐
    ▼               ▼               ▼
┌─────────┐   ┌─────────┐   ┌─────────┐
│ArangoDB │   │ Redis   │   │RabbitMQ │
│ 图数据  │   │ 缓存    │   │ 任务队列 │
└─────────┘   └─────────┘   └─────────┘
```

### 2.2 核心组件设计

#### 数据集项目管理
```python
# 数据集项目结构
{
    "project_id": "proj_123",
    "name": "技术文档知识图谱",
    "description": "公司技术文档的知识图谱",
    "owner_id": "user_456",
    "knowledge_base_ids": ["kb_1", "kb_2"],
    "graphs": [
        {
            "graph_id": "graph_789",
            "name": "API文档图谱",
            "status": "completed",
            "created_at": "2024-01-01T00:00:00Z"
        }
    ]
}
```

#### 异步任务处理
```python
# 任务流程
文档上传 → 任务创建 → 队列处理 → 实体提取 → 关系推理 → 图谱生成 → HTML渲染 → 完成通知
```

### 2.3 API设计

#### 数据集项目管理API
```http
# 项目管理
GET    /api/v1/projects                    # 获取项目列表
POST   /api/v1/projects                    # 创建项目
GET    /api/v1/projects/{project_id}       # 获取项目详情
PUT    /api/v1/projects/{project_id}       # 更新项目
DELETE /api/v1/projects/{project_id}       # 删除项目

# 图谱管理
GET    /api/v1/projects/{project_id}/graphs              # 获取项目图谱列表
POST   /api/v1/projects/{project_id}/graphs              # 创建图谱
GET    /api/v1/projects/{project_id}/graphs/{graph_id}   # 获取图谱详情
DELETE /api/v1/projects/{project_id}/graphs/{graph_id}   # 删除图谱
```

#### 图谱生成API
```http
# 异步生成
POST   /api/v1/projects/{project_id}/graphs/generate     # 异步生成图谱
GET    /api/v1/tasks/{task_id}/status                    # 获取任务状态
GET    /api/v1/tasks/{task_id}/progress                  # 获取任务进度

# 可视化
GET    /api/v1/graphs/{graph_id}/visualization           # 获取HTML可视化
GET    /api/v1/graphs/{graph_id}/data                    # 获取图谱数据
```

## 3. 目录结构

```
knowledge-graph-service/
├── app/
│   ├── api/                              # API接口层
│   │   ├── __init__.py
│   │   ├── project_routes.py             # 项目管理路由
│   │   ├── graph_routes.py               # 图谱管理路由
│   │   └── task_routes.py                # 任务管理路由
│   ├── core/                             # 核心业务逻辑
│   │   ├── __init__.py
│   │   ├── graph_generator.py            # 图谱生成器
│   │   ├── visualization_engine.py       # 可视化引擎
│   │   └── task_manager.py               # 任务管理器
│   ├── models/                           # 数据模型
│   │   ├── __init__.py
│   │   ├── project.py                    # 项目模型
│   │   ├── graph.py                      # 图谱模型
│   │   └── task.py                       # 任务模型
│   ├── services/                         # 服务层
│   │   ├── __init__.py
│   │   ├── project_service.py            # 项目服务
│   │   ├── graph_service.py              # 图谱服务
│   │   └── task_service.py               # 任务服务
│   ├── repositories/                     # 数据访问层
│   │   ├── __init__.py
│   │   ├── project_repository.py         # 项目数据访问
│   │   ├── graph_repository.py           # 图谱数据访问
│   │   └── arangodb_repository.py        # ArangoDB访问
│   ├── schemas/                          # API Schema
│   │   ├── __init__.py
│   │   ├── project_schemas.py            # 项目Schema
│   │   ├── graph_schemas.py              # 图谱Schema
│   │   └── task_schemas.py               # 任务Schema
│   ├── utils/                            # 工具类
│   │   ├── __init__.py
│   │   ├── arangodb_utils.py             # ArangoDB工具
│   │   └── async_utils.py                # 异步工具
│   ├── workers/                          # 异步任务处理
│   │   ├── __init__.py
│   │   ├── graph_worker.py               # 图谱生成Worker
│   │   └── celery_app.py                 # Celery应用
│   └── config/                           # 配置管理
│       ├── __init__.py
│       └── settings.py                   # 配置文件
├── frameworks/                           # 迁移的AI框架
│   └── ai_knowledge_graph/               # 完整迁移原始框架
├── static/                               # 静态资源
│   ├── vis.js/                           # vis.js库
│   ├── tom-select/                       # tom-select组件
│   └── custom/                           # 自定义JS/CSS
├── templates/                            # HTML模版
│   └── knowledge_graph.html              # 知识图谱展示模版
├── requirements.txt                      # 依赖文件
├── main.py                               # 服务入口
├── celery_worker.py                      # Celery Worker入口
└── README.md                             # 服务说明
```

## 4. 迁移步骤

### 4.1 阶段一：基础架构搭建（1-2天）
- [x] 创建微服务目录结构
- [x] 设计数据库Schema
- [x] 配置ArangoDB连接
- [x] 设置异步任务队列

### 4.2 阶段二：核心功能迁移（3-4天）
- [ ] 迁移AI知识图谱框架
- [ ] 迁移第三方库文件
- [ ] 适配数据库访问层
- [ ] 实现项目管理功能

### 4.3 阶段三：API和异步处理（2-3天）
- [ ] 实现RESTful API接口
- [ ] 实现异步任务处理
- [ ] 集成HTML可视化生成
- [ ] 实现任务状态管理

### 4.4 阶段四：集成和测试（1-2天）
- [ ] 集成网关层路由
- [ ] 实现微服务通信
- [ ] 端到端测试
- [ ] 性能优化

## 5. 技术要点

### 5.1 数据集项目管理
- 支持多用户项目隔离
- 项目级别的权限管理
- 图谱版本控制
- 批量操作支持

### 5.2 异步处理机制
- 基于Celery的任务队列
- 实时进度反馈
- 错误处理和重试
- 任务状态持久化

### 5.3 ArangoDB集成
- 租户级数据隔离
- 高性能图查询
- 事务支持
- 备份和恢复

### 5.4 可视化保持
- 完全复用原始HTML模版
- 保持vis.js交互效果
- 支持主题切换
- 响应式设计

## 6. 关键特性

### 6.1 完整功能迁移
- ✅ 实体提取和关系推理
- ✅ 图谱可视化和交互
- ✅ 多种导出格式
- ✅ 配置化处理流程

### 6.2 企业级特性
- 🔄 异步任务处理
- 👥 多用户项目管理
- 🗄️ 数据库租户隔离
- 🔌 微服务架构集成

### 6.3 性能优化
- 📈 大规模图谱支持
- 🚀 并行处理能力
- 💾 智能缓存机制
- 🔍 增量更新支持

## 7. 部署配置

### 7.1 环境变量
```bash
# 服务配置
KG_SERVICE_HOST=0.0.0.0
KG_SERVICE_PORT=8087

# ArangoDB配置
ARANGODB_URL=http://localhost:8529
ARANGODB_DATABASE=knowledge_graph
ARANGODB_USERNAME=root
ARANGODB_PASSWORD=password

# Redis配置
REDIS_URL=redis://localhost:6379/0

# Celery配置
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### 7.2 启动命令
```bash
# 启动主服务
python main.py

# 启动Celery Worker
celery -A app.workers.celery_app worker --loglevel=info

# 启动Celery Beat（定时任务）
celery -A app.workers.celery_app beat --loglevel=info
```

## 8. 监控和日志

### 8.1 监控指标
- 图谱生成成功率
- 任务处理延迟
- 数据库连接状态
- 内存和CPU使用率

### 8.2 日志记录
- 结构化日志输出
- 任务执行日志
- 错误详情记录
- 性能分析日志

## 9. 安全考虑

### 9.1 数据安全
- 项目级别访问控制
- 数据加密传输
- 敏感信息脱敏
- 审计日志记录

### 9.2 接口安全
- JWT身份认证
- 请求频率限制
- 输入参数验证
- SQL注入防护

## 10. 未来扩展

### 10.1 功能扩展
- 实时协作编辑
- 图谱版本对比
- 智能推荐系统
- 多语言支持

### 10.2 性能扩展
- 分布式计算支持
- 图数据库集群
- 缓存层优化
- CDN集成

这个迁移计划确保了原始功能的完整性，同时引入了现代微服务架构的所有优势，为知识图谱系统的未来发展奠定了坚实基础。