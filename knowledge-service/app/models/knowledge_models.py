"""
知识库相关数据模型
基于原始项目的知识库模型，针对微服务架构进行优化
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, DateTime, JSON, Integer, Float, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


class KnowledgeBase(Base):
    """
    知识库模型
    存储知识库的基本信息和配置
    """
    __tablename__ = "knowledge_bases"
    
    # 主键和基本信息
    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    user_id = Column(String(255), nullable=True, default=None)
    
    # 嵌入模型配置
    embedding_provider = Column(String(100), nullable=False, default="openai")
    embedding_model = Column(String(100), nullable=False, default="text-embedding-3-small")
    embedding_dimension = Column(Integer, nullable=False, default=1536)
    
    # 向量存储配置
    vector_store_type = Column(String(50), nullable=False, default="milvus")
    vector_store_config = Column(JSON, default={})
    
    # 分块配置
    chunk_size = Column(Integer, default=1000)
    chunk_overlap = Column(Integer, default=200)
    chunk_strategy = Column(String(50), default="token_based")
    
    # 检索配置
    similarity_threshold = Column(Float, default=0.7)
    enable_hybrid_search = Column(Boolean, default=True)
    enable_agno_integration = Column(Boolean, default=True)
    agno_search_type = Column(String(50), default="knowledge")
    
    # 状态和统计
    status = Column(String(20), default="active")  # active, inactive, processing, error
    document_count = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    total_size = Column(Integer, default=0)  # 总大小（字节）
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 扩展设置
    settings = Column(JSON, default={})
    
    # 关系
    documents = relationship("Document", back_populates="knowledge_base", cascade="all, delete-orphan")
    vector_stores = relationship("VectorStore", back_populates="knowledge_base", cascade="all, delete-orphan")
    processing_jobs = relationship("ProcessingJob", back_populates="knowledge_base")
    
    # 索引
    __table_args__ = (
        Index('idx_kb_name_status', 'name', 'status'),
        Index('idx_kb_created_at', 'created_at'),
        Index('idx_kb_embedding_model', 'embedding_model'),
    )


class Document(Base):
    """
    文档模型
    存储知识库中的文档信息
    """
    __tablename__ = "documents"
    
    # 主键和关联
    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    kb_id = Column(String(255), ForeignKey("knowledge_bases.id"), nullable=False, index=True)
    
    # 文件信息
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255))
    file_type = Column(String(50))  # pdf, docx, txt, etc.
    file_size = Column(Integer, default=0)
    file_path = Column(String(500))  # 存储路径
    file_hash = Column(String(64))  # MD5哈希，用于去重
    
    # 内容信息
    title = Column(String(500))
    content = Column(Text)
    content_preview = Column(Text)  # 内容预览（前500字符）
    
    # 处理状态
    status = Column(String(20), default="pending")  # pending, processing, completed, failed
    processing_stage = Column(String(50))  # upload, extract, chunk, embed, index
    error_message = Column(Text)
    
    # 统计信息
    chunk_count = Column(Integer, default=0)
    token_count = Column(Integer, default=0)
    
    # 元数据
    doc_metadata = Column(JSON, default={})
    language = Column(String(10), default="zh")
    tags = Column(ARRAY(String), default=[])
    
    # 时间戳
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系
    knowledge_base = relationship("KnowledgeBase", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    
    # 索引
    __table_args__ = (
        Index('idx_doc_kb_status', 'kb_id', 'status'),
        Index('idx_doc_filename', 'filename'),
        Index('idx_doc_file_hash', 'file_hash'),
        Index('idx_doc_created_at', 'created_at'),
    )


class DocumentChunk(Base):
    """
    文档分块模型
    存储文档的分块信息和向量数据
    """
    __tablename__ = "document_chunks"
    
    # 主键和关联
    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    doc_id = Column(String(255), ForeignKey("documents.id"), nullable=False, index=True)
    
    # 分块信息
    chunk_index = Column(Integer, nullable=False)  # 在文档中的序号
    content = Column(Text, nullable=False)
    content_hash = Column(String(64))  # 内容哈希，用于去重
    
    # 位置信息
    start_char = Column(Integer)  # 在原文档中的起始字符位置
    end_char = Column(Integer)    # 在原文档中的结束字符位置
    
    # 统计信息
    token_count = Column(Integer, default=0)
    char_count = Column(Integer, default=0)
    
    # 向量信息
    embedding_id = Column(String(255))  # 在向量存储中的ID
    embedding_model = Column(String(100))
    embedding_status = Column(String(20), default="pending")  # pending, completed, failed
    
    # 元数据
    chunk_metadata = Column(JSON, default={})
    section_title = Column(String(200))  # 所属章节标题
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系
    document = relationship("Document", back_populates="chunks")
    
    # 索引
    __table_args__ = (
        Index('idx_chunk_doc_index', 'doc_id', 'chunk_index'),
        Index('idx_chunk_embedding_id', 'embedding_id'),
        Index('idx_chunk_hash', 'content_hash'),
        Index('idx_chunk_status', 'embedding_status'),
    )


class VectorStore(Base):
    """
    向量存储配置模型
    存储不同向量存储的配置信息
    """
    __tablename__ = "vector_stores"
    
    # 主键和关联
    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    kb_id = Column(String(255), ForeignKey("knowledge_bases.id"), nullable=False, index=True)
    
    # 存储配置
    store_type = Column(String(50), nullable=False)  # milvus, pgvector, elasticsearch
    collection_name = Column(String(100), nullable=False)
    connection_config = Column(JSON, default={})
    
    # 索引配置
    index_type = Column(String(50), default="IVF_FLAT")
    index_params = Column(JSON, default={})
    
    # 状态信息
    status = Column(String(20), default="active")  # active, inactive, error
    is_primary = Column(Boolean, default=True)  # 是否为主存储
    
    # 统计信息
    total_vectors = Column(Integer, default=0)
    dimension = Column(Integer, nullable=False)
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系
    knowledge_base = relationship("KnowledgeBase", back_populates="vector_stores")
    
    # 索引
    __table_args__ = (
        Index('idx_vs_kb_type', 'kb_id', 'store_type'),
        Index('idx_vs_collection', 'collection_name'),
        Index('idx_vs_status', 'status'),
    )


class ChunkingStrategy(Base):
    """
    切分策略模型
    存储文档切分策略的配置信息
    """
    __tablename__ = "chunking_strategies"
    
    # 主键和基本信息
    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    
    # 策略类型和配置
    strategy_type = Column(String(50), nullable=False)  # system, custom
    chunker_type = Column(String(50), nullable=False)   # token_based, semantic_based, paragraph_based, agentic_based
    
    # 策略参数 (JSON格式存储)
    parameters = Column(JSON, nullable=False, default={})
    
    # 标签和分类
    tags = Column(ARRAY(String), default=[])
    category = Column(String(50), default="general")
    
    # 使用统计
    usage_count = Column(Integer, default=0)
    success_rate = Column(Float, default=0.0)
    avg_processing_time = Column(Float, default=0.0)
    
    # 状态信息
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    
    # 创建者信息（可选）
    created_by = Column(String(100))
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 索引
    __table_args__ = (
        Index('idx_chunking_strategy_type', 'strategy_type'),
        Index('idx_chunking_strategy_chunker_type', 'chunker_type'),
        Index('idx_chunking_strategy_active', 'is_active'),
        Index('idx_chunking_strategy_usage', 'usage_count'),
        Index('idx_chunking_strategy_created_at', 'created_at'),
    )


class ProcessingJob(Base):
    """
    处理任务模型
    追踪文档处理和向量化任务的状态
    """
    __tablename__ = "processing_jobs"
    
    # 主键和关联
    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    kb_id = Column(String(255), ForeignKey("knowledge_bases.id"), nullable=False, index=True)
    doc_id = Column(String(255), ForeignKey("documents.id"), index=True)
    
    # 任务信息
    job_type = Column(String(50), nullable=False)  # upload, extract, chunk, embed, index
    status = Column(String(20), default="pending")  # pending, running, completed, failed, cancelled
    priority = Column(Integer, default=0)  # 优先级，数字越大优先级越高
    
    # 任务配置
    config = Column(JSON, default={})
    
    # 进度信息
    progress = Column(Float, default=0.0)  # 0.0 到 1.0
    total_items = Column(Integer, default=0)
    processed_items = Column(Integer, default=0)
    
    # 结果信息
    result = Column(JSON, default={})
    error_message = Column(Text)
    error_details = Column(JSON, default={})
    
    # 时间信息
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    estimated_duration = Column(Integer)  # 预计耗时（秒）
    actual_duration = Column(Integer)     # 实际耗时（秒）
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系
    knowledge_base = relationship("KnowledgeBase", back_populates="processing_jobs")
    
    # 索引
    __table_args__ = (
        Index('idx_job_kb_status', 'kb_id', 'status'),
        Index('idx_job_type_status', 'job_type', 'status'),
        Index('idx_job_priority', 'priority'),
        Index('idx_job_created_at', 'created_at'),
    )