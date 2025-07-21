"""
事件分发器 - 事件驱动系统的核心分发器
负责事件的订阅、分发、处理和路由
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Set
from uuid import UUID
import uuid

from ..models.event import Event, EventType, EventStatus, EventHandler, EventSubscription, EventRule


logger = logging.getLogger(__name__)


class EventDispatcher:
    """事件分发器 - 负责事件的分发和处理"""
    
    def __init__(self, state_manager):
        self.state_manager = state_manager
        self._subscribers: Dict[str, List[Callable]] = {}  # 事件类型 -> 处理函数列表
        self._event_queue = asyncio.Queue()
        self._is_running = False
        self._processing_tasks: Set[asyncio.Task] = set()
        self._event_rules: List[Dict] = []
        self._retry_queue = asyncio.Queue()
        
    async def initialize(self):
        """初始化事件分发器"""
        logger.info("🚀 初始化事件分发器...")
        
        # 注册默认事件处理器
        await self._register_default_handlers()
        
        # 加载事件规则
        await self._load_event_rules()
        
        # 启动事件处理器
        self._is_running = True
        asyncio.create_task(self._process_event_queue())
        asyncio.create_task(self._process_retry_queue())
        
        logger.info("✅ 事件分发器初始化完成")
    
    async def cleanup(self):
        """清理资源"""
        logger.info("🔄 清理事件分发器资源...")
        self._is_running = False
        
        # 等待所有处理任务完成
        if self._processing_tasks:
            await asyncio.gather(*self._processing_tasks, return_exceptions=True)
        
        logger.info("✅ 事件分发器资源清理完成")
    
    def is_healthy(self) -> bool:
        """检查分发器健康状态"""
        return self._is_running and not self._event_queue.full()
    
    async def dispatch_event(self, event_data: Dict[str, Any]) -> str:
        """分发事件"""
        try:
            # 创建事件实例
            event = Event(
                event_type=event_data["event_type"],
                event_name=event_data.get("event_name"),
                description=event_data.get("description"),
                workflow_id=UUID(event_data["workflow_id"]) if event_data.get("workflow_id") else None,
                task_id=UUID(event_data["task_id"]) if event_data.get("task_id") else None,
                board_id=UUID(event_data["board_id"]) if event_data.get("board_id") else None,
                event_data=event_data.get("event_data", {}),
                context=event_data.get("context", {}),
                metadata=event_data.get("metadata", {}),
                priority=event_data.get("priority", "medium"),
                source=event_data.get("source", "kaiban-service"),
                correlation_id=event_data.get("correlation_id", str(uuid.uuid4()))
            )
            
            # 保存事件
            event_id = str(event.id)
            await self.state_manager.save_event(event)
            
            # 加入处理队列
            await self._event_queue.put({
                "event_id": event_id,
                "event_type": event.event_type,
                "priority": event.priority
            })
            
            logger.info(f"📤 事件已分发: {event.event_type}, ID: {event_id}")
            return event_id
            
        except Exception as e:
            logger.error(f"❌ 事件分发失败: {str(e)}")
            raise
    
    async def subscribe(self, event_type: str, handler: Callable, config: Dict[str, Any] = None):
        """订阅事件"""
        try:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            
            self._subscribers[event_type].append(handler)
            
            # 创建订阅记录
            subscription = EventSubscription(
                subscriber_name=handler.__name__ if hasattr(handler, '__name__') else str(handler),
                subscriber_type="function",
                subscription_config=config or {},
                event_type_filter=[event_type]
            )
            
            await self.state_manager.save_event_subscription(subscription)
            
            logger.info(f"📥 事件订阅成功: {event_type} -> {subscription.subscriber_name}")
            
        except Exception as e:
            logger.error(f"❌ 事件订阅失败: {str(e)}")
            raise
    
    async def unsubscribe(self, event_type: str, handler: Callable):
        """取消订阅事件"""
        try:
            if event_type in self._subscribers:
                if handler in self._subscribers[event_type]:
                    self._subscribers[event_type].remove(handler)
                    logger.info(f"📤 取消事件订阅: {event_type}")
                    return True
            
            logger.warning(f"⚠️ 未找到事件订阅: {event_type}")
            return False
            
        except Exception as e:
            logger.error(f"❌ 取消事件订阅失败: {str(e)}")
            return False
    
    async def create_event_rule(self, rule_data: Dict[str, Any]) -> str:
        """创建事件规则"""
        try:
            from ..models.event import EventRule
            
            rule = EventRule(
                name=rule_data["name"],
                description=rule_data.get("description", ""),
                rule_type=rule_data.get("rule_type", "trigger"),
                trigger_conditions=rule_data.get("trigger_conditions", {}),
                event_pattern=rule_data.get("event_pattern", {}),
                actions=rule_data.get("actions", []),
                action_config=rule_data.get("action_config", {}),
                priority=rule_data.get("priority", 0)
            )
            
            rule_id = str(rule.id)
            await self.state_manager.save_event_rule(rule)
            
            # 添加到内存规则列表
            self._event_rules.append(rule.to_dict())
            
            logger.info(f"📋 事件规则创建成功: {rule.name}, ID: {rule_id}")
            return rule_id
            
        except Exception as e:
            logger.error(f"❌ 事件规则创建失败: {str(e)}")
            raise
    
    async def _process_event_queue(self):
        """处理事件队列"""
        logger.info("🔄 启动事件队列处理")
        
        while self._is_running:
            try:
                # 从队列获取事件
                item = await asyncio.wait_for(
                    self._event_queue.get(), 
                    timeout=1.0
                )
                
                # 创建处理任务
                task = asyncio.create_task(
                    self._handle_event(item["event_id"])
                )
                self._processing_tasks.add(task)
                
                # 任务完成后从集合中移除
                task.add_done_callback(self._processing_tasks.discard)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"❌ 事件队列处理错误: {str(e)}")
    
    async def _process_retry_queue(self):
        """处理重试队列"""
        logger.info("🔄 启动重试队列处理")
        
        while self._is_running:
            try:
                # 检查需要重试的事件
                await self._check_retry_events()
                await asyncio.sleep(10)  # 每10秒检查一次
                
            except Exception as e:
                logger.error(f"❌ 重试队列处理错误: {str(e)}")
    
    async def _handle_event(self, event_id: str):
        """处理单个事件"""
        try:
            # 获取事件详情
            event = await self.state_manager.get_event(event_id)
            if not event:
                logger.warning(f"⚠️ 事件不存在: {event_id}")
                return
            
            # 更新事件状态为处理中
            event.status = EventStatus.PROCESSING
            event.processed_at = datetime.utcnow()
            await self.state_manager.update_event(event)
            
            logger.info(f"⚡ 处理事件: {event.event_type}, ID: {event_id}")
            
            # 应用事件规则
            await self._apply_event_rules(event)
            
            # 获取订阅者并执行
            handlers = self._subscribers.get(event.event_type, [])
            if not handlers:
                logger.info(f"ℹ️ 无订阅者的事件: {event.event_type}")
            
            # 并行执行所有处理器
            handler_tasks = []
            for i, handler in enumerate(handlers):
                handler_record = EventHandler(
                    event_id=event.id,
                    handler_name=handler.__name__ if hasattr(handler, '__name__') else f"handler_{i}",
                    handler_type="function",
                    execution_order=i,
                    started_at=datetime.utcnow()
                )
                await self.state_manager.save_event_handler(handler_record)
                
                # 创建处理任务
                task = asyncio.create_task(
                    self._execute_handler(handler, event, handler_record)
                )
                handler_tasks.append(task)
            
            # 等待所有处理器完成
            if handler_tasks:
                results = await asyncio.gather(*handler_tasks, return_exceptions=True)
                
                # 检查处理结果
                success_count = sum(1 for r in results if not isinstance(r, Exception))
                failure_count = len(results) - success_count
                
                if failure_count > 0:
                    logger.warning(f"⚠️ 事件处理部分失败: {event_id}, 成功: {success_count}, 失败: {failure_count}")
            
            # 更新事件状态为已处理
            event.status = EventStatus.PROCESSED
            processing_duration = (datetime.utcnow() - event.processed_at).total_seconds()
            event.processing_duration = processing_duration
            await self.state_manager.update_event(event)
            
            logger.info(f"✅ 事件处理完成: {event_id}, 耗时: {processing_duration:.2f}s")
            
        except Exception as e:
            logger.error(f"❌ 事件处理失败: {event_id}, 错误: {str(e)}")
            
            # 更新事件状态为失败
            try:
                event = await self.state_manager.get_event(event_id)
                if event:
                    event.status = EventStatus.FAILED
                    event.error_info = {
                        "error": str(e),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    event.retry_count += 1
                    
                    # 设置下次重试时间
                    if event.should_retry():
                        retry_delay = min(300, 30 * (2 ** event.retry_count))  # 指数退避，最大5分钟
                        event.next_retry_at = datetime.utcnow() + timedelta(seconds=retry_delay)
                    
                    await self.state_manager.update_event(event)
            except Exception as update_error:
                logger.error(f"❌ 更新事件状态失败: {str(update_error)}")
    
    async def _execute_handler(self, handler: Callable, event: Event, handler_record: EventHandler):
        """执行事件处理器"""
        try:
            # 执行处理器
            if asyncio.iscoroutinefunction(handler):
                result = await handler(event)
            else:
                result = handler(event)
            
            # 更新处理器记录
            handler_record.status = "completed"
            handler_record.completed_at = datetime.utcnow()
            handler_record.duration = (handler_record.completed_at - handler_record.started_at).total_seconds()
            handler_record.result = {"success": True, "data": result} if result else {"success": True}
            
            await self.state_manager.update_event_handler(handler_record)
            
            return result
            
        except Exception as e:
            # 更新处理器记录为失败
            handler_record.status = "failed"
            handler_record.completed_at = datetime.utcnow()
            handler_record.duration = (handler_record.completed_at - handler_record.started_at).total_seconds()
            handler_record.error_info = {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await self.state_manager.update_event_handler(handler_record)
            
            logger.error(f"❌ 处理器执行失败: {handler_record.handler_name}, 错误: {str(e)}")
            raise
    
    async def _apply_event_rules(self, event: Event):
        """应用事件规则"""
        try:
            for rule_dict in self._event_rules:
                if not rule_dict.get("is_active", True):
                    continue
                
                # 检查规则条件
                if await self._check_rule_conditions(event, rule_dict):
                    await self._execute_rule_actions(event, rule_dict)
                    
                    # 更新规则执行统计
                    await self._update_rule_stats(rule_dict["id"], True)
            
        except Exception as e:
            logger.error(f"❌ 应用事件规则失败: {str(e)}")
    
    async def _check_rule_conditions(self, event: Event, rule: Dict) -> bool:
        """检查规则条件"""
        try:
            trigger_conditions = rule.get("trigger_conditions", {})
            event_pattern = rule.get("event_pattern", {})
            
            # 检查事件类型匹配
            if event_pattern.get("event_types"):
                if event.event_type not in event_pattern["event_types"]:
                    return False
            
            # 检查数据条件
            if trigger_conditions.get("data_conditions"):
                for condition in trigger_conditions["data_conditions"]:
                    if not self._evaluate_condition(event.event_data, condition):
                        return False
            
            # 检查上下文条件
            if trigger_conditions.get("context_conditions"):
                for condition in trigger_conditions["context_conditions"]:
                    if not self._evaluate_condition(event.context, condition):
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 检查规则条件失败: {str(e)}")
            return False
    
    def _evaluate_condition(self, data: Dict, condition: Dict) -> bool:
        """评估单个条件"""
        try:
            field = condition.get("field")
            operator = condition.get("operator")
            value = condition.get("value")
            
            if not field or not operator:
                return True
            
            # 获取字段值
            field_value = data.get(field)
            
            # 根据操作符评估
            if operator == "equals":
                return field_value == value
            elif operator == "not_equals":
                return field_value != value
            elif operator == "contains":
                return value in str(field_value) if field_value else False
            elif operator == "greater_than":
                return float(field_value) > float(value) if field_value and value else False
            elif operator == "less_than":
                return float(field_value) < float(value) if field_value and value else False
            elif operator == "exists":
                return field_value is not None
            elif operator == "not_exists":
                return field_value is None
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 条件评估失败: {str(e)}")
            return False
    
    async def _execute_rule_actions(self, event: Event, rule: Dict):
        """执行规则动作"""
        try:
            actions = rule.get("actions", [])
            action_config = rule.get("action_config", {})
            
            for action in actions:
                if action == "create_task":
                    await self._action_create_task(event, action_config)
                elif action == "send_notification":
                    await self._action_send_notification(event, action_config)
                elif action == "trigger_workflow":
                    await self._action_trigger_workflow(event, action_config)
                elif action == "update_status":
                    await self._action_update_status(event, action_config)
                elif action == "send_webhook":
                    await self._action_send_webhook(event, action_config)
            
        except Exception as e:
            logger.error(f"❌ 执行规则动作失败: {str(e)}")
    
    async def _check_retry_events(self):
        """检查需要重试的事件"""
        try:
            # 获取需要重试的事件
            current_time = datetime.utcnow()
            failed_events = await self.state_manager.get_failed_events_for_retry(current_time)
            
            for event in failed_events:
                if event.should_retry():
                    logger.info(f"🔄 重试事件: {event.id}")
                    
                    # 重置事件状态
                    event.status = EventStatus.PENDING
                    event.next_retry_at = None
                    await self.state_manager.update_event(event)
                    
                    # 重新加入处理队列
                    await self._event_queue.put({
                        "event_id": str(event.id),
                        "event_type": event.event_type,
                        "priority": event.priority
                    })
            
        except Exception as e:
            logger.error(f"❌ 检查重试事件失败: {str(e)}")
    
    async def _load_event_rules(self):
        """加载事件规则"""
        try:
            rules = await self.state_manager.get_active_event_rules()
            self._event_rules = [rule.to_dict() for rule in rules]
            logger.info(f"📋 加载事件规则: {len(self._event_rules)} 条")
            
        except Exception as e:
            logger.error(f"❌ 加载事件规则失败: {str(e)}")
    
    async def _register_default_handlers(self):
        """注册默认事件处理器"""
        # 工作流事件处理器
        await self.subscribe(EventType.WORKFLOW_CREATED, self._handle_workflow_created)
        await self.subscribe(EventType.WORKFLOW_STARTED, self._handle_workflow_started)
        await self.subscribe(EventType.WORKFLOW_COMPLETED, self._handle_workflow_completed)
        await self.subscribe(EventType.WORKFLOW_FAILED, self._handle_workflow_failed)
        
        # 任务事件处理器
        await self.subscribe(EventType.TASK_CREATED, self._handle_task_created)
        await self.subscribe(EventType.TASK_STARTED, self._handle_task_started)
        await self.subscribe(EventType.TASK_COMPLETED, self._handle_task_completed)
        await self.subscribe(EventType.TASK_FAILED, self._handle_task_failed)
        await self.subscribe(EventType.TASK_MOVED, self._handle_task_moved)
        
        logger.info("📝 默认事件处理器注册完成")
    
    # 默认事件处理器实现
    async def _handle_workflow_created(self, event: Event):
        """处理工作流创建事件"""
        logger.info(f"🆕 工作流创建: {event.workflow_id}")
        # 可以在这里添加工作流创建后的自动化操作
    
    async def _handle_workflow_started(self, event: Event):
        """处理工作流启动事件"""
        logger.info(f"▶️ 工作流启动: {event.workflow_id}")
        # 可以在这里添加工作流启动后的监控逻辑
    
    async def _handle_workflow_completed(self, event: Event):
        """处理工作流完成事件"""
        logger.info(f"✅ 工作流完成: {event.workflow_id}")
        # 可以在这里添加工作流完成后的清理或通知逻辑
    
    async def _handle_workflow_failed(self, event: Event):
        """处理工作流失败事件"""
        logger.error(f"💥 工作流失败: {event.workflow_id}")
        # 可以在这里添加工作流失败后的恢复或报警逻辑
    
    async def _handle_task_created(self, event: Event):
        """处理任务创建事件"""
        logger.info(f"📋 任务创建: {event.task_id}")
    
    async def _handle_task_started(self, event: Event):
        """处理任务启动事件"""
        logger.info(f"🚀 任务启动: {event.task_id}")
    
    async def _handle_task_completed(self, event: Event):
        """处理任务完成事件"""
        logger.info(f"✅ 任务完成: {event.task_id}")
    
    async def _handle_task_failed(self, event: Event):
        """处理任务失败事件"""
        logger.error(f"💥 任务失败: {event.task_id}")
    
    async def _handle_task_moved(self, event: Event):
        """处理任务移动事件"""
        logger.info(f"🔄 任务移动: {event.task_id}")
    
    # 规则动作实现
    async def _action_create_task(self, event: Event, config: Dict):
        """规则动作：创建任务"""
        # 实现创建任务的逻辑
        pass
    
    async def _action_send_notification(self, event: Event, config: Dict):
        """规则动作：发送通知"""
        # 实现发送通知的逻辑
        pass
    
    async def _action_trigger_workflow(self, event: Event, config: Dict):
        """规则动作：触发工作流"""
        # 实现触发工作流的逻辑
        pass
    
    async def _action_update_status(self, event: Event, config: Dict):
        """规则动作：更新状态"""
        # 实现更新状态的逻辑
        pass
    
    async def _action_send_webhook(self, event: Event, config: Dict):
        """规则动作：发送Webhook"""
        # 实现发送Webhook的逻辑
        pass
    
    async def _update_rule_stats(self, rule_id: str, success: bool):
        """更新规则执行统计"""
        try:
            rule = await self.state_manager.get_event_rule(rule_id)
            if rule:
                rule.execution_count += 1
                if success:
                    rule.success_count += 1
                else:
                    rule.failure_count += 1
                rule.last_executed_at = datetime.utcnow()
                await self.state_manager.update_event_rule(rule)
                
        except Exception as e:
            logger.error(f"❌ 更新规则统计失败: {str(e)}") 