"""
FastMCP服务器管理模块 - V2版本
基于FastMCP框架V2实现统一的MCP服务管理
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
import json

from app.core.config import settings

logger = logging.getLogger(__name__)

# FastMCP V2接口模拟实现（基于官方文档设计）
@dataclass
class MCPTool:
    """MCP工具定义"""
    name: str
    description: str
    parameters: Dict[str, Any]
    function: Callable
    category: str = "general"
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class MCPResource:
    """MCP资源定义"""
    uri: str
    description: str
    function: Callable
    category: str = "general"
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class MCPPrompt:
    """MCP提示定义"""
    name: str
    description: str
    function: Callable
    category: str = "general"
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


class FastMCPServer:
    """FastMCP服务器 V2实现"""
    
    def __init__(self, name: str, description: str = None, version: str = "2.0.0"):
        """
        初始化FastMCP服务器
        
        参数:
            name: 服务器名称
            description: 服务器描述
            version: 服务器版本
        """
        self.name = name
        self.description = description or f"{name} - FastMCP V2服务器"
        self.version = version
        
        # 注册表
        self.tool_registry: Dict[str, MCPTool] = {}
        self.resource_registry: Dict[str, MCPResource] = {}
        self.prompt_registry: Dict[str, MCPPrompt] = {}
        
        # 服务器状态
        self.is_running = False
        self.start_time = None
        
        logger.info(f"FastMCP服务器已创建: {name} v{version}")
    
    def tool(self, name: str = None, description: str = None, 
             category: str = "general", tags: List[str] = None):
        """
        工具注册装饰器
        
        参数:
            name: 工具名称
            description: 工具描述
            category: 工具类别
            tags: 工具标签
        """
        def decorator(func: Callable) -> Callable:
            tool_name = name or func.__name__
            tool_description = description or func.__doc__ or f"{tool_name} MCP工具"
            tool_tags = tags or []
            
            # 从函数签名生成参数模式
            import inspect
            sig = inspect.signature(func)
            parameters = {}
            
            for param_name, param in sig.parameters.items():
                param_info = {
                    "type": "string",  # 默认类型
                    "description": f"参数 {param_name}"
                }
                
                # 根据类型注解设置参数类型
                if param.annotation != inspect.Parameter.empty:
                    if param.annotation == int:
                        param_info["type"] = "integer"
                    elif param.annotation == float:
                        param_info["type"] = "number"
                    elif param.annotation == bool:
                        param_info["type"] = "boolean"
                    elif param.annotation == list:
                        param_info["type"] = "array"
                    elif param.annotation == dict:
                        param_info["type"] = "object"
                
                # 设置默认值
                if param.default != inspect.Parameter.empty:
                    param_info["default"] = param.default
                
                parameters[param_name] = param_info
            
            # 创建工具实例
            tool = MCPTool(
                name=tool_name,
                description=tool_description,
                parameters=parameters,
                function=func,
                category=category,
                tags=tool_tags
            )
            
            # 注册工具
            self.tool_registry[tool_name] = tool
            logger.info(f"注册MCP工具: {tool_name}")
            
            return func
        
        return decorator
    
    def resource(self, uri: str, description: str = None, 
                 category: str = "general", tags: List[str] = None):
        """
        资源注册装饰器
        
        参数:
            uri: 资源URI
            description: 资源描述
            category: 资源类别
            tags: 资源标签
        """
        def decorator(func: Callable) -> Callable:
            resource_description = description or func.__doc__ or f"{uri} MCP资源"
            resource_tags = tags or []
            
            # 创建资源实例
            resource = MCPResource(
                uri=uri,
                description=resource_description,
                function=func,
                category=category,
                tags=resource_tags
            )
            
            # 注册资源
            self.resource_registry[uri] = resource
            logger.info(f"注册MCP资源: {uri}")
            
            return func
        
        return decorator
    
    def prompt(self, name: str = None, description: str = None,
               category: str = "general", tags: List[str] = None):
        """
        提示注册装饰器
        
        参数:
            name: 提示名称
            description: 提示描述
            category: 提示类别
            tags: 提示标签
        """
        def decorator(func: Callable) -> Callable:
            prompt_name = name or func.__name__
            prompt_description = description or func.__doc__ or f"{prompt_name} MCP提示"
            prompt_tags = tags or []
            
            # 创建提示实例
            prompt = MCPPrompt(
                name=prompt_name,
                description=prompt_description,
                function=func,
                category=category,
                tags=prompt_tags
            )
            
            # 注册提示
            self.prompt_registry[prompt_name] = prompt
            logger.info(f"注册MCP提示: {prompt_name}")
            
            return func
        
        return decorator
    
    async def call_tool(self, tool_name: str, parameters: Dict[str, Any] = None) -> Any:
        """
        调用工具
        
        参数:
            tool_name: 工具名称
            parameters: 工具参数
            
        返回:
            工具执行结果
        """
        if tool_name not in self.tool_registry:
            raise ValueError(f"工具不存在: {tool_name}")
        
        tool = self.tool_registry[tool_name]
        params = parameters or {}
        
        try:
            # 调用工具函数
            if asyncio.iscoroutinefunction(tool.function):
                result = await tool.function(**params)
            else:
                result = tool.function(**params)
            
            logger.info(f"工具调用成功: {tool_name}")
            return result
            
        except Exception as e:
            logger.error(f"工具调用失败 {tool_name}: {e}")
            raise
    
    async def get_resource(self, uri: str, parameters: Dict[str, Any] = None) -> Any:
        """
        获取资源
        
        参数:
            uri: 资源URI
            parameters: 资源参数
            
        返回:
            资源内容
        """
        if uri not in self.resource_registry:
            raise ValueError(f"资源不存在: {uri}")
        
        resource = self.resource_registry[uri]
        params = parameters or {}
        
        try:
            # 调用资源函数
            if asyncio.iscoroutinefunction(resource.function):
                result = await resource.function(**params)
            else:
                result = resource.function(**params)
            
            logger.info(f"资源获取成功: {uri}")
            return result
            
        except Exception as e:
            logger.error(f"资源获取失败 {uri}: {e}")
            raise
    
    async def get_prompt(self, prompt_name: str, parameters: Dict[str, Any] = None) -> Any:
        """
        获取提示
        
        参数:
            prompt_name: 提示名称
            parameters: 提示参数
            
        返回:
            提示内容
        """
        if prompt_name not in self.prompt_registry:
            raise ValueError(f"提示不存在: {prompt_name}")
        
        prompt = self.prompt_registry[prompt_name]
        params = parameters or {}
        
        try:
            # 调用提示函数
            if asyncio.iscoroutinefunction(prompt.function):
                result = await prompt.function(**params)
            else:
                result = prompt.function(**params)
            
            logger.info(f"提示获取成功: {prompt_name}")
            return result
            
        except Exception as e:
            logger.error(f"提示获取失败 {prompt_name}: {e}")
            raise
    
    def get_server_info(self) -> Dict[str, Any]:
        """获取服务器信息"""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "is_running": self.is_running,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "tools_count": len(self.tool_registry),
            "resources_count": len(self.resource_registry),
            "prompts_count": len(self.prompt_registry),
            "tools": list(self.tool_registry.keys()),
            "resources": list(self.resource_registry.keys()),
            "prompts": list(self.prompt_registry.keys())
        }
    
    async def start(self):
        """启动服务器"""
        if not self.is_running:
            self.is_running = True
            self.start_time = datetime.now()
            logger.info(f"FastMCP服务器已启动: {self.name}")
    
    async def stop(self):
        """停止服务器"""
        if self.is_running:
            self.is_running = False
            self.start_time = None
            logger.info(f"FastMCP服务器已停止: {self.name}")


# 全局服务器实例
_mcp_server: Optional[FastMCPServer] = None


def create_mcp_server(name: str = None, description: str = None, 
                      version: str = "2.0.0") -> FastMCPServer:
    """
    创建MCP服务器实例
    
    参数:
        name: 服务器名称
        description: 服务器描述
        version: 服务器版本
        
    返回:
        FastMCP服务器实例
    """
    global _mcp_server
    
    if _mcp_server is not None:
        logger.info("MCP服务器已存在，返回现有实例")
        return _mcp_server
    
    server_name = name or settings.fastmcp_name
    server_description = description or settings.fastmcp_description
    
    _mcp_server = FastMCPServer(
        name=server_name,
        description=server_description,
        version=version
    )
    
    logger.info(f"创建MCP服务器: {server_name}")
    return _mcp_server


def get_mcp_server() -> FastMCPServer:
    """
    获取MCP服务器实例，如果不存在则创建
    
    返回:
        FastMCP服务器实例
    """
    global _mcp_server
    
    if _mcp_server is None:
        return create_mcp_server()
    
    return _mcp_server


async def init_mcp_server():
    """初始化MCP服务器"""
    server = get_mcp_server()
    await server.start()
    return server


async def close_mcp_server():
    """关闭MCP服务器"""
    global _mcp_server
    
    if _mcp_server and _mcp_server.is_running:
        await _mcp_server.stop()
        _mcp_server = None


def get_server_status() -> Dict[str, Any]:
    """获取服务器状态"""
    server = get_mcp_server()
    return server.get_server_info()


# 导出
__all__ = [
    "FastMCPServer",
    "MCPTool",
    "MCPResource", 
    "MCPPrompt",
    "create_mcp_server",
    "get_mcp_server",
    "init_mcp_server",
    "close_mcp_server",
    "get_server_status"
] 