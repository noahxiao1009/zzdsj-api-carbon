"""
知识库服务配置管理
基于pydantic-settings的配置系统
"""

import os
from typing import Dict, Any, Optional, List
from pydantic import Field
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    """数据库配置"""
    
    # PostgreSQL配置
    postgres_host: str = Field(default="localhost", env="POSTGRES_HOST", description="PostgreSQL主机")
    postgres_port: int = Field(default=5432, env="POSTGRES_PORT", description="PostgreSQL端口")
    postgres_user: str = Field(default="postgres", env="POSTGRES_USER", description="PostgreSQL用户名")
    postgres_password: str = Field(default="", env="POSTGRES_PASSWORD", description="PostgreSQL密码")
    postgres_db: str = Field(default="knowledge_db", env="POSTGRES_DB", description="PostgreSQL数据库名")
    postgres_schema: str = Field(default="public", env="POSTGRES_SCHEMA", description="PostgreSQL模式")
    
    # Redis配置
    redis_host: str = Field(default="localhost", env="REDIS_HOST", description="Redis主机")
    redis_port: int = Field(default=6379, env="REDIS_PORT", description="Redis端口")
    redis_password: str = Field(default="", env="REDIS_PASSWORD", description="Redis密码")
    redis_db: int = Field(default=0, env="REDIS_DB", description="Redis数据库")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "allow"


class VectorStoreSettings(BaseSettings):
    """向量存储配置"""
    
    # 向量数据库类型
    vector_db_type: str = Field(default="milvus", description="向量数据库类型")
    
    # Milvus配置
    milvus_host: str = Field(default="localhost", description="Milvus主机")
    milvus_port: int = Field(default=19530, description="Milvus端口")
    milvus_user: str = Field(default="", description="Milvus用户名")
    milvus_password: str = Field(default="", description="Milvus密码")
    
    # PGVector配置 (使用PostgreSQL + pgvector扩展)
    pgvector_enabled: bool = Field(default=True, description="启用PGVector")
    pgvector_table_name: str = Field(default="vector_embeddings", description="PGVector表名")
    pgvector_dimension: int = Field(default=1536, description="向量维度")
    
    # Elasticsearch配置
    elasticsearch_enabled: bool = Field(default=False, env="ELASTICSEARCH_ENABLED", description="启用Elasticsearch")
    elasticsearch_host: str = Field(default="localhost", env="ELASTICSEARCH_HOST", description="Elasticsearch主机")
    elasticsearch_port: int = Field(default=9200, env="ELASTICSEARCH_PORT", description="Elasticsearch端口")
    elasticsearch_username: str = Field(default="", env="ELASTICSEARCH_USERNAME", description="Elasticsearch用户名")
    elasticsearch_password: str = Field(default="", env="ELASTICSEARCH_PASSWORD", description="Elasticsearch密码")
    elasticsearch_use_ssl: bool = Field(default=False, env="ELASTICSEARCH_USE_SSL", description="Elasticsearch使用SSL")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "allow"


class EmbeddingSettings(BaseSettings):
    """嵌入模型配置"""
    
    # 默认嵌入提供商和模型
    default_embedding_provider: str = Field(default="openai", description="默认嵌入提供商")
    default_embedding_model: str = Field(default="text-embedding-3-small", description="默认嵌入模型")
    default_embedding_dimension: int = Field(default=1536, description="默认嵌入维度")
    
    # OpenAI配置
    openai_api_key: str = Field(default="", description="OpenAI API密钥")
    openai_base_url: str = Field(default="", description="OpenAI API基础URL")
    
    # Azure OpenAI配置
    azure_openai_api_key: str = Field(default="", description="Azure OpenAI API密钥")
    azure_openai_endpoint: str = Field(default="", description="Azure OpenAI端点")
    azure_openai_api_version: str = Field(default="2023-12-01-preview", description="Azure OpenAI API版本")
    
    # HuggingFace配置
    huggingface_api_key: str = Field(default="", description="HuggingFace API密钥")
    huggingface_model_path: str = Field(default="", description="HuggingFace模型路径")
    
    # 本地模型配置
    local_model_path: str = Field(default="", description="本地模型路径")


