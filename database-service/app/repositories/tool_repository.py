"""
工具相关的仓库实现
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepository
from ..models.tool import Tool, ToolConfiguration, ToolExecution, UnifiedTool


class ToolRepository(BaseRepository[Tool, Dict[str, Any], Dict[str, Any]]):
    """工具仓库"""
    
    def __init__(self):
        super().__init__(Tool)
    
    async def get_by_category(self, db: AsyncSession, category: str) -> List[Tool]:
        """根据分类获取工具列表"""
        return await self.get_multi(db, filters={"category": category})


class ToolConfigurationRepository(BaseRepository[ToolConfiguration, Dict[str, Any], Dict[str, Any]]):
    """工具配置仓库"""
    
    def __init__(self):
        super().__init__(ToolConfiguration)
    
    async def get_by_tool_id(self, db: AsyncSession, tool_id: str) -> List[ToolConfiguration]:
        """根据工具ID获取配置列表"""
        return await self.get_multi(db, filters={"tool_id": tool_id})


class ToolExecutionRepository(BaseRepository[ToolExecution, Dict[str, Any], Dict[str, Any]]):
    """工具执行仓库"""
    
    def __init__(self):
        super().__init__(ToolExecution)
    
    async def get_by_tool_id(self, db: AsyncSession, tool_id: str) -> List[ToolExecution]:
        """根据工具ID获取执行记录"""
        return await self.get_multi(db, filters={"tool_id": tool_id})