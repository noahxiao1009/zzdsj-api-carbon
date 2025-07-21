"""
知识图谱数据模型
"""
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum

class GraphStatus(str, Enum):
    """图谱状态"""
    CREATED = "created"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"

class GraphType(str, Enum):
    """图谱类型"""
    DOCUMENT_BASED = "document_based"
    KNOWLEDGE_BASE = "knowledge_base"
    CUSTOM = "custom"
    HYBRID = "hybrid"

class VisualizationType(str, Enum):
    """可视化类型"""
    BASIC = "basic"
    INTERACTIVE = "interactive"
    ENHANCED = "enhanced"

class ProcessingStage(str, Enum):
    """处理阶段"""
    INITIALIZED = "initialized"
    EXTRACTING = "extracting"
    STANDARDIZING = "standardizing"
    INFERRING = "inferring"
    CLUSTERING = "clustering"
    VISUALIZING = "visualizing"
    COMPLETED = "completed"

class Entity(BaseModel):
    """实体模型"""
    id: str = Field(..., description="实体ID")
    name: str = Field(..., description="实体名称")
    entity_type: str = Field(..., description="实体类型")
    confidence: float = Field(..., description="置信度")
    properties: Dict[str, Any] = Field(default_factory=dict, description="实体属性")
    source: str = Field(..., description="来源")
    
    # 统计信息
    frequency: int = Field(default=1, description="出现频次")
    centrality: float = Field(default=0.0, description="中心性")
    
    # 可视化属性
    color: Optional[str] = Field(None, description="节点颜色")
    size: Optional[float] = Field(None, description="节点大小")
    position: Optional[Dict[str, float]] = Field(None, description="节点位置")

class Relation(BaseModel):
    """关系模型"""
    id: str = Field(..., description="关系ID")
    subject: str = Field(..., description="主语实体ID")
    predicate: str = Field(..., description="谓语/关系类型")
    object: str = Field(..., description="宾语实体ID")
    confidence: float = Field(..., description="置信度")
    
    # 关系属性
    properties: Dict[str, Any] = Field(default_factory=dict, description="关系属性")
    source: str = Field(..., description="来源")
    inferred: bool = Field(default=False, description="是否为推理关系")
    
    # 可视化属性
    color: Optional[str] = Field(None, description="边颜色")
    width: Optional[float] = Field(None, description="边宽度")
    style: Optional[str] = Field(None, description="边样式")

class GraphStatistics(BaseModel):
    """图谱统计信息"""
    entity_count: int = Field(default=0, description="实体数量")
    relation_count: int = Field(default=0, description="关系数量")
    document_count: int = Field(default=0, description="文档数量")
    
    # 类型统计
    entity_types: Dict[str, int] = Field(default_factory=dict, description="实体类型统计")
    relation_types: Dict[str, int] = Field(default_factory=dict, description="关系类型统计")
    
    # 图谱指标
    density: float = Field(default=0.0, description="图谱密度")
    clustering_coefficient: float = Field(default=0.0, description="聚类系数")
    average_path_length: float = Field(default=0.0, description="平均路径长度")
    
    # 质量指标
    average_confidence: float = Field(default=0.0, description="平均置信度")
    inferred_relation_ratio: float = Field(default=0.0, description="推理关系比例")

class ProcessingConfig(BaseModel):
    """处理配置"""
    # 提取配置
    chunk_size: int = Field(default=500, description="文本分块大小")
    overlap_size: int = Field(default=50, description="重叠大小")
    
    # LLM配置
    llm_model: str = Field(default="claude-3-5-sonnet", description="LLM模型")
    temperature: float = Field(default=0.3, description="温度参数")
    max_tokens: int = Field(default=8192, description="最大令牌数")
    
    # 阈值配置
    confidence_threshold: float = Field(default=0.7, description="置信度阈值")
    entity_frequency_threshold: int = Field(default=2, description="实体频次阈值")
    relation_frequency_threshold: int = Field(default=1, description="关系频次阈值")
    
    # 处理选项
    enable_standardization: bool = Field(default=True, description="启用实体标准化")
    enable_inference: bool = Field(default=True, description="启用关系推理")
    enable_clustering: bool = Field(default=True, description="启用聚类")
    
    # 限制配置
    max_entities: int = Field(default=1000, description="最大实体数量")
    max_relations: int = Field(default=5000, description="最大关系数量")

