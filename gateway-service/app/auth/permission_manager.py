"""
权限管理器

负责权限控制和角色管理
"""

import asyncio
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

from app.utils.common.logging_config import get_logger

logger = get_logger(__name__)


class PermissionType(Enum):
    """权限类型"""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    EXECUTE = "execute"


class ResourceType(Enum):
    """资源类型"""
    USER = "user"
    AGENT = "agent"
    KNOWLEDGE = "knowledge"
    MODEL = "model"
    SYSTEM = "system"
    GATEWAY = "gateway"
    FILE = "file"
    TASK = "task"


@dataclass
class Permission:
    """权限定义"""
    name: str
    resource_type: ResourceType
    permission_type: PermissionType
    description: str
    is_system: bool = False  # 是否为系统级权限
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Role:
    """角色定义"""
    name: str
    display_name: str
    description: str
    permissions: Set[str] = field(default_factory=set)
    inherits_from: Set[str] = field(default_factory=set)  # 继承的角色
    is_system: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class PermissionManager:
    """权限管理器"""
    
    def __init__(self):
        self.permissions: Dict[str, Permission] = {}
        self.roles: Dict[str, Role] = {}
        self._permission_cache: Dict[str, Set[str]] = {}  # 角色权限缓存
        self._lock = asyncio.Lock()
        
        # 初始化系统默认权限和角色
        self._init_default_permissions()
        self._init_default_roles()
        
        logger.info("权限管理器已初始化")
    
    def _init_default_permissions(self):
        """初始化默认权限"""
        default_permissions = [
            # 用户管理权限
            Permission("user.read", ResourceType.USER, PermissionType.READ, "查看用户信息", True),
            Permission("user.write", ResourceType.USER, PermissionType.WRITE, "修改用户信息", True),
            Permission("user.delete", ResourceType.USER, PermissionType.DELETE, "删除用户", True),
            Permission("user.admin", ResourceType.USER, PermissionType.ADMIN, "用户管理", True),
            
            # 智能体权限
            Permission("agent.read", ResourceType.AGENT, PermissionType.READ, "查看智能体", True),
            Permission("agent.write", ResourceType.AGENT, PermissionType.WRITE, "修改智能体", True),
            Permission("agent.delete", ResourceType.AGENT, PermissionType.DELETE, "删除智能体", True),
            Permission("agent.execute", ResourceType.AGENT, PermissionType.EXECUTE, "执行智能体", True),
            
            # 知识库权限
            Permission("knowledge.read", ResourceType.KNOWLEDGE, PermissionType.READ, "查看知识库", True),
            Permission("knowledge.write", ResourceType.KNOWLEDGE, PermissionType.WRITE, "修改知识库", True),
            Permission("knowledge.delete", ResourceType.KNOWLEDGE, PermissionType.DELETE, "删除知识库", True),
            
            # 模型权限
            Permission("model.read", ResourceType.MODEL, PermissionType.READ, "查看模型配置", True),
            Permission("model.write", ResourceType.MODEL, PermissionType.WRITE, "修改模型配置", True),
            Permission("model.execute", ResourceType.MODEL, PermissionType.EXECUTE, "调用模型", True),
            
            # 系统权限
            Permission("system.read", ResourceType.SYSTEM, PermissionType.READ, "查看系统信息", True),
            Permission("system.write", ResourceType.SYSTEM, PermissionType.WRITE, "修改系统配置", True),
            Permission("system.admin", ResourceType.SYSTEM, PermissionType.ADMIN, "系统管理", True),
            
            # 网关权限
            Permission("gateway.read", ResourceType.GATEWAY, PermissionType.READ, "查看网关信息", True),
            Permission("gateway.write", ResourceType.GATEWAY, PermissionType.WRITE, "修改网关配置", True),
            Permission("gateway.admin", ResourceType.GATEWAY, PermissionType.ADMIN, "网关管理", True),
            
            # 文件权限
            Permission("file.read", ResourceType.FILE, PermissionType.READ, "查看文件", True),
            Permission("file.write", ResourceType.FILE, PermissionType.WRITE, "上传/修改文件", True),
            Permission("file.delete", ResourceType.FILE, PermissionType.DELETE, "删除文件", True),
            
            # 任务权限
            Permission("task.read", ResourceType.TASK, PermissionType.READ, "查看任务", True),
            Permission("task.write", ResourceType.TASK, PermissionType.WRITE, "创建/修改任务", True),
            Permission("task.execute", ResourceType.TASK, PermissionType.EXECUTE, "执行任务", True),
            Permission("task.admin", ResourceType.TASK, PermissionType.ADMIN, "任务管理", True),
        ]
        
        for perm in default_permissions:
            self.permissions[perm.name] = perm
    
    def _init_default_roles(self):
        """初始化默认角色"""
        # 管理员角色
        admin_role = Role(
            name="admin",
            display_name="系统管理员",
            description="拥有所有权限的系统管理员",
            is_system=True
        )
        admin_role.permissions = set(self.permissions.keys())
        self.roles["admin"] = admin_role
        
        # 普通用户角色
        user_role = Role(
            name="user",
            display_name="普通用户",
            description="基础用户权限",
            is_system=True
        )
        user_role.permissions = {
            "user.read", "agent.read", "agent.execute", 
            "knowledge.read", "model.read", "model.execute",
            "file.read", "file.write", "task.read", "task.write"
        }
        self.roles["user"] = user_role
        
        # 开发者角色
        developer_role = Role(
            name="developer",
            display_name="开发者",
            description="开发者权限，可以管理智能体和知识库",
            is_system=True
        )
        developer_role.permissions = {
            "user.read", 
            "agent.read", "agent.write", "agent.execute",
            "knowledge.read", "knowledge.write",
            "model.read", "model.execute",
            "file.read", "file.write", "file.delete",
            "task.read", "task.write", "task.execute"
        }
        self.roles["developer"] = developer_role
        
        # 只读角色
        readonly_role = Role(
            name="readonly",
            display_name="只读用户",
            description="只能查看信息的用户",
            is_system=True
        )
        readonly_role.permissions = {
            "user.read", "agent.read", "knowledge.read", 
            "model.read", "file.read", "task.read"
        }
        self.roles["readonly"] = readonly_role
        
        # API用户角色
        api_role = Role(
            name="api_user",
            display_name="API用户",
            description="通过API访问的用户",
            is_system=True
        )
        api_role.permissions = {
            "agent.read", "agent.execute",
            "knowledge.read",
            "model.execute",
            "file.read", "file.write"
        }
        self.roles["api_user"] = api_role
        
        # 内部服务角色
        internal_role = Role(
            name="internal_service",
            display_name="内部服务",
            description="微服务间通信使用的角色",
            is_system=True
        )
        internal_role.permissions = set(self.permissions.keys())  # 内部服务拥有所有权限
        self.roles["internal_service"] = internal_role
    
    async def create_permission(
        self, 
        name: str, 
        resource_type: ResourceType,
        permission_type: PermissionType,
        description: str,
        is_system: bool = False
    ) -> bool:
        """创建权限"""
        async with self._lock:
            try:
                if name in self.permissions:
                    logger.warning(f"权限已存在: {name}")
                    return False
                
                permission = Permission(
                    name=name,
                    resource_type=resource_type,
                    permission_type=permission_type,
                    description=description,
                    is_system=is_system
                )
                
                self.permissions[name] = permission
                self._clear_cache()
                
                logger.info(f"权限创建成功: {name}")
                return True
                
            except Exception as e:
                logger.error(f"创建权限失败: {str(e)}")
                return False
    
    async def create_role(
        self, 
        name: str, 
        display_name: str,
        description: str,
        permissions: Optional[List[str]] = None,
        inherits_from: Optional[List[str]] = None,
        is_system: bool = False
    ) -> bool:
        """创建角色"""
        async with self._lock:
            try:
                if name in self.roles:
                    logger.warning(f"角色已存在: {name}")
                    return False
                
                # 验证权限是否存在
                if permissions:
                    for perm in permissions:
                        if perm not in self.permissions:
                            logger.error(f"权限不存在: {perm}")
                            return False
                
                # 验证继承角色是否存在
                if inherits_from:
                    for role in inherits_from:
                        if role not in self.roles:
                            logger.error(f"继承角色不存在: {role}")
                            return False
                
                role = Role(
                    name=name,
                    display_name=display_name,
                    description=description,
                    permissions=set(permissions or []),
                    inherits_from=set(inherits_from or []),
                    is_system=is_system
                )
                
                self.roles[name] = role
                self._clear_cache()
                
                logger.info(f"角色创建成功: {name}")
                return True
                
            except Exception as e:
                logger.error(f"创建角色失败: {str(e)}")
                return False
    
    def get_role_permissions(self, role_name: str) -> Set[str]:
        """获取角色的所有权限（包括继承的权限）"""
        if role_name in self._permission_cache:
            return self._permission_cache[role_name]
        
        permissions = set()
        visited = set()
        
        def _collect_permissions(role_name: str):
            if role_name in visited or role_name not in self.roles:
                return
            
            visited.add(role_name)
            role = self.roles[role_name]
            
            # 添加直接权限
            permissions.update(role.permissions)
            
            # 递归添加继承的权限
            for inherited_role in role.inherits_from:
                _collect_permissions(inherited_role)
        
        _collect_permissions(role_name)
        
        # 缓存结果
        self._permission_cache[role_name] = permissions
        return permissions
    
    def check_permission(self, user, permission: str) -> bool:
        """检查用户是否拥有指定权限"""
        try:
            # 获取用户的所有权限
            user_permissions = set()
            
            # 通过角色获取权限
            for role_name in user.roles:
                role_permissions = self.get_role_permissions(role_name)
                user_permissions.update(role_permissions)
            
            # 添加直接赋予的权限
            if hasattr(user, 'permissions') and user.permissions:
                user_permissions.update(user.permissions)
            
            return permission in user_permissions
            
        except Exception as e:
            logger.error(f"权限检查失败: {str(e)}")
            return False
    
    def check_any_permission(self, user, permissions: List[str]) -> bool:
        """检查用户是否拥有任一权限"""
        return any(self.check_permission(user, perm) for perm in permissions)
    
    def check_all_permissions(self, user, permissions: List[str]) -> bool:
        """检查用户是否拥有所有权限"""
        return all(self.check_permission(user, perm) for perm in permissions)
    
    def get_user_permissions(self, user) -> Set[str]:
        """获取用户的所有权限"""
        permissions = set()
        
        # 通过角色获取权限
        for role_name in user.roles:
            role_permissions = self.get_role_permissions(role_name)
            permissions.update(role_permissions)
        
        # 添加直接赋予的权限
        if hasattr(user, 'permissions') and user.permissions:
            permissions.update(user.permissions)
        
        return permissions
    
    def get_resource_permissions(self, resource_type: ResourceType) -> List[Permission]:
        """获取资源相关的所有权限"""
        return [perm for perm in self.permissions.values() if perm.resource_type == resource_type]
    
    def list_permissions(self, include_system: bool = True) -> List[Permission]:
        """列出所有权限"""
        if include_system:
            return list(self.permissions.values())
        else:
            return [perm for perm in self.permissions.values() if not perm.is_system]
    
    def list_roles(self, include_system: bool = True) -> List[Role]:
        """列出所有角色"""
        if include_system:
            return list(self.roles.values())
        else:
            return [role for role in self.roles.values() if not role.is_system]
    
    def get_permission(self, name: str) -> Optional[Permission]:
        """获取权限信息"""
        return self.permissions.get(name)
    
    def get_role(self, name: str) -> Optional[Role]:
        """获取角色信息"""
        return self.roles.get(name)
    
    async def update_role_permissions(self, role_name: str, permissions: List[str]) -> bool:
        """更新角色权限"""
        async with self._lock:
            try:
                if role_name not in self.roles:
                    logger.error(f"角色不存在: {role_name}")
                    return False
                
                role = self.roles[role_name]
                
                # 检查是否为系统角色
                if role.is_system:
                    logger.error(f"不能修改系统角色: {role_name}")
                    return False
                
                # 验证权限是否存在
                for perm in permissions:
                    if perm not in self.permissions:
                        logger.error(f"权限不存在: {perm}")
                        return False
                
                role.permissions = set(permissions)
                self._clear_cache()
                
                logger.info(f"角色权限更新成功: {role_name}")
                return True
                
            except Exception as e:
                logger.error(f"更新角色权限失败: {str(e)}")
                return False
    
    async def delete_permission(self, name: str) -> bool:
        """删除权限"""
        async with self._lock:
            try:
                if name not in self.permissions:
                    logger.warning(f"权限不存在: {name}")
                    return False
                
                permission = self.permissions[name]
                
                # 检查是否为系统权限
                if permission.is_system:
                    logger.error(f"不能删除系统权限: {name}")
                    return False
                
                # 从所有角色中移除该权限
                for role in self.roles.values():
                    role.permissions.discard(name)
                
                del self.permissions[name]
                self._clear_cache()
                
                logger.info(f"权限删除成功: {name}")
                return True
                
            except Exception as e:
                logger.error(f"删除权限失败: {str(e)}")
                return False
    
    async def delete_role(self, name: str) -> bool:
        """删除角色"""
        async with self._lock:
            try:
                if name not in self.roles:
                    logger.warning(f"角色不存在: {name}")
                    return False
                
                role = self.roles[name]
                
                # 检查是否为系统角色
                if role.is_system:
                    logger.error(f"不能删除系统角色: {name}")
                    return False
                
                # 检查是否有其他角色继承该角色
                for other_role in self.roles.values():
                    if name in other_role.inherits_from:
                        logger.error(f"角色被其他角色继承，不能删除: {name}")
                        return False
                
                del self.roles[name]
                self._clear_cache()
                
                logger.info(f"角色删除成功: {name}")
                return True
                
            except Exception as e:
                logger.error(f"删除角色失败: {str(e)}")
                return False
    
    def _clear_cache(self):
        """清空权限缓存"""
        self._permission_cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取权限管理统计信息"""
        return {
            "total_permissions": len(self.permissions),
            "system_permissions": len([p for p in self.permissions.values() if p.is_system]),
            "custom_permissions": len([p for p in self.permissions.values() if not p.is_system]),
            "total_roles": len(self.roles),
            "system_roles": len([r for r in self.roles.values() if r.is_system]),
            "custom_roles": len([r for r in self.roles.values() if not r.is_system]),
            "cache_size": len(self._permission_cache)
        } 