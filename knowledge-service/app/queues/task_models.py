"""
任务数据模型
定义队列任务的数据结构和状态
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"      # 等待处理
    PROCESSING = "processing"  # 正在处理
    COMPLETED = "completed"    # 处理完成
    FAILED = "failed"         # 处理失败
    CANCELLED = "cancelled"    # 已取消


class TaskModel(BaseModel):
    """基础任务模型"""
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="任务ID")
    task_type: str = Field(..., description="任务类型")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="任务状态")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    started_at: Optional[datetime] = Field(default=None, description="开始时间")
    completed_at: Optional[datetime] = Field(default=None, description="完成时间")
    progress: int = Field(default=0, description="进度百分比 (0-100)")
    message: str = Field(default="", description="状态消息")
    error_message: str = Field(default="", description="错误消息")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="任务元数据")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ProcessingTaskModel(TaskModel):
    """文档处理任务模型"""
    task_type: str = Field(default="document_processing", description="任务类型")
    
    # 用户信息
    user_id: Optional[str] = Field(default=None, description="用户ID（用于SSE推送）")
    
    # 知识库信息
    kb_id: str = Field(..., description="知识库ID")
    kb_name: str = Field(default="", description="知识库名称")
    
    # 文件信息
    file_info: Dict[str, Any] = Field(..., description="文件信息")
    file_path: str = Field(..., description="文件路径")
    original_filename: str = Field(..., description="原始文件名")
    file_size: int = Field(default=0, description="文件大小(字节)")
    file_type: str = Field(default="", description="文件类型")
    
    # 处理配置
    splitter_strategy_id: Optional[str] = Field(default=None, description="切分策略ID")
    custom_splitter_config: Optional[Dict[str, Any]] = Field(default=None, description="自定义切分配置")
    processing_options: Dict[str, Any] = Field(default_factory=dict, description="处理选项")
    
    # 处理结果
    chunks_count: int = Field(default=0, description="生成的分块数量")
    embedding_count: int = Field(default=0, description="嵌入向量数量")
    processing_duration: float = Field(default=0.0, description="处理耗时(秒)")
    
    # 回调配置
    callback_url: Optional[str] = Field(default=None, description="回调URL")
    webhook_config: Optional[Dict[str, Any]] = Field(default=None, description="Webhook配置")


class BatchProcessingTaskModel(TaskModel):
    """批量处理任务模型"""
    task_type: str = Field(default="batch_processing", description="任务类型")
    
    # 批量任务信息
    kb_id: str = Field(..., description="知识库ID")
    sub_tasks: List[str] = Field(default_factory=list, description="子任务ID列表")
    total_files: int = Field(default=0, description="总文件数量")
    completed_files: int = Field(default=0, description="已完成文件数量")
    failed_files: int = Field(default=0, description="失败文件数量")
    
    # 批量配置
    splitter_strategy_id: Optional[str] = Field(default=None, description="统一切分策略ID")
    processing_options: Dict[str, Any] = Field(default_factory=dict, description="批量处理选项")


class TaskUpdateModel(BaseModel):
    """任务更新模型"""
    status: Optional[TaskStatus] = Field(default=None, description="任务状态")
    progress: Optional[int] = Field(default=None, description="进度百分比")
    message: Optional[str] = Field(default=None, description="状态消息")
    error_message: Optional[str] = Field(default=None, description="错误消息")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="任务元数据")


class TaskQueryModel(BaseModel):
    """任务查询模型"""
    task_ids: Optional[List[str]] = Field(default=None, description="任务ID列表")
    task_types: Optional[List[str]] = Field(default=None, description="任务类型列表")
    statuses: Optional[List[TaskStatus]] = Field(default=None, description="状态列表")
    kb_id: Optional[str] = Field(default=None, description="知识库ID")
    created_after: Optional[datetime] = Field(default=None, description="创建时间起始")
    created_before: Optional[datetime] = Field(default=None, description="创建时间结束")
    limit: int = Field(default=100, description="查询限制")
    offset: int = Field(default=0, description="查询偏移")


# 任务类型常量
class TaskTypes:
    """任务类型常量"""
    DOCUMENT_PROCESSING = "document_processing"
    BATCH_PROCESSING = "batch_processing"
    KNOWLEDGE_INDEXING = "knowledge_indexing"
    EMBEDDING_GENERATION = "embedding_generation"
    VECTOR_STORAGE = "vector_storage"