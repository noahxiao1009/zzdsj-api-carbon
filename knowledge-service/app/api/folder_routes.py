"""
知识库文件夹管理API路由
提供文件夹的CRUD操作、层级管理和检索功能
"""

import logging
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Query, Path, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.models.database import get_db
from app.core.folder_manager import get_folder_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/knowledge-bases/{kb_id}/folders", tags=["知识库文件夹管理"])


# ===============================
# 请求/响应模型
# ===============================

class FolderCreateRequest(BaseModel):
    """创建文件夹请求"""
    name: str
    description: Optional[str] = None
    parent_id: Optional[str] = None
    color: str = "#1890ff"
    icon: str = "folder"

class FolderUpdateRequest(BaseModel):
    """更新文件夹请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None

class MoveDocumentRequest(BaseModel):
    """移动文档请求"""
    document_id: str
    target_folder_id: Optional[str] = None

class FolderSearchRequest(BaseModel):
    """文件夹内搜索请求"""
    query: str
    search_type: str = "semantic"
    include_subfolders: bool = True
    limit: int = 10


# ===============================
# 文件夹 CRUD API
# ===============================

@router.post("/",
            response_model=Dict[str, Any],
            summary="创建文件夹",
            description="在知识库中创建新的文件夹，支持一级和二级目录")
def create_folder(
    kb_id: str = Path(..., description="知识库ID"),
    request: FolderCreateRequest = ...,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """创建文件夹"""
    try:
        manager = get_folder_manager(db)
        
        result = manager.create_folder(
            kb_id=kb_id,
            name=request.name,
            description=request.description,
            parent_id=request.parent_id,
            color=request.color,
            icon=request.icon
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": "文件夹创建成功",
                "data": result["folder"]
            }
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "FOLDER_CREATION_FAILED",
                    "message": result["error"]
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create folder in kb {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.get("/",
           response_model=Dict[str, Any],
           summary="获取文件夹列表",
           description="获取知识库的文件夹列表，支持按层级查询")
def list_folders(
    kb_id: str = Path(..., description="知识库ID"),
    parent_id: Optional[str] = Query(None, description="父文件夹ID，为空则获取根目录文件夹"),
    include_documents: bool = Query(False, description="是否包含文档列表"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """获取文件夹列表"""
    try:
        manager = get_folder_manager(db)
        
        folders = manager.list_folders(
            kb_id=kb_id,
            parent_id=parent_id,
            include_documents=include_documents
        )
        
        return {
            "success": True,
            "data": {
                "folders": folders,
                "parent_id": parent_id,
                "total": len(folders)
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to list folders for kb {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.get("/tree",
           response_model=Dict[str, Any],
           summary="获取文件夹树结构",
           description="获取知识库的完整文件夹树结构")
def get_folder_tree(
    kb_id: str = Path(..., description="知识库ID"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """获取文件夹树结构"""
    try:
        manager = get_folder_manager(db)
        
        result = manager.get_folder_tree(kb_id)
        
        if result["success"]:
            return {
                "success": True,
                "data": {
                    "tree": result["tree"],
                    "total_folders": result["total_folders"]
                }
            }
        else:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "GET_TREE_FAILED",
                    "message": result["error"]
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get folder tree for kb {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.get("/{folder_id}",
           response_model=Dict[str, Any],
           summary="获取文件夹详情",
           description="获取特定文件夹的详细信息")
def get_folder(
    kb_id: str = Path(..., description="知识库ID"),
    folder_id: str = Path(..., description="文件夹ID"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """获取文件夹详情"""
    try:
        manager = get_folder_manager(db)
        
        folder = manager.get_folder(folder_id, kb_id)
        
        if folder:
            return {
                "success": True,
                "data": folder
            }
        else:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "FOLDER_NOT_FOUND",
                    "message": f"文件夹 {folder_id} 不存在"
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get folder {folder_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.put("/{folder_id}",
           response_model=Dict[str, Any],
           summary="更新文件夹",
           description="更新文件夹的基本信息")
def update_folder(
    kb_id: str = Path(..., description="知识库ID"),
    folder_id: str = Path(..., description="文件夹ID"),
    request: FolderUpdateRequest = ...,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """更新文件夹"""
    try:
        manager = get_folder_manager(db)
        
        result = manager.update_folder(
            folder_id=folder_id,
            kb_id=kb_id,
            name=request.name,
            description=request.description,
            color=request.color,
            icon=request.icon
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": "文件夹更新成功",
                "data": result["folder"]
            }
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "FOLDER_UPDATE_FAILED",
                    "message": result["error"]
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update folder {folder_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.delete("/{folder_id}",
              response_model=Dict[str, Any],
              summary="删除文件夹",
              description="删除文件夹，支持强制删除（包含子文件夹和文档）")
def delete_folder(
    kb_id: str = Path(..., description="知识库ID"),
    folder_id: str = Path(..., description="文件夹ID"),
    force: bool = Query(False, description="是否强制删除（包含子文件夹和文档）"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """删除文件夹"""
    try:
        manager = get_folder_manager(db)
        
        result = manager.delete_folder(folder_id, kb_id, force)
        
        if result["success"]:
            return {
                "success": True,
                "message": result["message"]
            }
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "FOLDER_DELETE_FAILED",
                    "message": result["error"]
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete folder {folder_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


# ===============================
# 文档管理 API
# ===============================

@router.get("/{folder_id}/documents",
           response_model=Dict[str, Any],
           summary="获取文件夹中的文档",
           description="获取文件夹中的文档列表，支持分页和子文件夹包含")
def get_folder_documents(
    kb_id: str = Path(..., description="知识库ID"),
    folder_id: str = Path(..., description="文件夹ID"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    include_subfolders: bool = Query(False, description="是否包含子文件夹的文档"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """获取文件夹中的文档"""
    try:
        manager = get_folder_manager(db)
        
        result = manager.get_folder_documents(
            folder_id=folder_id,
            kb_id=kb_id,
            page=page,
            page_size=page_size,
            include_subfolders=include_subfolders
        )
        
        if result["success"]:
            return {
                "success": True,
                "data": {
                    "documents": result["documents"],
                    "pagination": result["pagination"],
                    "include_subfolders": include_subfolders
                }
            }
        else:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "GET_DOCUMENTS_FAILED",
                    "message": result["error"]
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get documents for folder {folder_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.post("/documents/move",
            response_model=Dict[str, Any],
            summary="移动文档到文件夹",
            description="将文档移动到指定文件夹或根目录")
def move_document(
    kb_id: str = Path(..., description="知识库ID"),
    request: MoveDocumentRequest = ...,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """移动文档到文件夹"""
    try:
        manager = get_folder_manager(db)
        
        result = manager.move_document_to_folder(
            doc_id=request.document_id,
            folder_id=request.target_folder_id,
            kb_id=kb_id
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": result["message"]
            }
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "MOVE_DOCUMENT_FAILED",
                    "message": result["error"]
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to move document in kb {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


# ===============================
# 文件夹检索 API
# ===============================

@router.post("/{folder_id}/search",
            response_model=Dict[str, Any],
            summary="在文件夹内检索",
            description="在指定文件夹及其子文件夹内进行文档检索")
def search_in_folder(
    kb_id: str = Path(..., description="知识库ID"),
    folder_id: str = Path(..., description="文件夹ID"),
    request: FolderSearchRequest = ...,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """在文件夹内检索"""
    try:
        manager = get_folder_manager(db)
        
        result = manager.search_in_folder(
            folder_id=folder_id,
            kb_id=kb_id,
            query=request.query,
            search_type=request.search_type,
            include_subfolders=request.include_subfolders,
            limit=request.limit
        )
        
        if result["success"]:
            return {
                "success": True,
                "data": {
                    "results": result["results"],
                    "total": result["total"],
                    "search_scope": result["search_scope"],
                    "query": request.query,
                    "search_type": request.search_type,
                    "include_subfolders": request.include_subfolders
                }
            }
        else:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "FOLDER_SEARCH_FAILED",
                    "message": result["error"]
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to search in folder {folder_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


# ===============================
# 统计和分析 API
# ===============================

@router.get("/statistics",
           response_model=Dict[str, Any],
           summary="获取文件夹统计信息",
           description="获取知识库的文件夹使用统计")
def get_folder_statistics(
    kb_id: str = Path(..., description="知识库ID"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """获取文件夹统计信息"""
    try:
        manager = get_folder_manager(db)
        
        # 获取基本统计
        from app.models.folder_models import KnowledgeFolder
        from app.models.knowledge_models import Document
        from sqlalchemy import func, and_
        
        # 文件夹统计
        folder_stats = db.query(
            func.count(KnowledgeFolder.id).label('total_folders'),
            func.count(KnowledgeFolder.id).filter(KnowledgeFolder.level == 0).label('root_folders'),
            func.count(KnowledgeFolder.id).filter(KnowledgeFolder.level == 1).label('level1_folders'),
            func.count(KnowledgeFolder.id).filter(KnowledgeFolder.level == 2).label('level2_folders')
        ).filter(
            and_(
                KnowledgeFolder.kb_id == kb_id,
                KnowledgeFolder.status == "active"
            )
        ).first()
        
        # 文档分布统计
        doc_stats = db.query(
            func.count(Document.id).label('total_documents'),
            func.count(Document.id).filter(Document.folder_id.isnot(None)).label('organized_documents'),
            func.count(Document.id).filter(Document.folder_id.is_(None)).label('unorganized_documents')
        ).filter(Document.kb_id == kb_id).first()
        
        return {
            "success": True,
            "data": {
                "folder_statistics": {
                    "total_folders": folder_stats.total_folders or 0,
                    "root_folders": folder_stats.root_folders or 0,
                    "level1_folders": folder_stats.level1_folders or 0,
                    "level2_folders": folder_stats.level2_folders or 0
                },
                "document_statistics": {
                    "total_documents": doc_stats.total_documents or 0,
                    "organized_documents": doc_stats.organized_documents or 0,
                    "unorganized_documents": doc_stats.unorganized_documents or 0,
                    "organization_rate": round(
                        (doc_stats.organized_documents or 0) / max(doc_stats.total_documents or 1, 1) * 100, 2
                    )
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get folder statistics for kb {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )