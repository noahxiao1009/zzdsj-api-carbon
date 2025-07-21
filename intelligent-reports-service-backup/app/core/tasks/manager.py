"""
任务管理器
"""
import time
import uuid
from typing import Dict, Optional, List, Any
from threading import Lock
from app.core.tasks.plan import Plan
from app.models.task import TaskModel
from app.utils.logging import get_logger


logger = get_logger(__name__)


class TaskManager:
    """任务管理器 - 管理所有运行中的计划"""
    
    # 类变量存储计划映射
    _plans: Dict[str, Plan] = {}
    _tasks: Dict[str, TaskModel] = {}
    _lock = Lock()
    
    @classmethod
    def create_plan(cls, title: str = "", steps: List[str] = None, 
                   dependencies: Dict[int, List[int]] = None, 
                   work_space_path: str = "") -> tuple[str, Plan]:
        """创建新计划"""
        with cls._lock:
            plan_id = f"plan_{int(time.time())}_{uuid.uuid4().hex[:8]}"
            plan = Plan(title, steps, dependencies, work_space_path)
            plan.plan_id = plan_id
            cls._plans[plan_id] = plan
            logger.info(f"Created plan: {plan_id} - {title}")
            return plan_id, plan
    
    @classmethod
    def set_plan(cls, plan_id: str, plan: Plan):
        """设置计划"""
        with cls._lock:
            plan.plan_id = plan_id
            cls._plans[plan_id] = plan
            logger.info(f"Set plan: {plan_id} - {plan.title}")
    
    @classmethod
    def get_plan(cls, plan_id: str) -> Optional[Plan]:
        """获取计划"""
        return cls._plans.get(plan_id)
    
    @classmethod
    def update_plan(cls, plan_id: str, title: str = None, steps: List[str] = None,
                   dependencies: Dict[int, List[int]] = None) -> bool:
        """更新计划"""
        plan = cls.get_plan(plan_id)
        if plan:
            with cls._lock:
                plan.update(title, steps, dependencies)
                logger.info(f"Updated plan: {plan_id}")
                return True
        return False
    
    @classmethod
    def delete_plan(cls, plan_id: str) -> bool:
        """删除计划"""
        with cls._lock:
            if plan_id in cls._plans:
                del cls._plans[plan_id]
                logger.info(f"Deleted plan: {plan_id}")
                return True
        return False
    
    @classmethod
    def list_plans(cls) -> Dict[str, Dict[str, Any]]:
        """列出所有计划"""
        result = {}
        for plan_id, plan in cls._plans.items():
            result[plan_id] = {
                "title": plan.title,
                "total_steps": len(plan.steps),
                "progress": plan.get_progress(),
                "completion_percentage": plan.get_completion_percentage(),
                "is_completed": plan.is_completed(),
                "is_in_progress": plan.is_in_progress(),
                "has_blocked_steps": plan.has_blocked_steps(),
            }
        return result
    
    @classmethod
    def get_plan_stats(cls) -> Dict[str, Any]:
        """获取计划统计信息"""
        total_plans = len(cls._plans)
        completed_plans = sum(1 for plan in cls._plans.values() if plan.is_completed())
        in_progress_plans = sum(1 for plan in cls._plans.values() if plan.is_in_progress())
        blocked_plans = sum(1 for plan in cls._plans.values() if plan.has_blocked_steps())
        
        return {
            "total_plans": total_plans,
            "completed_plans": completed_plans,
            "in_progress_plans": in_progress_plans,
            "blocked_plans": blocked_plans,
            "not_started_plans": total_plans - in_progress_plans - completed_plans,
            "completion_rate": completed_plans / total_plans if total_plans > 0 else 0.0,
        }
    
    @classmethod
    def clear_all_plans(cls):
        """清除所有计划"""
        with cls._lock:
            cls._plans.clear()
            logger.info("Cleared all plans")
    
    @classmethod
    def clear_completed_plans(cls):
        """清除已完成的计划"""
        with cls._lock:
            completed_plans = [plan_id for plan_id, plan in cls._plans.items() if plan.is_completed()]
            for plan_id in completed_plans:
                del cls._plans[plan_id]
            logger.info(f"Cleared {len(completed_plans)} completed plans")
    
    @classmethod
    def register_task(cls, task_id: str, task: TaskModel):
        """注册任务"""
        with cls._lock:
            cls._tasks[task_id] = task
            logger.info(f"Registered task: {task_id} - {task.title}")
    
    @classmethod
    def unregister_task(cls, task_id: str):
        """注销任务"""
        with cls._lock:
            if task_id in cls._tasks:
                del cls._tasks[task_id]
                logger.info(f"Unregistered task: {task_id}")
    
    @classmethod
    def get_task(cls, task_id: str) -> Optional[TaskModel]:
        """获取任务"""
        return cls._tasks.get(task_id)
    
    @classmethod
    def list_tasks(cls) -> Dict[str, Dict[str, Any]]:
        """列出所有任务"""
        result = {}
        for task_id, task in cls._tasks.items():
            result[task_id] = {
                "title": task.title,
                "status": task.status,
                "type": task.type,
                "priority": task.priority,
                "progress": task.get_progress(),
                "completion_percentage": task.get_progress_percentage(),
                "user_id": task.user_id,
            }
        return result
    
    @classmethod
    def get_task_stats(cls) -> Dict[str, Any]:
        """获取任务统计信息"""
        total_tasks = len(cls._tasks)
        if total_tasks == 0:
            return {
                "total_tasks": 0,
                "by_status": {},
                "by_type": {},
                "by_priority": {},
            }
        
        # 按状态统计
        by_status = {}
        for task in cls._tasks.values():
            status = task.status
            by_status[status] = by_status.get(status, 0) + 1
        
        # 按类型统计
        by_type = {}
        for task in cls._tasks.values():
            task_type = task.type
            by_type[task_type] = by_type.get(task_type, 0) + 1
        
        # 按优先级统计
        by_priority = {}
        for task in cls._tasks.values():
            priority = task.priority
            by_priority[priority] = by_priority.get(priority, 0) + 1
        
        return {
            "total_tasks": total_tasks,
            "by_status": by_status,
            "by_type": by_type,
            "by_priority": by_priority,
        }
    
    @classmethod
    def sync_plan_from_task(cls, task: TaskModel) -> Optional[Plan]:
        """从任务同步创建计划"""
        if not task.steps:
            return None
        
        # 创建计划
        plan_id = f"task_{task.id}"
        plan = Plan(
            title=task.title,
            steps=task.steps,
            dependencies=task.dependencies or {},
            work_space_path=task.workspace_path or ""
        )
        
        # 同步状态
        if task.step_statuses:
            plan.step_statuses = task.step_statuses
        if task.step_notes:
            plan.step_notes = task.step_notes
        if task.step_details:
            plan.step_details = task.step_details
        if task.step_files:
            plan.step_files = task.step_files
        if task.result:
            plan.result = task.result
        
        cls.set_plan(plan_id, plan)
        return plan
    
    @classmethod
    def sync_task_from_plan(cls, plan: Plan, task: TaskModel):
        """从计划同步更新任务"""
        task.title = plan.title
        task.steps = plan.steps
        task.step_statuses = plan.step_statuses
        task.step_notes = plan.step_notes
        task.step_details = plan.step_details
        task.step_files = plan.step_files
        task.dependencies = plan.dependencies
        task.result = plan.result
        task.workspace_path = plan.work_space_path
    
    @classmethod
    def create_plan_from_task(cls, task: TaskModel) -> Optional[Plan]:
        """从任务创建计划"""
        if not task:
            return None
        
        plan = cls.sync_plan_from_task(task)
        if plan:
            # 注册任务
            cls.register_task(str(task.id), task)
        
        return plan
    
    @classmethod
    def get_ready_tasks(cls) -> List[str]:
        """获取所有有就绪步骤的任务ID"""
        ready_task_ids = []
        for task_id, task in cls._tasks.items():
            ready_steps = task.get_ready_steps()
            if ready_steps:
                ready_task_ids.append(task_id)
        return ready_task_ids
    
    @classmethod
    def get_system_status(cls) -> Dict[str, Any]:
        """获取系统状态"""
        plan_stats = cls.get_plan_stats()
        task_stats = cls.get_task_stats()
        
        return {
            "timestamp": time.time(),
            "plan_stats": plan_stats,
            "task_stats": task_stats,
            "active_plans": len(cls._plans),
            "active_tasks": len(cls._tasks),
            "ready_tasks": len(cls.get_ready_tasks()),
        }


class PlanEventManager:
    """计划事件管理器"""
    
    def __init__(self):
        self._subscribers: Dict[str, List[callable]] = {}
        self._lock = Lock()
    
    def subscribe(self, event_type: str, callback: callable):
        """订阅事件"""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)
    
    def unsubscribe(self, event_type: str, callback: callable):
        """取消订阅"""
        with self._lock:
            if event_type in self._subscribers:
                try:
                    self._subscribers[event_type].remove(callback)
                except ValueError:
                    pass
    
    def publish(self, event_type: str, data: Any):
        """发布事件"""
        subscribers = self._subscribers.get(event_type, [])
        for callback in subscribers:
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Event callback error: {str(e)}", exc_info=True)
    
    def clear_subscribers(self, event_type: str = None):
        """清除订阅者"""
        with self._lock:
            if event_type:
                self._subscribers.pop(event_type, None)
            else:
                self._subscribers.clear()


# 全局事件管理器实例
plan_report_event_manager = PlanEventManager()