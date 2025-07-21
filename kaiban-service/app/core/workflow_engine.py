"""
工作流引擎 - 事件驱动工作流的核心执行引擎
基于KaibanJS理念实现的工作流编排和执行系统
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from uuid import UUID
import uuid

from ..models.workflow import Workflow, WorkflowStatus, WorkflowExecution, WorkflowStage, WorkflowRole
from ..models.task import Task, TaskStatus, TaskType
from ..models.event import Event, EventType, EventStatus
from ..models.board import Board, BoardColumn


logger = logging.getLogger(__name__)


class WorkflowEngine:
    """工作流引擎 - 负责工作流的执行和管理"""
    
    def __init__(self, state_manager, event_dispatcher):
        self.state_manager = state_manager
        self.event_dispatcher = event_dispatcher
        self._running_workflows: Dict[str, Dict] = {}
        self._task_executors: Dict[str, Callable] = {}
        self._role_handlers: Dict[str, Callable] = {}
        self._is_running = False
        self._execution_queue = asyncio.Queue()
        
    async def initialize(self):
        """初始化工作流引擎"""
        logger.info("🚀 初始化工作流引擎...")
        
        # 注册默认任务执行器
        await self._register_default_executors()
        
        # 注册默认角色处理器
        await self._register_default_role_handlers()
        
        # 启动执行队列处理
        self._is_running = True
        asyncio.create_task(self._process_execution_queue())
        
        logger.info("✅ 工作流引擎初始化完成")
    
    async def cleanup(self):
        """清理资源"""
        logger.info("🔄 清理工作流引擎资源...")
        self._is_running = False
        
        # 停止所有运行中的工作流
        for workflow_id in list(self._running_workflows.keys()):
            await self.stop_workflow(workflow_id)
        
        logger.info("✅ 工作流引擎资源清理完成")
    
    def is_healthy(self) -> bool:
        """检查引擎健康状态"""
        return self._is_running and not self._execution_queue.full()
    
    async def create_workflow(self, workflow_data: Dict[str, Any]) -> str:
        """创建新工作流"""
        try:
            logger.info(f"📝 创建工作流: {workflow_data.get('name', 'Unnamed')}")
            
            # 创建工作流实例
            workflow = Workflow(
                name=workflow_data["name"],
                description=workflow_data.get("description", ""),
                config=workflow_data.get("config", {}),
                metadata=workflow_data.get("metadata", {}),
                trigger_type=workflow_data.get("trigger_type", "manual")
            )
            
            # 保存到状态管理器
            workflow_id = str(workflow.id)
            await self.state_manager.save_workflow(workflow)
            
            # 创建工作流阶段
            stages = workflow_data.get("stages", [])
            for i, stage_data in enumerate(stages):
                stage = WorkflowStage(
                    workflow_id=workflow.id,
                    name=stage_data["name"],
                    description=stage_data.get("description", ""),
                    order_index=i,
                    config=stage_data.get("config", {}),
                    is_parallel=stage_data.get("is_parallel", False),
                    max_tasks=stage_data.get("max_tasks", 10)
                )
                await self.state_manager.save_workflow_stage(stage)
            
            # 创建工作流角色
            roles = workflow_data.get("roles", [])
            for role_data in roles:
                role = WorkflowRole(
                    workflow_id=workflow.id,
                    name=role_data["name"],
                    description=role_data.get("description", ""),
                    capabilities=role_data.get("capabilities", {}),
                    model_config=role_data.get("model_config", {}),
                    tools=role_data.get("tools", [])
                )
                await self.state_manager.save_workflow_role(role)
            
            # 创建默认看板
            await self._create_default_board(workflow.id, stages)
            
            # 发送工作流创建事件
            await self.event_dispatcher.dispatch_event({
                "event_type": EventType.WORKFLOW_CREATED,
                "workflow_id": workflow_id,
                "event_data": {
                    "workflow_name": workflow.name,
                    "stages_count": len(stages),
                    "roles_count": len(roles)
                }
            })
            
            logger.info(f"✅ 工作流创建成功: {workflow_id}")
            return workflow_id
            
        except Exception as e:
            logger.error(f"❌ 工作流创建失败: {str(e)}")
            raise
    
    async def start_workflow(self, workflow_id: str, input_data: Dict[str, Any] = None) -> str:
        """启动工作流执行"""
        try:
            logger.info(f"🎬 启动工作流: {workflow_id}")
            
            # 获取工作流定义
            workflow = await self.state_manager.get_workflow(workflow_id)
            if not workflow:
                raise ValueError(f"工作流不存在: {workflow_id}")
            
            if workflow.status not in [WorkflowStatus.DRAFT, WorkflowStatus.PAUSED]:
                raise ValueError(f"工作流状态不允许启动: {workflow.status}")
            
            # 创建执行记录
            execution = WorkflowExecution(
                workflow_id=workflow.id,
                input_data=input_data or {},
                trigger_type="manual",
                trigger_data={"started_by": "system"}
            )
            execution_id = str(execution.id)
            await self.state_manager.save_workflow_execution(execution)
            
            # 更新工作流状态
            workflow.status = WorkflowStatus.ACTIVE
            workflow.last_executed_at = datetime.utcnow()
            workflow.execution_count += 1
            await self.state_manager.update_workflow(workflow)
            
            # 添加到运行队列
            self._running_workflows[workflow_id] = {
                "execution_id": execution_id,
                "started_at": datetime.utcnow(),
                "current_stage": 0,
                "context": input_data or {}
            }
            
            # 加入执行队列
            await self._execution_queue.put({
                "action": "start_workflow",
                "workflow_id": workflow_id,
                "execution_id": execution_id
            })
            
            # 发送工作流启动事件
            await self.event_dispatcher.dispatch_event({
                "event_type": EventType.WORKFLOW_STARTED,
                "workflow_id": workflow_id,
                "event_data": {
                    "execution_id": execution_id,
                    "input_data": input_data
                }
            })
            
            logger.info(f"✅ 工作流启动成功: {workflow_id}, 执行ID: {execution_id}")
            return execution_id
            
        except Exception as e:
            logger.error(f"❌ 工作流启动失败: {str(e)}")
            raise
    
    async def stop_workflow(self, workflow_id: str) -> bool:
        """停止工作流执行"""
        try:
            logger.info(f"⏹️ 停止工作流: {workflow_id}")
            
            if workflow_id not in self._running_workflows:
                logger.warning(f"⚠️ 工作流未在运行: {workflow_id}")
                return False
            
            # 获取执行信息
            execution_info = self._running_workflows[workflow_id]
            execution_id = execution_info["execution_id"]
            
            # 更新执行记录
            execution = await self.state_manager.get_workflow_execution(execution_id)
            if execution:
                execution.status = "stopped"
                execution.completed_at = datetime.utcnow()
                if execution.started_at:
                    duration = (execution.completed_at - execution.started_at).total_seconds()
                    execution.duration = int(duration)
                await self.state_manager.update_workflow_execution(execution)
            
            # 更新工作流状态
            workflow = await self.state_manager.get_workflow(workflow_id)
            if workflow:
                workflow.status = WorkflowStatus.PAUSED
                await self.state_manager.update_workflow(workflow)
            
            # 从运行队列移除
            del self._running_workflows[workflow_id]
            
            # 发送工作流暂停事件
            await self.event_dispatcher.dispatch_event({
                "event_type": EventType.WORKFLOW_PAUSED,
                "workflow_id": workflow_id,
                "event_data": {
                    "execution_id": execution_id,
                    "reason": "manual_stop"
                }
            })
            
            logger.info(f"✅ 工作流停止成功: {workflow_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 工作流停止失败: {str(e)}")
            return False
    
    async def execute_task(self, task_id: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """执行单个任务"""
        try:
            logger.info(f"⚡ 执行任务: {task_id}")
            
            # 获取任务信息
            task = await self.state_manager.get_task(task_id)
            if not task:
                raise ValueError(f"任务不存在: {task_id}")
            
            if task.status != TaskStatus.TODO:
                raise ValueError(f"任务状态不允许执行: {task.status}")
            
            # 更新任务状态为进行中
            task.status = TaskStatus.IN_PROGRESS
            task.started_at = datetime.utcnow()
            await self.state_manager.update_task(task)
            
            # 发送任务开始事件
            await self.event_dispatcher.dispatch_event({
                "event_type": EventType.TASK_STARTED,
                "workflow_id": str(task.workflow_id),
                "task_id": task_id,
                "event_data": {
                    "task_title": task.title,
                    "task_type": task.task_type
                }
            })
            
            # 根据任务类型选择执行器
            executor = self._task_executors.get(task.task_type)
            if not executor:
                raise ValueError(f"未找到任务类型执行器: {task.task_type}")
            
            try:
                # 执行任务
                result = await executor(task, context or {})
                
                # 更新任务为完成状态
                task.status = TaskStatus.DONE
                task.completed_at = datetime.utcnow()
                task.output_data = result
                task.progress = 100.0
                
                # 计算执行时长
                if task.started_at and task.completed_at:
                    duration = (task.completed_at - task.started_at).total_seconds()
                    task.actual_duration = int(duration / 60)  # 转换为分钟
                
                await self.state_manager.update_task(task)
                
                # 发送任务完成事件
                await self.event_dispatcher.dispatch_event({
                    "event_type": EventType.TASK_COMPLETED,
                    "workflow_id": str(task.workflow_id),
                    "task_id": task_id,
                    "event_data": {
                        "task_title": task.title,
                        "result": result,
                        "duration": task.actual_duration
                    }
                })
                
                logger.info(f"✅ 任务执行成功: {task_id}")
                return result
                
            except Exception as e:
                # 更新任务为失败状态
                task.status = TaskStatus.BLOCKED
                task.error_info = {
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
                task.retry_count += 1
                await self.state_manager.update_task(task)
                
                # 发送任务失败事件
                await self.event_dispatcher.dispatch_event({
                    "event_type": EventType.TASK_FAILED,
                    "workflow_id": str(task.workflow_id),
                    "task_id": task_id,
                    "event_data": {
                        "task_title": task.title,
                        "error": str(e),
                        "retry_count": task.retry_count
                    }
                })
                
                raise
                
        except Exception as e:
            logger.error(f"❌ 任务执行失败: {task_id}, 错误: {str(e)}")
            raise
    
    async def create_task(self, workflow_id: str, task_data: Dict[str, Any]) -> str:
        """创建新任务"""
        try:
            logger.info(f"📋 创建任务: {task_data.get('title', 'Unnamed')}")
            
            # 验证工作流是否存在
            workflow = await self.state_manager.get_workflow(workflow_id)
            if not workflow:
                raise ValueError(f"工作流不存在: {workflow_id}")
            
            # 创建任务实例
            task = Task(
                workflow_id=UUID(workflow_id),
                stage_id=UUID(task_data["stage_id"]),
                title=task_data["title"],
                description=task_data.get("description", ""),
                task_type=task_data.get("task_type", TaskType.AI_PROCESS),
                priority=task_data.get("priority", "medium"),
                input_data=task_data.get("input_data", {}),
                config=task_data.get("config", {}),
                assigned_role_id=UUID(task_data["assigned_role_id"]) if task_data.get("assigned_role_id") else None,
                due_date=task_data.get("due_date"),
                estimated_duration=task_data.get("estimated_duration"),
                tags=task_data.get("tags", []),
                dependencies=task_data.get("dependencies", [])
            )
            
            # 保存任务
            task_id = str(task.id)
            await self.state_manager.save_task(task)
            
            # 发送任务创建事件
            await self.event_dispatcher.dispatch_event({
                "event_type": EventType.TASK_CREATED,
                "workflow_id": workflow_id,
                "task_id": task_id,
                "event_data": {
                    "task_title": task.title,
                    "task_type": task.task_type,
                    "stage_id": str(task.stage_id)
                }
            })
            
            logger.info(f"✅ 任务创建成功: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"❌ 任务创建失败: {str(e)}")
            raise
    
    async def move_task(self, task_id: str, target_column_id: str, position: int = None) -> bool:
        """移动任务到指定列"""
        try:
            logger.info(f"🔄 移动任务: {task_id} -> {target_column_id}")
            
            # 获取任务信息
            task = await self.state_manager.get_task(task_id)
            if not task:
                raise ValueError(f"任务不存在: {task_id}")
            
            old_column_id = str(task.column_id) if task.column_id else None
            
            # 更新任务位置
            task.column_id = UUID(target_column_id)
            if position is not None:
                task.position_index = position
            
            await self.state_manager.update_task(task)
            
            # 发送任务移动事件
            await self.event_dispatcher.dispatch_event({
                "event_type": EventType.TASK_MOVED,
                "workflow_id": str(task.workflow_id),
                "task_id": task_id,
                "event_data": {
                    "task_title": task.title,
                    "from_column": old_column_id,
                    "to_column": target_column_id,
                    "position": position
                }
            })
            
            logger.info(f"✅ 任务移动成功: {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 任务移动失败: {str(e)}")
            return False
    
    async def _process_execution_queue(self):
        """处理执行队列"""
        logger.info("🔄 启动执行队列处理")
        
        while self._is_running:
            try:
                # 从队列获取任务
                item = await asyncio.wait_for(
                    self._execution_queue.get(), 
                    timeout=1.0
                )
                
                action = item.get("action")
                if action == "start_workflow":
                    await self._execute_workflow(
                        item["workflow_id"], 
                        item["execution_id"]
                    )
                elif action == "execute_task":
                    await self.execute_task(
                        item["task_id"], 
                        item.get("context", {})
                    )
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"❌ 执行队列处理错误: {str(e)}")
    
    async def _execute_workflow(self, workflow_id: str, execution_id: str):
        """执行工作流"""
        try:
            logger.info(f"🎯 执行工作流: {workflow_id}")
            
            # 获取工作流定义
            workflow = await self.state_manager.get_workflow(workflow_id)
            stages = await self.state_manager.get_workflow_stages(workflow_id)
            
            execution_info = self._running_workflows.get(workflow_id)
            if not execution_info:
                return
            
            # 按阶段执行
            for stage in sorted(stages, key=lambda x: x.order_index):
                if workflow_id not in self._running_workflows:
                    break  # 工作流已停止
                
                await self._execute_stage(workflow_id, stage, execution_info["context"])
            
            # 标记工作流完成
            await self._complete_workflow(workflow_id, execution_id)
            
        except Exception as e:
            logger.error(f"❌ 工作流执行失败: {workflow_id}, 错误: {str(e)}")
            await self._fail_workflow(workflow_id, execution_id, str(e))
    
    async def _execute_stage(self, workflow_id: str, stage, context: Dict[str, Any]):
        """执行工作流阶段"""
        try:
            logger.info(f"📍 执行阶段: {stage.name}")
            
            # 获取阶段内的任务
            tasks = await self.state_manager.get_stage_tasks(str(stage.id))
            
            if stage.is_parallel:
                # 并行执行任务
                await asyncio.gather(*[
                    self.execute_task(str(task.id), context) 
                    for task in tasks
                ])
            else:
                # 顺序执行任务
                for task in tasks:
                    await self.execute_task(str(task.id), context)
            
        except Exception as e:
            logger.error(f"❌ 阶段执行失败: {stage.name}, 错误: {str(e)}")
            raise
    
    async def _complete_workflow(self, workflow_id: str, execution_id: str):
        """完成工作流"""
        try:
            # 更新执行记录
            execution = await self.state_manager.get_workflow_execution(execution_id)
            if execution:
                execution.status = "completed"
                execution.completed_at = datetime.utcnow()
                if execution.started_at:
                    duration = (execution.completed_at - execution.started_at).total_seconds()
                    execution.duration = int(duration)
                await self.state_manager.update_workflow_execution(execution)
            
            # 更新工作流状态
            workflow = await self.state_manager.get_workflow(workflow_id)
            if workflow:
                workflow.status = WorkflowStatus.COMPLETED
                workflow.success_count += 1
                await self.state_manager.update_workflow(workflow)
            
            # 从运行队列移除
            if workflow_id in self._running_workflows:
                del self._running_workflows[workflow_id]
            
            # 发送工作流完成事件
            await self.event_dispatcher.dispatch_event({
                "event_type": EventType.WORKFLOW_COMPLETED,
                "workflow_id": workflow_id,
                "event_data": {
                    "execution_id": execution_id,
                    "duration": execution.duration if execution else None
                }
            })
            
            logger.info(f"🎉 工作流完成: {workflow_id}")
            
        except Exception as e:
            logger.error(f"❌ 工作流完成处理失败: {str(e)}")
    
    async def _fail_workflow(self, workflow_id: str, execution_id: str, error: str):
        """工作流执行失败"""
        try:
            # 更新执行记录
            execution = await self.state_manager.get_workflow_execution(execution_id)
            if execution:
                execution.status = "failed"
                execution.completed_at = datetime.utcnow()
                execution.error_info = {"error": error}
                if execution.started_at:
                    duration = (execution.completed_at - execution.started_at).total_seconds()
                    execution.duration = int(duration)
                await self.state_manager.update_workflow_execution(execution)
            
            # 更新工作流状态
            workflow = await self.state_manager.get_workflow(workflow_id)
            if workflow:
                workflow.status = WorkflowStatus.FAILED
                workflow.failure_count += 1
                await self.state_manager.update_workflow(workflow)
            
            # 从运行队列移除
            if workflow_id in self._running_workflows:
                del self._running_workflows[workflow_id]
            
            # 发送工作流失败事件
            await self.event_dispatcher.dispatch_event({
                "event_type": EventType.WORKFLOW_FAILED,
                "workflow_id": workflow_id,
                "event_data": {
                    "execution_id": execution_id,
                    "error": error
                }
            })
            
            logger.error(f"💥 工作流失败: {workflow_id}, 原因: {error}")
            
        except Exception as e:
            logger.error(f"❌ 工作流失败处理错误: {str(e)}")
    
    async def _create_default_board(self, workflow_id: UUID, stages: List[Dict]):
        """为工作流创建默认看板"""
        try:
            # 创建看板
            board = Board(
                workflow_id=workflow_id,
                name="默认看板",
                description="工作流的默认看板视图",
                board_type="kanban",
                layout_config={
                    "columns_per_row": 4,
                    "auto_layout": True
                },
                display_config={
                    "show_task_count": True,
                    "show_progress": True
                }
            )
            
            await self.state_manager.save_board(board)
            
            # 为每个阶段创建看板列
            for i, stage_data in enumerate(stages):
                column = BoardColumn(
                    board_id=board.id,
                    name=stage_data["name"],
                    description=stage_data.get("description", ""),
                    order_index=i,
                    color=self._get_stage_color(i),
                    max_tasks=stage_data.get("max_tasks", 10)
                )
                await self.state_manager.save_board_column(column)
            
            logger.info(f"📊 默认看板创建成功: {board.id}")
            
        except Exception as e:
            logger.error(f"❌ 默认看板创建失败: {str(e)}")
    
    def _get_stage_color(self, index: int) -> str:
        """获取阶段颜色"""
        colors = ["#3498db", "#2ecc71", "#f39c12", "#e74c3c", "#9b59b6", "#1abc9c"]
        return colors[index % len(colors)]
    
    async def _register_default_executors(self):
        """注册默认任务执行器"""
        self._task_executors = {
            TaskType.USER_INPUT: self._execute_user_input_task,
            TaskType.AI_PROCESS: self._execute_ai_process_task,
            TaskType.HUMAN_REVIEW: self._execute_human_review_task,
            TaskType.SYSTEM_TASK: self._execute_system_task,
            TaskType.INTEGRATION: self._execute_integration_task
        }
    
    async def _register_default_role_handlers(self):
        """注册默认角色处理器"""
        self._role_handlers = {
            "analyst": self._handle_analyst_role,
            "reviewer": self._handle_reviewer_role,
            "processor": self._handle_processor_role
        }
    
    # 默认任务执行器实现
    async def _execute_user_input_task(self, task: Task, context: Dict) -> Dict[str, Any]:
        """执行用户输入任务"""
        # 等待用户输入或返回模拟结果
        await asyncio.sleep(0.1)  # 模拟处理时间
        return {"status": "waiting_for_input", "prompt": task.description}
    
    async def _execute_ai_process_task(self, task: Task, context: Dict) -> Dict[str, Any]:
        """执行AI处理任务"""
        # 调用模型服务进行AI处理
        await asyncio.sleep(1.0)  # 模拟AI处理时间
        return {"status": "processed", "result": f"AI processed: {task.title}"}
    
    async def _execute_human_review_task(self, task: Task, context: Dict) -> Dict[str, Any]:
        """执行人工审核任务"""
        # 等待人工审核
        await asyncio.sleep(0.1)  # 模拟处理时间
        return {"status": "pending_review", "reviewer": task.assignee}
    
    async def _execute_system_task(self, task: Task, context: Dict) -> Dict[str, Any]:
        """执行系统任务"""
        # 执行系统级任务
        await asyncio.sleep(0.5)  # 模拟系统处理时间
        return {"status": "system_completed", "result": "System task executed"}
    
    async def _execute_integration_task(self, task: Task, context: Dict) -> Dict[str, Any]:
        """执行集成任务"""
        # 调用外部系统
        await asyncio.sleep(0.8)  # 模拟集成调用时间
        return {"status": "integration_completed", "external_result": "External system response"}
    
    # 默认角色处理器实现
    async def _handle_analyst_role(self, task: Task, context: Dict) -> Dict[str, Any]:
        """处理分析师角色"""
        # 分析师特定的处理逻辑
        return {"role": "analyst", "analysis": "Data analyzed"}
    
    async def _handle_reviewer_role(self, task: Task, context: Dict) -> Dict[str, Any]:
        """处理审核员角色"""
        # 审核员特定的处理逻辑
        return {"role": "reviewer", "review": "Content reviewed"}
    
    async def _handle_processor_role(self, task: Task, context: Dict) -> Dict[str, Any]:
        """处理处理器角色"""
        # 处理器特定的处理逻辑
        return {"role": "processor", "processed": "Content processed"} 