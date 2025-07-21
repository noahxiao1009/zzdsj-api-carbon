"""
网关服务的服务间通信集成
负责服务注册发现、路由管理、负载均衡和统一认证
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
import json
import hashlib
import sys
import os
from collections import defaultdict
import time
import random

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


class ServiceRegistry:
    """服务注册表"""
    
    def __init__(self):
        # 服务实例注册表: {service_name: [instance_info]}
        self.services = defaultdict(list)
        # 服务健康状态: {service_name-instance_id: last_heartbeat}
        self.health_status = {}
        # 服务路由配置: {service_name: route_config}
        self.route_configs = {}
        # 负载均衡状态: {service_name: current_index}
        self.load_balancer_state = defaultdict(int)
        
    def register_service(self, service_name: str, instance_info: Dict[str, Any]) -> bool:
        """注册服务实例"""
        try:
            instance_id = f"{service_name}-{instance_info.get('host', 'localhost')}-{instance_info.get('port', 8000)}"
            instance_info['instance_id'] = instance_id
            instance_info['registered_at'] = datetime.now().isoformat()
            instance_info['last_heartbeat'] = datetime.now().isoformat()
            
            # 检查是否已存在相同实例
            existing_instances = self.services[service_name]
            for i, existing in enumerate(existing_instances):
                if existing['instance_id'] == instance_id:
                    # 更新现有实例
                    existing_instances[i] = instance_info
                    logger.info(f"更新服务实例: {instance_id}")
                    return True
            
            # 添加新实例
            self.services[service_name].append(instance_info)
            self.health_status[instance_id] = datetime.now()
            
            logger.info(f"注册新服务实例: {instance_id}")
            return True
            
        except Exception as e:
            logger.error(f"服务注册失败 {service_name}: {e}")
            return False
    
    def unregister_service(self, service_name: str, instance_id: str) -> bool:
        """注销服务实例"""
        try:
            instances = self.services[service_name]
            self.services[service_name] = [
                instance for instance in instances 
                if instance['instance_id'] != instance_id
            ]
            
            if instance_id in self.health_status:
                del self.health_status[instance_id]
            
            logger.info(f"注销服务实例: {instance_id}")
            return True
            
        except Exception as e:
            logger.error(f"服务注销失败 {service_name}-{instance_id}: {e}")
            return False
    
    def get_healthy_instances(self, service_name: str) -> List[Dict[str, Any]]:
        """获取健康的服务实例"""
        instances = self.services.get(service_name, [])
        healthy_instances = []
        
        current_time = datetime.now()
        
        for instance in instances:
            instance_id = instance['instance_id']
            last_heartbeat = self.health_status.get(instance_id)
            
            if last_heartbeat:
                # 检查心跳超时 (30秒)
                if (current_time - last_heartbeat).total_seconds() < 30:
                    healthy_instances.append(instance)
                else:
                    logger.warning(f"服务实例心跳超时: {instance_id}")
            
        return healthy_instances
    
    def update_heartbeat(self, instance_id: str) -> bool:
        """更新服务实例心跳"""
        try:
            self.health_status[instance_id] = datetime.now()
            return True
        except Exception as e:
            logger.error(f"更新心跳失败 {instance_id}: {e}")
            return False
    
    def get_next_instance(self, service_name: str) -> Optional[Dict[str, Any]]:
        """负载均衡获取下一个服务实例"""
        healthy_instances = self.get_healthy_instances(service_name)
        
        if not healthy_instances:
            return None
        
        # 轮询负载均衡
        current_index = self.load_balancer_state[service_name]
        instance = healthy_instances[current_index % len(healthy_instances)]
        
        self.load_balancer_state[service_name] = (current_index + 1) % len(healthy_instances)
        
        return instance


class GatewayServiceIntegration:
    """网关服务集成类 - 统一路由和服务管理"""
    
    def __init__(self):
        self.service_client = None
        self.async_client = None
        self.service_registry = ServiceRegistry()
        
        # 不同操作的配置
        self.auth_config = CallConfig(
            timeout=5,    # 认证要快
            retry_times=2,
            retry_strategy=RetryStrategy.LINEAR,
            circuit_breaker_enabled=True
        )
        
        self.proxy_config = CallConfig(
            timeout=30,   # 代理请求允许较长时间
            retry_times=1,  # 减少重试避免重复请求
            retry_strategy=RetryStrategy.EXPONENTIAL
        )
        
        self.health_config = CallConfig(
            timeout=5,    # 健康检查要快
            retry_times=1,
            retry_strategy=RetryStrategy.LINEAR
        )
        
        # 服务路由配置
        self.service_routes = {
            "base-service": {
                "prefix": "/api/base",
                "strip_prefix": True,
                "auth_required": True,
                "rate_limit": {"requests": 1000, "window": 60}  # 每分钟1000请求
            },
            "agent-service": {
                "prefix": "/api/agent",
                "strip_prefix": True,
                "auth_required": True,
                "rate_limit": {"requests": 500, "window": 60}
            },
            "knowledge-service": {
                "prefix": "/api/knowledge",
                "strip_prefix": True,
                "auth_required": True,
                "rate_limit": {"requests": 200, "window": 60}
            },
            "model-service": {
                "prefix": "/api/model",
                "strip_prefix": True,
                "auth_required": True,
                "rate_limit": {"requests": 100, "window": 60}  # 模型调用限制更严格
            },
            "database-service": {
                "prefix": "/api/database",
                "strip_prefix": True,
                "auth_required": True,
                "rate_limit": {"requests": 2000, "window": 60}
            },
            "system-service": {
                "prefix": "/api/system",
                "strip_prefix": True,
                "auth_required": True,
                "rate_limit": {"requests": 500, "window": 60}
            }
        }
        
        # 限流状态: {user_id-service: [request_times]}
        self.rate_limit_state = defaultdict(list)
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.service_client = ServiceClient()
        self.async_client = AsyncServiceClient()
        await self.service_client.__aenter__()
        await self.async_client.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.service_client:
            await self.service_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.async_client:
            await self.async_client.__aexit__(exc_type, exc_val, exc_tb)
    
    # ==================== 服务注册和发现 ====================
    
    async def register_service_instance(self, service_info: Dict[str, Any]) -> Dict[str, Any]:
        """注册服务实例"""
        try:
            service_name = service_info['service_name']
            
            # 验证服务信息
            required_fields = ['service_name', 'host', 'port', 'version']
            for field in required_fields:
                if field not in service_info:
                    raise ValueError(f"缺少必需字段: {field}")
            
            # 注册到本地注册表
            success = self.service_registry.register_service(service_name, service_info)
            
            if success:
                # 发布服务注册事件
                await publish_event(
                    "service.registered",
                    {
                        "service_name": service_name,
                        "instance_id": service_info.get('instance_id'),
                        "timestamp": datetime.now().isoformat()
                    }
                )
                
                logger.info(f"服务注册成功: {service_name}")
                return {
                    "success": True,
                    "message": "服务注册成功",
                    "instance_id": service_info.get('instance_id')
                }
            else:
                return {"success": False, "message": "服务注册失败"}
                
        except Exception as e:
            logger.error(f"服务注册异常: {e}")
            return {"success": False, "message": str(e)}
    
    async def discover_services(self, service_name: Optional[str] = None) -> Dict[str, Any]:
        """服务发现"""
        try:
            if service_name:
                # 获取特定服务的健康实例
                instances = self.service_registry.get_healthy_instances(service_name)
                return {
                    "service_name": service_name,
                    "instances": instances,
                    "count": len(instances)
                }
            else:
                # 获取所有服务
                all_services = {}
                for svc_name in self.service_registry.services:
                    instances = self.service_registry.get_healthy_instances(svc_name)
                    all_services[svc_name] = {
                        "instances": instances,
                        "count": len(instances)
                    }
                
                return {"services": all_services}
                
        except Exception as e:
            logger.error(f"服务发现异常: {e}")
            return {"error": str(e)}
    
    async def service_heartbeat(self, instance_id: str) -> Dict[str, Any]:
        """处理服务心跳"""
        try:
            success = self.service_registry.update_heartbeat(instance_id)
            
            if success:
                return {"success": True, "timestamp": datetime.now().isoformat()}
            else:
                return {"success": False, "message": "心跳更新失败"}
                
        except Exception as e:
            logger.error(f"心跳处理异常: {e}")
            return {"success": False, "message": str(e)}
    
    # ==================== 认证和授权 ====================
    
    async def authenticate_request(self, headers: Dict[str, str]) -> Dict[str, Any]:
        """统一认证请求"""
        try:
            # 从headers中提取token
            auth_header = headers.get('Authorization', '')
            if not auth_header.startswith('Bearer '):
                return {"authenticated": False, "error": "缺少认证token"}
            
            token = auth_header[7:]  # 移除 'Bearer ' 前缀
            
            # 调用base-service验证token
            result = await self.service_client.call(
                service_name="base-service",
                method=CallMethod.POST,
                path="/api/v1/auth/verify",
                config=self.auth_config,
                json={"token": token}
            )
            
            if result.get("valid"):
                return {
                    "authenticated": True,
                    "user_id": result.get("user_id"),
                    "username": result.get("username"),
                    "role": result.get("role"),
                    "permissions": result.get("permissions", [])
                }
            else:
                return {"authenticated": False, "error": "无效token"}
                
        except ServiceCallError as e:
            logger.error(f"认证失败: {e}")
            if e.status_code == 503:
                # 认证服务不可用，允许请求通过（可配置）
                return {"authenticated": True, "user_id": "anonymous", "fallback": True}
            return {"authenticated": False, "error": "认证服务异常"}
        except Exception as e:
            logger.error(f"认证异常: {e}")
            return {"authenticated": False, "error": str(e)}
    
    def check_rate_limit(self, user_id: str, service_name: str) -> bool:
        """检查限流"""
        try:
            route_config = self.service_routes.get(service_name, {})
            rate_limit = route_config.get("rate_limit")
            
            if not rate_limit:
                return True  # 没有限流配置
            
            key = f"{user_id}-{service_name}"
            current_time = time.time()
            window = rate_limit["window"]
            max_requests = rate_limit["requests"]
            
            # 清理过期的请求记录
            request_times = self.rate_limit_state[key]
            self.rate_limit_state[key] = [
                req_time for req_time in request_times 
                if current_time - req_time < window
            ]
            
            # 检查是否超过限制
            if len(self.rate_limit_state[key]) >= max_requests:
                return False
            
            # 记录当前请求
            self.rate_limit_state[key].append(current_time)
            return True
            
        except Exception as e:
            logger.error(f"限流检查异常: {e}")
            return True  # 异常时允许通过
    
    # ==================== 请求代理和路由 ====================
    
    async def route_request(
        self, 
        path: str, 
        method: str, 
        headers: Dict[str, str],
        query_params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        form_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """路由请求到目标服务"""
        try:
            # 解析路径找到目标服务
            target_service = None
            target_path = path
            
            for service_name, route_config in self.service_routes.items():
                prefix = route_config["prefix"]
                if path.startswith(prefix):
                    target_service = service_name
                    if route_config.get("strip_prefix"):
                        target_path = path[len(prefix):]
                    break
            
            if not target_service:
                return {
                    "success": False,
                    "error": "未找到匹配的服务路由",
                    "status_code": 404
                }
            
            # 检查是否需要认证
            route_config = self.service_routes[target_service]
            if route_config.get("auth_required"):
                auth_result = await self.authenticate_request(headers)
                if not auth_result.get("authenticated"):
                    return {
                        "success": False,
                        "error": auth_result.get("error", "认证失败"),
                        "status_code": 401
                    }
                
                user_id = auth_result.get("user_id")
                
                # 检查限流
                if not self.check_rate_limit(user_id, target_service):
                    return {
                        "success": False,
                        "error": "请求频率超过限制",
                        "status_code": 429
                    }
            
            # 获取目标服务实例
            target_instance = self.service_registry.get_next_instance(target_service)
            if not target_instance:
                return {
                    "success": False,
                    "error": f"服务 {target_service} 不可用",
                    "status_code": 503
                }
            
            # 构建目标URL
            target_url = f"http://{target_instance['host']}:{target_instance['port']}{target_path}"
            
            # 代理请求
            call_method = getattr(CallMethod, method.upper(), CallMethod.GET)
            
            result = await self.service_client.call(
                service_name=target_service,
                method=call_method,
                path=target_path,
                config=self.proxy_config,
                params=query_params,
                json=json_data,
                data=form_data,
                headers=headers
            )
            
            return {
                "success": True,
                "data": result,
                "target_service": target_service,
                "target_instance": target_instance['instance_id']
            }
            
        except ServiceCallError as e:
            logger.error(f"请求代理失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "status_code": e.status_code
            }
        except Exception as e:
            logger.error(f"路由请求异常: {e}")
            return {
                "success": False,
                "error": str(e),
                "status_code": 500
            }
    
    # ==================== 健康检查和监控 ====================
    
    async def check_service_health(self, service_name: str) -> Dict[str, Any]:
        """检查特定服务健康状态"""
        try:
            instances = self.service_registry.get_healthy_instances(service_name)
            
            if not instances:
                return {
                    "service_name": service_name,
                    "status": "unhealthy",
                    "healthy_instances": 0,
                    "total_instances": len(self.service_registry.services.get(service_name, []))
                }
            
            # 并发检查所有实例
            health_checks = []
            for instance in instances:
                health_checks.append(self._check_instance_health(instance))
            
            health_results = await asyncio.gather(*health_checks, return_exceptions=True)
            
            healthy_count = sum(1 for result in health_results if result is True)
            
            return {
                "service_name": service_name,
                "status": "healthy" if healthy_count > 0 else "unhealthy",
                "healthy_instances": healthy_count,
                "total_instances": len(instances),
                "instance_details": [
                    {
                        "instance_id": instance['instance_id'],
                        "healthy": health_results[i] is True
                    }
                    for i, instance in enumerate(instances)
                ]
            }
            
        except Exception as e:
            logger.error(f"健康检查异常 {service_name}: {e}")
            return {
                "service_name": service_name,
                "status": "error",
                "error": str(e)
            }
    
    async def _check_instance_health(self, instance: Dict[str, Any]) -> bool:
        """检查单个实例健康状态"""
        try:
            # 尝试调用实例的健康检查接口
            result = await self.service_client.call(
                service_name="direct",  # 直接调用，不经过服务发现
                method=CallMethod.GET,
                path="/health",
                config=self.health_config,
                base_url=f"http://{instance['host']}:{instance['port']}"
            )
            
            return result.get("status") == "healthy"
            
        except Exception:
            return False
    
    async def get_gateway_metrics(self) -> Dict[str, Any]:
        """获取网关指标"""
        try:
            current_time = datetime.now()
            
            # 服务注册统计
            service_stats = {}
            for service_name in self.service_registry.services:
                healthy_instances = self.service_registry.get_healthy_instances(service_name)
                total_instances = len(self.service_registry.services[service_name])
                service_stats[service_name] = {
                    "total_instances": total_instances,
                    "healthy_instances": len(healthy_instances),
                    "health_ratio": len(healthy_instances) / total_instances if total_instances > 0 else 0
                }
            
            # 限流统计
            rate_limit_stats = {}
            for key, request_times in self.rate_limit_state.items():
                user_service = key.split('-', 1)
                if len(user_service) == 2:
                    user_id, service_name = user_service
                    if service_name not in rate_limit_stats:
                        rate_limit_stats[service_name] = {"total_requests": 0, "active_users": set()}
                    rate_limit_stats[service_name]["total_requests"] += len(request_times)
                    rate_limit_stats[service_name]["active_users"].add(user_id)
            
            # 转换set为count
            for service_name in rate_limit_stats:
                rate_limit_stats[service_name]["active_users"] = len(rate_limit_stats[service_name]["active_users"])
            
            return {
                "timestamp": current_time.isoformat(),
                "gateway_status": "healthy",
                "total_services": len(self.service_registry.services),
                "service_statistics": service_stats,
                "rate_limit_statistics": rate_limit_stats,
                "load_balancer_state": dict(self.service_registry.load_balancer_state)
            }
            
        except Exception as e:
            logger.error(f"获取网关指标异常: {e}")
            return {"error": str(e)}
    
    # ==================== 批量操作 ====================
    
    async def batch_health_check(self) -> Dict[str, Any]:
        """批量健康检查所有服务"""
        try:
            service_names = list(self.service_registry.services.keys())
            
            if not service_names:
                return {"services": {}, "summary": {"total": 0, "healthy": 0, "unhealthy": 0}}
            
            # 并发检查所有服务
            health_checks = [
                self.check_service_health(service_name) 
                for service_name in service_names
            ]
            
            health_results = await asyncio.gather(*health_checks)
            
            # 统计结果
            services_health = {}
            healthy_count = 0
            unhealthy_count = 0
            
            for result in health_results:
                service_name = result['service_name']
                services_health[service_name] = result
                
                if result['status'] == 'healthy':
                    healthy_count += 1
                else:
                    unhealthy_count += 1
            
            return {
                "services": services_health,
                "summary": {
                    "total": len(service_names),
                    "healthy": healthy_count,
                    "unhealthy": unhealthy_count,
                    "health_ratio": healthy_count / len(service_names) if service_names else 0
                },
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"批量健康检查异常: {e}")
            return {"error": str(e)}


# ==================== 全局便捷函数 ====================

async def register_service(service_info: Dict[str, Any]) -> Dict[str, Any]:
    """全局服务注册函数"""
    async with GatewayServiceIntegration() as gateway:
        return await gateway.register_service_instance(service_info)

async def discover_service(service_name: str) -> Dict[str, Any]:
    """全局服务发现函数"""
    async with GatewayServiceIntegration() as gateway:
        return await gateway.discover_services(service_name)

async def route_request_to_service(
    path: str, 
    method: str, 
    headers: Dict[str, str],
    **kwargs
) -> Dict[str, Any]:
    """全局请求路由函数"""
    async with GatewayServiceIntegration() as gateway:
        return await gateway.route_request(path, method, headers, **kwargs)

async def check_all_services_health() -> Dict[str, Any]:
    """全局批量健康检查函数"""
    async with GatewayServiceIntegration() as gateway:
        return await gateway.batch_health_check() 