"""
请求跟踪中间件
用于记录和监控API请求，包括响应时间、状态码、错误率等
"""

import time
import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from functools import wraps
from collections import defaultdict, deque
import asyncio
import threading

from fastapi import Request, Response
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class RequestMetrics:
    """请求指标类"""
    
    def __init__(self):
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.response_times = deque(maxlen=1000)  # 保留最近1000个请求的响应时间
        self.status_codes = defaultdict(int)
        self.endpoints = defaultdict(int)
        self.error_details = deque(maxlen=100)  # 保留最近100个错误
        self.start_time = datetime.now()
        self._lock = threading.Lock()
    
    def add_request(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        response_time: float,
        error: Optional[str] = None
    ):
        """添加请求记录"""
        with self._lock:
            self.total_requests += 1
            self.response_times.append(response_time)
            self.status_codes[status_code] += 1
            self.endpoints[f"{method} {endpoint}"] += 1
            
            if 200 <= status_code < 400:
                self.successful_requests += 1
            else:
                self.failed_requests += 1
                if error:
                    self.error_details.append({
                        "timestamp": datetime.now().isoformat(),
                        "endpoint": endpoint,
                        "method": method,
                        "status_code": status_code,
                        "error": error
                    })
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            if not self.response_times:
                avg_response_time = 0
                min_response_time = 0
                max_response_time = 0
            else:
                avg_response_time = sum(self.response_times) / len(self.response_times)
                min_response_time = min(self.response_times)
                max_response_time = max(self.response_times)
            
            error_rate = (self.failed_requests / self.total_requests * 100) if self.total_requests > 0 else 0
            uptime = (datetime.now() - self.start_time).total_seconds()
            
            return {
                "total_requests": self.total_requests,
                "successful_requests": self.successful_requests,
                "failed_requests": self.failed_requests,
                "error_rate": round(error_rate, 2),
                "response_time": {
                    "average": round(avg_response_time, 3),
                    "min": round(min_response_time, 3),
                    "max": round(max_response_time, 3)
                },
                "status_codes": dict(self.status_codes),
                "top_endpoints": dict(sorted(
                    self.endpoints.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:10]),
                "recent_errors": list(self.error_details)[-10:],
                "uptime_seconds": round(uptime, 1),
                "requests_per_second": round(self.total_requests / uptime, 2) if uptime > 0 else 0
            }


class RequestTracker:
    """请求跟踪器"""
    
    def __init__(self):
        self.metrics = RequestMetrics()
        self.active_requests = {}
        self._cleanup_task = None
        self._start_cleanup_task()
    
    def _start_cleanup_task(self):
        """启动清理任务"""
        async def cleanup_old_requests():
            while True:
                try:
                    current_time = time.time()
                    # 清理超过5分钟的活跃请求记录
                    expired_requests = [
                        req_id for req_id, req_info in self.active_requests.items()
                        if current_time - req_info["start_time"] > 300
                    ]
                    
                    for req_id in expired_requests:
                        del self.active_requests[req_id]
                    
                    await asyncio.sleep(60)  # 每分钟清理一次
                except Exception as e:
                    logger.error(f"清理请求记录失败: {str(e)}")
                    await asyncio.sleep(60)
        
        # 在后台启动清理任务
        try:
            loop = asyncio.get_event_loop()
            self._cleanup_task = loop.create_task(cleanup_old_requests())
        except RuntimeError:
            # 如果没有运行中的事件循环，稍后再启动
            pass
    
    def start_request(self, request: Request) -> str:
        """开始跟踪请求"""
        request_id = str(uuid.uuid4())
        
        self.active_requests[request_id] = {
            "start_time": time.time(),
            "endpoint": str(request.url.path),
            "method": request.method,
            "client_ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", "unknown")
        }
        
        return request_id
    
    def end_request(
        self,
        request_id: str,
        status_code: int,
        error: Optional[str] = None
    ):
        """结束跟踪请求"""
        if request_id not in self.active_requests:
            logger.warning(f"未找到请求ID: {request_id}")
            return
        
        request_info = self.active_requests.pop(request_id)
        response_time = time.time() - request_info["start_time"]
        
        self.metrics.add_request(
            endpoint=request_info["endpoint"],
            method=request_info["method"],
            status_code=status_code,
            response_time=response_time,
            error=error
        )
        
        # 记录日志
        log_level = logging.INFO if 200 <= status_code < 400 else logging.WARNING
        logger.log(
            log_level,
            f"{request_info['method']} {request_info['endpoint']} - "
            f"{status_code} - {response_time:.3f}s - {request_info['client_ip']}"
        )
    
    def get_active_requests(self) -> List[Dict[str, Any]]:
        """获取活跃请求列表"""
        current_time = time.time()
        active_list = []
        
        for request_id, request_info in self.active_requests.items():
            active_list.append({
                "request_id": request_id,
                "endpoint": request_info["endpoint"],
                "method": request_info["method"],
                "duration": round(current_time - request_info["start_time"], 3),
                "client_ip": request_info["client_ip"],
                "user_agent": request_info["user_agent"]
            })
        
        return sorted(active_list, key=lambda x: x["duration"], reverse=True)
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取完整指标"""
        stats = self.metrics.get_stats()
        stats["active_requests"] = {
            "count": len(self.active_requests),
            "details": self.get_active_requests()
        }
        return stats


# 全局请求跟踪器实例
request_tracker = RequestTracker()


def track_request(func):
    """请求跟踪装饰器"""
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        # 开始跟踪请求
        request_id = request_tracker.start_request(request)
        
        try:
            # 执行原函数
            response = await func(request, *args, **kwargs)
            
            # 获取状态码
            if hasattr(response, 'status_code'):
                status_code = response.status_code
            else:
                status_code = 200
            
            # 结束跟踪
            request_tracker.end_request(request_id, status_code)
            
            return response
            
        except Exception as e:
            # 记录错误
            error_msg = str(e)
            status_code = getattr(e, 'status_code', 500)
            
            request_tracker.end_request(request_id, status_code, error_msg)
            
            # 重新抛出异常
            raise
    
    return wrapper


# 便于外部访问的函数
def get_request_metrics() -> Dict[str, Any]:
    """获取请求指标"""
    return request_tracker.get_metrics()


def get_active_requests() -> List[Dict[str, Any]]:
    """获取活跃请求列表"""
    return request_tracker.get_active_requests()


def reset_metrics():
    """重置指标"""
    global request_tracker
    request_tracker = RequestTracker() 