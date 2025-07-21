"""
政策搜索相关数据模型
Policy Search Data Models
"""

from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, JSON, Float, Index
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

Base = declarative_base()

class SearchStrategy(str, Enum):
    """搜索策略枚举"""
    AUTO = "auto"                    # 自动策略
    LOCAL_ONLY = "local_only"        # 仅地方门户
    PROVINCIAL_ONLY = "provincial_only"  # 仅省级门户
    SEARCH_ONLY = "search_only"      # 仅搜索引擎
    HYBRID = "hybrid"                # 混合策略

class SearchLevel(str, Enum):
    """搜索层级枚举"""
    LOCAL = "local"                  # 地方门户
    PROVINCIAL = "provincial"        # 省级门户
    NATIONAL = "national"            # 国家级门户
    SEARCH_ENGINE = "search_engine"  # 搜索引擎

class ExtractionMethod(str, Enum):
    """内容提取方法"""
    TRADITIONAL = "traditional"      # 传统解析
    CRAWL4AI = "crawl4ai"           # Crawl4AI
    BROWSER_USE = "browser_use"      # Browser Use
    INTELLIGENT = "intelligent"      # 智能选择

# ==================== SQLAlchemy数据库模型 ====================

class PolicyPortal(Base):
    """政策门户配置表"""
    __tablename__ = "policy_portals"
    
    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(200), nullable=False, comment="门户名称")
    region = Column(String(100), nullable=False, comment="所属区域")
    level = Column(String(20), nullable=False, comment="门户层级")
    base_url = Column(String(500), nullable=False, comment="基础URL")
    search_endpoint = Column(String(500), nullable=False, comment="搜索端点")
    search_params = Column(JSON, nullable=False, comment="搜索参数模板")
    result_selector = Column(String(200), default="", comment="结果选择器")
    encoding = Column(String(20), default="utf-8", comment="页面编码")
    timeout_seconds = Column(Integer, default=30, comment="超时时间")
    max_results = Column(Integer, default=10, comment="最大结果数")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 索引
    __table_args__ = (
        Index('idx_portals_region', 'region'),
        Index('idx_portals_level', 'level'),
        Index('idx_portals_active', 'is_active'),
    )

class PolicySearchCache(Base):
    """政策搜索结果缓存表"""
    __tablename__ = "policy_search_cache"
    
    id = Column(String(36), primary_key=True, index=True)
    query_hash = Column(String(64), nullable=False, unique=True, comment="查询哈希")
    query = Column(String(500), nullable=False, comment="搜索查询")
    region = Column(String(100), nullable=False, comment="搜索区域")
    strategy = Column(String(50), nullable=False, comment="搜索策略")
    results = Column(JSON, nullable=False, comment="搜索结果")
    result_count = Column(Integer, nullable=False, comment="结果数量")
    execution_time_ms = Column(Integer, comment="执行时间(毫秒)")
    cache_expires_at = Column(DateTime(timezone=True), nullable=False, comment="缓存过期时间")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 索引
    __table_args__ = (
        Index('idx_cache_expires', 'cache_expires_at'),
        Index('idx_cache_region', 'region'),
    )

class ToolRegistry(Base):
    """工具注册表"""
    __tablename__ = "tools"
    
    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, comment="工具名称")
    display_name = Column(String(200), nullable=False, comment="显示名称")
    description = Column(Text, comment="工具描述")
    category = Column(String(50), nullable=False, comment="工具分类")
    tool_type = Column(String(50), nullable=False, comment="工具类型")
    version = Column(String(20), default="1.0.0", comment="版本号")
    status = Column(String(20), default="active", comment="状态")
    config = Column(JSON, default={}, comment="工具配置")
    metadata = Column(JSON, default={}, comment="元数据")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 索引
    __table_args__ = (
        Index('idx_tools_category', 'category'),
        Index('idx_tools_type', 'tool_type'),
        Index('idx_tools_status', 'status'),
    )

class ToolUsageStats(Base):
    """工具使用统计表"""
    __tablename__ = "tool_usage_stats"
    
    id = Column(String(36), primary_key=True, index=True)
    tool_id = Column(String(36), nullable=False, comment="工具ID")
    user_id = Column(String(36), comment="用户ID")
    session_id = Column(String(36), comment="会话ID")
    parameters = Column(JSON, comment="调用参数")
    execution_time_ms = Column(Integer, comment="执行时间(毫秒)")
    status = Column(String(20), comment="执行状态")
    error_message = Column(Text, comment="错误信息")
    result_summary = Column(Text, comment="结果摘要")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 索引
    __table_args__ = (
        Index('idx_usage_tool_id', 'tool_id'),
        Index('idx_usage_user_id', 'user_id'),
        Index('idx_usage_created_at', 'created_at'),
        Index('idx_usage_status', 'status'),
    )

# ==================== Pydantic响应模型 ====================

class PolicySearchResult(BaseModel):
    """政策搜索结果"""
    title: str = Field(..., description="标题")
    url: str = Field(..., description="链接")
    content: str = Field(..., description="内容")
    published_date: Optional[str] = Field(None, description="发布日期")
    source: str = Field(..., description="来源")
    search_level: SearchLevel = Field(..., description="搜索层级")
    relevance_score: float = Field(0.0, description="相关性评分")
    policy_type: Optional[str] = Field(None, description="政策类型")
    department: Optional[str] = Field(None, description="发布部门")
    region: Optional[str] = Field(None, description="所属区域")
    content_quality_score: float = Field(0.0, description="内容质量评分")
    extraction_method: ExtractionMethod = Field(ExtractionMethod.TRADITIONAL, description="提取方法")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")

