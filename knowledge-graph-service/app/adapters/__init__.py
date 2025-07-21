"""
数据适配器模块
提供新微服务与原始项目之间的数据格式转换
"""

from .legacy_adapter import (
    LegacyKnowledgeGraphAdapter,
    LegacyEntityAdapter,
    LegacyRelationAdapter,
    FrontendGraphAdapter,
    LegacyAPIResponseAdapter
)

__all__ = [
    "LegacyKnowledgeGraphAdapter",
    "LegacyEntityAdapter", 
    "LegacyRelationAdapter",
    "FrontendGraphAdapter",
    "LegacyAPIResponseAdapter"
]