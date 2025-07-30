"""
数据库连接配置
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config.settings import settings

# 创建SQLAlchemy引擎
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,                    # 连接池大小
    max_overflow=20,                 # 最大溢出连接数
    pool_timeout=30,                 # 获取连接的超时时间
    pool_recycle=3600,               # 连接回收时间(1小时)
    connect_args={
        "connect_timeout": 10,       # 连接超时
        "application_name": "knowledge-service",
        "sslmode": "prefer"          # SSL连接模式
    },
    echo=settings.DEBUG
)

# 创建SessionLocal类
SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine
)

# 创建Base基类
Base = declarative_base()

def get_db():
    """
    数据库会话依赖项，用于API路由中获取数据库会话
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()