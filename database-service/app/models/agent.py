"""
智能体模型模块: 智能体定义、模板、运行和编排相关的数据库模型
"""

from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, JSON, Boolean, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import ARRAY
from typing import List, Dict, Any, Optional

from .database import Base


class AgentDefinition(Base):
    """智能体定义模型"""
    __tablename__ = "agent_definitions"
    
    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="智能体名称")
    description = Column(Text, comment="智能体描述")
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment="创建用户ID")
    
    # 智能体配置
    agent_type = Column(String(50), nullable=False, comment="智能体类型")
    framework = Column(String(50), default="agno", comment="使用框架")
    model = Column(String(100), comment="使用模型")
    system_prompt = Column(Text, comment="系统提示词")
    
    # 能力配置
    capabilities = Column(JSON, comment="能力列表")
    tools = Column(JSON, comment="工具配置")
    knowledge_bases = Column(ARRAY(String), comment="关联知识库ID列表")
    
    # 执行配置
    execution_config = Column(JSON, comment="执行配置")
    workflow_config = Column(JSON, comment="工作流配置")
    
    # 状态信息
    is_active = Column(Boolean, default=True, comment="是否激活")
    is_public = Column(Boolean, default=False, comment="是否公开")
    status = Column(String(20), default="draft", comment="状态")
    
    # 版本信息
    version = Column(String(20), default="1.0", comment="版本")
    parent_id = Column(String(36), comment="父版本ID")
    
    # 统计信息
    usage_count = Column(Integer, default=0, comment="使用次数")
    success_rate = Column(Float, default=0.0, comment="成功率")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), comment="更新时间")
    published_at = Column(DateTime(timezone=True), comment="发布时间")
    
    # 关系
    runs = relationship("AgentRun", back_populates="agent_definition", cascade="all, delete-orphan")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "user_id": self.user_id,
            "agent_type": self.agent_type,
            "framework": self.framework,
            "model": self.model,
            "system_prompt": self.system_prompt,
            "capabilities": self.capabilities,
            "tools": self.tools,
            "knowledge_bases": self.knowledge_bases,
            "execution_config": self.execution_config,
            "workflow_config": self.workflow_config,
            "is_active": self.is_active,
            "is_public": self.is_public,
            "status": self.status,
            "version": self.version,
            "parent_id": self.parent_id,
            "usage_count": self.usage_count,
            "success_rate": self.success_rate,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "published_at": self.published_at.isoformat() if self.published_at else None
        }


