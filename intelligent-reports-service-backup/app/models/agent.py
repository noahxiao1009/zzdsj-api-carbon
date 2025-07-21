"""
智能体数据模型
"""
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
from sqlalchemy import Column, String, DateTime, Boolean, Text, JSON, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field
from app.models.base import Base, CreateRequestBase, UpdateRequestBase, StatusEnum


class AgentType(str, Enum):
    """智能体类型"""
    PLANNER = "planner"  # 规划智能体
    ACTOR = "actor"      # 执行智能体
    HYBRID = "hybrid"    # 混合智能体


class AgentStatus(str, Enum):
    """智能体状态"""
    IDLE = "idle"          # 空闲
    BUSY = "busy"          # 忙碌
    ERROR = "error"        # 错误
    OFFLINE = "offline"    # 离线


class AgentModel(Base):
    """智能体数据模型"""
    
    __tablename__ = "agents"
    
    name = Column(String(255), nullable=False, comment="智能体名称")
    display_name = Column(String(255), comment="显示名称")
    description = Column(Text, comment="描述")
    type = Column(String(50), nullable=False, comment="类型")
    status = Column(String(50), default=AgentStatus.IDLE, comment="状态")
    
    # 模板配置
    template_id = Column(String(255), comment="模板ID")
    template_name = Column(String(255), comment="模板名称")
    template_version = Column(String(50), comment="模板版本")
    
    # 配置信息
    configuration = Column(JSON, default=dict, comment="配置信息")
    model_config = Column(JSON, default=dict, comment="模型配置")
    tool_config = Column(JSON, default=dict, comment="工具配置")
    
    # 执行状态
    last_execution_at = Column(DateTime, comment="最后执行时间")
    execution_count = Column(Integer, default=0, comment="执行次数")
    success_count = Column(Integer, default=0, comment="成功次数")
    error_count = Column(Integer, default=0, comment="错误次数")
    
    # 关联关系
    user_id = Column(String(255), nullable=False, comment="用户ID")
    workspace_path = Column(String(500), comment="工作空间路径")
    
    # 能力配置
    skills = Column(JSON, default=list, comment="技能列表")
    tools = Column(JSON, default=list, comment="工具列表")
    max_iteration = Column(Integer, default=10, comment="最大迭代次数")
    
    def __repr__(self):
        return f"<Agent {self.name}({self.type})>"
    
    def is_available(self) -> bool:
        """检查智能体是否可用"""
        return self.status == AgentStatus.IDLE
    
    def update_status(self, status: AgentStatus):
        """更新状态"""
        self.status = status
        self.updated_at = datetime.now()
    
    def increment_execution(self, success: bool = True):
        """增加执行计数"""
        self.execution_count += 1
        self.last_execution_at = datetime.now()
        if success:
            self.success_count += 1
        else:
            self.error_count += 1
    
    def get_success_rate(self) -> float:
        """获取成功率"""
        if self.execution_count == 0:
            return 0.0
        return self.success_count / self.execution_count
    
    def add_skill(self, skill: Dict[str, Any]):
        """添加技能"""
        if not self.skills:
            self.skills = []
        self.skills.append(skill)
    
    def remove_skill(self, skill_name: str):
        """移除技能"""
        if self.skills:
            self.skills = [s for s in self.skills if s.get('name') != skill_name]
    
    def add_tool(self, tool: Dict[str, Any]):
        """添加工具"""
        if not self.tools:
            self.tools = []
        self.tools.append(tool)
    
    def remove_tool(self, tool_name: str):
        """移除工具"""
        if self.tools:
            self.tools = [t for t in self.tools if t.get('name') != tool_name]


