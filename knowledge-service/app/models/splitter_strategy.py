"""
切分策略数据模型
定义文档切分策略的数据结构和数据库映射
"""

from sqlalchemy import Column, String, Text, Boolean, DateTime, Integer, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.models.database import Base


class SplitterStrategy(Base):
    """切分策略模型"""
    __tablename__ = "splitter_strategies"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True, comment="策略名称")
    description = Column(Text, comment="策略描述")
    config = Column(JSON, nullable=False, comment="策略配置JSON")
    is_system = Column(Boolean, default=False, comment="是否为系统预设策略")
    is_active = Column(Boolean, default=True, comment="是否激活")
    created_by = Column(String(100), default="system", comment="创建者")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # 反向关系
    # knowledge_bases = relationship("KnowledgeBase", back_populates="default_splitter_strategy")
    usage_records = relationship("SplitterStrategyUsage", back_populates="strategy")
    
    def __repr__(self):
        return f"<SplitterStrategy(id={self.id}, name='{self.name}', is_system={self.is_system})>"
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "config": self.config,
            "is_system": self.is_system,
            "is_active": self.is_active,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def get_default_config(cls, strategy_type: str = "basic") -> dict:
        """获取默认配置"""
        default_configs = {
            "basic": {
                "chunk_size": 1000,
                "chunk_overlap": 200,
                "chunk_strategy": "basic",
                "preserve_structure": True,
                "separators": ["\n\n", "\n", " ", ""],
                "length_function": "len"
            },
            "semantic": {
                "chunk_size": 1500,
                "chunk_overlap": 150,
                "chunk_strategy": "semantic",
                "preserve_structure": True,
                "use_semantic_splitter": True,
                "embedding_model": "text-embedding-ada-002",
                "similarity_threshold": 0.7
            },
            "smart": {
                "chunk_size": 2000,
                "chunk_overlap": 100,
                "chunk_strategy": "smart",
                "preserve_structure": True,
                "detect_headers": True,
                "detect_paragraphs": True,
                "detect_lists": True,
                "min_chunk_size": 100,
                "max_chunk_size": 3000
            },
            "code": {
                "chunk_size": 1500,
                "chunk_overlap": 50,
                "chunk_strategy": "code",
                "preserve_structure": True,
                "detect_functions": True,
                "detect_classes": True,
                "detect_imports": True,
                "language_specific": True
            },
            "large": {
                "chunk_size": 3000,
                "chunk_overlap": 300,
                "chunk_strategy": "hierarchical",
                "preserve_structure": True,
                "use_hierarchy": True,
                "max_depth": 3,
                "min_section_size": 500
            }
        }
        return default_configs.get(strategy_type, default_configs["basic"])


class SplitterStrategyUsage(Base):
    """切分策略使用统计模型"""
    __tablename__ = "splitter_strategy_usage"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_id = Column(UUID(as_uuid=True), ForeignKey('splitter_strategies.id'), nullable=False, comment="策略ID")
    kb_id = Column(String(255), nullable=False, comment="知识库ID")
    usage_count = Column(Integer, default=1, comment="使用次数")
    last_used_at = Column(DateTime(timezone=True), server_default=func.now(), comment="最后使用时间")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    
    # 关系映射
    strategy = relationship("SplitterStrategy", back_populates="usage_records")
    
    def __repr__(self):
        return f"<SplitterStrategyUsage(strategy_id={self.strategy_id}, kb_id={self.kb_id}, count={self.usage_count})>"
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            "id": str(self.id),
            "strategy_id": str(self.strategy_id),
            "kb_id": str(self.kb_id),
            "usage_count": self.usage_count,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


