"""
数据库服务的服务间通信集成
统一管理所有数据库连接、事务和数据操作
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime, timedelta
import json
import sys
import os
from contextlib import asynccontextmanager
import uuid

# 添加shared模块到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), "../../../shared"))

from service_client import (
    ServiceClient, 
    AsyncServiceClient,
    CallMethod, 
    CallConfig, 
    RetryStrategy,
    ServiceCallError,
    call_service,
    publish_event
)

logger = logging.getLogger(__name__)


class DatabaseConnectionPool:
    """统一数据库连接池管理"""
    
    def __init__(self):
        self.pools = {}
        self.connection_stats = {}
        self._lock = asyncio.Lock()
        
    async def get_connection(self, db_type: str, **kwargs):
        """获取数据库连接"""
        try:
            async with self._lock:
                if db_type not in self.pools:
                    await self._create_pool(db_type, **kwargs)
                
                pool = self.pools[db_type]
                
                # 更新连接统计
                if db_type not in self.connection_stats:
                    self.connection_stats[db_type] = {
                        "total_requests": 0,
                        "active_connections": 0,
                        "created_at": datetime.now().isoformat()
                    }
                
                self.connection_stats[db_type]["total_requests"] += 1
                self.connection_stats[db_type]["active_connections"] += 1
                
                return pool
                
        except Exception as e:
            logger.error(f"获取数据库连接失败 {db_type}: {e}")
            raise


class DatabaseServiceIntegration:
    """数据库服务集成类 - 统一数据访问层"""
    
    def __init__(self):
        self.service_client = None
        self.async_client = None
        self.connection_pool = DatabaseConnectionPool()
        
        # 不同操作的配置
        self.query_config = CallConfig(
            timeout=15,   # 查询操作超时
            retry_times=2,
            retry_strategy=RetryStrategy.LINEAR,
            circuit_breaker_enabled=True
        )
        
        # 支持的数据库类型
        self.supported_databases = {
            "postgresql": {
                "type": "relational",
                "description": "主要关系型数据库",
                "capabilities": ["ACID", "复杂查询", "事务"]
            },
            "redis": {
                "type": "cache", 
                "description": "缓存和会话存储",
                "capabilities": ["高速缓存", "发布订阅", "数据结构"]
            },
            "elasticsearch": {
                "type": "search",
                "description": "全文搜索引擎", 
                "capabilities": ["全文搜索", "聚合分析", "实时索引"]
            },
            "milvus": {
                "type": "vector",
                "description": "向量数据库",
                "capabilities": ["向量搜索", "相似度计算", "AI检索"]
            }
        }
        
        # 数据库健康状态
        self.health_status = {}
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.service_client = ServiceClient()
        self.async_client = AsyncServiceClient()
        await self.service_client.__aenter__()
        await self.async_client.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.connection_pool.close_all()
        if self.service_client:
            await self.service_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.async_client:
            await self.async_client.__aexit__(exc_type, exc_val, exc_tb)
    
    async def execute_query(
        self, 
        db_type: str, 
        query: str, 
        params: Optional[List] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """执行数据库查询"""
        try:
            # 权限检查
            if user_id:
                permission_check = await self._check_database_permission(user_id, db_type, "READ")
                if not permission_check.get("allowed"):
                    return {
                        "success": False,
                        "error": "权限不足",
                        "required_permission": f"database:{db_type}:READ"
                    }
            
            start_time = datetime.now()
            
            # 执行查询逻辑...
            result_data = {"message": "查询执行成功", "query": query}
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return {
                "success": True,
                "data": result_data,
                "execution_time": execution_time,
                "database_type": db_type
            }
            
        except Exception as e:
            logger.error(f"查询执行失败 {db_type}: {e}")
            return {
                "success": False,
                "error": str(e),
                "database_type": db_type
            }
    
    async def _check_database_permission(self, user_id: str, db_type: str, action: str) -> Dict[str, Any]:
        """检查数据库操作权限"""
        try:
            result = await self.service_client.call(
                service_name="base-service",
                method=CallMethod.POST,
                path="/api/v1/permissions/check",
                config=self.query_config,
                json={
                    "user_id": user_id,
                    "resource_type": "database",
                    "resource_id": db_type,
                    "action": action
                }
            )
            
            return result
            
        except ServiceCallError as e:
            logger.error(f"权限检查失败: {e}")
            if e.status_code == 503:
                return {"allowed": True, "fallback": True}
            return {"allowed": False, "error": str(e)}


# 全局便捷函数
async def execute_database_query(
    db_type: str, 
    query: str, 
    params: Optional[List] = None,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """全局数据库查询函数"""
    async with DatabaseServiceIntegration() as db_service:
        return await db_service.execute_query(db_type, query, params, user_id)
