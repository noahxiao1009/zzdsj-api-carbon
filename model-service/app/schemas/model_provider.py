"""
模型提供商数据模型
Model Provider Schemas
"""

from typing import Dict, List, Any, Optional, Union
from pydantic import BaseModel, Field, validator
from enum import Enum
from datetime import datetime


class ProviderType(str, Enum):
    """模型提供商类型"""
    OPENAI = "openai"
    ZHIPU = "zhipu"  # 智谱AI
    DEEPSEEK = "deepseek"  # 深度求索
    DASHSCOPE = "dashscope"  # 阿里通义千问
    BAIDU = "baidu"  # 百度文心
    MOONSHOT = "moonshot"  # 月之暗面
    MINIMAX = "minimax"  # MiniMax海螺
    ANTHROPIC = "anthropic"  # Claude
    TENCENT = "tencent"  # 腾讯混元
    IFLYTEK = "iflytek"  # 讯飞星火
    COHERE = "cohere"  # Cohere
    TOGETHER = "together"  # TogetherAI
    OLLAMA = "ollama"  # 本地Ollama
    VLLM = "vllm"  # 本地vLLM
    CUSTOM = "custom"  # 自定义


class ModelType(str, Enum):
    """模型类型"""
    CHAT = "chat"  # 对话模型
    EMBEDDING = "embedding"  # 嵌入模型
    RERANK = "rerank"  # 重排模型
    MULTIMODAL = "multimodal"  # 多模态模型
    CODE = "code"  # 代码模型
    TTS = "tts"  # 语音合成
    STT = "stt"  # 语音识别
    IMAGE = "image"  # 图像生成


class ModelCapability(str, Enum):
    """模型能力"""
    TEXT_GENERATION = "text_generation"
    TEXT_EMBEDDING = "text_embedding"  
    DOCUMENT_RANKING = "document_ranking"
    IMAGE_UNDERSTANDING = "image_understanding"
    CODE_GENERATION = "code_generation"
    FUNCTION_CALLING = "function_calling"
    TOOL_USE = "tool_use"
    STREAM_OUTPUT = "stream_output"


# 基础模型信息Schema
class ModelInfoBase(BaseModel):
    """模型信息基础模型"""
    model_id: str = Field(..., description="模型ID")
    name: str = Field(..., description="模型显示名称")
    model_type: ModelType = Field(..., description="模型类型")
    description: Optional[str] = Field(None, description="模型描述")
    capabilities: List[ModelCapability] = Field(default_factory=list, description="模型能力")
    context_length: Optional[int] = Field(None, description="上下文长度")
    max_tokens: Optional[int] = Field(None, description="最大输出Token数")
    pricing: Optional[Dict[str, float]] = Field(None, description="定价信息")
    is_default: bool = Field(False, description="是否为提供商默认模型")
    is_enabled: bool = Field(True, description="是否启用")
    config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="模型配置")


class ModelInfoCreate(ModelInfoBase):
    """创建模型信息"""
    provider_id: Optional[str] = Field(None, description="提供商ID")


class ModelInfoUpdate(BaseModel):
    """更新模型信息"""
    name: Optional[str] = Field(None, description="模型显示名称")
    description: Optional[str] = Field(None, description="模型描述")
    is_default: Optional[bool] = Field(None, description="是否为默认模型")
    is_enabled: Optional[bool] = Field(None, description="是否启用")
    config: Optional[Dict[str, Any]] = Field(None, description="模型配置")


class ModelInfo(ModelInfoBase):
    """模型信息响应模型"""
    id: str = Field(..., description="数据库ID")
    provider_id: str = Field(..., description="提供商ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    class Config:
        from_attributes = True


# 基础提供商Schema
class ModelProviderBase(BaseModel):
    """模型提供商基础模型"""
    name: str = Field(..., description="提供商名称")
    provider_type: ProviderType = Field(..., description="提供商类型")
    display_name: Optional[str] = Field(None, description="显示名称")
    description: Optional[str] = Field(None, description="提供商描述")
    api_base: Optional[str] = Field(None, description="API基础URL")
    api_version: Optional[str] = Field(None, description="API版本")
    logo: Optional[str] = Field(None, description="Logo URL")
    is_enabled: bool = Field(True, description="是否启用")
    is_default: bool = Field(False, description="是否为默认提供商")
    config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="额外配置")


