"""
简化的知识库文件夹模型
专注于文档分类和检索范围控制
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
    知识库文件夹模型 - 简化版本
    专注于文档分类和检索范围控制
    """
    __tablename__ = "knowledge_folders"
    
    # 基本信息
    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    kb_id = Column(String(255), ForeignKey("knowledge_bases.id"), nullable=False, index=True)
    parent_id = Column(String(255), ForeignKey("knowledge_folders.id"), nullable=True, index=True)
    
    # 文件夹属性
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    level = Column(Integer, default=0)  # 0=根目录, 1=一级, 2=二级
    full_path = Column(String(1000))  # 如: /技术文档/API设计
    
    # 检索配置 - 核心功能
    enable_search = Column(Boolean, default=True)  # 是否可被检索
    search_scope = Column(String(50), default="folder_only")  # folder_only, include_subfolders
    search_weight = Column(Integer, default=1)  # 检索权重 1-10
    
    # 统计信息
    document_count = Column(Integer, default=0)
    total_size = Column(Integer, default=0)
    
    # 状态
    status = Column(String(20), default="active")  # active, archived, deleted
    
    # UI显示属性
    color = Column(String(50), default="#1890ff")  # 文件夹颜色
    icon = Column(String(50), default="folder")    # 文件夹图标
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系
    knowledge_base = relationship("KnowledgeBase", foreign_keys=[kb_id])
    parent = relationship("KnowledgeFolder", remote_side=[id], back_populates="children")
    children = relationship("KnowledgeFolder", back_populates="parent")
    # documents = relationship("Document", back_populates="folder")  # 暂时注释掉避免循环导入
    
    # 索引
    __table_args__ = (
        Index('idx_folder_kb_status', 'kb_id', 'status'),
        Index('idx_folder_search_enabled', 'kb_id', 'enable_search'),
        Index('idx_folder_path', 'full_path'),
        Index('idx_folder_level', 'level'),
    )
    
    def get_search_scope_folders(self):
        """获取检索范围内的文件夹ID列表"""
        if self.search_scope == "folder_only":
            return [self.id]
        elif self.search_scope == "include_subfolders":
            # 包含所有子文件夹
            folder_ids = [self.id]
            for child in self.children:
                if child.status == "active":
                    folder_ids.extend(child.get_search_scope_folders())
            return folder_ids
        return [self.id]


class FolderSearchConfig(Base):
    """
    文件夹检索配置表
    存储每个文件夹的个性化检索设置
    """
    __tablename__ = "folder_search_configs"
    
    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    folder_id = Column(String(255), ForeignKey("knowledge_folders.id"), nullable=False, unique=True, index=True)
    kb_id = Column(String(255), ForeignKey("knowledge_bases.id"), nullable=False, index=True)
    
    # 检索参数配置
    similarity_threshold = Column(Integer, default=70)  # 相似度阈值 0-100
    max_results = Column(Integer, default=10)  # 最大返回结果数
    enable_semantic_search = Column(Boolean, default=True)  # 是否启用语义检索
    enable_keyword_search = Column(Boolean, default=True)  # 是否启用关键词检索
    
    # 结果排序配置
    sort_by = Column(String(50), default="relevance")  # relevance, date, size, filename
    sort_order = Column(String(10), default="desc")  # asc, desc
    
    # 文件类型过滤
    allowed_file_types = Column(ARRAY(String), default=[])  # 允许的文件类型，空数组表示全部
    
    # 高级配置
    boost_recent_documents = Column(Boolean, default=False)  # 是否提升近期文档的权重
    boost_factor = Column(Integer, default=1)  # 权重提升因子 1-5
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系
    folder = relationship("KnowledgeFolder")
    knowledge_base = relationship("KnowledgeBase")
    
    # 索引
    __table_args__ = (
        Index('idx_search_config_kb', 'kb_id'),
        Index('idx_search_config_folder', 'folder_id'),
    )