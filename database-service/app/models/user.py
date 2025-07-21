"""
用户模型模块: 包含用户、角色和权限相关的数据模型
"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table, func, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY
import uuid
from typing import Dict, Any, List, Optional

from .database import Base

# 用户角色关联表（多对多）
user_role = Table(
    "user_role",
    Base.metadata,
    Column("user_id", String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", String(36), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
)

# 角色权限关联表（多对多）
role_permission = Table(
    "role_permission",
    Base.metadata,
    Column("role_id", String(36), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", String(36), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)
)


class User(Base):
    """用户模型"""
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # 添加自增ID字段
    auto_id = Column(Integer, autoincrement=True, unique=True, index=True, comment="自增ID")
    username = Column(String(50), unique=True, index=True, nullable=False, comment="用户名")
    email = Column(String(100), unique=True, index=True, nullable=False, comment="邮箱")
    hashed_password = Column(String(255), nullable=False, comment="哈希密码")
    full_name = Column(String(100), comment="全名")
    disabled = Column(Boolean, default=False, comment="是否禁用")
    is_superuser = Column(Boolean, default=False, comment="是否超级管理员")
    last_login = Column(DateTime, comment="最后登录时间")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # 用户头像
    avatar_url = Column(String(255), comment="头像URL")
    
    # 用户偏好设置
    preferences = Column(Text, comment="用户偏好设置JSON")
    
    # 关联角色（多对多）
    roles = relationship("Role", secondary=user_role, back_populates="users")
    
    # 关联用户设置（一对一）
    settings = relationship("UserSettings", uselist=False, back_populates="user", cascade="all, delete-orphan")
    
    # 关联API密钥（一对多）
    api_keys = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "auto_id": self.auto_id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "disabled": self.disabled,
            "is_superuser": self.is_superuser,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "avatar_url": self.avatar_url,
            "roles": [role.name for role in self.roles] if self.roles else []
        }


class Role(Base):
    """角色模型"""
    __tablename__ = "roles"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(50), unique=True, nullable=False, comment="角色名称")
    description = Column(String(255), comment="角色描述")
    is_default = Column(Boolean, default=False, comment="是否默认角色")
    is_system = Column(Boolean, default=False, comment="是否系统角色")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # 关联用户（多对多）
    users = relationship("User", secondary=user_role, back_populates="roles")
    
    # 关联权限（多对多）
    permissions = relationship("Permission", secondary=role_permission, back_populates="roles")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "is_default": self.is_default,
            "is_system": self.is_system,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "permissions": [perm.code for perm in self.permissions] if self.permissions else []
        }


class Permission(Base):
    """权限模型"""
    __tablename__ = "permissions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(50), unique=True, nullable=False, comment="权限名称")
    code = Column(String(50), unique=True, nullable=False, comment="权限代码")
    description = Column(String(255), comment="权限描述")
    resource = Column(String(50), comment="资源类型")
    action = Column(String(50), comment="操作类型")
    is_system = Column(Boolean, default=False, comment="是否系统权限")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # 关联角色（多对多）
    roles = relationship("Role", secondary=role_permission, back_populates="permissions")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "description": self.description,
            "resource": self.resource,
            "action": self.action,
            "is_system": self.is_system,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class UserSettings(Base):
    """用户设置模型"""
    __tablename__ = "user_settings"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, nullable=False, comment="用户ID")
    theme = Column(String(20), default="light", comment="UI主题")
    language = Column(String(10), default="zh-CN", comment="界面语言")
    timezone = Column(String(50), default="Asia/Shanghai", comment="时区")
    notification_enabled = Column(Boolean, default=True, comment="是否启用通知")
    email_notification = Column(Boolean, default=True, comment="是否启用邮件通知")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # 关联用户（一对一）
    user = relationship("User", back_populates="settings")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "theme": self.theme,
            "language": self.language,
            "timezone": self.timezone,
            "notification_enabled": self.notification_enabled,
            "email_notification": self.email_notification,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class ApiKey(Base):
    """API密钥模型"""
    __tablename__ = "api_keys"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment="用户ID")
    key = Column(String(64), unique=True, nullable=False, comment="API密钥")
    name = Column(String(100), comment="密钥名称")
    description = Column(String(255), comment="密钥描述")
    is_active = Column(Boolean, default=True, comment="是否激活")
    expires_at = Column(DateTime, comment="过期时间")
    last_used_at = Column(DateTime, comment="最后使用时间")
    usage_count = Column(Integer, default=0, comment="使用次数")
    rate_limit = Column(Integer, comment="速率限制（每小时请求数）")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # 关联用户（多对一）
    user = relationship("User", back_populates="api_keys")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "key": self.key[:8] + "..." if self.key else None,  # 只显示前8位
            "name": self.name,
            "description": self.description,
            "is_active": self.is_active,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "usage_count": self.usage_count,
            "rate_limit": self.rate_limit,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    def is_expired(self) -> bool:
        """检查API密钥是否过期"""
        if not self.expires_at:
            return False
        from datetime import datetime
        return datetime.utcnow() > self.expires_at


class UserSession(Base):
    """用户会话模型"""
    __tablename__ = "user_sessions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment="用户ID")
    session_token = Column(String(255), unique=True, nullable=False, comment="会话令牌")
    ip_address = Column(String(45), comment="IP地址")
    user_agent = Column(Text, comment="用户代理")
    is_active = Column(Boolean, default=True, comment="是否活跃")
    expires_at = Column(DateTime, nullable=False, comment="过期时间")
    last_activity = Column(DateTime, server_default=func.now(), comment="最后活动时间")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    
    # 关联用户
    user = relationship("User")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "session_token": self.session_token[:16] + "..." if self.session_token else None,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "is_active": self.is_active,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    def is_expired(self) -> bool:
        """检查会话是否过期"""
        from datetime import datetime
        return datetime.utcnow() > self.expires_at