class VisualizationConfig(BaseModel):
    """可视化配置"""
    # 基础设置
    width: int = Field(default=1200, description="宽度")
    height: int = Field(default=800, description="高度")
    
    # 物理引擎
    physics_enabled: bool = Field(default=True, description="启用物理模拟")
    physics_config: Dict[str, Any] = Field(default_factory=dict, description="物理引擎配置")
    
    # 显示设置
    show_labels: bool = Field(default=True, description="显示标签")
    show_edge_labels: bool = Field(default=False, description="显示边标签")
    color_by_type: bool = Field(default=True, description="按类型着色")
    
    # 主题设置
    theme: str = Field(default="light", description="主题")
    background_color: str = Field(default="#ffffff", description="背景颜色")
    
    # 节点设置
    node_size_range: List[int] = Field(default=[10, 50], description="节点大小范围")
    node_color_scheme: str = Field(default="category10", description="节点颜色方案")
    
    # 边设置
    edge_width_range: List[float] = Field(default=[1.0, 5.0], description="边宽度范围")
    edge_color: str = Field(default="#cccccc", description="边颜色")
    
    # 交互设置
    enable_zoom: bool = Field(default=True, description="启用缩放")
    enable_drag: bool = Field(default=True, description="启用拖拽")
    enable_selection: bool = Field(default=True, description="启用选择")

class ProcessingProgress(BaseModel):
    """处理进度"""
    stage: ProcessingStage = Field(..., description="当前阶段")
    progress: float = Field(default=0.0, description="进度百分比")
    message: str = Field(default="", description="进度消息")
    
    # 阶段详情
    stage_details: Dict[str, Any] = Field(default_factory=dict, description="阶段详情")
    
    # 时间信息
    started_at: datetime = Field(default_factory=datetime.now, description="开始时间")
    estimated_completion: Optional[datetime] = Field(None, description="预计完成时间")
    
    # 错误信息
    error: Optional[str] = Field(None, description="错误信息")
    warnings: List[str] = Field(default_factory=list, description="警告信息")

class KnowledgeGraph(BaseModel):
    """知识图谱模型"""
    
    # 基础信息
    graph_id: str = Field(..., description="图谱ID")
    project_id: str = Field(..., description="项目ID")
    name: str = Field(..., description="图谱名称")
    description: Optional[str] = Field(None, description="图谱描述")
    
    # 类型和状态
    graph_type: GraphType = Field(default=GraphType.DOCUMENT_BASED, description="图谱类型")
    status: GraphStatus = Field(default=GraphStatus.CREATED, description="状态")
    
    # 关联资源
    knowledge_base_ids: List[str] = Field(default_factory=list, description="关联知识库ID")
    document_ids: List[str] = Field(default_factory=list, description="关联文档ID")
    source_files: List[str] = Field(default_factory=list, description="源文件路径")
    
    # 配置
    processing_config: ProcessingConfig = Field(default_factory=ProcessingConfig, description="处理配置")
    visualization_config: VisualizationConfig = Field(default_factory=VisualizationConfig, description="可视化配置")
    
    # 数据
    entities: List[Entity] = Field(default_factory=list, description="实体列表")
    relations: List[Relation] = Field(default_factory=list, description="关系列表")
    
    # 统计信息
    statistics: GraphStatistics = Field(default_factory=GraphStatistics, description="统计信息")
    
    # 处理信息
    processing_progress: Optional[ProcessingProgress] = Field(None, description="处理进度")
    
    # 可视化信息
    visualization_type: VisualizationType = Field(default=VisualizationType.INTERACTIVE, description="可视化类型")
    visualization_url: Optional[str] = Field(None, description="可视化URL")
    visualization_data: Optional[Dict[str, Any]] = Field(None, description="可视化数据")
    
    # 版本信息
    version: str = Field(default="1.0.0", description="版本")
    
    # 创建者和时间
    created_by: str = Field(..., description="创建者ID")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    
    # 标签和元数据
    tags: List[str] = Field(default_factory=list, description="标签")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    
    # Pydantic v2 配置
    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat()
        }
    }

