"""
知识图谱项目数据模型
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum

class ProjectStatus(str, Enum):
    """项目状态"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"

class ProjectType(str, Enum):
    """项目类型"""
    KNOWLEDGE_BASE = "knowledge_base"
    DOCUMENT_SET = "document_set"
    CUSTOM = "custom"

class ProjectPermission(str, Enum):
    """项目权限"""
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"

class ProjectMember(BaseModel):
    """项目成员"""
    user_id: str = Field(..., description="用户ID")
    permission: ProjectPermission = Field(..., description="权限")
    added_at: datetime = Field(default_factory=datetime.now, description="添加时间")
    added_by: str = Field(..., description="添加者ID")

class ProjectSettings(BaseModel):
    """项目设置"""
    # 图谱生成设置
    chunk_size: int = Field(default=500, description="文本分块大小")
    confidence_threshold: float = Field(default=0.7, description="置信度阈值")
    max_entities: int = Field(default=1000, description="最大实体数量")
    max_relations: int = Field(default=5000, description="最大关系数量")
    
    # 处理设置
    enable_standardization: bool = Field(default=True, description="启用实体标准化")
    enable_inference: bool = Field(default=True, description="启用关系推理")
    enable_clustering: bool = Field(default=True, description="启用聚类")
    
    # 可视化设置
    visualization_theme: str = Field(default="light", description="可视化主题")
    physics_enabled: bool = Field(default=True, description="启用物理模拟")
    show_labels: bool = Field(default=True, description="显示标签")
    
    # 自定义设置
    custom_config: Dict[str, Any] = Field(default_factory=dict, description="自定义配置")

class ProjectStatistics(BaseModel):
    """项目统计信息"""
    total_graphs: int = Field(default=0, description="总图谱数量")
    total_entities: int = Field(default=0, description="总实体数量")
    total_relations: int = Field(default=0, description="总关系数量")
    total_documents: int = Field(default=0, description="总文档数量")
    
    # 状态统计
    active_tasks: int = Field(default=0, description="活跃任务数")
    completed_tasks: int = Field(default=0, description="已完成任务数")
    failed_tasks: int = Field(default=0, description="失败任务数")
    
    # 存储统计
    storage_used: int = Field(default=0, description="使用的存储空间(字节)")
    last_activity: Optional[datetime] = Field(default=None, description="最后活动时间")

class KnowledgeGraphProject(BaseModel):
    """知识图谱项目模型"""
    
    # 基础信息
    project_id: str = Field(..., description="项目ID")
    name: str = Field(..., description="项目名称")
    description: Optional[str] = Field(None, description="项目描述")
    project_type: ProjectType = Field(default=ProjectType.DOCUMENT_SET, description="项目类型")
    status: ProjectStatus = Field(default=ProjectStatus.ACTIVE, description="项目状态")
    
    # 所有者信息
    owner_id: str = Field(..., description="所有者ID")
    organization_id: Optional[str] = Field(None, description="组织ID")
    
    # 成员管理
    members: List[ProjectMember] = Field(default_factory=list, description="项目成员")
    
    # 关联资源
    knowledge_base_ids: List[str] = Field(default_factory=list, description="关联知识库ID列表")
    document_ids: List[str] = Field(default_factory=list, description="关联文档ID列表")
    
    # 项目设置
    settings: ProjectSettings = Field(default_factory=ProjectSettings, description="项目设置")
    
    # 统计信息
    statistics: ProjectStatistics = Field(default_factory=ProjectStatistics, description="统计信息")
    
    # 标签和元数据
    tags: List[str] = Field(default_factory=list, description="项目标签")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    
    # 时间信息
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    last_accessed_at: Optional[datetime] = Field(None, description="最后访问时间")
    
    # 版本控制
    version: str = Field(default="1.0.0", description="项目版本")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ProjectCreateRequest(BaseModel):
    """项目创建请求"""
    name: str = Field(..., description="项目名称")
    description: Optional[str] = Field(None, description="项目描述")
    project_type: ProjectType = Field(default=ProjectType.DOCUMENT_SET, description="项目类型")
    knowledge_base_ids: List[str] = Field(default_factory=list, description="关联知识库ID列表")
    tags: List[str] = Field(default_factory=list, description="项目标签")
    settings: Optional[ProjectSettings] = Field(None, description="项目设置")

class ProjectUpdateRequest(BaseModel):
    """项目更新请求"""
    name: Optional[str] = Field(None, description="项目名称")
    description: Optional[str] = Field(None, description="项目描述")
    status: Optional[ProjectStatus] = Field(None, description="项目状态")
    knowledge_base_ids: Optional[List[str]] = Field(None, description="关联知识库ID列表")
    tags: Optional[List[str]] = Field(None, description="项目标签")
    settings: Optional[ProjectSettings] = Field(None, description="项目设置")

class ProjectListResponse(BaseModel):
    """项目列表响应"""
    projects: List[KnowledgeGraphProject] = Field(..., description="项目列表")
    total: int = Field(..., description="总数量")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页大小")
    has_next: bool = Field(..., description="是否有下一页")

class ProjectMemberManageRequest(BaseModel):
    """项目成员管理请求"""
    user_id: str = Field(..., description="用户ID")
    permission: ProjectPermission = Field(..., description="权限")
    action: str = Field(..., description="操作类型：add/update/remove")

