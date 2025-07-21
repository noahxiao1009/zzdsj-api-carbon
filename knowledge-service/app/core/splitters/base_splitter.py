from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import uuid
import time
import logging
from ...schemas.splitter_schemas import ChunkInfo, SplitterType

logger = logging.getLogger(__name__)


class BaseSplitter(ABC):
    """文档切分器基础抽象类"""
    
    def __init__(self, config: Dict[str, Any], splitter_type: SplitterType):
        """
        初始化切分器
        
        Args:
            config: 切分器配置
            splitter_type: 切分器类型
        """
        self.config = config
        self.splitter_type = splitter_type
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    async def split_text(self, text: str, document_metadata: Optional[Dict[str, Any]] = None) -> List[ChunkInfo]:
        """
        切分文本的抽象方法
        
        Args:
            text: 要切分的文本
            document_metadata: 文档元数据
            
        Returns:
            切分后的文本块列表
        """
        pass
    
    def create_chunk_info(
        self, 
        content: str, 
        start_char: int, 
        end_char: int, 
        chunk_index: int,
        metadata: Optional[Dict[str, Any]] = None,
        semantic_info: Optional[Dict[str, Any]] = None
    ) -> ChunkInfo:
        """
        创建文本块信息对象
        
        Args:
            content: 文本块内容
            start_char: 起始字符位置
            end_char: 结束字符位置  
            chunk_index: 块索引
            metadata: 元数据
            semantic_info: 语义信息
            
        Returns:
            文本块信息对象
        """
        return ChunkInfo(
            id=str(uuid.uuid4()),
            content=content,
            start_char=start_char,
            end_char=end_char,
            chunk_index=chunk_index,
            metadata=metadata or {},
            semantic_info=semantic_info
        )
    
    def validate_config(self) -> bool:
        """
        验证配置的有效性
        
        Returns:
            配置是否有效
        """
        return True
    
    def get_statistics(self, chunks: List[ChunkInfo]) -> Dict[str, Any]:
        """
        计算切分统计信息
        
        Args:
            chunks: 切分后的文本块列表
            
        Returns:
            统计信息字典
        """
        if not chunks:
            return {
                "total_chunks": 0,
                "avg_chunk_length": 0,
                "min_chunk_length": 0,
                "max_chunk_length": 0,
                "total_characters": 0
            }
        
        chunk_lengths = [len(chunk.content) for chunk in chunks]
        
        return {
            "total_chunks": len(chunks),
            "avg_chunk_length": sum(chunk_lengths) / len(chunk_lengths),
            "min_chunk_length": min(chunk_lengths),
            "max_chunk_length": max(chunk_lengths),
            "total_characters": sum(chunk_lengths),
            "splitter_type": self.splitter_type.value,
            "config_summary": self._get_config_summary()
        }
    
    def _get_config_summary(self) -> Dict[str, Any]:
        """
        获取配置摘要
        
        Returns:
            配置摘要字典
        """
        # 返回关键配置参数的摘要
        return {
            "splitter_type": self.splitter_type.value,
            "config_keys": list(self.config.keys())
        }
    
    async def split_with_timing(self, text: str, document_metadata: Optional[Dict[str, Any]] = None) -> tuple[List[ChunkInfo], float]:
        """
        带计时的文本切分
        
        Args:
            text: 要切分的文本
            document_metadata: 文档元数据
            
        Returns:
            (切分结果, 处理时间)
        """
        start_time = time.time()
        try:
            chunks = await self.split_text(text, document_metadata)
            processing_time = time.time() - start_time
            
            self.logger.info(
                f"{self.splitter_type.value} splitter processed {len(text)} chars "
                f"into {len(chunks)} chunks in {processing_time:.3f}s"
            )
            
            return chunks, processing_time
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"Splitting failed after {processing_time:.3f}s: {e}")
            raise
    
    def preprocess_text(self, text: str) -> str:
        """
        预处理文本（子类可以重写）
        
        Args:
            text: 原始文本
            
        Returns:
            预处理后的文本
        """
        # 默认的预处理：去除多余空白字符
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # 保留有意义的换行
            cleaned_line = line.strip()
            if cleaned_line or (cleaned_lines and cleaned_lines[-1]):
                cleaned_lines.append(cleaned_line)
        
        return '\n'.join(cleaned_lines)
    
    def postprocess_chunks(self, chunks: List[ChunkInfo]) -> List[ChunkInfo]:
        """
        后处理文本块（子类可以重写）
        
        Args:
            chunks: 原始切分块
            
        Returns:
            后处理后的切分块
        """
        # 默认的后处理：过滤空块和过短的块
        min_length = self.config.get('min_chunk_length', 10)
        
        filtered_chunks = []
        for i, chunk in enumerate(chunks):
            if chunk.content.strip() and len(chunk.content.strip()) >= min_length:
                # 重新设置索引
                chunk.chunk_index = len(filtered_chunks)
                filtered_chunks.append(chunk)
        
        return filtered_chunks 