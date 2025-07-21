"""
Knowledge-Graph-Service Schema定义
定义知识图谱管理、实体关系、图谱查询等相关的Pydantic Schema
"""

from typing import List, Optional, Dict, Any, Union, Tuple
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator
import uuid


# ===== 枚举类型定义 =====

class EntityType(str, Enum):
    """实体类型枚举"""
    PERSON = "person"
    ORGANIZATION = "organization"
    LOCATION = "location"
    EVENT = "event"
    CONCEPT = "concept"
    DOCUMENT = "document"
    PRODUCT = "product"
    TECHNOLOGY = "technology"
    CUSTOM = "custom"


class RelationType(str, Enum):
    """关系类型枚举"""
    BELONGS_TO = "belongs_to"
    RELATED_TO = "related_to"
    CONTAINS = "contains"
    DEPENDS_ON = "depends_on"
    SIMILAR_TO = "similar_to"
    CAUSED_BY = "caused_by"
    LOCATED_IN = "located_in"
    PART_OF = "part_of"
    CUSTOM = "custom"


class GraphStatus(str, Enum):
    """图谱状态枚举"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    BUILDING = "building"
    ERROR = "error"
    UPDATING = "updating"
    ARCHIVED = "archived"


class QueryType(str, Enum):
    """查询类型枚举"""
    ENTITY_SEARCH = "entity_search"
    RELATION_SEARCH = "relation_search"
    PATH_SEARCH = "path_search"
    SIMILARITY_SEARCH = "similarity_search"
    SUBGRAPH_SEARCH = "subgraph_search"
    CYPHER_QUERY = "cypher_query"


class ExtractionStatus(str, Enum):
    """抽取状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AlgorithmType(str, Enum):
    """算法类型枚举"""
    PAGERANK = "pagerank"
    COMMUNITY_DETECTION = "community_detection"
    SHORTEST_PATH = "shortest_path"
    CENTRALITY = "centrality"
    SIMILARITY = "similarity"
    CLUSTERING = "clustering"


# ===== 基础Schema类 =====

class BaseSchema(BaseModel):
    """基础Schema类"""
    
    # Pydantic v2 配置
    model_config = {
        "from_attributes": True,
        "use_enum_values": True,
        "arbitrary_types_allowed": True
    }


# ===== 分页和过滤Schema =====

class PaginationParams(BaseSchema):
    """分页参数"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页大小")
    
    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class EntityFilterParams(BaseSchema):
    """实体过滤参数"""
    entity_type: Optional[EntityType] = Field(None, description="实体类型过滤")
    graph_id: Optional[str] = Field(None, description="图谱ID过滤")
    search: Optional[str] = Field(None, description="搜索关键词")
    created_start: Optional[datetime] = Field(None, description="创建时间起")
    created_end: Optional[datetime] = Field(None, description="创建时间止")


class RelationFilterParams(BaseSchema):
    """关系过滤参数"""
    relation_type: Optional[RelationType] = Field(None, description="关系类型过滤")
    source_entity_id: Optional[str] = Field(None, description="源实体ID过滤")
    target_entity_id: Optional[str] = Field(None, description="目标实体ID过滤")
    graph_id: Optional[str] = Field(None, description="图谱ID过滤")
    confidence_min: Optional[float] = Field(None, ge=0, le=1, description="最小置信度")


class GraphFilterParams(BaseSchema):
    """图谱过滤参数"""
    status: Optional[GraphStatus] = Field(None, description="图谱状态过滤")
    user_id: Optional[str] = Field(None, description="用户ID过滤")
    search: Optional[str] = Field(None, description="搜索关键词")
    created_start: Optional[datetime] = Field(None, description="创建时间起")
    created_end: Optional[datetime] = Field(None, description="创建时间止")


# ===== 知识图谱相关Schema =====

class KnowledgeGraphCreate(BaseSchema):
    """知识图谱创建请求"""
    name: str = Field(..., min_length=1, max_length=200, description="图谱名称")
    description: Optional[str] = Field(None, description="图谱描述")
    user_id: str = Field(..., description="创建用户ID")
    
    # 图谱配置
    is_public: Optional[bool] = Field(False, description="是否公开")
    auto_extract: Optional[bool] = Field(True, description="是否自动抽取")
    
    # 数据源配置
    knowledge_base_ids: Optional[List[str]] = Field(default_factory=list, description="知识库ID列表")
    document_ids: Optional[List[str]] = Field(default_factory=list, description="文档ID列表")
    
    # 抽取配置
    extraction_config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="抽取配置")
    
    # 其他配置
    tags: Optional[List[str]] = Field(default_factory=list, description="标签列表")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")


class KnowledgeGraphUpdate(BaseSchema):
    """知识图谱更新请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=200, description="图谱名称")
    description: Optional[str] = Field(None, description="图谱描述")
    status: Optional[GraphStatus] = Field(None, description="图谱状态")
    is_public: Optional[bool] = Field(None, description="是否公开")
    auto_extract: Optional[bool] = Field(None, description="是否自动抽取")
    knowledge_base_ids: Optional[List[str]] = Field(None, description="知识库ID列表")
    document_ids: Optional[List[str]] = Field(None, description="文档ID列表")
    extraction_config: Optional[Dict[str, Any]] = Field(None, description="抽取配置")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


