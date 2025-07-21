"""
统一模型调用器
提供chat、embedding、completion等接口的统一调用能力
支持多厂商模型的统一调用接口
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Union, AsyncIterator
from datetime import datetime
import json
import httpx
from enum import Enum

from ..schemas.model_provider import ModelType, ProviderType

logger = logging.getLogger(__name__)


class ModelCallType(str, Enum):
    """模型调用类型"""
    CHAT = "chat"
    COMPLETION = "completion"
    EMBEDDING = "embedding"
    RERANK = "rerank"
    MULTIMODAL = "multimodal"
    IMAGE_GENERATION = "image_generation"


class ModelInvoker:
    """统一模型调用器"""
    
    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.provider_adapters = {}
        self._initialize_adapters()
    
    def _initialize_adapters(self):
        """初始化厂商适配器"""
        self.provider_adapters = {
            ProviderType.ZHIPU: ZhipuAdapter(),
            ProviderType.BAIDU: BaiduAdapter(),
            ProviderType.IFLYTEK: IflytekAdapter(),
            ProviderType.ALIBABA: AlibabaAdapter(),
            ProviderType.TENCENT: TencentAdapter(),
            ProviderType.MOONSHOT: MoonshotAdapter(),
            ProviderType.DEEPSEEK: DeepseekAdapter(),
            ProviderType.OLLAMA: OllamaAdapter(),
            ProviderType.VLLM: VllmAdapter(),
            ProviderType.OPENAI: OpenAIAdapter(),
        }
    
    async def invoke_chat(
        self,
        provider_id: str,
        model_id: str,
        messages: List[Dict[str, str]],
        config: Dict[str, Any],
        stream: bool = False
    ) -> Union[Dict[str, Any], AsyncIterator[Dict[str, Any]]]:
        """
        统一聊天接口调用
        
        Args:
            provider_id: 提供商ID
            model_id: 模型ID
            messages: 消息列表
            config: 调用配置
            stream: 是否流式输出
            
        Returns:
            聊天响应或流式响应迭代器
        """
        try:
            adapter = self._get_adapter(provider_id)
            
            # 标准化消息格式
            normalized_messages = self._normalize_messages(messages)
            
            # 标准化配置参数
            normalized_config = self._normalize_chat_config(config)
            
            start_time = time.time()
            
            if stream:
                # 流式调用
                async for chunk in adapter.chat_stream(
                    model_id=model_id,
                    messages=normalized_messages,
                    config=normalized_config
                ):
                    yield self._standardize_chat_chunk(chunk, provider_id, model_id)
            else:
                # 非流式调用
                response = await adapter.chat_completion(
                    model_id=model_id,
                    messages=normalized_messages,
                    config=normalized_config
                )
                
                latency = (time.time() - start_time) * 1000
                
                return self._standardize_chat_response(
                    response, provider_id, model_id, latency
                )
                
        except Exception as e:
            logger.error(f"聊天调用失败 {provider_id}:{model_id}: {e}")
            raise ModelInvokeError(f"聊天调用失败: {e}", provider_id, model_id)
    
    async def invoke_embedding(
        self,
        provider_id: str,
        model_id: str,
        texts: Union[str, List[str]],
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        统一嵌入接口调用
        
        Args:
            provider_id: 提供商ID
            model_id: 模型ID
            texts: 文本或文本列表
            config: 调用配置
            
        Returns:
            嵌入响应
        """
        try:
            adapter = self._get_adapter(provider_id)
            
            # 标准化输入文本
            if isinstance(texts, str):
                texts = [texts]
            
            # 标准化配置参数
            normalized_config = self._normalize_embedding_config(config)
            
            start_time = time.time()
            
            response = await adapter.text_embedding(
                model_id=model_id,
                texts=texts,
                config=normalized_config
            )
            
            latency = (time.time() - start_time) * 1000
            
            return self._standardize_embedding_response(
                response, provider_id, model_id, latency
            )
            
        except Exception as e:
            logger.error(f"嵌入调用失败 {provider_id}:{model_id}: {e}")
            raise ModelInvokeError(f"嵌入调用失败: {e}", provider_id, model_id)
    
    async def invoke_completion(
        self,
        provider_id: str,
        model_id: str,
        prompt: str,
        config: Dict[str, Any],
        stream: bool = False
    ) -> Union[Dict[str, Any], AsyncIterator[Dict[str, Any]]]:
        """
        统一文本补全接口调用
        
        Args:
            provider_id: 提供商ID
            model_id: 模型ID
            prompt: 提示文本
            config: 调用配置
            stream: 是否流式输出
            
        Returns:
            补全响应或流式响应迭代器
        """
        try:
            adapter = self._get_adapter(provider_id)
            
            # 标准化配置参数
            normalized_config = self._normalize_completion_config(config)
            
            start_time = time.time()
            
            if stream:
                # 流式调用
                async for chunk in adapter.text_completion_stream(
                    model_id=model_id,
                    prompt=prompt,
                    config=normalized_config
                ):
                    yield self._standardize_completion_chunk(chunk, provider_id, model_id)
            else:
                # 非流式调用
                response = await adapter.text_completion(
                    model_id=model_id,
                    prompt=prompt,
                    config=normalized_config
                )
                
                latency = (time.time() - start_time) * 1000
                
                return self._standardize_completion_response(
                    response, provider_id, model_id, latency
                )
                
        except Exception as e:
            logger.error(f"补全调用失败 {provider_id}:{model_id}: {e}")
            raise ModelInvokeError(f"补全调用失败: {e}", provider_id, model_id)
    
    async def invoke_multimodal(
        self,
        provider_id: str,
        model_id: str,
        messages: List[Dict[str, Any]],
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        统一多模态接口调用
        
        Args:
            provider_id: 提供商ID
            model_id: 模型ID
            messages: 多模态消息列表（包含文本和图像）
            config: 调用配置
            
        Returns:
            多模态响应
        """
        try:
            adapter = self._get_adapter(provider_id)
            
            # 标准化多模态消息格式
            normalized_messages = self._normalize_multimodal_messages(messages)
            
            # 标准化配置参数
            normalized_config = self._normalize_multimodal_config(config)
            
            start_time = time.time()
            
            response = await adapter.multimodal_completion(
                model_id=model_id,
                messages=normalized_messages,
                config=normalized_config
            )
            
            latency = (time.time() - start_time) * 1000
            
            return self._standardize_multimodal_response(
                response, provider_id, model_id, latency
            )
            
        except Exception as e:
            logger.error(f"多模态调用失败 {provider_id}:{model_id}: {e}")
            raise ModelInvokeError(f"多模态调用失败: {e}", provider_id, model_id)
    
    async def invoke_rerank(
        self,
        provider_id: str,
        model_id: str,
        query: str,
        documents: List[str],
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        统一重排接口调用
        
        Args:
            provider_id: 提供商ID
            model_id: 模型ID
            query: 查询文本
            documents: 文档列表
            config: 调用配置
            
        Returns:
            重排响应
        """
        try:
            adapter = self._get_adapter(provider_id)
            
            # 标准化配置参数
            normalized_config = self._normalize_rerank_config(config)
            
            start_time = time.time()
            
            response = await adapter.document_rerank(
                model_id=model_id,
                query=query,
                documents=documents,
                config=normalized_config
            )
            
            latency = (time.time() - start_time) * 1000
            
            return self._standardize_rerank_response(
                response, provider_id, model_id, latency
            )
            
        except Exception as e:
            logger.error(f"重排调用失败 {provider_id}:{model_id}: {e}")
            raise ModelInvokeError(f"重排调用失败: {e}", provider_id, model_id)
    
    def _get_adapter(self, provider_id: str):
        """获取提供商适配器"""
        if provider_id not in self.provider_adapters:
            raise ValueError(f"不支持的提供商: {provider_id}")
        return self.provider_adapters[provider_id]
    
    def _normalize_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """标准化消息格式"""
        normalized = []
        for msg in messages:
            normalized.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })
        return normalized
    
    def _normalize_multimodal_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """标准化多模态消息格式"""
        normalized = []
        for msg in messages:
            normalized_msg = {
                "role": msg.get("role", "user"),
                "content": []
            }
            
            content = msg.get("content", [])
            if isinstance(content, str):
                # 纯文本消息
                normalized_msg["content"] = [{"type": "text", "text": content}]
            elif isinstance(content, list):
                # 多模态内容
                for item in content:
                    if isinstance(item, dict):
                        normalized_msg["content"].append(item)
                    else:
                        normalized_msg["content"].append({"type": "text", "text": str(item)})
            
            normalized.append(normalized_msg)
        return normalized
    
    def _normalize_chat_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """标准化聊天配置"""
        return {
            "temperature": config.get("temperature", 0.7),
            "max_tokens": config.get("max_tokens", 4000),
            "top_p": config.get("top_p", 0.9),
            "frequency_penalty": config.get("frequency_penalty", 0.0),
            "presence_penalty": config.get("presence_penalty", 0.0),
            "stop": config.get("stop", []),
            "stream": config.get("stream", False)
        }
    
    def _normalize_embedding_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """标准化嵌入配置"""
        return {
            "batch_size": config.get("batch_size", 100),
            "normalize": config.get("normalize", True),
            "truncate": config.get("truncate", True),
            "encoding_format": config.get("encoding_format", "float")
        }
    
    def _normalize_completion_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """标准化补全配置"""
        return {
            "temperature": config.get("temperature", 0.7),
            "max_tokens": config.get("max_tokens", 4000),
            "top_p": config.get("top_p", 0.9),
            "frequency_penalty": config.get("frequency_penalty", 0.0),
            "presence_penalty": config.get("presence_penalty", 0.0),
            "stop": config.get("stop", []),
            "stream": config.get("stream", False)
        }
    
    def _normalize_multimodal_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """标准化多模态配置"""
        return {
            "temperature": config.get("temperature", 0.5),
            "max_tokens": config.get("max_tokens", 2000),
            "detail": config.get("detail", "auto"),
            "quality": config.get("quality", "standard")
        }
    
    def _normalize_rerank_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """标准化重排配置"""
        return {
            "top_n": config.get("top_n", 10),
            "return_documents": config.get("return_documents", True)
        }
    
    def _standardize_chat_response(
        self, 
        response: Dict[str, Any], 
        provider_id: str, 
        model_id: str, 
        latency: float
    ) -> Dict[str, Any]:
        """标准化聊天响应格式"""
        return {
            "id": response.get("id", f"chat-{int(time.time())}"),
            "object": "chat.completion",
            "created": int(time.time()),
            "model": f"{provider_id}:{model_id}",
            "provider": provider_id,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response.get("content", response.get("text", ""))
                },
                "finish_reason": response.get("finish_reason", "stop")
            }],
            "usage": {
                "prompt_tokens": response.get("usage", {}).get("prompt_tokens", 0),
                "completion_tokens": response.get("usage", {}).get("completion_tokens", 0),
                "total_tokens": response.get("usage", {}).get("total_tokens", 0)
            },
            "latency_ms": round(latency, 2)
        }
    
    def _standardize_chat_chunk(
        self, 
        chunk: Dict[str, Any], 
        provider_id: str, 
        model_id: str
    ) -> Dict[str, Any]:
        """标准化聊天流式响应块"""
        return {
            "id": chunk.get("id", f"chatcmpl-{int(time.time())}"),
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": f"{provider_id}:{model_id}",
            "provider": provider_id,
            "choices": [{
                "index": 0,
                "delta": {
                    "content": chunk.get("content", chunk.get("text", ""))
                },
                "finish_reason": chunk.get("finish_reason")
            }]
        }
    
    def _standardize_embedding_response(
        self, 
        response: Dict[str, Any], 
        provider_id: str, 
        model_id: str, 
        latency: float
    ) -> Dict[str, Any]:
        """标准化嵌入响应格式"""
        embeddings = response.get("embeddings", response.get("data", []))
        
        # 确保嵌入数据格式统一
        formatted_embeddings = []
        for i, embedding in enumerate(embeddings):
            if isinstance(embedding, list):
                # 直接是向量列表
                formatted_embeddings.append({
                    "object": "embedding",
                    "index": i,
                    "embedding": embedding
                })
            elif isinstance(embedding, dict):
                # 已经是标准格式
                formatted_embeddings.append({
                    "object": "embedding",
                    "index": i,
                    "embedding": embedding.get("embedding", embedding.get("vector", []))
                })
        
        return {
            "object": "list",
            "model": f"{provider_id}:{model_id}",
            "provider": provider_id,
            "data": formatted_embeddings,
            "usage": {
                "prompt_tokens": response.get("usage", {}).get("prompt_tokens", 0),
                "total_tokens": response.get("usage", {}).get("total_tokens", 0)
            },
            "latency_ms": round(latency, 2)
        }
    
    def _standardize_completion_response(
        self, 
        response: Dict[str, Any], 
        provider_id: str, 
        model_id: str, 
        latency: float
    ) -> Dict[str, Any]:
        """标准化补全响应格式"""
        return {
            "id": response.get("id", f"cmpl-{int(time.time())}"),
            "object": "text_completion",
            "created": int(time.time()),
            "model": f"{provider_id}:{model_id}",
            "provider": provider_id,
            "choices": [{
                "text": response.get("text", response.get("content", "")),
                "index": 0,
                "finish_reason": response.get("finish_reason", "stop")
            }],
            "usage": {
                "prompt_tokens": response.get("usage", {}).get("prompt_tokens", 0),
                "completion_tokens": response.get("usage", {}).get("completion_tokens", 0),
                "total_tokens": response.get("usage", {}).get("total_tokens", 0)
            },
            "latency_ms": round(latency, 2)
        }
    
    def _standardize_completion_chunk(
        self, 
        chunk: Dict[str, Any], 
        provider_id: str, 
        model_id: str
    ) -> Dict[str, Any]:
        """标准化补全流式响应块"""
        return {
            "id": chunk.get("id", f"cmpl-{int(time.time())}"),
            "object": "text_completion.chunk",
            "created": int(time.time()),
            "model": f"{provider_id}:{model_id}",
            "provider": provider_id,
            "choices": [{
                "text": chunk.get("text", chunk.get("content", "")),
                "index": 0,
                "finish_reason": chunk.get("finish_reason")
            }]
        }
    
    def _standardize_multimodal_response(
        self, 
        response: Dict[str, Any], 
        provider_id: str, 
        model_id: str, 
        latency: float
    ) -> Dict[str, Any]:
        """标准化多模态响应格式"""
        return {
            "id": response.get("id", f"multimodal-{int(time.time())}"),
            "object": "multimodal.completion",
            "created": int(time.time()),
            "model": f"{provider_id}:{model_id}",
            "provider": provider_id,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response.get("content", response.get("text", ""))
                },
                "finish_reason": response.get("finish_reason", "stop")
            }],
            "usage": {
                "prompt_tokens": response.get("usage", {}).get("prompt_tokens", 0),
                "completion_tokens": response.get("usage", {}).get("completion_tokens", 0),
                "total_tokens": response.get("usage", {}).get("total_tokens", 0)
            },
            "latency_ms": round(latency, 2)
        }
    
    def _standardize_rerank_response(
        self, 
        response: Dict[str, Any], 
        provider_id: str, 
        model_id: str, 
        latency: float
    ) -> Dict[str, Any]:
        """标准化重排响应格式"""
        results = response.get("results", response.get("data", []))
        
        # 确保重排结果格式统一
        formatted_results = []
        for result in results:
            formatted_results.append({
                "index": result.get("index", 0),
                "relevance_score": result.get("relevance_score", result.get("score", 0.0)),
                "document": result.get("document", result.get("text", ""))
            })
        
        return {
            "object": "list",
            "model": f"{provider_id}:{model_id}",
            "provider": provider_id,
            "results": formatted_results,
            "usage": {
                "total_tokens": response.get("usage", {}).get("total_tokens", 0)
            },
            "latency_ms": round(latency, 2)
        }
    
    async def close(self):
        """关闭HTTP客户端"""
        await self.http_client.aclose()