class LlamaIndexSettings(BaseSettings):
    """LlamaIndex框架配置"""
    
    # 文档处理配置
    chunk_size: int = Field(default=1000, description="文档分块大小")
    chunk_overlap: int = Field(default=200, description="文档分块重叠")
    max_tokens: int = Field(default=4000, description="最大token数")
    
    # 检索配置
    similarity_top_k: int = Field(default=5, description="相似度检索数量")
    similarity_threshold: float = Field(default=0.7, description="相似度阈值")
    
    # 混合搜索配置
    enable_hybrid_search: bool = Field(default=True, description="启用混合搜索")
    vector_weight: float = Field(default=0.7, description="向量搜索权重")
    text_weight: float = Field(default=0.3, description="文本搜索权重")
    
    # 重排序配置
    enable_reranking: bool = Field(default=True, description="启用重排序")
    rerank_top_k: int = Field(default=10, description="重排序候选数量")
    
    # 缓存配置
    enable_caching: bool = Field(default=True, description="启用缓存")
    cache_ttl: int = Field(default=3600, description="缓存过期时间")


class AgnoSettings(BaseSettings):
    """Agno框架配置"""
    
    # Agno API配置
    enable_agno_integration: bool = Field(default=True, description="启用Agno集成")
    agno_knowledge_search: bool = Field(default=True, description="启用Agno知识搜索")
    agno_add_context: bool = Field(default=True, description="自动添加上下文")
    agno_markdown: bool = Field(default=True, description="启用Markdown")
    agno_show_tool_calls: bool = Field(default=True, description="显示工具调用")
    
    # Agno检索配置
    agno_search_type: str = Field(default="hybrid", description="Agno搜索类型")
    agno_max_results: int = Field(default=10, description="Agno最大结果数")
    agno_confidence_threshold: float = Field(default=0.6, description="Agno置信度阈值")


class ExternalServiceSettings(BaseSettings):
    """外部服务配置"""
    
    # Task Manager服务配置
    task_manager_url: str = Field(default="http://localhost:8084", env="TASK_MANAGER_URL", description="Task Manager服务URL")
    task_manager_grpc_address: str = Field(default="localhost:8085", env="TASK_MANAGER_GRPC_ADDRESS", description="Task Manager gRPC地址")
    task_manager_timeout: int = Field(default=30, env="TASK_MANAGER_TIMEOUT", description="Task Manager超时时间")
    enable_task_manager_integration: bool = Field(default=True, env="ENABLE_TASK_MANAGER_INTEGRATION", description="启用Task Manager集成")
    
    # 模型服务配置
    model_service_url: str = Field(default="http://localhost:8088", description="模型服务URL")
    model_service_timeout: int = Field(default=30, description="模型服务超时时间")
    
    # 智能体服务配置
    agent_service_url: str = Field(default="http://localhost:8081", description="智能体服务URL")
    agent_service_timeout: int = Field(default=60, description="智能体服务超时时间")
    
    # 基础服务配置
    base_service_url: str = Field(default="http://localhost:8085", description="基础服务URL")
    base_service_timeout: int = Field(default=30, description="基础服务超时时间")


class StorageSettings(BaseSettings):
    """存储配置"""
    
    # MinIO配置
    minio_endpoint: str = Field(default="localhost:9000", env="MINIO_ENDPOINT", description="MinIO服务地址")
    minio_access_key: str = Field(default="zzdsjadmin", env="MINIO_ACCESS_KEY", description="MinIO访问密钥")
    minio_secret_key: str = Field(default="zzdsjadmin", env="MINIO_SECRET_KEY", description="MinIO私钥")
    minio_secure: bool = Field(default=False, env="MINIO_SECURE", description="是否使用HTTPS")
    minio_bucket_name: str = Field(default="knowledge-files", env="MINIO_BUCKET_NAME", description="MinIO存储桶名称")
    
    @property
    def minio_host(self) -> str:
        """从endpoint中提取主机"""
        return self.minio_endpoint.split(':')[0]
    
    @property 
    def minio_port(self) -> int:
        """从endpoint中提取端口"""
        parts = self.minio_endpoint.split(':')
        return int(parts[1]) if len(parts) > 1 else 9000
    
    # 存储策略配置
    storage_backend: str = Field(default="minio", env="STORAGE_BACKEND", description="存储后端类型 (local/minio)")
    local_storage_path: str = Field(default="./uploads", env="LOCAL_STORAGE_PATH", description="本地存储路径")
    temp_upload_dir: str = Field(default="/tmp/uploads", env="TEMP_UPLOAD_DIR", description="临时上传目录")
    