class ModelProviderCreate(ModelProviderBase):
    """创建模型提供商"""
    api_key: str = Field(..., description="API密钥")
    
    @validator('name')
    def validate_name(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError('提供商名称至少需要2个字符')
        return v.strip()


class ModelProviderUpdate(BaseModel):
    """更新模型提供商"""
    name: Optional[str] = Field(None, description="提供商名称")
    display_name: Optional[str] = Field(None, description="显示名称")
    description: Optional[str] = Field(None, description="提供商描述")
    api_key: Optional[str] = Field(None, description="API密钥")
    api_base: Optional[str] = Field(None, description="API基础URL")
    api_version: Optional[str] = Field(None, description="API版本")
    is_enabled: Optional[bool] = Field(None, description="是否启用")
    is_default: Optional[bool] = Field(None, description="是否为默认提供商")
    config: Optional[Dict[str, Any]] = Field(None, description="额外配置")


class ModelProvider(ModelProviderBase):
    """模型提供商响应模型"""
    id: str = Field(..., description="提供商ID")
    api_key_masked: Optional[str] = Field(None, description="脱敏的API密钥")
    models: List[ModelInfo] = Field(default_factory=list, description="关联的模型列表")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    class Config:
        from_attributes = True


# 模型测试请求
class ModelTestRequest(BaseModel):
    """模型测试请求"""
    message: str = Field(..., description="测试消息")
    temperature: Optional[float] = Field(0.7, description="温度参数")
    max_tokens: Optional[int] = Field(100, description="最大Token数")
    stream: bool = Field(False, description="是否流式输出")


class ModelTestResponse(BaseModel):
    """模型测试响应"""
    success: bool = Field(..., description="测试是否成功")
    message: Optional[str] = Field(None, description="响应消息或错误信息")
    latency: Optional[float] = Field(None, description="响应延迟(毫秒)")
    response: Optional[str] = Field(None, description="模型回复内容")
    token_usage: Optional[Dict[str, int]] = Field(None, description="Token使用统计")


# 模型配置请求
class ModelConfigRequest(BaseModel):
    """模型配置请求"""
    name: str = Field(..., description="配置名称")
    provider_id: str = Field(..., description="提供商ID") 
    model_id: str = Field(..., description="模型ID")
    temperature: Optional[float] = Field(0.7, description="温度参数")
    max_tokens: Optional[int] = Field(None, description="最大Token数")
    top_p: Optional[float] = Field(None, description="Top-p参数")
    frequency_penalty: Optional[float] = Field(None, description="频率惩罚")
    presence_penalty: Optional[float] = Field(None, description="存在惩罚")
    system_prompt: Optional[str] = Field(None, description="系统提示词")
    config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="其他配置")


class ModelConfigResponse(BaseModel):
    """模型配置响应"""
    id: str = Field(..., description="配置ID")
    name: str = Field(..., description="配置名称")
    provider: ModelProvider = Field(..., description="提供商信息")
    model: ModelInfo = Field(..., description="模型信息")
    temperature: Optional[float] = Field(None, description="温度参数")
    max_tokens: Optional[int] = Field(None, description="最大Token数")
    top_p: Optional[float] = Field(None, description="Top-p参数")
    frequency_penalty: Optional[float] = Field(None, description="频率惩罚")
    presence_penalty: Optional[float] = Field(None, description="存在惩罚")
    system_prompt: Optional[str] = Field(None, description="系统提示词")
    config: Dict[str, Any] = Field(default_factory=dict, description="其他配置")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    class Config:
        from_attributes = True


# 模型使用统计
class ModelUsageStats(BaseModel):
    """模型使用统计"""
    model_id: str = Field(..., description="模型ID")
    provider_id: str = Field(..., description="提供商ID")
    total_requests: int = Field(0, description="总请求数")
    total_tokens: int = Field(0, description="总Token数")
    input_tokens: int = Field(0, description="输入Token数")
    output_tokens: int = Field(0, description="输出Token数")
    avg_latency: float = Field(0.0, description="平均延迟(毫秒)")
    error_rate: float = Field(0.0, description="错误率")
    date: datetime = Field(..., description="统计日期")


# 列表响应
class ModelProviderListResponse(BaseModel):
    """模型提供商列表响应"""
    providers: List[ModelProvider] = Field(..., description="提供商列表")
    total: int = Field(..., description="总数量")
    page: int = Field(1, description="当前页")
    size: int = Field(10, description="每页大小")


class ModelListResponse(BaseModel):
    """模型列表响应"""
    models: List[ModelInfo] = Field(..., description="模型列表")
    total: int = Field(..., description="总数量")
    page: int = Field(1, description="当前页")
    size: int = Field(10, description="每页大小") 