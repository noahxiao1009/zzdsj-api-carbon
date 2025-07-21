"""
文档切分API路由
提供多种文档切分策略的API接口
"""

import logging
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, HTTPException, Form, Query, Depends
from fastapi.responses import JSONResponse

from app.schemas.splitter_schemas import (
    DocumentSplitRequest,
    DocumentSplitResponse,
    SplitterType,
    TokenBasedConfig,
    SemanticBasedConfig,
    ParagraphBasedConfig,
    AgenticBasedConfig,
    SplitterTemplateCreate,
    SplitterTemplate
)
from app.core.document_splitter import get_document_splitter
from app.core.template_manager import get_template_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/splitter", tags=["文档切分"])


@router.post("/split",
             response_model=DocumentSplitResponse,
             summary="切分文档",
             description="使用指定策略切分文档内容")
async def split_document(
    request: DocumentSplitRequest
) -> DocumentSplitResponse:
    """
    切分文档
    
    支持的切分策略：
    - token_based: 基于Token的固定长度切分
    - semantic_based: 基于语义边界的智能切分
    - paragraph_based: 基于段落的切分
    - agentic_based: 基于AI代理的智能切分
    
    可以通过以下方式指定切分配置：
    1. 使用预定义模板 (template_id)
    2. 使用自定义配置 (custom_config + splitter_type)
    3. 使用默认配置 (仅指定splitter_type)
    """
    try:
        splitter = get_document_splitter()
        result = await splitter.split_document(request)
        
        logger.info(
            f"Document split completed: {result.total_chunks} chunks, "
            f"type: {result.splitter_type.value}, "
            f"success: {result.success}"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Document splitting failed: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "DOCUMENT_SPLIT_FAILED",
                "message": str(e)
            }
        )


@router.post("/split/simple",
             response_model=Dict[str, Any],
             summary="简单文档切分",
             description="使用表单参数进行简单的文档切分")
async def split_document_simple(
    content: str = Form(..., description="要切分的文档内容"),
    splitter_type: SplitterType = Form(SplitterType.TOKEN_BASED, description="切分器类型"),
    chunk_size: Optional[int] = Form(1000, description="分块大小"),
    chunk_overlap: Optional[int] = Form(200, description="分块重叠"),
    template_id: Optional[str] = Form(None, description="模板ID")
) -> Dict[str, Any]:
    """
    简单文档切分接口
    
    使用表单参数提供简化的切分接口，适合快速测试和简单场景。
    """
    try:
        # 构建切分请求
        if template_id:
            request = DocumentSplitRequest(
                content=content,
                template_id=template_id
            )
        else:
            # 根据切分器类型创建配置
            if splitter_type == SplitterType.TOKEN_BASED:
                custom_config = TokenBasedConfig(
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap
                )
            elif splitter_type == SplitterType.SEMANTIC_BASED:
                custom_config = SemanticBasedConfig(
                    min_chunk_size=max(200, chunk_size // 2),
                    max_chunk_size=chunk_size,
                    overlap_sentences=1
                )
            elif splitter_type == SplitterType.PARAGRAPH_BASED:
                custom_config = ParagraphBasedConfig(
                    min_paragraph_length=max(50, chunk_size // 4),
                    max_paragraph_length=chunk_size
                )
            else:
                custom_config = AgenticBasedConfig(
                    context_window=chunk_size,
                    max_chunks_per_call=10
                )
            
            request = DocumentSplitRequest(
                content=content,
                splitter_type=splitter_type,
                custom_config=custom_config
            )
        
        # 执行切分
        splitter = get_document_splitter()
        result = await splitter.split_document(request)
        
        # 转换为简化的响应格式
        return {
            "success": result.success,
            "total_chunks": result.total_chunks,
            "splitter_type": result.splitter_type.value,
            "processing_time": result.processing_time,
            "chunks": [
                {
                    "id": chunk.id,
                    "content": chunk.content,
                    "chunk_index": chunk.chunk_index,
                    "start_char": chunk.start_char,
                    "end_char": chunk.end_char,
                    "metadata": chunk.metadata
                }
                for chunk in result.chunks
            ],
            "statistics": result.statistics,
            "error": result.error
        }
        
    except Exception as e:
        logger.error(f"Simple document splitting failed: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "SIMPLE_SPLIT_FAILED",
                "message": str(e)
            }
        )


@router.get("/templates",
            response_model=Dict[str, Any],
            summary="获取切分模板列表",
            description="获取所有可用的文档切分模板")
async def list_splitter_templates(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    splitter_type: Optional[SplitterType] = Query(None, description="切分器类型筛选"),
    is_active: Optional[bool] = Query(None, description="是否激活筛选")
) -> Dict[str, Any]:
    """
    获取切分模板列表
    
    返回所有可用的文档切分模板，支持分页和筛选。
    """
    try:
        template_manager = get_template_manager()
        result = await template_manager.list_templates(
            page=page,
            page_size=page_size,
            splitter_type=splitter_type,
            is_active=is_active
        )
        
        return {
            "success": True,
            "data": {
                "templates": [template.dict() for template in result["templates"]],
                "pagination": {
                    "page": result["page"],
                    "page_size": result["page_size"],
                    "total": result["total"],
                    "total_pages": result.get("total_pages", 0)
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to list splitter templates: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "LIST_TEMPLATES_FAILED",
                "message": str(e)
            }
        )


@router.post("/templates",
             response_model=Dict[str, Any],
             summary="创建切分模板",
             description="创建新的文档切分模板")
async def create_splitter_template(
    request: SplitterTemplateCreate
) -> Dict[str, Any]:
    """
    创建切分模板
    
    创建一个新的文档切分模板，可以在后续的切分操作中重复使用。
    """
    try:
        template_manager = get_template_manager()
        result = await template_manager.create_template(request)
        
        if result["success"]:
            return {
                "success": True,
                "message": "切分模板创建成功",
                "data": result["template"]
            }
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "CREATE_TEMPLATE_FAILED",
                    "message": result["error"]
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create splitter template: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.get("/templates/{template_id}",
            response_model=Dict[str, Any],
            summary="获取切分模板详情",
            description="根据ID获取切分模板的详细信息")
async def get_splitter_template(
    template_id: str
) -> Dict[str, Any]:
    """
    获取切分模板详情
    
    返回指定模板的完整配置信息。
    """
    try:
        template_manager = get_template_manager()
        template = await template_manager.get_template(template_id)
        
        if template:
            return {
                "success": True,
                "data": template.dict()
            }
        else:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "TEMPLATE_NOT_FOUND",
                    "message": f"模板 {template_id} 不存在"
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get splitter template {template_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.put("/templates/{template_id}",
            response_model=Dict[str, Any],
            summary="更新切分模板",
            description="更新现有的切分模板配置")
async def update_splitter_template(
    template_id: str,
    request: SplitterTemplateCreate
) -> Dict[str, Any]:
    """
    更新切分模板
    
    更新指定模板的配置信息。
    """
    try:
        template_manager = get_template_manager()
        result = await template_manager.update_template(template_id, request)
        
        if result["success"]:
            return {
                "success": True,
                "message": "切分模板更新成功",
                "data": result["template"]
            }
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "UPDATE_TEMPLATE_FAILED",
                    "message": result["error"]
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update splitter template {template_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.delete("/templates/{template_id}",
               response_model=Dict[str, Any],
               summary="删除切分模板",
               description="删除指定的切分模板")
async def delete_splitter_template(
    template_id: str
) -> Dict[str, Any]:
    """
    删除切分模板
    
    删除指定的切分模板。注意：删除后无法恢复。
    """
    try:
        template_manager = get_template_manager()
        result = await template_manager.delete_template(template_id)
        
        if result["success"]:
            return {
                "success": True,
                "message": "切分模板删除成功",
                "data": {
                    "template_id": template_id
                }
            }
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "DELETE_TEMPLATE_FAILED",
                    "message": result["error"]
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete splitter template {template_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.get("/statistics",
            response_model=Dict[str, Any],
            summary="获取切分统计信息",
            description="获取文档切分器的统计信息")
async def get_splitter_statistics() -> Dict[str, Any]:
    """
    获取切分统计信息
    
    返回文档切分器的使用统计信息，包括：
    - 总切分次数
    - 成功率
    - 平均处理时间
    - 各种切分器的使用情况
    """
    try:
        splitter = get_document_splitter()
        stats = splitter.get_stats()
        
        template_manager = get_template_manager()
        template_stats = await template_manager.get_statistics()
        
        return {
            "success": True,
            "data": {
                "splitter_stats": stats,
                "template_stats": template_stats,
                "supported_types": [t.value for t in SplitterType]
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get splitter statistics: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )


@router.get("/types",
            response_model=Dict[str, Any],
            summary="获取支持的切分器类型",
            description="获取所有支持的文档切分器类型和配置说明")
async def get_splitter_types() -> Dict[str, Any]:
    """
    获取支持的切分器类型
    
    返回所有支持的文档切分器类型及其配置参数说明。
    """
    try:
        splitter_types = {
            "token_based": {
                "name": "基于Token的切分",
                "description": "按照固定的Token数量进行文档切分",
                "config_schema": TokenBasedConfig.schema(),
                "use_cases": ["通用文档", "长文本", "API文档"]
            },
            "semantic_based": {
                "name": "基于语义的切分",
                "description": "根据语义边界进行智能切分",
                "config_schema": SemanticBasedConfig.schema(),
                "use_cases": ["结构化文档", "学术论文", "技术文档"]
            },
            "paragraph_based": {
                "name": "基于段落的切分",
                "description": "按照段落边界进行切分",
                "config_schema": ParagraphBasedConfig.schema(),
                "use_cases": ["新闻文章", "博客文章", "简单文档"]
            },
            "agentic_based": {
                "name": "基于AI代理的切分",
                "description": "使用AI代理进行智能分析和切分",
                "config_schema": AgenticBasedConfig.schema(),
                "use_cases": ["复杂文档", "多格式文档", "专业文档"]
            }
        }
        
        return {
            "success": True,
            "data": {
                "types": splitter_types,
                "total_types": len(splitter_types)
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get splitter types: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": str(e)
            }
        )