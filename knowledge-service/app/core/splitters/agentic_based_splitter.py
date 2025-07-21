"""
AgenticBasedSplitter - 基于Agno框架的智能体文档分割器
使用Agno框架提供的Agentic Chunking功能
文档: https://docs.agno.com/chunking/agentic-chunking
"""

import asyncio
from typing import List, Optional, Dict, Any
from abc import abstractmethod

from .base_splitter import BaseSplitter
from ...schemas.splitter_schemas import ChunkInfo, SplitterType
from app.config.settings import settings

# Agno imports
try:
    from agno import AgnoClient
    from agno.chunking import AgenticChunker
except ImportError:
    AgnoClient = None
    AgenticChunker = None


class AgenticBasedSplitter(BaseSplitter):
    """
    基于Agno框架的智能体驱动文档分割器
    
    使用Agno框架自带的Agentic Chunking功能，
    通过LLM智能分析文档结构和语义边界进行分割
    
    参考文档: https://docs.agno.com/chunking/agentic-chunking
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化Agno Agentic切分器
        
        Args:
            config: 切分器配置，包含:
                - chunk_size: 目标块大小
                - chunk_overlap: 块重叠大小
                - max_chunks: 最大块数量
                - model_name: 使用的模型名称
                - api_key: API密钥
                - base_url: API基础URL
        """
        super().__init__(config, SplitterType.AGENTIC)
        
        # 检查Agno是否可用
        if AgnoClient is None or AgenticChunker is None:
            raise ImportError(
                "Agno framework is not installed. "
                "Please install it with: pip install agno"
            )
        
        # 从环境配置中获取模型配置
        self.api_key = settings.embedding.openai_api_key or config.get('api_key')
        self.base_url = settings.embedding.openai_base_url or config.get('base_url')
        self.model_name = settings.embedding.default_embedding_model or config.get('model_name', 'gpt-3.5-turbo')
        
        # Agno配置
        self.chunk_size = config.get('chunk_size', 1000)
        self.chunk_overlap = config.get('chunk_overlap', 200)
        self.max_chunks = config.get('max_chunks', 100)
        
        # 初始化Agno客户端
        try:
            self.agno_client = AgnoClient(
                api_key=self.api_key,
                base_url=self.base_url
            )
            
            # 初始化Agentic切分器
            self.chunker = AgenticChunker(
                client=self.agno_client,
                model=self.model_name,
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                max_chunks=self.max_chunks
            )
            
            self.logger.info(f"Initialized Agno AgenticChunker with model: {self.model_name}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Agno client: {e}")
            # 使用fallback模式
            self.agno_client = None
            self.chunker = None
    
    async def split_text(self, text: str, document_metadata: Optional[Dict[str, Any]] = None) -> List[ChunkInfo]:
        """
        使用Agno Agentic Chunking分割文本
        
        Args:
            text: 要分割的文本
            document_metadata: 文档元数据
            
        Returns:
            分割后的文本块列表
        """
        if not text.strip():
            return []
        
        try:
            # 预处理文本
            processed_text = self.preprocess_text(text)
            
            if self.chunker is not None:
                # 使用Agno Agentic Chunking
                chunks = await self._agno_split(processed_text, document_metadata)
            else:
                # 使用fallback分割
                chunks = await self._fallback_split(processed_text, document_metadata)
                
            # 后处理
            chunks = self.postprocess_chunks(chunks)
            
            self.logger.info(f"Agentic splitter created {len(chunks)} chunks from {len(text)} characters")
            return chunks
            
        except Exception as e:
            self.logger.error(f"Agentic splitting failed: {e}")
            # 使用简单的fallback分割
            return await self._simple_fallback_split(text, document_metadata)
    
    async def _agno_split(self, text: str, document_metadata: Optional[Dict[str, Any]] = None) -> List[ChunkInfo]:
        """
        使用Agno进行智能分割
        
        Args:
            text: 要分割的文本
            document_metadata: 文档元数据
            
        Returns:
            分割后的文本块列表
        """
        try:
            # 调用Agno Agentic Chunking
            chunk_results = await self.chunker.chunk_text(
                text=text,
                metadata=document_metadata or {}
            )
            
            chunks = []
            for i, chunk_result in enumerate(chunk_results):
                # Agno返回的chunk结构
                chunk_content = chunk_result.get('content', chunk_result.get('text', ''))
                chunk_start = chunk_result.get('start_index', 0)
                chunk_end = chunk_result.get('end_index', len(chunk_content))
                
                # 创建ChunkInfo对象
                chunk_info = self.create_chunk_info(
                    content=chunk_content,
                    start_char=chunk_start,
                    end_char=chunk_end,
                    chunk_index=i,
                    metadata={
                        **(document_metadata or {}),
                        'splitter': 'agentic',
                        'model': self.model_name,
                        'chunk_method': 'agno_agentic',
                        'agno_metadata': chunk_result.get('metadata', {})
                    },
                    semantic_info={
                        'semantic_score': chunk_result.get('semantic_score', 0.0),
                        'coherence_score': chunk_result.get('coherence_score', 0.0),
                        'topic_keywords': chunk_result.get('keywords', [])
                    }
                )
                
                chunks.append(chunk_info)
            
            return chunks
            
        except Exception as e:
            self.logger.error(f"Agno agentic chunking failed: {e}")
            raise
    
    async def _fallback_split(self, text: str, document_metadata: Optional[Dict[str, Any]] = None) -> List[ChunkInfo]:
        """
        备用的语义分割策略
        
        Args:
            text: 要分割的文本
            document_metadata: 文档元数据
            
        Returns:
            分割后的文本块列表
        """
        # 基于段落的智能分割
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        if not paragraphs:
            # 如果没有明显的段落分隔，按句子分割
            sentences = []
            for sent in text.split('。'):
                sent = sent.strip()
                if sent:
                    sentences.append(sent + '。')
            paragraphs = sentences
        
        # 合并过短的段落，分割过长的段落
        chunks = []
        current_chunk = ""
        current_start = 0
        
        for para in paragraphs:
            if not para.strip():
                continue
                
            # 如果当前块加上新段落不会太长，合并
            if len(current_chunk) + len(para) <= self.chunk_size:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para
                    current_start = text.find(para)
            else:
                # 保存当前块
                if current_chunk:
                    chunk_end = current_start + len(current_chunk)
                    chunk_info = self.create_chunk_info(
                        content=current_chunk,
                        start_char=current_start,
                        end_char=chunk_end,
                        chunk_index=len(chunks),
                        metadata={
                            **(document_metadata or {}),
                            'splitter': 'agentic_fallback',
                            'chunk_method': 'paragraph_based'
                        }
                    )
                    chunks.append(chunk_info)
                
                # 开始新块
                current_chunk = para
                current_start = text.find(para, current_start)
        
        # 添加最后一个块
        if current_chunk:
            chunk_end = current_start + len(current_chunk)
            chunk_info = self.create_chunk_info(
                content=current_chunk,
                start_char=current_start,
                end_char=chunk_end,
                chunk_index=len(chunks),
                metadata={
                    **(document_metadata or {}),
                    'splitter': 'agentic_fallback',
                    'chunk_method': 'paragraph_based'
                }
            )
            chunks.append(chunk_info)
        
        return chunks
    
    async def _simple_fallback_split(self, text: str, document_metadata: Optional[Dict[str, Any]] = None) -> List[ChunkInfo]:
        """
        简单的备用分割策略
        """
        chunks = []
        chunk_size = self.chunk_size
        overlap = self.chunk_overlap
        
        start = 0
        chunk_index = 0
        
        while start < len(text):
            end = min(start + chunk_size, len(text))
            
            # 尝试在句号或换行符处断开
            if end < len(text):
                for i in range(end, max(start + chunk_size // 2, start + 100), -1):
                    if text[i] in '.。\n':
                        end = i + 1
                        break
            
            chunk_content = text[start:end].strip()
            if chunk_content:
                chunk_info = self.create_chunk_info(
                    content=chunk_content,
                    start_char=start,
                    end_char=end,
                    chunk_index=chunk_index,
                    metadata={
                        **(document_metadata or {}),
                        'splitter': 'agentic_simple_fallback',
                        'chunk_method': 'fixed_size'
                    }
                )
                chunks.append(chunk_info)
                chunk_index += 1
            
            start = max(end - overlap, start + 1)
        
        return chunks
    
    def validate_config(self) -> bool:
        """
        验证配置有效性
        
        Returns:
            配置是否有效
        """
        if not self.api_key:
            self.logger.warning("No API key provided for Agentic splitter")
            return False
            
        if self.chunk_size <= 0:
            self.logger.error("Invalid chunk_size configuration")
            return False
            
        return True
