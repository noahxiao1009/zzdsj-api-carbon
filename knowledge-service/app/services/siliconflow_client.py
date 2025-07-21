"""
硅基流动API客户端
支持嵌入模型、重排序模型和聊天模型的API调用
"""

import asyncio
import logging
import aiohttp
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel
import json

logger = logging.getLogger(__name__)


class EmbeddingRequest(BaseModel):
    """嵌入请求模型"""
    model: str
    input: Union[str, List[str]]
    encoding_format: str = "float"
    dimensions: Optional[int] = None


class RerankRequest(BaseModel):
    """重排序请求模型"""
    model: str
    query: str
    documents: List[Union[str, Dict[str, str]]]
    top_n: Optional[int] = None
    return_documents: bool = True


class ChatRequest(BaseModel):
    """聊天请求模型"""
    model: str
    messages: List[Dict[str, str]]
    stream: bool = False
    max_tokens: Optional[int] = None
    temperature: float = 0.7
    top_p: float = 1.0


class SiliconFlowClient:
    """硅基流动API客户端"""
    
    def __init__(self, api_key: str = "sk-mnennlifdngjififromhljflqsblutyfgfvwerkfhsxummcn"):
        self.api_key = api_key
        self.base_url = "https://api.siliconflow.cn/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 模型配置
        self.models = {
            "embedding": "Qwen/Qwen3-Embedding-8B",
            "rerank": "Qwen/Qwen3-Reranker-8B",
            "chat": ["Qwen/Qwen3-32B", "moonshotai/Kimi-K2-Instruct"]
        }
    
    async def create_embedding(
        self, 
        texts: Union[str, List[str]], 
        model: str = None,
        batch_size: int = 10
    ) -> List[List[float]]:
        """
        创建文本嵌入向量
        
        Args:
            texts: 文本或文本列表
            model: 嵌入模型名称
            batch_size: 批处理大小
            
        Returns:
            嵌入向量列表
        """
        if model is None:
            model = self.models["embedding"]
        
        # 统一处理为列表
        if isinstance(texts, str):
            texts = [texts]
        
        all_embeddings = []
        
        try:
            # 分批处理
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                
                request_data = EmbeddingRequest(
                    model=model,
                    input=batch,
                    encoding_format="float"
                )
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.base_url}/embeddings",
                        headers=self.headers,
                        json=request_data.dict()
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            batch_embeddings = [item["embedding"] for item in result["data"]]
                            all_embeddings.extend(batch_embeddings)
                        else:
                            error_text = await response.text()
                            logger.error(f"Embedding API error: {response.status} - {error_text}")
                            raise Exception(f"Embedding API error: {response.status}")
                
                # 添加延迟避免频率限制
                if i + batch_size < len(texts):
                    await asyncio.sleep(0.1)
            
            logger.info(f"Successfully created embeddings for {len(texts)} texts")
            return all_embeddings
            
        except Exception as e:
            logger.error(f"Failed to create embeddings: {e}")
            raise
    
    async def rerank_documents(
        self, 
        query: str, 
        documents: List[str], 
        model: str = None,
        top_n: int = None
    ) -> List[Dict[str, Any]]:
        """
        对文档进行重排序
        
        Args:
            query: 查询文本
            documents: 文档列表
            model: 重排序模型名称
            top_n: 返回的文档数量
            
        Returns:
            重排序后的文档列表，包含相关性分数
        """
        if model is None:
            model = self.models["rerank"]
        
        try:
            request_data = RerankRequest(
                model=model,
                query=query,
                documents=documents,
                top_n=top_n,
                return_documents=True
            )
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/rerank",
                    headers=self.headers,
                    json=request_data.dict()
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        # 格式化结果
                        reranked_docs = []
                        for item in result["results"]:
                            reranked_docs.append({
                                "index": item["index"],
                                "text": item.get("document", {}).get("text", documents[item["index"]]),
                                "relevance_score": item["relevance_score"]
                            })
                        
                        logger.info(f"Successfully reranked {len(reranked_docs)} documents")
                        return reranked_docs
                    else:
                        error_text = await response.text()
                        logger.error(f"Rerank API error: {response.status} - {error_text}")
                        raise Exception(f"Rerank API error: {response.status}")
        
        except Exception as e:
            logger.error(f"Failed to rerank documents: {e}")
            raise
    
    async def chat_completion(
        self, 
        messages: List[Dict[str, str]], 
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = None
    ) -> str:
        """
        聊天对话完成
        
        Args:
            messages: 对话消息列表
            model: 聊天模型名称
            temperature: 温度参数
            max_tokens: 最大token数
            
        Returns:
            AI回复内容
        """
        if model is None:
            model = self.models["chat"][0]  # 默认使用第一个聊天模型
        
        try:
            request_data = ChatRequest(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=request_data.dict()
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        content = result["choices"][0]["message"]["content"]
                        
                        logger.info(f"Successfully completed chat with model {model}")
                        return content
                    else:
                        error_text = await response.text()
                        logger.error(f"Chat API error: {response.status} - {error_text}")
                        raise Exception(f"Chat API error: {response.status}")
        
        except Exception as e:
            logger.error(f"Failed to complete chat: {e}")
            raise
    
    async def get_available_models(self) -> Dict[str, Any]:
        """
        获取可用模型列表
        
        Returns:
            可用模型信息
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/models",
                    headers=self.headers
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info("Successfully retrieved available models")
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"Models API error: {response.status} - {error_text}")
                        raise Exception(f"Models API error: {response.status}")
        
        except Exception as e:
            logger.error(f"Failed to get available models: {e}")
            raise
    
    async def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        计算两个文本的相似度
        
        Args:
            text1: 第一个文本
            text2: 第二个文本
            
        Returns:
            相似度分数（0-1）
        """
        try:
            embeddings = await self.create_embedding([text1, text2])
            
            # 计算余弦相似度
            embedding1 = embeddings[0]
            embedding2 = embeddings[1]
            
            dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
            magnitude1 = sum(a * a for a in embedding1) ** 0.5
            magnitude2 = sum(a * a for a in embedding2) ** 0.5
            
            similarity = dot_product / (magnitude1 * magnitude2) if magnitude1 * magnitude2 > 0 else 0
            
            logger.info(f"Calculated similarity: {similarity}")
            return similarity
            
        except Exception as e:
            logger.error(f"Failed to calculate similarity: {e}")
            raise


# 全局客户端实例
_siliconflow_client = None


def get_siliconflow_client() -> SiliconFlowClient:
    """获取硅基流动客户端实例"""
    global _siliconflow_client
    if _siliconflow_client is None:
        _siliconflow_client = SiliconFlowClient()
    return _siliconflow_client


# 便捷函数
async def create_embeddings(texts: Union[str, List[str]]) -> List[List[float]]:
    """创建嵌入向量的便捷函数"""
    client = get_siliconflow_client()
    return await client.create_embedding(texts)


async def rerank_documents(query: str, documents: List[str], top_n: int = None) -> List[Dict[str, Any]]:
    """重排序文档的便捷函数"""
    client = get_siliconflow_client()
    return await client.rerank_documents(query, documents, top_n=top_n)


async def chat_with_ai(messages: List[Dict[str, str]], model: str = None) -> str:
    """AI聊天的便捷函数"""
    client = get_siliconflow_client()
    return await client.chat_completion(messages, model=model)
