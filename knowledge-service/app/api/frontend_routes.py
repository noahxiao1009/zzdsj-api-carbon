"""
前端专用API路由 - 优化版本
专门为前端BFF层提供高性能的知识库API接口
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query, Path, Depends
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.core.fast_knowledge_manager import get_fast_knowledge_manager
from app.schemas.knowledge_schemas import KnowledgeBaseResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/frontend/knowledge", tags=["前端专用API"])


@router.get("/bases",
            response_model=Dict[str, Any],
            summary="获取知识库列表（前端专用）",
            description="为前端BFF层提供的高性能知识库列表接口")
def get_knowledge_bases_for_frontend(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页大小"),
    status: Optional[str] = Query(None, description="状态筛选"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    category: Optional[str] = Query(None, description="分类筛选"),
    owner_id: Optional[int] = Query(None, description="所有者ID"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    前端专用知识库列表接口
    
    特点：
    - 超快响应（毫秒级）
    - 直接数据库查询
    - 符合前端BFF期望的数据格式
    """
    try:
        manager = get_fast_knowledge_manager(db)
        
        if search or status:
            # 使用搜索功能
            result = manager.search_knowledge_bases(
                search_term=search,
                status=status,
                page=page,
                page_size=page_size
            )
        else:
            # 使用基础列表功能
            result = manager.list_knowledge_bases(page=page, page_size=page_size)
        
        if result["success"]:
            # 转换为前端期望的格式
            return {
                "success": True,
                "data": result["knowledge_bases"],
                "pagination": {
                    "page": result["page"],
                    "page_size": result["page_size"], 
                    "total": result["total"],
                    "total_pages": result.get("total_pages", 0)
                },
                "message": "获取知识库列表成功"
            }
        else:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "LIST_KNOWLEDGE_BASES_FAILED",
                    "message": result["error"]
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get knowledge bases for frontend: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.get("/bases/{kb_id}",
            response_model=Dict[str, Any],
            summary="获取知识库详情（前端专用）",
            description="为前端BFF层提供的知识库详情接口")
def get_knowledge_base_for_frontend(
    kb_id: str = Path(..., description="知识库ID"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    前端专用知识库详情接口
    """
    try:
        manager = get_fast_knowledge_manager(db)
        result = manager.get_knowledge_base(kb_id)
        
        if result:
            return {
                "success": True,
                "data": result,
                "message": "获取知识库详情成功"
            }
        else:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "KNOWLEDGE_BASE_NOT_FOUND",
                    "message": f"知识库 {kb_id} 不存在"
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get knowledge base {kb_id} for frontend: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.get("/bases/{kb_id}/stats",
            response_model=Dict[str, Any],
            summary="获取知识库统计信息（前端专用）",
            description="为前端BFF层提供的知识库统计接口")
def get_knowledge_base_stats_for_frontend(
    kb_id: str = Path(..., description="知识库ID"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    前端专用知识库统计信息接口
    """
    try:
        manager = get_fast_knowledge_manager(db)
        kb = manager.get_knowledge_base(kb_id)
        
        if not kb:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "KNOWLEDGE_BASE_NOT_FOUND",
                    "message": f"知识库 {kb_id} 不存在"
                }
            )
        
        # 返回统计信息
        stats = {
            "document_count": kb.get("document_count", 0),
            "chunk_count": kb.get("chunk_count", 0),
            "size_bytes": kb.get("total_size", 0),
            "last_updated": kb.get("updated_at")
        }
        
        return {
            "success": True,
            "data": stats,
            "message": "获取统计信息成功"
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get knowledge base stats {kb_id} for frontend: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.get("/health",
            response_model=Dict[str, Any],
            summary="前端API健康检查",
            description="检查前端API服务状态")
def frontend_health_check(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    前端API健康检查
    """
    try:
        manager = get_fast_knowledge_manager(db)
        total_count = manager.count_knowledge_bases()
        
        return {
            "status": "healthy",
            "service": "knowledge-service-frontend-api",
            "total_knowledge_bases": total_count,
            "timestamp": "快速前端API模式",
            "performance": "optimized"
        }
        
    except Exception as e:
        logger.error(f"Frontend health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": "健康检查失败"
            }
        )