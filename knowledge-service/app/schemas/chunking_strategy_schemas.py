"""
切分策略相关的Pydantic模型
定义切分策略的请求和响应模式
"""

from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator


class StrategyType(str, Enum):
    """策略类型枚举"""
    SYSTEM = "system"
    CUSTOM = "custom"


class ChunkerType(str, Enum):
    """切分器类型枚举"""
    TOKEN_BASED = "token_based"
    SEMANTIC_BASED = "semantic_based"  
    PARAGRAPH_BASED = "paragraph_based"
    AGENTIC_BASED = "agentic_based"


class ChunkingCategory(str, Enum):
    """切分策略分类"""
    GENERAL = "general"
    TECHNICAL = "technical"
    ACADEMIC = "academic"
    LEGAL = "legal"
    MEDICAL = "medical"
    NEWS = "news"
    LONG_DOCUMENT = "long_document"
    CODE = "code"


# =========================
# 切分器参数配置模型
# =========================

class TokenBasedParameters(BaseModel):
    """基于Token的切分参数"""
    chunk_size: int = Field(1000, description="分块大小（Token数）", ge=100, le=8000)
    chunk_overlap: int = Field(200, description="分块重叠（Token数）", ge=0, le=1000)
    separator: Optional[str] = Field("\n\n", description="分隔符")
    preserve_structure: bool = Field(False, description="是否保留文档结构")


class SemanticBasedParameters(BaseModel):
    """基于语义的切分参数"""
    min_chunk_size: int = Field(200, description="最小分块大小", ge=50, le=1000)
    max_chunk_size: int = Field(1000, description="最大分块大小", ge=500, le=8000)
    overlap_sentences: int = Field(1, description="重叠句子数", ge=0, le=5)
    similarity_threshold: float = Field(0.8, description="语义相似度阈值", ge=0.1, le=1.0)
    use_embeddings: bool = Field(True, description="是否使用嵌入进行语义分析")


class ParagraphBasedParameters(BaseModel):
    """基于段落的切分参数"""
    min_paragraph_length: int = Field(50, description="最小段落长度", ge=10, le=500)
    max_paragraph_length: int = Field(2000, description="最大段落长度", ge=100, le=10000)
    merge_short_paragraphs: bool = Field(True, description="是否合并短段落")
    paragraph_separator: str = Field("\n\n", description="段落分隔符")


class AgenticBasedParameters(BaseModel):
    """基于AI代理的切分参数"""
    context_window: int = Field(4000, description="上下文窗口大小", ge=1000, le=16000)
    max_chunks_per_call: int = Field(10, description="每次调用最大分块数", ge=1, le=50)
    model_name: Optional[str] = Field("gpt-3.5-turbo", description="使用的模型名称")
    temperature: float = Field(0.1, description="模型温度", ge=0.0, le=1.0)
    use_structured_output: bool = Field(True, description="是否使用结构化输出")


# 参数联合类型
ChunkingParameters = Union[
    TokenBasedParameters,
    SemanticBasedParameters,
    ParagraphBasedParameters,
    AgenticBasedParameters
]


# =========================
# 请求和响应模型
# =========================

class ChunkingStrategyCreate(BaseModel):
    """创建切分策略的请求模型"""
    name: str = Field(..., description="策略名称", min_length=1, max_length=255)
    description: Optional[str] = Field(None, description="策略描述", max_length=1000)
    chunker_type: ChunkerType = Field(..., description="切分器类型")
    parameters: Dict[str, Any] = Field(..., description="策略参数")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    category: ChunkingCategory = Field(ChunkingCategory.GENERAL, description="策略分类")
    is_default: bool = Field(False, description="是否设为默认策略")

    @validator('parameters')
    def validate_parameters(cls, v, values):
        """验证参数配置"""
        chunker_type = values.get('chunker_type')
        
        if chunker_type == ChunkerType.TOKEN_BASED:
            TokenBasedParameters(**v)
        elif chunker_type == ChunkerType.SEMANTIC_BASED:
            SemanticBasedParameters(**v)
        elif chunker_type == ChunkerType.PARAGRAPH_BASED:
            ParagraphBasedParameters(**v)
        elif chunker_type == ChunkerType.AGENTIC_BASED:
            AgenticBasedParameters(**v)
        
        return v

    class Config:
        schema_extra = {
            "example": {
                "name": "长文档策略",
                "description": "适用于长文档的自定义切分策略",
                "chunker_type": "token_based",
                "parameters": {
                    "chunk_size": 1500,
                    "chunk_overlap": 300,
                    "separator": "\n\n",
                    "preserve_structure": True
                },
                "tags": ["长文档", "自定义"],
                "category": "long_document",
                "is_default": False
            }
        }


