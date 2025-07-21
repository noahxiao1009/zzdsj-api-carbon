"""
集成服务 - 负责与其他微服务的通信和网关注册
"""

import logging
import aiohttp
from typing import Dict, Any, Optional
import asyncio
import os


logger = logging.getLogger(__name__)


class IntegrationService:
    """集成服务 - 处理服务间通信"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.gateway_url = os.getenv("GATEWAY_URL", "http://localhost:8000")
        self.model_service_url = os.getenv("MODEL_SERVICE_URL", "http://localhost:8002")
        self.base_service_url = os.getenv("BASE_SERVICE_URL", "http://localhost:8001")
        
    async def initialize(self):
        """初始化服务"""
        self.session = aiohttp.ClientSession()
        logger.info("集成服务已初始化")
    
    async def cleanup(self):
        """清理资源"""
        if self.session:
            await self.session.close()
        logger.info("集成服务已清理")
    
    async def register_with_gateway(self, service_info: Dict[str, Any]) -> bool:
        """向网关注册服务"""
        try:
            if not self.session:
                await self.initialize()
            
            registration_url = f"{self.gateway_url}/api/services/register"
            
            async with self.session.post(registration_url, json=service_info) as response:
                if response.status == 200:
                    logger.info(f"✅ 成功注册到网关: {service_info['service_name']}")
                    return True
                else:
                    logger.warning(f"⚠️ 网关注册失败: {response.status}")
                    return False
                    
        except Exception as e:
            logger.warning(f"⚠️ 网关注册异常: {str(e)}")
            return False
    
    async def get_llm_models(self) -> Dict[str, Any]:
        """从模型服务获取LLM配置"""
        try:
            if not self.session:
                await self.initialize()
            
            models_url = f"{self.model_service_url}/api/v1/models"
            
            async with self.session.get(models_url) as response:
                if response.status == 200:
                    models = await response.json()
                    logger.info("✅ 成功获取LLM模型配置")
                    return models
                else:
                    logger.warning(f"⚠️ 获取模型配置失败: {response.status}")
                    return {}
                    
        except Exception as e:
            logger.warning(f"⚠️ 获取模型配置异常: {str(e)}")
            return {}
    
    async def validate_user_permission(self, user_id: str, resource: str, action: str) -> bool:
        """从基础服务验证用户权限"""
        try:
            if not self.session:
                await self.initialize()
            
            permission_url = f"{self.base_service_url}/api/v1/auth/permission"
            payload = {
                "user_id": user_id,
                "resource": resource,
                "action": action
            }
            
            async with self.session.post(permission_url, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("allowed", False)
                else:
                    logger.warning(f"⚠️ 权限验证失败: {response.status}")
                    return False
                    
        except Exception as e:
            logger.warning(f"⚠️ 权限验证异常: {str(e)}")
            return False
    
    async def notify_workflow_event(self, event_data: Dict[str, Any]) -> bool:
        """通知其他服务工作流事件"""
        try:
            if not self.session:
                await self.initialize()
            
            notification_url = f"{self.gateway_url}/api/events/notify"
            
            async with self.session.post(notification_url, json=event_data) as response:
                return response.status == 200
                
        except Exception as e:
            logger.warning(f"⚠️ 事件通知异常: {str(e)}")
            return False
    
    async def call_external_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """调用外部工具服务"""
        try:
            if not self.session:
                await self.initialize()
            
            tool_url = f"{self.gateway_url}/api/tools/{tool_name}/invoke"
            
            async with self.session.post(tool_url, json=parameters) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"error": f"Tool call failed: {response.status}"}
                    
        except Exception as e:
            logger.warning(f"⚠️ 工具调用异常: {str(e)}")
            return {"error": str(e)} 