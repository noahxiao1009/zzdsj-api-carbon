#!/usr/bin/env python3
"""
初始化切分策略模板数据
创建系统默认的切分策略模板
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import uuid
import json

from app.models.knowledge_models import ChunkingStrategy, Base
from app.schemas.chunking_strategy_schemas import ChunkerType, StrategyType

# 数据库配置
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://username:password@localhost/knowledge_service")

def create_system_templates():
    """创建系统切分策略模板"""
    
    templates = [
        # 基础Token切分模板
        {
            "name": "基础切分",
            "description": "适用于通用文档的标准切分策略，按固定大小进行分块",
            "strategy_type": StrategyType.SYSTEM.value,
            "chunker_type": ChunkerType.TOKEN_BASED.value,
            "parameters": {
                "chunk_size": 1000,
                "chunk_overlap": 200,
                "separator": "\n\n",
                "preserve_structure": False
            },
            "tags": ["通用", "基础"],
            "category": "general",
            "is_default": True,
            "is_active": True,
            "usage_count": 0,
            "success_rate": 0.95
        },
        
        # 长文档切分模板
        {
            "name": "长文档策略",
            "description": "适用于长文档的切分策略，增大分块尺寸以保持上下文连贯性",
            "strategy_type": StrategyType.SYSTEM.value,
            "chunker_type": ChunkerType.TOKEN_BASED.value,
            "parameters": {
                "chunk_size": 1500,
                "chunk_overlap": 300,
                "separator": "\n\n",
                "preserve_structure": True
            },
            "tags": ["长文档", "大分块"],
            "category": "long_document",
            "is_default": False,
            "is_active": True,
            "usage_count": 0,
            "success_rate": 0.92
        },
        
        # 代码文档切分模板  
        {
            "name": "代码文档策略",
            "description": "专门用于代码文档的切分策略，保持代码块的完整性",
            "strategy_type": StrategyType.SYSTEM.value,
            "chunker_type": ChunkerType.TOKEN_BASED.value,
            "parameters": {
                "chunk_size": 800,
                "chunk_overlap": 50,
                "separator": "\n```\n",
                "preserve_structure": True
            },
            "tags": ["代码", "技术文档"],
            "category": "code",
            "is_default": False,
            "is_active": True,
            "usage_count": 0,
            "success_rate": 0.88
        },
        
        # 语义切分模板
        {
            "name": "语义切分",
            "description": "基于语义边界进行智能切分，保持内容的语义完整性",
            "strategy_type": StrategyType.SYSTEM.value,
            "chunker_type": ChunkerType.SEMANTIC_BASED.value,
            "parameters": {
                "min_chunk_size": 200,
                "max_chunk_size": 800,
                "overlap_sentences": 1,
                "similarity_threshold": 0.8,
                "use_embeddings": True
            },
            "tags": ["语义", "智能"],
            "category": "academic",
            "is_default": True,
            "is_active": True,
            "usage_count": 0,
            "success_rate": 0.91
        },
        
        # 学术论文切分模板
        {
            "name": "学术论文策略",
            "description": "适用于学术论文的语义切分，保持逻辑结构完整",
            "strategy_type": StrategyType.SYSTEM.value,
            "chunker_type": ChunkerType.SEMANTIC_BASED.value,
            "parameters": {
                "min_chunk_size": 300,
                "max_chunk_size": 1200,
                "overlap_sentences": 2,
                "similarity_threshold": 0.85,
                "use_embeddings": True
            },
            "tags": ["学术", "论文", "研究"],
            "category": "academic",
            "is_default": False,
            "is_active": True,
            "usage_count": 0,
            "success_rate": 0.93
        },
        
        # 段落切分模板
        {
            "name": "段落切分",
            "description": "基于段落边界进行切分，适用于结构化文档",
            "strategy_type": StrategyType.SYSTEM.value,
            "chunker_type": ChunkerType.PARAGRAPH_BASED.value,
            "parameters": {
                "min_paragraph_length": 50,
                "max_paragraph_length": 2000,
                "merge_short_paragraphs": True,
                "paragraph_separator": "\n\n"
            },
            "tags": ["段落", "结构化"],
            "category": "general",
            "is_default": True,
            "is_active": True,
            "usage_count": 0,
            "success_rate": 0.89
        },
        
        # 新闻文章切分模板
        {
            "name": "新闻文章策略",
            "description": "适用于新闻文章的段落切分，保持新闻结构完整",
            "strategy_type": StrategyType.SYSTEM.value,
            "chunker_type": ChunkerType.PARAGRAPH_BASED.value,
            "parameters": {
                "min_paragraph_length": 30,
                "max_paragraph_length": 1500,
                "merge_short_paragraphs": True,
                "paragraph_separator": "\n\n"
            },
            "tags": ["新闻", "媒体"],
            "category": "news",
            "is_default": False,
            "is_active": True,
            "usage_count": 0,
            "success_rate": 0.87
        },
        
        # AI智能切分模板
        {
            "name": "智能切分",
            "description": "结合多种策略的智能切分，根据文档类型自动调整参数",
            "strategy_type": StrategyType.SYSTEM.value,
            "chunker_type": ChunkerType.AGENTIC_BASED.value,
            "parameters": {
                "context_window": 1200,
                "max_chunks_per_call": 10,
                "model_name": "gpt-3.5-turbo",
                "temperature": 0.1,
                "use_structured_output": True
            },
            "tags": ["智能", "自适应", "AI"],
            "category": "general",
            "is_default": True,
            "is_active": True,
            "usage_count": 0,
            "success_rate": 0.94
        },
        
        # 法律文档切分模板
        {
            "name": "法律文档策略",
            "description": "专用于法律文档的智能切分，保持条款和条文的完整性",
            "strategy_type": StrategyType.SYSTEM.value,
            "chunker_type": ChunkerType.AGENTIC_BASED.value,
            "parameters": {
                "context_window": 2000,
                "max_chunks_per_call": 8,
                "model_name": "gpt-4",
                "temperature": 0.05,
                "use_structured_output": True
            },
            "tags": ["法律", "条文", "专业"],
            "category": "legal",
            "is_default": False,
            "is_active": True,
            "usage_count": 0,
            "success_rate": 0.96
        },
        
        # 医疗文档切分模板
        {
            "name": "医疗文档策略", 
            "description": "专用于医疗文档的智能切分，保持医学概念的完整性",
            "strategy_type": StrategyType.SYSTEM.value,
            "chunker_type": ChunkerType.AGENTIC_BASED.value,
            "parameters": {
                "context_window": 1800,
                "max_chunks_per_call": 12,
                "model_name": "gpt-4",
                "temperature": 0.08,
                "use_structured_output": True
            },
            "tags": ["医疗", "医学", "专业"],
            "category": "medical",
            "is_default": False,
            "is_active": True,
            "usage_count": 0,
            "success_rate": 0.94
        }
    ]
    
    return templates

def init_database():
    """初始化数据库和表"""
    print("正在初始化数据库...")
    
    engine = create_engine(DATABASE_URL)
    
    # 创建所有表
    Base.metadata.create_all(bind=engine)
    print("数据库表创建完成")
    
    return engine

def insert_templates(engine):
    """插入模板数据"""
    print("正在插入切分策略模板...")
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        templates = create_system_templates()
        
        # 检查并插入模板
        inserted_count = 0
        for template_data in templates:
            # 检查是否已存在相同名称的策略
            existing = db.query(ChunkingStrategy).filter(
                ChunkingStrategy.name == template_data["name"]
            ).first()
            
            if existing:
                print(f"模板 '{template_data['name']}' 已存在，跳过")
                continue
            
            # 创建新的策略记录
            strategy = ChunkingStrategy(
                id=uuid.uuid4(),
                name=template_data["name"],
                description=template_data["description"],
                strategy_type=template_data["strategy_type"],
                chunker_type=template_data["chunker_type"],
                parameters=template_data["parameters"],
                tags=template_data["tags"],
                category=template_data["category"],
                usage_count=template_data["usage_count"],
                success_rate=template_data["success_rate"],
                avg_processing_time=0.0,
                is_active=template_data["is_active"],
                is_default=template_data["is_default"],
                created_by="system",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.add(strategy)
            inserted_count += 1
            print(f"已添加模板: {template_data['name']}")
        
        db.commit()
        print(f"成功插入 {inserted_count} 个切分策略模板")
        
    except Exception as e:
        db.rollback()
        print(f"插入模板时发生错误: {e}")
        raise
    finally:
        db.close()

def verify_templates(engine):
    """验证模板是否正确插入"""
    print("正在验证插入的模板...")
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # 查询所有系统模板
        system_templates = db.query(ChunkingStrategy).filter(
            ChunkingStrategy.strategy_type == StrategyType.SYSTEM.value
        ).all()
        
        print(f"\n=== 系统模板验证结果 ===")
        print(f"总计: {len(system_templates)} 个系统模板")
        
        # 按切分器类型分组统计
        type_stats = {}
        category_stats = {}
        
        for template in system_templates:
            # 统计切分器类型
            chunker_type = template.chunker_type
            type_stats[chunker_type] = type_stats.get(chunker_type, 0) + 1
            
            # 统计分类
            category = template.category
            category_stats[category] = category_stats.get(category, 0) + 1
            
            print(f"- {template.name} ({template.chunker_type}) - {template.category}")
        
        print(f"\n切分器类型分布:")
        for chunker_type, count in type_stats.items():
            print(f"  {chunker_type}: {count} 个")
        
        print(f"\n分类分布:")
        for category, count in category_stats.items():
            print(f"  {category}: {count} 个")
        
        # 检查默认策略
        default_templates = db.query(ChunkingStrategy).filter(
            ChunkingStrategy.strategy_type == StrategyType.SYSTEM.value,
            ChunkingStrategy.is_default == True
        ).all()
        
        print(f"\n默认策略:")
        for template in default_templates:
            print(f"  {template.name} ({template.chunker_type})")
            
    except Exception as e:
        print(f"验证模板时发生错误: {e}")
    finally:
        db.close()

def main():
    """主函数"""
    print("=== 切分策略模板初始化脚本 ===\n")
    
    try:
        # 初始化数据库
        engine = init_database()
        
        # 插入模板数据
        insert_templates(engine)
        
        # 验证插入结果
        verify_templates(engine)
        
        print(f"\n=== 初始化完成 ===")
        print("所有系统切分策略模板已成功创建！")
        
    except Exception as e:
        print(f"初始化过程中发生错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
