"""
文档分块服务
将文档内容分割成适合向量化的块
"""

import re
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging

# 集成现有的分块器
from app.core.splitters import (
    TokenBasedSplitter,
    SemanticBasedSplitter
)

logger = logging.getLogger(__name__)


@dataclass
class ChunkConfig:
    """分块配置"""
    chunk_size: int = 1000
    chunk_overlap: int = 200
    strategy: str = "token_based"  # token_based, semantic_based
    preserve_structure: bool = True
    min_chunk_size: int = 100
    max_chunk_size: int = 2000


@dataclass
class DocumentChunk:
    """文档分块数据结构"""
    index: int
    content: str
    start_char: int
    end_char: int
    token_count: int
    char_count: int
    content_hash: str
    metadata: Dict[str, Any]
    section_title: Optional[str] = None


class DocumentChunker:
    """文档分块服务"""
    
    def __init__(self):
        # 创建默认配置
        default_token_config = {
            'chunk_size': 1000,
            'chunk_overlap': 200,
            'use_token_count': False,
            'separator': '\n\n'
        }
        
        default_semantic_config = {
            'min_chunk_size': 100,
            'max_chunk_size': 2000,
            'similarity_threshold': 0.7,
            'language': 'zh'
        }
        
        self.token_splitter = TokenBasedSplitter(default_token_config)
        self.semantic_splitter = SemanticBasedSplitter(default_semantic_config)
        
    async def chunk_document(
        self, 
        content: str, 
        config: ChunkConfig,
        document_metadata: Optional[Dict[str, Any]] = None
    ) -> List[DocumentChunk]:
        """
        将文档内容分块
        
        Args:
            content: 文档内容
            config: 分块配置
            document_metadata: 文档元数据
            
        Returns:
            分块列表
        """
        try:
            if not content or not content.strip():
                return []
            
            # 预处理文档内容
            processed_content = self._preprocess_content(content, config)
            
            # 根据策略选择分块方法
            if config.strategy == "semantic_based":
                chunks = await self._semantic_chunk(processed_content, config)
            else:
                chunks = await self._token_based_chunk(processed_content, config)
            
            # 后处理分块
            processed_chunks = self._postprocess_chunks(chunks, config, document_metadata)
            
            return processed_chunks
            
        except Exception as e:
            logger.error(f"Error chunking document: {e}")
            raise e
    
    def _preprocess_content(self, content: str, config: ChunkConfig) -> str:
        """预处理文档内容"""
        # 标准化换行符
        content = re.sub(r'\r\n|\r', '\n', content)
        
        # 移除多余空白字符
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
        content = re.sub(r'[ \t]+', ' ', content)
        
        # 保留结构时保持段落分隔
        if config.preserve_structure:
            # 确保段落间有适当分隔
            content = re.sub(r'\n\n+', '\n\n', content)
        else:
            # 不保留结构时简化为单行
            content = re.sub(r'\n+', ' ', content)
        
        return content.strip()
    
    async def _token_based_chunk(
        self, 
        content: str, 
        config: ChunkConfig
    ) -> List[Tuple[str, int, int]]:
        """基于Token的分块"""
        try:
            chunks = await self.token_splitter.split_text(
                text=content,
                chunk_size=config.chunk_size,
                chunk_overlap=config.chunk_overlap
            )
            
            # 计算每个分块的字符位置
            result_chunks = []
            current_pos = 0
            
            for chunk in chunks:
                # 在原文中查找分块位置
                start_pos = content.find(chunk, current_pos)
                if start_pos == -1:
                    # 如果找不到，使用近似位置
                    start_pos = current_pos
                
                end_pos = start_pos + len(chunk)
                result_chunks.append((chunk, start_pos, end_pos))
                current_pos = start_pos + len(chunk) - config.chunk_overlap
            
            return result_chunks
            
        except Exception as e:
            logger.error(f"Token-based chunking failed: {e}")
            # 回退到简单分块
            return self._simple_chunk(content, config)
    
    async def _semantic_chunk(
        self, 
        content: str, 
        config: ChunkConfig
    ) -> List[Tuple[str, int, int]]:
        """基于语义的分块"""
        try:
            chunks = await self.semantic_splitter.split_text(
                text=content,
                chunk_size=config.chunk_size,
                chunk_overlap=config.chunk_overlap
            )
            
            # 计算每个分块的字符位置
            result_chunks = []
            current_pos = 0
            
            for chunk in chunks:
                start_pos = content.find(chunk, current_pos)
                if start_pos == -1:
                    start_pos = current_pos
                
                end_pos = start_pos + len(chunk)
                result_chunks.append((chunk, start_pos, end_pos))
                current_pos = end_pos
            
            return result_chunks
            
        except Exception as e:
            logger.error(f"Semantic chunking failed: {e}")
            # 回退到Token分块
            return await self._token_based_chunk(content, config)
    
    def _simple_chunk(
        self, 
        content: str, 
        config: ChunkConfig
    ) -> List[Tuple[str, int, int]]:
        """简单的字符级分块（回退方案）"""
        chunks = []
        content_length = len(content)
        
        start = 0
        while start < content_length:
            end = min(start + config.chunk_size, content_length)
            
            # 尝试在单词边界处分割
            if end < content_length:
                # 寻找最近的空格或标点符号
                for i in range(end, max(start + config.min_chunk_size, end - 100), -1):
                    if content[i] in ' \n.,;!?。，；！？':
                        end = i + 1
                        break
            
            chunk_text = content[start:end].strip()
            if len(chunk_text) >= config.min_chunk_size:
                chunks.append((chunk_text, start, end))
            
            start = end - config.chunk_overlap
        
        return chunks
    
    def _postprocess_chunks(
        self, 
        chunks: List[Tuple[str, int, int]], 
        config: ChunkConfig,
        document_metadata: Optional[Dict[str, Any]] = None
    ) -> List[DocumentChunk]:
        """后处理分块"""
        processed_chunks = []
        
        for i, (chunk_content, start_char, end_char) in enumerate(chunks):
            # 清理分块内容
            cleaned_content = self._clean_chunk_content(chunk_content)
            
            # 跳过过短的分块
            if len(cleaned_content) < config.min_chunk_size:
                continue
            
            # 截断过长的分块
            if len(cleaned_content) > config.max_chunk_size:
                cleaned_content = cleaned_content[:config.max_chunk_size]
            
            # 计算Token数量（简单估算）
            token_count = self._estimate_token_count(cleaned_content)
            
            # 生成内容哈希
            content_hash = hashlib.md5(cleaned_content.encode('utf-8')).hexdigest()
            
            # 提取章节标题（如果可能）
            section_title = self._extract_section_title(cleaned_content)
            
            # 构建分块元数据
            chunk_metadata = {
                'chunk_method': config.strategy,
                'original_length': len(chunk_content),
                'cleaned_length': len(cleaned_content),
            }
            
            if document_metadata:
                chunk_metadata.update({
                    'document_metadata': document_metadata
                })
            
            # 创建分块对象
            chunk = DocumentChunk(
                index=i,
                content=cleaned_content,
                start_char=start_char,
                end_char=end_char,
                token_count=token_count,
                char_count=len(cleaned_content),
                content_hash=content_hash,
                metadata=chunk_metadata,
                section_title=section_title
            )
            
            processed_chunks.append(chunk)
        
        return processed_chunks
    
    def _clean_chunk_content(self, content: str) -> str:
        """清理分块内容"""
        # 移除多余空白
        content = re.sub(r'\s+', ' ', content)
        
        # 移除开头和结尾的空白
        content = content.strip()
        
        # 确保以句号结尾（如果不是以标点符号结尾）
        if content and not content[-1] in '.!?。！？':
            # 查找最后一个完整句子
            last_punct = max(
                content.rfind('.'), content.rfind('!'), content.rfind('?'),
                content.rfind('。'), content.rfind('！'), content.rfind('？')
            )
            
            if last_punct > len(content) * 0.8:  # 如果最后一个标点符号位置合理
                content = content[:last_punct + 1]
        
        return content
    
    def _estimate_token_count(self, text: str) -> int:
        """估算Token数量"""
        # 简单估算：中文按字符计算，英文按单词计算
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_words = len(re.findall(r'\b[a-zA-Z]+\b', text))
        
        # 中文字符数 + 英文单词数 * 1.3（英文单词平均长度）
        estimated_tokens = chinese_chars + int(english_words * 1.3)
        
        return max(1, estimated_tokens)
    
    def _extract_section_title(self, content: str) -> Optional[str]:
        """提取章节标题"""
        lines = content.split('\n')
        
        for line in lines[:3]:  # 只检查前3行
            line = line.strip()
            
            # 检查是否是标题格式
            if (len(line) < 100 and  # 标题通常较短
                (line.startswith('#') or  # Markdown标题
                 re.match(r'^[一二三四五六七八九十\d]+[、\.]\s*', line) or  # 数字标题
                 re.match(r'^第[一二三四五六七八九十\d]+[章节条款]\s*', line) or  # 章节标题
                 line.isupper() or  # 全大写
                 re.match(r'^[A-Z][a-z\s]+$', line))):  # 首字母大写的英文标题
                return line
        
        return None
    
    async def get_chunk_statistics(self, chunks: List[DocumentChunk]) -> Dict[str, Any]:
        """获取分块统计信息"""
        if not chunks:
            return {}
        
        total_chars = sum(chunk.char_count for chunk in chunks)
        total_tokens = sum(chunk.token_count for chunk in chunks)
        
        chunk_sizes = [chunk.char_count for chunk in chunks]
        token_sizes = [chunk.token_count for chunk in chunks]
        
        return {
            'total_chunks': len(chunks),
            'total_characters': total_chars,
            'total_tokens': total_tokens,
            'avg_chunk_size': total_chars / len(chunks),
            'avg_token_count': total_tokens / len(chunks),
            'min_chunk_size': min(chunk_sizes),
            'max_chunk_size': max(chunk_sizes),
            'min_token_count': min(token_sizes),
            'max_token_count': max(token_sizes),
            'chunks_with_titles': len([c for c in chunks if c.section_title])
        }