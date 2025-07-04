"""
系统内部接口路由模块
提供系统内部的任务管理和调度接口
"""

import aiohttp
import asyncio
import logging
from fastapi import APIRouter, HTTPException, Depends, Request, Response, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Any, Dict, Optional, List
import json
import time
from datetime import datetime, timedelta
import uuid

from ..discovery import service_registry, LoadBalanceStrategy
from ..middleware.request_tracker import track_request
from ..middleware.internal_auth import verify_internal_token
from ..utils.proxy import ProxyUtils
from ..tasks.task_scheduler import TaskScheduler, Task, TaskStatus
from ..tasks.thread_pool import ThreadPoolManager

logger = logging.getLogger(__name__)

# 创建系统路由器
system_router = APIRouter(prefix="/system", tags=["System Internal"])

# 系统内部功能到微服务的映射
SYSTEM_SERVICE_MAPPING = {
    # 任务调度相关
    "scheduler": {
        "service": "gateway-service",  # 任务调度在网关层处理
        "endpoints": [
            "/tasks",
            "/scheduler",
            "/jobs"
        ]
    },
    # 服务管理相关
    "services": {
        "service": "gateway-service",  # 服务管理在网关层处理
        "endpoints": [
            "/services",
            "/discovery",
            "/health"
        ]
    },
    # 监控和日志相关
    "monitoring": {
        "service": "gateway-service",  # 监控在网关层处理
        "endpoints": [
            "/metrics",
            "/logs",
            "/alerts"
        ]
    },
    # 配置管理相关
    "config": {
        "service": "gateway-service",  # 配置管理在网关层处理
        "endpoints": [
            "/config",
            "/settings",
            "/parameters"
        ]
    }
}


