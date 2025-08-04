#!/usr/bin/env python3
"""
检查数据库表结构
"""

from app.models.database import get_db
from sqlalchemy import text

def check_table_schema():
    db = next(get_db())
    try:
        # 检查splitter_strategy_usage表结构
        result = db.execute(text("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'splitter_strategy_usage' 
            ORDER BY ordinal_position
        """))
        
        print("splitter_strategy_usage表结构:")
        for row in result:
            print(f"  {row[0]}: {row[1]} (nullable: {row[2]})")
        
        # 检查knowledge_bases表结构
        result = db.execute(text("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'knowledge_bases' 
            AND column_name = 'id'
        """))
        
        print("\nknowledge_bases.id字段类型:")
        for row in result:
            print(f"  {row[0]}: {row[1]} (nullable: {row[2]})")
            
    finally:
        db.close()

if __name__ == "__main__":
    check_table_schema() 