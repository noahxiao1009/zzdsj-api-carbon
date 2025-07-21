"""
LlamaIndex工具集成
为LlamaIndex提供自定义工具接口
"""

import asyncio
import json
from typing import Dict, Any, List, Optional, Type, Callable
from datetime import datetime

from app.schemas.tool_schemas import ToolRequest, ToolResponse
from app.core.tool_manager import ToolManager
from app.core.logger import logger

try:
    from llama_index.core.tools import BaseTool, ToolMetadata
    from llama_index.core.tools.function_tool import FunctionTool
    from pydantic import BaseModel, Field
    LLAMAINDEX_AVAILABLE = True
except ImportError:
    logger.warning("LlamaIndex未安装，跳过集成")
    LLAMAINDEX_AVAILABLE = False
    
    # 创建占位符类
    class BaseTool:
        pass
    class ToolMetadata:
        pass
    class FunctionTool:
        pass
    class BaseModel:
        pass
    def Field(*args, **kwargs):
        pass


class LlamaIndexToolIntegration:
    """LlamaIndex工具集成器"""
    
    def __init__(self, tool_manager: ToolManager):
        self.tool_manager = tool_manager
        self.registered_tools = {}
        self.function_tools = {}
    
    async def create_llamaindex_tool(self, tool_name: str, action: str) -> Optional[BaseTool]:
        """
        为指定工具动作创建LlamaIndex工具
        
        Args:
            tool_name: 工具名称
            action: 动作名称
            
        Returns:
            LlamaIndex工具实例
        """
        if not LLAMAINDEX_AVAILABLE:
            logger.warning("LlamaIndex不可用，无法创建工具")
            return None
        
        try:
            # 获取工具模式
            schema = await self.tool_manager.get_tool_schema(tool_name)
            if not schema:
                raise ValueError(f"工具 {tool_name} 不存在")
            
            action_def = schema.get("actions", {}).get(action)
            if not action_def:
                raise ValueError(f"动作 {action} 不存在于工具 {tool_name}")
            
            # 创建工具函数
            tool_func = self._create_tool_function(tool_name, action, action_def)
            
            # 创建LlamaIndex工具
            tool_metadata = ToolMetadata(
                name=f"{tool_name}_{action}",
                description=action_def.get("description", f"{tool_name} {action} 工具"),
            )
            
            llamaindex_tool = FunctionTool.from_defaults(
                fn=tool_func,
                name=tool_metadata.name,
                description=tool_metadata.description,
            )
            
            # 注册工具
            tool_key = f"{tool_name}_{action}"
            self.registered_tools[tool_key] = llamaindex_tool
            
            logger.info(f"LlamaIndex工具已创建: {tool_key}")
            return llamaindex_tool
            
        except Exception as e:
            logger.error(f"创建LlamaIndex工具失败: {e}")
            raise
    
    def _create_tool_function(self, tool_name: str, action: str, action_def: Dict[str, Any]) -> Callable:
        """
        创建工具函数
        """
        async def tool_function(**kwargs) -> str:
            """动态生成的工具函数"""
            try:
                # 过滤参数
                parameters = {}
                for param_name, param_def in action_def.get("parameters", {}).items():
                    if param_name in kwargs:
                        parameters[param_name] = kwargs[param_name]
                    elif param_def.get("required", False):
                        raise ValueError(f"缺少必需参数: {param_name}")
                
                # 创建工具请求
                request = ToolRequest(
                    tool_name=tool_name,
                    action=action,
                    parameters=parameters
                )
                
                # 执行工具
                response = await self.tool_manager.execute_tool(request)
                
                if response.success:
                    # 将结果转换为字符串格式
                    if isinstance(response.data, dict):
                        return json.dumps(response.data, ensure_ascii=False, indent=2)
                    elif isinstance(response.data, str):
                        return response.data
                    else:
                        return str(response.data)
                else:
                    return f"工具执行失败: {response.message}"
                    
            except Exception as e:
                logger.error(f"LlamaIndex工具函数执行失败: {e}")
                return f"工具执行异常: {str(e)}"
        
        # 设置函数元数据
        tool_function.__name__ = f"{tool_name}_{action}"
        tool_function.__doc__ = action_def.get("description", f"Execute {tool_name} {action}")
        
        return tool_function
    
    async def create_all_tools(self) -> List[BaseTool]:
        """
        为所有可用工具创建LlamaIndex工具
        """
        if not LLAMAINDEX_AVAILABLE:
            logger.warning("LlamaIndex不可用，无法创建工具")
            return []
        
        tools = []
        
        try:
            # 获取所有工具
            tool_list = await self.tool_manager.list_tools()
            
            for tool_info in tool_list:
                tool_name = tool_info.name
                schema = tool_info.schema
                
                # 为每个动作创建工具
                for action_name in schema.get("actions", {}):
                    tool = await self.create_llamaindex_tool(tool_name, action_name)
                    if tool:
                        tools.append(tool)
            
            logger.info(f"已创建 {len(tools)} 个LlamaIndex工具")
            return tools
            
        except Exception as e:
            logger.error(f"创建LlamaIndex工具列表失败: {e}")
            return []
    
    def get_tool_by_name(self, tool_name: str) -> Optional[BaseTool]:
        """
        根据名称获取工具
        """
        return self.registered_tools.get(tool_name)
    
    def get_all_tools(self) -> List[BaseTool]:
        """
        获取所有注册的工具
        """
        return list(self.registered_tools.values())
    
    async def create_websailor_tools(self) -> List[BaseTool]:
        """
        创建WebSailor专用工具
        """
        tools = []
        
        try:
            # 搜索工具
            search_tool = await self.create_llamaindex_tool("websailor", "search")
            if search_tool:
                tools.append(search_tool)
            
            # 访问工具
            visit_tool = await self.create_llamaindex_tool("websailor", "visit")
            if visit_tool:
                tools.append(visit_tool)
            
            logger.info("WebSailor LlamaIndex工具创建完成")
            return tools
            
        except Exception as e:
            logger.error(f"创建WebSailor工具失败: {e}")
            return []
    
    async def create_scraperr_tools(self) -> List[BaseTool]:
        """
        创建Scraperr专用工具
        """
        tools = []
        
        try:
            # 爬取工具
            scrape_tool = await self.create_llamaindex_tool("scraperr", "scrape")
            if scrape_tool:
                tools.append(scrape_tool)
            
            # 任务列表工具
            list_jobs_tool = await self.create_llamaindex_tool("scraperr", "list_jobs")
            if list_jobs_tool:
                tools.append(list_jobs_tool)
            
            # 任务详情工具
            get_job_tool = await self.create_llamaindex_tool("scraperr", "get_job")
            if get_job_tool:
                tools.append(get_job_tool)
            
            logger.info("Scraperr LlamaIndex工具创建完成")
            return tools
            
        except Exception as e:
            logger.error(f"创建Scraperr工具失败: {e}")
            return []


