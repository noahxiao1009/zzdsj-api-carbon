#!/usr/bin/env python3
"""
测试快速知识库管理器性能
"""

import asyncio
import time
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.core.fast_knowledge_manager import FastKnowledgeManager, get_fast_knowledge_manager
from app.models.database import get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def test_fast_manager_performance():
    """测试快速管理器性能"""
    # 创建数据库连接
    from app.config.settings import settings
    
    database_url = f"postgresql://{settings.database.postgres_user}:{settings.database.postgres_password}@{settings.database.postgres_host}:{settings.database.postgres_port}/{settings.database.postgres_db}"
    
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # 创建数据库会话
    db = SessionLocal()
    
    try:
        print("开始测试快速知识库管理器...")
        
        # 测试1: 创建管理器实例的时间
        start_time = time.time()
        manager = get_fast_knowledge_manager(db)
        init_time = time.time() - start_time
        print(f"✓ 管理器初始化时间: {init_time:.3f}s")
        
        # 测试2: 获取知识库列表的时间
        start_time = time.time()
        result = manager.list_knowledge_bases(page=1, page_size=10)
        list_time = time.time() - start_time
        print(f"✓ 列表查询时间: {list_time:.3f}s")
        print(f"✓ 查询结果: {result['success']}, 总数: {result.get('total', 0)}")
        
        # 测试3: 统计信息查询时间
        start_time = time.time()
        count = manager.count_knowledge_bases()
        count_time = time.time() - start_time
        print(f"✓ 统计查询时间: {count_time:.3f}s")
        print(f"✓ 知识库总数: {count}")
        
        # 测试4: 多次查询测试（缓存效果）
        print("\n测试多次查询性能:")
        times = []
        for i in range(5):
            start_time = time.time()
            result = manager.list_knowledge_bases(page=1, page_size=10)
            query_time = time.time() - start_time
            times.append(query_time)
            print(f"  第{i+1}次查询: {query_time:.3f}s")
        
        avg_time = sum(times) / len(times)
        print(f"✓ 平均查询时间: {avg_time:.3f}s")
        
        # 总结
        total_time = init_time + list_time + count_time + sum(times)
        print(f"\n性能测试总结:")
        print(f"• 初始化时间: {init_time:.3f}s")
        print(f"• 单次查询时间: {list_time:.3f}s") 
        print(f"• 平均查询时间: {avg_time:.3f}s")
        print(f"• 总测试时间: {total_time:.3f}s")
        
        if avg_time < 1.0:
            print("✓ 性能测试通过: 查询时间小于1秒")
            return True
        else:
            print("✗ 性能测试失败: 查询时间超过1秒")
            return False
            
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("FastKnowledgeManager 性能测试")
    print("=" * 50)
    
    success = test_fast_manager_performance()
    
    print("=" * 50)
    if success:
        print("测试完成: 快速管理器性能正常")
        sys.exit(0)
    else:
        print("测试失败: 快速管理器性能不达标")
        sys.exit(1)