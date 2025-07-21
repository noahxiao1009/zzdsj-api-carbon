"""
智能体管理路由 - 提供智能体实例管理和监控API
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query, Body, BackgroundTasks
from pydantic import BaseModel, Field

from app.services.agent_pool_manager import (
    get_agent_pool_manager, LoadBalanceStrategy, AgentStatus
)
from app.services.agent_sync_manager import (
    get_agent_sync_manager, SyncEvent, SyncEventType
)
from app.services.agent_health_monitor import (
    get_agent_health_monitor, HealthCheckType, HealthStatus
)
from app.services.resource_optimizer import (
    get_resource_optimizer, ScalingRule, ScalingTrigger, ScalingAction
)
from app.services.load_balancer import (
    get_smart_load_balancer, LoadBalanceConfig, LoadBalanceAlgorithm, RoutingRequest
)
from app.services.agent_service_integration import (
    get_agent_service_integration, AgentDefinition, AgentCapability, 
    ConversationRequest, IntegrationLevel
)
from app.core.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/agents", tags=["agent-management"])


class AgentInstanceRequest(BaseModel):
    """智能体实例请求"""
    agent_id: str = Field(..., description="智能体ID")
    max_concurrent_sessions: int = Field(50, ge=1, le=200, description="最大并发会话数")
    weight: float = Field(1.0, ge=0.1, le=10.0, description="权重")
    auto_scaling: bool = Field(True, description="是否启用自动伸缩")


class ScaleRequest(BaseModel):
    """伸缩请求"""
    target_count: int = Field(..., ge=0, le=10, description="目标实例数")
    force: bool = Field(False, description="是否强制伸缩")


class HealthCheckRequest(BaseModel):
    """健康检查请求"""
    check_type: HealthCheckType = Field(HealthCheckType.BASIC, description="检查类型")
    instances: Optional[List[str]] = Field(None, description="指定实例ID列表")


class AlertRuleRequest(BaseModel):
    """告警规则请求"""
    rule_id: str = Field(..., description="规则ID")
    alert_type: str = Field(..., description="告警类型")
    severity: str = Field("warning", description="严重程度")
    status_condition: Optional[List[str]] = Field(None, description="状态条件")
    metric_conditions: List[Dict[str, Any]] = Field(default_factory=list, description="指标条件")
    message: str = Field(..., description="告警消息")


class ScalingRuleRequest(BaseModel):
    """伸缩规则请求"""
    rule_id: str = Field(..., description="规则ID")
    agent_id: str = Field(..., description="智能体ID")
    trigger: ScalingTrigger = Field(..., description="触发器类型")
    metric_name: str = Field(..., description="指标名称")
    threshold_up: float = Field(..., description="扩容阈值")
    threshold_down: float = Field(..., description="缩容阈值")
    min_instances: int = Field(1, ge=1, le=20, description="最小实例数")
    max_instances: int = Field(10, ge=1, le=50, description="最大实例数")
    cooldown_period: int = Field(300, ge=60, le=3600, description="冷却期(秒)")
    enabled: bool = Field(True, description="是否启用")


class LoadBalanceConfigRequest(BaseModel):
    """负载均衡配置请求"""
    algorithm: LoadBalanceAlgorithm = Field(..., description="负载均衡算法")
    health_check_weight: float = Field(0.3, ge=0.0, le=1.0, description="健康检查权重")
    response_time_weight: float = Field(0.3, ge=0.0, le=1.0, description="响应时间权重")
    load_weight: float = Field(0.4, ge=0.0, le=1.0, description="负载权重")
    sticky_session_timeout: int = Field(3600, ge=300, le=86400, description="粘性会话超时")
    failover_retries: int = Field(3, ge=1, le=10, description="故障转移重试次数")
    circuit_breaker_enabled: bool = Field(True, description="启用熔断器")
    adaptive_weights: bool = Field(True, description="自适应权重")


class RoutingTestRequest(BaseModel):
    """路由测试请求"""
    agent_id: str = Field(..., description="智能体ID")
    session_id: Optional[str] = Field(None, description="会话ID")
    user_id: Optional[str] = Field(None, description="用户ID")
    client_ip: Optional[str] = Field(None, description="客户端IP")
    request_type: str = Field("chat", description="请求类型")
    priority: int = Field(1, ge=1, le=10, description="优先级")
    test_count: int = Field(1, ge=1, le=100, description="测试次数")


class AgentRegistrationRequest(BaseModel):
    """智能体注册请求"""
    agent_id: str = Field(..., description="智能体ID")
    name: str = Field(..., description="智能体名称")
    description: str = Field(..., description="智能体描述")
    version: str = Field("1.0.0", description="版本号")
    capabilities: List[AgentCapability] = Field(default_factory=list, description="能力列表")
    configuration: Dict[str, Any] = Field(default_factory=dict, description="配置")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")


class ConversationStartRequest(BaseModel):
    """对话开始请求"""
    agent_id: str = Field(..., description="智能体ID")
    session_id: str = Field(..., description="会话ID")
    user_id: str = Field(..., description="用户ID")
    initial_context: Dict[str, Any] = Field(default_factory=dict, description="初始上下文")


class MessageRequest(BaseModel):
    """消息请求"""
    agent_id: str = Field(..., description="智能体ID")
    session_id: str = Field(..., description="会话ID")
    user_id: str = Field(..., description="用户ID")
    message: str = Field(..., description="消息内容")
    message_type: str = Field("text", description="消息类型")
    context: Dict[str, Any] = Field(default_factory=dict, description="上下文")
    options: Dict[str, Any] = Field(default_factory=dict, description="选项")
    stream: bool = Field(False, description="是否流式响应")
    priority: int = Field(1, ge=1, le=10, description="优先级")


@router.get("/pool/status")
async def get_pool_status(
    current_user: Dict = Depends(get_current_user)
):
    """获取智能体池状态"""
    try:
        pool_manager = get_agent_pool_manager()
        status = await pool_manager.get_pool_status()
        
        return {
            "success": True,
            "data": status,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"获取池状态失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取池状态失败: {str(e)}"
        )


@router.get("/instances")
async def list_agent_instances(
    agent_id: Optional[str] = Query(None, description="智能体ID过滤"),
    status: Optional[AgentStatus] = Query(None, description="状态过滤"),
    current_user: Dict = Depends(get_current_user)
):
    """列出智能体实例"""
    try:
        pool_manager = get_agent_pool_manager()
        
        instances = []
        for instance_id, instance in pool_manager.instances.items():
            # 应用过滤条件
            if agent_id and instance.agent_id != agent_id:
                continue
            if status and instance.status != status:
                continue
            
            instances.append(instance.to_dict())
        
        return {
            "success": True,
            "instances": instances,
            "total": len(instances),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"列出智能体实例失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"列出智能体实例失败: {str(e)}"
        )


@router.post("/instances")
async def create_agent_instance(
    request: AgentInstanceRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict = Depends(get_current_user)
):
    """创建智能体实例"""
    try:
        pool_manager = get_agent_pool_manager()
        
        # 创建实例
        instance = await pool_manager._create_agent_instance(request.agent_id)
        
        if not instance:
            raise HTTPException(
                status_code=400,
                detail="创建智能体实例失败"
            )
        
        # 更新实例配置
        instance.max_concurrent_sessions = request.max_concurrent_sessions
        instance.weight = request.weight
        
        # 触发同步事件
        sync_manager = get_agent_sync_manager()
        background_tasks.add_task(
            sync_manager.add_sync_event,
            SyncEvent(
                event_type=SyncEventType.INSTANCE_CREATED,
                agent_id=request.agent_id,
                instance_id=instance.instance_id,
                data=instance.to_dict()
            )
        )
        
        return {
            "success": True,
            "instance": instance.to_dict(),
            "message": "智能体实例创建成功",
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建智能体实例失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"创建智能体实例失败: {str(e)}"
        )


@router.get("/instances/{instance_id}")
async def get_agent_instance(
    instance_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """获取智能体实例详情"""
    try:
        pool_manager = get_agent_pool_manager()
        instance = pool_manager.instances.get(instance_id)
        
        if not instance:
            raise HTTPException(
                status_code=404,
                detail=f"实例 {instance_id} 不存在"
            )
        
        return {
            "success": True,
            "instance": instance.to_dict(),
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取智能体实例详情失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取智能体实例详情失败: {str(e)}"
        )


@router.delete("/instances/{instance_id}")
async def delete_agent_instance(
    instance_id: str,
    background_tasks: BackgroundTasks,
    current_user: Dict = Depends(get_current_user)
):
    """删除智能体实例"""
    try:
        pool_manager = get_agent_pool_manager()
        instance = pool_manager.instances.get(instance_id)
        
        if not instance:
            raise HTTPException(
                status_code=404,
                detail=f"实例 {instance_id} 不存在"
            )
        
        agent_id = instance.agent_id
        
        # 删除实例
        await pool_manager._remove_instance(instance_id)
        
        # 触发同步事件
        sync_manager = get_agent_sync_manager()
        background_tasks.add_task(
            sync_manager.add_sync_event,
            SyncEvent(
                event_type=SyncEventType.INSTANCE_DELETED,
                agent_id=agent_id,
                instance_id=instance_id
            )
        )
        
        return {
            "success": True,
            "message": f"实例 {instance_id} 已删除",
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除智能体实例失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"删除智能体实例失败: {str(e)}"
        )


@router.post("/instances/{agent_id}/scale")
async def scale_agent_instances(
    agent_id: str,
    request: ScaleRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict = Depends(get_current_user)
):
    """伸缩智能体实例"""
    try:
        pool_manager = get_agent_pool_manager()
        
        # 执行伸缩操作
        result = await pool_manager.scale_agent_instances(agent_id, request.target_count)
        
        if not result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "伸缩操作失败")
            )
        
        # 触发同步事件
        sync_manager = get_agent_sync_manager()
        background_tasks.add_task(
            sync_manager.add_sync_event,
            SyncEvent(
                event_type=SyncEventType.INSTANCE_UPDATED,
                agent_id=agent_id,
                data=result
            )
        )
        
        return {
            "success": True,
            "scale_result": result,
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"伸缩智能体实例失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"伸缩智能体实例失败: {str(e)}"
        )


@router.get("/pool/config")
async def get_pool_config(
    current_user: Dict = Depends(get_current_user)
):
    """获取池配置"""
    try:
        pool_manager = get_agent_pool_manager()
        
        config = {
            "load_balance_strategy": pool_manager.load_balance_strategy.value,
            "min_instances_per_agent": pool_manager.min_instances_per_agent,
            "max_instances_per_agent": pool_manager.max_instances_per_agent,
            "health_check_interval": pool_manager.health_check_interval,
            "instance_timeout": pool_manager.instance_timeout
        }
        
        return {
            "success": True,
            "config": config,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"获取池配置失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取池配置失败: {str(e)}"
        )


@router.post("/pool/config")
async def update_pool_config(
    config: Dict[str, Any] = Body(...),
    current_user: Dict = Depends(get_current_user)
):
    """更新池配置"""
    try:
        pool_manager = get_agent_pool_manager()
        
        # 更新配置
        if "load_balance_strategy" in config:
            strategy = config["load_balance_strategy"]
            if strategy in [s.value for s in LoadBalanceStrategy]:
                pool_manager.load_balance_strategy = LoadBalanceStrategy(strategy)
        
        if "min_instances_per_agent" in config:
            pool_manager.min_instances_per_agent = max(1, config["min_instances_per_agent"])
        
        if "max_instances_per_agent" in config:
            pool_manager.max_instances_per_agent = max(1, config["max_instances_per_agent"])
        
        if "health_check_interval" in config:
            pool_manager.health_check_interval = max(10, config["health_check_interval"])
        
        if "instance_timeout" in config:
            pool_manager.instance_timeout = max(60, config["instance_timeout"])
        
        return {
            "success": True,
            "message": "池配置已更新",
            "updated_config": {
                "load_balance_strategy": pool_manager.load_balance_strategy.value,
                "min_instances_per_agent": pool_manager.min_instances_per_agent,
                "max_instances_per_agent": pool_manager.max_instances_per_agent,
                "health_check_interval": pool_manager.health_check_interval,
                "instance_timeout": pool_manager.instance_timeout
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"更新池配置失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"更新池配置失败: {str(e)}"
        )


@router.post("/health/check")
async def perform_health_check(
    request: HealthCheckRequest,
    current_user: Dict = Depends(get_current_user)
):
    """执行健康检查"""
    try:
        health_monitor = get_agent_health_monitor()
        pool_manager = get_agent_pool_manager()
        
        # 确定要检查的实例
        if request.instances:
            instance_ids = request.instances
        else:
            instance_ids = list(pool_manager.instances.keys())
        
        if not instance_ids:
            return {
                "success": True,
                "message": "没有可检查的实例",
                "results": [],
                "timestamp": datetime.now().isoformat()
            }
        
        # 并发执行健康检查
        check_tasks = [
            health_monitor.perform_health_check(instance_id, request.check_type)
            for instance_id in instance_ids
        ]
        
        results = await asyncio.gather(*check_tasks, return_exceptions=True)
        
        # 处理结果
        check_results = []
        for result in results:
            if isinstance(result, Exception):
                check_results.append({
                    "error": str(result),
                    "status": "failed"
                })
            else:
                check_results.append(result.to_dict())
        
        return {
            "success": True,
            "check_type": request.check_type.value,
            "results": check_results,
            "total_checked": len(instance_ids),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"执行健康检查失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"执行健康检查失败: {str(e)}"
        )


@router.get("/health/summary")
async def get_health_summary(
    instance_id: Optional[str] = Query(None, description="指定实例ID"),
    current_user: Dict = Depends(get_current_user)
):
    """获取健康状态摘要"""
    try:
        health_monitor = get_agent_health_monitor()
        summary = health_monitor.get_health_summary(instance_id)
        
        return {
            "success": True,
            "health_summary": summary,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"获取健康状态摘要失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取健康状态摘要失败: {str(e)}"
        )


@router.get("/health/trends/{instance_id}")
async def get_health_trends(
    instance_id: str,
    hours: int = Query(24, ge=1, le=168, description="时间范围(小时)"),
    current_user: Dict = Depends(get_current_user)
):
    """获取健康趋势"""
    try:
        health_monitor = get_agent_health_monitor()
        trends = health_monitor.get_health_trends(instance_id, hours)
        
        return {
            "success": True,
            "health_trends": trends,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"获取健康趋势失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取健康趋势失败: {str(e)}"
        )


@router.post("/alerts/rules")
async def add_alert_rule(
    request: AlertRuleRequest,
    current_user: Dict = Depends(get_current_user)
):
    """添加告警规则"""
    try:
        health_monitor = get_agent_health_monitor()
        
        rule = {
            "id": request.rule_id,
            "alert_type": request.alert_type,
            "severity": request.severity,
            "status_condition": request.status_condition,
            "metric_conditions": request.metric_conditions,
            "message": request.message,
            "created_by": current_user["user_id"],
            "created_at": datetime.now().isoformat()
        }
        
        health_monitor.add_alert_rule(rule)
        
        return {
            "success": True,
            "message": "告警规则已添加",
            "rule": rule,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"添加告警规则失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"添加告警规则失败: {str(e)}"
        )


@router.delete("/alerts/rules/{rule_id}")
async def remove_alert_rule(
    rule_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """移除告警规则"""
    try:
        health_monitor = get_agent_health_monitor()
        health_monitor.remove_alert_rule(rule_id)
        
        return {
            "success": True,
            "message": f"告警规则 {rule_id} 已移除",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"移除告警规则失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"移除告警规则失败: {str(e)}"
        )


@router.get("/alerts/rules")
async def list_alert_rules(
    current_user: Dict = Depends(get_current_user)
):
    """列出告警规则"""
    try:
        health_monitor = get_agent_health_monitor()
        
        return {
            "success": True,
            "alert_rules": health_monitor.alert_rules,
            "total": len(health_monitor.alert_rules),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"列出告警规则失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"列出告警规则失败: {str(e)}"
        )


@router.get("/sync/status")
async def get_sync_status(
    current_user: Dict = Depends(get_current_user)
):
    """获取同步状态"""
    try:
        sync_manager = get_agent_sync_manager()
        status = sync_manager.get_sync_status()
        
        return {
            "success": True,
            "sync_status": status,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"获取同步状态失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取同步状态失败: {str(e)}"
        )


@router.post("/sync/full")
async def trigger_full_sync(
    background_tasks: BackgroundTasks,
    current_user: Dict = Depends(get_current_user)
):
    """触发完整同步"""
    try:
        sync_manager = get_agent_sync_manager()
        
        # 后台执行完整同步
        background_tasks.add_task(sync_manager.perform_full_sync)
        
        return {
            "success": True,
            "message": "完整同步已触发",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"触发完整同步失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"触发完整同步失败: {str(e)}"
        )


@router.get("/metrics")
async def get_agent_metrics(
    current_user: Dict = Depends(get_current_user)
):
    """获取智能体指标"""
    try:
        pool_manager = get_agent_pool_manager()
        health_monitor = get_agent_health_monitor()
        sync_manager = get_agent_sync_manager()
        resource_optimizer = get_resource_optimizer()
        load_balancer = get_smart_load_balancer()
        
        metrics = {
            "pool_metrics": pool_manager.pool_metrics,
            "health_metrics": health_monitor.monitor_stats,
            "sync_metrics": sync_manager.sync_metrics,
            "optimization_stats": resource_optimizer.get_optimization_stats(),
            "load_balance_stats": load_balancer.get_load_balance_stats(),
            "instance_count": len(pool_manager.instances),
            "agent_count": len(pool_manager.agent_instances),
            "timestamp": datetime.now().isoformat()
        }
        
        return {
            "success": True,
            "metrics": metrics,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"获取智能体指标失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取智能体指标失败: {str(e)}"
        )


# ===== 资源优化接口 =====

@router.post("/optimization/scaling-rules")
async def add_scaling_rule(
    request: ScalingRuleRequest,
    current_user: Dict = Depends(get_current_user)
):
    """添加伸缩规则"""
    try:
        resource_optimizer = get_resource_optimizer()
        
        scaling_rule = ScalingRule(
            rule_id=request.rule_id,
            agent_id=request.agent_id,
            trigger=request.trigger,
            metric_name=request.metric_name,
            threshold_up=request.threshold_up,
            threshold_down=request.threshold_down,
            min_instances=request.min_instances,
            max_instances=request.max_instances,
            cooldown_period=request.cooldown_period,
            enabled=request.enabled
        )
        
        success = await resource_optimizer.add_scaling_rule(scaling_rule)
        
        if success:
            return {
                "success": True,
                "message": "伸缩规则添加成功",
                "rule": scaling_rule.to_dict(),
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(
                status_code=400,
                detail="伸缩规则添加失败"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加伸缩规则失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"添加伸缩规则失败: {str(e)}"
        )


@router.delete("/optimization/scaling-rules/{rule_id}")
async def remove_scaling_rule(
    rule_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """移除伸缩规则"""
    try:
        resource_optimizer = get_resource_optimizer()
        success = await resource_optimizer.remove_scaling_rule(rule_id)
        
        if success:
            return {
                "success": True,
                "message": f"伸缩规则 {rule_id} 已移除",
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"伸缩规则 {rule_id} 不存在"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"移除伸缩规则失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"移除伸缩规则失败: {str(e)}"
        )


@router.get("/optimization/scaling-rules")
async def list_scaling_rules(
    agent_id: Optional[str] = Query(None, description="智能体ID过滤"),
    current_user: Dict = Depends(get_current_user)
):
    """列出伸缩规则"""
    try:
        resource_optimizer = get_resource_optimizer()
        
        rules = list(resource_optimizer.scaling_rules.values())
        if agent_id:
            rules = [rule for rule in rules if rule.agent_id == agent_id]
        
        return {
            "success": True,
            "scaling_rules": [rule.to_dict() for rule in rules],
            "total": len(rules),
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"列出伸缩规则失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"列出伸缩规则失败: {str(e)}"
        )


@router.post("/optimization/agents/{agent_id}/optimize")
async def optimize_agent_resources(
    agent_id: str,
    background_tasks: BackgroundTasks,
    current_user: Dict = Depends(get_current_user)
):
    """手动优化智能体资源"""
    try:
        resource_optimizer = get_resource_optimizer()
        
        # 后台执行优化
        background_tasks.add_task(
            resource_optimizer.optimize_agent_resources,
            agent_id
        )
        
        return {
            "success": True,
            "message": f"智能体 {agent_id} 资源优化已触发",
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"优化智能体资源失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"优化智能体资源失败: {str(e)}"
        )


@router.get("/optimization/agents/{agent_id}/metrics")
async def get_agent_optimization_metrics(
    agent_id: str,
    limit: int = Query(50, ge=1, le=200, description="返回数量限制"),
    current_user: Dict = Depends(get_current_user)
):
    """获取智能体优化指标"""
    try:
        resource_optimizer = get_resource_optimizer()
        metrics_history = resource_optimizer.get_agent_metrics_history(agent_id, limit)
        
        return {
            "success": True,
            "agent_id": agent_id,
            "metrics_history": metrics_history,
            "total_points": len(metrics_history),
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"获取智能体优化指标失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取智能体优化指标失败: {str(e)}"
        )


# ===== 负载均衡接口 =====

@router.get("/loadbalance/config")
async def get_load_balance_config(
    current_user: Dict = Depends(get_current_user)
):
    """获取负载均衡配置"""
    try:
        load_balancer = get_smart_load_balancer()
        
        return {
            "success": True,
            "config": {
                "algorithm": load_balancer.config.algorithm.value,
                "session_affinity": load_balancer.config.session_affinity.value,
                "health_check_weight": load_balancer.config.health_check_weight,
                "response_time_weight": load_balancer.config.response_time_weight,
                "load_weight": load_balancer.config.load_weight,
                "sticky_session_timeout": load_balancer.config.sticky_session_timeout,
                "failover_retries": load_balancer.config.failover_retries,
                "circuit_breaker_enabled": load_balancer.config.circuit_breaker_enabled,
                "adaptive_weights": load_balancer.config.adaptive_weights
            },
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"获取负载均衡配置失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取负载均衡配置失败: {str(e)}"
        )


@router.put("/loadbalance/config")
async def update_load_balance_config(
    request: LoadBalanceConfigRequest,
    current_user: Dict = Depends(get_current_user)
):
    """更新负载均衡配置"""
    try:
        load_balancer = get_smart_load_balancer()
        
        # 验证权重总和
        total_weight = request.health_check_weight + request.response_time_weight + request.load_weight
        if abs(total_weight - 1.0) > 0.01:
            raise HTTPException(
                status_code=400,
                detail="权重总和必须等于1.0"
            )
        
        # 更新配置
        load_balancer.config.algorithm = request.algorithm
        load_balancer.config.health_check_weight = request.health_check_weight
        load_balancer.config.response_time_weight = request.response_time_weight
        load_balancer.config.load_weight = request.load_weight
        load_balancer.config.sticky_session_timeout = request.sticky_session_timeout
        load_balancer.config.failover_retries = request.failover_retries
        load_balancer.config.circuit_breaker_enabled = request.circuit_breaker_enabled
        load_balancer.config.adaptive_weights = request.adaptive_weights
        
        return {
            "success": True,
            "message": "负载均衡配置已更新",
            "updated_config": {
                "algorithm": load_balancer.config.algorithm.value,
                "health_check_weight": load_balancer.config.health_check_weight,
                "response_time_weight": load_balancer.config.response_time_weight,
                "load_weight": load_balancer.config.load_weight,
                "sticky_session_timeout": load_balancer.config.sticky_session_timeout,
                "failover_retries": load_balancer.config.failover_retries,
                "circuit_breaker_enabled": load_balancer.config.circuit_breaker_enabled,
                "adaptive_weights": load_balancer.config.adaptive_weights
            },
            "timestamp": datetime.now().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新负载均衡配置失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"更新负载均衡配置失败: {str(e)}"
        )


@router.post("/loadbalance/test-routing")
async def test_load_balance_routing(
    request: RoutingTestRequest,
    current_user: Dict = Depends(get_current_user)
):
    """测试负载均衡路由"""
    try:
        load_balancer = get_smart_load_balancer()
        
        results = []
        for i in range(request.test_count):
            routing_request = RoutingRequest(
                session_id=request.session_id,
                user_id=request.user_id,
                client_ip=request.client_ip,
                request_type=request.request_type,
                priority=request.priority
            )
            
            result = await load_balancer.route_request(request.agent_id, routing_request)
            
            results.append({
                "test_index": i + 1,
                "success": result.success,
                "instance_id": result.instance.instance_id if result.instance else None,
                "routing_time": result.routing_time,
                "algorithm_used": result.algorithm_used.value if result.algorithm_used else None,
                "affinity_hit": result.affinity_hit,
                "fallback_used": result.fallback_used,
                "error_message": result.error_message
            })
        
        # 统计结果
        successful_routes = sum(1 for r in results if r["success"])
        average_routing_time = sum(r["routing_time"] for r in results) / len(results)
        affinity_hits = sum(1 for r in results if r["affinity_hit"])
        
        return {
            "success": True,
            "test_summary": {
                "total_tests": request.test_count,
                "successful_routes": successful_routes,
                "success_rate": successful_routes / request.test_count,
                "average_routing_time": average_routing_time,
                "affinity_hits": affinity_hits,
                "affinity_hit_rate": affinity_hits / request.test_count
            },
            "detailed_results": results,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"测试负载均衡路由失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"测试负载均衡路由失败: {str(e)}"
        )


@router.get("/loadbalance/stats")
async def get_load_balance_stats(
    current_user: Dict = Depends(get_current_user)
):
    """获取负载均衡统计"""
    try:
        load_balancer = get_smart_load_balancer()
        stats = load_balancer.get_load_balance_stats()
        
        return {
            "success": True,
            "load_balance_stats": stats,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"获取负载均衡统计失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取负载均衡统计失败: {str(e)}"
        )


# ===== Agent-Service集成接口 =====

@router.post("/integration/initialize")
async def initialize_agent_integration(
    integration_level: IntegrationLevel = IntegrationLevel.FULL,
    current_user: Dict = Depends(get_current_user)
):
    """初始化Agent-Service集成"""
    try:
        integration = get_agent_service_integration()
        integration.integration_level = integration_level
        
        success = await integration.initialize_integration()
        
        if success:
            return {
                "success": True,
                "message": "Agent-Service集成初始化成功",
                "integration_level": integration_level.value,
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Agent-Service集成初始化失败"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"初始化Agent-Service集成失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"初始化Agent-Service集成失败: {str(e)}"
        )


@router.post("/integration/register")
async def register_agent_with_service(
    request: AgentRegistrationRequest,
    current_user: Dict = Depends(get_current_user)
):
    """向Agent-Service注册智能体"""
    try:
        integration = get_agent_service_integration()
        
        agent_definition = AgentDefinition(
            agent_id=request.agent_id,
            name=request.name,
            description=request.description,
            version=request.version,
            capabilities=request.capabilities,
            configuration=request.configuration,
            metadata=request.metadata
        )
        
        success = await integration.register_agent(agent_definition)
        
        if success:
            return {
                "success": True,
                "message": "智能体注册成功",
                "agent": agent_definition.to_dict(),
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(
                status_code=400,
                detail="智能体注册失败"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"注册智能体失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"注册智能体失败: {str(e)}"
        )


@router.get("/integration/agents/{agent_id}")
async def get_agent_from_service(
    agent_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """从Agent-Service获取智能体定义"""
    try:
        integration = get_agent_service_integration()
        agent_definition = await integration.get_agent_definition(agent_id)
        
        if agent_definition:
            return {
                "success": True,
                "agent": agent_definition.to_dict(),
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"智能体 {agent_id} 不存在"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取智能体定义失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取智能体定义失败: {str(e)}"
        )


@router.post("/integration/conversations/start")
async def start_conversation_with_agent(
    request: ConversationStartRequest,
    current_user: Dict = Depends(get_current_user)
):
    """开始与智能体的对话"""
    try:
        integration = get_agent_service_integration()
        
        conversation_id = await integration.start_conversation(
            agent_id=request.agent_id,
            session_id=request.session_id,
            user_id=request.user_id,
            initial_context=request.initial_context
        )
        
        if conversation_id:
            return {
                "success": True,
                "conversation_id": conversation_id,
                "message": "对话创建成功",
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(
                status_code=400,
                detail="对话创建失败"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"开始对话失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"开始对话失败: {str(e)}"
        )


@router.post("/integration/conversations/message")
async def send_message_to_agent(
    request: MessageRequest,
    current_user: Dict = Depends(get_current_user)
):
    """向智能体发送消息"""
    try:
        integration = get_agent_service_integration()
        
        conversation_request = ConversationRequest(
            agent_id=request.agent_id,
            session_id=request.session_id,
            user_id=request.user_id,
            message=request.message,
            message_type=request.message_type,
            context=request.context,
            options=request.options,
            stream=request.stream,
            priority=request.priority
        )
        
        response = await integration.send_message(conversation_request)
        
        return {
            "success": response.success,
            "response": response.response if response.success else None,
            "response_type": response.response_type,
            "metadata": response.metadata,
            "usage": response.usage,
            "error": response.error,
            "processing_time": response.processing_time,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"发送消息失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"发送消息失败: {str(e)}"
        )


@router.get("/integration/stats")
async def get_integration_stats(
    current_user: Dict = Depends(get_current_user)
):
    """获取Agent-Service集成统计"""
    try:
        integration = get_agent_service_integration()
        stats = integration.get_integration_stats()
        
        return {
            "success": True,
            "integration_stats": stats,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"获取集成统计失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取集成统计失败: {str(e)}"
        )


@router.get("/integration/agents")
async def list_registered_agents(
    current_user: Dict = Depends(get_current_user)
):
    """列出已注册的智能体"""
    try:
        integration = get_agent_service_integration()
        
        agents = [agent.to_dict() for agent in integration.agent_registry.values()]
        
        return {
            "success": True,
            "agents": agents,
            "total": len(agents),
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"列出已注册智能体失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"列出已注册智能体失败: {str(e)}"
        )


@router.get("/integration/conversations")
async def list_active_conversations(
    user_id: Optional[str] = Query(None, description="用户ID过滤"),
    agent_id: Optional[str] = Query(None, description="智能体ID过滤"),
    current_user: Dict = Depends(get_current_user)
):
    """列出活跃对话"""
    try:
        integration = get_agent_service_integration()
        
        conversations = []
        for conv_id, context in integration.conversation_contexts.items():
            # 应用过滤条件
            if user_id and context.user_id != user_id:
                continue
            if agent_id and context.agent_id != agent_id:
                continue
            
            conversations.append({
                "conversation_id": conv_id,
                "agent_id": context.agent_id,
                "session_id": context.session_id,
                "user_id": context.user_id,
                "message_count": len(context.messages),
                "created_at": context.created_at,
                "updated_at": context.updated_at
            })
        
        return {
            "success": True,
            "conversations": conversations,
            "total": len(conversations),
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"列出活跃对话失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"列出活跃对话失败: {str(e)}"
        )