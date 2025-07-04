"""
知识库相关数据模型
定义知识库、文档、检索等相关的Pydantic模型
"""

from typing import Dict, List, Any, Optional, Union, Literal
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator
import uuid


class EmbeddingProviderType(str, Enum):
    """嵌入模型提供商类型"""
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    HUGGINGFACE = "huggingface"
    LOCAL = "local"
    ANTHROPIC = "anthropic"
    COHERE = "cohere"


class VectorStoreType(str, Enum):
    """向量存储类型"""
    MILVUS = "milvus"
    PGVECTOR = "pgvector"
    ELASTICSEARCH = "elasticsearch"
    LANCEDB = "lancedb"
    SIMPLE = "simple"


class DocumentType(str, Enum):
    """文档类型"""
    PDF = "pdf"
    TXT = "txt"
    DOCX = "docx"
    DOC = "doc"
    MD = "markdown"
    CSV = "csv"
    JSON = "json"
    HTML = "html"
    URL = "url"


class ProcessingStatus(str, Enum):
    """处理状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SearchMode(str, Enum):
    """搜索模式"""
    LLAMAINDEX = "llamaindex"  # 精细化检索，使用LlamaIndex
    AGNO = "agno"             # 快速检索，使用Agno框架
    HYBRID = "hybrid"         # 混合模式


# ===== 嵌入模型相关 =====

class EmbeddingModelConfig(BaseModel):
    """嵌入模型配置"""
    provider: EmbeddingProviderType = Field(..., description="提供商类型")
    model_name: str = Field(..., description="模型名称")
    dimension: int = Field(default=1536, description="向量维度")
    api_key: Optional[str] = Field(None, description="API密钥")
    base_url: Optional[str] = Field(None, description="API基础URL")
    api_version: Optional[str] = Field(None, description="API版本")
    max_retries: int = Field(default=3, description="最大重试次数")
    timeout: int = Field(default=60, description="超时时间")
    batch_size: int = Field(default=100, description="批处理大小")
    
    class Config:
        use_enum_values = True


class EmbeddingModelList(BaseModel):
    """可用嵌入模型列表响应"""
    models: List[Dict[str, Any]] = Field(..., description="模型列表")
    total: int = Field(..., description="总数")
    provider_counts: Dict[str, int] = Field(..., description="按提供商分组的数量")


# ===== 知识库相关 =====

class KnowledgeBaseCreate(BaseModel):
    """创建知识库请求"""
    name: str = Field(..., min_length=1, max_length=100, description="知识库名称")
    description: Optional[str] = Field(None, max_length=500, description="知识库描述")
    
    # 嵌入配置
    embedding_provider: EmbeddingProviderType = Field(
        default=EmbeddingProviderType.OPENAI, 
        description="嵌入模型提供商"
    )
    embedding_model: str = Field(
        default="text-embedding-3-small", 
        description="嵌入模型名称"
    )
    embedding_dimension: int = Field(default=1536, description="嵌入维度")
    
    # 向量存储配置
    vector_store_type: VectorStoreType = Field(
        default=VectorStoreType.PGVECTOR, 
        description="向量存储类型"
    )
    
    # 处理配置
    chunk_size: int = Field(default=1000, ge=100, le=4000, description="文档分块大小")
    chunk_overlap: int = Field(default=200, ge=0, le=1000, description="分块重叠大小")
    
    # LlamaIndex配置
    enable_hybrid_search: bool = Field(default=True, description="启用混合搜索")
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="相似度阈值")
    
    # Agno配置
    enable_agno_integration: bool = Field(default=True, description="启用Agno集成")
    agno_search_type: str = Field(default="hybrid", description="Agno搜索类型")
    
    # 其他配置
    settings: Optional[Dict[str, Any]] = Field(default_factory=dict, description="其他配置")
    
    class Config:
        use_enum_values = True


class KnowledgeBaseUpdate(BaseModel):
    """更新知识库请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="知识库名称")
    description: Optional[str] = Field(None, max_length=500, description="知识库描述")
    
    # 可更新的配置
    chunk_size: Optional[int] = Field(None, ge=100, le=4000, description="文档分块大小")
    chunk_overlap: Optional[int] = Field(None, ge=0, le=1000, description="分块重叠大小")
    similarity_threshold: Optional[float] = Field(None, ge=0.0, le=1.0, description="相似度阈值")
    enable_hybrid_search: Optional[bool] = Field(None, description="启用混合搜索")
    enable_agno_integration: Optional[bool] = Field(None, description="启用Agno集成")
    
    settings: Optional[Dict[str, Any]] = Field(None, description="其他配置")


