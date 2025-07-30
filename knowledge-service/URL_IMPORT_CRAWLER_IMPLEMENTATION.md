# URL导入爬虫功能实现文档

## 功能概述

本文档描述了知识库服务中新增的URL导入爬虫功能的完整实现。该功能允许用户从URL导入内容到知识库，支持多种爬取模式和内容处理选项。

## 实现架构

### 核心组件

1. **WebCrawlerManager** (`app/core/web_crawler_manager.py`)
   - 核心爬虫管理器，负责URL爬取和内容处理
   - 支持异步并发爬取
   - 集成LlamaIndex和BeautifulSoup进行内容提取
   - 支持多种爬取模式和配置选项

2. **API路由** (`app/api/upload_routes.py`)
   - `/api/v1/knowledge-bases/{kb_id}/documents/import-urls` - URL导入接口
   - `/api/v1/knowledge-bases/{kb_id}/documents/crawl-preview` - 爬虫预览接口

3. **数据模型**
   - `CrawlConfig` - 爬虫配置参数
   - `CrawlResult` - 爬取结果数据结构
   - `URLImportRequest` - API请求模型

## 功能特性

### 支持的爬取模式

1. **单个URL** (`single_url`)
   - 爬取指定的单个URL
   - 适用于导入特定页面内容

2. **URL列表** (`url_list`)
   - 批量爬取多个指定URL
   - 支持并发处理

3. **站点地图** (`sitemap`)
   - 从XML站点地图提取URL
   - 自动发现网站所有页面

4. **域名爬取** (`domain_crawl`)
   - 有限深度的域名内链接发现
   - 支持深度控制和页面数量限制

### 内容处理能力

1. **多种内容提取方式**
   - LlamaIndex集成 (TrafilaturaWebReader, SimpleWebPageReader)
   - BeautifulSoup HTML解析
   - 自动回退机制

2. **内容清洗和过滤**
   - CSS选择器支持（包含和排除）
   - 自动移除导航、脚本、样式等元素
   - 内容长度过滤

3. **格式转换**
   - 自动转换为Markdown格式
   - 保留结构和元数据
   - 支持多种输出格式

4. **元数据管理**
   - 自动提取页面标题和元信息
   - 保留爬取时间和来源URL
   - 生成内容哈希用于去重

## API接口详细说明

### 1. URL导入接口

```http
POST /api/v1/knowledge-bases/{kb_id}/documents/import-urls
Content-Type: application/json

{
  "urls": ["https://example.com/doc1", "https://example.com/doc2"],
  "crawl_mode": "url_list",
  "max_pages": 50,
  "max_depth": 2,
  "concurrent_requests": 5,
  "request_delay": 1.0,
  "use_llamaindex": true,
  "use_trafilatura": true,
  "content_filters": ["script", "style", "nav"],
  "content_selectors": ["article", ".content"],
  "min_content_length": 100,
  "max_content_length": 100000,
  "folder_id": "optional-folder-id",
  "description": "导入描述",
  "enable_async_processing": true
}
```

**响应示例:**
```json
{
  "success": true,
  "message": "URL导入完成，成功创建 2 个处理任务",
  "data": {
    "kb_id": "kb-123",
    "crawl_summary": {
      "total_urls": 2,
      "successful_count": 2,
      "failed_count": 0,
      "processing_tasks_created": 2
    },
    "processing_tasks": [
      {
        "task_id": "task-456",
        "url": "https://example.com/doc1",
        "title": "Document 1",
        "content_length": 1500,
        "status": "pending"
      }
    ],
    "import_time": "2025-07-28T15:30:00"
  }
}
```

### 2. 爬虫预览接口

```http
POST /api/v1/knowledge-bases/{kb_id}/documents/crawl-preview
Content-Type: multipart/form-data

urls=https://example.com/doc1
urls=https://example.com/doc2
max_pages=5
use_trafilatura=true
```

**响应示例:**
```json
{
  "success": true,
  "message": "预览完成，成功爬取 2 个URL",
  "data": {
    "preview_results": [
      {
        "url": "https://example.com/doc1",
        "title": "Document 1",
        "content_preview": "文档内容预览...",
        "markdown_preview": "# Document 1\n\n内容...",
        "content_length": 1500,
        "markdown_length": 1200,
        "status": "completed"
      }
    ],
    "summary": {
      "total_urls": 2,
      "successful_count": 2,
      "failed_count": 0,
      "avg_content_length": 1400
    }
  }
}
```

## 配置参数说明

### CrawlConfig 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `mode` | CrawlMode | SINGLE_URL | 爬取模式 |
| `max_pages` | int | 50 | 最大页面数 |
| `max_depth` | int | 2 | 最大爬取深度 |
| `concurrent_requests` | int | 5 | 并发请求数 |
| `request_delay` | float | 1.0 | 请求延迟(秒) |
| `content_filters` | List[str] | None | CSS选择器过滤器 |
| `content_selectors` | List[str] | None | CSS内容选择器 |
| `min_content_length` | int | 100 | 最小内容长度 |
| `max_content_length` | int | 100000 | 最大内容长度 |
| `use_llamaindex` | bool | True | 是否使用LlamaIndex |
| `use_trafilatura` | bool | True | 是否使用Trafilatura |
| `include_metadata` | bool | True | 是否包含元数据 |
| `follow_redirects` | bool | True | 是否跟随重定向 |
| `respect_robots_txt` | bool | True | 是否遵守robots.txt |

## 集成到现有系统

### 1. 任务队列集成

爬取完成的内容会自动创建处理任务并加入Redis队列：

