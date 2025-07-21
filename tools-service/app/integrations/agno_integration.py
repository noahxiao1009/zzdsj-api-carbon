"""
Agno框架工具集成
为Agno智能体提供工具调用接口
"""

import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.schemas.tool_schemas import ToolRequest, ToolResponse
from app.core.tool_manager import ToolManager
from app.core.logger import logger


class AgnoToolIntegration:
    """Agno框架工具集成器"""
    
    def __init__(self, tool_manager: ToolManager):
        self.tool_manager = tool_manager
        self.registered_tools = {}
    
    async def register_tool_for_agno(self, tool_name: str, agno_tool_config: Dict[str, Any]):
        """
        为Agno注册工具
        
        Args:
            tool_name: 工具名称 (websailor, scraperr)
            agno_tool_config: Agno工具配置
        """
        try:
            # 获取工具模式
            schema = await self.tool_manager.get_tool_schema(tool_name)
            if not schema:
                raise ValueError(f"工具 {tool_name} 不存在")
            
            # 转换为Agno工具定义
            agno_tool_def = self._convert_to_agno_tool(schema, agno_tool_config)
            
            # 注册工具
            self.registered_tools[tool_name] = agno_tool_def
            
            logger.info(f"工具 {tool_name} 已注册到Agno框架")
            return agno_tool_def
            
        except Exception as e:
            logger.error(f"注册Agno工具失败: {e}")
            raise
    
    def _convert_to_agno_tool(self, schema: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        """
        将工具模式转换为Agno工具定义
        """
        agno_tool = {
            "name": schema["name"],
            "description": schema["description"],
            "version": schema.get("version", "1.0.0"),
            "actions": {},
            "config": config
        }
        
        # 转换动作定义
        for action_name, action_def in schema.get("actions", {}).items():
            agno_tool["actions"][action_name] = {
                "name": action_name,
                "description": action_def.get("description", ""),
                "parameters": self._convert_parameters(action_def.get("parameters", {})),
                "handler": f"tools_service_{schema['name']}_{action_name}"
            }
        
        return agno_tool
    
    def _convert_parameters(self, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        转换参数定义为Agno格式
        """
        agno_params = []
        
        for param_name, param_def in parameters.items():
            agno_param = {
                "name": param_name,
                "type": param_def.get("type", "string"),
                "description": param_def.get("description", ""),
                "required": param_def.get("required", False)
            }
            
            if "default" in param_def:
                agno_param["default"] = param_def["default"]
            
            agno_params.append(agno_param)
        
        return agno_params
    
    async def execute_tool_from_agno(self, tool_name: str, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        从Agno框架执行工具调用
        
        Args:
            tool_name: 工具名称
            action: 动作名称
            parameters: 参数
            
        Returns:
            执行结果
        """
        try:
            # 创建工具请求
            request = ToolRequest(
                tool_name=tool_name,
                action=action,
                parameters=parameters
            )
            
            # 执行工具
            response = await self.tool_manager.execute_tool(request)
            
            # 转换响应格式
            agno_response = {
                "success": response.success,
                "data": response.data,
                "message": response.message,
                "execution_time": response.execution_time,
                "metadata": {
                    "tool": tool_name,
                    "action": action,
                    "timestamp": datetime.now().isoformat(),
                    **(response.metadata or {})
                }
            }
            
            logger.info(f"Agno工具调用成功: {tool_name}.{action}")
            return agno_response
            
        except Exception as e:
            logger.error(f"Agno工具调用失败: {e}")
            return {
                "success": False,
                "data": None,
                "message": str(e),
                "error": True
            }
    
    def get_agno_tool_definitions(self) -> List[Dict[str, Any]]:
        """
        获取所有注册的Agno工具定义
        """
        return list(self.registered_tools.values())
    
    def get_agno_tool_by_name(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        根据名称获取Agno工具定义
        """
        return self.registered_tools.get(tool_name)


# WebSailor Agno工具定义
WEBSAILOR_AGNO_CONFIG = {
    "category": "search",
    "tags": ["search", "web", "ai"],
    "requirements": {
        "google_search_key": "Google Search API密钥",
        "jina_api_keys": "Jina API密钥列表"
    },
    "examples": [
        {
            "action": "search",
            "parameters": {
                "query": "人工智能最新发展"
            },
            "description": "搜索人工智能相关信息"
        },
        {
            "action": "visit",
            "parameters": {
                "url": "https://example.com/article",
                "goal": "提取文章标题和正文"
            },
            "description": "访问网页并提取特定内容"
        }
    ]
}

# Scraperr Agno工具定义
SCRAPERR_AGNO_CONFIG = {
    "category": "data_extraction",
    "tags": ["scraping", "data", "xpath"],
    "requirements": {
        "database": "数据库连接"
    },
    "examples": [
        {
            "action": "scrape",
            "parameters": {
                "url": "https://example.com",
                "elements": [
                    {"name": "title", "xpath": "//title"},
                    {"name": "content", "xpath": "//p"}
                ]
            },
            "description": "爬取网页指定元素"
        },
        {
            "action": "list_jobs",
            "parameters": {
                "limit": 10
            },
            "description": "获取爬取任务列表"
        }
    ]
}


async def setup_agno_integration(tool_manager: ToolManager) -> AgnoToolIntegration:
    """
    设置Agno集成
    """
    integration = AgnoToolIntegration(tool_manager)
    
    try:
        # 注册WebSailor工具
        await integration.register_tool_for_agno("websailor", WEBSAILOR_AGNO_CONFIG)
        
        # 注册Scraperr工具
        await integration.register_tool_for_agno("scraperr", SCRAPERR_AGNO_CONFIG)
        
        logger.info("Agno工具集成设置完成")
        return integration
        
    except Exception as e:
        logger.error(f"Agno集成设置失败: {e}")
        raise


# Agno工具调用处理器
class AgnoToolHandler:
    """Agno工具调用处理器"""
    
    def __init__(self, integration: AgnoToolIntegration):
        self.integration = integration
    
    async def handle_tool_call(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理来自Agno的工具调用
        """
        try:
            tool_name = tool_call.get("tool")
            action = tool_call.get("action")
            parameters = tool_call.get("parameters", {})
            
            if not tool_name or not action:
                raise ValueError("工具调用缺少必要参数")
            
            # 执行工具调用
            result = await self.integration.execute_tool_from_agno(
                tool_name, action, parameters
            )
            
            return result
            
        except Exception as e:
            logger.error(f"处理Agno工具调用失败: {e}")
            return {
                "success": False,
                "data": None,
                "message": f"工具调用失败: {str(e)}",
                "error": True
            }
    
    async def batch_handle_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量处理工具调用
        """
        tasks = [self.handle_tool_call(call) for call in tool_calls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常结果
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                processed_results.append({
                    "success": False,
                    "data": None,
                    "message": f"批量调用异常: {str(result)}",
                    "error": True
                })
            else:
                processed_results.append(result)
        
        return processed_results