class SystemProxy:
    """系统内部代理类"""
    
    def __init__(self):
        self.proxy_utils = ProxyUtils()
        self.task_scheduler = TaskScheduler()
        self.thread_pool = ThreadPoolManager()
    
    async def route_request(
        self,
        request: Request,
        target_service: str,
        path: str
    ) -> Response:
        """路由系统内部请求"""
        try:
            # 如果是网关自己处理的请求，直接处理
            if target_service == "gateway-service":
                return await self._handle_gateway_request(request, path)
            
            # 获取服务实例
            instance = await service_registry.get_service_instance(
                target_service,
                LoadBalanceStrategy.ROUND_ROBIN
            )
            
            if not instance:
                raise HTTPException(
                    status_code=503,
                    detail=f"服务 {target_service} 暂时不可用"
                )
            
            # 构建目标URL
            target_url = f"{instance.base_url}{path}"
            
            # 转发请求
            response = await self.proxy_utils.forward_request(
                request=request,
                target_url=target_url,
                auth_required=False  # 系统内部请求不需要用户认证
            )
            
            return response
            
        except Exception as e:
            logger.error(f"系统内部请求路由失败: {str(e)}")
            raise HTTPException(status_code=500, detail="内部服务错误")
    
    async def _handle_gateway_request(self, request: Request, path: str) -> Response:
        """处理网关自己的请求"""
        # 这里处理任务调度、服务发现等网关层功能
        if path.startswith("/system/tasks"):
            return await self._handle_task_request(request, path)
        elif path.startswith("/system/services"):
            return await self._handle_service_request(request, path)
        elif path.startswith("/system/monitoring"):
            return await self._handle_monitoring_request(request, path)
        elif path.startswith("/system/config"):
            return await self._handle_config_request(request, path)
        else:
            raise HTTPException(status_code=404, detail="端点未找到")
    
    async def _handle_task_request(self, request: Request, path: str) -> Response:
        """处理任务相关请求"""
        # 解析路径和方法
        method = request.method
        path_parts = path.split("/")[3:]  # 去掉 /system/tasks
        
        if not path_parts:
            if method == "GET":
                # 获取任务列表
                tasks = await self.task_scheduler.get_all_tasks()
                return JSONResponse({
                    "tasks": [task.to_dict() for task in tasks],
                    "total": len(tasks)
                })
            elif method == "POST":
                # 创建新任务
                body = await request.json()
                task = await self.task_scheduler.create_task(
                    name=body.get("name"),
                    task_type=body.get("type"),
                    payload=body.get("payload"),
                    schedule=body.get("schedule")
                )
                return JSONResponse(task.to_dict(), status_code=201)
        
        task_id = path_parts[0] if path_parts else None
        if task_id:
            if method == "GET":
                # 获取任务详情
                task = await self.task_scheduler.get_task(task_id)
                if not task:
                    raise HTTPException(status_code=404, detail="任务未找到")
                return JSONResponse(task.to_dict())
            elif method == "PUT":
                # 更新任务
                body = await request.json()
                task = await self.task_scheduler.update_task(task_id, body)
                if not task:
                    raise HTTPException(status_code=404, detail="任务未找到")
                return JSONResponse(task.to_dict())
            elif method == "DELETE":
                # 删除任务
                success = await self.task_scheduler.delete_task(task_id)
                if not success:
                    raise HTTPException(status_code=404, detail="任务未找到")
                return JSONResponse({"message": "任务已删除"})
        
        raise HTTPException(status_code=404, detail="端点未找到")
    
    async def _handle_service_request(self, request: Request, path: str) -> Response:
        """处理服务相关请求"""
        method = request.method
        path_parts = path.split("/")[3:]  # 去掉 /system/services
        
        if not path_parts:
            if method == "GET":
                # 获取所有服务
                services = service_registry.get_all_services()
                return JSONResponse({
                    "services": {
                        name: [instance.__dict__ for instance in instances]
                        for name, instances in services.items()
                    }
                })
        
        service_name = path_parts[0] if path_parts else None
        if service_name:
            if method == "GET":
                # 获取特定服务信息
                service_info = service_registry.get_service_info(service_name)
                if not service_info:
                    raise HTTPException(status_code=404, detail="服务未找到")
                return JSONResponse(service_info)
        
        raise HTTPException(status_code=404, detail="端点未找到")
    
    async def _handle_monitoring_request(self, request: Request, path: str) -> Response:
        """处理监控相关请求"""
        method = request.method
        path_parts = path.split("/")[3:]  # 去掉 /system/monitoring
        
        if not path_parts or path_parts[0] == "metrics":
            # 获取系统指标
            services = service_registry.get_all_services()
            metrics = {
                "timestamp": datetime.now().isoformat(),
                "services": {
                    name: {
                        "instance_count": len(instances),
                        "healthy_count": sum(1 for inst in instances if inst.status.value == "healthy")
                    }
                    for name, instances in services.items()
                },
                "tasks": {
                    "total": len(await self.task_scheduler.get_all_tasks()),
                    "running": len([t for t in await self.task_scheduler.get_all_tasks() if t.status == TaskStatus.RUNNING]),
                    "pending": len([t for t in await self.task_scheduler.get_all_tasks() if t.status == TaskStatus.PENDING])
                },
                "thread_pool": {
                    "active_threads": self.thread_pool.active_count(),
                    "max_workers": self.thread_pool.max_workers
                }
            }
            return JSONResponse(metrics)
        
        raise HTTPException(status_code=404, detail="端点未找到")
    
    async def _handle_config_request(self, request: Request, path: str) -> Response:
        """处理配置相关请求"""
        method = request.method
        
        # 简单的配置管理实现
        if method == "GET":
            config = {
                "gateway": {
                    "health_check_interval": 30,
                    "load_balance_strategy": "round_robin",
                    "max_connections": 1000
                },
                "services": {
                    "auto_discovery": True,
                    "health_check_enabled": True
                }
            }
            return JSONResponse(config)
        
        raise HTTPException(status_code=404, detail="端点未找到")


# 创建代理实例
system_proxy = SystemProxy()


# ==================== 任务管理接口 ====================

@system_router.get("/tasks")
@track_request
async def get_tasks(
    request: Request,
    internal_token: str = Depends(verify_internal_token)
):
    """获取任务列表"""
    return await system_proxy.route_request(
        request, "gateway-service", "/system/tasks"
    )


@system_router.post("/tasks")
@track_request
async def create_task(
    request: Request,
    background_tasks: BackgroundTasks,
    internal_token: str = Depends(verify_internal_token)
):
    """创建新任务"""
    return await system_proxy.route_request(
        request, "gateway-service", "/system/tasks"
    )


@system_router.get("/tasks/{task_id}")
@track_request
async def get_task(
    task_id: str,
    request: Request,
    internal_token: str = Depends(verify_internal_token)
):
    """获取任务详情"""
    return await system_proxy.route_request(
        request, "gateway-service", f"/system/tasks/{task_id}"
    )


