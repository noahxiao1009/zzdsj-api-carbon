import time
import logging
from typing import Dict, Any, Optional, List
from dataclasses import asdict

from ..schemas.splitter_schemas import (
    SplitterType, DocumentSplitRequest, DocumentSplitResponse, 
    ChunkInfo, TokenBasedConfig, SemanticBasedConfig,
    ParagraphBasedConfig, AgenticBasedConfig
)
from .template_manager import get_template_manager, SplitterTemplateManager
from .splitters.token_based_splitter import TokenBasedSplitter
from .splitters.semantic_based_splitter import SemanticBasedSplitter

logger = logging.getLogger(__name__)


class DocumentSplitter:
    """统一的文档切分器"""
    
    def __init__(self):
        """初始化文档切分器"""
        self.template_manager = get_template_manager()
        self.split_count = 0
        self.total_processing_time = 0.0
        self.success_count = 0
        self.error_count = 0
        
        logger.info("DocumentSplitter initialized")
    
    async def split_document(self, request: DocumentSplitRequest) -> DocumentSplitResponse:
        """
        切分文档
        
        Args:
            request: 文档切分请求
            
        Returns:
            切分结果
        """
        start_time = time.time()
        
        try:
            # 获取切分配置
            splitter_type, config, template_used = await self._get_splitter_config(request)
            
            # 创建切分器
            splitter = await self._create_splitter(splitter_type, config)
            
            # 执行切分
            chunks, processing_time = await splitter.split_with_timing(
                request.content, 
                request.document_metadata
            )
            
            # 计算统计信息
            statistics = splitter.get_statistics(chunks)
            
            # 更新计数器
            self.split_count += 1
            self.success_count += 1
            self.total_processing_time += processing_time
            
            logger.info(
                f"Document split successful: {len(chunks)} chunks, "
                f"{processing_time:.3f}s, type: {splitter_type.value}"
            )
            
            return DocumentSplitResponse(
                success=True,
                chunks=chunks,
                total_chunks=len(chunks),
                template_used=template_used,
                splitter_type=splitter_type,
                processing_time=processing_time,
                statistics=statistics
            )
            
        except Exception as e:
            self.error_count += 1
            processing_time = time.time() - start_time
            
            logger.error(f"Document split failed: {e}")
            
            return DocumentSplitResponse(
                success=False,
                chunks=[],
                total_chunks=0,
                template_used=request.template_id,
                splitter_type=request.splitter_type or SplitterType.TOKEN_BASED,
                processing_time=processing_time,
                statistics={},
                error=str(e)
            )
    
    async def _get_splitter_config(self, request: DocumentSplitRequest) -> tuple[SplitterType, Dict[str, Any], Optional[str]]:
        """
        获取切分器配置
        
        Args:
            request: 切分请求
            
        Returns:
            (切分器类型, 配置字典, 使用的模板ID)
        """
        # 方式1: 使用预定义模板
        if request.template_id:
            template = await self.template_manager.get_template(request.template_id)
            if not template:
                raise ValueError(f"Template not found: {request.template_id}")
            
            if not template.is_active:
                raise ValueError(f"Template is inactive: {request.template_id}")
            
            return template.splitter_type, template.config, request.template_id
        
        # 方式2: 使用自定义配置
        if request.custom_config:
            if not request.splitter_type:
                raise ValueError("splitter_type is required when using custom_config")
            
            config = request.custom_config.dict()
            return request.splitter_type, config, None
        
        # 方式3: 使用默认配置
        if request.splitter_type:
            config = self._get_default_config(request.splitter_type)
            return request.splitter_type, config, None
        
        raise ValueError("Must specify template_id, custom_config, or splitter_type")
    
    def _get_default_config(self, splitter_type: SplitterType) -> Dict[str, Any]:
        """
        获取默认配置
        
        Args:
            splitter_type: 切分器类型
            
        Returns:
            默认配置字典
        """
        if splitter_type == SplitterType.TOKEN_BASED:
            return TokenBasedConfig().dict()
        elif splitter_type == SplitterType.SEMANTIC_BASED:
            return SemanticBasedConfig().dict()
        elif splitter_type == SplitterType.PARAGRAPH_BASED:
            return ParagraphBasedConfig().dict()
        elif splitter_type == SplitterType.AGENTIC_BASED:
            return AgenticBasedConfig().dict()
        else:
            raise ValueError(f"Unsupported splitter type: {splitter_type}")
    
    async def _create_splitter(self, splitter_type: SplitterType, config: Dict[str, Any]):
        """
        创建切分器实例
        
        Args:
            splitter_type: 切分器类型
            config: 配置字典
            
        Returns:
            切分器实例
        """
        if splitter_type == SplitterType.TOKEN_BASED:
            return TokenBasedSplitter(config)
        elif splitter_type == SplitterType.SEMANTIC_BASED:
            # 使用真实的语义切分器
            return SemanticBasedSplitter(config)
        elif splitter_type == SplitterType.PARAGRAPH_BASED:
            return MockParagraphSplitter(config)
        elif splitter_type == SplitterType.AGENTIC_BASED:
            return MockAgenticSplitter(config)
        else:
            raise ValueError(f"Unsupported splitter type: {splitter_type}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取文档切分器统计信息
        
        Returns:
            统计信息字典
        """
        avg_processing_time = (
            self.total_processing_time / self.split_count 
            if self.split_count > 0 else 0
        )
        
        success_rate = (
            self.success_count / self.split_count 
            if self.split_count > 0 else 0
        )
        
        return {
            "total_splits": self.split_count,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "success_rate": success_rate,
            "avg_processing_time": avg_processing_time,
            "total_processing_time": self.total_processing_time
        }


# 模拟切分器实现（用于测试，实际部署时替换为真实实现）

class MockSemanticSplitter:
    """模拟语义切分器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.splitter_type = SplitterType.SEMANTIC_BASED
        self.logger = logging.getLogger(f"{__name__}.MockSemanticSplitter")
    
    async def split_with_timing(self, text: str, document_metadata: Optional[Dict[str, Any]] = None):
        """模拟语义切分"""
        import time
        import uuid
        
        start_time = time.time()
        
        # 简单的语义切分模拟：按句子分组
        sentences = text.replace('。', '。\n').replace('！', '！\n').replace('？', '？\n').split('\n')
        sentences = [s.strip() for s in sentences if s.strip()]
        
        chunks = []
        current_chunk = ""
        chunk_index = 0
        start_char = 0
        
        min_size = self.config.get('min_chunk_size', 200)
        max_size = self.config.get('max_chunk_size', 1500)
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) > max_size and current_chunk:
                # 创建当前块
                chunk = ChunkInfo(
                    id=str(uuid.uuid4()),
                    content=current_chunk.strip(),
                    start_char=start_char,
                    end_char=start_char + len(current_chunk),
                    chunk_index=chunk_index,
                    metadata={
                        'splitter_type': 'semantic_based',
                        'semantic_coherence_score': 0.8,
                        **(document_metadata or {})
                    },
                    semantic_info={'sentence_count': current_chunk.count('。') + current_chunk.count('！') + current_chunk.count('？')}
                )
                chunks.append(chunk)
                chunk_index += 1
                start_char += len(current_chunk)
                current_chunk = sentence
            else:
                current_chunk += (" " if current_chunk else "") + sentence
        
        # 处理最后一块
        if current_chunk and len(current_chunk) >= min_size:
            chunk = ChunkInfo(
                id=str(uuid.uuid4()),
                content=current_chunk.strip(),
                start_char=start_char,
                end_char=start_char + len(current_chunk),
                chunk_index=chunk_index,
                metadata={
                    'splitter_type': 'semantic_based',
                    'semantic_coherence_score': 0.8,
                    **(document_metadata or {})
                },
                semantic_info={'sentence_count': current_chunk.count('。') + current_chunk.count('！') + current_chunk.count('？')}
            )
            chunks.append(chunk)
        
        processing_time = time.time() - start_time
        return chunks, processing_time
    
    def get_statistics(self, chunks: List[ChunkInfo]) -> Dict[str, Any]:
        """获取统计信息"""
        if not chunks:
            return {"total_chunks": 0, "avg_chunk_length": 0}
        
        chunk_lengths = [len(chunk.content) for chunk in chunks]
        return {
            "total_chunks": len(chunks),
            "avg_chunk_length": sum(chunk_lengths) / len(chunk_lengths),
            "min_chunk_length": min(chunk_lengths),
            "max_chunk_length": max(chunk_lengths),
            "splitter_type": "semantic_based",
            "total_characters": sum(chunk_lengths)
        }


