"""
依赖注入 - FastAPI依赖项定义
"""

import logging
from typing import Dict, Any, Optional
from fastapi import Depends, HTTPException, Header
from app.services.chat_manager import get_chat_manager
from app.services.message_renderer import get_message_renderer

logger = logging.getLogger(__name__)

async def get_current_user(
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """
    获取当前用户信息
    
    支持两种认证方式：
    1. Authorization header (JWT token)
    2. X-User-ID header (简化开发模式)
    """
    
    # 简化开发模式：直接使用用户ID
    if x_user_id:
        return {
            "user_id": x_user_id,
            "username": f"user_{x_user_id}",
            "role": "user"
        }
    
    # JWT认证模式
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        
        try:
            # 这里应该验证JWT token
            # 目前简化为模拟用户
            return {
                "user_id": "mock_user_123",
                "username": "mock_user",
                "role": "user",
                "token": token
            }
        except Exception as e:
            logger.error(f"Token验证失败: {e}")
            raise HTTPException(
                status_code=401,
                detail="无效的认证token"
            )
    
    # 开发模式：返回默认用户
    return {
        "user_id": "dev_user",
        "username": "dev_user",
        "role": "user"
    }


def get_chat_manager_dependency():
    """获取聊天管理器依赖"""
    return Depends(get_chat_manager)


def get_message_renderer_dependency():
    """获取消息渲染器依赖"""
    return Depends(get_message_renderer)


async def validate_session_access(
    session_id: str,
    current_user: Dict = Depends(get_current_user),
    chat_manager = Depends(get_chat_manager)
) -> bool:
    """验证会话访问权限"""
    try:
        user_id = current_user["user_id"]
        session_info = await chat_manager._get_session_info(session_id)
        
        if not session_info:
            raise HTTPException(
                status_code=404,
                detail="会话不存在"
            )
        
        if session_info.get("user_id") != user_id:
            raise HTTPException(
                status_code=403,
                detail="无权限访问该会话"
            )
        
        return True
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"会话权限验证失败: {e}")
        raise HTTPException(
            status_code=500,
            detail="权限验证失败"
        )


async def validate_agent_access(
    agent_id: str,
    current_user: Dict = Depends(get_current_user)
) -> bool:
    """验证智能体访问权限"""
    try:
        # 这里应该调用base-service检查用户权限
        # 目前简化为允许所有访问
        return True
        
    except Exception as e:
        logger.error(f"智能体权限验证失败: {e}")
        raise HTTPException(
            status_code=500,
            detail="权限验证失败"
        )


def get_request_context(
    user_agent: Optional[str] = Header(None),
    x_forwarded_for: Optional[str] = Header(None),
    x_real_ip: Optional[str] = Header(None),
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """获取请求上下文信息"""
    return {
        "user_id": current_user["user_id"],
        "user_agent": user_agent,
        "client_ip": x_real_ip or x_forwarded_for or "unknown",
        "request_id": f"req_{current_user['user_id']}_{hash(user_agent or '')}",
        "user_info": current_user
    }