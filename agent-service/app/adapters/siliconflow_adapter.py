"""
硅基流动(SiliconFlow) API适配器
实现与硅基流动API的集成，支持聊天、嵌入和重排序功能
"""
import asyncio
import aiohttp
import json
import logging
from typing import Dict, List, Any, Optional, AsyncGenerator, Union
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..config.siliconflow_config import (
    siliconflow_config, 
    ModelType,
    get_siliconflow_model_id,
    get_model_info
)

logger = logging.getLogger(__name__)


@dataclass
class SiliconFlowMessage:
    """消息结构"""
    role: str  # system, user, assistant
    content: str
    name: Optional[str] = None


@dataclass
class SiliconFlowChatRequest:
    """聊天请求结构"""
    model: str
    messages: List[SiliconFlowMessage]
    temperature: float = 0.7
    top_p: float = 0.9
    max_tokens: Optional[int] = None
    stream: bool = False
    stop: Optional[List[str]] = None
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0


@dataclass
class SiliconFlowChatResponse:
    """聊天响应结构"""
    id: str
    model: str
    content: str
    finish_reason: str
    usage: Dict[str, int]
    created: int = field(default_factory=lambda: int(datetime.now().timestamp()))


@dataclass
class SiliconFlowEmbeddingRequest:
    """嵌入请求结构"""
    model: str
    input: Union[str, List[str]]
    encoding_format: str = "float"


@dataclass
class SiliconFlowEmbeddingResponse:
    """嵌入响应结构"""
    model: str
    data: List[Dict[str, Any]]
    usage: Dict[str, int]


@dataclass
class SiliconFlowRerankRequest:
    """重排序请求结构"""
    model: str
    query: str
    documents: List[str]
    top_n: Optional[int] = None
    return_documents: bool = True


@dataclass
class SiliconFlowRerankResponse:
    """重排序响应结构"""
    model: str
    results: List[Dict[str, Any]]
    usage: Dict[str, int]


