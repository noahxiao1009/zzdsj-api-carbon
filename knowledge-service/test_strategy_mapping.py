#!/usr/bin/env python3
"""
测试切分策略ID映射功能
"""

import sys
sys.path.append('/Users/wxn/Desktop/carbon/zzdsl-api-carbon/knowledge-service')

from app.core.splitter_strategy_manager import get_splitter_strategy_manager
from app.models.database import get_db

def test_strategy_mapping():
    """测试策略映射功能"""
    
    print("测试切分策略ID映射")
    print("=" * 40)
    
    # 获取策略管理器
    db = next(get_db())
    strategy_manager = get_splitter_strategy_manager(db)
    
    # 测试字符串ID
    test_ids = ["token_basic", "semantic_smart", "smart_adaptive"]
    
    for test_id in test_ids:
        print(f"\n测试ID: {test_id}")
        strategy = strategy_manager.get_strategy_by_id(test_id)
        
        if strategy:
            print(f"找到策略: {strategy['name']}")
            print(f"UUID: {strategy['id']}")
            print(f"配置: chunk_size={strategy['config'].get('chunk_size')}, "
                  f"overlap={strategy['config'].get('chunk_overlap')}")
        else:
            print("策略未找到")
    
    # 测试直接UUID
    print(f"\n测试直接UUID查找:")
    uuid_id = "a595ae7d-3494-4da4-be3a-b5d775131b08"
    strategy = strategy_manager.get_strategy_by_id(uuid_id)
    if strategy:
        print(f"找到策略: {strategy['name']}")
    else:
        print("UUID策略未找到")
    
    db.close()

if __name__ == "__main__":
    test_strategy_mapping()