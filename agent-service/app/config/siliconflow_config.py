"""
硅基流动(SiliconFlow)模型配置
自定义模型配置，支持聊天、嵌入和重排序功能
"""
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum


class ModelType(str, Enum):
    """模型类型"""
    CHAT = "chat"
    EMBEDDING = "embedding"
    RERANK = "rerank"


class SiliconFlowModelConfig(BaseModel):
    """硅基流动模型配置"""
    model_id: str
    model_name: str
    model_type: ModelType
    description: str
    max_tokens: int = 4096
    supports_streaming: bool = True
    supports_function_calling: bool = False
    context_window: int = 32768
    pricing: Dict[str, float] = Field(default_factory=dict)


class SiliconFlowConfig(BaseModel):
    """硅基流动配置"""
    
    # API配置
    api_key: str = "sk-jipjycienusxsfdptoweqvagdillzrumjjtcblfjfsrdhqxk"
    base_url: str = "https://api.siliconflow.cn/v1"
    
    # API端点
    chat_endpoint: str = "/chat/completions"
    embeddings_endpoint: str = "/embeddings"
    rerank_endpoint: str = "/rerank"
    
    # 请求配置
    timeout: int = 60
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # 模型配置
    available_models: List[SiliconFlowModelConfig] = [
        # 聊天模型
        SiliconFlowModelConfig(
            model_id="Qwen/Qwen3-32B",
            model_name="Qwen3-32B",
            model_type=ModelType.CHAT,
            description="通义千问3代32B参数模型，平衡性能与效果",
            max_tokens=8192,
            context_window=32768,
            supports_streaming=True,
            supports_function_calling=True,
            pricing={"input": 0.0005, "output": 0.002}
        ),
        SiliconFlowModelConfig(
            model_id="moonshotai/Kimi-K2-Instruct",
            model_name="Kimi-K2-Instruct",
            model_type=ModelType.CHAT,
            description="月之暗面Kimi K2指令模型，优秀的中文理解能力",
            max_tokens=4096,
            context_window=128000,
            supports_streaming=True,
            supports_function_calling=True,
            pricing={"input": 0.0008, "output": 0.003}
        ),
        SiliconFlowModelConfig(
            model_id="Qwen/Qwen3-235B-A22B",
            model_name="Qwen3-235B-A22B",
            model_type=ModelType.CHAT,
            description="通义千问3代235B参数A22B版本，顶级性能模型",
            max_tokens=8192,
            context_window=32768,
            supports_streaming=True,
            supports_function_calling=True,
            pricing={"input": 0.002, "output": 0.008}
        ),
        
        # 嵌入模型
        SiliconFlowModelConfig(
            model_id="Qwen/Qwen3-Embedding-8B",
            model_name="Qwen3-Embedding-8B",
            model_type=ModelType.EMBEDDING,
            description="通义千问3代8B嵌入模型，高质量向量表示",
            max_tokens=8192,
            context_window=8192,
            supports_streaming=False,
            supports_function_calling=False,
            pricing={"input": 0.0001, "output": 0.0}
        ),
        
        # 重排序模型
        SiliconFlowModelConfig(
            model_id="Qwen/Qwen3-Reranker-8B",
            model_name="Qwen3-Reranker-8B",
            model_type=ModelType.RERANK,
            description="通义千问3代8B重排序模型，优化检索结果排序",
            max_tokens=4096,
            context_window=4096,
            supports_streaming=False,
            supports_function_calling=False,
            pricing={"input": 0.0002, "output": 0.0}
        )
    ]
    
    # 默认模型配置
    default_chat_model: str = "Qwen/Qwen3-32B"
    default_embedding_model: str = "Qwen/Qwen3-Embedding-8B" 
    default_rerank_model: str = "Qwen/Qwen3-Reranker-8B"
    
    # 默认参数
    default_temperature: float = 0.7
    default_top_p: float = 0.9
    default_max_tokens: int = 4096
    
    def get_model_config(self, model_id: str) -> Optional[SiliconFlowModelConfig]:
        """获取指定模型的配置"""
        for model in self.available_models:
            if model.model_id == model_id:
                return model
        return None
    
    def get_models_by_type(self, model_type: ModelType) -> List[SiliconFlowModelConfig]:
        """根据类型获取模型列表"""
        return [model for model in self.available_models if model.model_type == model_type]
    
    def get_chat_models(self) -> List[SiliconFlowModelConfig]:
        """获取所有聊天模型"""
        return self.get_models_by_type(ModelType.CHAT)
    
    def get_embedding_models(self) -> List[SiliconFlowModelConfig]:
        """获取所有嵌入模型"""
        return self.get_models_by_type(ModelType.EMBEDDING)
    
    def get_rerank_models(self) -> List[SiliconFlowModelConfig]:
        """获取所有重排序模型"""
        return self.get_models_by_type(ModelType.RERANK)


# 全局配置实例
siliconflow_config = SiliconFlowConfig()


# 模型映射配置
SILICONFLOW_MODEL_MAPPING = {
    # Agno模型名称到硅基流动模型的映射
    "gpt-4": "Qwen/Qwen3-32B",
    "gpt-4o": "Qwen/Qwen3-32B", 
    "gpt-4o-mini": "Qwen/Qwen3-32B",
    "claude-3-5-sonnet": "moonshotai/Kimi-K2-Instruct",
    "claude-3-haiku": "Qwen/Qwen3-32B",
    "text-embedding-3-small": "Qwen/Qwen3-Embedding-8B",
    "text-embedding-3-large": "Qwen/Qwen3-Embedding-8B",
}


def get_siliconflow_model_id(agno_model_name: str) -> str:
    """将Agno模型名称转换为硅基流动模型ID"""
    return SILICONFLOW_MODEL_MAPPING.get(agno_model_name, siliconflow_config.default_chat_model)


def get_model_display_name(model_id: str) -> str:
    """获取模型的显示名称"""
    model_config = siliconflow_config.get_model_config(model_id)
    return model_config.model_name if model_config else model_id


def get_model_info(model_id: str) -> Dict[str, Any]:
    """获取模型详细信息"""
    model_config = siliconflow_config.get_model_config(model_id)
    if not model_config:
        return {"error": f"Model {model_id} not found"}
    
    return {
        "model_id": model_config.model_id,
        "model_name": model_config.model_name,
        "model_type": model_config.model_type.value,
        "description": model_config.description,
        "max_tokens": model_config.max_tokens,
        "context_window": model_config.context_window,
        "supports_streaming": model_config.supports_streaming,
        "supports_function_calling": model_config.supports_function_calling,
        "pricing": model_config.pricing
    }


# API文档信息
API_DOCS = {
    "chat_completions": "https://docs.siliconflow.cn/cn/api-reference/chat-completions/chat-completions",
    "embeddings": "https://docs.siliconflow.cn/cn/api-reference/embeddings/create-embeddings", 
    "rerank": "https://docs.siliconflow.cn/cn/api-reference/rerank/create-rerank"
} 