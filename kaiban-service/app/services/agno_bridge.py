"""
Kaiban与Agno智能体框架的桥接层
负责将Kaiban工作流与Agno智能体系统集成
"""

import logging
import httpx
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

from app.core.config import settings
from app.models.workflow import Workflow
from app.models.task import Task

logger = logging.getLogger(__name__)

class AgnoBridge:
    """Agno框架桥接器"""
    
    def __init__(self):
        self.agent_service_url = getattr(settings, 'AGENT_SERVICE_URL', 'http://localhost:8001')
        self.timeout = 30.0
        
    async def _make_request(self, method: str, endpoint: str, data: Dict = None, headers: Dict = None) -> Dict:
        """发起HTTP请求到agent-service"""
        url = f"{self.agent_service_url}/api/v1/agents{endpoint}"
        default_headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        if headers:
            default_headers.update(headers)
            
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                if method.upper() == 'GET':
                    response = await client.get(url, headers=default_headers, params=data)
                elif method.upper() == 'POST':
                    response = await client.post(url, headers=default_headers, json=data)
                elif method.upper() == 'PUT':
                    response = await client.put(url, headers=default_headers, json=data)
                elif method.upper() == 'DELETE':
                    response = await client.delete(url, headers=default_headers)
                else:
                    raise ValueError(f"不支持的HTTP方法: {method}")
                
                response.raise_for_status()
                return response.json()
                
            except httpx.HTTPStatusError as e:
                logger.error(f"Agent服务请求失败: {e.response.status_code} - {e.response.text}")
                raise Exception(f"Agent服务请求失败: {e.response.status_code}")
            except httpx.RequestError as e:
                logger.error(f"Agent服务连接失败: {e}")
                raise Exception(f"Agent服务连接失败: {e}")
            except Exception as e:
                logger.error(f"未知错误: {e}")
                raise
    
    async def get_agent_templates(self, category: Optional[str] = None) -> List[Dict]:
        """获取智能体模板列表"""
        params = {'category': category} if category else None
        return await self._make_request('GET', '/templates', data=params)
    
    async def get_agent_template(self, template_id: str) -> Dict:
        """获取指定模板详情"""
        return await self._make_request('GET', f'/templates/{template_id}')
    
    async def create_agent_from_workflow(self, workflow: Workflow, user_id: str) -> Dict:
        """基于工作流创建智能体"""
        try:
            # 构建智能体配置
            agent_config = {
                'name': workflow.name,
                'description': workflow.description,
                'template_id': 'intelligent-planning',  # 使用智能规划模板
                'config': {
                    'model_config': workflow.config.get('model_config', {}),
                    'prompt_template': self._generate_workflow_prompt(workflow),
                    'tools': workflow.config.get('tools', []),
                    'knowledge_base_ids': workflow.config.get('knowledge_base_ids', []),
                    'workflow_config': {
                        'workflow_id': workflow.id,
                        'trigger_type': workflow.trigger_type,
                        'version': workflow.version,
                        'auto_execution': workflow.config.get('auto_execution', False)
                    }
                },
                'tags': ['workflow', 'kaiban', workflow.status],
                'is_public': False
            }
            
            # 创建智能体
            headers = {'User-ID': user_id}  # 模拟用户认证
            agent = await self._make_request('POST', '/create', data=agent_config, headers=headers)
            
            logger.info(f"为工作流 {workflow.id} 创建智能体成功: {agent['agent_id']}")
            return agent
            
        except Exception as e:
            logger.error(f"创建智能体失败: {e}")
            raise Exception(f"创建智能体失败: {e}")
    
    def _generate_workflow_prompt(self, workflow: Workflow) -> str:
        """为工作流生成智能体提示词"""
        prompt = f"""
你是一个智能工作流执行助手，负责执行名为"{workflow.name}"的工作流。

工作流描述：{workflow.description}

工作流配置：
- 触发方式：{workflow.trigger_type}
- 当前版本：{workflow.version}
- 状态：{workflow.status}

主要职责：
1. 根据用户输入理解任务需求
2. 将复杂任务分解为多个子任务
3. 按照工作流程逐步执行任务
4. 实时更新任务状态和进度
5. 在任务完成后提供总结报告

执行原则：
- 严格按照工作流定义的步骤执行
- 确保每个子任务都有明确的输入和输出
- 及时反馈执行状态和进度
- 遇到问题时主动寻求用户确认
- 保持执行过程的透明性和可追溯性

现在请根据用户的输入开始执行工作流任务。
"""
        return prompt.strip()
    
    async def execute_workflow_with_agent(self, agent_id: str, workflow_id: str, tasks: List[Task], user_id: str) -> Dict:
        """使用智能体执行工作流"""
        try:
            # 构建执行请求
            execution_request = {
                'workflow_id': workflow_id,
                'input_data': {
                    'tasks': [self._task_to_dict(task) for task in tasks],
                    'execution_mode': 'sequential',  # 顺序执行
                    'auto_proceed': False  # 需要人工确认
                },
                'execution_config': {
                    'max_steps': 50,
                    'timeout': 300,  # 5分钟超时
                    'save_intermediate': True
                }
            }
            
            headers = {'User-ID': user_id}
            result = await self._make_request(
                'POST', 
                f'/{agent_id}/flow/execute', 
                data=execution_request,
                headers=headers
            )
            
            logger.info(f"智能体 {agent_id} 执行工作流 {workflow_id} 成功")
            return result
            
        except Exception as e:
            logger.error(f"智能体执行工作流失败: {e}")
            raise Exception(f"智能体执行工作流失败: {e}")
    
    def _task_to_dict(self, task: Task) -> Dict:
        """将任务对象转换为字典"""
        return {
            'id': task.id,
            'title': task.title,
            'description': task.description,
            'status': task.status,
            'priority': task.priority,
            'assignee': task.assignee,
            'due_date': task.due_date.isoformat() if task.due_date else None,
            'tags': task.tags or [],
            'meta_data': task.meta_data or {}
        }
    
    async def update_agent_workflow_design(self, agent_id: str, workflow: Workflow, user_id: str) -> Dict:
        """更新智能体的工作流设计"""
        try:
            flow_design = {
                'workflow_id': workflow.id,
                'flow_definition': {
                    'name': workflow.name,
                    'description': workflow.description,
                    'version': workflow.version,
                    'nodes': self._generate_flow_nodes(workflow),
                    'edges': self._generate_flow_edges(workflow),
                    'config': workflow.config
                },
                'execution_config': {
                    'trigger_type': workflow.trigger_type,
                    'auto_execution': workflow.config.get('auto_execution', False),
                    'max_parallel_tasks': workflow.config.get('max_parallel_tasks', 3)
                }
            }
            
            headers = {'User-ID': user_id}
            result = await self._make_request(
                'POST',
                f'/{agent_id}/flow/design',
                data=flow_design,
                headers=headers
            )
            
            logger.info(f"更新智能体 {agent_id} 工作流设计成功")
            return result
            
        except Exception as e:
            logger.error(f"更新智能体工作流设计失败: {e}")
            raise Exception(f"更新智能体工作流设计失败: {e}")
    
    def _generate_flow_nodes(self, workflow: Workflow) -> List[Dict]:
        """生成工作流节点"""
        nodes = [
            {
                'id': 'start',
                'type': 'start',
                'label': '开始',
                'position': {'x': 100, 'y': 100}
            },
            {
                'id': 'task_analysis',
                'type': 'analysis',
                'label': '任务分析',
                'position': {'x': 300, 'y': 100},
                'config': {
                    'analysis_type': 'requirement',
                    'output_format': 'structured'
                }
            },
            {
                'id': 'task_decomposition',
                'type': 'decomposition',
                'label': '任务分解',
                'position': {'x': 500, 'y': 100},
                'config': {
                    'max_subtasks': 10,
                    'decomposition_strategy': 'priority_based'
                }
            },
            {
                'id': 'task_execution',
                'type': 'execution',
                'label': '任务执行',
                'position': {'x': 700, 'y': 100},
                'config': {
                    'execution_mode': 'sequential',
                    'retry_count': 3
                }
            },
            {
                'id': 'result_summary',
                'type': 'summary',
                'label': '结果汇总',
                'position': {'x': 900, 'y': 100},
                'config': {
                    'summary_format': 'report',
                    'include_metrics': True
                }
            },
            {
                'id': 'end',
                'type': 'end',
                'label': '结束',
                'position': {'x': 1100, 'y': 100}
            }
        ]
        return nodes
    
    def _generate_flow_edges(self, workflow: Workflow) -> List[Dict]:
        """生成工作流边连接"""
        edges = [
            {
                'id': 'e1',
                'source': 'start',
                'target': 'task_analysis',
                'type': 'default'
            },
            {
                'id': 'e2',
                'source': 'task_analysis',
                'target': 'task_decomposition',
                'type': 'default'
            },
            {
                'id': 'e3',
                'source': 'task_decomposition',
                'target': 'task_execution',
                'type': 'default'
            },
            {
                'id': 'e4',
                'source': 'task_execution',
                'target': 'result_summary',
                'type': 'default'
            },
            {
                'id': 'e5',
                'source': 'result_summary',
                'target': 'end',
                'type': 'default'
            }
        ]
        return edges
    
    async def chat_with_workflow_agent(self, agent_id: str, message: str, user_id: str, stream: bool = False) -> Dict:
        """与工作流智能体对话"""
        try:
            chat_request = {
                'message': message,
                'conversation_id': f"workflow_{datetime.now().isoformat()}",
                'context': {
                    'source': 'kaiban_workflow',
                    'timestamp': datetime.now().isoformat()
                },
                'stream': stream
            }
            
            headers = {'User-ID': user_id}
            endpoint = f'/{agent_id}/chat/stream' if stream else f'/{agent_id}/chat'
            
            result = await self._make_request('POST', endpoint, data=chat_request, headers=headers)
            return result
            
        except Exception as e:
            logger.error(f"与智能体对话失败: {e}")
            raise Exception(f"与智能体对话失败: {e}")
    
    async def get_agent_workflow_stats(self, agent_id: str, user_id: str, period: str = "7d") -> Dict:
        """获取智能体工作流统计信息"""
        try:
            headers = {'User-ID': user_id}
            params = {'period': period}
            result = await self._make_request('GET', f'/{agent_id}/stats', data=params, headers=headers)
            return result
            
        except Exception as e:
            logger.error(f"获取智能体统计信息失败: {e}")
            raise Exception(f"获取智能体统计信息失败: {e}")
    
    async def sync_workflow_status_to_agent(self, agent_id: str, workflow: Workflow, user_id: str) -> bool:
        """同步工作流状态到智能体"""
        try:
            # 根据工作流状态决定智能体操作
            if workflow.status == 'active':
                action = 'activate'
            elif workflow.status == 'paused':
                action = 'pause'
            elif workflow.status == 'archived':
                action = 'deactivate'
            else:
                return True  # 草稿状态不需要同步
            
            headers = {'User-ID': user_id}
            await self._make_request('POST', f'/{agent_id}/status/{action}', headers=headers)
            
            logger.info(f"同步工作流 {workflow.id} 状态到智能体 {agent_id} 成功")
            return True
            
        except Exception as e:
            logger.error(f"同步工作流状态失败: {e}")
            return False
    
    async def test_agent_connection(self) -> bool:
        """测试与agent-service的连接"""
        try:
            await self._make_request('GET', '/templates', data={'category': 'simple-qa'})
            logger.info("Agent服务连接测试成功")
            return True
        except Exception as e:
            logger.error(f"Agent服务连接测试失败: {e}")
            return False

# 全局桥接器实例
agno_bridge = AgnoBridge() 