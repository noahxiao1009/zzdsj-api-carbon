"""
智能体服务层
集成统一ServiceClient SDK，提供完整的智能体管理功能
"""

import logging
import uuid
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import sys
import os

# 添加shared模块到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), "../../../shared"))

from service_client import (
    ServiceClient, 
    AsyncServiceClient,
    CallMethod, 
    CallConfig, 
    RetryStrategy,
    ServiceCallError
)
from .service_integration import AgentServiceIntegration

logger = logging.getLogger(__name__)


class AgentService:
    """
    智能体服务 - 使用统一ServiceClient SDK
    提供智能体的创建、管理、配置和对话功能
    """
    
    def __init__(self):
        self.integration = None
        self._initialized = False
    
    async def initialize(self):
        """初始化服务"""
        if not self._initialized:
            self.integration = AgentServiceIntegration()
            await self.integration.__aenter__()
            self._initialized = True
            logger.info("AgentService 初始化完成")
    
    async def cleanup(self):
        """清理资源"""
        if self.integration and self._initialized:
            await self.integration.__aexit__(None, None, None)
            self._initialized = False
            logger.info("AgentService 资源清理完成")
    
    # ==================== 智能体CRUD操作 ====================
    
    async def create_agent(self, config: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        创建智能体
        支持基于模板的快速创建和自定义配置
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            logger.info(f"用户 {user_id} 创建智能体")
            
            # 生成智能体ID
            agent_id = str(uuid.uuid4())
            
            # 验证用户权限
            has_permission = await self.integration.check_agent_permission(
                user_id=user_id,
                agent_id=agent_id,
                action="create"
            )
            
            if not has_permission:
                raise ValueError("没有创建智能体的权限")
            
            # 准备智能体配置
            agent_config = {
                "agent_id": agent_id,
                "name": config.get("name", f"智能体_{agent_id[:8]}"),
                "description": config.get("description", ""),
                "template_id": config.get("template_id", "basic_conversation"),
                "system_prompt": config.get("system_prompt", "你是一个有用的AI助手。"),
                "model_config": config.get("model_config", {
                    "model": "gpt-3.5-turbo",
                    "provider": "openai",
                    "temperature": 0.7,
                    "max_tokens": 1000
                }),
                "knowledge_enabled": config.get("knowledge_enabled", False),
                "knowledge_base_ids": config.get("knowledge_base_ids", []),
                "tools": config.get("tools", []),
                "status": "active",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            # 保存智能体配置
            result = await self.integration.save_agent_config(
                agent_id=agent_id,
                config=agent_config,
                user_id=user_id
            )
            
            logger.info(f"智能体 {agent_id} 创建成功")
            
            return {
                "agent_id": agent_id,
                "name": agent_config["name"],
                "description": agent_config["description"],
                "template_id": agent_config["template_id"],
                "status": agent_config["status"],
                "created_at": agent_config["created_at"],
                "model": agent_config["model_config"]["model"],
                "provider": agent_config["model_config"]["provider"]
            }
            
        except Exception as e:
            logger.error(f"创建智能体失败: {e}")
            raise
    
    async def get_agent(self, agent_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """获取智能体详情"""
        if not self._initialized:
            await self.initialize()
        
        try:
            # 检查权限
            has_permission = await self.integration.check_agent_permission(
                user_id=user_id,
                agent_id=agent_id,
                action="read"
            )
            
            if not has_permission:
                return None
            
            # 获取智能体配置
            agent_config = await self.integration.get_agent_config(agent_id)
            
            if not agent_config:
                return None
            
            return agent_config
            
        except Exception as e:
            logger.error(f"获取智能体详情失败: {e}")
            raise
    
    async def update_agent(self, agent_id: str, config: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """更新智能体配置"""
        if not self._initialized:
            await self.initialize()
        
        try:
            # 检查权限
            has_permission = await self.integration.check_agent_permission(
                user_id=user_id,
                agent_id=agent_id,
                action="update"
            )
            
            if not has_permission:
                raise ValueError("没有更新智能体的权限")
            
            # 获取现有配置
            existing_config = await self.integration.get_agent_config(agent_id)
            if not existing_config:
                raise ValueError(f"智能体 {agent_id} 不存在")
            
            # 合并配置
            updated_config = existing_config.copy()
            updated_config.update(config)
            updated_config["updated_at"] = datetime.now().isoformat()
            
            # 保存更新后的配置
            result = await self.integration.update_agent_config(agent_id, updated_config)
            
            logger.info(f"智能体 {agent_id} 更新成功")
            
            return result
            
        except Exception as e:
            logger.error(f"更新智能体失败: {e}")
            raise
    
    async def delete_agent(self, agent_id: str, user_id: str) -> bool:
        """删除智能体"""
        if not self._initialized:
            await self.initialize()
        
        try:
            # 检查权限
            has_permission = await self.integration.check_agent_permission(
                user_id=user_id,
                agent_id=agent_id,
                action="delete"
            )
            
            if not has_permission:
                raise ValueError("没有删除智能体的权限")
            
            # 标记为已删除（软删除）
            update_config = {
                "status": "deleted",
                "deleted_at": datetime.now().isoformat()
            }
            
            await self.integration.update_agent_config(agent_id, update_config)
            
            logger.info(f"智能体 {agent_id} 删除成功")
            
            return True
            
        except Exception as e:
            logger.error(f"删除智能体失败: {e}")
            raise
    
    async def get_agents(
        self, 
        user_id: str, 
        page: int = 1, 
        page_size: int = 20,
        search: Optional[str] = None,
        status_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取智能体列表"""
        if not self._initialized:
            await self.initialize()
        
        try:
            # TODO: 这里需要调用database-service获取用户的智能体列表
            # 目前返回模拟数据，后续需要实现完整的查询逻辑
            
            agents = [
                {
                    "agent_id": "agent_001",
                    "name": "客服助手",
                    "description": "处理客户咨询的智能助手",
                    "template_id": "simple-qa",
                    "status": "active",
                    "created_at": "2024-01-15T10:00:00Z",
                    "updated_at": "2024-01-15T10:00:00Z",
                    "model": "gpt-3.5-turbo",
                    "provider": "openai"
                }
            ]
            
            # 应用筛选
            if search:
                agents = [a for a in agents if search.lower() in a["name"].lower()]
            
            if status_filter:
                agents = [a for a in agents if a["status"] == status_filter]
            
            # 分页
            total = len(agents)
            start = (page - 1) * page_size
            end = start + page_size
            agents_page = agents[start:end]
            
            return {
                "agents": agents_page,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size
            }
            
        except Exception as e:
            logger.error(f"获取智能体列表失败: {e}")
            raise
    
    # ==================== 智能体对话功能 ====================
    
    async def chat(
        self, 
        agent_id: str, 
        message: str, 
        session_id: str,
        user_id: str,
        context: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """与智能体对话"""
        if not self._initialized:
            await self.initialize()
        
        try:
            logger.info(f"智能体对话: {agent_id} - {message[:50]}...")
            
            # 使用集成模块处理对话
            result = await self.integration.process_agent_chat(
                agent_id=agent_id,
                message=message,
                session_id=session_id,
                user_id=user_id,
                history=history
            )
            
            return result
            
        except Exception as e:
            logger.error(f"智能体对话失败: {e}")
            raise
    
    async def chat_stream(
        self, 
        agent_id: str, 
        message: str, 
        session_id: str,
        user_id: str,
        context: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, str]]] = None
    ):
        """流式对话（生成器）"""
        if not self._initialized:
            await self.initialize()
        
        try:
            logger.info(f"智能体流式对话: {agent_id} - {message[:50]}...")
            
            # TODO: 实现流式对话逻辑
            # 目前返回简单的模拟流式响应
            response_chunks = [
                "这是", "一个", "流式", "响应", "的", "示例", "。"
            ]
            
            for chunk in response_chunks:
                yield {
                    "content": chunk,
                    "delta": chunk,
                    "session_id": session_id,
                    "agent_id": agent_id,
                    "finished": False
                }
                await asyncio.sleep(0.1)  # 模拟流式延迟
            
            # 最后一个chunk
            yield {
                "content": "这是一个流式响应的示例。",
                "delta": "",
                "session_id": session_id,
                "agent_id": agent_id,
                "finished": True
            }
            
        except Exception as e:
            logger.error(f"智能体流式对话失败: {e}")
            raise
    
    # ==================== 智能体配置和管理 ====================
    
    async def validate_agent_config(self, config: Dict[str, Any]) -> bool:
        """验证智能体配置"""
        try:
            # 基础验证
            required_fields = ["name"]
            for field in required_fields:
                if field not in config or not config[field]:
                    raise ValueError(f"缺少必需字段: {field}")
            
            # 模型配置验证
            if "model_config" in config:
                model_config = config["model_config"]
                if "model" not in model_config:
                    raise ValueError("模型配置中缺少model字段")
            
            return True
            
        except Exception as e:
            logger.error(f"配置验证失败: {e}")
            raise
    
    async def get_agent_config(self, agent_id: str, user_id: str) -> Dict[str, Any]:
        """获取智能体详细配置"""
        if not self._initialized:
            await self.initialize()
        
        try:
            agent_config = await self.get_agent(agent_id, user_id)
            
            if not agent_config:
                raise ValueError(f"智能体 {agent_id} 不存在")
            
            return {
                "agent_id": agent_id,
                "basic_config": {
                    "name": agent_config.get("name"),
                    "description": agent_config.get("description"),
                    "system_prompt": agent_config.get("system_prompt")
                },
                "model_config": agent_config.get("model_config", {}),
                "knowledge_config": {
                    "enabled": agent_config.get("knowledge_enabled", False),
                    "knowledge_base_ids": agent_config.get("knowledge_base_ids", [])
                },
                "tool_config": {
                    "tools": agent_config.get("tools", [])
                },
                "advanced_config": {
                    "template_id": agent_config.get("template_id"),
                    "status": agent_config.get("status")
                }
            }
            
        except Exception as e:
            logger.error(f"获取智能体配置失败: {e}")
            raise
    
    async def initialize_agent(self, agent_id: str):
        """初始化智能体（后台任务）"""
        try:
            logger.info(f"开始初始化智能体: {agent_id}")
            
            # 模拟初始化过程
            await asyncio.sleep(2)
            
            # 更新状态为已初始化
            update_config = {
                "status": "initialized",
                "initialized_at": datetime.now().isoformat()
            }
            
            await self.integration.update_agent_config(agent_id, update_config)
            
            logger.info(f"智能体 {agent_id} 初始化完成")
            
        except Exception as e:
            logger.error(f"智能体初始化失败: {e}")
    
    # ==================== 智能体统计和监控 ====================
    
    async def get_agent_stats(self, agent_id: str, period: str, user_id: str) -> Dict[str, Any]:
        """获取智能体使用统计"""
        if not self._initialized:
            await self.initialize()
        
        try:
            # 检查权限
            has_permission = await self.integration.check_agent_permission(
                user_id=user_id,
                agent_id=agent_id,
                action="stats"
            )
            
            if not has_permission:
                raise ValueError("没有查看统计信息的权限")
            
            # TODO: 从数据库获取实际统计数据
            # 目前返回模拟数据
            stats = {
                "agent_id": agent_id,
                "period": period,
                "chat_count": 156,
                "total_tokens": 45230,
                "avg_response_time": 0.85,
                "user_satisfaction": 4.5,
                "error_rate": 0.02,
                "top_topics": [
                    {"topic": "产品咨询", "count": 45},
                    {"topic": "技术支持", "count": 32},
                    {"topic": "退款问题", "count": 28}
                ],
                "daily_usage": [
                    {"date": "2024-01-15", "count": 23},
                    {"date": "2024-01-16", "count": 31},
                    {"date": "2024-01-17", "count": 28}
                ]
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"获取智能体统计失败: {e}")
            raise
    
    async def test_agent(self, agent_id: str, test_message: str, user_id: str) -> Dict[str, Any]:
        """测试智能体"""
        if not self._initialized:
            await self.initialize()
        
        try:
            logger.info(f"测试智能体: {agent_id}")
            
            # 使用特殊的测试会话ID
            test_session_id = f"test_session_{uuid.uuid4()}"
            
            # 调用对话功能
            start_time = datetime.now()
            
            result = await self.chat(
                agent_id=agent_id,
                message=test_message,
                session_id=test_session_id,
                user_id=user_id
            )
            
            end_time = datetime.now()
            response_time = (end_time - start_time).total_seconds()
            
            return {
                "agent_id": agent_id,
                "test_message": test_message,
                "response": result.get("response", ""),
                "response_time": response_time,
                "status": "success" if result.get("response") else "failed",
                "metadata": result.get("metadata", {}),
                "timestamp": end_time.isoformat()
            }
            
        except Exception as e:
            logger.error(f"测试智能体失败: {e}")
            return {
                "agent_id": agent_id,
                "test_message": test_message,
                "response": "",
                "response_time": 0,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def change_agent_status(self, agent_id: str, action: str, user_id: str) -> Dict[str, Any]:
        """更改智能体状态"""
        if not self._initialized:
            await self.initialize()
        
        try:
            # 检查权限
            has_permission = await self.integration.check_agent_permission(
                user_id=user_id,
                agent_id=agent_id,
                action="manage"
            )
            
            if not has_permission:
                raise ValueError("没有管理智能体的权限")
            
            # 状态映射
            status_map = {
                "activate": "active",
                "deactivate": "inactive",
                "pause": "paused",
                "resume": "active"
            }
            
            if action not in status_map:
                raise ValueError(f"无效的操作: {action}")
            
            new_status = status_map[action]
            
            # 更新状态
            update_config = {
                "status": new_status,
                "status_updated_at": datetime.now().isoformat()
            }
            
            await self.integration.update_agent_config(agent_id, update_config)
            
            logger.info(f"智能体 {agent_id} 状态更新为: {new_status}")
            
            return {
                "agent_id": agent_id,
                "action": action,
                "new_status": new_status,
                "timestamp": update_config["status_updated_at"]
            }
            
        except Exception as e:
            logger.error(f"更改智能体状态失败: {e}")
            raise
    
    # ==================== 批量操作 ====================
    
    async def batch_create_agents(self, agent_configs: List[Dict[str, Any]], user_id: str) -> Dict[str, Any]:
        """批量创建智能体"""
        if not self._initialized:
            await self.initialize()
        
        try:
            logger.info(f"批量创建 {len(agent_configs)} 个智能体")
            
            # 为每个配置生成agent_id
            for config in agent_configs:
                if "agent_id" not in config:
                    config["agent_id"] = str(uuid.uuid4())
            
            # 使用集成模块的批量创建功能
            result = await self.integration.batch_create_agents(agent_configs, user_id)
            
            return result
            
        except Exception as e:
            logger.error(f"批量创建智能体失败: {e}")
            raise
    
    # ==================== 健康检查和监控 ====================
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        if not self._initialized:
            await self.initialize()
        
        try:
            # 检查所有依赖服务
            dependency_health = await self.integration.health_check_dependencies()
            
            # 检查本服务状态
            service_health = {
                "agent-service": True,
                "initialized": self._initialized,
                "timestamp": datetime.now().isoformat()
            }
            
            # 合并健康状态
            all_health = {**service_health, **dependency_health}
            
            # 计算整体健康状态
            overall_healthy = all(all_health.values())
            
            return {
                "healthy": overall_healthy,
                "services": all_health,
                "timestamp": service_health["timestamp"]
            }
            
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return {
                "healthy": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def get_metrics(self) -> Dict[str, Any]:
        """获取服务指标"""
        if not self._initialized:
            await self.initialize()
        
        try:
            # 获取服务调用指标
            service_metrics = await self.integration.get_service_metrics()
            
            return {
                "agent_service_metrics": service_metrics,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取服务指标失败: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
