# 知识库服务 (Knowledge Service)

基于 LlamaIndex 和 Agno 框架的微服务化知识库管理系统，提供企业级文档处理、向量化存储和智能检索功能。

## 功能特性

### 核心功能
- **知识库管理**: 创建、配置、管理和删除知识库
- **文档处理**: 支持多种文档格式的上传、解析和处理
- **分块策略**: 提供基础分块、语义分块、智能分块等多种策略
- **向量化存储**: 基于多种嵌入模型的向量化和存储
- **智能检索**: 支持向量检索、关键词检索和混合检索
- **框架集成**: 同时支持 LlamaIndex 和 Agno 框架的检索

### 技术特点
- **LlamaIndex框架**: 基于官方LlamaIndex框架，提供专业的RAG能力
- **Agno集成**: 支持Agno框架的自定义检索调度
- **多模态支持**: 支持文本、图片、表格等多种数据类型
- **可扩展架构**: 支持自定义分块器和嵌入模型
- **高性能**: 基于Milvus的高性能向量存储和检索

## API接口文档

### 知识库管理

#### 创建知识库
```http
POST /knowledge-bases/
```

**请求体:**
```json
{
  "name": "技术文档库",
  "description": "存储技术文档和API说明",
  "config": {
    "embedding_model": "text-embedding-3-small",
    "chunk_size": 1000,
    "chunk_overlap": 200,
    "chunk_strategy": "semantic"
  }
}
```

