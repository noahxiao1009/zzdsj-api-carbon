# 前端集成准备文档

## 📋 概述

本文档为前端开发者提供知识库微服务的API接口说明和集成指南。第二阶段的后端重构已完成，现在可以开始前端集成工作。

## 🔗 API 基础信息

### 服务地址
- **开发环境**: `http://localhost:8082`
- **API 前缀**: `/api/v1`
- **完整 API 基础路径**: `http://localhost:8082/api/v1`

### 认证方式
- 当前版本暂未实现认证，后续会集成 JWT 认证
- 所有请求都使用 `Content-Type: application/json`

## 🛠️ 核心 API 接口

### 1. 知识库管理

#### 获取知识库列表
```typescript
GET /knowledge-bases?page=1&page_size=10&status=active&search=keyword

Response:
{
  "success": true,
  "data": {
    "knowledge_bases": [
      {
        "id": "uuid",
        "name": "知识库名称",
        "description": "知识库描述",
        "status": "active",
        "document_count": 10,
        "chunk_count": 256,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "embedding_model": "text-embedding-3-small",
        "vector_store_type": "milvus"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 10,
      "total": 50,
      "total_pages": 5
    }
  }
}
```

#### 创建知识库
```typescript
POST /knowledge-bases

Request Body:
{
  "name": "新知识库",
  "description": "知识库描述",
  "embedding_provider": "openai",
  "embedding_model": "text-embedding-3-small",
  "embedding_dimension": 1536,
  "vector_store_type": "milvus",
  "chunk_size": 1000,
  "chunk_overlap": 200,
  "similarity_threshold": 0.7,
  "enable_hybrid_search": true,
  "enable_agno_integration": true,
  "settings": {}
}

Response:
{
  "success": true,
  "message": "知识库创建成功",
  "data": {
    "id": "uuid",
    "name": "新知识库",
    // ... 其他字段
  },
  "frameworks": {
    "llamaindex_enabled": true,
    "agno_enabled": true
  }
}
```

#### 获取知识库详情
```typescript
GET /knowledge-bases/{kb_id}

Response:
{
  "success": true,
  "data": {
    "id": "uuid",
    "name": "知识库名称",
    "description": "知识库描述",
    "status": "active",
    "document_count": 10,
    "chunk_count": 256,
    "total_size": 1024000,
    "embedding_model": "text-embedding-3-small",
    "vector_store_type": "milvus",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z",
    "statistics": {
      "documents": {
        "total_documents": 10,
        "completed_documents": 8,
        "processing_documents": 1,
        "failed_documents": 1
      },
      "chunks": {
        "total_chunks": 256,
        "embedded_chunks": 200,
        "pending_chunks": 56
      }
    }
  }
}
```

#### 更新知识库
```typescript
PUT /knowledge-bases/{kb_id}

Request Body:
{
  "name": "更新后的名称",
  "description": "更新后的描述",
  "similarity_threshold": 0.8
}

Response:
{
  "success": true,
  "message": "知识库更新成功",
  "data": {
    "kb_id": "uuid",
    "updated_fields": ["name", "description", "similarity_threshold"]
  }
}
```

#### 删除知识库
```typescript
DELETE /knowledge-bases/{kb_id}

Response:
{
  "success": true,
  "message": "知识库删除成功",
  "data": {
    "kb_id": "uuid",
    "llamaindex_deleted": true,
    "agno_deleted": true
  }
}
```

### 2. 文档管理

#### 上传文档
```typescript
POST /knowledge-bases/{kb_id}/documents

Request: multipart/form-data
- files: File[]
- chunk_size: number (optional)
- chunk_overlap: number (optional)
- chunk_strategy: string (optional, default: "token_based")
- preserve_structure: boolean (optional, default: true)

Response:
{
  "success": true,
  "message": "成功上传 3 个文件",
  "data": {
    "processed_files": 3,
    "failed_files": 0,
    "results": [
      {
        "filename": "document1.pdf",
        "success": true,
        "document_id": "uuid",
        "job_id": "uuid",
        "status": "processing_started"
      }
    ]
  }
}
```

#### 获取文档列表
```typescript
GET /knowledge-bases/{kb_id}/documents?page=1&page_size=20&status=completed

Response:
{
  "success": true,
  "data": {
    "documents": [
      {
        "id": "uuid",
        "filename": "document1.pdf",
        "file_type": "pdf",
        "file_size": 1024000,
        "status": "completed",
        "chunk_count": 25,
        "created_at": "2024-01-01T00:00:00Z",
        "processed_at": "2024-01-01T00:05:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 10,
      "total_pages": 1
    }
  }
}
```

