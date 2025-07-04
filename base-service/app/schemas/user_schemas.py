"""
Base-Service用户管理Schema定义
基于原始项目的用户schema，提供完整的用户、角色、权限管理数据验证
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, EmailStr, Field, validator, root_validator
import re


# ===== 枚举类型定义 =====

class UserStatus(str, Enum):
    """用户状态枚举"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"


class UserType(str, Enum):
    """用户类型枚举"""
    REGULAR = "regular"
    ADMIN = "admin"
    SYSTEM = "system"
    SERVICE = "service"


class RoleType(str, Enum):
    """角色类型枚举"""
    SYSTEM = "system"
    CUSTOM = "custom"
    DEFAULT = "default"


class PermissionScope(str, Enum):
    """权限范围枚举"""
    GLOBAL = "global"
    ORGANIZATION = "organization"
    PROJECT = "project"
    RESOURCE = "resource"


class AccessLevel(str, Enum):
    """访问级别枚举"""
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    OWNER = "owner"


# ===== 基础Schema类 =====

class BaseSchema(BaseModel):
    """基础Schema类"""
    class Config:
        from_attributes = True
        use_enum_values = True
        arbitrary_types_allowed = True


# ===== 分页和过滤Schema =====

class PaginationParams(BaseSchema):
    """分页参数"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页大小")
    
    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


# ===== 用户相关Schema =====

class UserCreate(BaseSchema):
    """用户创建请求"""
    username: str = Field(..., min_length=3, max_length=20, description="用户名")
    email: str = Field(..., description="邮箱地址")
    password: str = Field(..., min_length=8, max_length=64, description="密码")
    confirm_password: str = Field(..., description="确认密码")
    full_name: Optional[str] = Field(None, max_length=100, description="全名")
    nickname: Optional[str] = Field(None, max_length=50, description="昵称")
    phone: Optional[str] = Field(None, description="手机号码")
    user_type: Optional[UserType] = Field(UserType.REGULAR, description="用户类型")
    status: Optional[UserStatus] = Field(UserStatus.ACTIVE, description="用户状态")
    roles: Optional[List[str]] = Field(default_factory=list, description="角色ID列表")
    
    @validator('username')
    def validate_username(cls, v):
        if not v or not v.strip():
            raise ValueError('用户名不能为空')
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('用户名只能包含字母、数字和下划线')
        if v[0].isdigit():
            raise ValueError('用户名不能以数字开头')
        return v.lower()

    @validator('email')
    def validate_email(cls, v):
        if not v or not v.strip():
            raise ValueError('邮箱地址不能为空')
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v.strip()):
            raise ValueError('邮箱格式不正确')
        return v.lower().strip()

    @validator('password')
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('密码长度至少为8个字符')
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        has_special = any(c in "!@#$%^&*(),.?\":{}|<>" for c in v)
        complexity_count = sum([has_upper, has_lower, has_digit, has_special])
        if complexity_count < 3:
            raise ValueError('密码必须包含以下至少3种类型：大写字母、小写字母、数字、特殊字符')
        weak_passwords = ['12345678', 'password', 'qwerty123', '11111111']
        if v.lower() in weak_passwords:
            raise ValueError('密码过于简单，请使用更复杂的密码')
        return v

    @validator('confirm_password')
    def passwords_match(cls, v, values, **kwargs):
        if 'password' in values and v != values['password']:
            raise ValueError('密码确认不匹配')
        return v


class UserUpdate(BaseSchema):
    """用户更新请求"""
    email: Optional[str] = Field(None, description="邮箱地址")
    full_name: Optional[str] = Field(None, max_length=100, description="全名")
    nickname: Optional[str] = Field(None, max_length=50, description="昵称")
    phone: Optional[str] = Field(None, description="手机号码")
    avatar_url: Optional[str] = Field(None, description="头像URL")
    bio: Optional[str] = Field(None, max_length=200, description="个人简介")
    status: Optional[UserStatus] = Field(None, description="用户状态")
    user_type: Optional[UserType] = Field(None, description="用户类型")


class PasswordUpdate(BaseSchema):
    """密码更新请求"""
    current_password: str = Field(..., description="当前密码")
    new_password: str = Field(..., min_length=8, max_length=64, description="新密码")
    confirm_password: str = Field(..., description="确认新密码")
    
    @validator('new_password')
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('密码长度至少为8个字符')
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        has_special = any(c in "!@#$%^&*(),.?\":{}|<>" for c in v)
        complexity_count = sum([has_upper, has_lower, has_digit, has_special])
        if complexity_count < 3:
            raise ValueError('密码必须包含以下至少3种类型：大写字母、小写字母、数字、特殊字符')
        return v

    @validator('confirm_password')
    def passwords_match(cls, v, values, **kwargs):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('密码确认不匹配')
        return v


# ===== 角色相关Schema =====

class RoleCreate(BaseSchema):
    """角色创建请求"""
    name: str = Field(..., min_length=2, max_length=50, description="角色名称")
    description: Optional[str] = Field(None, description="角色描述")
    role_type: Optional[RoleType] = Field(RoleType.CUSTOM, description="角色类型")
    is_default: Optional[bool] = Field(False, description="是否为默认角色")
    permissions: Optional[List[str]] = Field(default_factory=list, description="权限ID列表")


class RoleUpdate(BaseSchema):
    """角色更新请求"""
    name: Optional[str] = Field(None, min_length=2, max_length=50, description="角色名称")
    description: Optional[str] = Field(None, description="角色描述")
    is_default: Optional[bool] = Field(None, description="是否为默认角色")
    role_type: Optional[RoleType] = Field(None, description="角色类型")


# ===== 权限相关Schema =====

class PermissionCreate(BaseSchema):
    """权限创建请求"""
    name: str = Field(..., min_length=2, max_length=50, description="权限名称")
    code: str = Field(..., min_length=2, max_length=50, description="权限代码")
    description: Optional[str] = Field(None, description="权限描述")
    resource: Optional[str] = Field(None, description="资源类型")
    scope: Optional[PermissionScope] = Field(PermissionScope.GLOBAL, description="权限范围")
    category: Optional[str] = Field(None, description="权限分类")


class PermissionUpdate(BaseSchema):
    """权限更新请求"""
    name: Optional[str] = Field(None, min_length=2, max_length=50, description="权限名称")
    description: Optional[str] = Field(None, description="权限描述")
    resource: Optional[str] = Field(None, description="资源类型")
    scope: Optional[PermissionScope] = Field(None, description="权限范围")
    category: Optional[str] = Field(None, description="权限分类")


# ===== 认证相关Schema =====

class LoginRequest(BaseSchema):
    """登录请求"""
    username: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")
    remember_me: Optional[bool] = Field(False, description="记住我")


class TokenResponse(BaseSchema):
    """令牌响应"""
    access_token: str = Field(..., description="访问令牌")
    refresh_token: str = Field(..., description="刷新令牌")
    token_type: str = Field(..., description="令牌类型")
    expires_in: int = Field(..., description="过期时间(秒)")


class RefreshTokenRequest(BaseSchema):
    """刷新令牌请求"""
    refresh_token: str = Field(..., description="刷新令牌")


# ===== 响应Schema =====

class UserSettings(BaseSchema):
    """用户设置响应"""
    theme: str = Field(..., description="UI主题")
    language: str = Field(..., description="界面语言")
    notification_enabled: bool = Field(..., description="是否启用通知")
    timezone: str = Field(..., description="时区")
    preferences: Optional[Dict[str, Any]] = Field(None, description="用户偏好设置")


class RoleResponse(BaseSchema):
    """角色响应"""
    id: str = Field(..., description="角色ID")
    name: str = Field(..., description="角色名称")
    description: Optional[str] = Field(None, description="角色描述")
    role_type: RoleType = Field(..., description="角色类型")
    is_default: bool = Field(..., description="是否为默认角色")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class PermissionResponse(BaseSchema):
    """权限响应"""
    id: str = Field(..., description="权限ID")
    name: str = Field(..., description="权限名称")
    code: str = Field(..., description="权限代码")
    description: Optional[str] = Field(None, description="权限描述")
    resource: Optional[str] = Field(None, description="资源类型")
    scope: PermissionScope = Field(..., description="权限范围")
    category: Optional[str] = Field(None, description="权限分类")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class UserResponse(BaseSchema):
    """用户响应"""
    id: str = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    email: str = Field(..., description="邮箱地址")
    full_name: Optional[str] = Field(None, description="全名")
    nickname: Optional[str] = Field(None, description="昵称")
    phone: Optional[str] = Field(None, description="手机号码")
    avatar_url: Optional[str] = Field(None, description="头像URL")
    bio: Optional[str] = Field(None, description="个人简介")
    user_type: UserType = Field(..., description="用户类型")
    status: UserStatus = Field(..., description="用户状态")
    is_superuser: bool = Field(..., description="是否为超级管理员")
    last_login: Optional[datetime] = Field(None, description="最后登录时间")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    settings: Optional[UserSettings] = Field(None, description="用户设置")
    roles: List[RoleResponse] = Field([], description="用户角色")


# ===== 统一API响应Schema =====

class APIResponse(BaseSchema):
    """统一API响应格式"""
    success: bool = Field(..., description="请求是否成功")
    message: str = Field(default="", description="响应消息")
    data: Optional[Any] = Field(default=None, description="响应数据")
    error_code: Optional[str] = Field(default=None, description="错误代码")
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间")


class PaginatedResponse(BaseSchema):
    """分页响应格式"""
    success: bool = Field(..., description="请求是否成功")
    message: str = Field(default="", description="响应消息")
    data: List[Any] = Field(..., description="数据列表")
    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页大小")
    total_pages: int = Field(..., description="总页数")
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间")


# ===== 健康检查Schema =====

class HealthCheckResponse(BaseSchema):
    """健康检查响应"""
    status: str = Field(..., description="服务状态")
    version: str = Field(..., description="服务版本")
    uptime: float = Field(..., description="运行时间(秒)")
    timestamp: datetime = Field(..., description="检查时间")
    database: bool = Field(..., description="数据库连接状态")
    redis: bool = Field(..., description="Redis连接状态")
    cpu_usage: float = Field(..., description="CPU使用率")
    memory_usage: float = Field(..., description="内存使用率")
    disk_usage: float = Field(..., description="磁盘使用率")
    total_users: int = Field(..., description="用户总数")
    active_users: int = Field(..., description="活跃用户数")
    total_roles: int = Field(..., description="角色总数")
    total_permissions: int = Field(..., description="权限总数")
