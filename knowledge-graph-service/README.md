# 知识图谱微服务 (Knowledge Graph Service)

基于AI的知识图谱生成、管理和可视化微服务，提供完整的数据集项目管理模式和异步处理能力。

## 🚀 核心特性

### 🧠 AI驱动的知识图谱生成
- **完整迁移原始AI框架**: 保留所有核心处理逻辑和算法
- **三重提取**: 实体识别、关系推理、知识标准化
- **多数据源支持**: 文本内容、知识库、文档集合
- **智能推理**: 基于LLM的关系推断和实体标准化

### 📊 项目化管理模式
- **数据集项目管理**: 按独立项目组织图谱和资源
- **权限控制**: 项目级别的用户权限管理
- **成员协作**: 多用户项目协作支持
- **资源隔离**: 租户级数据隔离和安全

### ⚡ 异步任务处理
- **任务队列**: 基于Celery的分布式任务调度
- **实时进度**: WebSocket进度推送和状态跟踪
- **错误恢复**: 自动重试和错误处理机制
- **批量处理**: 支持大规模数据批量生成

### 🎨 交互式可视化
- **完全保留原始HTML模板**: 无修改迁移vis.js可视化
- **实时交互**: 节点拖拽、缩放、搜索、筛选
- **多主题支持**: 明暗主题切换
- **导出功能**: 多格式数据导出（JSON、Cypher、RDF等）

### 🗄️ 图数据库集成
- **ArangoDB**: 高性能图数据存储
- **租户模式**: 项目级数据库隔离
- **图算法**: 最短路径、邻居查询、社区检测
- **全文搜索**: 实体和关系的语义搜索

## 🏗️ 架构设计

### 微服务架构
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

### 目录结构
```
knowledge-graph-service/
├── app/                              # 应用程序主目录
│   ├── api/                          # API接口层
│   │   ├── project_routes.py         # 项目管理路由
│   │   ├── graph_routes.py           # 图谱管理路由
│   │   └── task_routes.py            # 任务管理路由
│   ├── core/                         # 核心业务逻辑
│   │   ├── graph_generator.py        # 图谱生成器
│   │   ├── visualization_engine.py   # 可视化引擎
│   │   └── task_manager.py           # 任务管理器
│   ├── models/                       # 数据模型
│   │   ├── project.py                # 项目模型
│   │   ├── graph.py                  # 图谱模型
│   │   └── task.py                   # 任务模型
│   ├── services/                     # 服务层
│   │   ├── project_service.py        # 项目服务
│   │   └── graph_service.py          # 图谱服务
│   ├── repositories/                 # 数据访问层
│   │   └── arangodb_repository.py    # ArangoDB访问
│   ├── utils/                        # 工具类
│   │   └── auth.py                   # 认证工具
│   └── config/                       # 配置管理
│       └── settings.py               # 配置文件
├── frameworks/                       # 迁移的AI框架
│   └── ai_knowledge_graph/           # 完整原始框架
├── static/                           # 静态资源
│   ├── vis.js/                       # vis.js库
│   ├── tom-select/                   # tom-select组件
│   └── custom/                       # 自定义JS/CSS
├── templates/                        # HTML模版
│   └── knowledge_graph.html          # 知识图谱展示模版
├── requirements.txt                  # 依赖文件
├── main.py                          # 服务入口
└── README.md                        # 服务说明
```

## 🚀 快速开始

### 环境要求
- Python 3.9+
- ArangoDB 3.8+
- Redis 6.0+
- RabbitMQ 3.8+ (可选，可使用Redis作为Broker)

### 安装依赖
```bash
# 安装Python依赖
pip install -r requirements.txt

# 下载NLTK数据
python -c "import nltk; nltk.download('punkt')"
```

### 环境配置
创建 `.env` 文件：
```bash
# 服务配置
KG_SERVICE_HOST=0.0.0.0
KG_SERVICE_PORT=8087
KG_DEBUG=true

# ArangoDB配置
KG_ARANGODB_URL=http://localhost:8529
KG_ARANGODB_DATABASE=knowledge_graph
KG_ARANGODB_USERNAME=root
KG_ARANGODB_PASSWORD=password

# Redis配置
KG_REDIS_URL=redis://localhost:6379/0

# Celery配置
KG_CELERY_BROKER_URL=redis://localhost:6379/0
KG_CELERY_RESULT_BACKEND=redis://localhost:6379/0

# JWT配置
KG_JWT_SECRET_KEY=your-secret-key-here
```

### 启动服务
```bash
# 启动主服务
python main.py

# 启动Celery Worker (另一个终端)
celery -A app.workers.celery_app worker --loglevel=info

# 启动Celery Beat (定时任务，可选)
celery -A app.workers.celery_app beat --loglevel=info
```