class AgentTemplate(Base):
    """智能体模板"""
    
    __tablename__ = "agent_templates"
    
    name = Column(String(255), nullable=False, comment="模板名称")
    display_name = Column(String(255), comment="显示名称")
    description = Column(Text, comment="描述")
    type = Column(String(50), nullable=False, comment="类型")
    version = Column(String(50), default="1.0.0", comment="版本")
    
    # 模板配置
    configuration = Column(JSON, default=dict, comment="默认配置")
    model_config = Column(JSON, default=dict, comment="模型配置")
    tool_config = Column(JSON, default=dict, comment="工具配置")
    
    # 技能和工具
    skills = Column(JSON, default=list, comment="技能列表")
    tools = Column(JSON, default=list, comment="工具列表")
    
    # 提示词
    system_prompt = Column(Text, comment="系统提示词")
    user_prompt_template = Column(Text, comment="用户提示词模板")
    
    # 状态
    is_active = Column(Boolean, default=True, comment="是否激活")
    is_public = Column(Boolean, default=False, comment="是否公开")
    
    # 创建者
    created_by = Column(String(255), comment="创建者")
    
    def __repr__(self):
        return f"<AgentTemplate {self.name}({self.version})>"


class AgentExecution(Base):
    """智能体执行记录"""
    
    __tablename__ = "agent_executions"
    
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False, comment="智能体ID")
    task_id = Column(UUID(as_uuid=True), comment="任务ID")
    report_id = Column(UUID(as_uuid=True), comment="报告ID")
    
    # 执行信息
    input_data = Column(JSON, comment="输入数据")
    output_data = Column(JSON, comment="输出数据")
    execution_time = Column(Integer, comment="执行时间(毫秒)")
    
    # 状态
    status = Column(String(50), comment="执行状态")
    error_message = Column(Text, comment="错误信息")
    
    # 执行详情
    started_at = Column(DateTime, comment="开始时间")
    completed_at = Column(DateTime, comment="完成时间")
    
    # 关联关系
    agent = relationship("AgentModel", backref="executions")
    
    def __repr__(self):
        return f"<AgentExecution {self.id}>"
    
    def get_duration(self) -> Optional[int]:
        """获取执行时长"""
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds() * 1000)
        return None


# Pydantic 模型
class AgentBase(BaseModel):
    """智能体基础模型"""
    
    name: str = Field(..., description="智能体名称")
    display_name: Optional[str] = Field(None, description="显示名称")
    description: Optional[str] = Field(None, description="描述")
    type: AgentType = Field(..., description="类型")
    
    class Config:
        use_enum_values = True


class AgentCreate(CreateRequestBase, AgentBase):
    """创建智能体请求"""
    
    template_id: Optional[str] = Field(None, description="模板ID")
    configuration: Optional[Dict[str, Any]] = Field(default_factory=dict, description="配置信息")
    model_config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="模型配置")
    tool_config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="工具配置")
    skills: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="技能列表")
    tools: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="工具列表")
    max_iteration: Optional[int] = Field(10, description="最大迭代次数")
    workspace_path: Optional[str] = Field(None, description="工作空间路径")


class AgentUpdate(UpdateRequestBase):
    """更新智能体请求"""
    
    name: Optional[str] = Field(None, description="智能体名称")
    display_name: Optional[str] = Field(None, description="显示名称")
    description: Optional[str] = Field(None, description="描述")
    configuration: Optional[Dict[str, Any]] = Field(None, description="配置信息")
    model_config: Optional[Dict[str, Any]] = Field(None, description="模型配置")
    tool_config: Optional[Dict[str, Any]] = Field(None, description="工具配置")
    skills: Optional[List[Dict[str, Any]]] = Field(None, description="技能列表")
    tools: Optional[List[Dict[str, Any]]] = Field(None, description="工具列表")
    max_iteration: Optional[int] = Field(None, description="最大迭代次数")
    workspace_path: Optional[str] = Field(None, description="工作空间路径")


