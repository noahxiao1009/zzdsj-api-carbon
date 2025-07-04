"""
MCP服务数据库模型
定义MCP服务、工具、配置和调用历史等数据结构
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from uuid import uuid4
import datetime

from app.core.database import Base


class MCPServiceConfig(Base):
    """MCP服务配置表"""
    __tablename__ = "mcp_service_config"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    deployment_id = Column(String(36), nullable=False, unique=True, index=True, default=lambda: str(uuid4()))
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    service_type = Column(String(50), nullable=False, default="docker")  # docker, kubernetes, cloud, local
    status = Column(String(20), nullable=False, default="pending")  # pending, running, stopped, error
    
    # Docker相关信息
    image = Column(String(255), nullable=True)
    container_id = Column(String(255), nullable=True)
    service_port = Column(Integer, nullable=True)
    host_port = Column(Integer, nullable=True)
    deploy_directory = Column(String(255), nullable=True)
    
    # 网络配置
    network_name = Column(String(100), nullable=True)
    ip_address = Column(String(50), nullable=True)
    
    # 配置信息
    settings = Column(JSON, nullable=True)
    environment_vars = Column(JSON, nullable=True)
    
    # 资源限制
    cpu_limit = Column(String(20), nullable=True)
    memory_limit = Column(String(20), nullable=True)
    disk_limit = Column(String(20), nullable=True)
    
    # 健康检查
    health_check_url = Column(String(255), nullable=True)
    health_check_interval = Column(Integer, default=30)
    health_check_timeout = Column(Integer, default=10)
    health_check_retries = Column(Integer, default=3)
    
    # 时间信息
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    last_started_at = Column(DateTime, nullable=True)
    last_stopped_at = Column(DateTime, nullable=True)
    last_health_check = Column(DateTime, nullable=True)
    
    # 关联
    tools = relationship("MCPTool", back_populates="service", cascade="all, delete-orphan")
    executions = relationship("MCPToolExecution", back_populates="service", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<MCPServiceConfig(id={self.id}, name='{self.name}', status='{self.status}')>"


class MCPTool(Base):
    """MCP工具表"""
    __tablename__ = "mcp_tool"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    service_id = Column(Integer, ForeignKey("mcp_service_config.id"), nullable=False)
    
    # 工具基本信息
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=False, default="general")
    version = Column(String(20), nullable=True)
    
    # 工具配置
    parameters_schema = Column(JSON, nullable=True)  # JSON Schema for parameters
    return_schema = Column(JSON, nullable=True)      # JSON Schema for return value
    tags = Column(JSON, nullable=True)               # 标签列表
    
    # 工具状态
    is_enabled = Column(Boolean, nullable=False, default=True)
    is_deprecated = Column(Boolean, nullable=False, default=False)
    
    # 缓存配置
    cache_enabled = Column(Boolean, nullable=False, default=True)
    cache_ttl = Column(Integer, nullable=False, default=1800)  # 30分钟
    
    # 性能配置
    timeout_seconds = Column(Integer, nullable=False, default=30)
    max_retries = Column(Integer, nullable=False, default=3)
    rate_limit_per_minute = Column(Integer, nullable=True)
    
    # 统计信息
    total_calls = Column(Integer, nullable=False, default=0)
    success_calls = Column(Integer, nullable=False, default=0)
    error_calls = Column(Integer, nullable=False, default=0)
    avg_response_time = Column(Float, nullable=True)
    
    # 时间信息
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    last_used_at = Column(DateTime, nullable=True)
    
    # 关联
    service = relationship("MCPServiceConfig", back_populates="tools")
    executions = relationship("MCPToolExecution", back_populates="tool", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<MCPTool(id={self.id}, name='{self.name}', service_id={self.service_id})>"


class MCPToolExecution(Base):
    """MCP工具执行记录表"""
    __tablename__ = "mcp_tool_execution"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    execution_id = Column(String(36), nullable=False, unique=True, index=True, default=lambda: str(uuid4()))
    
    # 关联信息
    service_id = Column(Integer, ForeignKey("mcp_service_config.id"), nullable=False)
    tool_id = Column(Integer, ForeignKey("mcp_tool.id"), nullable=False)
    
    # 执行信息
    tool_name = Column(String(100), nullable=False)
    parameters = Column(JSON, nullable=True)
    result = Column(JSON, nullable=True)
    
    # 执行状态
    status = Column(String(20), nullable=False)  # pending, running, completed, failed, timeout
    error_message = Column(Text, nullable=True)
    error_code = Column(String(50), nullable=True)
    
    # 性能指标
    start_time = Column(DateTime, nullable=False, default=func.now())
    end_time = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    
    # 用户信息（可选）
    user_id = Column(String(50), nullable=True)
    session_id = Column(String(100), nullable=True)
    request_id = Column(String(100), nullable=True)
    
    # 缓存信息
    cache_hit = Column(Boolean, nullable=False, default=False)
    cached_result = Column(Boolean, nullable=False, default=False)
    
    # 重试信息
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    
    # 时间信息
    created_at = Column(DateTime, nullable=False, default=func.now())
    
    # 关联
    service = relationship("MCPServiceConfig", back_populates="executions")
    tool = relationship("MCPTool", back_populates="executions")
    
    def __repr__(self):
        return f"<MCPToolExecution(id={self.id}, tool_name='{self.tool_name}', status='{self.status}')>"


class MCPServiceDeployment(Base):
    """MCP服务部署记录表"""
    __tablename__ = "mcp_service_deployment"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    deployment_id = Column(String(36), nullable=False, unique=True, index=True, default=lambda: str(uuid4()))
    
    # 服务信息
    service_config_id = Column(Integer, ForeignKey("mcp_service_config.id"), nullable=False)
    service_name = Column(String(100), nullable=False)
    
    # 部署信息
    deployment_type = Column(String(50), nullable=False)  # docker, kubernetes, manual
    deployment_config = Column(JSON, nullable=True)
    
    # 部署状态
    status = Column(String(20), nullable=False)  # deploying, deployed, failed, stopped
    progress = Column(Integer, nullable=False, default=0)  # 0-100
    
    # 部署结果
    deployment_logs = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    deployed_version = Column(String(50), nullable=True)
    
    # 资源使用
    cpu_usage = Column(Float, nullable=True)
    memory_usage = Column(Float, nullable=True)
    disk_usage = Column(Float, nullable=True)
    
    # 时间信息
    started_at = Column(DateTime, nullable=False, default=func.now())
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    
    # 关联
    service_config = relationship("MCPServiceConfig")
    
    def __repr__(self):
        return f"<MCPServiceDeployment(id={self.id}, service_name='{self.service_name}', status='{self.status}')>"


class MCPServiceHealthCheck(Base):
    """MCP服务健康检查记录表"""
    __tablename__ = "mcp_service_health_check"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 服务信息
    service_config_id = Column(Integer, ForeignKey("mcp_service_config.id"), nullable=False)
    service_name = Column(String(100), nullable=False)
    
    # 检查结果
    status = Column(String(20), nullable=False)  # healthy, unhealthy, unknown
    response_time_ms = Column(Integer, nullable=True)
    status_code = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # 检查详情
    check_type = Column(String(50), nullable=False, default="http")  # http, tcp, custom
    check_url = Column(String(255), nullable=True)
    check_config = Column(JSON, nullable=True)
    
    # 时间信息
    checked_at = Column(DateTime, nullable=False, default=func.now())
    
    # 关联
    service_config = relationship("MCPServiceConfig")
    
    def __repr__(self):
        return f"<MCPServiceHealthCheck(id={self.id}, service_name='{self.service_name}', status='{self.status}')>"


# 导出所有模型
__all__ = [
    "MCPServiceConfig",
    "MCPTool",
    "MCPToolExecution", 
    "MCPServiceDeployment",
    "MCPServiceHealthCheck"
] 