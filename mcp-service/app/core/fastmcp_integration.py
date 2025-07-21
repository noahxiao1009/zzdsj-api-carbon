"""
FastMCP 2.0框架集成实现
FastMCP V2 Framework Integration
"""

import asyncio
import json
import uuid
import logging
from typing import Dict, Any, Optional, List, Callable, AsyncGenerator
from datetime import datetime
from contextlib import asynccontextmanager

# FastMCP V2 imports (模拟实现，实际应使用真实的FastMCP库)
try:
    from fastmcp import FastMCP
    from fastmcp.server import MCPServer
    from fastmcp.client import MCPClient
    from fastmcp.transport import SSETransport, WebSocketTransport
    from fastmcp.protocol import MCPRequest, MCPResponse, MCPError
    from fastmcp.tools import Tool, ToolResult
except ImportError:
    # 如果FastMCP库不可用，提供模拟实现
    logging.warning("FastMCP library not available, using mock implementation")
    
    class MockMCPServer:
        def __init__(self, name: str, version: str = "1.0.0"):
            self.name = name
            self.version = version
            self.tools = {}
            self.resources = {}
            self.prompts = {}
    
    class MockMCPClient:
        def __init__(self, transport):
            self.transport = transport
    
    # 使用模拟类
    MCPServer = MockMCPServer
    MCPClient = MockMCPClient

from ..models.mcp_models import (
    MCPServiceConfig, MCPServiceInfo, MCPToolInfo, MCPServiceStatus,
    MCPToolExecuteRequest, MCPToolExecuteResponse, StreamType
)

logger = logging.getLogger(__name__)