### Docker部署
```bash
# 构建镜像
docker build -t knowledge-graph-service .

# 使用docker-compose启动
docker-compose up -d
```

## 📚 API文档

### 认证
所有API都需要JWT认证，在Header中包含：
```
Authorization: Bearer <your-jwt-token>
```

### 获取Token
```bash
curl -X POST "http://localhost:8087/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

### 核心API端点

#### 项目管理
```bash
# 创建项目
POST /api/v1/projects

# 获取项目列表
GET /api/v1/projects

# 获取项目详情
GET /api/v1/projects/{project_id}

# 更新项目
PUT /api/v1/projects/{project_id}

# 删除项目
DELETE /api/v1/projects/{project_id}
```

#### 图谱管理
```bash
# 创建图谱
POST /api/v1/graphs

# 在项目中创建图谱
POST /api/v1/projects/{project_id}/graphs

# 异步生成图谱
POST /api/v1/graphs/generate

# 获取图谱详情
GET /api/v1/graphs/{graph_id}

# 获取图谱数据
GET /api/v1/graphs/{graph_id}/data

# 获取图谱可视化
GET /api/v1/graphs/{graph_id}/visualization

# 搜索图谱
POST /api/v1/graphs/{graph_id}/search

# 获取实体邻居
GET /api/v1/graphs/{graph_id}/entities/{entity_id}/neighbors

# 获取最短路径
GET /api/v1/graphs/{graph_id}/path/{start_id}/{end_id}

# 导出图谱
POST /api/v1/graphs/{graph_id}/export
```

#### 任务管理
```bash
# 获取任务状态
GET /api/v1/tasks/{task_id}/status

# 获取任务进度
GET /api/v1/tasks/{task_id}/progress

# 取消任务
POST /api/v1/tasks/{task_id}/cancel

# 获取用户任务列表
GET /api/v1/tasks
```

## 🎯 使用示例

### 创建项目并生成图谱
```python
import httpx

# 登录获取token
auth_response = httpx.post("http://localhost:8087/auth/login", json={
    "username": "admin",
    "password": "admin123"
})
token = auth_response.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# 创建项目
project_response = httpx.post("http://localhost:8087/api/v1/projects", 
    headers=headers,
    json={
        "name": "技术文档知识图谱",
        "description": "公司技术文档的知识图谱项目",
        "project_type": "document_set",
        "tags": ["技术文档", "知识管理"]
    }
)
project_id = project_response.json()["project_id"]

# 异步生成图谱
graph_response = httpx.post(f"http://localhost:8087/api/v1/projects/{project_id}/graphs/generate",
    headers=headers,
    json={
        "name": "API文档图谱",
        "data_source": "text",
        "text_content": "FastAPI是一个现代、快速的Python Web框架...",
        "visualization_type": "interactive"
    }
)
task_id = graph_response.json()["task_id"]

# 查询任务进度
progress_response = httpx.get(f"http://localhost:8087/api/v1/tasks/{task_id}/progress",
    headers=headers
)
print(progress_response.json())
```

### 前端集成示例
```javascript
// 获取图谱可视化
async function loadGraphVisualization(graphId) {
    const response = await fetch(`/api/v1/graphs/${graphId}/visualization`, {
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
    });
    
    if (response.ok) {
        const html = await response.text();
        document.getElementById('graph-container').innerHTML = html;
    }
}

// 搜索图谱实体
async function searchEntities(graphId, query) {
    const response = await fetch(`/api/v1/graphs/${graphId}/search`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({
            query: query,
            search_type: 'fuzzy',
            max_results: 50
        })
    });
    
    return response.json();
}
```

## 🔧 配置说明

### 服务配置
```python
# 基础服务配置
SERVICE_NAME = "knowledge-graph-service"
HOST = "0.0.0.0"
PORT = 8087
DEBUG = True

# 数据库配置
ARANGODB_URL = "http://localhost:8529"
ARANGODB_DATABASE = "knowledge_graph"
GRAPH_DATABASE_TENANT_MODE = True

# 异步处理配置
CELERY_BROKER_URL = "redis://localhost:6379/0"
TASK_TIMEOUT = 3600
TASK_RETRY_TIMES = 3

# 知识图谱处理配置
CHUNK_SIZE = 500
MAX_ENTITIES = 1000
MAX_RELATIONS = 5000
CONFIDENCE_THRESHOLD = 0.7

# LLM配置
LLM_TEMPERATURE = 0.3
LLM_MAX_TOKENS = 8192

