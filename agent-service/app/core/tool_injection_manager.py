"""
工具注入管理器
Tool Injection Manager

负责从各个微服务动态获取工具，并注入到DAG智能体中：
- MCP服务工具
- 工具服务工具 (WebSailor, Scraperr等)
- 系统服务工具 (文件上传、敏感词过滤、政策搜索等)
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Set, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json

from shared.service_client import call_service, CallMethod, CallConfig

logger = logging.getLogger(__name__)

class ToolType(str, Enum):
    """工具类型"""
    MCP = "mcp"
    BUILTIN = "builtin"
    SYSTEM = "system"
    EXTERNAL = "external"

class ToolCategory(str, Enum):
    """工具分类"""
    SEARCH = "search"
    CONTENT = "content"
    FILE = "file"
    REASONING = "reasoning"
    CALCULATION = "calculation"
    COMMUNICATION = "communication"
    ANALYSIS = "analysis"
    AUTOMATION = "automation"
    SECURITY = "security"
    DATA = "data"

@dataclass
class ToolDefinition:
    """工具定义"""
    id: str
    name: str
    display_name: str
    description: str
    type: ToolType
    category: ToolCategory
    version: str = "1.0.0"
    
    # 工具配置
    schema: Dict[str, Any] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)
    
    # 服务信息
    service_name: str = ""
    service_url: str = ""
    endpoint: str = ""
    
    # 权限和限制
    permission_level: str = "user"
    rate_limit: Optional[int] = None
    timeout: int = 30
    
    # 状态信息
    is_enabled: bool = True
    is_available: bool = True
    health_status: str = "unknown"
    
    # 性能指标
    total_calls: int = 0
    success_rate: float = 0.0
    avg_response_time: float = 0.0
    
    # 元数据
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

@dataclass 
class ToolExecutionRequest:
    """工具执行请求"""
    tool_id: str
    action: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    timeout: Optional[int] = None

@dataclass
class ToolExecutionResult:
    """工具执行结果"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

