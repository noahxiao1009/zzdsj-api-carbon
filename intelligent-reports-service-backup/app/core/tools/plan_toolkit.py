"""
计划工具包
"""
from typing import Dict, List, Any, Optional
from app.core.tasks.plan import Plan
from app.core.tools.base import BaseTool
from app.utils.logging import get_logger


logger = get_logger(__name__)


class PlanToolkit(BaseTool):
    """计划工具包"""
    
    def __init__(self, plan: Plan):
        super().__init__(
            name="plan_toolkit",
            description="用于管理任务计划的工具包",
            config={}
        )
        self.plan = plan
    
    async def execute(self, *args, **kwargs) -> Any:
        """执行工具 - 此方法不直接使用"""
        return "PlanToolkit is a collection of tools"
    
    def get_parameters(self) -> Dict[str, Any]:
        """获取参数定义"""
        return {}
    
    def create_plan(self, title: str, steps: List[str], dependencies: Dict[int, List[int]] = None) -> str:
        """创建计划
        
        Args:
            title: 计划标题
            steps: 步骤列表
            dependencies: 依赖关系字典
        
        Returns:
            创建结果信息
        """
        try:
            # 转换依赖关系键类型
            if dependencies:
                dependencies = {int(k): v for k, v in dependencies.items()}
            
            # 更新计划
            self.plan.update(title=title, steps=steps, dependencies=dependencies)
            
            logger.info(f"Created plan: {title} with {len(steps)} steps")
            
            result = f"成功创建计划 '{title}'，包含 {len(steps)} 个步骤。\n\n"
            result += self.plan.format()
            
            return result
            
        except Exception as e:
            error_msg = f"创建计划失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
    
    def update_plan(self, step_index: int, operation: str, step_content: str = None) -> str:
        """更新计划
        
        Args:
            step_index: 步骤索引
            operation: 操作类型 (add, update, remove)
            step_content: 步骤内容
        
        Returns:
            更新结果信息
        """
        try:
            if operation == "add":
                if step_content:
                    self.plan.add_step(step_content)
                    result = f"成功添加步骤: {step_content}"
                else:
                    return "添加步骤时必须提供步骤内容"
            
            elif operation == "update":
                if step_index < 0 or step_index >= len(self.plan.steps):
                    return f"步骤索引超出范围: {step_index}"
                
                if step_content:
                    old_step = self.plan.steps[step_index]
                    # 更新步骤内容
                    new_steps = self.plan.steps.copy()
                    new_steps[step_index] = step_content
                    
                    # 更新状态映射
                    new_statuses = {}
                    new_notes = {}
                    new_details = {}
                    new_files = {}
                    
                    for i, step in enumerate(new_steps):
                        if i == step_index:
                            # 保留旧状态但使用新内容
                            new_statuses[step] = self.plan.step_statuses.get(old_step, "not_started")
                            new_notes[step] = self.plan.step_notes.get(old_step, "")
                            new_details[step] = self.plan.step_details.get(old_step, "")
                            new_files[step] = self.plan.step_files.get(old_step, "")
                        else:
                            new_statuses[step] = self.plan.step_statuses.get(step, "not_started")
                            new_notes[step] = self.plan.step_notes.get(step, "")
                            new_details[step] = self.plan.step_details.get(step, "")
                            new_files[step] = self.plan.step_files.get(step, "")
                    
                    self.plan.steps = new_steps
                    self.plan.step_statuses = new_statuses
                    self.plan.step_notes = new_notes
                    self.plan.step_details = new_details
                    self.plan.step_files = new_files
                    
                    result = f"成功更新步骤 {step_index}: {old_step} -> {step_content}"
                else:
                    return "更新步骤时必须提供新的步骤内容"
            
            elif operation == "remove":
                if step_index < 0 or step_index >= len(self.plan.steps):
                    return f"步骤索引超出范围: {step_index}"
                
                removed_step = self.plan.steps[step_index]
                self.plan.remove_step(step_index)
                result = f"成功移除步骤 {step_index}: {removed_step}"
            
            else:
                return f"不支持的操作类型: {operation}"
            
            logger.info(f"Updated plan with operation: {operation}")
            result += f"\n\n更新后的计划:\n{self.plan.format()}"
            
            return result
            
        except Exception as e:
            error_msg = f"更新计划失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
    
    def add_dependency(self, step_index: int, depends_on: List[int]) -> str:
        """添加步骤依赖
        
        Args:
            step_index: 步骤索引
            depends_on: 依赖的步骤索引列表
        
        Returns:
            操作结果
        """
        try:
            if step_index < 0 or step_index >= len(self.plan.steps):
                return f"步骤索引超出范围: {step_index}"
            
            # 验证依赖索引
            for dep in depends_on:
                if dep < 0 or dep >= len(self.plan.steps):
                    return f"依赖步骤索引超出范围: {dep}"
                if dep == step_index:
                    return f"步骤不能依赖自己: {step_index}"
            
            self.plan.dependencies[step_index] = depends_on
            
            result = f"成功为步骤 {step_index} 添加依赖: {depends_on}"
            logger.info(result)
            
            return result
            
        except Exception as e:
            error_msg = f"添加依赖失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
    
    def get_plan_status(self) -> str:
        """获取计划状态"""
        return self.plan.format(with_detail=True)
    
    def get_ready_steps(self) -> str:
        """获取就绪步骤"""
        ready_steps = self.plan.get_ready_steps()
        if ready_steps:
            step_info = []
            for idx in ready_steps:
                step_info.append(f"步骤 {idx}: {self.plan.steps[idx]}")
            return f"就绪步骤:\n" + "\n".join(step_info)
        else:
            return "当前没有就绪的步骤"
    
    def get_progress(self) -> str:
        """获取进度信息"""
        progress = self.plan.get_progress()
        percentage = self.plan.get_completion_percentage()
        
        return f"""
计划进度:
- 总步骤数: {progress['total']}
- 已完成: {progress['completed']}
- 进行中: {progress['in_progress']}
- 被阻塞: {progress['blocked']}
- 未开始: {progress['not_started']}
- 完成百分比: {percentage:.1f}%
"""
    
    def validate_plan(self) -> str:
        """验证计划的有效性"""
        issues = []
        
        # 检查空计划
        if not self.plan.steps:
            issues.append("计划没有任何步骤")
        
        # 检查依赖关系
        for step_idx, deps in self.plan.dependencies.items():
            if step_idx >= len(self.plan.steps):
                issues.append(f"步骤索引超出范围: {step_idx}")
            
            for dep in deps:
                if dep >= len(self.plan.steps):
                    issues.append(f"依赖步骤索引超出范围: {dep}")
                if dep == step_idx:
                    issues.append(f"步骤 {step_idx} 不能依赖自己")
        
        # 检查循环依赖
        def has_cycle(graph: Dict[int, List[int]]) -> bool:
            visited = set()
            rec_stack = set()
            
            def dfs(node: int) -> bool:
                if node in rec_stack:
                    return True
                if node in visited:
                    return False
                
                visited.add(node)
                rec_stack.add(node)
                
                for neighbor in graph.get(node, []):
                    if dfs(neighbor):
                        return True
                
                rec_stack.remove(node)
                return False
            
            for node in graph:
                if node not in visited:
                    if dfs(node):
                        return True
            return False
        
        if has_cycle(self.plan.dependencies):
            issues.append("存在循环依赖")
        
        if issues:
            return f"计划验证失败:\n" + "\n".join(f"- {issue}" for issue in issues)
        else:
            return "计划验证通过"


def create_plan_toolkit(plan: Plan) -> PlanToolkit:
    """创建计划工具包"""
    return PlanToolkit(plan)