class PolicySearchRequest(BaseModel):
    """政策搜索请求"""
    query: str = Field(..., description="搜索查询", min_length=1, max_length=500)
    region: str = Field("六盘水", description="搜索区域")
    search_strategy: SearchStrategy = Field(SearchStrategy.AUTO, description="搜索策略")
    max_results: int = Field(10, description="最大结果数", ge=1, le=100)
    enable_intelligent_crawling: bool = Field(True, description="启用智能爬取")
    enable_caching: bool = Field(True, description="启用结果缓存")
    cache_ttl_seconds: int = Field(3600, description="缓存时间(秒)", ge=60, le=86400)

class PolicySearchResponse(BaseModel):
    """政策搜索响应"""
    query: str = Field(..., description="搜索查询")
    region: str = Field(..., description="搜索区域")
    strategy: SearchStrategy = Field(..., description="实际使用策略")
    results: List[PolicySearchResult] = Field(..., description="搜索结果列表")
    total_results: int = Field(..., description="结果总数")
    search_time_ms: int = Field(..., description="搜索耗时(毫秒)")
    cache_hit: bool = Field(False, description="是否命中缓存")
    search_levels_used: List[SearchLevel] = Field(..., description="使用的搜索层级")
    statistics: Dict[str, Any] = Field(default_factory=dict, description="统计信息")

class PortalConfigModel(BaseModel):
    """门户配置模型"""
    id: Optional[str] = Field(None, description="门户ID")
    name: str = Field(..., description="门户名称")
    region: str = Field(..., description="所属区域")
    level: SearchLevel = Field(..., description="门户层级")
    base_url: str = Field(..., description="基础URL")
    search_endpoint: str = Field(..., description="搜索端点")
    search_params: Dict[str, str] = Field(..., description="搜索参数模板")
    result_selector: str = Field("", description="结果选择器")
    encoding: str = Field("utf-8", description="页面编码")
    timeout_seconds: int = Field(30, description="超时时间", ge=5, le=300)
    max_results: int = Field(10, description="最大结果数", ge=1, le=100)
    is_active: bool = Field(True, description="是否启用")

class PortalTestRequest(BaseModel):
    """门户测试请求"""
    portal_id: str = Field(..., description="门户ID")
    test_query: str = Field("测试", description="测试查询")

class PortalTestResponse(BaseModel):
    """门户测试响应"""
    portal_id: str = Field(..., description="门户ID")
    portal_name: str = Field(..., description="门户名称")
    success: bool = Field(..., description="测试是否成功")
    status_code: Optional[int] = Field(None, description="HTTP状态码")
    response_time_ms: float = Field(..., description="响应时间(毫秒)")
    test_url: str = Field(..., description="测试URL")
    error_message: Optional[str] = Field(None, description="错误信息")

class ToolInfo(BaseModel):
    """工具信息"""
    id: str = Field(..., description="工具ID")
    name: str = Field(..., description="工具名称")
    display_name: str = Field(..., description="显示名称")
    description: Optional[str] = Field(None, description="工具描述")
    category: str = Field(..., description="工具分类")
    tool_type: str = Field(..., description="工具类型")
    version: str = Field(..., description="版本号")
    status: str = Field(..., description="状态")
    config: Dict[str, Any] = Field(default_factory=dict, description="工具配置")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

class ToolExecuteRequest(BaseModel):
    """工具执行请求"""
    tool_name: str = Field(..., description="工具名称")
    parameters: Dict[str, Any] = Field(..., description="执行参数")
    user_id: Optional[str] = Field(None, description="用户ID")
    session_id: Optional[str] = Field(None, description="会话ID")

class ToolExecuteResponse(BaseModel):
    """工具执行响应"""
    tool_name: str = Field(..., description="工具名称")
    success: bool = Field(..., description="执行是否成功")
    result: Any = Field(None, description="执行结果")
    execution_time_ms: int = Field(..., description="执行时间(毫秒)")
    error_message: Optional[str] = Field(None, description="错误信息")
    usage_id: str = Field(..., description="使用记录ID")

class ToolStatsResponse(BaseModel):
    """工具统计响应"""
    tool_id: str = Field(..., description="工具ID")
    tool_name: str = Field(..., description="工具名称")
    total_calls: int = Field(..., description="总调用次数")
    success_calls: int = Field(..., description="成功调用次数")
    error_calls: int = Field(..., description="错误调用次数")
    average_execution_time_ms: float = Field(..., description="平均执行时间(毫秒)")
    success_rate: float = Field(..., description="成功率")
    last_called_at: Optional[datetime] = Field(None, description="最后调用时间")
    period_days: int = Field(..., description="统计周期(天)")

class CacheStatsResponse(BaseModel):
    """缓存统计响应"""
    total_cached_queries: int = Field(..., description="总缓存查询数")
    cache_hit_rate: float = Field(..., description="缓存命中率")
    average_search_time_ms: float = Field(..., description="平均搜索时间(毫秒)")
    most_searched_regions: List[Dict[str, Any]] = Field(..., description="最多搜索的区域")
    cache_size_mb: float = Field(..., description="缓存大小(MB)")
    expired_entries_count: int = Field(..., description="过期条目数量")