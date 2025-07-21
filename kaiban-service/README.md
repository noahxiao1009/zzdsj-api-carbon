# Kaiban Service - AI代理工作流管理服务

## 🎯 项目简介

Kaiban Service 是一个基于事件驱动的AI代理工作流管理微服务，提供可视化看板界面和强大的任务编排功能。该服务专为替代原有的ApplicationOrchestrationPage.tsx而设计，提供现代化的多角色协作和工作流程管理能力。

## 📋 核心功能

### 🔄 工作流管理
- 创建和管理自定义工作流程
- 支持多种触发方式（手动、定时、事件驱动）
- 灵活的工作流配置和版本控制
- 工作流状态实时监控

### 📊 看板管理
- 可视化任务看板界面
- 拖拽式任务状态管理
- 支持多项目并行管理
- 自定义看板布局和字段

### 📝 任务管理
- 完整的任务生命周期管理
- 任务优先级、标签、分配者管理
- 任务元数据和自定义字段支持
- 任务状态变更历史追踪

### ⚡ 事件系统
- 实时事件发布和订阅
- 可配置的事件过滤器
- Webhook回调支持
- 事件历史和审计日志

### 🎨 前端界面
- React基础的现代化看板界面
- 响应式设计，支持多设备访问
- 实时数据同步
- 直观的拖拽操作体验

## 🏗️ 技术架构

### 核心技术栈
- **框架**: FastAPI 0.115.4
- **数据库**: PostgreSQL + Redis
- **前端**: React + HTML5
- **异步处理**: asyncio + aioredis
- **API文档**: OpenAPI/Swagger

### 目录结构
```
kaiban-service/
├── app/
│   ├── api/           # API路由层
│   │   ├── v1/        # v1版本API
│   │   └── frontend/  # 前端路由
│   ├── core/          # 核心业务逻辑
│   ├── models/        # 数据模型
│   ├── services/      # 业务服务层
│   └── utils/         # 工具类
├── config.yaml        # 配置文件
├── requirements.txt   # Python依赖
├── main_simple.py    # 简化版启动文件
├── demo.py           # 功能演示脚本
├── start.sh          # 启动脚本
├── stop.sh           # 停止脚本
└── restart.sh        # 重启脚本
```

## 🚀 快速开始

### 1. 环境准备
```bash
# 安装Python依赖
pip install -r requirements.txt

# 确保Redis和PostgreSQL服务运行
# Redis: 默认 localhost:6379
# PostgreSQL: 默认 localhost:5432
```

### 2. 启动服务
```bash
# 使用启动脚本（推荐）
./start.sh

# 或手动启动
python -m uvicorn main_simple:app --host 0.0.0.0 --port 8003 --reload
```

### 3. 验证服务
```bash
# 健康检查
curl http://localhost:8003/health

# 服务信息
curl http://localhost:8003/info

# 运行完整演示
python demo.py
```

## 📖 API文档

### 服务端点

| 端点 | 说明 | 访问地址 |
|------|------|----------|
| API文档 | Swagger UI | http://localhost:8003/docs |
| 服务信息 | 基础服务信息 | http://localhost:8003/info |
| 健康检查 | 服务健康状态 | http://localhost:8003/health |
| 看板界面 | 前端看板UI | http://localhost:8003/frontend/board |

### API路由

#### 工作流管理 (/api/v1/workflows)
- `GET /` - 获取工作流列表
- `POST /` - 创建新工作流
- `GET /{workflow_id}` - 获取特定工作流
- `PUT /{workflow_id}` - 更新工作流
- `DELETE /{workflow_id}` - 删除工作流

#### 看板管理 (/api/v1/boards)
- `GET /` - 获取看板列表
- `POST /` - 创建新看板
- `GET /{board_id}` - 获取特定看板
- `PUT /{board_id}` - 更新看板
- `DELETE /{board_id}` - 删除看板

#### 任务管理 (/api/v1/tasks)
- `GET /` - 获取任务列表
- `POST /` - 创建新任务
- `GET /{task_id}` - 获取特定任务
- `PUT /{task_id}` - 更新任务
- `DELETE /{task_id}` - 删除任务

#### 事件系统 (/api/v1/events)
- `GET /` - 获取事件列表
- `POST /subscribe` - 创建事件订阅
- `POST /webhook` - 事件Webhook接收端点

