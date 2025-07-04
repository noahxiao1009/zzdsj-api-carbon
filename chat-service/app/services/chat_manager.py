"""
聊天管理器 - 统一管理聊天会话和消息处理
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, AsyncGenerator, Union
from datetime import datetime, timedelta
import json
import uuid

from app.core.config import settings
from app.core.redis import redis_manager
from app.services.agno_integration import get_agno_integration, MessageRole

logger = logging.getLogger(__name__)


class VoiceService:
    """语音服务（简化版）"""
    
    async def initialize(self):
        """初始化语音服务"""
        logger.info("语音服务初始化完成")
    
    async def speech_to_text(self, audio_data: bytes, format: str = "wav") -> Optional[str]:
        """语音转文字"""
        # 这里应该集成实际的语音识别服务
        logger.info("执行语音转文字")
        return "这是语音识别的结果"
    
    async def text_to_speech(self, text: str, voice: str = "default") -> Optional[bytes]:
        """文字转语音"""
        # 这里应该集成实际的语音合成服务
        logger.info("执行文字转语音")
        return b"audio_data"


class ChatManager:
    """聊天管理器"""
    
    def __init__(self):
        self.voice_service = VoiceService()
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self._initialized = False
    
    async def initialize(self):
        """初始化聊天管理器"""
        if self._initialized:
            return
            
        try:
            logger.info("初始化聊天管理器...")
            
            # 检查Redis连接
            if not redis_manager.ping():
                logger.warning("Redis连接不可用")
            else:
                logger.info("Redis连接正常")
            
            # 初始化语音服务
            await self.voice_service.initialize()
            
            self._initialized = True
            logger.info("聊天管理器初始化完成")
            
        except Exception as e:
            logger.error(f"聊天管理器初始化失败: {e}")
            raise
    
    async def create_session(
        self,
        user_id: str,
        agent_id: Optional[str] = None,
        session_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """创建聊天会话"""
        try:
            # 获取Agno集成实例
            agno = await get_agno_integration()
            
            session_id = await agno.create_chat_session(
                user_id=user_id,
                agent_id=agent_id
            )
            
            session_info = {
                "session_id": session_id,
                "user_id": user_id,
                "agent_id": agent_id or "general-chat",
                "created_at": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat(),
                "config": session_config or {},
                "status": "active",
                "message_count": 0
            }
            
            # 缓存会话信息
            self.active_sessions[session_id] = session_info
            
            # 持久化会话信息到Redis
            session_key = f"chat_manager:session:{session_id}"
            redis_manager.set_json(session_key, session_info, ex=86400)  # 24小时过期
            
            logger.info(f"创建聊天会话成功: {session_id}")
            
            return {
                "success": True,
                "session_id": session_id,
                "session_info": session_info
            }
            
        except Exception as e:
            logger.error(f"创建聊天会话失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def send_message(
        self,
        session_id: str,
        message: str,
        message_type: str = "text",
        stream: bool = False,
        voice_config: Optional[Dict[str, Any]] = None
    ) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        """发送消息"""
        try:
            # 验证会话
            session_info = await self._get_session_info(session_id)
            if not session_info:
                return {
                    "success": False,
                    "error": f"会话 {session_id} 不存在"
                }
            
            # 处理语音消息
            processed_message = message
            if message_type == "voice" and voice_config:
                audio_data = voice_config.get("audio_data")
                if audio_data:
                    processed_message = await self.voice_service.speech_to_text(
                        audio_data,
                        voice_config.get("format", "wav")
                    )
                    if not processed_message:
                        return {
                            "success": False,
                            "error": "语音识别失败"
                        }
            
            # 获取Agno集成实例
            agno = await get_agno_integration()
            
            # 发送消息到Agno
            if stream:
                return self._stream_chat_response(session_id, processed_message, voice_config)
            else:
                response = await agno.send_message(
                    session_id=session_id,
                    message=processed_message,
                    role=MessageRole.USER,
                    stream=False
                )
                
                # 更新会话活动时间
                await self._update_session_activity(session_id)
                
                result = {
                    "success": response.get("success", True),
                    "session_id": session_id,
                    "message_id": response.get("message_id"),
                    "response": response.get("response", ""),
                    "timestamp": response.get("timestamp", datetime.now().isoformat()),
                    "agent_id": response.get("agent_id"),
                    "original_message": message,
                    "processed_message": processed_message if message_type == "voice" else None
                }
                
                # 处理语音响应
                if voice_config and voice_config.get("enable_tts") and result.get("success"):
                    response_text = result.get("response", "")
                    if response_text:
                        audio_response = await self.voice_service.text_to_speech(
                            response_text,
                            voice_config.get("voice", "default")
                        )
                        if audio_response:
                            result["audio_response"] = {
                                "format": "wav",
                                "data": audio_response.hex()  # 转换为十六进制字符串
                            }
                
                return result
                
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "session_id": session_id
            }
    
    async def _stream_chat_response(
        self,
        session_id: str,
        message: str,
        voice_config: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """流式聊天响应"""
        try:
            # 发送用户消息事件
            yield {
                "type": "user_message",
                "session_id": session_id,
                "message": message,
                "timestamp": datetime.now().isoformat()
            }
            
            # 获取Agno集成实例
            agno = await get_agno_integration()
            
            # 获取流式响应
            response_stream = agno.send_message(
                session_id=session_id,
                message=message,
                role=MessageRole.USER,
                stream=True
            )
            
            # 收集完整响应用于语音合成
            full_response = ""
            
            async for chunk in response_stream:
                if chunk.get("success", True):
                    chunk_text = chunk.get("chunk", "")
                    full_response += chunk_text
                    
                    yield {
                        "type": "assistant_chunk",
                        "session_id": session_id,
                        "chunk": chunk_text,
                        "finished": chunk.get("finished", False),
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    # 如果是最后一个块，处理语音合成
                    if chunk.get("finished", False):
                        # 更新会话活动时间
                        await self._update_session_activity(session_id)
                        
                        # 处理语音响应
                        if voice_config and voice_config.get("enable_tts") and full_response:
                            audio_response = await self.voice_service.text_to_speech(
                                full_response,
                                voice_config.get("voice", "default")
                            )
                            if audio_response:
                                yield {
                                    "type": "audio_response",
                                    "session_id": session_id,
                                    "audio": {
                                        "format": "wav",
                                        "data": audio_response.hex()
                                    },
                                    "timestamp": datetime.now().isoformat()
                                }
                        
                        # 发送完成事件
                        yield {
                            "type": "conversation_complete",
                            "session_id": session_id,
                            "full_response": full_response,
                            "timestamp": datetime.now().isoformat()
                        }
                else:
                    # 错误处理
                    yield {
                        "type": "error",
                        "session_id": session_id,
                        "error": chunk.get("error", "未知错误"),
                        "timestamp": datetime.now().isoformat()
                    }
                    break
            
        except Exception as e:
            logger.error(f"流式响应失败: {e}")
            yield {
                "type": "error",
                "session_id": session_id,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def get_session_history(
        self,
        session_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """获取会话历史"""
        try:
            # 验证会话
            session_info = await self._get_session_info(session_id)
            if not session_info:
                return {
                    "success": False,
                    "error": f"会话 {session_id} 不存在"
                }
            
            # 获取Agno集成实例
            agno = await get_agno_integration()
            
            # 获取完整历史
            all_history = await agno.get_session_history(session_id)
            
            # 应用分页
            total_count = len(all_history)
            start_idx = offset
            end_idx = offset + limit
            
            paginated_history = all_history[start_idx:end_idx]
            
            return {
                "success": True,
                "session_id": session_id,
                "messages": paginated_history,
                "pagination": {
                    "total": total_count,
                    "limit": limit,
                    "offset": offset,
                    "has_more": end_idx < total_count
                },
                "session_info": session_info
            }
            
        except Exception as e:
            logger.error(f"获取会话历史失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def list_user_sessions(
        self,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """列出用户会话"""
        try:
            user_sessions = []
            
            # 从内存中获取活跃会话
            for session_id, session_info in self.active_sessions.items():
                if session_info.get("user_id") == user_id:
                    if not status or session_info.get("status") == status:
                        user_sessions.append(session_info)
            
            # 从Redis中获取更多会话（简化实现）
            # 这里可以实现更复杂的索引和查询逻辑
            
            # 按创建时间排序
            user_sessions.sort(
                key=lambda x: x.get("created_at", ""), 
                reverse=True
            )
            
            # 应用分页
            total_count = len(user_sessions)
            start_idx = offset
            end_idx = offset + limit
            
            paginated_sessions = user_sessions[start_idx:end_idx]
            
            return {
                "success": True,
                "user_id": user_id,
                "sessions": paginated_sessions,
                "pagination": {
                    "total": total_count,
                    "limit": limit,
                    "offset": offset,
                    "has_more": end_idx < total_count
                }
            }
            
        except Exception as e:
            logger.error(f"列出用户会话失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def delete_session(self, session_id: str) -> Dict[str, Any]:
        """删除会话"""
        try:
            # 获取Agno集成实例
            agno = await get_agno_integration()
            
            # 从Agno中删除会话
            success = await agno.delete_session(session_id)
            
            # 从内存中删除
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
            
            # 从Redis中删除
            session_key = f"chat_manager:session:{session_id}"
            redis_manager.delete(session_key)
            
            if success:
                logger.info(f"会话 {session_id} 删除成功")
                return {
                    "success": True,
                    "session_id": session_id
                }
            else:
                return {
                    "success": False,
                    "error": "删除会话失败"
                }
                
        except Exception as e:
            logger.error(f"删除会话失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_available_agents(self) -> Dict[str, Any]:
        """获取可用智能体"""
        try:
            # 获取Agno集成实例
            agno = await get_agno_integration()
            
            agents = await agno.get_available_agents()
            
            return {
                "success": True,
                "agents": agents,
                "count": len(agents)
            }
            
        except Exception as e:
            logger.error(f"获取可用智能体失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话信息"""
        try:
            # 先从内存中查找
            if session_id in self.active_sessions:
                return self.active_sessions[session_id]
            
            # 从Redis中查找
            session_key = f"chat_manager:session:{session_id}"
            session_data = redis_manager.get_json(session_key)
            
            if session_data:
                # 缓存到内存
                self.active_sessions[session_id] = session_data
                return session_data
            
            return None
            
        except Exception as e:
            logger.error(f"获取会话信息失败: {e}")
            return None
    
    async def _update_session_activity(self, session_id: str):
        """更新会话活动时间"""
        try:
            session_info = await self._get_session_info(session_id)
            if session_info:
                session_info["last_activity"] = datetime.now().isoformat()
                session_info["message_count"] = session_info.get("message_count", 0) + 1
                
                # 更新内存缓存
                self.active_sessions[session_id] = session_info
                
                # 更新Redis缓存
                session_key = f"chat_manager:session:{session_id}"
                redis_manager.set_json(session_key, session_info, ex=86400)
                
        except Exception as e:
            logger.error(f"更新会话活动时间失败: {e}")
    
    async def get_service_status(self) -> Dict[str, Any]:
        """获取服务状态"""
        try:
            # 获取Agno集成状态
            agno = await get_agno_integration()
            agno_status = await agno.get_status()
            
            return {
                "chat_manager": {
                    "initialized": self._initialized,
                    "active_sessions": len(self.active_sessions),
                    "redis_available": redis_manager.ping()
                },
                "agno_integration": agno_status,
                "voice_service": {
                    "enabled": settings.voice_enabled
                },
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取服务状态失败: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def is_healthy(self) -> bool:
        """检查服务健康状态"""
        try:
            return (
                self._initialized and
                redis_manager.ping()
            )
        except Exception:
            return False
    
    async def cleanup(self):
        """清理资源"""
        try:
            logger.info("清理聊天管理器资源...")
            
            # 清理活跃会话
            self.active_sessions.clear()
            
            # 获取Agno集成实例并清理
            agno = await get_agno_integration()
            await agno.cleanup()
            
            logger.info("聊天管理器资源清理完成")
            
        except Exception as e:
            logger.error(f"清理聊天管理器资源失败: {e}")


# 全局聊天管理器实例
_chat_manager: Optional[ChatManager] = None


async def get_chat_manager() -> ChatManager:
    """获取聊天管理器实例"""
    global _chat_manager
    if _chat_manager is None:
        _chat_manager = ChatManager()
        await _chat_manager.initialize()
    return _chat_manager 