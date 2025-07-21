"""
状态管理器 - 事件驱动工作流的状态管理和持久化
基于Redis和PostgreSQL的双层存储架构
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from uuid import UUID
import uuid

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, update, delete

from ..models.workflow import Workflow, WorkflowStage, WorkflowRole, WorkflowExecution
from ..models.task import Task, TaskComment, TaskActivity
from ..models.event import Event, EventHandler, EventSubscription, EventRule
from ..models.board import Board, BoardColumn


logger = logging.getLogger(__name__)


class StateManager:
    """状态管理器 - 负责数据状态的管理和持久化"""
    
    def __init__(self):
        self.redis = None
        self.db_engine = None
        self.async_session = None
        self._cache_ttl = 3600  # 1小时缓存
        self._is_initialized = False
        
    async def initialize(self):
        """初始化状态管理器"""
        logger.info("🚀 初始化状态管理器...")
        
        try:
            # 初始化Redis连接
            await self._init_redis()
            
            # 初始化数据库连接
            await self._init_database()
            
            self._is_initialized = True
            logger.info("✅ 状态管理器初始化完成")
            
        except Exception as e:
            logger.error(f"❌ 状态管理器初始化失败: {str(e)}")
            raise
    
    async def cleanup(self):
        """清理资源"""
        logger.info("🔄 清理状态管理器资源...")
        
        if self.redis:
            await self.redis.close()
        
        if self.db_engine:
            await self.db_engine.dispose()
        
        logger.info("✅ 状态管理器资源清理完成")
    
    def is_healthy(self) -> bool:
        """检查状态管理器健康状态"""
        return (self._is_initialized and 
                self.redis is not None and 
                self.db_engine is not None)
    
    # ==================== 工作流管理 ====================
    
    async def save_workflow(self, workflow: Workflow) -> None:
        """保存工作流"""
        try:
            async with self.async_session() as session:
                session.add(workflow)
                await session.commit()
                await session.refresh(workflow)
            
            # 缓存到Redis
            await self._cache_workflow(workflow)
            
            logger.info(f"💾 工作流保存成功: {workflow.id}")
            
        except Exception as e:
            logger.error(f"❌ 工作流保存失败: {str(e)}")
            raise
    
    async def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """获取工作流"""
        try:
            # 先从缓存获取
            cached = await self._get_cached_workflow(workflow_id)
            if cached:
                return cached
            
            # 从数据库获取
            async with self.async_session() as session:
                result = await session.execute(
                    select(Workflow).where(Workflow.id == UUID(workflow_id))
                )
                workflow = result.scalar_one_or_none()
                
                if workflow:
                    await self._cache_workflow(workflow)
                
                return workflow
                
        except Exception as e:
            logger.error(f"❌ 获取工作流失败: {workflow_id}, 错误: {str(e)}")
            return None
    
    async def update_workflow(self, workflow: Workflow) -> None:
        """更新工作流"""
        try:
            async with self.async_session() as session:
                await session.merge(workflow)
                await session.commit()
            
            # 更新缓存
            await self._cache_workflow(workflow)
            
            logger.info(f"🔄 工作流更新成功: {workflow.id}")
            
        except Exception as e:
            logger.error(f"❌ 工作流更新失败: {str(e)}")
            raise
    
    async def delete_workflow(self, workflow_id: str) -> bool:
        """删除工作流"""
        try:
            async with self.async_session() as session:
                result = await session.execute(
                    delete(Workflow).where(Workflow.id == UUID(workflow_id))
                )
                await session.commit()
                
                deleted = result.rowcount > 0
                
                if deleted:
                    # 从缓存移除
                    await self._remove_cached_workflow(workflow_id)
                    logger.info(f"🗑️ 工作流删除成功: {workflow_id}")
                
                return deleted
                
        except Exception as e:
            logger.error(f"❌ 工作流删除失败: {workflow_id}, 错误: {str(e)}")
            return False
    
    async def list_workflows(self, page: int = 1, limit: int = 10, status: str = None) -> List[Workflow]:
        """列出工作流"""
        try:
            async with self.async_session() as session:
                query = select(Workflow)
                
                if status:
                    query = query.where(Workflow.status == status)
                
                query = query.offset((page - 1) * limit).limit(limit)
                query = query.order_by(Workflow.created_at.desc())
                
                result = await session.execute(query)
                workflows = result.scalars().all()
                
                return list(workflows)
                
        except Exception as e:
            logger.error(f"❌ 列出工作流失败: {str(e)}")
            return []
    
    # ==================== 工作流阶段管理 ====================
    
    async def save_workflow_stage(self, stage: WorkflowStage) -> None:
        """保存工作流阶段"""
        try:
            async with self.async_session() as session:
                session.add(stage)
                await session.commit()
                await session.refresh(stage)
            
            logger.info(f"💾 工作流阶段保存成功: {stage.id}")
            
        except Exception as e:
            logger.error(f"❌ 工作流阶段保存失败: {str(e)}")
            raise
    
    async def get_workflow_stages(self, workflow_id: str) -> List[WorkflowStage]:
        """获取工作流阶段列表"""
        try:
            async with self.async_session() as session:
                result = await session.execute(
                    select(WorkflowStage)
                    .where(WorkflowStage.workflow_id == UUID(workflow_id))
                    .order_by(WorkflowStage.order_index)
                )
                stages = result.scalars().all()
                return list(stages)
                
        except Exception as e:
            logger.error(f"❌ 获取工作流阶段失败: {workflow_id}, 错误: {str(e)}")
            return []
    
    # ==================== 工作流角色管理 ====================
    
    async def save_workflow_role(self, role: WorkflowRole) -> None:
        """保存工作流角色"""
        try:
            async with self.async_session() as session:
                session.add(role)
                await session.commit()
                await session.refresh(role)
            
            logger.info(f"💾 工作流角色保存成功: {role.id}")
            
        except Exception as e:
            logger.error(f"❌ 工作流角色保存失败: {str(e)}")
            raise
    
    # ==================== 任务管理 ====================
    
    async def save_task(self, task: Task) -> None:
        """保存任务"""
        try:
            async with self.async_session() as session:
                session.add(task)
                await session.commit()
                await session.refresh(task)
            
            # 缓存到Redis
            await self._cache_task(task)
            
            logger.info(f"💾 任务保存成功: {task.id}")
            
        except Exception as e:
            logger.error(f"❌ 任务保存失败: {str(e)}")
            raise
    
    async def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        try:
            # 先从缓存获取
            cached = await self._get_cached_task(task_id)
            if cached:
                return cached
            
            # 从数据库获取
            async with self.async_session() as session:
                result = await session.execute(
                    select(Task).where(Task.id == UUID(task_id))
                )
                task = result.scalar_one_or_none()
                
                if task:
                    await self._cache_task(task)
                
                return task
                
        except Exception as e:
            logger.error(f"❌ 获取任务失败: {task_id}, 错误: {str(e)}")
            return None
    
    async def update_task(self, task: Task) -> None:
        """更新任务"""
        try:
            async with self.async_session() as session:
                await session.merge(task)
                await session.commit()
            
            # 更新缓存
            await self._cache_task(task)
            
            logger.info(f"🔄 任务更新成功: {task.id}")
            
        except Exception as e:
            logger.error(f"❌ 任务更新失败: {str(e)}")
            raise
    
    async def get_stage_tasks(self, stage_id: str) -> List[Task]:
        """获取阶段任务列表"""
        try:
            async with self.async_session() as session:
                result = await session.execute(
                    select(Task)
                    .where(Task.stage_id == UUID(stage_id))
                    .order_by(Task.position_index, Task.created_at)
                )
                tasks = result.scalars().all()
                return list(tasks)
                
        except Exception as e:
            logger.error(f"❌ 获取阶段任务失败: {stage_id}, 错误: {str(e)}")
            return []
    
    # ==================== 事件管理 ====================
    
    async def save_event(self, event: Event) -> None:
        """保存事件"""
        try:
            async with self.async_session() as session:
                session.add(event)
                await session.commit()
                await session.refresh(event)
            
            # 缓存到Redis
            await self._cache_event(event)
            
            logger.info(f"💾 事件保存成功: {event.id}")
            
        except Exception as e:
            logger.error(f"❌ 事件保存失败: {str(e)}")
            raise
    
    async def get_event(self, event_id: str) -> Optional[Event]:
        """获取事件"""
        try:
            # 先从缓存获取
            cached = await self._get_cached_event(event_id)
            if cached:
                return cached
            
            # 从数据库获取
            async with self.async_session() as session:
                result = await session.execute(
                    select(Event).where(Event.id == UUID(event_id))
                )
                event = result.scalar_one_or_none()
                
                if event:
                    await self._cache_event(event)
                
                return event
                
        except Exception as e:
            logger.error(f"❌ 获取事件失败: {event_id}, 错误: {str(e)}")
            return None
    
    async def update_event(self, event: Event) -> None:
        """更新事件"""
        try:
            async with self.async_session() as session:
                await session.merge(event)
                await session.commit()
            
            # 更新缓存
            await self._cache_event(event)
            
            logger.info(f"🔄 事件更新成功: {event.id}")
            
        except Exception as e:
            logger.error(f"❌ 事件更新失败: {str(e)}")
            raise
    
    async def get_failed_events_for_retry(self, current_time: datetime) -> List[Event]:
        """获取需要重试的失败事件"""
        try:
            async with self.async_session() as session:
                result = await session.execute(
                    select(Event).where(
                        Event.status == "failed",
                        Event.next_retry_at <= current_time,
                        Event.retry_count < Event.max_retries
                    )
                )
                events = result.scalars().all()
                return list(events)
                
        except Exception as e:
            logger.error(f"❌ 获取重试事件失败: {str(e)}")
            return []
    
    # ==================== 事件处理器管理 ====================
    
    async def save_event_handler(self, handler: EventHandler) -> None:
        """保存事件处理器"""
        try:
            async with self.async_session() as session:
                session.add(handler)
                await session.commit()
                await session.refresh(handler)
            
            logger.info(f"💾 事件处理器保存成功: {handler.id}")
            
        except Exception as e:
            logger.error(f"❌ 事件处理器保存失败: {str(e)}")
            raise
    
    async def update_event_handler(self, handler: EventHandler) -> None:
        """更新事件处理器"""
        try:
            async with self.async_session() as session:
                await session.merge(handler)
                await session.commit()
            
            logger.info(f"🔄 事件处理器更新成功: {handler.id}")
            
        except Exception as e:
            logger.error(f"❌ 事件处理器更新失败: {str(e)}")
            raise
    
    # ==================== 事件订阅管理 ====================
    
    async def save_event_subscription(self, subscription: EventSubscription) -> None:
        """保存事件订阅"""
        try:
            async with self.async_session() as session:
                session.add(subscription)
                await session.commit()
                await session.refresh(subscription)
            
            logger.info(f"💾 事件订阅保存成功: {subscription.id}")
            
        except Exception as e:
            logger.error(f"❌ 事件订阅保存失败: {str(e)}")
            raise
    
    # ==================== 事件规则管理 ====================
    
    async def save_event_rule(self, rule: EventRule) -> None:
        """保存事件规则"""
        try:
            async with self.async_session() as session:
                session.add(rule)
                await session.commit()
                await session.refresh(rule)
            
            logger.info(f"💾 事件规则保存成功: {rule.id}")
            
        except Exception as e:
            logger.error(f"❌ 事件规则保存失败: {str(e)}")
            raise
    
    async def get_event_rule(self, rule_id: str) -> Optional[EventRule]:
        """获取事件规则"""
        try:
            async with self.async_session() as session:
                result = await session.execute(
                    select(EventRule).where(EventRule.id == UUID(rule_id))
                )
                rule = result.scalar_one_or_none()
                return rule
                
        except Exception as e:
            logger.error(f"❌ 获取事件规则失败: {rule_id}, 错误: {str(e)}")
            return None
    
    async def update_event_rule(self, rule: EventRule) -> None:
        """更新事件规则"""
        try:
            async with self.async_session() as session:
                await session.merge(rule)
                await session.commit()
            
            logger.info(f"🔄 事件规则更新成功: {rule.id}")
            
        except Exception as e:
            logger.error(f"❌ 事件规则更新失败: {str(e)}")
            raise
    
    async def get_active_event_rules(self) -> List[EventRule]:
        """获取激活的事件规则"""
        try:
            async with self.async_session() as session:
                result = await session.execute(
                    select(EventRule)
                    .where(EventRule.is_active == True)
                    .order_by(EventRule.priority.desc())
                )
                rules = result.scalars().all()
                return list(rules)
                
        except Exception as e:
            logger.error(f"❌ 获取激活事件规则失败: {str(e)}")
            return []
    
    # ==================== 工作流执行管理 ====================
    
    async def save_workflow_execution(self, execution: WorkflowExecution) -> None:
        """保存工作流执行记录"""
        try:
            async with self.async_session() as session:
                session.add(execution)
                await session.commit()
                await session.refresh(execution)
            
            logger.info(f"💾 工作流执行记录保存成功: {execution.id}")
            
        except Exception as e:
            logger.error(f"❌ 工作流执行记录保存失败: {str(e)}")
            raise
    
    async def get_workflow_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """获取工作流执行记录"""
        try:
            async with self.async_session() as session:
                result = await session.execute(
                    select(WorkflowExecution).where(WorkflowExecution.id == UUID(execution_id))
                )
                execution = result.scalar_one_or_none()
                return execution
                
        except Exception as e:
            logger.error(f"❌ 获取工作流执行记录失败: {execution_id}, 错误: {str(e)}")
            return None
    
    async def update_workflow_execution(self, execution: WorkflowExecution) -> None:
        """更新工作流执行记录"""
        try:
            async with self.async_session() as session:
                await session.merge(execution)
                await session.commit()
            
            logger.info(f"🔄 工作流执行记录更新成功: {execution.id}")
            
        except Exception as e:
            logger.error(f"❌ 工作流执行记录更新失败: {str(e)}")
            raise
    
    # ==================== 看板管理 ====================
    
    async def save_board(self, board: Board) -> None:
        """保存看板"""
        try:
            async with self.async_session() as session:
                session.add(board)
                await session.commit()
                await session.refresh(board)
            
            logger.info(f"💾 看板保存成功: {board.id}")
            
        except Exception as e:
            logger.error(f"❌ 看板保存失败: {str(e)}")
            raise
    
    async def save_board_column(self, column: BoardColumn) -> None:
        """保存看板列"""
        try:
            async with self.async_session() as session:
                session.add(column)
                await session.commit()
                await session.refresh(column)
            
            logger.info(f"💾 看板列保存成功: {column.id}")
            
        except Exception as e:
            logger.error(f"❌ 看板列保存失败: {str(e)}")
            raise
    
    # ==================== 缓存管理 ====================
    
    async def _cache_workflow(self, workflow: Workflow) -> None:
        """缓存工作流"""
        try:
            key = f"workflow:{workflow.id}"
            data = workflow.to_dict()
            await self.redis.setex(key, self._cache_ttl, json.dumps(data, default=str))
            
        except Exception as e:
            logger.error(f"❌ 缓存工作流失败: {str(e)}")
    
    async def _get_cached_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """从缓存获取工作流"""
        try:
            key = f"workflow:{workflow_id}"
            data = await self.redis.get(key)
            if data:
                workflow_dict = json.loads(data)
                # 这里需要将字典转换回Workflow对象
                # 简化实现，实际应该有完整的反序列化逻辑
                return None  # 暂时返回None，让其从数据库获取
            return None
            
        except Exception as e:
            logger.error(f"❌ 从缓存获取工作流失败: {str(e)}")
            return None
    
    async def _remove_cached_workflow(self, workflow_id: str) -> None:
        """从缓存移除工作流"""
        try:
            key = f"workflow:{workflow_id}"
            await self.redis.delete(key)
            
        except Exception as e:
            logger.error(f"❌ 从缓存移除工作流失败: {str(e)}")
    
    async def _cache_task(self, task: Task) -> None:
        """缓存任务"""
        try:
            key = f"task:{task.id}"
            data = task.to_dict()
            await self.redis.setex(key, self._cache_ttl, json.dumps(data, default=str))
            
        except Exception as e:
            logger.error(f"❌ 缓存任务失败: {str(e)}")
    
    async def _get_cached_task(self, task_id: str) -> Optional[Task]:
        """从缓存获取任务"""
        try:
            key = f"task:{task_id}"
            data = await self.redis.get(key)
            if data:
                # 简化实现，实际应该有完整的反序列化逻辑
                return None
            return None
            
        except Exception as e:
            logger.error(f"❌ 从缓存获取任务失败: {str(e)}")
            return None
    
    async def _cache_event(self, event: Event) -> None:
        """缓存事件"""
        try:
            key = f"event:{event.id}"
            data = event.to_dict()
            await self.redis.setex(key, self._cache_ttl, json.dumps(data, default=str))
            
        except Exception as e:
            logger.error(f"❌ 缓存事件失败: {str(e)}")
    
    async def _get_cached_event(self, event_id: str) -> Optional[Event]:
        """从缓存获取事件"""
        try:
            key = f"event:{event_id}"
            data = await self.redis.get(key)
            if data:
                # 简化实现，实际应该有完整的反序列化逻辑
                return None
            return None
            
        except Exception as e:
            logger.error(f"❌ 从缓存获取事件失败: {str(e)}")
            return None
    
    # ==================== 私有方法 ====================
    
    async def _init_redis(self):
        """初始化Redis连接"""
        try:
            import os
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            self.redis = redis.from_url(redis_url, decode_responses=True)
            
            # 测试连接
            await self.redis.ping()
            logger.info("✅ Redis连接成功")
            
        except Exception as e:
            logger.error(f"❌ Redis连接失败: {str(e)}")
            raise
    
    async def _init_database(self):
        """初始化数据库连接"""
        try:
            import os
            database_url = os.getenv(
                "DATABASE_URL", 
                "postgresql+asyncpg://user:password@localhost/kaiban_db"
            )
            
            self.db_engine = create_async_engine(
                database_url,
                echo=False,  # 生产环境设为False
                pool_size=10,
                max_overflow=20
            )
            
            self.async_session = sessionmaker(
                bind=self.db_engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            logger.info("✅ 数据库连接成功")
            
        except Exception as e:
            logger.error(f"❌ 数据库连接失败: {str(e)}")
            raise 