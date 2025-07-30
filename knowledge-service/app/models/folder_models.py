"""
知识库文件夹管理模型
支持层级化文档组织和检索优化
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, DateTime, JSON, Integer, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


class KnowledgeFolder(Base):
    """
    知识库文件夹模型
    支持层级化文档组织，提供检索范围限定和权限控制基础
    """
    __tablename__ = "knowledge_folders"
    
    # 主键和关联
    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    kb_id = Column(String(255), ForeignKey("knowledge_bases.id"), nullable=False, index=True)
    parent_id = Column(String(255), ForeignKey("knowledge_folders.id"), nullable=True, index=True)
    
    # 文件夹基本信息
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    folder_type = Column(String(50), default="user_created")  # user_created, system_generated, auto_classified
    
    # 层级信息
    level = Column(Integer, default=0)  # 0=根目录, 1=一级目录, 2=二级目录
    full_path = Column(String(1000))  # 完整路径，如: /技术文档/开发规范
    sort_order = Column(Integer, default=0)  # 同级排序
    
    # 检索配置
    enable_scoped_search = Column(Boolean, default=True)  # 是否支持范围检索
    search_priority = Column(Integer, default=0)  # 检索优先级
    enable_semantic_grouping = Column(Boolean, default=True)  # 是否启用语义分组
    
    # 自动分类配置
    auto_classify_rules = Column(JSON, default={})  # 自动分类规则
    classification_keywords = Column(ARRAY(String), default=[])  # 分类关键词
    
    # 统计信息
    document_count = Column(Integer, default=0)  # 直接包含的文档数量
    total_document_count = Column(Integer, default=0)  # 包括子文件夹的总文档数量
    total_size = Column(Integer, default=0)  # 总大小（字节）
    chunk_count = Column(Integer, default=0)  # 总分块数量
    
    # 权限和可见性
    is_public = Column(Boolean, default=True)  # 是否公开可见
    access_permissions = Column(JSON, default={})  # 访问权限配置
    
    # 状态信息
    status = Column(String(20), default="active")  # active, archived, deleted
    is_system_folder = Column(Boolean, default=False)  # 是否为系统文件夹
    
    # 元数据
    folder_metadata = Column(JSON, default={})
    tags = Column(ARRAY(String), default=[])
    color = Column(String(20), default="#1890ff")  # 文件夹颜色
    icon = Column(String(50), default="folder")  # 文件夹图标
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系定义
    knowledge_base = relationship("KnowledgeBase", foreign_keys=[kb_id])
    parent = relationship("KnowledgeFolder", remote_side=[id], back_populates="children")
    children = relationship("KnowledgeFolder", back_populates="parent", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="folder")
    
    # 复合索引
    __table_args__ = (
        Index('idx_folder_kb_parent', 'kb_id', 'parent_id'),
        Index('idx_folder_path', 'full_path'),
        Index('idx_folder_level_order', 'level', 'sort_order'),
        Index('idx_folder_status', 'status'),
        Index('idx_folder_created_at', 'created_at'),
        Index('idx_folder_search_priority', 'enable_scoped_search', 'search_priority'),
    )
    
    def get_full_path(self):
        """获取完整路径"""
        if self.parent:
            return f"{self.parent.get_full_path()}/{self.name}"
        return f"/{self.name}"
    
    def get_all_children_ids(self):
        """递归获取所有子文件夹ID"""
        child_ids = [child.id for child in self.children]
        for child in self.children:
            child_ids.extend(child.get_all_children_ids())
        return child_ids
    
    def get_breadcrumb(self):
        """获取面包屑导航"""
        breadcrumb = []
        current = self
        while current:
            breadcrumb.insert(0, {"id": current.id, "name": current.name})
            current = current.parent
        return breadcrumb


class FolderDocumentMapping(Base):
    """
    文件夹-文档映射表
    支持文档在多个文件夹中的软链接
    """
    __tablename__ = "folder_document_mappings"
    
    # 主键
    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    
    # 关联关系
    folder_id = Column(String(255), ForeignKey("knowledge_folders.id"), nullable=False, index=True)
    doc_id = Column(String(255), ForeignKey("documents.id"), nullable=False, index=True)
    
    # 映射类型
    mapping_type = Column(String(50), default="primary")  # primary, symbolic_link, auto_classified
    
    # 权重和优先级
    relevance_score = Column(Integer, default=100)  # 相关性评分 0-100
    display_priority = Column(Integer, default=0)  # 显示优先级
    
    # 分类信息
    auto_classified = Column(Boolean, default=False)  # 是否为自动分类
    classification_confidence = Column(Integer, default=0)  # 分类置信度 0-100
    classification_reason = Column(Text)  # 分类原因
    
    # 元数据
    mapping_metadata = Column(JSON, default={})
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系
    folder = relationship("KnowledgeFolder")
    document = relationship("Document")
    
    # 索引
    __table_args__ = (
        Index('idx_folder_doc_mapping', 'folder_id', 'doc_id'),
        Index('idx_mapping_type', 'mapping_type'),
        Index('idx_relevance_score', 'relevance_score'),
        Index('idx_auto_classified', 'auto_classified'),
    )


class FolderSearchIndex(Base):
    """
    文件夹搜索索引
    为文件夹级别的检索提供性能优化
    """
    __tablename__ = "folder_search_indexes"
    
    # 主键
    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    
    # 关联信息
    folder_id = Column(String(255), ForeignKey("knowledge_folders.id"), nullable=False, index=True)
    kb_id = Column(String(255), ForeignKey("knowledge_bases.id"), nullable=False, index=True)
    
    # 搜索索引数据
    searchable_content = Column(Text)  # 可搜索内容（文件夹名称+描述+文档摘要）
    keywords = Column(ARRAY(String), default=[])  # 提取的关键词
    semantic_tags = Column(ARRAY(String), default=[])  # 语义标签
    
    # 统计信息
    total_documents = Column(Integer, default=0)
    total_chunks = Column(Integer, default=0)
    avg_relevance_score = Column(Integer, default=0)
    
    # 检索配置
    boost_factor = Column(Integer, default=1)  # 检索加权因子
    enable_fuzzy_search = Column(Boolean, default=True)  # 是否启用模糊搜索
    
    # 缓存信息
    last_indexed_at = Column(DateTime(timezone=True))
    index_version = Column(String(50), default="1.0")
    needs_reindex = Column(Boolean, default=False)
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系
    folder = relationship("KnowledgeFolder")
    knowledge_base = relationship("KnowledgeBase")
    
    # 索引
    __table_args__ = (
        Index('idx_folder_search_kb', 'kb_id', 'folder_id'),
        Index('idx_search_needs_reindex', 'needs_reindex'),
        Index('idx_search_boost_factor', 'boost_factor'),
        Index('idx_search_last_indexed', 'last_indexed_at'),
    )


class FolderAccessLog(Base):
    """
    文件夹访问日志
    记录文件夹的访问和检索统计
    """
    __tablename__ = "folder_access_logs"
    
    # 主键
    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    
    # 关联信息
    folder_id = Column(String(255), ForeignKey("knowledge_folders.id"), nullable=False, index=True)
    kb_id = Column(String(255), ForeignKey("knowledge_bases.id"), nullable=False, index=True)
    
    # 访问信息
    access_type = Column(String(50), nullable=False)  # view, search, upload, download
    user_id = Column(String(255))  # 用户ID（可选）
    session_id = Column(String(255))  # 会话ID
    
    # 检索信息（如果是搜索类型）
    search_query = Column(Text)  # 搜索查询
    search_results_count = Column(Integer, default=0)  # 搜索结果数量
    search_duration = Column(Integer, default=0)  # 搜索耗时（毫秒）
    
    # 访问统计
    access_duration = Column(Integer, default=0)  # 访问时长（秒）
    documents_accessed = Column(Integer, default=0)  # 访问的文档数量
    
    # 元数据
    access_metadata = Column(JSON, default={})
    user_agent = Column(String(500))
    ip_address = Column(String(50))
    
    # 时间戳
    access_time = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    folder = relationship("KnowledgeFolder")
    knowledge_base = relationship("KnowledgeBase")
    
    # 索引
    __table_args__ = (
        Index('idx_access_folder_time', 'folder_id', 'access_time'),
        Index('idx_access_type_time', 'access_type', 'access_time'),
        Index('idx_access_user', 'user_id', 'access_time'),
        Index('idx_access_kb', 'kb_id', 'access_time'),
    )