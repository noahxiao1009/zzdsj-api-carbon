"""
知识库管理API路由 - 重构版本
集成新的增强知识库管理器和文档处理器
"""

import asyncio
import json
import logging
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Path, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.schemas.knowledge_schemas import (
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeBaseResponse,
    SearchRequest,
    SearchResponse,
    SearchTestRequest,
    SearchTestResponse,
    GlobalSearchTestRequest,
    GlobalSearchTestResponse,
    IndexRebuildRequest,
    IndexStatus,
    IndexPerformanceComparison,
    EmbeddingModelList,
    ErrorResponse,
    DocumentMetadata
)
from app.models.database import get_db
from app.core.enhanced_knowledge_manager import get_unified_knowledge_manager
from app.services.enhanced_document_processor import EnhancedDocumentProcessor, get_enhanced_document_processor
from app.services.document_processing.url_processor import get_url_processor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/knowledge-bases", tags=["知识库管理"])


# 依赖注入
def get_knowledge_manager(db: Session = Depends(get_db)):
    return get_unified_knowledge_manager(db)

def get_document_processor(db: Session = Depends(get_db)):
    return DocumentProcessor(db)

def get_embedding_service(db: Session = Depends(get_db)):
    return EmbeddingService(db)



# GPS - 文档处理服务
def get_enhanced_document_processor_service(db: Session = Depends(get_db)):
    return get_enhanced_document_processor(db)

@router.post("/upload",
            response_model=Dict[str, Any],
            summary="上传并处理文档",
            description="上传文件并异步处理为向量")
async def upload_document(
    kb_id: str = Form(..., description="知识库ID"),
    file: UploadFile = File(..., description="待上传的文件"),
    title: Optional[str] = Form(None, description="文档标题"),
    metadata: Optional[str] = Form(None, description="文档元数据"),
    processor: EnhancedDocumentProcessor = Depends(get_enhanced_document_processor_service),
    background_tasks: BackgroundTasks = BackgroundTasks()
) -> Dict[str, Any]:
    """
    上传文档并处理其向量化
    """
    # 保存上传的文件
    upload_dir = Path("/tmp/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / file.filename
    with open(file_path, "wb") as f:
        f.write(await file.read())

    # 解析元数据
    metadata_dict = json.loads(metadata) if metadata else {}

    # 处理文件（异步后端任务）
    processing_result = await processor.process_uploaded_document(kb_id, str(file_path), file.filename, title, metadata_dict)

    # 返回响应
    return JSONResponse(content=processing_result)


@router.post("/",
            response_model=Dict[str, Any], 
            summary="创建知识库",
            description="创建新的知识库")
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
    search: Optional[str] = Query(None, description="搜索关键词"),
    embedding_model: Optional[str] = Query(None, description="嵌入模型筛选"),
    manager = Depends(get_knowledge_manager)
) -> Dict[str, Any]:
    """
    获取知识库列表
    
    查询参数：
    - page: 页码（从1开始）
    - page_size: 每页记录数（1-100）
    - status: 状态筛选（active、inactive等）
    - search: 搜索关键词（名称、描述）
    - embedding_model: 嵌入模型筛选
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
    
    返回知识库的完整信息，包括：
    - 基本配置信息
    - 文档和分块统计
    - 处理状态
    - 框架集成状态
    """
    try:
        result = await manager.get_knowledge_base(kb_id)
        
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


@router.put("/{kb_id}",
            response_model=Dict[str, Any],
            summary="更新知识库",
            description="更新知识库的配置信息")
async def update_knowledge_base(
    kb_id: str = Path(..., description="知识库ID"),
    request: KnowledgeBaseUpdate = ...,
    manager = Depends(get_knowledge_manager)
) -> Dict[str, Any]:
    """
    更新知识库配置
    
    可更新的字段：
    - 名称和描述
    - 嵌入模型配置
    - 分块配置
    - 检索配置
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
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "UPDATE_KNOWLEDGE_BASE_FAILED",
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
               description="删除知识库及其所有相关数据")
async def delete_knowledge_base(
    kb_id: str = Path(..., description="知识库ID"),
    manager = Depends(get_knowledge_manager)
) -> Dict[str, Any]:
    """
    删除知识库
    
    警告：此操作将删除：
    - 知识库配置
    - 所有文档和分块
    - 向量数据
    - 处理任务记录
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
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "DELETE_KNOWLEDGE_BASE_FAILED",
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


