"""
租户隔离管理器
提供多租户数据隔离和管理功能
"""

import logging
import hashlib
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager
from arango import ArangoClient, ArangoError
from arango.database import Database
import asyncio

from ..config.settings import settings

logger = logging.getLogger(__name__)


class TenantIsolationManager:
    """租户隔离管理器"""
    
    def __init__(self, client: ArangoClient, username: str, password: str):
        self.client = client
        self.username = username
        self.password = password
        self.database_prefix = settings.ARANGODB_DATABASE_PREFIX or "kg_"
        
        # 租户缓存
        self._tenant_cache: Dict[str, str] = {}
        self._db_cache: Dict[str, Database] = {}
        
        # 租户策略配置
        self.users_per_tenant = settings.GRAPH_TENANT_USERS_PER_SHARD or 1000
        self.max_cached_dbs = settings.GRAPH_TENANT_MAX_CACHED_DBS or 100
        
        # 延迟初始化系统数据库
        self.sys_db = None
    
    def _ensure_system_db(self):
        """确保系统数据库连接已初始化"""
        if self.sys_db is None:
            self.sys_db = self.client.db('_system', username=self.username, password=self.password)
    
    async def get_tenant_context(self, user_id: str, project_id: str = None) -> str:
        """获取用户的租户上下文"""
        cache_key = f"{user_id}_{project_id or 'default'}"
        
        if cache_key in self._tenant_cache:
            return self._tenant_cache[cache_key]
        
        tenant_id = self._calculate_tenant_id(user_id, project_id)
        self._tenant_cache[cache_key] = tenant_id
        
        return tenant_id
    
    def _calculate_tenant_id(self, user_id: str, project_id: str = None) -> str:
        """计算租户ID"""
        try:
            # 尝试将user_id转换为整数进行分片
            user_int = int(user_id) if user_id.isdigit() else int(hashlib.md5(user_id.encode()).hexdigest()[:8], 16)
            tenant_group = user_int // self.users_per_tenant
            
            if project_id:
                # 项目级别隔离
                return f"group_{tenant_group}_project_{project_id}"
            else:
                # 用户级别隔离
                return f"group_{tenant_group}"
        except Exception as e:
            logger.warning(f"Failed to calculate tenant ID for user {user_id}: {e}")
            # 回退到简单hash策略
            hash_key = f"{user_id}_{project_id or 'default'}"
            tenant_hash = hashlib.md5(hash_key.encode()).hexdigest()[:8]
            return f"group_{tenant_hash}"
    
    async def get_tenant_database(self, tenant_id: str) -> Database:
        """获取租户数据库连接"""
        if tenant_id in self._db_cache:
            try:
                # 测试连接是否有效
                db = self._db_cache[tenant_id]
                await asyncio.to_thread(db.properties)
                return db
            except Exception as e:
                logger.warning(f"Cached tenant database connection invalid: {e}")
                del self._db_cache[tenant_id]
        
        # 创建或获取租户数据库
        db = await self._ensure_tenant_database(tenant_id)
        
        # 缓存管理
        if len(self._db_cache) >= self.max_cached_dbs:
            # 清理最旧的缓存
            oldest_key = next(iter(self._db_cache))
            del self._db_cache[oldest_key]
        
        self._db_cache[tenant_id] = db
        return db
    
    async def _ensure_tenant_database(self, tenant_id: str) -> Database:
        """确保租户数据库存在"""
        self._ensure_system_db()  # 确保系统数据库连接已初始化
        db_name = f"{self.database_prefix}tenant_{tenant_id}"
        
        try:
            # 检查数据库是否存在
            if not await asyncio.to_thread(self.sys_db.has_database, db_name):
                logger.info(f"Creating tenant database: {db_name}")
                await asyncio.to_thread(self.sys_db.create_database, db_name)
            
            # 连接到租户数据库
            tenant_db = self.client.db(db_name, username=self.username, password=self.password)
            
            # 初始化租户数据库结构
            await self._init_tenant_database_structure(tenant_db)
            
            return tenant_db
            
        except ArangoError as e:
            logger.error(f"Failed to create/access tenant database {db_name}: {e}")
            raise
    
    async def _init_tenant_database_structure(self, tenant_db: Database):
        """初始化租户数据库结构"""
        try:
            # 创建基础集合
            collections_to_create = [
                'entities',
                'relations', 
                'graphs_metadata',
                'processing_tasks'
            ]
            
            for collection_name in collections_to_create:
                if not await asyncio.to_thread(tenant_db.has_collection, collection_name):
                    await asyncio.to_thread(tenant_db.create_collection, collection_name)
            
            # 创建边集合（如果不存在）
            edge_collections = ['relations']
            for edge_collection in edge_collections:
                if not await asyncio.to_thread(tenant_db.has_collection, edge_collection):
                    await asyncio.to_thread(tenant_db.create_collection, edge_collection, edge=True)
            
            # 创建图（如果不存在）
            graph_name = 'knowledge_graph'
            if not await asyncio.to_thread(tenant_db.has_graph, graph_name):
                await asyncio.to_thread(
                    tenant_db.create_graph,
                    graph_name,
                    edge_definitions=[{
                        'edge_collection': 'relations',
                        'from_vertex_collections': ['entities'],
                        'to_vertex_collections': ['entities']
                    }]
                )
            
            # 创建索引
            await self._create_tenant_indexes(tenant_db)
            
        except ArangoError as e:
            logger.error(f"Failed to initialize tenant database structure: {e}")
            raise
    
    async def _create_tenant_indexes(self, tenant_db: Database):
        """创建租户数据库索引"""
        try:
            # 实体集合索引
            entities_collection = tenant_db.collection('entities')
            indexes_to_create = [
                {'fields': ['name'], 'unique': False},
                {'fields': ['entity_type'], 'unique': False},
                {'fields': ['graph_id'], 'unique': False},
                {'fields': ['graph_id', 'name'], 'unique': True},
                {'fields': ['created_at'], 'unique': False}
            ]
            
            for index_config in indexes_to_create:
                try:
                    await asyncio.to_thread(entities_collection.add_index, **index_config)
                except ArangoError as e:
                    # 索引可能已存在，忽略错误
                    if "duplicate" not in str(e).lower():
                        logger.warning(f"Failed to create index {index_config}: {e}")
            
            # 关系集合索引
            relations_collection = tenant_db.collection('relations')
            relation_indexes = [
                {'fields': ['_from'], 'unique': False},
                {'fields': ['_to'], 'unique': False},
                {'fields': ['predicate'], 'unique': False},
                {'fields': ['graph_id'], 'unique': False},
                {'fields': ['created_at'], 'unique': False}
            ]
            
            for index_config in relation_indexes:
                try:
                    await asyncio.to_thread(relations_collection.add_index, **index_config)
                except ArangoError as e:
                    if "duplicate" not in str(e).lower():
                        logger.warning(f"Failed to create relation index {index_config}: {e}")
                        
        except Exception as e:
            logger.error(f"Failed to create tenant indexes: {e}")
    
    async def cleanup_tenant_cache(self):
        """清理租户缓存"""
        self._tenant_cache.clear()
        
        # 关闭缓存的数据库连接
        for db in self._db_cache.values():
            try:
                # ArangoDB连接会自动清理，这里只是清理引用
                pass
            except Exception as e:
                logger.warning(f"Error cleaning up database connection: {e}")
        
        self._db_cache.clear()
    
    async def get_tenant_statistics(self, tenant_id: str) -> Dict[str, Any]:
        """获取租户统计信息"""
        try:
            tenant_db = await self.get_tenant_database(tenant_id)
            
            stats = {}
            
            # 获取集合统计
            for collection_name in ['entities', 'relations', 'graphs_metadata']:
                if await asyncio.to_thread(tenant_db.has_collection, collection_name):
                    collection = tenant_db.collection(collection_name)
                    properties = await asyncio.to_thread(collection.properties)
                    stats[f"{collection_name}_count"] = properties.get('count', 0)
            
            # 获取数据库统计
            db_properties = await asyncio.to_thread(tenant_db.properties)
            stats['database_size'] = db_properties.get('size', 0)
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get tenant statistics for {tenant_id}: {e}")
            return {}
    
    async def list_tenant_graphs(self, tenant_id: str) -> List[str]:
        """列出租户的所有图谱"""
        try:
            tenant_db = await self.get_tenant_database(tenant_id)
            
            if not await asyncio.to_thread(tenant_db.has_collection, 'graphs_metadata'):
                return []
            
            collection = tenant_db.collection('graphs_metadata')
            cursor = await asyncio.to_thread(collection.all)
            
            graphs = []
            for doc in cursor:
                graphs.append(doc.get('graph_id'))
            
            return graphs
            
        except Exception as e:
            logger.error(f"Failed to list tenant graphs for {tenant_id}: {e}")
            return []
    
    @asynccontextmanager
    async def tenant_context(self, user_id: str, project_id: str = None):
        """租户上下文管理器"""
        tenant_id = await self.get_tenant_context(user_id, project_id)
        tenant_db = await self.get_tenant_database(tenant_id)
        
        try:
            yield tenant_db, tenant_id
        finally:
            # 清理资源（如果需要）
            pass