class FastMCPServerManager:
    """FastMCP服务器管理器"""
    
    def __init__(self):
        self.servers: Dict[str, MCPServer] = {}
        self.transports: Dict[str, Any] = {}
        self.server_configs: Dict[str, MCPServiceConfig] = {}
        self.is_running: Dict[str, bool] = {}
        
        # 全局配置
        self.default_host = "0.0.0.0"
        self.default_port_range = (9000, 9999)
        self.used_ports = set()
    
    async def create_server(self, service_config: MCPServiceConfig) -> str:
        """创建MCP服务器实例"""
        try:
            service_id = str(uuid.uuid4())
            
            # 创建FastMCP服务器
            server = MCPServer(
                name=service_config.name,
                version=service_config.version
            )
            
            # 分配端口
            port = self._allocate_port()
            
            # 配置传输层（默认使用SSE）
            transport = SSETransport(
                host=self.default_host,
                port=port,
                path="/mcp"
            )
            
            # 注册工具
            await self._register_tools(server, service_config.tools)
            
            # 注册资源（如果有）
            await self._register_resources(server, service_config)
            
            # 注册提示模板（如果有）
            await self._register_prompts(server, service_config)
            
            # 保存配置
            self.servers[service_id] = server
            self.transports[service_id] = transport
            self.server_configs[service_id] = service_config
            self.is_running[service_id] = False
            
            logger.info(f"Created MCP server {service_config.name} with ID {service_id}")
            return service_id
            
        except Exception as e:
            logger.error(f"Failed to create MCP server: {e}")
            raise
    
    async def start_server(self, service_id: str) -> bool:
        """启动MCP服务器"""
        try:
            if service_id not in self.servers:
                raise ValueError(f"Server {service_id} not found")
            
            if self.is_running.get(service_id, False):
                logger.warning(f"Server {service_id} is already running")
                return True
            
            server = self.servers[service_id]
            transport = self.transports[service_id]
            
            # 启动服务器
            await server.start(transport)
            self.is_running[service_id] = True
            
            logger.info(f"Started MCP server {service_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start MCP server {service_id}: {e}")
            self.is_running[service_id] = False
            return False
    
    async def stop_server(self, service_id: str) -> bool:
        """停止MCP服务器"""
        try:
            if service_id not in self.servers:
                raise ValueError(f"Server {service_id} not found")
            
            if not self.is_running.get(service_id, False):
                logger.warning(f"Server {service_id} is not running")
                return True
            
            server = self.servers[service_id]
            
            # 停止服务器
            await server.stop()
            self.is_running[service_id] = False
            
            # 释放端口
            transport = self.transports[service_id]
            if hasattr(transport, 'port'):
                self.used_ports.discard(transport.port)
            
            logger.info(f"Stopped MCP server {service_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop MCP server {service_id}: {e}")
            return False
    
    async def remove_server(self, service_id: str) -> bool:
        """移除MCP服务器"""
        try:
            # 先停止服务器
            await self.stop_server(service_id)
            
            # 移除相关数据
            self.servers.pop(service_id, None)
            self.transports.pop(service_id, None)
            self.server_configs.pop(service_id, None)
            self.is_running.pop(service_id, None)
            
            logger.info(f"Removed MCP server {service_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove MCP server {service_id}: {e}")
            return False
    
    async def get_server_status(self, service_id: str) -> Dict[str, Any]:
        """获取服务器状态"""
        try:
            if service_id not in self.servers:
                return {
                    "status": MCPServiceStatus.ERROR,
                    "error": "Server not found"
                }
            
            is_running = self.is_running.get(service_id, False)
            server = self.servers[service_id]
            transport = self.transports[service_id]
            
            status_info = {
                "status": MCPServiceStatus.ACTIVE if is_running else MCPServiceStatus.INACTIVE,
                "server_name": server.name,
                "server_version": server.version,
                "transport_type": type(transport).__name__,
                "is_running": is_running
            }
            
            if hasattr(transport, 'host') and hasattr(transport, 'port'):
                status_info["host"] = transport.host
                status_info["port"] = transport.port
                status_info["url"] = f"http://{transport.host}:{transport.port}/mcp"
            
            return status_info
            
        except Exception as e:
            logger.error(f"Failed to get server status {service_id}: {e}")
            return {
                "status": MCPServiceStatus.ERROR,
                "error": str(e)
            }
    
    async def list_servers(self) -> List[Dict[str, Any]]:
        """列出所有服务器"""
        servers_info = []
        
        for service_id in self.servers.keys():
            status = await self.get_server_status(service_id)
            status["service_id"] = service_id
            servers_info.append(status)
        
        return servers_info
    
    async def _register_tools(self, server: MCPServer, tools_config: List[Dict[str, Any]]):
        """注册工具到MCP服务器"""
        for tool_config in tools_config:
            try:
                tool_name = tool_config["name"]
                tool_description = tool_config.get("description", "")
                tool_schema = tool_config.get("schema", {})
                
                # 创建工具处理函数
                async def tool_handler(**kwargs):
                    return await self._execute_tool_handler(tool_config, kwargs)
                
                # 注册工具（模拟FastMCP的装饰器语法）
                if hasattr(server, 'tool'):
                    server.tool(
                        name=tool_name,
                        description=tool_description,
                        schema=tool_schema
                    )(tool_handler)
                else:
                    # 模拟实现
                    if not hasattr(server, 'tools'):
                        server.tools = {}
                    server.tools[tool_name] = {
                        "handler": tool_handler,
                        "description": tool_description,
                        "schema": tool_schema
                    }
                
                logger.debug(f"Registered tool: {tool_name}")
                
            except Exception as e:
                logger.error(f"Failed to register tool {tool_config.get('name', 'unknown')}: {e}")
    
    async def _register_resources(self, server: MCPServer, service_config: MCPServiceConfig):
        """注册资源到MCP服务器"""
        resources_config = service_config.config.get("resources", [])
        
        for resource_config in resources_config:
            try:
                resource_name = resource_config["name"]
                resource_type = resource_config.get("type", "text")
                
                # 创建资源处理函数
                async def resource_handler(**kwargs):
                    return await self._execute_resource_handler(resource_config, kwargs)
                
                # 注册资源
                if hasattr(server, 'resource'):
                    server.resource(
                        name=resource_name,
                        resource_type=resource_type
                    )(resource_handler)
                else:
                    # 模拟实现
                    if not hasattr(server, 'resources'):
                        server.resources = {}
                    server.resources[resource_name] = {
                        "handler": resource_handler,
                        "type": resource_type
                    }
                
                logger.debug(f"Registered resource: {resource_name}")
                
            except Exception as e:
                logger.error(f"Failed to register resource: {e}")
    
    async def _register_prompts(self, server: MCPServer, service_config: MCPServiceConfig):
        """注册提示模板到MCP服务器"""
        prompts_config = service_config.config.get("prompts", [])
        
        for prompt_config in prompts_config:
            try:
                prompt_name = prompt_config["name"]
                prompt_template = prompt_config.get("template", "")
                
                # 创建提示处理函数
                async def prompt_handler(**kwargs):
                    return await self._execute_prompt_handler(prompt_config, kwargs)
                
                # 注册提示
                if hasattr(server, 'prompt'):
                    server.prompt(
                        name=prompt_name,
                        template=prompt_template
                    )(prompt_handler)
                else:
                    # 模拟实现
                    if not hasattr(server, 'prompts'):
                        server.prompts = {}
                    server.prompts[prompt_name] = {
                        "handler": prompt_handler,
                        "template": prompt_template
                    }
                
                logger.debug(f"Registered prompt: {prompt_name}")
                
            except Exception as e:
                logger.error(f"Failed to register prompt: {e}")
    
    async def _execute_tool_handler(self, tool_config: Dict[str, Any], parameters: Dict[str, Any]) -> Any:
        """执行工具处理逻辑"""
        try:
            # 这里应该根据工具类型执行相应的逻辑
            tool_type = tool_config.get("type", "function")
            
            if tool_type == "function":
                return await self._execute_function_tool(tool_config, parameters)
            elif tool_type == "resource":
                return await self._execute_resource_tool(tool_config, parameters)
            else:
                return {"error": f"Unsupported tool type: {tool_type}"}
                
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return {"error": str(e)}
    
    async def _execute_function_tool(self, tool_config: Dict[str, Any], parameters: Dict[str, Any]) -> Any:
        """执行函数工具"""
        # 模拟工具执行
        tool_name = tool_config["name"]
        
        # 模拟不同类型的工具响应
        if "search" in tool_name.lower():
            return {
                "results": [
                    {"title": f"搜索结果 {i}", "content": f"这是第{i}个搜索结果", "url": f"http://example.com/{i}"}
                    for i in range(1, 4)
                ],
                "query": parameters.get("query", ""),
                "total": 3
            }
        elif "weather" in tool_name.lower():
            return {
                "location": parameters.get("location", "未知地点"),
                "temperature": "25°C",
                "condition": "晴朗",
                "humidity": "60%"
            }
        else:
            return {
                "tool": tool_name,
                "parameters": parameters,
                "result": "执行成功",
                "timestamp": datetime.now().isoformat()
            }
    
    async def _execute_resource_tool(self, tool_config: Dict[str, Any], parameters: Dict[str, Any]) -> Any:
        """执行资源工具"""
        return {
            "resource_type": "text",
            "content": "这是一个资源内容示例",
            "metadata": parameters
        }
    
    async def _execute_resource_handler(self, resource_config: Dict[str, Any], parameters: Dict[str, Any]) -> Any:
        """执行资源处理逻辑"""
        return {
            "resource": resource_config["name"],
            "type": resource_config.get("type", "text"),
            "content": "资源内容示例"
        }
    
    async def _execute_prompt_handler(self, prompt_config: Dict[str, Any], parameters: Dict[str, Any]) -> Any:
        """执行提示处理逻辑"""
        template = prompt_config.get("template", "")
        
        # 简单的模板替换
        for key, value in parameters.items():
            template = template.replace(f"{{{key}}}", str(value))
        
        return {
            "prompt": prompt_config["name"],
            "rendered": template,
            "parameters": parameters
        }
    
    def _allocate_port(self) -> int:
        """分配可用端口"""
        for port in range(*self.default_port_range):
            if port not in self.used_ports:
                self.used_ports.add(port)
                return port
        
        raise Exception("No available ports in range")