class ChunkingStrategyUpdate(BaseModel):
    """更新切分策略的请求模型"""
    name: Optional[str] = Field(None, description="策略名称", min_length=1, max_length=255)
    description: Optional[str] = Field(None, description="策略描述", max_length=1000)
    parameters: Optional[Dict[str, Any]] = Field(None, description="策略参数")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    category: Optional[ChunkingCategory] = Field(None, description="策略分类")
    is_active: Optional[bool] = Field(None, description="是否激活")
    is_default: Optional[bool] = Field(None, description="是否设为默认策略")


class ChunkingStrategyResponse(BaseModel):
    """切分策略响应模型"""
    id: str = Field(..., description="策略ID")
    name: str = Field(..., description="策略名称")
    description: Optional[str] = Field(None, description="策略描述")
    strategy_type: StrategyType = Field(..., description="策略类型")
    chunker_type: ChunkerType = Field(..., description="切分器类型")
    parameters: Dict[str, Any] = Field(..., description="策略参数")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    category: str = Field(..., description="策略分类")
    usage_count: int = Field(..., description="使用次数")
    success_rate: float = Field(..., description="成功率")
    avg_processing_time: float = Field(..., description="平均处理时间（秒）")
    is_active: bool = Field(..., description="是否激活")
    is_default: bool = Field(..., description="是否为默认策略")
    created_by: Optional[str] = Field(None, description="创建者")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True


class ChunkingStrategyList(BaseModel):
    """切分策略列表响应模型"""
    strategies: List[ChunkingStrategyResponse] = Field(..., description="策略列表")
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页大小")
    total_pages: int = Field(..., description="总页数")


class ChunkingStrategyStats(BaseModel):
    """切分策略统计信息"""
    total_strategies: int = Field(..., description="总策略数")
    active_strategies: int = Field(..., description="活跃策略数")
    system_strategies: int = Field(..., description="系统策略数")
    custom_strategies: int = Field(..., description="自定义策略数")
    chunker_type_distribution: Dict[str, int] = Field(..., description="切分器类型分布")
    category_distribution: Dict[str, int] = Field(..., description="分类分布")
    most_used_strategy: Optional[ChunkingStrategyResponse] = Field(None, description="最常用策略")
    avg_success_rate: float = Field(..., description="平均成功率")


# =========================
# 切分测试和预览模型
# =========================

class ChunkingPreviewRequest(BaseModel):
    """切分预览请求模型"""
    content: str = Field(..., description="要预览切分的内容", min_length=1)
    strategy_id: Optional[str] = Field(None, description="使用的策略ID")
    chunker_type: Optional[ChunkerType] = Field(None, description="切分器类型")
    parameters: Optional[Dict[str, Any]] = Field(None, description="自定义参数")
    max_preview_chunks: int = Field(5, description="最大预览分块数", ge=1, le=20)


class ChunkPreview(BaseModel):
    """分块预览信息"""
    index: int = Field(..., description="分块索引")
    content: str = Field(..., description="分块内容")
    start_char: int = Field(..., description="起始字符位置")
    end_char: int = Field(..., description="结束字符位置")
    token_count: int = Field(..., description="Token数量")
    char_count: int = Field(..., description="字符数量")


class ChunkingPreviewResponse(BaseModel):
    """切分预览响应模型"""
    success: bool = Field(..., description="是否成功")
    total_chunks: int = Field(..., description="总分块数")
    preview_chunks: List[ChunkPreview] = Field(..., description="预览分块列表")
    chunker_type: ChunkerType = Field(..., description="使用的切分器类型")
    parameters: Dict[str, Any] = Field(..., description="使用的参数")
    processing_time: float = Field(..., description="处理时间（秒）")
    statistics: Dict[str, Any] = Field(..., description="统计信息")
    error: Optional[str] = Field(None, description="错误信息")


class ChunkingTestRequest(BaseModel):
    """切分性能测试请求"""
    test_contents: List[str] = Field(..., description="测试内容列表", min_items=1)
    strategy_configs: List[Dict[str, Any]] = Field(..., description="测试配置列表")
    include_preview: bool = Field(False, description="是否包含预览")


class ChunkingTestResult(BaseModel):
    """单个切分测试结果"""
    content_index: int = Field(..., description="内容索引")
    config_index: int = Field(..., description="配置索引")
    success: bool = Field(..., description="是否成功")
    total_chunks: int = Field(..., description="总分块数")
    processing_time: float = Field(..., description="处理时间（秒）")
    avg_chunk_size: float = Field(..., description="平均分块大小")
    config_used: Dict[str, Any] = Field(..., description="使用的配置")
    error: Optional[str] = Field(None, description="错误信息")


class ChunkingTestResponse(BaseModel):
    """切分性能测试响应"""
    test_id: str = Field(..., description="测试ID")
    results: List[ChunkingTestResult] = Field(..., description="测试结果列表")
    summary: Dict[str, Any] = Field(..., description="测试摘要")
    best_config_index: Optional[int] = Field(None, description="最佳配置索引")
    recommendations: List[str] = Field(default_factory=list, description="优化建议")