class ProjectBulkOperationRequest(BaseModel):
    """项目批量操作请求"""
    project_ids: List[str] = Field(..., description="项目ID列表")
    action: str = Field(..., description="操作类型：archive/delete/restore")
    
class ProjectExportRequest(BaseModel):
    """项目导出请求"""
    project_id: str = Field(..., description="项目ID")
    export_format: str = Field(default="json", description="导出格式：json/csv/rdf")
    include_visualizations: bool = Field(default=True, description="包含可视化文件")
    include_metadata: bool = Field(default=True, description="包含元数据")

class ProjectImportRequest(BaseModel):
    """项目导入请求"""
    name: str = Field(..., description="项目名称")
    import_data: Dict[str, Any] = Field(..., description="导入数据")
    override_settings: Optional[ProjectSettings] = Field(None, description="覆盖设置")

# 数据库表结构（用于PostgreSQL）
class ProjectDBModel:
    """项目数据库模型"""
    
    @staticmethod
    def create_table_sql():
        """创建项目表的SQL"""
        return """
        CREATE TABLE IF NOT EXISTS knowledge_graph_projects (
            project_id VARCHAR(255) PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            project_type VARCHAR(50) NOT NULL DEFAULT 'document_set',
            status VARCHAR(50) NOT NULL DEFAULT 'active',
            owner_id VARCHAR(255) NOT NULL,
            organization_id VARCHAR(255),
            knowledge_base_ids JSONB DEFAULT '[]',
            document_ids JSONB DEFAULT '[]',
            members JSONB DEFAULT '[]',
            settings JSONB DEFAULT '{}',
            statistics JSONB DEFAULT '{}',
            tags JSONB DEFAULT '[]',
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            last_accessed_at TIMESTAMP WITH TIME ZONE,
            version VARCHAR(20) DEFAULT '1.0.0',
            
            -- 索引
            CONSTRAINT fk_owner_id FOREIGN KEY (owner_id) REFERENCES users(id),
            INDEX idx_project_owner (owner_id),
            INDEX idx_project_status (status),
            INDEX idx_project_type (project_type),
            INDEX idx_project_created_at (created_at),
            INDEX idx_project_updated_at (updated_at)
        );
        
        -- 创建项目成员表
        CREATE TABLE IF NOT EXISTS project_members (
            id SERIAL PRIMARY KEY,
            project_id VARCHAR(255) NOT NULL,
            user_id VARCHAR(255) NOT NULL,
            permission VARCHAR(50) NOT NULL,
            added_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            added_by VARCHAR(255) NOT NULL,
            
            CONSTRAINT fk_project_id FOREIGN KEY (project_id) REFERENCES knowledge_graph_projects(project_id) ON DELETE CASCADE,
            CONSTRAINT fk_user_id FOREIGN KEY (user_id) REFERENCES users(id),
            CONSTRAINT fk_added_by FOREIGN KEY (added_by) REFERENCES users(id),
            UNIQUE (project_id, user_id)
        );
        
        -- 创建项目活动日志表
        CREATE TABLE IF NOT EXISTS project_activities (
            id SERIAL PRIMARY KEY,
            project_id VARCHAR(255) NOT NULL,
            user_id VARCHAR(255) NOT NULL,
            action VARCHAR(100) NOT NULL,
            details JSONB DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            
            CONSTRAINT fk_activity_project_id FOREIGN KEY (project_id) REFERENCES knowledge_graph_projects(project_id) ON DELETE CASCADE,
            CONSTRAINT fk_activity_user_id FOREIGN KEY (user_id) REFERENCES users(id),
            INDEX idx_activity_project (project_id),
            INDEX idx_activity_created_at (created_at)
        );
        """

# 工具函数
def generate_project_id(user_id: str, name: str) -> str:
    """生成项目ID"""
    import hashlib
    from datetime import datetime
    
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    source = f"{user_id}_{name}_{timestamp}"
    hash_obj = hashlib.md5(source.encode())
    return f"proj_{hash_obj.hexdigest()[:16]}"

def validate_project_permission(user_id: str, project: KnowledgeGraphProject, required_permission: ProjectPermission) -> bool:
    """验证项目权限"""
    # 所有者拥有所有权限
    if project.owner_id == user_id:
        return True
    
    # 检查成员权限
    for member in project.members:
        if member.user_id == user_id:
            if required_permission == ProjectPermission.VIEWER:
                return True
            elif required_permission == ProjectPermission.EDITOR:
                return member.permission in [ProjectPermission.EDITOR, ProjectPermission.OWNER]
            elif required_permission == ProjectPermission.OWNER:
                return member.permission == ProjectPermission.OWNER
    
    return False

def calculate_storage_usage(project: KnowledgeGraphProject) -> int:
    """计算项目存储使用量"""
    # 这里应该实现实际的存储计算逻辑
    # 包括图谱数据、文档、可视化文件等
    return project.statistics.storage_used

def update_project_statistics(project: KnowledgeGraphProject, new_stats: Dict[str, Any]) -> KnowledgeGraphProject:
    """更新项目统计信息"""
    project.statistics = ProjectStatistics(**{**project.statistics.dict(), **new_stats})
    project.updated_at = datetime.now()
    return project