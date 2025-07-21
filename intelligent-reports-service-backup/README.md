# 智能报告服务 (Intelligent Reports Service)

基于Co-Sight的多智能体报告生成微服务，提供完整的智能报告创建、管理和协作功能。

## 项目概述

智能报告服务是一个独立的微服务，集成了Co-Sight项目的核心功能，提供：

- **多智能体协作**: 规划智能体(TaskPlannerAgent)和执行智能体(TaskActorAgent)协同工作
- **任务计划管理**: 基于DAG的任务依赖管理和并发执行
- **丰富工具集**: 搜索、文件操作、代码执行、图像分析等工具
- **实时流式响应**: 支持WebSocket和流式API响应
- **报告生成**: HTML可视化报告生成和多种图表支持

## 技术架构

### 核心架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                     前端 (React)                            │
│                  智能报告管理界面                            │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                  API网关                                    │
│            认证、路由、负载均衡                              │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                智能报告服务                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │
│  │ 多智能体    │ │ 任务计划    │ │ 工具管理    │            │
│  │ 协作引擎    │ │ 管理器      │ │ 系统        │            │
│  └─────────────┘ └─────────────┘ └─────────────┘            │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │
│  │ 报告生成    │ │ 流式响应    │ │ 模型服务    │            │
│  │ 引擎        │ │ 处理器      │ │ 代理        │            │
│  └─────────────┘ └─────────────┘ └─────────────┘            │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                 基础服务层                                   │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │
│  │ 数据库      │ │ 缓存服务    │ │ 消息队列    │            │
│  │ PostgreSQL  │ │ Redis       │ │ RabbitMQ    │            │
│  └─────────────┘ └─────────────┘ └─────────────┘            │
└─────────────────────────────────────────────────────────────┘
```

### 服务模块设计

```
intelligent-reports-service/
├── app/
│   ├── api/                    # API路由层
│   │   ├── v1/                 # 版本化API
│   │   │   ├── reports.py      # 报告管理API
│   │   │   ├── agents.py       # 智能体管理API
│   │   │   ├── tasks.py        # 任务管理API
│   │   │   └── tools.py        # 工具管理API
│   │   └── websocket/          # WebSocket接口
│   │       └── report_stream.py # 实时报告流
│   ├── core/                   # 核心业务逻辑
│   │   ├── agents/             # 智能体核心
│   │   │   ├── planner/        # 规划智能体
│   │   │   └── actor/          # 执行智能体
│   │   ├── tasks/              # 任务管理
│   │   │   ├── manager.py      # 任务管理器
│   │   │   ├── plan.py         # 计划模型
│   │   │   └── executor.py     # 执行引擎
│   │   └── tools/              # 工具集
│   │       ├── search/         # 搜索工具
│   │       ├── file/           # 文件操作工具
│   │       ├── code/           # 代码执行工具
│   │       └── visualization/  # 可视化工具
│   ├── models/                 # 数据模型
│   │   ├── report.py           # 报告模型
│   │   ├── agent.py            # 智能体模型
│   │   ├── task.py             # 任务模型
│   │   └── user.py             # 用户模型
│   ├── services/               # 业务服务层
│   │   ├── report_service.py   # 报告服务
│   │   ├── agent_service.py    # 智能体服务
│   │   ├── task_service.py     # 任务服务
│   │   └── model_service.py    # 模型服务
│   ├── utils/                  # 工具函数
│   │   ├── db.py               # 数据库工具
│   │   ├── auth.py             # 认证工具
│   │   ├── cache.py            # 缓存工具
│   │   └── logging.py          # 日志工具
│   └── config/                 # 配置管理
│       ├── settings.py         # 应用配置
│       └── database.py         # 数据库配置
├── migrations/                 # 数据库迁移
├── tests/                      # 测试文件
├── docker/                     # Docker配置
├── requirements.txt            # Python依赖
├── Dockerfile                  # Docker构建文件
└── main.py                     # 应用入口
```

## 核心功能

### 1. 多智能体协作

- **TaskPlannerAgent**: 负责分析用户需求，制定详细的执行计划
- **TaskActorAgent**: 负责执行具体的任务步骤
- **协作机制**: 通过共享Plan对象实现智能体间的协作
- **并发执行**: 支持多个步骤并行执行，提高效率

### 2. 任务计划管理

- **DAG结构**: 支持复杂的任务依赖关系
- **状态管理**: 跟踪每个步骤的执行状态
- **动态调度**: 根据依赖关系动态调度就绪任务
- **异常处理**: 支持任务失败重试和错误恢复

### 3. 工具生态系统

- **搜索工具**: 百度搜索、Google搜索、Tavily搜索
- **文件工具**: 文件读写、内容处理、格式转换
- **代码工具**: 代码执行、结果分析、错误处理
- **可视化工具**: 图表生成、报告渲染、数据展示
- **多媒体工具**: 图像分析、视频处理、音频识别

### 4. 报告生成

- **HTML报告**: 基于模板的报告生成
- **数据可视化**: 支持多种图表类型
- **中文支持**: 完整的中文字体和布局支持
- **交互式报告**: 支持动态图表和交互元素

### 5. 实时通信

- **WebSocket**: 实时状态更新
- **流式API**: 支持流式响应
- **事件驱动**: 基于事件的状态通知
- **异步处理**: 高性能的异步处理架构

## 数据模型

### 1. 报告模型

```python
class Report(BaseModel):
    id: str
    title: str
    description: str
    content: str
    status: ReportStatus
    created_by: str
    created_at: datetime
    updated_at: datetime
    plan_id: str
    result_files: List[str]
