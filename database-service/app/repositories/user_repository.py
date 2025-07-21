"""
用户相关的仓库实现
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

from .base import BaseRepository
from ..models.user import User, Role, Permission, UserSettings, ApiKey, UserSession
from ..schemas.user import (
    UserCreate, UserUpdate,
    RoleCreate, RoleUpdate,
    PermissionCreate, PermissionUpdate,
    UserSettingsCreate, UserSettingsUpdate,
    ApiKeyCreate, ApiKeyUpdate
)


class UserRepository(BaseRepository[User, UserCreate, UserUpdate]):
    """用户仓库"""
    
    def __init__(self):
        super().__init__(User)
    
    async def get_by_username(self, db: AsyncSession, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        return await self.get_by_field(db, "username", username)
    
    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        """根据邮箱获取用户"""
        return await self.get_by_field(db, "email", email)
    
    async def get_by_username_or_email(self, db: AsyncSession, identifier: str) -> Optional[User]:
        """根据用户名或邮箱获取用户"""
        query = select(User).where(
            or_(User.username == identifier, User.email == identifier)
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_with_roles(self, db: AsyncSession, user_id: str) -> Optional[User]:
        """获取用户及其角色信息"""
        return await self.get_with_relations(db, user_id, ["roles"])
    
    async def get_with_permissions(self, db: AsyncSession, user_id: str) -> Optional[User]:
        """获取用户及其权限信息"""
        query = select(User).where(User.id == user_id).options(
            selectinload(User.roles).selectinload(Role.permissions)
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def check_username_exists(self, db: AsyncSession, username: str, exclude_id: Optional[str] = None) -> bool:
        """检查用户名是否存在"""
        query = select(User.id).where(User.username == username)
        if exclude_id:
            query = query.where(User.id != exclude_id)
        
        result = await db.execute(query)
        return result.scalar() is not None
    
    async def check_email_exists(self, db: AsyncSession, email: str, exclude_id: Optional[str] = None) -> bool:
        """检查邮箱是否存在"""
        query = select(User.id).where(User.email == email)
        if exclude_id:
            query = query.where(User.id != exclude_id)
        
        result = await db.execute(query)
        return result.scalar() is not None
    
    async def get_active_users(self, db: AsyncSession, skip: int = 0, limit: int = 100) -> List[User]:
        """获取活跃用户列表"""
        return await self.get_multi(db, skip=skip, limit=limit, filters={"disabled": False})
    
    async def get_superusers(self, db: AsyncSession) -> List[User]:
        """获取超级管理员列表"""
        return await self.get_multi(db, filters={"is_superuser": True})
    
    async def update_last_login(self, db: AsyncSession, user_id: str) -> Optional[User]:
        """更新用户最后登录时间"""
        from datetime import datetime
        user = await self.get(db, user_id)
        if user:
            user.last_login = datetime.utcnow()
            await db.commit()
            await db.refresh(user)
        return user
    
    async def search_users(
        self,
        db: AsyncSession,
        query: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[User]:
        """搜索用户"""
        return await self.search(
            db,
            query=query,
            search_fields=["username", "email", "full_name"],
            skip=skip,
            limit=limit
        )


class RoleRepository(BaseRepository[Role, RoleCreate, RoleUpdate]):
    """角色仓库"""
    
    def __init__(self):
        super().__init__(Role)
    
    async def get_by_name(self, db: AsyncSession, name: str) -> Optional[Role]:
        """根据角色名获取角色"""
        return await self.get_by_field(db, "name", name)
    
    async def get_with_permissions(self, db: AsyncSession, role_id: str) -> Optional[Role]:
        """获取角色及其权限信息"""
        return await self.get_with_relations(db, role_id, ["permissions"])
    
    async def get_with_users(self, db: AsyncSession, role_id: str) -> Optional[Role]:
        """获取角色及其用户信息"""
        return await self.get_with_relations(db, role_id, ["users"])
    
    async def get_default_roles(self, db: AsyncSession) -> List[Role]:
        """获取默认角色列表"""
        return await self.get_multi(db, filters={"is_default": True})
    
    async def get_system_roles(self, db: AsyncSession) -> List[Role]:
        """获取系统角色列表"""
        return await self.get_multi(db, filters={"is_system": True})
    
    async def check_name_exists(self, db: AsyncSession, name: str, exclude_id: Optional[str] = None) -> bool:
        """检查角色名是否存在"""
        query = select(Role.id).where(Role.name == name)
        if exclude_id:
            query = query.where(Role.id != exclude_id)
        
        result = await db.execute(query)
        return result.scalar() is not None
    
    async def add_permission(self, db: AsyncSession, role_id: str, permission_id: str) -> bool:
        """为角色添加权限"""
        role = await self.get_with_permissions(db, role_id)
        permission = await PermissionRepository().get(db, permission_id)
        
        if role and permission and permission not in role.permissions:
            role.permissions.append(permission)
            await db.commit()
            return True
        return False
    
    async def remove_permission(self, db: AsyncSession, role_id: str, permission_id: str) -> bool:
        """从角色移除权限"""
        role = await self.get_with_permissions(db, role_id)
        permission = await PermissionRepository().get(db, permission_id)
        
        if role and permission and permission in role.permissions:
            role.permissions.remove(permission)
            await db.commit()
            return True
        return False


class PermissionRepository(BaseRepository[Permission, PermissionCreate, PermissionUpdate]):
    """权限仓库"""
    
    def __init__(self):
        super().__init__(Permission)
    
    async def get_by_code(self, db: AsyncSession, code: str) -> Optional[Permission]:
        """根据权限代码获取权限"""
        return await self.get_by_field(db, "code", code)
    
    async def get_by_resource(self, db: AsyncSession, resource: str) -> List[Permission]:
        """根据资源类型获取权限列表"""
        return await self.get_multi(db, filters={"resource": resource})
    
    async def get_system_permissions(self, db: AsyncSession) -> List[Permission]:
        """获取系统权限列表"""
        return await self.get_multi(db, filters={"is_system": True})
    
    async def check_code_exists(self, db: AsyncSession, code: str, exclude_id: Optional[str] = None) -> bool:
        """检查权限代码是否存在"""
        query = select(Permission.id).where(Permission.code == code)
        if exclude_id:
            query = query.where(Permission.id != exclude_id)
        
        result = await db.execute(query)
        return result.scalar() is not None
    
    async def get_user_permissions(self, db: AsyncSession, user_id: str) -> List[Permission]:
        """获取用户的所有权限"""
        query = select(Permission).join(Role.permissions).join(User.roles).where(User.id == user_id)
        result = await db.execute(query)
        return result.scalars().all()


class UserSettingsRepository(BaseRepository[UserSettings, UserSettingsCreate, UserSettingsUpdate]):
    """用户设置仓库"""
    
    def __init__(self):
        super().__init__(UserSettings)
    
    async def get_by_user_id(self, db: AsyncSession, user_id: str) -> Optional[UserSettings]:
        """根据用户ID获取用户设置"""
        return await self.get_by_field(db, "user_id", user_id)
    
    async def create_or_update(
        self,
        db: AsyncSession,
        user_id: str,
        settings_data: Dict[str, Any]
    ) -> UserSettings:
        """创建或更新用户设置"""
        existing = await self.get_by_user_id(db, user_id)
        
        if existing:
            return await self.update(db, db_obj=existing, obj_in=settings_data)
        else:
            settings_data["user_id"] = user_id
            return await self.create(db, obj_in=UserSettingsCreate(**settings_data))


class ApiKeyRepository(BaseRepository[ApiKey, ApiKeyCreate, ApiKeyUpdate]):
    """API密钥仓库"""
    
    def __init__(self):
        super().__init__(ApiKey)
    
    async def get_by_key(self, db: AsyncSession, key: str) -> Optional[ApiKey]:
        """根据密钥获取API密钥记录"""
        return await self.get_by_field(db, "key", key)
    
    async def get_by_user_id(self, db: AsyncSession, user_id: str) -> List[ApiKey]:
        """根据用户ID获取API密钥列表"""
        return await self.get_multi(db, filters={"user_id": user_id})
    
    async def get_active_keys(self, db: AsyncSession, user_id: str) -> List[ApiKey]:
        """获取用户的活跃API密钥"""
        return await self.get_multi(db, filters={"user_id": user_id, "is_active": True})
    
    async def update_usage(self, db: AsyncSession, key: str) -> Optional[ApiKey]:
        """更新API密钥使用记录"""
        from datetime import datetime
        api_key = await self.get_by_key(db, key)
        if api_key:
            api_key.last_used_at = datetime.utcnow()
            api_key.usage_count += 1
            await db.commit()
            await db.refresh(api_key)
        return api_key
    
    async def check_key_exists(self, db: AsyncSession, key: str) -> bool:
        """检查API密钥是否存在"""
        return await self.exists(db, filters={"key": key})


class UserSessionRepository(BaseRepository[UserSession, Dict[str, Any], Dict[str, Any]]):
    """用户会话仓库"""
    
    def __init__(self):
        super().__init__(UserSession)
    
    async def get_by_token(self, db: AsyncSession, token: str) -> Optional[UserSession]:
        """根据会话令牌获取会话"""
        return await self.get_by_field(db, "session_token", token)
    
    async def get_by_user_id(self, db: AsyncSession, user_id: str) -> List[UserSession]:
        """根据用户ID获取会话列表"""
        return await self.get_multi(db, filters={"user_id": user_id})
    
    async def get_active_sessions(self, db: AsyncSession, user_id: str) -> List[UserSession]:
        """获取用户的活跃会话"""
        return await self.get_multi(db, filters={"user_id": user_id, "is_active": True})
    
    async def update_activity(self, db: AsyncSession, token: str) -> Optional[UserSession]:
        """更新会话活动时间"""
        from datetime import datetime
        session = await self.get_by_token(db, token)
        if session:
            session.last_activity = datetime.utcnow()
            await db.commit()
            await db.refresh(session)
        return session
    
    async def deactivate_session(self, db: AsyncSession, token: str) -> Optional[UserSession]:
        """停用会话"""
        session = await self.get_by_token(db, token)
        if session:
            session.is_active = False
            await db.commit()
            await db.refresh(session)
        return session
    
    async def cleanup_expired_sessions(self, db: AsyncSession) -> int:
        """清理过期会话"""
        from datetime import datetime
        from sqlalchemy import delete
        
        stmt = delete(UserSession).where(UserSession.expires_at < datetime.utcnow())
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount