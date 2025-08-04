"""
文档上传路由
集成Redis队列的异步文档处理接口
"""

import os
import uuid
import json
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, File, UploadFile, Form, Path as PathParam, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config.settings import settings
from app.core.enhanced_knowledge_manager import get_unified_knowledge_manager
from app.utils.minio_client import upload_to_minio, test_minio_connection
from app.queues.redis_queue import get_redis_queue
from app.queues.task_models import ProcessingTaskModel, TaskStatus, TaskQueryModel
from app.queues.task_processor import get_task_processor
from app.core.web_crawler_manager import get_web_crawler_manager, CrawlConfig, CrawlMode
from app.models.database import get_db
from sqlalchemy.orm import Session

import logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge-bases", tags=["文档上传"])


@router.post("/{kb_id}/documents/upload-async",
             response_model=Dict[str, Any],
             summary="异步上传文档",
             description="上传文档到知识库并通过Redis队列异步处理")
async def upload_documents_async(
    kb_id: str = PathParam(..., description="知识库ID"),
    files: List[UploadFile] = File(..., description="要上传的文档文件"),
    user_id: Optional[str] = Form(None, description="用户ID（用于SSE推送）"),
    splitter_strategy_id: Optional[str] = Form(None, description="切分策略ID"),
    chunk_size: Optional[int] = Form(None, description="分块大小（覆盖策略配置）"),
    chunk_overlap: Optional[int] = Form(None, description="分块重叠（覆盖策略配置）"),
    chunk_strategy: Optional[str] = Form(None, description="分块策略（覆盖策略配置）"),
    preserve_structure: Optional[bool] = Form(None, description="保留文档结构（覆盖策略配置）"),
    enable_async_processing: bool = Form(True, description="启用异步处理"),
    callback_url: Optional[str] = Form(None, description="处理完成回调URL"),
    folder_id: Optional[str] = Form(None, description="目标文件夹ID")
) -> Dict[str, Any]:
    """
    异步上传文档到知识库
    
    处理流程：
    1. 文件验证和上传到MinIO
    2. 创建处理任务加入Redis队列
    3. 返回任务ID用于跟踪进度
    4. 后台异步处理文档
    
    支持的文件格式：
    - PDF文档 (.pdf)
    - Word文档 (.doc, .docx)
    - 纯文本文件 (.txt)
    - Markdown文件 (.md)
    - HTML文件 (.html)
    """
    try:
        # 验证知识库是否存在
        knowledge_manager = get_unified_knowledge_manager()
        kb_exists = await knowledge_manager.get_knowledge_base(kb_id)
        if not kb_exists:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "KNOWLEDGE_BASE_NOT_FOUND",
                    "message": f"知识库 {kb_id} 不存在"
                }
            )
        
        # 获取切分策略配置
        from app.core.splitter_strategy_manager import get_splitter_strategy_manager
        strategy_manager = get_splitter_strategy_manager()
        
        effective_splitter_config = {}
        
        # 如果指定了策略ID，使用指定策略
        if splitter_strategy_id:
            strategy = strategy_manager.get_strategy_by_id(splitter_strategy_id)
            if strategy:
                effective_splitter_config = strategy["config"].copy()
                # 记录策略使用
                strategy_manager.record_strategy_usage(splitter_strategy_id, kb_id)
            else:
                logger.warning(f"指定的切分策略不存在: {splitter_strategy_id}")
        
        # 如果策略不存在，使用知识库默认策略
        if not effective_splitter_config:
            # 这里需要从knowledge_base获取默认策略
            # 暂时使用基础配置
            from app.models.splitter_strategy import SplitterStrategy
            effective_splitter_config = SplitterStrategy.get_default_config("basic")
        
        # 用户参数覆盖策略配置
        if chunk_size is not None:
            effective_splitter_config["chunk_size"] = chunk_size
        if chunk_overlap is not None:
            effective_splitter_config["chunk_overlap"] = chunk_overlap
        if chunk_strategy is not None:
            effective_splitter_config["chunk_strategy"] = chunk_strategy
        if preserve_structure is not None:
            effective_splitter_config["preserve_structure"] = preserve_structure
        
        # 验证MinIO连接
        if not test_minio_connection():
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "STORAGE_UNAVAILABLE",
                    "message": "文件存储服务不可用"
                }
            )
        
        # 获取Redis队列
        redis_queue = get_redis_queue()
        
        uploaded_tasks = []
        
        for file in files:
            try:
                # 1. 文件验证
                await _validate_upload_file(file)
                
                # 2. 生成文件路径
                file_id = str(uuid.uuid4())
                file_extension = os.path.splitext(file.filename)[1]
                stored_filename = f"{kb_id}/{file_id}{file_extension}"
                
                # 3. 上传文件到MinIO
                file_content = await file.read()
                file_size = len(file_content)
                
                # 重置文件指针
                await file.seek(0)
                
                # 创建BytesIO对象
                import io
                file_data = io.BytesIO(file_content)
                
                success = upload_to_minio(
                    stored_filename,
                    file_data,
                    file.content_type or "application/octet-stream"
                )
                
                if not success:
                    raise HTTPException(
                        status_code=500,
                        detail={
                            "error": "UPLOAD_FAILED",
                            "message": f"文件 {file.filename} 上传失败"
                        }
                    )
                
                # 4. 创建处理任务
                processing_task = ProcessingTaskModel(
                    user_id=user_id,
                    kb_id=kb_id,
                    kb_name=kb_exists.get("name", ""),
                    file_info={
                        "file_id": file_id,
                        "stored_filename": stored_filename,
                        "content_type": file.content_type,
                        "upload_time": datetime.now().isoformat(),
                        "folder_id": folder_id
                    },
                    file_path=stored_filename,
                    original_filename=file.filename,
                    file_size=file_size,
                    file_type=file_extension,
                    splitter_strategy_id=splitter_strategy_id,
                    custom_splitter_config=effective_splitter_config,
                    processing_options={
                        "enable_async_processing": enable_async_processing,
                        "generate_embeddings": True,
                        "store_vectors": True,
                        "folder_id": folder_id
                    },
                    callback_url=callback_url
                )
                
                # 5. 提交任务到Task Manager Service
                import httpx
                
                task_data = {
                    "task_type": "document_processing",
                    "kb_id": kb_id,
                    "priority": "normal",
                    "payload": {
                        "task_id": processing_task.task_id,
                        "user_id": user_id,
                        "kb_id": kb_id,
                        "kb_name": kb_exists.get("name", ""),
                        "file_info": processing_task.file_info,
                        "file_path": stored_filename,
                        "original_filename": file.filename,
                        "file_size": file_size,
                        "file_type": file_extension,
                        "splitter_strategy_id": splitter_strategy_id,
                        "custom_splitter_config": effective_splitter_config,
                        "processing_options": processing_task.processing_options,
                        "callback_url": callback_url,
                        "service_name": "knowledge-service",
                        "source": "upload_documents_async"
                    },
                    "max_retries": 3,
                    "timeout": 300
                }
                
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            "http://localhost:8084/api/v1/tasks",
                            json=task_data,
                            timeout=10.0
                        )
                        
                        if response.status_code not in [200, 201]:
                            raise HTTPException(
                                status_code=500,
                                detail={
                                    "error": "TASK_SUBMISSION_FAILED",
                                    "message": f"任务提交到Task Manager失败: {response.text}"
                                }
                            )
                        
                        # 获取task-manager返回的任务信息
                        task_response = response.json()
                        actual_task_id = task_response.get("id", processing_task.task_id)
                        
                        logger.info(f"任务 {processing_task.task_id} 已提交到Task Manager，实际任务ID: {actual_task_id}")
                        
                        # 更新任务ID为task-manager返回的ID
                        processing_task.task_id = actual_task_id
                        
                except httpx.RequestError as e:
                    raise HTTPException(
                        status_code=500,
                        detail={
                            "error": "TASK_MANAGER_CONNECTION_FAILED",
                            "message": f"无法连接到Task Manager: {str(e)}"
                        }
                    )
                
                uploaded_tasks.append({
                    "task_id": processing_task.task_id,
                    "filename": file.filename,
                    "file_size": file_size,
                    "status": TaskStatus.PENDING.value,
                    "message": "文件已上传，等待处理"
                })
                
                logger.info(f"文件 {file.filename} 上传成功，任务ID: {processing_task.task_id}")
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"处理文件 {file.filename} 时出错: {e}")
                uploaded_tasks.append({
                    "filename": file.filename,
                    "status": "failed",
                    "error": str(e)
                })
        
        # 统计结果
        successful_uploads = [task for task in uploaded_tasks if "task_id" in task]
        failed_uploads = [task for task in uploaded_tasks if "error" in task]
        
        return {
            "success": True,
            "message": f"上传完成，成功 {len(successful_uploads)} 个，失败 {len(failed_uploads)} 个",
            "data": {
                "kb_id": kb_id,
                "total_files": len(files),
                "successful_uploads": len(successful_uploads),
                "failed_uploads": len(failed_uploads),
                "tasks": uploaded_tasks,
                "upload_time": datetime.now().isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文档上传失败: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "UPLOAD_ERROR",
                "message": str(e)
            }
        )


@router.get("/{kb_id}/upload-tasks",
            response_model=Dict[str, Any],
            summary="获取上传任务列表",
            description="获取知识库的文档上传任务状态")
async def get_upload_tasks(
    kb_id: str = PathParam(..., description="知识库ID"),
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> Dict[str, Any]:
    """获取知识库的上传任务列表"""
    try:
        redis_queue = get_redis_queue()
        
        # 构建查询条件
        query = TaskQueryModel(
            task_types=["document_processing"],
            limit=limit,
            offset=offset
        )
        
        if status:
            try:
                query.statuses = [TaskStatus(status)]
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "INVALID_STATUS",
                        "message": f"无效的状态值: {status}"
                    }
                )
        
        # 查询任务
        tasks = await redis_queue.query_tasks(query)
        
        # 过滤属于指定知识库的任务
        kb_tasks = []
        for task in tasks:
            if hasattr(task, 'kb_id') and task.kb_id == kb_id:
                kb_tasks.append({
                    "task_id": task.task_id,
                    "status": task.status.value,
                    "progress": task.progress,
                    "message": task.message,
                    "error_message": task.error_message,
                    "created_at": task.created_at.isoformat(),
                    "started_at": task.started_at.isoformat() if task.started_at else None,
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                    "file_info": getattr(task, 'file_info', {}),
                    "original_filename": getattr(task, 'original_filename', ''),
                    "file_size": getattr(task, 'file_size', 0),
                    "chunks_count": getattr(task, 'chunks_count', 0),
                    "embedding_count": getattr(task, 'embedding_count', 0)
                })
        
        return {
            "success": True,
            "data": {
                "kb_id": kb_id,
                "total_tasks": len(kb_tasks),
                "tasks": kb_tasks,
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "has_more": len(tasks) == limit
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取上传任务失败: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "QUERY_ERROR",
                "message": str(e)
            }
        )


