"""
SSE消息推送客户端
用于向消息推送服务发送实时进度更新
"""

import asyncio
import logging
import httpx
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class SSEMessageClient:
    """SSE消息推送客户端"""
    
    def __init__(self, message_push_url: str = "http://localhost:8089"):
        self.message_push_url = message_push_url
        self.send_message_url = f"{message_push_url}/sse/api/v1/messages/send"
        
    async def send_progress_message(
        self,
        user_id: str,
        task_id: str,
        progress: int,
        stage: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """发送进度消息"""
        try:
            message_data = {
                "type": "progress",
                "service": "knowledge-service", 
                "source": "document_processing",
                "target": {
                    "user_id": user_id,
                    "task_id": task_id
                },
                "data": {
                    "task_id": task_id,
                    "progress": progress,
                    "stage": stage,
                    "message": message,
                    "details": details or {},
                    "timestamp": datetime.now().isoformat()
                }
            }
            
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    self.send_message_url,
                    json=message_data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"进度消息发送成功: {progress}% - {message}")
                    return True
                else:
                    logger.warning(f"进度消息发送失败: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"发送进度消息异常: {e}")
            return False
    
    async def send_status_message(
        self,
        user_id: str,
        task_id: str,
        status: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """发送状态变更消息"""
        try:
            message_data = {
                "type": "status",
                "service": "knowledge-service",
                "source": "document_processing", 
                "target": {
                    "user_id": user_id,
                    "task_id": task_id
                },
                "data": {
                    "task_id": task_id,
                    "status": status,
                    "message": message,
                    "data": data or {},
                    "timestamp": datetime.now().isoformat()
                }
            }
            
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    self.send_message_url,
                    json=message_data
                )
                
                if response.status_code == 200:
                    logger.info(f"状态消息发送成功: {status} - {message}")
                    return True
                else:
                    logger.warning(f"状态消息发送失败: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"发送状态消息异常: {e}")
            return False
    
    async def send_error_message(
        self,
        user_id: str,
        task_id: str,
        error_message: str,
        error_details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """发送错误消息"""
        try:
            message_data = {
                "type": "error",
                "service": "knowledge-service",
                "source": "document_processing",
                "target": {
                    "user_id": user_id,
                    "task_id": task_id
                },
                "data": {
                    "task_id": task_id,
                    "error_message": error_message,
                    "error_details": error_details or {},
                    "timestamp": datetime.now().isoformat()
                }
            }
            
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    self.send_message_url,
                    json=message_data
                )
                
                if response.status_code == 200:
                    logger.info(f"错误消息发送成功: {error_message}")
                    return True
                else:
                    logger.warning(f"错误消息发送失败: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"发送错误消息异常: {e}")
            return False
    
    async def send_success_message(
        self,
        user_id: str,
        task_id: str,
        message: str,
        result_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """发送成功完成消息"""
        try:
            message_data = {
                "type": "success",
                "service": "knowledge-service",
                "source": "document_processing",
                "target": {
                    "user_id": user_id,
                    "task_id": task_id
                },
                "data": {
                    "task_id": task_id,
                    "message": message,
                    "result": result_data or {},
                    "timestamp": datetime.now().isoformat()
                }
            }
            
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    self.send_message_url,
                    json=message_data
                )
                
                if response.status_code == 200:
                    logger.info(f"成功消息发送成功: {message}")
                    return True
                else:
                    logger.warning(f"成功消息发送失败: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"发送成功消息异常: {e}")
            return False


# 全局SSE客户端实例
sse_client = SSEMessageClient()


async def send_document_progress(
    user_id: str,
    document_id: str,
    progress: int,
    stage: str,
    message: str,
    details: Optional[Dict[str, Any]] = None
):
    """发送文档处理进度（便捷方法）"""
    await sse_client.send_progress_message(
        user_id=user_id,
        task_id=f"doc_{document_id}",
        progress=progress,
        stage=stage,
        message=message,
        details=details
    )


async def send_document_status(
    user_id: str,
    document_id: str,
    status: str,
    message: str,
    data: Optional[Dict[str, Any]] = None
):
    """发送文档状态变更（便捷方法）"""
    await sse_client.send_status_message(
        user_id=user_id,
        task_id=f"doc_{document_id}",
        status=status,
        message=message,
        data=data
    )


async def send_document_error(
    user_id: str,
    document_id: str,
    error_message: str,
    error_details: Optional[Dict[str, Any]] = None
):
    """发送文档处理错误（便捷方法）"""
    await sse_client.send_error_message(
        user_id=user_id,
        task_id=f"doc_{document_id}",
        error_message=error_message,
        error_details=error_details
    )


async def send_document_success(
    user_id: str,
    document_id: str,
    message: str,
    result_data: Optional[Dict[str, Any]] = None
):
    """发送文档处理成功（便捷方法）"""
    await sse_client.send_success_message(
        user_id=user_id,
        task_id=f"doc_{document_id}",
        message=message,
        result_data=result_data
    )