"""
代理工具类
用于转发请求到微服务，处理HTTP请求代理
"""

import aiohttp
import asyncio
import logging
import json
from typing import Dict, Any, Optional, List
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
import time
from datetime import datetime

logger = logging.getLogger(__name__)


class ProxyUtils:
    """HTTP代理工具类"""
    
    def __init__(self, timeout: int = 30, max_retries: int = 3):
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max_retries
        self.session = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建HTTP会话"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self.session
    
    async def close(self):
        """关闭HTTP会话"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def forward_request(
        self,
        request: Request,
        target_url: str,
        auth_required: bool = True,
        headers_override: Optional[Dict[str, str]] = None,
        timeout_override: Optional[int] = None
    ) -> Response:
        """转发HTTP请求到目标服务"""
        session = await self._get_session()
        method = request.method
        
        # 构建请求头
        headers = dict(request.headers)
        
        # 移除可能导致问题的头部
        headers_to_remove = [
            "host", "content-length", "transfer-encoding",
            "connection", "upgrade", "proxy-connection"
        ]
        for header in headers_to_remove:
            headers.pop(header, None)
        
        # 应用头部覆盖
        if headers_override:
            headers.update(headers_override)
        
        # 处理请求体
        body = None
        if method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
            except Exception as e:
                logger.error(f"读取请求体失败: {str(e)}")
                body = None
        
        # 构建查询参数
        query_params = dict(request.query_params)
        
        # 设置超时
        request_timeout = timeout_override or self.timeout.total
        timeout = aiohttp.ClientTimeout(total=request_timeout)
        
        # 执行请求
        for attempt in range(self.max_retries + 1):
            try:
                start_time = time.time()
                
                async with session.request(
                    method=method,
                    url=target_url,
                    headers=headers,
                    data=body,
                    params=query_params,
                    timeout=timeout,
                    allow_redirects=False
                ) as response:
                    
                    response_time = time.time() - start_time
                    
                    # 读取响应内容
                    content = await response.read()
                    
                    # 构建响应头
                    response_headers = dict(response.headers)
                    
                    # 移除可能导致问题的响应头
                    response_headers.pop("content-length", None)
                    response_headers.pop("transfer-encoding", None)
                    response_headers.pop("connection", None)
                    
                    # 记录请求日志
                    logger.info(
                        f"代理请求: {method} {target_url} -> {response.status} "
                        f"({response_time:.3f}s)"
                    )
                    
                    # 返回响应
                    return Response(
                        content=content,
                        status_code=response.status,
                        headers=response_headers,
                        media_type=response_headers.get("content-type", "application/json")
                    )
                    
            except asyncio.TimeoutError:
                logger.warning(f"请求超时 (尝试 {attempt + 1}/{self.max_retries + 1}): {target_url}")
                if attempt == self.max_retries:
                    raise HTTPException(status_code=504, detail="请求超时")
                await asyncio.sleep(2 ** attempt)  # 指数退避
                
            except aiohttp.ClientConnectorError as e:
                logger.error(f"连接错误 (尝试 {attempt + 1}/{self.max_retries + 1}): {str(e)}")
                if attempt == self.max_retries:
                    raise HTTPException(status_code=503, detail="服务不可用")
                await asyncio.sleep(2 ** attempt)
                
            except Exception as e:
                logger.error(f"代理请求失败 (尝试 {attempt + 1}/{self.max_retries + 1}): {str(e)}")
                if attempt == self.max_retries:
                    raise HTTPException(status_code=500, detail="代理请求失败")
                await asyncio.sleep(1)
    
    async def forward_streaming_request(
        self,
        request: Request,
        target_url: str,
        headers_override: Optional[Dict[str, str]] = None
    ) -> StreamingResponse:
        """转发流式HTTP请求"""
        session = await self._get_session()
        method = request.method
        
        # 构建请求头
        headers = dict(request.headers)
        headers_to_remove = [
            "host", "content-length", "transfer-encoding",
            "connection", "upgrade", "proxy-connection"
        ]
        for header in headers_to_remove:
            headers.pop(header, None)
        
        if headers_override:
            headers.update(headers_override)
        
        # 处理请求体
        body = None
        if method in ["POST", "PUT", "PATCH"]:
            body = await request.body()
        
        query_params = dict(request.query_params)
        
        try:
            async with session.request(
                method=method,
                url=target_url,
                headers=headers,
                data=body,
                params=query_params,
                allow_redirects=False
            ) as response:
                
                async def stream_generator():
                    async for chunk in response.content.iter_chunked(8192):
                        yield chunk
                
                response_headers = dict(response.headers)
                response_headers.pop("content-length", None)
                response_headers.pop("transfer-encoding", None)
                
                return StreamingResponse(
                    stream_generator(),
                    status_code=response.status,
                    headers=response_headers,
                    media_type=response_headers.get("content-type", "application/octet-stream")
                )
                
        except Exception as e:
            logger.error(f"流式代理请求失败: {str(e)}")
            raise HTTPException(status_code=500, detail="流式代理请求失败")
    
    async def make_internal_request(
        self,
        method: str,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """发起内部服务调用"""
        session = await self._get_session()
        
        request_headers = {
            "Content-Type": "application/json"
        }
        if headers:
            request_headers.update(headers)
        
        request_timeout = aiohttp.ClientTimeout(total=timeout or self.timeout.total)
        
        try:
            async with session.request(
                method=method,
                url=url,
                json=data,
                headers=request_headers,
                timeout=request_timeout
            ) as response:
                
                if response.content_type == 'application/json':
                    return await response.json()
                else:
                    text_content = await response.text()
                    return {"content": text_content, "status_code": response.status}
                    
        except Exception as e:
            logger.error(f"内部请求失败: {method} {url} - {str(e)}")
            raise
    
    async def check_service_health(self, health_url: str) -> bool:
        """检查服务健康状态"""
        session = await self._get_session()
        
        try:
            async with session.get(
                health_url,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                return response.status == 200
                
        except Exception as e:
            logger.debug(f"健康检查失败: {health_url} - {str(e)}")
            return False
    
    async def batch_health_check(self, health_urls: List[str]) -> Dict[str, bool]:
        """批量健康检查"""
        tasks = []
        for url in health_urls:
            task = asyncio.create_task(self.check_service_health(url))
            tasks.append((url, task))
        
        results = {}
        for url, task in tasks:
            try:
                results[url] = await task
            except Exception:
                results[url] = False
        
        return results
    
    def build_target_url(self, base_url: str, path: str) -> str:
        """构建目标URL"""
        # 移除base_url末尾的斜杠
        base_url = base_url.rstrip('/')
        
        # 确保path以斜杠开头
        if not path.startswith('/'):
            path = '/' + path
        
        return f"{base_url}{path}"
    
    def extract_service_error(self, response_content: bytes) -> Optional[str]:
        """从响应中提取服务错误信息"""
        try:
            content_str = response_content.decode('utf-8')
            
            # 尝试解析JSON错误
            try:
                error_data = json.loads(content_str)
                if isinstance(error_data, dict):
                    return error_data.get('detail') or error_data.get('message') or error_data.get('error')
            except json.JSONDecodeError:
                pass
            
            # 如果不是JSON，返回前100个字符
            return content_str[:100] if content_str else None
            
        except Exception:
            return None


# 响应处理工具
class ResponseHandler:
    """响应处理工具"""
    
    @staticmethod
    def create_error_response(
        status_code: int,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> JSONResponse:
        """创建错误响应"""
        error_data = {
            "error": True,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "status_code": status_code
        }
        
        if details:
            error_data["details"] = details
        
        return JSONResponse(
            content=error_data,
            status_code=status_code
        )
    
    @staticmethod
    def create_success_response(
        data: Any,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> JSONResponse:
        """创建成功响应"""
        response_data = {
            "success": True,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        
        if message:
            response_data["message"] = message
        
        if metadata:
            response_data["metadata"] = metadata
        
        return JSONResponse(content=response_data)
    
    @staticmethod
    def wrap_service_response(
        service_response: Response,
        service_name: str
    ) -> Response:
        """包装服务响应，添加元数据"""
        # 在响应头中添加服务信息
        service_response.headers["X-Service-Name"] = service_name
        service_response.headers["X-Gateway-Timestamp"] = datetime.now().isoformat()
        
        return service_response 