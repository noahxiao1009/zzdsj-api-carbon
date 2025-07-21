"""
增强的聊天数据模型 - 支持消息渲染和格式化
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from enum import Enum

class MessageType(str, Enum):
    """消息类型枚举"""
    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"
    FILE = "file"
    SYSTEM = "system"

class RenderFormat(str, Enum):
    """渲染格式枚举"""
    MARKDOWN = "markdown"
    CODE = "code"
    LATEX = "latex"
    TABLE = "table"
    HTML = "html"

class ComplexityLevel(str, Enum):
    """复杂度级别枚举"""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"

class VoiceConfig(BaseModel):
    """语音配置"""
    enable_stt: bool = Field(False, description="是否启用语音转文字")
    enable_tts: bool = Field(False, description="是否启用文字转语音")
    voice_model: str = Field("default", description="语音模型")
    language: str = Field("zh-CN", description="语言代码")
    audio_format: str = Field("wav", description="音频格式")
    sample_rate: int = Field(16000, description="采样率")

class RenderConfig(BaseModel):
    """渲染配置"""
    enable_markdown: bool = Field(True, description="启用Markdown渲染")
    enable_code_highlight: bool = Field(True, description="启用代码高亮")
    enable_latex: bool = Field(True, description="启用LaTeX渲染")
    enable_table: bool = Field(True, description="启用表格渲染")
    enable_html: bool = Field(True, description="启用HTML渲染")
    enable_cache: bool = Field(True, description="启用渲染缓存")
    max_render_size: int = Field(100000, description="最大渲染内容大小")
    render_timeout: int = Field(30, description="渲染超时时间(秒)")

class EnhancedChatRequest(BaseModel):
    """增强的聊天请求"""
    message: str = Field(..., description="用户消息内容")
    session_id: Optional[str] = Field(None, description="会话ID")
    agent_id: Optional[str] = Field(None, description="智能体ID")
    stream: bool = Field(False, description="是否流式响应")
    message_type: MessageType = Field(MessageType.TEXT, description="消息类型")
    
    # 渲染相关配置
    enable_rendering: bool = Field(True, description="是否启用消息渲染")
    analyze_format: bool = Field(True, description="是否分析格式")
    render_config: Optional[RenderConfig] = Field(None, description="渲染配置")
    
    # 语音配置
    voice_config: Optional[VoiceConfig] = Field(None, description="语音配置")
    
    # 会话配置
    session_config: Optional[Dict[str, Any]] = Field(None, description="会话配置")
    
    # 上下文配置
    context: Optional[Dict[str, Any]] = Field(None, description="额外上下文")
    
    # 用户偏好
    user_preferences: Optional[Dict[str, Any]] = Field(None, description="用户偏好设置")

class FormatAnalysis(BaseModel):
    """格式分析结果"""
    has_markdown: bool = Field(False, description="是否包含Markdown")
    has_latex: bool = Field(False, description="是否包含LaTeX公式")
    has_code: bool = Field(False, description="是否包含代码")
    has_table: bool = Field(False, description="是否包含表格")
    has_html: bool = Field(False, description="是否包含HTML")
    
    detected_formats: List[RenderFormat] = Field(default_factory=list, description="检测到的格式")
    code_language: Optional[str] = Field(None, description="代码语言")
    complexity_level: ComplexityLevel = Field(ComplexityLevel.SIMPLE, description="内容复杂度")
    
    # 详细分析
    code_blocks: List[Dict[str, Any]] = Field(default_factory=list, description="代码块详情")
    latex_formulas: List[Dict[str, Any]] = Field(default_factory=list, description="LaTeX公式详情")
    tables: List[Dict[str, Any]] = Field(default_factory=list, description="表格详情")
    
    # 统计信息
    statistics: Dict[str, Any] = Field(default_factory=dict, description="内容统计")

class RenderedPart(BaseModel):
    """渲染部分"""
    format: RenderFormat = Field(..., description="渲染格式")
    success: bool = Field(..., description="渲染是否成功")
    rendered: Optional[str] = Field(None, description="渲染后内容")
    raw: Optional[str] = Field(None, description="原始内容")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    error: Optional[str] = Field(None, description="错误信息")

class RenderedContent(BaseModel):
    """渲染后的内容"""
    success: bool = Field(..., description="整体渲染是否成功")
    original: str = Field(..., description="原始内容")
    rendered_parts: List[RenderedPart] = Field(default_factory=list, description="渲染部分列表")
    formats_detected: List[RenderFormat] = Field(default_factory=list, description="检测到的格式")
    render_time: float = Field(..., description="渲染耗时(毫秒)")
    analysis: Optional[FormatAnalysis] = Field(None, description="格式分析结果")
    timestamp: str = Field(..., description="渲染时间戳")

class AudioResponse(BaseModel):
    """音频响应"""
    format: str = Field(..., description="音频格式")
    data: str = Field(..., description="音频数据(Base64)")
    duration: Optional[float] = Field(None, description="音频时长(秒)")
    sample_rate: int = Field(16000, description="采样率")
    size: Optional[int] = Field(None, description="文件大小(字节)")

class EnhancedChatResponse(BaseModel):
    """增强的聊天响应"""
    success: bool = Field(..., description="请求是否成功")
    session_id: str = Field(..., description="会话ID")
    message_id: Optional[str] = Field(None, description="消息ID")
    
    # 响应内容
    response: str = Field(..., description="AI响应内容")
    rendered_content: Optional[RenderedContent] = Field(None, description="渲染后内容")
    format_analysis: Optional[FormatAnalysis] = Field(None, description="格式分析")
    
    # 音频响应
    audio_response: Optional[AudioResponse] = Field(None, description="语音响应")
    
    # 元数据
    timestamp: str = Field(..., description="响应时间戳")
    agent_id: Optional[str] = Field(None, description="智能体ID")
    processing_time: float = Field(0, description="处理耗时(毫秒)")
    
    # 上下文信息
    context: Optional[Dict[str, Any]] = Field(None, description="响应上下文")
    
    # 错误信息
    error: Optional[str] = Field(None, description="错误信息")
    error_code: Optional[str] = Field(None, description="错误代码")

class StreamEvent(BaseModel):
    """流式事件"""
    type: str = Field(..., description="事件类型")
    session_id: str = Field(..., description="会话ID")
    timestamp: str = Field(..., description="事件时间戳")
    data: Dict[str, Any] = Field(default_factory=dict, description="事件数据")

class SessionStartEvent(StreamEvent):
    """会话开始事件"""
    type: str = Field("session_start", description="事件类型")
    agent_id: Optional[str] = Field(None, description="智能体ID")

class ContentChunkEvent(StreamEvent):
    """内容块事件"""
    type: str = Field("content_chunk", description="事件类型")
    chunk: str = Field(..., description="内容块")
    accumulated: str = Field(..., description="累积内容")
    finished: bool = Field(False, description="是否完成")
    format_analysis: Optional[FormatAnalysis] = Field(None, description="实时格式分析")

class ContentRenderedEvent(StreamEvent):
    """内容渲染事件"""
    type: str = Field("content_rendered", description="事件类型")
    rendered_content: RenderedContent = Field(..., description="渲染后内容")

class AudioResponseEvent(StreamEvent):
    """音频响应事件"""
    type: str = Field("audio_response", description="事件类型")
    audio_data: AudioResponse = Field(..., description="音频数据")

class ErrorEvent(StreamEvent):
    """错误事件"""
    type: str = Field("error", description="事件类型")
    error: str = Field(..., description="错误信息")
    error_code: Optional[str] = Field(None, description="错误代码")

class SessionCompleteEvent(StreamEvent):
    """会话完成事件"""
    type: str = Field("session_complete", description="事件类型")
    total_content: str = Field(..., description="完整内容")
    final_analysis: Optional[FormatAnalysis] = Field(None, description="最终分析")
    performance_metrics: Dict[str, Any] = Field(default_factory=dict, description="性能指标")

class RenderCapabilities(BaseModel):
    """渲染能力信息"""
    markdown: Dict[str, Any] = Field(default_factory=dict, description="Markdown渲染能力")
    code: Dict[str, Any] = Field(default_factory=dict, description="代码渲染能力")
    latex: Dict[str, Any] = Field(default_factory=dict, description="LaTeX渲染能力")
    tables: Dict[str, Any] = Field(default_factory=dict, description="表格渲染能力")
    html: Dict[str, Any] = Field(default_factory=dict, description="HTML渲染能力")

class BatchRenderRequest(BaseModel):
    """批量渲染请求"""
    contents: List[str] = Field(..., description="要渲染的内容列表")
    render_config: Optional[RenderConfig] = Field(None, description="渲染配置")
    enable_parallel: bool = Field(True, description="是否并行渲染")
    max_concurrent: int = Field(5, description="最大并发数")

class BatchRenderResponse(BaseModel):
    """批量渲染响应"""
    success: bool = Field(..., description="整体是否成功")
    results: List[RenderedContent] = Field(..., description="渲染结果列表")
    total_time: float = Field(..., description="总耗时(毫秒)")
    success_count: int = Field(..., description="成功数量")
    error_count: int = Field(..., description="错误数量")
    errors: List[str] = Field(default_factory=list, description="错误信息列表")

class RenderMetrics(BaseModel):
    """渲染性能指标"""
    total_requests: int = Field(0, description="总请求数")
    successful_renders: int = Field(0, description="成功渲染数")
    failed_renders: int = Field(0, description="失败渲染数")
    average_render_time: float = Field(0, description="平均渲染时间(毫秒)")
    cache_hit_rate: float = Field(0, description="缓存命中率")
    format_distribution: Dict[str, int] = Field(default_factory=dict, description="格式分布")
    
    # 性能统计
    render_times: Dict[str, float] = Field(default_factory=dict, description="各格式渲染时间")
    error_distribution: Dict[str, int] = Field(default_factory=dict, description="错误分布")
    
    # 时间统计
    last_updated: str = Field(..., description="最后更新时间")
    collection_period: str = Field("1h", description="统计周期")