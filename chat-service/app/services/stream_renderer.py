"""
流式渲染管理器 - 处理实时消息渲染和格式化
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, AsyncGenerator, List
from datetime import datetime
from collections import deque
from dataclasses import dataclass, field

from app.services.message_renderer import MessageRenderer
from app.utils.format_detector import FormatDetector
from app.schemas.enhanced_chat import (
    StreamEvent, ContentChunkEvent, ContentRenderedEvent,
    FormatAnalysis, RenderedContent
)

logger = logging.getLogger(__name__)


@dataclass
class StreamBuffer:
    """流式缓冲区"""
    content: str = ""
    chunks: List[str] = field(default_factory=list)
    last_render_point: int = 0
    detected_formats: List[str] = field(default_factory=list)
    render_queue: deque = field(default_factory=deque)
    
    def add_chunk(self, chunk: str):
        """添加内容块"""
        self.chunks.append(chunk)
        self.content += chunk
    
    def get_new_content(self) -> str:
        """获取自上次渲染后的新内容"""
        if len(self.content) <= self.last_render_point:
            return ""
        return self.content[self.last_render_point:]
    
    def mark_rendered(self, position: int):
        """标记渲染位置"""
        self.last_render_point = position


class StreamRenderManager:
    """流式渲染管理器"""
    
    def __init__(self, renderer: MessageRenderer):
        self.renderer = renderer
        self.detector = FormatDetector()
        self.active_streams: Dict[str, StreamBuffer] = {}
        self._render_semaphore = asyncio.Semaphore(5)  # 限制并发渲染数量
        
    async def create_stream(self, stream_id: str) -> StreamBuffer:
        """创建新的流式缓冲区"""
        buffer = StreamBuffer()
        self.active_streams[stream_id] = buffer
        return buffer
    
    async def add_chunk(
        self, 
        stream_id: str, 
        chunk: str, 
        enable_realtime_render: bool = True
    ) -> Dict[str, Any]:
        """添加内容块并处理渲染"""
        if stream_id not in self.active_streams:
            await self.create_stream(stream_id)
        
        buffer = self.active_streams[stream_id]
        buffer.add_chunk(chunk)
        
        result = {
            "stream_id": stream_id,
            "chunk": chunk,
            "accumulated_content": buffer.content,
            "chunk_index": len(buffer.chunks),
            "total_length": len(buffer.content)
        }
        
        # 实时格式分析
        if enable_realtime_render:
            format_analysis = await self._analyze_stream_format(buffer)
            result["format_analysis"] = format_analysis
            
            # 检查是否需要触发渲染
            if self._should_trigger_render(buffer, format_analysis):
                render_result = await self._trigger_stream_render(stream_id, buffer)
                result["render_result"] = render_result
        
        return result
    
    async def finalize_stream(self, stream_id: str) -> Dict[str, Any]:
        """完成流式处理并进行最终渲染"""
        if stream_id not in self.active_streams:
            return {"success": False, "error": "流不存在"}
        
        buffer = self.active_streams[stream_id]
        
        try:
            # 最终渲染
            final_rendered = await self.renderer.auto_render(
                buffer.content,
                enable_cache=True
            )
            
            # 格式分析
            final_analysis = self.detector.analyze_content(buffer.content)
            
            result = {
                "success": True,
                "stream_id": stream_id,
                "final_content": buffer.content,
                "total_chunks": len(buffer.chunks),
                "final_rendered": final_rendered,
                "final_analysis": final_analysis,
                "timestamp": datetime.now().isoformat()
            }
            
            # 清理流缓冲区
            del self.active_streams[stream_id]
            
            return result
            
        except Exception as e:
            logger.error(f"流式渲染完成失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "stream_id": stream_id
            }
    
    async def _analyze_stream_format(self, buffer: StreamBuffer) -> FormatAnalysis:
        """分析流式内容格式"""
        try:
            # 只分析新增的内容部分，提高性能
            new_content = buffer.get_new_content()
            if not new_content:
                # 如果没有新内容，返回之前的分析结果
                return FormatAnalysis(detected_formats=buffer.detected_formats)
            
            # 分析完整内容
            analysis = self.detector.analyze_content(buffer.content)
            
            # 更新检测到的格式
            buffer.detected_formats = analysis.get("detected_formats", [])
            
            return FormatAnalysis(**analysis)
            
        except Exception as e:
            logger.error(f"流式格式分析失败: {e}")
            return FormatAnalysis()
    
    def _should_trigger_render(self, buffer: StreamBuffer, analysis: FormatAnalysis) -> bool:
        """判断是否应该触发渲染"""
        # 如果内容较短，不触发渲染
        if len(buffer.content) < 500:
            return False
        
        # 如果检测到复杂格式，触发渲染
        if analysis.complexity_level.value in ["moderate", "complex"]:
            return True
        
        # 如果累积了足够的内容，触发渲染
        if len(buffer.content) - buffer.last_render_point > 2000:
            return True
        
        # 如果检测到特定格式标记，触发渲染
        trigger_patterns = ["```", "$$", "| ", "# "]
        recent_content = buffer.content[-200:]  # 检查最近200个字符
        for pattern in trigger_patterns:
            if pattern in recent_content:
                return True
        
        return False
    
    async def _trigger_stream_render(self, stream_id: str, buffer: StreamBuffer) -> Dict[str, Any]:
        """触发流式渲染"""
        async with self._render_semaphore:
            try:
                # 渲染当前内容
                rendered = await self.renderer.auto_render(
                    buffer.content,
                    enable_cache=True
                )
                
                # 更新渲染位置
                buffer.mark_rendered(len(buffer.content))
                
                return {
                    "success": True,
                    "rendered_content": rendered,
                    "render_point": buffer.last_render_point,
                    "timestamp": datetime.now().isoformat()
                }
                
            except Exception as e:
                logger.error(f"流式渲染触发失败: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
    
    async def get_stream_status(self, stream_id: str) -> Dict[str, Any]:
        """获取流状态"""
        if stream_id not in self.active_streams:
            return {"exists": False}
        
        buffer = self.active_streams[stream_id]
        return {
            "exists": True,
            "total_chunks": len(buffer.chunks),
            "content_length": len(buffer.content),
            "last_render_point": buffer.last_render_point,
            "detected_formats": buffer.detected_formats,
            "pending_render": len(buffer.render_queue)
        }
    
    def cleanup_stream(self, stream_id: str):
        """清理流缓冲区"""
        if stream_id in self.active_streams:
            del self.active_streams[stream_id]
    
    def get_active_streams(self) -> List[str]:
        """获取活跃流列表"""
        return list(self.active_streams.keys())


class RealTimeRenderer:
    """实时渲染器"""
    
    def __init__(self, renderer: MessageRenderer):
        self.renderer = renderer
        self.detector = FormatDetector()
        self.render_cache = {}
        self.cache_ttl = 300  # 5分钟缓存
    
    async def render_streaming_content(
        self,
        content: str,
        previous_content: str = "",
        enable_incremental: bool = True
    ) -> Dict[str, Any]:
        """渲染流式内容"""
        try:
            # 如果启用增量渲染，只渲染新增部分
            if enable_incremental and previous_content:
                new_content = content[len(previous_content):]
                if not new_content.strip():
                    return {"success": True, "no_changes": True}
            
            # 检查缓存
            cache_key = f"stream_{hash(content)}"
            if cache_key in self.render_cache:
                cache_entry = self.render_cache[cache_key]
                if datetime.now().timestamp() - cache_entry["timestamp"] < self.cache_ttl:
                    return cache_entry["result"]
            
            # 执行渲染
            result = await self.renderer.auto_render(content, enable_cache=True)
            
            # 缓存结果
            self.render_cache[cache_key] = {
                "result": result,
                "timestamp": datetime.now().timestamp()
            }
            
            return result
            
        except Exception as e:
            logger.error(f"实时渲染失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "original_content": content
            }
    
    async def detect_format_changes(
        self,
        current_content: str,
        previous_analysis: Optional[FormatAnalysis] = None
    ) -> Dict[str, Any]:
        """检测格式变化"""
        try:
            current_analysis = self.detector.analyze_content(current_content)
            
            if not previous_analysis:
                return {
                    "has_changes": True,
                    "current_analysis": current_analysis,
                    "new_formats": current_analysis.get("detected_formats", [])
                }
            
            # 比较格式变化
            prev_formats = set(previous_analysis.detected_formats)
            curr_formats = set(current_analysis.get("detected_formats", []))
            
            new_formats = curr_formats - prev_formats
            removed_formats = prev_formats - curr_formats
            
            return {
                "has_changes": bool(new_formats or removed_formats),
                "current_analysis": current_analysis,
                "new_formats": list(new_formats),
                "removed_formats": list(removed_formats),
                "stable_formats": list(curr_formats & prev_formats)
            }
            
        except Exception as e:
            logger.error(f"格式变化检测失败: {e}")
            return {
                "has_changes": False,
                "error": str(e)
            }
    
    def clear_cache(self):
        """清理缓存"""
        self.render_cache.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        now = datetime.now().timestamp()
        valid_entries = sum(
            1 for entry in self.render_cache.values()
            if now - entry["timestamp"] < self.cache_ttl
        )
        
        return {
            "total_entries": len(self.render_cache),
            "valid_entries": valid_entries,
            "cache_hit_rate": valid_entries / max(len(self.render_cache), 1),
            "cache_ttl": self.cache_ttl
        }


class StreamEventGenerator:
    """流式事件生成器"""
    
    def __init__(self, stream_manager: StreamRenderManager, realtime_renderer: RealTimeRenderer):
        self.stream_manager = stream_manager
        self.realtime_renderer = realtime_renderer
    
    async def generate_enhanced_stream_events(
        self,
        session_id: str,
        message_stream: AsyncGenerator[Dict[str, Any], None],
        enable_realtime_render: bool = True,
        enable_format_analysis: bool = True
    ) -> AsyncGenerator[StreamEvent, None]:
        """生成增强的流式事件"""
        
        stream_id = f"stream_{session_id}_{datetime.now().timestamp()}"
        accumulated_content = ""
        previous_analysis = None
        
        try:
            # 创建流缓冲区
            await self.stream_manager.create_stream(stream_id)
            
            # 发送流开始事件
            yield StreamEvent(
                type="stream_start",
                session_id=session_id,
                timestamp=datetime.now().isoformat(),
                data={
                    "stream_id": stream_id,
                    "realtime_render_enabled": enable_realtime_render,
                    "format_analysis_enabled": enable_format_analysis
                }
            )
            
            async for chunk_data in message_stream:
                if chunk_data.get("type") == "assistant_chunk":
                    chunk_text = chunk_data.get("chunk", "")
                    accumulated_content += chunk_text
                    
                    # 添加到流管理器
                    stream_result = await self.stream_manager.add_chunk(
                        stream_id, 
                        chunk_text, 
                        enable_realtime_render
                    )
                    
                    # 格式分析
                    format_analysis = None
                    if enable_format_analysis:
                        format_changes = await self.realtime_renderer.detect_format_changes(
                            accumulated_content,
                            previous_analysis
                        )
                        if format_changes["has_changes"]:
                            format_analysis = FormatAnalysis(**format_changes["current_analysis"])
                            previous_analysis = format_analysis
                    
                    # 生成内容块事件
                    chunk_event = ContentChunkEvent(
                        session_id=session_id,
                        timestamp=datetime.now().isoformat(),
                        chunk=chunk_text,
                        accumulated=accumulated_content,
                        finished=chunk_data.get("finished", False),
                        format_analysis=format_analysis,
                        data={
                            "stream_id": stream_id,
                            "chunk_index": stream_result["chunk_index"],
                            "total_length": stream_result["total_length"]
                        }
                    )
                    yield chunk_event
                    
                    # 如果触发了渲染，发送渲染事件
                    if "render_result" in stream_result and stream_result["render_result"]["success"]:
                        render_event = ContentRenderedEvent(
                            session_id=session_id,
                            timestamp=datetime.now().isoformat(),
                            rendered_content=stream_result["render_result"]["rendered_content"],
                            data={
                                "stream_id": stream_id,
                                "render_trigger": "realtime",
                                "render_point": stream_result["render_result"]["render_point"]
                            }
                        )
                        yield render_event
                
                elif chunk_data.get("type") == "error":
                    # 错误事件
                    error_event = StreamEvent(
                        type="error",
                        session_id=session_id,
                        timestamp=datetime.now().isoformat(),
                        data={
                            "stream_id": stream_id,
                            "error": chunk_data.get("error"),
                            "error_type": "stream_error"
                        }
                    )
                    yield error_event
                    break
            
            # 流完成，进行最终渲染
            final_result = await self.stream_manager.finalize_stream(stream_id)
            
            if final_result["success"]:
                # 最终渲染事件
                final_render_event = ContentRenderedEvent(
                    session_id=session_id,
                    timestamp=datetime.now().isoformat(),
                    rendered_content=final_result["final_rendered"],
                    data={
                        "stream_id": stream_id,
                        "render_trigger": "final",
                        "total_chunks": final_result["total_chunks"],
                        "final_analysis": final_result["final_analysis"]
                    }
                )
                yield final_render_event
            
            # 流完成事件
            complete_event = StreamEvent(
                type="stream_complete",
                session_id=session_id,
                timestamp=datetime.now().isoformat(),
                data={
                    "stream_id": stream_id,
                    "total_content": accumulated_content,
                    "success": final_result["success"]
                }
            )
            yield complete_event
            
        except Exception as e:
            logger.error(f"流式事件生成失败: {e}")
            error_event = StreamEvent(
                type="error",
                session_id=session_id,
                timestamp=datetime.now().isoformat(),
                data={
                    "stream_id": stream_id,
                    "error": str(e),
                    "error_type": "generation_error"
                }
            )
            yield error_event
        finally:
            # 清理流缓冲区
            self.stream_manager.cleanup_stream(stream_id)


# 全局实例
_stream_manager: Optional[StreamRenderManager] = None
_realtime_renderer: Optional[RealTimeRenderer] = None
_event_generator: Optional[StreamEventGenerator] = None


def get_stream_manager(renderer: MessageRenderer) -> StreamRenderManager:
    """获取流式渲染管理器"""
    global _stream_manager
    if _stream_manager is None:
        _stream_manager = StreamRenderManager(renderer)
    return _stream_manager


def get_realtime_renderer(renderer: MessageRenderer) -> RealTimeRenderer:
    """获取实时渲染器"""
    global _realtime_renderer
    if _realtime_renderer is None:
        _realtime_renderer = RealTimeRenderer(renderer)
    return _realtime_renderer


def get_stream_event_generator(
    stream_manager: StreamRenderManager,
    realtime_renderer: RealTimeRenderer
) -> StreamEventGenerator:
    """获取流式事件生成器"""
    global _event_generator
    if _event_generator is None:
        _event_generator = StreamEventGenerator(stream_manager, realtime_renderer)
    return _event_generator