class AgentResponse(BaseModel):
    """智能体响应模型"""
    
    id: str = Field(..., description="智能体ID")
    name: str = Field(..., description="智能体名称")
    display_name: Optional[str] = Field(None, description="显示名称")
    description: Optional[str] = Field(None, description="描述")
    type: AgentType = Field(..., description="类型")
    status: AgentStatus = Field(..., description="状态")
    
    template_id: Optional[str] = Field(None, description="模板ID")
    template_name: Optional[str] = Field(None, description="模板名称")
    template_version: Optional[str] = Field(None, description="模板版本")
    
    configuration: Dict[str, Any] = Field(default_factory=dict, description="配置信息")
    model_config: Dict[str, Any] = Field(default_factory=dict, description="模型配置")
    tool_config: Dict[str, Any] = Field(default_factory=dict, description="工具配置")
    
    skills: List[Dict[str, Any]] = Field(default_factory=list, description="技能列表")
    tools: List[Dict[str, Any]] = Field(default_factory=list, description="工具列表")
    max_iteration: int = Field(10, description="最大迭代次数")
    
    user_id: str = Field(..., description="用户ID")
    workspace_path: Optional[str] = Field(None, description="工作空间路径")
    
    execution_count: int = Field(0, description="执行次数")
    success_count: int = Field(0, description="成功次数")
    error_count: int = Field(0, description="错误次数")
    last_execution_at: Optional[datetime] = Field(None, description="最后执行时间")
    
    created_at: datetime = Field(..., description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.execution_count == 0:
            return 0.0
        return self.success_count / self.execution_count
    
    class Config:
        from_attributes = True
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
        }


class AgentTemplateResponse(BaseModel):
    """智能体模板响应模型"""
    
    id: str = Field(..., description="模板ID")
    name: str = Field(..., description="模板名称")
    display_name: Optional[str] = Field(None, description="显示名称")
    description: Optional[str] = Field(None, description="描述")
    type: AgentType = Field(..., description="类型")
    version: str = Field(..., description="版本")
    
    configuration: Dict[str, Any] = Field(default_factory=dict, description="默认配置")
    model_config: Dict[str, Any] = Field(default_factory=dict, description="模型配置")
    tool_config: Dict[str, Any] = Field(default_factory=dict, description="工具配置")
    
    skills: List[Dict[str, Any]] = Field(default_factory=list, description="技能列表")
    tools: List[Dict[str, Any]] = Field(default_factory=list, description="工具列表")
    
    system_prompt: Optional[str] = Field(None, description="系统提示词")
    user_prompt_template: Optional[str] = Field(None, description="用户提示词模板")
    
    is_active: bool = Field(True, description="是否激活")
    is_public: bool = Field(False, description="是否公开")
    
    created_by: Optional[str] = Field(None, description="创建者")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")
    
    class Config:
        from_attributes = True
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
        }


class AgentExecutionResponse(BaseModel):
    """智能体执行响应模型"""
    
    id: str = Field(..., description="执行ID")
    agent_id: str = Field(..., description="智能体ID")
    task_id: Optional[str] = Field(None, description="任务ID")
    report_id: Optional[str] = Field(None, description="报告ID")
    
    input_data: Optional[Dict[str, Any]] = Field(None, description="输入数据")
    output_data: Optional[Dict[str, Any]] = Field(None, description="输出数据")
    execution_time: Optional[int] = Field(None, description="执行时间(毫秒)")
    
    status: str = Field(..., description="执行状态")
    error_message: Optional[str] = Field(None, description="错误信息")
    
    started_at: Optional[datetime] = Field(None, description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
        }


class AgentChatRequest(BaseModel):
    """智能体对话请求"""
    
    message: str = Field(..., description="消息内容")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="上下文")
    stream: bool = Field(False, description="是否流式响应")
    max_tokens: Optional[int] = Field(None, description="最大token数")
    temperature: Optional[float] = Field(None, description="温度")


class AgentChatResponse(BaseModel):
    """智能体对话响应"""
    
    message: str = Field(..., description="回复消息")
    usage: Optional[Dict[str, Any]] = Field(None, description="使用情况")
    context: Optional[Dict[str, Any]] = Field(None, description="上下文")
    tools_used: Optional[List[str]] = Field(None, description="使用的工具")
    execution_time: Optional[int] = Field(None, description="执行时间(毫秒)")