"""
知识图谱服务层
提供图谱生成、管理和查询的业务逻辑
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import json
import asyncio
from pathlib import Path

from ..models.graph import (
    KnowledgeGraph, 
    Entity, 
    Relation, 
    GraphStatistics,
    GraphCreateRequest,
    GraphUpdateRequest,
    GraphGenerateRequest,
    GraphStatus,
    ProcessingProgress,
    ProcessingStage,
    VisualizationType
)
from ..models.project import KnowledgeGraphProject
from ..repositories.arangodb_repository import ArangoDBRepository, get_arangodb_repository
from ..core.graph_generator import GraphGenerator
from ..core.visualization_engine import VisualizationEngine
from ..core.task_manager import TaskManager
from ..config.settings import settings

logger = logging.getLogger(__name__)


class GraphService:
    """知识图谱服务"""
    
    def __init__(self):
        """初始化服务"""
        self.arangodb_repo: Optional[ArangoDBRepository] = None
        self.graph_generator: Optional[GraphGenerator] = None
        self.visualization_engine: Optional[VisualizationEngine] = None
        self.task_manager: Optional[TaskManager] = None
    
    async def initialize(self):
        """初始化服务依赖"""
        if not self.arangodb_repo:
            self.arangodb_repo = await get_arangodb_repository()
        
        if not self.graph_generator:
            self.graph_generator = GraphGenerator()
        
        if not self.visualization_engine:
            self.visualization_engine = VisualizationEngine()
        
        if not self.task_manager:
            self.task_manager = TaskManager()
    
    async def create_graph(self, request: GraphCreateRequest, user_id: str) -> KnowledgeGraph:
        """创建图谱"""
        await self.initialize()
        
        try:
            # 生成图谱ID
            from ..models.graph import generate_graph_id
            graph_id = generate_graph_id(request.project_id, request.name)
            
            # 创建图谱对象
            graph = KnowledgeGraph(
                graph_id=graph_id,
                project_id=request.project_id,
                name=request.name,
                description=request.description,
                graph_type=request.graph_type,
                status=GraphStatus.CREATED,
                knowledge_base_ids=request.knowledge_base_ids,
                document_ids=request.document_ids,
                processing_config=request.processing_config or {},
                visualization_config=request.visualization_config or {},
                created_by=user_id
            )
            
            # 保存图谱元数据
            await self.arangodb_repo.save_graph_metadata(graph)
            
            # 如果启用异步处理，创建处理任务
            if request.async_processing:
                task_id = await self.task_manager.create_graph_generation_task(
                    graph_id=graph_id,
                    user_id=user_id,
                    data_source=request.knowledge_base_ids or request.document_ids,
                    text_content=request.text_content,
                    processing_config=request.processing_config
                )
                
                graph.processing_progress = ProcessingProgress(
                    stage=ProcessingStage.INITIALIZED,
                    progress=0.0,
                    message="图谱生成任务已创建"
                )
                
                await self.arangodb_repo.save_graph_metadata(graph)
                
                logger.info(f"Created async graph generation task {task_id} for graph {graph_id}")
            
            else:
                # 同步处理
                if request.text_content:
                    await self._process_text_content(graph, request.text_content, user_id)
                elif request.knowledge_base_ids:
                    await self._process_knowledge_bases(graph, request.knowledge_base_ids, user_id)
                elif request.document_ids:
                    await self._process_documents(graph, request.document_ids, user_id)
                
                # 生成可视化
                if request.generate_visualization:
                    await self._generate_visualization(graph, user_id)
            
            logger.info(f"Created graph: {graph_id}")
            return graph
            
        except Exception as e:
            logger.error(f"Failed to create graph: {e}")
            raise
    
    async def get_graph(self, graph_id: str, user_id: str = None, project_id: str = None) -> Optional[KnowledgeGraph]:
        """获取图谱"""
        await self.initialize()
        
        try:
            graph = await self.arangodb_repo.get_graph_metadata(graph_id)
            if not graph:
                return None
            
            # 权限检查
            if user_id and graph.created_by != user_id:
                # 这里可以添加更复杂的权限检查逻辑
                pass
            
            return graph
            
        except Exception as e:
            logger.error(f"Failed to get graph {graph_id}: {e}")
            raise
    
    async def update_graph(self, graph_id: str, request: GraphUpdateRequest, user_id: str) -> Optional[KnowledgeGraph]:
        """更新图谱"""
        await self.initialize()
        
        try:
            graph = await self.arangodb_repo.get_graph_metadata(graph_id)
            if not graph:
                return None
            
            # 权限检查
            if graph.created_by != user_id:
                raise PermissionError("无权限修改此图谱")
            
            # 更新字段
            if request.name:
                graph.name = request.name
            if request.description is not None:
                graph.description = request.description
            if request.status:
                graph.status = request.status
            if request.processing_config:
                graph.processing_config = request.processing_config
            if request.visualization_config:
                graph.visualization_config = request.visualization_config
            if request.tags is not None:
                graph.tags = request.tags
            
            graph.updated_at = datetime.now()
            
            # 保存更新
            await self.arangodb_repo.save_graph_metadata(graph)
            
            logger.info(f"Updated graph: {graph_id}")
            return graph
            
        except Exception as e:
            logger.error(f"Failed to update graph {graph_id}: {e}")
            raise
    
    async def delete_graph(self, graph_id: str, user_id: str, project_id: str = None) -> bool:
        """删除图谱"""
        await self.initialize()
        
        try:
            graph = await self.arangodb_repo.get_graph_metadata(graph_id)
            if not graph:
                return False
            
            # 权限检查
            if graph.created_by != user_id:
                raise PermissionError("无权限删除此图谱")
            
            # 删除图谱数据和元数据
            await self.arangodb_repo.delete_graph(graph_id, user_id, project_id)
            
            # 删除可视化文件
            await self._delete_visualization_files(graph_id)
            
            logger.info(f"Deleted graph: {graph_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete graph {graph_id}: {e}")
            raise
    
    async def get_graph_data(self, graph_id: str, user_id: str = None, project_id: str = None) -> Tuple[List[Entity], List[Relation]]:
        """获取图谱数据"""
        await self.initialize()
        
        try:
            entities, relations = await self.arangodb_repo.get_graph_data(graph_id, user_id, project_id)
            logger.info(f"Retrieved data for graph {graph_id}: {len(entities)} entities, {len(relations)} relations")
            return entities, relations
            
        except Exception as e:
            logger.error(f"Failed to get graph data {graph_id}: {e}")
            raise
    
    async def get_graph_statistics(self, graph_id: str, user_id: str = None, project_id: str = None) -> GraphStatistics:
        """获取图谱统计信息"""
        await self.initialize()
        
        try:
            statistics = await self.arangodb_repo.get_graph_statistics(graph_id, user_id, project_id)
            logger.info(f"Retrieved statistics for graph {graph_id}")
            return statistics
            
        except Exception as e:
            logger.error(f"Failed to get graph statistics {graph_id}: {e}")
            raise
    
    async def search_entities(self, graph_id: str, query: str, limit: int = 100, 
                            user_id: str = None, project_id: str = None) -> List[Entity]:
        """搜索实体"""
        await self.initialize()
        
        try:
            entities = await self.arangodb_repo.search_entities(graph_id, query, limit, user_id, project_id)
            logger.info(f"Found {len(entities)} entities for query '{query}' in graph {graph_id}")
            return entities
            
        except Exception as e:
            logger.error(f"Failed to search entities in graph {graph_id}: {e}")
            raise
    
    async def get_entity_neighbors(self, graph_id: str, entity_id: str, depth: int = 1,
                                 user_id: str = None, project_id: str = None) -> Dict[str, Any]:
        """获取实体邻居"""
        await self.initialize()
        
        try:
            neighbors = await self.arangodb_repo.get_entity_neighbors(graph_id, entity_id, depth, user_id, project_id)
            logger.info(f"Retrieved neighbors for entity {entity_id} in graph {graph_id}")
            return neighbors
            
        except Exception as e:
            logger.error(f"Failed to get entity neighbors in graph {graph_id}: {e}")
            raise
    
    async def get_shortest_path(self, graph_id: str, start_entity_id: str, end_entity_id: str,
                              user_id: str = None, project_id: str = None) -> Optional[List[Dict[str, Any]]]:
        """获取最短路径"""
        await self.initialize()
        
        try:
            path = await self.arangodb_repo.get_shortest_path(graph_id, start_entity_id, end_entity_id, user_id, project_id)
            if path:
                logger.info(f"Found shortest path between {start_entity_id} and {end_entity_id} in graph {graph_id}")
            else:
                logger.info(f"No path found between {start_entity_id} and {end_entity_id} in graph {graph_id}")
            return path
            
        except Exception as e:
            logger.error(f"Failed to get shortest path in graph {graph_id}: {e}")
            raise
    
    async def export_graph(self, graph_id: str, format: str = 'json', 
                         user_id: str = None, project_id: str = None) -> Dict[str, Any]:
        """导出图谱"""
        await self.initialize()
        
        try:
            export_data = await self.arangodb_repo.export_graph(graph_id, format, user_id, project_id)
            logger.info(f"Exported graph {graph_id} in format {format}")
            return export_data
            
        except Exception as e:
            logger.error(f"Failed to export graph {graph_id}: {e}")
            raise
    
    async def generate_graph_async(self, request: GraphGenerateRequest, user_id: str) -> str:
        """异步生成图谱"""
        await self.initialize()
        
        try:
            # 生成图谱ID
            from ..models.graph import generate_graph_id
            graph_id = generate_graph_id(request.project_id, request.name)
            
            # 创建任务
            task_id = await self.task_manager.create_graph_generation_task(
                graph_id=graph_id,
                user_id=user_id,
                data_source=request.knowledge_base_ids or request.document_ids,
                text_content=request.text_content,
                processing_config=request.processing_config
            )
            
            logger.info(f"Created async graph generation task {task_id} for graph {graph_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to create async graph generation task: {e}")
            raise
    
    async def get_visualization(self, graph_id: str, user_id: str = None, project_id: str = None) -> Optional[str]:
        """获取图谱可视化"""
        await self.initialize()
        
        try:
            graph = await self.arangodb_repo.get_graph_metadata(graph_id)
            if not graph:
                return None
            
            # 检查可视化URL
            if graph.visualization_url:
                visualization_path = Path(graph.visualization_url)
                if visualization_path.exists():
                    return visualization_path.read_text(encoding='utf-8')
            
            # 如果没有可视化文件，生成新的
            await self._generate_visualization(graph, user_id)
            
            # 重新获取
            graph = await self.arangodb_repo.get_graph_metadata(graph_id)
            if graph.visualization_url:
                visualization_path = Path(graph.visualization_url)
                if visualization_path.exists():
                    return visualization_path.read_text(encoding='utf-8')
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get visualization for graph {graph_id}: {e}")
            raise
    
    async def _process_text_content(self, graph: KnowledgeGraph, text_content: str, user_id: str):
        """处理文本内容"""
        try:
            # 更新处理进度
            graph.processing_progress = ProcessingProgress(
                stage=ProcessingStage.EXTRACTING,
                progress=10.0,
                message="正在提取实体和关系"
            )
            await self.arangodb_repo.save_graph_metadata(graph)
            
            # 使用图谱生成器处理文本
            entities, relations = await self.graph_generator.process_text(
                text_content=text_content,
                config=graph.processing_config
            )
            
            # 保存图谱数据
            await self.arangodb_repo.save_graph_data(graph.graph_id, entities, relations, user_id, graph.project_id)
            
            # 更新统计信息
            statistics = await self.arangodb_repo.get_graph_statistics(graph.graph_id, user_id, graph.project_id)
            graph.statistics = statistics
            
            # 更新状态
            graph.status = GraphStatus.COMPLETED
            graph.processing_progress = ProcessingProgress(
                stage=ProcessingStage.COMPLETED,
                progress=100.0,
                message="图谱生成完成"
            )
            graph.completed_at = datetime.now()
            
            await self.arangodb_repo.save_graph_metadata(graph)
            
            logger.info(f"Processed text content for graph {graph.graph_id}")
            
        except Exception as e:
            logger.error(f"Failed to process text content: {e}")
            graph.status = GraphStatus.FAILED
            graph.processing_progress = ProcessingProgress(
                stage=ProcessingStage.COMPLETED,
                progress=0.0,
                message=f"处理失败: {str(e)}",
                error=str(e)
            )
            await self.arangodb_repo.save_graph_metadata(graph)
            raise
    
    async def _process_knowledge_bases(self, graph: KnowledgeGraph, knowledge_base_ids: List[str], user_id: str):
        """处理知识库"""
        try:
            # 更新处理进度
            graph.processing_progress = ProcessingProgress(
                stage=ProcessingStage.EXTRACTING,
                progress=10.0,
                message="正在处理知识库"
            )
            await self.arangodb_repo.save_graph_metadata(graph)
            
            # 使用图谱生成器处理知识库
            entities, relations = await self.graph_generator.process_knowledge_bases(
                knowledge_base_ids=knowledge_base_ids,
                config=graph.processing_config
            )
            
            # 保存图谱数据
            await self.arangodb_repo.save_graph_data(graph.graph_id, entities, relations, user_id, graph.project_id)
            
            # 更新统计信息
            statistics = await self.arangodb_repo.get_graph_statistics(graph.graph_id, user_id, graph.project_id)
            graph.statistics = statistics
            
            # 更新状态
            graph.status = GraphStatus.COMPLETED
            graph.processing_progress = ProcessingProgress(
                stage=ProcessingStage.COMPLETED,
                progress=100.0,
                message="图谱生成完成"
            )
            graph.completed_at = datetime.now()
            
            await self.arangodb_repo.save_graph_metadata(graph)
            
            logger.info(f"Processed knowledge bases for graph {graph.graph_id}")
            
        except Exception as e:
            logger.error(f"Failed to process knowledge bases: {e}")
            graph.status = GraphStatus.FAILED
            graph.processing_progress = ProcessingProgress(
                stage=ProcessingStage.COMPLETED,
                progress=0.0,
                message=f"处理失败: {str(e)}",
                error=str(e)
            )
            await self.arangodb_repo.save_graph_metadata(graph)
            raise
    
    async def _process_documents(self, graph: KnowledgeGraph, document_ids: List[str], user_id: str):
        """处理文档"""
        try:
            # 更新处理进度
            graph.processing_progress = ProcessingProgress(
                stage=ProcessingStage.EXTRACTING,
                progress=10.0,
                message="正在处理文档"
            )
            await self.arangodb_repo.save_graph_metadata(graph)
            
            # 使用图谱生成器处理文档
            entities, relations = await self.graph_generator.process_documents(
                document_ids=document_ids,
                config=graph.processing_config
            )
            
            # 保存图谱数据
            await self.arangodb_repo.save_graph_data(graph.graph_id, entities, relations, user_id, graph.project_id)
            
            # 更新统计信息
            statistics = await self.arangodb_repo.get_graph_statistics(graph.graph_id, user_id, graph.project_id)
            graph.statistics = statistics
            
            # 更新状态
            graph.status = GraphStatus.COMPLETED
            graph.processing_progress = ProcessingProgress(
                stage=ProcessingStage.COMPLETED,
                progress=100.0,
                message="图谱生成完成"
            )
            graph.completed_at = datetime.now()
            
            await self.arangodb_repo.save_graph_metadata(graph)
            
            logger.info(f"Processed documents for graph {graph.graph_id}")
            
        except Exception as e:
            logger.error(f"Failed to process documents: {e}")
            graph.status = GraphStatus.FAILED
            graph.processing_progress = ProcessingProgress(
                stage=ProcessingStage.COMPLETED,
                progress=0.0,
                message=f"处理失败: {str(e)}",
                error=str(e)
            )
            await self.arangodb_repo.save_graph_metadata(graph)
            raise
    
    async def _generate_visualization(self, graph: KnowledgeGraph, user_id: str):
        """生成可视化"""
        try:
            # 获取图谱数据
            entities, relations = await self.arangodb_repo.get_graph_data(graph.graph_id, user_id, graph.project_id)
            
            if not entities:
                logger.warning(f"No entities found for graph {graph.graph_id}, skipping visualization")
                return
            
            # 生成HTML可视化
            html_content = await self.visualization_engine.generate_html_visualization(
                entities=entities,
                relations=relations,
                config=graph.visualization_config,
                graph_title=graph.name
            )
            
            # 保存可视化文件
            visualization_dir = Path(settings.VISUALIZATION_DIR)
            visualization_dir.mkdir(parents=True, exist_ok=True)
            
            visualization_file = visualization_dir / f"{graph.graph_id}.html"
            visualization_file.write_text(html_content, encoding='utf-8')
            
            # 更新图谱元数据
            graph.visualization_url = str(visualization_file)
            graph.visualization_type = VisualizationType.INTERACTIVE
            
            await self.arangodb_repo.save_graph_metadata(graph)
            
            logger.info(f"Generated visualization for graph {graph.graph_id}")
            
        except Exception as e:
            logger.error(f"Failed to generate visualization: {e}")
            raise
    
    async def _delete_visualization_files(self, graph_id: str):
        """删除可视化文件"""
        try:
            visualization_dir = Path(settings.VISUALIZATION_DIR)
            visualization_file = visualization_dir / f"{graph_id}.html"
            
            if visualization_file.exists():
                visualization_file.unlink()
                logger.info(f"Deleted visualization file for graph {graph_id}")
                
        except Exception as e:
            logger.error(f"Failed to delete visualization files: {e}")


# 全局服务实例
graph_service = GraphService()


async def get_graph_service() -> GraphService:
    """获取图谱服务实例"""
    return graph_service