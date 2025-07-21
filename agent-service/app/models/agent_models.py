"""
智能体服务数据库模型
定义智能体、DAG配置、工具加载等相关的数据库表结构
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON, Float, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
from uuid import uuid4
import datetime

Base = declarative_base()


class Agent(Base):
    """智能体表"""
    __tablename__ = "agents"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String(36), nullable=False, unique=True, index=True, default=lambda: str(uuid4()))
    
    # 基础信息
    name = Column(String(200), nullable=False, comment="智能体名称")
    display_name = Column(String(200), nullable=False, comment="显示名称")
    description = Column(Text, nullable=True, comment="智能体描述")
    version = Column(String(20), nullable=False, default="1.0.0", comment="版本号")
    
    # 模板和配置
    template_id = Column(String(50), nullable=False, comment="模板ID")
    template_name = Column(String(200), nullable=False, comment="模板名称")
    
    # 状态信息
    status = Column(String(20), nullable=False, default="draft", comment="状态")  # draft, active, inactive, deleted
    health_status = Column(String(20), nullable=False, default="unknown", comment="健康状态")
    
    # 用户信息
    user_id = Column(String(36), nullable=False, index=True, comment="创建用户ID")
    created_by = Column(String(36), nullable=False, comment="创建者用户ID")
    updated_by = Column(String(36), nullable=True, comment="更新者用户ID")
    
    # 配置数据
    basic_config = Column(JSON, nullable=False, default=dict, comment="基础配置")
    model_config = Column(JSON, nullable=False, default=dict, comment="模型配置")
    capability_config = Column(JSON, nullable=False, default=dict, comment="能力配置")
    advanced_config = Column(JSON, nullable=False, default=dict, comment="高级配置")
    
    # DAG配置
    dag_config = Column(JSON, nullable=True, comment="DAG配置")
    execution_graph = Column(JSON, nullable=True, comment="执行图配置")
    
    # 权限和可见性
    is_public = Column(Boolean, nullable=False, default=False, comment="是否公开")
    is_system = Column(Boolean, nullable=False, default=False, comment="是否系统内置")
    permission_level = Column(String(50), nullable=False, default="user", comment="权限级别")
    
    # 统计信息
    total_conversations = Column(Integer, nullable=False, default=0, comment="总对话数")
    total_messages = Column(Integer, nullable=False, default=0, comment="总消息数")
    total_tokens_used = Column(Integer, nullable=False, default=0, comment="总消耗令牌数")
    avg_response_time = Column(Float, nullable=True, comment="平均响应时间")
    success_rate = Column(Float, nullable=False, default=0.0, comment="成功率")
    
    # 元数据
    tags = Column(JSON, nullable=True, default=list, comment="标签列表")
    metadata = Column(JSON, nullable=True, default=dict, comment="元数据")
    
    # 时间信息
    created_at = Column(DateTime, nullable=False, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now(), comment="更新时间")
    last_active_at = Column(DateTime, nullable=True, comment="最后活跃时间")
    last_used_at = Column(DateTime, nullable=True, comment="最后使用时间")
    
    # 关系
    tool_configs = relationship("AgentToolConfig", back_populates="agent", cascade="all, delete-orphan")
    dag_executions = relationship("DAGExecution", back_populates="agent", cascade="all, delete-orphan")
    conversations = relationship("AgentConversation", back_populates="agent", cascade="all, delete-orphan")
    
    # 索引
    __table_args__ = (
        Index('idx_agents_user_status', 'user_id', 'status'),
        Index('idx_agents_template', 'template_id'),
        Index('idx_agents_created_at', 'created_at'),
        Index('idx_agents_health', 'health_status'),
    )


class AgentToolConfig(Base):
    """智能体工具配置表"""
    __tablename__ = "agent_tool_configs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    config_id = Column(String(36), nullable=False, unique=True, index=True, default=lambda: str(uuid4()))
    
    # 关联信息
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    
    # 工具信息
    tool_id = Column(String(100), nullable=False, comment="工具ID")
    tool_name = Column(String(100), nullable=False, comment="工具名称")
    tool_type = Column(String(50), nullable=False, comment="工具类型")  # builtin, mcp, external, system
    tool_category = Column(String(50), nullable=False, comment="工具分类")
    service_name = Column(String(100), nullable=True, comment="服务名称")
    
    # 配置信息
    tool_config = Column(JSON, nullable=False, default=dict, comment="工具配置")
    tool_schema = Column(JSON, nullable=True, comment="工具Schema")
    parameters = Column(JSON, nullable=True, comment="工具参数")
    
    # 状态信息
    is_enabled = Column(Boolean, nullable=False, default=True, comment="是否启用")
    is_available = Column(Boolean, nullable=False, default=True, comment="是否可用")
    load_mode = Column(String(20), nullable=False, default="auto", comment="加载模式")  # auto, manual, lazy
    priority = Column(Integer, nullable=False, default=0, comment="优先级")
    
    # 使用统计
    usage_count = Column(Integer, nullable=False, default=0, comment="使用次数")
    success_count = Column(Integer, nullable=False, default=0, comment="成功次数")
    error_count = Column(Integer, nullable=False, default=0, comment="错误次数")
    avg_execution_time = Column(Float, nullable=True, comment="平均执行时间")
    
    # 时间信息
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    last_used_at = Column(DateTime, nullable=True, comment="最后使用时间")
    
    # 关系
    agent = relationship("Agent", back_populates="tool_configs")
    
    # 索引
    __table_args__ = (
        Index('idx_tool_configs_agent', 'agent_id'),
        Index('idx_tool_configs_tool', 'tool_id'),
        Index('idx_tool_configs_enabled', 'is_enabled'),
    )


class DAGTemplate(Base):
    """DAG模板表"""
    __tablename__ = "dag_templates"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    template_id = Column(String(50), nullable=False, unique=True, index=True)
    
    # 基础信息
    name = Column(String(200), nullable=False, comment="模板名称")
    display_name = Column(String(200), nullable=False, comment="显示名称")
    description = Column(Text, nullable=True, comment="模板描述")
    category = Column(String(50), nullable=False, comment="模板分类")
    version = Column(String(20), nullable=False, default="1.0.0", comment="版本号")
    
    # 模板配置
    dag_definition = Column(JSON, nullable=False, comment="DAG定义")
    default_config = Column(JSON, nullable=False, default=dict, comment="默认配置")
    variables = Column(JSON, nullable=False, default=dict, comment="变量定义")
    
    # 节点和边
    nodes_config = Column(JSON, nullable=False, default=list, comment="节点配置")
    edges_config = Column(JSON, nullable=False, default=list, comment="边配置")
    
    # 状态信息
    is_active = Column(Boolean, nullable=False, default=True, comment="是否激活")
    is_system = Column(Boolean, nullable=False, default=False, comment="是否系统模板")
    
    # 元数据
    tags = Column(JSON, nullable=True, default=list, comment="标签")
    use_cases = Column(JSON, nullable=True, default=list, comment="使用场景")
    estimated_cost = Column(String(20), nullable=True, comment="预估成本")
    
    # 统计信息
    usage_count = Column(Integer, nullable=False, default=0, comment="使用次数")
    success_count = Column(Integer, nullable=False, default=0, comment="成功次数")
    
    # 时间信息
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    
    # 关系
    executions = relationship("DAGExecution", back_populates="template", cascade="all, delete-orphan")


class DAGExecution(Base):
    """DAG执行记录表"""
    __tablename__ = "dag_executions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    execution_id = Column(String(36), nullable=False, unique=True, index=True, default=lambda: str(uuid4()))
    
    # 关联信息
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    template_id = Column(Integer, ForeignKey("dag_templates.id"), nullable=False)
    user_id = Column(String(36), nullable=False, index=True, comment="执行用户ID")
    session_id = Column(String(36), nullable=True, comment="会话ID")
    
    # 执行配置
    input_data = Column(JSON, nullable=False, default=dict, comment="输入数据")
    config_overrides = Column(JSON, nullable=False, default=dict, comment="配置覆盖")
    execution_config = Column(JSON, nullable=False, default=dict, comment="执行配置")
    
    # 执行状态
    status = Column(String(20), nullable=False, default="pending", comment="执行状态")  # pending, running, completed, failed, cancelled
    progress = Column(Float, nullable=False, default=0.0, comment="执行进度")
    
    # 节点执行状态
    node_statuses = Column(JSON, nullable=False, default=dict, comment="节点状态")
    node_results = Column(JSON, nullable=False, default=dict, comment="节点结果")
    node_errors = Column(JSON, nullable=False, default=dict, comment="节点错误")
    execution_path = Column(JSON, nullable=False, default=list, comment="执行路径")
    
    # 执行结果
    final_result = Column(JSON, nullable=True, comment="最终结果")
    output_data = Column(JSON, nullable=True, comment="输出数据")
    
    # 性能指标
    start_time = Column(DateTime, nullable=True, comment="开始时间")
    end_time = Column(DateTime, nullable=True, comment="结束时间")
    execution_time = Column(Float, nullable=True, comment="执行时间(秒)")
    total_tokens = Column(Integer, nullable=False, default=0, comment="总消耗令牌")
    total_cost = Column(Float, nullable=False, default=0.0, comment="总成本")
    
    # 错误信息
    error_message = Column(Text, nullable=True, comment="错误消息")
    error_type = Column(String(100), nullable=True, comment="错误类型")
    stack_trace = Column(Text, nullable=True, comment="堆栈跟踪")
    
    # 元数据
    metadata = Column(JSON, nullable=False, default=dict, comment="元数据")
    
    # 时间信息
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    
    # 关系
    agent = relationship("Agent", back_populates="dag_executions")
    template = relationship("DAGTemplate", back_populates="executions")
    
    # 索引
    __table_args__ = (
        Index('idx_executions_agent', 'agent_id'),
        Index('idx_executions_user', 'user_id'),
        Index('idx_executions_status', 'status'),
        Index('idx_executions_created', 'created_at'),
    )


class AgentConversation(Base):
    """智能体对话记录表"""
    __tablename__ = "agent_conversations"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String(36), nullable=False, unique=True, index=True, default=lambda: str(uuid4()))
    
    # 关联信息
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    user_id = Column(String(36), nullable=False, index=True, comment="用户ID")
    session_id = Column(String(36), nullable=True, comment="会话ID")
    execution_id = Column(String(36), nullable=True, comment="执行ID")
    
    # 对话内容
    user_message = Column(Text, nullable=False, comment="用户消息")
    agent_response = Column(Text, nullable=True, comment="智能体回复")
    message_type = Column(String(20), nullable=False, default="text", comment="消息类型")
    
    # 执行信息
    execution_time = Column(Float, nullable=True, comment="执行时间")
    tokens_used = Column(Integer, nullable=False, default=0, comment="使用令牌数")
    cost = Column(Float, nullable=False, default=0.0, comment="成本")
    
    # 工具使用
    tools_used = Column(JSON, nullable=True, default=list, comment="使用的工具")
    tool_results = Column(JSON, nullable=True, default=dict, comment="工具执行结果")
    
    # 状态信息
    status = Column(String(20), nullable=False, default="completed", comment="状态")
    error_message = Column(Text, nullable=True, comment="错误消息")
    
    # 评价信息
    user_rating = Column(Integer, nullable=True, comment="用户评分")
    user_feedback = Column(Text, nullable=True, comment="用户反馈")
    
    # 元数据
    metadata = Column(JSON, nullable=False, default=dict, comment="元数据")
    
    # 时间信息
    created_at = Column(DateTime, nullable=False, default=func.now())
    
    # 关系
    agent = relationship("Agent", back_populates="conversations")
    
    # 索引
    __table_args__ = (
        Index('idx_conversations_agent', 'agent_id'),
        Index('idx_conversations_user', 'user_id'),
        Index('idx_conversations_session', 'session_id'),
        Index('idx_conversations_created', 'created_at'),
    )


class SystemToolRegistry(Base):
    """系统工具注册表"""
    __tablename__ = "system_tool_registry"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    tool_id = Column(String(100), nullable=False, unique=True, index=True)
    
    # 工具信息
    name = Column(String(100), nullable=False, comment="工具名称")
    display_name = Column(String(200), nullable=False, comment="显示名称")
    description = Column(Text, nullable=True, comment="工具描述")
    version = Column(String(20), nullable=False, default="1.0.0", comment="版本号")
    
    # 工具分类
    tool_type = Column(String(50), nullable=False, comment="工具类型")  # builtin, mcp, external, system
    category = Column(String(50), nullable=False, comment="工具分类")
    service_name = Column(String(100), nullable=True, comment="服务名称")
    provider = Column(String(100), nullable=True, comment="提供者")
    
    # 工具配置
    tool_schema = Column(JSON, nullable=False, comment="工具Schema")
    default_config = Column(JSON, nullable=False, default=dict, comment="默认配置")
    parameters_schema = Column(JSON, nullable=True, comment="参数Schema")
    
    # 服务信息
    service_url = Column(String(500), nullable=True, comment="服务URL")
    endpoint = Column(String(500), nullable=True, comment="调用端点")
    auth_config = Column(JSON, nullable=True, comment="认证配置")
    
    # 状态信息
    is_enabled = Column(Boolean, nullable=False, default=True, comment="是否启用")
    is_available = Column(Boolean, nullable=False, default=True, comment="是否可用")
    health_status = Column(String(20), nullable=False, default="unknown", comment="健康状态")
    
    # 权限和限制
    permission_level = Column(String(50), nullable=False, default="user", comment="权限级别")
    rate_limit = Column(Integer, nullable=True, comment="速率限制")
    timeout = Column(Integer, nullable=False, default=30, comment="超时时间")
    
    # 统计信息
    total_calls = Column(Integer, nullable=False, default=0, comment="总调用次数")
    success_calls = Column(Integer, nullable=False, default=0, comment="成功调用次数")
    error_calls = Column(Integer, nullable=False, default=0, comment="错误调用次数")
    avg_response_time = Column(Float, nullable=True, comment="平均响应时间")
    
    # 元数据
    tags = Column(JSON, nullable=True, default=list, comment="标签")
    metadata = Column(JSON, nullable=False, default=dict, comment="元数据")
    
    # 时间信息
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    last_health_check = Column(DateTime, nullable=True, comment="最后健康检查时间")
    last_used_at = Column(DateTime, nullable=True, comment="最后使用时间")
    
    # 索引
    __table_args__ = (
        Index('idx_tools_type_category', 'tool_type', 'category'),
        Index('idx_tools_service', 'service_name'),
        Index('idx_tools_enabled', 'is_enabled'),
        Index('idx_tools_health', 'health_status'),
    ) 