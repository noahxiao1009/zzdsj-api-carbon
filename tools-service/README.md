# 工具微服务 (Tools Service)

统一工具管理微服务，集成WebSailor智能搜索和Scraperr网页爬虫工具，并提供Agno和LlamaIndex框架集成。

## 项目概览

本微服务提供：
- **WebSailor**: 阿里巴巴智能搜索工具，支持批量搜索和智能网页内容提取
- **Scraperr**: 自托管网页爬虫，支持XPath元素提取和域名爬取
- **统一工具API**: 标准化的工具调用接口
- **框架集成**: 支持Agno和LlamaIndex框架的工具集成

## 技术架构

```
Frontend (React/TypeScript)
    ↓
Tools Service API (FastAPI)
    ↓
┌─────────────────┬─────────────────┐
│   WebSailor     │    Scraperr     │
│   (阿里巴巴)     │   (开源爬虫)     │
└─────────────────┴─────────────────┘
    ↓
Framework Integrations
├── Agno Integration
└── LlamaIndex Integration
```

## 快速启动

### 1. 环境准备

```bash
# 进入工具服务目录
cd tools-service

# 安装依赖
pip install -r requirements.txt

# 设置环境变量
export GOOGLE_SEARCH_KEY="your_serper_api_key"
export JINA_API_KEYS="your_jina_api_key1,your_jina_api_key2"
export SCRAPERR_USER_EMAIL="admin@tools.local"
```

### 2. 启动服务

```bash
# 开发模式启动
python main.py

# 或使用uvicorn
uvicorn main:app --reload --port 8090
```

### 3. 验证安装

```bash
# 检查服务状态
curl http://localhost:8090/health

# 检查工具状态
curl http://localhost:8090/api/v1/tools/health
```

## API 接口

### 工具管理

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/v1/tools/list` | GET | 获取工具列表 |
| `/api/v1/tools/health` | GET | 健康检查 |
| `/api/v1/tools/execute` | POST | 执行工具 |
| `/api/v1/tools/metrics` | GET | 获取指标 |

### WebSailor接口

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/v1/tools/websailor/search` | POST | 智能搜索 |
| `/api/v1/tools/websailor/visit` | POST | 网页访问 |

### Scraperr接口

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/v1/tools/scraperr/scrape` | POST | 创建爬取任务 |
| `/api/v1/tools/scraperr/jobs` | GET | 获取任务列表 |
| `/api/v1/tools/scraperr/jobs/{id}` | GET | 获取任务详情 |
| `/api/v1/tools/scraperr/jobs` | DELETE | 删除任务 |

### 框架集成接口

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/v1/integrations/agno/setup` | POST | 设置Agno集成 |
| `/api/v1/integrations/llamaindex/setup` | POST | 设置LlamaIndex集成 |
| `/api/v1/integrations/status` | GET | 获取集成状态 |

## 使用示例

### WebSailor搜索

```python
import httpx

# 搜索示例
response = httpx.post("http://localhost:8090/api/v1/tools/websailor/search", 
    json={"query": "人工智能最新发展"}
)
print(response.json())
```

### Scraperr爬取

```python
import httpx

# 爬取示例
response = httpx.post("http://localhost:8090/api/v1/tools/scraperr/scrape",
    json={
        "url": "https://example.com",
        "elements": [
            {"name": "title", "xpath": "//title"},
            {"name": "content", "xpath": "//p"}
        ]
    }
)
print(response.json())
```

### Agno集成使用

```python
# 设置Agno集成
response = httpx.post("http://localhost:8090/api/v1/integrations/agno/setup")

# 获取Agno工具定义
tools = httpx.get("http://localhost:8090/api/v1/integrations/agno/tools")

# 执行Agno工具
result = httpx.post("http://localhost:8090/api/v1/integrations/agno/execute",
    json={
        "tool": "websailor",
        "action": "search", 
        "parameters": {"query": "AI news"}
    }
)
```

## 前端集成

### 工具广场

访问 `http://localhost:3000/tool-plaza/home` 查看工具广场界面。

### WebSailor测试页面

访问 `http://localhost:3000/tools/websailor` 使用WebSailor工具。

### Scraperr管理页面

访问 `http://localhost:3000/tools/scraperr` 管理爬取任务。

## 配置说明

### 环境变量

| 变量名 | 描述 | 必需 |
|--------|------|------|
| `GOOGLE_SEARCH_KEY` | Serper搜索API密钥 | 是 |
| `JINA_API_KEYS` | Jina Reader API密钥（逗号分隔） | 是 |
| `SCRAPERR_USER_EMAIL` | Scraperr用户邮箱 | 否 |
| `PORT` | 服务端口 | 否 |

### API密钥获取

1. **Serper API**: 访问 [serper.dev](https://serper.dev/) 注册获取
2. **Jina API**: 访问 [jina.ai](https://jina.ai/api-dashboard/) 注册获取

## 开发指南

### 项目结构

```
tools-service/
├── app/
│   ├── api/                    # API接口
│   │   ├── tools_api.py       # 工具API
│   │   └── integrations_api.py # 集成API
│   ├── core/                   # 核心组件
│   │   ├── tool_manager.py    # 工具管理器
│   │   └── logger.py          # 日志配置
│   ├── tools/                  # 工具实现
│   │   ├── webagent_tool.py   # WebSailor工具
│   │   └── scraperr_tool.py   # Scraperr工具
│   ├── integrations/           # 框架集成
│   │   ├── agno_integration.py
│   │   └── llamaindex_integration.py
│   └── schemas/                # 数据模型
│       └── tool_schemas.py
├── WebAgent/                   # WebAgent项目
├── Scraperr/                   # Scraperr项目
├── main.py                     # 应用入口
└── requirements.txt            # 依赖列表
```

### 添加新工具

1. 在 `app/tools/` 目录创建工具实现
2. 继承基础工具接口
3. 在 `tool_manager.py` 中注册工具
4. 添加API接口和前端界面

### 测试

```bash
# 运行测试
pytest tests/

# 健康检查
curl http://localhost:8090/health

# 工具状态检查
curl http://localhost:8090/api/v1/tools/health
```

## 监控和日志

### 健康检查

服务提供多层健康检查：
- 基础服务健康检查: `/health`
- 工具健康检查: `/api/v1/tools/health`
- 集成状态检查: `/api/v1/integrations/status`

### 性能指标

工具调用指标包括：
- 总调用次数
- 成功率
- 平均响应时间
- 24小时内调用次数

### 日志配置

日志文件位置和配置见 `app/core/logger.py`。

## 故障排除

### 常见问题

1. **工具初始化失败**
   - 检查API密钥是否正确设置
   - 确认网络连接正常
   - 查看服务日志

2. **搜索功能异常**
   - 验证Serper API密钥
   - 检查搜索查询格式

3. **爬虫任务失败**
   - 确认目标网站可访问
   - 检查XPath表达式语法
   - 验证数据库连接

### 调试模式

```bash
# 启用调试日志
export LOG_LEVEL=DEBUG
python main.py
```

## 贡献指南

1. Fork项目
2. 创建功能分支
3. 提交更改
4. 创建Pull Request

## 许可证

本项目采用MIT许可证，详见LICENSE文件。

## 相关链接

- [WebAgent项目](https://github.com/Alibaba-NLP/WebAgent)
- [Scraperr项目](https://github.com/jaypyles/www-scrape)
- [Agno框架文档](https://docs.agno.com/)
- [LlamaIndex文档](https://docs.llamaindex.ai/)