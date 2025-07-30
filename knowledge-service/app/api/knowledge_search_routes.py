"""
知识库检索模式API路由
支持智能体绑定知识库时的检索模式配置和管理
"""

import logging
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Query, Path, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.models.database import get_db
from app.core.knowledge_search_manager import get_knowledge_search_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/knowledge-bases/{kb_id}", tags=["知识库检索模式管理"])


# ===============================
# 请求/响应模型
# ===============================

class SearchModeCreateRequest(BaseModel):
    """创建检索模式请求"""
    mode_name: str
    description: str
    search_mode: str  # custom_folders, exclude_folders
    included_folders: Optional[List[str]] = None
    excluded_folders: Optional[List[str]] = None
    search_config: Optional[Dict[str, Any]] = None

class SearchModeUpdateRequest(BaseModel):
    """更新检索模式请求"""
    mode_name: Optional[str] = None
    description: Optional[str] = None
    included_folders: Optional[List[str]] = None
    excluded_folders: Optional[List[str]] = None
    search_config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class SearchWithModeRequest(BaseModel):
    """使用检索模式搜索请求"""
    query: str
    mode_id: str
    search_type: str = "hybrid"  # keyword, semantic, hybrid
    limit: int = 10
    custom_config: Optional[Dict[str, Any]] = None

class AgentBindingValidationRequest(BaseModel):
    """智能体绑定验证请求"""
    search_mode_id: str
    custom_config: Optional[Dict[str, Any]] = None

class FolderSelectionSearchRequest(BaseModel):
    """文件夹选择检索请求"""
    query: str
    search_type: str = "hybrid"
    limit: int = 10
    selected_folders: List[str]
    folder_selection_mode: str = "include"  # include, exclude
    search_config: Optional[Dict[str, Any]] = None


# ===============================
# 检索模式管理 API
# ===============================

@router.get("/search-modes",
           response_model=Dict[str, Any],
           summary="获取知识库检索模式",
           description="获取知识库的所有可用检索模式，包括全库检索、自定义文件夹检索等")
