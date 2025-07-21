"""
政策搜索数据访问层
Policy Search Repository
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update, delete, and_, or_, func, desc
from sqlalchemy.orm import selectinload

from ..models.policy_models import (
    PolicyPortal, PolicySearchCache, ToolRegistry, ToolUsageStats,
    PortalConfigModel, SearchLevel, PolicySearchResult
)
from ..core.database import get_async_session

import logging

logger = logging.getLogger(__name__)

class PolicyRepository:
    """政策搜索数据访问层"""
    
    def __init__(self):
        self.session_factory = get_async_session
    
    # ==================== 门户配置管理 ====================
    
    async def create_portal(self, portal_config: PortalConfigModel) -> str:
        """创建门户配置"""
        async with self.session_factory() as session:
            try:
                portal_id = str(uuid.uuid4())
                
                portal = PolicyPortal(
                    id=portal_id,
                    name=portal_config.name,
                    region=portal_config.region,
                    level=portal_config.level.value,
                    base_url=portal_config.base_url,
                    search_endpoint=portal_config.search_endpoint,
                    search_params=portal_config.search_params,
                    result_selector=portal_config.result_selector,
                    encoding=portal_config.encoding,
                    timeout_seconds=portal_config.timeout_seconds,
                    max_results=portal_config.max_results,
                    is_active=portal_config.is_active
                )
                
                session.add(portal)
                await session.commit()
                
                return portal_id
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to create portal: {e}")
                raise
    
    async def get_portal_by_id(self, portal_id: str) -> Optional[PortalConfigModel]:
        """根据ID获取门户配置"""
        async with self.session_factory() as session:
            try:
                result = await session.execute(
                    select(PolicyPortal).where(PolicyPortal.id == portal_id)
                )
                portal = result.scalar_one_or_none()
                
                if portal:
                    return self._portal_db_to_model(portal)
                return None
                
            except Exception as e:
                logger.error(f"Failed to get portal by id: {e}")
                return None
    
    async def get_portals_by_level_and_region(self, level: SearchLevel, region: str) -> List[PortalConfigModel]:
        """根据层级和区域获取门户配置"""
        async with self.session_factory() as session:
            try:
                query = select(PolicyPortal).where(
                    and_(
                        PolicyPortal.level == level.value,
                        or_(
                            PolicyPortal.region == region,
                            PolicyPortal.region.like(f"%{region}%")
                        ),
                        PolicyPortal.is_active == True
                    )
                ).order_by(PolicyPortal.name)
                
                result = await session.execute(query)
                portals = result.scalars().all()
                
                return [self._portal_db_to_model(portal) for portal in portals]
                
            except Exception as e:
                logger.error(f"Failed to get portals by level and region: {e}")
                return []
    
    async def get_portals(self, level: Optional[SearchLevel] = None, region: Optional[str] = None) -> List[PortalConfigModel]:
        """获取门户配置列表"""
        async with self.session_factory() as session:
            try:
                query = select(PolicyPortal).where(PolicyPortal.is_active == True)
                
                if level:
                    query = query.where(PolicyPortal.level == level.value)
                
                if region:
                    query = query.where(
                        or_(
                            PolicyPortal.region == region,
                            PolicyPortal.region.like(f"%{region}%")
                        )
                    )
                
                query = query.order_by(PolicyPortal.level, PolicyPortal.name)
                
                result = await session.execute(query)
                portals = result.scalars().all()
                
                return [self._portal_db_to_model(portal) for portal in portals]
                
            except Exception as e:
                logger.error(f"Failed to get portals: {e}")
                return []
    
    async def update_portal(self, portal_id: str, portal_config: PortalConfigModel) -> bool:
        """更新门户配置"""
        async with self.session_factory() as session:
            try:
                query = update(PolicyPortal).where(PolicyPortal.id == portal_id).values(
                    name=portal_config.name,
                    region=portal_config.region,
                    level=portal_config.level.value,
                    base_url=portal_config.base_url,
                    search_endpoint=portal_config.search_endpoint,
                    search_params=portal_config.search_params,
                    result_selector=portal_config.result_selector,
                    encoding=portal_config.encoding,
                    timeout_seconds=portal_config.timeout_seconds,
                    max_results=portal_config.max_results,
                    is_active=portal_config.is_active,
                    updated_at=datetime.now()
                )
                
                result = await session.execute(query)
                await session.commit()
                
                return result.rowcount > 0
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to update portal: {e}")
                return False
    
    async def delete_portal(self, portal_id: str) -> bool:
        """删除门户配置"""
        async with self.session_factory() as session:
            try:
                query = delete(PolicyPortal).where(PolicyPortal.id == portal_id)
                result = await session.execute(query)
                await session.commit()
                
                return result.rowcount > 0
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to delete portal: {e}")
                return False
    
    async def get_all_regions(self) -> List[str]:
        """获取所有支持的区域"""
        async with self.session_factory() as session:
            try:
                result = await session.execute(
                    select(PolicyPortal.region).distinct().where(PolicyPortal.is_active == True)
                )
                regions = result.scalars().all()
                
                return sorted(list(set(regions)))
                
            except Exception as e:
                logger.error(f"Failed to get regions: {e}")
                return []
    
    # ==================== 缓存管理 ====================
    
    async def save_cached_result(
        self,
        cache_key: str,
        query: str,
        region: str,
        strategy: str,
        results: Dict[str, Any],
        result_count: int,
        execution_time_ms: int,
        expires_at: datetime
    ) -> bool:
        """保存缓存结果"""
        async with self.session_factory() as session:
            try:
                cache_entry = PolicySearchCache(
                    id=str(uuid.uuid4()),
                    query_hash=cache_key,
                    query=query,
                    region=region,
                    strategy=strategy,
                    results=results,
                    result_count=result_count,
                    execution_time_ms=execution_time_ms,
                    cache_expires_at=expires_at
                )
                
                session.add(cache_entry)
                await session.commit()
                
                return True
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to save cached result: {e}")
                return False
    
    async def get_cached_result(self, cache_key: str) -> Optional[PolicySearchCache]:
        """获取缓存结果"""
        async with self.session_factory() as session:
            try:
                result = await session.execute(
                    select(PolicySearchCache).where(
                        and_(
                            PolicySearchCache.query_hash == cache_key,
                            PolicySearchCache.cache_expires_at > datetime.now()
                        )
                    )
                )
                
                return result.scalar_one_or_none()
                
            except Exception as e:
                logger.error(f"Failed to get cached result: {e}")
                return None
    
    async def delete_cached_result(self, cache_key: str) -> bool:
        """删除缓存结果"""
        async with self.session_factory() as session:
            try:
                query = delete(PolicySearchCache).where(PolicySearchCache.query_hash == cache_key)
                result = await session.execute(query)
                await session.commit()
                
                return result.rowcount > 0
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to delete cached result: {e}")
                return False
    
    async def cleanup_expired_cache(self) -> int:
        """清理过期缓存"""
        async with self.session_factory() as session:
            try:
                query = delete(PolicySearchCache).where(
                    PolicySearchCache.cache_expires_at <= datetime.now()
                )
                result = await session.execute(query)
                await session.commit()
                
                return result.rowcount
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to cleanup expired cache: {e}")
                return 0
    
    async def get_cache_statistics(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        async with self.session_factory() as session:
            try:
                # 总缓存查询数
                total_result = await session.execute(
                    select(func.count(PolicySearchCache.id))
                )
                total_cached_queries = total_result.scalar() or 0
                
                # 平均搜索时间
                avg_time_result = await session.execute(
                    select(func.avg(PolicySearchCache.execution_time_ms))
                )
                avg_search_time = avg_time_result.scalar() or 0.0
                
                # 最多搜索的区域
                regions_result = await session.execute(
                    select(
                        PolicySearchCache.region,
                        func.count(PolicySearchCache.id).label('count')
                    ).group_by(PolicySearchCache.region).order_by(desc('count')).limit(10)
                )
                most_searched_regions = [
                    {"region": row[0], "count": row[1]}
                    for row in regions_result.fetchall()
                ]
                
                # 过期条目数
                expired_result = await session.execute(
                    select(func.count(PolicySearchCache.id)).where(
                        PolicySearchCache.cache_expires_at <= datetime.now()
                    )
                )
                expired_entries_count = expired_result.scalar() or 0
                
                return {
                    "total_cached_queries": total_cached_queries,
                    "cache_hit_rate": 0.0,  # 需要另外计算
                    "average_search_time_ms": float(avg_search_time),
                    "most_searched_regions": most_searched_regions,
                    "cache_size_mb": 0.0,  # 需要另外计算
                    "expired_entries_count": expired_entries_count
                }
                
            except Exception as e:
                logger.error(f"Failed to get cache statistics: {e}")
                return {
                    "total_cached_queries": 0,
                    "cache_hit_rate": 0.0,
                    "average_search_time_ms": 0.0,
                    "most_searched_regions": [],
                    "cache_size_mb": 0.0,
                    "expired_entries_count": 0
                }
    
    # ==================== 工具使用统计 ====================
    
    async def create_usage_record(self, usage_data: Dict[str, Any]) -> str:
        """创建工具使用记录"""
        async with self.session_factory() as session:
            try:
                usage_id = str(uuid.uuid4())
                
                usage_record = ToolUsageStats(
                    id=usage_id,
                    tool_id=usage_data.get("tool_id"),
                    user_id=usage_data.get("user_id"),
                    session_id=usage_data.get("session_id"),
                    parameters=usage_data.get("parameters", {}),
                    execution_time_ms=usage_data.get("execution_time_ms"),
                    status=usage_data.get("status"),
                    error_message=usage_data.get("error_message"),
                    result_summary=usage_data.get("result_summary")
                )
                
                session.add(usage_record)
                await session.commit()
                
                return usage_id
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to create usage record: {e}")
                raise
    
    async def get_tool_stats(self, tool_id: str, days: int = 30) -> Dict[str, Any]:
        """获取工具统计信息"""
        async with self.session_factory() as session:
            try:
                since_date = datetime.now() - timedelta(days=days)
                
                # 总调用次数
                total_calls_result = await session.execute(
                    select(func.count(ToolUsageStats.id)).where(
                        and_(
                            ToolUsageStats.tool_id == tool_id,
                            ToolUsageStats.created_at >= since_date
                        )
                    )
                )
                total_calls = total_calls_result.scalar() or 0
                
                # 成功调用次数
                success_calls_result = await session.execute(
                    select(func.count(ToolUsageStats.id)).where(
                        and_(
                            ToolUsageStats.tool_id == tool_id,
                            ToolUsageStats.status == "success",
                            ToolUsageStats.created_at >= since_date
                        )
                    )
                )
                success_calls = success_calls_result.scalar() or 0
                
                # 平均执行时间
                avg_time_result = await session.execute(
                    select(func.avg(ToolUsageStats.execution_time_ms)).where(
                        and_(
                            ToolUsageStats.tool_id == tool_id,
                            ToolUsageStats.status == "success",
                            ToolUsageStats.created_at >= since_date
                        )
                    )
                )
                avg_execution_time = avg_time_result.scalar() or 0.0
                
                # 最后调用时间
                last_called_result = await session.execute(
                    select(func.max(ToolUsageStats.created_at)).where(
                        ToolUsageStats.tool_id == tool_id
                    )
                )
                last_called_at = last_called_result.scalar()
                
                error_calls = total_calls - success_calls
                success_rate = (success_calls / total_calls) if total_calls > 0 else 0.0
                
                return {
                    "tool_id": tool_id,
                    "total_calls": total_calls,
                    "success_calls": success_calls,
                    "error_calls": error_calls,
                    "average_execution_time_ms": float(avg_execution_time),
                    "success_rate": success_rate,
                    "last_called_at": last_called_at,
                    "period_days": days
                }
                
            except Exception as e:
                logger.error(f"Failed to get tool stats: {e}")
                return {
                    "tool_id": tool_id,
                    "total_calls": 0,
                    "success_calls": 0,
                    "error_calls": 0,
                    "average_execution_time_ms": 0.0,
                    "success_rate": 0.0,
                    "last_called_at": None,
                    "period_days": days
                }
    
    # ==================== 工具注册管理 ====================
    
    async def register_tool(self, tool_data: Dict[str, Any]) -> str:
        """注册工具"""
        async with self.session_factory() as session:
            try:
                tool_id = str(uuid.uuid4())
                
                tool = ToolRegistry(
                    id=tool_id,
                    name=tool_data["name"],
                    display_name=tool_data["display_name"],
                    description=tool_data.get("description"),
                    category=tool_data["category"],
                    tool_type=tool_data["tool_type"],
                    version=tool_data.get("version", "1.0.0"),
                    status=tool_data.get("status", "active"),
                    config=tool_data.get("config", {}),
                    metadata=tool_data.get("metadata", {})
                )
                
                session.add(tool)
                await session.commit()
                
                return tool_id
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to register tool: {e}")
                raise
    
    async def get_tool_by_name(self, tool_name: str) -> Optional[ToolRegistry]:
        """根据名称获取工具"""
        async with self.session_factory() as session:
            try:
                result = await session.execute(
                    select(ToolRegistry).where(ToolRegistry.name == tool_name)
                )
                return result.scalar_one_or_none()
                
            except Exception as e:
                logger.error(f"Failed to get tool by name: {e}")
                return None
    
    async def get_tools_by_category(self, category: str) -> List[ToolRegistry]:
        """根据分类获取工具列表"""
        async with self.session_factory() as session:
            try:
                result = await session.execute(
                    select(ToolRegistry).where(
                        and_(
                            ToolRegistry.category == category,
                            ToolRegistry.status == "active"
                        )
                    ).order_by(ToolRegistry.name)
                )
                return result.scalars().all()
                
            except Exception as e:
                logger.error(f"Failed to get tools by category: {e}")
                return []
    
    def _portal_db_to_model(self, portal: PolicyPortal) -> PortalConfigModel:
        """数据库模型转换为Pydantic模型"""
        return PortalConfigModel(
            id=portal.id,
            name=portal.name,
            region=portal.region,
            level=SearchLevel(portal.level),
            base_url=portal.base_url,
            search_endpoint=portal.search_endpoint,
            search_params=portal.search_params,
            result_selector=portal.result_selector,
            encoding=portal.encoding,
            timeout_seconds=portal.timeout_seconds,
            max_results=portal.max_results,
            is_active=portal.is_active
        )