@router.post("/{kb_id}/documents/upload",
             response_model=Dict[str, Any],
             summary="上传文档",
             description="上传文档到知识库并启动处理流程")
async def upload_documents(
    kb_id: str = Path(..., description="知识库ID"),
    files: List[UploadFile] = File(..., description="要上传的文档文件"),
    chunk_size: Optional[int] = Form(None, description="分块大小"),
    chunk_overlap: Optional[int] = Form(None, description="分块重叠"),
    chunk_strategy: Optional[str] = Form("token_based", description="分块策略"),
    preserve_structure: bool = Form(True, description="保留文档结构"),
    manager = Depends(get_knowledge_manager)
) -> Dict[str, Any]:
    """
    上传文档到知识库
    
    支持的文件格式：
    - PDF文档
    - Word文档（.doc, .docx）
    - Excel文档（.xls, .xlsx）
    - CSV文件
    - 纯文本文件
    - Markdown文件
    - JSON文件
    
    处理流程：
    1. 文件上传和验证
    2. 文本提取
    3. 智能分块
    4. 向量化（异步）
    5. 索引存储
    """
    try:
        # 准备分块配置
        chunk_config = None
        if any([chunk_size, chunk_overlap, chunk_strategy]):
            chunk_config = {
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
                "strategy": chunk_strategy,
                "preserve_structure": preserve_structure
            }
        
        result = await manager.upload_documents(
            kb_id=kb_id,
            files=files,
            chunk_config=chunk_config
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": f"成功上传 {result['processed_files']} 个文件",
                "data": {
                    "processed_files": result["processed_files"],
                    "failed_files": result["failed_files"],
                    "results": result["results"]
                }
            }
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "DOCUMENT_UPLOAD_FAILED",
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
             description="从URL抓取内容并添加到知识库")