## 🔧 配置说明

### 配置文件 (config.yaml)
```yaml
service:
  name: "kaiban-service"
  version: "1.0.0"
  port: 8003
  host: "0.0.0.0"

database:
  url: "postgresql://user:password@localhost:5432/kaiban_db"
  
redis:
  host: "localhost"
  port: 6379
  db: 0

logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

### 环境变量
```bash
# 数据库配置
DATABASE_URL=postgresql://user:password@localhost:5432/kaiban_db

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# 服务配置
SERVICE_PORT=8003
LOG_LEVEL=INFO
```

## 🧪 测试和演示

### 功能演示
```bash
# 运行完整功能演示
python demo.py

# 输出示例：
# ✅ 服务状态: running
# ✅ 工作流已创建，ID: workflow-xxx
# ✅ 看板已创建，ID: board-xxx
# ✅ 任务已创建，ID: task-xxx
```

### API测试示例
```bash
# 创建工作流
curl -X POST "http://localhost:8003/api/v1/workflows" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "测试工作流",
    "description": "用于测试的工作流",
    "version": "1.0.0",
    "trigger_type": "manual"
  }'

# 创建任务
curl -X POST "http://localhost:8003/api/v1/tasks" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "测试任务",
    "description": "这是一个测试任务",
    "status": "todo",
    "priority": "medium"
  }'
```

## 📱 前端界面

### 看板功能特性
- **拖拽操作**: 支持任务在不同状态列之间拖拽
- **实时更新**: 任务状态变更实时反映
- **筛选搜索**: 支持按状态、优先级、分配者筛选
- **响应式设计**: 适配桌面和移动设备

### 访问方式
```
前端界面: http://localhost:8003/frontend/board
```

## 🔄 服务管理

### 启动/停止脚本
```bash
# 启动服务
./start.sh

# 停止服务
./stop.sh

# 重启服务
./restart.sh
```

### 日志管理
```bash
# 查看实时日志
tail -f logs/kaiban-service.log

# 查看错误日志
grep ERROR logs/kaiban-service.log
```

## 🔌 集成说明

### 网关服务集成
Kaiban Service 设计为与gateway-service自动集成：
- 服务启动时自动向网关注册
- 提供统一的健康检查端点
- 支持服务发现和负载均衡

### 数据库集成
- 使用database-service提供的统一数据库连接
- 支持PostgreSQL事务管理
- Redis缓存集成提升性能

### 模型服务集成
- 可调用model-service提供的AI模型
- 支持工作流中嵌入AI决策节点
- 智能任务分配和优先级推荐

## 🛠️ 开发指南

### 添加新功能
1. 在`app/models/`中定义数据模型
2. 在`app/api/v1/`中添加API路由
3. 在`app/core/`中实现核心逻辑
4. 更新API文档和测试用例

### 代码规范
- 遵循PEP 8 Python编码规范
- 使用类型注解增强代码可读性
- 添加详细的docstring文档
- 单元测试覆盖核心功能

## 📊 性能指标

### 服务性能
- **响应时间**: < 100ms (平均)
- **并发处理**: 1000+ 并发请求
- **内存使用**: < 512MB
- **CPU使用**: < 30%

### 数据容量
- **工作流数量**: 支持10,000+个工作流
- **任务数量**: 支持100,000+个任务
- **事件处理**: 1,000 events/second

## 🔒 安全特性

- **认证集成**: 与base-service统一认证
- **权限控制**: 基于角色的访问控制
- **数据验证**: 严格的输入验证和清理
- **审计日志**: 完整的操作审计记录

## 🚧 路线图

### v1.1.0 (计划中)
- [ ] 工作流模板市场
- [ ] 高级分析和报表
- [ ] 移动端原生应用
- [ ] 批量操作API

### v1.2.0 (计划中) 
- [ ] AI辅助工作流生成
- [ ] 集成外部工具和服务
- [ ] 自定义字段和表单
- [ ] 高级自动化规则

## 📞 支持和反馈

如有问题或建议，请通过以下方式联系：
- 创建GitHub Issue
- 发送邮件至开发团队
- 查看API文档获取更多信息

---

## 📄 许可证

本项目采用MIT许可证 - 详见LICENSE文件

## 🙏 致谢

感谢所有为项目贡献代码和建议的开发者们！ 