```python
processing_task = ProcessingTaskModel(
    kb_id=kb_id,
    file_path=stored_filename,
    original_filename=f"{result.title}.md",
    file_size=result.file_size,
    file_type=".md",
    custom_splitter_config={
        "chunk_size": 1000,
        "chunk_overlap": 200,
        "chunk_strategy": "semantic"
    },
    processing_options={
        "source_type": "url_import",
        "source_url": result.url
    }
)
```

### 2. 文件存储集成

爬取的内容自动保存到MinIO：
- 存储路径：`{kb_id}/crawled/{file_id}.md`
- 内容类型：`text/markdown`
- 包含完整的元数据和来源信息

### 3. 文件夹管理集成

支持将导入的内容分配到指定文件夹：
```json
{
  "folder_id": "folder-123",
  "description": "从官网导入的API文档"
}
```

## 错误处理和监控

### 错误类型

1. **网络错误**
   - 连接超时
   - DNS解析失败
   - HTTP错误状态码

2. **内容错误**
   - 内容为空
   - 内容长度不符合要求
   - 解析失败

3. **配置错误**
   - 无效的爬取模式
   - URL格式错误
   - 知识库不存在

### 监控指标

1. **性能指标**
   - 爬取速度 (页面/秒)
   - 平均响应时间
   - 成功率

2. **内容指标**
   - 平均内容长度
   - 去重率
   - 处理成功率

## 测试脚本

### 1. 核心功能测试

```bash
cd /Users/wxn/Desktop/carbon/zzdsl-api-carbon/knowledge-service
python test_web_crawler.py
```

测试内容：
- 基础爬虫功能
- LlamaIndex集成
- 内容过滤功能

### 2. API接口测试

```bash
python test_url_import_api.py
```

测试内容：
- 健康检查
- 爬虫预览API
- URL导入API
- 错误处理

## 性能优化

### 1. 并发控制

```python
# 使用信号量控制并发
semaphore = asyncio.Semaphore(config.concurrent_requests)

async def _crawl_single_url_with_semaphore(url, config, semaphore):
    async with semaphore:
        if config.request_delay > 0:
            await asyncio.sleep(config.request_delay)
        return await self._crawl_single_url(url, config)
```

### 2. 连接池

```python
# 复用HTTP连接
async with aiohttp.ClientSession() as session:
    # 所有请求共享连接池
    pass
```

### 3. 内容缓存

- 使用内容哈希避免重复爬取
- 支持条件请求 (If-Modified-Since)

## 安全考虑

### 1. 请求限制

- 并发请求数限制
- 请求频率控制
- 总页面数限制

### 2. 内容过滤

- 文件大小限制
- 内容类型验证
- 恶意内容检测

### 3. 网络安全

- User-Agent设置
- Robots.txt遵守
- 超时控制

## 部署要求

### 依赖库

```txt
aiohttp>=3.8.0
beautifulsoup4>=4.11.0
markitdown>=0.0.1a2
llama-index>=0.9.0  # 可选
trafilatura>=1.6.0  # 可选
```

### 环境变量

```bash
# 爬虫相关配置
CRAWLER_DEFAULT_DELAY=1.0
CRAWLER_MAX_CONCURRENT=5
CRAWLER_TIMEOUT=30
CRAWLER_USER_AGENT="Knowledge-Service-Crawler/1.0"
```

## 使用示例

### 1. 导入单个技术文档

```python
import aiohttp

url = "http://localhost:8082/api/v1/knowledge-bases/kb-123/documents/import-urls"
data = {
    "urls": ["https://docs.python.org/3/tutorial/introduction.html"],
    "crawl_mode": "single_url",
    "use_llamaindex": True,
    "use_trafilatura": True,
    "folder_id": "python-docs",
    "description": "Python官方教程"
}

async with aiohttp.ClientSession() as session:
    async with session.post(url, json=data) as response:
        result = await response.json()
        print(result)
```

### 2. 批量导入API文档

```python
data = {
    "urls": [
        "https://api.example.com/docs/auth",
        "https://api.example.com/docs/users",
        "https://api.example.com/docs/data"
    ],
    "crawl_mode": "url_list",
    "concurrent_requests": 3,
    "content_selectors": [".api-content", ".documentation"],
    "content_filters": ["nav", ".sidebar", "footer"],
    "folder_id": "api-docs"
}
```

### 3. 爬取整个文档站点

```python
data = {
    "urls": ["https://docs.example.com/sitemap.xml"],
    "crawl_mode": "sitemap",
    "max_pages": 100,
    "use_trafilatura": True,
    "min_content_length": 200
}
```

## 故障排除

### 常见问题

1. **爬取失败**
   - 检查URL可访问性
   - 验证网络连接
   - 查看错误日志

2. **内容质量差**
   - 调整content_selectors
   - 优化content_filters
   - 启用Trafilatura

3. **性能问题**
   - 降低并发数
   - 增加请求延迟
   - 限制爬取深度

### 日志分析

```bash
# 查看爬虫相关日志
grep "WebCrawlerManager" knowledge_service.log

# 查看API调用日志
grep "import-urls" knowledge_service.log
```

## 未来扩展

### 计划功能

1. **内容去重**
   - 基于内容哈希的智能去重
   - 增量更新支持

2. **定时爬取**
   - 定期检查内容更新
   - 自动同步最新内容

3. **高级过滤**
   - 基于内容的智能过滤
   - 自定义过滤规则

4. **多媒体支持**
   - 图片内容提取
   - 视频字幕爬取

## 总结

URL导入爬虫功能为知识库服务提供了强大的内容获取能力，支持灵活的配置和多种使用场景。通过与现有的文档处理流程集成，用户可以轻松地从网络资源导入高质量的结构化内容到知识库中。

该功能已完成基础实现并提供了完整的测试方案，可以立即投入使用。后续可根据实际需求进行功能扩展和性能优化。