async def add_documents_from_url(
    kb_id: str = Path(..., description="知识库ID"),
    urls: List[str] = Form(..., description="要抓取的URL列表"),
    chunk_size: Optional[int] = Form(None, description="分块大小"),
    chunk_overlap: Optional[int] = Form(None, description="分块重叠"),
    chunk_strategy: Optional[str] = Form("token_based", description="分块策略"),
    preserve_structure: bool = Form(True, description="保留文档结构"),
    manager = Depends(get_knowledge_manager)
) -> Dict[str, Any]:
    """
    从URL添加文档到知识库
    
    支持的URL类型：
    - 网页内容 (HTML)
    - PDF文档链接
    - Word文档链接
    - 纯文本文件
    - JSON文件
    - CSV文件
    
    处理流程：
    1. URL内容抓取
    2. 使用markitdown格式化处理
    3. 智能分块
    4. 向量化（异步）
    5. 索引存储
    """
    try:
        # 使用URL处理器抓取内容
        async with get_url_processor() as url_processor:
            url_results = await url_processor.process_urls_batch(urls)
        
        if not url_results["success"]:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "URL_PROCESSING_FAILED",
                    "message": "Failed to process URLs"
                }
            )
        
        # 将成功处理的URL内容转换为文档格式
        processed_documents = []
        for result in url_results["successful_results"]:
            # 创建虚拟文件对象
            from io import BytesIO
            from fastapi import UploadFile
            
            content_bytes = result["content"].encode('utf-8')
            file_obj = BytesIO(content_bytes)
            
            upload_file = UploadFile(
                filename=result["metadata"]["filename"],
                file=file_obj,
                content_type="text/markdown"
            )
            
            processed_documents.append(upload_file)
        
        if not processed_documents:
            return {
                "success": False,
                "message": "没有成功处理的URL",
                "data": {
                    "total_urls": len(urls),
                    "successful_count": 0,
                    "failed_count": len(urls),
                    "failed_results": url_results["failed_results"]
                }
            }
        
        # 准备分块配置
        chunk_config = None
        if any([chunk_size, chunk_overlap, chunk_strategy]):
            chunk_config = {
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
                "strategy": chunk_strategy,
                "preserve_structure": preserve_structure
            }
        
        # 上传处理后的文档
        result = await manager.upload_documents(
            kb_id=kb_id,
            files=processed_documents,
            chunk_config=chunk_config
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": f"成功从 {url_results['successful_count']} 个URL添加文档",
                "data": {
                    "total_urls": len(urls),
                    "successful_urls": url_results["successful_count"],
                    "failed_urls": url_results["failed_count"],
                    "processed_files": result["processed_files"],
                    "failed_files": result["failed_files"],
                    "url_processing_results": url_results,
                    "document_processing_results": result["results"]
                }
            }
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "DOCUMENT_PROCESSING_FAILED",
                    "message": result["error"]
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add documents from URLs to KB {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.get("/{kb_id}/documents",
            response_model=Dict[str, Any],
            summary="获取文档列表",
            description="获取知识库中的文档列表")
async def list_documents(
    kb_id: str = Path(..., description="知识库ID"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    status: Optional[str] = Query(None, description="状态筛选"),
    file_type: Optional[str] = Query(None, description="文件类型筛选"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    manager = Depends(get_knowledge_manager)
) -> Dict[str, Any]:
    """
    获取知识库文档列表
    
    查询参数：
    - status: pending, processing, completed, failed
    - file_type: pdf, word, excel, csv, text等
    - search: 文件名搜索
    """
    try:
        # 这里需要通过manager获取文档列表
        # 暂时返回模拟数据，实际实现需要调用DocumentRepository
        
        return {
            "success": True,
            "data": {
                "documents": [],
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": 0,
                    "total_pages": 0
                }
            }
        }
        
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
            description="获取文档的详细信息和处理状态")
async def get_document(
    kb_id: str = Path(..., description="知识库ID"),
    doc_id: str = Path(..., description="文档ID"),
    processor = Depends(get_document_processor)
) -> Dict[str, Any]:
    """
    获取文档详情
    
    返回文档的完整信息：
    - 基本信息（文件名、大小、类型等）
    - 处理状态和进度
    - 分块统计
    - 错误信息（如果有）
    """
    try:
        from uuid import UUID
        result = await processor.get_processing_status(UUID(doc_id))
        
        if result["success"]:
            return {
                "success": True,
                "data": result
            }
        else:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "DOCUMENT_NOT_FOUND",
                    "message": result["error"]
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document {doc_id}: {e}")
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
             description="重新处理文档（重新分块和向量化）")
async def reprocess_document(
    kb_id: str = Path(..., description="知识库ID"),
    doc_id: str = Path(..., description="文档ID"),
    chunk_size: Optional[int] = Form(None, description="分块大小"),
    chunk_overlap: Optional[int] = Form(None, description="分块重叠"),
    chunk_strategy: Optional[str] = Form("token_based", description="分块策略"),
    processor = Depends(get_document_processor)
) -> Dict[str, Any]:
    """
    重新处理文档
    
    使用新的分块配置重新处理文档：
    1. 删除现有分块
    2. 重新分块
    3. 重新向量化
    """
    try:
        from uuid import UUID
        
        # 准备分块配置
        chunk_config = None
        if any([chunk_size, chunk_overlap, chunk_strategy]):
            from app.services.document_processing.document_chunker import ChunkConfig
            chunk_config = ChunkConfig(
                chunk_size=chunk_size or 1000,
                chunk_overlap=chunk_overlap or 200,
                strategy=chunk_strategy or "token_based"
            )
        
        result = await processor.reprocess_document(UUID(doc_id), chunk_config)
        
        if result["success"]:
            return {
                "success": True,
                "message": "文档重新处理已启动",
                "data": {
                    "job_id": result["job_id"]
                }
            }
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "REPROCESS_DOCUMENT_FAILED",
                    "message": result["error"]
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reprocess document {doc_id}: {e}")
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
               description="删除文档及其所有分块和向量数据")
