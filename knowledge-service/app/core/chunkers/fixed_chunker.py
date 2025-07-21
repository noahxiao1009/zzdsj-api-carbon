"""
固定大小分块器
从原始后端项目迁移并适配到微服务架构
"""

import logging
from typing import List, Optional

from ..text_base import TextChunker, ChunkConfig

logger = logging.getLogger(__name__)

class FixedSizeChunker(TextChunker):
    """固定大小分块器（简单且快速）"""
    
    def __init__(self, config: Optional[ChunkConfig] = None):
        super().__init__(config)
    
    def chunk(self, text: str) -> List[str]:
        """固定大小分块"""
        if not text:
            return []
        
        chunks = []
        text_len = len(text)
        start = 0
        
        while start < text_len:
            end = min(start + self.config.chunk_size, text_len)
            chunk = text[start:end]
            
            if chunk.strip():
                chunks.append(chunk.strip())
            
            start = end - self.config.chunk_overlap if self.config.chunk_overlap > 0 else end
            
            # 防止无限循环
            if start >= end:
                break
        
        return self.validate_chunks(chunks)