class ModelInvokeError(Exception):
    """模型调用错误"""
    
    def __init__(self, message: str, provider_id: str, model_id: str):
        super().__init__(message)
        self.provider_id = provider_id
        self.model_id = model_id
        self.message = message


# ==================== 厂商适配器基类 ====================

class BaseProviderAdapter:
    """厂商适配器基类"""
    
    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=30.0)
    
    async def chat_completion(
        self, 
        model_id: str, 
        messages: List[Dict[str, str]], 
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """聊天补全"""
        raise NotImplementedError
    
    async def chat_stream(
        self, 
        model_id: str, 
        messages: List[Dict[str, str]], 
        config: Dict[str, Any]
    ) -> AsyncIterator[Dict[str, Any]]:
        """流式聊天补全"""
        raise NotImplementedError
    
    async def text_completion(
        self, 
        model_id: str, 
        prompt: str, 
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """文本补全"""
        raise NotImplementedError
    
    async def text_completion_stream(
        self, 
        model_id: str, 
        prompt: str, 
        config: Dict[str, Any]
    ) -> AsyncIterator[Dict[str, Any]]:
        """流式文本补全"""
        raise NotImplementedError
    
    async def text_embedding(
        self, 
        model_id: str, 
        texts: List[str], 
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """文本嵌入"""
        raise NotImplementedError
    
    async def multimodal_completion(
        self, 
        model_id: str, 
        messages: List[Dict[str, Any]], 
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """多模态补全"""
        raise NotImplementedError
    
    async def document_rerank(
        self, 
        model_id: str, 
        query: str, 
        documents: List[str], 
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """文档重排"""
        raise NotImplementedError


# ==================== 具体厂商适配器实现 ====================

class ZhipuAdapter(BaseProviderAdapter):
    """智谱AI适配器"""
    
    async def chat_completion(self, model_id: str, messages: List[Dict[str, str]], config: Dict[str, Any]) -> Dict[str, Any]:
        # TODO: 实现智谱AI聊天接口调用
        await asyncio.sleep(0.5)  # 模拟网络延迟
        return {
            "content": f"智谱AI {model_id} 模拟回复: {messages[-1]['content']}",
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            "finish_reason": "stop"
        }
    
    async def text_embedding(self, model_id: str, texts: List[str], config: Dict[str, Any]) -> Dict[str, Any]:
        # TODO: 实现智谱AI嵌入接口调用
        await asyncio.sleep(0.3)
        embeddings = []
        for text in texts:
            # 模拟嵌入向量（实际应该调用API）
            embedding = [0.1] * 1024  # 1024维向量
            embeddings.append(embedding)
        
        return {
            "embeddings": embeddings,
            "usage": {"prompt_tokens": sum(len(t) for t in texts), "total_tokens": sum(len(t) for t in texts)}
        }


class BaiduAdapter(BaseProviderAdapter):
    """百度文心适配器"""
    
    async def chat_completion(self, model_id: str, messages: List[Dict[str, str]], config: Dict[str, Any]) -> Dict[str, Any]:
        # TODO: 实现百度文心聊天接口调用
        await asyncio.sleep(0.6)
        return {
            "content": f"百度文心 {model_id} 模拟回复: {messages[-1]['content']}",
            "usage": {"prompt_tokens": 12, "completion_tokens": 25, "total_tokens": 37},
            "finish_reason": "stop"
        }


class IflytekAdapter(BaseProviderAdapter):
    """讯飞星火适配器"""
    
    async def chat_completion(self, model_id: str, messages: List[Dict[str, str]], config: Dict[str, Any]) -> Dict[str, Any]:
        # TODO: 实现讯飞星火聊天接口调用
        await asyncio.sleep(0.7)
        return {
            "content": f"讯飞星火 {model_id} 模拟回复: {messages[-1]['content']}",
            "usage": {"prompt_tokens": 8, "completion_tokens": 18, "total_tokens": 26},
            "finish_reason": "stop"
        }


class AlibabaAdapter(BaseProviderAdapter):
    """阿里通义适配器"""
    
    async def chat_completion(self, model_id: str, messages: List[Dict[str, str]], config: Dict[str, Any]) -> Dict[str, Any]:
        # TODO: 实现阿里通义聊天接口调用
        await asyncio.sleep(0.4)
        return {
            "content": f"阿里通义 {model_id} 模拟回复: {messages[-1]['content']}",
            "usage": {"prompt_tokens": 15, "completion_tokens": 30, "total_tokens": 45},
            "finish_reason": "stop"
        }


class TencentAdapter(BaseProviderAdapter):
    """腾讯混元适配器"""
    
    async def chat_completion(self, model_id: str, messages: List[Dict[str, str]], config: Dict[str, Any]) -> Dict[str, Any]:
        # TODO: 实现腾讯混元聊天接口调用
        await asyncio.sleep(0.5)
        return {
            "content": f"腾讯混元 {model_id} 模拟回复: {messages[-1]['content']}",
            "usage": {"prompt_tokens": 11, "completion_tokens": 22, "total_tokens": 33},
            "finish_reason": "stop"
        }


class MoonshotAdapter(BaseProviderAdapter):
    """月之暗面适配器"""
    
    async def chat_completion(self, model_id: str, messages: List[Dict[str, str]], config: Dict[str, Any]) -> Dict[str, Any]:
        # TODO: 实现月之暗面聊天接口调用
        await asyncio.sleep(0.8)
        return {
            "content": f"月之暗面 {model_id} 模拟回复: {messages[-1]['content']}",
            "usage": {"prompt_tokens": 20, "completion_tokens": 40, "total_tokens": 60},
            "finish_reason": "stop"
        }


class DeepseekAdapter(BaseProviderAdapter):
    """深度求索适配器"""
    
    async def chat_completion(self, model_id: str, messages: List[Dict[str, str]], config: Dict[str, Any]) -> Dict[str, Any]:
        # TODO: 实现深度求索聊天接口调用
        await asyncio.sleep(0.6)
        return {
            "content": f"深度求索 {model_id} 模拟回复: {messages[-1]['content']}",
            "usage": {"prompt_tokens": 9, "completion_tokens": 19, "total_tokens": 28},
            "finish_reason": "stop"
        }


class OllamaAdapter(BaseProviderAdapter):
    """Ollama本地适配器"""
    
    async def chat_completion(self, model_id: str, messages: List[Dict[str, str]], config: Dict[str, Any]) -> Dict[str, Any]:
        # TODO: 实现Ollama本地聊天接口调用
        await asyncio.sleep(1.0)  # 本地模型可能较慢
        return {
            "content": f"Ollama {model_id} 模拟回复: {messages[-1]['content']}",
            "usage": {"prompt_tokens": 13, "completion_tokens": 27, "total_tokens": 40},
            "finish_reason": "stop"
        }


class VllmAdapter(BaseProviderAdapter):
    """vLLM本地适配器"""
    
    async def chat_completion(self, model_id: str, messages: List[Dict[str, str]], config: Dict[str, Any]) -> Dict[str, Any]:
        # TODO: 实现vLLM本地聊天接口调用
        await asyncio.sleep(0.3)  # vLLM通常较快
        return {
            "content": f"vLLM {model_id} 模拟回复: {messages[-1]['content']}",
            "usage": {"prompt_tokens": 14, "completion_tokens": 28, "total_tokens": 42},
            "finish_reason": "stop"
        }


class OpenAIAdapter(BaseProviderAdapter):
    """OpenAI适配器"""
    
    async def chat_completion(self, model_id: str, messages: List[Dict[str, str]], config: Dict[str, Any]) -> Dict[str, Any]:
        # TODO: 实现OpenAI聊天接口调用
        await asyncio.sleep(0.4)
        return {
            "content": f"OpenAI {model_id} 模拟回复: {messages[-1]['content']}",
            "usage": {"prompt_tokens": 16, "completion_tokens": 32, "total_tokens": 48},
            "finish_reason": "stop"
        }