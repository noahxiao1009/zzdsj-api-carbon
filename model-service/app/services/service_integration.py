"""
模型服务的服务间通信集成
基于统一ServiceClient SDK实现模型服务的高效微服务间通信与协作
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
import sys
import os
import hashlib
import time

# 添加shared模块到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), "../../../shared"))

from service_client import (
    ServiceClient, 
    AsyncServiceClient,
    CallMethod, 
    CallConfig, 
    RetryStrategy,
    ServiceCallError
)

logger = logging.getLogger(__name__)


class ModelServiceIntegration:
    """模型服务集成类 - 模型调用密集场景优化"""
    
    def __init__(self):
        self.service_client = None
        self.async_client = None
        
        # 针对模型服务的专用配置
        self.base_config = CallConfig(
            timeout=10,   # 权限检查要快速响应
            retry_times=3,
            retry_strategy=RetryStrategy.LINEAR,
            circuit_breaker_enabled=True
        )
        
        self.database_config = CallConfig(
            timeout=15,   # 统计数据存储
            retry_times=2,
            retry_strategy=RetryStrategy.LINEAR
        )
        
        self.gateway_config = CallConfig(
            timeout=5,    # 服务注册要快
            retry_times=3,
            retry_strategy=RetryStrategy.LINEAR
        )
        
        # 模型调用统计缓存
        self.usage_stats_cache = {}
        self.last_stats_flush = datetime.now()
        self.stats_flush_interval = timedelta(minutes=5)  # 5分钟刷新一次统计
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.service_client = ServiceClient()
        self.async_client = AsyncServiceClient()
        await self.service_client.__aenter__()
        await self.async_client.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        # 退出前刷新统计数据
        await self.flush_usage_stats()
        
        if self.service_client:
            await self.service_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.async_client:
            await self.async_client.__aexit__(exc_type, exc_val, exc_tb)
    
    # ==================== 权限和用户管理 ====================
    
    async def check_model_permission(self, user_id: str, provider_id: str, model_id: str, action: str) -> bool:
        """检查模型使用权限"""
        try:
            result = await self.service_client.call(
                service_name="base-service",
                method=CallMethod.POST,
                path="/api/v1/permissions/check",
                config=self.base_config,
                json={
                    "user_id": user_id,
                    "resource_type": "model",
                    "resource_id": f"{provider_id}:{model_id}",
                    "action": action
                }
            )
            
            return result.get("allowed", False)
            
        except ServiceCallError as e:
            logger.error(f"模型权限检查失败: {e}")
            if e.status_code == 503:
                # 服务不可用时，根据操作类型决定策略
                if action in ["use", "test"]:
                    return True  # 使用权限默认允许
                else:
                    return False  # 管理权限默认拒绝
            return False
        except Exception as e:
            logger.error(f"模型权限检查异常: {e}")
            return False
    
    async def get_user_model_quota(self, user_id: str) -> Dict[str, Any]:
        """获取用户模型调用配额"""
        try:
            result = await self.service_client.call(
                service_name="base-service",
                method=CallMethod.GET,
                path=f"/api/v1/users/{user_id}/quota",
                config=self.base_config,
                params={"resource_type": "model_calls"}
            )
            
            return result
            
        except ServiceCallError as e:
            logger.error(f"获取用户模型配额失败: {e}")
            if e.status_code == 503:
                # 服务不可用，返回默认配额
                return {
                    "daily_calls": 1000,
                    "monthly_calls": 30000,
                    "max_tokens_per_call": 4000,
                    "current_daily_usage": 0,
                    "current_monthly_usage": 0,
                    "fallback": True
                }
            raise
        except Exception as e:
            logger.error(f"获取用户模型配额异常: {e}")
            raise
    
    async def validate_api_key_access(self, user_id: str, provider_id: str) -> bool:
        """验证用户对提供商API密钥的访问权限"""
        try:
            result = await self.service_client.call(
                service_name="base-service",
                method=CallMethod.POST,
                path="/api/v1/permissions/api-key-access",
                config=self.base_config,
                json={
                    "user_id": user_id,
                    "provider_id": provider_id
                }
            )
            
            return result.get("has_access", False)
            
        except ServiceCallError as e:
            logger.error(f"API密钥访问验证失败: {e}")
            if e.status_code == 503:
                return True  # 服务不可用时默认允许
            return False
        except Exception as e:
            logger.error(f"API密钥访问验证异常: {e}")
            return False
    
    # ==================== 配置管理 ====================
    
    async def save_provider_config(
        self, 
        provider_id: str, 
        config: Dict[str, Any], 
        user_id: str
    ) -> Dict[str, Any]:
        """保存提供商配置"""
        try:
            logger.info(f"保存提供商配置: {provider_id}")
            
            result = await self.service_client.call(
                service_name="database-service",
                method=CallMethod.POST,
                path="/api/v1/model_providers",
                config=self.database_config,
                json={
                    "provider_id": provider_id,
                    "user_id": user_id,
                    "config": config,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }
            )
            
            # 发布配置更新事件
            await self.async_client.publish_event(
                event_type="provider_configured",
                data={
                    "provider_id": provider_id,
                    "user_id": user_id,
                    "config_fields": list(config.keys()),
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            return result
            
        except ServiceCallError as e:
            logger.error(f"保存提供商配置失败: {e}")
            raise
        except Exception as e:
            logger.error(f"保存提供商配置异常: {e}")
            raise
    
    async def get_provider_config(self, provider_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """获取提供商配置"""
        try:
            result = await self.service_client.call(
                service_name="database-service",
                method=CallMethod.GET,
                path=f"/api/v1/model_providers/{provider_id}",
                config=self.database_config,
                params={"user_id": user_id}
            )
            
            return result
            
        except ServiceCallError as e:
            if e.status_code == 404:
                return None
            logger.error(f"获取提供商配置失败: {e}")
            raise
        except Exception as e:
            logger.error(f"获取提供商配置异常: {e}")
            raise
    
    async def save_model_config(
        self, 
        config_id: str, 
        config: Dict[str, Any], 
        user_id: str
    ) -> Dict[str, Any]:
        """保存模型配置"""
        try:
            logger.info(f"保存模型配置: {config_id}")
            
            result = await self.service_client.call(
                service_name="database-service",
                method=CallMethod.POST,
                path="/api/v1/model_configs",
                config=self.database_config,
                json={
                    "config_id": config_id,
                    "user_id": user_id,
                    "config": config,
                    "created_at": datetime.now().isoformat()
                }
            )
            
            return result
            
        except ServiceCallError as e:
            logger.error(f"保存模型配置失败: {e}")
            raise
        except Exception as e:
            logger.error(f"保存模型配置异常: {e}")
            raise
    
    async def get_user_model_configs(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户的模型配置列表"""
        try:
            result = await self.service_client.call(
                service_name="database-service",
                method=CallMethod.GET,
                path="/api/v1/model_configs",
                config=self.database_config,
                params={"user_id": user_id}
            )
            
            return result.get("data", [])
            
        except ServiceCallError as e:
            logger.error(f"获取用户模型配置失败: {e}")
            if e.status_code == 503:
                return []
            raise
        except Exception as e:
            logger.error(f"获取用户模型配置异常: {e}")
            raise
    
    # ==================== 使用统计和监控 ====================
    
    async def record_model_usage(
        self, 
        user_id: str, 
        provider_id: str, 
        model_id: str,
        usage_data: Dict[str, Any]
    ):
        """记录模型使用情况（缓存模式）"""
        try:
            cache_key = f"{user_id}:{provider_id}:{model_id}"
            current_stats = self.usage_stats_cache.get(cache_key, {
                "user_id": user_id,
                "provider_id": provider_id,
                "model_id": model_id,
                "call_count": 0,
                "total_tokens": 0,
                "total_cost": 0.0,
                "total_latency": 0.0,
                "error_count": 0,
                "first_call": datetime.now().isoformat(),
                "last_call": datetime.now().isoformat()
            })
            
            # 更新统计数据
            current_stats["call_count"] += 1
            current_stats["total_tokens"] += usage_data.get("tokens", 0)
            current_stats["total_cost"] += usage_data.get("cost", 0.0)
            current_stats["total_latency"] += usage_data.get("latency", 0.0)
            current_stats["last_call"] = datetime.now().isoformat()
            
            if usage_data.get("error"):
                current_stats["error_count"] += 1
            
            self.usage_stats_cache[cache_key] = current_stats
            
            # 检查是否需要刷新统计数据
            if datetime.now() - self.last_stats_flush > self.stats_flush_interval:
                await self.flush_usage_stats()
            
        except Exception as e:
            logger.error(f"记录模型使用情况失败: {e}")
    
    async def flush_usage_stats(self):
        """刷新使用统计数据到数据库"""
        if not self.usage_stats_cache:
            return
        
        try:
            logger.info(f"刷新 {len(self.usage_stats_cache)} 条模型使用统计")
            
            stats_data = list(self.usage_stats_cache.values())
            
            result = await self.service_client.call(
                service_name="database-service",
                method=CallMethod.POST,
                path="/api/v1/model_usage_stats/batch",
                config=self.database_config,
                json={
                    "stats": stats_data,
                    "flush_time": datetime.now().isoformat()
                }
            )
            
            # 清空缓存
            self.usage_stats_cache.clear()
            self.last_stats_flush = datetime.now()
            
            logger.info("模型使用统计刷新完成")
            
        except Exception as e:
            logger.error(f"刷新使用统计失败: {e}")
    
    async def get_model_usage_stats(
        self, 
        user_id: str, 
        provider_id: Optional[str] = None,
        model_id: Optional[str] = None,
        period: str = "daily"
    ) -> Dict[str, Any]:
        """获取模型使用统计"""
        try:
            params = {
                "user_id": user_id,
                "period": period
            }
            
            if provider_id:
                params["provider_id"] = provider_id
            if model_id:
                params["model_id"] = model_id
            
            result = await self.service_client.call(
                service_name="database-service",
                method=CallMethod.GET,
                path="/api/v1/model_usage_stats",
                config=self.database_config,
                params=params
            )
            
            return result
            
        except ServiceCallError as e:
            logger.error(f"获取模型使用统计失败: {e}")
            if e.status_code == 503:
                return {
                    "stats": [],
                    "summary": {
                        "total_calls": 0,
                        "total_tokens": 0,
                        "total_cost": 0.0,
                        "avg_latency": 0.0
                    },
                    "fallback": True
                }
            raise
        except Exception as e:
            logger.error(f"获取模型使用统计异常: {e}")
            raise
    
    # ==================== 服务注册和发现 ====================
    
    async def register_with_gateway(self, service_info: Dict[str, Any]) -> bool:
        """向网关注册模型服务"""
        try:
            logger.info("向网关注册模型服务")
            
            registration_data = {
                "service_name": "model-service",
                "service_url": service_info.get("url", "http://localhost:8003"),
                "health_check_url": "/api/v1/models/health",
                "service_type": "core",
                "capabilities": [
                    "model_management",
                    "provider_configuration", 
                    "model_calling",
                    "usage_analytics"
                ],
                "metadata": {
                    "version": service_info.get("version", "1.0.0"),
                    "supported_providers": service_info.get("supported_providers", []),
                    "api_endpoints": [
                        "/api/v1/models/providers",
                        "/api/v1/models/",
                        "/api/v1/models/config"
                    ]
                },
                "registered_at": datetime.now().isoformat()
            }
            
            result = await self.service_client.call(
                service_name="gateway-service",
                method=CallMethod.POST,
                path="/api/v1/services/register",
                config=self.gateway_config,
                json=registration_data
            )
            
            if result.get("success"):
                logger.info("模型服务注册成功")
                
                # 发布服务注册事件
                await self.async_client.publish_event(
                    event_type="service_registered",
                    data={
                        "service_name": "model-service",
                        "capabilities": registration_data["capabilities"],
                        "timestamp": datetime.now().isoformat()
                    }
                )
                
                return True
            else:
                logger.error(f"模型服务注册失败: {result}")
                return False
            
        except ServiceCallError as e:
            logger.error(f"向网关注册失败: {e}")
            return False
        except Exception as e:
            logger.error(f"向网关注册异常: {e}")
            return False
    
    async def update_service_status(self, status: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """更新服务状态"""
        try:
            update_data = {
                "service_name": "model-service",
                "status": status,
                "updated_at": datetime.now().isoformat()
            }
            
            if metadata:
                update_data["metadata"] = metadata
            
            result = await self.service_client.call(
                service_name="gateway-service",
                method=CallMethod.PUT,
                path="/api/v1/services/model-service/status",
                config=self.gateway_config,
                json=update_data
            )
            
            return result.get("success", False)
            
        except Exception as e:
            logger.error(f"更新服务状态失败: {e}")
            return False
    
    # ==================== 模型调用工作流 ====================
    
    async def model_call_workflow(
        self, 
        user_id: str, 
        provider_id: str, 
        model_id: str,
        call_data: Dict[str, Any],
        track_usage: bool = True
    ) -> Dict[str, Any]:
        """模型调用的完整工作流"""
        start_time = time.time()
        call_successful = False
        error_message = None
        
        try:
            logger.info(f"开始模型调用工作流: {provider_id}:{model_id}")
            
            # 1. 权限检查
            has_permission = await self.check_model_permission(user_id, provider_id, model_id, "use")
            if not has_permission:
                return {
                    "success": False,
                    "error": "没有使用此模型的权限",
                    "code": "PERMISSION_DENIED"
                }
            
            # 2. 配额检查
            user_quota = await self.get_user_model_quota(user_id)
            
            # 检查日调用限制
            if user_quota.get("current_daily_usage", 0) >= user_quota.get("daily_calls", 1000):
                return {
                    "success": False,
                    "error": "日调用次数已达上限",
                    "code": "DAILY_QUOTA_EXCEEDED"
                }
            
            # 检查Token限制
            max_tokens = call_data.get("max_tokens", 1000)
            if max_tokens > user_quota.get("max_tokens_per_call", 4000):
                return {
                    "success": False,
                    "error": f"单次调用Token数超限 (最大: {user_quota.get('max_tokens_per_call')})",
                    "code": "TOKEN_LIMIT_EXCEEDED"
                }
            
            # 3. 获取提供商配置
            provider_config = await self.get_provider_config(provider_id, user_id)
            if not provider_config:
                return {
                    "success": False,
                    "error": f"提供商 {provider_id} 未配置",
                    "code": "PROVIDER_NOT_CONFIGURED"
                }
            
            # 4. 验证API密钥访问权限
            has_api_access = await self.validate_api_key_access(user_id, provider_id)
            if not has_api_access:
                return {
                    "success": False,
                    "error": "没有访问此提供商API的权限",
                    "code": "API_ACCESS_DENIED"
                }
            
            # 5. 执行实际的模型调用（模拟实现）
            # TODO: 这里应该实现真实的模型调用逻辑
            response_text = f"这是来自 {provider_id} 的 {model_id} 模型的回复：{call_data.get('message', '')}"
            
            # 模拟调用延迟
            await asyncio.sleep(0.5)
            call_successful = True
            
            # 6. 计算使用情况
            latency = (time.time() - start_time) * 1000  # 毫秒
            token_usage = {
                "input_tokens": len(call_data.get("message", "")),
                "output_tokens": len(response_text),
                "total_tokens": len(call_data.get("message", "")) + len(response_text)
            }
            
            # 模拟成本计算（实际应该根据提供商价格计算）
            cost = token_usage["total_tokens"] * 0.0001
            
            # 7. 记录使用统计
            if track_usage:
                await self.record_model_usage(
                    user_id=user_id,
                    provider_id=provider_id,
                    model_id=model_id,
                    usage_data={
                        "tokens": token_usage["total_tokens"],
                        "cost": cost,
                        "latency": latency,
                        "error": False
                    }
                )
            
            # 8. 发布模型调用事件
            await self.async_client.publish_event(
                event_type="model_called",
                data={
                    "user_id": user_id,
                    "provider_id": provider_id,
                    "model_id": model_id,
                    "tokens": token_usage["total_tokens"],
                    "cost": cost,
                    "latency": latency,
                    "success": True,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            logger.info(f"模型调用工作流完成: {provider_id}:{model_id}, 延迟: {latency:.1f}ms")
            
            return {
                "success": True,
                "response": response_text,
                "token_usage": token_usage,
                "cost": cost,
                "latency": latency,
                "provider_id": provider_id,
                "model_id": model_id
            }
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"模型调用工作流失败: {e}")
            
            # 记录错误统计
            if track_usage:
                await self.record_model_usage(
                    user_id=user_id,
                    provider_id=provider_id,
                    model_id=model_id,
                    usage_data={
                        "tokens": 0,
                        "cost": 0.0,
                        "latency": (time.time() - start_time) * 1000,
                        "error": True
                    }
                )
            
            # 发布错误事件
            await self.async_client.publish_event(
                event_type="model_call_failed",
                data={
                    "user_id": user_id,
                    "provider_id": provider_id,
                    "model_id": model_id,
                    "error": error_message,
                    "timestamp": datetime.now().isoformat()
                },
                priority="high"
            )
            
            raise
    
    async def batch_model_calls(
        self, 
        user_id: str, 
        calls: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """批量模型调用"""
        try:
            logger.info(f"批量模型调用: {len(calls)} 个请求")
            
            # 并发执行所有调用
            tasks = []
            for call in calls:
                task = asyncio.create_task(
                    self.model_call_workflow(
                        user_id=user_id,
                        provider_id=call["provider_id"],
                        model_id=call["model_id"],
                        call_data=call["call_data"],
                        track_usage=call.get("track_usage", True)
                    )
                )
                tasks.append(task)
            
            # 等待所有任务完成
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            success_count = 0
            failed_count = 0
            processed_results = []
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    failed_count += 1
                    processed_results.append({
                        "success": False,
                        "error": str(result),
                        "call_index": i
                    })
                    logger.error(f"批量调用 {i} 失败: {result}")
                else:
                    success_count += 1
                    processed_results.append(result)
                    logger.debug(f"批量调用 {i} 成功")
            
            # 发布批量调用完成事件
            await self.async_client.publish_event(
                event_type="batch_model_calls_completed",
                data={
                    "user_id": user_id,
                    "total_calls": len(calls),
                    "success_count": success_count,
                    "failed_count": failed_count,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            return processed_results
            
        except Exception as e:
            logger.error(f"批量模型调用失败: {e}")
            raise
    
    # ==================== 模型测试工作流 ====================
    
    async def test_model_workflow(
        self, 
        provider_id: str, 
        model_id: str,
        test_config: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """模型测试的完整工作流"""
        try:
            logger.info(f"开始模型测试工作流: {provider_id}:{model_id}")
            
            # 1. 获取提供商配置
            provider_config = await self.get_provider_config(provider_id, user_id or "system")
            if not provider_config:
                return {
                    "success": False,
                    "error": f"提供商 {provider_id} 未配置",
                    "code": "PROVIDER_NOT_CONFIGURED"
                }
            
            # 2. 执行连接测试
            start_time = time.time()
            
            # 模拟测试调用
            test_message = test_config.get("message", "Hello, this is a test message.")
            
            # TODO: 实现真实的模型测试调用
            await asyncio.sleep(0.3)  # 模拟网络延迟
            
            latency = (time.time() - start_time) * 1000
            test_response = f"Test response from {provider_id} {model_id}: {test_message}"
            
            # 3. 记录测试结果
            test_result = {
                "success": True,
                "provider_id": provider_id,
                "model_id": model_id,
                "latency": round(latency, 2),
                "response": test_response,
                "token_usage": {
                    "input_tokens": len(test_message),
                    "output_tokens": len(test_response),
                    "total_tokens": len(test_message) + len(test_response)
                },
                "test_time": datetime.now().isoformat()
            }
            
            # 4. 发布测试完成事件
            await self.async_client.publish_event(
                event_type="model_tested",
                data={
                    "provider_id": provider_id,
                    "model_id": model_id,
                    "latency": latency,
                    "success": True,
                    "user_id": user_id,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            logger.info(f"模型测试工作流完成: {provider_id}:{model_id}, 延迟: {latency:.1f}ms")
            
            return test_result
            
        except Exception as e:
            logger.error(f"模型测试工作流失败: {e}")
            
            # 发布测试失败事件
            await self.async_client.publish_event(
                event_type="model_test_failed",
                data={
                    "provider_id": provider_id,
                    "model_id": model_id,
                    "error": str(e),
                    "user_id": user_id,
                    "timestamp": datetime.now().isoformat()
                },
                priority="high"
            )
            
            return {
                "success": False,
                "error": str(e),
                "provider_id": provider_id,
                "model_id": model_id,
                "test_time": datetime.now().isoformat()
            }
    
    # ==================== 健康检查和监控 ====================
    
    async def health_check_dependencies(self) -> Dict[str, bool]:
        """检查所有依赖服务的健康状态"""
        services = ["base-service", "database-service", "gateway-service"]
        
        health_status = {}
        for service in services:
            try:
                is_healthy = await self.service_client.health_check(service)
                health_status[service] = is_healthy
                logger.info(f"服务 {service} 健康状态: {'正常' if is_healthy else '异常'}")
            except Exception as e:
                health_status[service] = False
                logger.error(f"检查服务 {service} 健康状态失败: {e}")
        
        return health_status
    
    async def get_service_metrics(self) -> Dict[str, Any]:
        """获取服务调用指标"""
        base_metrics = await self.service_client.get_metrics()
        
        # 添加模型服务特有的指标
        model_metrics = {
            "cached_usage_stats": len(self.usage_stats_cache),
            "last_stats_flush": self.last_stats_flush.isoformat(),
            "stats_flush_interval_minutes": self.stats_flush_interval.total_seconds() / 60
        }
        
        return {
            **base_metrics,
            "model_service_metrics": model_metrics
        }
    
    async def get_system_health_report(self) -> Dict[str, Any]:
        """获取系统健康报告"""
        try:
            # 并行检查所有依赖
            tasks = [
                self.health_check_dependencies(),
                self.get_service_metrics()
            ]
            
            dependency_health, service_metrics = await asyncio.gather(*tasks)
            
            overall_healthy = all(dependency_health.values())
            
            return {
                "overall_healthy": overall_healthy,
                "dependency_services": dependency_health,
                "service_metrics": service_metrics,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取系统健康报告失败: {e}")
            return {
                "overall_healthy": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


# ==================== 便捷的全局函数 ====================

async def call_model_integrated(
    user_id: str, 
    provider_id: str, 
    model_id: str,
    call_data: Dict[str, Any]
) -> Dict[str, Any]:
    """便捷的模型调用函数"""
    async with ModelServiceIntegration() as integration:
        return await integration.model_call_workflow(user_id, provider_id, model_id, call_data)


async def test_model_integrated(
    provider_id: str, 
    model_id: str,
    test_config: Dict[str, Any],
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """便捷的模型测试函数"""
    async with ModelServiceIntegration() as integration:
        return await integration.test_model_workflow(provider_id, model_id, test_config, user_id)


async def batch_call_models_integrated(
    user_id: str, 
    calls: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """便捷的批量模型调用函数"""
    async with ModelServiceIntegration() as integration:
        return await integration.batch_model_calls(user_id, calls) 