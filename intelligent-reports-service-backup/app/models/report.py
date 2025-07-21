"""
报告数据模型
"""
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
from sqlalchemy import Column, String, DateTime, Boolean, Text, JSON, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field
from app.models.base import Base, CreateRequestBase, UpdateRequestBase


class ReportStatus(str, Enum):
    """报告状态"""
    DRAFT = "draft"             # 草稿
    GENERATING = "generating"   # 生成中
    COMPLETED = "completed"     # 已完成
    FAILED = "failed"           # 失败
    CANCELLED = "cancelled"     # 已取消


class ReportType(str, Enum):
    """报告类型"""
    RESEARCH = "research"           # 研究报告
    ANALYSIS = "analysis"           # 分析报告
    SUMMARY = "summary"             # 总结报告
    COMPARISON = "comparison"       # 对比报告
    TECHNICAL = "technical"         # 技术报告
    BUSINESS = "business"           # 商业报告
    CUSTOM = "custom"               # 自定义报告


class ReportFormat(str, Enum):
    """报告格式"""
    HTML = "html"       # HTML格式
    PDF = "pdf"         # PDF格式
    MARKDOWN = "markdown"  # Markdown格式
    DOCX = "docx"       # Word格式
    JSON = "json"       # JSON格式


class ReportModel(Base):
    """报告数据模型"""
    
    __tablename__ = "reports"
    
    title = Column(String(500), nullable=False, comment="报告标题")
    description = Column(Text, comment="报告描述")
    type = Column(String(50), default=ReportType.CUSTOM, comment="报告类型")
    status = Column(String(50), default=ReportStatus.DRAFT, comment="报告状态")
    format = Column(String(50), default=ReportFormat.HTML, comment="报告格式")
    
    # 内容
    content = Column(Text, comment="报告内容")
    summary = Column(Text, comment="报告摘要")
    outline = Column(JSON, default=list, comment="报告大纲")
    
    # 生成信息
    input_query = Column(Text, comment="输入查询")
    input_data = Column(JSON, comment="输入数据")
    output_data = Column(JSON, comment="输出数据")
    generation_config = Column(JSON, default=dict, comment="生成配置")
    
    # 文件信息
    file_path = Column(String(500), comment="文件路径")
    file_size = Column(Integer, comment="文件大小(字节)")
    file_url = Column(String(500), comment="文件URL")
    attachments = Column(JSON, default=list, comment="附件列表")
    
    # 执行信息
    task_id = Column(UUID(as_uuid=True), comment="关联任务ID")
    agent_id = Column(UUID(as_uuid=True), comment="执行智能体ID")
    plan_id = Column(String(255), comment="执行计划ID")
    workspace_path = Column(String(500), comment="工作空间路径")
    
    # 时间信息
    started_at = Column(DateTime, comment="开始生成时间")
    completed_at = Column(DateTime, comment="完成时间")
    generation_time = Column(Integer, comment="生成时长(秒)")
    
    # 质量信息
    quality_score = Column(Integer, comment="质量评分(1-100)")
    word_count = Column(Integer, comment="字数")
    page_count = Column(Integer, comment="页数")
    
    # 用户信息
    user_id = Column(String(255), nullable=False, comment="用户ID")
    is_public = Column(Boolean, default=False, comment="是否公开")
    is_featured = Column(Boolean, default=False, comment="是否推荐")
    
    # 版本信息
    version = Column(String(50), default="1.0", comment="版本")
    parent_id = Column(UUID(as_uuid=True), comment="父报告ID")
    
    # 标签和分类
    tags = Column(JSON, default=list, comment="标签")
    category = Column(String(100), comment="分类")
    
    # 统计信息
    view_count = Column(Integer, default=0, comment="查看次数")
    download_count = Column(Integer, default=0, comment="下载次数")
    share_count = Column(Integer, default=0, comment="分享次数")
    
    def __repr__(self):
        return f"<Report {self.title}({self.status})>"
    
    def increment_view(self):
        """增加查看次数"""
        self.view_count += 1
        self.updated_at = datetime.now()
    
    def increment_download(self):
        """增加下载次数"""
        self.download_count += 1
        self.updated_at = datetime.now()
    
    def increment_share(self):
        """增加分享次数"""
        self.share_count += 1
        self.updated_at = datetime.now()
    
    def start_generation(self):
        """开始生成"""
        self.status = ReportStatus.GENERATING
        self.started_at = datetime.now()
        self.updated_at = datetime.now()
    
    def complete_generation(self, content: str = None, file_path: str = None):
        """完成生成"""
        self.status = ReportStatus.COMPLETED
        self.completed_at = datetime.now()
        self.updated_at = datetime.now()
        
        if content:
            self.content = content
            self.word_count = len(content)
        
        if file_path:
            self.file_path = file_path
        
        if self.started_at:
            duration = (self.completed_at - self.started_at).total_seconds()
            self.generation_time = int(duration)
    
    def fail_generation(self, error_message: str = None):
        """生成失败"""
        self.status = ReportStatus.FAILED
        self.updated_at = datetime.now()
        
        if error_message:
            if not self.output_data:
                self.output_data = {}
            self.output_data["error"] = error_message
    
    def cancel_generation(self):
        """取消生成"""
        self.status = ReportStatus.CANCELLED
        self.updated_at = datetime.now()
    
    def get_generation_duration(self) -> Optional[int]:
        """获取生成时长(秒)"""
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds())
        return None
    
    def is_generating(self) -> bool:
        """是否正在生成"""
        return self.status == ReportStatus.GENERATING
    
    def is_completed(self) -> bool:
        """是否已完成"""
        return self.status == ReportStatus.COMPLETED
    
    def is_failed(self) -> bool:
        """是否失败"""
        return self.status == ReportStatus.FAILED


