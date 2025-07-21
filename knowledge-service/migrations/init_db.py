"""
数据库迁移初始化脚本
"""

import os
import sys
import asyncio
from sqlalchemy import create_engine, text
from alembic import command
from alembic.config import Config

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config.settings import settings
from app.models.database import Base, engine
from app.models.knowledge_models import *


def create_database_if_not_exists():
    """创建数据库（如果不存在）"""
    # 解析数据库URL
    db_url_parts = settings.DATABASE_URL.split('/')
    db_name = db_url_parts[-1]
    server_url = '/'.join(db_url_parts[:-1]) + '/postgres'
    
    # 连接到postgres数据库
    temp_engine = create_engine(server_url)
    with temp_engine.connect() as conn:
        # 检查数据库是否存在
        result = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
            {"db_name": db_name}
        )
        
        if not result.fetchone():
            # 创建数据库
            conn.execute(text("COMMIT"))
            conn.execute(text(f"CREATE DATABASE {db_name}"))
            print(f"数据库 {db_name} 已创建")
        else:
            print(f"数据库 {db_name} 已存在")
    
    temp_engine.dispose()


def init_alembic():
    """初始化Alembic配置"""
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", "migrations")
    alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    
    # 创建migrations目录结构
    if not os.path.exists("migrations"):
        command.init(alembic_cfg, "migrations")
        print("Alembic migrations目录已初始化")
    
    return alembic_cfg


def create_tables():
    """创建所有表"""
    try:
        # 确保数据库存在
        create_database_if_not_exists()
        
        # 创建所有表
        Base.metadata.create_all(bind=engine)
        print("所有数据表已创建")
        
        # 显示创建的表
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """))
            tables = [row[0] for row in result]
            print(f"已创建的表: {', '.join(tables)}")
            
    except Exception as e:
        print(f"创建表失败: {e}")
        raise


def create_migration():
    """创建初始迁移文件"""
    try:
        alembic_cfg = init_alembic()
        
        # 创建初始迁移
        command.revision(
            alembic_cfg, 
            message="Initial migration with knowledge base models",
            autogenerate=True
        )
        print("初始迁移文件已创建")
        
    except Exception as e:
        print(f"创建迁移文件失败: {e}")
        raise


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="数据库迁移管理")
    parser.add_argument("--init", action="store_true", help="初始化数据库和迁移")
    parser.add_argument("--create-tables", action="store_true", help="直接创建表")
    parser.add_argument("--create-migration", action="store_true", help="创建迁移文件")
    
    args = parser.parse_args()
    
    if args.init:
        print("开始初始化数据库...")
        create_tables()
        create_migration()
        print("数据库初始化完成")
    elif args.create_tables:
        create_tables()
    elif args.create_migration:
        create_migration()
    else:
        print("请使用 --init, --create-tables 或 --create-migration 参数")