"""
模型服务监控和管理API
提供完整的模型调用统计、监控和管理功能
"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime, timedelta
import asyncio

from ..services.usage_monitor import usage_monitor, TimeWindow
from ..services.model_manager import model_manager
from ..services.service_integration import ModelServiceIntegration
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
monitoring_router = APIRouter(prefix="/api/v1/models", tags=["模型监控管理"])

# 请求模型定义
class UsageStatsRequest(BaseModel):
    """使用统计请求"""
    user_id: Optional[str] = Field(None, description="用户ID筛选")
    provider_id: Optional[str] = Field(None, description="提供商ID筛选")
    model_id: Optional[str] = Field(None, description="模型ID筛选")
    time_window: TimeWindow = Field(TimeWindow.DAY, description="时间窗口")
    start_time: Optional[datetime] = Field(None, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")

class AlertRule(BaseModel):
    """告警规则"""
    name: str = Field(..., description="规则名称")
    metric_type: str = Field(..., description="指标类型")
    threshold: float = Field(..., description="阈值")
    operator: str = Field(..., description="操作符: >, <, >=, <=, ==")
    duration: int = Field(300, description="持续时间(秒)")
    enabled: bool = Field(True, description="是否启用")
    notification_channels: List[str] = Field([], description="通知渠道")

# ==================== 使用统计接口 ====================

@monitoring_router.post("/usage/stats")
async def get_usage_statistics(request: UsageStatsRequest):
    """
    获取详细的使用统计
    """
    try:
        stats = await usage_monitor.get_usage_stats(
            user_id=request.user_id,
            provider_id=request.provider_id,
            model_id=request.model_id,
            time_window=request.time_window,
            start_time=request.start_time,
            end_time=request.end_time
        )
        
        return {
            "success": True,
            "data": stats
        }
        
    except Exception as e:
        logger.error(f"获取使用统计失败: {e}")
        raise HTTPException(status_code=500, detail="获取使用统计失败")

@monitoring_router.get("/usage/realtime")
async def get_realtime_metrics():
    """
    获取实时指标
    """
    try:
        metrics = await usage_monitor.get_realtime_metrics()
        
        return {
            "success": True,
            "data": metrics
        }
        
    except Exception as e:
        logger.error(f"获取实时指标失败: {e}")
        raise HTTPException(status_code=500, detail="获取实时指标失败")

@monitoring_router.get("/usage/top-models")
async def get_top_models(limit: int = Query(10, description="返回数量限制")):
    """
    获取使用最多的模型
    """
    try:
        top_models = await usage_monitor.get_top_models(limit=limit)
        
        return {
            "success": True,
            "data": {
                "models": top_models,
                "total": len(top_models),
                "limit": limit
            }
        }
        
    except Exception as e:
        logger.error(f"获取热门模型失败: {e}")
        raise HTTPException(status_code=500, detail="获取热门模型失败")

@monitoring_router.get("/usage/export")
async def export_usage_data(
    format_type: str = Query("json", description="导出格式: json, csv"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间")
):
    """
    导出使用数据
    """
    try:
        data = await usage_monitor.export_usage_data(
            format_type=format_type,
            start_time=start_time,
            end_time=end_time
        )
        
        # 设置响应头
        filename = f"model_usage_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}"
        media_type = "application/json" if format_type == "json" else "text/csv"
        
        from fastapi.responses import Response
        return Response(
            content=data,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"导出使用数据失败: {e}")
        raise HTTPException(status_code=500, detail="导出使用数据失败")

# ==================== 模型管理接口 ====================

@monitoring_router.get("/management/statistics")
async def get_model_statistics():
    """
    获取模型管理统计信息
    """
    try:
        stats = await model_manager.get_model_statistics()
        
        return {
            "success": True,
            "data": stats
        }
        
    except Exception as e:
        logger.error(f"获取模型统计失败: {e}")
        raise HTTPException(status_code=500, detail="获取模型统计失败")

@monitoring_router.get("/management/defaults")
async def get_all_default_models():
    """
    获取所有默认模型配置
    """
    try:
        from ..schemas.model_provider import ModelType
        
        defaults = {}
        for model_type in ModelType:
            system_default = await model_manager.get_default_model(model_type)
            defaults[model_type] = system_default
        
        return {
            "success": True,
            "data": {
                "defaults": defaults,
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"获取默认模型配置失败: {e}")
        raise HTTPException(status_code=500, detail="获取默认模型配置失败")

@monitoring_router.put("/management/defaults/{model_type}")
async def set_system_default_model(
    model_type: str,
    provider_id: str = Query(..., description="提供商ID"),
    model_id: str = Query(..., description="模型ID"),
    config: Optional[Dict[str, Any]] = None
):
    """
    设置系统级默认模型
    """
    try:
        from ..schemas.model_provider import ModelType
        
        # 验证模型类型
        try:
            model_type_enum = ModelType(model_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的模型类型: {model_type}")
        
        success = await model_manager.set_system_default_model(
            model_type=model_type_enum,
            provider_id=provider_id,
            model_id=model_id,
            config=config or {}
        )
        
        if success:
            return {
                "success": True,
                "message": f"系统默认模型设置成功: {model_type}",
                "data": {
                    "model_type": model_type,
                    "provider_id": provider_id,
                    "model_id": model_id,
                    "config": config
                }
            }
        else:
            raise HTTPException(status_code=500, detail="设置系统默认模型失败")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"设置系统默认模型失败: {e}")
        raise HTTPException(status_code=500, detail="设置系统默认模型失败")

@monitoring_router.get("/management/user-preferences/{user_id}")
async def get_user_model_preferences(user_id: str):
    """
    获取用户模型偏好设置
    """
    try:
        preferences = await model_manager.get_user_model_preferences(user_id)
        
        return {
            "success": True,
            "data": preferences
        }
        
    except Exception as e:
        logger.error(f"获取用户模型偏好失败: {e}")
        raise HTTPException(status_code=500, detail="获取用户模型偏好失败")

# ==================== 服务健康监控接口 ====================

@monitoring_router.get("/health/detailed")
async def get_detailed_health_status():
    """
    获取详细的服务健康状态
    """
    try:
        async with ModelServiceIntegration() as integration:
            health_report = await integration.get_system_health_report()
        
        # 添加模型服务特有的健康检查
        model_stats = await model_manager.get_model_statistics()
        realtime_metrics = await usage_monitor.get_realtime_metrics()
        
        health_report["model_service_status"] = {
            "total_providers": model_stats["total_providers"],
            "configured_providers": model_stats["configured_providers"],
            "enabled_models": model_stats["enabled_models"],
            "active_records": realtime_metrics.get("active_records", 0),
            "last_call": realtime_metrics.get("last_updated"),
            "error_rate": realtime_metrics.get("error_rate", 0.0)
        }
        
        return {
            "success": True,
            "data": health_report
        }
        
    except Exception as e:
        logger.error(f"获取详细健康状态失败: {e}")
        raise HTTPException(status_code=500, detail="获取详细健康状态失败")

@monitoring_router.get("/health/dependencies")
async def check_service_dependencies():
    """
    检查服务依赖状态
    """
    try:
        async with ModelServiceIntegration() as integration:
            dependency_health = await integration.health_check_dependencies()
        
        return {
            "success": True,
            "data": {
                "dependencies": dependency_health,
                "overall_healthy": all(dependency_health.values()),
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"检查服务依赖失败: {e}")
        raise HTTPException(status_code=500, detail="检查服务依赖失败")

# ==================== 性能监控接口 ====================

@monitoring_router.get("/performance/metrics")
async def get_performance_metrics():
    """
    获取性能指标
    """
    try:
        async with ModelServiceIntegration() as integration:
            service_metrics = await integration.get_service_metrics()
        
        realtime_metrics = await usage_monitor.get_realtime_metrics()
        
        # 合并指标
        performance_metrics = {
            "service_metrics": service_metrics,
            "usage_metrics": realtime_metrics,
            "timestamp": datetime.now().isoformat()
        }
        
        return {
            "success": True,
            "data": performance_metrics
        }
        
    except Exception as e:
        logger.error(f"获取性能指标失败: {e}")
        raise HTTPException(status_code=500, detail="获取性能指标失败")

@monitoring_router.get("/performance/latency-analysis")
async def get_latency_analysis(
    provider_id: Optional[str] = Query(None, description="提供商ID筛选"),
    model_id: Optional[str] = Query(None, description="模型ID筛选"),
    time_window: TimeWindow = Query(TimeWindow.HOUR, description="时间窗口")
):
    """
    获取延迟分析
    """
    try:
        # 获取使用统计数据
        stats = await usage_monitor.get_usage_stats(
            provider_id=provider_id,
            model_id=model_id,
            time_window=time_window
        )
        
        # 分析延迟数据
        time_series = stats.get("time_series", [])
        latencies = [point["avg_latency"] for point in time_series if point["avg_latency"] > 0]
        
        if latencies:
            latencies.sort()
            n = len(latencies)
            
            analysis = {
                "min_latency": min(latencies),
                "max_latency": max(latencies),
                "avg_latency": sum(latencies) / n,
                "median_latency": latencies[n // 2],
                "p95_latency": latencies[int(n * 0.95)] if n > 0 else 0,
                "p99_latency": latencies[int(n * 0.99)] if n > 0 else 0,
                "sample_count": n
            }
        else:
            analysis = {
                "min_latency": 0,
                "max_latency": 0,
                "avg_latency": 0,
                "median_latency": 0,
                "p95_latency": 0,
                "p99_latency": 0,
                "sample_count": 0
            }
        
        return {
            "success": True,
            "data": {
                "analysis": analysis,
                "time_series": time_series,
                "filters": {
                    "provider_id": provider_id,
                    "model_id": model_id,
                    "time_window": time_window
                }
            }
        }
        
    except Exception as e:
        logger.error(f"获取延迟分析失败: {e}")
        raise HTTPException(status_code=500, detail="获取延迟分析失败")

# ==================== 告警管理接口 ====================

# 内存存储告警规则（实际项目中应该使用数据库）
alert_rules_db: Dict[str, Dict] = {}

@monitoring_router.post("/alerts/rules")
async def create_alert_rule(rule: AlertRule):
    """
    创建告警规则
    """
    try:
        import uuid
        
        rule_id = str(uuid.uuid4())
        
        rule_data = {
            "id": rule_id,
            "name": rule.name,
            "metric_type": rule.metric_type,
            "threshold": rule.threshold,
            "operator": rule.operator,
            "duration": rule.duration,
            "enabled": rule.enabled,
            "notification_channels": rule.notification_channels,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "last_triggered": None,
            "trigger_count": 0
        }
        
        alert_rules_db[rule_id] = rule_data
        
        return {
            "success": True,
            "message": "告警规则创建成功",
            "data": rule_data
        }
        
    except Exception as e:
        logger.error(f"创建告警规则失败: {e}")
        raise HTTPException(status_code=500, detail="创建告警规则失败")

@monitoring_router.get("/alerts/rules")
async def get_alert_rules():
    """
    获取所有告警规则
    """
    try:
        rules = list(alert_rules_db.values())
        
        return {
            "success": True,
            "data": {
                "rules": rules,
                "total": len(rules)
            }
        }
        
    except Exception as e:
        logger.error(f"获取告警规则失败: {e}")
        raise HTTPException(status_code=500, detail="获取告警规则失败")

@monitoring_router.put("/alerts/rules/{rule_id}")
async def update_alert_rule(rule_id: str, rule: AlertRule):
    """
    更新告警规则
    """
    try:
        if rule_id not in alert_rules_db:
            raise HTTPException(status_code=404, detail="告警规则不存在")
        
        rule_data = alert_rules_db[rule_id]
        
        # 更新规则
        rule_data.update({
            "name": rule.name,
            "metric_type": rule.metric_type,
            "threshold": rule.threshold,
            "operator": rule.operator,
            "duration": rule.duration,
            "enabled": rule.enabled,
            "notification_channels": rule.notification_channels,
            "updated_at": datetime.now().isoformat()
        })
        
        return {
            "success": True,
            "message": "告警规则更新成功",
            "data": rule_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新告警规则失败: {e}")
        raise HTTPException(status_code=500, detail="更新告警规则失败")

@monitoring_router.delete("/alerts/rules/{rule_id}")
async def delete_alert_rule(rule_id: str):
    """
    删除告警规则
    """
    try:
        if rule_id not in alert_rules_db:
            raise HTTPException(status_code=404, detail="告警规则不存在")
        
        deleted_rule = alert_rules_db.pop(rule_id)
        
        return {
            "success": True,
            "message": "告警规则删除成功",
            "data": {
                "rule_id": rule_id,
                "deleted_rule": deleted_rule
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除告警规则失败: {e}")
        raise HTTPException(status_code=500, detail="删除告警规则失败")

# ==================== 系统管理接口 ====================

@monitoring_router.post("/management/cleanup")
async def cleanup_old_data(
    days: int = Query(30, description="保留天数"),
    dry_run: bool = Query(True, description="是否为试运行")
):
    """
    清理旧数据
    """
    try:
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # 统计要清理的数据
        cleanup_stats = {
            "usage_records_before": len(usage_monitor.usage_records),
            "cutoff_date": cutoff_date.isoformat(),
            "dry_run": dry_run
        }
        
        if not dry_run:
            # 实际清理数据
            original_count = len(usage_monitor.usage_records)
            
            # 过滤保留最近的记录
            usage_monitor.usage_records = [
                record for record in usage_monitor.usage_records
                if record.timestamp >= cutoff_date
            ]
            
            cleanup_stats["usage_records_after"] = len(usage_monitor.usage_records)
            cleanup_stats["cleaned_records"] = original_count - len(usage_monitor.usage_records)
        else:
            # 试运行，只统计
            records_to_clean = sum(
                1 for record in usage_monitor.usage_records
                if record.timestamp < cutoff_date
            )
            cleanup_stats["records_to_clean"] = records_to_clean
        
        return {
            "success": True,
            "message": "数据清理完成" if not dry_run else "数据清理预览",
            "data": cleanup_stats
        }
        
    except Exception as e:
        logger.error(f"清理旧数据失败: {e}")
        raise HTTPException(status_code=500, detail="清理旧数据失败")

@monitoring_router.post("/management/cache/clear")
async def clear_cache():
    """
    清理缓存
    """
    try:
        # 清理使用监控器的缓存
        usage_monitor.metrics_cache.clear()
        usage_monitor.windowed_stats.clear()
        
        # 重置实时统计
        usage_monitor.realtime_stats = {
            "total_calls": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
            "avg_latency": 0.0,
            "error_count": 0,
            "last_updated": datetime.now()
        }
        
        return {
            "success": True,
            "message": "缓存清理完成",
            "data": {
                "cleared_at": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"清理缓存失败: {e}")
        raise HTTPException(status_code=500, detail="清理缓存失败")

# ==================== 综合仪表板接口 ====================

@monitoring_router.get("/dashboard")
async def get_dashboard_data():
    """
    获取仪表板数据
    """
    try:
        # 并行获取各种数据
        tasks = [
            usage_monitor.get_realtime_metrics(),
            usage_monitor.get_top_models(5),
            model_manager.get_model_statistics(),
        ]
        
        realtime_metrics, top_models, model_stats = await asyncio.gather(*tasks)
        
        # 获取最近24小时的使用趋势
        usage_stats = await usage_monitor.get_usage_stats(
            time_window=TimeWindow.HOUR,
            start_time=datetime.now() - timedelta(hours=24),
            end_time=datetime.now()
        )
        
        dashboard_data = {
            "overview": {
                "total_calls": realtime_metrics.get("total_calls", 0),
                "total_tokens": realtime_metrics.get("total_tokens", 0),
                "avg_latency": realtime_metrics.get("avg_latency", 0),
                "error_rate": realtime_metrics.get("error_rate", 0),
                "calls_per_minute": realtime_metrics.get("calls_per_minute", 0)
            },
            "models": {
                "total_providers": model_stats["total_providers"],
                "configured_providers": model_stats["configured_providers"],
                "total_models": model_stats["total_models"],
                "enabled_models": model_stats["enabled_models"],
                "top_models": top_models
            },
            "trends": {
                "time_series": usage_stats.get("time_series", []),
                "breakdown": usage_stats.get("breakdown", {})
            },
            "timestamp": datetime.now().isoformat()
        }
        
        return {
            "success": True,
            "data": dashboard_data
        }
        
    except Exception as e:
        logger.error(f"获取仪表板数据失败: {e}")
        raise HTTPException(status_code=500, detail="获取仪表板数据失败")