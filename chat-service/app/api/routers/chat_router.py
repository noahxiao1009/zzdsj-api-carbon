"""
聊天路由 - 基于Agno框架的聊天API接口
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Query, Body, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import json

from app.core.dependencies import get_chat_manager, get_current_user
from app.services.chat_manager import ChatManager
from app.schemas.chat import (
    ChatRequest, ChatResponse, SessionCreateRequest, 
    SessionResponse, MessageHistory, VoiceConfig
)

logger = logging.getLogger(__name__)
router = APIRouter()


class AgnoMessageRequest(BaseModel):
    """Agno消息请求格式"""
    message: str = Field(..., description="消息内容")
    session_id: Optional[str] = Field(None, description="会话ID")
    agent_id: Optional[str] = Field(None, description="智能体ID")
    stream: bool = Field(False, description="是否流式响应")
    message_type: str = Field("text", description="消息类型: text, voice")
    voice_config: Optional[VoiceConfig] = Field(None, description="语音配置")
    context: Optional[Dict[str, Any]] = Field(None, description="额外上下文")


class AgnoSessionRequest(BaseModel):
    """Agno会话创建请求"""
    agent_id: Optional[str] = Field(None, description="智能体ID")
    session_config: Optional[Dict[str, Any]] = Field(None, description="会话配置")
    user_preferences: Optional[Dict[str, Any]] = Field(None, description="用户偏好")


@router.post("/message", response_model=Dict[str, Any])
async def send_message(
    request: AgnoMessageRequest,
    current_user: Dict = Depends(get_current_user),
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """
    发送聊天消息 - Agno API格式
    
    支持文本和语音消息，可选择流式或非流式响应
    """
    try:
        user_id = current_user["user_id"]
        
        # 如果没有提供session_id，创建新会话
        session_id = request.session_id
        if not session_id:
            session_result = await chat_manager.create_session(
                user_id=user_id,
                agent_id=request.agent_id
            )
            if not session_result["success"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"创建会话失败: {session_result['error']}"
                )
            session_id = session_result["session_id"]
        
        # 发送消息
        if request.stream:
            # 流式响应
            async def generate_stream():
                try:
                    async for chunk in await chat_manager.send_message(
                        session_id=session_id,
                        message=request.message,
                        message_type=request.message_type,
                        stream=True,
                        voice_config=request.voice_config.dict() if request.voice_config else None
                    ):
                        yield f"data: {json.dumps(chunk)}\n\n"
                except Exception as e:
                    error_data = {
                        "type": "error",
                        "error": str(e),
                        "timestamp": asyncio.get_event_loop().time()
                    }
                    yield f"data: {json.dumps(error_data)}\n\n"
                finally:
                    yield "data: [DONE]\n\n"
            
            return StreamingResponse(
                generate_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Session-ID": session_id
                }
            )
        else:
            # 非流式响应
            result = await chat_manager.send_message(
                session_id=session_id,
                message=request.message,
                message_type=request.message_type,
                stream=False,
                voice_config=request.voice_config.dict() if request.voice_config else None
            )
            
            if not result["success"]:
                raise HTTPException(
                    status_code=400,
                    detail=result["error"]
                )
            
            # 返回Agno标准格式
            return {
                "success": True,
                "session_id": session_id,
                "response": result["response"],
                "audio_response": result.get("audio_response"),
                "timestamp": result["timestamp"],
                "agent_id": request.agent_id or "general-chat",
                "message_type": request.message_type,
                "context": request.context
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"发送消息失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"内部服务器错误: {str(e)}"
        )


@router.post("/session", response_model=Dict[str, Any])
async def create_session(
    request: AgnoSessionRequest,
    current_user: Dict = Depends(get_current_user),
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """
    创建聊天会话 - Agno API格式
    """
    try:
        user_id = current_user["user_id"]
        
        result = await chat_manager.create_session(
            user_id=user_id,
            agent_id=request.agent_id,
            session_config=request.session_config
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=400,
                detail=result["error"]
            )
        
        return {
            "success": True,
            "session_id": result["session_id"],
            "session_info": result["session_info"],
            "agent_id": request.agent_id or "general-chat",
            "user_preferences": request.user_preferences
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建会话失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"内部服务器错误: {str(e)}"
        )


@router.get("/session/{session_id}/history", response_model=Dict[str, Any])
async def get_session_history(
    session_id: str,
    limit: int = Query(50, ge=1, le=100, description="消息数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
    current_user: Dict = Depends(get_current_user),
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """
    获取会话历史 - Agno API格式
    """
    try:
        result = await chat_manager.get_session_history(
            session_id=session_id,
            limit=limit,
            offset=offset
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=404,
                detail=result["error"]
            )
        
        return {
            "success": True,
            "session_id": session_id,
            "messages": result["messages"],
            "pagination": result["pagination"],
            "user_id": current_user["user_id"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取会话历史失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"内部服务器错误: {str(e)}"
        )


@router.get("/sessions", response_model=Dict[str, Any])
async def list_user_sessions(
    status: Optional[str] = Query(None, description="会话状态筛选"),
    current_user: Dict = Depends(get_current_user),
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """
    列出用户会话 - Agno API格式
    """
    try:
        user_id = current_user["user_id"]
        
        result = await chat_manager.list_user_sessions(
            user_id=user_id,
            status=status
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=400,
                detail=result["error"]
            )
        
        return {
            "success": True,
            "user_id": user_id,
            "sessions": result["sessions"],
            "total": result["total"],
            "filter": {"status": status} if status else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"列出用户会话失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"内部服务器错误: {str(e)}"
        )


@router.delete("/session/{session_id}", response_model=Dict[str, Any])
async def delete_session(
    session_id: str,
    current_user: Dict = Depends(get_current_user),
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """
    删除聊天会话 - Agno API格式
    """
    try:
        result = await chat_manager.delete_session(session_id)
        
        if not result["success"]:
            raise HTTPException(
                status_code=404,
                detail=result["error"]
            )
        
        return {
            "success": True,
            "session_id": session_id,
            "message": "会话已删除",
            "user_id": current_user["user_id"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除会话失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"内部服务器错误: {str(e)}"
        )


@router.post("/agent/{agent_id}/query", response_model=Dict[str, Any])
async def query_agent_directly(
    agent_id: str,
    query: str = Body(..., embed=True),
    stream: bool = Body(False, embed=True),
    context: Optional[Dict[str, Any]] = Body(None, embed=True),
    current_user: Dict = Depends(get_current_user),
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """
    直接查询智能体 - Agno API格式
    无需创建持久会话，适用于一次性查询
    """
    try:
        user_id = current_user["user_id"]
        
        # 创建临时会话
        session_result = await chat_manager.create_session(
            user_id=user_id,
            agent_id=agent_id,
            session_config={"temporary": True}
        )
        
        if not session_result["success"]:
            raise HTTPException(
                status_code=400,
                detail=f"创建临时会话失败: {session_result['error']}"
            )
        
        session_id = session_result["session_id"]
        
        try:
            if stream:
                # 流式响应
                async def generate_stream():
                    try:
                        async for chunk in await chat_manager.send_message(
                            session_id=session_id,
                            message=query,
                            stream=True
                        ):
                            yield f"data: {json.dumps(chunk)}\n\n"
                    except Exception as e:
                        error_data = {
                            "type": "error",
                            "error": str(e),
                            "timestamp": asyncio.get_event_loop().time()
                        }
                        yield f"data: {json.dumps(error_data)}\n\n"
                    finally:
                        # 清理临时会话
                        await chat_manager.delete_session(session_id)
                        yield "data: [DONE]\n\n"
                
                return StreamingResponse(
                    generate_stream(),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Agent-ID": agent_id,
                        "X-Query-Type": "direct"
                    }
                )
            else:
                # 非流式响应
                result = await chat_manager.send_message(
                    session_id=session_id,
                    message=query,
                    stream=False
                )
                
                # 清理临时会话
                await chat_manager.delete_session(session_id)
                
                if not result["success"]:
                    raise HTTPException(
                        status_code=400,
                        detail=result["error"]
                    )
                
                return {
                    "success": True,
                    "agent_id": agent_id,
                    "query": query,
                    "response": result["response"],
                    "timestamp": result["timestamp"],
                    "context": context
                }
                
        except Exception as e:
            # 确保清理临时会话
            await chat_manager.delete_session(session_id)
            raise e
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"直接查询智能体失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"内部服务器错误: {str(e)}"
        )


@router.get("/agents", response_model=Dict[str, Any])
async def list_available_agents(
    current_user: Dict = Depends(get_current_user)
):
    """
    列出可用的智能体 - Agno API格式
    """
    try:
        # 这里应该从agent-service获取智能体列表
        # 目前返回硬编码的列表
        agents = [
            {
                "agent_id": "general-chat",
                "name": "通用聊天助手",
                "description": "提供通用对话能力的智能助手",
                "capabilities": ["chat", "qa", "general"],
                "status": "active"
            },
            {
                "agent_id": "analyst",
                "name": "专业分析师",
                "description": "提供深度分析和洞察的专业智能体",
                "capabilities": ["analysis", "insights", "data"],
                "status": "active"
            }
        ]
        
        return {
            "success": True,
            "agents": agents,
            "total": len(agents),
            "user_id": current_user["user_id"]
        }
        
    except Exception as e:
        logger.error(f"列出可用智能体失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"内部服务器错误: {str(e)}"
        )


@router.get("/status", response_model=Dict[str, Any])
async def get_chat_service_status(
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """
    获取聊天服务状态
    """
    try:
        is_healthy = chat_manager.is_healthy()
        agno_status = await chat_manager.agno.get_status()
        
        return {
            "success": True,
            "service": "chat-service",
            "status": "healthy" if is_healthy else "unhealthy",
            "agno_available": agno_status,
            "timestamp": asyncio.get_event_loop().time(),
            "version": "1.0.0"
        }
        
    except Exception as e:
        logger.error(f"获取服务状态失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"内部服务器错误: {str(e)}"
        ) 