```

### 2. 智能体模型

```python
class Agent(BaseModel):
    id: str
    name: str
    type: AgentType  # PLANNER, ACTOR
    template_id: str
    configuration: Dict[str, Any]
    status: AgentStatus
    created_at: datetime
```

### 3. 任务模型

```python
class Task(BaseModel):
    id: str
    title: str
    description: str
    steps: List[TaskStep]
    dependencies: Dict[int, List[int]]
    status: TaskStatus
    created_at: datetime
    completed_at: Optional[datetime]
```

## API接口设计

### 1. 报告管理API

```python
# 创建报告
POST /api/v1/reports
# 获取报告列表
GET /api/v1/reports
# 获取报告详情
GET /api/v1/reports/{report_id}
# 更新报告
PUT /api/v1/reports/{report_id}
# 删除报告
DELETE /api/v1/reports/{report_id}
# 生成报告
POST /api/v1/reports/{report_id}/generate
```

### 2. 智能体管理API

```python
# 获取智能体列表
GET /api/v1/agents
# 创建智能体
POST /api/v1/agents
# 获取智能体详情
GET /api/v1/agents/{agent_id}
# 更新智能体
PUT /api/v1/agents/{agent_id}
# 智能体对话
POST /api/v1/agents/{agent_id}/chat
```

### 3. 任务管理API

```python
# 获取任务列表
GET /api/v1/tasks
# 创建任务
POST /api/v1/tasks
# 获取任务详情
GET /api/v1/tasks/{task_id}
# 执行任务
POST /api/v1/tasks/{task_id}/execute
# 任务状态查询
GET /api/v1/tasks/{task_id}/status
```

### 4. WebSocket接口

```python
# 实时报告生成状态
ws://localhost:8000/ws/reports/{report_id}
# 任务执行状态
ws://localhost:8000/ws/tasks/{task_id}
# 智能体对话
ws://localhost:8000/ws/agents/{agent_id}/chat
```

## 技术特性

### 1. 高性能

- **异步处理**: 基于asyncio的高性能异步架构
- **并发执行**: 多线程任务并发执行
- **缓存优化**: Redis缓存提高响应速度
- **连接池**: 数据库连接池管理

### 2. 高可用

- **容错机制**: 智能体失败重试和降级
- **健康检查**: 服务健康状态监控
- **优雅关闭**: 支持优雅关闭和重启
- **监控告警**: 完整的监控和告警体系

### 3. 可扩展

- **模块化设计**: 清晰的模块边界
- **插件系统**: 支持工具插件扩展
- **配置驱动**: 基于配置的功能开关
- **API版本化**: 支持多版本API共存

### 4. 安全性

- **认证授权**: JWT令牌认证
- **权限控制**: 基于角色的访问控制
- **数据加密**: 敏感数据加密存储
- **审计日志**: 完整的操作审计

## 部署方案

### 1. 开发环境

```bash
# 克隆项目
git clone <repository-url>
cd intelligent-reports-service

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
vim .env

# 数据库迁移
alembic upgrade head

# 启动服务
python main.py
```

### 2. 生产环境

```bash
# Docker构建
docker build -t intelligent-reports-service .

# Docker Compose部署
docker-compose up -d

# Kubernetes部署
kubectl apply -f k8s/
```

## 监控和运维

### 1. 监控指标

- **业务指标**: 报告生成成功率、平均生成时间
- **技术指标**: 响应时间、错误率、并发数
- **资源指标**: CPU、内存、数据库连接数

### 2. 日志管理

- **结构化日志**: JSON格式日志
- **链路追踪**: 分布式链路追踪
- **日志聚合**: ELK日志聚合分析

### 3. 告警配置

- **服务可用性**: 服务下线告警
- **性能异常**: 响应时间异常告警
- **错误率**: 高错误率告警
- **资源使用**: 资源使用率告警

## 开发指南

### 1. 环境要求

- Python 3.9+
- PostgreSQL 13+
- Redis 6+
- RabbitMQ 3.8+

### 2. 开发规范

- 代码规范: PEP 8
- 文档规范: Google风格docstring
- 测试覆盖率: > 80%
- 提交规范: Conventional Commits

### 3. 测试策略

```bash
# 单元测试
pytest tests/unit/

# 集成测试
pytest tests/integration/

# 端到端测试
pytest tests/e2e/

# 性能测试
pytest tests/performance/
```

## 常见问题

### 1. 性能优化

- 合理设置并发数量
- 使用缓存减少重复计算
- 优化数据库查询
- 选择合适的模型

### 2. 故障排查

- 检查日志文件
- 验证服务健康状态
- 检查数据库连接
- 验证模型服务可用性

### 3. 扩展开发

- 添加新的工具类型
- 扩展智能体能力
- 自定义报告模板
- 集成新的模型服务

## 贡献指南

1. Fork项目
2. 创建功能分支
3. 提交更改
4. 发起Pull Request
5. 代码审查
6. 合并分支

## 许可证

本项目采用MIT许可证，详见LICENSE文件。

## 联系方式

- 项目维护者: 智能报告团队
- 邮箱: intelligent-reports@company.com
- 文档: https://docs.company.com/intelligent-reports
- 问题反馈: https://github.com/company/intelligent-reports-service/issues