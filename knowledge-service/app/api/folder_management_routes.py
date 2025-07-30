"""
知识库文件夹管理API路由
专注于文件夹的基础管理功能，配合检索模式使用
"""

import logging
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Query, Path, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.models.database import get_db
from app.models.simple_folder_models import KnowledgeFolder
from app.models.knowledge_models import Document
from sqlalchemy import and_, func

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
    enable_search: bool = True
    search_scope: str = "folder_only"  # folder_only, include_subfolders
    search_weight: int = 5

class FolderUpdateRequest(BaseModel):
    """更新文件夹请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    enable_search: Optional[bool] = None
    search_scope: Optional[str] = None
    search_weight: Optional[int] = None

class DocumentMoveRequest(BaseModel):
    """移动文档请求"""
    document_ids: List[str]
    target_folder_id: Optional[str] = None


# ===============================
# 文件夹 CRUD API
# ===============================

@router.post("/",
            response_model=Dict[str, Any],
            summary="创建文件夹",
            description="在知识库中创建新的文件夹")
def create_folder(
    kb_id: str = Path(..., description="知识库ID"),
    request: FolderCreateRequest = ...,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """创建文件夹"""
    try:
        # 验证知识库存在
        from app.models.knowledge_models import KnowledgeBase
        kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
        if not kb:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "KB_NOT_FOUND",
                    "message": "知识库不存在"
                }
            )
        
        # 验证父文件夹（如果指定）
        level = 0
        full_path = f"/{request.name}"
        
        if request.parent_id:
            parent_folder = db.query(KnowledgeFolder).filter(
                and_(
                    KnowledgeFolder.id == request.parent_id,
                    KnowledgeFolder.kb_id == kb_id,
                    KnowledgeFolder.status == "active"
                )
            ).first()
            
            if not parent_folder:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "PARENT_FOLDER_NOT_FOUND",
                        "message": "父文件夹不存在"
                    }
                )
            
            if parent_folder.level >= 1:  # 最多支持二级目录
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "MAX_LEVEL_EXCEEDED",
                        "message": "最多支持二级目录"
                    }
                )
            
            level = parent_folder.level + 1
            full_path = f"{parent_folder.full_path}/{request.name}"
        
        # 检查同级名称重复
        existing = db.query(KnowledgeFolder).filter(
            and_(
                KnowledgeFolder.kb_id == kb_id,
                KnowledgeFolder.parent_id == request.parent_id,
                KnowledgeFolder.name == request.name,
                KnowledgeFolder.status == "active"
            )
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "FOLDER_NAME_EXISTS",
                    "message": "同级目录下已存在相同名称的文件夹"
                }
            )
        
        # 创建文件夹
        import uuid
        folder = KnowledgeFolder(
            id=str(uuid.uuid4()),
            kb_id=kb_id,
            parent_id=request.parent_id,
            name=request.name,
            description=request.description,
            level=level,
            full_path=full_path,
            color=request.color,
            icon=request.icon,
            enable_search=request.enable_search,
            search_scope=request.search_scope,
            search_weight=request.search_weight
        )
        
        db.add(folder)
        db.commit()
        db.refresh(folder)
        
        logger.info(f"Created folder: {request.name} in kb: {kb_id}")
        
        return {
            "success": True,
            "message": "文件夹创建成功",
            "data": _format_folder_response(folder)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
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
           description="获取知识库的文件夹列表")
def list_folders(
    kb_id: str = Path(..., description="知识库ID"),
    parent_id: Optional[str] = Query(None, description="父文件夹ID"),
    include_stats: bool = Query(True, description="是否包含统计信息"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """获取文件夹列表"""
    try:
        query = db.query(KnowledgeFolder).filter(
            and_(
                KnowledgeFolder.kb_id == kb_id,
                KnowledgeFolder.parent_id == parent_id,
                KnowledgeFolder.status == "active"
            )
        ).order_by(KnowledgeFolder.name)
        
        folders = query.all()
        
        folder_list = []
        for folder in folders:
            folder_data = _format_folder_response(folder)
            
            if include_stats:
                # 获取子文件夹数量
                children_count = db.query(func.count(KnowledgeFolder.id)).filter(
                    and_(
                        KnowledgeFolder.parent_id == folder.id,
                        KnowledgeFolder.status == "active"
                    )
                ).scalar() or 0
                
                folder_data["children_count"] = children_count
            
            folder_list.append(folder_data)
        
        return {
            "success": True,
            "data": {
                "folders": folder_list,
                "total": len(folder_list),
                "parent_id": parent_id
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
    include_stats: bool = Query(True, description="是否包含统计信息"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """获取文件夹树结构"""
    try:
        # 获取所有文件夹
        all_folders = db.query(KnowledgeFolder).filter(
            and_(
                KnowledgeFolder.kb_id == kb_id,
                KnowledgeFolder.status == "active"
            )
        ).order_by(KnowledgeFolder.level, KnowledgeFolder.name).all()
        
        # 构建树结构
        folder_map = {}
        root_folders = []
        
        for folder in all_folders:
            folder_data = _format_folder_response(folder)
            folder_data["children"] = []
            
            if include_stats:
                # 获取子文件夹数量
                children_count = db.query(func.count(KnowledgeFolder.id)).filter(
                    and_(
                        KnowledgeFolder.parent_id == folder.id,
                        KnowledgeFolder.status == "active"
                    )
                ).scalar() or 0
                folder_data["children_count"] = children_count
            
            folder_map[folder.id] = folder_data
            
            if folder.parent_id is None:
                root_folders.append(folder_data)
            else:
                if folder.parent_id in folder_map:
                    folder_map[folder.parent_id]["children"].append(folder_data)
        
        return {
            "success": True,
            "data": {
                "tree": root_folders,
                "total_folders": len(all_folders),
                "kb_id": kb_id
            }
        }
        
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
    include_documents: bool = Query(False, description="是否包含文档列表"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """获取文件夹详情"""
    try:
        folder = db.query(KnowledgeFolder).filter(
            and_(
                KnowledgeFolder.id == folder_id,
                KnowledgeFolder.kb_id == kb_id,
                KnowledgeFolder.status == "active"
            )
        ).first()
        
        if not folder:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "FOLDER_NOT_FOUND",
                    "message": f"文件夹 {folder_id} 不存在"
                }
            )
        
        folder_data = _format_folder_response(folder)
        
        # 获取子文件夹
        children = db.query(KnowledgeFolder).filter(
            and_(
                KnowledgeFolder.parent_id == folder_id,
                KnowledgeFolder.status == "active"
            )
        ).order_by(KnowledgeFolder.name).all()
        
        folder_data["children"] = [_format_folder_response(child) for child in children]
        
        # 获取文档列表（如果需要）
        if include_documents:
            documents = db.query(Document).filter(
                and_(
                    Document.folder_id == folder_id,
                    Document.status == "completed"
                )
            ).order_by(Document.filename).all()
            
            folder_data["documents"] = [
                {
                    "id": doc.id,
                    "filename": doc.filename,
                    "file_type": doc.file_type,
                    "file_size": doc.file_size,
                    "created_at": doc.created_at.isoformat() if doc.created_at else None
                }
                for doc in documents
            ]
        
        # 获取面包屑导航
        breadcrumb = _get_folder_breadcrumb(db, folder)
        folder_data["breadcrumb"] = breadcrumb
        
        return {
            "success": True,
            "data": folder_data
        }
        
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
        folder = db.query(KnowledgeFolder).filter(
            and_(
                KnowledgeFolder.id == folder_id,
                KnowledgeFolder.kb_id == kb_id,
                KnowledgeFolder.status == "active"
            )
        ).first()
        
        if not folder:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "FOLDER_NOT_FOUND",
                    "message": f"文件夹 {folder_id} 不存在"
                }
            )
        
        # 更新字段
        if request.name and request.name != folder.name:
            # 检查同级名称重复
            existing = db.query(KnowledgeFolder).filter(
                and_(
                    KnowledgeFolder.kb_id == kb_id,
                    KnowledgeFolder.parent_id == folder.parent_id,
                    KnowledgeFolder.name == request.name,
                    KnowledgeFolder.id != folder_id,
                    KnowledgeFolder.status == "active"
                )
            ).first()
            
            if existing:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "FOLDER_NAME_EXISTS",
                        "message": "同级目录下已存在相同名称的文件夹"
                    }
                )
            
            folder.name = request.name
            # 更新完整路径
            if folder.parent_id:
                parent = db.query(KnowledgeFolder).filter(KnowledgeFolder.id == folder.parent_id).first()
                folder.full_path = f"{parent.full_path}/{request.name}" if parent else f"/{request.name}"
            else:
                folder.full_path = f"/{request.name}"
        
        if request.description is not None:
            folder.description = request.description
        if request.color:
            folder.color = request.color
        if request.icon:
            folder.icon = request.icon
        if request.enable_search is not None:
            folder.enable_search = request.enable_search
        if request.search_scope:
            folder.search_scope = request.search_scope
        if request.search_weight is not None:
            folder.search_weight = request.search_weight
        
        db.commit()
        db.refresh(folder)
        
        logger.info(f"Updated folder: {folder_id}")
        
        return {
            "success": True,
            "message": "文件夹更新成功",
            "data": _format_folder_response(folder)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
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
              description="删除文件夹")
def delete_folder(
    kb_id: str = Path(..., description="知识库ID"),
    folder_id: str = Path(..., description="文件夹ID"),
    force: bool = Query(False, description="是否强制删除"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """删除文件夹"""
    try:
        folder = db.query(KnowledgeFolder).filter(
            and_(
                KnowledgeFolder.id == folder_id,
                KnowledgeFolder.kb_id == kb_id,
                KnowledgeFolder.status == "active"
            )
        ).first()
        
        if not folder:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "FOLDER_NOT_FOUND",
                    "message": f"文件夹 {folder_id} 不存在"
                }
            )
        
        # 检查是否有子文件夹
        children_count = db.query(func.count(KnowledgeFolder.id)).filter(
            and_(
                KnowledgeFolder.parent_id == folder_id,
                KnowledgeFolder.status == "active"
            )
        ).scalar() or 0
        
        if children_count > 0 and not force:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "FOLDER_HAS_CHILDREN",
                    "message": f"文件夹包含 {children_count} 个子文件夹，请先删除子文件夹或使用强制删除"
                }
            )
        
        # 检查是否有文档
        doc_count = db.query(func.count(Document.id)).filter(Document.folder_id == folder_id).scalar() or 0
        
        if doc_count > 0 and not force:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "FOLDER_HAS_DOCUMENTS",
                    "message": f"文件夹包含 {doc_count} 个文档，请先移动文档或使用强制删除"
                }
            )
        
        # 执行删除
        if force:
            # 递归删除子文件夹
            _recursive_delete_folder(db, folder_id)
            # 将文档移动到根目录
            db.query(Document).filter(Document.folder_id == folder_id).update({"folder_id": None})
        
        # 标记为已删除
        folder.status = "deleted"
        db.commit()
        
        logger.info(f"Deleted folder: {folder_id} (force={force})")
        
        return {
            "success": True,
            "message": "文件夹删除成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
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

@router.post("/documents/move",
            response_model=Dict[str, Any],
            summary="移动文档到文件夹",
            description="将文档移动到指定文件夹")
def move_documents(
    kb_id: str = Path(..., description="知识库ID"),
    request: DocumentMoveRequest = ...,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """移动文档到文件夹"""
    try:
        # 验证目标文件夹（如果不是移动到根目录）
        if request.target_folder_id:
            target_folder = db.query(KnowledgeFolder).filter(
                and_(
                    KnowledgeFolder.id == request.target_folder_id,
                    KnowledgeFolder.kb_id == kb_id,
                    KnowledgeFolder.status == "active"
                )
            ).first()
            
            if not target_folder:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "TARGET_FOLDER_NOT_FOUND",
                        "message": "目标文件夹不存在"
                    }
                )
        
        # 验证文档存在
        documents = db.query(Document).filter(
            and_(
                Document.id.in_(request.document_ids),
                Document.kb_id == kb_id
            )
        ).all()
        
        if len(documents) != len(request.document_ids):
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "DOCUMENTS_NOT_FOUND",
                    "message": "部分文档不存在"
                }
            )
        
        # 执行移动
        moved_count = 0
        for doc in documents:
            old_folder_id = doc.folder_id
            doc.folder_id = request.target_folder_id
            moved_count += 1
        
        db.commit()
        
        # 更新文件夹统计
        affected_folders = set()
        for doc in documents:
            if doc.folder_id:
                affected_folders.add(doc.folder_id)
        if request.target_folder_id:
            affected_folders.add(request.target_folder_id)
        
        for folder_id in affected_folders:
            _update_folder_stats(db, folder_id)
        
        logger.info(f"Moved {moved_count} documents to folder {request.target_folder_id}")
        
        return {
            "success": True,
            "message": f"成功移动 {moved_count} 个文档",
            "data": {
                "moved_count": moved_count,
                "target_folder_id": request.target_folder_id
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to move documents: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.get("/{folder_id}/documents",
           response_model=Dict[str, Any],
           summary="获取文件夹中的文档",
           description="获取文件夹中的文档列表")
def get_folder_documents(
    kb_id: str = Path(..., description="知识库ID"),
    folder_id: str = Path(..., description="文件夹ID"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """获取文件夹中的文档"""
    try:
        # 验证文件夹存在
        folder = db.query(KnowledgeFolder).filter(
            and_(
                KnowledgeFolder.id == folder_id,
                KnowledgeFolder.kb_id == kb_id,
                KnowledgeFolder.status == "active"
            )
        ).first()
        
        if not folder:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "FOLDER_NOT_FOUND",
                    "message": f"文件夹 {folder_id} 不存在"
                }
            )
        
        # 分页查询文档
        offset = (page - 1) * page_size
        doc_query = db.query(Document).filter(
            and_(
                Document.folder_id == folder_id,
                Document.kb_id == kb_id
            )
        ).order_by(Document.filename)
        
        total = doc_query.count()
        documents = doc_query.offset(offset).limit(page_size).all()
        
        doc_list = []
        for doc in documents:
            doc_data = {
                "id": doc.id,
                "filename": doc.filename,
                "original_filename": doc.original_filename,
                "file_type": doc.file_type,
                "file_size": doc.file_size,
                "status": doc.status,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
                "updated_at": doc.updated_at.isoformat() if doc.updated_at else None
            }
            doc_list.append(doc_data)
        
        return {
            "success": True,
            "data": {
                "folder": _format_folder_response(folder),
                "documents": doc_list,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": (total + page_size - 1) // page_size
                }
            }
        }
        
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


# ===============================
# 统计信息 API
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
        # 文件夹统计
        folder_stats = db.query(
            func.count(KnowledgeFolder.id).label('total_folders'),
            func.count(KnowledgeFolder.id).filter(KnowledgeFolder.level == 0).label('root_folders'),
            func.count(KnowledgeFolder.id).filter(KnowledgeFolder.level == 1).label('level1_folders'),
            func.count(KnowledgeFolder.id).filter(KnowledgeFolder.enable_search == True).label('searchable_folders')
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
        
        # 计算组织率
        total_docs = doc_stats.total_documents or 0
        organized_docs = doc_stats.organized_documents or 0
        organization_rate = round(organized_docs / max(total_docs, 1) * 100, 2)
        
        return {
            "success": True,
            "data": {
                "folder_statistics": {
                    "total_folders": folder_stats.total_folders or 0,
                    "root_folders": folder_stats.root_folders or 0,
                    "level1_folders": folder_stats.level1_folders or 0,
                    "searchable_folders": folder_stats.searchable_folders or 0
                },
                "document_statistics": {
                    "total_documents": total_docs,
                    "organized_documents": organized_docs,
                    "unorganized_documents": doc_stats.unorganized_documents or 0,
                    "organization_rate": organization_rate
                },
                "kb_id": kb_id
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


# ===============================
# 辅助函数
# ===============================

def _format_folder_response(folder: KnowledgeFolder) -> Dict[str, Any]:
    """格式化文件夹响应"""
    return {
        "id": folder.id,
        "name": folder.name,
        "description": folder.description,
        "level": folder.level,
        "full_path": folder.full_path,
        "parent_id": folder.parent_id,
        "color": folder.color,
        "icon": folder.icon,
        "enable_search": folder.enable_search,
        "search_scope": folder.search_scope,
        "search_weight": folder.search_weight,
        "document_count": folder.document_count or 0,
        "total_size": folder.total_size or 0,
        "status": folder.status,
        "created_at": folder.created_at.isoformat() if folder.created_at else None,
        "updated_at": folder.updated_at.isoformat() if folder.updated_at else None
    }


def _get_folder_breadcrumb(db: Session, folder: KnowledgeFolder) -> List[Dict[str, Any]]:
    """获取文件夹面包屑导航"""
    breadcrumb = []
    current = folder
    
    while current:
        breadcrumb.insert(0, {
            "id": current.id,
            "name": current.name,
            "level": current.level
        })
        
        if current.parent_id:
            current = db.query(KnowledgeFolder).filter(KnowledgeFolder.id == current.parent_id).first()
        else:
            current = None
    
    return breadcrumb


def _recursive_delete_folder(db: Session, folder_id: str):
    """递归删除文件夹及其子文件夹"""
    # 获取所有子文件夹
    children = db.query(KnowledgeFolder).filter(KnowledgeFolder.parent_id == folder_id).all()
    
    # 递归删除子文件夹
    for child in children:
        _recursive_delete_folder(db, child.id)
    
    # 删除当前文件夹
    db.query(KnowledgeFolder).filter(KnowledgeFolder.id == folder_id).update({"status": "deleted"})


def _update_folder_stats(db: Session, folder_id: str):
    """更新文件夹统计信息"""
    try:
        doc_stats = db.query(
            func.count(Document.id).label('count'),
            func.sum(Document.file_size).label('total_size')
        ).filter(
            and_(
                Document.folder_id == folder_id,
                Document.status == "completed"
            )
        ).first()
        
        db.query(KnowledgeFolder).filter(KnowledgeFolder.id == folder_id).update({
            "document_count": doc_stats.count or 0,
            "total_size": doc_stats.total_size or 0
        })
        
        db.commit()
        
    except Exception as e:
        logger.error(f"Failed to update folder stats for {folder_id}: {e}")
        db.rollback()