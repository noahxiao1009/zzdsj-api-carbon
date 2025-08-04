#!/usr/bin/env python3
"""
初始化预定义切分策略
创建系统内置的切分策略，并建立字符串ID到UUID的映射
"""

import sys
import uuid
from sqlalchemy.orm import Session

# 添加项目路径
sys.path.append('/Users/wxn/Desktop/carbon/zzdsl-api-carbon/knowledge-service')

from app.models.database import get_db
from app.models.splitter_strategy import SplitterStrategy

# 预定义策略配置
PREDEFINED_STRATEGIES = {
    "token_basic": {
        "name": "基础Token分块",
        "description": "基于Token数量进行固定大小分块，速度快，适合通用文档",
        "config": {
            "chunk_size": 1000,
            "chunk_overlap": 200,
            "chunk_strategy": "token_based",
            "preserve_structure": True,
            "separators": ["\n\n", "\n", " ", ""],
            "length_function": "len"
        }
    },
    "semantic_smart": {
        "name": "语义分块",
        "description": "基于语义相似度进行智能分块，保持内容连贯性",
        "config": {
            "chunk_size": 800,
            "chunk_overlap": 150,
            "chunk_strategy": "semantic",
            "preserve_structure": True,
            "use_semantic_splitter": True,
            "embedding_model": "text-embedding-ada-002",
            "similarity_threshold": 0.7
        }
    },
    "smart_adaptive": {
        "name": "智能自适应",
        "description": "结合文档结构和语义，自动选择最佳分块策略",
        "config": {
            "chunk_size": 1200,
            "chunk_overlap": 250,
            "chunk_strategy": "smart",
            "preserve_structure": True,
            "detect_headers": True,
            "detect_paragraphs": True,
            "detect_lists": True,
            "min_chunk_size": 300,
            "max_chunk_size": 3000
        }
    }
}

def init_predefined_strategies():
    """初始化预定义策略"""
    
    print("正在初始化预定义切分策略...")
    
    db = next(get_db())
    
    try:
        strategy_mapping = {}
        
        for strategy_key, strategy_data in PREDEFINED_STRATEGIES.items():
            # 检查策略是否已存在
            existing_strategy = db.query(SplitterStrategy).filter(
                SplitterStrategy.name == strategy_data["name"]
            ).first()
            
            if existing_strategy:
                print(f"策略 '{strategy_data['name']}' 已存在，跳过创建")
                strategy_mapping[strategy_key] = str(existing_strategy.id)
                continue
            
            # 创建新策略
            new_strategy = SplitterStrategy(
                name=strategy_data["name"],
                description=strategy_data["description"],
                config=strategy_data["config"],
                is_system=True,  # 标记为系统策略
                is_active=True,
                created_by="system"
            )
            
            db.add(new_strategy)
            db.flush()  # 获取生成的ID
            
            strategy_mapping[strategy_key] = str(new_strategy.id)
            print(f"创建策略: {strategy_data['name']} -> {new_strategy.id}")
        
        db.commit()
        
        # 输出映射关系
        print("\n策略ID映射关系:")
        print("=" * 50)
        for key, uuid_id in strategy_mapping.items():
            print(f"{key:15} -> {uuid_id}")
        
        # 生成映射代码
        print("\n用于代码的策略映射:")
        print("=" * 50)
        print("STRATEGY_ID_MAPPING = {")
        for key, uuid_id in strategy_mapping.items():
            print(f'    "{key}": "{uuid_id}",')
        print("}")
        
        return strategy_mapping
        
    except Exception as e:
        db.rollback()
        print(f"初始化策略失败: {e}")
        raise
    finally:
        db.close()

def verify_strategies():
    """验证策略创建结果"""
    
    print("\n验证策略创建结果...")
    
    db = next(get_db())
    
    try:
        strategies = db.query(SplitterStrategy).filter(
            SplitterStrategy.is_system == True
        ).all()
        
        print(f"找到 {len(strategies)} 个系统策略:")
        for strategy in strategies:
            print(f"- {strategy.name} ({strategy.id})")
            print(f"  配置: chunk_size={strategy.config.get('chunk_size')}, "
                  f"overlap={strategy.config.get('chunk_overlap')}")
        
    except Exception as e:
        print(f"验证失败: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    print("切分策略初始化工具")
    print("=" * 50)
    
    try:
        # 初始化策略
        mapping = init_predefined_strategies()
        
        # 验证结果
        verify_strategies()
        
        print("\n初始化完成！")
        
    except Exception as e:
        print(f"\n初始化失败: {e}")
        sys.exit(1)