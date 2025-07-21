"""
工具模型模块: 工具定义、配置和执行相关的数据库模型
"""

from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, JSON, Boolean, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import ARRAY
from typing import List, Dict, Any, Optional

from .database import Base


class Tool(Base):
    """工具模型"""
    __tablename__ = "tools"
    
    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="工具名称")
    description = Column(Text, comment="工具描述")
    category = Column(String(50), comment="工具分类")
    
    # 工具类型和来源
    tool_type = Column(String(50), nullable=False, comment="工具类型")
    source_type = Column(String(50), default="builtin", comment="来源类型")  # builtin/custom/third_party
    provider = Column(String(100), comment="提供者")
    
    # 工具定义
    tool_schema = Column(JSON, nullable=False, comment="工具模式定义")
    parameters_schema = Column(JSON, comment="参数模式")
    return_schema = Column(JSON, comment="返回值模式")
    
    # 执行配置
    execution_config = Column(JSON, comment="执行配置")
    timeout = Column(Integer, default=30, comment="超时时间（秒）")
    retry_count = Column(Integer, default=3, comment="重试次数")
    
    # 权限和安全
    required_permissions = Column(ARRAY(String), comment="所需权限")
    security_level = Column(String(20), default="low", comment="安全级别")
    is_dangerous = Column(Boolean, default=False, comment="是否危险")
    
    # 状态信息
    is_active = Column(Boolean, default=True, comment="是否激活")
    is_public = Column(Boolean, default=False, comment="是否公开")
    status = Column(String(20), default="active", comment="状态")
    
    # 版本信息
    version = Column(String(20), default="1.0", comment="版本")
    
    # 统计信息
    usage_count = Column(Integer, default=0, comment="使用次数")
    success_rate = Column(Float, default=0.0, comment="成功率")
    avg_execution_time = Column(Float, comment="平均执行时间")
    
    # 元数据
    tags = Column(ARRAY(String), comment="标签")
    icon = Column(String(255), comment="图标URL")
    documentation_url = Column(String(500), comment="文档URL")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), comment="更新时间")
    
    # 关系
    configurations = relationship("ToolConfiguration", back_populates="tool", cascade="all, delete-orphan")
    executions = relationship("ToolExecution", back_populates="tool", cascade="all, delete-orphan")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "tool_type": self.tool_type,
            "source_type": self.source_type,
            "provider": self.provider,
            "tool_schema": self.tool_schema,
            "parameters_schema": self.parameters_schema,
            "return_schema": self.return_schema,
            "execution_config": self.execution_config,
            "timeout": self.timeout,
            "retry_count": self.retry_count,
            "required_permissions": self.required_permissions,
            "security_level": self.security_level,
            "is_dangerous": self.is_dangerous,
            "is_active": self.is_active,
            "is_public": self.is_public,
            "status": self.status,
            "version": self.version,
            "usage_count": self.usage_count,
            "success_rate": self.success_rate,
            "avg_execution_time": self.avg_execution_time,
            "tags": self.tags,
            "icon": self.icon,
            "documentation_url": self.documentation_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class ToolConfiguration(Base):
    """工具配置模型"""
    __tablename__ = "tool_configurations"
    
    id = Column(String(36), primary_key=True, index=True)
    tool_id = Column(String(36), ForeignKey("tools.id"), nullable=False, comment="工具ID")
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment="用户ID")
    
    # 配置信息
    name = Column(String(100), nullable=False, comment="配置名称")
    description = Column(Text, comment="配置描述")
    config_data = Column(JSON, nullable=False, comment="配置数据")
    
    # 环境配置
    environment = Column(String(50), default="production", comment="环境")
    variables = Column(JSON, comment="环境变量")
    secrets = Column(JSON, comment="密钥配置")
    
    # 状态信息
    is_active = Column(Boolean, default=True, comment="是否激活")
    is_default = Column(Boolean, default=False, comment="是否默认配置")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), comment="更新时间")
    
    # 关系
    tool = relationship("Tool", back_populates="configurations")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "tool_id": self.tool_id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "config_data": self.config_data,
            "environment": self.environment,
            "variables": self.variables,
            "is_active": self.is_active,
            "is_default": self.is_default,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class ToolExecution(Base):
    """工具执行记录模型"""
    __tablename__ = "tool_executions"
    
    id = Column(String(36), primary_key=True, index=True)
    tool_id = Column(String(36), ForeignKey("tools.id"), nullable=False, comment="工具ID")
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment="用户ID")
    
    # 执行信息
    execution_id = Column(String(100), unique=True, nullable=False, comment="执行ID")
    input_data = Column(JSON, comment="输入数据")
    output_data = Column(JSON, comment="输出数据")
    
    # 执行状态
    status = Column(String(20), default="pending", comment="执行状态")
    progress = Column(Float, default=0.0, comment="执行进度")
    error_message = Column(Text, comment="错误信息")
    error_code = Column(String(50), comment="错误代码")
    
    # 性能指标
    start_time = Column(DateTime(timezone=True), comment="开始时间")
    end_time = Column(DateTime(timezone=True), comment="结束时间")
    execution_time = Column(Float, comment="执行时间（秒）")
    
    # 资源使用
    memory_usage = Column(Integer, comment="内存使用（MB）")
    cpu_usage = Column(Float, comment="CPU使用率")
    
    # 执行环境
    environment = Column(String(50), comment="执行环境")
    executor = Column(String(100), comment="执行器")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), comment="更新时间")
    
    # 关系
    tool = relationship("Tool", back_populates="executions")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "tool_id": self.tool_id,
            "user_id": self.user_id,
            "execution_id": self.execution_id,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "status": self.status,
            "progress": self.progress,
            "error_message": self.error_message,
            "error_code": self.error_code,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "execution_time": self.execution_time,
            "memory_usage": self.memory_usage,
            "cpu_usage": self.cpu_usage,
            "environment": self.environment,
            "executor": self.executor,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class UnifiedTool(Base):
    """统一工具模型"""
    __tablename__ = "unified_tools"
    
    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="工具名称")
    description = Column(Text, comment="工具描述")
    
    # 工具分类
    category = Column(String(50), comment="工具分类")
    subcategory = Column(String(50), comment="子分类")
    
    # 统一配置
    unified_config = Column(JSON, nullable=False, comment="统一配置")
    adapter_config = Column(JSON, comment="适配器配置")
    mapping_config = Column(JSON, comment="映射配置")
    
    # 支持的框架
    supported_frameworks = Column(ARRAY(String), comment="支持的框架")
    framework_configs = Column(JSON, comment="框架特定配置")
    
    # 状态信息
    is_active = Column(Boolean, default=True, comment="是否激活")
    is_verified = Column(Boolean, default=False, comment="是否验证")
    
    # 统计信息
    usage_count = Column(Integer, default=0, comment="使用次数")
    rating = Column(Float, default=0.0, comment="评分")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), comment="更新时间")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "subcategory": self.subcategory,
            "unified_config": self.unified_config,
            "adapter_config": self.adapter_config,
            "mapping_config": self.mapping_config,
            "supported_frameworks": self.supported_frameworks,
            "framework_configs": self.framework_configs,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "usage_count": self.usage_count,
            "rating": self.rating,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }