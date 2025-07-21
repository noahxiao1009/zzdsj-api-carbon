"""
增强的聊天路由 - 支持消息渲染和格式化
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from fastapi.responses import StreamingResponse

from app.services.chat_manager import get_chat_manager
from app.services.message_renderer import get_message_renderer
from app.services.stream_renderer import (
    get_stream_manager, get_realtime_renderer, get_stream_event_generator
)
from app.utils.format_detector import FormatDetector
from app.core.dependencies import get_current_user
from app.schemas.enhanced_chat import (
    EnhancedChatRequest, EnhancedChatResponse, RenderCapabilities,
    BatchRenderRequest, BatchRenderResponse, RenderMetrics,
    StreamEvent, SessionStartEvent, ContentChunkEvent,
    ContentRenderedEvent, AudioResponseEvent, ErrorEvent,
    SessionCompleteEvent, FormatAnalysis, RenderedContent
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/chat", tags=["enhanced-chat"])

# 全局指标收集器
render_metrics = RenderMetrics(last_updated=datetime.now().isoformat())

@router.post("/message/enhanced", response_model=EnhancedChatResponse)
async def send_enhanced_message(
    request: EnhancedChatRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict = Depends(get_current_user),
    chat_manager = Depends(get_chat_manager),
    renderer = Depends(get_message_renderer)
):
    """
    发送增强消息
    支持自动格式检测、渲染和流式响应
    """
    try:
        user_id = current_user["user_id"]
        start_time = datetime.now()
        
        # 1. 权限检查
        if request.agent_id:
            has_permission = await _check_agent_permission(
                chat_manager, user_id, request.agent_id
            )
            if not has_permission:
                raise HTTPException(
                    status_code=403,
                    detail="无权限访问该智能体"
                )
        
        # 2. 创建或获取会话
        session_id = await _ensure_session(
            chat_manager, user_id, request.session_id, 
            request.agent_id, request.session_config
        )
        
        # 3. 发送消息
        if request.stream:
            return await _handle_stream_response(
                chat_manager, renderer, session_id, request, current_user
            )
        else:
            return await _handle_normal_response(
                chat_manager, renderer, session_id, request, 
                current_user, start_time, background_tasks
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"发送增强消息失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"内部服务器错误: {str(e)}"
        )

@router.post("/message/stream")
async def send_stream_message(
    request: EnhancedChatRequest,
    current_user: Dict = Depends(get_current_user),
    chat_manager = Depends(get_chat_manager),
    renderer = Depends(get_message_renderer)
):
    """
    发送流式消息
    返回SSE格式的流式响应
    """
    try:
        user_id = current_user["user_id"]
        
        # 权限检查
        if request.agent_id:
            has_permission = await _check_agent_permission(
                chat_manager, user_id, request.agent_id
            )
            if not has_permission:
                raise HTTPException(
                    status_code=403,
                    detail="无权限访问该智能体"
                )
        
        # 确保会话存在
        session_id = await _ensure_session(
            chat_manager, user_id, request.session_id,
            request.agent_id, request.session_config
        )
        
        # 返回流式响应
        return await _generate_stream_response(
            chat_manager, renderer, session_id, request, current_user
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"流式消息发送失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"内部服务器错误: {str(e)}"
        )

@router.post("/render/batch", response_model=BatchRenderResponse)
async def batch_render(
    request: BatchRenderRequest,
    current_user: Dict = Depends(get_current_user),
    renderer = Depends(get_message_renderer)
):
    """
    批量渲染内容
    """
    try:
        start_time = datetime.now()
        results = []
        errors = []
        
        if request.enable_parallel:
            # 并行渲染
            semaphore = asyncio.Semaphore(request.max_concurrent)
            
            async def render_with_semaphore(content: str) -> RenderedContent:
                async with semaphore:
                    return await renderer.auto_render(
                        content, 
                        enable_cache=request.render_config.enable_cache if request.render_config else True
                    )
            
            tasks = [render_with_semaphore(content) for content in request.contents]
            render_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(render_results):
                if isinstance(result, Exception):
                    errors.append(f"Content {i}: {str(result)}")
                    results.append(RenderedContent(
                        success=False,
                        original=request.contents[i],
                        rendered_parts=[],
                        formats_detected=[],
                        render_time=0,
                        timestamp=datetime.now().isoformat()
                    ))
                else:
                    results.append(result)
        else:
            # 串行渲染
            for i, content in enumerate(request.contents):
                try:
                    result = await renderer.auto_render(
                        content,
                        enable_cache=request.render_config.enable_cache if request.render_config else True
                    )
                    results.append(result)
                except Exception as e:
                    errors.append(f"Content {i}: {str(e)}")
                    results.append(RenderedContent(
                        success=False,
                        original=content,
                        rendered_parts=[],
                        formats_detected=[],
                        render_time=0,
                        timestamp=datetime.now().isoformat()
                    ))
        
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds() * 1000
        
        success_count = sum(1 for r in results if r.success)
        error_count = len(results) - success_count
        
        return BatchRenderResponse(
            success=error_count == 0,
            results=results,
            total_time=total_time,
            success_count=success_count,
            error_count=error_count,
            errors=errors
        )
        
    except Exception as e:
        logger.error(f"批量渲染失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"批量渲染失败: {str(e)}"
        )

@router.get("/render/capabilities", response_model=RenderCapabilities)
async def get_render_capabilities(
    current_user: Dict = Depends(get_current_user),
    renderer = Depends(get_message_renderer)
):
    """
    获取渲染能力信息
    """
    try:
        capabilities = renderer.get_render_capabilities()
        return RenderCapabilities(**capabilities)
    except Exception as e:
        logger.error(f"获取渲染能力失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取渲染能力失败: {str(e)}"
        )

@router.get("/render/metrics", response_model=RenderMetrics)
async def get_render_metrics(
    current_user: Dict = Depends(get_current_user)
):
    """
    获取渲染性能指标
    """
    try:
        global render_metrics
        render_metrics.last_updated = datetime.now().isoformat()
        return render_metrics
    except Exception as e:
        logger.error(f"获取渲染指标失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取渲染指标失败: {str(e)}"
        )

@router.post("/render/test")
async def test_render_format(
    content: str,
    format_type: Optional[str] = Query(None, description="指定格式类型"),
    current_user: Dict = Depends(get_current_user),
    renderer = Depends(get_message_renderer)
):
    """
    测试渲染功能
    """
    try:
        if format_type:
            # 测试特定格式
            if format_type == "markdown":
                result = await renderer.render_markdown(content)
            elif format_type == "code":
                result = await renderer.render_code(content)
            elif format_type == "latex":
                result = await renderer.render_latex_formulas(content)
            elif format_type == "html":
                result = await renderer.render_html_content(content)
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"不支持的格式类型: {format_type}"
                )
        else:
            # 自动检测和渲染
            result = await renderer.auto_render(content)
        
        return {
            "success": True,
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"测试渲染失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"测试渲染失败: {str(e)}"
        )

@router.post("/format/analyze")
async def analyze_format(
    content: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    分析内容格式
    """
    try:
        detector = FormatDetector()
        analysis = detector.analyze_content(content)
        
        return {
            "success": True,
            "analysis": analysis,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"格式分析失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"格式分析失败: {str(e)}"
        )

@router.delete("/render/cache")
async def clear_render_cache(
    current_user: Dict = Depends(get_current_user),
    renderer = Depends(get_message_renderer)
):
    """
    清理渲染缓存
    """
    try:
        renderer.clear_cache()
        return {
            "success": True,
            "message": "渲染缓存已清理",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"清理缓存失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"清理缓存失败: {str(e)}"
        )

# 辅助函数

async def _check_agent_permission(chat_manager, user_id: str, agent_id: str) -> bool:
    """检查智能体访问权限"""
    try:
        # 这里应该调用权限服务检查
        # 目前简化为允许所有访问
        return True
    except Exception as e:
        logger.error(f"权限检查失败: {e}")
        return False

async def _ensure_session(
    chat_manager, user_id: str, session_id: Optional[str],
    agent_id: Optional[str], session_config: Optional[Dict[str, Any]]
) -> str:
    """确保会话存在"""
    if session_id:
        return session_id
    
    # 创建新会话
    session_result = await chat_manager.create_session(
        user_id=user_id,
        agent_id=agent_id,
        session_config=session_config
    )
    
    if not session_result["success"]:
        raise HTTPException(
            status_code=400,
            detail=f"创建会话失败: {session_result['error']}"
        )
    
    return session_result["session_id"]

async def _handle_normal_response(
    chat_manager, renderer, session_id: str, request: EnhancedChatRequest,
    current_user: Dict, start_time: datetime, background_tasks: BackgroundTasks
) -> EnhancedChatResponse:
    """处理普通响应"""
    # 发送消息
    response = await chat_manager.send_message(
        session_id=session_id,
        message=request.message,
        message_type=request.message_type.value,
        stream=False,
        voice_config=request.voice_config.dict() if request.voice_config else None
    )
    
    if not response.get("success"):
        raise HTTPException(
            status_code=400,
            detail=response.get("error", "发送消息失败")
        )
    
    # 消息渲染
    rendered_content = None
    format_analysis = None
    
    if request.enable_rendering and response.get("response"):
        rendered_content = await renderer.auto_render(
            response["response"],
            enable_cache=request.render_config.enable_cache if request.render_config else True
        )
        
        # 更新渲染指标
        background_tasks.add_task(_update_render_metrics, rendered_content)
    
    # 格式分析
    if request.analyze_format and response.get("response"):
        detector = FormatDetector()
        analysis = detector.analyze_content(response["response"])
        format_analysis = FormatAnalysis(**analysis)
    
    # 计算处理时间
    processing_time = (datetime.now() - start_time).total_seconds() * 1000
    
    return EnhancedChatResponse(
        success=True,
        session_id=session_id,
        message_id=response.get("message_id"),
        response=response.get("response", ""),
        rendered_content=rendered_content,
        format_analysis=format_analysis,
        audio_response=response.get("audio_response"),
        timestamp=response.get("timestamp", datetime.now().isoformat()),
        agent_id=request.agent_id,
        processing_time=processing_time,
        context=request.context
    )