# ===== 实体相关Schema =====

class EntityCreate(BaseSchema):
    """实体创建请求"""
    graph_id: str = Field(..., description="所属图谱ID")
    name: str = Field(..., min_length=1, max_length=200, description="实体名称")
    entity_type: EntityType = Field(..., description="实体类型")
    
    # 实体属性
    properties: Optional[Dict[str, Any]] = Field(default_factory=dict, description="实体属性")
    aliases: Optional[List[str]] = Field(default_factory=list, description="别名列表")
    description: Optional[str] = Field(None, description="实体描述")
    
    # 位置信息
    embedding: Optional[List[float]] = Field(None, description="向量表示")
    coordinates: Optional[Tuple[float, float]] = Field(None, description="坐标位置")
    
    # 置信度和权重
    confidence: Optional[float] = Field(1.0, ge=0, le=1, description="置信度")
    weight: Optional[float] = Field(1.0, ge=0, description="权重")
    
    # 其他配置
    tags: Optional[List[str]] = Field(default_factory=list, description="标签列表")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")


class EntityUpdate(BaseSchema):
    """实体更新请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=200, description="实体名称")
    entity_type: Optional[EntityType] = Field(None, description="实体类型")
    properties: Optional[Dict[str, Any]] = Field(None, description="实体属性")
    aliases: Optional[List[str]] = Field(None, description="别名列表")
    description: Optional[str] = Field(None, description="实体描述")
    embedding: Optional[List[float]] = Field(None, description="向量表示")
    coordinates: Optional[Tuple[float, float]] = Field(None, description="坐标位置")
    confidence: Optional[float] = Field(None, ge=0, le=1, description="置信度")
    weight: Optional[float] = Field(None, ge=0, description="权重")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


class EntityMerge(BaseSchema):
    """实体合并请求"""
    source_entity_id: str = Field(..., description="源实体ID")
    target_entity_id: str = Field(..., description="目标实体ID")
    merge_strategy: Optional[str] = Field("preserve_target", description="合并策略")
    preserve_relations: Optional[bool] = Field(True, description="是否保留关系")


# ===== 关系相关Schema =====

class RelationCreate(BaseSchema):
    """关系创建请求"""
    graph_id: str = Field(..., description="所属图谱ID")
    source_entity_id: str = Field(..., description="源实体ID")
    target_entity_id: str = Field(..., description="目标实体ID")
    relation_type: RelationType = Field(..., description="关系类型")
    
    # 关系属性
    properties: Optional[Dict[str, Any]] = Field(default_factory=dict, description="关系属性")
    description: Optional[str] = Field(None, description="关系描述")
    
    # 置信度和权重
    confidence: Optional[float] = Field(1.0, ge=0, le=1, description="置信度")
    weight: Optional[float] = Field(1.0, ge=0, description="权重")
    
    # 方向性
    is_directed: Optional[bool] = Field(True, description="是否有向")
    
    # 其他配置
    tags: Optional[List[str]] = Field(default_factory=list, description="标签列表")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")


class RelationUpdate(BaseSchema):
    """关系更新请求"""
    relation_type: Optional[RelationType] = Field(None, description="关系类型")
    properties: Optional[Dict[str, Any]] = Field(None, description="关系属性")
    description: Optional[str] = Field(None, description="关系描述")
    confidence: Optional[float] = Field(None, ge=0, le=1, description="置信度")
    weight: Optional[float] = Field(None, ge=0, description="权重")
    is_directed: Optional[bool] = Field(None, description="是否有向")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


# ===== 查询相关Schema =====

class GraphQuery(BaseSchema):
    """图谱查询请求"""
    graph_id: str = Field(..., description="图谱ID")
    query_type: QueryType = Field(..., description="查询类型")
    
    # 查询参数
    query_text: Optional[str] = Field(None, description="查询文本")
    entity_names: Optional[List[str]] = Field(default_factory=list, description="实体名称列表")
    entity_types: Optional[List[EntityType]] = Field(default_factory=list, description="实体类型列表")
    relation_types: Optional[List[RelationType]] = Field(default_factory=list, description="关系类型列表")
    
    # Cypher查询
    cypher_query: Optional[str] = Field(None, description="Cypher查询语句")
    
    # 查询配置
    max_depth: Optional[int] = Field(3, ge=1, le=10, description="最大深度")
    max_results: Optional[int] = Field(100, ge=1, le=1000, description="最大结果数")
    confidence_threshold: Optional[float] = Field(0.5, ge=0, le=1, description="置信度阈值")
    
    # 相似度查询
    similarity_threshold: Optional[float] = Field(0.8, ge=0, le=1, description="相似度阈值")
    embedding: Optional[List[float]] = Field(None, description="查询向量")
    
    # 其他配置
    include_properties: Optional[bool] = Field(True, description="是否包含属性")
    return_paths: Optional[bool] = Field(False, description="是否返回路径")

    @validator('cypher_query')
    def validate_cypher_query(cls, v, values):
        """验证Cypher查询"""
        if values.get('query_type') == QueryType.CYPHER_QUERY and not v:
            raise ValueError('Cypher查询类型必须提供cypher_query')
        return v


class PathQuery(BaseSchema):
    """路径查询请求"""
    graph_id: str = Field(..., description="图谱ID")
    source_entity_id: str = Field(..., description="源实体ID")
    target_entity_id: str = Field(..., description="目标实体ID")
    
    # 路径配置
    max_length: Optional[int] = Field(5, ge=1, le=10, description="最大路径长度")
    max_paths: Optional[int] = Field(10, ge=1, le=100, description="最大路径数")
    
    # 权重配置
    weight_property: Optional[str] = Field(None, description="权重属性")
    use_confidence: Optional[bool] = Field(True, description="是否使用置信度")


class SimilarityQuery(BaseSchema):
    """相似度查询请求"""
    graph_id: str = Field(..., description="图谱ID")
    entity_id: Optional[str] = Field(None, description="参考实体ID")
    entity_name: Optional[str] = Field(None, description="参考实体名称")
    embedding: Optional[List[float]] = Field(None, description="查询向量")
    
    # 相似度配置
    similarity_threshold: Optional[float] = Field(0.8, ge=0, le=1, description="相似度阈值")
    max_results: Optional[int] = Field(20, ge=1, le=100, description="最大结果数")
    entity_types: Optional[List[EntityType]] = Field(default_factory=list, description="限制实体类型")

    @validator('entity_id')
    def validate_entity_reference(cls, v, values):
        """验证实体引用"""
        entity_name = values.get('entity_name')
        embedding = values.get('embedding')
        if not any([v, entity_name, embedding]):
            raise ValueError('必须提供entity_id、entity_name或embedding中的一个')
        return v


# ===== 抽取相关Schema =====

class ExtractionTask(BaseSchema):
    """抽取任务请求"""
    graph_id: str = Field(..., description="目标图谱ID")
    source_type: str = Field(..., description="数据源类型")
    
    # 数据源配置
    knowledge_base_ids: Optional[List[str]] = Field(default_factory=list, description="知识库ID列表")
    document_ids: Optional[List[str]] = Field(default_factory=list, description="文档ID列表")
    text_content: Optional[str] = Field(None, description="文本内容")
    
    # 抽取配置
    extract_entities: Optional[bool] = Field(True, description="是否抽取实体")
    extract_relations: Optional[bool] = Field(True, description="是否抽取关系")
    entity_types: Optional[List[EntityType]] = Field(default_factory=list, description="抽取实体类型")
    relation_types: Optional[List[RelationType]] = Field(default_factory=list, description="抽取关系类型")
    
    # 模型配置
    model_config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="模型配置")
    confidence_threshold: Optional[float] = Field(0.7, ge=0, le=1, description="置信度阈值")
    
    # 其他配置
    merge_duplicates: Optional[bool] = Field(True, description="是否合并重复实体")
    async_processing: Optional[bool] = Field(True, description="是否异步处理")


class ExtractionConfig(BaseSchema):
    """抽取配置"""
    # 实体抽取配置
    entity_models: Optional[Dict[str, Any]] = Field(default_factory=dict, description="实体抽取模型配置")
    entity_confidence_threshold: Optional[float] = Field(0.7, ge=0, le=1, description="实体置信度阈值")
    
    # 关系抽取配置
    relation_models: Optional[Dict[str, Any]] = Field(default_factory=dict, description="关系抽取模型配置")
    relation_confidence_threshold: Optional[float] = Field(0.7, ge=0, le=1, description="关系置信度阈值")
    
    # 后处理配置
    enable_coreference: Optional[bool] = Field(True, description="是否启用指代消解")
    enable_linking: Optional[bool] = Field(True, description="是否启用实体链接")
    enable_filtering: Optional[bool] = Field(True, description="是否启用结果过滤")
    
    # 其他配置
    batch_size: Optional[int] = Field(32, ge=1, description="批次大小")
    max_text_length: Optional[int] = Field(10000, ge=100, description="最大文本长度")


# ===== 分析相关Schema =====

class GraphAnalysis(BaseSchema):
    """图谱分析请求"""
    graph_id: str = Field(..., description="图谱ID")
    algorithm_type: AlgorithmType = Field(..., description="算法类型")
    
    # 算法参数
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="算法参数")
    
    # 分析配置
    target_entities: Optional[List[str]] = Field(default_factory=list, description="目标实体ID列表")
    entity_types: Optional[List[EntityType]] = Field(default_factory=list, description="分析实体类型")
    relation_types: Optional[List[RelationType]] = Field(default_factory=list, description="分析关系类型")
    
    # 其他配置
    async_processing: Optional[bool] = Field(True, description="是否异步处理")
    save_results: Optional[bool] = Field(True, description="是否保存结果")


# ===== 响应Schema =====

class KnowledgeGraphResponse(BaseSchema):
    """知识图谱响应"""
    id: str = Field(..., description="图谱ID")
    name: str = Field(..., description="图谱名称")
    description: Optional[str] = Field(None, description="图谱描述")
    user_id: str = Field(..., description="创建用户ID")
    status: GraphStatus = Field(..., description="图谱状态")
    
    # 图谱配置
    is_public: bool = Field(..., description="是否公开")
    auto_extract: bool = Field(..., description="是否自动抽取")
    
    # 数据源信息
    knowledge_base_ids: List[str] = Field(..., description="知识库ID列表")
    document_ids: List[str] = Field(..., description="文档ID列表")
    
    # 统计信息
    entity_count: int = Field(..., description="实体数量")
    relation_count: int = Field(..., description="关系数量")
    node_types: Dict[str, int] = Field(..., description="节点类型统计")
    edge_types: Dict[str, int] = Field(..., description="边类型统计")
    
    # 抽取配置
    extraction_config: Dict[str, Any] = Field(..., description="抽取配置")
    
    # 时间信息
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    last_extracted_at: Optional[datetime] = Field(None, description="最后抽取时间")
    
    # 其他信息
    tags: List[str] = Field(..., description="标签列表")
    metadata: Dict[str, Any] = Field(..., description="元数据")
    
    # 关联信息
    user_name: Optional[str] = Field(None, description="用户名称")


class EntityResponse(BaseSchema):
    """实体响应"""
    id: str = Field(..., description="实体ID")
    graph_id: str = Field(..., description="所属图谱ID")
    name: str = Field(..., description="实体名称")
    entity_type: EntityType = Field(..., description="实体类型")
    
    # 实体属性
    properties: Dict[str, Any] = Field(..., description="实体属性")
    aliases: List[str] = Field(..., description="别名列表")
    description: Optional[str] = Field(None, description="实体描述")
    
    # 位置信息
    embedding: Optional[List[float]] = Field(None, description="向量表示")
    coordinates: Optional[Tuple[float, float]] = Field(None, description="坐标位置")
    
    # 置信度和权重
    confidence: float = Field(..., description="置信度")
    weight: float = Field(..., description="权重")
    
    # 统计信息
    relation_count: int = Field(..., description="关系数量")
    in_degree: int = Field(..., description="入度")
    out_degree: int = Field(..., description="出度")
    
    # 时间信息
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    # 其他信息
    tags: List[str] = Field(..., description="标签列表")
    metadata: Dict[str, Any] = Field(..., description="元数据")
    
    # 关联信息
    graph_name: Optional[str] = Field(None, description="图谱名称")


class RelationResponse(BaseSchema):
    """关系响应"""
    id: str = Field(..., description="关系ID")
    graph_id: str = Field(..., description="所属图谱ID")
    source_entity_id: str = Field(..., description="源实体ID")
    target_entity_id: str = Field(..., description="目标实体ID")
    relation_type: RelationType = Field(..., description="关系类型")
    
    # 关系属性
    properties: Dict[str, Any] = Field(..., description="关系属性")
    description: Optional[str] = Field(None, description="关系描述")
    
    # 置信度和权重
    confidence: float = Field(..., description="置信度")
    weight: float = Field(..., description="权重")
    
    # 方向性
    is_directed: bool = Field(..., description="是否有向")
    
    # 时间信息
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    # 其他信息
    tags: List[str] = Field(..., description="标签列表")
    metadata: Dict[str, Any] = Field(..., description="元数据")
    
    # 关联信息
    graph_name: Optional[str] = Field(None, description="图谱名称")
    source_entity_name: Optional[str] = Field(None, description="源实体名称")
    target_entity_name: Optional[str] = Field(None, description="目标实体名称")


class QueryResult(BaseSchema):
    """查询结果响应"""
    query_id: str = Field(..., description="查询ID")
    query_type: QueryType = Field(..., description="查询类型")
    
    # 查询结果
    entities: List[EntityResponse] = Field(..., description="实体列表")
    relations: List[RelationResponse] = Field(..., description="关系列表")
    paths: Optional[List[Dict[str, Any]]] = Field(None, description="路径列表")
    
    # 统计信息
    total_entities: int = Field(..., description="实体总数")
    total_relations: int = Field(..., description="关系总数")
    execution_time_ms: int = Field(..., description="执行时间(毫秒)")
    
    # 查询信息
    query_text: Optional[str] = Field(None, description="查询文本")
    cypher_query: Optional[str] = Field(None, description="Cypher查询")
    
    # 时间信息
    created_at: datetime = Field(..., description="查询时间")


class ExtractionResult(BaseSchema):
    """抽取结果响应"""
    task_id: str = Field(..., description="任务ID")
    graph_id: str = Field(..., description="图谱ID")
    status: ExtractionStatus = Field(..., description="抽取状态")
    
    # 抽取结果
    extracted_entities: int = Field(..., description="抽取实体数")
    extracted_relations: int = Field(..., description="抽取关系数")
    merged_entities: int = Field(..., description="合并实体数")
    
    # 错误信息
    errors: List[str] = Field(..., description="错误列表")
    warnings: List[str] = Field(..., description="警告列表")
    
    # 时间信息
    started_at: datetime = Field(..., description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    processing_time_ms: Optional[int] = Field(None, description="处理时间(毫秒)")
    
    # 其他信息
    metadata: Dict[str, Any] = Field(..., description="元数据")


class AnalysisResult(BaseSchema):
    """分析结果响应"""
    analysis_id: str = Field(..., description="分析ID")
    graph_id: str = Field(..., description="图谱ID")
    algorithm_type: AlgorithmType = Field(..., description="算法类型")
    
    # 分析结果
    results: Dict[str, Any] = Field(..., description="分析结果")
    
    # 统计信息
    processed_entities: int = Field(..., description="处理实体数")
    processed_relations: int = Field(..., description="处理关系数")
    execution_time_ms: int = Field(..., description="执行时间(毫秒)")
    
    # 时间信息
    started_at: datetime = Field(..., description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    
    # 其他信息
    parameters: Dict[str, Any] = Field(..., description="算法参数")
    metadata: Dict[str, Any] = Field(..., description="元数据")


# ===== 统计和监控Schema =====

class GraphStatistics(BaseSchema):
    """图谱统计信息"""
    total_graphs: int = Field(..., description="图谱总数")
    active_graphs: int = Field(..., description="活跃图谱数")
    total_entities: int = Field(..., description="实体总数")
    total_relations: int = Field(..., description="关系总数")
    
    # 按类型统计
    entities_by_type: Dict[str, int] = Field(..., description="按类型统计实体")
    relations_by_type: Dict[str, int] = Field(..., description="按类型统计关系")
    
    # 时间统计
    graphs_created_today: int = Field(..., description="今日创建图谱数")
    entities_created_today: int = Field(..., description="今日创建实体数")
    queries_today: int = Field(..., description="今日查询次数")
    extractions_today: int = Field(..., description="今日抽取次数")
    
    # 性能统计
    avg_query_time: Optional[float] = Field(None, description="平均查询时间(毫秒)")
    avg_extraction_time: Optional[float] = Field(None, description="平均抽取时间(毫秒)")


# ===== 统一API响应Schema =====

class APIResponse(BaseSchema):
    """统一API响应格式"""
    success: bool = Field(..., description="请求是否成功")
    message: str = Field(default="", description="响应消息")
    data: Optional[Any] = Field(default=None, description="响应数据")
    error_code: Optional[str] = Field(default=None, description="错误代码")
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间")


class PaginatedResponse(BaseSchema):
    """分页响应格式"""
    success: bool = Field(..., description="请求是否成功")
    message: str = Field(default="", description="响应消息")
    data: List[Any] = Field(..., description="数据列表")
    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页大小")
    total_pages: int = Field(..., description="总页数")
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间")


# ===== 健康检查Schema =====

class HealthCheckResponse(BaseSchema):
    """健康检查响应"""
    status: str = Field(..., description="服务状态")
    version: str = Field(..., description="服务版本")
    uptime: float = Field(..., description="运行时间(秒)")
    timestamp: datetime = Field(..., description="检查时间")
    
    # 组件状态
    database: bool = Field(..., description="数据库连接状态")
    neo4j: bool = Field(..., description="Neo4j连接状态")
    redis: bool = Field(..., description="Redis连接状态")
    
    # 系统指标
    cpu_usage: float = Field(..., description="CPU使用率")
    memory_usage: float = Field(..., description="内存使用率")
    disk_usage: float = Field(..., description="磁盘使用率")
    
    # 服务统计
    total_graphs: int = Field(..., description="图谱总数")
    active_graphs: int = Field(..., description="活跃图谱数")
    total_entities: int = Field(..., description="实体总数")
    total_relations: int = Field(..., description="关系总数")
    running_extractions: int = Field(..., description="运行中的抽取任务数")
