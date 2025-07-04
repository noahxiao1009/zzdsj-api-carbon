from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List, Union
from enum import Enum
from datetime import datetime


class SplitterType(str, Enum):
    """切分器类型枚举"""
    TOKEN_BASED = "token_based"      # 常规切分（按token大小）
    SEMANTIC_BASED = "semantic_based"  # 语义切分（NLP方式）
    PARAGRAPH_BASED = "paragraph_based"  # 按段落切分
    AGENTIC_BASED = "agentic_based"   # Agno框架Agentic切分


class TokenBasedConfig(BaseModel):
    """基于Token的切分配置"""
    chunk_size: int = Field(default=1000, ge=100, le=8000, description="分块大小（字符数或token数）")
    chunk_overlap: int = Field(default=200, ge=0, le=1000, description="分块重叠大小")
    use_token_count: bool = Field(default=False, description="是否使用token计数而非字符计数")
    separator: str = Field(default="\n\n", description="主要分隔符")
    secondary_separators: List[str] = Field(default=["\n", "。", "！", "？", ". ", "! ", "? "], description="次要分隔符列表")
    keep_separator: bool = Field(default=True, description="是否保留分隔符")
    strip_whitespace: bool = Field(default=True, description="是否去除空白字符")
    
    @validator('chunk_overlap')
    def validate_overlap(cls, v, values):
        if 'chunk_size' in values and v >= values['chunk_size']:
            raise ValueError("chunk_overlap must be less than chunk_size")
        return v


