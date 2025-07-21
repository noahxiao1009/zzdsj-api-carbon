"""
知识库模型模块: 知识库、文档和知识图谱相关的数据库模型
"""

from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, JSON, Boolean, Float, LargeBinary
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import ARRAY
from typing import List, Dict, Any, Optional

from .database import Base


class KnowledgeBase(Base):
    """知识库模型"""
    __tablename__ = "knowledge_bases"
    
    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="知识库名称")
    description = Column(Text, comment="知识库描述")
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment="创建用户ID")
    
    # 配置信息
    chunk_strategy = Column(String(50), default="basic", comment="切分策略")
    chunk_size = Column(Integer, default=1000, comment="切分大小")
    chunk_overlap = Column(Integer, default=200, comment="切分重叠")
    retrieval_config = Column(JSON, comment="检索配置")
    tokenizer_config = Column(JSON, comment="分词器配置")
    language_settings = Column(JSON, comment="语言设置")
    
    # 状态信息
    is_public = Column(Boolean, default=False, comment="是否公开")
    is_active = Column(Boolean, default=True, comment="是否激活")
    status = Column(String(20), default="active", comment="状态")
    
    # 统计信息
    document_count = Column(Integer, default=0, comment="文档数量")
    chunk_count = Column(Integer, default=0, comment="分块数量")
    total_size = Column(Integer, default=0, comment="总大小（字节）")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), comment="更新时间")
    last_indexed_at = Column(DateTime(timezone=True), comment="最后索引时间")
    
    # 关系
    documents = relationship("Document", back_populates="knowledge_base", cascade="all, delete-orphan")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "user_id": self.user_id,
            "chunk_strategy": self.chunk_strategy,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "retrieval_config": self.retrieval_config,
            "tokenizer_config": self.tokenizer_config,
            "language_settings": self.language_settings,
            "is_public": self.is_public,
            "is_active": self.is_active,
            "status": self.status,
            "document_count": self.document_count,
            "chunk_count": self.chunk_count,
            "total_size": self.total_size,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_indexed_at": self.last_indexed_at.isoformat() if self.last_indexed_at else None
        }


class Document(Base):
    """文档模型"""
    __tablename__ = "documents"
    
    id = Column(String(36), primary_key=True, index=True)
    kb_id = Column(String(36), ForeignKey("knowledge_bases.id"), nullable=False, comment="知识库ID")
    title = Column(String(255), nullable=False, comment="文档标题")
    content = Column(Text, comment="文档内容")
    
    # 来源信息
    source_type = Column(String(50), nullable=False, comment="来源类型")  # file/url/text
    source_path = Column(String(500), comment="来源路径")
    source_url = Column(String(500), comment="来源URL")
    file_name = Column(String(255), comment="文件名")
    file_type = Column(String(50), comment="文件类型")
    file_size = Column(Integer, comment="文件大小")
    
    # 处理信息
    language = Column(String(10), comment="主要语言")
    mixed_languages = Column(ARRAY(String), comment="混合语言列表")
    tokenizer_used = Column(String(50), comment="使用的分词器")
    processing_status = Column(String(20), default="pending", comment="处理状态")
    processing_error = Column(Text, comment="处理错误信息")
    
    # 元数据
    metadata = Column(JSON, comment="文档元数据")
    tags = Column(ARRAY(String), comment="标签")
    
    # 统计信息
    chunk_count = Column(Integer, default=0, comment="分块数量")
    character_count = Column(Integer, comment="字符数")
    word_count = Column(Integer, comment="词数")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), comment="更新时间")
    processed_at = Column(DateTime(timezone=True), comment="处理时间")
    
    # 关系
    knowledge_base = relationship("KnowledgeBase", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "kb_id": self.kb_id,
            "title": self.title,
            "source_type": self.source_type,
            "source_path": self.source_path,
            "source_url": self.source_url,
            "file_name": self.file_name,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "language": self.language,
            "mixed_languages": self.mixed_languages,
            "tokenizer_used": self.tokenizer_used,
            "processing_status": self.processing_status,
            "processing_error": self.processing_error,
            "metadata": self.metadata,
            "tags": self.tags,
            "chunk_count": self.chunk_count,
            "character_count": self.character_count,
            "word_count": self.word_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None
        }


