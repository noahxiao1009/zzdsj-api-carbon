"""
切分策略数据库操作仓储
处理切分策略的数据库CRUD操作
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.models.knowledge_models import ChunkingStrategy
from app.schemas.chunking_strategy_schemas import (
    ChunkingStrategyCreate,
    ChunkingStrategyUpdate,
    StrategyType,
    ChunkerType
)


class ChunkingStrategyRepository:
    """切分策略数据仓储"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, strategy_data: ChunkingStrategyCreate, created_by: Optional[str] = None) -> ChunkingStrategy:
        """创建新的切分策略"""
        # 如果设为默认策略，需要先取消其他默认策略
        if strategy_data.is_default:
            self.db.query(ChunkingStrategy).filter(
                ChunkingStrategy.is_default == True,
                ChunkingStrategy.chunker_type == strategy_data.chunker_type.value
            ).update({"is_default": False})
        
        strategy = ChunkingStrategy(
            name=strategy_data.name,
            description=strategy_data.description,
            strategy_type=StrategyType.CUSTOM.value,
            chunker_type=strategy_data.chunker_type.value,
            parameters=strategy_data.parameters,
            tags=strategy_data.tags,
            category=strategy_data.category.value,
            is_default=strategy_data.is_default,
            created_by=created_by
        )
        
        self.db.add(strategy)
        self.db.commit()
        self.db.refresh(strategy)
        return strategy
    
    def get_by_id(self, strategy_id: UUID) -> Optional[ChunkingStrategy]:
        """根据ID获取切分策略"""
        return self.db.query(ChunkingStrategy).filter(
            ChunkingStrategy.id == strategy_id
        ).first()
    
    def get_by_name(self, name: str) -> Optional[ChunkingStrategy]:
        """根据名称获取切分策略"""
        return self.db.query(ChunkingStrategy).filter(
            ChunkingStrategy.name == name
        ).first()
    
    def list_strategies(
        self,
        page: int = 1,
        page_size: int = 10,
        strategy_type: Optional[StrategyType] = None,
        chunker_type: Optional[ChunkerType] = None,
        category: Optional[str] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """分页查询切分策略"""
        query = self.db.query(ChunkingStrategy)
        
        # 应用筛选条件
        if strategy_type:
            query = query.filter(ChunkingStrategy.strategy_type == strategy_type.value)
        if chunker_type:
            query = query.filter(ChunkingStrategy.chunker_type == chunker_type.value)
        if category:
            query = query.filter(ChunkingStrategy.category == category)
        if is_active is not None:
            query = query.filter(ChunkingStrategy.is_active == is_active)
        if search:
            query = query.filter(
                (ChunkingStrategy.name.ilike(f"%{search}%")) |
                (ChunkingStrategy.description.ilike(f"%{search}%"))
            )
        
        # 按使用次数排序
        query = query.order_by(desc(ChunkingStrategy.usage_count), ChunkingStrategy.created_at)
        
        total = query.count()
        strategies = query.offset((page - 1) * page_size).limit(page_size).all()
        
        return {
            "strategies": strategies,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }
    
    def update(self, strategy_id: UUID, update_data: ChunkingStrategyUpdate) -> Optional[ChunkingStrategy]:
        """更新切分策略"""
        strategy = self.get_by_id(strategy_id)
        if not strategy:
            return None
        
        # 如果设为默认策略，需要先取消其他默认策略
        if update_data.is_default and not strategy.is_default:
            self.db.query(ChunkingStrategy).filter(
                ChunkingStrategy.is_default == True,
                ChunkingStrategy.chunker_type == strategy.chunker_type,
                ChunkingStrategy.id != strategy_id
            ).update({"is_default": False})
        
        # 更新字段
        update_dict = update_data.dict(exclude_unset=True)
        if "category" in update_dict and update_dict["category"]:
            update_dict["category"] = update_dict["category"].value
        
        for key, value in update_dict.items():
            setattr(strategy, key, value)
        
        self.db.commit()
        self.db.refresh(strategy)
        return strategy
    
    def delete(self, strategy_id: UUID) -> bool:
        """删除切分策略"""
        strategy = self.get_by_id(strategy_id)
        if not strategy:
            return False
        
        # 系统策略不能删除
        if strategy.strategy_type == StrategyType.SYSTEM.value:
            return False
        
        self.db.delete(strategy)
        self.db.commit()
        return True
    
    def get_default_strategy(self, chunker_type: ChunkerType) -> Optional[ChunkingStrategy]:
        """获取指定类型的默认策略"""
        return self.db.query(ChunkingStrategy).filter(
            ChunkingStrategy.chunker_type == chunker_type.value,
            ChunkingStrategy.is_default == True,
            ChunkingStrategy.is_active == True
        ).first()
    
    def increment_usage(self, strategy_id: UUID, processing_time: float, success: bool) -> bool:
        """更新策略使用统计"""
        strategy = self.get_by_id(strategy_id)
        if not strategy:
            return False
        
        # 更新使用计数
        strategy.usage_count += 1
        
        # 更新成功率
        if strategy.usage_count == 1:
            strategy.success_rate = 1.0 if success else 0.0
        else:
            old_success_count = int(strategy.success_rate * (strategy.usage_count - 1))
            new_success_count = old_success_count + (1 if success else 0)
            strategy.success_rate = new_success_count / strategy.usage_count
        
        # 更新平均处理时间
        if strategy.usage_count == 1:
            strategy.avg_processing_time = processing_time
        else:
            old_total_time = strategy.avg_processing_time * (strategy.usage_count - 1)
            strategy.avg_processing_time = (old_total_time + processing_time) / strategy.usage_count
        
        self.db.commit()
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取切分策略统计信息"""
        stats = {}
        
        # 基础统计
        stats["total_strategies"] = self.db.query(ChunkingStrategy).count()
        stats["active_strategies"] = self.db.query(ChunkingStrategy).filter(
            ChunkingStrategy.is_active == True
        ).count()
        stats["system_strategies"] = self.db.query(ChunkingStrategy).filter(
            ChunkingStrategy.strategy_type == StrategyType.SYSTEM.value
        ).count()
        stats["custom_strategies"] = self.db.query(ChunkingStrategy).filter(
            ChunkingStrategy.strategy_type == StrategyType.CUSTOM.value
        ).count()
        
        # 切分器类型分布
        chunker_types = [ChunkerType.TOKEN_BASED, ChunkerType.SEMANTIC_BASED, 
                        ChunkerType.PARAGRAPH_BASED, ChunkerType.AGENTIC_BASED]
        stats["chunker_type_distribution"] = {}
        for chunker_type in chunker_types:
            count = self.db.query(ChunkingStrategy).filter(
                ChunkingStrategy.chunker_type == chunker_type.value
            ).count()
            stats["chunker_type_distribution"][chunker_type.value] = count
        
        # 分类分布
        category_query = self.db.query(
            ChunkingStrategy.category,
            func.count(ChunkingStrategy.id)
        ).group_by(ChunkingStrategy.category).all()
        stats["category_distribution"] = dict(category_query)
        
        # 最常用策略
        most_used = self.db.query(ChunkingStrategy).filter(
            ChunkingStrategy.usage_count > 0
        ).order_by(desc(ChunkingStrategy.usage_count)).first()
        stats["most_used_strategy"] = most_used
        
        # 平均成功率
        avg_success_rate = self.db.query(func.avg(ChunkingStrategy.success_rate)).filter(
            ChunkingStrategy.success_rate.isnot(None)
        ).scalar()
        stats["avg_success_rate"] = float(avg_success_rate) if avg_success_rate else 0.0
        
        return stats
    
    def get_system_templates(self) -> List[ChunkingStrategy]:
        """获取系统模板策略"""
        return self.db.query(ChunkingStrategy).filter(
            ChunkingStrategy.strategy_type == StrategyType.SYSTEM.value,
            ChunkingStrategy.is_active == True
        ).order_by(ChunkingStrategy.chunker_type, ChunkingStrategy.name).all()
    
    def create_system_templates(self) -> None:
        """创建系统默认模板（在数据库初始化时调用）"""
        templates = [
            {
                "name": "基础切分",
                "description": "适用于通用文档的标准切分策略，按固定大小进行分块",
                "chunker_type": ChunkerType.TOKEN_BASED.value,
                "parameters": {
                    "chunk_size": 1000,
                    "chunk_overlap": 200,
                    "separator": "\n\n",
                    "preserve_structure": False
                },
                "tags": ["通用", "基础"],
                "category": "general",
                "is_default": True
            },
            {
                "name": "语义切分",
                "description": "基于语义边界进行智能切分，保持内容的语义完整性",
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
                "is_default": True
            },
            {
                "name": "智能切分",
                "description": "结合多种策略的智能切分，根据文档类型自动调整参数",
                "chunker_type": ChunkerType.AGENTIC_BASED.value,
                "parameters": {
                    "context_window": 1200,
                    "max_chunks_per_call": 10,
                    "model_name": "gpt-3.5-turbo",
                    "temperature": 0.1,
                    "use_structured_output": True
                },
                "tags": ["智能", "自适应"],
                "category": "general",
                "is_default": True
            }
        ]
        
        for template_data in templates:
            # 检查是否已存在
            existing = self.get_by_name(template_data["name"])
            if not existing:
                strategy = ChunkingStrategy(
                    name=template_data["name"],
                    description=template_data["description"],
                    strategy_type=StrategyType.SYSTEM.value,
                    chunker_type=template_data["chunker_type"],
                    parameters=template_data["parameters"],
                    tags=template_data["tags"],
                    category=template_data["category"],
                    is_default=template_data["is_default"],
                    usage_count=0,
                    success_rate=0.95  # 系统模板的初始成功率
                )
                self.db.add(strategy)
        
        self.db.commit()


def get_chunking_strategy_repository(db: Session) -> ChunkingStrategyRepository:
    """获取切分策略仓储实例"""
    return ChunkingStrategyRepository(db)
