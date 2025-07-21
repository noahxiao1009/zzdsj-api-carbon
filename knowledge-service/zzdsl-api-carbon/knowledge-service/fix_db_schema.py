#!/usr/bin/env python3
"""
修复数据库表结构
"""

import sys
import os
from sqlalchemy import create_engine, text, inspect

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.config.settings import settings

def check_and_fix_knowledge_bases_table():
    """检查并修复knowledge_bases表结构"""
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        # 检查当前表结构
        inspector = inspect(engine)
        columns = inspector.get_columns('knowledge_bases')
        column_names = [col['name'] for col in columns]
        
        print("当前knowledge_bases表的列:", column_names)
        
        # 需要添加的列
        missing_columns = []
        
        required_columns = {
            'vector_store_type': 'VARCHAR(50) DEFAULT \'milvus\'',
            'vector_store_config': 'JSON DEFAULT \'{}\'',
            'chunk_strategy': 'VARCHAR(50) DEFAULT \'token_based\'',
            'enable_hybrid_search': 'BOOLEAN DEFAULT TRUE',
            'enable_agno_integration': 'BOOLEAN DEFAULT TRUE',
            'agno_search_type': 'VARCHAR(50) DEFAULT \'knowledge\'',
        }
        
        for col_name, col_def in required_columns.items():
            if col_name not in column_names:
                missing_columns.append((col_name, col_def))
        
        if missing_columns:
            print(f"需要添加的列: {[col[0] for col in missing_columns]}")
            
            # 添加缺失的列
            for col_name, col_def in missing_columns:
                try:
                    alter_sql = f"ALTER TABLE knowledge_bases ADD COLUMN {col_name} {col_def}"
                    print(f"执行: {alter_sql}")
                    conn.execute(text(alter_sql))
                    conn.commit()
                    print(f"✅ 成功添加列: {col_name}")
                except Exception as e:
                    print(f"❌ 添加列 {col_name} 失败: {e}")
                    conn.rollback()
        else:
            print("✅ 表结构完整，无需修复")

        # 再次检查表结构
        inspector = inspect(engine)
        columns = inspector.get_columns('knowledge_bases')
        column_names = [col['name'] for col in columns]
        
        print("修复后knowledge_bases表的列:", column_names)

if __name__ == "__main__":
    print("开始检查和修复数据库表结构...")
    check_and_fix_knowledge_bases_table()
    print("数据库表结构检查完成")
