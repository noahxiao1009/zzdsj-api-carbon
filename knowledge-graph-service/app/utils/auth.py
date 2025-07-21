"""
认证工具模块
提供JWT认证和用户权限验证功能
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import jwt
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..config.settings import settings

logger = logging.getLogger(__name__)

# JWT配置
JWT_SECRET_KEY = settings.JWT_SECRET_KEY
JWT_ALGORITHM = settings.JWT_ALGORITHM
JWT_EXPIRATION_HOURS = settings.JWT_EXPIRATION_HOURS

# 安全方案
security = HTTPBearer()


class AuthenticationError(Exception):
    """认证错误"""
    pass


class AuthorizationError(Exception):
    """授权错误"""
    pass


def create_jwt_token(user_data: Dict[str, Any]) -> str:
    """创建JWT令牌
    
    Args:
        user_data: 用户数据
        
    Returns:
        JWT令牌字符串
    """
    try:
        # 设置过期时间
        expiration = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
        
        # 创建载荷
        payload = {
            "user_id": user_data.get("user_id"),
            "username": user_data.get("username"),
            "email": user_data.get("email"),
            "role": user_data.get("role", "user"),
            "exp": expiration,
            "iat": datetime.utcnow(),
            "iss": "knowledge-graph-service"
        }
        
        # 编码JWT
        token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        
        logger.info(f"Created JWT token for user {user_data.get('user_id')}")
        return token
        
    except Exception as e:
        logger.error(f"Failed to create JWT token: {e}")
        raise AuthenticationError("令牌创建失败")


def verify_jwt_token(token: str) -> Dict[str, Any]:
    """验证JWT令牌
    
    Args:
        token: JWT令牌
        
    Returns:
        解码后的用户数据
        
    Raises:
        AuthenticationError: 令牌验证失败
    """
    try:
        # 解码JWT
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        
        # 检查必要字段
        if not payload.get("user_id"):
            raise AuthenticationError("令牌格式无效")
        
        # 检查发行者（接受多个可信发行者）
        trusted_issuers = [
            "knowledge-graph-service",
            "gateway-service", 
            "base-service",
            "auth-service"
        ]
        if payload.get("iss") and payload.get("iss") not in trusted_issuers:
            logger.warning(f"Unknown issuer: {payload.get('iss')}, but accepting for compatibility")
            # raise AuthenticationError("令牌发行者无效")
        
        logger.debug(f"Verified JWT token for user {payload.get('user_id')}")
        return payload
        
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("令牌已过期")
    except jwt.InvalidTokenError:
        raise AuthenticationError("令牌无效")
    except Exception as e:
        logger.error(f"Failed to verify JWT token: {e}")
        raise AuthenticationError("令牌验证失败")


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """获取当前用户信息
    
    Args:
        credentials: HTTP认证凭据
        
    Returns:
        当前用户信息
        
    Raises:
        HTTPException: 认证失败
    """
    try:
        # 提取令牌
        token = credentials.credentials
        
        # 验证令牌
        user_data = verify_jwt_token(token)
        
        return user_data
        
    except AuthenticationError as e:
        logger.warning(f"Authentication failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        logger.error(f"Unexpected authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证失败",
            headers={"WWW-Authenticate": "Bearer"}
        )


async def get_current_admin_user(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """获取当前管理员用户
    
    Args:
        current_user: 当前用户信息
        
    Returns:
        管理员用户信息
        
    Raises:
        HTTPException: 权限不足
    """
    try:
        if current_user.get("role") != "admin":
            raise AuthorizationError("需要管理员权限")
        
        return current_user
        
    except AuthorizationError as e:
        logger.warning(f"Authorization failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )


def require_permission(permission: str):
    """权限装饰器
    
    Args:
        permission: 所需权限
        
    Returns:
        装饰器函数
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # 从kwargs中获取当前用户
            current_user = kwargs.get("current_user")
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="认证信息缺失"
                )
            
            # 检查权限
            user_permissions = current_user.get("permissions", [])
            if permission not in user_permissions and current_user.get("role") != "admin":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"需要权限: {permission}"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def validate_project_access(user_id: str, project_owner_id: str, required_role: str = "viewer") -> bool:
    """验证项目访问权限
    
    Args:
        user_id: 用户ID
        project_owner_id: 项目所有者ID
        required_role: 所需角色
        
    Returns:
        是否有权限
    """
    try:
        # 项目所有者拥有所有权限
        if user_id == project_owner_id:
            return True
        
        # TODO: 实现更复杂的项目权限检查
        # 这里可以查询数据库获取用户在项目中的角色
        
        return False
        
    except Exception as e:
        logger.error(f"Failed to validate project access: {e}")
        return False