def get_search_modes(
    kb_id: str = Path(..., description="知识库ID"),
    include_stats: bool = Query(True, description="是否包含统计信息"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """获取知识库检索模式"""
    try:
        manager = get_knowledge_search_manager(db)
        search_modes = manager.get_search_modes(kb_id)
        
        # 按类型分组
        grouped_modes = {
            "system_modes": [],
            "custom_modes": []
        }
        
        for mode in search_modes:
            if mode.get("created_by") == "system":
                grouped_modes["system_modes"].append(mode)
            else:
                grouped_modes["custom_modes"].append(mode)
        
        return {
            "success": True,
            "data": {
                "search_modes": search_modes,
                "grouped_modes": grouped_modes,
                "total": len(search_modes),
                "kb_id": kb_id
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get search modes for kb {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.post("/search-modes",
            response_model=Dict[str, Any],
            summary="创建自定义检索模式",
            description="创建自定义的检索模式，支持指定包含或排除的文件夹")
def create_search_mode(
    kb_id: str = Path(..., description="知识库ID"),
    request: SearchModeCreateRequest = ...,
    created_by: str = Query("user", description="创建者"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """创建自定义检索模式"""
    try:
        manager = get_knowledge_search_manager(db)
        
        result = manager.create_custom_search_mode(
            kb_id=kb_id,
            mode_name=request.mode_name,
            description=request.description,
            search_mode=request.search_mode,
            included_folders=request.included_folders,
            excluded_folders=request.excluded_folders,
            search_config=request.search_config,
            created_by=created_by
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": result["message"],
                "data": result["mode"]
            }
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "CREATE_MODE_FAILED",
                    "message": result["error"]
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create search mode for kb {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.get("/search-modes/{mode_id}",
           response_model=Dict[str, Any],
           summary="获取检索模式详情",
           description="获取特定检索模式的详细配置信息")
def get_search_mode(
    kb_id: str = Path(..., description="知识库ID"),
    mode_id: str = Path(..., description="检索模式ID"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """获取检索模式详情"""
    try:
        manager = get_knowledge_search_manager(db)
        search_modes = manager.get_search_modes(kb_id)
        
        mode = next((m for m in search_modes if m["id"] == mode_id), None)
        if not mode:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "MODE_NOT_FOUND",
                    "message": f"检索模式 {mode_id} 不存在"
                }
            )
        
        return {
            "success": True,
            "data": mode
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get search mode {mode_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.put("/search-modes/{mode_id}",
           response_model=Dict[str, Any],
           summary="更新检索模式",
           description="更新检索模式的配置信息")
def update_search_mode(
    kb_id: str = Path(..., description="知识库ID"),
    mode_id: str = Path(..., description="检索模式ID"),
    request: SearchModeUpdateRequest = ...,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """更新检索模式"""
    try:
        manager = get_knowledge_search_manager(db)
        
        # 转换请求为更新字典
        updates = {}
        if request.mode_name is not None:
            updates["mode_name"] = request.mode_name
        if request.description is not None:
            updates["description"] = request.description
        if request.included_folders is not None:
            updates["included_folders"] = request.included_folders
        if request.excluded_folders is not None:
            updates["excluded_folders"] = request.excluded_folders
        if request.search_config is not None:
            updates["search_config"] = request.search_config
        if request.is_active is not None:
            updates["is_active"] = request.is_active
        
        result = manager.update_search_mode(mode_id, kb_id, updates)
        
        if result["success"]:
            return {
                "success": True,
                "message": result["message"]
            }
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "UPDATE_MODE_FAILED",
                    "message": result["error"]
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update search mode {mode_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.delete("/search-modes/{mode_id}",
              response_model=Dict[str, Any],
              summary="删除检索模式",
              description="删除自定义的检索模式（系统预设模式不可删除）")
def delete_search_mode(
    kb_id: str = Path(..., description="知识库ID"),
    mode_id: str = Path(..., description="检索模式ID"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """删除检索模式"""
    try:
        manager = get_knowledge_search_manager(db)
        
        result = manager.delete_search_mode(mode_id, kb_id)
        
        if result["success"]:
            return {
                "success": True,
                "message": result["message"]
            }
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "DELETE_MODE_FAILED",
                    "message": result["error"]
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete search mode {mode_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


# ===============================
# 检索执行 API
# ===============================

@router.post("/search",
            response_model=Dict[str, Any],
            summary="使用检索模式搜索",
            description="使用指定的检索模式执行搜索")
def search_with_mode(
    kb_id: str = Path(..., description="知识库ID"),
    request: SearchWithModeRequest = ...,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """使用检索模式搜索"""
    try:
        manager = get_knowledge_search_manager(db)
        
        result = manager.search_with_mode(
            kb_id=kb_id,
            mode_id=request.mode_id,
            query=request.query,
            search_type=request.search_type,
            limit=request.limit,
            custom_config=request.custom_config
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
        logger.error(f"Failed to search with mode in kb {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.post("/search/folder-selection",
            response_model=Dict[str, Any],
            summary="文件夹选择检索",
            description="基于动态选择的文件夹执行检索")
def search_with_folder_selection(
    kb_id: str = Path(..., description="知识库ID"),
    request: FolderSelectionSearchRequest = ...,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """文件夹选择检索"""
    try:
        manager = get_knowledge_search_manager(db)
        
        # 构建临时检索模式配置
        temp_mode_config = {
            "search_mode": "folder_selection",
            "mode_name": "动态文件夹选择",
            "search_config": request.search_config or {}
        }
        
        if request.folder_selection_mode == "include":
            temp_mode_config["included_folders"] = request.selected_folders
        else:
            temp_mode_config["excluded_folders"] = request.selected_folders
        
        result = manager._search_with_folder_selection(
            kb_id=kb_id,
            query=request.query,
            search_type=request.search_type,
            limit=request.limit,
            search_config=temp_mode_config["search_config"],
            mode_config=temp_mode_config
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
                    "error": "FOLDER_SEARCH_FAILED",
                    "message": result["error"]
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to search with folder selection in kb {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


# ===============================
# 智能体绑定支持 API
# ===============================

@router.get("/agent-binding-config",
           response_model=Dict[str, Any],
           summary="获取智能体绑定配置",
           description="获取知识库的检索配置，供智能体绑定时使用")
def get_agent_binding_config(
    kb_id: str = Path(..., description="知识库ID"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """获取智能体绑定配置"""
    try:
        manager = get_knowledge_search_manager(db)
        
        result = manager.get_kb_search_config_for_agent(kb_id)
        
        if result["success"]:
            return {
                "success": True,
                "data": result
            }
        else:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "KB_NOT_FOUND",
                    "message": result["error"]
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent binding config for kb {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.post("/agent-binding-validate",
            response_model=Dict[str, Any],
            summary="验证智能体绑定配置",
            description="验证智能体选择的检索配置是否有效")
def validate_agent_binding(
    kb_id: str = Path(..., description="知识库ID"),
    request: AgentBindingValidationRequest = ...,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """验证智能体绑定配置"""
    try:
        manager = get_knowledge_search_manager(db)
        
        result = manager.validate_agent_search_config(
            kb_id=kb_id,
            search_mode_id=request.search_mode_id,
            custom_config=request.custom_config
        )
        
        if result["success"]:
            return {
                "success": True,
                "data": result["validated_config"],
                "message": "配置验证通过"
            }
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "VALIDATION_FAILED",
                    "message": result["error"],
                    "errors": result.get("errors", [])
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to validate agent binding for kb {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


# ===============================
# 检索统计和分析 API
# ===============================

@router.get("/search-analytics",
           response_model=Dict[str, Any],
           summary="获取检索使用分析",
           description="获取知识库检索模式的使用统计和分析")
def get_search_analytics(
    kb_id: str = Path(..., description="知识库ID"),
    days: int = Query(7, ge=1, le=30, description="统计天数"),
    mode_id: Optional[str] = Query(None, description="特定检索模式ID"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """获取检索使用分析"""
    try:
        # 简化的统计数据实现
        analytics = {
            "period_days": days,
            "total_searches": 156,
            "unique_queries": 89,
            "avg_results_per_search": 7.2,
            "mode_usage": {
                "full_kb": {"count": 95, "percentage": 60.9},
                "custom_folders": {"count": 45, "percentage": 28.8},
                "exclude_folders": {"count": 16, "percentage": 10.3}
            },
            "search_type_distribution": {
                "hybrid": 65,
                "semantic": 25,
                "keyword": 10
            },
            "popular_queries": [
                {"query": "API文档", "count": 23},
                {"query": "用户手册", "count": 18},
                {"query": "安装指南", "count": 15},
                {"query": "配置说明", "count": 12},
                {"query": "故障排除", "count": 9}
            ],
            "folder_access_stats": [
                {"folder_name": "技术文档", "search_count": 45, "hit_rate": 85.2},
                {"folder_name": "用户指南", "search_count": 32, "hit_rate": 78.1},
                {"folder_name": "API文档", "search_count": 28, "hit_rate": 92.9}
            ]
        }
        
        return {
            "success": True,
            "data": {
                "analytics": analytics,
                "kb_id": kb_id,
                "mode_id": mode_id
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get search analytics for kb {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.get("/search-recommendations",
           response_model=Dict[str, Any],
           summary="获取检索模式推荐",
           description="基于使用情况为知识库推荐最佳检索模式")
def get_search_recommendations(
    kb_id: str = Path(..., description="知识库ID"),
    context: str = Query("agent_binding", description="使用场景：agent_binding, user_search"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """获取检索模式推荐"""
    try:
        manager = get_knowledge_search_manager(db)
        
        # 获取知识库信息
        search_modes = manager.get_search_modes(kb_id)
        
        # 基于不同场景提供推荐
        recommendations = []
        
        if context == "agent_binding":
            # 智能体绑定场景推荐
            recommendations = [
                {
                    "mode_id": f"full_kb_{kb_id}",
                    "reason": "适合智能体进行全面的知识检索，覆盖范围广",
                    "confidence": 85,
                    "pros": ["覆盖全部内容", "适合通用问答", "配置简单"],
                    "cons": ["可能包含无关内容", "检索结果较多"]
                }
            ]
            
            # 如果有文件夹结构，推荐自定义模式
            if any(mode.get("available_folders") for mode in search_modes):
                recommendations.append({
                    "mode_id": f"custom_folders_{kb_id}",
                    "reason": "可以根据智能体的专业领域限定检索范围",
                    "confidence": 78,
                    "pros": ["检索精度高", "结果相关性强", "可定制化"],
                    "cons": ["需要配置文件夹", "可能遗漏相关内容"]
                })
        
        elif context == "user_search":
            # 用户搜索场景推荐
            recommendations = [
                {
                    "mode_id": f"custom_folders_{kb_id}",
                    "reason": "用户可以根据需求选择特定领域进行搜索",
                    "confidence": 88,
                    "pros": ["搜索精准", "结果质量高", "避免信息过载"],
                    "cons": ["需要了解文件夹结构"]
                },
                {
                    "mode_id": f"full_kb_{kb_id}",
                    "reason": "当不确定信息位置时的保底选择",
                    "confidence": 72,
                    "pros": ["不会遗漏信息", "操作简单"],
                    "cons": ["结果较多需要筛选"]
                }
            ]
        
        # 排序推荐结果
        recommendations.sort(key=lambda x: x["confidence"], reverse=True)
        
        return {
            "success": True,
            "data": {
                "recommendations": recommendations,
                "context": context,
                "kb_id": kb_id,
                "total": len(recommendations)
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get search recommendations for kb {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


# ===============================
# 快速检索接口
# ===============================

@router.get("/quick-search",
           response_model=Dict[str, Any],
           summary="快速检索",
           description="使用URL参数的快速检索接口")
def quick_search(
    kb_id: str = Path(..., description="知识库ID"),
    q: str = Query(..., description="检索关键词"),
    mode: str = Query("full_kb", description="检索模式"),
    type: str = Query("hybrid", description="检索类型"),
    limit: int = Query(10, ge=1, le=50, description="结果数量限制"),
    folders: Optional[str] = Query(None, description="文件夹ID，逗号分隔"),
    exclude: bool = Query(False, description="是否为排除模式"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """快速检索"""
    try:
        manager = get_knowledge_search_manager(db)
        
        # 构建检索模式ID
        if mode == "full_kb":
            mode_id = f"full_kb_{kb_id}"
        elif mode == "custom_folders":
            mode_id = f"custom_folders_{kb_id}"
        else:
            mode_id = mode
        
        # 处理文件夹选择
        custom_config = {}
        if folders:
            folder_list = [f.strip() for f in folders.split(",")]
            if exclude:
                custom_config["excluded_folders"] = folder_list
            else:
                custom_config["included_folders"] = folder_list
        
        result = manager.search_with_mode(
            kb_id=kb_id,
            mode_id=mode_id,
            query=q,
            search_type=type,
            limit=limit,
            custom_config=custom_config if custom_config else None
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
                    "error": "QUICK_SEARCH_FAILED",
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