#### 获取文档详情
```typescript
GET /knowledge-bases/{kb_id}/documents/{doc_id}

Response:
{
  "success": true,
  "data": {
    "document_id": "uuid",
    "filename": "document1.pdf",
    "status": "completed",
    "processing_stage": "completed",
    "chunk_count": 25,
    "token_count": 5000,
    "processed_at": "2024-01-01T00:05:00Z",
    "job_info": {
      "job_id": "uuid",
      "status": "completed",
      "progress": 1.0,
      "started_at": "2024-01-01T00:00:00Z",
      "completed_at": "2024-01-01T00:05:00Z"
    },
    "chunk_statistics": {
      "total_chunks": 25,
      "embedded_chunks": 25,
      "pending_chunks": 0,
      "failed_chunks": 0
    }
  }
}
```

#### 重新处理文档
```typescript
POST /knowledge-bases/{kb_id}/documents/{doc_id}/reprocess

Request: form-data
- chunk_size: number (optional)
- chunk_overlap: number (optional)
- chunk_strategy: string (optional)

Response:
{
  "success": true,
  "message": "文档重新处理已启动",
  "data": {
    "job_id": "uuid"
  }
}
```

### 3. 搜索功能

#### 搜索知识库
```typescript
POST /knowledge-bases/{kb_id}/search

Request Body:
{
  "query": "搜索关键词",
  "search_mode": "hybrid", // "llamaindex" | "agno" | "hybrid"
  "top_k": 5,
  "similarity_threshold": 0.7,
  "enable_reranking": true,
  "vector_weight": 0.7,
  "text_weight": 0.3,
  "agno_confidence_threshold": 0.6
}

Response:
{
  "success": true,
  "data": {
    "query": "搜索关键词",
    "search_mode": "hybrid",
    "results": [
      {
        "chunk_id": "uuid",
        "document_id": "uuid",
        "document_name": "document1.pdf",
        "content": "相关内容片段...",
        "score": 0.85,
        "metadata": {
          "chunk_index": 5,
          "section_title": "第一章"
        }
      }
    ],
    "total_results": 5,
    "search_time": 0.123,
    "llamaindex_results": 3,
    "agno_results": 2,
    "reranked": true,
    "cached": false
  }
}
```

### 4. 嵌入管理

#### 处理待嵌入分块
```typescript
POST /knowledge-bases/{kb_id}/embedding/process?batch_size=50

Response:
{
  "success": true,
  "message": "嵌入处理已启动",
  "data": {
    "total_processed": 50,
    "knowledge_bases": 1,
    "results": {
      "kb_id": {
        "job_id": "uuid",
        "chunk_count": 50
      }
    }
  }
}
```

#### 获取嵌入统计
```typescript
GET /knowledge-bases/{kb_id}/embedding/statistics

Response:
{
  "success": true,
  "data": {
    "total_chunks": 256,
    "embedded_chunks": 200,
    "pending_chunks": 56,
    "failed_chunks": 0,
    "avg_tokens": 500,
    "embedding_models_distribution": {
      "text-embedding-3-small": 200
    }
  }
}
```

### 5. 系统接口

#### 获取全局统计
```typescript
GET /knowledge-bases/statistics

Response:
{
  "success": true,
  "data": {
    "unified_manager": {
      "total_knowledge_bases": 5,
      "active_knowledge_bases": 4,
      "frameworks_enabled": ["llamaindex", "agno"]
    },
    "knowledge_bases": {
      "total_knowledge_bases": 5,
      "active_knowledge_bases": 4,
      "total_documents": 50,
      "total_chunks": 1280
    },
    "chunks": {
      "total_chunks": 1280,
      "embedded_chunks": 1000,
      "total_tokens": 640000
    }
  }
}
```

#### 获取可用嵌入模型
```typescript
GET /knowledge-bases/models/embedding

Response:
{
  "success": true,
  "data": {
    "models": [
      {
        "provider": "openai",
        "model_name": "text-embedding-3-small",
        "dimension": 1536,
        "description": "OpenAI 最新小型嵌入模型"
      },
      {
        "provider": "openai",
        "model_name": "text-embedding-3-large",
        "dimension": 3072,
        "description": "OpenAI 最新大型嵌入模型"
      }
    ],
    "total": 4,
    "provider_counts": {
      "openai": 2,
      "azure_openai": 1,
      "huggingface": 1
    }
  }
}
```

#### 健康检查
```typescript
GET /health

Response:
{
  "status": "healthy",
  "service": "knowledge-service",
  "version": "1.0.0",
  "port": 8082,
  "timestamp": 1672531200.0,
  "stats": {
    "unified_manager": {
      "total_knowledge_bases": 5,
      "active_knowledge_bases": 4
    }
  }
}
```

## 📱 前端集成建议

### 1. 状态管理

推荐使用 React Context 或 Redux 来管理知识库状态：