class SiliconFlowClient:
    """硅基流动客户端"""
    
    def __init__(self):
        self.config = siliconflow_config
        self.session: Optional[aiohttp.ClientSession] = None
        self._headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "ZZDSJ-Carbon-Agent-Service/1.0"
        }
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers=self._headers
            )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def _make_request(self, endpoint: str, data: Dict[str, Any], 
                          stream: bool = False) -> Union[Dict[str, Any], AsyncGenerator]:
        """发起HTTP请求"""
        url = f"{self.config.base_url}{endpoint}"
        
        for attempt in range(self.config.max_retries):
            try:
                if not self.session:
                    raise RuntimeError("Client session not initialized. Use async context manager.")
                
                async with self.session.post(url, json=data) as response:
                    if response.status == 200:
                        if stream:
                            return self._handle_stream_response(response)
                        else:
                            return await response.json()
                    else:
                        error_text = await response.text()
                        logger.error(f"SiliconFlow API error {response.status}: {error_text}")
                        
                        if attempt == self.config.max_retries - 1:
                            raise Exception(f"SiliconFlow API error {response.status}: {error_text}")
                        
                        # 重试前等待
                        await asyncio.sleep(self.config.retry_delay * (attempt + 1))
            
            except aiohttp.ClientError as e:
                logger.error(f"HTTP client error: {e}")
                if attempt == self.config.max_retries - 1:
                    raise Exception(f"HTTP client error: {e}")
                
                await asyncio.sleep(self.config.retry_delay * (attempt + 1))
    
    async def _handle_stream_response(self, response: aiohttp.ClientResponse) -> AsyncGenerator[str, None]:
        """处理流式响应"""
        async for line in response.content:
            if line:
                line_str = line.decode('utf-8').strip()
                if line_str.startswith('data: '):
                    data_str = line_str[6:]  # 移除 'data: ' 前缀
                    if data_str == '[DONE]':
                        break
                    try:
                        data = json.loads(data_str)
                        if 'choices' in data and len(data['choices']) > 0:
                            delta = data['choices'][0].get('delta', {})
                            content = delta.get('content', '')
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        continue
    
    async def chat_completions(self, request: SiliconFlowChatRequest) -> Union[SiliconFlowChatResponse, AsyncGenerator[str, None]]:
        """聊天完成API"""
        # 构建请求数据
        request_data = {
            "model": request.model,
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content
                } for msg in request.messages
            ],
            "temperature": request.temperature,
            "top_p": request.top_p,
            "stream": request.stream
        }
        
        if request.max_tokens:
            request_data["max_tokens"] = request.max_tokens
        if request.stop:
            request_data["stop"] = request.stop
        if request.presence_penalty != 0.0:
            request_data["presence_penalty"] = request.presence_penalty
        if request.frequency_penalty != 0.0:
            request_data["frequency_penalty"] = request.frequency_penalty
        
        logger.info(f"发送聊天请求到模型: {request.model}")
        
        if request.stream:
            # 流式响应
            response_generator = await self._make_request(
                self.config.chat_endpoint, 
                request_data, 
                stream=True
            )
            return response_generator
        else:
            # 非流式响应
            response_data = await self._make_request(
                self.config.chat_endpoint, 
                request_data
            )
            
            # 解析响应
            choice = response_data['choices'][0]
            return SiliconFlowChatResponse(
                id=response_data['id'],
                model=response_data['model'],
                content=choice['message']['content'],
                finish_reason=choice['finish_reason'],
                usage=response_data['usage']
            )
    
    async def create_embeddings(self, request: SiliconFlowEmbeddingRequest) -> SiliconFlowEmbeddingResponse:
        """创建嵌入向量"""
        request_data = {
            "model": request.model,
            "input": request.input,
            "encoding_format": request.encoding_format
        }
        
        logger.info(f"发送嵌入请求到模型: {request.model}")
        
        response_data = await self._make_request(
            self.config.embeddings_endpoint,
            request_data
        )
        
        return SiliconFlowEmbeddingResponse(
            model=response_data['model'],
            data=response_data['data'],
            usage=response_data['usage']
        )
    
    async def create_rerank(self, request: SiliconFlowRerankRequest) -> SiliconFlowRerankResponse:
        """创建重排序"""
        request_data = {
            "model": request.model,
            "query": request.query,
            "documents": request.documents,
            "return_documents": request.return_documents
        }
        
        if request.top_n:
            request_data["top_n"] = request.top_n
        
        logger.info(f"发送重排序请求到模型: {request.model}")
        
        response_data = await self._make_request(
            self.config.rerank_endpoint,
            request_data
        )
        
        return SiliconFlowRerankResponse(
            model=response_data['model'],
            results=response_data['results'],
            usage=response_data['usage']
        )


class SiliconFlowAgnoAdapter:
    """硅基流动Agno适配器
    
    将硅基流动API适配为类似Agno的接口，便于workflow_v2_manager使用
    """
    
    def __init__(self):
        self.client = SiliconFlowClient()
    
    async def create_agent_instance(self, agent_config: Dict[str, Any]) -> 'SiliconFlowAgent':
        """创建智能体实例"""
        return SiliconFlowAgent(
            name=agent_config.get('name', 'Agent'),
            model_name=agent_config.get('model_name', 'Qwen/Qwen3-32B'),
            instructions=agent_config.get('instructions', ''),
            tools=agent_config.get('tools', []),
            temperature=agent_config.get('temperature', 0.7),
            max_tokens=agent_config.get('max_tokens', 4096),
            client=self.client
        )


