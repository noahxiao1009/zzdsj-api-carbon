"""
JWT处理器

负责JWT Token的生成、验证和管理
"""

import jwt
import time
import secrets
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

from app.utils.common.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class JWTConfig:
    """JWT配置"""
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    issuer: str = "zzdsj-gateway"
    audience: str = "zzdsj-services"


@dataclass
class TokenPair:
    """Token对"""
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "Bearer"


class JWTHandler:
    """JWT处理器"""
    
    def __init__(self, config: Optional[JWTConfig] = None):
        if config is None:
            # 默认配置
            config = JWTConfig(
                secret_key=self._generate_secret_key(),
                algorithm="HS256",
                access_token_expire_minutes=30,
                refresh_token_expire_days=7
            )
        
        self.config = config
        self.blacklisted_tokens: set = set()
        
        logger.info("JWT处理器已初始化")
    
    def _generate_secret_key(self) -> str:
        """生成安全密钥"""
        return secrets.token_urlsafe(32)
    
    def create_access_token(
        self, 
        subject: str, 
        user_id: Optional[str] = None,
        roles: Optional[List[str]] = None,
        permissions: Optional[List[str]] = None,
        extra_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """创建访问令牌"""
        now = datetime.utcnow()
        expire = now + timedelta(minutes=self.config.access_token_expire_minutes)
        
        payload = {
            "sub": subject,
            "iat": now,
            "exp": expire,
            "iss": self.config.issuer,
            "aud": self.config.audience,
            "type": "access",
            "jti": secrets.token_urlsafe(16)  # JWT ID
        }
        
        # 添加用户相关信息
        if user_id:
            payload["user_id"] = user_id
        if roles:
            payload["roles"] = roles
        if permissions:
            payload["permissions"] = permissions
        
        # 添加额外声明
        if extra_claims:
            payload.update(extra_claims)
        
        try:
            token = jwt.encode(
                payload, 
                self.config.secret_key, 
                algorithm=self.config.algorithm
            )
            logger.debug(f"创建访问令牌成功: {subject}")
            return token
        except Exception as e:
            logger.error(f"创建访问令牌失败: {str(e)}")
            raise
    
    def create_refresh_token(
        self, 
        subject: str, 
        user_id: Optional[str] = None
    ) -> str:
        """创建刷新令牌"""
        now = datetime.utcnow()
        expire = now + timedelta(days=self.config.refresh_token_expire_days)
        
        payload = {
            "sub": subject,
            "iat": now,
            "exp": expire,
            "iss": self.config.issuer,
            "aud": self.config.audience,
            "type": "refresh",
            "jti": secrets.token_urlsafe(16)
        }
        
        if user_id:
            payload["user_id"] = user_id
        
        try:
            token = jwt.encode(
                payload, 
                self.config.secret_key, 
                algorithm=self.config.algorithm
            )
            logger.debug(f"创建刷新令牌成功: {subject}")
            return token
        except Exception as e:
            logger.error(f"创建刷新令牌失败: {str(e)}")
            raise
    
    def create_token_pair(
        self, 
        subject: str, 
        user_id: Optional[str] = None,
        roles: Optional[List[str]] = None,
        permissions: Optional[List[str]] = None,
        extra_claims: Optional[Dict[str, Any]] = None
    ) -> TokenPair:
        """创建Token对"""
        access_token = self.create_access_token(
            subject=subject,
            user_id=user_id,
            roles=roles,
            permissions=permissions,
            extra_claims=extra_claims
        )
        
        refresh_token = self.create_refresh_token(
            subject=subject,
            user_id=user_id
        )
        
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self.config.access_token_expire_minutes * 60,
            token_type="Bearer"
        )
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """验证令牌"""
        try:
            # 检查是否在黑名单中
            if token in self.blacklisted_tokens:
                raise jwt.InvalidTokenError("Token已被撤销")
            
            payload = jwt.decode(
                token,
                self.config.secret_key,
                algorithms=[self.config.algorithm],
                audience=self.config.audience,
                issuer=self.config.issuer
            )
            
            logger.debug(f"令牌验证成功: {payload.get('sub')}")
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("令牌已过期")
            raise
        except jwt.InvalidTokenError as e:
            logger.warning(f"无效令牌: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"令牌验证失败: {str(e)}")
            raise
    
    def decode_token_without_verification(self, token: str) -> Dict[str, Any]:
        """不验证地解码令牌（用于获取过期令牌信息）"""
        try:
            payload = jwt.decode(
                token,
                options={"verify_signature": False, "verify_exp": False}
            )
            return payload
        except Exception as e:
            logger.error(f"令牌解码失败: {str(e)}")
            raise
    
    def refresh_access_token(self, refresh_token: str) -> str:
        """使用刷新令牌获取新的访问令牌"""
        try:
            payload = self.verify_token(refresh_token)
            
            # 检查是否为刷新令牌
            if payload.get("type") != "refresh":
                raise jwt.InvalidTokenError("不是有效的刷新令牌")
            
            # 创建新的访问令牌
            subject = payload.get("sub")
            user_id = payload.get("user_id")
            
            # 注意：这里需要重新获取用户的最新角色和权限
            # 在实际应用中，应该从数据库获取用户的最新权限信息
            new_access_token = self.create_access_token(
                subject=subject,
                user_id=user_id
            )
            
            logger.info(f"刷新令牌成功: {subject}")
            return new_access_token
            
        except Exception as e:
            logger.error(f"刷新令牌失败: {str(e)}")
            raise
    
    def revoke_token(self, token: str) -> bool:
        """撤销令牌"""
        try:
            # 将令牌添加到黑名单
            self.blacklisted_tokens.add(token)
            
            # 解码令牌获取信息
            payload = self.decode_token_without_verification(token)
            subject = payload.get("sub", "unknown")
            
            logger.info(f"令牌已撤销: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"撤销令牌失败: {str(e)}")
            return False
    
    def is_token_revoked(self, token: str) -> bool:
        """检查令牌是否已被撤销"""
        return token in self.blacklisted_tokens
    
    def get_token_info(self, token: str) -> Dict[str, Any]:
        """获取令牌信息"""
        try:
            payload = self.verify_token(token)
            
            info = {
                "subject": payload.get("sub"),
                "user_id": payload.get("user_id"),
                "roles": payload.get("roles", []),
                "permissions": payload.get("permissions", []),
                "issued_at": payload.get("iat"),
                "expires_at": payload.get("exp"),
                "token_type": payload.get("type"),
                "jwt_id": payload.get("jti"),
                "issuer": payload.get("iss"),
                "audience": payload.get("aud"),
                "is_expired": False,
                "is_revoked": self.is_token_revoked(token)
            }
            
            return info
            
        except jwt.ExpiredSignatureError:
            # 即使过期也返回基本信息
            payload = self.decode_token_without_verification(token)
            return {
                "subject": payload.get("sub"),
                "user_id": payload.get("user_id"),
                "token_type": payload.get("type"),
                "jwt_id": payload.get("jti"),
                "is_expired": True,
                "is_revoked": self.is_token_revoked(token)
            }
        except Exception as e:
            logger.error(f"获取令牌信息失败: {str(e)}")
            return {
                "is_expired": None,
                "is_revoked": self.is_token_revoked(token),
                "error": str(e)
            }
    
    def cleanup_blacklist(self):
        """清理黑名单中的过期令牌"""
        expired_tokens = set()
        
        for token in self.blacklisted_tokens:
            try:
                payload = self.decode_token_without_verification(token)
                exp = payload.get("exp")
                
                if exp and datetime.fromtimestamp(exp) < datetime.utcnow():
                    expired_tokens.add(token)
                    
            except Exception:
                # 无法解码的令牌也移除
                expired_tokens.add(token)
        
        self.blacklisted_tokens -= expired_tokens
        
        if expired_tokens:
            logger.info(f"清理过期黑名单令牌: {len(expired_tokens)}个")
    
    def validate_claims(
        self, 
        token: str, 
        required_roles: Optional[List[str]] = None,
        required_permissions: Optional[List[str]] = None
    ) -> bool:
        """验证令牌的角色和权限声明"""
        try:
            payload = self.verify_token(token)
            
            # 检查角色
            if required_roles:
                user_roles = payload.get("roles", [])
                if not any(role in user_roles for role in required_roles):
                    logger.warning(f"用户角色不足: 需要{required_roles}, 拥有{user_roles}")
                    return False
            
            # 检查权限
            if required_permissions:
                user_permissions = payload.get("permissions", [])
                if not all(perm in user_permissions for perm in required_permissions):
                    logger.warning(f"用户权限不足: 需要{required_permissions}, 拥有{user_permissions}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"验证声明失败: {str(e)}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "blacklisted_tokens": len(self.blacklisted_tokens),
            "token_expire_minutes": self.config.access_token_expire_minutes,
            "refresh_expire_days": self.config.refresh_token_expire_days,
            "algorithm": self.config.algorithm,
            "issuer": self.config.issuer,
            "audience": self.config.audience
        } 