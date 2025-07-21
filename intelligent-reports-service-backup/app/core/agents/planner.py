"""
任务规划智能体
"""
from typing import Dict, Any, List, Optional
from app.core.agents.base import BaseAgent
from app.models.agent import AgentModel, AgentType
from app.core.tasks.plan import Plan
from app.core.tasks.manager import TaskManager
from app.core.tools.plan_toolkit import PlanToolkit
from app.core.tools.terminate_toolkit import TerminateToolkit
from app.utils.logging import get_logger


logger = get_logger(__name__)


class TaskPlannerAgent(BaseAgent):
    """任务规划智能体"""
    
    def __init__(self, agent_model: AgentModel, llm_client, plan_id: str = None):
        super().__init__(agent_model, llm_client)
        
        # 获取或创建计划
        self.plan_id = plan_id
        if plan_id:
            self.plan = TaskManager.get_plan(plan_id)
        else:
            self.plan = None
        
        # 初始化工具
        self._initialize_planner_tools()
        
        # 添加系统提示词
        self.add_to_history("system", self.get_system_prompt())
    
    def _initialize_planner_tools(self):
        """初始化规划工具"""
        if self.plan:
            plan_toolkit = PlanToolkit(self.plan)
            self.add_function(
                "create_plan",
                plan_toolkit.create_plan,
                "创建执行计划",
                {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "计划标题"},
                        "steps": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "执行步骤列表"
                        },
                        "dependencies": {
                            "type": "object",
                            "description": "步骤依赖关系"
                        }
                    },
                    "required": ["title", "steps"]
                }
            )
            
            self.add_function(
                "update_plan",
                plan_toolkit.update_plan,
                "更新执行计划",
                {
                    "type": "object",
                    "properties": {
                        "step_index": {"type": "integer", "description": "步骤索引"},
                        "step_content": {"type": "string", "description": "步骤内容"},
                        "operation": {
                            "type": "string",
                            "enum": ["add", "update", "remove"],
                            "description": "操作类型"
                        }
                    },
                    "required": ["step_index", "operation"]
                }
            )
        
        # 添加终止工具
        terminate_toolkit = TerminateToolkit()
        self.add_function(
            "terminate",
            terminate_toolkit.terminate,
            "终止任务执行",
            {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "终止原因"},
                    "result": {"type": "string", "description": "最终结果"}
                },
                "required": ["reason"]
            }
        )
    
    def get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """你是一个专业的任务规划智能体，负责分析用户需求并制定详细的执行计划。

你的主要职责：
1. 理解用户的需求和目标
2. 将复杂任务分解为可执行的步骤
3. 确定步骤之间的依赖关系
4. 制定合理的执行顺序
5. 考虑资源限制和时间约束

规划原则：
- 步骤应该具体、可操作、可验证
- 考虑步骤之间的逻辑依赖关系
- 尽可能并行执行独立的步骤
- 预留错误处理和备选方案
- 确保计划的完整性和可行性

请使用提供的工具创建和管理执行计划。
"""
    
    def prepare_messages(self, input_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """准备消息"""
        messages = self.get_history()
        
        # 添加用户请求
        user_message = self._format_user_request(input_data)
        messages.append({"role": "user", "content": user_message})
        
        return messages
    
    def _format_user_request(self, input_data: Dict[str, Any]) -> str:
        """格式化用户请求"""
        question = input_data.get("question", "")
        output_format = input_data.get("output_format", "")
        
        if output_format:
            return f"""
请为以下任务创建详细的执行计划：

任务: {question}

输出格式要求: {output_format}

请使用create_plan工具创建计划，确保：
1. 步骤清晰具体
2. 逻辑顺序合理
3. 包含必要的依赖关系
4. 考虑输出格式要求
"""
        else:
            return f"""
请为以下任务创建详细的执行计划：

任务: {question}

请使用create_plan工具创建计划，确保：
1. 步骤清晰具体
2. 逻辑顺序合理
3. 包含必要的依赖关系
"""
    
    async def create_plan(self, question: str, output_format: str = "") -> str:
        """创建计划"""
        input_data = {
            "question": question,
            "output_format": output_format
        }
        
        messages = self.prepare_messages(input_data)
        result = await self.execute(messages, max_iteration=3)
        
        return result
    
    async def re_plan(self, question: str, output_format: str = "") -> str:
        """重新规划"""
        if not self.plan:
            return await self.create_plan(question, output_format)
        
        re_plan_message = f"""
基于当前计划执行情况，请重新评估和调整计划：

原始任务: {question}
输出格式要求: {output_format}

当前计划状态:
{self.plan.format()}

请分析当前进度，识别问题，并使用update_plan工具调整计划。
"""
        
        messages = self.get_history()
        messages.append({"role": "user", "content": re_plan_message})
        
        result = await self.execute(messages, max_iteration=3)
        return result
    
    async def finalize_plan(self, question: str, output_format: str = "") -> str:
        """最终化计划"""
        if not self.plan:
            return "无可用计划"
        
        finalize_message = f"""
请基于计划执行结果，生成最终的总结报告：

任务: {question}
输出格式要求: {output_format}

计划执行状态:
{self.plan.format()}

请提供：
1. 任务完成情况总结
2. 关键结果和发现
3. 生成的文件和资源
4. 遇到的问题和解决方案
"""
        
        messages = self.get_history()
        messages.append({"role": "user", "content": finalize_message})
        
        # 不使用工具，直接生成总结
        response = await self._call_llm(messages, [])
        
        # 设置计划结果
        if self.plan:
            self.plan.set_plan_result(response.content)
        
        return self._format_final_result(question, response.content)
    
    def _format_final_result(self, question: str, summary: str) -> str:
        """格式化最终结果"""
        plan_status = self.plan.format() if self.plan else "无计划信息"
        
        return f"""
任务: {question}

计划状态:
{plan_status}

总结:
{summary}
"""
    
    def get_termination_tools(self) -> List[str]:
        """获取终止工具列表"""
        return ["terminate", "create_plan", "update_plan"]
    
    def set_plan(self, plan: Plan):
        """设置计划"""
        self.plan = plan
        self.plan_id = plan.plan_id if hasattr(plan, 'plan_id') else None
        
        # 重新初始化工具
        self._initialize_planner_tools()
    
    def get_plan_status(self) -> Dict[str, Any]:
        """获取计划状态"""
        if not self.plan:
            return {"status": "no_plan", "message": "无可用计划"}
        
        return {
            "status": "active",
            "plan_id": self.plan_id,
            "title": self.plan.title,
            "total_steps": len(self.plan.steps),
            "completed_steps": len([s for s in self.plan.step_statuses.values() if s == "completed"]),
            "in_progress_steps": len([s for s in self.plan.step_statuses.values() if s == "in_progress"]),
            "blocked_steps": len([s for s in self.plan.step_statuses.values() if s == "blocked"]),
            "not_started_steps": len([s for s in self.plan.step_statuses.values() if s == "not_started"]),
            "progress": self.plan.get_progress(),
            "ready_steps": self.plan.get_ready_steps(),
        }
    
    def __repr__(self):
        return f"<TaskPlannerAgent {self.agent_model.name} plan_id={self.plan_id}>"


def create_planner_agent(agent_model: AgentModel, llm_client, plan_id: str = None) -> TaskPlannerAgent:
    """创建规划智能体"""
    # 确保智能体类型正确
    if agent_model.type != AgentType.PLANNER:
        raise ValueError(f"智能体类型必须是 {AgentType.PLANNER}，当前类型是 {agent_model.type}")
    
    return TaskPlannerAgent(agent_model, llm_client, plan_id)


def create_planner_instance(instance_name: str, llm_client = None, plan_id: str = None) -> TaskPlannerAgent:
    """创建规划智能体实例"""
    # 创建默认智能体模型
    agent_model = AgentModel(
        name=instance_name,
        display_name="任务规划智能体",
        description="负责分析任务需求并制定执行计划",
        type=AgentType.PLANNER,
        configuration={
            "max_planning_steps": 50,
            "enable_dependency_analysis": True,
            "enable_resource_optimization": True,
        },
        model_config={
            "temperature": 0.7,
            "max_tokens": 2000,
        },
        max_iteration=3,
        user_id="system",
    )
    
    return TaskPlannerAgent(agent_model, llm_client, plan_id)