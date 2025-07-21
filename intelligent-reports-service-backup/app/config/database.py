"""
数据库配置和连接管理
"""
import asyncio
from typing import AsyncGenerator
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool
import redis.asyncio as redis
from app.config.settings import settings
from shared.service_client import call_service, CallMethod


# 获取数据库配置
async def get_db_config():
    """从数据库服务获取配置"""
    try:
        result = await call_service(
            service_name="database-service",
            method=CallMethod.GET,
            path="/api/v1/config/postgresql"
        )
        return result
    except Exception as e:
        # 回退到默认配置
        return {
            "host": "localhost",
            "port": 5432,
            "username": "postgres",
            "password": "password",
            "database": "carbon_db",
            "max_connections": 20
        }

# 数据库引擎（使用统一配置）
engine = None

async def init_db_engine():
    """初始化数据库引擎"""
    global engine
    if engine is None:
        db_config = await get_db_config()
        database_url = f"postgresql+asyncpg://{db_config['username']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"
        
        engine = create_async_engine(
            database_url,
            echo=settings.debug,
            pool_size=db_config.get('max_connections', 20),
            max_overflow=30,
            pool_pre_ping=True,
        )
    return engine

# 会话工厂
async_session_factory = None

async def get_session_factory():
    """获取会话工厂"""
    global async_session_factory
    if async_session_factory is None:
        db_engine = await init_db_engine()
        async_session_factory = async_sessionmaker(
            db_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return async_session_factory

# 同步引擎（用于迁移）
sync_engine = None

async def init_sync_engine():
    """初始化同步引擎"""
    global sync_engine
    if sync_engine is None:
        db_config = await get_db_config()
        database_url = f"postgresql+psycopg2://{db_config['username']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"
        
        sync_engine = create_engine(
            database_url,
            echo=settings.debug,
            pool_size=db_config.get('max_connections', 20),
            max_overflow=30,
            pool_pre_ping=True,
        )
    return sync_engine

# 同步会话（用于迁移）
sync_session_factory = None

async def get_sync_session_factory():
    """获取同步会话工厂"""
    global sync_session_factory
    if sync_session_factory is None:
        sync_db_engine = await init_sync_engine()
        sync_session_factory = sessionmaker(
            sync_db_engine,
            expire_on_commit=False,
        )
    return sync_session_factory

# 基础模型
Base = declarative_base()

# 元数据
metadata = MetaData()

# Redis连接
redis_client = None

async def get_redis_config():
    """从数据库服务获取Redis配置"""
    try:
        result = await call_service(
            service_name="database-service",
            method=CallMethod.GET,
            path="/api/v1/config/redis"
        )
        return result
    except Exception as e:
        # 回退到默认配置
        return {
            "host": "localhost",
            "port": 6379,
            "password": None,
            "db": 0
        }


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话"""
    session_factory = await get_session_factory()
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_database():
    """初始化数据库"""
    db_engine = await init_db_engine()
    async with db_engine.begin() as conn:
        # 创建所有表
        await conn.run_sync(Base.metadata.create_all)


async def close_database():
    """关闭数据库连接"""
    global engine
    if engine:
        await engine.dispose()


async def init_redis():
    """初始化Redis连接"""
    global redis_client
    redis_config = await get_redis_config()
    
    redis_url = f"redis://{redis_config['host']}:{redis_config['port']}/{redis_config['db']}"
    redis_client = redis.from_url(
        redis_url,
        password=redis_config.get('password'),
        decode_responses=True,
        retry_on_timeout=True,
        socket_keepalive=True,
        socket_keepalive_options={},
    )
    
    # 测试连接
    try:
        await redis_client.ping()
        print("Redis连接成功")
    except Exception as e:
        print(f"Redis连接失败: {e}")
        raise


async def close_redis():
    """关闭Redis连接"""
    global redis_client
    if redis_client:
        await redis_client.close()


async def get_redis() -> redis.Redis:
    """获取Redis客户端"""
    global redis_client
    if redis_client is None:
        await init_redis()
    return redis_client


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self):
        self.engine = None
        self.session_factory = None
    
    async def init(self):
        """初始化管理器"""
        self.engine = await init_db_engine()
        self.session_factory = await get_session_factory()
    
    async def create_session(self) -> AsyncSession:
        """创建数据库会话"""
        if self.session_factory is None:
            await self.init()
        return self.session_factory()
    
    async def execute_query(self, query: str, params: dict = None):
        """执行查询"""
        if self.session_factory is None:
            await self.init()
        async with self.session_factory() as session:
            result = await session.execute(query, params or {})
            return result
    
    async def execute_transaction(self, operations: list):
        """执行事务"""
        if self.session_factory is None:
            await self.init()
        async with self.session_factory() as session:
            async with session.begin():
                results = []
                for operation in operations:
                    result = await session.execute(operation["query"], operation.get("params", {}))
                    results.append(result)
                return results
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            if self.session_factory is None:
                await self.init()
            async with self.session_factory() as session:
                await session.execute("SELECT 1")
                return True
        except Exception:
            return False


class RedisManager:
    """Redis管理器"""
    
    def __init__(self):
        self.client = None
    
    async def init(self):
        """初始化Redis连接"""
        await init_redis()
        self.client = redis_client
    
    async def get(self, key: str) -> str:
        """获取值"""
        return await self.client.get(key)
    
    async def set(self, key: str, value: str, ex: int = None):
        """设置值"""
        return await self.client.set(key, value, ex=ex)
    
    async def delete(self, key: str):
        """删除键"""
        return await self.client.delete(key)
    
    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        return await self.client.exists(key)
    
    async def hget(self, name: str, key: str) -> str:
        """获取哈希值"""
        return await self.client.hget(name, key)
    
    async def hset(self, name: str, key: str, value: str):
        """设置哈希值"""
        return await self.client.hset(name, key, value)
    
    async def hdel(self, name: str, key: str):
        """删除哈希键"""
        return await self.client.hdel(name, key)
    
    async def lpush(self, name: str, *values):
        """列表左推"""
        return await self.client.lpush(name, *values)
    
    async def rpop(self, name: str):
        """列表右弹"""
        return await self.client.rpop(name)
    
    async def llen(self, name: str) -> int:
        """列表长度"""
        return await self.client.llen(name)
    
    async def expire(self, key: str, seconds: int):
        """设置过期时间"""
        return await self.client.expire(key, seconds)
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            await self.client.ping()
            return True
        except Exception:
            return False


# 全局实例
db_manager = DatabaseManager()
redis_manager = RedisManager()


async def init_connections():
    """初始化所有连接"""
    await init_database()
    await redis_manager.init()


async def close_connections():
    """关闭所有连接"""
    await close_database()
    await close_redis()


# 依赖注入
async def get_database() -> DatabaseManager:
    """获取数据库管理器"""
    return db_manager


async def get_redis_manager() -> RedisManager:
    """获取Redis管理器"""
    return redis_manager