"""
智能报告服务数据库模型定义
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()


class User(Base):
    """用户表"""
    __tablename__ = 'users'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(100), unique=True, nullable=False, comment='用户名')
    email = Column(String(100), unique=True, nullable=False, comment='邮箱')
    password_hash = Column(String(255), nullable=False, comment='密码哈希')
    full_name = Column(String(100), comment='全名')
    avatar_url = Column(String(255), comment='头像URL')
    is_active = Column(Boolean, default=True, comment='是否激活')
    is_admin = Column(Boolean, default=False, comment='是否管理员')
    created_at = Column(DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')
    
    # 关联关系
    reports = relationship("Report", back_populates="user")
    sessions = relationship("ReportSession", back_populates="user")


class Report(Base):
    """报告表"""
    __tablename__ = 'reports'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False, comment='用户ID')
    title = Column(String(200), nullable=False, comment='报告标题')
    description = Column(Text, comment='报告描述')
    query = Column(Text, nullable=False, comment='生成查询')
    output_format = Column(String(50), comment='输出格式')
    status = Column(String(20), default='pending', comment='状态: pending, processing, completed, failed')
    result_summary = Column(Text, comment='结果摘要')
    workspace_path = Column(String(500), comment='工作空间路径')
    plan_id = Column(String(100), comment='计划ID')
    
    # 统计信息
    total_steps = Column(Integer, default=0, comment='总步骤数')
    completed_steps = Column(Integer, default=0, comment='已完成步骤数')
    progress_percentage = Column(Float, default=0.0, comment='进度百分比')
    
    # 时间信息
    started_at = Column(DateTime, comment='开始时间')
    completed_at = Column(DateTime, comment='完成时间')
    created_at = Column(DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')
    
    # 关联关系
    user = relationship("User", back_populates="reports")
    files = relationship("ReportFile", back_populates="report")
    tasks = relationship("ReportTask", back_populates="report")
    logs = relationship("ReportLog", back_populates="report")


class ReportFile(Base):
    """报告文件表"""
    __tablename__ = 'report_files'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id = Column(String(36), ForeignKey('reports.id'), nullable=False, comment='报告ID')
    filename = Column(String(255), nullable=False, comment='文件名')
    file_path = Column(String(500), nullable=False, comment='文件路径')
    file_size = Column(Integer, comment='文件大小(字节)')
    file_type = Column(String(50), comment='文件类型')
    mime_type = Column(String(100), comment='MIME类型')
    is_main_output = Column(Boolean, default=False, comment='是否为主输出文件')
    download_count = Column(Integer, default=0, comment='下载次数')
    created_at = Column(DateTime, default=datetime.utcnow, comment='创建时间')
    
    # 关联关系
    report = relationship("Report", back_populates="files")


class ReportTask(Base):
    """报告任务表"""
    __tablename__ = 'report_tasks'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id = Column(String(36), ForeignKey('reports.id'), nullable=False, comment='报告ID')
    task_index = Column(Integer, nullable=False, comment='任务索引')
    task_name = Column(String(200), comment='任务名称')
    task_description = Column(Text, comment='任务描述')
    task_type = Column(String(50), comment='任务类型: planning, execution, tool_call')
    status = Column(String(20), default='pending', comment='状态: pending, running, completed, failed')
    
    # 任务内容
    input_data = Column(JSON, comment='输入数据')
    output_data = Column(JSON, comment='输出数据')
    error_message = Column(Text, comment='错误信息')
    
    # 时间信息
    started_at = Column(DateTime, comment='开始时间')
    completed_at = Column(DateTime, comment='完成时间')
    duration_seconds = Column(Float, comment='执行时长(秒)')
    created_at = Column(DateTime, default=datetime.utcnow, comment='创建时间')
    
    # 关联关系
    report = relationship("Report", back_populates="tasks")


class ReportSession(Base):
    """报告会话表"""
    __tablename__ = 'report_sessions'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id'), comment='用户ID')
    session_id = Column(String(100), unique=True, nullable=False, comment='会话ID')
    status = Column(String(20), default='active', comment='状态: active, expired, closed')
    workspace_path = Column(String(500), comment='工作空间路径')
    
    # 会话统计
    total_reports = Column(Integer, default=0, comment='总报告数')
    successful_reports = Column(Integer, default=0, comment='成功报告数')
    failed_reports = Column(Integer, default=0, comment='失败报告数')
    
    # 时间信息
    last_activity_at = Column(DateTime, default=datetime.utcnow, comment='最后活动时间')
    expires_at = Column(DateTime, comment='过期时间')
    created_at = Column(DateTime, default=datetime.utcnow, comment='创建时间')
    
    # 关联关系
    user = relationship("User", back_populates="sessions")


class ReportLog(Base):
    """报告日志表"""
    __tablename__ = 'report_logs'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id = Column(String(36), ForeignKey('reports.id'), comment='报告ID')
    session_id = Column(String(100), comment='会话ID')
    log_level = Column(String(20), nullable=False, comment='日志级别: DEBUG, INFO, WARNING, ERROR')
    log_message = Column(Text, nullable=False, comment='日志消息')
    log_context = Column(JSON, comment='日志上下文')
    source = Column(String(100), comment='日志来源')
    created_at = Column(DateTime, default=datetime.utcnow, comment='创建时间')
    
    # 关联关系
    report = relationship("Report", back_populates="logs")


class ModelUsage(Base):
    """模型使用记录表"""
    __tablename__ = 'model_usage'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id'), comment='用户ID')
    report_id = Column(String(36), ForeignKey('reports.id'), comment='报告ID')
    model_provider = Column(String(50), nullable=False, comment='模型提供商')
    model_name = Column(String(100), nullable=False, comment='模型名称')
    model_type = Column(String(50), comment='模型类型: planning, execution, tool, vision')
    
    # 使用统计
    input_tokens = Column(Integer, default=0, comment='输入Token数')
    output_tokens = Column(Integer, default=0, comment='输出Token数')
    total_tokens = Column(Integer, default=0, comment='总Token数')
    api_calls = Column(Integer, default=1, comment='API调用次数')
    
    # 成本信息
    input_cost = Column(Float, default=0.0, comment='输入成本')
    output_cost = Column(Float, default=0.0, comment='输出成本')
    total_cost = Column(Float, default=0.0, comment='总成本')
    
    # 性能信息
    latency_ms = Column(Float, comment='延迟(毫秒)')
    success = Column(Boolean, default=True, comment='是否成功')
    error_message = Column(Text, comment='错误信息')
    
    created_at = Column(DateTime, default=datetime.utcnow, comment='创建时间')


class SystemConfig(Base):
    """系统配置表"""
    __tablename__ = 'system_configs'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    config_key = Column(String(100), unique=True, nullable=False, comment='配置键')
    config_value = Column(JSON, comment='配置值')
    config_type = Column(String(50), comment='配置类型')
    description = Column(Text, comment='配置描述')
    is_encrypted = Column(Boolean, default=False, comment='是否加密')
    created_at = Column(DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')


class UserQuota(Base):
    """用户配额表"""
    __tablename__ = 'user_quotas'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id'), unique=True, nullable=False, comment='用户ID')
    
    # 报告配额
    daily_report_limit = Column(Integer, default=10, comment='每日报告限制')
    monthly_report_limit = Column(Integer, default=100, comment='每月报告限制')
    daily_report_used = Column(Integer, default=0, comment='每日已使用报告数')
    monthly_report_used = Column(Integer, default=0, comment='每月已使用报告数')
    
    # Token配额
    daily_token_limit = Column(Integer, default=100000, comment='每日Token限制')
    monthly_token_limit = Column(Integer, default=1000000, comment='每月Token限制')
    daily_token_used = Column(Integer, default=0, comment='每日已使用Token数')
    monthly_token_used = Column(Integer, default=0, comment='每月已使用Token数')
    
    # 存储配额
    storage_limit_mb = Column(Integer, default=1024, comment='存储限制(MB)')
    storage_used_mb = Column(Float, default=0.0, comment='已使用存储(MB)')
    
    # 重置时间
    daily_reset_at = Column(DateTime, comment='每日重置时间')
    monthly_reset_at = Column(DateTime, comment='每月重置时间')
    
    created_at = Column(DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')


class ReportTemplate(Base):
    """报告模板表"""
    __tablename__ = 'report_templates'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False, comment='模板名称')
    description = Column(Text, comment='模板描述')
    category = Column(String(50), comment='模板分类')
    template_query = Column(Text, nullable=False, comment='模板查询')
    default_format = Column(String(50), comment='默认输出格式')
    
    # 模板配置
    config = Column(JSON, comment='模板配置')
    variables = Column(JSON, comment='模板变量')
    
    # 统计信息
    usage_count = Column(Integer, default=0, comment='使用次数')
    is_public = Column(Boolean, default=False, comment='是否公开')
    is_active = Column(Boolean, default=True, comment='是否激活')
    
    # 创建者信息
    created_by = Column(String(36), ForeignKey('users.id'), comment='创建者ID')
    
    created_at = Column(DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')