# Pydantic 模型
class ReportBase(BaseModel):
    """报告基础模型"""
    
    title: str = Field(..., description="报告标题")
    description: Optional[str] = Field(None, description="报告描述")
    type: ReportType = Field(ReportType.CUSTOM, description="报告类型")
    format: ReportFormat = Field(ReportFormat.HTML, description="报告格式")
    
    class Config:
        use_enum_values = True


class ReportCreate(CreateRequestBase, ReportBase):
    """创建报告请求"""
    
    input_query: str = Field(..., description="输入查询")
    input_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="输入数据")
    generation_config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="生成配置")
    outline: Optional[List[str]] = Field(default_factory=list, description="报告大纲")
    tags: Optional[List[str]] = Field(default_factory=list, description="标签")
    category: Optional[str] = Field(None, description="分类")
    is_public: bool = Field(False, description="是否公开")


class ReportUpdate(UpdateRequestBase):
    """更新报告请求"""
    
    title: Optional[str] = Field(None, description="报告标题")
    description: Optional[str] = Field(None, description="报告描述")
    type: Optional[ReportType] = Field(None, description="报告类型")
    status: Optional[ReportStatus] = Field(None, description="报告状态")
    content: Optional[str] = Field(None, description="报告内容")
    summary: Optional[str] = Field(None, description="报告摘要")
    outline: Optional[List[str]] = Field(None, description="报告大纲")
    tags: Optional[List[str]] = Field(None, description="标签")
    category: Optional[str] = Field(None, description="分类")
    is_public: Optional[bool] = Field(None, description="是否公开")
    is_featured: Optional[bool] = Field(None, description="是否推荐")
    quality_score: Optional[int] = Field(None, ge=1, le=100, description="质量评分")


class ReportResponse(BaseModel):
    """报告响应模型"""
    
    id: str = Field(..., description="报告ID")
    title: str = Field(..., description="报告标题")
    description: Optional[str] = Field(None, description="报告描述")
    type: ReportType = Field(..., description="报告类型")
    status: ReportStatus = Field(..., description="报告状态")
    format: ReportFormat = Field(..., description="报告格式")
    
    content: Optional[str] = Field(None, description="报告内容")
    summary: Optional[str] = Field(None, description="报告摘要")
    outline: List[str] = Field(default_factory=list, description="报告大纲")
    
    input_query: Optional[str] = Field(None, description="输入查询")
    input_data: Optional[Dict[str, Any]] = Field(None, description="输入数据")
    output_data: Optional[Dict[str, Any]] = Field(None, description="输出数据")
    generation_config: Dict[str, Any] = Field(default_factory=dict, description="生成配置")
    
    file_path: Optional[str] = Field(None, description="文件路径")
    file_size: Optional[int] = Field(None, description="文件大小")
    file_url: Optional[str] = Field(None, description="文件URL")
    attachments: List[str] = Field(default_factory=list, description="附件列表")
    
    task_id: Optional[str] = Field(None, description="关联任务ID")
    agent_id: Optional[str] = Field(None, description="执行智能体ID")
    plan_id: Optional[str] = Field(None, description="执行计划ID")
    workspace_path: Optional[str] = Field(None, description="工作空间路径")
    
    started_at: Optional[datetime] = Field(None, description="开始生成时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    generation_time: Optional[int] = Field(None, description="生成时长(秒)")
    
    quality_score: Optional[int] = Field(None, description="质量评分")
    word_count: Optional[int] = Field(None, description="字数")
    page_count: Optional[int] = Field(None, description="页数")
    
    user_id: str = Field(..., description="用户ID")
    is_public: bool = Field(False, description="是否公开")
    is_featured: bool = Field(False, description="是否推荐")
    
    version: str = Field("1.0", description="版本")
    parent_id: Optional[str] = Field(None, description="父报告ID")
    
    tags: List[str] = Field(default_factory=list, description="标签")
    category: Optional[str] = Field(None, description="分类")
    
    view_count: int = Field(0, description="查看次数")
    download_count: int = Field(0, description="下载次数")
    share_count: int = Field(0, description="分享次数")
    
    created_at: datetime = Field(..., description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")
    
    class Config:
        from_attributes = True
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
        }


class ReportGenerateRequest(BaseModel):
    """报告生成请求"""
    
    query: str = Field(..., description="生成查询")
    type: ReportType = Field(ReportType.CUSTOM, description="报告类型")
    format: ReportFormat = Field(ReportFormat.HTML, description="报告格式")
    config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="生成配置")
    outline: Optional[List[str]] = Field(None, description="指定大纲")
    agent_id: Optional[str] = Field(None, description="指定智能体ID")
    workspace_path: Optional[str] = Field(None, description="工作空间路径")
    async_generation: bool = Field(True, description="是否异步生成")
    
    class Config:
        use_enum_values = True