```typescript
interface KnowledgeBaseState {
  knowledgeBases: KnowledgeBase[];
  currentKnowledgeBase: KnowledgeBase | null;
  documents: Document[];
  loading: boolean;
  error: string | null;
}

interface KnowledgeBase {
  id: string;
  name: string;
  description: string;
  status: 'active' | 'inactive' | 'processing';
  document_count: number;
  chunk_count: number;
  created_at: string;
  updated_at: string;
  embedding_model: string;
  vector_store_type: string;
}

interface Document {
  id: string;
  filename: string;
  file_type: string;
  file_size: number;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  chunk_count: number;
  created_at: string;
  processed_at?: string;
}
```

### 2. API 客户端

创建一个 API 客户端来处理所有请求：

```typescript
class KnowledgeServiceClient {
  private baseURL = 'http://localhost:8082/api/v1';

  async getKnowledgeBases(params: {
    page?: number;
    page_size?: number;
    status?: string;
    search?: string;
  }) {
    const queryParams = new URLSearchParams(params as any);
    const response = await fetch(`${this.baseURL}/knowledge-bases?${queryParams}`);
    return response.json();
  }

  async createKnowledgeBase(data: KnowledgeBaseCreateRequest) {
    const response = await fetch(`${this.baseURL}/knowledge-bases`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return response.json();
  }

  async uploadDocuments(kbId: string, files: File[], options?: {
    chunk_size?: number;
    chunk_overlap?: number;
    chunk_strategy?: string;
  }) {
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));
    
    if (options) {
      Object.entries(options).forEach(([key, value]) => {
        formData.append(key, value.toString());
      });
    }

    const response = await fetch(`${this.baseURL}/knowledge-bases/${kbId}/documents`, {
      method: 'POST',
      body: formData
    });
    return response.json();
  }

  async searchKnowledgeBase(kbId: string, searchRequest: SearchRequest) {
    const response = await fetch(`${this.baseURL}/knowledge-bases/${kbId}/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(searchRequest)
    });
    return response.json();
  }
}
```

### 3. 实时更新

对于文档处理状态，建议实现轮询或 WebSocket：

```typescript
// 轮询示例
const useDocumentStatus = (kbId: string, docId: string) => {
  const [status, setStatus] = useState<DocumentStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const pollStatus = async () => {
      try {
        const response = await client.getDocument(kbId, docId);
        if (response.success) {
          setStatus(response.data);
          setLoading(false);
          
          // 如果还在处理中，继续轮询
          if (response.data.status === 'processing') {
            setTimeout(pollStatus, 2000);
          }
        }
      } catch (error) {
        console.error('Failed to fetch document status:', error);
        setLoading(false);
      }
    };

    pollStatus();
  }, [kbId, docId]);

  return { status, loading };
};
```

### 4. 错误处理

实现统一的错误处理：

```typescript
interface APIError {
  error: string;
  message: string;
  status_code?: number;
}

const handleAPIError = (error: APIError) => {
  switch (error.error) {
    case 'KNOWLEDGE_BASE_NOT_FOUND':
      return '知识库不存在';
    case 'DOCUMENT_UPLOAD_FAILED':
      return '文档上传失败';
    case 'SEARCH_FAILED':
      return '搜索失败';
    default:
      return error.message || '未知错误';
  }
};
```

### 5. 组件更新建议

基于新的 API，需要更新以下组件：

1. **KnowledgeBaseDetailDrawer** 组件：
   - 使用新的 API 获取知识库详情
   - 添加文档上传功能
   - 实现搜索测试功能
   - 显示实时统计信息

2. **KnowledgeBaseFiles** 组件：
   - 集成文档管理 API
   - 添加文档重新处理功能
   - 显示处理状态和进度

3. **主知识库页面**：
   - 使用新的知识库列表 API
   - 添加搜索和筛选功能
   - 实现知识库创建表单

## 🔧 开发环境设置

1. **启动知识库服务**：
   ```bash
   cd /home/wxn/carbon/zzdsl-api-carbon/knowledge-service
   python main.py
   ```

2. **运行 API 测试**：
   ```bash
   cd /home/wxn/carbon/zzdsl-api-carbon/knowledge-service
   python test_api.py
   ```

3. **查看 API 文档**：
   访问 `http://localhost:8082/docs` 查看完整的 API 文档

## 📝 注意事项

1. **异步处理**：文档上传和处理是异步的，需要通过轮询或 WebSocket 获取状态更新
2. **错误处理**：所有 API 都返回统一的错误格式，需要适当处理
3. **文件上传**：支持多文件上传，需要使用 FormData
4. **搜索模式**：支持三种搜索模式，可以根据需求选择
5. **分页**：列表接口都支持分页，需要实现分页组件

## 🎯 下一步行动

1. **更新前端 API 客户端**：使用新的 API 接口
2. **修改组件实现**：集成真实的 API 调用
3. **添加错误处理**：实现统一的错误处理机制
4. **测试集成**：确保前端和后端正常协作
5. **性能优化**：实现缓存、懒加载等优化

这个文档提供了完整的 API 接口说明和集成指南，可以帮助前端开发者快速开始集成工作。