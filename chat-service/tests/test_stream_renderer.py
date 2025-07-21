"""
流式渲染器测试用例
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from app.services.stream_renderer import (
    StreamRenderManager, RealTimeRenderer, StreamEventGenerator,
    StreamBuffer
)
from app.services.message_renderer import MessageRenderer
from app.schemas.enhanced_chat import FormatAnalysis


class TestStreamBuffer:
    """流式缓冲区测试"""
    
    def test_stream_buffer_initialization(self):
        """测试缓冲区初始化"""
        buffer = StreamBuffer()
        
        assert buffer.content == ""
        assert buffer.chunks == []
        assert buffer.last_render_point == 0
        assert buffer.detected_formats == []
    
    def test_add_chunk(self):
        """测试添加内容块"""
        buffer = StreamBuffer()
        
        buffer.add_chunk("Hello ")
        assert buffer.content == "Hello "
        assert buffer.chunks == ["Hello "]
        
        buffer.add_chunk("World!")
        assert buffer.content == "Hello World!"
        assert buffer.chunks == ["Hello ", "World!"]
    
    def test_get_new_content(self):
        """测试获取新内容"""
        buffer = StreamBuffer()
        
        buffer.add_chunk("Hello ")
        buffer.add_chunk("World!")
        
        # 未标记渲染点，应该返回全部内容
        assert buffer.get_new_content() == "Hello World!"
        
        # 标记渲染点
        buffer.mark_rendered(6)  # "Hello "的长度
        assert buffer.get_new_content() == "World!"
        
        # 添加更多内容
        buffer.add_chunk(" Test")
        assert buffer.get_new_content() == "World! Test"


class TestStreamRenderManager:
    """流式渲染管理器测试"""
    
    @pytest.fixture
    def mock_renderer(self):
        """创建模拟渲染器"""
        renderer = MagicMock(spec=MessageRenderer)
        renderer.auto_render = AsyncMock(return_value={
            "success": True,
            "rendered_parts": [],
            "formats_detected": ["markdown"],
            "render_time": 100,
            "timestamp": datetime.now().isoformat()
        })
        return renderer
    
    @pytest.fixture
    def stream_manager(self, mock_renderer):
        """创建流式渲染管理器"""
        return StreamRenderManager(mock_renderer)
    
    @pytest.mark.asyncio
    async def test_create_stream(self, stream_manager):
        """测试创建流"""
        stream_id = "test_stream_1"
        buffer = await stream_manager.create_stream(stream_id)
        
        assert isinstance(buffer, StreamBuffer)
        assert stream_id in stream_manager.active_streams
        assert stream_manager.active_streams[stream_id] is buffer
    
    @pytest.mark.asyncio
    async def test_add_chunk(self, stream_manager):
        """测试添加内容块"""
        stream_id = "test_stream_1"
        await stream_manager.create_stream(stream_id)
        
        result = await stream_manager.add_chunk(stream_id, "Hello ", False)
        
        assert result["stream_id"] == stream_id
        assert result["chunk"] == "Hello "
        assert result["accumulated_content"] == "Hello "
        assert result["chunk_index"] == 1
        assert result["total_length"] == 6
    
    @pytest.mark.asyncio
    async def test_finalize_stream(self, stream_manager, mock_renderer):
        """测试完成流处理"""
        stream_id = "test_stream_1"
        await stream_manager.create_stream(stream_id)
        
        # 添加一些内容
        await stream_manager.add_chunk(stream_id, "# Hello", False)
        await stream_manager.add_chunk(stream_id, " World!", False)
        
        # 完成流
        result = await stream_manager.finalize_stream(stream_id)
        
        assert result["success"] == True
        assert result["stream_id"] == stream_id
        assert result["final_content"] == "# Hello World!"
        assert result["total_chunks"] == 2
        assert "final_rendered" in result
        assert "final_analysis" in result
        
        # 流应该被清理
        assert stream_id not in stream_manager.active_streams
    
    @pytest.mark.asyncio
    async def test_should_trigger_render(self, stream_manager):
        """测试渲染触发条件"""
        buffer = StreamBuffer()
        
        # 内容太短，不应该触发
        buffer.add_chunk("Hello")
        analysis = FormatAnalysis(complexity_level="simple")
        assert not stream_manager._should_trigger_render(buffer, analysis)
        
        # 复杂内容，应该触发
        analysis = FormatAnalysis(complexity_level="complex")
        assert stream_manager._should_trigger_render(buffer, analysis)
        
        # 内容足够长，应该触发
        buffer.content = "x" * 2500
        analysis = FormatAnalysis(complexity_level="simple")
        assert stream_manager._should_trigger_render(buffer, analysis)
    
    @pytest.mark.asyncio
    async def test_get_stream_status(self, stream_manager):
        """测试获取流状态"""
        stream_id = "test_stream_1"
        
        # 不存在的流
        status = await stream_manager.get_stream_status(stream_id)
        assert status["exists"] == False
        
        # 创建流并添加内容
        await stream_manager.create_stream(stream_id)
        await stream_manager.add_chunk(stream_id, "Hello", False)
        
        status = await stream_manager.get_stream_status(stream_id)
        assert status["exists"] == True
        assert status["total_chunks"] == 1
        assert status["content_length"] == 5
    
    def test_cleanup_stream(self, stream_manager):
        """测试清理流"""
        stream_id = "test_stream_1"
        stream_manager.active_streams[stream_id] = StreamBuffer()
        
        stream_manager.cleanup_stream(stream_id)
        assert stream_id not in stream_manager.active_streams
    
    def test_get_active_streams(self, stream_manager):
        """测试获取活跃流列表"""
        stream_manager.active_streams["stream1"] = StreamBuffer()
        stream_manager.active_streams["stream2"] = StreamBuffer()
        
        active_streams = stream_manager.get_active_streams()
        assert len(active_streams) == 2
        assert "stream1" in active_streams
        assert "stream2" in active_streams


class TestRealTimeRenderer:
    """实时渲染器测试"""
    
    @pytest.fixture
    def mock_renderer(self):
        """创建模拟渲染器"""
        renderer = MagicMock(spec=MessageRenderer)
        renderer.auto_render = AsyncMock(return_value={
            "success": True,
            "rendered_parts": [],
            "formats_detected": ["markdown"],
            "render_time": 100
        })
        return renderer
    
    @pytest.fixture
    def realtime_renderer(self, mock_renderer):
        """创建实时渲染器"""
        return RealTimeRenderer(mock_renderer)
    
    @pytest.mark.asyncio
    async def test_render_streaming_content(self, realtime_renderer):
        """测试流式内容渲染"""
        content = "# Hello World\n\nThis is a test."
        
        result = await realtime_renderer.render_streaming_content(content)
        
        assert result["success"] == True
        assert "rendered_parts" in result
    
    @pytest.mark.asyncio
    async def test_render_streaming_content_incremental(self, realtime_renderer):
        """测试增量渲染"""
        previous_content = "# Hello"
        current_content = "# Hello World"
        
        result = await realtime_renderer.render_streaming_content(
            current_content, 
            previous_content, 
            enable_incremental=True
        )
        
        assert result["success"] == True
    
    @pytest.mark.asyncio
    async def test_render_streaming_content_no_changes(self, realtime_renderer):
        """测试无变化内容"""
        content = "# Hello World"
        
        result = await realtime_renderer.render_streaming_content(
            content, 
            content,  # 相同内容
            enable_incremental=True
        )
        
        assert result["success"] == True
        assert result.get("no_changes") == True
    
    @pytest.mark.asyncio
    async def test_detect_format_changes(self, realtime_renderer):
        """测试格式变化检测"""
        current_content = "# Hello\n\n```python\nprint('world')\n```"
        
        # 无之前分析
        result = await realtime_renderer.detect_format_changes(current_content)
        assert result["has_changes"] == True
        assert "markdown" in result["new_formats"]
        
        # 有之前分析
        previous_analysis = FormatAnalysis(detected_formats=["markdown"])
        result = await realtime_renderer.detect_format_changes(
            current_content, 
            previous_analysis
        )
        assert result["has_changes"] == True
        assert "code" in result["new_formats"]
    
    def test_cache_functionality(self, realtime_renderer):
        """测试缓存功能"""
        # 初始状态
        assert len(realtime_renderer.render_cache) == 0
        
        # 添加缓存项
        realtime_renderer.render_cache["test_key"] = {
            "result": {"success": True},
            "timestamp": datetime.now().timestamp()
        }
        
        # 获取缓存统计
        stats = realtime_renderer.get_cache_stats()
        assert stats["total_entries"] == 1
        assert stats["valid_entries"] == 1
        
        # 清理缓存
        realtime_renderer.clear_cache()
        assert len(realtime_renderer.render_cache) == 0


class TestStreamEventGenerator:
    """流式事件生成器测试"""
    
    @pytest.fixture
    def mock_components(self):
        """创建模拟组件"""
        renderer = MagicMock(spec=MessageRenderer)
        stream_manager = MagicMock(spec=StreamRenderManager)
        realtime_renderer = MagicMock(spec=RealTimeRenderer)
        
        return renderer, stream_manager, realtime_renderer
    
    @pytest.fixture
    def event_generator(self, mock_components):
        """创建事件生成器"""
        _, stream_manager, realtime_renderer = mock_components
        return StreamEventGenerator(stream_manager, realtime_renderer)
    
    @pytest.mark.asyncio
    async def test_generate_enhanced_stream_events(self, event_generator, mock_components):
        """测试生成增强流式事件"""
        _, stream_manager, realtime_renderer = mock_components
        
        # 模拟消息流
        async def mock_message_stream():
            yield {"type": "assistant_chunk", "chunk": "Hello ", "finished": False}
            yield {"type": "assistant_chunk", "chunk": "World!", "finished": True}
        
        # 模拟流管理器行为
        stream_manager.create_stream = AsyncMock()
        stream_manager.add_chunk = AsyncMock(return_value={
            "stream_id": "test_stream",
            "chunk": "Hello ",
            "chunk_index": 1,
            "total_length": 6
        })
        stream_manager.finalize_stream = AsyncMock(return_value={
            "success": True,
            "stream_id": "test_stream",
            "final_content": "Hello World!",
            "total_chunks": 2,
            "final_rendered": {"success": True},
            "final_analysis": {}
        })
        stream_manager.cleanup_stream = MagicMock()
        
        # 模拟实时渲染器行为
        realtime_renderer.detect_format_changes = AsyncMock(return_value={
            "has_changes": True,
            "current_analysis": {
                "detected_formats": ["markdown"],
                "complexity_level": "simple"
            }
        })
        
        # 生成事件
        events = []
        async for event in event_generator.generate_enhanced_stream_events(
            session_id="test_session",
            message_stream=mock_message_stream(),
            enable_realtime_render=True,
            enable_format_analysis=True
        ):
            events.append(event)
        
        # 验证事件
        assert len(events) >= 3  # 至少包含开始、内容和完成事件
        assert events[0].type == "stream_start"
        assert events[-1].type == "stream_complete"
        
        # 验证调用
        stream_manager.create_stream.assert_called_once()
        assert stream_manager.add_chunk.call_count == 2
        stream_manager.finalize_stream.assert_called_once()
        stream_manager.cleanup_stream.assert_called_once()


class TestIntegration:
    """集成测试"""
    
    @pytest.mark.asyncio
    async def test_full_stream_rendering_pipeline(self):
        """测试完整的流式渲染管道"""
        # 创建真实组件（但使用模拟的底层渲染器）
        mock_renderer = MagicMock(spec=MessageRenderer)
        mock_renderer.auto_render = AsyncMock(return_value={
            "success": True,
            "rendered_parts": [{"format": "markdown", "success": True}],
            "formats_detected": ["markdown"],
            "render_time": 100,
            "timestamp": datetime.now().isoformat()
        })
        
        stream_manager = StreamRenderManager(mock_renderer)
        realtime_renderer = RealTimeRenderer(mock_renderer)
        event_generator = StreamEventGenerator(stream_manager, realtime_renderer)
        
        # 创建测试消息流
        async def test_message_stream():
            chunks = [
                {"type": "assistant_chunk", "chunk": "# ", "finished": False},
                {"type": "assistant_chunk", "chunk": "Hello ", "finished": False},
                {"type": "assistant_chunk", "chunk": "World\n\n", "finished": False},
                {"type": "assistant_chunk", "chunk": "This is a **test**.", "finished": True}
            ]
            for chunk in chunks:
                yield chunk
        
        # 生成事件并收集
        events = []
        async for event in event_generator.generate_enhanced_stream_events(
            session_id="integration_test",
            message_stream=test_message_stream(),
            enable_realtime_render=True,
            enable_format_analysis=True
        ):
            events.append(event)
        
        # 验证事件序列
        event_types = [event.type for event in events]
        assert "stream_start" in event_types
        assert "content_chunk" in event_types
        assert "content_rendered" in event_types
        assert "stream_complete" in event_types
        
        # 验证最终内容
        complete_event = next(e for e in events if e.type == "stream_complete")
        assert complete_event.data["total_content"] == "# Hello World\n\nThis is a **test**."
    
    @pytest.mark.asyncio
    async def test_error_handling_in_stream(self):
        """测试流式处理中的错误处理"""
        mock_renderer = MagicMock(spec=MessageRenderer)
        mock_renderer.auto_render = AsyncMock(side_effect=Exception("Render error"))
        
        stream_manager = StreamRenderManager(mock_renderer)
        realtime_renderer = RealTimeRenderer(mock_renderer)
        event_generator = StreamEventGenerator(stream_manager, realtime_renderer)
        
        # 创建会产生错误的消息流
        async def error_message_stream():
            yield {"type": "assistant_chunk", "chunk": "Hello", "finished": False}
            yield {"type": "error", "error": "Stream error"}
        
        # 生成事件
        events = []
        async for event in event_generator.generate_enhanced_stream_events(
            session_id="error_test",
            message_stream=error_message_stream(),
            enable_realtime_render=True,
            enable_format_analysis=True
        ):
            events.append(event)
        
        # 验证错误处理
        event_types = [event.type for event in events]
        assert "error" in event_types
        
        # 验证清理
        assert len(stream_manager.active_streams) == 0
    
    @pytest.mark.asyncio
    async def test_concurrent_stream_processing(self):
        """测试并发流处理"""
        mock_renderer = MagicMock(spec=MessageRenderer)
        mock_renderer.auto_render = AsyncMock(return_value={
            "success": True,
            "rendered_parts": [],
            "formats_detected": [],
            "render_time": 50
        })
        
        stream_manager = StreamRenderManager(mock_renderer)
        
        # 创建多个并发流
        async def create_concurrent_streams():
            tasks = []
            for i in range(5):
                task = asyncio.create_task(
                    stream_manager.create_stream(f"concurrent_stream_{i}")
                )
                tasks.append(task)
            
            await asyncio.gather(*tasks)
        
        await create_concurrent_streams()
        
        # 验证所有流都被创建
        assert len(stream_manager.active_streams) == 5
        
        # 并发添加内容
        async def add_content_concurrently():
            tasks = []
            for i in range(5):
                task = asyncio.create_task(
                    stream_manager.add_chunk(f"concurrent_stream_{i}", f"Content {i}", False)
                )
                tasks.append(task)
            
            results = await asyncio.gather(*tasks)
            return results
        
        results = await add_content_concurrently()
        assert len(results) == 5
        assert all(r["chunk"] == f"Content {i}" for i, r in enumerate(results))