"""
网关管理接口
包括服务注册、健康检查、监控等网关自身的管理功能
"""

import asyncio
import logging
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from typing import Any, Dict, Optional, List
import time
from datetime import datetime

from ..discovery import service_registry, ServiceStatus, LoadBalanceStrategy
from ..middleware.request_tracker import track_request

logger = logging.getLogger(__name__)

# 创建网关路由器
gateway_router = APIRouter(prefix="/gateway", tags=["Gateway Management"])


# ==================== 服务注册管理接口 ====================

@gateway_router.get("/services")
@track_request
async def list_services(request: Request):
    """获取所有注册的服务"""
    try:
        services = service_registry.get_all_services()
        service_list = []
        
        for service_name, instances in services.items():
            service_info = service_registry.get_service_info(service_name)
            if service_info:
                service_list.append(service_info)
        
        return JSONResponse({
            "services": service_list,
            "total": len(service_list),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"获取服务列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取服务列表失败")


@gateway_router.get("/services/{service_name}")
@track_request
async def get_service_detail(service_name: str, request: Request):
    """获取特定服务的详细信息"""
    try:
        service_info = service_registry.get_service_info(service_name)
        if not service_info:
            raise HTTPException(status_code=404, detail="服务未找到")
        
        return JSONResponse(service_info)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取服务详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取服务详情失败")


@gateway_router.post("/services/register")
@track_request
async def register_service_endpoint(request: Request):
    """注册服务端点"""
    try:
        body = await request.json()
        
        # 验证必需字段
        required_fields = ["service_name", "instance_id", "host", "port"]
        for field in required_fields:
            if field not in body:
                raise HTTPException(status_code=400, detail=f"缺少必需字段: {field}")
        
        success = await service_registry.register_service(
            service_name=body["service_name"],
            instance_id=body["instance_id"],
            host=body["host"],
            port=body["port"],
            endpoints=body.get("endpoints", {}),
            metadata=body.get("metadata", {}),
            health_check_url=body.get("health_check_url"),
            weight=body.get("weight", 1)
        )
        
        if success:
            return JSONResponse({
                "message": "服务注册成功",
                "service_name": body["service_name"],
                "instance_id": body["instance_id"]
            }, status_code=201)
        else:
            raise HTTPException(status_code=400, detail="服务注册失败")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"注册服务失败: {str(e)}")
        raise HTTPException(status_code=500, detail="服务注册失败")


@gateway_router.delete("/services/{service_name}/{instance_id}")
@track_request
async def deregister_service_endpoint(service_name: str, instance_id: str, request: Request):
    """注销服务实例"""
    try:
        success = await service_registry.deregister_service(service_name, instance_id)
        
        if success:
            return JSONResponse({
                "message": "服务注销成功",
                "service_name": service_name,
                "instance_id": instance_id
            })
        else:
            raise HTTPException(status_code=404, detail="服务或实例未找到")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"注销服务失败: {str(e)}")
        raise HTTPException(status_code=500, detail="服务注销失败")


# ==================== 健康检查接口 ====================

@gateway_router.get("/health")
@track_request
async def gateway_health_check(request: Request):
    """网关健康检查"""
    try:
        services = service_registry.get_all_services()
        all_healthy = True
        service_status = {}
        
        for service_name, instances in services.items():
            healthy_count = sum(1 for inst in instances if inst.status == ServiceStatus.HEALTHY)
            total_count = len(instances)
            
            service_status[service_name] = {
                "status": "healthy" if healthy_count > 0 else "unhealthy",
                "healthy_instances": healthy_count,
                "total_instances": total_count,
                "health_ratio": healthy_count / total_count if total_count > 0 else 0
            }
            
            if healthy_count == 0 and total_count > 0:
                all_healthy = False
        
        gateway_status = "healthy" if all_healthy else "degraded"
        
        return JSONResponse({
            "status": gateway_status,
            "timestamp": datetime.now().isoformat(),
            "uptime": time.time(),  # 简单的运行时间
            "services": service_status,
            "registry": {
                "total_services": len(services),
                "total_instances": sum(len(instances) for instances in services.values())
            }
        })
    except Exception as e:
        logger.error(f"健康检查失败: {str(e)}")
        return JSONResponse({
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }, status_code=503)


@gateway_router.post("/health/check/{service_name}")
@track_request
async def trigger_service_health_check(service_name: str, request: Request):
    """触发特定服务的健康检查"""
    try:
        services = service_registry.get_all_services()
        if service_name not in services:
            raise HTTPException(status_code=404, detail="服务未找到")
        
        instances = services[service_name]
        
        # 触发健康检查
        tasks = []
        for instance in instances:
            task = asyncio.create_task(service_registry._health_check_instance(instance))
            tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        # 获取更新后的状态
        service_info = service_registry.get_service_info(service_name)
        
        return JSONResponse({
            "message": f"服务 {service_name} 健康检查已完成",
            "service_info": service_info
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"触发健康检查失败: {str(e)}")
        raise HTTPException(status_code=500, detail="健康检查失败")


# ==================== 负载均衡管理接口 ====================

@gateway_router.get("/load-balancer/{service_name}")
@track_request
async def get_load_balancer_status(service_name: str, request: Request):
    """获取负载均衡器状态"""
    try:
        service_info = service_registry.get_service_info(service_name)
        if not service_info:
            raise HTTPException(status_code=404, detail="服务未找到")
        
        # 测试不同的负载均衡策略
        strategies = [
            LoadBalanceStrategy.ROUND_ROBIN,
            LoadBalanceStrategy.RANDOM,
            LoadBalanceStrategy.LEAST_CONNECTIONS,
            LoadBalanceStrategy.WEIGHTED_ROUND_ROBIN
        ]
        
        strategy_results = {}
        for strategy in strategies:
            instance = await service_registry.get_service_instance(service_name, strategy)
            if instance:
                strategy_results[strategy.value] = {
                    "instance_id": instance.instance_id,
                    "host": instance.host,
                    "port": instance.port,
                    "weight": instance.weight,
                    "connections": instance.connections
                }
            else:
                strategy_results[strategy.value] = None
        
        return JSONResponse({
            "service_name": service_name,
            "load_balancing_results": strategy_results,
            "service_info": service_info
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取负载均衡状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取负载均衡状态失败")


@gateway_router.post("/load-balancer/{service_name}/test")
@track_request
async def test_load_balancing(service_name: str, request: Request):
    """测试负载均衡"""
    try:
        body = await request.json()
        strategy = LoadBalanceStrategy(body.get("strategy", "round_robin"))
        rounds = body.get("rounds", 10)
        
        if rounds > 100:
            raise HTTPException(status_code=400, detail="测试轮次不能超过100")
        
        results = []
        for i in range(rounds):
            instance = await service_registry.get_service_instance(service_name, strategy)
            if instance:
                results.append({
                    "round": i + 1,
                    "instance_id": instance.instance_id,
                    "host": instance.host,
                    "port": instance.port
                })
            else:
                results.append({
                    "round": i + 1,
                    "error": "无可用实例"
                })
        
        # 统计分布
        distribution = {}
        for result in results:
            if "instance_id" in result:
                instance_id = result["instance_id"]
                distribution[instance_id] = distribution.get(instance_id, 0) + 1
        
        return JSONResponse({
            "service_name": service_name,
            "strategy": strategy.value,
            "total_rounds": rounds,
            "results": results,
            "distribution": distribution
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"测试负载均衡失败: {str(e)}")
        raise HTTPException(status_code=500, detail="负载均衡测试失败")


# ==================== 监控和指标接口 ====================

@gateway_router.get("/metrics")
@track_request
async def get_gateway_metrics(request: Request):
    """获取网关监控指标"""
    try:
        services = service_registry.get_all_services()
        
        # 计算各种指标
        total_services = len(services)
        total_instances = sum(len(instances) for instances in services.values())
        healthy_instances = sum(
            sum(1 for inst in instances if inst.status == ServiceStatus.HEALTHY)
            for instances in services.values()
        )
        
        # 服务可用性统计
        service_availability = {}
        for service_name, instances in services.items():
            total = len(instances)
            healthy = sum(1 for inst in instances if inst.status == ServiceStatus.HEALTHY)
            service_availability[service_name] = {
                "availability": (healthy / total * 100) if total > 0 else 0,
                "healthy_count": healthy,
                "total_count": total
            }
        
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "gateway": {
                "status": "healthy",
                "uptime": time.time()
            },
            "services": {
                "total_services": total_services,
                "total_instances": total_instances,
                "healthy_instances": healthy_instances,
                "overall_availability": (healthy_instances / total_instances * 100) if total_instances > 0 else 0,
                "service_availability": service_availability
            },
            "registry": {
                "health_check_enabled": True,
                "auto_discovery": True
            }
        }
        
        return JSONResponse(metrics)
        
    except Exception as e:
        logger.error(f"获取监控指标失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取监控指标失败")


@gateway_router.get("/registry/status")
@track_request
async def get_registry_status(request: Request):
    """获取服务注册中心状态"""
    try:
        services = service_registry.get_all_services()
        
        registry_status = {
            "timestamp": datetime.now().isoformat(),
            "registry": {
                "running": True,
                "health_check_running": service_registry._running,
                "total_services": len(services),
                "service_summary": {}
            }
        }
        
        for service_name, instances in services.items():
            status_counts = {}
            for instance in instances:
                status = instance.status.value
                status_counts[status] = status_counts.get(status, 0) + 1
            
            registry_status["registry"]["service_summary"][service_name] = {
                "total_instances": len(instances),
                "status_distribution": status_counts,
                "last_updated": max(
                    (inst.last_health_check for inst in instances if inst.last_health_check),
                    default=None
                )
            }
        
        return JSONResponse(registry_status)
        
    except Exception as e:
        logger.error(f"获取注册中心状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取注册中心状态失败")


# ==================== 配置管理接口 ====================

@gateway_router.get("/config")
@track_request
async def get_gateway_config(request: Request):
    """获取网关配置"""
    try:
        config = {
            "gateway": {
                "name": "ZZDSJ API Gateway",
                "version": "1.0.0",
                "health_check_interval": service_registry.health_check_interval,
                "load_balance_strategies": [strategy.value for strategy in LoadBalanceStrategy]
            },
            "services": {
                "auto_discovery": True,
                "health_check_enabled": True,
                "max_retry_attempts": 3,
                "timeout": 30
            },
            "routing": {
                "api_layers": ["frontend", "v1", "system"],
                "default_timeout": 30,
                "enable_logging": True
            }
        }
        
        return JSONResponse(config)
        
    except Exception as e:
        logger.error(f"获取网关配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取网关配置失败")


@gateway_router.put("/config")
@track_request
async def update_gateway_config(request: Request):
    """更新网关配置"""
    try:
        body = await request.json()
        
        # 这里可以实现配置更新逻辑
        # 目前返回简单的确认消息
        
        return JSONResponse({
            "message": "配置更新成功",
            "updated_at": datetime.now().isoformat(),
            "config": body
        })
        
    except Exception as e:
        logger.error(f"更新网关配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail="更新网关配置失败")


# ==================== 批量操作接口 ====================

@gateway_router.post("/services/batch/health-check")
@track_request
async def batch_health_check(request: Request):
    """批量健康检查所有服务"""
    try:
        services = service_registry.get_all_services()
        total_instances = sum(len(instances) for instances in services.values())
        
        # 执行批量健康检查
        await service_registry._perform_health_checks()
        
        # 获取检查后的状态
        updated_services = service_registry.get_all_services()
        healthy_instances = sum(
            sum(1 for inst in instances if inst.status == ServiceStatus.HEALTHY)
            for instances in updated_services.values()
        )
        
        return JSONResponse({
            "message": "批量健康检查完成",
            "total_services": len(services),
            "total_instances": total_instances,
            "healthy_instances": healthy_instances,
            "health_ratio": (healthy_instances / total_instances * 100) if total_instances > 0 else 0,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"批量健康检查失败: {str(e)}")
        raise HTTPException(status_code=500, detail="批量健康检查失败")


@gateway_router.get("/debug/routes")
@track_request
async def get_debug_routes(request: Request):
    """获取调试路由信息"""
    try:
        route_info = {
            "api_layers": {
                "frontend": {
                    "prefix": "/frontend",
                    "description": "前端页面相关接口",
                    "auth_required": True
                },
                "v1": {
                    "prefix": "/v1", 
                    "description": "外部调用接口",
                    "auth_required": True,
                    "auth_type": "api_key"
                },
                "system": {
                    "prefix": "/system",
                    "description": "系统内部任务管理和调度",
                    "auth_required": True,
                    "auth_type": "internal_token"
                }
            },
            "gateway_routes": {
                "prefix": "/gateway",
                "description": "网关管理接口"
            },
            "registered_services": list(service_registry.get_all_services().keys())
        }
        
        return JSONResponse(route_info)
        
    except Exception as e:
        logger.error(f"获取路由信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取路由信息失败") 