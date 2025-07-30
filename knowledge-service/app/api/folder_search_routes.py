"""
文件夹检索API路由
专注于检索范围控制和文件夹级别的搜索功能
"""

import logging
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Query, Path, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.models.database import get_db
from app.core.folder_search_manager import get_folder_search_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/knowledge-bases/{kb_id}/search", tags=["知识库检索 - 文件夹支持"])


# ===============================
# 请求/响应模型
# ===============================

class SearchRequest(BaseModel):
    """检索请求"""
    query: str
    search_scope_id: str  # 检索范围ID：kb_{kb_id} 或 folder_id
    search_type: str = "hybrid"  # keyword, semantic, hybrid
    limit: int = 10
    filters: Optional[Dict[str, Any]] = None

class SearchConfigRequest(BaseModel):
    """检索配置请求"""
    similarity_threshold: Optional[int] = None  # 0-100
    max_results: Optional[int] = None
    enable_semantic_search: Optional[bool] = None
    enable_keyword_search: Optional[bool] = None
    sort_by: Optional[str] = None  # relevance, date, size, filename
    sort_order: Optional[str] = None  # asc, desc
    allowed_file_types: Optional[List[str]] = None
    boost_recent_documents: Optional[bool] = None
    boost_factor: Optional[int] = None  # 1-5
    search_scope: Optional[str] = None  # folder_only, include_subfolders
    search_weight: Optional[int] = None  # 1-10
    enable_search: Optional[bool] = None


# ===============================
# 检索范围管理 API
# ===============================

@router.get("/scopes",
           response_model=Dict[str, Any],
           summary="获取检索范围选项",
           description="获取知识库的所有可用检索范围（整个知识库 + 各文件夹）")
