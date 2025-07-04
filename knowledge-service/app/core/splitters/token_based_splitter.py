import re
import tiktoken
from typing import List, Dict, Any, Optional
from .base_splitter import BaseSplitter
from ...schemas.splitter_schemas import ChunkInfo, SplitterType


class TokenBasedSplitter(BaseSplitter):
    """基于Token/字符的文档切分器"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化Token切分器
        
        Args:
            config: TokenBasedConfig配置字典
        """
        super().__init__(config, SplitterType.TOKEN_BASED)
        
        # 初始化tokenizer（如果使用token计数）
        self.tokenizer = None
        if config.get('use_token_count', False):
            try:
                self.tokenizer = tiktoken.encoding_for_model("gpt-3.5-turbo")
            except Exception as e:
                self.logger.warning(f"Failed to initialize tokenizer: {e}, falling back to character count")
                self.config['use_token_count'] = False
    
    async def split_text(self, text: str, document_metadata: Optional[Dict[str, Any]] = None) -> List[ChunkInfo]:
        """
        切分文本
        
        Args:
            text: 要切分的文本
            document_metadata: 文档元数据
            
        Returns:
            切分后的文本块列表
        """
        # 预处理文本
        if self.config.get('strip_whitespace', True):
            text = self.preprocess_text(text)
        
        # 获取配置参数
        chunk_size = self.config.get('chunk_size', 1000)
        chunk_overlap = self.config.get('chunk_overlap', 200)
        separators = self._get_separators()
        
        # 执行切分
        chunks = []
        if self.config.get('use_token_count', False) and self.tokenizer:
            chunks = await self._split_by_tokens(text, chunk_size, chunk_overlap, separators)
        else:
            chunks = await self._split_by_characters(text, chunk_size, chunk_overlap, separators)
        
        # 添加元数据
        for chunk in chunks:
            chunk.metadata.update({
                'splitter_type': 'token_based',
                'chunk_size_config': chunk_size,
                'chunk_overlap_config': chunk_overlap,
                'use_token_count': self.config.get('use_token_count', False),
                **(document_metadata or {})
            })
        
        # 后处理
        chunks = self.postprocess_chunks(chunks)
        
        return chunks
    
    def _get_separators(self) -> List[str]:
        """获取分隔符列表"""
        primary_separator = self.config.get('separator', '\n\n')
        secondary_separators = self.config.get('secondary_separators', ['\n', '。', '！', '？', '. ', '! ', '? '])
        
        # 构建分隔符优先级列表
        separators = [primary_separator] + secondary_separators
        
        # 去重但保持顺序
        seen = set()
        unique_separators = []
        for sep in separators:
            if sep not in seen:
                seen.add(sep)
                unique_separators.append(sep)
        
        return unique_separators
    
    async def _split_by_characters(
        self, 
        text: str, 
        chunk_size: int, 
        chunk_overlap: int, 
        separators: List[str]
    ) -> List[ChunkInfo]:
        """
        按字符数切分文本
        
        Args:
            text: 要切分的文本
            chunk_size: 块大小
            chunk_overlap: 重叠大小
            separators: 分隔符列表
            
        Returns:
            切分后的文本块列表
        """
        chunks = []
        start_pos = 0
        chunk_index = 0
        
        while start_pos < len(text):
            # 确定当前块的结束位置
            end_pos = min(start_pos + chunk_size, len(text))
            
            # 尝试在分隔符处断开
            if end_pos < len(text):
                best_break_pos = self._find_best_break_position(
                    text, start_pos, end_pos, separators
                )
                if best_break_pos > start_pos:
                    end_pos = best_break_pos
            
            # 提取文本块
            chunk_content = text[start_pos:end_pos]
            
            # 处理分隔符保留
            if self.config.get('keep_separator', True):
                chunk_content = self._handle_separator_preservation(chunk_content)
            
            # 创建文本块
            if chunk_content.strip():
                chunk = self.create_chunk_info(
                    content=chunk_content.strip(),
                    start_char=start_pos,
                    end_char=end_pos,
                    chunk_index=chunk_index
                )
                chunks.append(chunk)
                chunk_index += 1
            
            # 移动到下一个位置
            if end_pos >= len(text):
                break
            
            # 计算下一个开始位置（考虑重叠）
            next_start = end_pos - chunk_overlap
            if next_start <= start_pos:
                next_start = start_pos + 1
            
            start_pos = next_start
        
        return chunks
    
    async def _split_by_tokens(
        self, 
        text: str, 
        chunk_size: int, 
        chunk_overlap: int, 
        separators: List[str]
    ) -> List[ChunkInfo]:
        """
        按token数切分文本
        
        Args:
            text: 要切分的文本
            chunk_size: 块大小（token数）
            chunk_overlap: 重叠大小（token数）
            separators: 分隔符列表
            
        Returns:
            切分后的文本块列表
        """
        # 先将文本编码为tokens
        tokens = self.tokenizer.encode(text)
        total_tokens = len(tokens)
        
        chunks = []
        start_token = 0
        chunk_index = 0
        
        while start_token < total_tokens:
            # 确定当前块的token范围
            end_token = min(start_token + chunk_size, total_tokens)
            
            # 解码当前块的tokens
            chunk_tokens = tokens[start_token:end_token]
            chunk_content = self.tokenizer.decode(chunk_tokens)
            
            # 尝试在分隔符处优化断点
            if end_token < total_tokens:
                chunk_content = self._optimize_token_chunk_boundary(
                    chunk_content, separators
                )
            
            # 创建文本块
            if chunk_content.strip():
                # 计算字符位置（近似）
                char_start = self._estimate_char_position(text, tokens, start_token)
                char_end = self._estimate_char_position(text, tokens, end_token)
                
                chunk = self.create_chunk_info(
                    content=chunk_content.strip(),
                    start_char=char_start,
                    end_char=char_end,
                    chunk_index=chunk_index,
                    semantic_info={
                        'token_count': len(chunk_tokens),
                        'start_token': start_token,
                        'end_token': end_token
                    }
                )
                chunks.append(chunk)
                chunk_index += 1
            
            # 移动到下一个位置
            if end_token >= total_tokens:
                break
            
            next_start_token = end_token - chunk_overlap
            if next_start_token <= start_token:
                next_start_token = start_token + 1
            
            start_token = next_start_token
        
        return chunks
    
    def _find_best_break_position(
        self, 
        text: str, 
        start_pos: int, 
        end_pos: int, 
        separators: List[str]
    ) -> int:
        """
        在指定范围内找到最佳断点位置
        
        Args:
            text: 文本
            start_pos: 起始位置
            end_pos: 结束位置
            separators: 分隔符列表
            
        Returns:
            最佳断点位置
        """
        # 搜索范围：从end_pos向前搜索chunk_size的1/3
        search_range = min(200, (end_pos - start_pos) // 3)
        search_start = max(start_pos, end_pos - search_range)
        
        # 按优先级搜索分隔符
        for separator in separators:
            # 在搜索范围内查找最后一个分隔符
            search_text = text[search_start:end_pos]
            last_index = search_text.rfind(separator)
            
            if last_index != -1:
                break_pos = search_start + last_index + len(separator)
                if break_pos > start_pos and break_pos < end_pos:
                    return break_pos
        
        return end_pos
    
    def _handle_separator_preservation(self, chunk_content: str) -> str:
        """
        处理分隔符保留逻辑
        
        Args:
            chunk_content: 原始块内容
            
        Returns:
            处理后的块内容
        """
        if not self.config.get('keep_separator', True):
            return chunk_content
        
        # 默认保留所有分隔符
        return chunk_content
    
    def _optimize_token_chunk_boundary(self, chunk_content: str, separators: List[str]) -> str:
        """
        优化基于token的分块边界
        
        Args:
            chunk_content: 原始块内容
            separators: 分隔符列表
            
        Returns:
            优化后的块内容
        """
        # 尝试在分隔符处截断，避免截断单词
        for separator in separators:
            last_sep_index = chunk_content.rfind(separator)
            if last_sep_index > len(chunk_content) // 2:  # 至少保留一半内容
                return chunk_content[:last_sep_index + len(separator)]
        
        return chunk_content
    
    def _estimate_char_position(self, text: str, tokens: List[int], token_index: int) -> int:
        """
        估算token位置对应的字符位置
        
        Args:
            text: 原始文本
            tokens: 所有tokens
            token_index: token索引
            
        Returns:
            估算的字符位置
        """
        if token_index <= 0:
            return 0
        if token_index >= len(tokens):
            return len(text)
        
        # 简单估算：假设字符和token的比例是固定的
        char_per_token = len(text) / len(tokens)
        return int(token_index * char_per_token)
    
    def validate_config(self) -> bool:
        """验证配置有效性"""
        required_fields = ['chunk_size', 'chunk_overlap']
        
        for field in required_fields:
            if field not in self.config:
                self.logger.error(f"Missing required config field: {field}")
                return False
        
        chunk_size = self.config.get('chunk_size', 0)
        chunk_overlap = self.config.get('chunk_overlap', 0)
        
        if chunk_size <= 0:
            self.logger.error("chunk_size must be positive")
            return False
        
        if chunk_overlap >= chunk_size:
            self.logger.error("chunk_overlap must be less than chunk_size")
            return False
        
        return True
    
    def _get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要"""
        return {
            'splitter_type': 'token_based',
            'chunk_size': self.config.get('chunk_size'),
            'chunk_overlap': self.config.get('chunk_overlap'),
            'use_token_count': self.config.get('use_token_count', False),
            'separator': self.config.get('separator'),
            'tokenizer_available': self.tokenizer is not None
        } 