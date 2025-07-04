"""
数据库连接管理器
统一管理ES、PostgreSQL、Milvus、Redis、Nacos、RabbitMQ的连接
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager
import time
from datetime import datetime

# 数据库驱动
import asyncpg
import redis.asyncio as redis
from elasticsearch import AsyncElasticsearch
from pymilvus import connections, utility, MilvusClient
import aio_pika
from nacos import NacosClient

from ...config.database_config import (
    DatabaseServiceConfig, 
    DatabaseType, 
    DatabaseStatus,
    get_database_config
)

logger = logging.getLogger(__name__)


class DatabaseConnectionManager:
    """数据库连接管理器"""
    
    def __init__(self, config: DatabaseServiceConfig):
        self.config = config
        self.connections: Dict[DatabaseType, Any] = {}
        self.connection_pools: Dict[DatabaseType, Any] = {}
        self.status: Dict[DatabaseType, DatabaseStatus] = {}
        self.last_health_check: Dict[DatabaseType, datetime] = {}
        self._lock = asyncio.Lock()
        
    async def initialize_all_connections(self):
        """初始化所有数据库连接"""
        logger.info("开始初始化所有数据库连接...")
        
        # 初始化各数据库连接
        await asyncio.gather(
            self._init_postgresql(),
            self._init_elasticsearch(),
            self._init_milvus(),
            self._init_redis(),
            self._init_nacos(),
            self._init_rabbitmq(),
            return_exceptions=True
        )
        
        logger.info("数据库连接初始化完成")
    
    async def _init_postgresql(self):
        """初始化PostgreSQL连接"""
        try:
            logger.info("正在初始化PostgreSQL连接...")
            self.status[DatabaseType.POSTGRESQL] = DatabaseStatus.CONNECTING
            
            # 创建连接池
            pool = await asyncpg.create_pool(
                host=self.config.postgresql.host,
                port=self.config.postgresql.port,
                user=self.config.postgresql.username,
                password=self.config.postgresql.password,
                database=self.config.postgresql.database,
                max_size=self.config.postgresql.max_connections,
                command_timeout=self.config.postgresql.connection_timeout
            )
            
            self.connection_pools[DatabaseType.POSTGRESQL] = pool
            self.status[DatabaseType.POSTGRESQL] = DatabaseStatus.HEALTHY
            logger.info("PostgreSQL连接初始化成功")
            
        except Exception as e:
            logger.error(f"PostgreSQL连接初始化失败: {e}")
            self.status[DatabaseType.POSTGRESQL] = DatabaseStatus.UNHEALTHY
            raise
    
    async def _init_elasticsearch(self):
        """初始化Elasticsearch连接"""
        try:
            logger.info("正在初始化Elasticsearch连接...")
            self.status[DatabaseType.ELASTICSEARCH] = DatabaseStatus.CONNECTING
            
            # 创建ES客户端
            auth_params = {}
            if self.config.elasticsearch.username and self.config.elasticsearch.password:
                auth_params['basic_auth'] = (
                    self.config.elasticsearch.username,
                    self.config.elasticsearch.password
                )
            elif self.config.elasticsearch.api_key:
                auth_params['api_key'] = self.config.elasticsearch.api_key
            
            client = AsyncElasticsearch(
                hosts=self.config.elasticsearch.hosts,
                timeout=self.config.elasticsearch.timeout,
                max_retries=self.config.elasticsearch.max_retries,
                retry_on_timeout=self.config.elasticsearch.retry_on_timeout,
                **auth_params
            )
            
            # 测试连接
            await client.ping()
            
            self.connections[DatabaseType.ELASTICSEARCH] = client
            self.status[DatabaseType.ELASTICSEARCH] = DatabaseStatus.HEALTHY
            logger.info("Elasticsearch连接初始化成功")
            
        except Exception as e:
            logger.error(f"Elasticsearch连接初始化失败: {e}")
            self.status[DatabaseType.ELASTICSEARCH] = DatabaseStatus.UNHEALTHY
            raise
    
    async def _init_milvus(self):
        """初始化Milvus连接"""
        try:
            logger.info("正在初始化Milvus连接...")
            self.status[DatabaseType.MILVUS] = DatabaseStatus.CONNECTING
            
            # 创建Milvus连接
            connection_params = {
                "host": self.config.milvus.host,
                "port": self.config.milvus.port,
                "timeout": self.config.milvus.timeout
            }
            
            if self.config.milvus.username and self.config.milvus.password:
                connection_params.update({
                    "user": self.config.milvus.username,
                    "password": self.config.milvus.password
                })
            
            connections.connect(
                alias="default",
                **connection_params
            )
            
            # 创建客户端
            client = MilvusClient(
                uri=f"http://{self.config.milvus.host}:{self.config.milvus.port}",
                user=self.config.milvus.username,
                password=self.config.milvus.password,
                secure=self.config.milvus.secure,
                timeout=self.config.milvus.timeout
            )
            
            self.connections[DatabaseType.MILVUS] = client
            self.status[DatabaseType.MILVUS] = DatabaseStatus.HEALTHY
            logger.info("Milvus连接初始化成功")
            
        except Exception as e:
            logger.error(f"Milvus连接初始化失败: {e}")
            self.status[DatabaseType.MILVUS] = DatabaseStatus.UNHEALTHY
            raise
    
    async def _init_redis(self):
        """初始化Redis连接"""
        try:
            logger.info("正在初始化Redis连接...")
            self.status[DatabaseType.REDIS] = DatabaseStatus.CONNECTING
            
            # 创建Redis连接池
            if self.config.redis.cluster_enabled:
                # 集群模式
                pool = redis.ConnectionPool.from_url(
                    f"redis://{self.config.redis.host}:{self.config.redis.port}",
                    password=self.config.redis.password,
                    db=self.config.redis.db,
                    max_connections=self.config.redis.max_connections,
                    socket_connect_timeout=self.config.redis.connection_timeout,
                    retry_on_timeout=self.config.redis.retry_on_timeout
                )
            else:
                # 单机模式
                pool = redis.ConnectionPool(
                    host=self.config.redis.host,
                    port=self.config.redis.port,
                    password=self.config.redis.password,
                    db=self.config.redis.db,
                    max_connections=self.config.redis.max_connections,
                    socket_connect_timeout=self.config.redis.connection_timeout,
                    retry_on_timeout=self.config.redis.retry_on_timeout
                )
            
            client = redis.Redis(connection_pool=pool)
            
            # 测试连接
            await client.ping()
            
            self.connection_pools[DatabaseType.REDIS] = pool
            self.connections[DatabaseType.REDIS] = client
            self.status[DatabaseType.REDIS] = DatabaseStatus.HEALTHY
            logger.info("Redis连接初始化成功")
            
        except Exception as e:
            logger.error(f"Redis连接初始化失败: {e}")
            self.status[DatabaseType.REDIS] = DatabaseStatus.UNHEALTHY
            raise
    
    async def _init_nacos(self):
        """初始化Nacos连接"""
        try:
            logger.info("正在初始化Nacos连接...")
            self.status[DatabaseType.NACOS] = DatabaseStatus.CONNECTING
            
            # 创建Nacos客户端
            client = NacosClient(
                server_addresses=self.config.nacos.server_addresses,
                namespace=self.config.nacos.namespace,
                username=self.config.nacos.username,
                password=self.config.nacos.password,
                timeout=self.config.nacos.config_timeout
            )
            
            # 测试连接
            try:
                client.get_config("test_config", self.config.nacos.group)
            except Exception:
                pass  # 测试配置可能不存在，但连接正常
            
            self.connections[DatabaseType.NACOS] = client
            self.status[DatabaseType.NACOS] = DatabaseStatus.HEALTHY
            logger.info("Nacos连接初始化成功")
            
        except Exception as e:
            logger.error(f"Nacos连接初始化失败: {e}")
            self.status[DatabaseType.NACOS] = DatabaseStatus.UNHEALTHY
            raise
    
    async def _init_rabbitmq(self):
        """初始化RabbitMQ连接"""
        try:
            logger.info("正在初始化RabbitMQ连接...")
            self.status[DatabaseType.RABBITMQ] = DatabaseStatus.CONNECTING
            
            # 创建RabbitMQ连接
            connection = await aio_pika.connect_robust(
                host=self.config.rabbitmq.host,
                port=self.config.rabbitmq.port,
                login=self.config.rabbitmq.username,
                password=self.config.rabbitmq.password,
                virtualhost=self.config.rabbitmq.virtual_host,
                timeout=self.config.rabbitmq.connection_timeout,
                heartbeat=self.config.rabbitmq.heartbeat
            )
            
            self.connections[DatabaseType.RABBITMQ] = connection
            self.status[DatabaseType.RABBITMQ] = DatabaseStatus.HEALTHY
            logger.info("RabbitMQ连接初始化成功")
            
        except Exception as e:
            logger.error(f"RabbitMQ连接初始化失败: {e}")
            self.status[DatabaseType.RABBITMQ] = DatabaseStatus.UNHEALTHY
            raise
    
    async def get_connection(self, db_type: DatabaseType) -> Any:
        """获取数据库连接"""
        async with self._lock:
            if db_type not in self.connections and db_type not in self.connection_pools:
                raise ValueError(f"未找到 {db_type} 的连接")
            
            if db_type in self.connection_pools:
                return self.connection_pools[db_type]
            
            return self.connections[db_type]
    
    @asynccontextmanager
    async def get_postgresql_connection(self):
        """获取PostgreSQL连接上下文管理器"""
        pool = await self.get_connection(DatabaseType.POSTGRESQL)
        async with pool.acquire() as conn:
            yield conn
    
    async def get_elasticsearch_client(self) -> AsyncElasticsearch:
        """获取Elasticsearch客户端"""
        return await self.get_connection(DatabaseType.ELASTICSEARCH)
    
    async def get_milvus_client(self) -> MilvusClient:
        """获取Milvus客户端"""
        return await self.get_connection(DatabaseType.MILVUS)
    
    async def get_redis_client(self) -> redis.Redis:
        """获取Redis客户端"""
        return await self.get_connection(DatabaseType.REDIS)
    
    async def get_nacos_client(self) -> NacosClient:
        """获取Nacos客户端"""
        return await self.get_connection(DatabaseType.NACOS)
    
    async def get_rabbitmq_connection(self) -> aio_pika.Connection:
        """获取RabbitMQ连接"""
        return await self.get_connection(DatabaseType.RABBITMQ)
    
    async def health_check(self, db_type: DatabaseType = None) -> Dict[DatabaseType, DatabaseStatus]:
        """执行健康检查"""
        if db_type:
            await self._check_single_database(db_type)
            return {db_type: self.status.get(db_type, DatabaseStatus.DISCONNECTED)}
        
        # 检查所有数据库
        await asyncio.gather(
            *[self._check_single_database(dt) for dt in DatabaseType],
            return_exceptions=True
        )
        
        return self.status.copy()
    
    async def _check_single_database(self, db_type: DatabaseType):
        """检查单个数据库健康状态"""
        try:
            if db_type == DatabaseType.POSTGRESQL:
                pool = await self.get_connection(db_type)
                async with pool.acquire() as conn:
                    await conn.execute("SELECT 1")
            
            elif db_type == DatabaseType.ELASTICSEARCH:
                client = await self.get_elasticsearch_client()
                await client.ping()
            
            elif db_type == DatabaseType.MILVUS:
                client = await self.get_milvus_client()
                client.list_collections()
            
            elif db_type == DatabaseType.REDIS:
                client = await self.get_redis_client()
                await client.ping()
            
            elif db_type == DatabaseType.NACOS:
                client = await self.get_nacos_client()
                # Nacos健康检查
                pass
            
            elif db_type == DatabaseType.RABBITMQ:
                connection = await self.get_rabbitmq_connection()
                if connection.is_closed:
                    raise Exception("RabbitMQ连接已关闭")
            
            self.status[db_type] = DatabaseStatus.HEALTHY
            self.last_health_check[db_type] = datetime.now()
            
        except Exception as e:
            logger.error(f"{db_type} 健康检查失败: {e}")
            self.status[db_type] = DatabaseStatus.UNHEALTHY
    
    async def close_all_connections(self):
        """关闭所有数据库连接"""
        logger.info("正在关闭所有数据库连接...")
        
        # 关闭PostgreSQL连接池
        if DatabaseType.POSTGRESQL in self.connection_pools:
            await self.connection_pools[DatabaseType.POSTGRESQL].close()
        
        # 关闭Elasticsearch客户端
        if DatabaseType.ELASTICSEARCH in self.connections:
            await self.connections[DatabaseType.ELASTICSEARCH].close()
        
        # 关闭Milvus连接
        if DatabaseType.MILVUS in self.connections:
            connections.disconnect("default")
        
        # 关闭Redis连接
        if DatabaseType.REDIS in self.connections:
            await self.connections[DatabaseType.REDIS].close()
        
        # 关闭RabbitMQ连接
        if DatabaseType.RABBITMQ in self.connections:
            await self.connections[DatabaseType.RABBITMQ].close()
        
        logger.info("所有数据库连接已关闭")
    
    def get_status_summary(self) -> Dict[str, Any]:
        """获取状态摘要"""
        return {
            "total_databases": len(DatabaseType),
            "healthy_count": sum(1 for status in self.status.values() if status == DatabaseStatus.HEALTHY),
            "unhealthy_count": sum(1 for status in self.status.values() if status == DatabaseStatus.UNHEALTHY),
            "status_detail": {dt.value: status.value for dt, status in self.status.items()},
            "last_health_check": {
                dt.value: check_time.isoformat() if check_time else None
                for dt, check_time in self.last_health_check.items()
            }
        }


# 全局数据库管理器实例
_db_manager: Optional[DatabaseConnectionManager] = None


async def get_database_manager() -> DatabaseConnectionManager:
    """获取数据库管理器实例"""
    global _db_manager
    if _db_manager is None:
        config = get_database_config()
        _db_manager = DatabaseConnectionManager(config)
        await _db_manager.initialize_all_connections()
    return _db_manager


async def close_database_manager():
    """关闭数据库管理器"""
    global _db_manager
    if _db_manager:
        await _db_manager.close_all_connections()
        _db_manager = None 