# 可视化配置
VISUALIZATION_WIDTH = 1200
VISUALIZATION_HEIGHT = 800
VISUALIZATION_PHYSICS = True
```

### 处理配置示例
```json
{
    "chunk_size": 500,
    "overlap_size": 50,
    "llm_model": "claude-3-5-sonnet",
    "temperature": 0.3,
    "max_tokens": 8192,
    "confidence_threshold": 0.7,
    "entity_frequency_threshold": 2,
    "relation_frequency_threshold": 1,
    "enable_standardization": true,
    "enable_inference": true,
    "enable_clustering": true,
    "max_entities": 1000,
    "max_relations": 5000
}
```

### 可视化配置示例
```json
{
    "width": 1200,
    "height": 800,
    "physics_enabled": true,
    "show_labels": true,
    "show_edge_labels": false,
    "color_by_type": true,
    "theme": "light",
    "background_color": "#ffffff",
    "node_size_range": [10, 50],
    "node_color_scheme": "category10",
    "edge_width_range": [1.0, 5.0],
    "edge_color": "#cccccc",
    "enable_zoom": true,
    "enable_drag": true,
    "enable_selection": true
}
```

## 🎨 可视化特性

### 交互功能
- **节点拖拽**: 自由移动和布局调整
- **缩放导航**: 鼠标滚轮缩放和平移
- **实时搜索**: 实体名称和类型快速搜索
- **邻居高亮**: 点击节点高亮相关节点和边
- **路径查找**: 可视化两个实体间的最短路径
- **筛选控制**: 按实体类型、置信度等筛选显示

### 主题和样式
- **明暗主题**: 一键切换明暗两种主题
- **颜色方案**: 支持多种颜色方案（category10、category20、pastel等）
- **物理引擎**: 可开关的力导向布局算法
- **响应式设计**: 适配不同屏幕尺寸

### 导出功能
- **图像导出**: PNG、SVG格式的图像导出
- **数据导出**: JSON、CSV、RDF、Cypher等格式
- **可视化导出**: 完整HTML文件导出
- **统计报告**: 图谱分析报告生成

## 🔍 监控和调试

### 健康检查
```bash
# 服务健康检查
curl http://localhost:8087/health

# 组件健康检查
curl http://localhost:8087/api/v1/projects/health
curl http://localhost:8087/api/v1/tasks/health
```

### 日志查看
```bash
# 查看服务日志
tail -f knowledge_graph_service.log

# 查看Celery日志
celery -A app.workers.celery_app events

# 查看任务状态
celery -A app.workers.celery_app inspect active
```

### 性能监控
- **Prometheus指标**: 集成Prometheus监控
- **任务统计**: 任务执行时间和成功率
- **数据库监控**: ArangoDB连接和查询性能
- **内存使用**: 图谱生成过程的内存监控

## 🚧 开发和贡献

### 开发环境
```bash
# 安装开发依赖
pip install -r requirements-dev.txt

# 代码格式化
black app/ --line-length 120
isort app/

# 类型检查
mypy app/

# 运行测试
pytest tests/ -v
```

### 测试覆盖
```bash
# 运行测试并生成覆盖率报告
pytest --cov=app tests/ --cov-report=html
```

### API测试
使用FastAPI自动生成的API文档进行测试：
- Swagger UI: http://localhost:8087/docs
- ReDoc: http://localhost:8087/redoc

## 📋 注意事项

### 迁移完整性
- ✅ **完全保留原始AI框架**: 所有核心处理逻辑无修改
- ✅ **HTML模板完整迁移**: vis.js可视化效果完全保留
- ✅ **第三方库完整迁移**: 从lib/目录迁移所有依赖
- ✅ **配置参数兼容**: 保持原有配置参数和行为

### 性能优化
- **异步处理**: 大规模图谱生成不阻塞API响应
- **数据库优化**: ArangoDB索引和查询优化
- **缓存策略**: Redis缓存频繁查询的数据
- **内存管理**: 大图谱分批处理和内存回收

### 安全考虑
- **JWT认证**: 所有API接口都需要有效token
- **项目权限**: 项目级别的访问控制
- **数据隔离**: 租户模式确保数据安全
- **输入验证**: 所有用户输入都经过严格验证

## 🔗 相关项目

- **网关服务**: http://localhost:8080
- **知识服务**: http://localhost:8082  
- **模型服务**: http://localhost:8088
- **基础服务**: http://localhost:8085
- **前端项目**: Vue.js/React.js知识图谱管理界面

## 📄 许可证

本项目采用 MIT 许可证。

## 🤝 支持

如有问题或建议，请提交 Issue 或联系开发团队。

---

**Knowledge Graph Service** - AI驱动的企业级知识图谱解决方案