class ToolInjectionManager:
    """工具注入管理器"""
    
    def __init__(self):
        self.tools: Dict[str, ToolDefinition] = {}
        self.tools_by_category: Dict[ToolCategory, List[str]] = {}
        self.tools_by_service: Dict[str, List[str]] = {}
        
        # 工具发现配置
        self.discovery_config = {
            "mcp-service": {
                "health_endpoint": "/health",
                "tools_endpoint": "/api/v1/mcp/tools/list",
                "execute_endpoint": "/api/v1/mcp/tools/execute"
            },
            "tools-service": {
                "health_endpoint": "/health",
                "tools_endpoint": "/api/v1/tools/list",
                "execute_endpoint": "/api/v1/tools/execute"
            },
            "system-service": {
                "health_endpoint": "/health",
                "tools_endpoint": "/api/v1/tools/list",
                "execute_endpoint": "/api/v1/tools/execute"
            }
        }
        
        # 缓存配置
        self.cache_ttl = 300  # 5分钟缓存
        self.last_discovery = {}
        self.health_check_interval = 60  # 1分钟健康检查间隔
        
        # 性能统计
        self.stats = {
            "total_discoveries": 0,
            "total_executions": 0,
            "failed_executions": 0,
            "last_discovery_time": None
        }
    
    async def initialize(self):
        """初始化工具注入管理器"""
        logger.info("初始化工具注入管理器...")
        
        try:
            # 注册内置工具
            await self._register_builtin_tools()
            
            # 发现外部工具
            await self.discover_tools()
            
            # 启动健康检查任务
            asyncio.create_task(self._health_check_loop())
            
            logger.info(f"工具注入管理器初始化完成，共发现 {len(self.tools)} 个工具")
            
        except Exception as e:
            logger.error(f"工具注入管理器初始化失败: {e}")
            raise
    
    async def discover_tools(self) -> Dict[str, List[ToolDefinition]]:
        """发现可用工具"""
        logger.info("开始工具发现...")
        
        discovered_tools = {
            "mcp-service": [],
            "tools-service": [],
            "system-service": []
        }
        
        # 并行发现各服务的工具
        discovery_tasks = []
        for service_name in self.discovery_config.keys():
            task = asyncio.create_task(
                self._discover_service_tools(service_name),
                name=f"discover_{service_name}"
            )
            discovery_tasks.append(task)
        
        results = await asyncio.gather(*discovery_tasks, return_exceptions=True)
        
        # 处理发现结果
        for i, result in enumerate(results):
            service_name = list(self.discovery_config.keys())[i]
            
            if isinstance(result, Exception):
                logger.error(f"发现 {service_name} 工具失败: {result}")
                continue
            
            if result:
                discovered_tools[service_name] = result
                # 注册工具到管理器
                for tool in result:
                    await self._register_tool(tool)
        
        self.stats["total_discoveries"] += 1
        self.stats["last_discovery_time"] = datetime.now()
        
        logger.info(f"工具发现完成: MCP={len(discovered_tools['mcp-service'])}, "
                   f"Tools={len(discovered_tools['tools-service'])}, "
                   f"System={len(discovered_tools['system-service'])}")
        
        return discovered_tools
    
    async def _discover_service_tools(self, service_name: str) -> List[ToolDefinition]:
        """发现特定服务的工具"""
        try:
            # 检查服务健康状态
            health_ok = await self._check_service_health(service_name)
            if not health_ok:
                logger.warning(f"服务 {service_name} 健康检查失败，跳过工具发现")
                return []
            
            config = self.discovery_config[service_name]
            
            # 获取工具列表
            response = await call_service(
                service_name=service_name,
                method=CallMethod.GET,
                path=config["tools_endpoint"],
                timeout=10
            )
            
            if not response.get("success", False):
                logger.error(f"获取 {service_name} 工具列表失败: {response}")
                return []
            
            tools_data = response.get("data", response.get("tools", []))
            discovered_tools = []
            
            # 解析工具定义
            for tool_data in tools_data:
                tool = await self._parse_tool_definition(tool_data, service_name)
                if tool:
                    discovered_tools.append(tool)
            
            return discovered_tools
            
        except Exception as e:
            logger.error(f"发现 {service_name} 工具异常: {e}")
            return []
    
    async def _parse_tool_definition(self, tool_data: Dict[str, Any], service_name: str) -> Optional[ToolDefinition]:
        """解析工具定义"""
        try:
            # 确定工具类型
            tool_type = ToolType.EXTERNAL
            if service_name == "mcp-service":
                tool_type = ToolType.MCP
            elif service_name == "system-service":
                tool_type = ToolType.SYSTEM
            elif "builtin" in tool_data.get("tags", []):
                tool_type = ToolType.BUILTIN
            
            # 确定工具分类
            category = self._determine_tool_category(tool_data, service_name)
            
            tool = ToolDefinition(
                id=f"{service_name}.{tool_data.get('name', tool_data.get('id', 'unknown'))}",
                name=tool_data.get("name", ""),
                display_name=tool_data.get("display_name", tool_data.get("name", "")),
                description=tool_data.get("description", ""),
                type=tool_type,
                category=category,
                version=tool_data.get("version", "1.0.0"),
                
                # 配置信息
                schema=tool_data.get("schema", {}),
                parameters=tool_data.get("parameters", {}),
                config=tool_data.get("config", {}),
                
                # 服务信息
                service_name=service_name,
                endpoint=self.discovery_config[service_name]["execute_endpoint"],
                
                # 权限和限制
                permission_level=tool_data.get("permission_level", "user"),
                rate_limit=tool_data.get("rate_limit"),
                timeout=tool_data.get("timeout", 30),
                
                # 状态信息
                is_enabled=tool_data.get("is_enabled", True),
                is_available=tool_data.get("is_available", True),
                health_status=tool_data.get("health_status", "unknown"),
                
                # 性能指标
                total_calls=tool_data.get("total_calls", 0),
                success_rate=tool_data.get("success_rate", 0.0),
                avg_response_time=tool_data.get("avg_response_time", 0.0),
                
                # 元数据
                tags=tool_data.get("tags", [])
            )
            
            return tool
            
        except Exception as e:
            logger.error(f"解析工具定义失败: {e}, 数据: {tool_data}")
            return None
    
    def _determine_tool_category(self, tool_data: Dict[str, Any], service_name: str) -> ToolCategory:
        """确定工具分类"""
        name = tool_data.get("name", "").lower()
        category = tool_data.get("category", "").lower()
        description = tool_data.get("description", "").lower()
        
        # 根据工具名称和描述判断分类
        if any(keyword in name + description for keyword in ["search", "搜索", "查找", "检索"]):
            return ToolCategory.SEARCH
        elif any(keyword in name + description for keyword in ["file", "upload", "文件", "上传", "下载"]):
            return ToolCategory.FILE
        elif any(keyword in name + description for keyword in ["filter", "sensitive", "敏感", "过滤"]):
            return ToolCategory.SECURITY
        elif any(keyword in name + description for keyword in ["content", "extract", "内容", "提取", "爬取"]):
            return ToolCategory.CONTENT
        elif any(keyword in name + description for keyword in ["calculate", "math", "计算", "数学"]):
            return ToolCategory.CALCULATION
        elif any(keyword in name + description for keyword in ["analyze", "analysis", "分析"]):
            return ToolCategory.ANALYSIS
        elif any(keyword in name + description for keyword in ["reason", "think", "推理", "思考"]):
            return ToolCategory.REASONING
        elif any(keyword in name + description for keyword in ["automation", "automate", "自动化"]):
            return ToolCategory.AUTOMATION
        elif any(keyword in name + description for keyword in ["data", "database", "数据"]):
            return ToolCategory.DATA
        elif any(keyword in name + description for keyword in ["communication", "chat", "通信", "聊天"]):
            return ToolCategory.COMMUNICATION
        
        # 按服务类型推断
        if service_name == "system-service":
            return ToolCategory.SECURITY
        elif service_name == "tools-service":
            return ToolCategory.CONTENT
        
        return ToolCategory.REASONING  # 默认分类
    
    async def _register_builtin_tools(self):
        """注册内置工具"""
        builtin_tools = [
            ToolDefinition(
                id="builtin.reasoning",
                name="reasoning",
                display_name="推理工具",
                description="基础推理和逻辑分析工具",
                type=ToolType.BUILTIN,
                category=ToolCategory.REASONING,
                schema={
                    "type": "function",
                    "function": {
                        "name": "reasoning",
                        "description": "进行逻辑推理和分析",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "需要推理的问题或情况"
                                }
                            },
                            "required": ["query"]
                        }
                    }
                },
                service_name="builtin",
                is_enabled=True,
                is_available=True,
                health_status="healthy"
            ),
            ToolDefinition(
                id="builtin.calculator",
                name="calculator",
                display_name="计算器",
                description="基础数学计算工具",
                type=ToolType.BUILTIN,
                category=ToolCategory.CALCULATION,
                schema={
                    "type": "function",
                    "function": {
                        "name": "calculator",
                        "description": "执行数学计算",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "expression": {
                                    "type": "string",
                                    "description": "数学表达式"
                                }
                            },
                            "required": ["expression"]
                        }
                    }
                },
                service_name="builtin",
                is_enabled=True,
                is_available=True,
                health_status="healthy"
            )
        ]
        
        for tool in builtin_tools:
            await self._register_tool(tool)
    
    async def _register_tool(self, tool: ToolDefinition):
        """注册工具"""
        self.tools[tool.id] = tool
        
        # 按分类索引
        if tool.category not in self.tools_by_category:
            self.tools_by_category[tool.category] = []
        self.tools_by_category[tool.category].append(tool.id)
        
        # 按服务索引
        if tool.service_name not in self.tools_by_service:
            self.tools_by_service[tool.service_name] = []
        self.tools_by_service[tool.service_name].append(tool.id)
    
    async def _check_service_health(self, service_name: str) -> bool:
        """检查服务健康状态"""
        try:
            config = self.discovery_config[service_name]
            response = await call_service(
                service_name=service_name,
                method=CallMethod.GET,
                path=config["health_endpoint"],
                timeout=5
            )
            
            return response.get("status") == "healthy" or response.get("overall_healthy", False)
            
        except Exception as e:
            logger.error(f"检查 {service_name} 健康状态失败: {e}")
            return False
    
    async def _health_check_loop(self):
        """健康检查循环"""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)
                await self._update_tools_health()
            except Exception as e:
                logger.error(f"健康检查循环异常: {e}")
    
    async def _update_tools_health(self):
        """更新工具健康状态"""
        for service_name in self.discovery_config.keys():
            is_healthy = await self._check_service_health(service_name)
            
            # 更新该服务下所有工具的可用性
            if service_name in self.tools_by_service:
                for tool_id in self.tools_by_service[service_name]:
                    if tool_id in self.tools:
                        self.tools[tool_id].is_available = is_healthy
                        self.tools[tool_id].health_status = "healthy" if is_healthy else "unhealthy"
    
    async def execute_tool(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        """执行工具"""
        start_time = datetime.now()
        
        try:
            tool = self.tools.get(request.tool_id)
            if not tool:
                return ToolExecutionResult(
                    success=False,
                    error=f"工具 {request.tool_id} 未找到"
                )
            
            if not tool.is_enabled or not tool.is_available:
                return ToolExecutionResult(
                    success=False,
                    error=f"工具 {request.tool_id} 不可用"
                )
            
            # 内置工具特殊处理
            if tool.type == ToolType.BUILTIN:
                return await self._execute_builtin_tool(tool, request)
            
            # 调用外部服务
            response = await call_service(
                service_name=tool.service_name,
                method=CallMethod.POST,
                path=tool.endpoint,
                json={
                    "tool_name": tool.name,
                    "action": request.action,
                    "parameters": request.parameters,
                    "user_id": request.user_id,
                    "session_id": request.session_id
                },
                timeout=request.timeout or tool.timeout
            )
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            if response.get("success", False):
                self.stats["total_executions"] += 1
                return ToolExecutionResult(
                    success=True,
                    data=response.get("data"),
                    execution_time=execution_time,
                    metadata=response.get("metadata", {})
                )
            else:
                self.stats["failed_executions"] += 1
                return ToolExecutionResult(
                    success=False,
                    error=response.get("message", "工具执行失败"),
                    execution_time=execution_time
                )
                
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            self.stats["failed_executions"] += 1
            logger.error(f"工具执行异常 {request.tool_id}: {e}")
            
            return ToolExecutionResult(
                success=False,
                error=str(e),
                execution_time=execution_time
            )
    
    async def _execute_builtin_tool(self, tool: ToolDefinition, request: ToolExecutionRequest) -> ToolExecutionResult:
        """执行内置工具"""
        try:
            if tool.name == "reasoning":
                # 简单的推理逻辑
                query = request.parameters.get("query", "")
                result = f"基于推理分析：{query}"
                return ToolExecutionResult(success=True, data={"result": result})
                
            elif tool.name == "calculator":
                # 简单的计算逻辑
                expression = request.parameters.get("expression", "")
                try:
                    # 安全的数学表达式计算
                    import ast
                    import operator
                    
                    # 支持的操作
                    ops = {
                        ast.Add: operator.add,
                        ast.Sub: operator.sub,
                        ast.Mult: operator.mul,
                        ast.Div: operator.truediv,
                        ast.Pow: operator.pow,
                        ast.USub: operator.neg,
                    }
                    
                    def eval_expr(node):
                        if isinstance(node, ast.Num):
                            return node.n
                        elif isinstance(node, ast.BinOp):
                            return ops[type(node.op)](eval_expr(node.left), eval_expr(node.right))
                        elif isinstance(node, ast.UnaryOp):
                            return ops[type(node.op)](eval_expr(node.operand))
                        else:
                            raise TypeError(node)
                    
                    result = eval_expr(ast.parse(expression, mode='eval').body)
                    return ToolExecutionResult(success=True, data={"result": result})
                    
                except Exception as e:
                    return ToolExecutionResult(success=False, error=f"计算错误: {e}")
            
            return ToolExecutionResult(success=False, error="未知的内置工具")
            
        except Exception as e:
            return ToolExecutionResult(success=False, error=str(e))
    
    def get_tools_for_agent(
        self, 
        categories: Optional[List[ToolCategory]] = None,
        tool_types: Optional[List[ToolType]] = None,
        max_tools: Optional[int] = None
    ) -> List[ToolDefinition]:
        """获取适用于智能体的工具列表"""
        available_tools = []
        
        for tool in self.tools.values():
            # 检查工具状态
            if not tool.is_enabled or not tool.is_available:
                continue
            
            # 检查分类过滤
            if categories and tool.category not in categories:
                continue
            
            # 检查类型过滤
            if tool_types and tool.type not in tool_types:
                continue
            
            available_tools.append(tool)
        
        # 按成功率和响应时间排序
        available_tools.sort(
            key=lambda t: (t.success_rate, -t.avg_response_time),
            reverse=True
        )
        
        # 限制数量
        if max_tools:
            available_tools = available_tools[:max_tools]
        
        return available_tools
    
    def get_tool_schemas_for_agno(self, tool_ids: List[str]) -> List[Dict[str, Any]]:
        """获取适用于Agno的工具Schema"""
        schemas = []
        
        for tool_id in tool_ids:
            tool = self.tools.get(tool_id)
            if not tool or not tool.is_enabled or not tool.is_available:
                continue
            
            # 转换为Agno工具格式
            agno_schema = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.schema.get("function", {}).get("parameters", {})
                }
            }
            
            schemas.append(agno_schema)
        
        return schemas
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        tool_stats = {
            "total_tools": len(self.tools),
            "enabled_tools": len([t for t in self.tools.values() if t.is_enabled]),
            "available_tools": len([t for t in self.tools.values() if t.is_available]),
            "tools_by_type": {},
            "tools_by_category": {},
            "tools_by_service": {}
        }
        
        # 按类型统计
        for tool in self.tools.values():
            tool_type = tool.type.value
            if tool_type not in tool_stats["tools_by_type"]:
                tool_stats["tools_by_type"][tool_type] = 0
            tool_stats["tools_by_type"][tool_type] += 1
        
        # 按分类统计
        for tool in self.tools.values():
            category = tool.category.value
            if category not in tool_stats["tools_by_category"]:
                tool_stats["tools_by_category"][category] = 0
            tool_stats["tools_by_category"][category] += 1
        
        # 按服务统计
        for tool in self.tools.values():
            service = tool.service_name
            if service not in tool_stats["tools_by_service"]:
                tool_stats["tools_by_service"][service] = 0
            tool_stats["tools_by_service"][service] += 1
        
        return {
            **tool_stats,
            **self.stats
        }

# 全局工具注入管理器实例
tool_injection_manager = ToolInjectionManager() 