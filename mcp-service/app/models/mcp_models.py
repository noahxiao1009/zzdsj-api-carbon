"""
MCP服务相关数据模型
MCP Service Data Models
"""

from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, JSON, Float, Index, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum
import ipaddress

Base = declarative_base()

class MCPServiceType(str, Enum):
    """MCP服务类型"""
    BUILTIN = "builtin"          # 内置服务
    CUSTOM = "custom"            # 自定义服务
    THIRD_PARTY = "third_party"  # 第三方服务

class MCPServiceStatus(str, Enum):
    """MCP服务状态"""
    INACTIVE = "inactive"        # 未激活
    STARTING = "starting"        # 启动中
    ACTIVE = "active"           # 运行中
    ERROR = "error"             # 错误状态
    STOPPING = "stopping"       # 停止中
    STOPPED = "stopped"         # 已停止

class MCPServiceCategory(str, Enum):
    """MCP服务分类"""
    MAP = "map"                 # 地图服务
    CONTENT = "content"         # 内容生成
    SEARCH = "search"           # 搜索服务
    CODE = "code"               # 代码管理
    NOTEBOOK = "notebook"       # 笔记服务
    CHART = "chart"             # 图表生成
    FINANCE = "finance"         # 金融服务
    UTILITY = "utility"         # 工具类

class MCPToolType(str, Enum):
    """MCP工具类型"""
    FUNCTION = "function"       # 函数工具
    RESOURCE = "resource"       # 资源工具
    PROMPT = "prompt"           # 提示工具

class StreamType(str, Enum):
    """流式通信类型"""
    SSE = "sse"                 # Server-Sent Events
    WEBSOCKET = "websocket"     # WebSocket

class StreamStatus(str, Enum):
    """流状态"""
    ACTIVE = "active"           # 活跃
    COMPLETED = "completed"     # 完成
    ERROR = "error"             # 错误
    TIMEOUT = "timeout"         # 超时

# ==================== SQLAlchemy数据库模型 ====================

class MCPService(Base):
    """MCP服务表"""
    __tablename__ = "mcp_services"
    
    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, comment="服务名称")
    display_name = Column(String(200), nullable=False, comment="显示名称")
    description = Column(Text, comment="服务描述")
    type = Column(String(50), nullable=False, comment="服务类型")
    category = Column(String(50), nullable=False, comment="服务分类")
    version = Column(String(20), default="1.0.0", comment="版本号")
    status = Column(String(20), default="inactive", comment="服务状态")
    config = Column(JSON, default={}, comment="服务配置")
    metadata = Column(JSON, default={}, comment="元数据")
    
    # Docker相关
    container_id = Column(String(64), comment="容器ID")
    container_name = Column(String(100), comment="容器名称")
    image_name = Column(String(200), comment="镜像名称")
    port_mapping = Column(JSON, comment="端口映射配置")
    
    # 网络配置
    network_id = Column(String(64), comment="网络ID")
    ip_address = Column(String(45), comment="IP地址")  # 支持IPv6
    vlan_id = Column(Integer, comment="VLAN ID")
    
    # 资源配置
    cpu_limit = Column(String(20), comment="CPU限制")
    memory_limit = Column(String(20), comment="内存限制")
    disk_limit = Column(String(20), comment="磁盘限制")
    
    # 服务配置
    service_url = Column(String(500), comment="服务URL")
    health_check_url = Column(String(500), comment="健康检查URL")
    api_key = Column(String(500), comment="API密钥")
    auth_config = Column(JSON, comment="认证配置")
    
    # 统计信息
    usage_count = Column(Integer, default=0, comment="使用次数")
    last_used_at = Column(DateTime(timezone=True), comment="最后使用时间")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系
    tools = relationship("MCPTool", back_populates="service", cascade="all, delete-orphan")
    
    # 索引
    __table_args__ = (
        Index('idx_mcp_services_type', 'type'),
        Index('idx_mcp_services_category', 'category'),
        Index('idx_mcp_services_status', 'status'),
        Index('idx_mcp_services_container', 'container_id'),
    )

