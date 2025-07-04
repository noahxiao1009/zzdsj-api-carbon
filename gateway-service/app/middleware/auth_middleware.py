"""
前端用户认证中间件
处理JWT Token验证和用户身份认证
"""

import jwt
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

# JWT配置
JWT_SECRET_KEY = "your-secret-key-here"  # 应从环境变量获取
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_DELTA = timedelta(hours=24)

# HTTP Bearer scheme
bearer_scheme = HTTPBearer()


class TokenManager:
    """Token管理器"""
    
    def __init__(self, secret_key: str = JWT_SECRET_KEY, algorithm: str = JWT_ALGORITHM):
        self.secret_key = secret_key
        self.algorithm = algorithm
    
    def create_token(self, user_data: Dict[str, Any]) -> str:
        """创建JWT Token"""
        try:
            payload = {
                "user_id": user_data.get("user_id"),
                "username": user_data.get("username"),
                "email": user_data.get("email"),
                "roles": user_data.get("roles", []),
                "permissions": user_data.get("permissions", []),
                "exp": datetime.utcnow() + JWT_EXPIRATION_DELTA,
                "iat": datetime.utcnow(),
                "type": "access_token"
            }
            
            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            return token
            
        except Exception as e:
            logger.error(f"创建Token失败: {str(e)}")
            raise
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """验证JWT Token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # 检查token类型
            if payload.get("type") != "access_token":
                raise jwt.InvalidTokenError("Invalid token type")
            
            # 检查过期时间
            exp = payload.get("exp")
            if exp and datetime.utcnow().timestamp() > exp:
                raise jwt.ExpiredSignatureError("Token has expired")
            
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token已过期")
            raise HTTPException(status_code=401, detail="Token已过期")
        except jwt.InvalidTokenError as e:
            logger.warning(f"无效的Token: {str(e)}")
            raise HTTPException(status_code=401, detail="无效的Token")
        except Exception as e:
            logger.error(f"Token验证失败: {str(e)}")
            raise HTTPException(status_code=401, detail="Token验证失败")
    
    def refresh_token(self, token: str) -> str:
        """刷新Token"""
        try:
            payload = self.verify_token(token)
            
            # 创建新的Token
            user_data = {
                "user_id": payload.get("user_id"),
                "username": payload.get("username"),
                "email": payload.get("email"),
                "roles": payload.get("roles", []),
                "permissions": payload.get("permissions", [])
            }
            
            return self.create_token(user_data)
            
        except Exception as e:
            logger.error(f"Token刷新失败: {str(e)}")
            raise HTTPException(status_code=401, detail="Token刷新失败")


# 全局Token管理器实例
token_manager = TokenManager()


async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> Dict[str, Any]:
    """验证用户Token的依赖函数"""
    try:
        token = credentials.credentials
        user_data = token_manager.verify_token(token)
        
        # 记录用户访问日志
        logger.info(f"用户 {user_data.get('username')} 访问API")
        
        return user_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token验证失败: {str(e)}")
        raise HTTPException(status_code=401, detail="认证失败")


async def verify_token_optional(request: Request) -> Optional[Dict[str, Any]]:
    """可选的Token验证（不强制要求登录）"""
    try:
        auth_header = request.headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None
        
        token = auth_header.split(" ")[1]
        user_data = token_manager.verify_token(token)
        return user_data
        
    except Exception:
        # 可选验证，失败时返回None而不是抛出异常
        return None


def require_roles(required_roles: list):
    """角色验证装饰器"""
    async def role_dependency(current_user: Dict[str, Any] = Depends(verify_token)):
        user_roles = current_user.get("roles", [])
        
        # 检查是否有所需角色
        if not any(role in user_roles for role in required_roles):
            raise HTTPException(
                status_code=403,
                detail=f"需要以下角色之一: {', '.join(required_roles)}"
            )
        
        return current_user
    
    return role_dependency


def require_permissions(required_permissions: list):
    """权限验证装饰器"""
    async def permission_dependency(current_user: Dict[str, Any] = Depends(verify_token)):
        user_permissions = current_user.get("permissions", [])
        
        # 检查是否有所需权限
        missing_permissions = [perm for perm in required_permissions if perm not in user_permissions]
        if missing_permissions:
            raise HTTPException(
                status_code=403,
                detail=f"缺少权限: {', '.join(missing_permissions)}"
            )
        
        return current_user
    
    return permission_dependency


class AdminRequired:
    """管理员权限验证"""
    
    @staticmethod
    async def __call__(current_user: Dict[str, Any] = Depends(verify_token)):
        user_roles = current_user.get("roles", [])
        
        if "admin" not in user_roles and "super_admin" not in user_roles:
            raise HTTPException(
                status_code=403,
                detail="需要管理员权限"
            )
        
        return current_user


# 创建实例供外部使用
admin_required = AdminRequired()


def create_user_token(user_data: Dict[str, Any]) -> str:
    """创建用户Token（供外部调用）"""
    return token_manager.create_token(user_data)


def verify_user_token(token: str) -> Dict[str, Any]:
    """验证用户Token（供外部调用）"""
    return token_manager.verify_token(token)


def refresh_user_token(token: str) -> str:
    """刷新用户Token（供外部调用）"""
    return token_manager.refresh_token(token) 