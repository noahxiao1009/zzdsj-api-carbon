"""
智能体相关的仓库实现
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepository
from ..models.agent import AgentDefinition, AgentTemplate, AgentRun, AgentChain, AgentOrchestration


class AgentDefinitionRepository(BaseRepository[AgentDefinition, Dict[str, Any], Dict[str, Any]]):
    """智能体定义仓库"""
    
    def __init__(self):
        super().__init__(AgentDefinition)
    
    async def get_by_user_id(self, db: AsyncSession, user_id: str) -> List[AgentDefinition]:
        """根据用户ID获取智能体定义列表"""
        return await self.get_multi(db, filters={"user_id": user_id})


class AgentTemplateRepository(BaseRepository[AgentTemplate, Dict[str, Any], Dict[str, Any]]):
    """智能体模板仓库"""
    
    def __init__(self):
        super().__init__(AgentTemplate)
    
    async def get_by_level(self, db: AsyncSession, level: str) -> List[AgentTemplate]:
        """根据级别获取模板列表"""
        return await self.get_multi(db, filters={"level": level})


class AgentRunRepository(BaseRepository[AgentRun, Dict[str, Any], Dict[str, Any]]):
    """智能体运行仓库"""
    
    def __init__(self):
        super().__init__(AgentRun)
    
    async def get_by_agent_id(self, db: AsyncSession, agent_id: str) -> List[AgentRun]:
        """根据智能体ID获取运行记录"""
        return await self.get_multi(db, filters={"agent_definition_id": agent_id})