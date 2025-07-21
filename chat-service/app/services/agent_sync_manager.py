"""
智能体状态同步管理器 - 与Agent-Service保持状态一致性
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, List, Set
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import json

from shared.service_client import call_service, CallMethod, CallConfig, RetryStrategy
from app.core.redis import redis_manager
from app.core.config import settings
from app.services.agent_pool_manager import AgentInstance, AgentStatus, get_agent_pool_manager

logger = logging.getLogger(__name__)


class SyncEventType(str, Enum):
    """同步事件类型"""
    AGENT_CREATED = "agent_created"
    AGENT_UPDATED = "agent_updated"
    AGENT_DELETED = "agent_deleted"
    INSTANCE_CREATED = "instance_created"
    INSTANCE_UPDATED = "instance_updated"
    INSTANCE_DELETED = "instance_deleted"
    STATUS_CHANGED = "status_changed"
    HEALTH_CHECK = "health_check"


@dataclass
class SyncEvent:
    """同步事件"""
    event_type: SyncEventType
    agent_id: str
    instance_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    retry_count: int = 0
    max_retries: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "agent_id": self.agent_id,
            "instance_id": self.instance_id,
            "data": self.data,
            "timestamp": self.timestamp,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries
        }


class AgentSyncManager:
    """智能体状态同步管理器"""
    
    def __init__(self):
        self.sync_queue: asyncio.Queue = asyncio.Queue()
        self.sync_interval = 30  # 秒
        self.full_sync_interval = 300  # 5分钟
        self.agent_states: Dict[str, Dict[str, Any]] = {}
        self.instance_states: Dict[str, Dict[str, Any]] = {}
        self.last_full_sync = 0
        
        # 同步统计
        self.sync_metrics = {
            "successful_syncs": 0,
            "failed_syncs": 0,
            "events_processed": 0,
            "last_sync_time": 0,
            "sync_errors": []
        }
        
        # 启动同步任务
        self._sync_task = None
        self._full_sync_task = None
        self._start_sync_tasks()
    
    async def sync_agent_from_service(self, agent_id: str) -> Dict[str, Any]:
        """从Agent-Service同步智能体信息"""
        try:
            sync_config = CallConfig(
                timeout=10,
                retry_times=3,
                retry_strategy=RetryStrategy.EXPONENTIAL
            )
            
            # 获取智能体详细信息
            response = await call_service(
                service_name="agent-service",
                method=CallMethod.GET,
                path=f"/api/v1/agents/{agent_id}",
                config=sync_config
            )
            
            if not response.get("success"):
                logger.error(f"同步智能体信息失败: {response.get('error')}")
                return {"success": False, "error": response.get("error")}
            
            agent_data = response.get("agent", {})
            
            # 更新本地状态
            self.agent_states[agent_id] = {
                "agent_id": agent_id,
                "name": agent_data.get("name"),
                "description": agent_data.get("description"),
                "status": agent_data.get("status", "active"),
                "config": agent_data.get("config", {}),
                "capabilities": agent_data.get("capabilities", []),
                "last_updated": agent_data.get("updated_at"),
                "sync_timestamp": time.time()
            }
            
            # 持久化到Redis
            await self._persist_agent_state(agent_id)
            
            # 同步智能体实例
            await self._sync_agent_instances(agent_id)
            
            return {"success": True, "agent_data": self.agent_states[agent_id]}
            
        except Exception as e:
            logger.error(f"同步智能体失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _sync_agent_instances(self, agent_id: str) -> List[Dict[str, Any]]:
        """同步智能体实例"""
        try:
            sync_config = CallConfig(timeout=10, retry_times=2)
            
            # 获取智能体实例列表
            response = await call_service(
                service_name="agent-service",
                method=CallMethod.GET,
                path=f"/api/v1/agents/{agent_id}/instances",
                config=sync_config
            )
            
            if not response.get("success"):
                logger.warning(f"获取智能体实例失败: {response.get('error')}")
                return []
            
            instances_data = response.get("instances", [])
            synced_instances = []
            
            for instance_data in instances_data:
                instance_id = instance_data.get("instance_id")
                if not instance_id:
                    continue
                
                # 更新实例状态
                self.instance_states[instance_id] = {
                    "instance_id": instance_id,
                    "agent_id": agent_id,
                    "status": instance_data.get("status", "unknown"),
                    "health": instance_data.get("health", {}),
                    "performance": instance_data.get("performance", {}),
                    "service_url": instance_data.get("service_url"),
                    "created_at": instance_data.get("created_at"),
                    "last_activity": instance_data.get("last_activity"),
                    "sync_timestamp": time.time()
                }
                
                synced_instances.append(self.instance_states[instance_id])
                
                # 持久化实例状态
                await self._persist_instance_state(instance_id)
                
                # 同步到池管理器
                await self._sync_to_pool_manager(instance_id, instance_data)
            
            return synced_instances
            
        except Exception as e:
            logger.error(f"同步智能体实例失败: {e}")
            return []
    
    async def _sync_to_pool_manager(self, instance_id: str, instance_data: Dict[str, Any]):
        """同步到池管理器"""
        try:
            pool_manager = get_agent_pool_manager()
            
            # 检查实例是否已存在于池中
            existing_instance = pool_manager.instances.get(instance_id)
            
            if existing_instance:
                # 更新现有实例
                existing_instance.status = AgentStatus(instance_data.get("status", "idle"))
                
                # 更新健康信息
                health_data = instance_data.get("health", {})
                existing_instance.cpu_usage = health_data.get("cpu_usage", 0)
                existing_instance.memory_usage = health_data.get("memory_usage", 0)
                existing_instance.health_score = health_data.get("health_score", 100)
                
                # 更新性能信息
                performance_data = instance_data.get("performance", {})
                existing_instance.active_sessions = performance_data.get("active_sessions", 0)
                existing_instance.total_requests = performance_data.get("total_requests", 0)
                existing_instance.successful_requests = performance_data.get("successful_requests", 0)
                existing_instance.failed_requests = performance_data.get("failed_requests", 0)
                existing_instance.average_response_time = performance_data.get("average_response_time", 0)
                
                # 更新同步时间
                existing_instance.last_health_check = time.time()
                
                logger.debug(f"同步更新实例: {instance_id}")
            else:
                # 创建新实例（如果在Agent-Service中存在但池中没有）
                agent_id = instance_data.get("agent_id")
                if agent_id:
                    new_instance = AgentInstance(
                        instance_id=instance_id,
                        agent_id=agent_id,
                        service_url=instance_data.get("service_url", ""),
                        status=AgentStatus(instance_data.get("status", "idle")),
                        created_at=instance_data.get("created_at", time.time())
                    )
                    
                    # 添加到池中
                    pool_manager.instances[instance_id] = new_instance
                    if agent_id not in pool_manager.agent_instances:
                        pool_manager.agent_instances[agent_id] = []
                    pool_manager.agent_instances[agent_id].append(instance_id)
                    
                    logger.info(f"同步创建实例: {instance_id}")
        
        except Exception as e:
            logger.error(f"同步到池管理器失败: {e}")
    
    async def report_instance_status(
        self, 
        instance_id: str, 
        status_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """向Agent-Service报告实例状态"""
        try:
            agent_id = status_data.get("agent_id")
            if not agent_id:
                return {"success": False, "error": "缺少agent_id"}
            
            report_config = CallConfig(
                timeout=5,
                retry_times=2,
                retry_strategy=RetryStrategy.LINEAR
            )
            
            # 构造状态报告
            status_report = {
                "instance_id": instance_id,
                "status": status_data.get("status", "idle"),
                "health": {
                    "cpu_usage": status_data.get("cpu_usage", 0),
                    "memory_usage": status_data.get("memory_usage", 0),
                    "health_score": status_data.get("health_score", 100),
                    "last_check": time.time()
                },
                "performance": {
                    "active_sessions": status_data.get("active_sessions", 0),
                    "total_requests": status_data.get("total_requests", 0),
                    "successful_requests": status_data.get("successful_requests", 0),
                    "failed_requests": status_data.get("failed_requests", 0),
                    "average_response_time": status_data.get("average_response_time", 0),
                    "error_rate": status_data.get("error_rate", 0)
                },
                "timestamp": time.time()
            }
            
            # 发送状态报告
            response = await call_service(
                service_name="agent-service",
                method=CallMethod.POST,
                path=f"/api/v1/agents/{agent_id}/instances/{instance_id}/status",
                config=report_config,
                json=status_report
            )
            
            if response.get("success"):
                logger.debug(f"状态报告成功: {instance_id}")
                self.sync_metrics["successful_syncs"] += 1
            else:
                logger.warning(f"状态报告失败: {response.get('error')}")
                self.sync_metrics["failed_syncs"] += 1
            
            return response
            
        except Exception as e:
            logger.error(f"报告实例状态失败: {e}")
            self.sync_metrics["failed_syncs"] += 1
            return {"success": False, "error": str(e)}
    
    async def handle_agent_event(self, event: SyncEvent):
        """处理智能体事件"""
        try:
            if event.event_type == SyncEventType.AGENT_CREATED:
                await self._handle_agent_created(event)
            elif event.event_type == SyncEventType.AGENT_UPDATED:
                await self._handle_agent_updated(event)
            elif event.event_type == SyncEventType.AGENT_DELETED:
                await self._handle_agent_deleted(event)
            elif event.event_type == SyncEventType.INSTANCE_CREATED:
                await self._handle_instance_created(event)
            elif event.event_type == SyncEventType.INSTANCE_UPDATED:
                await self._handle_instance_updated(event)
            elif event.event_type == SyncEventType.INSTANCE_DELETED:
                await self._handle_instance_deleted(event)
            elif event.event_type == SyncEventType.STATUS_CHANGED:
                await self._handle_status_changed(event)
            
            self.sync_metrics["events_processed"] += 1
            
        except Exception as e:
            logger.error(f"处理智能体事件失败: {e}")
            
            # 增加重试计数
            event.retry_count += 1
            if event.retry_count < event.max_retries:
                # 重新加入队列
                await self.sync_queue.put(event)
            else:
                logger.error(f"事件处理失败，超过最大重试次数: {event.to_dict()}")
    
    async def _handle_agent_created(self, event: SyncEvent):
        """处理智能体创建事件"""
        agent_id = event.agent_id
        await self.sync_agent_from_service(agent_id)
        logger.info(f"处理智能体创建事件: {agent_id}")
    
    async def _handle_agent_updated(self, event: SyncEvent):
        """处理智能体更新事件"""
        agent_id = event.agent_id
        await self.sync_agent_from_service(agent_id)
        logger.info(f"处理智能体更新事件: {agent_id}")
    
    async def _handle_agent_deleted(self, event: SyncEvent):
        """处理智能体删除事件"""
        agent_id = event.agent_id
        
        # 从本地状态中移除
        if agent_id in self.agent_states:
            del self.agent_states[agent_id]
        
        # 移除相关实例
        pool_manager = get_agent_pool_manager()
        if agent_id in pool_manager.agent_instances:
            instance_ids = pool_manager.agent_instances[agent_id].copy()
            for instance_id in instance_ids:
                await pool_manager._remove_instance(instance_id)
        
        # 从Redis中移除
        agent_key = f"agent_sync:agent:{agent_id}"
        redis_manager.delete(agent_key)
        
        logger.info(f"处理智能体删除事件: {agent_id}")
    
    async def _handle_instance_created(self, event: SyncEvent):
        """处理实例创建事件"""
        agent_id = event.agent_id
        instance_id = event.instance_id
        
        if instance_id:
            # 同步特定实例
            await self._sync_single_instance(agent_id, instance_id)
        else:
            # 同步所有实例
            await self._sync_agent_instances(agent_id)
        
        logger.info(f"处理实例创建事件: {agent_id}/{instance_id}")
    
    async def _handle_instance_updated(self, event: SyncEvent):
        """处理实例更新事件"""
        await self._handle_instance_created(event)  # 使用相同逻辑
    
    async def _handle_instance_deleted(self, event: SyncEvent):
        """处理实例删除事件"""
        instance_id = event.instance_id
        if not instance_id:
            return
        
        # 从本地状态中移除
        if instance_id in self.instance_states:
            del self.instance_states[instance_id]
        
        # 从池管理器中移除
        pool_manager = get_agent_pool_manager()
        await pool_manager._remove_instance(instance_id)
        
        # 从Redis中移除
        instance_key = f"agent_sync:instance:{instance_id}"
        redis_manager.delete(instance_key)
        
        logger.info(f"处理实例删除事件: {instance_id}")
    
    async def _handle_status_changed(self, event: SyncEvent):
        """处理状态变更事件"""
        instance_id = event.instance_id
        if not instance_id:
            return
        
        # 更新实例状态
        status_data = event.data
        pool_manager = get_agent_pool_manager()
        instance = pool_manager.instances.get(instance_id)
        
        if instance:
            new_status = status_data.get("status")
            if new_status:
                instance.status = AgentStatus(new_status)
                await pool_manager._update_instance_status(instance)
        
        logger.debug(f"处理状态变更事件: {instance_id} -> {status_data.get('status')}")
    
    async def _sync_single_instance(self, agent_id: str, instance_id: str):
        """同步单个实例"""
        try:
            sync_config = CallConfig(timeout=10, retry_times=2)
            
            response = await call_service(
                service_name="agent-service",
                method=CallMethod.GET,
                path=f"/api/v1/agents/{agent_id}/instances/{instance_id}",
                config=sync_config
            )
            
            if response.get("success"):
                instance_data = response.get("instance", {})
                await self._sync_to_pool_manager(instance_id, instance_data)
        
        except Exception as e:
            logger.error(f"同步单个实例失败: {e}")
    
    async def perform_full_sync(self) -> Dict[str, Any]:
        """执行完整同步"""
        try:
            start_time = time.time()
            sync_results = {
                "agents_synced": 0,
                "instances_synced": 0,
                "errors": []
            }
            
            # 获取所有智能体列表
            list_config = CallConfig(timeout=30, retry_times=2)
            
            response = await call_service(
                service_name="agent-service",
                method=CallMethod.GET,
                path="/api/v1/agents",
                config=list_config
            )
            
            if not response.get("success"):
                error_msg = f"获取智能体列表失败: {response.get('error')}"
                sync_results["errors"].append(error_msg)
                return sync_results
            
            agents = response.get("agents", [])
            
            # 同步每个智能体
            for agent_data in agents:
                agent_id = agent_data.get("agent_id")
                if not agent_id:
                    continue
                
                try:
                    sync_result = await self.sync_agent_from_service(agent_id)
                    if sync_result.get("success"):
                        sync_results["agents_synced"] += 1
                        
                        # 统计同步的实例数
                        instances = await self._sync_agent_instances(agent_id)
                        sync_results["instances_synced"] += len(instances)
                    else:
                        sync_results["errors"].append(f"同步智能体 {agent_id} 失败: {sync_result.get('error')}")
                
                except Exception as e:
                    error_msg = f"同步智能体 {agent_id} 异常: {str(e)}"
                    sync_results["errors"].append(error_msg)
                    logger.error(error_msg)
            
            # 清理不存在的智能体
            await self._cleanup_orphaned_agents(set(agent["agent_id"] for agent in agents if agent.get("agent_id")))
            
            # 更新同步时间
            self.last_full_sync = time.time()
            sync_results["sync_duration"] = self.last_full_sync - start_time
            sync_results["timestamp"] = datetime.now().isoformat()
            
            logger.info(f"完整同步完成: {sync_results}")
            return sync_results
            
        except Exception as e:
            logger.error(f"完整同步失败: {e}")
            return {
                "agents_synced": 0,
                "instances_synced": 0,
                "errors": [str(e)]
            }
    
    async def _cleanup_orphaned_agents(self, valid_agent_ids: Set[str]):
        """清理孤立的智能体"""
        try:
            # 清理本地状态中不存在的智能体
            orphaned_agents = set(self.agent_states.keys()) - valid_agent_ids
            
            for agent_id in orphaned_agents:
                logger.info(f"清理孤立智能体: {agent_id}")
                await self._handle_agent_deleted(SyncEvent(
                    event_type=SyncEventType.AGENT_DELETED,
                    agent_id=agent_id
                ))
        
        except Exception as e:
            logger.error(f"清理孤立智能体失败: {e}")
    
    async def _persist_agent_state(self, agent_id: str):
        """持久化智能体状态"""
        try:
            agent_state = self.agent_states.get(agent_id)
            if agent_state:
                agent_key = f"agent_sync:agent:{agent_id}"
                redis_manager.set_json(agent_key, agent_state, ex=3600)
        except Exception as e:
            logger.error(f"持久化智能体状态失败: {e}")
    
    async def _persist_instance_state(self, instance_id: str):
        """持久化实例状态"""
        try:
            instance_state = self.instance_states.get(instance_id)
            if instance_state:
                instance_key = f"agent_sync:instance:{instance_id}"
                redis_manager.set_json(instance_key, instance_state, ex=3600)
        except Exception as e:
            logger.error(f"持久化实例状态失败: {e}")
    
    def _start_sync_tasks(self):
        """启动同步任务"""
        async def sync_event_processor():
            """处理同步事件队列"""
            while True:
                try:
                    event = await self.sync_queue.get()
                    await self.handle_agent_event(event)
                    self.sync_queue.task_done()
                except Exception as e:
                    logger.error(f"同步事件处理循环错误: {e}")
        
        async def periodic_sync():
            """定期同步"""
            while True:
                try:
                    await asyncio.sleep(self.sync_interval)
                    
                    # 检查是否需要完整同步
                    if time.time() - self.last_full_sync > self.full_sync_interval:
                        await self.perform_full_sync()
                    
                    # 更新同步指标
                    self.sync_metrics["last_sync_time"] = time.time()
                
                except Exception as e:
                    logger.error(f"定期同步循环错误: {e}")
        
        self._sync_task = asyncio.create_task(sync_event_processor())
        self._full_sync_task = asyncio.create_task(periodic_sync())
    
    async def add_sync_event(self, event: SyncEvent):
        """添加同步事件"""
        await self.sync_queue.put(event)
    
    def get_sync_status(self) -> Dict[str, Any]:
        """获取同步状态"""
        return {
            "sync_metrics": self.sync_metrics,
            "queue_size": self.sync_queue.qsize(),
            "agent_count": len(self.agent_states),
            "instance_count": len(self.instance_states),
            "last_full_sync": self.last_full_sync,
            "next_full_sync": self.last_full_sync + self.full_sync_interval,
            "configuration": {
                "sync_interval": self.sync_interval,
                "full_sync_interval": self.full_sync_interval
            },
            "timestamp": time.time()
        }
    
    async def cleanup(self):
        """清理资源"""
        try:
            # 取消同步任务
            if self._sync_task:
                self._sync_task.cancel()
            if self._full_sync_task:
                self._full_sync_task.cancel()
            
            # 等待队列处理完成
            await self.sync_queue.join()
            
            logger.info("智能体同步管理器清理完成")
        
        except Exception as e:
            logger.error(f"清理智能体同步管理器失败: {e}")


# 全局实例
_agent_sync_manager: Optional[AgentSyncManager] = None


def get_agent_sync_manager() -> AgentSyncManager:
    """获取智能体同步管理器实例"""
    global _agent_sync_manager
    if _agent_sync_manager is None:
        _agent_sync_manager = AgentSyncManager()
    return _agent_sync_manager