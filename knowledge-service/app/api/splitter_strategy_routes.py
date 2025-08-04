"""
切分策略管理API路由
提供切分策略的CRUD和管理接口
"""

import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.core.splitter_strategy_manager import get_splitter_strategy_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/splitter-strategies", tags=["切分策略管理"])


# ===========================
# 请求和响应模型
# ===========================

class SplitterStrategyCreate(BaseModel):
    """创建切分策略请求模型"""
    name: str = Field(..., min_length=1, max_length=100, description="策略名称")
    description: Optional[str] = Field(None, max_length=500, description="策略描述")
    config: Dict[str, Any] = Field(..., description="策略配置")

class SplitterStrategyUpdate(BaseModel):
    """更新切分策略请求模型"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="策略名称")
    description: Optional[str] = Field(None, max_length=500, description="策略描述")
    config: Optional[Dict[str, Any]] = Field(None, description="策略配置")
    is_active: Optional[bool] = Field(None, description="是否激活")

class StrategyRecommendationRequest(BaseModel):
    """策略推荐请求模型"""
    file_type: str = Field(..., description="文件类型（扩展名）")
    file_size: int = Field(..., ge=0, description="文件大小（字节）")
    file_name: Optional[str] = Field(None, description="文件名称")


# ===========================
# API路由
# ===========================

@router.get("/",
            response_model=Dict[str, Any],
            summary="获取切分策略列表",
            description="获取所有可用的切分策略")
async def get_splitter_strategies(
    include_inactive: bool = Query(False, description="是否包含未激活的策略"),
    system_only: bool = Query(False, description="仅返回系统预设策略"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """获取切分策略列表"""
    try:
        strategy_manager = get_splitter_strategy_manager(db)
        
        if system_only:
            strategies = strategy_manager.get_system_strategies()
        else:
            strategies = strategy_manager.get_all_strategies(include_inactive)
        
        return {
            "success": True,
            "message": f"成功获取 {len(strategies)} 个切分策略",
            "data": {
                "strategies": strategies,
                "total_count": len(strategies)
            }
        }
        
    except Exception as e:
        logger.error(f"获取切分策略列表失败: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "STRATEGY_LIST_ERROR",
                "message": "获取切分策略列表失败"
            }
        )


@router.get("/{strategy_id}",
            response_model=Dict[str, Any],
            summary="获取切分策略详情",
            description="根据ID获取特定切分策略的详细信息")
async def get_splitter_strategy(
    strategy_id: str = Path(..., description="策略ID"),
    include_usage_stats: bool = Query(False, description="是否包含使用统计"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """获取切分策略详情"""
    try:
        strategy_manager = get_splitter_strategy_manager(db)
        
        strategy = strategy_manager.get_strategy_by_id(strategy_id)
        if not strategy:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "STRATEGY_NOT_FOUND",
                    "message": f"切分策略不存在: {strategy_id}"
                }
            )
        
        result_data = {"strategy": strategy}
        
        # 如果需要使用统计
        if include_usage_stats:
            usage_stats = strategy_manager.get_strategy_usage_stats(strategy_id)
            result_data["usage_stats"] = usage_stats
        
        return {
            "success": True,
            "message": "成功获取切分策略详情",
            "data": result_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取切分策略详情失败: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "STRATEGY_DETAIL_ERROR",
                "message": "获取切分策略详情失败"
            }
        )


@router.post("/",
             response_model=Dict[str, Any],
             summary="创建切分策略",
             description="创建新的文档切分策略")
async def create_splitter_strategy(
    request: SplitterStrategyCreate,
    created_by: str = Query("system", description="创建者"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """创建切分策略"""
    try:
        strategy_manager = get_splitter_strategy_manager(db)
        
        strategy = strategy_manager.create_strategy(
            name=request.name,
            description=request.description or "",
            config=request.config,
            is_system=False,  # 用户创建的策略不是系统策略
            created_by=created_by
        )
        
        if not strategy:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "STRATEGY_CREATE_FAILED",
                    "message": "创建切分策略失败，可能是名称已存在或配置无效"
                }
            )
        
        return {
            "success": True,
            "message": f"成功创建切分策略: {request.name}",
            "data": {"strategy": strategy}
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建切分策略失败: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "STRATEGY_CREATE_ERROR",
                "message": "创建切分策略失败"
            }
        )


@router.put("/{strategy_id}",
            response_model=Dict[str, Any],
            summary="更新切分策略",
            description="更新已存在的切分策略")
async def update_splitter_strategy(
    request: SplitterStrategyUpdate,
    strategy_id: str = Path(..., description="策略ID"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """更新切分策略"""
    try:
        strategy_manager = get_splitter_strategy_manager(db)
        
        strategy = strategy_manager.update_strategy(
            strategy_id=strategy_id,
            name=request.name,
            description=request.description,
            config=request.config,
            is_active=request.is_active
        )
        
        if not strategy:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "STRATEGY_UPDATE_FAILED",
                    "message": "更新切分策略失败，可能是策略不存在或配置无效"
                }
            )
        
        return {
            "success": True,
            "message": f"成功更新切分策略: {strategy_id}",
            "data": {"strategy": strategy}
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新切分策略失败: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "STRATEGY_UPDATE_ERROR",
                "message": "更新切分策略失败"
            }
        )


@router.delete("/{strategy_id}",
               response_model=Dict[str, Any],
               summary="删除切分策略",
               description="删除指定的切分策略（不能删除系统预设策略）")
async def delete_splitter_strategy(
    strategy_id: str = Path(..., description="策略ID"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """删除切分策略"""
    try:
        strategy_manager = get_splitter_strategy_manager(db)
        
        success = strategy_manager.delete_strategy(strategy_id)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "STRATEGY_DELETE_FAILED",
                    "message": "删除切分策略失败，可能是系统策略或正在使用中"
                }
            )
        
        return {
            "success": True,
            "message": f"成功删除切分策略: {strategy_id}",
            "data": {"deleted_strategy_id": strategy_id}
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除切分策略失败: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "STRATEGY_DELETE_ERROR",
                "message": "删除切分策略失败"
            }
        )


@router.get("/{strategy_id}/usage",
            response_model=Dict[str, Any],
            summary="获取策略使用统计",
            description="获取指定策略的使用统计信息")
async def get_strategy_usage_stats(
    strategy_id: str = Path(..., description="策略ID"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """获取策略使用统计"""
    try:
        strategy_manager = get_splitter_strategy_manager(db)
        
        # 先验证策略是否存在
        strategy = strategy_manager.get_strategy_by_id(strategy_id)
        if not strategy:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "STRATEGY_NOT_FOUND",
                    "message": f"切分策略不存在: {strategy_id}"
                }
            )
        
        usage_stats = strategy_manager.get_strategy_usage_stats(strategy_id)
        
        return {
            "success": True,
            "message": "成功获取策略使用统计",
            "data": {
                "strategy": strategy,
                "usage_stats": usage_stats
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取策略使用统计失败: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "USAGE_STATS_ERROR",
                "message": "获取策略使用统计失败"
            }
        )


@router.post("/recommend",
             response_model=Dict[str, Any],
             summary="获取推荐策略",
             description="根据文件类型和大小推荐合适的切分策略")
async def recommend_strategy(
    request: StrategyRecommendationRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """获取推荐策略"""
    try:
        strategy_manager = get_splitter_strategy_manager(db)
        
        recommended_strategy = strategy_manager.get_recommended_strategy(
            file_type=request.file_type,
            file_size=request.file_size
        )
        
        return {
            "success": True,
            "message": "成功获取推荐策略",
            "data": {
                "recommended_strategy": recommended_strategy,
                "recommendation_reason": _get_recommendation_reason(
                    request.file_type, 
                    request.file_size,
                    recommended_strategy["name"]
                )
            }
        }
        
    except Exception as e:
        logger.error(f"获取推荐策略失败: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "RECOMMENDATION_ERROR",
                "message": "获取推荐策略失败"
            }
        )


@router.get("/configs/defaults",
            response_model=Dict[str, Any],
            summary="获取默认配置模板",
            description="获取各种策略类型的默认配置模板")
async def get_default_configs() -> Dict[str, Any]:
    """获取默认配置模板"""
    try:
        from app.models.splitter_strategy import SplitterStrategy
        
        default_configs = {
            "basic": SplitterStrategy.get_default_config("basic"),
            "semantic": SplitterStrategy.get_default_config("semantic"),
            "smart": SplitterStrategy.get_default_config("smart"),
            "code": SplitterStrategy.get_default_config("code"),
            "large": SplitterStrategy.get_default_config("large")
        }
        
        return {
            "success": True,
            "message": "成功获取默认配置模板",
            "data": {
                "default_configs": default_configs,
                "config_descriptions": {
                    "basic": "基础切分策略 - 适用于一般文档",
                    "semantic": "语义切分策略 - 基于语义边界分割",
                    "smart": "智能切分策略 - 基于文档结构智能分割",
                    "code": "代码切分策略 - 专门针对代码文件",
                    "large": "大文档切分策略 - 适用于长文档"
                }
            }
        }
        
    except Exception as e:
        logger.error(f"获取默认配置模板失败: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "DEFAULT_CONFIGS_ERROR",
                "message": "获取默认配置模板失败"
            }
        )


# ===========================
# 辅助函数
# ===========================

def _get_recommendation_reason(file_type: str, file_size: int, strategy_name: str) -> str:
    """获取推荐理由"""
    reasons = {
        "code_chunking": f"检测到代码文件类型 ({file_type})，推荐使用代码专用切分策略",
        "large_document": f"文件大小 ({file_size // (1024*1024)}MB) 较大，推荐使用大文档切分策略",
        "semantic_chunking": f"文本文档 ({file_type}) 适合使用语义切分策略保持内容连贯性",
        "smart_chunking": f"一般文档 ({file_type}) 推荐使用智能切分策略以获得最佳效果",
        "basic_chunking": "使用基础切分策略作为默认选择"
    }
    
    return reasons.get(strategy_name, f"根据文件特征推荐使用 {strategy_name} 策略")