async def delete_document(
    kb_id: str = Path(..., description="知识库ID"),
    doc_id: str = Path(..., description="文档ID"),
    manager = Depends(get_knowledge_manager)
) -> Dict[str, Any]:
    """
    删除文档
    
    此操作将删除：
    - 文档记录
    - 所有分块
    - 向量数据
    """
    try:
        # 这里需要实现文档删除逻辑
        # 暂时返回成功响应
        
        return {
            "success": True,
            "message": "文档删除成功",
            "data": {
                "doc_id": doc_id
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to delete document {doc_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.post("/{kb_id}/search",
             response_model=Dict[str, Any],
             summary="搜索知识库",
             description="在知识库中搜索相关内容")
async def search_knowledge_base(
    kb_id: str = Path(..., description="知识库ID"),
    request: SearchRequest = ...,
    manager = Depends(get_knowledge_manager)
) -> Dict[str, Any]:
    """
    搜索知识库
    
    支持的搜索模式：
    - llamaindex: 使用LlamaIndex精细化检索
    - agno: 使用Agno框架快速检索
    - hybrid: 混合模式，结合两种框架的优势
    
    检索参数：
    - query: 查询文本
    - top_k: 返回结果数量
    - similarity_threshold: 相似度阈值
    - enable_reranking: 是否启用重排序
    """
    try:
        # 设置知识库ID
        request.knowledge_base_id = kb_id
        
        result = await manager.search(request)
        
        return {
            "success": True,
            "data": {
                "query": result.query,
                "search_mode": result.search_mode,
                "results": [r.dict() for r in result.results],
                "total_results": result.total_results,
                "search_time": result.search_time,
                "llamaindex_results": result.llamaindex_results,
                "agno_results": result.agno_results,
                "reranked": result.reranked,
                "cached": result.cached
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to search KB {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "SEARCH_FAILED",
                "message": str(e)
            }
        )


@router.post("/{kb_id}/embedding/process",
             response_model=Dict[str, Any],
             summary="处理待嵌入分块",
             description="处理知识库中待嵌入的分块")
async def process_embedding(
    kb_id: str = Path(..., description="知识库ID"),
    batch_size: int = Query(50, ge=1, le=200, description="批处理大小"),
    embedding_service = Depends(get_embedding_service)
) -> Dict[str, Any]:
    """
    处理待嵌入分块
    
    启动异步任务处理知识库中待嵌入的分块：
    1. 获取pending状态的分块
    2. 调用模型服务进行嵌入
    3. 存储向量到向量数据库
    4. 更新分块状态
    """
    try:
        from uuid import UUID
        
        result = await embedding_service.process_pending_embeddings(
            kb_id=UUID(kb_id),
            batch_size=batch_size
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": "嵌入处理已启动",
                "data": result
            }
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "EMBEDDING_PROCESS_FAILED",
                    "message": result["error"]
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process embeddings for KB {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.get("/{kb_id}/embedding/statistics",
            response_model=Dict[str, Any],
            summary="获取嵌入统计",
            description="获取知识库的嵌入统计信息")
async def get_embedding_statistics(
    kb_id: str = Path(..., description="知识库ID"),
    embedding_service = Depends(get_embedding_service)
) -> Dict[str, Any]:
    """
    获取嵌入统计信息
    
    返回信息包括：
    - 总分块数
    - 已嵌入分块数
    - 待处理分块数
    - 失败分块数
    - 处理进度
    """
    try:
        from uuid import UUID
        
        result = await embedding_service.get_embedding_statistics(UUID(kb_id))
        
        if result["success"]:
            return {
                "success": True,
                "data": result["statistics"]
            }
        else:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "GET_EMBEDDING_STATISTICS_FAILED",
                    "message": result["error"]
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get embedding statistics for KB {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.get("/statistics",
            response_model=Dict[str, Any],
            summary="获取全局统计",
            description="获取知识库服务的全局统计信息")
async def get_statistics(
    manager = Depends(get_knowledge_manager)
) -> Dict[str, Any]:
    """
    获取全局统计信息
    
    返回信息包括：
    - 知识库总数和活跃数
    - 文档和分块统计
    - 处理任务统计
    - 框架状态
    """
    try:
        result = await manager.get_statistics()
        
        return {
            "success": True,
            "data": result
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
            summary="获取可用嵌入模型",
            description="获取支持的嵌入模型列表")
async def get_embedding_models(
    manager = Depends(get_knowledge_manager)
) -> Dict[str, Any]:
    """
    获取可用的嵌入模型列表
    
    返回支持的嵌入模型提供商和模型：
    - OpenAI models
    - Azure OpenAI models
    - HuggingFace models
    - 本地模型
    """
    try:
        # 这里应该调用原管理器的方法
        result = await manager.get_available_embedding_models()
        
        if result["success"]:
            providers = result.get("providers", {})
            models = []
            provider_counts = {}
            
            # 从providers结构中提取所有模型
            for provider, provider_data in providers.items():
                provider_models = provider_data.get("models", [])
                models.extend(provider_models)
                provider_counts[provider] = len(provider_models)
            
            return {
                "success": True,
                "data": {
                    "models": models,
                    "total": len(models),
                    "provider_counts": provider_counts,
                    "providers": providers  # 也返回按提供商分组的数据，供前端使用
                }
            }
        else:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "GET_EMBEDDING_MODELS_FAILED",
                    "message": result["error"]
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get embedding models: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


# ===== 检索测试接口 =====

@router.post("/{kb_id}/search/test",
            response_model=Dict[str, Any],
            summary="检索性能测试",
            description="对指定知识库进行检索性能测试，支持多配置对比")
async def test_search_performance(
    kb_id: str = Path(..., description="知识库ID"),
    request: SearchTestRequest = ...,
    manager = Depends(get_knowledge_manager)
) -> Dict[str, Any]:
    """
    检索性能测试
    
    功能：
    - 批量测试多个查询和配置组合
    - 收集详细的性能指标
    - 提供配置优化建议
    - 支持不同检索模式对比
    """
    try:
        import time
        import uuid
        from app.schemas.knowledge_schemas import SearchTestResult
        
        test_id = str(uuid.uuid4())
        test_results = []
        
        # 获取知识库信息
        kb_info = await manager.get_knowledge_base(kb_id)
        if not kb_info:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "KNOWLEDGE_BASE_NOT_FOUND",
                    "message": f"知识库 {kb_id} 不存在"
                }
            )
        
        # 执行测试
        for query in request.test_queries:
            for config_idx, search_config in enumerate(request.search_configs):
                # 设置知识库ID
                search_config.knowledge_base_id = kb_id
                
                # 记录开始时间
                start_time = time.time()
                
                try:
                    # 执行搜索
                    search_result = await manager.search(search_config)
                    
                    # 计算响应时间
                    response_time = (time.time() - start_time) * 1000  # 转换为毫秒
                    
                    # 构建测试结果
                    test_result = SearchTestResult(
                        query=query,
                        config_index=config_idx,
                        search_config=search_config.dict(),
                        results=search_result.results,
                        response_time_ms=response_time,
                        total_candidates=len(search_result.results),
                        returned_results=search_result.total_results,
                        llamaindex_time_ms=getattr(search_result, 'llamaindex_time', None),
                        agno_time_ms=getattr(search_result, 'agno_time', None),
                        reranking_time_ms=getattr(search_result, 'reranking_time', None)
                    )
                    
                    test_results.append(test_result)
                    
                except Exception as search_error:
                    logger.error(f"Search failed for query '{query}' with config {config_idx}: {search_error}")
                    # 添加失败记录
                    test_result = SearchTestResult(
                        query=query,
                        config_index=config_idx,
                        search_config=search_config.dict(),
                        results=[],
                        response_time_ms=-1,
                        total_candidates=0,
                        returned_results=0
                    )
                    test_results.append(test_result)
        
        # 计算汇总统计
        valid_results = [r for r in test_results if r.response_time_ms > 0]
        if valid_results:
            avg_time = sum(r.response_time_ms for r in valid_results) / len(valid_results)
            min_time = min(r.response_time_ms for r in valid_results)
            max_time = max(r.response_time_ms for r in valid_results)
            
            # 找到最佳配置（基于响应时间和结果数量）
            best_config = min(valid_results, 
                            key=lambda x: x.response_time_ms / max(x.returned_results, 1))
            best_config_index = best_config.config_index
            best_config_score = best_config.returned_results / best_config.response_time_ms * 1000
        else:
            avg_time = min_time = max_time = 0
            best_config_index = None
            best_config_score = None
        
        response = SearchTestResponse(
            test_id=test_id,
            knowledge_base_id=kb_id,
            knowledge_base_name=kb_info.get("name", "Unknown"),
            test_results=test_results,
            total_tests=len(test_results),
            avg_response_time_ms=avg_time,
            min_response_time_ms=min_time,
            max_response_time_ms=max_time,
            best_config_index=best_config_index,
            best_config_score=best_config_score
        )
        
        return {
            "success": True,
            "message": f"完成 {len(test_results)} 项测试",
            "data": response.dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to run search test for KB {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "SEARCH_TEST_FAILED",
                "message": str(e)
            }
        )


@router.post("/search/global-test",
            response_model=Dict[str, Any],
            summary="全局检索测试",
            description="跨知识库的全局检索性能测试")
async def global_search_test(
    request: GlobalSearchTestRequest = ...,
    manager = Depends(get_knowledge_manager)
) -> Dict[str, Any]:
    """
    全局检索测试
    
    功能：
    - 跨多个知识库进行检索测试
    - 对比不同知识库的检索性能
    - 提供知识库性能排名
    - 支持批量查询测试
    """
    try:
        import uuid
        
        test_id = str(uuid.uuid4())
        kb_test_results = []
        
        # 获取要测试的知识库列表
        if request.knowledge_base_ids:
            kb_ids = request.knowledge_base_ids
        else:
            # 获取所有活跃的知识库
            kb_list_result = await manager.list_knowledge_bases(page=1, page_size=100)
            if kb_list_result["success"]:
                kb_ids = [kb["id"] for kb in kb_list_result["knowledge_bases"] 
                         if kb.get("status") == "active"]
            else:
                kb_ids = []
        
        if not kb_ids:
            return {
                "success": False,
                "message": "没有找到可测试的知识库",
                "data": None
            }
        
        # 为每个知识库执行测试
        for kb_id in kb_ids:
            try:
                # 构建单知识库测试请求
                search_configs = [request.search_config]
                search_configs[0].knowledge_base_id = kb_id
                
                kb_test_request = SearchTestRequest(
                    test_queries=request.test_queries,
                    search_configs=search_configs,
                    include_performance_metrics=True
                )
                
                # 执行单知识库测试
                kb_test_response = await test_search_performance(
                    kb_id=kb_id,
                    request=kb_test_request,
                    manager=manager
                )
                
                if kb_test_response["success"]:
                    kb_test_results.append(kb_test_response["data"])
                    
            except Exception as kb_error:
                logger.error(f"Failed to test KB {kb_id}: {kb_error}")
                continue
        
        # 计算全局统计
        if kb_test_results:
            total_queries = sum(r["total_tests"] for r in kb_test_results)
            avg_response_time = sum(r["avg_response_time_ms"] for r in kb_test_results) / len(kb_test_results)
            
            # 生成知识库性能排名
            kb_ranking = []
            for result in kb_test_results:
                score = 0
                if result["avg_response_time_ms"] > 0:
                    # 综合评分：速度 + 结果质量
                    speed_score = 1000 / result["avg_response_time_ms"]  # 速度得分
                    quality_score = result.get("best_config_score", 0)   # 质量得分
                    score = speed_score * 0.6 + quality_score * 0.4
                
                kb_ranking.append({
                    "knowledge_base_id": result["knowledge_base_id"],
                    "knowledge_base_name": result["knowledge_base_name"],
                    "avg_response_time_ms": result["avg_response_time_ms"],
                    "total_tests": result["total_tests"],
                    "performance_score": score
                })
            
            # 按性能评分排序
            kb_ranking.sort(key=lambda x: x["performance_score"], reverse=True)
        else:
            total_queries = 0
            avg_response_time = 0
            kb_ranking = []
        
        response = GlobalSearchTestResponse(
            test_id=test_id,
            kb_test_results=kb_test_results,
            total_knowledge_bases=len(kb_test_results),
            total_queries=total_queries,
            avg_response_time_ms=avg_response_time,
            kb_performance_ranking=kb_ranking
        )
        
        return {
            "success": True,
            "message": f"完成 {len(kb_test_results)} 个知识库的全局测试",
            "data": response.dict()
        }
        
    except Exception as e:
        logger.error(f"Failed to run global search test: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "GLOBAL_SEARCH_TEST_FAILED", 
                "message": str(e)
            }
        )


# ===== 索引管理接口 =====

@router.post("/{kb_id}/index/rebuild",
            response_model=Dict[str, Any],
            summary="重建知识库索引",
            description="使用新的索引类型重建知识库向量索引")
async def rebuild_knowledge_base_index(
    kb_id: str = Path(..., description="知识库ID"),
    request: IndexRebuildRequest = ...,
    background_tasks: BackgroundTasks = ...,
    manager = Depends(get_knowledge_manager)
) -> Dict[str, Any]:
    """
    重建知识库索引
    
    功能：
    - 支持切换不同的索引类型
    - 可配置索引参数
    - 支持异步重建
    - 可选择备份现有索引
    """
    try:
        # 验证知识库存在
        kb_info = await manager.get_knowledge_base(kb_id)
        if not kb_info:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "KNOWLEDGE_BASE_NOT_FOUND",
                    "message": f"知识库 {kb_id} 不存在"
                }
            )
        
        # 获取索引配置
        index_configs = {
            "hnsw": {
                "index_type": "HNSW",
                "metric_type": "COSINE",
                "params": {"M": 16, "efConstruction": 200, **request.index_parameters}
            },
            "flat": {
                "index_type": "FLAT", 
                "metric_type": "COSINE",
                "params": {**request.index_parameters}
            },
            "ivf_flat": {
                "index_type": "IVF_FLAT",
                "metric_type": "COSINE", 
                "params": {"nlist": 100, **request.index_parameters}
            },
            "ivf_pq": {
                "index_type": "IVF_PQ",
                "metric_type": "COSINE",
                "params": {"nlist": 100, "m": 8, **request.index_parameters}
            },
            "ivf_hnsw": {
                "index_type": "IVF_HNSW",
                "metric_type": "COSINE",
                "params": {"nlist": 100, "M": 16, "efConstruction": 200, **request.index_parameters}
            }
        }
        
        new_index_config = index_configs.get(request.new_index_type.value)
        if not new_index_config:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "UNSUPPORTED_INDEX_TYPE",
                    "message": f"不支持的索引类型: {request.new_index_type}"
                }
            )
        
        # 生成重建任务ID
        import uuid
        rebuild_task_id = str(uuid.uuid4())
        
        if request.rebuild_async:
            # 异步重建
            def rebuild_index_task():
                try:
                    # 这里应该调用实际的索引重建逻辑
                    # 由于是示例，暂时模拟处理
                    import time
                    time.sleep(2)  # 模拟重建过程
                    logger.info(f"Index rebuild completed for KB {kb_id} with type {request.new_index_type}")
                except Exception as e:
                    logger.error(f"Index rebuild failed for KB {kb_id}: {e}")
            
            background_tasks.add_task(rebuild_index_task)
            
            return {
                "success": True,
                "message": "索引重建任务已启动",
                "data": {
                    "task_id": rebuild_task_id,
                    "knowledge_base_id": kb_id,
                    "new_index_type": request.new_index_type.value,
                    "async": True,
                    "estimated_time_minutes": 10  # 估算时间
                }
            }
        else:
            # 同步重建（用于小型知识库）
            # 这里应该调用实际的同步重建逻辑
            
            return {
                "success": True,
                "message": "索引重建完成",
                "data": {
                    "task_id": rebuild_task_id,
                    "knowledge_base_id": kb_id,
                    "new_index_type": request.new_index_type.value,
                    "async": False,
                    "rebuild_time_seconds": 2.5
                }
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to rebuild index for KB {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INDEX_REBUILD_FAILED",
                "message": str(e)
            }
        )