class MCPTool(Base):
    """MCP工具表"""
    __tablename__ = "mcp_tools"
    
    id = Column(String(36), primary_key=True, index=True)
    service_id = Column(String(36), ForeignKey('mcp_services.id', ondelete='CASCADE'), nullable=False)
    name = Column(String(100), nullable=False, comment="工具名称")
    display_name = Column(String(200), nullable=False, comment="显示名称")
    description = Column(Text, comment="工具描述")
    tool_type = Column(String(50), comment="工具类型")
    schema = Column(JSON, nullable=False, comment="工具schema定义")
    enabled = Column(Boolean, default=True, comment="是否启用")
    
    # 使用统计
    usage_count = Column(Integer, default=0, comment="使用次数")
    success_count = Column(Integer, default=0, comment="成功次数")
    error_count = Column(Integer, default=0, comment="错误次数")
    avg_execution_time_ms = Column(Float, default=0.0, comment="平均执行时间(毫秒)")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系
    service = relationship("MCPService", back_populates="tools")
    
    # 索引
    __table_args__ = (
        Index('idx_tools_service_name', 'service_id', 'name', unique=True),
        Index('idx_tools_enabled', 'enabled'),
        Index('idx_tools_type', 'tool_type'),
    )

class MCPToolUsage(Base):
    """MCP工具使用记录表"""
    __tablename__ = "mcp_tool_usage"
    
    id = Column(String(36), primary_key=True, index=True)
    service_id = Column(String(36), ForeignKey('mcp_services.id'), nullable=False)
    tool_id = Column(String(36), ForeignKey('mcp_tools.id'), nullable=False)
    user_id = Column(String(36), comment="用户ID")
    session_id = Column(String(36), comment="会话ID")
    
    # 调用信息
    request_data = Column(JSON, comment="请求数据")
    response_data = Column(JSON, comment="响应数据")
    execution_time_ms = Column(Integer, comment="执行时间(毫秒)")
    status = Column(String(20), comment="执行状态")
    error_message = Column(Text, comment="错误信息")
    
    # 流式通信信息
    stream_id = Column(String(36), comment="流ID")
    is_streaming = Column(Boolean, default=False, comment="是否流式")
    stream_events_count = Column(Integer, default=0, comment="流事件数量")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 索引
    __table_args__ = (
        Index('idx_usage_service_id', 'service_id'),
        Index('idx_usage_tool_id', 'tool_id'),
        Index('idx_usage_user_id', 'user_id'),
        Index('idx_usage_created_at', 'created_at'),
        Index('idx_usage_status', 'status'),
    )

class MCPNetwork(Base):
    """MCP网络配置表"""
    __tablename__ = "mcp_networks"
    
    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, comment="网络名称")
    network_type = Column(String(20), nullable=False, default="vlan", comment="网络类型")
    vlan_id = Column(Integer, unique=True, comment="VLAN ID")
    subnet = Column(String(18), nullable=False, comment="子网CIDR")
    gateway = Column(String(45), nullable=False, comment="网关IP")
    dns_servers = Column(JSON, comment="DNS服务器列表")
    
    # 安全配置
    isolation_enabled = Column(Boolean, default=True, comment="是否启用隔离")
    allowed_ports = Column(JSON, comment="允许的端口列表")
    firewall_rules = Column(JSON, comment="防火墙规则")
    
    is_active = Column(Boolean, default=True, comment="是否活跃")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 索引
    __table_args__ = (
        Index('idx_networks_vlan_id', 'vlan_id'),
        Index('idx_networks_active', 'is_active'),
    )

class MCPStream(Base):
    """流式会话表"""
    __tablename__ = "mcp_streams"
    
    id = Column(String(36), primary_key=True, index=True)
    stream_id = Column(String(100), nullable=False, unique=True, comment="流ID")
    service_id = Column(String(36), ForeignKey('mcp_services.id'), nullable=False)
    tool_id = Column(String(36), ForeignKey('mcp_tools.id'), comment="工具ID")
    user_id = Column(String(36), comment="用户ID")
    
    # 流式配置
    stream_type = Column(String(20), nullable=False, comment="流类型")
    connection_id = Column(String(100), comment="连接ID")
    
    # 状态信息
    status = Column(String(20), default="active", comment="流状态")
    events_sent = Column(Integer, default=0, comment="已发送事件数")
    last_event_at = Column(DateTime(timezone=True), comment="最后事件时间")
    
    # 配置信息
    keepalive_interval = Column(Integer, default=30, comment="保活间隔(秒)")
    timeout_seconds = Column(Integer, default=300, comment="超时时间(秒)")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 索引
    __table_args__ = (
        Index('idx_streams_service_id', 'service_id'),
        Index('idx_streams_user_id', 'user_id'),
        Index('idx_streams_status', 'status'),
        Index('idx_streams_created_at', 'created_at'),
    )