class FastMCPClientManager:
    """FastMCP客户端管理器"""
    
    def __init__(self):
        self.clients: Dict[str, MCPClient] = {}
        self.connection_pool: Dict[str, Any] = {}
    
    async def create_client(self, service_id: str, service_url: str) -> bool:
        """创建MCP客户端连接"""
        try:
            # 创建传输层
            if service_url.startswith("sse://"):
                transport = SSETransport.from_url(service_url)
            elif service_url.startswith("ws://") or service_url.startswith("wss://"):
                transport = WebSocketTransport.from_url(service_url)
            else:
                # 默认使用SSE
                transport = SSETransport.from_url(f"sse://{service_url}")
            
            # 创建客户端
            client = MCPClient(transport)
            
            # 建立连接
            await client.connect()
            
            self.clients[service_id] = client
            logger.info(f"Created MCP client for service {service_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to create MCP client for {service_id}: {e}")
            return False
    
    async def call_tool(self, service_id: str, tool_name: str, parameters: Dict[str, Any]) -> Any:
        """调用MCP工具"""
        try:
            if service_id not in self.clients:
                raise ValueError(f"Client for service {service_id} not found")
            
            client = self.clients[service_id]
            
            # 调用工具
            result = await client.call_tool(tool_name, parameters)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to call tool {tool_name} on service {service_id}: {e}")
            raise
    
    async def call_tool_streaming(
        self,
        service_id: str,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> AsyncGenerator[Any, None]:
        """流式调用MCP工具"""
        try:
            if service_id not in self.clients:
                raise ValueError(f"Client for service {service_id} not found")
            
            client = self.clients[service_id]
            
            # 流式调用工具
            async for chunk in client.call_tool_streaming(tool_name, parameters):
                yield chunk
                
        except Exception as e:
            logger.error(f"Failed to call tool streaming {tool_name} on service {service_id}: {e}")
            raise
    
    async def disconnect_client(self, service_id: str) -> bool:
        """断开客户端连接"""
        try:
            if service_id in self.clients:
                client = self.clients[service_id]
                await client.disconnect()
                del self.clients[service_id]
                
                logger.info(f"Disconnected MCP client for service {service_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to disconnect client {service_id}: {e}")
            return False

class FastMCPIntegration:
    """FastMCP集成管理器"""
    
    def __init__(self):
        self.server_manager = FastMCPServerManager()
        self.client_manager = FastMCPClientManager()
        
        # 服务映射：service_id -> server_id
        self.service_mappings: Dict[str, str] = {}
    
    async def deploy_mcp_service(self, service_config: MCPServiceConfig) -> str:
        """部署MCP服务"""
        try:
            # 1. 创建MCP服务器
            server_id = await self.server_manager.create_server(service_config)
            
            # 2. 启动服务器
            success = await self.server_manager.start_server(server_id)
            if not success:
                await self.server_manager.remove_server(server_id)
                raise Exception("Failed to start MCP server")
            
            # 3. 获取服务URL
            status = await self.server_manager.get_server_status(server_id)
            service_url = status.get("url")
            
            # 4. 创建客户端连接（用于健康检查）
            if service_url:
                await asyncio.sleep(1)  # 等待服务器完全启动
                await self.client_manager.create_client(server_id, service_url)
            
            # 5. 记录映射关系
            self.service_mappings[service_config.name] = server_id
            
            logger.info(f"Successfully deployed MCP service: {service_config.name}")
            return server_id
            
        except Exception as e:
            logger.error(f"Failed to deploy MCP service {service_config.name}: {e}")
            raise
    
    async def undeploy_mcp_service(self, service_name: str) -> bool:
        """下线MCP服务"""
        try:
            if service_name not in self.service_mappings:
                logger.warning(f"Service {service_name} not found in mappings")
                return False
            
            server_id = self.service_mappings[service_name]
            
            # 1. 断开客户端连接
            await self.client_manager.disconnect_client(server_id)
            
            # 2. 停止并移除服务器
            await self.server_manager.remove_server(server_id)
            
            # 3. 清理映射关系
            del self.service_mappings[service_name]
            
            logger.info(f"Successfully undeployed MCP service: {service_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to undeploy MCP service {service_name}: {e}")
            return False
    
    async def execute_tool(self, service_name: str, request: MCPToolExecuteRequest) -> MCPToolExecuteResponse:
        """执行MCP工具"""
        start_time = datetime.now()
        usage_id = str(uuid.uuid4())
        
        try:
            if service_name not in self.service_mappings:
                raise ValueError(f"Service {service_name} not found")
            
            server_id = self.service_mappings[service_name]
            
            # 执行工具
            if request.stream:
                # 流式执行
                stream_id = str(uuid.uuid4())
                # 这里应该启动流式执行逻辑
                return MCPToolExecuteResponse(
                    success=True,
                    result=None,
                    execution_time_ms=0,
                    usage_id=usage_id,
                    stream_id=stream_id,
                    stream_url=f"/api/v1/mcp/streams/{stream_id}/events"
                )
            else:
                # 同步执行
                result = await self.client_manager.call_tool(
                    server_id,
                    request.tool_name,
                    request.parameters
                )
                
                execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
                
                return MCPToolExecuteResponse(
                    success=True,
                    result=result,
                    execution_time_ms=execution_time,
                    usage_id=usage_id
                )
                
        except Exception as e:
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            return MCPToolExecuteResponse(
                success=False,
                result=None,
                execution_time_ms=execution_time,
                error_message=str(e),
                usage_id=usage_id
            )
    
    async def get_service_status(self, service_name: str) -> Dict[str, Any]:
        """获取服务状态"""
        if service_name not in self.service_mappings:
            return {"error": "Service not found"}
        
        server_id = self.service_mappings[service_name]
        return await self.server_manager.get_server_status(server_id)
    
    async def list_all_services(self) -> List[Dict[str, Any]]:
        """列出所有服务"""
        services = []
        
        for service_name, server_id in self.service_mappings.items():
            status = await self.server_manager.get_server_status(server_id)
            status["service_name"] = service_name
            status["server_id"] = server_id
            services.append(status)
        
        return services