class AgentTemplate(Base):
    """智能体模板模型"""
    __tablename__ = "agent_templates"
    
    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="模板名称")
    description = Column(Text, comment="模板描述")
    category = Column(String(50), comment="模板分类")
    
    # 模板级别
    level = Column(String(20), nullable=False, comment="模板级别")  # basic/enhanced/expert
    difficulty = Column(Integer, default=1, comment="难度等级")
    
    # 模板配置
    template_config = Column(JSON, nullable=False, comment="模板配置")
    dag_config = Column(JSON, comment="DAG配置")
    default_tools = Column(JSON, comment="默认工具")
    required_capabilities = Column(ARRAY(String), comment="必需能力")
    
    # 元数据
    tags = Column(ARRAY(String), comment="标签")
    icon = Column(String(255), comment="图标URL")
    
    # 状态信息
    is_active = Column(Boolean, default=True, comment="是否激活")
    is_system = Column(Boolean, default=False, comment="是否系统模板")
    
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
            "level": self.level,
            "difficulty": self.difficulty,
            "template_config": self.template_config,
            "dag_config": self.dag_config,
            "default_tools": self.default_tools,
            "required_capabilities": self.required_capabilities,
            "tags": self.tags,
            "icon": self.icon,
            "is_active": self.is_active,
            "is_system": self.is_system,
            "usage_count": self.usage_count,
            "rating": self.rating,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class AgentRun(Base):
    """智能体运行记录模型"""
    __tablename__ = "agent_runs"
    
    id = Column(String(36), primary_key=True, index=True)
    agent_definition_id = Column(String(36), ForeignKey("agent_definitions.id"), nullable=False, comment="智能体定义ID")
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment="用户ID")
    
    # 运行信息
    run_name = Column(String(100), comment="运行名称")
    input_data = Column(JSON, comment="输入数据")
    output_data = Column(JSON, comment="输出数据")
    
    # 执行状态
    status = Column(String(20), default="pending", comment="执行状态")
    progress = Column(Float, default=0.0, comment="执行进度")
    error_message = Column(Text, comment="错误信息")
    
    # 执行配置
    execution_config = Column(JSON, comment="执行配置")
    runtime_config = Column(JSON, comment="运行时配置")
    
    # 性能指标
    start_time = Column(DateTime(timezone=True), comment="开始时间")
    end_time = Column(DateTime(timezone=True), comment="结束时间")
    execution_time = Column(Float, comment="执行时间（秒）")
    token_usage = Column(Integer, comment="Token使用量")
    cost = Column(Float, comment="成本")
    
    # 结果评估
    success = Column(Boolean, comment="是否成功")
    quality_score = Column(Float, comment="质量分数")
    user_rating = Column(Integer, comment="用户评分")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), comment="更新时间")
    
    # 关系
    agent_definition = relationship("AgentDefinition", back_populates="runs")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "agent_definition_id": self.agent_definition_id,
            "user_id": self.user_id,
            "run_name": self.run_name,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "status": self.status,
            "progress": self.progress,
            "error_message": self.error_message,
            "execution_config": self.execution_config,
            "runtime_config": self.runtime_config,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "execution_time": self.execution_time,
            "token_usage": self.token_usage,
            "cost": self.cost,
            "success": self.success,
            "quality_score": self.quality_score,
            "user_rating": self.user_rating,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class AgentChain(Base):
    """智能体链模型"""
    __tablename__ = "agent_chains"
    
    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="链名称")
    description = Column(Text, comment="链描述")
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment="创建用户ID")
    
    # 链配置
    chain_config = Column(JSON, nullable=False, comment="链配置")
    agents = Column(JSON, nullable=False, comment="智能体列表")
    flow_config = Column(JSON, comment="流程配置")
    
    # 状态信息
    is_active = Column(Boolean, default=True, comment="是否激活")
    status = Column(String(20), default="draft", comment="状态")
    
    # 统计信息
    execution_count = Column(Integer, default=0, comment="执行次数")
    success_rate = Column(Float, default=0.0, comment="成功率")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), comment="更新时间")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "user_id": self.user_id,
            "chain_config": self.chain_config,
            "agents": self.agents,
            "flow_config": self.flow_config,
            "is_active": self.is_active,
            "status": self.status,
            "execution_count": self.execution_count,
            "success_rate": self.success_rate,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class AgentOrchestration(Base):
    """智能体编排模型"""
    __tablename__ = "agent_orchestrations"
    
    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="编排名称")
    description = Column(Text, comment="编排描述")
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment="创建用户ID")
    assistant_id = Column(String(36), ForeignKey("assistants.id"), comment="关联助手ID")
    
    # 编排配置
    orchestration_type = Column(String(50), nullable=False, comment="编排类型")
    workflow_definition = Column(JSON, nullable=False, comment="工作流定义")
    dag_definition = Column(JSON, comment="DAG定义")
    
    # 参与者配置
    agents = Column(JSON, comment="智能体配置")
    tools = Column(JSON, comment="工具配置")
    services = Column(JSON, comment="服务配置")
    
    # 执行配置
    execution_strategy = Column(String(50), default="sequential", comment="执行策略")
    retry_config = Column(JSON, comment="重试配置")
    timeout_config = Column(JSON, comment="超时配置")
    
    # 状态信息
    is_active = Column(Boolean, default=True, comment="是否激活")
    status = Column(String(20), default="draft", comment="状态")
    
    # 统计信息
    execution_count = Column(Integer, default=0, comment="执行次数")
    success_rate = Column(Float, default=0.0, comment="成功率")
    avg_execution_time = Column(Float, comment="平均执行时间")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), comment="更新时间")
    last_executed_at = Column(DateTime(timezone=True), comment="最后执行时间")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "user_id": self.user_id,
            "assistant_id": self.assistant_id,
            "orchestration_type": self.orchestration_type,
            "workflow_definition": self.workflow_definition,
            "dag_definition": self.dag_definition,
            "agents": self.agents,
            "tools": self.tools,
            "services": self.services,
            "execution_strategy": self.execution_strategy,
            "retry_config": self.retry_config,
            "timeout_config": self.timeout_config,
            "is_active": self.is_active,
            "status": self.status,
            "execution_count": self.execution_count,
            "success_rate": self.success_rate,
            "avg_execution_time": self.avg_execution_time,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_executed_at": self.last_executed_at.isoformat() if self.last_executed_at else None
        }