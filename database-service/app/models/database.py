"""
数据库基础模块
提供数据库连接、会话管理和基础模型类
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
import uuid
from datetime import datetime

from sqlalchemy import create_engine, Column, String, DateTime, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from ..config.database_config import get_database_config

# 创建基础模型类
Base = declarative_base()

# 全局变量存储引擎和会话工厂
_async_engine = None
_async_session_factory = None
_sync_engine = None
_sync_session_factory = None


class BaseModel(Base):
    """基础模型类，包含通用字段"""
    __abstract__ = True
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


async def init_database():
    """初始化数据库连接"""
    global _async_engine, _async_session_factory, _sync_engine, _sync_session_factory
    
    config = get_database_config()
    
    # 创建异步引擎
    _async_engine = create_async_engine(
        config.postgresql.async_database_url,
        echo=config.debug,
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_size=10,
        max_overflow=20
    )
    
    # 创建异步会话工厂
    _async_session_factory = async_sessionmaker(
        bind=_async_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    # 创建同步引擎（用于迁移等操作）
    _sync_engine = create_engine(
        config.postgresql.sync_database_url,
        echo=config.debug,
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_size=5,
        max_overflow=10
    )
    
    # 创建同步会话工厂
    _sync_session_factory = sessionmaker(
        bind=_sync_engine,
        autocommit=False,
        autoflush=False
    )


async def close_database():
    """关闭数据库连接"""
    global _async_engine, _sync_engine
    
    if _async_engine:
        await _async_engine.dispose()
        _async_engine = None
    
    if _sync_engine:
        _sync_engine.dispose()
        _sync_engine = None


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """获取异步数据库会话"""
    if not _async_session_factory:
        await init_database()
    
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_sync_db_session() -> Session:
    """获取同步数据库会话（用于迁移等操作）"""
    if not _sync_session_factory:
        # 同步初始化
        config = get_database_config()
        global _sync_engine, _sync_session_factory
        
        _sync_engine = create_engine(
            config.postgresql.sync_database_url,
            echo=config.debug,
            pool_pre_ping=True
        )
        
        _sync_session_factory = sessionmaker(
            bind=_sync_engine,
            autocommit=False,
            autoflush=False
        )
    
    return _sync_session_factory()


async def create_tables():
    """创建所有数据库表"""
    if not _async_engine:
        await init_database()
    
    async with _async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables():
    """删除所有数据库表"""
    if not _async_engine:
        await init_database()
    
    async with _async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def get_engine():
    """获取数据库引擎"""
    return _async_engine


def get_sync_engine():
    """获取同步数据库引擎"""
    return _sync_engine


# 数据库依赖注入函数（用于FastAPI）
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """数据库会话依赖项，用于API路由中获取数据库会话"""
    async with get_db_session() as session:
        yield session


# 事务装饰器
def transactional(func):
    """事务装饰器，自动处理事务提交和回滚"""
    async def wrapper(*args, **kwargs):
        async with get_db_session() as session:
            try:
                result = await func(session, *args, **kwargs)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise
    return wrapper


class DatabaseManager:
    """数据库管理器，提供高级数据库操作"""
    
    def __init__(self):
        self.is_initialized = False
    
    async def initialize(self):
        """初始化数据库管理器"""
        if not self.is_initialized:
            await init_database()
            self.is_initialized = True
    
    async def health_check(self) -> bool:
        """数据库健康检查"""
        try:
            async with get_db_session() as session:
                await session.execute("SELECT 1")
                return True
        except Exception:
            return False
    
    async def get_connection_info(self) -> dict:
        """获取数据库连接信息"""
        config = get_database_config()
        return {
            "database_url": config.postgresql.host,
            "database_name": config.postgresql.database,
            "pool_size": 10,
            "max_overflow": 20,
            "is_connected": await self.health_check()
        }
    
    async def execute_raw_sql(self, sql: str, params: dict = None):
        """执行原始SQL语句"""
        async with get_db_session() as session:
            result = await session.execute(sql, params or {})
            return result.fetchall()
    
    async def backup_database(self, backup_path: str):
        """备份数据库（需要实现具体逻辑）"""
        # TODO: 实现数据库备份逻辑
        pass
    
    async def restore_database(self, backup_path: str):
        """恢复数据库（需要实现具体逻辑）"""
        # TODO: 实现数据库恢复逻辑
        pass


# 全局数据库管理器实例
db_manager = DatabaseManager()