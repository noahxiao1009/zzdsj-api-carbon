"""
切分策略API路由
提供切分策略的创建、更新、删除和查询接口
"""

import logging
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends, Query, Path
from sqlalchemy.orm import Session

from app.schemas.chunking_strategy_schemas import (
    ChunkingStrategyCreate,
    ChunkingStrategyUpdate,
    ChunkingStrategyResponse,
    ChunkingStrategyList,
    ChunkingStrategyStats,
    ChunkingCategory
)
from app.models.database import get_db
from app.repositories.chunking_strategy_repository import get_chunking_strategy_repository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chunking-strategies", tags=["切分策略管理"])


def get_repository(db: Session = Depends(get_db)):
    return get_chunking_strategy_repository(db)


@router.post("/", response_model=ChunkingStrategyResponse, summary="创建切分策略")
async def create_chunking_strategy(
    request: ChunkingStrategyCreate,
    repository = Depends(get_repository)
) -> ChunkingStrategyResponse:
    """
    创建新的切分策略
    """
    try:
        strategy = repository.create(request)
        return strategy
    except Exception as e:
        logger.error(f"Failed to create chunking strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=ChunkingStrategyList, summary="获取切分策略列表")
async def list_chunking_strategies(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页大小"),
    repository = Depends(get_repository)
) -> ChunkingStrategyList:
    """
    获取分页的切分策略列表
    """
    try:
        result = repository.list_strategies(page=page, page_size=page_size)
        return ChunkingStrategyList(**result)
    except Exception as e:
        logger.error(f"Failed to list chunking strategies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{strategy_id}", response_model=ChunkingStrategyResponse, summary="获取切分策略详情")
async def get_chunking_strategy(
    strategy_id: str,
    repository = Depends(get_repository)
) -> ChunkingStrategyResponse:
    """
    根据策略ID获取切分策略的详细信息
    """
    try:
        from uuid import UUID
        strategy = repository.get_by_id(UUID(strategy_id))
        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")
        return strategy
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid strategy ID format")
    except Exception as e:
        logger.error(f"Failed to get chunking strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{strategy_id}", response_model=ChunkingStrategyResponse, summary="更新切分策略")
async def update_chunking_strategy(
    strategy_id: str,
    request: ChunkingStrategyUpdate,
    repository = Depends(get_repository)
) -> ChunkingStrategyResponse:
    """
    更新切分策略
    """
    try:
        from uuid import UUID
        strategy = repository.update(UUID(strategy_id), request)
        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")
        return strategy
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid strategy ID format")
    except Exception as e:
        logger.error(f"Failed to update chunking strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{strategy_id}", response_model=Dict[str, Any], summary="删除切分策略")
async def delete_chunking_strategy(
    strategy_id: str,
    repository = Depends(get_repository)
) -> Dict[str, Any]:
    """
    删除切分策略
    """
    try:
        from uuid import UUID
        success = repository.delete(UUID(strategy_id))
        if not success:
            raise HTTPException(status_code=404, detail="Strategy not found or cannot be deleted")
        return {"success": True, "message": "Strategy deleted successfully"}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid strategy ID format")
    except Exception as e:
        logger.error(f"Failed to delete chunking strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics", response_model=ChunkingStrategyStats, summary="获取切分策略统计信息")
async def get_chunking_strategy_stats(
    repository = Depends(get_repository)
) -> ChunkingStrategyStats:
    """
    获取切分策略的统计信息
    """
    try:
        stats = repository.get_statistics()
        return ChunkingStrategyStats(**stats)
    except Exception as e:
        logger.error(f"Failed to get chunking strategy statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