class LlamaIndexCustomTool(BaseTool):
    """
    自定义LlamaIndex工具基类
    """
    
    def __init__(
        self,
        tool_manager: ToolManager,
        tool_name: str,
        action: str,
        metadata: ToolMetadata
    ):
        self.tool_manager = tool_manager
        self.tool_name = tool_name
        self.action = action
        super().__init__(metadata=metadata)
    
    async def acall(self, **kwargs) -> str:
        """
        异步调用工具
        """
        try:
            # 创建工具请求
            request = ToolRequest(
                tool_name=self.tool_name,
                action=self.action,
                parameters=kwargs
            )
            
            # 执行工具
            response = await self.tool_manager.execute_tool(request)
            
            if response.success:
                if isinstance(response.data, dict):
                    return json.dumps(response.data, ensure_ascii=False, indent=2)
                elif isinstance(response.data, str):
                    return response.data
                else:
                    return str(response.data)
            else:
                return f"工具执行失败: {response.message}"
                
        except Exception as e:
            logger.error(f"LlamaIndex自定义工具执行失败: {e}")
            return f"工具执行异常: {str(e)}"
    
    def call(self, **kwargs) -> str:
        """
        同步调用工具（通过事件循环）
        """
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.acall(**kwargs))
        except Exception as e:
            logger.error(f"同步调用工具失败: {e}")
            return f"工具调用失败: {str(e)}"


async def setup_llamaindex_integration(tool_manager: ToolManager) -> LlamaIndexToolIntegration:
    """
    设置LlamaIndex集成
    """
    if not LLAMAINDEX_AVAILABLE:
        logger.warning("LlamaIndex不可用，跳过集成设置")
        return LlamaIndexToolIntegration(tool_manager)
    
    integration = LlamaIndexToolIntegration(tool_manager)
    
    try:
        # 创建所有工具
        await integration.create_all_tools()
        
        logger.info("LlamaIndex工具集成设置完成")
        return integration
        
    except Exception as e:
        logger.error(f"LlamaIndex集成设置失败: {e}")
        raise


# 便捷函数
async def get_websailor_llamaindex_tools(tool_manager: ToolManager) -> List[BaseTool]:
    """
    获取WebSailor的LlamaIndex工具
    """
    integration = LlamaIndexToolIntegration(tool_manager)
    return await integration.create_websailor_tools()


async def get_scraperr_llamaindex_tools(tool_manager: ToolManager) -> List[BaseTool]:
    """
    获取Scraperr的LlamaIndex工具
    """
    integration = LlamaIndexToolIntegration(tool_manager)
    return await integration.create_scraperr_tools()


async def get_all_llamaindex_tools(tool_manager: ToolManager) -> List[BaseTool]:
    """
    获取所有工具的LlamaIndex版本
    """
    integration = LlamaIndexToolIntegration(tool_manager)
    return await integration.create_all_tools()