class SiliconFlowAgent:
    """硅基流动智能体
    
    模拟Agno Agent的接口
    """
    
    def __init__(self, name: str, model_name: str, instructions: str, 
                 tools: List[str], temperature: float, max_tokens: int,
                 client: SiliconFlowClient):
        self.name = name
        self.model_name = get_siliconflow_model_id(model_name)
        self.instructions = instructions
        self.tools = tools
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.client = client
    
    async def run(self, message: str, stream: bool = False) -> Union['AgentResponse', AsyncGenerator[str, None]]:
        """运行智能体"""
        # 构建消息列表
        messages = []
        if self.instructions:
            messages.append(SiliconFlowMessage(role="system", content=self.instructions))
        messages.append(SiliconFlowMessage(role="user", content=message))
        
        # 构建请求
        request = SiliconFlowChatRequest(
            model=self.model_name,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=stream
        )
        
        # 调用API
        async with self.client:
            if stream:
                # 流式响应
                async def response_generator():
                    content_parts = []
                    async for content in await self.client.chat_completions(request):
                        content_parts.append(content)
                        yield content
                    
                    # 最后返回完整响应
                    full_content = ''.join(content_parts)
                    final_response = AgentResponse(
                        content=full_content,
                        agent_name=self.name,
                        model_name=self.model_name,
                        usage={"estimated_tokens": len(full_content) // 4}
                    )
                    yield final_response
                
                return response_generator()
            else:
                # 非流式响应
                response = await self.client.chat_completions(request)
                return AgentResponse(
                    content=response.content,
                    agent_name=self.name,
                    model_name=self.model_name,
                    usage=response.usage
                )


@dataclass
class AgentResponse:
    """智能体响应结构"""
    content: str
    agent_name: str
    model_name: str
    usage: Dict[str, int]
    metadata: Dict[str, Any] = field(default_factory=dict)


# 全局适配器实例
siliconflow_adapter = SiliconFlowAgnoAdapter()


# 测试函数
async def test_siliconflow_client():
    """测试硅基流动API客户端"""
    print("🧪 测试硅基流动API客户端")
    print("=" * 50)
    
    async with SiliconFlowClient() as client:
        # 测试聊天API
        print("1. 测试聊天API:")
        messages = [
            SiliconFlowMessage(role="system", content="你是一个专业的AI助手"),
            SiliconFlowMessage(role="user", content="你好，请介绍一下你自己")
        ]
        
        request = SiliconFlowChatRequest(
            model="Qwen/Qwen3-32B",
            messages=messages,
            temperature=0.7,
            max_tokens=100
        )
        
        try:
            response = await client.chat_completions(request)
            print(f"   ✅ 响应: {response.content[:100]}...")
            print(f"   📊 使用量: {response.usage}")
        except Exception as e:
            print(f"   ❌ 错误: {e}")
        
        print()
        
        # 测试嵌入API
        print("2. 测试嵌入API:")
        embed_request = SiliconFlowEmbeddingRequest(
            model="Qwen/Qwen3-Embedding-8B",
            input=["测试文本嵌入", "另一个测试文本"]
        )
        
        try:
            embed_response = await client.create_embeddings(embed_request)
            print(f"   ✅ 嵌入维度: {len(embed_response.data[0]['embedding']) if embed_response.data else 0}")
            print(f"   📊 使用量: {embed_response.usage}")
        except Exception as e:
            print(f"   ❌ 错误: {e}")
        
        print()
        
        # 测试重排序API
        print("3. 测试重排序API:")
        rerank_request = SiliconFlowRerankRequest(
            model="Qwen/Qwen3-Reranker-8B",
            query="人工智能技术",
            documents=[
                "机器学习是人工智能的一个重要分支",
                "深度学习推动了AI技术的发展",
                "今天天气很好，适合出门游玩"
            ],
            top_n=2
        )
        
        try:
            rerank_response = await client.create_rerank(rerank_request)
            print(f"   ✅ 重排序结果数量: {len(rerank_response.results)}")
            for i, result in enumerate(rerank_response.results):
                print(f"   📈 排名{i+1}: 分数{result.get('relevance_score', 0):.3f}")
            print(f"   📊 使用量: {rerank_response.usage}")
        except Exception as e:
            print(f"   ❌ 错误: {e}")


if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_siliconflow_client()) 