@router.get("/tasks/{task_id}/status",
            response_model=Dict[str, Any],
            summary="获取任务状态",
            description="获取指定任务的详细状态")
async def get_task_status(
    task_id: str = PathParam(..., description="任务ID")
) -> Dict[str, Any]:
    """获取任务状态"""
    try:
        redis_queue = get_redis_queue()
        task = await redis_queue.get_task(task_id)
        
        if not task:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "TASK_NOT_FOUND",
                    "message": f"任务 {task_id} 不存在"
                }
            )
        
        return {
            "success": True,
            "data": {
                "task_id": task.task_id,
                "task_type": task.task_type,
                "status": task.status.value,
                "progress": task.progress,
                "message": task.message,
                "error_message": task.error_message,
                "created_at": task.created_at.isoformat(),
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "metadata": task.metadata
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务状态失败: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "STATUS_ERROR",
                "message": str(e)
            }
        )


@router.delete("/tasks/{task_id}",
               response_model=Dict[str, Any],
               summary="取消任务",
               description="取消指定的处理任务")
async def cancel_task(
    task_id: str = PathParam(..., description="任务ID"),
    reason: str = Form("用户取消", description="取消原因")
) -> Dict[str, Any]:
    """取消任务"""
    try:
        redis_queue = get_redis_queue()
        
        # 检查任务是否存在
        task = await redis_queue.get_task(task_id)
        if not task:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "TASK_NOT_FOUND",
                    "message": f"任务 {task_id} 不存在"
                }
            )
        
        # 检查任务状态
        if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "TASK_CANNOT_CANCEL",
                    "message": f"任务状态为 {task.status.value}，无法取消"
                }
            )
        
        # 取消任务
        success = await redis_queue.cancel_task(task_id, reason)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "CANCEL_FAILED",
                    "message": "取消任务失败"
                }
            )
        
        return {
            "success": True,
            "message": f"任务 {task_id} 已取消",
            "data": {
                "task_id": task_id,
                "reason": reason,
                "cancelled_at": datetime.now().isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取消任务失败: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "CANCEL_ERROR",
                "message": str(e)
            }
        )


@router.get("/{kb_id}/upload-status/stream",
            summary="实时获取上传状态",
            description="通过SSE实时推送知识库上传任务状态")
async def stream_upload_status(
    kb_id: str = PathParam(..., description="知识库ID")
):
    """通过SSE实时推送上传状态"""
    async def event_stream():
        redis_queue = get_redis_queue()
        
        while True:
            try:
                # 获取知识库相关任务
                tasks = await redis_queue.query_tasks(
                    TaskQueryModel(
                        task_types=["document_processing"],
                        limit=100
                    )
                )
                
                # 过滤知识库任务
                kb_tasks = [
                    task for task in tasks 
                    if hasattr(task, 'kb_id') and task.kb_id == kb_id
                ]
                
                # 构建状态数据
                status_data = {
                    "kb_id": kb_id,
                    "timestamp": datetime.now().isoformat(),
                    "tasks": [
                        {
                            "task_id": task.task_id,
                            "status": task.status.value,
                            "progress": task.progress,
                            "message": task.message,
                            "filename": getattr(task, 'original_filename', ''),
                        }
                        for task in kb_tasks
                    ]
                }
                
                yield f"data: {json.dumps(status_data)}\n\n"
                await asyncio.sleep(2)  # 每2秒推送一次
                
            except Exception as e:
                logger.error(f"SSE推送失败: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                break
    
    return StreamingResponse(
        event_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )


async def _validate_upload_file(file: UploadFile):
    """验证上传文件"""
    # 检查文件名
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_FILENAME",
                "message": "文件名不能为空"
            }
        )
    
    # 检查文件类型
    allowed_extensions = ['.pdf', '.txt', '.docx', '.doc', '.md', '.html', '.csv', '.json']
    file_extension = os.path.splitext(file.filename)[1].lower()
    
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "UNSUPPORTED_FILE_TYPE",
                "message": f"不支持的文件类型: {file_extension}",
                "supported_types": allowed_extensions
            }
        )
    
    # 检查文件大小
    file_content = await file.read()
    await file.seek(0)  # 重置文件指针
    
    max_file_size = 100 * 1024 * 1024  # 100MB
    if len(file_content) > max_file_size:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "FILE_TOO_LARGE",
                "message": f"文件大小超过限制: {len(file_content)} bytes",
                "max_size": max_file_size
            }
        )
    
    # 检查文件内容
    if len(file_content) == 0:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "EMPTY_FILE",
                "message": "文件内容为空"
            }
        )


# ===============================
# URL导入爬虫 API
# ===============================

class URLImportRequest(BaseModel):
    """URL导入请求模型"""
    urls: List[str]
    crawl_mode: str = "single_url"  # single_url, url_list, sitemap, domain_crawl
    max_pages: int = 50
    max_depth: int = 2
    concurrent_requests: int = 5
    request_delay: float = 1.0
    output_format: str = "markdown"
    include_metadata: bool = True
    use_llamaindex: bool = True
    use_trafilatura: bool = True
    content_filters: Optional[List[str]] = None
    content_selectors: Optional[List[str]] = None
    min_content_length: int = 100
    max_content_length: int = 100000
    custom_headers: Optional[Dict[str, str]] = None
    follow_redirects: bool = True
    respect_robots_txt: bool = True
    folder_id: Optional[str] = None
    description: Optional[str] = None
    enable_async_processing: bool = True

@router.post("/{kb_id}/documents/import-urls",
             response_model=Dict[str, Any],
             summary="URL导入爬虫",
             description="从URL导入内容到知识库，支持单个URL、URL列表、站点地图和域名爬取")