# ==================== Pydantic响应模型 ====================

class MCPServiceConfig(BaseModel):
    """MCP服务配置"""
    name: str = Field(..., description="服务名称")
    display_name: str = Field(..., description="显示名称")
    description: Optional[str] = Field(None, description="服务描述")
    type: MCPServiceType = Field(..., description="服务类型")
    category: MCPServiceCategory = Field(..., description="服务分类")
    version: str = Field("1.0.0", description="版本号")
    
    # Docker配置
    image_name: str = Field(..., description="Docker镜像名称")
    port: int = Field(8080, description="服务端口")
    cpu_limit: str = Field("0.5", description="CPU限制")
    memory_limit: str = Field("512m", description="内存限制")
    
    # 网络配置
    vlan_id: Optional[int] = Field(None, description="VLAN ID")
    
    # 服务配置
    environment: Dict[str, str] = Field(default_factory=dict, description="环境变量")
    volumes: List[str] = Field(default_factory=list, description="挂载卷")
    auth_config: Dict[str, Any] = Field(default_factory=dict, description="认证配置")
    
    # 工具配置
    tools: List[Dict[str, Any]] = Field(default_factory=list, description="工具列表")

class MCPServiceInfo(BaseModel):
    """MCP服务信息"""
    id: str = Field(..., description="服务ID")
    name: str = Field(..., description="服务名称")
    display_name: str = Field(..., description="显示名称")
    description: Optional[str] = Field(None, description="服务描述")
    type: MCPServiceType = Field(..., description="服务类型")
    category: MCPServiceCategory = Field(..., description="服务分类")
    version: str = Field(..., description="版本号")
    status: MCPServiceStatus = Field(..., description="服务状态")
    
    # 容器信息
    container_id: Optional[str] = Field(None, description="容器ID")
    container_name: Optional[str] = Field(None, description="容器名称")
    image_name: Optional[str] = Field(None, description="镜像名称")
    
    # 网络信息
    service_url: Optional[str] = Field(None, description="服务URL")
    ip_address: Optional[str] = Field(None, description="IP地址")
    vlan_id: Optional[int] = Field(None, description="VLAN ID")
    
    # 统计信息
    usage_count: int = Field(0, description="使用次数")
    tools_count: int = Field(0, description="工具数量")
    last_used_at: Optional[datetime] = Field(None, description="最后使用时间")
    
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

class MCPToolInfo(BaseModel):
    """MCP工具信息"""
    id: str = Field(..., description="工具ID")
    service_id: str = Field(..., description="服务ID")
    name: str = Field(..., description="工具名称")
    display_name: str = Field(..., description="显示名称")
    description: Optional[str] = Field(None, description="工具描述")
    tool_type: MCPToolType = Field(..., description="工具类型")
    schema: Dict[str, Any] = Field(..., description="工具schema")
    enabled: bool = Field(True, description="是否启用")
    
    # 统计信息
    usage_count: int = Field(0, description="使用次数")
    success_count: int = Field(0, description="成功次数")
    error_count: int = Field(0, description="错误次数")
    success_rate: float = Field(0.0, description="成功率")
    avg_execution_time_ms: float = Field(0.0, description="平均执行时间")
    
    created_at: datetime = Field(..., description="创建时间")

class MCPToolExecuteRequest(BaseModel):
    """MCP工具执行请求"""
    service_id: str = Field(..., description="服务ID")
    tool_name: str = Field(..., description="工具名称")
    parameters: Dict[str, Any] = Field(..., description="工具参数")
    user_id: Optional[str] = Field(None, description="用户ID")
    session_id: Optional[str] = Field(None, description="会话ID")
    stream: bool = Field(False, description="是否流式执行")
    timeout: int = Field(30, description="超时时间(秒)")