**响应示例:**
```json
{
  "success": true,
  "message": "知识库创建成功",
  "data": {
    "id": "kb_001",
    "name": "技术文档库",
    "description": "存储技术文档和API说明",
    "status": "active",
    "document_count": 0,
    "total_chunks": 0,
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

#### 获取知识库列表
```http
GET /knowledge-bases/?page=1&page_size=10&search=技术
```

**查询参数:**
- `page`: 页码 (默认: 1)
- `page_size`: 每页大小 (默认: 10, 最大: 100)
- `search`: 搜索关键词
- `status`: 状态筛选 (active, inactive)

#### 获取知识库详情
```http
GET /knowledge-bases/{kb_id}
```

#### 更新知识库
```http
PUT /knowledge-bases/{kb_id}
```

#### 删除知识库
```http
DELETE /knowledge-bases/{kb_id}
```

### 文档管理

#### 上传文档
```http
POST /knowledge-bases/{kb_id}/documents/upload
```

**请求参数:**
- `files`: 文档文件 (支持多文件上传)
- `chunk_strategy`: 分块策略 (auto, semantic, fixed, paragraph)
- `process_immediately`: 是否立即处理 (默认: true)

**支持的文档格式:**
- PDF文档 (.pdf)
- Word文档 (.docx, .doc)
- Excel表格 (.xlsx, .xls)
- PowerPoint演示文稿 (.pptx, .ppt)
- 纯文本文件 (.txt, .md)
- 网页文件 (.html)

**响应示例:**
```json
{
  "success": true,
  "message": "文档上传成功",
  "data": {
    "uploaded_files": [
      {
        "filename": "API文档.pdf",
        "size": 1024000,
        "document_id": "doc_001",
        "status": "processing"
      }
    ],
    "total_files": 1,
    "processing_status": "started"
  }
}
```

#### 从URL添加文档
```http
POST /knowledge-bases/{kb_id}/documents/url
```

**请求体:**
```json
{
  "urls": [
    "https://example.com/doc1.pdf",
    "https://example.com/page1.html"
  ],
  "extract_links": false,
  "max_depth": 1
}
```

#### 获取文档列表
```http
GET /knowledge-bases/{kb_id}/documents?page=1&page_size=20&search=API&file_type=pdf&status=completed
```

**查询参数:**
- `page`: 页码
- `page_size`: 每页大小
- `search`: 搜索关键词
- `file_type`: 文件类型筛选 (pdf, docx, txt等)
- `status`: 处理状态筛选 (pending, processing, completed, failed)

#### 获取文档详情
```http
GET /knowledge-bases/{kb_id}/documents/{doc_id}
```

**响应示例:**
```json
{
  "success": true,
  "data": {
    "id": "doc_001",
    "filename": "API文档.pdf",
    "file_type": "pdf",
    "file_size": 1024000,
    "status": "completed",
    "chunk_count": 50,
    "vector_count": 50,
    "processing_time": 30.5,
    "created_at": "2024-01-15T10:30:00Z",
    "completed_at": "2024-01-15T10:31:00Z",
    "metadata": {
      "pages": 20,
      "language": "zh-CN",
      "encoding": "utf-8"
    }
  }
}
```

#### 删除文档
```http
DELETE /knowledge-bases/{kb_id}/documents/{doc_id}
```

#### 重新处理文档
```http
POST /knowledge-bases/{kb_id}/documents/{doc_id}/reprocess?chunk_strategy=semantic&force=false
```

### 分块管理

#### 获取文档分块
```http
GET /knowledge-bases/{kb_id}/documents/{doc_id}/chunks?page=1&page_size=20
```

**响应示例:**
```json
{
  "success": true,
  "data": {
    "chunks": [
      {
        "id": "chunk_001",
        "content": "这是文档的第一个分块内容...",
        "position": {
          "page": 1,
          "paragraph": 1,
          "start_char": 0,
          "end_char": 500
        },
        "vector_status": "completed",
        "created_at": "2024-01-15T10:30:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 50,
      "total_pages": 3
    }
  }
}
```

### 智能检索

#### 执行检索
```http
POST /knowledge-bases/search
```

**请求体:**
```json
{
  "query": "如何使用API接口",
  "knowledge_base_id": "kb_001",
  "search_mode": "hybrid",
  "top_k": 5,
  "include_metadata": true
}
```

**检索模式:**
- `vector`: 纯向量检索
- `keyword`: 纯关键词检索
- `hybrid`: 混合检索 (推荐)
- `llamaindex`: 使用LlamaIndex检索
- `agno`: 使用Agno框架检索

**响应示例:**
```json
{
  "query": "如何使用API接口",
  "search_mode": "hybrid",
  "results": [
    {
      "content": "API接口使用说明：首先需要获取访问令牌...",
      "score": 0.95,
      "metadata": {
        "document_id": "doc_001",
        "document_name": "API文档.pdf",
        "page": 5,
        "chunk_id": "chunk_005"
      }
    }
  ],
  "total_results": 5,
  "search_time": 0.12,
  "llamaindex_results": 3,
  "agno_results": 2
}
```

#### 测试检索
```http
POST /knowledge-bases/{kb_id}/test/search?query=测试查询&search_mode=hybrid&top_k=5&include_scores=true&include_content=true
```

### 向量化管理

#### 向量化知识库
```http
POST /knowledge-bases/{kb_id}/vectorize
```

**请求体:**
```json
{
  "embedding_model": "text-embedding-3-small",
  "batch_size": 100,
  "force_reprocess": false
}
```

#### 获取向量化状态
```http
GET /knowledge-bases/{kb_id}/vectorization-status
```

### 配置管理

#### 更新知识库配置
```http
PUT /knowledge-bases/{kb_id}/config
```

**请求体:**
```json
{
  "embedding_model": "text-embedding-3-large",
  "chunk_size": 1500,
  "chunk_overlap": 300,
  "chunk_strategy": "semantic",
  "retrieval_top_k": 10,
  "similarity_threshold": 0.7
}
```

#### 获取可用嵌入模型
```http
GET /knowledge-bases/models/embedding?provider=openai
```

**响应示例:**
```json
{
  "success": true,
  "data": {
    "models": [
      {
        "id": "text-embedding-3-small",
        "name": "Text Embedding 3 Small",
        "provider": "openai",
        "dimensions": 1536,
        "max_input": 8192,
        "cost_per_token": 0.00002,
        "performance": "high",
        "available": true
      }
    ],
    "total": 5,
    "provider_counts": {
      "openai": 3,
      "azure_openai": 1,
      "huggingface": 1
    }
  }
}
```

### 系统监控

#### 健康检查
```http
GET /knowledge-bases/health
```

**响应示例:**
```json
{
  "success": true,
  "data": {
    "service": "knowledge-service",
    "status": "healthy",
    "timestamp": "2024-01-15T10:30:00Z",
    "version": "1.0.0",
    "frameworks": {
      "llamaindex": true,
      "agno": true
    },
    "total_knowledge_bases": 5
  }
}
```

## 快速开始

### 环境要求
- Python 3.11+
- FastAPI
- LlamaIndex Framework
- Agno Framework (可选)
- Milvus 2.0+ (向量数据库)
- Elasticsearch 8.0+ (可选，用于关键词检索)
- PostgreSQL (用于元数据存储)

### 安装依赖
```bash
cd zzdsl-api-carbon/knowledge-service
pip install -r requirements.txt
```

### 配置环境变量
```bash
# .env 文件
# 向量数据库配置
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_USER=
MILVUS_PASSWORD=

# 数据库配置
DATABASE_URL=postgresql://user:password@localhost/knowledgedb

# 嵌入模型配置
OPENAI_API_KEY=your_openai_api_key
AZURE_OPENAI_API_KEY=your_azure_key
AZURE_OPENAI_ENDPOINT=your_azure_endpoint

# Elasticsearch配置 (可选)
ELASTICSEARCH_URL=http://localhost:9200

# Agno框架配置 (可选)
AGNO_API_KEY=your_agno_api_key

# 文件存储配置
DOCUMENT_STORAGE_PATH=/data/documents
MAX_FILE_SIZE=50MB
```

### 启动服务
```bash
# 开发模式
uvicorn main:app --host 0.0.0.0 --port 8002 --reload

# 生产模式
uvicorn main:app --host 0.0.0.0 --port 8002
```

### 验证服务
```bash
curl http://localhost:8002/knowledge-bases/health
```

## 配置说明

### LlamaIndex配置
```yaml
llamaindex:
  chunk_size: 1000
  chunk_overlap: 200
  embedding_model: "text-embedding-3-small"
  vector_store:
    type: "milvus"
    collection_name: "knowledge_vectors"
    similarity_metric: "cosine"
```

### Milvus配置
```yaml
milvus:
  host: "${MILVUS_HOST}"
  port: ${MILVUS_PORT}
  user: "${MILVUS_USER}"
  password: "${MILVUS_PASSWORD}"
  collection_params:
    dim: 1536
    metric_type: "COSINE"
    index_type: "IVF_FLAT"
    nlist: 1024
```

### 文档处理配置
```yaml
document_processing:
  max_file_size: 50MB
  allowed_extensions:
    - .pdf
    - .docx
    - .doc
    - .txt
    - .md
    - .html
  chunk_strategies:
    - auto
    - semantic
    - fixed
    - paragraph
```

## 开发指南

### 项目结构
```
knowledge-service/
├── app/
│   ├── api/
│   │   └── knowledge_routes.py     # API路由定义
│   ├── core/
│   │   ├── knowledge_manager.py    # 知识库管理器
│   │   ├── document_processor.py   # 文档处理器
│   │   └── vector_store.py         # 向量存储
│   ├── schemas/
│   │   └── knowledge_schemas.py    # 数据模型定义
│   ├── models/
│   │   └── knowledge_models.py     # 数据库模型
│   └── utils/
│       ├── chunking.py             # 分块工具
│       └── embedding.py            # 嵌入工具
├── main.py                         # 应用入口
├── requirements.txt                # 依赖包列表
└── README.md                      # 项目文档
```

### 添加新的分块策略
1. 在 `chunking.py` 中实现新的分块器
2. 注册到分块策略管理器
3. 添加配置选项和验证
4. 更新API文档

### 集成新的嵌入模型
1. 在 `embedding.py` 中添加模型支持
2. 更新模型列表和配置
3. 添加模型测试用例
4. 更新模型选择界面

### 扩展检索功能
1. 实现新的检索算法
2. 注册到检索管理器
3. 添加配置选项
4. 提供API接口

## 性能优化

### 分块策略选择
- **固定分块**: 处理速度快，适合结构化文档
- **语义分块**: 质量高，适合非结构化文档
- **智能分块**: 自适应，适合混合文档类型
- **段落分块**: 保持结构，适合格式化文档

### 嵌入模型选择
- **text-embedding-3-small**: 性价比高，适合大规模部署
- **text-embedding-3-large**: 精度高，适合高质量检索
- **本地模型**: 数据安全，适合私有部署

### 检索优化
- 使用混合检索提高召回率
- 调整相似度阈值过滤低质量结果
- 启用缓存减少重复计算
- 优化向量索引参数

## 安全考虑

### 数据安全
- 文档内容加密存储
- 向量数据访问控制
- API接口认证授权
- 敏感信息脱敏处理

### 隐私保护
- 用户数据隔离
- 查询日志脱敏
- 数据删除确认
- 合规性检查

## 与其他服务集成

### 智能体服务集成
- 提供知识库检索能力
- 支持智能体知识库绑定
- 实现上下文增强生成

### 模型服务集成
- 获取可用嵌入模型
- 统一模型调用接口
- 模型性能监控

### 系统服务集成
- 文件上传和存储
- 敏感词过滤
- 系统配置管理
