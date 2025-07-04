"""
数据库健康检查服务
定期检查所有数据库的健康状态并提供监控接口
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass

from ..connections.database_manager import DatabaseConnectionManager, get_database_manager
from ...config.database_config import DatabaseType, DatabaseStatus, get_database_config

logger = logging.getLogger(__name__)


@dataclass
class HealthCheckResult:
    """健康检查结果"""
    database_type: DatabaseType
    status: DatabaseStatus
    response_time: float
    error_message: Optional[str] = None
    last_check: Optional[datetime] = None


class DatabaseHealthChecker:
    """数据库健康检查器"""
    
    def __init__(self, db_manager: DatabaseConnectionManager):
        self.db_manager = db_manager
        self.config = get_database_config()
        self.health_history: Dict[DatabaseType, List[HealthCheckResult]] = {}
        self.current_status: Dict[DatabaseType, HealthCheckResult] = {}
        self.check_task: Optional[asyncio.Task] = None
        self.is_running = False
        
        # 初始化健康历史记录
        for db_type in DatabaseType:
            self.health_history[db_type] = []
    
    async def start_health_monitoring(self):
        """启动健康监控"""
        if self.is_running:
            logger.warning("健康监控已经在运行中")
            return
        
        self.is_running = True
        self.check_task = asyncio.create_task(self._health_check_loop())
        logger.info("数据库健康监控已启动")
    
    async def stop_health_monitoring(self):
        """停止健康监控"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.check_task:
            self.check_task.cancel()
            try:
                await self.check_task
            except asyncio.CancelledError:
                pass
        
        logger.info("数据库健康监控已停止")
    
    async def _health_check_loop(self):
        """健康检查循环"""
        while self.is_running:
            try:
                await self.check_all_databases()
                await asyncio.sleep(self.config.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"健康检查循环出错: {e}")
                await asyncio.sleep(10)  # 出错后等待10秒再继续
    
    async def check_all_databases(self) -> Dict[DatabaseType, HealthCheckResult]:
        """检查所有数据库的健康状态"""
        results = {}
        
        # 并行检查所有数据库
        tasks = [
            self._check_single_database(db_type) 
            for db_type in DatabaseType
        ]
        
        check_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for db_type, result in zip(DatabaseType, check_results):
            if isinstance(result, Exception):
                health_result = HealthCheckResult(
                    database_type=db_type,
                    status=DatabaseStatus.UNHEALTHY,
                    response_time=0.0,
                    error_message=str(result),
                    last_check=datetime.now()
                )
            else:
                health_result = result
            
            results[db_type] = health_result
            self.current_status[db_type] = health_result
            self._add_to_history(health_result)
        
        return results
    
    async def _check_single_database(self, db_type: DatabaseType) -> HealthCheckResult:
        """检查单个数据库"""
        start_time = datetime.now()
        
        try:
            if db_type == DatabaseType.POSTGRESQL:
                async with self.db_manager.get_postgresql_connection() as conn:
                    await conn.execute("SELECT 1")
            
            elif db_type == DatabaseType.ELASTICSEARCH:
                client = await self.db_manager.get_elasticsearch_client()
                await client.ping()
            
            elif db_type == DatabaseType.MILVUS:
                client = await self.db_manager.get_milvus_client()
                client.list_collections()
            
            elif db_type == DatabaseType.REDIS:
                client = await self.db_manager.get_redis_client()
                await client.ping()
            
            elif db_type == DatabaseType.NACOS:
                client = await self.db_manager.get_nacos_client()
                # Nacos健康检查 - 尝试获取配置
                try:
                    client.get_config("health_check", self.config.nacos.group)
                except Exception:
                    pass  # 配置可能不存在，但连接正常
            
            elif db_type == DatabaseType.RABBITMQ:
                connection = await self.db_manager.get_rabbitmq_connection()
                if connection.is_closed:
                    raise Exception("RabbitMQ连接已关闭")
            
            # 计算响应时间
            response_time = (datetime.now() - start_time).total_seconds()
            
            return HealthCheckResult(
                database_type=db_type,
                status=DatabaseStatus.HEALTHY,
                response_time=response_time,
                last_check=datetime.now()
            )
            
        except Exception as e:
            response_time = (datetime.now() - start_time).total_seconds()
            
            return HealthCheckResult(
                database_type=db_type,
                status=DatabaseStatus.UNHEALTHY,
                response_time=response_time,
                error_message=str(e),
                last_check=datetime.now()
            )
    
    def _add_to_history(self, result: HealthCheckResult):
        """添加健康检查结果到历史记录"""
        history = self.health_history[result.database_type]
        history.append(result)
        
        # 保持最近100条记录
        if len(history) > 100:
            history.pop(0)
    
    def get_current_status(self) -> Dict[str, Any]:
        """获取当前健康状态"""
        return {
            "timestamp": datetime.now().isoformat(),
            "overall_status": self._get_overall_status(),
            "databases": {
                db_type.value: {
                    "status": result.status.value,
                    "response_time": result.response_time,
                    "error_message": result.error_message,
                    "last_check": result.last_check.isoformat() if result.last_check else None
                }
                for db_type, result in self.current_status.items()
            }
        }
    
    def _get_overall_status(self) -> str:
        """获取整体健康状态"""
        if not self.current_status:
            return "unknown"
        
        unhealthy_count = sum(
            1 for result in self.current_status.values() 
            if result.status == DatabaseStatus.UNHEALTHY
        )
        
        if unhealthy_count == 0:
            return "healthy"
        elif unhealthy_count == len(self.current_status):
            return "unhealthy"
        else:
            return "degraded"
    
    def get_database_status(self, db_type: DatabaseType) -> Optional[HealthCheckResult]:
        """获取指定数据库的健康状态"""
        return self.current_status.get(db_type)
    
    def get_health_history(self, db_type: DatabaseType, limit: int = 10) -> List[HealthCheckResult]:
        """获取数据库健康历史记录"""
        history = self.health_history.get(db_type, [])
        return history[-limit:] if history else []
    
    def get_health_summary(self) -> Dict[str, Any]:
        """获取健康状态摘要"""
        summary = {
            "total_databases": len(DatabaseType),
            "healthy_count": 0,
            "unhealthy_count": 0,
            "degraded_count": 0,
            "average_response_time": 0.0,
            "last_check": None
        }
        
        if not self.current_status:
            return summary
        
        healthy_count = 0
        unhealthy_count = 0
        total_response_time = 0.0
        latest_check = None
        
        for result in self.current_status.values():
            if result.status == DatabaseStatus.HEALTHY:
                healthy_count += 1
            else:
                unhealthy_count += 1
            
            total_response_time += result.response_time
            
            if latest_check is None or (result.last_check and result.last_check > latest_check):
                latest_check = result.last_check
        
        summary.update({
            "healthy_count": healthy_count,
            "unhealthy_count": unhealthy_count,
            "average_response_time": total_response_time / len(self.current_status),
            "last_check": latest_check.isoformat() if latest_check else None
        })
        
        return summary
    
    def get_alerts(self) -> List[Dict[str, Any]]:
        """获取健康检查警报"""
        alerts = []
        
        for db_type, result in self.current_status.items():
            if result.status == DatabaseStatus.UNHEALTHY:
                alerts.append({
                    "type": "database_unhealthy",
                    "database": db_type.value,
                    "message": f"{db_type.value} 数据库不健康",
                    "error": result.error_message,
                    "timestamp": result.last_check.isoformat() if result.last_check else None
                })
            
            # 响应时间过长警告
            if result.response_time > self.config.health_check_timeout:
                alerts.append({
                    "type": "slow_response",
                    "database": db_type.value,
                    "message": f"{db_type.value} 数据库响应时间过长",
                    "response_time": result.response_time,
                    "timestamp": result.last_check.isoformat() if result.last_check else None
                })
        
        return alerts


# 全局健康检查器实例
_health_checker: Optional[DatabaseHealthChecker] = None


async def get_health_checker() -> DatabaseHealthChecker:
    """获取健康检查器实例"""
    global _health_checker
    if _health_checker is None:
        db_manager = await get_database_manager()
        _health_checker = DatabaseHealthChecker(db_manager)
        await _health_checker.start_health_monitoring()
    return _health_checker


async def stop_health_checker():
    """停止健康检查器"""
    global _health_checker
    if _health_checker:
        await _health_checker.stop_health_monitoring()
        _health_checker = None 