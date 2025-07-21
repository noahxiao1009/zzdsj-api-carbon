"""
统一模型调用API接口
提供chat、embedding、completion等统一调用接口
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any, Optional, Union
import logging
from datetime import datetime
import json
import asyncio

from ..services.model_invoker import ModelInvoker, ModelInvokeError
from ..services.service_integration import ModelServiceIntegration
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
invoke_router = APIRouter(prefix="/api/v1/models", tags=["模型调用"])

# 请求模型定义
class ChatRequest(BaseModel):
    """聊天请求"""
    provider_id: str = Field(..., description="提供商ID")
    model_id: str = Field(..., description="模型ID")
    messages: List[Dict[str, str]] = Field(..., description="消息列表")
    temperature: Optional[float] = Field(0.7, description="温度参数")
    max_tokens: Optional[int] = Field(4000, description="最大Token数")
    top_p: Optional[float] = Field(0.9, description="Top-p参数")
    frequency_penalty: Optional[float] = Field(0.0, description="频率惩罚")
    presence_penalty: Optional[float] = Field(0.0, description="存在惩罚")
    stop: Optional[List[str]] = Field([], description="停止词")
    stream: bool = Field(False, description="是否流式输出")
    user_id: Optional[str] = Field(None, description="用户ID")

class CompletionRequest(BaseModel):
    """文本补全请求"""
    provider_id: str = Field(..., description="提供商ID")
    model_id: str = Field(..., description="模型ID")
    prompt: str = Field(..., description="提示文本")
    temperature: Optional[float] = Field(0.7, description="温度参数")
    max_tokens: Optional[int] = Field(4000, description="最大Token数")
    top_p: Optional[float] = Field(0.9, description="Top-p参数")
    frequency_penalty: Optional[float] = Field(0.0, description="频率惩罚")
    presence_penalty: Optional[float] = Field(0.0, description="存在惩罚")
    stop: Optional[List[str]] = Field([], description="停止词")
    stream: bool = Field(False, description="是否流式输出")
    user_id: Optional[str] = Field(None, description="用户ID")

class EmbeddingRequest(BaseModel):
    """嵌入请求"""
    provider_id: str = Field(..., description="提供商ID")
    model_id: str = Field(..., description="模型ID")
    input: Union[str, List[str]] = Field(..., description="输入文本或文本列表")
    encoding_format: str = Field("float", description="编码格式")
    user_id: Optional[str] = Field(None, description="用户ID")

class MultimodalRequest(BaseModel):
    """多模态请求"""
    provider_id: str = Field(..., description="提供商ID")
    model_id: str = Field(..., description="模型ID")
    messages: List[Dict[str, Any]] = Field(..., description="多模态消息列表")
    temperature: Optional[float] = Field(0.5, description="温度参数")
    max_tokens: Optional[int] = Field(2000, description="最大Token数")
    detail: str = Field("auto", description="图像细节级别")
    user_id: Optional[str] = Field(None, description="用户ID")

class RerankRequest(BaseModel):
    """重排请求"""
    provider_id: str = Field(..., description="提供商ID")
    model_id: str = Field(..., description="模型ID")
    query: str = Field(..., description="查询文本")
    documents: List[str] = Field(..., description="文档列表")
    top_n: Optional[int] = Field(10, description="返回前N个结果")
    return_documents: bool = Field(True, description="是否返回文档内容")
    user_id: Optional[str] = Field(None, description="用户ID")

class BatchRequest(BaseModel):
    """批量请求"""
    requests: List[Dict[str, Any]] = Field(..., description="批量请求列表")
    user_id: Optional[str] = Field(None, description="用户ID")
    max_concurrent: int = Field(5, description="最大并发数")

# 全局模型调用器实例
model_invoker = ModelInvoker()

# ==================== 聊天接口 ====================

@invoke_router.post("/chat/completions")
async def chat_completions(
    request: ChatRequest,
    background_tasks: BackgroundTasks
):
    """
    聊天补全接口 - 兼容OpenAI格式
    """
    try:
        logger.info(f"聊天请求: {request.provider_id}:{request.model_id}")
        
        # 构建配置参数
        config = {
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "top_p": request.top_p,
            "frequency_penalty": request.frequency_penalty,
            "presence_penalty": request.presence_penalty,
            "stop": request.stop,
            "stream": request.stream
        }
        
        # 如果需要权限检查和使用统计
        if request.user_id:
            async with ModelServiceIntegration() as integration:
                # 执行完整的模型调用工作流（包含权限检查、配额验证等）
                result = await integration.model_call_workflow(
                    user_id=request.user_id,
                    provider_id=request.provider_id,
                    model_id=request.model_id,
                    call_data={
                        "message": request.messages[-1]["content"] if request.messages else "",
                        "messages": request.messages,
                        **config
                    }
                )
                
                if not result["success"]:
                    raise HTTPException(
                        status_code=400 if result.get("code") in ["PERMISSION_DENIED", "QUOTA_EXCEEDED"] else 500,
                        detail=result["error"]
                    )
                
                # 返回标准化格式
                return {
                    "id": f"chatcmpl-{int(datetime.now().timestamp())}",
                    "object": "chat.completion",
                    "created": int(datetime.now().timestamp()),
                    "model": f"{request.provider_id}:{request.model_id}",
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": result["response"]
                        },
                        "finish_reason": "stop"
                    }],
                    "usage": result.get("token_usage", {}),
                    "latency_ms": result.get("latency", 0)
                }
        
        # 直接调用模型（无权限检查）
        if request.stream:
            # 流式响应
            async def generate_stream():
                try:
                    async for chunk in model_invoker.invoke_chat(
                        provider_id=request.provider_id,
                        model_id=request.model_id,
                        messages=request.messages,
                        config=config,
                        stream=True
                    ):
                        yield f"data: {json.dumps(chunk)}\n\n"
                    yield "data: [DONE]\n\n"
                except Exception as e:
                    error_chunk = {
                        "error": {
                            "message": str(e),
                            "type": "model_error"
                        }
                    }
                    yield f"data: {json.dumps(error_chunk)}\n\n"
            
            return StreamingResponse(
                generate_stream(),
                media_type="text/plain",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
            )
        else:
            # 非流式响应
            response = await model_invoker.invoke_chat(
                provider_id=request.provider_id,
                model_id=request.model_id,
                messages=request.messages,
                config=config,
                stream=False
            )
            
            return response
        
    except ModelInvokeError as e:
        logger.error(f"模型调用错误: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"聊天接口异常: {e}")
        raise HTTPException(status_code=500, detail="聊天接口调用失败")

# ==================== 文本补全接口 ====================

@invoke_router.post("/completions")
async def text_completions(
    request: CompletionRequest,
    background_tasks: BackgroundTasks
):
    """
    文本补全接口 - 兼容OpenAI格式
    """
    try:
        logger.info(f"补全请求: {request.provider_id}:{request.model_id}")
        
        # 构建配置参数
        config = {
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "top_p": request.top_p,
            "frequency_penalty": request.frequency_penalty,
            "presence_penalty": request.presence_penalty,
            "stop": request.stop,
            "stream": request.stream
        }
        
        if request.stream:
            # 流式响应
            async def generate_stream():
                try:
                    async for chunk in model_invoker.invoke_completion(
                        provider_id=request.provider_id,
                        model_id=request.model_id,
                        prompt=request.prompt,
                        config=config,
                        stream=True
                    ):
                        yield f"data: {json.dumps(chunk)}\n\n"
                    yield "data: [DONE]\n\n"
                except Exception as e:
                    error_chunk = {
                        "error": {
                            "message": str(e),
                            "type": "model_error"
                        }
                    }
                    yield f"data: {json.dumps(error_chunk)}\n\n"
            
            return StreamingResponse(
                generate_stream(),
                media_type="text/plain",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
            )
        else:
            # 非流式响应
            response = await model_invoker.invoke_completion(
                provider_id=request.provider_id,
                model_id=request.model_id,
                prompt=request.prompt,
                config=config,
                stream=False
            )
            
            return response
        
    except ModelInvokeError as e:
        logger.error(f"模型调用错误: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"补全接口异常: {e}")
        raise HTTPException(status_code=500, detail="补全接口调用失败")

# ==================== 嵌入接口 ====================

@invoke_router.post("/embeddings")
async def text_embeddings(
    request: EmbeddingRequest,
    background_tasks: BackgroundTasks
):
    """
    文本嵌入接口 - 兼容OpenAI格式
    """
    try:
        logger.info(f"嵌入请求: {request.provider_id}:{request.model_id}")
        
        # 构建配置参数
        config = {
            "encoding_format": request.encoding_format
        }
        
        # 如果需要权限检查
        if request.user_id:
            async with ModelServiceIntegration() as integration:
                # 检查权限
                has_permission = await integration.check_model_permission(
                    user_id=request.user_id,
                    provider_id=request.provider_id,
                    model_id=request.model_id,
                    action="use"
                )
                
                if not has_permission:
                    raise HTTPException(status_code=403, detail="没有使用此模型的权限")
        
        # 调用嵌入接口
        response = await model_invoker.invoke_embedding(
            provider_id=request.provider_id,
            model_id=request.model_id,
            texts=request.input if isinstance(request.input, list) else [request.input],
            config=config
        )
        
        # 记录使用统计
        if request.user_id:
            background_tasks.add_task(
                record_embedding_usage,
                request.user_id,
                request.provider_id,
                request.model_id,
                response
            )
        
        return response
        
    except ModelInvokeError as e:
        logger.error(f"模型调用错误: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"嵌入接口异常: {e}")
        raise HTTPException(status_code=500, detail="嵌入接口调用失败")

# ==================== 多模态接口 ====================

@invoke_router.post("/multimodal/completions")
async def multimodal_completions(
    request: MultimodalRequest,
    background_tasks: BackgroundTasks
):
    """
    多模态补全接口
    """
    try:
        logger.info(f"多模态请求: {request.provider_id}:{request.model_id}")
        
        # 构建配置参数
        config = {
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "detail": request.detail
        }
        
        # 调用多模态接口
        response = await model_invoker.invoke_multimodal(
            provider_id=request.provider_id,
            model_id=request.model_id,
            messages=request.messages,
            config=config
        )
        
        return response
        
    except ModelInvokeError as e:
        logger.error(f"模型调用错误: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"多模态接口异常: {e}")
        raise HTTPException(status_code=500, detail="多模态接口调用失败")

# ==================== 重排接口 ====================

@invoke_router.post("/rerank")
async def document_rerank(
    request: RerankRequest,
    background_tasks: BackgroundTasks
):
    """
    文档重排接口
    """
    try:
        logger.info(f"重排请求: {request.provider_id}:{request.model_id}")
        
        # 构建配置参数
        config = {
            "top_n": request.top_n,
            "return_documents": request.return_documents
        }
        
        # 调用重排接口
        response = await model_invoker.invoke_rerank(
            provider_id=request.provider_id,
            model_id=request.model_id,
            query=request.query,
            documents=request.documents,
            config=config
        )
        
        return response
        
    except ModelInvokeError as e:
        logger.error(f"模型调用错误: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"重排接口异常: {e}")
        raise HTTPException(status_code=500, detail="重排接口调用失败")

# ==================== 批量调用接口 ====================

@invoke_router.post("/batch")
async def batch_invoke(
    request: BatchRequest,
    background_tasks: BackgroundTasks
):
    """
    批量模型调用接口
    """
    try:
        logger.info(f"批量请求: {len(request.requests)} 个调用")
        
        if request.user_id:
            # 使用集成服务进行批量调用
            async with ModelServiceIntegration() as integration:
                results = await integration.batch_model_calls(
                    user_id=request.user_id,
                    calls=request.requests
                )
                
                return {
                    "success": True,
                    "results": results,
                    "total": len(results),
                    "timestamp": datetime.now().isoformat()
                }
        else:
            # 直接批量调用（无权限检查）
            semaphore = asyncio.Semaphore(request.max_concurrent)
            
            async def process_single_request(req_data):
                async with semaphore:
                    try:
                        call_type = req_data.get("type", "chat")
                        
                        if call_type == "chat":
                            return await model_invoker.invoke_chat(
                                provider_id=req_data["provider_id"],
                                model_id=req_data["model_id"],
                                messages=req_data["messages"],
                                config=req_data.get("config", {}),
                                stream=False
                            )
                        elif call_type == "embedding":
                            return await model_invoker.invoke_embedding(
                                provider_id=req_data["provider_id"],
                                model_id=req_data["model_id"],
                                texts=req_data["texts"],
                                config=req_data.get("config", {})
                            )
                        else:
                            return {"error": f"不支持的调用类型: {call_type}"}
                    except Exception as e:
                        return {"error": str(e)}
            
            # 并发执行所有请求
            tasks = [process_single_request(req) for req in request.requests]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理异常结果
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    processed_results.append({
                        "success": False,
                        "error": str(result),
                        "index": i
                    })
                else:
                    processed_results.append({
                        "success": True,
                        "data": result,
                        "index": i
                    })
            
            return {
                "success": True,
                "results": processed_results,
                "total": len(processed_results),
                "timestamp": datetime.now().isoformat()
            }
        
    except Exception as e:
        logger.error(f"批量调用异常: {e}")
        raise HTTPException(status_code=500, detail="批量调用失败")

# ==================== 模型状态和监控接口 ====================

@invoke_router.get("/status")
async def get_models_status():
    """
    获取模型服务状态
    """
    try:
        # 检查各个提供商的模型状态
        from .models import SUPPORTED_PROVIDERS, providers_db
        
        provider_status = {}
        total_models = 0
        available_models = 0
        
        for provider_id, provider_data in SUPPORTED_PROVIDERS.items():
            configured_provider = providers_db.get(provider_id)
            enabled_models = configured_provider.get("enabled_models", []) if configured_provider else []
            
            provider_status[provider_id] = {
                "name": provider_data["name"],
                "configured": configured_provider is not None,
                "enabled": configured_provider["is_enabled"] if configured_provider else False,
                "total_models": len(provider_data["models"]),
                "enabled_models": len(enabled_models),
                "models": enabled_models
            }
            
            total_models += len(provider_data["models"])
            available_models += len(enabled_models)
        
        return {
            "success": True,
            "data": {
                "service_status": "healthy",
                "total_providers": len(SUPPORTED_PROVIDERS),
                "configured_providers": len(providers_db),
                "total_models": total_models,
                "available_models": available_models,
                "provider_status": provider_status,
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"获取模型状态失败: {e}")
        raise HTTPException(status_code=500, detail="获取模型状态失败")

@invoke_router.get("/usage/stats")
async def get_usage_statistics(
    user_id: Optional[str] = None,
    provider_id: Optional[str] = None,
    model_id: Optional[str] = None,
    period: str = "daily"
):
    """
    获取模型使用统计
    """
    try:
        if user_id:
            async with ModelServiceIntegration() as integration:
                stats = await integration.get_model_usage_stats(
                    user_id=user_id,
                    provider_id=provider_id,
                    model_id=model_id,
                    period=period
                )
                return {
                    "success": True,
                    "data": stats
                }
        else:
            # 返回系统级统计（模拟数据）
            return {
                "success": True,
                "data": {
                    "total_calls": 12345,
                    "total_tokens": 1234567,
                    "avg_latency": 456.7,
                    "error_rate": 0.02,
                    "top_models": [
                        {"provider_id": "zhipu", "model_id": "glm-4", "calls": 5000},
                        {"provider_id": "baidu", "model_id": "ernie-4.0-8k", "calls": 3000}
                    ],
                    "period": period,
                    "timestamp": datetime.now().isoformat()
                }
            }
        
    except Exception as e:
        logger.error(f"获取使用统计失败: {e}")
        raise HTTPException(status_code=500, detail="获取使用统计失败")

# ==================== 辅助函数 ====================

async def record_embedding_usage(
    user_id: str,
    provider_id: str,
    model_id: str,
    response: Dict[str, Any]
):
    """记录嵌入使用情况"""
    try:
        async with ModelServiceIntegration() as integration:
            await integration.record_model_usage(
                user_id=user_id,
                provider_id=provider_id,
                model_id=model_id,
                usage_data={
                    "tokens": response.get("usage", {}).get("total_tokens", 0),
                    "cost": 0.0,  # 根据实际定价计算
                    "latency": response.get("latency_ms", 0),
                    "error": False
                }
            )
    except Exception as e:
        logger.error(f"记录嵌入使用统计失败: {e}")