class ProcessingSettings(BaseSettings):
    """文档处理配置"""
    
    # 并发配置
    max_workers: int = Field(default=4, env="MAX_WORKERS", description="最大工作线程数")
    batch_size: int = Field(default=100, env="BATCH_SIZE", description="批处理大小")
    
    # 文件上传配置
    upload_dir: str = Field(default="uploads", env="UPLOAD_DIR", description="上传目录")
    max_file_size: int = Field(default=104857600, env="MAX_FILE_SIZE", description="最大文件大小(字节)")
    
    # 异步队列配置
    enable_async_processing: bool = Field(default=True, env="ENABLE_ASYNC_PROCESSING", description="启用异步处理")
    default_queue_name: str = Field(default="document_processing", env="DEFAULT_QUEUE_NAME", description="默认队列名称")
    task_timeout: int = Field(default=300, env="TASK_TIMEOUT", description="任务超时时间(秒)")
    max_task_retries: int = Field(default=3, env="MAX_TASK_RETRIES", description="最大重试次数")
    worker_concurrency: int = Field(default=3, env="WORKER_CONCURRENCY", description="工作进程并发数")
    
    # 任务通知配置
    enable_task_notifications: bool = Field(default=True, env="ENABLE_TASK_NOTIFICATIONS", description="启用任务通知")
    notification_channel: str = Field(default="task_notifications", env="NOTIFICATION_CHANNEL", description="通知频道")
    task_retention_days: int = Field(default=7, env="TASK_RETENTION_DAYS", description="任务保留天数")
    
    # 切分策略配置
    default_chunk_size: int = Field(default=1024, env="DEFAULT_CHUNK_SIZE", description="默认分块大小")
    default_chunk_overlap: int = Field(default=128, env="DEFAULT_CHUNK_OVERLAP", description="默认分块重叠")
    default_chunk_strategy: str = Field(default="basic", env="DEFAULT_CHUNK_STRATEGY", description="默认切分策略")
    enable_semantic_chunking: bool = Field(default=True, env="ENABLE_SEMANTIC_CHUNKING", description="启用语义切分")
    enable_intelligent_chunking: bool = Field(default=True, env="ENABLE_INTELLIGENT_CHUNKING", description="启用智能切分")
    
    # 文件类型配置
    allowed_extensions: List[str] = Field(
        default=[".pdf", ".txt", ".docx", ".doc", ".md", ".csv", ".json", ".html"],
        description="允许的文件扩展名"
    )
    
    # 文档解析配置
    enable_ocr: bool = Field(default=True, description="启用OCR")
    ocr_language: str = Field(default="chi_sim+eng", description="OCR语言")
    extract_tables: bool = Field(default=True, description="提取表格")
    extract_images: bool = Field(default=False, description="提取图片")


