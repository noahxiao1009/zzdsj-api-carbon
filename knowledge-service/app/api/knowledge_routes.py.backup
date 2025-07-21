"""
知识库管理API路由
基于LlamaIndex框架和Agno框架，提供完整的知识库管理功能
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Path, Depends
from fastapi.responses import JSONResponse
from datetime import datetime

from app.schemas.knowledge_schemas import (
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeBaseResponse,
    KnowledgeBaseList,
    SearchRequest,
    SearchResponse,
    EmbeddingModelList,
    ErrorResponse,
    KnowledgeBaseConfig,
    VectorizationRequest,
    DocumentMetadata
)
from app.core.knowledge_manager import get_unified_knowledge_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/knowledge-bases", tags=["知识库管理"])


# 依赖注入：获取知识库管理器
def get_knowledge_manager():
    return get_unified_knowledge_manager()


@router.post("/", 
             response_model=Dict[str, Any],
             summary="创建知识库",
             description="创建新的知识库，支持LlamaIndex和Agno双框架")
async def create_knowledge_base(
    request: KnowledgeBaseCreate,
    manager = Depends(get_knowledge_manager)
) -> Dict[str, Any]:
    """
    创建知识库
    
    支持的特性：
    - 多种嵌入模型提供商（OpenAI、Azure、HuggingFace等）
    - 多种向量存储类型（PGVector、Milvus等）
    - LlamaIndex精细化检索
    - Agno框架快速检索
    - 自定义分块策略
    """
    try:
        result = await manager.create_knowledge_base(request)
        
        if result["success"]:
            return {
                "success": True,
                "message": "知识库创建成功",
                "data": result["knowledge_base"],
                "frameworks": {
                    "llamaindex_enabled": result["llamaindex_enabled"],
                    "agno_enabled": result["agno_enabled"]
                }
            }
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "KNOWLEDGE_BASE_CREATION_FAILED",
                    "message": result["error"]
                }
            )
            
    except Exception as e:
        logger.error(f"Failed to create knowledge base: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.get("/",
            response_model=Dict[str, Any],
            summary="获取知识库列表",
            description="分页获取知识库列表，支持筛选和排序")
async def list_knowledge_bases(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页大小"),
    status: Optional[str] = Query(None, description="状态筛选"),
    manager = Depends(get_knowledge_manager)
) -> Dict[str, Any]:
    """
    获取知识库列表
    
    查询参数：
    - page: 页码（从1开始）
    - page_size: 每页记录数（1-100）
    - status: 状态筛选（active、inactive等）
    """
    try:
        result = await manager.list_knowledge_bases(page=page, page_size=page_size)
        
        if result["success"]:
            return {
                "success": True,
                "data": {
                    "knowledge_bases": result["knowledge_bases"],
                    "pagination": {
                        "page": result["page"],
                        "page_size": result["page_size"],
                        "total": result["total"],
                        "total_pages": (result["total"] + page_size - 1) // page_size
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
            summary="获取知识库详情",
            description="根据ID获取知识库的详细信息")
async def get_knowledge_base(
    kb_id: str = Path(..., description="知识库ID"),
    manager = Depends(get_knowledge_manager)
) -> Dict[str, Any]:
    """
    获取知识库详情
    
    返回知识库的完整信息，包括配置、统计数据等
    """
    try:
        kb_info = await manager.get_knowledge_base(kb_id)
        
        if kb_info:
            return {
                "success": True,
                "data": kb_info
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


@router.put("/{kb_id}",
            response_model=Dict[str, Any],
            summary="更新知识库",
            description="更新知识库的配置信息")
async def update_knowledge_base(
    kb_id: str = Path(..., description="知识库ID"),
    request: KnowledgeBaseUpdate = None,
    manager = Depends(get_knowledge_manager)
) -> Dict[str, Any]:
    """
    更新知识库配置
    
    支持更新：
    - 基本信息（名称、描述）
    - 检索参数（相似度阈值、分块大小等）
    - 功能开关（混合搜索、Agno集成等）
    """
    try:
        result = await manager.update_knowledge_base(kb_id, request)
        
        if result["success"]:
            return {
                "success": True,
                "message": "知识库更新成功",
                "data": {
                    "kb_id": result["kb_id"],
                    "updated_fields": result["updated_fields"]
                }
            }
        else:
            if "not found" in result["error"].lower():
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "KNOWLEDGE_BASE_NOT_FOUND",
                        "message": result["error"]
                    }
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "UPDATE_FAILED",
                        "message": result["error"]
                    }
                )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update knowledge base {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.delete("/{kb_id}",
               response_model=Dict[str, Any],
               summary="删除知识库",
               description="删除指定的知识库及其所有数据")
async def delete_knowledge_base(
    kb_id: str = Path(..., description="知识库ID"),
    manager = Depends(get_knowledge_manager)
) -> Dict[str, Any]:
    """
    删除知识库
    
    ⚠️ 警告：此操作不可逆，将删除知识库及其所有文档数据
    """
    try:
        result = await manager.delete_knowledge_base(kb_id)
        
        if result["success"]:
            return {
                "success": True,
                "message": "知识库删除成功",
                "data": {
                    "kb_id": result["kb_id"],
                    "llamaindex_deleted": result["llamaindex_deleted"],
                    "agno_deleted": result["agno_deleted"]
                }
            }
        else:
            if "not found" in result["error"].lower():
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "KNOWLEDGE_BASE_NOT_FOUND",
                        "message": result["error"]
                    }
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "DELETE_FAILED",
                        "message": result["error"]
                    }
                )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete knowledge base {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.post("/{kb_id}/search",
             response_model=SearchResponse,
             summary="搜索知识库",
             description="在知识库中搜索相关内容，支持多种检索模式")
async def search_knowledge_base(
    kb_id: str = Path(..., description="知识库ID"),
    request: SearchRequest = None,
    manager = Depends(get_knowledge_manager)
) -> SearchResponse:
    """
    搜索知识库
    
    支持三种检索模式：
    1. llamaindex: 精细化检索，使用LlamaIndex框架
    2. agno: 快速检索，使用Agno框架 (search_knowledge=true)
    3. hybrid: 混合模式，同时使用两个框架并合并结果
    
    检索参数：
    - top_k: 返回结果数量
    - similarity_threshold: 相似度阈值
    - enable_reranking: 是否启用重排序
    - agno_confidence_threshold: Agno框架置信度阈值
    """
    try:
        # 设置请求中的知识库ID
        request.knowledge_base_id = kb_id
        
        # 执行搜索
        response = await manager.search(request)
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to search knowledge base {kb_id}: {e}")
        return SearchResponse(
            query=request.query if request else "",
            search_mode="error",
            results=[],
            total_results=0,
            search_time=0.0,
            llamaindex_results=0,
            agno_results=0
        )


@router.get("/{kb_id}/stats",
            response_model=Dict[str, Any],
            summary="获取知识库统计信息",
            description="获取知识库的详细统计数据")
async def get_knowledge_base_stats(
    kb_id: str = Path(..., description="知识库ID"),
    manager = Depends(get_knowledge_manager)
) -> Dict[str, Any]:
    """
    获取知识库统计信息
    
    包括：
    - 文档数量
    - 分块数量
    - 向量数量
    - 存储大小
    - 最后更新时间
    """
    try:
        kb_info = await manager.get_knowledge_base(kb_id)
        
        if not kb_info:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "KNOWLEDGE_BASE_NOT_FOUND",
                    "message": f"知识库 {kb_id} 不存在"
                }
            )
        
        # 获取详细统计信息
        stats = {
            "kb_id": kb_id,
            "name": kb_info["name"],
            "document_count": kb_info["document_count"],
            "chunk_count": kb_info["chunk_count"],
            "embedding_model": kb_info["embedding_model"],
            "vector_store_type": kb_info["vector_store_type"],
            "created_at": kb_info["created_at"],
            "updated_at": kb_info["updated_at"],
            "frameworks": {
                "llamaindex_enabled": True,
                "agno_enabled": kb_info.get("enable_agno_integration", False)
            }
        }
        
        return {
            "success": True,
            "data": stats
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get knowledge base stats {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.get("/models/embedding",
            response_model=Dict[str, Any],
            summary="获取可用嵌入模型",
            description="获取系统中可用的嵌入模型列表")
async def get_available_embedding_models(
    provider: Optional[str] = Query(None, description="提供商筛选"),
    manager = Depends(get_knowledge_manager)
) -> Dict[str, Any]:
    """
    获取可用嵌入模型列表
    
    从模型服务获取当前可用的嵌入模型，包括：
    - OpenAI models
    - Azure OpenAI models  
    - HuggingFace models
    - 本地部署models
    
    查询参数：
    - provider: 按提供商筛选（openai, azure_openai, huggingface, local）
    """
    try:
        result = await manager.get_available_embedding_models()
        
        if result["success"]:
            models = result["models"]
            
            # 按提供商筛选
            if provider:
                models = [m for m in models if m["provider"] == provider]
            
            return {
                "success": True,
                "data": {
                    "models": models,
                    "total": len(models),
                    "provider_counts": result["provider_counts"]
                }
            }
        else:
            return {
                "success": False,
                "error": result["error"],
                "data": {
                    "models": [],
                    "total": 0,
                    "provider_counts": {}
                }
            }
            
    except Exception as e:
        logger.error(f"Failed to get available embedding models: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


# ===== 文档管理 =====

@router.post("/{kb_id}/documents/upload",
            response_model=Dict[str, Any],
            summary="上传文档到知识库",
            description="上传文档文件到知识库，支持多种文档格式")
async def upload_document(
    kb_id: str = Path(..., description="知识库ID"),
    files: List[UploadFile] = File(..., description="上传的文档文件"),
    chunk_strategy: Optional[str] = Form("auto", description="分块策略"),
    process_immediately: bool = Form(True, description="是否立即处理"),
    manager = Depends(get_knowledge_manager)
) -> Dict[str, Any]:
    """
    上传文档到知识库
    
    支持的文档格式：
    - PDF文档 (.pdf)
    - Word文档 (.docx, .doc)
    - Excel表格 (.xlsx, .xls)
    - PowerPoint演示文稿 (.pptx, .ppt)
    - 纯文本文件 (.txt, .md)
    - 网页文件 (.html)
    
    分块策略：
    - auto: 自动选择最佳策略
    - semantic: 语义分块
    - fixed: 固定大小分块
    - paragraph: 段落分块
    """
    try:
        # 检查知识库是否存在
        kb_info = await manager.get_knowledge_base(kb_id)
        if not kb_info:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "KNOWLEDGE_BASE_NOT_FOUND",
                    "message": f"知识库 {kb_id} 不存在"
                }
            )
        
        # 验证文件格式
        allowed_extensions = {'.pdf', '.docx', '.doc', '.xlsx', '.xls', 
                            '.pptx', '.ppt', '.txt', '.md', '.html', '.htm'}
        
        uploaded_files = []
        for file in files:
            # 检查文件扩展名
            file_ext = Path(file.filename).suffix.lower()
            if file_ext not in allowed_extensions:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "UNSUPPORTED_FILE_FORMAT",
                        "message": f"不支持的文件格式: {file_ext}"
                    }
                )
            
            # 读取文件内容
            content = await file.read()
            
            # 重置文件指针
            await file.seek(0)
            
            uploaded_files.append({
                "filename": file.filename,
                "content": content,
                "content_type": file.content_type,
                "size": len(content)
            })
        
        # 处理文档上传
        result = await manager.upload_documents(
            kb_id=kb_id,
            files=uploaded_files,
            chunk_strategy=chunk_strategy,
            process_immediately=process_immediately
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": "文档上传成功",
                "data": {
                    "uploaded_files": result["uploaded_files"],
                    "total_files": len(uploaded_files),
                    "processing_status": result["processing_status"]
                }
            }
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "UPLOAD_FAILED",
                    "message": result["error"]
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload documents to KB {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.post("/{kb_id}/documents/url",
            response_model=Dict[str, Any],
            summary="从URL添加文档",
            description="通过URL抓取网页内容并添加到知识库")
async def add_document_from_url(
    kb_id: str = Path(..., description="知识库ID"),
    urls: List[str] = None,
    extract_links: bool = False,
    max_depth: int = 1,
    manager = Depends(get_knowledge_manager)
) -> Dict[str, Any]:
    """
    从URL添加文档
    
    支持抓取：
    - 网页内容
    - PDF文档链接
    - 在线文档
    
    参数：
    - urls: 要抓取的URL列表
    - extract_links: 是否提取页面中的链接
    - max_depth: 最大抓取深度
    """
    try:
        # 检查知识库是否存在
        kb_info = await manager.get_knowledge_base(kb_id)
        if not kb_info:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "KNOWLEDGE_BASE_NOT_FOUND",
                    "message": f"知识库 {kb_id} 不存在"
                }
            )
        
        # 处理URL抓取
        result = await manager.add_documents_from_urls(
            kb_id=kb_id,
            urls=urls,
            extract_links=extract_links,
            max_depth=max_depth
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": "URL文档添加成功",
                "data": result["data"]
            }
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "URL_EXTRACTION_FAILED",
                    "message": result["error"]
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add documents from URL to KB {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.get("/{kb_id}/documents",
           response_model=Dict[str, Any],
           summary="获取知识库文档列表",
           description="分页获取知识库中的所有文档")
async def list_documents(
    kb_id: str = Path(..., description="知识库ID"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    file_type: Optional[str] = Query(None, description="文件类型筛选"),
    status: Optional[str] = Query(None, description="处理状态筛选"),
    manager = Depends(get_knowledge_manager)
) -> Dict[str, Any]:
    """
    获取知识库文档列表
    
    支持的筛选条件：
    - search: 按文档名称搜索
    - file_type: 按文件类型筛选（pdf, docx, txt等）
    - status: 按处理状态筛选（pending, processing, completed, failed）
    """
    try:
        # 检查知识库是否存在
        kb_info = await manager.get_knowledge_base(kb_id)
        if not kb_info:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "KNOWLEDGE_BASE_NOT_FOUND",
                    "message": f"知识库 {kb_id} 不存在"
                }
            )
        
        # 获取文档列表
        result = await manager.list_documents(
            kb_id=kb_id,
            page=page,
            page_size=page_size,
            search=search,
            file_type=file_type,
            status=status
        )
        
        if result["success"]:
            return {
                "success": True,
                "data": {
                    "documents": result["documents"],
                    "pagination": {
                        "page": page,
                        "page_size": page_size,
                        "total": result["total"],
                        "total_pages": (result["total"] + page_size - 1) // page_size
                    },
                    "filters": {
                        "file_types": result.get("file_types", []),
                        "statuses": result.get("statuses", [])
                    }
                }
            }
        else:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "LIST_DOCUMENTS_FAILED",
                    "message": result["error"]
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list documents for KB {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.get("/{kb_id}/documents/{doc_id}",
           response_model=Dict[str, Any],
           summary="获取文档详情",
           description="获取知识库中指定文档的详细信息")
async def get_document_details(
    kb_id: str = Path(..., description="知识库ID"),
    doc_id: str = Path(..., description="文档ID"),
    manager = Depends(get_knowledge_manager)
) -> Dict[str, Any]:
    """
    获取文档详情
    
    返回文档的完整信息，包括：
    - 基本信息（名称、大小、类型等）
    - 处理状态和进度
    - 分块信息
    - 向量化状态
    - 错误信息（如有）
    """
    try:
        # 获取文档详情
        result = await manager.get_document_details(kb_id, doc_id)
        
        if result["success"]:
            return {
                "success": True,
                "data": result["document"]
            }
        else:
            if "not found" in result["error"].lower():
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "DOCUMENT_NOT_FOUND",
                        "message": result["error"]
                    }
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error": "GET_DOCUMENT_FAILED",
                        "message": result["error"]
                    }
                )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document details {doc_id} in KB {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.delete("/{kb_id}/documents/{doc_id}",
              response_model=Dict[str, Any],
              summary="删除文档",
              description="从知识库中删除指定文档及其相关数据")
async def delete_document(
    kb_id: str = Path(..., description="知识库ID"),
    doc_id: str = Path(..., description="文档ID"),
    manager = Depends(get_knowledge_manager)
) -> Dict[str, Any]:
    """
    删除文档
    
    ⚠️ 警告：此操作将删除文档及其所有分块和向量数据，不可恢复
    """
    try:
        # 删除文档
        result = await manager.delete_document(kb_id, doc_id)
        
        if result["success"]:
            return {
                "success": True,
                "message": "文档删除成功",
                "data": {
                    "doc_id": doc_id,
                    "deleted_chunks": result.get("deleted_chunks", 0),
                    "deleted_vectors": result.get("deleted_vectors", 0)
                }
            }
        else:
            if "not found" in result["error"].lower():
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "DOCUMENT_NOT_FOUND",
                        "message": result["error"]
                    }
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "DELETE_DOCUMENT_FAILED",
                        "message": result["error"]
                    }
                )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document {doc_id} in KB {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.post("/{kb_id}/documents/{doc_id}/reprocess",
            response_model=Dict[str, Any],
            summary="重新处理文档",
            description="重新处理文档，重新生成分块和向量")
async def reprocess_document(
    kb_id: str = Path(..., description="知识库ID"),
    doc_id: str = Path(..., description="文档ID"),
    chunk_strategy: Optional[str] = Query("auto", description="分块策略"),
    force: bool = Query(False, description="强制重新处理"),
    manager = Depends(get_knowledge_manager)
) -> Dict[str, Any]:
    """
    重新处理文档
    
    在以下情况下可能需要重新处理：
    - 修改了分块参数
    - 更换了嵌入模型
    - 处理过程中出现错误
    """
    try:
        # 重新处理文档
        result = await manager.reprocess_document(
            kb_id=kb_id,
            doc_id=doc_id,
            chunk_strategy=chunk_strategy,
            force=force
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": "文档重新处理已启动",
                "data": {
                    "doc_id": doc_id,
                    "processing_status": result["processing_status"],
                    "estimated_time": result.get("estimated_time")
                }
            }
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "REPROCESS_FAILED",
                    "message": result["error"]
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reprocess document {doc_id} in KB {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


# ===== 分块管理 =====

@router.get("/{kb_id}/documents/{doc_id}/chunks",
           response_model=Dict[str, Any],
           summary="获取文档分块列表",
           description="获取文档的所有分块信息")
async def get_document_chunks(
    kb_id: str = Path(..., description="知识库ID"),
    doc_id: str = Path(..., description="文档ID"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    manager = Depends(get_knowledge_manager)
) -> Dict[str, Any]:
    """
    获取文档分块列表
    
    返回文档的所有分块，包括：
    - 分块内容
    - 分块位置信息
    - 向量状态
    - 相似度分数（如果有搜索上下文）
    """
    try:
        # 获取文档分块
        result = await manager.get_document_chunks(
            kb_id=kb_id,
            doc_id=doc_id,
            page=page,
            page_size=page_size
        )
        
        if result["success"]:
            return {
                "success": True,
                "data": {
                    "chunks": result["chunks"],
                    "pagination": {
                        "page": page,
                        "page_size": page_size,
                        "total": result["total"],
                        "total_pages": (result["total"] + page_size - 1) // page_size
                    }
                }
            }
        else:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "GET_CHUNKS_FAILED",
                    "message": result["error"]
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get chunks for document {doc_id} in KB {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


# ===== 检索测试 =====

@router.post("/{kb_id}/test/search",
            response_model=SearchResponse,
            summary="测试检索功能",
            description="测试知识库的检索效果，用于调试和优化")
async def test_search(
    kb_id: str = Path(..., description="知识库ID"),
    query: str = Query(..., description="测试查询"),
    search_mode: str = Query("hybrid", description="搜索模式"),
    top_k: int = Query(5, ge=1, le=20, description="返回结果数量"),
    include_scores: bool = Query(True, description="包含相似度分数"),
    include_content: bool = Query(True, description="包含分块内容"),
    manager = Depends(get_knowledge_manager)
) -> SearchResponse:
    """
    测试检索功能
    
    用于：
    - 测试查询效果
    - 调试检索参数
    - 比较不同检索模式
    - 分析结果质量
    """
    try:
        from app.schemas.knowledge_schemas import SearchRequest, SearchMode
        
        # 构建搜索请求
        search_request = SearchRequest(
            query=query,
            knowledge_base_id=kb_id,
            search_mode=SearchMode(search_mode),
            top_k=top_k,
            include_metadata=True
        )
        
        # 执行测试搜索
        response = await manager.search(search_request)
        
        # 如果不需要完整内容，则截断
        if not include_content:
            for result in response.results:
                if len(result.content) > 200:
                    result.content = result.content[:200] + "..."
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to test search in KB {kb_id}: {e}")
        return SearchResponse(
            query=query,
            search_mode="error",
            results=[],
            total_results=0,
            search_time=0.0,
            llamaindex_results=0,
            agno_results=0
        )


# ===== 系统状态 =====

@router.get("/health",
           summary="服务健康检查",
           description="检查知识库服务的健康状态")
async def health_check():
    """服务健康检查"""
    try:
        manager = get_knowledge_manager()
        
        # 检查服务状态
        health_status = {
            "service": "knowledge-service",
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "frameworks": {
                "llamaindex": True,
                "agno": True
            },
            "total_knowledge_bases": len(manager.knowledge_bases)
        }
        
        return {
            "success": True,
            "data": health_status
        }
        
    except Exception as e:
        logger.error(f"健康检查失败: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "status": "unhealthy"
        } 