"""
文本分块器工厂
从原始后端项目迁移并适配到微服务架构
"""

import logging
from typing import Optional

from ..text_base import TextChunker, ChunkConfig
from .smart_chunker import SmartTextChunker
from .semantic_chunker import SemanticChunker
from .fixed_chunker import FixedSizeChunker

logger = logging.getLogger(__name__)

def create_chunker(chunker_type: str = "smart", config: Optional[ChunkConfig] = None) -> TextChunker:
    """创建文本分块器"""
    chunkers = {
        "smart": SmartTextChunker,
        "semantic": SemanticChunker,
        "fixed": FixedSizeChunker
    }
    
    if chunker_type not in chunkers:
        raise ValueError(f"未知的分块器类型: {chunker_type}")
    
    return chunkers[chunker_type](config)

def chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200, 
               chunker_type: str = "smart") -> list[str]:
    """向后兼容的文本分块函数"""
    config = ChunkConfig(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunker = create_chunker(chunker_type, config)
    return chunker.chunk(text)