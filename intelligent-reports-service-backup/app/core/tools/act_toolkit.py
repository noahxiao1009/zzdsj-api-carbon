"""
执行动作工具包
"""
from typing import Dict, Any, Optional
from app.core.tasks.plan import Plan
from app.core.tools.base import BaseTool
from app.utils.logging import get_logger


logger = get_logger(__name__)


class ActToolkit(BaseTool):
    """执行动作工具包"""
    
    def __init__(self, plan: Plan):
        super().__init__(
            name="act_toolkit",
            description="用于执行任务步骤的工具包",
            config={}
        )
        self.plan = plan
    
    async def execute(self, *args, **kwargs) -> Any:
        """执行工具 - 此方法不直接使用"""
        return "ActToolkit is a collection of tools"
    
    def get_parameters(self) -> Dict[str, Any]:
        """获取参数定义"""
        return {}
    
    def mark_step(self, step_index: int, step_status: str, step_notes: str = None, step_result: str = None) -> str:
        """标记步骤状态
        
        Args:
            step_index: 步骤索引
            step_status: 步骤状态 (not_started, in_progress, completed, blocked)
            step_notes: 步骤备注
            step_result: 步骤结果
        
        Returns:
            标记结果信息
        """
        try:
            if step_index < 0 or step_index >= len(self.plan.steps):
                return f"步骤索引超出范围: {step_index}，有效范围: 0-{len(self.plan.steps)-1}"
            
            # 验证状态值
            valid_statuses = ["not_started", "in_progress", "completed", "blocked"]
            if step_status not in valid_statuses:
                return f"无效的步骤状态: {step_status}，有效状态: {valid_statuses}"
            
            # 标记步骤
            self.plan.mark_step(step_index, step_status, step_notes, step_result)
            
            step_name = self.plan.steps[step_index]
            result_msg = f"成功标记步骤 {step_index} '{step_name}' 为状态: {step_status}"
            
            if step_notes:
                result_msg += f"\n备注: {step_notes}"
            
            if step_result:
                result_msg += f"\n结果: {step_result}"
            
            logger.info(f"Marked step {step_index} as {step_status}")
            
            # 添加计划状态信息
            progress = self.plan.get_progress()
            result_msg += f"\n\n当前进度: {progress['completed']}/{progress['total']} 步骤已完成"
            
            return result_msg
            
        except Exception as e:
            error_msg = f"标记步骤状态失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
    
    def get_step_info(self, step_index: int) -> str:
        """获取步骤信息
        
        Args:
            step_index: 步骤索引
        
        Returns:
            步骤详细信息
        """
        try:
            if step_index < 0 or step_index >= len(self.plan.steps):
                return f"步骤索引超出范围: {step_index}"
            
            step = self.plan.steps[step_index]
            status = self.plan.step_statuses.get(step, "not_started")
            notes = self.plan.step_notes.get(step, "")
            details = self.plan.step_details.get(step, "")
            files = self.plan.step_files.get(step, "")
            
            info = f"步骤 {step_index}: {step}\n"
            info += f"状态: {status}\n"
            
            if notes:
                info += f"备注: {notes}\n"
            if details:
                info += f"详情: {details}\n"
            if files:
                info += f"文件: {files}\n"
            
            # 依赖信息
            deps = self.plan.dependencies.get(step_index, [])
            if deps:
                info += f"依赖: {deps}\n"
            
            return info
            
        except Exception as e:
            error_msg = f"获取步骤信息失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
    
    def get_current_status(self) -> str:
        """获取当前计划状态"""
        try:
            return self.plan.format(with_detail=True)
        except Exception as e:
            error_msg = f"获取计划状态失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
    
    def get_next_steps(self) -> str:
        """获取下一步可执行的步骤"""
        try:
            ready_steps = self.plan.get_ready_steps()
            
            if not ready_steps:
                return "当前没有可执行的步骤"
            
            result = "可执行的步骤:\n"
            for idx in ready_steps:
                step = self.plan.steps[idx]
                result += f"- 步骤 {idx}: {step}\n"
            
            return result
            
        except Exception as e:
            error_msg = f"获取下一步骤失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
    
    def check_dependencies(self, step_index: int) -> str:
        """检查步骤依赖
        
        Args:
            step_index: 步骤索引
        
        Returns:
            依赖检查结果
        """
        try:
            if step_index < 0 or step_index >= len(self.plan.steps):
                return f"步骤索引超出范围: {step_index}"
            
            deps = self.plan.dependencies.get(step_index, [])
            
            if not deps:
                return f"步骤 {step_index} 没有依赖"
            
            result = f"步骤 {step_index} 的依赖检查:\n"
            all_satisfied = True
            
            for dep in deps:
                if dep >= len(self.plan.steps):
                    result += f"- 依赖 {dep}: 索引超出范围\n"
                    all_satisfied = False
                    continue
                
                dep_step = self.plan.steps[dep]
                dep_status = self.plan.step_statuses.get(dep_step, "not_started")
                
                if dep_status == "completed":
                    result += f"- 依赖 {dep} '{dep_step}': ✓ 已完成\n"
                else:
                    result += f"- 依赖 {dep} '{dep_step}': ✗ 状态为 {dep_status}\n"
                    all_satisfied = False
            
            if all_satisfied:
                result += "\n所有依赖都已满足，可以执行此步骤"
            else:
                result += "\n部分依赖未满足，无法执行此步骤"
            
            return result
            
        except Exception as e:
            error_msg = f"检查依赖失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
    
    def add_step_note(self, step_index: int, note: str) -> str:
        """添加步骤备注
        
        Args:
            step_index: 步骤索引
            note: 备注内容
        
        Returns:
            操作结果
        """
        try:
            if step_index < 0 or step_index >= len(self.plan.steps):
                return f"步骤索引超出范围: {step_index}"
            
            step = self.plan.steps[step_index]
            existing_note = self.plan.step_notes.get(step, "")
            
            if existing_note:
                new_note = f"{existing_note}\n{note}"
            else:
                new_note = note
            
            self.plan.step_notes[step] = new_note
            
            logger.info(f"Added note to step {step_index}")
            return f"成功为步骤 {step_index} 添加备注"
            
        except Exception as e:
            error_msg = f"添加备注失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
    
    def block_step(self, step_index: int, reason: str) -> str:
        """阻塞步骤
        
        Args:
            step_index: 步骤索引
            reason: 阻塞原因
        
        Returns:
            操作结果
        """
        return self.mark_step(step_index, "blocked", f"阻塞原因: {reason}")
    
    def unblock_step(self, step_index: int, reason: str = "问题已解决") -> str:
        """解除步骤阻塞
        
        Args:
            step_index: 步骤索引
            reason: 解除原因
        
        Returns:
            操作结果
        """
        return self.mark_step(step_index, "not_started", f"解除阻塞: {reason}")


def create_act_toolkit(plan: Plan) -> ActToolkit:
    """创建执行工具包"""
    return ActToolkit(plan)