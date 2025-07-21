"""
系统配置模型模块: 系统配置、模型提供商和框架配置相关的数据库模型
"""

from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, JSON, Boolean, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import ARRAY
from typing import List, Dict, Any, Optional

from .database import Base


class SystemConfig(Base):
    """系统配置模型"""
    __tablename__ = "system_configs"
    
    id = Column(String(36), primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, comment="配置键")
    value = Column(JSON, comment="配置值")
    
    # 配置分类
    category = Column(String(50), comment="配置分类")
    subcategory = Column(String(50), comment="子分类")
    
    # 配置属性
    data_type = Column(String(20), default="string", comment="数据类型")
    is_secret = Column(Boolean, default=False, comment="是否敏感信息")
    is_required = Column(Boolean, default=False, comment="是否必需")
    is_system = Column(Boolean, default=False, comment="是否系统配置")
    
    # 配置描述
    name = Column(String(100), comment="配置名称")
    description = Column(Text, comment="配置描述")
    default_value = Column(JSON, comment="默认值")
    
    # 验证规则
    validation_rules = Column(JSON, comment="验证规则")
    allowed_values = Column(JSON, comment="允许的值")
    
    # 状态信息
    is_active = Column(Boolean, default=True, comment="是否激活")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), comment="更新时间")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "key": self.key,
            "value": self.value if not self.is_secret else "***",
            "category": self.category,
            "subcategory": self.subcategory,
            "data_type": self.data_type,
            "is_secret": self.is_secret,
            "is_required": self.is_required,
            "is_system": self.is_system,
            "name": self.name,
            "description": self.description,
            "default_value": self.default_value,
            "validation_rules": self.validation_rules,
            "allowed_values": self.allowed_values,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class ModelProvider(Base):
    """模型提供商模型"""
    __tablename__ = "model_providers"
    
    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="提供商名称")
    display_name = Column(String(100), comment="显示名称")
    description = Column(Text, comment="提供商描述")
    
    # 提供商类型
    provider_type = Column(String(50), nullable=False, comment="提供商类型")  # openai/domestic/local
    vendor = Column(String(100), comment="厂商名称")
    
    # 连接配置
    api_endpoint = Column(String(500), comment="API端点")
    api_key = Column(String(500), comment="API密钥")
    api_version = Column(String(20), comment="API版本")
    
    # 配置信息
    config = Column(JSON, comment="提供商配置")
    headers = Column(JSON, comment="请求头配置")
    parameters = Column(JSON, comment="默认参数")
    
    # 支持的功能
    supported_models = Column(JSON, comment="支持的模型列表")
    supported_features = Column(ARRAY(String), comment="支持的功能")
    model_types = Column(ARRAY(String), comment="模型类型")
    
    # 限制和配额
    rate_limit = Column(JSON, comment="速率限制")
    quota_config = Column(JSON, comment="配额配置")
    pricing = Column(JSON, comment="定价信息")
    
    # 状态信息
    is_active = Column(Boolean, default=True, comment="是否激活")
    is_default = Column(Boolean, default=False, comment="是否默认")
    status = Column(String(20), default="active", comment="状态")
    
    # 统计信息
    usage_count = Column(Integer, default=0, comment="使用次数")
    success_rate = Column(Float, default=0.0, comment="成功率")
    avg_response_time = Column(Float, comment="平均响应时间")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), comment="更新时间")
    last_used_at = Column(DateTime(timezone=True), comment="最后使用时间")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "provider_type": self.provider_type,
            "vendor": self.vendor,
            "api_endpoint": self.api_endpoint,
            "api_key": self.api_key[:8] + "..." if self.api_key else None,
            "api_version": self.api_version,
            "config": self.config,
            "headers": self.headers,
            "parameters": self.parameters,
            "supported_models": self.supported_models,
            "supported_features": self.supported_features,
            "model_types": self.model_types,
            "rate_limit": self.rate_limit,
            "quota_config": self.quota_config,
            "pricing": self.pricing,
            "is_active": self.is_active,
            "is_default": self.is_default,
            "status": self.status,
            "usage_count": self.usage_count,
            "success_rate": self.success_rate,
            "avg_response_time": self.avg_response_time,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None
        }


class FrameworkConfig(Base):
    """框架配置模型"""
    __tablename__ = "framework_configs"
    
    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="框架名称")
    framework_type = Column(String(50), nullable=False, comment="框架类型")
    version = Column(String(20), comment="框架版本")
    
    # 配置信息
    config_data = Column(JSON, nullable=False, comment="配置数据")
    environment_config = Column(JSON, comment="环境配置")
    integration_config = Column(JSON, comment="集成配置")
    
    # 依赖信息
    dependencies = Column(JSON, comment="依赖配置")
    requirements = Column(JSON, comment="需求配置")
    
    # 状态信息
    is_active = Column(Boolean, default=True, comment="是否激活")
    is_default = Column(Boolean, default=False, comment="是否默认")
    
    # 用户关联
    user_id = Column(String(36), ForeignKey("users.id"), comment="用户ID")
    is_global = Column(Boolean, default=False, comment="是否全局配置")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), comment="更新时间")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "name": self.name,
            "framework_type": self.framework_type,
            "version": self.version,
            "config_data": self.config_data,
            "environment_config": self.environment_config,
            "integration_config": self.integration_config,
            "dependencies": self.dependencies,
            "requirements": self.requirements,
            "is_active": self.is_active,
            "is_default": self.is_default,
            "user_id": self.user_id,
            "is_global": self.is_global,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class ServiceRegistry(Base):
    """服务注册表模型"""
    __tablename__ = "service_registry"
    
    id = Column(String(36), primary_key=True, index=True)
    service_name = Column(String(100), nullable=False, comment="服务名称")
    service_id = Column(String(100), unique=True, nullable=False, comment="服务ID")
    
    # 服务信息
    service_type = Column(String(50), comment="服务类型")
    version = Column(String(20), comment="服务版本")
    description = Column(Text, comment="服务描述")
    
    # 网络信息
    host = Column(String(255), nullable=False, comment="主机地址")
    port = Column(Integer, nullable=False, comment="端口")
    protocol = Column(String(20), default="http", comment="协议")
    
    # 健康检查
    health_check_url = Column(String(500), comment="健康检查URL")
    health_check_interval = Column(Integer, default=30, comment="健康检查间隔")
    
    # 服务元数据
    metadata = Column(JSON, comment="服务元数据")
    tags = Column(ARRAY(String), comment="服务标签")
    
    # 状态信息
    status = Column(String(20), default="active", comment="服务状态")
    is_healthy = Column(Boolean, default=True, comment="是否健康")
    last_heartbeat = Column(DateTime(timezone=True), comment="最后心跳时间")
    
    # 统计信息
    request_count = Column(Integer, default=0, comment="请求次数")
    error_count = Column(Integer, default=0, comment="错误次数")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), comment="更新时间")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "service_name": self.service_name,
            "service_id": self.service_id,
            "service_type": self.service_type,
            "version": self.version,
            "description": self.description,
            "host": self.host,
            "port": self.port,
            "protocol": self.protocol,
            "health_check_url": self.health_check_url,
            "health_check_interval": self.health_check_interval,
            "metadata": self.metadata,
            "tags": self.tags,
            "status": self.status,
            "is_healthy": self.is_healthy,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "request_count": self.request_count,
            "error_count": self.error_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }