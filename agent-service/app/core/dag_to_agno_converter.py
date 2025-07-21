"""
DAG到Agno智能体转换器
DAG to Agno Agent Converter

将动态生成的DAG执行图转换为具体的Agno智能体实例，
实现从配置到可执行智能体的完整转换流程
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime
from dataclasses import dataclass, field
import json

from .dynamic_dag_generator import GeneratedDAG, DAGGenerationRequest
from .dag_orchestrator import DAGNode, NodeType
from .agno_api_manager import agno_manager, AgentConfig
from .tool_injection_manager import ToolDefinition, ToolExecutionRequest

logger = logging.getLogger(__name__)

@dataclass
class AgnoAgentInstance:
    """Agno智能体实例"""
    instance_id: str
    agent_id: str  # Agno内部智能体ID
    dag_id: str
    user_id: str
    
    # 配置信息
    agent_config: AgentConfig
    tools_config: Dict[str, Any]
    dag_config: Dict[str, Any]
    
    # 状态信息
    status: str = "created"  # created, active, inactive, error
    health_status: str = "unknown"
    
    # 执行统计
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    avg_execution_time: float = 0.0
    
    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    last_used_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ConversionResult:
    """转换结果"""
    success: bool
    agent_instance: Optional[AgnoAgentInstance] = None
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    
    # 转换统计
    nodes_converted: int = 0
    tools_loaded: int = 0
    conversion_time: float = 0.0

class DAGToAgnoConverter:
    """DAG到Agno智能体转换器"""
    
    def __init__(self):
        self.agno_manager = agno_manager
        self.active_instances: Dict[str, AgnoAgentInstance] = {}
        
        # 转换配置
        self.conversion_config = {
            "max_conversion_time": 60,  # 最大转换时间(秒)
            "enable_health_check": True,
            "auto_activate": True,
            "enable_monitoring": True
        }
        
        # 节点转换器映射
        self.node_converters = {
            NodeType.AGENT: self._convert_agent_node,
            NodeType.INPUT: self._convert_input_node,
            NodeType.OUTPUT: self._convert_output_node,
            NodeType.CONDITION: self._convert_condition_node,
            NodeType.MERGE: self._convert_merge_node,
            NodeType.PARALLEL: self._convert_parallel_node
        }
    
    async def convert_dag_to_agno(
        self, 
        generated_dag: GeneratedDAG,
        conversion_options: Optional[Dict[str, Any]] = None
    ) -> ConversionResult:
        """将DAG转换为Agno智能体实例"""
        start_time = datetime.now()
        logger.info(f"开始转换DAG到Agno智能体: {generated_dag.dag_id}")
        
        try:
            # 1. 验证DAG
            await self._validate_dag_for_conversion(generated_dag)
            
            # 2. 创建主智能体配置
            primary_agent_config = await self._create_primary_agent_config(generated_dag)
            
            # 3. 创建Agno智能体
            agno_agent_id = await self.agno_manager.create_agent(primary_agent_config)
            
            # 4. 配置工具
            tools_config = await self._configure_agent_tools(generated_dag, agno_agent_id)
            
            # 5. 创建智能体实例
            instance = AgnoAgentInstance(
                instance_id=f"instance_{generated_dag.dag_id}_{datetime.now().strftime('%H%M%S')}",
                agent_id=agno_agent_id,
                dag_id=generated_dag.dag_id,
                user_id=generated_dag.user_id,
                agent_config=primary_agent_config,
                tools_config=tools_config,
                dag_config=self._extract_dag_config(generated_dag)
            )
            
            # 6. 激活智能体
            if conversion_options and conversion_options.get("auto_activate", True):
                await self._activate_agent_instance(instance)
            
            # 7. 注册实例
            self.active_instances[instance.instance_id] = instance
            
            conversion_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"DAG转换成功: {instance.instance_id}, 耗时: {conversion_time:.2f}s")
            
            return ConversionResult(
                success=True,
                agent_instance=instance,
                nodes_converted=len(generated_dag.nodes),
                tools_loaded=len(generated_dag.selected_tools),
                conversion_time=conversion_time
            )
            
        except Exception as e:
            conversion_time = (datetime.now() - start_time).total_seconds()
            error_message = f"DAG转换失败: {str(e)}"
            logger.error(error_message)
            
            return ConversionResult(
                success=False,
                error_message=error_message,
                conversion_time=conversion_time
            )
    
    async def _validate_dag_for_conversion(self, dag: GeneratedDAG):
        """验证DAG是否可以转换"""
        # 检查必需节点
        has_agent_node = any(node.type == NodeType.AGENT for node in dag.nodes)
        if not has_agent_node:
            raise ValueError("DAG必须包含至少一个智能体节点")
        
        # 检查工具配置
        if not dag.selected_tools:
            logger.warning("DAG未配置任何工具，将使用默认工具")
        
        # 检查Agno管理器状态
        if not hasattr(self.agno_manager, '_initialized') or not self.agno_manager._initialized:
            raise ValueError("Agno管理器未初始化")
    
    async def _create_primary_agent_config(self, dag: GeneratedDAG) -> AgentConfig:
        """创建主智能体配置"""
        # 找到主要的智能体节点（通常是第一个）
        primary_agent_node = None
        for node in dag.nodes:
            if node.type == NodeType.AGENT:
                primary_agent_node = node
                break
        
        if not primary_agent_node:
            raise ValueError("未找到主要智能体节点")
        
        # 提取智能体配置
        agent_config_data = primary_agent_node.config.get("agent_config", {})
        
        # 获取工具Schema
        node_tools = dag.tool_mappings.get(primary_agent_node.id, [])
        tool_schemas = []
        
        for tool_id in node_tools:
            tool = next((t for t in dag.selected_tools if t.id == tool_id), None)
            if tool and tool.schema:
                tool_schemas.append(tool.schema)
        
        # 创建AgentConfig
        config = AgentConfig(
            name=agent_config_data.get("name", f"Agent_{dag.dag_id[:8]}"),
            description=agent_config_data.get("description", "Generated from DAG"),
            instructions=agent_config_data.get("instructions", "You are a helpful AI assistant."),
            model_config=agent_config_data.get("model_config", {
                "model_name": "claude-3-5-sonnet",
                "temperature": 0.7,
                "max_tokens": 1000
            }),
            tools=tool_schemas,
            knowledge_bases=agent_config_data.get("knowledge_bases", []),
            temperature=agent_config_data.get("temperature", 0.7),
            max_tokens=agent_config_data.get("max_tokens", 1000),
            memory_enabled=agent_config_data.get("memory_enabled", True)
        )
        
        # 添加DAG元数据
        config.metadata = {
            "dag_id": dag.dag_id,
            "template_id": dag.template_id,
            "generation_mode": dag.generation_mode.value,
            "optimization_score": dag.optimization_score,
            "tools_count": len(node_tools),
            "estimated_cost": dag.estimated_cost,
            "estimated_time": dag.estimated_time
        }
        
        return config
    
    async def _configure_agent_tools(self, dag: GeneratedDAG, agno_agent_id: str) -> Dict[str, Any]:
        """配置智能体工具"""
        tools_config = {
            "total_tools": len(dag.selected_tools),
            "tools_by_category": {},
            "tools_by_node": dag.tool_mappings,
            "tool_details": {}
        }
        
        # 按分类统计工具
        for tool in dag.selected_tools:
            category = tool.category.value
            if category not in tools_config["tools_by_category"]:
                tools_config["tools_by_category"][category] = []
            tools_config["tools_by_category"][category].append(tool.id)
            
            # 保存工具详情
            tools_config["tool_details"][tool.id] = {
                "name": tool.name,
                "type": tool.type.value,
                "category": tool.category.value,
                "service_name": tool.service_name,
                "is_enabled": tool.is_enabled,
                "is_available": tool.is_available,
                "schema": tool.schema
            }
        
        return tools_config
    
    def _extract_dag_config(self, dag: GeneratedDAG) -> Dict[str, Any]:
        """提取DAG配置"""
        return {
            "dag_id": dag.dag_id,
            "template_id": dag.template_id,
            "generation_mode": dag.generation_mode.value,
            "nodes_count": len(dag.nodes),
            "edges_count": len(dag.edges),
            "execution_order": dag.execution_order,
            "optimization_score": dag.optimization_score,
            "estimated_cost": dag.estimated_cost,
            "estimated_time": dag.estimated_time,
            "created_at": dag.created_at.isoformat(),
            "metadata": dag.metadata
        }
    
    async def _activate_agent_instance(self, instance: AgnoAgentInstance):
        """激活智能体实例"""
        try:
            # 执行健康检查
            if self.conversion_config["enable_health_check"]:
                health_result = await self._health_check_instance(instance)
                instance.health_status = "healthy" if health_result else "unhealthy"
            
            # 设置状态为激活
            instance.status = "active"
            logger.info(f"智能体实例已激活: {instance.instance_id}")
            
        except Exception as e:
            instance.status = "error"
            instance.metadata["activation_error"] = str(e)
            logger.error(f"激活智能体实例失败: {e}")
    
    async def _health_check_instance(self, instance: AgnoAgentInstance) -> bool:
        """健康检查智能体实例"""
        try:
            # 执行简单的测试调用
            test_result = await self.agno_manager.run_agent(
                agent_id=instance.agent_id,
                message="Health check",
                user_id=instance.user_id,
                session_id=f"health_check_{instance.instance_id}"
            )
            
            return test_result.success
            
        except Exception as e:
            logger.warning(f"健康检查失败: {e}")
            return False
    
    async def execute_agent_instance(
        self, 
        instance_id: str, 
        message: str, 
        user_id: str,
        execution_options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """执行智能体实例"""
        if instance_id not in self.active_instances:
            raise ValueError(f"智能体实例 {instance_id} 不存在")
        
        instance = self.active_instances[instance_id]
        
        if instance.status != "active":
            raise ValueError(f"智能体实例 {instance_id} 状态为 {instance.status}，无法执行")
        
        start_time = datetime.now()
        
        try:
            # 执行智能体
            result = await self.agno_manager.run_agent(
                agent_id=instance.agent_id,
                message=message,
                user_id=user_id,
                session_id=execution_options.get("session_id") if execution_options else None
            )
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # 更新统计信息
            instance.total_executions += 1
            if result.success:
                instance.successful_executions += 1
            else:
                instance.failed_executions += 1
            
            # 更新平均执行时间
            if instance.total_executions > 0:
                instance.avg_execution_time = (
                    (instance.avg_execution_time * (instance.total_executions - 1) + execution_time) 
                    / instance.total_executions
                )
            
            instance.last_used_at = datetime.now()
            
            return {
                "success": result.success,
                "response": result.response,
                "execution_time": execution_time,
                "metadata": {
                    "instance_id": instance_id,
                    "dag_id": instance.dag_id,
                    "tools_used": result.metadata.get("tools_used", []),
                    "total_executions": instance.total_executions,
                    "success_rate": instance.successful_executions / instance.total_executions
                }
            }
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            instance.total_executions += 1
            instance.failed_executions += 1
            
            logger.error(f"执行智能体实例失败: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "execution_time": execution_time,
                "metadata": {
                    "instance_id": instance_id,
                    "dag_id": instance.dag_id
                }
            }
    
    async def get_instance_status(self, instance_id: str) -> Dict[str, Any]:
        """获取智能体实例状态"""
        if instance_id not in self.active_instances:
            raise ValueError(f"智能体实例 {instance_id} 不存在")
        
        instance = self.active_instances[instance_id]
        
        return {
            "instance_id": instance.instance_id,
            "agent_id": instance.agent_id,
            "dag_id": instance.dag_id,
            "user_id": instance.user_id,
            "status": instance.status,
            "health_status": instance.health_status,
            
            # 统计信息
            "statistics": {
                "total_executions": instance.total_executions,
                "successful_executions": instance.successful_executions,
                "failed_executions": instance.failed_executions,
                "success_rate": (
                    instance.successful_executions / instance.total_executions 
                    if instance.total_executions > 0 else 0.0
                ),
                "avg_execution_time": instance.avg_execution_time
            },
            
            # 配置信息
            "configuration": {
                "agent_name": instance.agent_config.name,
                "model_name": instance.agent_config.model_config.get("model_name"),
                "tools_count": len(instance.tools_config.get("tool_details", {})),
                "optimization_score": instance.dag_config.get("optimization_score", 0.0)
            },
            
            # 时间信息
            "created_at": instance.created_at.isoformat(),
            "last_used_at": instance.last_used_at.isoformat() if instance.last_used_at else None,
            
            # 元数据
            "metadata": instance.metadata
        }
    
    async def update_instance_config(
        self, 
        instance_id: str, 
        config_updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """更新智能体实例配置"""
        if instance_id not in self.active_instances:
            raise ValueError(f"智能体实例 {instance_id} 不存在")
        
        instance = self.active_instances[instance_id]
        
        try:
            # 更新智能体配置
            if "agent_config" in config_updates:
                agent_config_updates = config_updates["agent_config"]
                
                # 更新Agno智能体配置
                updated_config = AgentConfig(
                    name=agent_config_updates.get("name", instance.agent_config.name),
                    description=agent_config_updates.get("description", instance.agent_config.description),
                    instructions=agent_config_updates.get("instructions", instance.agent_config.instructions),
                    model_config=agent_config_updates.get("model_config", instance.agent_config.model_config),
                    tools=instance.agent_config.tools,  # 工具配置单独处理
                    knowledge_bases=agent_config_updates.get("knowledge_bases", instance.agent_config.knowledge_bases),
                    temperature=agent_config_updates.get("temperature", instance.agent_config.temperature),
                    max_tokens=agent_config_updates.get("max_tokens", instance.agent_config.max_tokens),
                    memory_enabled=agent_config_updates.get("memory_enabled", instance.agent_config.memory_enabled)
                )
                
                # 更新Agno智能体
                await self.agno_manager.update_agent(instance.agent_id, updated_config)
                instance.agent_config = updated_config
            
            # 更新工具配置
            if "tools_config" in config_updates:
                # 这里可以添加工具配置更新逻辑
                pass
            
            # 更新元数据
            if "metadata" in config_updates:
                instance.metadata.update(config_updates["metadata"])
            
            return {
                "success": True,
                "message": "智能体实例配置已更新",
                "instance_id": instance_id
            }
            
        except Exception as e:
            logger.error(f"更新智能体实例配置失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "instance_id": instance_id
            }
    
    async def deactivate_instance(self, instance_id: str) -> Dict[str, Any]:
        """停用智能体实例"""
        if instance_id not in self.active_instances:
            raise ValueError(f"智能体实例 {instance_id} 不存在")
        
        instance = self.active_instances[instance_id]
        
        try:
            # 删除Agno智能体
            await self.agno_manager.delete_agent(instance.agent_id)
            
            # 更新状态
            instance.status = "inactive"
            
            logger.info(f"智能体实例已停用: {instance_id}")
            
            return {
                "success": True,
                "message": "智能体实例已停用",
                "instance_id": instance_id
            }
            
        except Exception as e:
            logger.error(f"停用智能体实例失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "instance_id": instance_id
            }
    
    async def remove_instance(self, instance_id: str) -> Dict[str, Any]:
        """移除智能体实例"""
        if instance_id not in self.active_instances:
            raise ValueError(f"智能体实例 {instance_id} 不存在")
        
        try:
            # 先停用
            await self.deactivate_instance(instance_id)
            
            # 从管理器中移除
            del self.active_instances[instance_id]
            
            logger.info(f"智能体实例已移除: {instance_id}")
            
            return {
                "success": True,
                "message": "智能体实例已移除",
                "instance_id": instance_id
            }
            
        except Exception as e:
            logger.error(f"移除智能体实例失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "instance_id": instance_id
            }
    
    def list_instances(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出智能体实例"""
        instances = []
        
        for instance_id, instance in self.active_instances.items():
            if user_id and instance.user_id != user_id:
                continue
            
            instances.append({
                "instance_id": instance.instance_id,
                "agent_id": instance.agent_id,
                "dag_id": instance.dag_id,
                "user_id": instance.user_id,
                "status": instance.status,
                "health_status": instance.health_status,
                "agent_name": instance.agent_config.name,
                "total_executions": instance.total_executions,
                "success_rate": (
                    instance.successful_executions / instance.total_executions 
                    if instance.total_executions > 0 else 0.0
                ),
                "created_at": instance.created_at.isoformat(),
                "last_used_at": instance.last_used_at.isoformat() if instance.last_used_at else None
            })
        
        return instances
    
    def get_converter_statistics(self) -> Dict[str, Any]:
        """获取转换器统计信息"""
        total_instances = len(self.active_instances)
        active_instances = len([i for i in self.active_instances.values() if i.status == "active"])
        total_executions = sum(i.total_executions for i in self.active_instances.values())
        total_successful = sum(i.successful_executions for i in self.active_instances.values())
        
        return {
            "total_instances": total_instances,
            "active_instances": active_instances,
            "inactive_instances": total_instances - active_instances,
            "total_executions": total_executions,
            "total_successful_executions": total_successful,
            "overall_success_rate": (
                total_successful / total_executions if total_executions > 0 else 0.0
            ),
            "avg_executions_per_instance": (
                total_executions / total_instances if total_instances > 0 else 0.0
            )
        }

# 全局DAG到Agno转换器实例
dag_to_agno_converter = DAGToAgnoConverter() 