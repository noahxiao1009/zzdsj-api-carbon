"""
数据库管理微服务API
提供数据库连接、健康检查、配置管理等接口
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any, Optional, List
import logging

from ..core.connections.database_manager import get_database_manager, DatabaseConnectionManager
from ..core.health.health_checker import get_health_checker, DatabaseHealthChecker
from ..services.gateway_registry import get_gateway_registry, GatewayRegistry
from ..config.database_config import DatabaseType, get_database_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/database", tags=["database"])


@router.get("/health")
async def health_check():
    """服务健康检查"""
    try:
        health_checker = await get_health_checker()
        status = health_checker.get_current_status()
        
        return {
            "status": "healthy" if status["overall_status"] == "healthy" else "unhealthy",
            "timestamp": status["timestamp"],
            "details": status
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        raise HTTPException(status_code=500, detail="健康检查失败")


@router.get("/status")
async def get_database_status():
    """获取所有数据库状态"""
    try:
        health_checker = await get_health_checker()
        status = health_checker.get_current_status()
        summary = health_checker.get_health_summary()
        alerts = health_checker.get_alerts()
        
        return {
            "status": status,
            "summary": summary,
            "alerts": alerts
        }
    except Exception as e:
        logger.error(f"获取数据库状态失败: {e}")
        raise HTTPException(status_code=500, detail="获取状态失败")


@router.get("/status/{database_type}")
async def get_single_database_status(database_type: str):
    """获取单个数据库状态"""
    try:
        # 验证数据库类型
        try:
            db_type = DatabaseType(database_type.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"不支持的数据库类型: {database_type}")
        
        health_checker = await get_health_checker()
        result = health_checker.get_database_status(db_type)
        
        if not result:
            raise HTTPException(status_code=404, detail=f"未找到 {database_type} 的状态信息")
        
        return {
            "database_type": result.database_type.value,
            "status": result.status.value,
            "response_time": result.response_time,
            "error_message": result.error_message,
            "last_check": result.last_check.isoformat() if result.last_check else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取数据库 {database_type} 状态失败: {e}")
        raise HTTPException(status_code=500, detail="获取状态失败")


@router.get("/connections")
async def get_connection_info():
    """获取连接信息"""
    try:
        db_manager = await get_database_manager()
        status_summary = db_manager.get_status_summary()
        
        config = get_database_config()
        
        connection_info = {
            "service_name": config.service_name,
            "service_port": config.service_port,
            "databases": status_summary,
            "configurations": {
                "postgresql": {
                    "host": config.postgresql.host,
                    "port": config.postgresql.port,
                    "database": config.postgresql.database,
                    "max_connections": config.postgresql.max_connections
                },
                "elasticsearch": {
                    "hosts": config.elasticsearch.hosts,
                    "timeout": config.elasticsearch.timeout
                },
                "milvus": {
                    "host": config.milvus.host,
                    "port": config.milvus.port,
                    "default_dimension": config.milvus.default_dimension
                },
                "redis": {
                    "host": config.redis.host,
                    "port": config.redis.port,
                    "db": config.redis.db,
                    "cluster_enabled": config.redis.cluster_enabled
                },
                "rabbitmq": {
                    "host": config.rabbitmq.host,
                    "port": config.rabbitmq.port,
                    "virtual_host": config.rabbitmq.virtual_host
                }
            }
        }
        
        return connection_info
    except Exception as e:
        logger.error(f"获取连接信息失败: {e}")
        raise HTTPException(status_code=500, detail="获取连接信息失败")


@router.post("/connections/test/{database_type}")
async def test_database_connection(database_type: str):
    """测试数据库连接"""
    try:
        # 验证数据库类型
        try:
            db_type = DatabaseType(database_type.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"不支持的数据库类型: {database_type}")
        
        health_checker = await get_health_checker()
        
        # 执行单个数据库健康检查
        result = await health_checker._check_single_database(db_type)
        
        return {
            "database_type": result.database_type.value,
            "test_result": "success" if result.status.value == "healthy" else "failed",
            "response_time": result.response_time,
            "error_message": result.error_message,
            "timestamp": result.last_check.isoformat() if result.last_check else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"测试数据库 {database_type} 连接失败: {e}")
        raise HTTPException(status_code=500, detail="连接测试失败")


@router.get("/config")
async def get_service_config():
    """获取服务配置"""
    try:
        config = get_database_config()
        
        # 返回配置信息（隐藏敏感信息）
        config_data = {
            "service_name": config.service_name,
            "service_port": config.service_port,
            "debug": config.debug,
            "health_check_enabled": config.health_check_enabled,
            "health_check_interval": config.health_check_interval,
            "monitoring_enabled": config.monitoring_enabled,
            "gateway_enabled": config.gateway_enabled,
            "gateway_url": config.gateway_url,
            "databases": {
                "postgresql": {
                    "host": config.postgresql.host,
                    "port": config.postgresql.port,
                    "database": config.postgresql.database,
                    "max_connections": config.postgresql.max_connections
                },
                "elasticsearch": {
                    "hosts": config.elasticsearch.hosts,
                    "timeout": config.elasticsearch.timeout,
                    "max_retries": config.elasticsearch.max_retries
                },
                "milvus": {
                    "host": config.milvus.host,
                    "port": config.milvus.port,
                    "default_dimension": config.milvus.default_dimension
                },
                "redis": {
                    "host": config.redis.host,
                    "port": config.redis.port,
                    "db": config.redis.db,
                    "cluster_enabled": config.redis.cluster_enabled
                },
                "nacos": {
                    "server_addresses": config.nacos.server_addresses,
                    "namespace": config.nacos.namespace,
                    "group": config.nacos.group,
                    "service_name": config.nacos.service_name
                },
                "rabbitmq": {
                    "host": config.rabbitmq.host,
                    "port": config.rabbitmq.port,
                    "virtual_host": config.rabbitmq.virtual_host
                }
            }
        }
        
        return config_data
    except Exception as e:
        logger.error(f"获取服务配置失败: {e}")
        raise HTTPException(status_code=500, detail="获取配置失败")


@router.get("/registry/status")
async def get_registry_status():
    """获取网关注册状态"""
    try:
        registry = await get_gateway_registry()
        service_info = await registry.get_service_info()
        
        return service_info
    except Exception as e:
        logger.error(f"获取注册状态失败: {e}")
        raise HTTPException(status_code=500, detail="获取注册状态失败")


@router.post("/registry/update")
async def update_registry_metadata(metadata: Dict[str, Any]):
    """更新注册元数据"""
    try:
        registry = await get_gateway_registry()
        await registry.update_service_metadata(metadata)
        
        return {"message": "元数据更新成功"}
    except Exception as e:
        logger.error(f"更新注册元数据失败: {e}")
        raise HTTPException(status_code=500, detail="更新元数据失败")


@router.get("/metrics")
async def get_metrics():
    """获取监控指标"""
    try:
        health_checker = await get_health_checker()
        db_manager = await get_database_manager()
        
        status = health_checker.get_current_status()
        summary = health_checker.get_health_summary()
        db_status = db_manager.get_status_summary()
        
        metrics = {
            "timestamp": status["timestamp"],
            "overall_status": status["overall_status"],
            "database_count": summary["total_databases"],
            "healthy_databases": summary["healthy_count"],
            "unhealthy_databases": summary["unhealthy_count"],
            "average_response_time": summary["average_response_time"],
            "uptime_percentage": (summary["healthy_count"] / summary["total_databases"]) * 100 if summary["total_databases"] > 0 else 0,
            "database_details": status["databases"],
            "connection_status": db_status
        }
        
        return metrics
    except Exception as e:
        logger.error(f"获取监控指标失败: {e}")
        raise HTTPException(status_code=500, detail="获取指标失败")


@router.get("/history/{database_type}")
async def get_health_history(
    database_type: str, 
    limit: int = Query(10, ge=1, le=100, description="返回记录数量")
):
    """获取数据库健康历史记录"""
    try:
        # 验证数据库类型
        try:
            db_type = DatabaseType(database_type.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"不支持的数据库类型: {database_type}")
        
        health_checker = await get_health_checker()
        history = health_checker.get_health_history(db_type, limit)
        
        history_data = [
            {
                "status": record.status.value,
                "response_time": record.response_time,
                "error_message": record.error_message,
                "timestamp": record.last_check.isoformat() if record.last_check else None
            }
            for record in history
        ]
        
        return {
            "database_type": database_type,
            "total_records": len(history_data),
            "history": history_data
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取数据库 {database_type} 历史记录失败: {e}")
        raise HTTPException(status_code=500, detail="获取历史记录失败")


@router.get("/alerts")
async def get_alerts():
    """获取系统警报"""
    try:
        health_checker = await get_health_checker()
        alerts = health_checker.get_alerts()
        
        return {
            "total_alerts": len(alerts),
            "alerts": alerts
        }
    except Exception as e:
        logger.error(f"获取系统警报失败: {e}")
        raise HTTPException(status_code=500, detail="获取警报失败") 