class DocumentChunk(Base):
    """文档分块模型"""
    __tablename__ = "document_chunks"
    
    id = Column(String(36), primary_key=True, index=True)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False, comment="文档ID")
    content = Column(Text, nullable=False, comment="分块内容")
    
    # 位置信息
    start_char = Column(Integer, comment="起始字符位置")
    end_char = Column(Integer, comment="结束字符位置")
    chunk_index = Column(Integer, nullable=False, comment="分块索引")
    
    # 分词信息
    tokens = Column(JSON, comment="分词结果")
    semantic_boundaries = Column(ARRAY(Integer), comment="语义边界")
    coherence_score = Column(Float, comment="连贯性分数")
    language_segments = Column(JSON, comment="语言分段信息")
    
    # 向量信息
    embedding = Column(ARRAY(Float), comment="向量嵌入")
    embedding_model = Column(String(100), comment="嵌入模型")
    
    # 元数据
    metadata = Column(JSON, comment="分块元数据")
    keywords = Column(ARRAY(String), comment="关键词")
    
    # 统计信息
    character_count = Column(Integer, comment="字符数")
    token_count = Column(Integer, comment="Token数")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), comment="更新时间")
    
    # 关系
    document = relationship("Document", back_populates="chunks")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "content": self.content,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "chunk_index": self.chunk_index,
            "tokens": self.tokens,
            "semantic_boundaries": self.semantic_boundaries,
            "coherence_score": self.coherence_score,
            "language_segments": self.language_segments,
            "embedding_model": self.embedding_model,
            "metadata": self.metadata,
            "keywords": self.keywords,
            "character_count": self.character_count,
            "token_count": self.token_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class KnowledgeGraph(Base):
    """知识图谱模型"""
    __tablename__ = "knowledge_graphs"
    
    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="图谱名称")
    description = Column(Text, comment="图谱描述")
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment="创建用户ID")
    kb_id = Column(String(36), ForeignKey("knowledge_bases.id"), comment="关联知识库ID")
    
    # 图谱配置
    graph_type = Column(String(50), default="general", comment="图谱类型")
    config = Column(JSON, comment="图谱配置")
    
    # 图谱数据
    nodes = Column(JSON, comment="节点数据")
    edges = Column(JSON, comment="边数据")
    schema = Column(JSON, comment="图谱模式")
    
    # 统计信息
    node_count = Column(Integer, default=0, comment="节点数量")
    edge_count = Column(Integer, default=0, comment="边数量")
    
    # 状态信息
    is_active = Column(Boolean, default=True, comment="是否激活")
    status = Column(String(20), default="active", comment="状态")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), comment="更新时间")
    last_built_at = Column(DateTime(timezone=True), comment="最后构建时间")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "user_id": self.user_id,
            "kb_id": self.kb_id,
            "graph_type": self.graph_type,
            "config": self.config,
            "nodes": self.nodes,
            "edges": self.edges,
            "schema": self.schema,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "is_active": self.is_active,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_built_at": self.last_built_at.isoformat() if self.last_built_at else None
        }


class SearchHistory(Base):
    """搜索历史模型"""
    __tablename__ = "search_history"
    
    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment="用户ID")
    kb_id = Column(String(36), ForeignKey("knowledge_bases.id"), nullable=False, comment="知识库ID")
    query = Column(Text, nullable=False, comment="搜索查询")
    
    # 搜索配置
    search_type = Column(String(50), default="semantic", comment="搜索类型")
    search_config = Column(JSON, comment="搜索配置")
    
    # 搜索结果
    result_count = Column(Integer, comment="结果数量")
    results = Column(JSON, comment="搜索结果")
    
    # 性能指标
    response_time = Column(Float, comment="响应时间（秒）")
    relevance_score = Column(Float, comment="相关性分数")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "kb_id": self.kb_id,
            "query": self.query,
            "search_type": self.search_type,
            "search_config": self.search_config,
            "result_count": self.result_count,
            "results": self.results,
            "response_time": self.response_time,
            "relevance_score": self.relevance_score,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }