"""
Task Manager gRPC客户端
用于与Go Task Manager服务通信
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
import grpc
from datetime import datetime

from app.config.settings import settings
from app.queues.task_models import TaskModel, TaskStatus

logger = logging.getLogger(__name__)


class TaskManagerGRPCClient:
    """Task Manager gRPC客户端"""
    
    def __init__(self):
        self.channel = None
        self.stub = None
        self.connected = False
        
        # Task Manager地址
        self.task_manager_address = getattr(settings, 'TASK_MANAGER_ADDRESS', 'localhost:8084')
        
        logger.info(f"初始化Task Manager gRPC客户端，地址: {self.task_manager_address}")
    
    async def initialize(self):
        """初始化gRPC连接"""
        try:
            # 创建gRPC通道
            self.channel = grpc.aio.insecure_channel(self.task_manager_address)
            
            # 测试连接
            await self._test_connection()
            
            self.connected = True
            logger.info("Task Manager gRPC连接建立成功")
            
        except Exception as e:
            logger.error(f"Task Manager gRPC连接失败: {e}")
            self.connected = False
            raise
    
    async def close(self):
        """关闭gRPC连接"""
        if self.channel:
            await self.channel.close()
            self.connected = False
            logger.info("Task Manager gRPC连接已关闭")
    
    async def _test_connection(self):
        """测试gRPC连接"""
        try:
            # 这里应该调用实际的gRPC方法
            # 目前先模拟连接测试
            await asyncio.sleep(0.1)
            logger.debug("gRPC连接测试通过")
        except Exception as e:
            logger.error(f"gRPC连接测试失败: {e}")
            raise
    
    async def get_pending_tasks(self, service_name: str, limit: int = 10) -> List[TaskModel]:
        """获取待处理任务"""
        try:
            if not self.connected:
                logger.warning("gRPC连接未建立，尝试重新连接")
                await self.initialize()
            
            # 模拟从Task Manager获取任务
            # 实际实现应该调用gRPC方法
            tasks = await self._fetch_tasks_from_manager(service_name, limit)
            
            logger.debug(f"获取到 {len(tasks)} 个待处理任务")
            return tasks
            
        except Exception as e:
            logger.error(f"获取待处理任务失败: {e}")
            return []
    
    async def update_task_status(
        self, 
        task_id: str, 
        status: TaskStatus, 
        message: str, 
        progress: int = None,
        result_data: Dict[str, Any] = None,
        error_details: str = None,
        metadata: Dict[str, Any] = None
    ):
        """更新任务状态"""
        try:
            if not self.connected:
                logger.warning("gRPC连接未建立，跳过状态更新")
                return
            
            update_data = {
                "task_id": task_id,
                "status": status.value,
                "message": message,
                "updated_at": datetime.now().isoformat()
            }
            
            if progress is not None:
                update_data["progress"] = progress
            
            if result_data:
                update_data["result_data"] = result_data
            
            if error_details:
                update_data["error_details"] = error_details
            
            if metadata:
                update_data["metadata"] = metadata
            
            # 实际实现应该调用gRPC方法
            await self._send_status_update(update_data)
            
            logger.debug(f"任务状态更新成功: {task_id} -> {status.value}")
            
        except Exception as e:
            logger.error(f"更新任务状态失败: {e}")
    
    async def report_service_status(self, status_data: Dict[str, Any]):
        """报告服务状态"""
        try:
            if not self.connected:
                return
            
            # 实际实现应该调用gRPC方法
            await self._send_service_status(status_data)
            
            logger.debug("服务状态报告成功")
            
        except Exception as e:
            logger.error(f"报告服务状态失败: {e}")
    
    async def _fetch_tasks_from_manager(self, service_name: str, limit: int) -> List[TaskModel]:
        """从Task Manager获取任务（模拟实现）"""
        # 这里是模拟实现，实际应该调用gRPC
        # 为了演示，返回一些模拟任务
        
        if not hasattr(self, '_mock_tasks'):
            self._mock_tasks = []
        
        # 模拟任务队列为空的情况
        return self._mock_tasks[:limit]
    
    async def _send_status_update(self, update_data: Dict[str, Any]):
        """发送状态更新（模拟实现）"""
        # 实际实现：
        # request = TaskStatusUpdateRequest(**update_data)
        # response = await self.stub.UpdateTaskStatus(request)
        
        logger.debug(f"发送状态更新: {update_data}")
        await asyncio.sleep(0.01)  # 模拟网络延迟
    
    async def _send_service_status(self, status_data: Dict[str, Any]):
        """发送服务状态（模拟实现）"""
        # 实际实现：
        # request = ServiceStatusRequest(**status_data)
        # response = await self.stub.ReportServiceStatus(request)
        
        logger.debug(f"发送服务状态: {status_data}")
        await asyncio.sleep(0.01)  # 模拟网络延迟
    
    async def submit_task_result(self, task_id: str, result: Dict[str, Any]):
        """提交任务结果"""
        try:
            if not self.connected:
                return
            
            result_data = {
                "task_id": task_id,
                "result": result,
                "completed_at": datetime.now().isoformat()
            }
            
            # 实际实现应该调用gRPC方法
            await self._send_task_result(result_data)
            
            logger.debug(f"任务结果提交成功: {task_id}")
            
        except Exception as e:
            logger.error(f"提交任务结果失败: {e}")
    
    async def _send_task_result(self, result_data: Dict[str, Any]):
        """发送任务结果（模拟实现）"""
        logger.debug(f"发送任务结果: {result_data}")
        await asyncio.sleep(0.01)
    
    async def request_task_cancellation(self, task_id: str, reason: str = ""):
        """请求取消任务"""
        try:
            if not self.connected:
                return
            
            cancel_data = {
                "task_id": task_id,
                "reason": reason,
                "cancelled_by": "knowledge-service",
                "cancelled_at": datetime.now().isoformat()
            }
            
            await self._send_cancellation_request(cancel_data)
            
            logger.debug(f"任务取消请求发送成功: {task_id}")
            
        except Exception as e:
            logger.error(f"请求取消任务失败: {e}")
    
    async def _send_cancellation_request(self, cancel_data: Dict[str, Any]):
        """发送取消请求（模拟实现）"""
        logger.debug(f"发送取消请求: {cancel_data}")
        await asyncio.sleep(0.01)
    
    async def get_task_details(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务详情"""
        try:
            if not self.connected:
                return None
            
            # 实际实现应该调用gRPC方法
            task_details = await self._fetch_task_details(task_id)
            
            logger.debug(f"获取任务详情成功: {task_id}")
            return task_details
            
        except Exception as e:
            logger.error(f"获取任务详情失败: {e}")
            return None
    
    async def _fetch_task_details(self, task_id: str) -> Dict[str, Any]:
        """获取任务详情（模拟实现）"""
        # 模拟返回任务详情
        return {
            "task_id": task_id,
            "status": "processing",
            "created_at": datetime.now().isoformat(),
            "metadata": {}
        }
    
    def is_connected(self) -> bool:
        """检查连接状态"""
        return self.connected
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            if not self.connected:
                return False
            
            # 实际实现应该调用健康检查gRPC方法
            await asyncio.sleep(0.01)
            return True
            
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return False