def validate_graph_access(user_id: str, graph_creator_id: str, required_role: str = "viewer") -> bool:
    """验证图谱访问权限
    
    Args:
        user_id: 用户ID
        graph_creator_id: 图谱创建者ID
        required_role: 所需角色
        
    Returns:
        是否有权限
    """
    try:
        # 图谱创建者拥有所有权限
        if user_id == graph_creator_id:
            return True
        
        # TODO: 实现更复杂的图谱权限检查
        
        return False
        
    except Exception as e:
        logger.error(f"Failed to validate graph access: {e}")
        return False


def create_service_token(service_name: str) -> str:
    """创建服务间通信令牌
    
    Args:
        service_name: 服务名称
        
    Returns:
        服务令牌
    """
    try:
        # 设置过期时间（服务令牌有效期较长）
        expiration = datetime.utcnow() + timedelta(days=30)
        
        # 创建载荷
        payload = {
            "service_name": service_name,
            "type": "service",
            "exp": expiration,
            "iat": datetime.utcnow(),
            "iss": "knowledge-graph-service"
        }
        
        # 编码JWT
        token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        
        logger.info(f"Created service token for {service_name}")
        return token
        
    except Exception as e:
        logger.error(f"Failed to create service token: {e}")
        raise AuthenticationError("服务令牌创建失败")


def verify_service_token(token: str) -> Dict[str, Any]:
    """验证服务令牌
    
    Args:
        token: 服务令牌
        
    Returns:
        解码后的服务信息
        
    Raises:
        AuthenticationError: 令牌验证失败
    """
    try:
        # 解码JWT
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        
        # 检查令牌类型
        if payload.get("type") != "service":
            raise AuthenticationError("令牌类型无效")
        
        # 检查服务名称
        if not payload.get("service_name"):
            raise AuthenticationError("服务名称缺失")
        
        logger.debug(f"Verified service token for {payload.get('service_name')}")
        return payload
        
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("服务令牌已过期")
    except jwt.InvalidTokenError:
        raise AuthenticationError("服务令牌无效")
    except Exception as e:
        logger.error(f"Failed to verify service token: {e}")
        raise AuthenticationError("服务令牌验证失败")


async def get_service_identity(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """获取服务身份信息
    
    Args:
        credentials: HTTP认证凭据
        
    Returns:
        服务身份信息
        
    Raises:
        HTTPException: 认证失败
    """
    try:
        # 提取令牌
        token = credentials.credentials
        
        # 验证服务令牌
        service_data = verify_service_token(token)
        
        return service_data
        
    except AuthenticationError as e:
        logger.warning(f"Service authentication failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        logger.error(f"Unexpected service authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="服务认证失败",
            headers={"WWW-Authenticate": "Bearer"}
        )


def hash_password(password: str) -> str:
    """密码哈希（占位实现）
    
    Args:
        password: 明文密码
        
    Returns:
        哈希后的密码
    """
    import hashlib
    import secrets
    
    # 生成盐值
    salt = secrets.token_hex(16)
    
    # 哈希密码
    password_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    
    return f"{salt}:{password_hash.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    """验证密码（占位实现）
    
    Args:
        password: 明文密码
        password_hash: 哈希后的密码
        
    Returns:
        密码是否正确
    """
    import hashlib
    
    try:
        salt, hash_value = password_hash.split(':')
        password_hash_check = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return password_hash_check.hex() == hash_value
    except Exception:
        return False


# 示例用户数据（实际应该从数据库获取）
DEMO_USERS = {
    "admin": {
        "user_id": "admin_001",
        "username": "admin",
        "email": "admin@example.com",
        "role": "admin",
        "password_hash": hash_password("admin123"),
        "permissions": ["read", "write", "admin"]
    },
    "user1": {
        "user_id": "user_001",
        "username": "user1",
        "email": "user1@example.com",
        "role": "user",
        "password_hash": hash_password("user123"),
        "permissions": ["read", "write"]
    }
}


async def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """用户认证（示例实现）
    
    Args:
        username: 用户名
        password: 密码
        
    Returns:
        用户信息或None
    """
    try:
        user_data = DEMO_USERS.get(username)
        if not user_data:
            return None
        
        if not verify_password(password, user_data["password_hash"]):
            return None
        
        # 返回用户信息（不包含密码）
        user_info = {k: v for k, v in user_data.items() if k != "password_hash"}
        
        logger.info(f"User {username} authenticated successfully")
        return user_info
        
    except Exception as e:
        logger.error(f"Authentication failed for user {username}: {e}")
        return None