"""
PostgreSQL数据迁移器
专门处理PostgreSQL数据库的迁移操作
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine

from ...models.database import get_db_session
from ...config.database_config import get_database_config

logger = logging.getLogger(__name__)


class PostgresMigrator:
    """PostgreSQL数据迁移器"""
    
    def __init__(self):
        self.config = get_database_config()
    
    async def migrate_users_data(self, source_db_url: str) -> bool:
        """迁移用户数据"""
        try:
            logger.info("开始迁移用户数据...")
            
            # 创建源数据库连接
            source_engine = create_engine(source_db_url)
            
            async with get_db_session() as target_db:
                # 迁移用户表
                await self._migrate_users_table(source_engine, target_db)
                
                # 迁移角色表
                await self._migrate_roles_table(source_engine, target_db)
                
                # 迁移权限表
                await self._migrate_permissions_table(source_engine, target_db)
                
                # 迁移用户设置表
                await self._migrate_user_settings_table(source_engine, target_db)
            
            source_engine.dispose()
            logger.info("用户数据迁移完成")
            return True
            
        except Exception as e:
            logger.error(f"用户数据迁移失败: {e}")
            return False
    
    async def _migrate_users_table(self, source_engine, target_db):
        """迁移用户表"""
        from ...models.user import User
        from ...repositories.user_repository import UserRepository
        
        user_repo = UserRepository()
        
        # 从源数据库读取用户数据
        with source_engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM users"))
            users_data = result.fetchall()
        
        # 转换并插入目标数据库
        for user_row in users_data:
            user_data = {
                "id": user_row.id,
                "username": user_row.username,
                "email": user_row.email,
                "hashed_password": user_row.hashed_password,
                "full_name": user_row.full_name,
                "disabled": user_row.disabled,
                "is_superuser": user_row.is_superuser,
                "last_login": user_row.last_login,
                "created_at": user_row.created_at,
                "updated_at": user_row.updated_at,
                "avatar_url": user_row.avatar_url
            }
            
            # 检查用户是否已存在
            existing = await user_repo.get(target_db, user_row.id)
            if not existing:
                await user_repo.create(target_db, obj_in=user_data)
                logger.info(f"迁移用户: {user_row.username}")
    
    async def _migrate_roles_table(self, source_engine, target_db):
        """迁移角色表"""
        from ...models.user import Role
        from ...repositories.user_repository import RoleRepository
        
        role_repo = RoleRepository()
        
        # 从源数据库读取角色数据
        with source_engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM roles"))
            roles_data = result.fetchall()
        
        # 转换并插入目标数据库
        for role_row in roles_data:
            role_data = {
                "id": role_row.id,
                "name": role_row.name,
                "description": role_row.description,
                "is_default": role_row.is_default,
                "created_at": role_row.created_at,
                "updated_at": role_row.updated_at
            }
            
            # 检查角色是否已存在
            existing = await role_repo.get(target_db, role_row.id)
            if not existing:
                await role_repo.create(target_db, obj_in=role_data)
                logger.info(f"迁移角色: {role_row.name}")
    
    async def _migrate_permissions_table(self, source_engine, target_db):
        """迁移权限表"""
        from ...models.user import Permission
        from ...repositories.user_repository import PermissionRepository
        
        permission_repo = PermissionRepository()
        
        # 从源数据库读取权限数据
        with source_engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM permissions"))
            permissions_data = result.fetchall()
        
        # 转换并插入目标数据库
        for perm_row in permissions_data:
            perm_data = {
                "id": perm_row.id,
                "name": perm_row.name,
                "code": perm_row.code,
                "description": perm_row.description,
                "resource": perm_row.resource,
                "created_at": perm_row.created_at,
                "updated_at": perm_row.updated_at
            }
            
            # 检查权限是否已存在
            existing = await permission_repo.get(target_db, perm_row.id)
            if not existing:
                await permission_repo.create(target_db, obj_in=perm_data)
                logger.info(f"迁移权限: {perm_row.code}")
    
    async def _migrate_user_settings_table(self, source_engine, target_db):
        """迁移用户设置表"""
        from ...models.user import UserSettings
        from ...repositories.user_repository import UserSettingsRepository
        
        settings_repo = UserSettingsRepository()
        
        # 从源数据库读取用户设置数据
        with source_engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM user_settings"))
            settings_data = result.fetchall()
        
        # 转换并插入目标数据库
        for settings_row in settings_data:
            settings_data = {
                "id": settings_row.id,
                "user_id": settings_row.user_id,
                "theme": settings_row.theme,
                "language": settings_row.language,
                "notification_enabled": settings_row.notification_enabled,
                "created_at": settings_row.created_at,
                "updated_at": settings_row.updated_at
            }
            
            # 检查设置是否已存在
            existing = await settings_repo.get(target_db, settings_row.id)
            if not existing:
                await settings_repo.create(target_db, obj_in=settings_data)
                logger.info(f"迁移用户设置: {settings_row.user_id}")
    
    async def migrate_assistants_data(self, source_db_url: str) -> bool:
        """迁移助手数据"""
        try:
            logger.info("开始迁移助手数据...")
            
            # 创建源数据库连接
            source_engine = create_engine(source_db_url)
            
            async with get_db_session() as target_db:
                # 迁移助手表
                await self._migrate_assistants_table(source_engine, target_db)
                
                # 迁移对话表
                await self._migrate_conversations_table(source_engine, target_db)
                
                # 迁移消息表
                await self._migrate_messages_table(source_engine, target_db)
            
            source_engine.dispose()
            logger.info("助手数据迁移完成")
            return True
            
        except Exception as e:
            logger.error(f"助手数据迁移失败: {e}")
            return False
    
    async def _migrate_assistants_table(self, source_engine, target_db):
        """迁移助手表"""
        from ...models.assistant import Assistant
        from ...repositories.assistant_repository import AssistantRepository
        
        assistant_repo = AssistantRepository()
        
        # 从源数据库读取助手数据
        with source_engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM assistants"))
            assistants_data = result.fetchall()
        
        # 转换并插入目标数据库
        for assistant_row in assistants_data:
            assistant_data = {
                "id": assistant_row.id,
                "name": assistant_row.name,
                "description": assistant_row.description,
                "model": assistant_row.model,
                "capabilities": assistant_row.capabilities,
                "configuration": assistant_row.configuration,
                "system_prompt": assistant_row.system_prompt,
                "framework": getattr(assistant_row, 'framework', 'general'),
                "agno_config": getattr(assistant_row, 'agno_config', None),
                "is_agno_managed": getattr(assistant_row, 'is_agno_managed', False),
                "created_at": assistant_row.created_at,
                "updated_at": assistant_row.updated_at
            }
            
            # 检查助手是否已存在
            existing = await assistant_repo.get(target_db, assistant_row.id)
            if not existing:
                await assistant_repo.create(target_db, obj_in=assistant_data)
                logger.info(f"迁移助手: {assistant_row.name}")
    
    async def _migrate_conversations_table(self, source_engine, target_db):
        """迁移对话表"""
        from ...models.assistant import Conversation
        from ...repositories.assistant_repository import ConversationRepository
        
        conversation_repo = ConversationRepository()
        
        # 从源数据库读取对话数据
        with source_engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM conversations"))
            conversations_data = result.fetchall()
        
        # 转换并插入目标数据库
        for conv_row in conversations_data:
            conv_data = {
                "id": conv_row.id,
                "assistant_id": conv_row.assistant_id,
                "title": conv_row.title,
                "metadata": conv_row.metadata,
                "created_at": conv_row.created_at,
                "updated_at": conv_row.updated_at
            }
            
            # 检查对话是否已存在
            existing = await conversation_repo.get(target_db, conv_row.id)
            if not existing:
                await conversation_repo.create(target_db, obj_in=conv_data)
                logger.info(f"迁移对话: {conv_row.title}")
    
    async def _migrate_messages_table(self, source_engine, target_db):
        """迁移消息表"""
        from ...models.assistant import Message
        from ...repositories.assistant_repository import MessageRepository
        
        message_repo = MessageRepository()
        
        # 从源数据库读取消息数据
        with source_engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM messages"))
            messages_data = result.fetchall()
        
        # 转换并插入目标数据库
        for msg_row in messages_data:
            msg_data = {
                "id": msg_row.id,
                "conversation_id": msg_row.conversation_id,
                "role": msg_row.role,
                "content": msg_row.content,
                "metadata": msg_row.metadata,
                "created_at": msg_row.created_at
            }
            
            # 检查消息是否已存在
            existing = await message_repo.get(target_db, msg_row.id)
            if not existing:
                await message_repo.create(target_db, obj_in=msg_data)
    
    async def validate_migration(self) -> Dict[str, Any]:
        """验证迁移结果"""
        try:
            logger.info("开始验证迁移结果...")
            
            validation_report = {
                "status": "success",
                "tables_validated": [],
                "data_counts": {},
                "issues": []
            }
            
            async with get_db_session() as db:
                # 验证用户表
                from ...repositories.user_repository import UserRepository
                user_repo = UserRepository()
                user_count = await user_repo.count(db)
                validation_report["data_counts"]["users"] = user_count
                validation_report["tables_validated"].append("users")
                
                # 验证助手表
                from ...repositories.assistant_repository import AssistantRepository
                assistant_repo = AssistantRepository()
                assistant_count = await assistant_repo.count(db)
                validation_report["data_counts"]["assistants"] = assistant_count
                validation_report["tables_validated"].append("assistants")
            
            logger.info("迁移验证完成")
            return validation_report
            
        except Exception as e:
            logger.error(f"迁移验证失败: {e}")
            return {
                "status": "error",
                "error": str(e)
            }