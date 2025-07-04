"""
响应处理工具
用于标准化API响应格式
"""

from typing import Any, Dict, Optional
from datetime import datetime
from fastapi import Response
from fastapi.responses import JSONResponse


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