class ReportGenerateResponse(BaseModel):
    """报告生成响应"""
    
    report_id: str = Field(..., description="报告ID")
    task_id: Optional[str] = Field(None, description="任务ID")
    status: str = Field(..., description="生成状态")
    message: str = Field(..., description="消息")
    estimated_time: Optional[int] = Field(None, description="预估完成时间(秒)")


class ReportSummary(BaseModel):
    """报告摘要"""
    
    id: str = Field(..., description="报告ID")
    title: str = Field(..., description="报告标题")
    type: ReportType = Field(..., description="报告类型")
    status: ReportStatus = Field(..., description="报告状态")
    format: ReportFormat = Field(..., description="报告格式")
    
    word_count: Optional[int] = Field(None, description="字数")
    quality_score: Optional[int] = Field(None, description="质量评分")
    
    user_id: str = Field(..., description="用户ID")
    is_public: bool = Field(False, description="是否公开")
    is_featured: bool = Field(False, description="是否推荐")
    
    view_count: int = Field(0, description="查看次数")
    download_count: int = Field(0, description="下载次数")
    
    created_at: datetime = Field(..., description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")
    
    class Config:
        from_attributes = True
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
        }


class ReportStatistics(BaseModel):
    """报告统计"""
    
    total_reports: int = Field(0, description="总报告数")
    completed_reports: int = Field(0, description="已完成报告数")
    generating_reports: int = Field(0, description="生成中报告数")
    failed_reports: int = Field(0, description="失败报告数")
    
    avg_generation_time: Optional[float] = Field(None, description="平均生成时间(秒)")
    avg_word_count: Optional[float] = Field(None, description="平均字数")
    avg_quality_score: Optional[float] = Field(None, description="平均质量评分")
    
    success_rate: float = Field(0.0, description="成功率")
    
    by_type: Dict[str, int] = Field(default_factory=dict, description="按类型统计")
    by_format: Dict[str, int] = Field(default_factory=dict, description="按格式统计")
    by_user: Dict[str, int] = Field(default_factory=dict, description="按用户统计")
    by_date: Dict[str, int] = Field(default_factory=dict, description="按日期统计")


class ReportSearchRequest(BaseModel):
    """报告搜索请求"""
    
    query: Optional[str] = Field(None, description="搜索关键词")
    type: Optional[ReportType] = Field(None, description="报告类型")
    status: Optional[ReportStatus] = Field(None, description="报告状态")
    format: Optional[ReportFormat] = Field(None, description="报告格式")
    category: Optional[str] = Field(None, description="分类")
    tags: Optional[List[str]] = Field(None, description="标签")
    user_id: Optional[str] = Field(None, description="用户ID")
    is_public: Optional[bool] = Field(None, description="是否公开")
    is_featured: Optional[bool] = Field(None, description="是否推荐")
    
    date_from: Optional[datetime] = Field(None, description="开始日期")
    date_to: Optional[datetime] = Field(None, description="结束日期")
    
    min_quality_score: Optional[int] = Field(None, ge=1, le=100, description="最低质量评分")
    min_word_count: Optional[int] = Field(None, description="最少字数")
    
    sort_by: str = Field("created_at", description="排序字段")
    sort_order: str = Field("desc", description="排序顺序")
    
    page: int = Field(1, ge=1, description="页码")
    size: int = Field(10, ge=1, le=100, description="每页数量")
    
    class Config:
        use_enum_values = True