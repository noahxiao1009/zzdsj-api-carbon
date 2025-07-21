"""
ArangoDB 数据访问层
提供知识图谱数据的持久化存储和查询功能
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import json
from contextlib import asynccontextmanager
from arango import ArangoClient, ArangoError
from arango.database import Database
from arango.graph import Graph
from arango.collection import Collection

from ..config.settings import settings
from ..models.graph import KnowledgeGraph, Entity, Relation, GraphStatistics
from ..models.project import KnowledgeGraphProject
from .tenant_manager import TenantIsolationManager
from .networkx_adapter import NetworkXAdapter

logger = logging.getLogger(__name__)


class ArangoDBRepository:
    """ArangoDB 数据访问仓库"""
    
    def __init__(self):
        """初始化ArangoDB连接"""
        self.client = ArangoClient(hosts=settings.ARANGODB_URL)
        self.username = settings.ARANGODB_USERNAME
        self.password = settings.ARANGODB_PASSWORD
        self.database_name = settings.ARANGODB_DATABASE
        
        # 租户模式设置
        self.tenant_mode = settings.GRAPH_DATABASE_TENANT_MODE
        
        # 连接池配置
        self.max_connections = settings.GRAPH_DATABASE_MAX_CONNECTIONS
        
        # 初始化组件
        self.tenant_manager = TenantIsolationManager(self.client, self.username, self.password)
        self.networkx_adapter = NetworkXAdapter()
        
        # 延迟初始化系统数据库（避免模块导入时连接数据库）
        self._db_initialized = False
    
    def _init_system_database(self):
        """初始化系统数据库"""
        try:
            # 连接系统数据库
            sys_db = self.client.db('_system', username=self.username, password=self.password)
            
            # 创建主数据库
            if not sys_db.has_database(self.database_name):
                sys_db.create_database(self.database_name)
                logger.info(f"Created database: {self.database_name}")
            
            # 创建基础集合
            self._create_base_collections()
            
        except ArangoError as e:
            logger.error(f"Failed to initialize system database: {e}")
            raise
    
    def _create_base_collections(self):
        """创建基础集合"""
        try:
            db = self.get_database()
            
            # 创建项目集合
            if not db.has_collection('projects'):
                db.create_collection('projects')
                logger.info("Created projects collection")
            
            # 创建图谱元数据集合
            if not db.has_collection('graph_metadata'):
                db.create_collection('graph_metadata')
                logger.info("Created graph_metadata collection")
            
            # 创建任务集合
            if not db.has_collection('tasks'):
                db.create_collection('tasks')
                logger.info("Created tasks collection")
                
        except ArangoError as e:
            logger.error(f"Failed to create base collections: {e}")
            raise
    
    def get_database(self, user_id: str = None, project_id: str = None) -> Database:
        """获取数据库连接"""
        try:
            # 延迟初始化
            if not self._db_initialized:
                self._init_system_database()
                self._db_initialized = True
            
            if self.tenant_mode and user_id and project_id:
                # 租户模式：为每个用户项目创建独立数据库
                tenant_db_name = f"kg_tenant_{user_id}_{project_id}"
                
                # 检查租户数据库是否存在
                sys_db = self.client.db('_system', username=self.username, password=self.password)
                if not sys_db.has_database(tenant_db_name):
                    sys_db.create_database(tenant_db_name)
                    logger.info(f"Created tenant database: {tenant_db_name}")
                
                return self.client.db(tenant_db_name, username=self.username, password=self.password)
            else:
                # 共享模式：使用主数据库
                return self.client.db(self.database_name, username=self.username, password=self.password)
                
        except ArangoError as e:
            logger.error(f"Failed to get database connection: {e}")
            raise
    
    def get_graph_database(self, graph_id: str, user_id: str = None, project_id: str = None) -> Tuple[Database, Graph]:
        """获取图数据库和图实例"""
        try:
            db = self.get_database(user_id, project_id)
            graph_name = f"knowledge_graph_{graph_id}"
            
            # 检查图是否存在
            if not db.has_graph(graph_name):
                # 创建图
                graph_def = {
                    "edge_definitions": [
                        {
                            "edge_collection": f"relations_{graph_id}",
                            "from_vertex_collections": [f"entities_{graph_id}"],
                            "to_vertex_collections": [f"entities_{graph_id}"]
                        }
                    ]
                }
                graph = db.create_graph(graph_name, graph_def)
                logger.info(f"Created graph: {graph_name}")
            else:
                graph = db.graph(graph_name)
            
            return db, graph
            
        except ArangoError as e:
            logger.error(f"Failed to get graph database: {e}")
            raise
    
    async def save_project(self, project: KnowledgeGraphProject) -> KnowledgeGraphProject:
        """保存项目"""
        try:
            db = self.get_database()
            projects = db.collection('projects')
            
            project_data = project.dict()
            project_data['_key'] = project.project_id
            
            # 插入或更新项目
            if projects.has(project.project_id):
                projects.update(project.project_id, project_data)
                logger.info(f"Updated project: {project.project_id}")
            else:
                projects.insert(project_data)
                logger.info(f"Created project: {project.project_id}")
            
            return project
            
        except ArangoError as e:
            logger.error(f"Failed to save project: {e}")
            raise
    
    async def get_project(self, project_id: str) -> Optional[KnowledgeGraphProject]:
        """获取项目"""
        try:
            db = self.get_database()
            projects = db.collection('projects')
            
            if projects.has(project_id):
                project_data = projects.get(project_id)
                return KnowledgeGraphProject(**project_data)
            
            return None
            
        except ArangoError as e:
            logger.error(f"Failed to get project: {e}")
            raise
    
    async def save_graph_metadata(self, graph: KnowledgeGraph) -> KnowledgeGraph:
        """保存图谱元数据"""
        try:
            db = self.get_database()
            metadata_collection = db.collection('graph_metadata')
            
            metadata = graph.dict()
            metadata['_key'] = graph.graph_id
            
            # 插入或更新元数据
            if metadata_collection.has(graph.graph_id):
                metadata_collection.update(graph.graph_id, metadata)
                logger.info(f"Updated graph metadata: {graph.graph_id}")
            else:
                metadata_collection.insert(metadata)
                logger.info(f"Created graph metadata: {graph.graph_id}")
            
            return graph
            
        except ArangoError as e:
            logger.error(f"Failed to save graph metadata: {e}")
            raise
    
    async def get_graph_metadata(self, graph_id: str) -> Optional[KnowledgeGraph]:
        """获取图谱元数据"""
        try:
            db = self.get_database()
            metadata_collection = db.collection('graph_metadata')
            
            if metadata_collection.has(graph_id):
                metadata = metadata_collection.get(graph_id)
                return KnowledgeGraph(**metadata)
            
            return None
            
        except ArangoError as e:
            logger.error(f"Failed to get graph metadata: {e}")
            raise
    
    async def save_graph_data(self, graph_id: str, entities: List[Entity], relations: List[Relation], 
                             user_id: str = None, project_id: str = None) -> bool:
        """保存图谱数据"""
        try:
            db, graph = self.get_graph_database(graph_id, user_id, project_id)
            
            # 获取实体和关系集合
            entities_collection = graph.vertex_collection(f"entities_{graph_id}")
            relations_collection = graph.edge_collection(f"relations_{graph_id}")
            
            # 清空现有数据
            entities_collection.truncate()
            relations_collection.truncate()
            
            # 批量插入实体
            entity_docs = []
            for entity in entities:
                entity_doc = entity.dict()
                entity_doc['_key'] = entity.id
                entity_docs.append(entity_doc)
            
            if entity_docs:
                entities_collection.insert_many(entity_docs)
                logger.info(f"Inserted {len(entity_docs)} entities for graph {graph_id}")
            
            # 批量插入关系
            relation_docs = []
            for relation in relations:
                relation_doc = relation.dict()
                relation_doc['_key'] = relation.id
                relation_doc['_from'] = f"entities_{graph_id}/{relation.subject}"
                relation_doc['_to'] = f"entities_{graph_id}/{relation.object}"
                relation_docs.append(relation_doc)
            
            if relation_docs:
                relations_collection.insert_many(relation_docs)
                logger.info(f"Inserted {len(relation_docs)} relations for graph {graph_id}")
            
            return True
            
        except ArangoError as e:
            logger.error(f"Failed to save graph data: {e}")
            raise
    
    async def get_graph_data(self, graph_id: str, user_id: str = None, project_id: str = None) -> Tuple[List[Entity], List[Relation]]:
        """获取图谱数据"""
        try:
            db, graph = self.get_graph_database(graph_id, user_id, project_id)
            
            # 获取实体和关系集合
            entities_collection = graph.vertex_collection(f"entities_{graph_id}")
            relations_collection = graph.edge_collection(f"relations_{graph_id}")
            
            # 查询实体
            entities = []
            for entity_doc in entities_collection.all():
                entities.append(Entity(**entity_doc))
            
            # 查询关系
            relations = []
            for relation_doc in relations_collection.all():
                relations.append(Relation(**relation_doc))
            
            logger.info(f"Retrieved {len(entities)} entities and {len(relations)} relations for graph {graph_id}")
            return entities, relations
            
        except ArangoError as e:
            logger.error(f"Failed to get graph data: {e}")
            raise
    
    async def search_entities(self, graph_id: str, query: str, limit: int = 100, 
                            user_id: str = None, project_id: str = None) -> List[Entity]:
        """搜索实体"""
        try:
            db, graph = self.get_graph_database(graph_id, user_id, project_id)
            
            # 构建搜索查询
            aql_query = f"""
            FOR entity IN entities_{graph_id}
            FILTER CONTAINS(LOWER(entity.name), LOWER(@query)) OR 
                   CONTAINS(LOWER(entity.entity_type), LOWER(@query))
            LIMIT @limit
            RETURN entity
            """
            
            # 执行查询
            cursor = db.aql.execute(aql_query, bind_vars={'query': query, 'limit': limit})
            
            # 转换结果
            entities = []
            for entity_doc in cursor:
                entities.append(Entity(**entity_doc))
            
            logger.info(f"Found {len(entities)} entities for query '{query}' in graph {graph_id}")
            return entities
            
        except ArangoError as e:
            logger.error(f"Failed to search entities: {e}")
            raise
    
    async def get_entity_neighbors(self, graph_id: str, entity_id: str, depth: int = 1, 
                                 user_id: str = None, project_id: str = None) -> Dict[str, Any]:
        """获取实体邻居"""
        try:
            db, graph = self.get_graph_database(graph_id, user_id, project_id)
            
            # 构建邻居查询
            aql_query = f"""
            FOR vertex, edge, path IN 1..@depth ANY 'entities_{graph_id}/@entity_id' 
            GRAPH 'knowledge_graph_{graph_id}'
            RETURN {{
                vertex: vertex,
                edge: edge,
                path: path
            }}
            """
            
            # 执行查询
            cursor = db.aql.execute(aql_query, bind_vars={'depth': depth, 'entity_id': entity_id})
            
            # 处理结果
            neighbors = {'entities': [], 'relations': [], 'paths': []}
            for result in cursor:
                if result['vertex']:
                    neighbors['entities'].append(Entity(**result['vertex']))
                if result['edge']:
                    neighbors['relations'].append(Relation(**result['edge']))
                if result['path']:
                    neighbors['paths'].append(result['path'])
            
            logger.info(f"Found {len(neighbors['entities'])} neighbors for entity {entity_id} in graph {graph_id}")
            return neighbors
            
        except ArangoError as e:
            logger.error(f"Failed to get entity neighbors: {e}")
            raise
    
    async def get_shortest_path(self, graph_id: str, start_entity_id: str, end_entity_id: str,
                              user_id: str = None, project_id: str = None) -> Optional[List[Dict[str, Any]]]:
        """获取最短路径"""
        try:
            db, graph = self.get_graph_database(graph_id, user_id, project_id)
            
            # 构建最短路径查询
            aql_query = f"""
            FOR vertex, edge IN OUTBOUND SHORTEST_PATH 
            'entities_{graph_id}/@start_id' TO 'entities_{graph_id}/@end_id'
            GRAPH 'knowledge_graph_{graph_id}'
            RETURN {{
                vertex: vertex,
                edge: edge
            }}
            """
            
            # 执行查询
            cursor = db.aql.execute(aql_query, bind_vars={
                'start_id': start_entity_id, 
                'end_id': end_entity_id
            })
            
            # 处理结果
            path = []
            for result in cursor:
                path.append(result)
            
            logger.info(f"Found path with {len(path)} steps between {start_entity_id} and {end_entity_id}")
            return path if path else None
            
        except ArangoError as e:
            logger.error(f"Failed to get shortest path: {e}")
            raise
    
    async def get_graph_statistics(self, graph_id: str, user_id: str = None, project_id: str = None) -> GraphStatistics:
        """获取图谱统计信息"""
        try:
            db, graph = self.get_graph_database(graph_id, user_id, project_id)
            
            # 统计实体数量
            entity_count_query = f"RETURN LENGTH(entities_{graph_id})"
            entity_count = list(db.aql.execute(entity_count_query))[0]
            
            # 统计关系数量
            relation_count_query = f"RETURN LENGTH(relations_{graph_id})"
            relation_count = list(db.aql.execute(relation_count_query))[0]
            
            # 统计实体类型
            entity_types_query = f"""
            FOR entity IN entities_{graph_id}
            COLLECT type = entity.entity_type WITH COUNT INTO count
            RETURN {{type: type, count: count}}
            """
            entity_types = {}
            for result in db.aql.execute(entity_types_query):
                entity_types[result['type']] = result['count']
            
            # 统计关系类型
            relation_types_query = f"""
            FOR relation IN relations_{graph_id}
            COLLECT type = relation.predicate WITH COUNT INTO count
            RETURN {{type: type, count: count}}
            """
            relation_types = {}
            for result in db.aql.execute(relation_types_query):
                relation_types[result['type']] = result['count']
            
            # 计算图谱密度
            density = 0.0
            if entity_count > 1:
                max_edges = entity_count * (entity_count - 1)
                density = (2 * relation_count) / max_edges if max_edges > 0 else 0.0
            
            # 计算平均置信度
            confidence_query = f"""
            FOR entity IN entities_{graph_id}
            RETURN AVG(entity.confidence)
            """
            avg_entity_confidence = list(db.aql.execute(confidence_query))[0] or 0.0
            
            confidence_relation_query = f"""
            FOR relation IN relations_{graph_id}
            RETURN AVG(relation.confidence)
            """
            avg_relation_confidence = list(db.aql.execute(confidence_relation_query))[0] or 0.0
            
            average_confidence = (avg_entity_confidence + avg_relation_confidence) / 2
            
            # 统计推理关系比例
            inferred_query = f"""
            FOR relation IN relations_{graph_id}
            FILTER relation.inferred == true
            RETURN COUNT(relation)
            """
            inferred_count = list(db.aql.execute(inferred_query))[0] or 0
            inferred_ratio = inferred_count / relation_count if relation_count > 0 else 0.0
            
            statistics = GraphStatistics(
                entity_count=entity_count,
                relation_count=relation_count,
                entity_types=entity_types,
                relation_types=relation_types,
                density=density,
                average_confidence=average_confidence,
                inferred_relation_ratio=inferred_ratio
            )
            
            logger.info(f"Generated statistics for graph {graph_id}")
            return statistics
            
        except ArangoError as e:
            logger.error(f"Failed to get graph statistics: {e}")
            raise
    
    async def delete_graph(self, graph_id: str, user_id: str = None, project_id: str = None) -> bool:
        """删除图谱"""
        try:
            db, graph = self.get_graph_database(graph_id, user_id, project_id)
            
            # 删除图
            graph_name = f"knowledge_graph_{graph_id}"
            if db.has_graph(graph_name):
                db.delete_graph(graph_name, drop_collections=True)
                logger.info(f"Deleted graph: {graph_name}")
            
            # 删除元数据
            metadata_collection = db.collection('graph_metadata')
            if metadata_collection.has(graph_id):
                metadata_collection.delete(graph_id)
                logger.info(f"Deleted graph metadata: {graph_id}")
            
            return True
            
        except ArangoError as e:
            logger.error(f"Failed to delete graph: {e}")
            raise
    
    async def export_graph(self, graph_id: str, format: str = 'json', 
                         user_id: str = None, project_id: str = None) -> Dict[str, Any]:
        """导出图谱数据"""
        try:
            entities, relations = await self.get_graph_data(graph_id, user_id, project_id)
            
            if format == 'json':
                return {
                    'graph_id': graph_id,
                    'entities': [entity.dict() for entity in entities],
                    'relations': [relation.dict() for relation in relations],
                    'exported_at': datetime.now().isoformat()
                }
            elif format == 'cypher':
                # 生成Cypher创建语句
                cypher_statements = []
                
                # 创建实体
                for entity in entities:
                    cypher_statements.append(
                        f"CREATE (:{entity.entity_type} {{id: '{entity.id}', name: '{entity.name}', confidence: {entity.confidence}}})"
                    )
                
                # 创建关系
                for relation in relations:
                    cypher_statements.append(
                        f"MATCH (a {{id: '{relation.subject}'}}), (b {{id: '{relation.object}'}}) "
                        f"CREATE (a)-[:{relation.predicate.replace(' ', '_').upper()} {{confidence: {relation.confidence}}}]->(b)"
                    )
                
                return {
                    'graph_id': graph_id,
                    'cypher_statements': cypher_statements,
                    'exported_at': datetime.now().isoformat()
                }
            
            logger.info(f"Exported graph {graph_id} in format {format}")
            return {}
            
        except ArangoError as e:
            logger.error(f"Failed to export graph: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            db = self.get_database()
            
            # 测试连接
            server_info = db.server_info()
            
            # 检查集合状态
            collections = db.collections()
            collection_count = len(collections)
            
            return {
                'status': 'healthy',
                'server_version': server_info.get('version', 'unknown'),
                'database': self.database_name,
                'collection_count': collection_count,
                'tenant_mode': self.tenant_mode,
                'checked_at': datetime.now().isoformat()
            }
            
        except ArangoError as e:
            logger.error(f"Health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'checked_at': datetime.now().isoformat()
            }
    
    # ===== 新增的高级功能方法 =====
    
    async def get_graph_with_tenant_context(self, graph_id: str, user_id: str, project_id: str = None) -> Tuple[List[Entity], List[Relation]]:
        """使用租户上下文获取图数据"""
        try:
            async with self.tenant_manager.tenant_context(user_id, project_id) as (tenant_db, tenant_id):
                entities = await self._get_entities_from_tenant_db(tenant_db, graph_id)
                relations = await self._get_relations_from_tenant_db(tenant_db, graph_id)
                return entities, relations
                
        except Exception as e:
            logger.error(f"Failed to get graph with tenant context: {e}")
            raise
    
    async def _get_entities_from_tenant_db(self, tenant_db: Database, graph_id: str) -> List[Entity]:
        """从租户数据库获取实体"""
        try:
            entities_collection = tenant_db.collection('entities')
            cursor = await asyncio.to_thread(
                entities_collection.find,
                {'graph_id': graph_id}
            )
            
            entities = []
            for doc in cursor:
                entity = Entity(
                    id=doc['_key'],
                    name=doc['name'],
                    entity_type=doc['entity_type'],
                    confidence=doc['confidence'],
                    properties=doc.get('properties', {}),
                    source=doc.get('source', ''),
                    frequency=doc.get('frequency', 1),
                    centrality=doc.get('centrality', 0.0)
                )
                entities.append(entity)
            
            return entities
            
        except Exception as e:
            logger.error(f"Failed to get entities from tenant db: {e}")
            return []
    
    async def _get_relations_from_tenant_db(self, tenant_db: Database, graph_id: str) -> List[Relation]:
        """从租户数据库获取关系"""
        try:
            relations_collection = tenant_db.collection('relations')
            cursor = await asyncio.to_thread(
                relations_collection.find,
                {'graph_id': graph_id}
            )
            
            relations = []
            for doc in cursor:
                relation = Relation(
                    id=doc['_key'],
                    subject=doc['_from'].split('/')[-1],  # 提取实际的实体ID
                    predicate=doc['predicate'],
                    object=doc['_to'].split('/')[-1],   # 提取实际的实体ID
                    confidence=doc['confidence'],
                    properties=doc.get('properties', {}),
                    source=doc.get('source', ''),
                    inferred=doc.get('inferred', False)
                )
                relations.append(relation)
            
            return relations
            
        except Exception as e:
            logger.error(f"Failed to get relations from tenant db: {e}")
            return []
    
    async def export_to_networkx(self, graph_id: str, user_id: str, project_id: str = None) -> Any:
        """导出图数据为NetworkX对象"""
        try:
            entities, relations = await self.get_graph_with_tenant_context(graph_id, user_id, project_id)
            return await self.networkx_adapter.export_to_networkx(graph_id, entities, relations)
            
        except Exception as e:
            logger.error(f"Failed to export graph to NetworkX: {e}")
            raise
    
    async def compute_advanced_metrics(self, graph_id: str, user_id: str, project_id: str = None, algorithms: List[str] = None) -> Dict[str, Any]:
        """计算高级图指标"""
        try:
            entities, relations = await self.get_graph_with_tenant_context(graph_id, user_id, project_id)
            return await self.networkx_adapter.compute_advanced_metrics(graph_id, entities, relations, algorithms)
            
        except Exception as e:
            logger.error(f"Failed to compute advanced metrics: {e}")
            return {"error": str(e)}
    
    async def get_subgraph(self, graph_id: str, center_entity: str, depth: int = 2, limit: int = 100, 
                          user_id: str = None, project_id: str = None) -> Dict[str, Any]:
        """获取子图"""
        try:
            entities, relations = await self.get_graph_with_tenant_context(graph_id, user_id, project_id)
            return await self.networkx_adapter.get_subgraph(graph_id, entities, relations, center_entity, depth, limit)
            
        except Exception as e:
            logger.error(f"Failed to get subgraph: {e}")
            return {"error": str(e), "nodes": [], "edges": []}
    
    async def find_shortest_path(self, graph_id: str, start_entity: str, end_entity: str,
                                user_id: str = None, project_id: str = None) -> Dict[str, Any]:
        """查找最短路径"""
        try:
            entities, relations = await self.get_graph_with_tenant_context(graph_id, user_id, project_id)
            return await self.networkx_adapter.find_shortest_path(graph_id, entities, relations, start_entity, end_entity)
            
        except Exception as e:
            logger.error(f"Failed to find shortest path: {e}")
            return {"error": str(e), "path": []}
    
    async def export_graph_data(self, graph_id: str, export_format: str = "json", 
                               user_id: str = None, project_id: str = None) -> Dict[str, Any]:
        """导出图数据为不同格式"""
        try:
            entities, relations = await self.get_graph_with_tenant_context(graph_id, user_id, project_id)
            return await self.networkx_adapter.export_to_formats(graph_id, entities, relations, export_format)
            
        except Exception as e:
            logger.error(f"Failed to export graph data: {e}")
            return {"error": str(e)}
    
    async def get_tenant_statistics(self, user_id: str, project_id: str = None) -> Dict[str, Any]:
        """获取租户统计信息"""
        try:
            tenant_id = await self.tenant_manager.get_tenant_context(user_id, project_id)
            return await self.tenant_manager.get_tenant_statistics(tenant_id)
            
        except Exception as e:
            logger.error(f"Failed to get tenant statistics: {e}")
            return {}
    
    async def list_tenant_graphs(self, user_id: str, project_id: str = None) -> List[str]:
        """列出租户的所有图谱"""
        try:
            tenant_id = await self.tenant_manager.get_tenant_context(user_id, project_id)
            return await self.tenant_manager.list_tenant_graphs(tenant_id)
            
        except Exception as e:
            logger.error(f"Failed to list tenant graphs: {e}")
            return []
    
    async def cleanup_resources(self):
        """清理资源"""
        try:
            await self.tenant_manager.cleanup_tenant_cache()
            await self.networkx_adapter.close()
            logger.info("ArangoDB repository resources cleaned up")
            
        except Exception as e:
            logger.error(f"Failed to cleanup resources: {e}")


# 全局仓库实例
_arangodb_repository = None


async def get_arangodb_repository() -> ArangoDBRepository:
    """获取ArangoDB仓库实例"""
    global _arangodb_repository
    if _arangodb_repository is None:
        _arangodb_repository = ArangoDBRepository()
    return _arangodb_repository