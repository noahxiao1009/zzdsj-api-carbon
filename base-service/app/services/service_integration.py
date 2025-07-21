"""
基础服务集成模块
Base Service Integration

该模块负责用户管理、权限控制、资源所有权管理等核心基础服务功能
基于统一ServiceClient SDK实现高效的微服务间通信与协作
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime, timedelta
import sys
import os
import hashlib
import jwt
from enum import Enum

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


class UserRole(str, Enum):
    """用户角色枚举"""
    ADMIN = "admin"
    USER = "user"
    EDITOR = "editor"
    VIEWER = "viewer"


class PermissionAction(str, Enum):
    """权限操作枚举"""
    READ = "read"
    WRITE = "write"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    MANAGE = "manage"
    ALL = "*"


class ResourceType(str, Enum):
    """资源类型枚举"""
    USER = "user"
    KNOWLEDGE_BASE = "knowledge_base"
    AGENT = "agent"
    MODEL = "model"
    SYSTEM = "system"
    FILE = "file"


class BaseServiceIntegration:
    """基础服务集成类 - 用户权限核心服务"""
    
    def __init__(self):
        self.service_client = None
        self.async_client = None
        
        # 针对基础服务的专用配置
        self.database_config = CallConfig(
            timeout=20,   # 权限数据查询可能较复杂
            retry_times=3,
            retry_strategy=RetryStrategy.LINEAR,
            circuit_breaker_enabled=True
        )
        
        self.gateway_config = CallConfig(
            timeout=5,    # 服务注册要快
            retry_times=3,
            retry_strategy=RetryStrategy.LINEAR
        )
        
        self.system_config = CallConfig(
            timeout=15,   # 系统配置查询
            retry_times=2,
            retry_strategy=RetryStrategy.LINEAR
        )
        
        # 权限缓存
        self.permission_cache = {}
        self.user_cache = {}
        self.role_cache = {}
        self.cache_ttl = timedelta(minutes=15)  # 15分钟缓存
    
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
    
    # ==================== 用户管理 ====================
    
    async def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建用户"""
        try:
            logger.info(f"创建用户: {user_data.get('username')}")
            
            # 1. 数据验证和处理
            user_record = {
                "username": user_data["username"],
                "email": user_data["email"],
                "password_hash": self._hash_password(user_data["password"]),
                "full_name": user_data.get("full_name"),
                "role": user_data.get("role", UserRole.USER),
                "status": "active",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "metadata": user_data.get("metadata", {})
            }
            
            # 2. 保存到数据库
            result = await self.service_client.call(
                service_name="database-service",
                method=CallMethod.POST,
                path="/api/v1/users",
                config=self.database_config,
                json=user_record
            )
            
            if not result.get("success"):
                return result
            
            user_id = result.get("user_id")
            
            # 3. 创建默认权限（基于角色）
            await self._assign_default_permissions(user_id, user_record["role"])
            
            # 4. 发布用户创建事件
            await self.async_client.publish_event(
                event_type="user_created",
                data={
                    "user_id": user_id,
                    "username": user_record["username"],
                    "email": user_record["email"],
                    "role": user_record["role"],
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            # 5. 返回用户信息（脱敏）
            sanitized_user = {k: v for k, v in user_record.items() if k != "password_hash"}
            sanitized_user["user_id"] = user_id
            
            logger.info(f"用户创建成功: {user_id}")
            
            return {
                "success": True,
                "user_id": user_id,
                "user": sanitized_user
            }
            
        except ServiceCallError as e:
            logger.error(f"创建用户失败: {e}")
            raise
        except Exception as e:
            logger.error(f"创建用户异常: {e}")
            raise
    
    async def get_user_by_id(self, user_id: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """根据ID获取用户信息"""
        try:
            # 检查缓存
            if use_cache:
                cached_user = self._get_from_cache(self.user_cache, f"user:{user_id}")
                if cached_user:
                    return cached_user
            
            result = await self.service_client.call(
                service_name="database-service",
                method=CallMethod.GET,
                path=f"/api/v1/users/{user_id}",
                config=self.database_config
            )
            
            if not result.get("success"):
                return None
            
            user_data = result.get("user")
            
            # 脱敏处理
            if user_data and "password_hash" in user_data:
                del user_data["password_hash"]
            
            # 缓存用户信息
            if use_cache and user_data:
                self._set_cache(self.user_cache, f"user:{user_id}", user_data)
            
            return user_data
            
        except ServiceCallError as e:
            if e.status_code == 404:
                return None
            logger.error(f"获取用户信息失败: {e}")
            raise
        except Exception as e:
            logger.error(f"获取用户信息异常: {e}")
            raise
    
    async def update_user(self, user_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """更新用户信息"""
        try:
            logger.info(f"更新用户: {user_id}")
            
            # 处理密码更新
            if "password" in update_data:
                update_data["password_hash"] = self._hash_password(update_data.pop("password"))
            
            update_data["updated_at"] = datetime.now().isoformat()
            
            result = await self.service_client.call(
                service_name="database-service",
                method=CallMethod.PUT,
                path=f"/api/v1/users/{user_id}",
                config=self.database_config,
                json=update_data
            )
            
            if result.get("success"):
                # 清空用户缓存
                self._remove_from_cache(self.user_cache, f"user:{user_id}")
                
                # 发布用户更新事件
                await self.async_client.publish_event(
                    event_type="user_updated",
                    data={
                        "user_id": user_id,
                        "updated_fields": list(update_data.keys()),
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            return result
            
        except Exception as e:
            logger.error(f"更新用户失败: {e}")
            raise
    
    async def authenticate_user(self, username: str, password: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """用户认证"""
        try:
            logger.info(f"用户认证: {username}")
            
            # 获取用户信息（包含密码哈希）
            result = await self.service_client.call(
                service_name="database-service",
                method=CallMethod.GET,
                path="/api/v1/users/by-username",
                config=self.database_config,
                params={"username": username, "include_password": True}
            )
            
            if not result.get("success"):
                return False, None
            
            user_data = result.get("user")
            if not user_data:
                return False, None
            
            # 验证密码
            stored_hash = user_data.get("password_hash")
            if not self._verify_password(password, stored_hash):
                # 记录认证失败
                await self.async_client.publish_event(
                    event_type="auth_failed",
                    data={
                        "username": username,
                        "reason": "invalid_password",
                        "ip_address": None,  # TODO: 获取真实IP
                        "timestamp": datetime.now().isoformat()
                    },
                    priority="high"
                )
                return False, None
            
            # 检查用户状态
            if user_data.get("status") != "active":
                await self.async_client.publish_event(
                    event_type="auth_failed",
                    data={
                        "username": username,
                        "reason": "user_inactive",
                        "user_status": user_data.get("status"),
                        "timestamp": datetime.now().isoformat()
                    },
                    priority="high"
                )
                return False, None
            
            # 脱敏处理
            sanitized_user = {k: v for k, v in user_data.items() if k != "password_hash"}
            
            # 记录认证成功
            await self.async_client.publish_event(
                event_type="auth_success",
                data={
                    "user_id": sanitized_user["user_id"],
                    "username": username,
                    "role": sanitized_user.get("role"),
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            logger.info(f"用户认证成功: {username}")
            
            return True, sanitized_user
            
        except Exception as e:
            logger.error(f"用户认证异常: {e}")
            return False, None
    
    # ==================== 权限管理 ====================
    
    async def check_permission(
        self, 
        user_id: str, 
        resource_type: str, 
        action: str,
        resource_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """检查用户权限"""
        try:
            # 构建权限检查缓存键
            cache_key = f"perm:{user_id}:{resource_type}:{action}:{resource_id or 'none'}"
            
            # 检查缓存
            cached_result = self._get_from_cache(self.permission_cache, cache_key)
            if cached_result is not None:
                return cached_result
            
            logger.debug(f"权限检查: user={user_id}, resource={resource_type}, action={action}, resource_id={resource_id}")
            
            # 1. 获取用户信息
            user = await self.get_user_by_id(user_id)
            if not user:
                return False
            
            # 2. 管理员拥有所有权限
            if user.get("role") == UserRole.ADMIN:
                self._set_cache(self.permission_cache, cache_key, True)
                return True
            
            # 3. 检查资源所有权（用户对自己的资源有完全权限）
            if resource_id and await self._is_resource_owner(user_id, resource_type, resource_id):
                self._set_cache(self.permission_cache, cache_key, True)
                return True
            
            # 4. 查询用户权限
            permission_result = await self.service_client.call(
                service_name="database-service",
                method=CallMethod.POST,
                path="/api/v1/permissions/check",
                config=self.database_config,
                json={
                    "user_id": user_id,
                    "resource_type": resource_type,
                    "action": action,
                    "resource_id": resource_id,
                    "context": context or {}
                }
            )
            
            has_permission = permission_result.get("has_permission", False)
            
            # 5. 缓存结果
            self._set_cache(self.permission_cache, cache_key, has_permission)
            
            # 6. 记录权限检查（仅失败时）
            if not has_permission:
                await self.async_client.publish_event(
                    event_type="permission_denied",
                    data={
                        "user_id": user_id,
                        "resource_type": resource_type,
                        "action": action,
                        "resource_id": resource_id,
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            return has_permission
            
        except ServiceCallError as e:
            logger.error(f"权限检查失败: {e}")
            # 服务不可用时，根据操作类型决定默认策略
            if e.status_code == 503:
                if action == PermissionAction.READ:
                    return True  # 读操作默认允许
                else:
                    return False  # 写操作默认拒绝
            return False
        except Exception as e:
            logger.error(f"权限检查异常: {e}")
            return False
    
    async def assign_permission(
        self, 
        user_id: str, 
        resource_type: str, 
        actions: List[str],
        resource_id: Optional[str] = None,
        granted_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """分配权限给用户"""
        try:
            logger.info(f"分配权限: user={user_id}, resource={resource_type}, actions={actions}")
            
            permission_data = {
                "user_id": user_id,
                "resource_type": resource_type,
                "actions": actions,
                "resource_id": resource_id,
                "granted_by": granted_by,
                "granted_at": datetime.now().isoformat()
            }
            
            result = await self.service_client.call(
                service_name="database-service",
                method=CallMethod.POST,
                path="/api/v1/user_permissions",
                config=self.database_config,
                json=permission_data
            )
            
            if result.get("success"):
                # 清空相关权限缓存
                self._clear_user_permission_cache(user_id)
                
                # 发布权限分配事件
                await self.async_client.publish_event(
                    event_type="permission_granted",
                    data={
                        "user_id": user_id,
                        "resource_type": resource_type,
                        "actions": actions,
                        "resource_id": resource_id,
                        "granted_by": granted_by,
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            return result
            
        except Exception as e:
            logger.error(f"分配权限失败: {e}")
            raise
    
    async def revoke_permission(
        self, 
        user_id: str, 
        resource_type: str, 
        actions: List[str],
        resource_id: Optional[str] = None,
        revoked_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """撤销用户权限"""
        try:
            logger.info(f"撤销权限: user={user_id}, resource={resource_type}, actions={actions}")
            
            revoke_data = {
                "user_id": user_id,
                "resource_type": resource_type,
                "actions": actions,
                "resource_id": resource_id,
                "revoked_by": revoked_by,
                "revoked_at": datetime.now().isoformat()
            }
            
            result = await self.service_client.call(
                service_name="database-service",
                method=CallMethod.DELETE,
                path="/api/v1/user_permissions",
                config=self.database_config,
                json=revoke_data
            )
            
            if result.get("success"):
                # 清空相关权限缓存
                self._clear_user_permission_cache(user_id)
                
                # 发布权限撤销事件
                await self.async_client.publish_event(
                    event_type="permission_revoked",
                    data={
                        "user_id": user_id,
                        "resource_type": resource_type,
                        "actions": actions,
                        "resource_id": resource_id,
                        "revoked_by": revoked_by,
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            return result
            
        except Exception as e:
            logger.error(f"撤销权限失败: {e}")
            raise
    
    # ==================== 资源管理 ====================
    
    async def register_resource(
        self, 
        resource_type: str, 
        resource_id: str,
        owner_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """注册资源"""
        try:
            logger.info(f"注册资源: type={resource_type}, id={resource_id}, owner={owner_id}")
            
            resource_data = {
                "resource_type": resource_type,
                "resource_id": resource_id,
                "owner_id": owner_id,
                "metadata": metadata or {},
                "created_at": datetime.now().isoformat()
            }
            
            result = await self.service_client.call(
                service_name="database-service",
                method=CallMethod.POST,
                path="/api/v1/resources",
                config=self.database_config,
                json=resource_data
            )
            
            if result.get("success"):
                # 发布资源注册事件
                await self.async_client.publish_event(
                    event_type="resource_registered",
                    data={
                        "resource_type": resource_type,
                        "resource_id": resource_id,
                        "owner_id": owner_id,
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            return result
            
        except Exception as e:
            logger.error(f"注册资源失败: {e}")
            raise
    
    async def transfer_resource_ownership(
        self, 
        resource_type: str, 
        resource_id: str,
        current_owner_id: str,
        new_owner_id: str,
        transfer_reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """转移资源所有权"""
        try:
            logger.info(f"转移资源所有权: {resource_type}:{resource_id} from {current_owner_id} to {new_owner_id}")
            
            transfer_data = {
                "resource_type": resource_type,
                "resource_id": resource_id,
                "current_owner_id": current_owner_id,
                "new_owner_id": new_owner_id,
                "transfer_reason": transfer_reason,
                "transferred_at": datetime.now().isoformat()
            }
            
            result = await self.service_client.call(
                service_name="database-service",
                method=CallMethod.PUT,
                path=f"/api/v1/resources/{resource_type}/{resource_id}/transfer",
                config=self.database_config,
                json=transfer_data
            )
            
            if result.get("success"):
                # 清空相关权限缓存
                self._clear_user_permission_cache(current_owner_id)
                self._clear_user_permission_cache(new_owner_id)
                
                # 发布所有权转移事件
                await self.async_client.publish_event(
                    event_type="resource_ownership_transferred",
                    data={
                        "resource_type": resource_type,
                        "resource_id": resource_id,
                        "previous_owner": current_owner_id,
                        "new_owner": new_owner_id,
                        "transfer_reason": transfer_reason,
                        "timestamp": datetime.now().isoformat()
                    },
                    priority="high"
                )
            
            return result
            
        except Exception as e:
            logger.error(f"转移资源所有权失败: {e}")
            raise
    
    async def get_user_resources(
        self, 
        user_id: str, 
        resource_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取用户拥有的资源列表"""
        try:
            params = {"user_id": user_id}
            if resource_type:
                params["resource_type"] = resource_type
            
            result = await self.service_client.call(
                service_name="database-service",
                method=CallMethod.GET,
                path="/api/v1/resources/by-owner",
                config=self.database_config,
                params=params
            )
            
            return result.get("resources", [])
            
        except ServiceCallError as e:
            logger.error(f"获取用户资源失败: {e}")
            if e.status_code == 503:
                return []
            raise
        except Exception as e:
            logger.error(f"获取用户资源异常: {e}")
            raise
    
    # ==================== 配额管理 ====================
    
    async def get_user_quota(self, user_id: str, resource_type: str) -> Dict[str, Any]:
        """获取用户配额信息"""
        try:
            result = await self.service_client.call(
                service_name="database-service",
                method=CallMethod.GET,
                path=f"/api/v1/users/{user_id}/quota",
                config=self.database_config,
                params={"resource_type": resource_type}
            )
            
            if result.get("success"):
                return result.get("quota", {})
            else:
                # 返回默认配额
                return self._get_default_quota(resource_type)
            
        except ServiceCallError as e:
            logger.error(f"获取用户配额失败: {e}")
            if e.status_code == 503:
                return self._get_default_quota(resource_type)
            raise
        except Exception as e:
            logger.error(f"获取用户配额异常: {e}")
            raise
    
    async def update_user_quota(
        self, 
        user_id: str, 
        resource_type: str, 
        quota_updates: Dict[str, Any],
        updated_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """更新用户配额"""
        try:
            logger.info(f"更新用户配额: user={user_id}, resource={resource_type}")
            
            quota_data = {
                "user_id": user_id,
                "resource_type": resource_type,
                "quota_updates": quota_updates,
                "updated_by": updated_by,
                "updated_at": datetime.now().isoformat()
            }
            
            result = await self.service_client.call(
                service_name="database-service",
                method=CallMethod.PUT,
                path=f"/api/v1/users/{user_id}/quota",
                config=self.database_config,
                json=quota_data
            )
            
            if result.get("success"):
                # 发布配额更新事件
                await self.async_client.publish_event(
                    event_type="user_quota_updated",
                    data={
                        "user_id": user_id,
                        "resource_type": resource_type,
                        "quota_updates": quota_updates,
                        "updated_by": updated_by,
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            return result
            
        except Exception as e:
            logger.error(f"更新用户配额失败: {e}")
            raise
    
    # ==================== 服务注册 ====================
    
    async def register_with_gateway(self, service_info: Dict[str, Any]) -> bool:
        """向网关注册基础服务"""
        try:
            logger.info("向网关注册基础服务")
            
            registration_data = {
                "service_name": "base-service",
                "service_url": service_info.get("url", "http://localhost:8001"),
                "health_check_url": "/api/v1/health",
                "service_type": "core",
                "capabilities": [
                    "user_management",
                    "authentication",
                    "authorization",
                    "permission_control",
                    "resource_management",
                    "quota_management"
                ],
                "metadata": {
                    "version": service_info.get("version", "1.0.0"),
                    "api_endpoints": [
                        "/api/v1/auth/login",
                        "/api/v1/users",
                        "/api/v1/permissions",
                        "/api/v1/resources"
                    ],
                    "auth_provider": True,
                    "permission_provider": True
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
                logger.info("基础服务注册成功")
                
                # 发布服务注册事件
                await self.async_client.publish_event(
                    event_type="service_registered",
                    data={
                        "service_name": "base-service",
                        "capabilities": registration_data["capabilities"],
                        "timestamp": datetime.now().isoformat()
                    }
                )
                
                return True
            else:
                logger.error(f"基础服务注册失败: {result}")
                return False
            
        except ServiceCallError as e:
            logger.error(f"向网关注册失败: {e}")
            return False
        except Exception as e:
            logger.error(f"向网关注册异常: {e}")
            return False
    
    # ==================== 辅助方法 ====================
    
    def _hash_password(self, password: str) -> str:
        """密码哈希"""
        import bcrypt
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def _verify_password(self, password: str, hashed: str) -> bool:
        """验证密码"""
        import bcrypt
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    
    async def _assign_default_permissions(self, user_id: str, role: str):
        """分配默认权限"""
        try:
            default_permissions = {
                UserRole.ADMIN: [
                    (ResourceType.USER, [PermissionAction.ALL]),
                    (ResourceType.KNOWLEDGE_BASE, [PermissionAction.ALL]),
                    (ResourceType.AGENT, [PermissionAction.ALL]),
                    (ResourceType.MODEL, [PermissionAction.ALL]),
                    (ResourceType.SYSTEM, [PermissionAction.ALL])
                ],
                UserRole.EDITOR: [
                    (ResourceType.USER, [PermissionAction.READ]),
                    (ResourceType.KNOWLEDGE_BASE, [PermissionAction.READ, PermissionAction.CREATE, PermissionAction.UPDATE]),
                    (ResourceType.AGENT, [PermissionAction.READ, PermissionAction.CREATE, PermissionAction.UPDATE]),
                    (ResourceType.MODEL, [PermissionAction.READ])
                ],
                UserRole.USER: [
                    (ResourceType.USER, [PermissionAction.READ]),
                    (ResourceType.KNOWLEDGE_BASE, [PermissionAction.READ, PermissionAction.CREATE]),
                    (ResourceType.AGENT, [PermissionAction.READ, PermissionAction.CREATE]),
                    (ResourceType.MODEL, [PermissionAction.READ])
                ]
            }
            
            permissions = default_permissions.get(role, default_permissions[UserRole.USER])
            
            for resource_type, actions in permissions:
                await self.assign_permission(
                    user_id=user_id,
                    resource_type=resource_type,
                    actions=actions,
                    granted_by="system"
                )
                
        except Exception as e:
            logger.error(f"分配默认权限失败: {e}")
    
    async def _is_resource_owner(self, user_id: str, resource_type: str, resource_id: str) -> bool:
        """检查用户是否为资源所有者"""
        try:
            result = await self.service_client.call(
                service_name="database-service",
                method=CallMethod.GET,
                path=f"/api/v1/resources/{resource_type}/{resource_id}/owner",
                config=self.database_config
            )
            
            return result.get("owner_id") == user_id
            
        except Exception as e:
            logger.error(f"检查资源所有权失败: {e}")
            return False
    
    def _get_default_quota(self, resource_type: str) -> Dict[str, Any]:
        """获取默认配额"""
        default_quotas = {
            ResourceType.KNOWLEDGE_BASE: {
                "max_knowledge_bases": 10,
                "max_documents_per_kb": 1000,
                "max_storage_mb": 1024
            },
            ResourceType.AGENT: {
                "max_agents": 50,
                "max_team_size": 10,
                "max_execution_time_minutes": 30
            },
            ResourceType.MODEL: {
                "daily_calls": 1000,
                "monthly_calls": 30000,
                "max_tokens_per_call": 4000
            }
        }
        
        return default_quotas.get(resource_type, {})
    
    def _get_from_cache(self, cache: Dict, key: str) -> Any:
        """从缓存获取数据"""
        if key in cache:
            value, timestamp = cache[key]
            if datetime.now() - timestamp < self.cache_ttl:
                return value
            else:
                del cache[key]
        return None
    
    def _set_cache(self, cache: Dict, key: str, value: Any):
        """设置缓存"""
        cache[key] = (value, datetime.now())
    
    def _remove_from_cache(self, cache: Dict, key: str):
        """从缓存移除"""
        cache.pop(key, None)
    
    def _clear_user_permission_cache(self, user_id: str):
        """清空用户权限缓存"""
        keys_to_remove = [k for k in self.permission_cache.keys() if k.startswith(f"perm:{user_id}:")]
        for key in keys_to_remove:
            del self.permission_cache[key]
    
    async def health_check_dependencies(self) -> Dict[str, bool]:
        """检查所有依赖服务的健康状态"""
        services = ["database-service", "gateway-service", "system-service"]
        
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


# ==================== 便捷的全局函数 ====================

async def check_user_permission_integrated(
    user_id: str, 
    resource_type: str, 
    action: str,
    resource_id: Optional[str] = None
) -> bool:
    """便捷的权限检查函数"""
    async with BaseServiceIntegration() as integration:
        return await integration.check_permission(user_id, resource_type, action, resource_id)


async def authenticate_user_integrated(username: str, password: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """便捷的用户认证函数"""
    async with BaseServiceIntegration() as integration:
        return await integration.authenticate_user(username, password)


async def create_user_integrated(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """便捷的用户创建函数"""
    async with BaseServiceIntegration() as integration:
        return await integration.create_user(user_data) 