class SemanticBasedConfig(BaseModel):
    """基于语义的切分配置"""
    min_chunk_size: int = Field(default=100, ge=50, le=2000, description="最小分块大小")
    max_chunk_size: int = Field(default=2000, ge=500, le=8000, description="最大分块大小")
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="语义相似度阈值")
    sentence_split_method: str = Field(default="punctuation", description="句子分割方法")
    embedding_model: Optional[str] = Field(default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", description="语义嵌入模型")
    language: str = Field(default="zh", description="文档语言")
    merge_threshold: float = Field(default=0.8, ge=0.0, le=1.0, description="合并相似句子的阈值")
    
    @validator('max_chunk_size')
    def validate_chunk_sizes(cls, v, values):
        if 'min_chunk_size' in values and v <= values['min_chunk_size']:
            raise ValueError("max_chunk_size must be greater than min_chunk_size")
        return v


class ParagraphBasedConfig(BaseModel):
    """基于段落的切分配置"""
    paragraph_separators: List[str] = Field(default=["\n\n", "\r\n\r\n"], description="段落分隔符")
    merge_short_paragraphs: bool = Field(default=True, description="是否合并短段落")
    min_paragraph_length: int = Field(default=50, ge=10, le=500, description="最小段落长度")
    max_paragraph_length: int = Field(default=3000, ge=500, le=10000, description="最大段落长度")
    preserve_structure: bool = Field(default=True, description="是否保留文档结构")
    split_long_paragraphs: bool = Field(default=True, description="是否分割过长段落")
    structure_markers: List[str] = Field(default=["#", "##", "###", "第", "章", "节"], description="结构标记")
    
    @validator('max_paragraph_length')
    def validate_paragraph_lengths(cls, v, values):
        if 'min_paragraph_length' in values and v <= values['min_paragraph_length']:
            raise ValueError("max_paragraph_length must be greater than min_paragraph_length")
        return v


class AgenticBasedConfig(BaseModel):
    """基于Agno框架Agentic的切分配置"""
    agent_model: str = Field(default="gpt-3.5-turbo", description="Agentic切分使用的模型")
    analysis_depth: str = Field(default="medium", description="分析深度: shallow, medium, deep")
    context_window: int = Field(default=4000, ge=1000, le=16000, description="上下文窗口大小")
    coherence_score_threshold: float = Field(default=0.6, ge=0.0, le=1.0, description="连贯性分数阈值")
    topic_boundary_detection: bool = Field(default=True, description="是否启用主题边界检测")
    semantic_clustering: bool = Field(default=True, description="是否启用语义聚类")
    adaptive_chunking: bool = Field(default=True, description="是否启用自适应分块")
    instruction_template: str = Field(
        default="请分析以下文档内容，识别自然的主题边界和语义单元，将文档切分为连贯的片段。",
        description="Agentic分析指令模板"
    )
    max_chunks_per_call: int = Field(default=10, ge=1, le=50, description="每次调用最大生成分块数")


class SplitterTemplateBase(BaseModel):
    """切分模板基础模型"""
    name: str = Field(..., min_length=1, max_length=100, description="模板名称")
    description: Optional[str] = Field(None, max_length=500, description="模板描述")
    splitter_type: SplitterType = Field(..., description="切分器类型")
    is_system_template: bool = Field(default=False, description="是否为系统模板")
    is_active: bool = Field(default=True, description="是否激活")
    tags: List[str] = Field(default=[], description="模板标签")
    priority: int = Field(default=0, description="模板优先级")


class SplitterTemplateCreate(SplitterTemplateBase):
    """创建切分模板请求"""
    config: Union[TokenBasedConfig, SemanticBasedConfig, ParagraphBasedConfig, AgenticBasedConfig] = Field(
        ..., description="切分配置"
    )


class SplitterTemplateUpdate(BaseModel):
    """更新切分模板请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    config: Optional[Union[TokenBasedConfig, SemanticBasedConfig, ParagraphBasedConfig, AgenticBasedConfig]] = None
    is_active: Optional[bool] = None
    tags: Optional[List[str]] = None
    priority: Optional[int] = None


class SplitterTemplate(SplitterTemplateBase):
    """切分模板响应"""
    id: str = Field(..., description="模板ID")
    config: Dict[str, Any] = Field(..., description="切分配置")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")
    created_by: Optional[str] = Field(None, description="创建者")
    usage_count: int = Field(default=0, description="使用次数")

    class Config:
        from_attributes = True


class SplitterTemplateList(BaseModel):
    """切分模板列表响应"""
    templates: List[SplitterTemplate] = Field(..., description="模板列表")
    total: int = Field(..., description="总数量")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="页面大小")
    total_pages: int = Field(..., description="总页数")


class DocumentSplitRequest(BaseModel):
    """文档切分请求"""
    content: str = Field(..., min_length=1, description="文档内容")
    template_id: Optional[str] = Field(None, description="使用的模板ID")
    splitter_type: Optional[SplitterType] = Field(None, description="切分器类型（如果不使用模板）")
    custom_config: Optional[Union[TokenBasedConfig, SemanticBasedConfig, ParagraphBasedConfig, AgenticBasedConfig]] = Field(
        None, description="自定义配置（如果不使用模板）"
    )
    document_metadata: Dict[str, Any] = Field(default={}, description="文档元数据")


class ChunkInfo(BaseModel):
    """分块信息"""
    id: str = Field(..., description="分块ID")
    content: str = Field(..., description="分块内容")
    start_char: int = Field(..., description="起始字符位置")
    end_char: int = Field(..., description="结束字符位置")
    chunk_index: int = Field(..., description="分块索引")
    metadata: Dict[str, Any] = Field(default={}, description="分块元数据")
    semantic_info: Optional[Dict[str, Any]] = Field(None, description="语义信息")


class DocumentSplitResponse(BaseModel):
    """文档切分响应"""
    success: bool = Field(..., description="是否成功")
    chunks: List[ChunkInfo] = Field(default=[], description="分块列表")
    total_chunks: int = Field(..., description="总分块数")
    template_used: Optional[str] = Field(None, description="使用的模板ID")
    splitter_type: SplitterType = Field(..., description="使用的切分器类型")
    processing_time: float = Field(..., description="处理时间（秒）")
    statistics: Dict[str, Any] = Field(default={}, description="切分统计信息")
    error: Optional[str] = Field(None, description="错误信息")


class TemplateUsageStats(BaseModel):
    """模板使用统计"""
    template_id: str = Field(..., description="模板ID")
    template_name: str = Field(..., description="模板名称")
    splitter_type: SplitterType = Field(..., description="切分器类型")
    usage_count: int = Field(..., description="使用次数")
    last_used: Optional[datetime] = Field(None, description="最后使用时间")
    average_chunks_per_document: float = Field(..., description="平均每文档分块数")
    success_rate: float = Field(..., description="成功率")


class SystemTemplatesResponse(BaseModel):
    """系统模板响应"""
    token_based_templates: List[SplitterTemplate] = Field(..., description="Token切分模板")
    semantic_based_templates: List[SplitterTemplate] = Field(..., description="语义切分模板") 
    paragraph_based_templates: List[SplitterTemplate] = Field(..., description="段落切分模板")
    agentic_based_templates: List[SplitterTemplate] = Field(..., description="Agentic切分模板")
    total_templates: int = Field(..., description="总模板数") 