async def _handle_stream_response(
    chat_manager, renderer, session_id: str, request: EnhancedChatRequest,
    current_user: Dict
):
    """处理流式响应"""
    return await _generate_stream_response(
        chat_manager, renderer, session_id, request, current_user
    )

async def _generate_stream_response(
    chat_manager, renderer, session_id: str, request: EnhancedChatRequest,
    current_user: Dict
):
    """生成流式响应"""
    # 获取流式渲染组件
    stream_manager = get_stream_manager(renderer)
    realtime_renderer = get_realtime_renderer(renderer)
    event_generator = get_stream_event_generator(stream_manager, realtime_renderer)
    
    async def generate_enhanced_stream():
        try:
            # 获取原始消息流
            response_stream = await chat_manager.send_message(
                session_id=session_id,
                message=request.message,
                message_type=request.message_type.value,
                stream=True,
                voice_config=request.voice_config.dict() if request.voice_config else None
            )
            
            # 使用增强的事件生成器
            async for event in event_generator.generate_enhanced_stream_events(
                session_id=session_id,
                message_stream=response_stream,
                enable_realtime_render=request.enable_rendering,
                enable_format_analysis=request.analyze_format
            ):
                yield f"data: {json.dumps(event.dict(), ensure_ascii=False)}\n\n"
            
        except Exception as e:
            logger.error(f"流式响应生成失败: {e}")
            error_event = ErrorEvent(
                session_id=session_id,
                timestamp=datetime.now().isoformat(),
                error=str(e),
                data={"error_type": "generation_error"}
            )
            yield f"data: {json.dumps(error_event.dict(), ensure_ascii=False)}\n\n"
        finally:
            yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        generate_enhanced_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用nginx缓冲
            "X-Session-ID": session_id,
            "X-User-ID": current_user["user_id"]
        }
    )

def _update_render_metrics(rendered_content: RenderedContent):
    """更新渲染指标"""
    global render_metrics
    
    try:
        render_metrics.total_requests += 1
        
        if rendered_content.success:
            render_metrics.successful_renders += 1
            
            # 更新格式分布
            for format_type in rendered_content.formats_detected:
                format_str = format_type.value if hasattr(format_type, 'value') else str(format_type)
                render_metrics.format_distribution[format_str] = (
                    render_metrics.format_distribution.get(format_str, 0) + 1
                )
            
            # 更新平均渲染时间
            total_time = (
                render_metrics.average_render_time * (render_metrics.successful_renders - 1) +
                rendered_content.render_time
            )
            render_metrics.average_render_time = total_time / render_metrics.successful_renders
            
        else:
            render_metrics.failed_renders += 1
            
        # 更新缓存命中率（简化计算）
        if render_metrics.total_requests > 0:
            render_metrics.cache_hit_rate = (
                render_metrics.successful_renders / render_metrics.total_requests
            )
            
    except Exception as e:
        logger.error(f"更新渲染指标失败: {e}")