"""
系统配置相关的仓库实现
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepository
from ..models.system import SystemConfig, ModelProvider, FrameworkConfig, ServiceRegistry


class SystemConfigRepository(BaseRepository[SystemConfig, Dict[str, Any], Dict[str, Any]]):
    """系统配置仓库"""
    
    def __init__(self):
        super().__init__(SystemConfig)
    
    async def get_by_key(self, db: AsyncSession, key: str) -> Optional[SystemConfig]:
        """根据配置键获取配置"""
        return await self.get_by_field(db, "key", key)
    
    async def get_by_category(self, db: AsyncSession, category: str) -> List[SystemConfig]:
        """根据分类获取配置列表"""
        return await self.get_multi(db, filters={"category": category})


class ModelProviderRepository(BaseRepository[ModelProvider, Dict[str, Any], Dict[str, Any]]):
    """模型提供商仓库"""
    
    def __init__(self):
        super().__init__(ModelProvider)
    
    async def get_by_provider_type(self, db: AsyncSession, provider_type: str) -> List[ModelProvider]:
        """根据提供商类型获取列表"""
        return await self.get_multi(db, filters={"provider_type": provider_type})


class FrameworkConfigRepository(BaseRepository[FrameworkConfig, Dict[str, Any], Dict[str, Any]]):
    """框架配置仓库"""
    
    def __init__(self):
        super().__init__(FrameworkConfig)
    
    async def get_by_framework_type(self, db: AsyncSession, framework_type: str) -> List[FrameworkConfig]:
        """根据框架类型获取配置列表"""
        return await self.get_multi(db, filters={"framework_type": framework_type})