def get_search_scopes(
    kb_id: str = Path(..., description="知识库ID"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """获取检索范围选项"""
    try:
        manager = get_folder_search_manager(db)
        scopes = manager.get_search_scopes(kb_id)
        
        return {
            "success": True,
            "data": {
                "scopes": scopes,
                "total": len(scopes),
                "kb_id": kb_id
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get search scopes for kb {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.get("/scopes/{scope_id}/config",
           response_model=Dict[str, Any],
           summary="获取检索范围配置",
           description="获取特定检索范围的配置信息")
def get_scope_config(
    kb_id: str = Path(..., description="知识库ID"),
    scope_id: str = Path(..., description="检索范围ID"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """获取检索范围配置"""
    try:
        if scope_id.startswith("kb_"):
            # 知识库级别配置
            return {
                "success": True,
                "data": {
                    "scope_id": scope_id,
                    "scope_type": "knowledge_base",
                    "name": "整个知识库",
                    "config": {
                        "enable_search": True,
                        "search_scope": "entire_kb",
                        "max_results": 20,
                        "enable_semantic_search": True,
                        "enable_keyword_search": True,
                        "sort_by": "relevance",
                        "sort_order": "desc"
                    }
                }
            }
        else:
            # 文件夹级别配置
            manager = get_folder_search_manager(db)
            config = manager.get_folder_search_config(scope_id, kb_id)
            
            if config:
                return {
                    "success": True,
                    "data": {
                        "scope_id": scope_id,
                        "scope_type": "folder",
                        "config": config
                    }
                }
            else:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "SCOPE_NOT_FOUND",
                        "message": f"检索范围 {scope_id} 不存在"
                    }
                )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get scope config for {scope_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.put("/scopes/{scope_id}/config",
           response_model=Dict[str, Any],
           summary="设置检索范围配置",
           description="设置特定文件夹的检索配置（知识库级别配置不可修改）")
def set_scope_config(
    kb_id: str = Path(..., description="知识库ID"),
    scope_id: str = Path(..., description="检索范围ID"),
    request: SearchConfigRequest = ...,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """设置检索范围配置"""
    try:
        if scope_id.startswith("kb_"):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "KB_CONFIG_IMMUTABLE",
                    "message": "知识库级别的检索配置不可修改"
                }
            )
        
        manager = get_folder_search_manager(db)
        
        # 转换请求为配置字典
        config = {}
        if request.similarity_threshold is not None:
            config["similarity_threshold"] = request.similarity_threshold
        if request.max_results is not None:
            config["max_results"] = request.max_results
        if request.enable_semantic_search is not None:
            config["enable_semantic_search"] = request.enable_semantic_search
        if request.enable_keyword_search is not None:
            config["enable_keyword_search"] = request.enable_keyword_search
        if request.sort_by is not None:
            config["sort_by"] = request.sort_by
        if request.sort_order is not None:
            config["sort_order"] = request.sort_order
        if request.allowed_file_types is not None:
            config["allowed_file_types"] = request.allowed_file_types
        if request.boost_recent_documents is not None:
            config["boost_recent_documents"] = request.boost_recent_documents
        if request.boost_factor is not None:
            config["boost_factor"] = request.boost_factor
        if request.search_scope is not None:
            config["search_scope"] = request.search_scope
        if request.search_weight is not None:
            config["search_weight"] = request.search_weight
        if request.enable_search is not None:
            config["enable_search"] = request.enable_search
        
        result = manager.set_folder_search_config(scope_id, kb_id, config)
        
        if result["success"]:
            return {
                "success": True,
                "message": result["message"],
                "data": result["config"]
            }
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "CONFIG_UPDATE_FAILED",
                    "message": result["error"]
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set scope config for {scope_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


# ===============================
# 检索功能 API
# ===============================

@router.post("/",
            response_model=Dict[str, Any],
            summary="执行检索",
            description="在指定检索范围内执行搜索，支持知识库级别和文件夹级别")
def search_documents(
    kb_id: str = Path(..., description="知识库ID"),
    request: SearchRequest = ...,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """执行检索"""
    try:
        manager = get_folder_search_manager(db)
        
        result = manager.search_in_scope(
            kb_id=kb_id,
            query=request.query,
            search_scope_id=request.search_scope_id,
            search_type=request.search_type,
            limit=request.limit,
            filters=request.filters
        )
        
        if result["success"]:
            return {
                "success": True,
                "data": {
                    "results": result["results"],
                    "total": result["total"],
                    "search_scope": result["search_scope"],
                    "search_type": result["search_type"],
                    "query": result["query"],
                    "kb_id": kb_id,
                    "scope_info": result.get("folder_info"),
                    "search_scope_type": result.get("search_scope_type")
                }
            }
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "SEARCH_FAILED",
                    "message": result["error"]
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to search in kb {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.get("/quick",
           response_model=Dict[str, Any],
           summary="快速检索",
           description="使用URL参数的快速检索接口")
def quick_search(
    kb_id: str = Path(..., description="知识库ID"),
    q: str = Query(..., description="检索关键词"),
    scope: str = Query(..., description="检索范围ID"),
    type: str = Query("hybrid", description="检索类型"),
    limit: int = Query(10, ge=1, le=50, description="结果数量限制"),
    file_types: Optional[str] = Query(None, description="文件类型过滤，逗号分隔"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """快速检索"""
    try:
        manager = get_folder_search_manager(db)
        
        # 处理文件类型过滤
        filters = None
        if file_types:
            filters = {"file_types": [ft.strip() for ft in file_types.split(",")]}
        
        result = manager.search_in_scope(
            kb_id=kb_id,
            query=q,
            search_scope_id=scope,
            search_type=type,
            limit=limit,
            filters=filters
        )
        
        if result["success"]:
            return {
                "success": True,
                "data": result
            }
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "SEARCH_FAILED",
                    "message": result["error"]
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to quick search in kb {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


# ===============================
# 检索建议 API
# ===============================

@router.get("/suggestions",
           response_model=Dict[str, Any],
           summary="获取检索建议",
           description="根据知识库内容提供检索建议和常用关键词")
def get_search_suggestions(
    kb_id: str = Path(..., description="知识库ID"),
    scope_id: Optional[str] = Query(None, description="检索范围ID，不指定则为整个知识库"),
    limit: int = Query(10, ge=1, le=20, description="建议数量"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """获取检索建议"""
    try:
        # 这里是简化实现，实际可以基于文档内容分析生成建议
        suggestions = [
            {
                "keyword": "API文档",
                "description": "查找API相关文档",
                "popularity": 85,
                "category": "技术文档"
            },
            {
                "keyword": "用户手册",
                "description": "查找用户操作手册",
                "popularity": 72,
                "category": "用户文档"
            },
            {
                "keyword": "架构设计",
                "description": "查找系统架构设计文档",
                "popularity": 68,
                "category": "设计文档"
            },
            {
                "keyword": "测试报告",
                "description": "查找测试相关报告",
                "popularity": 45,
                "category": "测试文档"
            },
            {
                "keyword": "需求分析",
                "description": "查找需求分析文档",
                "popularity": 62,
                "category": "需求文档"
            }
        ]
        
        # 按热门程度排序并限制数量
        suggestions.sort(key=lambda x: x["popularity"], reverse=True)
        suggestions = suggestions[:limit]
        
        return {
            "success": True,
            "data": {
                "suggestions": suggestions,
                "scope_id": scope_id or f"kb_{kb_id}",
                "total": len(suggestions)
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get search suggestions for kb {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


# ===============================
# 检索统计 API
# ===============================

@router.get("/statistics",
           response_model=Dict[str, Any],
           summary="获取检索统计",
           description="获取知识库和文件夹的检索使用统计")
def get_search_statistics(
    kb_id: str = Path(..., description="知识库ID"),
    scope_id: Optional[str] = Query(None, description="检索范围ID"),
    days: int = Query(7, ge=1, le=30, description="统计天数"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """获取检索统计"""
    try:
        # 简化的统计实现
        stats = {
            "total_searches": 245,
            "successful_searches": 234,
            "success_rate": 95.5,
            "avg_results_per_search": 8.3,
            "popular_keywords": [
                {"keyword": "API", "count": 45},
                {"keyword": "用户手册", "count": 32},
                {"keyword": "架构", "count": 28},
                {"keyword": "测试", "count": 19},
                {"keyword": "需求", "count": 15}
            ],
            "search_type_distribution": {
                "hybrid": 60,
                "semantic": 25,
                "keyword": 15
            },
            "scope_usage": {
                "knowledge_base": 40,
                "folders": 60
            }
        }
        
        return {
            "success": True,
            "data": {
                "statistics": stats,
                "scope_id": scope_id or f"kb_{kb_id}",
                "period_days": days,
                "kb_id": kb_id
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get search statistics for kb {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )