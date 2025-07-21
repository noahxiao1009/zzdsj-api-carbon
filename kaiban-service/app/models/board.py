"""
看板模型 - 工作流可视化看板的数据模型
"""

from sqlalchemy import Column, String, Text, DateTime, JSON, Boolean, Integer, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
import uuid

from .workflow import Base


class BoardType(str, Enum):
    """看板类型枚举"""
    KANBAN = "kanban"         # 看板模式
    TIMELINE = "timeline"     # 时间轴模式
    GANTT = "gantt"          # 甘特图模式
    DASHBOARD = "dashboard"   # 仪表板模式


class BoardStatus(str, Enum):
    """看板状态枚举"""
    ACTIVE = "active"         # 激活
    PAUSED = "paused"        # 暂停
    ARCHIVED = "archived"     # 归档


class Board(Base):
    """看板主表"""
    __tablename__ = "boards"
    
    # 基础字段
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=False)
    
    name = Column(String(255), nullable=False, comment="看板名称")
    description = Column(Text, comment="看板描述")
    
    # 看板配置
    board_type = Column(String(50), default=BoardType.KANBAN, comment="看板类型")
    status = Column(String(50), default=BoardStatus.ACTIVE, comment="看板状态")
    
    # 布局配置
    layout_config = Column(JSONB, comment="布局配置")
    display_config = Column(JSONB, comment="显示配置")
    theme_config = Column(JSONB, comment="主题配置")
    
    # 权限配置
    permissions = Column(JSONB, comment="权限配置")
    visibility = Column(String(50), default="private", comment="可见性")
    
    # 统计信息
    total_columns = Column(Integer, default=0, comment="总列数")
    total_tasks = Column(Integer, default=0, comment="总任务数")
    active_tasks = Column(Integer, default=0, comment="活跃任务数")
    
    # 时间字段
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
    last_accessed_at = Column(DateTime, comment="最后访问时间")
    
    # 关联关系
    workflow = relationship("Workflow", back_populates="boards")
    columns = relationship("BoardColumn", back_populates="board", cascade="all, delete-orphan")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": str(self.id),
            "workflow_id": str(self.workflow_id),
            "name": self.name,
            "description": self.description,
            "board_type": self.board_type,
            "status": self.status,
            "layout_config": self.layout_config,
            "display_config": self.display_config,
            "theme_config": self.theme_config,
            "permissions": self.permissions,
            "visibility": self.visibility,
            "total_columns": self.total_columns,
            "total_tasks": self.total_tasks,
            "active_tasks": self.active_tasks,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_accessed_at": self.last_accessed_at.isoformat() if self.last_accessed_at else None,
            "columns": [column.to_dict() for column in self.columns or []]
        }


class BoardColumn(Base):
    """看板列表"""
    __tablename__ = "board_columns"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    board_id = Column(UUID(as_uuid=True), ForeignKey("boards.id"), nullable=False)
    stage_id = Column(UUID(as_uuid=True), ForeignKey("workflow_stages.id"), nullable=True)
    
    # 列属性
    name = Column(String(255), nullable=False, comment="列名称")
    description = Column(Text, comment="列描述")
    color = Column(String(7), comment="列颜色")
    
    # 排序和位置
    order_index = Column(Integer, nullable=False, comment="列顺序")
    position_x = Column(Float, comment="X坐标")
    position_y = Column(Float, comment="Y坐标")
    width = Column(Float, comment="列宽度")
    
    # 配置属性
    config = Column(JSONB, comment="列配置")
    constraints = Column(JSONB, comment="约束条件")
    
    # 状态控制
    is_visible = Column(Boolean, default=True, comment="是否可见")
    is_collapsed = Column(Boolean, default=False, comment="是否折叠")
    max_tasks = Column(Integer, comment="最大任务数")
    min_tasks = Column(Integer, default=0, comment="最小任务数")
    
    # 统计信息
    task_count = Column(Integer, default=0, comment="任务数量")
    
    # 时间字段
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联关系
    board = relationship("Board", back_populates="columns")
    stage = relationship("WorkflowStage")
    tasks = relationship("Task", back_populates="column")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": str(self.id),
            "board_id": str(self.board_id),
            "stage_id": str(self.stage_id) if self.stage_id else None,
            "name": self.name,
            "description": self.description,
            "color": self.color,
            "order_index": self.order_index,
            "position_x": self.position_x,
            "position_y": self.position_y,
            "width": self.width,
            "config": self.config,
            "constraints": self.constraints,
            "is_visible": self.is_visible,
            "is_collapsed": self.is_collapsed,
            "max_tasks": self.max_tasks,
            "min_tasks": self.min_tasks,
            "task_count": self.task_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class BoardView(Base):
    """看板视图表"""
    __tablename__ = "board_views"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    board_id = Column(UUID(as_uuid=True), ForeignKey("boards.id"), nullable=False)
    
    # 视图属性
    name = Column(String(255), nullable=False, comment="视图名称")
    description = Column(Text, comment="视图描述")
    view_type = Column(String(50), comment="视图类型")
    
    # 视图配置
    filter_config = Column(JSONB, comment="过滤配置")
    sort_config = Column(JSONB, comment="排序配置")
    display_config = Column(JSONB, comment="显示配置")
    
    # 状态控制
    is_default = Column(Boolean, default=False, comment="是否默认视图")
    is_public = Column(Boolean, default=False, comment="是否公开视图")
    
    # 访问统计
    access_count = Column(Integer, default=0, comment="访问次数")
    
    # 时间字段
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_accessed_at = Column(DateTime, comment="最后访问时间")
    
    # 关联关系
    board = relationship("Board")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": str(self.id),
            "board_id": str(self.board_id),
            "name": self.name,
            "description": self.description,
            "view_type": self.view_type,
            "filter_config": self.filter_config,
            "sort_config": self.sort_config,
            "display_config": self.display_config,
            "is_default": self.is_default,
            "is_public": self.is_public,
            "access_count": self.access_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_accessed_at": self.last_accessed_at.isoformat() if self.last_accessed_at else None
        }


class BoardTemplate(Base):
    """看板模板表"""
    __tablename__ = "board_templates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 模板属性
    name = Column(String(255), nullable=False, comment="模板名称")
    description = Column(Text, comment="模板描述")
    category = Column(String(100), comment="模板分类")
    
    # 模板配置
    template_config = Column(JSONB, comment="模板配置")
    default_columns = Column(JSONB, comment="默认列配置")
    default_stages = Column(JSONB, comment="默认阶段配置")
    
    # 状态控制
    is_public = Column(Boolean, default=True, comment="是否公开")
    is_featured = Column(Boolean, default=False, comment="是否推荐")
    
    # 使用统计
    usage_count = Column(Integer, default=0, comment="使用次数")
    rating = Column(Float, default=0.0, comment="评分")
    
    # 时间字段
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "template_config": self.template_config,
            "default_columns": self.default_columns,
            "default_stages": self.default_stages,
            "is_public": self.is_public,
            "is_featured": self.is_featured,
            "usage_count": self.usage_count,
            "rating": self.rating,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        } 