"""
切分策略管理器
负责管理文档切分策略的CRUD操作和应用
"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func

from app.models.splitter_strategy import SplitterStrategy, SplitterStrategyUsage
from app.models.database import get_db

logger = logging.getLogger(__name__)

# 字符串ID到UUID的映射（从初始化脚本获得）
STRATEGY_ID_MAPPING = {
    "token_basic": "a595ae7d-3494-4da4-be3a-b5d775131b08",
    "semantic_smart": "f21f12a2-972f-4109-bf66-c411321a62af",
    "smart_adaptive": "dafc5759-0ffa-4d7f-813d-118b54170636",
}


class SplitterStrategyManager:
    """切分策略管理器"""
    
    def __init__(self, db: Session = None):
        if db:
            self.db = db
        else:
            # 创建新的数据库连接
            self.db = next(get_db())
    
    def get_all_strategies(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """获取所有切分策略"""
        try:
            query = self.db.query(SplitterStrategy)
            
            if not include_inactive:
                query = query.filter(SplitterStrategy.is_active == True)
            
            strategies = query.order_by(
                desc(SplitterStrategy.is_system),  # 系统策略排在前面
                SplitterStrategy.name
            ).all()
            
            return [strategy.to_dict() for strategy in strategies]
            
        except Exception as e:
            logger.error(f"获取切分策略列表失败: {e}")
            return []
    
    def get_strategy_by_id(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取切分策略（支持字符串ID映射）"""
        try:
            # 如果是字符串ID，先查找映射
            actual_id = strategy_id
            if strategy_id in STRATEGY_ID_MAPPING:
                actual_id = STRATEGY_ID_MAPPING[strategy_id]
                logger.info(f"使用映射: {strategy_id} -> {actual_id}")
            
            strategy = self.db.query(SplitterStrategy).filter(
                SplitterStrategy.id == actual_id
            ).first()
            
            return strategy.to_dict() if strategy else None
            
        except Exception as e:
            logger.error(f"获取切分策略失败 (ID: {strategy_id}): {e}")
            return None
    
    def get_strategy_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """根据名称获取切分策略"""
        try:
            strategy = self.db.query(SplitterStrategy).filter(
                SplitterStrategy.name == name,
                SplitterStrategy.is_active == True
            ).first()
            
            return strategy.to_dict() if strategy else None
            
        except Exception as e:
            logger.error(f"获取切分策略失败 (Name: {name}): {e}")
            return None
    
    def get_system_strategies(self) -> List[Dict[str, Any]]:
        """获取系统预设策略"""
        try:
            strategies = self.db.query(SplitterStrategy).filter(
                SplitterStrategy.is_system == True,
                SplitterStrategy.is_active == True
            ).order_by(SplitterStrategy.name).all()
            
            return [strategy.to_dict() for strategy in strategies]
            
        except Exception as e:
            logger.error(f"获取系统预设策略失败: {e}")
            return []
    
    def create_strategy(
        self, 
        name: str, 
        description: str, 
        config: Dict[str, Any],
        is_system: bool = False,
        created_by: str = "system"
    ) -> Optional[Dict[str, Any]]:
        """创建新的切分策略"""
        try:
            # 检查名称是否已存在
            existing = self.db.query(SplitterStrategy).filter(
                SplitterStrategy.name == name
            ).first()
            
            if existing:
                logger.warning(f"切分策略名称已存在: {name}")
                return None
            
            # 验证配置格式
            if not self._validate_config(config):
                logger.error(f"切分策略配置格式无效: {config}")
                return None
            
            # 创建新策略
            strategy = SplitterStrategy(
                name=name,
                description=description,
                config=config,
                is_system=is_system,
                created_by=created_by
            )
            
            self.db.add(strategy)
            self.db.commit()
            self.db.refresh(strategy)
            
            logger.info(f"成功创建切分策略: {name}")
            return strategy.to_dict()
            
        except Exception as e:
            logger.error(f"创建切分策略失败: {e}")
            self.db.rollback()
            return None
    
    def update_strategy(
        self, 
        strategy_id: str, 
        name: str = None,
        description: str = None,
        config: Dict[str, Any] = None,
        is_active: bool = None
    ) -> Optional[Dict[str, Any]]:
        """更新切分策略"""
        try:
            strategy = self.db.query(SplitterStrategy).filter(
                SplitterStrategy.id == strategy_id
            ).first()
            
            if not strategy:
                logger.warning(f"切分策略不存在: {strategy_id}")
                return None
            
            # 系统策略只能修改激活状态和描述
            if strategy.is_system:
                if name or config:
                    logger.warning(f"系统策略不允许修改名称和配置: {strategy_id}")
                    return None
            
            # 更新字段
            if name and not strategy.is_system:
                # 检查名称冲突
                existing = self.db.query(SplitterStrategy).filter(
                    SplitterStrategy.name == name,
                    SplitterStrategy.id != strategy_id
                ).first()
                if existing:
                    logger.warning(f"策略名称已存在: {name}")
                    return None
                strategy.name = name
            
            if description:
                strategy.description = description
            
            if config and not strategy.is_system:
                if not self._validate_config(config):
                    logger.error(f"配置格式无效: {config}")
                    return None
                strategy.config = config
            
            if is_active is not None:
                strategy.is_active = is_active
            
            self.db.commit()
            self.db.refresh(strategy)
            
            logger.info(f"成功更新切分策略: {strategy_id}")
            return strategy.to_dict()
            
        except Exception as e:
            logger.error(f"更新切分策略失败: {e}")
            self.db.rollback()
            return None
    
    def delete_strategy(self, strategy_id: str) -> bool:
        """删除切分策略（只能删除非系统策略）"""
        try:
            strategy = self.db.query(SplitterStrategy).filter(
                SplitterStrategy.id == strategy_id
            ).first()
            
            if not strategy:
                logger.warning(f"切分策略不存在: {strategy_id}")
                return False
            
            if strategy.is_system:
                logger.warning(f"不能删除系统预设策略: {strategy_id}")
                return False
            
            # 检查是否有知识库在使用该策略
            from app.models.knowledge_base import KnowledgeBase
            kb_count = self.db.query(KnowledgeBase).filter(
                KnowledgeBase.default_splitter_strategy_id == strategy_id
            ).count()
            
            if kb_count > 0:
                logger.warning(f"策略正在被 {kb_count} 个知识库使用，不能删除: {strategy_id}")
                return False
            
            # 删除使用统计记录
            self.db.query(SplitterStrategyUsage).filter(
                SplitterStrategyUsage.strategy_id == strategy_id
            ).delete()
            
            # 删除策略
            self.db.delete(strategy)
            self.db.commit()
            
            logger.info(f"成功删除切分策略: {strategy_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除切分策略失败: {e}")
            self.db.rollback()
            return False
    
    def get_strategy_usage_stats(self, strategy_id: str) -> Dict[str, Any]:
        """获取策略使用统计"""
        try:
            usage_records = self.db.query(SplitterStrategyUsage).filter(
                SplitterStrategyUsage.strategy_id == strategy_id
            ).all()
            
            if not usage_records:
                return {
                    "total_usage": 0,
                    "knowledge_bases_count": 0,
                    "last_used_at": None,
                    "usage_details": []
                }
            
            total_usage = sum(record.usage_count for record in usage_records)
            knowledge_bases_count = len(usage_records)
            last_used_at = max(record.last_used_at for record in usage_records)
            
            usage_details = [record.to_dict() for record in usage_records]
            
            return {
                "total_usage": total_usage,
                "knowledge_bases_count": knowledge_bases_count,
                "last_used_at": last_used_at.isoformat() if last_used_at else None,
                "usage_details": usage_details
            }
            
        except Exception as e:
            logger.error(f"获取策略使用统计失败: {e}")
            return {
                "total_usage": 0,
                "knowledge_bases_count": 0,
                "last_used_at": None,
                "usage_details": []
            }
    
    def record_strategy_usage(self, strategy_id: str, kb_id: str) -> bool:
        """记录策略使用（支持字符串ID映射）"""
        try:
            import uuid
            
            # 如果是字符串ID，先查找映射
            actual_strategy_id = strategy_id
            if strategy_id in STRATEGY_ID_MAPPING:
                actual_strategy_id = STRATEGY_ID_MAPPING[strategy_id]
                logger.info(f"记录使用映射: {strategy_id} -> {actual_strategy_id}")
            
            # 将策略ID转换为UUID
            try:
                strategy_uuid = uuid.UUID(actual_strategy_id)
            except ValueError as e:
                logger.error(f"策略ID格式错误: {e}")
                return False
            
            # 查找或创建使用记录
            usage = self.db.query(SplitterStrategyUsage).filter(
                SplitterStrategyUsage.strategy_id == strategy_uuid,
                SplitterStrategyUsage.kb_id == kb_id
            ).first()
            
            if usage:
                usage.usage_count += 1
                usage.last_used_at = datetime.now()
            else:
                usage = SplitterStrategyUsage(
                    strategy_id=strategy_uuid,
                    kb_id=kb_id,
                    usage_count=1
                )
                self.db.add(usage)
            
            self.db.commit()
            return True
            
        except Exception as e:
            logger.error(f"记录策略使用失败: {e}")
            self.db.rollback()
            return False
    
    def get_recommended_strategy(self, file_type: str, file_size: int) -> Dict[str, Any]:
        """根据文件类型和大小推荐策略"""
        try:
            # 推荐逻辑
            if file_type.lower() in ['.py', '.js', '.java', '.cpp', '.c', '.go', '.rs']:
                # 代码文件
                strategy_name = "code_chunking"
            elif file_size > 5 * 1024 * 1024:  # 大于5MB
                # 大文档
                strategy_name = "large_document"
            elif file_type.lower() in ['.md', '.txt', '.rtf']:
                # 文本文档，使用语义切分
                strategy_name = "semantic_chunking"
            else:
                # 默认使用智能切分
                strategy_name = "smart_chunking"
            
            strategy = self.get_strategy_by_name(strategy_name)
            if strategy:
                return strategy
            
            # 如果推荐策略不存在，返回基础策略
            return self.get_strategy_by_name("basic_chunking") or {
                "id": None,
                "name": "basic_chunking",
                "config": SplitterStrategy.get_default_config("basic")
            }
            
        except Exception as e:
            logger.error(f"获取推荐策略失败: {e}")
            return {
                "id": None,
                "name": "basic_chunking", 
                "config": SplitterStrategy.get_default_config("basic")
            }
    
    def _validate_config(self, config: Dict[str, Any]) -> bool:
        """验证切分策略配置格式"""
        try:
            required_fields = ["chunk_size", "chunk_overlap", "chunk_strategy"]
            
            # 检查必需字段
            for field in required_fields:
                if field not in config:
                    logger.error(f"配置缺少必需字段: {field}")
                    return False
            
            # 检查数值范围
            chunk_size = config.get("chunk_size", 0)
            chunk_overlap = config.get("chunk_overlap", 0)
            
            if not isinstance(chunk_size, int) or chunk_size <= 0:
                logger.error(f"chunk_size必须是正整数: {chunk_size}")
                return False
            
            if not isinstance(chunk_overlap, int) or chunk_overlap < 0:
                logger.error(f"chunk_overlap必须是非负整数: {chunk_overlap}")
                return False
            
            if chunk_overlap >= chunk_size:
                logger.error(f"chunk_overlap不能大于等于chunk_size")
                return False
            
            # 检查策略类型
            valid_strategies = ["basic", "semantic", "smart", "code", "hierarchical"]
            if config.get("chunk_strategy") not in valid_strategies:
                logger.error(f"无效的chunk_strategy: {config.get('chunk_strategy')}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"验证配置格式失败: {e}")
            return False


# 全局实例
_strategy_manager = None

def get_splitter_strategy_manager(db: Session = None) -> SplitterStrategyManager:
    """获取切分策略管理器实例"""
    global _strategy_manager
    if _strategy_manager is None or db is not None:
        _strategy_manager = SplitterStrategyManager(db)
    return _strategy_manager