class MCPToolExecuteResponse(BaseModel):
    """MCP工具执行响应"""
    success: bool = Field(..., description="执行是否成功")
    result: Any = Field(None, description="执行结果")
    execution_time_ms: int = Field(..., description="执行时间(毫秒)")
    error_message: Optional[str] = Field(None, description="错误信息")
    usage_id: str = Field(..., description="使用记录ID")
    
    # 流式响应信息
    stream_id: Optional[str] = Field(None, description="流ID")
    stream_url: Optional[str] = Field(None, description="流URL")

class MCPStreamInfo(BaseModel):
    """MCP流信息"""
    stream_id: str = Field(..., description="流ID")
    service_id: str = Field(..., description="服务ID")
    tool_id: Optional[str] = Field(None, description="工具ID")
    user_id: Optional[str] = Field(None, description="用户ID")
    stream_type: StreamType = Field(..., description="流类型")
    status: StreamStatus = Field(..., description="流状态")
    events_sent: int = Field(0, description="已发送事件数")
    created_at: datetime = Field(..., description="创建时间")

class MCPNetworkConfig(BaseModel):
    """MCP网络配置"""
    name: str = Field(..., description="网络名称")
    network_type: str = Field("vlan", description="网络类型")
    vlan_id: int = Field(..., description="VLAN ID", ge=1, le=4094)
    subnet: str = Field(..., description="子网CIDR")
    gateway: str = Field(..., description="网关IP")
    dns_servers: List[str] = Field(default_factory=lambda: ["8.8.8.8", "8.8.4.4"], description="DNS服务器")
    isolation_enabled: bool = Field(True, description="是否启用隔离")
    allowed_ports: List[int] = Field(default_factory=list, description="允许的端口")

class MCPServiceStats(BaseModel):
    """MCP服务统计"""
    service_id: str = Field(..., description="服务ID")
    service_name: str = Field(..., description="服务名称")
    total_calls: int = Field(0, description="总调用次数")
    successful_calls: int = Field(0, description="成功调用次数")
    failed_calls: int = Field(0, description="失败调用次数")
    success_rate: float = Field(0.0, description="成功率")
    avg_execution_time: float = Field(0.0, description="平均执行时间")
    total_tools: int = Field(0, description="工具总数")
    active_tools: int = Field(0, description="活跃工具数")
    last_used_at: Optional[datetime] = Field(None, description="最后使用时间")

class MCPContainerStats(BaseModel):
    """MCP容器统计"""
    container_id: str = Field(..., description="容器ID")
    container_name: str = Field(..., description="容器名称")
    status: str = Field(..., description="容器状态")
    
    # 资源使用情况
    cpu_usage_percent: float = Field(0.0, description="CPU使用率")
    memory_usage_mb: float = Field(0.0, description="内存使用(MB)")
    memory_limit_mb: float = Field(0.0, description="内存限制(MB)")
    network_rx_bytes: int = Field(0, description="网络接收字节")
    network_tx_bytes: int = Field(0, description="网络发送字节")
    
    # 时间信息
    uptime_seconds: int = Field(0, description="运行时间(秒)")
    created_at: datetime = Field(..., description="创建时间")

class MCPDashboardStats(BaseModel):
    """MCP仪表板统计"""
    total_services: int = Field(0, description="总服务数")
    active_services: int = Field(0, description="活跃服务数")
    inactive_services: int = Field(0, description="非活跃服务数")
    error_services: int = Field(0, description="错误服务数")
    
    total_tools: int = Field(0, description="总工具数")
    enabled_tools: int = Field(0, description="启用工具数")
    
    total_containers: int = Field(0, description="总容器数")
    running_containers: int = Field(0, description="运行中容器数")
    
    total_calls_today: int = Field(0, description="今日总调用数")
    successful_calls_today: int = Field(0, description="今日成功调用数")
    
    active_streams: int = Field(0, description="活跃流数")
    
    avg_response_time: float = Field(0.0, description="平均响应时间")
    system_health_score: float = Field(100.0, description="系统健康评分")