class KnowledgeServiceSettings(BaseSettings):
    """知识库服务主配置"""
    
    # 基础配置
    service_name: str = Field(default="knowledge-service", description="服务名称")
    service_version: str = Field(default="1.0.0", description="服务版本")
    host: str = Field(default="0.0.0.0", description="服务主机")
    port: int = Field(default=8082, description="服务端口")
    debug: bool = Field(default=False, description="调试模式")
    
    # 环境配置
    environment: str = Field(default="development", description="运行环境")
    is_local: bool = Field(default=False, description="是否为本地环境")
    
    # 开发配置
    enable_reload: bool = Field(default=True, description="启用热重载(仅开发环境)")
    reload_dirs: List[str] = Field(default=["app", "config"], description="热重载监控目录")
    reload_excludes: List[str] = Field(default=["*.log", "*.tmp", "__pycache__"], description="热重载排除文件")
    
    # 数据库配置快捷属性
    DATABASE_URL: str = Field(default="", description="数据库连接URL")
    REDIS_URL: str = Field(default="", description="Redis连接URL")
    
    # 文件处理配置快捷属性  
    UPLOAD_DIR: str = Field(default="uploads", description="上传目录")
    MAX_FILE_SIZE: int = Field(default=100 * 1024 * 1024, description="最大文件大小")
    
    # 调试配置
    DEBUG: bool = Field(default=False, description="调试模式")
    TESTING: bool = Field(default=False, description="测试模式")
    
    # 日志配置
    log_level: str = Field(default="INFO", description="日志级别")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="日志格式"
    )
    log_file: str = Field(default="", description="日志文件路径")
    
    # CORS配置
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        description="CORS允许的源"
    )
    cors_methods: List[str] = Field(
        default=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        description="CORS允许的方法"
    )
    
    # API配置
    api_prefix: str = Field(default="/api/v1", description="API前缀")
    docs_url: str = Field(default="/docs", description="文档URL")
    openapi_url: str = Field(default="/openapi.json", description="OpenAPI URL")
    
    # 子配置
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    vector_store: VectorStoreSettings = Field(default_factory=VectorStoreSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    llamaindex: LlamaIndexSettings = Field(default_factory=LlamaIndexSettings)
    agno: AgnoSettings = Field(default_factory=AgnoSettings)
    external_services: ExternalServiceSettings = Field(default_factory=ExternalServiceSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    processing: ProcessingSettings = Field(default_factory=ProcessingSettings)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "allow"
        extra = "allow"  # 允许额外的环境变量
        
    def get_database_url(self) -> str:
        """获取数据库连接URL"""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql://{self.database.postgres_user}:"
            f"{self.database.postgres_password}@"
            f"{self.database.postgres_host}:{self.database.postgres_port}/"
            f"{self.database.postgres_db}"
        )
    
    def get_redis_url(self) -> str:
        """获取Redis连接URL"""
        if self.REDIS_URL:
            return self.REDIS_URL
        if self.database.redis_password:
            return (
                f"redis://:{self.database.redis_password}@"
                f"{self.database.redis_host}:{self.database.redis_port}/"
                f"{self.database.redis_db}"
            )
        else:
            return (
                f"redis://{self.database.redis_host}:"
                f"{self.database.redis_port}/{self.database.redis_db}"
            )
    
    @property 
    def upload_directory(self) -> str:
        """获取上传目录"""
        return self.UPLOAD_DIR or self.processing.upload_dir
    
    def __init__(self, **kwargs):
        """初始化处理，根据环境自动设置is_local"""
        super().__init__(**kwargs)
        if self.environment == "local":
            self.is_local = True
    
    def get_database_config(self) -> dict:
        """获取数据库配置，适配本地环境"""
        config = {
            "host": self.database.postgres_host,
            "port": self.database.postgres_port,
            "database": self.database.postgres_db,
            "user": self.database.postgres_user,
        }
        
        # 本地环境通常不需要密码
        if not self.is_local and self.database.postgres_password:
            config["password"] = self.database.postgres_password
            
        return config
    
    def get_elasticsearch_config(self) -> dict:
        """获取Elasticsearch配置，适配本地环境"""
        if not self.vector_store.elasticsearch_enabled:
            return {}
            
        # 本地环境使用HTTP，远程环境使用HTTPS和认证
        if self.is_local:
            hosts = [f"http://{self.vector_store.elasticsearch_host}:{self.vector_store.elasticsearch_port}"]
        else:
            scheme = "https" if self.vector_store.elasticsearch_use_ssl else "http"
            hosts = [f"{scheme}://{self.vector_store.elasticsearch_host}:{self.vector_store.elasticsearch_port}"]
            
        config = {
            "hosts": hosts,
            "verify_certs": False,
            "ssl_show_warn": False
        }
        
        # 远程环境添加认证
        if not self.is_local and self.vector_store.elasticsearch_username:
            config["http_auth"] = (
                self.vector_store.elasticsearch_username,
                self.vector_store.elasticsearch_password
            )
                
        return config
    
    def get_connection_test_config(self) -> dict:
        """获取连接测试配置"""
        return {
            "database_timeout": 5 if self.is_local else 30,
            "elasticsearch_timeout": 3 if self.is_local else 15,
            "redis_timeout": 2 if self.is_local else 10,
            "skip_auth_test": self.is_local  # 本地环境跳过认证测试
        }
    
    @property
    def max_upload_size(self) -> int:
        """获取最大上传大小"""
        return self.MAX_FILE_SIZE or self.processing.max_file_size


# 全局配置实例
settings = KnowledgeServiceSettings() 