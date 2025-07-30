"""
快速知识库API路由 - 性能优化版本
专门用于高频查询操作，避免复杂依赖的初始化开销
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path as PathLib
from fastapi import APIRouter, HTTPException, Query, Path, Depends
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.core.fast_knowledge_manager import get_fast_knowledge_manager
from app.schemas.knowledge_schemas import KnowledgeBaseCreate
from fastapi import UploadFile, File, Form

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/knowledge-bases", tags=["知识库管理 - 快速版本"])


@router.get("/",
            response_model=Dict[str, Any],
            summary="获取知识库列表（快速版本）",
            description="快速获取知识库列表，避免外部依赖的初始化延迟")
def list_knowledge_bases_fast(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页大小"),
    status: Optional[str] = Query(None, description="状态筛选"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    快速获取知识库列表
    
    这个版本专门优化了性能：
    - 避免异步开销
    - 直接数据库查询
    - 最小化对象创建
    - 跳过外部依赖初始化
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
            return {
                "success": True,
                "data": {
                    "knowledge_bases": result["knowledge_bases"],
                    "pagination": {
                        "page": result["page"],
                        "page_size": result["page_size"],
                        "total": result["total"],
                        "total_pages": result.get("total_pages", 0)
                    }
                }
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
        logger.error(f"Failed to list knowledge bases: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.get("/{kb_id}",
            response_model=Dict[str, Any],
            summary="获取知识库详情（快速版本）",
            description="快速获取知识库详情")
def get_knowledge_base_fast(
    kb_id: str = Path(..., description="知识库ID"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    快速获取知识库详情
    """
    try:
        manager = get_fast_knowledge_manager(db)
        result = manager.get_knowledge_base(kb_id)
        
        if result:
            return {
                "success": True,
                "data": result
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
        logger.error(f"Failed to get knowledge base {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.get("/statistics/quick",
            response_model=Dict[str, Any],
            summary="快速统计信息",
            description="获取知识库的快速统计信息")
def get_quick_statistics(
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    获取快速统计信息
    """
    try:
        manager = get_fast_knowledge_manager(db)
        total_count = manager.count_knowledge_bases()
        
        return {
            "success": True,
            "data": {
                "total_knowledge_bases": total_count,
                "active_knowledge_bases": total_count,  # 简化统计
                "timestamp": "快速统计模式"
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get quick statistics: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.get("/statistics",
            response_model=Dict[str, Any],
            summary="获取知识库统计信息",
            description="获取知识库的整体统计信息")
def get_statistics(
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    获取知识库整体统计信息
    """
    try:
        manager = get_fast_knowledge_manager(db)
        total_count = manager.count_knowledge_bases()
        
        return {
            "success": True,
            "data": {
                "total_knowledge_bases": total_count,
                "active_knowledge_bases": total_count,
                "document_count": 0,  # 简化统计
                "chunk_count": 0,
                "total_size": 0,
                "last_updated": None,
                "timestamp": "快速统计模式"
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR", 
                "message": str(e)
            }
        )


@router.get("/models/embedding",
            response_model=Dict[str, Any],
            summary="获取嵌入模型列表",
            description="获取可用的嵌入模型列表")
def get_embedding_models(
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    获取可用的嵌入模型列表
    """
    try:
        # 返回常用的嵌入模型列表
        models = [
            {
                "id": "text-embedding-3-small",
                "name": "OpenAI text-embedding-3-small",
                "provider": "openai",
                "dimension": 1536,
                "description": "OpenAI最新小型嵌入模型"
            },
            {
                "id": "text-embedding-3-large", 
                "name": "OpenAI text-embedding-3-large",
                "provider": "openai",
                "dimension": 3072,
                "description": "OpenAI最新大型嵌入模型"
            },
            {
                "id": "text-embedding-ada-002",
                "name": "OpenAI text-embedding-ada-002", 
                "provider": "openai",
                "dimension": 1536,
                "description": "OpenAI经典嵌入模型"
            }
        ]
        
        return {
            "success": True,
            "data": models
        }
        
    except Exception as e:
        logger.error(f"Failed to get embedding models: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.post("/",
            response_model=Dict[str, Any],
            summary="创建知识库（快速版本）",
            description="快速创建新的知识库")
def create_knowledge_base_fast(
    request: KnowledgeBaseCreate,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    快速创建知识库
    
    这个版本专门优化了性能：
    - 同步处理，避免异步开销
    - 直接数据库操作
    - 最小化初始化过程
    """
    try:
        manager = get_fast_knowledge_manager(db)
        
        # 使用快速管理器创建知识库
        result = manager.create_knowledge_base(
            name=request.name,
            description=request.description,
            user_id=request.user_id or "system",
            embedding_provider=request.embedding_provider,
            embedding_model=request.embedding_model,
            vector_store_type=request.vector_store_type,
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": "知识库创建成功",
                "data": result["knowledge_base"]
            }
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "KNOWLEDGE_BASE_CREATION_FAILED",
                    "message": result["error"]
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create knowledge base: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR", 
                "message": str(e)
            }
        )


@router.post("/{kb_id}/documents",
            response_model=Dict[str, Any],
            summary="上传文档到知识库（兼容版本）",
            description="兼容前端的文档上传接口，内部转发到异步上传服务")
async def upload_document_fast(
    kb_id: str = Path(..., description="知识库ID"),
    file: UploadFile = File(..., description="上传的文档文件"),
    description: Optional[str] = Form(None, description="文档描述"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    兼容前端的文档上传接口
    
    这个版本转发请求到现有的异步上传服务：
    - 兼容前端现有调用方式
    - 内部转发到 /upload-async 端点
    - 保持API响应格式兼容
    """
    try:
        # 调用现有的异步上传服务
        import httpx
        
        # 准备文件数据
        files = {"files": (file.filename, await file.read(), file.content_type)}
        
        # 调用内部异步上传API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://localhost:8082/api/v1/knowledge-bases/{kb_id}/documents/upload-async",
                files=files,
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # 转换响应格式以兼容前端期望
                if result.get("success") and result.get("data", {}).get("tasks"):
                    task = result["data"]["tasks"][0]  # 取第一个任务
                    return {
                        "success": True,
                        "message": "文档上传成功",
                        "data": {
                            "document_id": task["task_id"],
                            "kb_id": kb_id,
                            "filename": task["filename"],
                            "status": task["status"],
                            "task_id": task["task_id"],
                            "description": description or "",
                            "file_size": task["file_size"],
                            "upload_time": result["data"]["upload_time"]
                        }
                    }
                else:
                    raise HTTPException(
                        status_code=500,
                        detail={
                            "error": "UPLOAD_FAILED",
                            "message": result.get("message", "上传失败")
                        }
                    )
            else:
                # 转发错误响应
                error_detail = response.json() if response.headers.get("content-type", "").startswith("application/json") else {"message": response.text}
                raise HTTPException(
                    status_code=response.status_code,
                    detail=error_detail
                )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload document to knowledge base {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )