from fastapi import APIRouter, HTTPException, Query, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Optional, List
import logging

from ..schemas.splitter_schemas import (
    SplitterType, SplitterTemplate, SplitterTemplateCreate, 
    SplitterTemplateUpdate, SplitterTemplateList, DocumentSplitRequest,
    DocumentSplitResponse, SystemTemplatesResponse, TemplateUsageStats
)
from ..core.template_manager import get_template_manager, SplitterTemplateManager
from ..core.document_splitter import get_document_splitter, DocumentSplitter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/splitter", tags=["文档切分"])


def get_current_user_id() -> Optional[str]:
    """获取当前用户ID（占位符函数）"""
    # 实际应该从认证中间件获取
    return "user_123"


@router.post("/templates/", response_model=SplitterTemplate, summary="创建切分模板")
async def create_template(
    request: SplitterTemplateCreate,
    template_manager: SplitterTemplateManager = Depends(get_template_manager),
    current_user: Optional[str] = Depends(get_current_user_id)
):
    """
    创建新的文档切分模板
    
    - **name**: 模板名称
    - **description**: 模板描述
    - **splitter_type**: 切分器类型
    - **config**: 切分配置
    - **tags**: 模板标签
    """
    try:
        template = await template_manager.create_template(request, current_user)
        return template
    except Exception as e:
        logger.error(f"Failed to create template: {e}")
        raise HTTPException(status_code=500, detail=f"创建模板失败: {str(e)}")


@router.get("/templates/", response_model=SplitterTemplateList, summary="获取模板列表")
async def list_templates(
    splitter_type: Optional[SplitterType] = Query(None, description="过滤切分器类型"),
    is_active: Optional[bool] = Query(None, description="过滤激活状态"),
    tags: Optional[str] = Query(None, description="过滤标签（逗号分隔）"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="页面大小"),
    template_manager: SplitterTemplateManager = Depends(get_template_manager)
):
    """
    获取文档切分模板列表
    
    支持按类型、激活状态、标签进行过滤，并支持分页
    """
    try:
        # 解析标签
        tag_list = tags.split(',') if tags else None
        
        result = await template_manager.list_templates(
            splitter_type=splitter_type,
            is_active=is_active,
            tags=tag_list,
            page=page,
            page_size=page_size
        )
        
        return SplitterTemplateList(**result)
    except Exception as e:
        logger.error(f"Failed to list templates: {e}")
        raise HTTPException(status_code=500, detail=f"获取模板列表失败: {str(e)}")


@router.get("/templates/system", response_model=SystemTemplatesResponse, summary="获取系统默认模板")
async def get_system_templates(
    template_manager: SplitterTemplateManager = Depends(get_template_manager)
):
    """
    获取系统默认模板，按切分类型分组
    
    返回四种类型的系统默认模板：
    - Token切分模板
    - 语义切分模板  
    - 段落切分模板
    - Agentic切分模板
    """
    try:
        return await template_manager.get_system_templates()
    except Exception as e:
        logger.error(f"Failed to get system templates: {e}")
        raise HTTPException(status_code=500, detail=f"获取系统模板失败: {str(e)}")


@router.get("/templates/popular", response_model=List[SplitterTemplate], summary="获取热门模板")
async def get_popular_templates(
    limit: int = Query(10, ge=1, le=50, description="返回数量限制"),
    template_manager: SplitterTemplateManager = Depends(get_template_manager)
):
    """
    获取使用次数最多的热门模板
    """
    try:
        return await template_manager.get_popular_templates(limit)
    except Exception as e:
        logger.error(f"Failed to get popular templates: {e}")
        raise HTTPException(status_code=500, detail=f"获取热门模板失败: {str(e)}")


@router.get("/templates/search", response_model=List[SplitterTemplate], summary="搜索模板")
async def search_templates(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    template_manager: SplitterTemplateManager = Depends(get_template_manager)
):
    """
    根据关键词搜索模板
    
    在模板名称、描述、标签中进行搜索
    """
    try:
        return await template_manager.search_templates(q)
    except Exception as e:
        logger.error(f"Failed to search templates: {e}")
        raise HTTPException(status_code=500, detail=f"搜索模板失败: {str(e)}")


@router.get("/templates/{template_id}", response_model=SplitterTemplate, summary="获取模板详情")
async def get_template(
    template_id: str,
    template_manager: SplitterTemplateManager = Depends(get_template_manager)
):
    """
    获取指定模板的详细信息
    """
    template = await template_manager.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    return template


@router.put("/templates/{template_id}", response_model=SplitterTemplate, summary="更新模板")
async def update_template(
    template_id: str,
    request: SplitterTemplateUpdate,
    template_manager: SplitterTemplateManager = Depends(get_template_manager)
):
    """
    更新指定模板
    
    注意：系统模板不允许修改
    """
    try:
        template = await template_manager.update_template(template_id, request)
        if not template:
            raise HTTPException(status_code=404, detail="模板不存在")
        
        return template
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update template {template_id}: {e}")
        raise HTTPException(status_code=500, detail=f"更新模板失败: {str(e)}")


@router.delete("/templates/{template_id}", summary="删除模板")
async def delete_template(
    template_id: str,
    template_manager: SplitterTemplateManager = Depends(get_template_manager)
):
    """
    删除指定模板
    
    注意：系统模板不允许删除
    """
    try:
        success = await template_manager.delete_template(template_id)
        if not success:
            raise HTTPException(status_code=404, detail="模板不存在")
        
        return {"success": True, "message": "模板删除成功"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete template {template_id}: {e}")
        raise HTTPException(status_code=500, detail=f"删除模板失败: {str(e)}")


@router.post("/split", response_model=DocumentSplitResponse, summary="文档切分")
async def split_document(
    request: DocumentSplitRequest,
    background_tasks: BackgroundTasks,
    document_splitter: DocumentSplitter = Depends(get_document_splitter),
    template_manager: SplitterTemplateManager = Depends(get_template_manager)
):
    """
    对文档进行切分
    
    支持三种使用方式：
    1. 使用预定义模板：指定 template_id
    2. 使用默认配置：指定 splitter_type  
    3. 使用自定义配置：指定 splitter_type 和 custom_config
    """
    try:
        # 验证请求参数
        if not request.template_id and not request.splitter_type:
            raise HTTPException(
                status_code=400, 
                detail="必须指定 template_id 或 splitter_type"
            )
        
        # 执行文档切分
        result = await document_splitter.split_document(request)
        
        # 记录模板使用（后台任务）
        if request.template_id:
            background_tasks.add_task(
                template_manager.record_template_usage, 
                request.template_id
            )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to split document: {e}")
        raise HTTPException(status_code=500, detail=f"文档切分失败: {str(e)}")


@router.get("/templates/{template_id}/usage", summary="获取模板使用统计")
async def get_template_usage_stats(
    template_id: str,
    template_manager: SplitterTemplateManager = Depends(get_template_manager)
):
    """
    获取指定模板的使用统计信息
    """
    template = await template_manager.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    stats = {
        "template_id": template_id,
        "template_name": template.name,
        "splitter_type": template.splitter_type,
        "usage_count": template.usage_count,
        "last_used": template_manager.last_used.get(template_id),
        "is_system_template": template.is_system_template,
        "created_at": template.created_at
    }
    
    return stats


@router.get("/stats", summary="获取切分系统统计")
async def get_splitter_stats(
    template_manager: SplitterTemplateManager = Depends(get_template_manager),
    document_splitter: DocumentSplitter = Depends(get_document_splitter)
):
    """
    获取文档切分系统的整体统计信息
    """
    try:
        template_stats = template_manager.get_stats()
        splitter_stats = document_splitter.get_stats()
        
        return {
            "template_statistics": template_stats,
            "splitter_statistics": splitter_stats,
            "system_info": {
                "available_splitter_types": [t.value for t in SplitterType],
                "total_system_templates": template_stats.get("system_templates", 0),
                "total_user_templates": template_stats.get("user_templates", 0)
            }
        }
    except Exception as e:
        logger.error(f"Failed to get splitter stats: {e}")
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")


@router.get("/types", summary="获取支持的切分类型")
async def get_splitter_types():
    """
    获取系统支持的所有切分类型及其说明
    """
    return {
        "splitter_types": [
            {
                "type": SplitterType.TOKEN_BASED,
                "name": "Token切分",
                "description": "按字符数或token数进行固定长度切分，支持重叠和智能断句"
            },
            {
                "type": SplitterType.SEMANTIC_BASED,
                "name": "语义切分", 
                "description": "基于语义相似度进行智能切分，保持内容的语义连贯性"
            },
            {
                "type": SplitterType.PARAGRAPH_BASED,
                "name": "段落切分",
                "description": "按自然段落或文档结构进行切分，保持文档的逻辑结构"
            },
            {
                "type": SplitterType.AGENTIC_BASED,
                "name": "Agentic切分",
                "description": "使用AI代理进行主题边界识别的高级智能切分"
            }
        ]
    } 