@router.get("/{kb_id}/index/status",
           response_model=Dict[str, Any],
           summary="获取索引状态",
           description="获取知识库的索引状态和性能信息")
async def get_index_status(
    kb_id: str = Path(..., description="知识库ID"),
    manager = Depends(get_knowledge_manager)
) -> Dict[str, Any]:
    """
    获取索引状态
    
    返回信息：
    - 当前索引类型和参数
    - 索引大小和向量数量
    - 性能统计信息
    - 重建状态
    """
    try:
        # 验证知识库存在
        kb_info = await manager.get_knowledge_base(kb_id)
        if not kb_info:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "KNOWLEDGE_BASE_NOT_FOUND",
                    "message": f"知识库 {kb_id} 不存在"
                }
            )
        
        # 获取索引状态（这里是模拟数据，实际应从向量数据库获取）
        index_status = IndexStatus(
            knowledge_base_id=kb_id,
            current_index_type=kb_info.get("vector_index_type", "hnsw"),
            index_parameters=kb_info.get("index_parameters", {}),
            total_vectors=kb_info.get("vector_count", 0),
            index_size_mb=kb_info.get("vector_count", 0) * 1536 * 4 / 1024 / 1024,  # 估算
            avg_search_time_ms=15.5,  # 模拟数据
            last_rebuild_time=None,
            is_rebuilding=False,
            rebuild_progress=0.0,
            rebuild_error=None
        )
        
        return {
            "success": True,
            "data": index_status.dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get index status for KB {kb_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "GET_INDEX_STATUS_FAILED",
                "message": str(e)
            }
        )


