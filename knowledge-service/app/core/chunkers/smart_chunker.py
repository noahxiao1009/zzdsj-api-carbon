"""
智能文本分块器
从原始后端项目迁移并适配到微服务架构
"""

import re
import logging
from typing import List, Optional, Set

from ..text_base import TextChunker, ChunkConfig, TextProcessingError

logger = logging.getLogger(__name__)

class SmartTextChunker(TextChunker):
    """智能文本分块器"""
    
    def __init__(self, config: Optional[ChunkConfig] = None):
        super().__init__(config)
        # 预编译边界字符的正则表达式
        self._boundary_pattern = self._compile_boundary_pattern()
        # 缓存句子边界
        self._sentence_boundaries: Set[str] = {'.', '!', '?', '。', '！', '？'}
    
    def _compile_boundary_pattern(self) -> re.Pattern:
        """编译边界字符的正则表达式"""
        escaped_chars = re.escape(self.config.boundary_chars)
        return re.compile(f'[{escaped_chars}]')
    
    def chunk(self, text: str) -> List[str]:
        """智能文本分块"""
        if not text or self.config.chunk_size <= 0:
            return []
        
        # 预处理文本
        text = text.strip()
        if len(text) <= self.config.chunk_size:
            return [text]
        
        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            # 计算当前块的结束位置
            end = min(start + self.config.chunk_size, text_len)
            
            # 如果不是最后一块且需要考虑边界，寻找最佳分割点
            if end < text_len and self.config.respect_boundaries:
                end = self._find_best_split_point(text, start, end)
            
            # 提取块
            chunk = text[start:end].strip()
            if chunk and len(chunk) >= self.config.min_chunk_size:
                chunks.append(chunk)
            
            # 计算下一个起始位置，考虑重叠
            start = self._calculate_next_start(end, start)
            
            # 防止无限循环
            if start >= end:
                if end < text_len:
                    start = end + 1
                else:
                    break
        
        return self.validate_chunks(chunks)
    
    def _find_best_split_point(self, text: str, start: int, initial_end: int) -> int:
        """寻找最佳分割点"""
        # 在chunk_size的80%-100%范围内寻找最佳分割点
        min_search_pos = start + int(self.config.chunk_size * 0.8)
        max_search_pos = min(initial_end, len(text))
        
        # 优先级：句子边界 > 段落边界 > 其他边界字符
        best_split = initial_end
        
        # 搜索范围
        search_range = text[min_search_pos:max_search_pos]
        
        # 1. 首先寻找句子边界
        sentence_pos = self._find_last_sentence_boundary(search_range)
        if sentence_pos != -1:
            return min_search_pos + sentence_pos + 1
        
        # 2. 寻找段落边界
        paragraph_pos = search_range.rfind('\n\n')
        if paragraph_pos != -1:
            return min_search_pos + paragraph_pos
        
        # 3. 寻找行边界
        line_pos = search_range.rfind('\n')
        if line_pos != -1:
            return min_search_pos + line_pos
        
        # 4. 寻找单词边界
        word_pos = search_range.rfind(' ')
        if word_pos != -1:
            return min_search_pos + word_pos
        
        # 5. 寻找其他边界字符
        boundary_match = None
        for match in self._boundary_pattern.finditer(search_range):
            boundary_match = match
        
        if boundary_match:
            return min_search_pos + boundary_match.end()
        
        # 如果都找不到，使用原始位置
        return initial_end
    
    def _find_last_sentence_boundary(self, text: str) -> int:
        """寻找最后一个句子边界"""
        last_pos = -1
        for boundary in self._sentence_boundaries:
            pos = text.rfind(boundary)
            if pos > last_pos:
                last_pos = pos
        return last_pos
    
    def _calculate_next_start(self, current_end: int, current_start: int) -> int:
        """计算下一个起始位置"""
        if self.config.chunk_overlap <= 0:
            return current_end
        
        next_start = current_end - self.config.chunk_overlap
        
        # 确保有进展
        if next_start <= current_start:
            return current_start + 1
        
        return next_start