class MockParagraphSplitter:
    """模拟段落切分器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.splitter_type = SplitterType.PARAGRAPH_BASED
        self.logger = logging.getLogger(f"{__name__}.MockParagraphSplitter")
    
    async def split_with_timing(self, text: str, document_metadata: Optional[Dict[str, Any]] = None):
        """模拟段落切分"""
        import time
        import uuid
        
        start_time = time.time()
        
        # 按段落分隔符分割
        separators = self.config.get('paragraph_separators', ['\n\n', '\r\n\r\n'])
        paragraphs = text.split(separators[0])
        
        chunks = []
        chunk_index = 0
        start_char = 0
        
        min_length = self.config.get('min_paragraph_length', 50)
        max_length = self.config.get('max_paragraph_length', 2000)
        
        current_chunk = ""
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            if len(current_chunk) + len(paragraph) > max_length and current_chunk:
                # 创建当前块
                chunk = ChunkInfo(
                    id=str(uuid.uuid4()),
                    content=current_chunk.strip(),
                    start_char=start_char,
                    end_char=start_char + len(current_chunk),
                    chunk_index=chunk_index,
                    metadata={
                        'splitter_type': 'paragraph_based',
                        'paragraph_count': current_chunk.count('\n\n') + 1,
                        **(document_metadata or {})
                    }
                )
                chunks.append(chunk)
                chunk_index += 1
                start_char += len(current_chunk) + len(separators[0])
                current_chunk = paragraph
            else:
                current_chunk += (separators[0] if current_chunk else "") + paragraph
        
        # 处理最后一块
        if current_chunk and len(current_chunk) >= min_length:
            chunk = ChunkInfo(
                id=str(uuid.uuid4()),
                content=current_chunk.strip(),
                start_char=start_char,
                end_char=start_char + len(current_chunk),
                chunk_index=chunk_index,
                metadata={
                    'splitter_type': 'paragraph_based',
                    'paragraph_count': current_chunk.count('\n\n') + 1,
                    **(document_metadata or {})
                }
            )
            chunks.append(chunk)
        
        processing_time = time.time() - start_time
        return chunks, processing_time
    
    def get_statistics(self, chunks: List[ChunkInfo]) -> Dict[str, Any]:
        """获取统计信息"""
        if not chunks:
            return {"total_chunks": 0, "avg_chunk_length": 0}
        
        chunk_lengths = [len(chunk.content) for chunk in chunks]
        return {
            "total_chunks": len(chunks),
            "avg_chunk_length": sum(chunk_lengths) / len(chunk_lengths),
            "min_chunk_length": min(chunk_lengths),
            "max_chunk_length": max(chunk_lengths),
            "splitter_type": "paragraph_based",
            "total_characters": sum(chunk_lengths)
        }


class MockAgenticSplitter:
    """模拟Agentic切分器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.splitter_type = SplitterType.AGENTIC_BASED
        self.logger = logging.getLogger(f"{__name__}.MockAgenticSplitter")
    
    async def split_with_timing(self, text: str, document_metadata: Optional[Dict[str, Any]] = None):
        """模拟Agentic切分"""
        import time
        import uuid
        import random
        
        start_time = time.time()
        
        # 模拟AI代理分析文档结构
        context_window = self.config.get('context_window', 4000)
        max_chunks = self.config.get('max_chunks_per_call', 10)
        
        # 简单的主题边界检测模拟
        topic_markers = ['第', '章', '节', '#', '##', '一、', '二、', '三、', '四、', '五、']
        
        chunks = []
        chunk_index = 0
        start_pos = 0
        
        # 寻找主题边界
        boundaries = [0]
        for i, char in enumerate(text):
            if i > 0 and any(text[i:i+len(marker)] == marker for marker in topic_markers):
                if i - boundaries[-1] > 200:  # 最小块大小
                    boundaries.append(i)
        
        boundaries.append(len(text))
        
        # 创建基于主题边界的分块
        for i in range(len(boundaries) - 1):
            chunk_start = boundaries[i]
            chunk_end = boundaries[i + 1]
            chunk_content = text[chunk_start:chunk_end].strip()
            
            if chunk_content and len(chunk_content) > 50:
                # 模拟AI分析的连贯性分数
                coherence_score = random.uniform(0.6, 0.9)
                
                chunk = ChunkInfo(
                    id=str(uuid.uuid4()),
                    content=chunk_content,
                    start_char=chunk_start,
                    end_char=chunk_end,
                    chunk_index=chunk_index,
                    metadata={
                        'splitter_type': 'agentic_based',
                        'ai_model': self.config.get('agent_model', 'gpt-3.5-turbo'),
                        'analysis_depth': self.config.get('analysis_depth', 'medium'),
                        **(document_metadata or {})
                    },
                    semantic_info={
                        'coherence_score': coherence_score,
                        'topic_boundary_detected': True,
                        'semantic_cluster_id': f"cluster_{chunk_index // 3}"
                    }
                )
                chunks.append(chunk)
                chunk_index += 1
        
        # 如果没有找到足够的边界，回退到固定长度切分
        if len(chunks) == 0:
            chunk_size = min(context_window, 2000)
            for i in range(0, len(text), chunk_size):
                chunk_content = text[i:i+chunk_size].strip()
                if chunk_content:
                    chunk = ChunkInfo(
                        id=str(uuid.uuid4()),
                        content=chunk_content,
                        start_char=i,
                        end_char=min(i+chunk_size, len(text)),
                        chunk_index=len(chunks),
                        metadata={
                            'splitter_type': 'agentic_based',
                            'fallback_mode': True,
                            **(document_metadata or {})
                        },
                        semantic_info={'coherence_score': 0.7}
                    )
                    chunks.append(chunk)
        
        processing_time = time.time() - start_time
        return chunks, processing_time
    
    def get_statistics(self, chunks: List[ChunkInfo]) -> Dict[str, Any]:
        """获取统计信息"""
        if not chunks:
            return {"total_chunks": 0, "avg_chunk_length": 0}
        
        chunk_lengths = [len(chunk.content) for chunk in chunks]
        coherence_scores = [
            chunk.semantic_info.get('coherence_score', 0.7) 
            for chunk in chunks if chunk.semantic_info
        ]
        
        return {
            "total_chunks": len(chunks),
            "avg_chunk_length": sum(chunk_lengths) / len(chunk_lengths),
            "min_chunk_length": min(chunk_lengths),
            "max_chunk_length": max(chunk_lengths),
            "splitter_type": "agentic_based",
            "avg_coherence_score": sum(coherence_scores) / len(coherence_scores) if coherence_scores else 0,
            "total_characters": sum(chunk_lengths)
        }


# 全局文档切分器实例
_document_splitter = None

def get_document_splitter() -> DocumentSplitter:
    """获取文档切分器实例"""
    global _document_splitter
    if _document_splitter is None:
        _document_splitter = DocumentSplitter()
    return _document_splitter 