"""
知识库配置管理API路由
提供知识库级别的配置管理，包括默认切分策略设置
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Path
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.knowledge_models import KnowledgeBase
from app.core.splitter_strategy_manager import get_splitter_strategy_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge-bases", tags=["知识库配置管理"])


# ===========================
# 请求和响应模型
# ===========================

class DefaultSplitterConfigRequest(BaseModel):
    """默认切分策略配置请求模型"""
    strategy_id: Optional[str] = Field(None, description="策略ID（null表示使用自定义配置）")
    custom_config: Optional[Dict[str, Any]] = Field(None, description="自定义切分配置")

class KnowledgeBaseConfigUpdate(BaseModel):
    """知识库配置更新请求模型"""
    default_splitter_strategy_id: Optional[str] = Field(None, description="默认切分策略ID")
    default_splitter_config: Optional[Dict[str, Any]] = Field(None, description="默认切分配置")
    chunk_size: Optional[int] = Field(None, ge=100, le=10000, description="分块大小")
    chunk_overlap: Optional[int] = Field(None, ge=0, le=1000, description="分块重叠")
    chunk_strategy: Optional[str] = Field(None, description="分块策略")
    similarity_threshold: Optional[float] = Field(None, ge=0.0, le=1.0, description="相似度阈值")
    enable_hybrid_search: Optional[bool] = Field(None, description="启用混合搜索")
    enable_agno_integration: Optional[bool] = Field(None, description="启用Agno集成")


# ===========================
# API路由
# ===========================

@router.get("/{kb_id}/config",
            response_model=Dict[str, Any],
            summary="获取知识库配置",
            description="获取知识库的完整配置信息，包括默认切分策略")
async def get_knowledge_base_config(
    kb_id: str = Path(..., description="知识库ID"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """获取知识库配置"""
    try:
        # 获取知识库
        kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
        if not kb:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "KNOWLEDGE_BASE_NOT_FOUND",
                    "message": f"知识库不存在: {kb_id}"
                }
            )
        
        # 获取关联的切分策略信息
        strategy_info = None
        if kb.default_splitter_strategy_id:
            strategy_manager = get_splitter_strategy_manager(db)
            strategy = strategy_manager.get_strategy_by_id(str(kb.default_splitter_strategy_id))
            if strategy:
                strategy_info = strategy
        
        # 获取有效的切分配置
        effective_config = kb.get_effective_splitter_config()
        
        return {
            "success": True,
            "message": "成功获取知识库配置",
            "data": {
                "knowledge_base": kb.to_dict(),
                "default_splitter_strategy": strategy_info,
                "effective_splitter_config": effective_config,
                "config_source": _get_config_source(kb)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取知识库配置失败: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "GET_CONFIG_ERROR",
                "message": "获取知识库配置失败"
            }
        )


@router.put("/{kb_id}/config",
            response_model=Dict[str, Any],
            summary="更新知识库配置",
            description="更新知识库的配置信息")
async def update_knowledge_base_config(
    request: KnowledgeBaseConfigUpdate,
    kb_id: str = Path(..., description="知识库ID"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """更新知识库配置"""
    try:
        # 获取知识库
        kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
        if not kb:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "KNOWLEDGE_BASE_NOT_FOUND",
                    "message": f"知识库不存在: {kb_id}"
                }
            )
        
        # 验证切分策略ID
        if request.default_splitter_strategy_id:
            strategy_manager = get_splitter_strategy_manager(db)
            strategy = strategy_manager.get_strategy_by_id(request.default_splitter_strategy_id)
            if not strategy:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "STRATEGY_NOT_FOUND",
                        "message": f"切分策略不存在: {request.default_splitter_strategy_id}"
                    }
                )
        
        # 更新字段
        updated_fields = []
        
        if request.default_splitter_strategy_id is not None:
            kb.default_splitter_strategy_id = request.default_splitter_strategy_id
            updated_fields.append("default_splitter_strategy_id")
        
        if request.default_splitter_config is not None:
            # 验证配置格式
            if request.default_splitter_config:
                from app.core.splitter_strategy_manager import SplitterStrategyManager
                manager = SplitterStrategyManager(db)
                if not manager._validate_config(request.default_splitter_config):
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "error": "INVALID_CONFIG",
                            "message": "切分配置格式无效"
                        }
                    )
            kb.default_splitter_config = request.default_splitter_config
            updated_fields.append("default_splitter_config")
        
        # 更新其他基础配置
        if request.chunk_size is not None:
            kb.chunk_size = request.chunk_size
            updated_fields.append("chunk_size")
        
        if request.chunk_overlap is not None:
            kb.chunk_overlap = request.chunk_overlap
            updated_fields.append("chunk_overlap")
        
        if request.chunk_strategy is not None:
            kb.chunk_strategy = request.chunk_strategy
            updated_fields.append("chunk_strategy")
        
        if request.similarity_threshold is not None:
            kb.similarity_threshold = request.similarity_threshold
            updated_fields.append("similarity_threshold")
        
        if request.enable_hybrid_search is not None:
            kb.enable_hybrid_search = request.enable_hybrid_search
            updated_fields.append("enable_hybrid_search")
        
        if request.enable_agno_integration is not None:
            kb.enable_agno_integration = request.enable_agno_integration
            updated_fields.append("enable_agno_integration")
        
        # 提交更改
        db.commit()
        db.refresh(kb)
        
        # 记录策略使用（如果切换了策略）
        if request.default_splitter_strategy_id and "default_splitter_strategy_id" in updated_fields:
            strategy_manager = get_splitter_strategy_manager(db)
            strategy_manager.record_strategy_usage(request.default_splitter_strategy_id, kb_id)
        
        return {
            "success": True,
            "message": f"成功更新知识库配置，更新了 {len(updated_fields)} 个字段",
            "data": {
                "knowledge_base": kb.to_dict(),
                "updated_fields": updated_fields,
                "effective_splitter_config": kb.get_effective_splitter_config()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新知识库配置失败: {e}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail={
                "error": "UPDATE_CONFIG_ERROR",
                "message": "更新知识库配置失败"
            }
        )


@router.put("/{kb_id}/default-splitter",
            response_model=Dict[str, Any],
            summary="设置默认切分策略",
            description="为知识库设置默认切分策略")
async def set_default_splitter_strategy(
    request: DefaultSplitterConfigRequest,
    kb_id: str = Path(..., description="知识库ID"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """设置默认切分策略"""
    try:
        # 获取知识库
        kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
        if not kb:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "KNOWLEDGE_BASE_NOT_FOUND",
                    "message": f"知识库不存在: {kb_id}"
                }
            )
        
        strategy_manager = get_splitter_strategy_manager(db)
        
        # 如果指定了策略ID，验证策略是否存在
        if request.strategy_id:
            strategy = strategy_manager.get_strategy_by_id(request.strategy_id)
            if not strategy:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "STRATEGY_NOT_FOUND",
                        "message": f"切分策略不存在: {request.strategy_id}"
                    }
                )
            
            # 设置策略ID，清空自定义配置
            kb.default_splitter_strategy_id = request.strategy_id
            kb.default_splitter_config = None
            
            # 记录策略使用
            strategy_manager.record_strategy_usage(request.strategy_id, kb_id)
            
            config_source = f"strategy: {strategy['name']}"
            
        elif request.custom_config:
            # 验证自定义配置
            if not strategy_manager._validate_config(request.custom_config):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "INVALID_CONFIG",
                        "message": "切分配置格式无效"
                    }
                )
            
            # 设置自定义配置，清空策略ID
            kb.default_splitter_strategy_id = None
            kb.default_splitter_config = request.custom_config
            
            config_source = "custom_config"
            
        else:
            # 清空配置，使用系统默认
            kb.default_splitter_strategy_id = None
            kb.default_splitter_config = None
            
            config_source = "system_default"
        
        # 提交更改
        db.commit()
        db.refresh(kb)
        
        return {
            "success": True,
            "message": f"成功设置默认切分策略: {config_source}",
            "data": {
                "knowledge_base_id": kb_id,
                "default_splitter_strategy_id": str(kb.default_splitter_strategy_id) if kb.default_splitter_strategy_id else None,
                "default_splitter_config": kb.default_splitter_config,
                "effective_splitter_config": kb.get_effective_splitter_config(),
                "config_source": _get_config_source(kb)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"设置默认切分策略失败: {e}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail={
                "error": "SET_DEFAULT_SPLITTER_ERROR",
                "message": "设置默认切分策略失败"
            }
        )


@router.get("/{kb_id}/default-splitter",
            response_model=Dict[str, Any],
            summary="获取默认切分策略",
            description="获取知识库的默认切分策略配置")
async def get_default_splitter_strategy(
    kb_id: str = Path(..., description="知识库ID"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """获取默认切分策略"""
    try:
        # 获取知识库
        kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
        if not kb:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "KNOWLEDGE_BASE_NOT_FOUND",
                    "message": f"知识库不存在: {kb_id}"
                }
            )
        
        # 获取策略信息
        strategy_info = None
        if kb.default_splitter_strategy_id:
            strategy_manager = get_splitter_strategy_manager(db)
            strategy = strategy_manager.get_strategy_by_id(str(kb.default_splitter_strategy_id))
            if strategy:
                strategy_info = strategy
        
        return {
            "success": True,
            "message": "成功获取默认切分策略",
            "data": {
                "knowledge_base_id": kb_id,
                "default_splitter_strategy_id": str(kb.default_splitter_strategy_id) if kb.default_splitter_strategy_id else None,
                "default_splitter_strategy": strategy_info,
                "default_splitter_config": kb.default_splitter_config,
                "effective_splitter_config": kb.get_effective_splitter_config(),
                "config_source": _get_config_source(kb)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取默认切分策略失败: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "GET_DEFAULT_SPLITTER_ERROR",
                "message": "获取默认切分策略失败"
            }
        )


@router.delete("/{kb_id}/default-splitter",
               response_model=Dict[str, Any],
               summary="清除默认切分策略",
               description="清除知识库的默认切分策略配置，恢复系统默认")
async def clear_default_splitter_strategy(
    kb_id: str = Path(..., description="知识库ID"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """清除默认切分策略"""
    try:
        # 获取知识库
        kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
        if not kb:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "KNOWLEDGE_BASE_NOT_FOUND",
                    "message": f"知识库不存在: {kb_id}"
                }
            )
        
        # 清空策略配置
        kb.default_splitter_strategy_id = None
        kb.default_splitter_config = None
        
        # 提交更改
        db.commit()
        db.refresh(kb)
        
        return {
            "success": True,
            "message": "成功清除默认切分策略，已恢复系统默认配置",
            "data": {
                "knowledge_base_id": kb_id,
                "effective_splitter_config": kb.get_effective_splitter_config(),
                "config_source": "system_default"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"清除默认切分策略失败: {e}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail={
                "error": "CLEAR_DEFAULT_SPLITTER_ERROR",
                "message": "清除默认切分策略失败"
            }
        )


# ===========================
# 辅助函数
# ===========================

def _get_config_source(kb: KnowledgeBase) -> str:
    """获取配置来源"""
    if kb.default_splitter_config:
        return "custom_config"
    elif kb.default_splitter_strategy_id:
        return "strategy"
    else:
        return "system_default"