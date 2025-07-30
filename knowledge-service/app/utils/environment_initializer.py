"""
环境初始化和验证器
在服务启动时自动验证和初始化所有必要的环境组件
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from sqlalchemy import text, inspect
from sqlalchemy.exc import SQLAlchemyError
from elasticsearch import Elasticsearch
from minio import Minio
from minio.error import S3Error
from pymilvus import connections, utility, Collection, FieldSchema, CollectionSchema, DataType
import redis
from app.config.settings import settings
from app.models.database import engine, SessionLocal

logger = logging.getLogger(__name__)


@dataclass
class InitializationResult:
    """初始化结果"""
    component: str
    status: str  # 'success', 'error', 'skipped'
    message: str
    details: Optional[Dict[str, Any]] = None


class EnvironmentInitializer:
    """环境初始化器"""
    
    def __init__(self):
        self.results: List[InitializationResult] = []
        self.required_tables = [
            "knowledge_bases",
            "documents", 
            "document_chunks",
            "knowledge_base_documents",
            "upload_records",
            "processing_tasks"
        ]
        self.required_buckets = ["knowledge-files"]
        self.required_indices = ["knowledge-chunks", "documents"]
        self.required_collections = ["knowledge_embeddings"]
    
    async def initialize_all(self) -> Dict[str, Any]:
        """初始化所有环境组件"""
        logger.info("开始环境初始化验证...")
        
        # 按依赖顺序初始化
        await self._initialize_postgresql()
        await self._initialize_redis()
        await self._initialize_minio()
        await self._initialize_elasticsearch()
        await self._initialize_milvus()
        
        # 汇总结果
        success_count = len([r for r in self.results if r.status == 'success'])
        error_count = len([r for r in self.results if r.status == 'error'])
        total_count = len(self.results)
        
        overall_status = 'success' if error_count == 0 else 'partial' if success_count > 0 else 'failed'
        
        result = {
            'overall_status': overall_status,
            'summary': f'{success_count}/{total_count} 组件初始化成功',
            'components': {r.component: r for r in self.results},
            'errors': [r for r in self.results if r.status == 'error'],
            'recommendations': self._get_recommendations()
        }
        
        logger.info(f"环境初始化完成: {result['summary']}")
        return result
    
    async def _initialize_postgresql(self):
        """初始化PostgreSQL数据库表"""
        try:
            logger.info("正在初始化PostgreSQL数据库表...")
            
            # 检查数据库连接
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            # 检查现有表
            inspector = inspect(engine)
            existing_tables = inspector.get_table_names()
            
            missing_tables = [table for table in self.required_tables if table not in existing_tables]
            
            if missing_tables:
                # 创建缺失的表
                await self._create_database_tables(missing_tables)
                message = f"已创建 {len(missing_tables)} 个数据库表: {', '.join(missing_tables)}"
            else:
                message = "所有数据库表已存在"
            
            self.results.append(InitializationResult(
                component="postgresql",
                status="success",
                message=message,
                details={"existing_tables": existing_tables, "missing_tables": missing_tables}
            ))
            
        except Exception as e:
            logger.error(f"PostgreSQL初始化失败: {e}")
            self.results.append(InitializationResult(
                component="postgresql",
                status="error",
                message=f"数据库初始化失败: {str(e)}"
            ))
    
    async def _create_database_tables(self, missing_tables: List[str]):
        """创建缺失的数据库表"""
        # 数据库表创建SQL
        table_schemas = {
            "knowledge_bases": """
                CREATE TABLE knowledge_bases (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    user_id INTEGER,
                    status VARCHAR(50) DEFAULT 'active',
                    document_count INTEGER DEFAULT 0,
                    chunk_count INTEGER DEFAULT 0,
                    total_size BIGINT DEFAULT 0,
                    embedding_model VARCHAR(255),
                    chunk_strategy VARCHAR(100) DEFAULT 'basic',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """,
            "documents": """
                CREATE TABLE documents (
                    id SERIAL PRIMARY KEY,
                    filename VARCHAR(255) NOT NULL,
                    original_filename VARCHAR(255),
                    file_path VARCHAR(500),
                    file_size BIGINT,
                    content_type VARCHAR(100),
                    file_hash VARCHAR(255),
                    status VARCHAR(50) DEFAULT 'pending',
                    chunk_count INTEGER DEFAULT 0,
                    processing_metadata JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """,
            "document_chunks": """
                CREATE TABLE document_chunks (
                    id SERIAL PRIMARY KEY,
                    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    content_hash VARCHAR(255),
                    chunk_size INTEGER,
                    token_count INTEGER DEFAULT 0,
                    embedding_status VARCHAR(50) DEFAULT 'pending',
                    metadata JSONB,
                    vector_id VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """,
            "knowledge_base_documents": """
                CREATE TABLE knowledge_base_documents (
                    id SERIAL PRIMARY KEY,
                    knowledge_base_id INTEGER REFERENCES knowledge_bases(id) ON DELETE CASCADE,
                    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(knowledge_base_id, document_id)
                );
            """,
            "upload_records": """
                CREATE TABLE upload_records (
                    id SERIAL PRIMARY KEY,
                    knowledge_base_id INTEGER REFERENCES knowledge_bases(id) ON DELETE CASCADE,
                    batch_id VARCHAR(255),
                    total_files INTEGER,
                    processed_files INTEGER DEFAULT 0,
                    failed_files INTEGER DEFAULT 0,
                    status VARCHAR(50) DEFAULT 'pending',
                    error_messages JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                );
            """,
            "processing_tasks": """
                CREATE TABLE processing_tasks (
                    id SERIAL PRIMARY KEY,
                    task_id VARCHAR(255) UNIQUE NOT NULL,
                    task_type VARCHAR(100) NOT NULL,
                    status VARCHAR(50) DEFAULT 'pending',
                    progress FLOAT DEFAULT 0.0,
                    result JSONB,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP
                );
            """
        }
        
        with engine.connect() as conn:
            for table in missing_tables:
                if table in table_schemas:
                    logger.info(f"创建数据库表: {table}")
                    conn.execute(text(table_schemas[table]))
                    conn.commit()
    
    async def _initialize_redis(self):
        """初始化Redis环境"""
        try:
            logger.info("正在初始化Redis环境...")
            
            # 连接Redis
            redis_client = redis.Redis(
                host=settings.database.redis_host,
                port=settings.database.redis_port,
                password=settings.database.redis_password or None,
                db=settings.database.redis_db,
                decode_responses=True
            )
            
            # 测试连接
            redis_client.ping()
            
            # 初始化必要的键结构
            key_patterns = [
                "document_processing:*",
                "task_notifications:*", 
                "cache:*",
                "session:*"
            ]
            
            # 清理可能的旧数据（仅在本地环境）
            if settings.is_local:
                for pattern in key_patterns:
                    keys = redis_client.keys(pattern)
                    if keys:
                        redis_client.delete(*keys)
                        logger.info(f"清理Redis键: {pattern} ({len(keys)} 个)")
            
            self.results.append(InitializationResult(
                component="redis",
                status="success",
                message="Redis环境初始化成功",
                details={"host": settings.database.redis_host, "port": settings.database.redis_port}
            ))
            
        except Exception as e:
            logger.error(f"Redis初始化失败: {e}")
            self.results.append(InitializationResult(
                component="redis",
                status="error",
                message=f"Redis初始化失败: {str(e)}"
            ))
    
    async def _initialize_minio(self):
        """初始化MinIO存储桶"""
        try:
            logger.info("正在初始化MinIO存储桶...")
            
            # 创建MinIO客户端
            minio_client = Minio(
                endpoint=f"{settings.storage.minio_host}:{settings.storage.minio_port}",
                access_key=settings.storage.minio_access_key,
                secret_key=settings.storage.minio_secret_key,
                secure=settings.storage.minio_secure
            )
            
            created_buckets = []
            existing_buckets = []
            
            for bucket_name in self.required_buckets:
                if not minio_client.bucket_exists(bucket_name):
                    minio_client.make_bucket(bucket_name)
                    created_buckets.append(bucket_name)
                    logger.info(f"创建MinIO存储桶: {bucket_name}")
                else:
                    existing_buckets.append(bucket_name)
            
            message = f"MinIO初始化完成"
            if created_buckets:
                message += f"，已创建 {len(created_buckets)} 个存储桶"
            
            self.results.append(InitializationResult(
                component="minio",
                status="success",
                message=message,
                details={"created_buckets": created_buckets, "existing_buckets": existing_buckets}
            ))
            
        except Exception as e:
            logger.error(f"MinIO初始化失败: {e}")
            self.results.append(InitializationResult(
                component="minio",
                status="error",
                message=f"MinIO初始化失败: {str(e)}"
            ))
    
    async def _initialize_elasticsearch(self):
        """初始化Elasticsearch索引"""
        try:
            if not settings.vector_store.elasticsearch_enabled:
                self.results.append(InitializationResult(
                    component="elasticsearch",
                    status="skipped",
                    message="Elasticsearch未启用"
                ))
                return
            
            logger.info("正在初始化Elasticsearch索引...")
            
            # 创建ES客户端
            es_config = settings.get_elasticsearch_config()
            es = Elasticsearch(**es_config)
            
            # 测试连接
            es.info()
            
            created_indices = []
            existing_indices = []
            
            # 索引配置
            index_configs = {
                "knowledge-chunks": {
                    "mappings": {
                        "properties": {
                            "content": {"type": "text", "analyzer": "standard"},
                            "document_id": {"type": "keyword"},
                            "chunk_index": {"type": "integer"},
                            "metadata": {"type": "object"},
                            "created_at": {"type": "date"}
                        }
                    },
                    "settings": {
                        "number_of_shards": 1,
                        "number_of_replicas": 0
                    }
                },
                "documents": {
                    "mappings": {
                        "properties": {
                            "filename": {"type": "keyword"},
                            "content": {"type": "text", "analyzer": "standard"},
                            "file_type": {"type": "keyword"},
                            "metadata": {"type": "object"},
                            "created_at": {"type": "date"}
                        }
                    },
                    "settings": {
                        "number_of_shards": 1,
                        "number_of_replicas": 0
                    }
                }
            }
            
            for index_name in self.required_indices:
                if not es.indices.exists(index=index_name):
                    if index_name in index_configs:
                        es.indices.create(index=index_name, body=index_configs[index_name])
                        created_indices.append(index_name)
                        logger.info(f"创建Elasticsearch索引: {index_name}")
                else:
                    existing_indices.append(index_name)
            
            message = f"Elasticsearch初始化完成"
            if created_indices:
                message += f"，已创建 {len(created_indices)} 个索引"
            
            self.results.append(InitializationResult(
                component="elasticsearch",
                status="success",
                message=message,
                details={"created_indices": created_indices, "existing_indices": existing_indices}
            ))
            
        except Exception as e:
            logger.error(f"Elasticsearch初始化失败: {e}")
            self.results.append(InitializationResult(
                component="elasticsearch",
                status="error",
                message=f"Elasticsearch初始化失败: {str(e)}"
            ))
    
    async def _initialize_milvus(self):
        """初始化Milvus集合"""
        try:
            logger.info("正在初始化Milvus集合...")
            
            # 连接Milvus
            connections.connect(
                alias="default",
                host=settings.vector_store.milvus_host,
                port=settings.vector_store.milvus_port,
                user=settings.vector_store.milvus_user or "",
                password=settings.vector_store.milvus_password or ""
            )
            
            created_collections = []
            existing_collections = []
            
            for collection_name in self.required_collections:
                if not utility.has_collection(collection_name):
                    # 创建集合
                    fields = [
                        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                        FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=settings.embedding.default_embedding_dimension),
                        FieldSchema(name="document_id", dtype=DataType.INT64),
                        FieldSchema(name="chunk_id", dtype=DataType.INT64),
                        FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
                        FieldSchema(name="metadata", dtype=DataType.JSON)
                    ]
                    
                    schema = CollectionSchema(fields, description=f"Knowledge base collection: {collection_name}")
                    collection = Collection(collection_name, schema)
                    
                    # 创建索引
                    index_params = {
                        "metric_type": "COSINE",
                        "index_type": "IVF_FLAT",
                        "params": {"nlist": 1024}
                    }
                    collection.create_index("vector", index_params)
                    
                    created_collections.append(collection_name)
                    logger.info(f"创建Milvus集合: {collection_name}")
                else:
                    existing_collections.append(collection_name)
            
            message = f"Milvus初始化完成"
            if created_collections:
                message += f"，已创建 {len(created_collections)} 个集合"
            
            self.results.append(InitializationResult(
                component="milvus",
                status="success",
                message=message,
                details={"created_collections": created_collections, "existing_collections": existing_collections}
            ))
            
        except Exception as e:
            logger.error(f"Milvus初始化失败: {e}")
            self.results.append(InitializationResult(
                component="milvus",
                status="error",
                message=f"Milvus初始化失败: {str(e)}"
            ))
    
    def _get_recommendations(self) -> List[str]:
        """获取推荐操作"""
        recommendations = []
        
        for result in self.results:
            if result.status == 'error':
                component = result.component
                if component == 'postgresql':
                    recommendations.append("请确保PostgreSQL服务已启动且数据库权限正确")
                elif component == 'redis':
                    recommendations.append("请确保Redis服务已启动: brew services start redis")
                elif component == 'minio':
                    recommendations.append("请确保MinIO服务已启动且认证信息正确")
                elif component == 'elasticsearch':
                    recommendations.append("请确保Elasticsearch服务已启动且可访问")
                elif component == 'milvus':
                    recommendations.append("请确保Milvus服务已启动且连接配置正确")
        
        return recommendations


# 创建全局初始化器实例
environment_initializer = EnvironmentInitializer()


async def initialize_environment() -> Dict[str, Any]:
    """初始化环境的便捷函数"""
    return await environment_initializer.initialize_all()


async def quick_environment_check() -> bool:
    """快速环境检查"""
    try:
        result = await initialize_environment()
        return result['overall_status'] == 'success'
    except Exception as e:
        logger.error(f"环境检查失败: {e}")
        return False