async def import_urls_to_knowledge_base(
    kb_id: str = PathParam(..., description="知识库ID"),
    request: URLImportRequest = ...,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    URL导入爬虫功能
    
    支持的导入模式：
    - single_url: 单个URL
    - url_list: URL列表
    - sitemap: 站点地图
    - domain_crawl: 域名爬取（有限深度）
    
    处理流程：
    1. 验证URL和知识库
    2. 配置爬虫参数
    3. 执行爬虫和内容提取
    4. 内容清洗和Markdown转换
    5. 生成任务进入处理队列
    """
    try:
        # 验证知识库是否存在
        knowledge_manager = get_unified_knowledge_manager()
        kb_exists = await knowledge_manager.get_knowledge_base(kb_id)
        if not kb_exists:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "KNOWLEDGE_BASE_NOT_FOUND",
                    "message": f"知识库 {kb_id} 不存在"
                }
            )
        
        # 验证URL格式
        if not request.urls:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "EMPTY_URL_LIST",
                    "message": "URL列表不能为空"
                }
            )
        
        # 验证爬虫模式
        try:
            crawl_mode = CrawlMode(request.crawl_mode)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "INVALID_CRAWL_MODE",
                    "message": f"无效的爬虫模式: {request.crawl_mode}",
                    "supported_modes": [mode.value for mode in CrawlMode]
                }
            )
        
        # 构建爬虫配置
        crawl_config = CrawlConfig(
            mode=crawl_mode,
            max_pages=request.max_pages,
            max_depth=request.max_depth,
            concurrent_requests=request.concurrent_requests,
            request_delay=request.request_delay,
            content_filters=request.content_filters,
            content_selectors=request.content_selectors,
            min_content_length=request.min_content_length,
            max_content_length=request.max_content_length,
            output_format=request.output_format,
            include_metadata=request.include_metadata,
            headers=request.custom_headers,
            follow_redirects=request.follow_redirects,
            respect_robots_txt=request.respect_robots_txt,
            use_llamaindex=request.use_llamaindex,
            use_trafilatura=request.use_trafilatura
        )
        
        # 执行爬虫
        async with get_web_crawler_manager(db) as crawler:
            crawl_result = await crawler.crawl_urls(
                kb_id=kb_id,
                urls=request.urls,
                config=crawl_config
            )
        
        if not crawl_result["success"]:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "CRAWL_FAILED",
                    "message": "爬虫执行失败",
                    "details": crawl_result
                }
            )
        
        # 处理爬虫结果，为每个成功的结果创建处理任务
        redis_queue = get_redis_queue()
        processing_tasks = []
        
        for result in crawl_result["results"]:
            try:
                # 生成文件ID和存储路径
                file_id = str(uuid.uuid4())
                stored_filename = f"{kb_id}/crawled/{file_id}.md"
                
                # 将Markdown内容上传到MinIO
                import io
                content_data = io.BytesIO(result.markdown_content.encode('utf-8'))
                
                success = upload_to_minio(
                    stored_filename,
                    content_data,
                    "text/markdown"
                )
                
                if not success:
                    logger.error(f"Failed to upload crawled content for URL: {result.url}")
                    continue
                
                # 创建处理任务
                processing_task = ProcessingTaskModel(
                    kb_id=kb_id,
                    kb_name=kb_exists.get("name", ""),
                    file_info={
                        "file_id": file_id,
                        "stored_filename": stored_filename,
                        "content_type": "text/markdown",
                        "source_url": result.url,
                        "crawl_time": result.crawl_time,
                        "content_hash": result.content_hash,
                        "upload_time": datetime.now().isoformat()
                    },
                    file_path=stored_filename,
                    original_filename=f"{result.title or 'Untitled'}.md",
                    file_size=result.file_size,
                    file_type=".md",
                    custom_splitter_config={
                        "chunk_size": 1000,
                        "chunk_overlap": 200,
                        "chunk_strategy": "semantic",
                        "preserve_structure": True
                    },
                    processing_options={
                        "enable_async_processing": request.enable_async_processing,
                        "generate_embeddings": True,
                        "store_vectors": True,
                        "source_type": "url_import",
                        "source_url": result.url
                    },
                    metadata={
                        "crawl_config": crawl_config.__dict__,
                        "crawl_metadata": result.metadata,
                        "folder_id": request.folder_id,
                        "description": request.description
                    }
                )
                
                # 加入处理队列
                success = await redis_queue.enqueue_task(processing_task, "document_processing")
                
                if success:
                    processing_tasks.append({
                        "task_id": processing_task.task_id,
                        "url": result.url,
                        "title": result.title,
                        "content_length": len(result.content),
                        "markdown_length": len(result.markdown_content),
                        "status": TaskStatus.PENDING.value,
                        "message": "URL内容已爬取，等待处理"
                    })
                    logger.info(f"URL {result.url} 爬取成功，任务ID: {processing_task.task_id}")
                else:
                    logger.error(f"Failed to enqueue task for URL: {result.url}")
                
            except Exception as e:
                logger.error(f"处理爬虫结果时出错 {result.url}: {e}")
                continue
        
        # 统计结果
        return {
            "success": True,
            "message": f"URL导入完成，成功创建 {len(processing_tasks)} 个处理任务",
            "data": {
                "kb_id": kb_id,
                "crawl_summary": {
                    "total_urls": crawl_result["total_urls"],
                    "successful_count": crawl_result["successful_count"],
                    "failed_count": crawl_result["failed_count"],
                    "processing_tasks_created": len(processing_tasks)
                },
                "crawl_config": crawl_config.__dict__,
                "processing_tasks": processing_tasks,
                "failed_crawls": crawl_result.get("failed_results", []),
                "import_time": datetime.now().isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"URL导入失败: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "IMPORT_ERROR",
                "message": str(e)
            }
        )


@router.post("/{kb_id}/documents/crawl-preview",
             response_model=Dict[str, Any],
             summary="URL爬虫预览",
             description="预览URL爬虫结果，不创建处理任务")
async def crawl_url_preview(
    kb_id: str = PathParam(..., description="知识库ID"),
    urls: List[str] = Form(..., description="要预览的URL列表"),
    max_pages: int = Form(5, description="最大页面数（预览模式）"),
    use_trafilatura: bool = Form(True, description="是否使用Trafilatura提取"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    URL爬虫预览功能
    
    只爬取内容并返回预览，不创建处理任务
    适用于用户确认内容质量后再决定是否导入
    """
    try:
        # 验证知识库是否存在
        knowledge_manager = get_unified_knowledge_manager()
        kb_exists = await knowledge_manager.get_knowledge_base(kb_id)
        if not kb_exists:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "KNOWLEDGE_BASE_NOT_FOUND",
                    "message": f"知识库 {kb_id} 不存在"
                }
            )
        
        # 限制预览URL数量
        if len(urls) > 10:
            urls = urls[:10]
            logger.warning("预览模式限制最多10个URL")
        
        # 构建预览配置
        preview_config = CrawlConfig(
            mode=CrawlMode.URL_LIST,
            max_pages=min(max_pages, 5),  # 预览模式最多5个页面
            concurrent_requests=3,
            request_delay=0.5,
            use_trafilatura=use_trafilatura,
            min_content_length=50,  # 预览时降低最小长度要求
            include_metadata=True
        )
        
        # 执行爬虫预览
        async with get_web_crawler_manager(db) as crawler:
            crawl_result = await crawler.crawl_urls(
                kb_id=kb_id,
                urls=urls,
                config=preview_config
            )
        
        # 构建预览结果
        preview_results = []
        for result in crawl_result.get("results", []):
            preview_results.append({
                "url": result.url,
                "title": result.title,
                "content_preview": result.content[:500] + "..." if len(result.content) > 500 else result.content,
                "markdown_preview": result.markdown_content[:500] + "..." if len(result.markdown_content) > 500 else result.markdown_content,
                "content_length": len(result.content),
                "markdown_length": len(result.markdown_content),
                "crawl_time": result.crawl_time,
                "metadata": result.metadata,
                "status": result.status.value if hasattr(result.status, 'value') else str(result.status)
            })
        
        return {
            "success": True,
            "message": f"预览完成，成功爬取 {len(preview_results)} 个URL",
            "data": {
                "kb_id": kb_id,
                "preview_results": preview_results,
                "failed_results": crawl_result.get("failed_results", []),
                "crawl_config": preview_config.__dict__,
                "summary": {
                    "total_urls": len(urls),
                    "successful_count": len(preview_results),
                    "failed_count": len(crawl_result.get("failed_results", [])),
                    "avg_content_length": sum(len(r.content) for r in crawl_result.get("results", [])) // max(len(crawl_result.get("results", [])), 1)
                },
                "preview_time": datetime.now().isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"URL预览失败: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "PREVIEW_ERROR",
                "message": str(e)
            }
        )


# 添加处理器状态接口
@router.get("/processor/status",
            response_model=Dict[str, Any],
            summary="获取处理器状态",
            description="获取任务处理器运行状态和统计信息")
async def get_processor_status() -> Dict[str, Any]:
    """获取处理器状态"""
    try:
        task_processor = await get_task_processor()
        stats = await task_processor.get_processing_stats()
        
        return {
            "success": True,
            "data": stats
        }
        
    except Exception as e:
        logger.error(f"获取处理器状态失败: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "PROCESSOR_ERROR",
                "message": str(e)
            }
        )