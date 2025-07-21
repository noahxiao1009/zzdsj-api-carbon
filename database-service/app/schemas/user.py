"""
用户相关的Pydantic模式定义
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr, validator
from datetime import datetime


class UserBase(BaseModel):
    """用户基础模式"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱")
    full_name: Optional[str] = Field(None, max_length=100, description="全名")
    disabled: bool = Field(default=False, description="是否禁用")
    is_superuser: bool = Field(default=False, description="是否超级管理员")
    avatar_url: Optional[str] = Field(None, description="头像URL")


class UserCreate(UserBase):
    """用户创建模式"""
    password: str = Field(..., min_length=8, description="密码")
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('密码长度至少8位')
        return v


class UserUpdate(BaseModel):
    """用户更新模式"""
    username: Optional[str] = Field(None, min_length=3, max_length=50, description="用户名")
    email: Optional[EmailStr] = Field(None, description="邮箱")
    full_name: Optional[str] = Field(None, max_length=100, description="全名")
    disabled: Optional[bool] = Field(None, description="是否禁用")
    is_superuser: Optional[bool] = Field(None, description="是否超级管理员")
    avatar_url: Optional[str] = Field(None, description="头像URL")
    password: Optional[str] = Field(None, min_length=8, description="新密码")


class UserResponse(UserBase):
    """用户响应模式"""
    id: str = Field(..., description="用户ID")
    auto_id: int = Field(..., description="自增ID")
    last_login: Optional[datetime] = Field(None, description="最后登录时间")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    roles: List[str] = Field(default=[], description="角色列表")
    
    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    """用户登录模式"""
    username: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")


class UserLoginResponse(BaseModel):
    """用户登录响应模式"""
    access_token: str = Field(..., description="访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(..., description="过期时间（秒）")
    user: UserResponse = Field(..., description="用户信息")


class RoleBase(BaseModel):
    """角色基础模式"""
    name: str = Field(..., min_length=1, max_length=50, description="角色名称")
    description: Optional[str] = Field(None, max_length=255, description="角色描述")
    is_default: bool = Field(default=False, description="是否默认角色")
    is_system: bool = Field(default=False, description="是否系统角色")


class RoleCreate(RoleBase):
    """角色创建模式"""
    permissions: Optional[List[str]] = Field(default=[], description="权限列表")


class RoleUpdate(BaseModel):
    """角色更新模式"""
    name: Optional[str] = Field(None, min_length=1, max_length=50, description="角色名称")
    description: Optional[str] = Field(None, max_length=255, description="角色描述")
    is_default: Optional[bool] = Field(None, description="是否默认角色")
    permissions: Optional[List[str]] = Field(None, description="权限列表")


class RoleResponse(RoleBase):
    """角色响应模式"""
    id: str = Field(..., description="角色ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    permissions: List[str] = Field(default=[], description="权限列表")
    
    class Config:
        from_attributes = True


class PermissionBase(BaseModel):
    """权限基础模式"""
    name: str = Field(..., min_length=1, max_length=50, description="权限名称")
    code: str = Field(..., min_length=1, max_length=50, description="权限代码")
    description: Optional[str] = Field(None, max_length=255, description="权限描述")
    resource: Optional[str] = Field(None, max_length=50, description="资源类型")
    action: Optional[str] = Field(None, max_length=50, description="操作类型")
    is_system: bool = Field(default=False, description="是否系统权限")


class PermissionCreate(PermissionBase):
    """权限创建模式"""
    pass


class PermissionUpdate(BaseModel):
    """权限更新模式"""
    name: Optional[str] = Field(None, min_length=1, max_length=50, description="权限名称")
    description: Optional[str] = Field(None, max_length=255, description="权限描述")
    resource: Optional[str] = Field(None, max_length=50, description="资源类型")
    action: Optional[str] = Field(None, max_length=50, description="操作类型")


class PermissionResponse(PermissionBase):
    """权限响应模式"""
    id: str = Field(..., description="权限ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    class Config:
        from_attributes = True


class UserSettingsBase(BaseModel):
    """用户设置基础模式"""
    theme: str = Field(default="light", description="UI主题")
    language: str = Field(default="zh-CN", description="界面语言")
    timezone: str = Field(default="Asia/Shanghai", description="时区")
    notification_enabled: bool = Field(default=True, description="是否启用通知")
    email_notification: bool = Field(default=True, description="是否启用邮件通知")


class UserSettingsCreate(UserSettingsBase):
    """用户设置创建模式"""
    user_id: str = Field(..., description="用户ID")


class UserSettingsUpdate(BaseModel):
    """用户设置更新模式"""
    theme: Optional[str] = Field(None, description="UI主题")
    language: Optional[str] = Field(None, description="界面语言")
    timezone: Optional[str] = Field(None, description="时区")
    notification_enabled: Optional[bool] = Field(None, description="是否启用通知")
    email_notification: Optional[bool] = Field(None, description="是否启用邮件通知")


class UserSettingsResponse(UserSettingsBase):
    """用户设置响应模式"""
    id: str = Field(..., description="设置ID")
    user_id: str = Field(..., description="用户ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    class Config:
        from_attributes = True


class ApiKeyBase(BaseModel):
    """API密钥基础模式"""
    name: Optional[str] = Field(None, max_length=100, description="密钥名称")
    description: Optional[str] = Field(None, max_length=255, description="密钥描述")
    is_active: bool = Field(default=True, description="是否激活")
    expires_at: Optional[datetime] = Field(None, description="过期时间")
    rate_limit: Optional[int] = Field(None, description="速率限制（每小时请求数）")


class ApiKeyCreate(ApiKeyBase):
    """API密钥创建模式"""
    user_id: str = Field(..., description="用户ID")


class ApiKeyUpdate(BaseModel):
    """API密钥更新模式"""
    name: Optional[str] = Field(None, max_length=100, description="密钥名称")
    description: Optional[str] = Field(None, max_length=255, description="密钥描述")
    is_active: Optional[bool] = Field(None, description="是否激活")
    expires_at: Optional[datetime] = Field(None, description="过期时间")
    rate_limit: Optional[int] = Field(None, description="速率限制（每小时请求数）")


class ApiKeyResponse(ApiKeyBase):
    """API密钥响应模式"""
    id: str = Field(..., description="密钥ID")
    user_id: str = Field(..., description="用户ID")
    key: str = Field(..., description="API密钥（部分显示）")
    last_used_at: Optional[datetime] = Field(None, description="最后使用时间")
    usage_count: int = Field(default=0, description="使用次数")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    class Config:
        from_attributes = True


class PasswordChangeRequest(BaseModel):
    """密码修改请求"""
    current_password: str = Field(..., description="当前密码")
    new_password: str = Field(..., min_length=8, description="新密码")
    
    @validator('new_password')
    def validate_new_password(cls, v):
        if len(v) < 8:
            raise ValueError('新密码长度至少8位')
        return v


class PasswordResetRequest(BaseModel):
    """密码重置请求"""
    email: EmailStr = Field(..., description="邮箱")


class PasswordResetConfirm(BaseModel):
    """密码重置确认"""
    token: str = Field(..., description="重置令牌")
    new_password: str = Field(..., min_length=8, description="新密码")
    
    @validator('new_password')
    def validate_new_password(cls, v):
        if len(v) < 8:
            raise ValueError('新密码长度至少8位')
        return v