class KnowledgeBaseResponse(BaseModel):
    """知识库响应"""
    id: str = Field(..., description="知识库ID")
    name: str = Field(..., description="知识库名称")
    description: Optional[str] = Field(None, description="知识库描述")
    
    # 配置信息
    embedding_provider: str = Field(..., description="嵌入模型提供商")
    embedding_model: str = Field(..., description="嵌入模型名称")
    embedding_dimension: int = Field(..., description="嵌入维度")
    vector_store_type: str = Field(..., description="向量存储类型")
    
    # 处理配置
    chunk_size: int = Field(..., description="文档分块大小")
    chunk_overlap: int = Field(..., description="分块重叠大小")
    similarity_threshold: float = Field(..., description="相似度阈值")
    
    # 状态信息
    status: str = Field(..., description="知识库状态")
    document_count: int = Field(default=0, description="文档数量")
    chunk_count: int = Field(default=0, description="分块数量")
    
    # 时间信息
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    # 其他配置
    settings: Dict[str, Any] = Field(default_factory=dict, description="其他配置")


class KnowledgeBaseStats(BaseModel):
    """知识库统计信息"""
    id: str = Field(..., description="知识库ID")
    name: str = Field(..., description="知识库名称")
    document_count: int = Field(..., description="文档数量")
    chunk_count: int = Field(..., description="分块数量")
    total_size: int = Field(..., description="总大小(字节)")
    last_updated: datetime = Field(..., description="最后更新时间")
    vector_count: int = Field(..., description="向量数量")
    avg_chunk_size: float = Field(..., description="平均分块大小")


class KnowledgeBaseList(BaseModel):
    """知识库列表响应"""
    knowledge_bases: List[KnowledgeBaseResponse] = Field(..., description="知识库列表")
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页大小")


# ===== 文档相关 =====

class DocumentCreate(BaseModel):
    """创建文档请求"""
    name: str = Field(..., min_length=1, max_length=200, description="文档名称")
    content: Optional[str] = Field(None, description="文档内容")
    document_type: DocumentType = Field(..., description="文档类型")
    source_url: Optional[str] = Field(None, description="源URL")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")
    
    # 处理选项
    auto_process: bool = Field(default=True, description="自动处理")
    chunk_override: Optional[Dict[str, Any]] = Field(None, description="分块参数覆盖")
    
    class Config:
        use_enum_values = True


class DocumentUpload(BaseModel):
    """文档上传请求"""
    knowledge_base_id: str = Field(..., description="知识库ID")
    auto_process: bool = Field(default=True, description="自动处理")
    extract_metadata: bool = Field(default=True, description="提取元数据")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="额外元数据")


class DocumentResponse(BaseModel):
    """文档响应"""
    id: str = Field(..., description="文档ID")
    knowledge_base_id: str = Field(..., description="知识库ID")
    name: str = Field(..., description="文档名称")
    document_type: str = Field(..., description="文档类型")
    file_path: Optional[str] = Field(None, description="文件路径")
    source_url: Optional[str] = Field(None, description="源URL")
    
    # 状态信息
    status: ProcessingStatus = Field(..., description="处理状态")
    chunk_count: int = Field(default=0, description="分块数量")
    file_size: int = Field(default=0, description="文件大小")
    
    # 时间信息
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    processed_at: Optional[datetime] = Field(None, description="处理完成时间")
    
    # 元数据和错误信息
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    error_message: Optional[str] = Field(None, description="错误信息")


class DocumentList(BaseModel):
    """文档列表响应"""
    documents: List[DocumentResponse] = Field(..., description="文档列表")
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页大小")


class DocumentChunk(BaseModel):
    """文档分块"""
    id: str = Field(..., description="分块ID")
    document_id: str = Field(..., description="文档ID")
    content: str = Field(..., description="分块内容")
    chunk_index: int = Field(..., description="分块索引")
    start_char: int = Field(..., description="起始字符位置")
    end_char: int = Field(..., description="结束字符位置")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="分块元数据")
    embedding: Optional[List[float]] = Field(None, description="向量嵌入")


# ===== 检索相关 =====

