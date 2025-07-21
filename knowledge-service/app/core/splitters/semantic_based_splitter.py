"""
语义切分器 - 基于语义边界的智能文档切分
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, Any, Optional, List
import re
from datetime import datetime

from app.schemas.splitter_schemas import ChunkInfo, SplitterType
from .base_splitter import BaseSplitter

logger = logging.getLogger(__name__)


class SemanticBasedSplitter(BaseSplitter):
    """语义切分器 - 基于语义边界进行智能切分"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config, SplitterType.SEMANTIC_BASED)
        # self.splitter_type is already set in parent class
        
        # 语义切分配置
        self.min_chunk_size = config.get('min_chunk_size', 200)
        self.max_chunk_size = config.get('max_chunk_size', 1500)
        self.overlap_sentences = config.get('overlap_sentences', 1)
        self.coherence_threshold = config.get('coherence_threshold', 0.7)
        self.use_sentence_embeddings = config.get('use_sentence_embeddings', False)
        
        # 语义边界标识符
        self.semantic_boundaries = [
            # 段落边界
            r'\n\s*\n',
            # 标题边界
            r'\n#+\s+',
            r'\n\d+\.\s+',
            r'\n[一二三四五六七八九十]+[、\.]\s*',
            r'\n[（\(][一二三四五六七八九十]+[）\)]\s*',
            # 列表边界
            r'\n[-•·]\s+',
            r'\n\d+\)\s+',
            # 引用边界
            r'\n>\s+',
            # 代码块边界
            r'\n```',
            r'\n---+',
        ]
        
        logger.info(f"SemanticBasedSplitter initialized with config: {config}")
    
    async def split_text(self, text: str, document_metadata: Optional[Dict[str, Any]] = None) -> List[ChunkInfo]:
        """
        执行语义切分
        
        Args:
            text: 要切分的文本
            document_metadata: 文档元数据
            
        Returns:
            分块列表
        """
        chunks, _ = await self.split_with_timing(text, document_metadata)
        return chunks
    
    async def split_with_timing(self, text: str, document_metadata: Optional[Dict[str, Any]] = None) -> tuple[List[ChunkInfo], float]:
        """
        执行语义切分并计时
        
        Args:
            text: 要切分的文本
            document_metadata: 文档元数据
            
        Returns:
            (分块列表, 处理时间)
        """
        start_time = time.time()
        
        try:
            # 预处理文本
            processed_text = self._preprocess_text(text)
            
            # 检测语义边界
            boundaries = await self._detect_semantic_boundaries(processed_text)
            
            # 基于边界创建分块
            chunks = await self._create_chunks_from_boundaries(
                processed_text, boundaries, document_metadata
            )
            
            # 后处理优化
            optimized_chunks = await self._optimize_chunks(chunks)
            
            processing_time = time.time() - start_time
            
            logger.info(
                f"Semantic splitting completed: {len(optimized_chunks)} chunks, "
                f"{processing_time:.3f}s"
            )
            
            return optimized_chunks, processing_time
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Semantic splitting failed: {e}")
            raise
    
    def _preprocess_text(self, text: str) -> str:
        """
        预处理文本
        
        Args:
            text: 原始文本
            
        Returns:
            预处理后的文本
        """
        # 标准化换行符
        text = re.sub(r'\r\n|\r', '\n', text)
        
        # 清理多余的空白字符
        text = re.sub(r'[ \t]+', ' ', text)
        
        # 标准化段落分隔
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        return text.strip()
    
    async def _detect_semantic_boundaries(self, text: str) -> List[int]:
        """
        检测语义边界
        
        Args:
            text: 预处理后的文本
            
        Returns:
            边界位置列表
        """
        boundaries = [0]  # 文档开始
        
        # 使用正则表达式检测各种语义边界
        for pattern in self.semantic_boundaries:
            matches = re.finditer(pattern, text, re.MULTILINE)
            for match in matches:
                pos = match.start()
                if pos not in boundaries and pos > 0:
                    boundaries.append(pos)
        
        # 检测句子边界
        sentence_boundaries = await self._detect_sentence_boundaries(text)
        boundaries.extend(sentence_boundaries)
        
        # 排序并去重
        boundaries = sorted(list(set(boundaries)))
        
        # 添加文档结束
        if boundaries[-1] != len(text):
            boundaries.append(len(text))
        
        return boundaries
    
    async def _detect_sentence_boundaries(self, text: str) -> List[int]:
        """
        检测句子边界
        
        Args:
            text: 文本
            
        Returns:
            句子边界位置列表
        """
        boundaries = []
        
        # 中文句子结束标点
        chinese_endings = r'[。！？；]'
        # 英文句子结束标点
        english_endings = r'[.!?;]'
        
        # 检测中文句子边界
        for match in re.finditer(chinese_endings, text):
            pos = match.end()
            # 确保不是小数点或缩写
            if pos < len(text) and (text[pos:pos+1].isspace() or text[pos:pos+1] in '\n\r'):
                boundaries.append(pos)
        
        # 检测英文句子边界
        for match in re.finditer(english_endings + r'\s+[A-Z]', text):
            pos = match.start() + 1
            boundaries.append(pos)
        
        return boundaries
    
    async def _create_chunks_from_boundaries(self, text: str, boundaries: List[int], 
                                           document_metadata: Optional[Dict[str, Any]] = None) -> List[ChunkInfo]:
        """
        基于边界创建分块
        
        Args:
            text: 文本
            boundaries: 边界位置列表
            document_metadata: 文档元数据
            
        Returns:
            分块列表
        """
        chunks = []
        chunk_index = 0
        
        i = 0
        while i < len(boundaries) - 1:
            chunk_start = boundaries[i]
            chunk_end = boundaries[i + 1]
            
            # 尝试扩展分块到合适的大小
            while (chunk_end - chunk_start < self.min_chunk_size and 
                   i + 2 < len(boundaries)):
                i += 1
                chunk_end = boundaries[i + 1]
            
            # 如果分块太大，尝试在中间找到合适的分割点
            if chunk_end - chunk_start > self.max_chunk_size:
                chunk_end = await self._find_optimal_split_point(
                    text, chunk_start, chunk_start + self.max_chunk_size, boundaries
                )
            
            # 提取分块内容
            chunk_content = text[chunk_start:chunk_end].strip()
            
            if chunk_content and len(chunk_content) >= 50:  # 最小内容长度
                # 计算语义连贯性分数
                coherence_score = await self._calculate_coherence_score(chunk_content)
                
                # 提取语义信息
                semantic_info = await self._extract_semantic_info(chunk_content)
                
                chunk = ChunkInfo(
                    id=str(uuid.uuid4()),
                    content=chunk_content,
                    start_char=chunk_start,
                    end_char=chunk_end,
                    chunk_index=chunk_index,
                    metadata={
                        'splitter_type': 'semantic_based',
                        'coherence_score': coherence_score,
                        'semantic_boundaries_count': len([b for b in boundaries if chunk_start <= b <= chunk_end]),
                        **(document_metadata or {})
                    },
                    semantic_info=semantic_info
                )
                
                chunks.append(chunk)
                chunk_index += 1
            
            i += 1
        
        return chunks
    
    async def _find_optimal_split_point(self, text: str, start: int, max_end: int, 
                                      boundaries: List[int]) -> int:
        """
        在指定范围内找到最优分割点
        
        Args:
            text: 文本
            start: 开始位置
            max_end: 最大结束位置
            boundaries: 边界列表
            
        Returns:
            最优分割点位置
        """
        # 在范围内查找边界点
        valid_boundaries = [b for b in boundaries if start < b <= max_end]
        
        if not valid_boundaries:
            return max_end
        
        # 选择最接近目标大小的边界点
        target_size = (self.min_chunk_size + self.max_chunk_size) // 2
        target_pos = start + target_size
        
        best_boundary = min(valid_boundaries, key=lambda b: abs(b - target_pos))
        return best_boundary
    
    async def _calculate_coherence_score(self, text: str) -> float:
        """
        计算文本的语义连贯性分数
        
        Args:
            text: 文本内容
            
        Returns:
            连贯性分数 (0-1)
        """
        try:
            # 简化的连贯性评估
            score = 0.7  # 基础分数
            
            # 检查句子数量
            sentences = re.split(r'[。！？.!?]', text)
            sentence_count = len([s for s in sentences if s.strip()])
            
            if sentence_count >= 2:
                score += 0.1
            
            # 检查段落结构
            paragraphs = text.split('\n\n')
            if len(paragraphs) > 1:
                score += 0.1
            
            # 检查关键词重复（简单的主题一致性）
            words = re.findall(r'\b\w+\b', text.lower())
            if len(words) > 10:
                word_freq = {}
                for word in words:
                    if len(word) > 3:  # 忽略短词
                        word_freq[word] = word_freq.get(word, 0) + 1
                
                # 如果有重复的关键词，增加连贯性分数
                repeated_words = [w for w, c in word_freq.items() if c > 1]
                if repeated_words:
                    score += min(0.1, len(repeated_words) * 0.02)
            
            return min(1.0, score)
            
        except Exception as e:
            logger.warning(f"Failed to calculate coherence score: {e}")
            return 0.7
    
    async def _extract_semantic_info(self, text: str) -> Dict[str, Any]:
        """
        提取语义信息
        
        Args:
            text: 文本内容
            
        Returns:
            语义信息字典
        """
        try:
            # 句子统计
            sentences = re.split(r'[。！？.!?]', text)
            sentence_count = len([s for s in sentences if s.strip()])
            
            # 段落统计
            paragraphs = text.split('\n\n')
            paragraph_count = len([p for p in paragraphs if p.strip()])
            
            # 检测内容类型
            content_type = self._detect_content_type(text)
            
            # 提取关键词（简化版）
            keywords = self._extract_keywords(text)
            
            return {
                'sentence_count': sentence_count,
                'paragraph_count': paragraph_count,
                'content_type': content_type,
                'keywords': keywords[:10],  # 最多10个关键词
                'avg_sentence_length': len(text) / max(sentence_count, 1),
                'has_structure': paragraph_count > 1 or any(marker in text for marker in ['#', '1.', '一、'])
            }
            
        except Exception as e:
            logger.warning(f"Failed to extract semantic info: {e}")
            return {}
    
    def _detect_content_type(self, text: str) -> str:
        """检测内容类型"""
        if re.search(r'```|def |class |import ', text):
            return 'code'
        elif re.search(r'#+\s+|\*\*|__', text):
            return 'markdown'
        elif re.search(r'第[一二三四五六七八九十\d]+章|第[一二三四五六七八九十\d]+节', text):
            return 'structured_document'
        elif re.search(r'\d+\.\s+|\([一二三四五六七八九十\d]+\)', text):
            return 'list'
        else:
            return 'plain_text'
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词（简化版）"""
        try:
            # 移除标点符号，提取词汇
            words = re.findall(r'\b\w+\b', text.lower())
            
            # 过滤短词和常见停用词
            stop_words = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', 
                         'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with'}
            
            filtered_words = [w for w in words if len(w) > 2 and w not in stop_words]
            
            # 统计词频
            word_freq = {}
            for word in filtered_words:
                word_freq[word] = word_freq.get(word, 0) + 1
            
            # 按频率排序，返回前10个
            keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
            return [word for word, freq in keywords[:10]]
            
        except Exception:
            return []
    
    async def _optimize_chunks(self, chunks: List[ChunkInfo]) -> List[ChunkInfo]:
        """
        优化分块结果
        
        Args:
            chunks: 原始分块列表
            
        Returns:
            优化后的分块列表
        """
        if not chunks:
            return chunks
        
        optimized_chunks = []
        
        for i, chunk in enumerate(chunks):
            # 检查分块质量
            if chunk.metadata.get('coherence_score', 0) < self.coherence_threshold:
                # 尝试与相邻分块合并
                if i > 0 and len(optimized_chunks) > 0:
                    prev_chunk = optimized_chunks[-1]
                    combined_length = len(prev_chunk.content) + len(chunk.content)
                    
                    if combined_length <= self.max_chunk_size:
                        # 合并分块
                        merged_chunk = await self._merge_chunks(prev_chunk, chunk)
                        optimized_chunks[-1] = merged_chunk
                        continue
            
            optimized_chunks.append(chunk)
        
        return optimized_chunks
    
    async def _merge_chunks(self, chunk1: ChunkInfo, chunk2: ChunkInfo) -> ChunkInfo:
        """
        合并两个分块
        
        Args:
            chunk1: 第一个分块
            chunk2: 第二个分块
            
        Returns:
            合并后的分块
        """
        merged_content = chunk1.content + "\n\n" + chunk2.content
        
        # 重新计算语义信息
        coherence_score = await self._calculate_coherence_score(merged_content)
        semantic_info = await self._extract_semantic_info(merged_content)
        
        return ChunkInfo(
            id=str(uuid.uuid4()),
            content=merged_content,
            start_char=chunk1.start_char,
            end_char=chunk2.end_char,
            chunk_index=chunk1.chunk_index,
            metadata={
                **chunk1.metadata,
                'coherence_score': coherence_score,
                'merged_from': [chunk1.id, chunk2.id]
            },
            semantic_info=semantic_info
        )
    
    def get_statistics(self, chunks: List[ChunkInfo]) -> Dict[str, Any]:
        """获取切分统计信息"""
        if not chunks:
            return {"total_chunks": 0, "avg_chunk_length": 0}
        
        chunk_lengths = [len(chunk.content) for chunk in chunks]
        coherence_scores = [
            chunk.metadata.get('coherence_score', 0.7) 
            for chunk in chunks
        ]
        
        return {
            "total_chunks": len(chunks),
            "avg_chunk_length": sum(chunk_lengths) / len(chunk_lengths),
            "min_chunk_length": min(chunk_lengths),
            "max_chunk_length": max(chunk_lengths),
            "avg_coherence_score": sum(coherence_scores) / len(coherence_scores),
            "high_coherence_chunks": len([s for s in coherence_scores if s >= 0.8]),
            "splitter_type": "semantic_based",
            "total_characters": sum(chunk_lengths)
        }