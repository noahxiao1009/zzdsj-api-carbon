"""
System Service 数据库连接管理
"""

import logging
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from typing import Generator

from app.core.config import settings

logger = logging.getLogger(__name__)

# SQLAlchemy引擎
engine = create_engine(
    settings.database_url,
    echo=settings.db_echo,
    poolclass=QueuePool,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,  # 连接前检查
    pool_recycle=3600,   # 1小时后回收连接
    connect_args={
        "options": "-c timezone=Asia/Shanghai"
    }
)

# Session工厂
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False
)

# 声明基类
Base = declarative_base()


def init_database():
    """初始化数据库连接"""
    try:
        # 测试数据库连接
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("数据库连接初始化成功")
    except Exception as e:
        logger.error(f"数据库连接初始化失败: {e}")
        raise


def get_db() -> Generator[Session, None, None]:
    """
    获取数据库会话
    用作FastAPI依赖注入
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"数据库会话错误: {e}")
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    获取数据库会话上下文管理器
    用于直接调用
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        logger.error(f"数据库操作错误: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def check_database_health() -> bool:
    """检查数据库健康状态"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"数据库健康检查失败: {e}")
        return False


def get_database_info() -> dict:
    """获取数据库信息"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            
            pool_status = {
                "pool_size": engine.pool.size(),
                "checked_out": engine.pool.checkedout(),
                "overflow": engine.pool.overflow(),
                "checked_in": engine.pool.checkedin()
            }
            
            return {
                "connected": True,
                "version": version,
                "pool_status": pool_status,
                "url": str(engine.url).replace(f":{engine.url.password}@", ":***@")
            }
    except Exception as e:
        logger.error(f"获取数据库信息失败: {e}")
        return {
            "connected": False,
            "error": str(e)
        }


# 导出
__all__ = [
    "engine", 
    "SessionLocal", 
    "Base", 
    "init_database", 
    "get_db", 
    "get_db_session",
    "check_database_health",
    "get_database_info"
]