class GraphCreateRequest(BaseModel):
    """图谱创建请求"""
    project_id: str = Field(..., description="项目ID")
    name: str = Field(..., description="图谱名称")
    description: Optional[str] = Field(None, description="图谱描述")
    graph_type: GraphType = Field(default=GraphType.DOCUMENT_BASED, description="图谱类型")
    
    # 数据源
    knowledge_base_ids: List[str] = Field(default_factory=list, description="知识库ID列表")
    document_ids: List[str] = Field(default_factory=list, description="文档ID列表")
    text_content: Optional[str] = Field(None, description="文本内容")
    
    # 配置
    processing_config: Optional[ProcessingConfig] = Field(None, description="处理配置")
    visualization_config: Optional[VisualizationConfig] = Field(None, description="可视化配置")
    
    # 选项
    async_processing: bool = Field(default=True, description="异步处理")
    generate_visualization: bool = Field(default=True, description="生成可视化")
    
    tags: List[str] = Field(default_factory=list, description="标签")

class GraphUpdateRequest(BaseModel):
    """图谱更新请求"""
    name: Optional[str] = Field(None, description="图谱名称")
    description: Optional[str] = Field(None, description="图谱描述")
    status: Optional[GraphStatus] = Field(None, description="状态")
    processing_config: Optional[ProcessingConfig] = Field(None, description="处理配置")
    visualization_config: Optional[VisualizationConfig] = Field(None, description="可视化配置")
    tags: Optional[List[str]] = Field(None, description="标签")

class GraphGenerateRequest(BaseModel):
    """图谱生成请求"""
    project_id: str = Field(..., description="项目ID")
    name: str = Field(..., description="图谱名称")
    
    # 数据源选择
    data_source: str = Field(..., description="数据源类型：knowledge_base/documents/text")
    knowledge_base_ids: List[str] = Field(default_factory=list, description="知识库ID列表")
    document_ids: List[str] = Field(default_factory=list, description="文档ID列表")
    text_content: Optional[str] = Field(None, description="文本内容")
    
    # 生成配置
    processing_config: Optional[ProcessingConfig] = Field(None, description="处理配置")
    visualization_type: VisualizationType = Field(default=VisualizationType.INTERACTIVE, description="可视化类型")
    
    # 选项
    overwrite_existing: bool = Field(default=False, description="覆盖已存在的图谱")

class GraphListResponse(BaseModel):
    """图谱列表响应"""
    graphs: List[KnowledgeGraph] = Field(..., description="图谱列表")
    total: int = Field(..., description="总数量")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页大小")
    has_next: bool = Field(..., description="是否有下一页")

class GraphDataResponse(BaseModel):
    """图谱数据响应"""
    graph_id: str = Field(..., description="图谱ID")
    entities: List[Entity] = Field(..., description="实体列表")
    relations: List[Relation] = Field(..., description="关系列表")
    statistics: GraphStatistics = Field(..., description="统计信息")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")

class GraphExportRequest(BaseModel):
    """图谱导出请求"""
    graph_id: str = Field(..., description="图谱ID")
    export_format: str = Field(default="json", description="导出格式：json/csv/rdf/cypher/networkx")
    include_metadata: bool = Field(default=True, description="包含元数据")
    include_visualization: bool = Field(default=False, description="包含可视化")
    filter_confidence: Optional[float] = Field(None, description="置信度过滤")

class GraphSearchRequest(BaseModel):
    """图谱搜索请求"""
    query: str = Field(..., description="搜索查询")
    search_type: str = Field(default="fuzzy", description="搜索类型：exact/fuzzy/semantic")
    entity_types: Optional[List[str]] = Field(None, description="实体类型过滤")
    relation_types: Optional[List[str]] = Field(None, description="关系类型过滤")
    confidence_threshold: Optional[float] = Field(None, description="置信度阈值")
    max_results: int = Field(default=100, description="最大结果数")

class GraphSearchResponse(BaseModel):
    """图谱搜索响应"""
    entities: List[Entity] = Field(default_factory=list, description="匹配的实体")
    relations: List[Relation] = Field(default_factory=list, description="匹配的关系")
    total_entities: int = Field(default=0, description="实体总数")
    total_relations: int = Field(default=0, description="关系总数")
    query_time: float = Field(default=0.0, description="查询时间")

