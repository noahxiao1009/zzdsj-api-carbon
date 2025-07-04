"""
聊天相关API路由
"""

import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends, Request, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import json
import base64

from app.services.chat_manager import get_chat_manager, ChatManager
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["聊天"])


# Pydantic模型定义
class CreateSessionRequest(BaseModel):
    """创建会话请求"""
    user_id: str = Field(..., description="用户ID")
    agent_id: Optional[str] = Field(None, description="智能体ID，默认为通用聊天")
    session_config: Optional[Dict[str, Any]] = Field(None, description="会话配置")


class CreateSessionResponse(BaseModel):
    """创建会话响应"""
    success: bool
    session_id: Optional[str] = None
    session_info: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class SendMessageRequest(BaseModel):
    """发送消息请求"""
    session_id: str = Field(..., description="会话ID")
    message: str = Field(..., description="消息内容")
    message_type: str = Field("text", description="消息类型：text, voice")
    stream: bool = Field(False, description="是否流式响应")
    voice_config: Optional[Dict[str, Any]] = Field(None, description="语音配置")


class SendMessageResponse(BaseModel):
    """发送消息响应"""
    success: bool
    session_id: str
    message_id: Optional[str] = None
    response: Optional[str] = None
    timestamp: Optional[str] = None
    agent_id: Optional[str] = None
    original_message: Optional[str] = None
    processed_message: Optional[str] = None
    audio_response: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class VoiceMessageRequest(BaseModel):
    """语音消息请求"""
    session_id: str = Field(..., description="会话ID")
    audio_format: str = Field("wav", description="音频格式")
    enable_tts: bool = Field(True, description="是否启用文字转语音")
    voice: str = Field("default", description="语音类型")


class GetHistoryResponse(BaseModel):
    """获取历史响应"""
    success: bool
    session_id: Optional[str] = None
    messages: Optional[List[Dict[str, Any]]] = None
    pagination: Optional[Dict[str, Any]] = None
    session_info: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class AgentsResponse(BaseModel):
    """智能体列表响应"""
    success: bool
    agents: Optional[List[Dict[str, Any]]] = None
    count: Optional[int] = None
    error: Optional[str] = None


@router.post("/session", response_model=CreateSessionResponse)
async def create_chat_session(
    request: CreateSessionRequest,
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """创建聊天会话"""
    try:
        logger.info(f"创建聊天会话请求: user_id={request.user_id}, agent_id={request.agent_id}")
        
        result = await chat_manager.create_session(
            user_id=request.user_id,
            agent_id=request.agent_id,
            session_config=request.session_config
        )
        
        return CreateSessionResponse(**result)
        
    except Exception as e:
        logger.error(f"创建聊天会话失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/message", response_model=SendMessageResponse)
async def send_message(
    request: SendMessageRequest,
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """发送文本消息（非流式）"""
    try:
        logger.info(f"发送消息请求: session_id={request.session_id}, type={request.message_type}")
        
        if request.stream:
            raise HTTPException(
                status_code=400, 
                detail="流式响应请使用 /chat/message/stream 接口"
            )
        
        result = await chat_manager.send_message(
            session_id=request.session_id,
            message=request.message,
            message_type=request.message_type,
            stream=False,
            voice_config=request.voice_config
        )
        
        if isinstance(result, dict):
            return SendMessageResponse(**result)
        else:
            raise HTTPException(status_code=500, detail="响应格式错误")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"发送消息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/message/stream")
async def send_message_stream(
    request: SendMessageRequest,
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """发送消息（流式响应）"""
    try:
        logger.info(f"发送流式消息请求: session_id={request.session_id}")
        
        async def generate():
            try:
                response_stream = await chat_manager.send_message(
                    session_id=request.session_id,
                    message=request.message,
                    message_type=request.message_type,
                    stream=True,
                    voice_config=request.voice_config
                )
                
                async for chunk in response_stream:
                    # 发送Server-Sent Events格式的数据
                    yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                
                # 发送结束信号
                yield "data: [DONE]\n\n"
                
            except Exception as e:
                logger.error(f"流式响应生成失败: {e}")
                error_chunk = {
                    "type": "error",
                    "error": str(e),
                    "timestamp": "now"
                }
                yield f"data: {json.dumps(error_chunk, ensure_ascii=False)}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # 禁用nginx缓冲
            }
        )
        
    except Exception as e:
        logger.error(f"创建流式响应失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/voice")
async def send_voice_message(
    request: VoiceMessageRequest,
    audio_file: UploadFile = File(..., description="音频文件"),
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """发送语音消息"""
    try:
        logger.info(f"发送语音消息请求: session_id={request.session_id}")
        
        # 读取音频数据
        audio_data = await audio_file.read()
        
        # 构建语音配置
        voice_config = {
            "audio_data": audio_data,
            "format": request.audio_format,
            "enable_tts": request.enable_tts,
            "voice": request.voice
        }
        
        # 发送语音消息
        result = await chat_manager.send_message(
            session_id=request.session_id,
            message="[语音消息]",  # 占位符，实际内容通过语音识别获取
            message_type="voice",
            stream=False,
            voice_config=voice_config
        )
        
        if isinstance(result, dict):
            return SendMessageResponse(**result)
        else:
            raise HTTPException(status_code=500, detail="响应格式错误")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"发送语音消息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{session_id}", response_model=GetHistoryResponse)
async def get_session_history(
    session_id: str,
    limit: int = Query(50, ge=1, le=200, description="每页消息数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """获取会话历史"""
    try:
        logger.info(f"获取会话历史请求: session_id={session_id}, limit={limit}, offset={offset}")
        
        result = await chat_manager.get_session_history(
            session_id=session_id,
            limit=limit,
            offset=offset
        )
        
        return GetHistoryResponse(**result)
        
    except Exception as e:
        logger.error(f"获取会话历史失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents", response_model=AgentsResponse)
async def get_available_agents(
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """获取可用智能体列表"""
    try:
        logger.info("获取可用智能体列表请求")
        
        result = await chat_manager.get_available_agents()
        
        return AgentsResponse(**result)
        
    except Exception as e:
        logger.error(f"获取智能体列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/session/{session_id}")
async def delete_session(
    session_id: str,
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """删除会话"""
    try:
        logger.info(f"删除会话请求: session_id={session_id}")
        
        result = await chat_manager.delete_session(session_id)
        
        if result.get("success"):
            return {"message": "会话删除成功", "session_id": session_id}
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "删除失败"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除会话失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}/status")
async def get_session_status(
    session_id: str,
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """获取会话状态"""
    try:
        logger.info(f"获取会话状态请求: session_id={session_id}")
        
        # 获取会话信息
        session_info = await chat_manager._get_session_info(session_id)
        
        if not session_info:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        return {
            "session_id": session_id,
            "status": session_info.get("status", "unknown"),
            "last_activity": session_info.get("last_activity"),
            "message_count": session_info.get("message_count", 0),
            "user_id": session_info.get("user_id"),
            "agent_id": session_info.get("agent_id"),
            "created_at": session_info.get("created_at")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取会话状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# WebSocket相关接口（预留）
@router.get("/ws/info")
async def get_websocket_info():
    """获取WebSocket连接信息"""
    return {
        "websocket_enabled": settings.websocket_enabled,
        "websocket_path": "/chat/ws",
        "supported_features": [
            "real_time_chat",
            "voice_streaming",
            "typing_indicators",
            "presence_updates"
        ]
    } 