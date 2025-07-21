"""
资源权限模型模块: 资源权限、访问控制和配额管理相关的数据库模型
"""

from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, JSON, Boolean, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import ARRAY
from typing import List, Dict, Any, Optional

from .database import Base


class ResourcePermission(Base):
    """资源权限模型"""
    __tablename__ = "resource_permissions"
    
    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment="用户ID")
    
    # 资源信息
    resource_type = Column(String(50), nullable=False, comment="资源类型")
    resource_id = Column(String(36), nullable=False, comment="资源ID")
    resource_name = Column(String(100), comment="资源名称")
    
    # 权限信息
    permissions = Column(ARRAY(String), nullable=False, comment="权限列表")
    access_level = Column(String(20), default="read", comment="访问级别")
    
    # 权限来源
    granted_by = Column(String(36), ForeignKey("users.id"), comment="授权者ID")
    grant_reason = Column(Text, comment="授权原因")
    
    # 时间限制
    expires_at = Column(DateTime(timezone=True), comment="过期时间")
    
    # 状态信息
    is_active = Column(Boolean, default=True, comment="是否激活")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), comment="更新时间")
    
    # 关系
    user = relationship("User", foreign_keys=[user_id])
    granted_by_user = relationship("User", foreign_keys=[granted_by])
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "permissions": self.permissions,
            "access_level": self.access_level,
            "granted_by": self.granted_by,
            "grant_reason": self.grant_reason,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class KnowledgeBaseAccess(Base):
    """知识库访问权限模型"""
    __tablename__ = "knowledge_base_access"
    
    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment="用户ID")
    kb_id = Column(String(36), ForeignKey("knowledge_bases.id"), nullable=False, comment="知识库ID")
    
    # 访问权限
    access_type = Column(String(20), nullable=False, comment="访问类型")  # read/write/admin
    permissions = Column(ARRAY(String), comment="具体权限")
    
    # 限制条件
    query_limit = Column(Integer, comment="查询限制")
    daily_limit = Column(Integer, comment="每日限制")
    
    # 状态信息
    is_active = Column(Boolean, default=True, comment="是否激活")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), comment="更新时间")
    
    # 关系
    user = relationship("User")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "kb_id": self.kb_id,
            "access_type": self.access_type,
            "permissions": self.permissions,
            "query_limit": self.query_limit,
            "daily_limit": self.daily_limit,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class AssistantAccess(Base):
    """助手访问权限模型"""
    __tablename__ = "assistant_access"
    
    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment="用户ID")
    assistant_id = Column(String(36), ForeignKey("assistants.id"), nullable=False, comment="助手ID")
    
    # 访问权限
    access_type = Column(String(20), nullable=False, comment="访问类型")  # use/edit/admin
    permissions = Column(ARRAY(String), comment="具体权限")
    
    # 使用限制
    usage_limit = Column(Integer, comment="使用限制")
    daily_limit = Column(Integer, comment="每日限制")
    
    # 状态信息
    is_active = Column(Boolean, default=True, comment="是否激活")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), comment="更新时间")
    
    # 关系
    user = relationship("User")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "assistant_id": self.assistant_id,
            "access_type": self.access_type,
            "permissions": self.permissions,
            "usage_limit": self.usage_limit,
            "daily_limit": self.daily_limit,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class ModelConfigAccess(Base):
    """模型配置访问权限模型"""
    __tablename__ = "model_config_access"
    
    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment="用户ID")
    model_provider_id = Column(String(36), ForeignKey("model_providers.id"), nullable=False, comment="模型提供商ID")
    
    # 访问权限
    access_type = Column(String(20), nullable=False, comment="访问类型")  # use/config/admin
    allowed_models = Column(ARRAY(String), comment="允许的模型")
    
    # 使用限制
    token_limit = Column(Integer, comment="Token限制")
    daily_limit = Column(Integer, comment="每日限制")
    cost_limit = Column(Float, comment="成本限制")
    
    # 状态信息
    is_active = Column(Boolean, default=True, comment="是否激活")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), comment="更新时间")
    
    # 关系
    user = relationship("User")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "model_provider_id": self.model_provider_id,
            "access_type": self.access_type,
            "allowed_models": self.allowed_models,
            "token_limit": self.token_limit,
            "daily_limit": self.daily_limit,
            "cost_limit": self.cost_limit,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class MCPConfigAccess(Base):
    """MCP配置访问权限模型"""
    __tablename__ = "mcp_config_access"
    
    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment="用户ID")
    mcp_service_id = Column(String(100), nullable=False, comment="MCP服务ID")
    
    # 访问权限
    access_type = Column(String(20), nullable=False, comment="访问类型")  # use/config/admin
    allowed_tools = Column(ARRAY(String), comment="允许的工具")
    
    # 使用限制
    call_limit = Column(Integer, comment="调用限制")
    daily_limit = Column(Integer, comment="每日限制")
    
    # 状态信息
    is_active = Column(Boolean, default=True, comment="是否激活")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), comment="更新时间")
    
    # 关系
    user = relationship("User")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "mcp_service_id": self.mcp_service_id,
            "access_type": self.access_type,
            "allowed_tools": self.allowed_tools,
            "call_limit": self.call_limit,
            "daily_limit": self.daily_limit,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class UserResourceQuota(Base):
    """用户资源配额模型"""
    __tablename__ = "user_resource_quotas"
    
    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, nullable=False, comment="用户ID")
    
    # 存储配额
    storage_quota = Column(Integer, comment="存储配额（MB）")
    storage_used = Column(Integer, default=0, comment="已使用存储（MB）")
    
    # 知识库配额
    kb_quota = Column(Integer, comment="知识库配额")
    kb_used = Column(Integer, default=0, comment="已使用知识库数")
    
    # 助手配额
    assistant_quota = Column(Integer, comment="助手配额")
    assistant_used = Column(Integer, default=0, comment="已使用助手数")
    
    # API调用配额
    api_quota = Column(Integer, comment="API调用配额")
    api_used = Column(Integer, default=0, comment="已使用API调用数")
    
    # Token配额
    token_quota = Column(Integer, comment="Token配额")
    token_used = Column(Integer, default=0, comment="已使用Token数")
    
    # 成本配额
    cost_quota = Column(Float, comment="成本配额")
    cost_used = Column(Float, default=0.0, comment="已使用成本")
    
    # 配额周期
    quota_period = Column(String(20), default="monthly", comment="配额周期")
    period_start = Column(DateTime(timezone=True), comment="周期开始时间")
    period_end = Column(DateTime(timezone=True), comment="周期结束时间")
    
    # 状态信息
    is_active = Column(Boolean, default=True, comment="是否激活")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), comment="更新时间")
    
    # 关系
    user = relationship("User")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "storage_quota": self.storage_quota,
            "storage_used": self.storage_used,
            "kb_quota": self.kb_quota,
            "kb_used": self.kb_used,
            "assistant_quota": self.assistant_quota,
            "assistant_used": self.assistant_used,
            "api_quota": self.api_quota,
            "api_used": self.api_used,
            "token_quota": self.token_quota,
            "token_used": self.token_used,
            "cost_quota": self.cost_quota,
            "cost_used": self.cost_used,
            "quota_period": self.quota_period,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    def check_quota(self, resource_type: str, amount: int = 1) -> bool:
        """检查配额是否足够"""
        quota_map = {
            "storage": (self.storage_quota, self.storage_used),
            "kb": (self.kb_quota, self.kb_used),
            "assistant": (self.assistant_quota, self.assistant_used),
            "api": (self.api_quota, self.api_used),
            "token": (self.token_quota, self.token_used)
        }
        
        if resource_type not in quota_map:
            return True
        
        quota, used = quota_map[resource_type]
        if quota is None:
            return True
        
        return used + amount <= quota
    
    def use_quota(self, resource_type: str, amount: int = 1) -> bool:
        """使用配额"""
        if not self.check_quota(resource_type, amount):
            return False
        
        if resource_type == "storage":
            self.storage_used += amount
        elif resource_type == "kb":
            self.kb_used += amount
        elif resource_type == "assistant":
            self.assistant_used += amount
        elif resource_type == "api":
            self.api_used += amount
        elif resource_type == "token":
            self.token_used += amount
        
        return True