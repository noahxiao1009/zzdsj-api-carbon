#!/usr/bin/env python3
"""
直接测试数据库连接和查询性能
"""

import time
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.config.settings import settings

def test_direct_db_performance():
    """测试直接数据库性能"""
    
    # 创建数据库连接
    database_url = f"postgresql://{settings.database.postgres_user}:{settings.database.postgres_password}@{settings.database.postgres_host}:{settings.database.postgres_port}/{settings.database.postgres_db}"
    
    print("测试数据库连接性能...")
    print(f"连接URL: {database_url}")
    
    # 测试1: 数据库连接时间
    start_time = time.time()
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    connect_time = time.time() - start_time
    print(f"✓ 数据库连接时间: {connect_time:.3f}s")
    
    # 测试2: 会话创建时间
    start_time = time.time()
    db = SessionLocal()
    session_time = time.time() - start_time
    print(f"✓ 会话创建时间: {session_time:.3f}s")
    
    try:
        # 测试3: 简单查询时间
        start_time = time.time()
        result = db.execute(text("SELECT 1"))
        simple_query_time = time.time() - start_time
        print(f"✓ 简单查询时间: {simple_query_time:.3f}s")
        
        # 测试4: knowledge_bases表查询时间
        start_time = time.time()
        result = db.execute(text("SELECT COUNT(*) FROM knowledge_bases"))
        count = result.scalar()
        table_query_time = time.time() - start_time
        print(f"✓ 知识库表查询时间: {table_query_time:.3f}s")
        print(f"✓ 知识库总数: {count}")
        
        # 测试5: 分页查询时间
        start_time = time.time()
        result = db.execute(text("""
            SELECT id, name, description, status, created_at, updated_at 
            FROM knowledge_bases 
            ORDER BY updated_at DESC 
            LIMIT 10 OFFSET 0
        """))
        rows = result.fetchall()
        paginated_query_time = time.time() - start_time
        print(f"✓ 分页查询时间: {paginated_query_time:.3f}s")
        print(f"✓ 返回行数: {len(rows)}")
        
        # 测试6: 多次查询平均时间
        times = []
        for i in range(5):
            start_time = time.time()
            result = db.execute(text("SELECT COUNT(*) FROM knowledge_bases"))
            result.scalar()
            query_time = time.time() - start_time
            times.append(query_time)
        
        avg_time = sum(times) / len(times)
        print(f"✓ 5次查询平均时间: {avg_time:.3f}s")
        
        # 性能评估
        total_time = connect_time + session_time + simple_query_time + table_query_time + paginated_query_time + sum(times)
        print(f"\n性能总结:")
        print(f"• 数据库连接: {connect_time:.3f}s")
        print(f"• 会话创建: {session_time:.3f}s")
        print(f"• 查询执行: {avg_time:.3f}s")
        print(f"• 总耗时: {total_time:.3f}s")
        
        if avg_time < 0.1:
            print("✓ 数据库性能正常")
            return True
        else:
            print("✗ 数据库性能异常")
            return False
            
    except Exception as e:
        print(f"✗ 数据库查询失败: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("数据库性能直接测试")
    print("=" * 50)
    
    success = test_direct_db_performance()
    
    print("=" * 50)
    if success:
        print("测试完成: 数据库性能正常")
        sys.exit(0)
    else:
        print("测试失败: 数据库性能异常")
        sys.exit(1)