class SearchRequest(BaseModel):
    """搜索请求"""
    query: str = Field(..., min_length=1, description="搜索查询")
    knowledge_base_id: str = Field(..., description="知识库ID")
    
    # 搜索参数
    search_mode: SearchMode = Field(default=SearchMode.HYBRID, description="搜索模式")
    top_k: int = Field(default=5, ge=1, le=50, description="返回结果数量")
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="相似度阈值")
    
    # LlamaIndex参数
    enable_reranking: bool = Field(default=True, description="启用重排序")
    vector_weight: float = Field(default=0.7, ge=0.0, le=1.0, description="向量搜索权重")
    text_weight: float = Field(default=0.3, ge=0.0, le=1.0, description="文本搜索权重")
    
    # Agno参数
    agno_confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0, description="Agno置信度阈值")
    
    # 过滤条件
    filter_conditions: Optional[Dict[str, Any]] = Field(None, description="过滤条件")
    include_metadata: bool = Field(default=True, description="包含元数据")
    
    class Config:
        use_enum_values = True
    
    @validator('vector_weight', 'text_weight')
    def validate_weights(cls, v, values):
        if 'vector_weight' in values and 'text_weight' in values:
            if abs(values['vector_weight'] + values['text_weight'] - 1.0) > 0.01:
                raise ValueError("向量权重和文本权重之和必须等于1.0")
        return v


class SearchResult(BaseModel):
    """搜索结果项"""
    chunk_id: str = Field(..., description="分块ID")
    document_id: str = Field(..., description="文档ID")
    document_name: str = Field(..., description="文档名称")
    content: str = Field(..., description="内容")
    score: float = Field(..., description="相似度分数")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    chunk_index: int = Field(..., description="分块索引")
    highlights: Optional[List[str]] = Field(None, description="高亮片段")


class SearchResponse(BaseModel):
    """搜索响应"""
    query: str = Field(..., description="搜索查询")
    search_mode: str = Field(..., description="搜索模式")
    results: List[SearchResult] = Field(..., description="搜索结果")
    total_results: int = Field(..., description="总结果数")
    search_time: float = Field(..., description="搜索时间(秒)")
    
    # 检索统计
    llamaindex_results: int = Field(default=0, description="LlamaIndex检索结果数")
    agno_results: int = Field(default=0, description="Agno检索结果数")
    
    # 额外信息
    reranked: bool = Field(default=False, description="是否进行了重排序")
    cached: bool = Field(default=False, description="结果是否来自缓存")


# ===== 批量操作 =====

class BatchProcessingRequest(BaseModel):
    """批量处理请求"""
    knowledge_base_id: str = Field(..., description="知识库ID")
    document_ids: List[str] = Field(..., description="文档ID列表")
    operation: Literal["reprocess", "delete", "update_metadata"] = Field(..., description="操作类型")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="操作参数")


class BatchProcessingResponse(BaseModel):
    """批量处理响应"""
    task_id: str = Field(..., description="任务ID")
    operation: str = Field(..., description="操作类型")
    total_items: int = Field(..., description="总项目数")
    status: ProcessingStatus = Field(..., description="处理状态")
    created_at: datetime = Field(..., description="创建时间")
    
    # 进度信息
    processed_items: int = Field(default=0, description="已处理项目数")
    successful_items: int = Field(default=0, description="成功项目数")
    failed_items: int = Field(default=0, description="失败项目数")
    error_details: List[Dict[str, Any]] = Field(default_factory=list, description="错误详情")


# ===== 系统相关 =====

class HealthCheckResponse(BaseModel):
    """健康检查响应"""
    status: str = Field(..., description="服务状态")
    version: str = Field(..., description="服务版本")
    timestamp: datetime = Field(..., description="检查时间")
    
    # 组件状态
    database: bool = Field(..., description="数据库状态")
    vector_store: bool = Field(..., description="向量存储状态")
    redis: bool = Field(..., description="Redis状态")
    
    # 外部服务状态
    model_service: bool = Field(..., description="模型服务状态")
    agent_service: bool = Field(..., description="智能体服务状态")
    
    # 系统信息
    uptime: float = Field(..., description="运行时间(秒)")
    memory_usage: float = Field(..., description="内存使用率")
    cpu_usage: float = Field(..., description="CPU使用率")


class ServiceStats(BaseModel):
    """服务统计信息"""
    total_knowledge_bases: int = Field(..., description="总知识库数")
    total_documents: int = Field(..., description="总文档数")
    total_chunks: int = Field(..., description="总分块数")
    total_vectors: int = Field(..., description="总向量数")
    
    # 使用统计
    daily_searches: int = Field(..., description="日搜索量")
    monthly_searches: int = Field(..., description="月搜索量")
    avg_search_time: float = Field(..., description="平均搜索时间")
    
    # 存储统计
    total_storage_size: int = Field(..., description="总存储大小(字节)")
    vector_db_size: int = Field(..., description="向量数据库大小(字节)")


# ===== 错误响应 =====

class ErrorResponse(BaseModel):
    """错误响应"""
    error: str = Field(..., description="错误类型")
    message: str = Field(..., description="错误消息")
    details: Optional[Dict[str, Any]] = Field(None, description="错误详情")
    timestamp: datetime = Field(default_factory=datetime.now, description="错误时间")
    request_id: Optional[str] = Field(None, description="请求ID") 