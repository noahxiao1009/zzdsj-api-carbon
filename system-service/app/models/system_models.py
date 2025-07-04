"""
System-Service数据库模型
定义系统服务相关的数据库表结构，包含文件管理、敏感词过滤、政策搜索、系统配置、工具注册等功能
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON, BigInteger, Float, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from uuid import uuid4
import datetime

from app.core.database import Base


class FileRecord(Base):
    """文件记录表"""
    __tablename__ = "file_records"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(String(36), nullable=False, unique=True, index=True, default=lambda: str(uuid4()))
    
    # 文件基本信息
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=True)
    content_type = Column(String(100), nullable=True)
    file_size = Column(BigInteger, nullable=False, default=0)
    file_hash = Column(String(64), nullable=True)  # MD5或SHA256
    
    # 存储信息
    storage_backend = Column(String(50), nullable=False, default="minio")  # minio, local, s3
    storage_path = Column(String(500), nullable=True)
    bucket_name = Column(String(100), nullable=True)
    
    # 文件分类和用途
    file_category = Column(String(50), nullable=True)  # document, image, video, other
    usage_type = Column(String(50), nullable=True)  # knowledge, system, temporary
    
    # 关联信息
    user_id = Column(String(36), nullable=True)
    knowledge_base_id = Column(String(36), nullable=True)
    document_id = Column(String(36), nullable=True)
    
    # 状态信息
    status = Column(String(20), nullable=False, default="uploaded")  # uploaded, processing, completed, failed, deleted
    upload_progress = Column(Integer, nullable=False, default=100)  # 上传进度百分比
    processing_status = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    
    # 元数据
    metadata = Column(JSON, nullable=True, default=dict)
    
    # 访问控制
    is_public = Column(Boolean, nullable=False, default=False)
    access_level = Column(String(50), nullable=False, default="private")  # public, private, restricted
    
    # 时间信息
    upload_time = Column(DateTime, nullable=False, default=func.now())
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    accessed_at = Column(DateTime, nullable=True)
    
    # 统计信息
    download_count = Column(Integer, nullable=False, default=0)
    
    def __repr__(self):
        return f"<FileRecord(id={self.id}, filename='{self.filename}', status='{self.status}')>"


class SensitiveWord(Base):
    """敏感词库表"""
    __tablename__ = "sensitive_words"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 敏感词信息
    word = Column(String(200), nullable=False, unique=True, index=True)
    word_hash = Column(String(64), nullable=True, index=True)  # 敏感词的hash值，用于快速查找
    
    # 分类信息
    category = Column(String(50), nullable=False, default="general")  # general, political, violence, adult, custom
    severity = Column(String(20), nullable=False, default="medium")  # low, medium, high, critical
    
    # 语言和处理规则
    language = Column(String(10), nullable=False, default="zh-CN")
    match_type = Column(String(20), nullable=False, default="exact")  # exact, partial, regex, fuzzy
    replacement_text = Column(String(200), nullable=True)  # 替换文本
    
    # 来源信息
    source = Column(String(50), nullable=False, default="manual")  # manual, import, auto, api
    source_reference = Column(String(255), nullable=True)
    
    # 状态信息
    is_enabled = Column(Boolean, nullable=False, default=True)
    is_system = Column(Boolean, nullable=False, default=False)
    
    # 统计信息
    hit_count = Column(Integer, nullable=False, default=0)
    last_hit_at = Column(DateTime, nullable=True)
    
    # 管理信息
    added_by = Column(String(36), nullable=True)
    approved_by = Column(String(36), nullable=True)
    review_status = Column(String(20), nullable=False, default="approved")  # pending, approved, rejected
    
    # 时间信息
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<SensitiveWord(id={self.id}, word='{self.word}', category='{self.category}')>"


class PolicySearchConfig(Base):
    """政策搜索配置表"""
    __tablename__ = "policy_search_configs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    config_id = Column(String(36), nullable=False, unique=True, index=True, default=lambda: str(uuid4()))
    
    # 配置基本信息
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # 搜索配置
    search_engine = Column(String(50), nullable=False, default="elastic")  # elastic, whoosh, custom
    index_name = Column(String(100), nullable=True)
    
    # 数据源配置
    data_sources = Column(JSON, nullable=False, default=list)  # 数据源列表
    source_weights = Column(JSON, nullable=True, default=dict)  # 各数据源权重
    
    # 搜索参数
    search_fields = Column(JSON, nullable=False, default=list)  # 搜索字段
    boost_fields = Column(JSON, nullable=True, default=dict)  # 字段权重
    default_operator = Column(String(10), nullable=False, default="AND")  # AND, OR
    
    # 结果配置
    max_results = Column(Integer, nullable=False, default=50)
    result_fields = Column(JSON, nullable=False, default=list)  # 返回字段
    highlight_fields = Column(JSON, nullable=True, default=list)  # 高亮字段
    
    # 过滤配置
    default_filters = Column(JSON, nullable=True, default=dict)
    date_range_field = Column(String(100), nullable=True)
    category_field = Column(String(100), nullable=True)
    
    # 排序配置
    default_sort = Column(JSON, nullable=True, default=dict)
    sort_options = Column(JSON, nullable=True, default=list)
    
    # 扩展功能
    enable_fuzzy_search = Column(Boolean, nullable=False, default=True)
    enable_synonym_expansion = Column(Boolean, nullable=False, default=False)
    enable_spell_check = Column(Boolean, nullable=False, default=False)
    
    # 缓存配置
    cache_enabled = Column(Boolean, nullable=False, default=True)
    cache_ttl = Column(Integer, nullable=False, default=1800)  # 30分钟
    
    # 状态信息
    is_active = Column(Boolean, nullable=False, default=True)
    is_default = Column(Boolean, nullable=False, default=False)
    
    # 管理信息
    created_by = Column(String(36), nullable=True)
    
    # 时间信息
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    last_indexed_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<PolicySearchConfig(id={self.id}, name='{self.name}', engine='{self.search_engine}')>"


class SystemConfig(Base):
    """系统配置表"""
    __tablename__ = "system_configs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    config_id = Column(String(36), nullable=False, unique=True, index=True, default=lambda: str(uuid4()))
    
    # 配置标识
    key = Column(String(255), nullable=False, unique=True, index=True)
    category = Column(String(100), nullable=False, default="general")
    
    # 配置值
    value = Column(Text, nullable=True)
    value_type = Column(String(50), nullable=False, default="string")  # string, number, boolean, json, encrypted
    default_value = Column(Text, nullable=True)
    
    # 配置描述
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # 验证规则
    validation_rules = Column(JSON, nullable=True)  # JSON Schema格式的验证规则
    allowed_values = Column(JSON, nullable=True)  # 允许的值列表
    
    # 权限和可见性
    is_system = Column(Boolean, nullable=False, default=False)
    is_sensitive = Column(Boolean, nullable=False, default=False)
    is_encrypted = Column(Boolean, nullable=False, default=False)
    is_readonly = Column(Boolean, nullable=False, default=False)
    visible_level = Column(String(50), nullable=False, default="admin")  # admin, user, public
    
    # 覆盖信息
    is_overridden = Column(Boolean, nullable=False, default=False)
    override_source = Column(String(100), nullable=True)  # env, file, api
    override_value = Column(Text, nullable=True)
    
    # 应用信息
    requires_restart = Column(Boolean, nullable=False, default=False)
    restart_service = Column(String(100), nullable=True)
    
    # 管理信息
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)
    
    # 时间信息
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    last_applied_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<SystemConfig(id={self.id}, key='{self.key}', category='{self.category}')>"


class ToolRegistry(Base):
    """工具注册表"""
    __tablename__ = "tool_registry"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    tool_id = Column(String(36), nullable=False, unique=True, index=True, default=lambda: str(uuid4()))
    
    # 工具基本信息
    name = Column(String(100), nullable=False, unique=True)
    display_name = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    version = Column(String(50), nullable=False, default="1.0.0")
    
    # 工具分类
    category = Column(String(50), nullable=False, default="general")
    subcategory = Column(String(50), nullable=True)
    tags = Column(JSON, nullable=True, default=list)
    
    # 工具类型和来源
    tool_type = Column(String(50), nullable=False)  # builtin, custom, mcp, external, api
    source_type = Column(String(50), nullable=False)  # internal, external, plugin, service
    provider = Column(String(100), nullable=True)
    
    # 实现信息
    implementation_type = Column(String(50), nullable=False, default="python")  # python, api, mcp, shell
    module_path = Column(String(500), nullable=True)
    class_name = Column(String(200), nullable=True)
    function_name = Column(String(200), nullable=True)
    entry_point = Column(String(500), nullable=True)
    
    # 接口定义
    function_schema = Column(JSON, nullable=False)  # OpenAPI格式的函数定义
    parameters_schema = Column(JSON, nullable=True)  # 参数Schema
    return_schema = Column(JSON, nullable=True)  # 返回值Schema
    
    # 配置信息
    config_schema = Column(JSON, nullable=True)  # 配置Schema
    default_config = Column(JSON, nullable=True, default=dict)
    
    # 权限和访问控制
    permission_level = Column(String(50), nullable=False, default="user")  # admin, user, guest, system
    access_level = Column(String(50), nullable=False, default="public")  # public, private, restricted
    required_permissions = Column(JSON, nullable=True, default=list)
    
    # 运行时配置
    execution_timeout = Column(Integer, nullable=False, default=30)  # 秒
    max_retries = Column(Integer, nullable=False, default=3)
    rate_limit = Column(Integer, nullable=True)  # 每分钟最大调用次数
    
    # 缓存配置
    cache_enabled = Column(Boolean, nullable=False, default=False)
    cache_ttl = Column(Integer, nullable=False, default=300)  # 5分钟
    
    # 状态信息
    is_enabled = Column(Boolean, nullable=False, default=True)
    is_system = Column(Boolean, nullable=False, default=False)
    is_deprecated = Column(Boolean, nullable=False, default=False)
    health_status = Column(String(20), nullable=False, default="unknown")  # healthy, unhealthy, unknown
    
    # 统计信息
    total_calls = Column(Integer, nullable=False, default=0)
    success_calls = Column(Integer, nullable=False, default=0)
    error_calls = Column(Integer, nullable=False, default=0)
    avg_execution_time = Column(Float, nullable=True)
    
    # 管理信息
    created_by = Column(String(36), nullable=True)
    approved_by = Column(String(36), nullable=True)
    approval_status = Column(String(20), nullable=False, default="approved")  # pending, approved, rejected
    
    # 时间信息
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    last_used_at = Column(DateTime, nullable=True)
    last_health_check = Column(DateTime, nullable=True)
    
    # 关联关系
    executions = relationship("ExecutionLog", back_populates="tool", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ToolRegistry(id={self.id}, name='{self.name}', type='{self.tool_type}')>"


class ExecutionLog(Base):
    """执行日志表"""
    __tablename__ = "execution_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    execution_id = Column(String(36), nullable=False, unique=True, index=True, default=lambda: str(uuid4()))
    
    # 关联信息
    tool_id = Column(Integer, ForeignKey("tool_registry.id"), nullable=True)
    tool_name = Column(String(100), nullable=False)
    
    # 执行上下文
    execution_type = Column(String(50), nullable=False)  # tool_call, file_upload, sensitive_filter, policy_search, config_update
    service_name = Column(String(100), nullable=False, default="system-service")
    request_id = Column(String(100), nullable=True)
    session_id = Column(String(100), nullable=True)
    user_id = Column(String(36), nullable=True)
    
    # 执行参数
    input_parameters = Column(JSON, nullable=True)
    execution_config = Column(JSON, nullable=True)
    
    # 执行结果
    status = Column(String(20), nullable=False)  # pending, running, completed, failed, timeout, cancelled
    result_data = Column(JSON, nullable=True)
    output_size = Column(Integer, nullable=True)  # 输出数据大小（字节）
    
    # 错误信息
    error_type = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    error_code = Column(String(50), nullable=True)
    stack_trace = Column(Text, nullable=True)
    
    # 性能指标
    start_time = Column(DateTime, nullable=False, default=func.now())
    end_time = Column(DateTime, nullable=True)
    execution_time = Column(Float, nullable=True)  # 执行时间（秒）
    cpu_usage = Column(Float, nullable=True)  # CPU使用率
    memory_usage = Column(Float, nullable=True)  # 内存使用量（MB）
    
    # 重试信息
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    
    # 缓存信息
    cache_hit = Column(Boolean, nullable=False, default=False)
    cache_key = Column(String(255), nullable=True)
    
    # 时间信息
    created_at = Column(DateTime, nullable=False, default=func.now())
    
    # 关联关系
    tool = relationship("ToolRegistry", back_populates="executions")
    
    def __repr__(self):
        return f"<ExecutionLog(id={self.id}, tool='{self.tool_name}', status='{self.status}')>"


# 创建索引以提高查询性能
Index('idx_file_records_status', FileRecord.status)
Index('idx_file_records_user_id', FileRecord.user_id)
Index('idx_file_records_upload_time', FileRecord.upload_time)
Index('idx_file_records_file_hash', FileRecord.file_hash)

Index('idx_sensitive_words_category', SensitiveWord.category)
Index('idx_sensitive_words_enabled', SensitiveWord.is_enabled)
Index('idx_sensitive_words_hit_count', SensitiveWord.hit_count)

Index('idx_policy_search_active', PolicySearchConfig.is_active)
Index('idx_policy_search_default', PolicySearchConfig.is_default)

Index('idx_system_configs_category', SystemConfig.category)
Index('idx_system_configs_system', SystemConfig.is_system)
Index('idx_system_configs_sensitive', SystemConfig.is_sensitive)

Index('idx_tool_registry_category', ToolRegistry.category)
Index('idx_tool_registry_type', ToolRegistry.tool_type)
Index('idx_tool_registry_enabled', ToolRegistry.is_enabled)
Index('idx_tool_registry_health', ToolRegistry.health_status)

Index('idx_execution_logs_tool_name', ExecutionLog.tool_name)
Index('idx_execution_logs_status', ExecutionLog.status)
Index('idx_execution_logs_start_time', ExecutionLog.start_time)
Index('idx_execution_logs_user_id', ExecutionLog.user_id)
Index('idx_execution_logs_execution_type', ExecutionLog.execution_type) 