# 数据库表结构
class GraphDBModel:
    """图谱数据库模型"""
    
    @staticmethod
    def create_table_sql():
        """创建图谱表的SQL"""
        return """
        CREATE TABLE IF NOT EXISTS knowledge_graphs (
            graph_id VARCHAR(255) PRIMARY KEY,
            project_id VARCHAR(255) NOT NULL,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            graph_type VARCHAR(50) NOT NULL DEFAULT 'document_based',
            status VARCHAR(50) NOT NULL DEFAULT 'created',
            knowledge_base_ids JSONB DEFAULT '[]',
            document_ids JSONB DEFAULT '[]',
            source_files JSONB DEFAULT '[]',
            processing_config JSONB DEFAULT '{}',
            visualization_config JSONB DEFAULT '{}',
            statistics JSONB DEFAULT '{}',
            processing_progress JSONB,
            visualization_type VARCHAR(50) DEFAULT 'interactive',
            visualization_url VARCHAR(500),
            visualization_data JSONB,
            version VARCHAR(20) DEFAULT '1.0.0',
            created_by VARCHAR(255) NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            completed_at TIMESTAMP WITH TIME ZONE,
            tags JSONB DEFAULT '[]',
            metadata JSONB DEFAULT '{}',
            
            CONSTRAINT fk_graph_project_id FOREIGN KEY (project_id) REFERENCES knowledge_graph_projects(project_id) ON DELETE CASCADE,
            CONSTRAINT fk_graph_created_by FOREIGN KEY (created_by) REFERENCES users(id),
            INDEX idx_graph_project (project_id),
            INDEX idx_graph_status (status),
            INDEX idx_graph_type (graph_type),
            INDEX idx_graph_created_at (created_at)
        );
        """

# 工具函数
def generate_graph_id(project_id: str, name: str) -> str:
    """生成图谱ID"""
    import hashlib
    from datetime import datetime
    
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    source = f"{project_id}_{name}_{timestamp}"
    hash_obj = hashlib.md5(source.encode())
    return f"graph_{hash_obj.hexdigest()[:16]}"

def generate_entity_id(name: str, entity_type: str) -> str:
    """生成实体ID"""
    import hashlib
    
    source = f"{name}_{entity_type}".lower()
    hash_obj = hashlib.md5(source.encode())
    return f"entity_{hash_obj.hexdigest()[:16]}"

def generate_relation_id(subject: str, predicate: str, object: str) -> str:
    """生成关系ID"""
    import hashlib
    
    source = f"{subject}_{predicate}_{object}".lower()
    hash_obj = hashlib.md5(source.encode())
    return f"relation_{hash_obj.hexdigest()[:16]}"

def calculate_graph_statistics(entities: List[Entity], relations: List[Relation]) -> GraphStatistics:
    """计算图谱统计信息"""
    from collections import defaultdict
    
    entity_types = defaultdict(int)
    relation_types = defaultdict(int)
    
    for entity in entities:
        entity_types[entity.entity_type] += 1
    
    for relation in relations:
        relation_types[relation.predicate] += 1
    
    # 计算图谱密度
    entity_count = len(entities)
    relation_count = len(relations)
    
    density = 0.0
    if entity_count > 1:
        max_edges = entity_count * (entity_count - 1)
        density = (2 * relation_count) / max_edges if max_edges > 0 else 0.0
    
    # 计算平均置信度
    total_confidence = sum(entity.confidence for entity in entities) + sum(relation.confidence for relation in relations)
    total_items = entity_count + relation_count
    average_confidence = total_confidence / total_items if total_items > 0 else 0.0
    
    # 计算推理关系比例
    inferred_relations = sum(1 for relation in relations if relation.inferred)
    inferred_ratio = inferred_relations / relation_count if relation_count > 0 else 0.0
    
    return GraphStatistics(
        entity_count=entity_count,
        relation_count=relation_count,
        entity_types=dict(entity_types),
        relation_types=dict(relation_types),
        density=density,
        average_confidence=average_confidence,
        inferred_relation_ratio=inferred_ratio
    )