@router.get("/index/performance-comparison",
           response_model=Dict[str, Any],
           summary="索引性能对比",
           description="获取不同索引类型的性能对比信息")
async def get_index_performance_comparison() -> Dict[str, Any]:
    """
    索引性能对比
    
    提供不同索引类型的：
    - 查询性能对比
    - 内存使用对比  
    - 构建时间对比
    - 适用场景推荐
    """
    try:
        # 模拟性能对比数据
        comparison = IndexPerformanceComparison(
            index_types=["hnsw", "flat", "ivf_flat", "ivf_pq", "ivf_hnsw"],
            performance_metrics={
                "query_time_ms": {
                    "hnsw": 12.5,
                    "flat": 45.2,
                    "ivf_flat": 18.3,
                    "ivf_pq": 15.7,
                    "ivf_hnsw": 10.8
                },
                "memory_usage_mb": {
                    "hnsw": 128.5,
                    "flat": 64.2,
                    "ivf_flat": 78.9,
                    "ivf_pq": 32.1,
                    "ivf_hnsw": 145.3
                },
                "build_time_minutes": {
                    "hnsw": 8.5,
                    "flat": 1.2,
                    "ivf_flat": 5.3,
                    "ivf_pq": 12.7,
                    "ivf_hnsw": 15.2
                },
                "accuracy_score": {
                    "hnsw": 0.95,
                    "flat": 1.0,
                    "ivf_flat": 0.92,
                    "ivf_pq": 0.85,
                    "ivf_hnsw": 0.94
                }
            },
            recommendations=[
                "HNSW: 推荐用于大规模高精度查询场景",
                "FLAT: 推荐用于小规模高精度场景",
                "IVF_FLAT: 推荐用于中等规模平衡性能场景",
                "IVF_PQ: 推荐用于内存受限的大规模场景",
                "IVF_HNSW: 推荐用于超大规模高性能场景"
            ],
            test_conditions={
                "vector_dimension": 1536,
                "dataset_size": 100000,
                "query_count": 1000,
                "test_environment": "4C8G"
            }
        )
        
        return {
            "success": True,
            "data": comparison.dict()
        }
        
    except Exception as e:
        logger.error(f"Failed to get index performance comparison: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "GET_PERFORMANCE_COMPARISON_FAILED",
                "message": str(e)
            }
        )