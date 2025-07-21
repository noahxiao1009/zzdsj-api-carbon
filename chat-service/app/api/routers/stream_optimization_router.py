"""
流式渲染性能优化路由
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.message_renderer import get_message_renderer
from app.services.stream_renderer import (
    get_stream_manager, get_realtime_renderer
)
from app.core.dependencies import get_current_user
from app.core.redis import redis_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/stream", tags=["stream-optimization"])


class StreamOptimizationConfig(BaseModel):
    """流式优化配置"""
    enable_incremental_render: bool = True
    render_trigger_threshold: int = 1000  # 触发渲染的字符数阈值
    render_debounce_ms: int = 200  # 渲染防抖时间（毫秒）
    max_concurrent_renders: int = 3  # 最大并发渲染数
    cache_strategy: str = "aggressive"  # 缓存策略: conservative, balanced, aggressive
    format_detection_level: str = "smart"  # 格式检测级别: basic, smart, comprehensive


class RenderPerformanceMonitor:
    """渲染性能监控器"""
    
    def __init__(self):
        self.metrics = {
            "total_renders": 0,
            "successful_renders": 0,
            "failed_renders": 0,
            "average_render_time": 0.0,
            "render_times": [],
            "cache_hits": 0,
            "cache_misses": 0,
            "peak_concurrent_renders": 0,
            "current_concurrent_renders": 0
        }
        self.performance_history = []
        self.max_history_size = 1000
    
    def record_render_start(self):
        """记录渲染开始"""
        self.metrics["current_concurrent_renders"] += 1
        self.metrics["peak_concurrent_renders"] = max(
            self.metrics["peak_concurrent_renders"],
            self.metrics["current_concurrent_renders"]
        )
    
    def record_render_end(self, render_time: float, success: bool, cache_hit: bool = False):
        """记录渲染结束"""
        self.metrics["current_concurrent_renders"] -= 1
        self.metrics["total_renders"] += 1
        
        if success:
            self.metrics["successful_renders"] += 1
            self.metrics["render_times"].append(render_time)
            
            # 保持最近1000次的渲染时间
            if len(self.metrics["render_times"]) > 1000:
                self.metrics["render_times"] = self.metrics["render_times"][-1000:]
            
            # 更新平均渲染时间
            self.metrics["average_render_time"] = sum(self.metrics["render_times"]) / len(self.metrics["render_times"])
        else:
            self.metrics["failed_renders"] += 1
        
        if cache_hit:
            self.metrics["cache_hits"] += 1
        else:
            self.metrics["cache_misses"] += 1
        
        # 记录性能历史
        self.performance_history.append({
            "timestamp": datetime.now().isoformat(),
            "render_time": render_time,
            "success": success,
            "cache_hit": cache_hit,
            "concurrent_renders": self.metrics["current_concurrent_renders"]
        })
        
        # 保持历史记录大小
        if len(self.performance_history) > self.max_history_size:
            self.performance_history = self.performance_history[-self.max_history_size:]
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        cache_total = self.metrics["cache_hits"] + self.metrics["cache_misses"]
        cache_hit_rate = self.metrics["cache_hits"] / max(cache_total, 1)
        
        success_rate = self.metrics["successful_renders"] / max(self.metrics["total_renders"], 1)
        
        return {
            "render_metrics": self.metrics,
            "cache_hit_rate": cache_hit_rate,
            "success_rate": success_rate,
            "recent_performance": self.performance_history[-10:],  # 最近10次
            "timestamp": datetime.now().isoformat()
        }
    
    def get_performance_trends(self, minutes: int = 60) -> Dict[str, Any]:
        """获取性能趋势"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        
        recent_history = [
            record for record in self.performance_history
            if datetime.fromisoformat(record["timestamp"]) > cutoff_time
        ]
        
        if not recent_history:
            return {"message": "没有最近的性能数据"}
        
        # 计算趋势
        render_times = [r["render_time"] for r in recent_history if r["success"]]
        cache_hits = sum(1 for r in recent_history if r["cache_hit"])
        
        return {
            "time_period_minutes": minutes,
            "total_renders": len(recent_history),
            "successful_renders": len(render_times),
            "average_render_time": sum(render_times) / max(len(render_times), 1),
            "min_render_time": min(render_times) if render_times else 0,
            "max_render_time": max(render_times) if render_times else 0,
            "cache_hit_rate": cache_hits / max(len(recent_history), 1),
            "performance_grade": self._calculate_performance_grade(render_times, cache_hits, len(recent_history))
        }
    
    def _calculate_performance_grade(self, render_times: List[float], cache_hits: int, total: int) -> str:
        """计算性能等级"""
        if not render_times:
            return "N/A"
        
        avg_time = sum(render_times) / len(render_times)
        cache_rate = cache_hits / max(total, 1)
        
        # 综合评分
        time_score = min(100, max(0, 100 - (avg_time - 100) * 2))  # 100ms为基准
        cache_score = cache_rate * 100
        
        overall_score = (time_score + cache_score) / 2
        
        if overall_score >= 90:
            return "A"
        elif overall_score >= 80:
            return "B"
        elif overall_score >= 70:
            return "C"
        elif overall_score >= 60:
            return "D"
        else:
            return "F"


# 全局性能监控器
performance_monitor = RenderPerformanceMonitor()


@router.get("/config")
async def get_stream_config():
    """获取流式渲染配置"""
    return StreamOptimizationConfig()


@router.post("/config")
async def update_stream_config(
    config: StreamOptimizationConfig,
    current_user: Dict = Depends(get_current_user)
):
    """更新流式渲染配置"""
    try:
        # 将配置保存到Redis
        config_key = f"stream_config:{current_user['user_id']}"
        redis_manager.set_json(config_key, config.dict(), ex=86400)
        
        return {
            "success": True,
            "message": "配置已更新",
            "config": config.dict(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"更新流式配置失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"更新配置失败: {str(e)}"
        )


@router.get("/performance/metrics")
async def get_performance_metrics(
    current_user: Dict = Depends(get_current_user)
):
    """获取性能指标"""
    return performance_monitor.get_metrics()


@router.get("/performance/trends")
async def get_performance_trends(
    minutes: int = Query(60, ge=1, le=1440),
    current_user: Dict = Depends(get_current_user)
):
    """获取性能趋势"""
    return performance_monitor.get_performance_trends(minutes)


@router.post("/performance/reset")
async def reset_performance_metrics(
    current_user: Dict = Depends(get_current_user)
):
    """重置性能指标"""
    global performance_monitor
    performance_monitor = RenderPerformanceMonitor()
    
    return {
        "success": True,
        "message": "性能指标已重置",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/cache/stats")
async def get_cache_stats(
    current_user: Dict = Depends(get_current_user),
    renderer = Depends(get_message_renderer)
):
    """获取缓存统计"""
    try:
        realtime_renderer = get_realtime_renderer(renderer)
        cache_stats = realtime_renderer.get_cache_stats()
        
        # 获取Redis缓存统计
        redis_stats = {
            "redis_available": redis_manager.ping(),
            "redis_memory_usage": "N/A",  # 需要Redis INFO命令
            "redis_keys_count": "N/A"
        }
        
        return {
            "realtime_cache": cache_stats,
            "redis_cache": redis_stats,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"获取缓存统计失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取缓存统计失败: {str(e)}"
        )


@router.delete("/cache/clear")
async def clear_cache(
    cache_type: str = Query("all", description="缓存类型: all, memory, redis"),
    current_user: Dict = Depends(get_current_user),
    renderer = Depends(get_message_renderer)
):
    """清理缓存"""
    try:
        cleared = []
        
        if cache_type in ["all", "memory"]:
            # 清理内存缓存
            renderer.clear_cache()
            realtime_renderer = get_realtime_renderer(renderer)
            realtime_renderer.clear_cache()
            cleared.append("memory")
        
        if cache_type in ["all", "redis"]:
            # 清理Redis缓存
            pattern = "render_cache:*"
            keys = redis_manager.scan_iter(match=pattern)
            deleted_count = 0
            for key in keys:
                redis_manager.delete(key)
                deleted_count += 1
            cleared.append(f"redis({deleted_count} keys)")
        
        return {
            "success": True,
            "message": f"缓存已清理: {', '.join(cleared)}",
            "cleared_caches": cleared,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"清理缓存失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"清理缓存失败: {str(e)}"
        )


@router.get("/render/queue")
async def get_render_queue_status(
    current_user: Dict = Depends(get_current_user),
    renderer = Depends(get_message_renderer)
):
    """获取渲染队列状态"""
    try:
        stream_manager = get_stream_manager(renderer)
        active_streams = stream_manager.get_active_streams()
        
        queue_status = []
        for stream_id in active_streams:
            status = await stream_manager.get_stream_status(stream_id)
            queue_status.append({
                "stream_id": stream_id,
                "status": status
            })
        
        return {
            "active_streams": len(active_streams),
            "queue_details": queue_status,
            "current_concurrent_renders": performance_monitor.metrics["current_concurrent_renders"],
            "peak_concurrent_renders": performance_monitor.metrics["peak_concurrent_renders"],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"获取渲染队列状态失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取渲染队列状态失败: {str(e)}"
        )


@router.post("/render/benchmark")
async def run_render_benchmark(
    content: str,
    iterations: int = Query(10, ge=1, le=100),
    current_user: Dict = Depends(get_current_user),
    renderer = Depends(get_message_renderer)
):
    """运行渲染性能基准测试"""
    try:
        results = []
        
        for i in range(iterations):
            start_time = datetime.now()
            
            # 执行渲染
            result = await renderer.auto_render(content, enable_cache=False)
            
            end_time = datetime.now()
            render_time = (end_time - start_time).total_seconds() * 1000
            
            results.append({
                "iteration": i + 1,
                "render_time_ms": render_time,
                "success": result.get("success", False),
                "formats_detected": len(result.get("formats_detected", [])),
                "rendered_parts": len(result.get("rendered_parts", []))
            })
        
        # 计算统计信息
        successful_results = [r for r in results if r["success"]]
        render_times = [r["render_time_ms"] for r in successful_results]
        
        if render_times:
            avg_time = sum(render_times) / len(render_times)
            min_time = min(render_times)
            max_time = max(render_times)
            
            # 计算标准差
            variance = sum((t - avg_time) ** 2 for t in render_times) / len(render_times)
            std_dev = variance ** 0.5
        else:
            avg_time = min_time = max_time = std_dev = 0
        
        return {
            "benchmark_results": {
                "total_iterations": iterations,
                "successful_iterations": len(successful_results),
                "success_rate": len(successful_results) / iterations,
                "average_render_time_ms": avg_time,
                "min_render_time_ms": min_time,
                "max_render_time_ms": max_time,
                "std_deviation_ms": std_dev,
                "performance_grade": performance_monitor._calculate_performance_grade(
                    render_times, 0, len(results)
                )
            },
            "detailed_results": results,
            "test_content_length": len(content),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"运行渲染基准测试失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"基准测试失败: {str(e)}"
        )


@router.get("/health")
async def get_stream_health():
    """获取流式服务健康状态"""
    try:
        # 检查各个组件的健康状态
        health_checks = {
            "redis": redis_manager.ping(),
            "performance_monitor": performance_monitor.metrics["current_concurrent_renders"] < 10,
            "memory_usage": "OK",  # 需要实际内存检查
            "cache_performance": performance_monitor.metrics["cache_hits"] > performance_monitor.metrics["cache_misses"]
        }
        
        all_healthy = all(health_checks.values())
        
        return {
            "overall_health": "healthy" if all_healthy else "unhealthy",
            "component_health": health_checks,
            "current_load": {
                "concurrent_renders": performance_monitor.metrics["current_concurrent_renders"],
                "peak_concurrent_renders": performance_monitor.metrics["peak_concurrent_renders"],
                "total_renders": performance_monitor.metrics["total_renders"]
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"获取流式服务健康状态失败: {e}")
        return {
            "overall_health": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


# 中间件：记录渲染性能
async def record_render_performance(render_func, *args, **kwargs):
    """记录渲染性能的装饰器"""
    performance_monitor.record_render_start()
    start_time = datetime.now()
    
    try:
        result = await render_func(*args, **kwargs)
        success = result.get("success", False)
        cache_hit = False  # 需要从结果中检测
        
        end_time = datetime.now()
        render_time = (end_time - start_time).total_seconds() * 1000
        
        performance_monitor.record_render_end(render_time, success, cache_hit)
        
        return result
    except Exception as e:
        end_time = datetime.now()
        render_time = (end_time - start_time).total_seconds() * 1000
        performance_monitor.record_render_end(render_time, False, False)
        raise