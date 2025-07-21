"""
兼容原始项目的数据适配器
用于处理新微服务与原始项目之间的数据格式转换
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from ..models.graph import (
    KnowledgeGraph, Entity, Relation, GraphStatistics, ProcessingProgress,
    GraphCreateRequest, GraphUpdateRequest, GraphStatus, GraphType
)


class LegacyKnowledgeGraphAdapter:
    """知识图谱数据适配器"""
    
    @staticmethod
    def adapt_create_request(legacy_data: Dict[str, Any]) -> GraphCreateRequest:
        """适配创建请求格式"""
        return GraphCreateRequest(
            project_id=legacy_data.get("project_id", "default"),
            name=legacy_data["name"],
            description=legacy_data.get("description"),
            graph_type=GraphType.DOCUMENT_BASED,
            knowledge_base_ids=[str(legacy_data["knowledge_base_id"])] if legacy_data.get("knowledge_base_id") else [],
            document_ids=[],
            text_content=legacy_data.get("text_content"),
            tags=legacy_data.get("tags", [])
        )
    
    @staticmethod 
    def adapt_update_request(legacy_data: Dict[str, Any]) -> GraphUpdateRequest:
        """适配更新请求格式"""
        return GraphUpdateRequest(
            name=legacy_data.get("name"),
            description=legacy_data.get("description"),
            tags=legacy_data.get("tags")
        )
    
    @staticmethod
    def adapt_graph_response(graph: KnowledgeGraph) -> Dict[str, Any]:
        """适配图谱响应格式到原始项目格式"""
        return {
            "id": graph.graph_id,
            "name": graph.name,
            "description": graph.description,
            "status": graph.status.value,
            "knowledge_base_id": int(graph.knowledge_base_ids[0]) if graph.knowledge_base_ids else None,
            "user_id": int(graph.created_by),
            "is_public": graph.metadata.get("is_public", False),
            "tags": graph.tags,
            
            # 统计信息适配
            "statistics": LegacyKnowledgeGraphAdapter._adapt_statistics(graph.statistics) if graph.statistics else None,
            
            # 处理进度适配
            "processing_progress": LegacyKnowledgeGraphAdapter._adapt_progress(graph.processing_progress) if graph.processing_progress else None,
            
            # 配置信息适配
            "extraction_config": LegacyKnowledgeGraphAdapter._adapt_extraction_config(graph.processing_config),
            "visualization_config": LegacyKnowledgeGraphAdapter._adapt_visualization_config(graph.visualization_config),
            
            # 时间信息
            "created_at": graph.created_at,
            "updated_at": graph.updated_at,
            "completed_at": graph.completed_at,
            
            # 文件信息
            "source_files": graph.source_files
        }
    
    @staticmethod
    def _adapt_statistics(stats: GraphStatistics) -> Dict[str, Any]:
        """适配统计信息格式"""
        return {
            "total_entities": stats.entity_count,
            "total_relations": stats.relation_count,
            "total_documents": stats.document_count,
            "entity_type_distribution": stats.entity_types,
            "relation_type_distribution": stats.relation_types,
            "graph_density": stats.density,
            "average_degree": 0.0,  # 需要计算
            "connected_components": 1,  # 需要计算
            "clustering_coefficient": stats.clustering_coefficient
        }
    
    @staticmethod
    def _adapt_progress(progress: ProcessingProgress) -> Dict[str, Any]:
        """适配处理进度格式"""
        return {
            "total_files": progress.stage_details.get("total_files", 0),
            "processed_files": progress.stage_details.get("processed_files", 0),
            "total_entities": progress.stage_details.get("total_entities", 0),
            "total_relations": progress.stage_details.get("total_relations", 0),
            "current_step": progress.stage.value,
            "progress_percentage": progress.progress,
            "estimated_remaining_time": None,
            "error_message": progress.error
        }
    
    @staticmethod
    def _adapt_extraction_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """适配提取配置格式"""
        return {
            "llm_model": config.get("llm_model", "gpt-3.5-turbo"),
            "temperature": config.get("temperature", 0.3),
            "max_tokens": config.get("max_tokens", 2000),
            "chunk_size": config.get("chunk_size", 1000),
            "chunk_overlap": config.get("overlap_size", 100),
            "entity_types": [],  # 需要映射
            "extract_relations": True,
            "relation_threshold": config.get("confidence_threshold", 0.7),
            "enable_inference": config.get("enable_inference", True)
        }
    
    @staticmethod
    def _adapt_visualization_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """适配可视化配置格式"""
        return {
            "theme": config.get("theme", "light"),
            "layout": "physics",
            "physics_enabled": config.get("physics_enabled", True),
            "width": f"{config.get('width', 1200)}px",
            "height": f"{config.get('height', 800)}px",
            "node_size_factor": 1.0,
            "edge_width_factor": 1.0,
            "show_labels": config.get("show_labels", True),
            "show_legend": True
        }


class LegacyEntityAdapter:
    """实体数据适配器"""
    
    @staticmethod
    def adapt_entity_response(entity: Entity) -> Dict[str, Any]:
        """适配实体响应格式"""
        return {
            "id": entity.id,
            "name": entity.name,
            "entity_type": entity.entity_type,
            "description": entity.properties.get("description"),
            "properties": entity.properties,
            "confidence": entity.confidence,
            "connections": 0,  # 需要计算
            "importance": entity.centrality,
            "created_at": datetime.now()  # 需要从数据库获取
        }


class LegacyRelationAdapter:
    """关系数据适配器"""
    
    @staticmethod
    def adapt_relation_response(relation: Relation) -> Dict[str, Any]:
        """适配关系响应格式"""
        return {
            "id": relation.id,
            "subject": relation.subject,
            "predicate": relation.predicate,
            "object": relation.object,
            "relation_type": relation.predicate,  # 原始项目中relation_type就是predicate
            "confidence": relation.confidence,
            "properties": relation.properties,
            "is_inferred": relation.inferred,
            "created_at": datetime.now()  # 需要从数据库获取
        }


class FrontendGraphAdapter:
    """前端图谱数据适配器"""
    
    @staticmethod
    def adapt_for_frontend(graph: KnowledgeGraph) -> Dict[str, Any]:
        """适配为前端期望的格式"""
        return {
            "id": graph.graph_id,
            "name": graph.name,
            "description": graph.description,
            "createdAt": graph.created_at.isoformat(),
            "updatedAt": graph.updated_at.isoformat(),
            "nodeCount": graph.statistics.entity_count if graph.statistics else 0,
            "edgeCount": graph.statistics.relation_count if graph.statistics else 0,
            "type": "knowledge",  # 映射到前端类型
            "tags": graph.tags
        }
    
    @staticmethod
    def adapt_node_for_frontend(entity: Entity) -> Dict[str, Any]:
        """适配节点数据为前端格式"""
        return {
            "id": entity.id,
            "label": entity.name,
            "properties": entity.properties,
            "type": entity.entity_type,
            "x": entity.position.get("x", 0) if entity.position else 0,
            "y": entity.position.get("y", 0) if entity.position else 0,
            "size": entity.size or 20,
            "color": entity.color or "#1f77b4"
        }
    
    @staticmethod
    def adapt_edge_for_frontend(relation: Relation) -> Dict[str, Any]:
        """适配边数据为前端格式"""
        return {
            "id": relation.id,
            "source": relation.subject,
            "target": relation.object,
            "label": relation.predicate,
            "properties": relation.properties,
            "type": relation.predicate,
            "weight": relation.properties.get("weight", 1.0)
        }


class LegacyAPIResponseAdapter:
    """API响应适配器"""
    
    @staticmethod
    def adapt_list_response(graphs: List[KnowledgeGraph]) -> List[Dict[str, Any]]:
        """适配图谱列表响应"""
        return [LegacyKnowledgeGraphAdapter.adapt_graph_response(graph) for graph in graphs]
    
    @staticmethod
    def adapt_graph_data_response(graph_id: str, entities: List[Entity], relations: List[Relation]) -> Dict[str, Any]:
        """适配图谱数据响应"""
        return {
            "graph_id": graph_id,
            "entities": [LegacyEntityAdapter.adapt_entity_response(entity) for entity in entities],
            "relations": [LegacyRelationAdapter.adapt_relation_response(relation) for relation in relations],
            "metadata": {
                "total_entities": len(entities),
                "total_relations": len(relations),
                "generated_at": datetime.now().isoformat()
            }
        }
    
    @staticmethod
    def adapt_frontend_data_response(graph_id: str, entities: List[Entity], relations: List[Relation]) -> Dict[str, Any]:
        """适配前端数据响应"""
        return {
            "graph_id": graph_id,
            "nodes": [FrontendGraphAdapter.adapt_node_for_frontend(entity) for entity in entities],
            "edges": [FrontendGraphAdapter.adapt_edge_for_frontend(relation) for relation in relations],
            "metadata": {
                "nodeCount": len(entities),
                "edgeCount": len(relations),
                "lastUpdated": datetime.now().isoformat()
            }
        }