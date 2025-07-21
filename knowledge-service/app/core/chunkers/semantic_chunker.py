"""
语义感知的文本分块器
从原始后端项目迁移并适配到微服务架构
"""

import re
import logging
from typing import List, Optional

from ..text_base import TextChunker, ChunkConfig
from .smart_chunker import SmartTextChunker

logger = logging.getLogger(__name__)

class SemanticChunker(TextChunker):
    """语义感知的文本分块器"""
    
    def __init__(self, config: Optional[ChunkConfig] = None):
        super().__init__(config)
    
    def chunk(self, text: str) -> List[str]:
        """基于语义的文本分块"""
        if not text:
            return []
        
        # 首先按段落分割
        paragraphs = self._split_by_paragraphs(text)
        
        chunks = []
        current_chunk = ""
        
        for paragraph in paragraphs:
            # 如果当前段落本身就很长，需要进一步分割
            if len(paragraph) > self.config.chunk_size:
                # 保存当前块（如果有内容）
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                
                # 分割长段落
                sub_chunks = self._split_long_paragraph(paragraph)
                chunks.extend(sub_chunks)
            else:
                # 检查加入当前段落后是否超过大小限制
                potential_chunk = current_chunk + "\n\n" + paragraph if current_chunk else paragraph
                
                if len(potential_chunk) <= self.config.chunk_size:
                    current_chunk = potential_chunk
                else:
                    # 保存当前块并开始新块
                    if current_chunk.strip():
                        chunks.append(current_chunk.strip())
                    current_chunk = paragraph
        
        # 添加最后一个块
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return self.validate_chunks(chunks)
    
    def _split_by_paragraphs(self, text: str) -> List[str]:
        """按段落分割文本"""
        # 标准化换行符
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # 按双换行符分割段落
        paragraphs = text.split('\n\n')
        
        # 清理并过滤空段落
        return [p.strip() for p in paragraphs if p.strip()]
    
    def _split_long_paragraph(self, paragraph: str) -> List[str]:
        """分割过长的段落"""
        # 如果段落不是太长，直接返回
        if len(paragraph) <= self.config.chunk_size:
            return [paragraph]
        
        # 尝试按句子分割
        sentences = self._split_by_sentences(paragraph)
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if len(sentence) > self.config.chunk_size:
                # 单个句子就超过限制，使用基本分块器
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                
                basic_chunker = SmartTextChunker(self.config)
                chunks.extend(basic_chunker.chunk(sentence))
            else:
                potential_chunk = current_chunk + " " + sentence if current_chunk else sentence
                
                if len(potential_chunk) <= self.config.chunk_size:
                    current_chunk = potential_chunk
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = sentence
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _split_by_sentences(self, text: str) -> List[str]:
        """按句子分割文本"""
        # 简单的句子分割（可以后续优化为更复杂的NLP分割）
        sentence_endings = r'[.!?。！？]'
        sentences = re.split(f'({sentence_endings})', text)
        
        # 重新组合句子和标点
        result = []
        for i in range(0, len(sentences) - 1, 2):
            if i + 1 < len(sentences):
                sentence = sentences[i] + sentences[i + 1]
                sentence = sentence.strip()
                if sentence:
                    result.append(sentence)
        
        # 处理最后一个句子（如果没有标点结尾）
        if len(sentences) % 2 == 1 and sentences[-1].strip():
            result.append(sentences[-1].strip())
        
        return result