@system_router.put("/tasks/{task_id}")
@track_request
async def update_task(
    task_id: str,
    request: Request,
    internal_token: str = Depends(verify_internal_token)
):
    """更新任务"""
    return await system_proxy.route_request(
        request, "gateway-service", f"/system/tasks/{task_id}"
    )


@system_router.delete("/tasks/{task_id}")
@track_request
async def delete_task(
    task_id: str,
    request: Request,
    internal_token: str = Depends(verify_internal_token)
):
    """删除任务"""
    return await system_proxy.route_request(
        request, "gateway-service", f"/system/tasks/{task_id}"
    )


@system_router.post("/tasks/{task_id}/execute")
@track_request
async def execute_task(
    task_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    internal_token: str = Depends(verify_internal_token)
):
    """执行任务"""
    try:
        task = await system_proxy.task_scheduler.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务未找到")
        
        # 在后台执行任务
        background_tasks.add_task(system_proxy.task_scheduler.execute_task, task_id)
        
        return JSONResponse({
            "message": "任务已提交执行",
            "task_id": task_id,
            "status": "submitted"
        })
    except Exception as e:
        logger.error(f"执行任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail="任务执行失败")


# ==================== 调度管理接口 ====================

@system_router.get("/scheduler/status")
@track_request
async def get_scheduler_status(
    request: Request,
    internal_token: str = Depends(verify_internal_token)
):
    """获取调度器状态"""
    try:
        status = await system_proxy.task_scheduler.get_status()
        return JSONResponse(status)
    except Exception as e:
        logger.error(f"获取调度器状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取调度器状态失败")


@system_router.post("/scheduler/start")
@track_request
async def start_scheduler(
    request: Request,
    internal_token: str = Depends(verify_internal_token)
):
    """启动调度器"""
    try:
        await system_proxy.task_scheduler.start()
        return JSONResponse({"message": "调度器已启动"})
    except Exception as e:
        logger.error(f"启动调度器失败: {str(e)}")
        raise HTTPException(status_code=500, detail="启动调度器失败")


@system_router.post("/scheduler/stop")
@track_request
async def stop_scheduler(
    request: Request,
    internal_token: str = Depends(verify_internal_token)
):
    """停止调度器"""
    try:
        await system_proxy.task_scheduler.stop()
        return JSONResponse({"message": "调度器已停止"})
    except Exception as e:
        logger.error(f"停止调度器失败: {str(e)}")
        raise HTTPException(status_code=500, detail="停止调度器失败")


# ==================== 服务管理接口 ====================

@system_router.get("/services")
@track_request
async def get_services(
    request: Request,
    internal_token: str = Depends(verify_internal_token)
):
    """获取所有注册的服务"""
    return await system_proxy.route_request(
        request, "gateway-service", "/system/services"
    )


@system_router.get("/services/{service_name}")
@track_request
async def get_service(
    service_name: str,
    request: Request,
    internal_token: str = Depends(verify_internal_token)
):
    """获取特定服务信息"""
    return await system_proxy.route_request(
        request, "gateway-service", f"/system/services/{service_name}"
    )


@system_router.post("/services/register")
@track_request
async def register_service(
    request: Request,
    internal_token: str = Depends(verify_internal_token)
):
    """注册服务"""
    try:
        body = await request.json()
        success = await service_registry.register_service(
            service_name=body.get("service_name"),
            instance_id=body.get("instance_id"),
            host=body.get("host"),
            port=body.get("port"),
            endpoints=body.get("endpoints"),
            metadata=body.get("metadata"),
            health_check_url=body.get("health_check_url"),
            weight=body.get("weight", 1)
        )
        
        if success:
            return JSONResponse({"message": "服务注册成功"}, status_code=201)
        else:
            raise HTTPException(status_code=400, detail="服务注册失败")
    except Exception as e:
        logger.error(f"服务注册失败: {str(e)}")
        raise HTTPException(status_code=500, detail="服务注册失败")


@system_router.delete("/services/{service_name}/{instance_id}")
@track_request
async def deregister_service(
    service_name: str,
    instance_id: str,
    request: Request,
    internal_token: str = Depends(verify_internal_token)
):
    """注销服务"""
    try:
        success = await service_registry.deregister_service(service_name, instance_id)
        
        if success:
            return JSONResponse({"message": "服务注销成功"})
        else:
            raise HTTPException(status_code=404, detail="服务或实例未找到")
    except Exception as e:
        logger.error(f"服务注销失败: {str(e)}")
        raise HTTPException(status_code=500, detail="服务注销失败")


# ==================== 监控接口 ====================

@system_router.get("/monitoring/metrics")
@track_request
async def get_metrics(
    request: Request,
    internal_token: str = Depends(verify_internal_token)
):
    """获取系统监控指标"""
    return await system_proxy.route_request(
        request, "gateway-service", "/system/monitoring/metrics"
    )


@system_router.get("/monitoring/health")
@track_request
async def health_check(
    request: Request,
    internal_token: str = Depends(verify_internal_token)
):
    """系统健康检查"""
    try:
        services = service_registry.get_all_services()
        all_healthy = True
        service_status = {}
        
        for service_name, instances in services.items():
            healthy_count = sum(1 for inst in instances if inst.status.value == "healthy")
            service_status[service_name] = {
                "status": "healthy" if healthy_count > 0 else "unhealthy",
                "instance_count": len(instances),
                "healthy_count": healthy_count
            }
            if healthy_count == 0:
                all_healthy = False
        
        return JSONResponse({
            "status": "healthy" if all_healthy else "degraded",
            "timestamp": datetime.now().isoformat(),
            "services": service_status
        })
    except Exception as e:
        logger.error(f"健康检查失败: {str(e)}")
        return JSONResponse({
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }, status_code=503)


# ==================== 配置管理接口 ====================

@system_router.get("/config")
@track_request
async def get_config(
    request: Request,
    internal_token: str = Depends(verify_internal_token)
):
    """获取系统配置"""
    return await system_proxy.route_request(
        request, "gateway-service", "/system/config"
    )


@system_router.put("/config")
@track_request
async def update_config(
    request: Request,
    internal_token: str = Depends(verify_internal_token)
):
    """更新系统配置"""
    return await system_proxy.route_request(
        request, "gateway-service", "/system/config"
    )


# ==================== 批量操作接口 ====================

@system_router.post("/batch/tasks")
@track_request
async def batch_create_tasks(
    request: Request,
    background_tasks: BackgroundTasks,
    internal_token: str = Depends(verify_internal_token)
):
    """批量创建任务"""
    try:
        body = await request.json()
        tasks_data = body.get("tasks", [])
        
        created_tasks = []
        for task_data in tasks_data:
            task = await system_proxy.task_scheduler.create_task(
                name=task_data.get("name"),
                task_type=task_data.get("type"),
                payload=task_data.get("payload"),
                schedule=task_data.get("schedule")
            )
            created_tasks.append(task.to_dict())
        
        return JSONResponse({
            "message": f"成功创建 {len(created_tasks)} 个任务",
            "tasks": created_tasks
        }, status_code=201)
    except Exception as e:
        logger.error(f"批量创建任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail="批量创建任务失败")


@system_router.post("/batch/services/health-check")
@track_request
async def batch_health_check(
    request: Request,
    background_tasks: BackgroundTasks,
    internal_token: str = Depends(verify_internal_token)
):
    """批量健康检查"""
    try:
        # 触发所有服务的健康检查
        services = service_registry.get_all_services()
        total_instances = sum(len(instances) for instances in services.values())
        
        # 在后台执行健康检查
        background_tasks.add_task(service_registry._perform_health_checks)
        
        return JSONResponse({
            "message": "批量健康检查已启动",
            "total_services": len(services),
            "total_instances": total_instances
        })
    except Exception as e:
        logger.error(f"批量健康检查失败: {str(e)}")
        raise HTTPException(status_code=500, detail="批量健康检查失败")


# ==================== 通用路由处理 ====================

@system_router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
@track_request
async def catch_all_system(
    path: str,
    request: Request,
    internal_token: str = Depends(verify_internal_token)
):
    """捕获所有系统请求的通用路由"""
    
    # 根据路径确定目标服务
    target_service = "gateway-service"  # 默认由网关处理
    
    for service_key, service_config in SYSTEM_SERVICE_MAPPING.items():
        for endpoint in service_config["endpoints"]:
            if path.startswith(endpoint.lstrip("/")):
                target_service = service_config["service"]
                break
        if target_service != "gateway-service":
            break
    
    return await system_proxy.route_request(
        request, target_service, f"/system/{path}"
    ) 