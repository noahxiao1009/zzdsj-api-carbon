"""
任务执行智能体
"""
import os
import re
from typing import Dict, Any, List, Optional
from app.core.agents.base import BaseAgent
from app.models.agent import AgentModel, AgentType
from app.core.tasks.plan import Plan
from app.core.tasks.manager import TaskManager
from app.core.tools.act_toolkit import ActToolkit
from app.core.tools.terminate_toolkit import TerminateToolkit
from app.core.tools.file_toolkit import FileToolkit
from app.core.tools.search.search_toolkit import SearchToolkit
from app.core.tools.code.code_toolkit import CodeToolkit
from app.core.tools.visualization.html_toolkit import HtmlVisualizationToolkit
from app.config.settings import settings
from app.utils.logging import get_logger


logger = get_logger(__name__)


class TaskActorAgent(BaseAgent):
    """任务执行智能体"""
    
    def __init__(self, agent_model: AgentModel, llm_client, vision_llm_client=None, 
                 tool_llm_client=None, plan_id: str = None, workspace_path: str = None):
        super().__init__(agent_model, llm_client)
        
        # 设置其他LLM客户端
        self.vision_llm_client = vision_llm_client or llm_client
        self.tool_llm_client = tool_llm_client or llm_client
        
        # 设置工作空间
        self.workspace_path = workspace_path or settings.workspace_path
        
        # 获取计划
        self.plan_id = plan_id
        if plan_id:
            self.plan = TaskManager.get_plan(plan_id)
        else:
            self.plan = None
        
        # 存储用户问题
        self.question = None
        
        # 初始化工具
        self._initialize_actor_tools()
        
        # 添加系统提示词
        self.add_to_history("system", self.get_system_prompt())
    
    def _initialize_actor_tools(self):
        """初始化执行工具"""
        # 基础工具
        if self.plan:
            act_toolkit = ActToolkit(self.plan)
            self.add_function(
                "mark_step",
                act_toolkit.mark_step,
                "标记步骤完成状态",
                {
                    "type": "object",
                    "properties": {
                        "step_index": {"type": "integer", "description": "步骤索引"},
                        "step_status": {
                            "type": "string",
                            "enum": ["completed", "in_progress", "blocked", "not_started"],
                            "description": "步骤状态"
                        },
                        "step_notes": {"type": "string", "description": "步骤备注"},
                        "step_result": {"type": "string", "description": "步骤结果"}
                    },
                    "required": ["step_index", "step_status"]
                }
            )
        
        # 文件工具
        file_toolkit = FileToolkit(self.workspace_path)
        self.add_function(
            "file_saver",
            file_toolkit.file_saver,
            "保存文件到工作空间",
            {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "文件路径"},
                    "content": {"type": "string", "description": "文件内容"},
                    "encoding": {"type": "string", "default": "utf-8", "description": "编码格式"}
                },
                "required": ["file_path", "content"]
            }
        )
        
        self.add_function(
            "file_read",
            file_toolkit.file_read,
            "读取文件内容",
            {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "文件路径"},
                    "encoding": {"type": "string", "default": "utf-8", "description": "编码格式"}
                },
                "required": ["file_path"]
            }
        )
        
        self.add_function(
            "file_str_replace",
            file_toolkit.file_str_replace,
            "替换文件中的字符串",
            {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "文件路径"},
                    "old_str": {"type": "string", "description": "要替换的字符串"},
                    "new_str": {"type": "string", "description": "新字符串"}
                },
                "required": ["file_path", "old_str", "new_str"]
            }
        )
        
        self.add_function(
            "file_find_in_content",
            file_toolkit.file_find_in_content,
            "在文件内容中查找字符串",
            {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "文件路径"},
                    "search_str": {"type": "string", "description": "搜索字符串"},
                    "case_sensitive": {"type": "boolean", "default": False, "description": "是否区分大小写"}
                },
                "required": ["file_path", "search_str"]
            }
        )
        
        # 搜索工具
        search_toolkit = SearchToolkit()
        self.add_function(
            "search_baidu",
            search_toolkit.search_baidu,
            "使用百度搜索",
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索查询"},
                    "num_results": {"type": "integer", "default": 10, "description": "结果数量"}
                },
                "required": ["query"]
            }
        )
        
        self.add_function(
            "search_google",
            search_toolkit.search_google,
            "使用Google搜索",
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索查询"},
                    "num_results": {"type": "integer", "default": 10, "description": "结果数量"}
                },
                "required": ["query"]
            }
        )
        
        self.add_function(
            "tavily_search",
            search_toolkit.tavily_search,
            "使用Tavily搜索",
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索查询"},
                    "search_depth": {"type": "string", "enum": ["basic", "advanced"], "default": "basic", "description": "搜索深度"}
                },
                "required": ["query"]
            }
        )
        
        # 代码执行工具
        code_toolkit = CodeToolkit(sandbox="subprocess")
        self.add_function(
            "execute_code",
            code_toolkit.execute_code,
            "执行代码",
            {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "要执行的代码"},
                    "language": {"type": "string", "enum": ["python", "bash", "javascript"], "default": "python", "description": "编程语言"},
                    "timeout": {"type": "integer", "default": 30, "description": "超时时间(秒)"}
                },
                "required": ["code"]
            }
        )
        
        # HTML可视化工具
        html_toolkit = HtmlVisualizationToolkit(workspace_path=self.workspace_path)
        self.add_function(
            "create_html_report",
            lambda title=None, include_charts=True, chart_types=['all'], output_filename=None: html_toolkit.create_html_report(
                title=title,
                include_charts=include_charts,
                chart_types=chart_types,
                output_filename=output_filename,
                user_query=self.question
            ),
            "创建HTML报告",
            {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "报告标题"},
                    "include_charts": {"type": "boolean", "default": True, "description": "是否包含图表"},
                    "chart_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": ["all"],
                        "description": "图表类型"
                    },
                    "output_filename": {"type": "string", "description": "输出文件名"}
                }
            }
        )
        
        # 终止工具
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
        is_chinese = self._is_chinese_context()
        
        if is_chinese:
            return f"""你是一个专业的任务执行智能体，负责执行具体的任务步骤。

工作空间: {self.workspace_path}

你的主要职责：
1. 按照计划执行具体的任务步骤
2. 使用提供的工具完成各种操作
3. 处理执行过程中的错误和异常
4. 记录执行结果和状态
5. 与其他智能体协作完成复杂任务

工具使用原则：
- 优先使用最适合的工具
- 注意工具的参数和限制
- 处理工具执行的错误
- 记录工具使用的结果
- 及时更新任务状态

执行规范：
- 严格按照计划步骤执行
- 遇到问题时尝试多种解决方案
- 保持工作空间整洁
- 生成有价值的中间结果
- 使用mark_step工具更新步骤状态

请根据任务需求，合理使用工具完成任务。
"""
        else:
            return f"""You are a professional task execution agent responsible for executing specific task steps.

Workspace: {self.workspace_path}

Your main responsibilities:
1. Execute specific task steps according to the plan
2. Use provided tools to complete various operations
3. Handle errors and exceptions during execution
4. Record execution results and status
5. Collaborate with other agents to complete complex tasks

Tool usage principles:
- Prioritize using the most suitable tools
- Pay attention to tool parameters and limitations
- Handle tool execution errors
- Record tool usage results
- Update task status in time

Execution standards:
- Execute strictly according to plan steps
- Try multiple solutions when encountering problems
- Keep workspace clean
- Generate valuable intermediate results
- Use mark_step tool to update step status

Please use tools reasonably to complete tasks according to task requirements.
"""
    
    def _is_chinese_context(self) -> bool:
        """判断是否是中文上下文"""
        if self.question:
            return bool(re.search(r'[\u4e00-\u9fff]', self.question))
        if self.plan and self.plan.title:
            return bool(re.search(r'[\u4e00-\u9fff]', self.plan.title))
        return True  # 默认中文
    
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
        step_index = input_data.get("step_index", 0)
        
        is_chinese = self._is_chinese_context()
        
        if is_chinese:
            if self.plan:
                return f"""
请执行以下任务步骤：

任务: {question}
步骤索引: {step_index}
步骤内容: {self.plan.steps[step_index] if step_index < len(self.plan.steps) else '未知步骤'}

当前计划状态:
{self.plan.format()}

工作空间: {self.workspace_path}

请：
1. 理解当前步骤的具体要求
2. 选择合适的工具完成任务
3. 处理执行过程中的问题
4. 使用mark_step工具更新步骤状态
5. 生成有价值的结果
"""
            else:
                return f"""
请执行以下任务：

任务: {question}
工作空间: {self.workspace_path}

请使用提供的工具完成任务，并记录执行结果。
"""
        else:
            if self.plan:
                return f"""
Please execute the following task step:

Task: {question}
Step Index: {step_index}
Step Content: {self.plan.steps[step_index] if step_index < len(self.plan.steps) else 'Unknown step'}

Current Plan Status:
{self.plan.format()}

Workspace: {self.workspace_path}

Please:
1. Understand the specific requirements of the current step
2. Choose appropriate tools to complete the task
3. Handle problems during execution
4. Use mark_step tool to update step status
5. Generate valuable results
"""
            else:
                return f"""
Please execute the following task:

Task: {question}
Workspace: {self.workspace_path}

Please use the provided tools to complete the task and record the execution results.
"""
    
    async def act(self, question: str, step_index: int = 0) -> str:
        """执行任务"""
        self.question = question
        
        # 标记步骤开始
        if self.plan and step_index < len(self.plan.steps):
            self.plan.mark_step(step_index, step_status="in_progress")
        
        try:
            input_data = {
                "question": question,
                "step_index": step_index
            }
            
            messages = self.prepare_messages(input_data)
            result = await self.execute(messages, step_index=step_index)
            
            # 检查步骤是否已完成
            if self.plan and step_index < len(self.plan.steps):
                current_status = self.plan.step_statuses.get(self.plan.steps[step_index], "")
                if current_status == "in_progress":
                    self.plan.mark_step(step_index, step_status="completed", step_notes=str(result))
            
            return result
            
        except Exception as e:
            # 标记步骤失败
            if self.plan and step_index < len(self.plan.steps):
                self.plan.mark_step(step_index, step_status="blocked", step_notes=str(e))
            
            logger.error(f"任务执行失败: {str(e)}", exc_info=True)
            return f"执行失败: {str(e)}"
    
    def get_termination_tools(self) -> List[str]:
        """获取终止工具列表"""
        return ["terminate", "mark_step"]
    
    def set_plan(self, plan: Plan):
        """设置计划"""
        self.plan = plan
        self.plan_id = plan.plan_id if hasattr(plan, 'plan_id') else None
        
        # 重新初始化工具
        self._initialize_actor_tools()
    
    def get_workspace_files(self) -> List[str]:
        """获取工作空间文件列表"""
        try:
            files = []
            for root, dirs, filenames in os.walk(self.workspace_path):
                for filename in filenames:
                    rel_path = os.path.relpath(os.path.join(root, filename), self.workspace_path)
                    files.append(rel_path)
            return files
        except Exception as e:
            logger.error(f"获取工作空间文件失败: {str(e)}")
            return []
    
    def get_execution_context(self) -> Dict[str, Any]:
        """获取执行上下文"""
        return {
            "workspace_path": self.workspace_path,
            "question": self.question,
            "plan_id": self.plan_id,
            "plan_title": self.plan.title if self.plan else None,
            "plan_progress": self.plan.get_progress() if self.plan else 0,
            "workspace_files": self.get_workspace_files(),
            "execution_stats": self.get_stats(),
        }
    
    def __repr__(self):
        return f"<TaskActorAgent {self.agent_model.name} plan_id={self.plan_id}>"


def create_actor_agent(agent_model: AgentModel, llm_client, vision_llm_client=None, 
                      tool_llm_client=None, plan_id: str = None, workspace_path: str = None) -> TaskActorAgent:
    """创建执行智能体"""
    # 确保智能体类型正确
    if agent_model.type != AgentType.ACTOR:
        raise ValueError(f"智能体类型必须是 {AgentType.ACTOR}，当前类型是 {agent_model.type}")
    
    return TaskActorAgent(
        agent_model, 
        llm_client, 
        vision_llm_client, 
        tool_llm_client, 
        plan_id, 
        workspace_path
    )


def create_actor_instance(instance_name: str, workspace_path: str = None, 
                         llm_client=None, vision_llm_client=None, 
                         tool_llm_client=None, plan_id: str = None) -> TaskActorAgent:
    """创建执行智能体实例"""
    # 创建默认智能体模型
    agent_model = AgentModel(
        name=instance_name,
        display_name="任务执行智能体",
        description="负责执行具体的任务步骤",
        type=AgentType.ACTOR,
        configuration={
            "enable_file_operations": True,
            "enable_web_search": True,
            "enable_code_execution": True,
            "enable_visualization": True,
        },
        model_config={
            "temperature": 0.3,
            "max_tokens": 2000,
        },
        max_iteration=10,
        user_id="system",
        workspace_path=workspace_path or settings.workspace_path,
    )
    
    return TaskActorAgent(
        agent_model, 
        llm_client, 
        vision_llm_client, 
        tool_llm_client, 
        plan_id, 
        workspace_path
    )