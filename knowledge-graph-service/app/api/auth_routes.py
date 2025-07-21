"""
认证API路由
提供JWT认证相关的API接口
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any
import logging

from ..utils.auth import create_jwt_token, authenticate_user

logger = logging.getLogger(__name__)

# 创建认证路由器
router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    """登录请求"""
    username: str
    password: str


class LoginResponse(BaseModel):
    """登录响应"""
    access_token: str
    token_type: str = "bearer"
    user_info: Dict[str, Any]


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """用户登录"""
    try:
        # 认证用户
        user_info = await authenticate_user(request.username, request.password)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # 创建JWT令牌
        token = create_jwt_token(user_info)
        
        return LoginResponse(
            access_token=token,
            user_info=user_info
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登录失败"
        )


@router.post("/test-token")
async def create_test_token():
    """创建测试令牌（仅用于开发）"""
    try:
        # 创建测试用户信息
        test_user = {
            "user_id": "test_user_001",
            "username": "test_user",
            "email": "test@example.com",
            "role": "user"
        }
        
        # 创建JWT令牌
        token = create_jwt_token(test_user)
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "user_info": test_user,
            "note": "这是测试令牌，仅用于开发环境"
        }
        
    except Exception as e:
        logger.error(f"Failed to create test token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="测试令牌创建失败"
        )


@router.get("/test-auth")
async def test_auth_endpoint():
    """测试认证端点（无需认证）"""
    return {
        "message": "认证服务正常运行",
        "timestamp": "2024-01-01T00:00:00Z",
        "service": "knowledge-graph-service"
    }