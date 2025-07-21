"""
工具基础类
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from app.utils.logging import get_logger


logger = get_logger(__name__)


class BaseTool(ABC):
    """基础工具类"""
    
    def __init__(self, name: str, description: str = "", config: Dict[str, Any] = None):
        self.name = name
        self.description = description
        self.config = config or {}
        self.usage_count = 0
        self.error_count = 0
    
    @abstractmethod
    async def execute(self, *args, **kwargs) -> Any:
        """执行工具"""
        pass
    
    def get_definition(self) -> Dict[str, Any]:
        """获取工具定义"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.get_parameters(),
            }
        }
    
    @abstractmethod
    def get_parameters(self) -> Dict[str, Any]:
        """获取参数定义"""
        pass
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """验证参数"""
        return True
    
    def log_usage(self, success: bool = True):
        """记录使用情况"""
        self.usage_count += 1
        if not success:
            self.error_count += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "usage_count": self.usage_count,
            "error_count": self.error_count,
            "success_rate": (
                (self.usage_count - self.error_count) / self.usage_count 
                if self.usage_count > 0 else 0
            )
        }
    
    def __repr__(self):
        return f"<{self.__class__.__name__} {self.name}>"


class ToolRegistry:
    """工具注册表"""
    
    _tools = {}
    
    @classmethod
    def register(cls, tool: BaseTool):
        """注册工具"""
        cls._tools[tool.name] = tool
    
    @classmethod
    def unregister(cls, name: str):
        """注销工具"""
        if name in cls._tools:
            del cls._tools[name]
    
    @classmethod
    def get(cls, name: str) -> Optional[BaseTool]:
        """获取工具"""
        return cls._tools.get(name)
    
    @classmethod
    def get_all(cls) -> Dict[str, BaseTool]:
        """获取所有工具"""
        return cls._tools.copy()
    
    @classmethod
    def get_definitions(cls) -> list:
        """获取所有工具定义"""
        return [tool.get_definition() for tool in cls._tools.values()]


class ToolExecutor:
    """工具执行器"""
    
    def __init__(self, registry: ToolRegistry = None):
        self.registry = registry or ToolRegistry()
    
    async def execute(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        """执行工具"""
        tool = self.registry.get(tool_name)
        if not tool:
            raise ValueError(f"工具 {tool_name} 不存在")
        
        # 验证参数
        if not tool.validate_parameters(parameters):
            raise ValueError(f"工具 {tool_name} 参数验证失败")
        
        try:
            result = await tool.execute(**parameters)
            tool.log_usage(success=True)
            return result
        except Exception as e:
            tool.log_usage(success=False)
            logger.error(f"工具 {tool_name} 执行失败: {str(e)}", exc_info=True)
            raise
    
    def get_tool_definitions(self) -> list:
        """获取工具定义"""
        return self.registry.get_definitions()
    
    def get_tool_stats(self) -> Dict[str, Any]:
        """获取工具统计"""
        tools = self.registry.get_all()
        return {
            "total_tools": len(tools),
            "tool_stats": {name: tool.get_stats() for name, tool in tools.items()}
        }