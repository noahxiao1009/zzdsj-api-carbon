"""
数据仓库层 - 数据访问操作封装
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
import json

from app.database.sqlite_db import SQLiteDB, get_db
from app.database.models import (
    ConversationModel, MessageModel, PlanModel, UserSessionModel,
    MessageRole, MessageType, PlanStatus
)
from app.common.logger_util import logger


class ConversationRepository:
    """会话数据仓库"""
    
    def __init__(self, db: SQLiteDB):
        self.db = db
    
    async def create(self, user_id: str, title: str = None, metadata: Dict = None) -> ConversationModel:
        """创建新会话"""
        conversation_id = await self.db.create_conversation(user_id, title, metadata)
        
        # 返回创建的会话对象
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                return ConversationModel(
                    id=row['id'],
                    user_id=row['user_id'],
                    title=row['title'],
                    created_at=datetime.fromisoformat(row['created_at']),
                    updated_at=datetime.fromisoformat(row['updated_at']),
                    is_active=bool(row['is_active']),
                    metadata=json.loads(row['metadata']) if row['metadata'] else {}
                )
    
    async def get_by_id(self, conversation_id: str) -> Optional[ConversationModel]:
        """根据ID获取会话"""
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                return ConversationModel(
                    id=row['id'],
                    user_id=row['user_id'],
                    title=row['title'],
                    created_at=datetime.fromisoformat(row['created_at']),
                    updated_at=datetime.fromisoformat(row['updated_at']),
                    is_active=bool(row['is_active']),
                    metadata=json.loads(row['metadata']) if row['metadata'] else {}
                )
            return None
    
    async def get_by_user(self, user_id: str, limit: int = 10) -> List[ConversationModel]:
        """获取用户的会话列表"""
        conversations_data = await self.db.get_conversations(user_id, limit)
        
        return [
            ConversationModel(
                id=conv['id'],
                user_id=conv['user_id'],
                title=conv['title'],
                created_at=datetime.fromisoformat(conv['created_at']),
                updated_at=datetime.fromisoformat(conv['updated_at']),
                is_active=bool(conv['is_active']),
                metadata=conv['metadata']
            )
            for conv in conversations_data
        ]
    
    async def update(self, conversation_id: str, title: str = None, 
                    metadata: Dict = None, is_active: bool = None) -> bool:
        """更新会话"""
        updates = []
        params = []
        
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        
        if metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata))
        
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(is_active)
        
        if not updates:
            return False
        
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(conversation_id)
        
        async with self.db.get_connection() as conn:
            await conn.execute(
                f"UPDATE conversations SET {', '.join(updates)} WHERE id = ?",
                params
            )
            await conn.commit()
        
        return True


class MessageRepository:
    """消息数据仓库"""
    
    def __init__(self, db: SQLiteDB):
        self.db = db
    
    async def save(self, conversation_id: str, content: str, role: MessageRole,
                  message_type: MessageType = MessageType.CHAT, 
                  metadata: Dict = None) -> MessageModel:
        """保存消息"""
        message_id = await self.db.save_message(
            conversation_id, content, role.value, message_type.value, metadata
        )
        
        # 返回创建的消息对象
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM messages WHERE id = ?", (message_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                return MessageModel(
                    id=row['id'],
                    conversation_id=row['conversation_id'],
                    content=row['content'],
                    role=MessageRole(row['role']),
                    message_type=MessageType(row['message_type']),
                    timestamp=datetime.fromisoformat(row['timestamp']),
                    metadata=json.loads(row['metadata']) if row['metadata'] else {}
                )
    
    async def get_conversation_history(self, conversation_id: str, 
                                     limit: int = 100) -> List[MessageModel]:
        """获取会话历史"""
        messages_data = await self.db.get_conversation_history(conversation_id, limit)
        
        return [
            MessageModel(
                id=msg['id'],
                conversation_id=msg['conversation_id'],
                content=msg['content'],
                role=MessageRole(msg['role']),
                message_type=MessageType(msg['message_type']),
                timestamp=datetime.fromisoformat(msg['timestamp']),
                metadata=msg['metadata']
            )
            for msg in messages_data
        ]
    
    async def get_latest_messages(self, conversation_id: str, 
                                 count: int = 10) -> List[MessageModel]:
        """获取最新的几条消息"""
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(
                """SELECT * FROM messages 
                   WHERE conversation_id = ? 
                   ORDER BY timestamp DESC LIMIT ?""",
                (conversation_id, count)
            )
            rows = await cursor.fetchall()
            
            messages = []
            for row in reversed(rows):  # 反转以获得正确的时间顺序
                messages.append(MessageModel(
                    id=row['id'],
                    conversation_id=row['conversation_id'],
                    content=row['content'],
                    role=MessageRole(row['role']),
                    message_type=MessageType(row['message_type']),
                    timestamp=datetime.fromisoformat(row['timestamp']),
                    metadata=json.loads(row['metadata']) if row['metadata'] else {}
                ))
            
            return messages


class PlanRepository:
    """计划数据仓库"""
    
    def __init__(self, db: SQLiteDB):
        self.db = db
    
    async def save(self, plan_id: str, conversation_id: str, user_id: str,
                  question: str, plan_data: Dict) -> PlanModel:
        """保存计划"""
        await self.db.save_plan(plan_id, conversation_id, user_id, question, plan_data)
        
        # 返回保存的计划对象
        plan_data_db = await self.db.get_plan(plan_id)
        if plan_data_db:
            return PlanModel(
                id=plan_data_db['id'],
                conversation_id=plan_data_db['conversation_id'],
                user_id=plan_data_db['user_id'],
                question=plan_data_db['question'],
                plan_data=plan_data_db['plan_data'],
                status=PlanStatus(plan_data_db['status']),
                created_at=datetime.fromisoformat(plan_data_db['created_at']),
                updated_at=datetime.fromisoformat(plan_data_db['updated_at'])
            )
    
    async def get_by_id(self, plan_id: str) -> Optional[PlanModel]:
        """根据ID获取计划"""
        plan_data = await self.db.get_plan(plan_id)
        if plan_data:
            return PlanModel(
                id=plan_data['id'],
                conversation_id=plan_data['conversation_id'],
                user_id=plan_data['user_id'],
                question=plan_data['question'],
                plan_data=plan_data['plan_data'],
                status=PlanStatus(plan_data['status']),
                created_at=datetime.fromisoformat(plan_data['created_at']),
                updated_at=datetime.fromisoformat(plan_data['updated_at'])
            )
        return None
    
    async def update_status(self, plan_id: str, status: PlanStatus) -> bool:
        """更新计划状态"""
        await self.db.update_plan_status(plan_id, status.value)
        return True
    
    async def get_by_conversation(self, conversation_id: str) -> List[PlanModel]:
        """获取会话相关的计划"""
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(
                """SELECT * FROM plans 
                   WHERE conversation_id = ? 
                   ORDER BY created_at DESC""",
                (conversation_id,)
            )
            rows = await cursor.fetchall()
            
            plans = []
            for row in rows:
                plans.append(PlanModel(
                    id=row['id'],
                    conversation_id=row['conversation_id'],
                    user_id=row['user_id'],
                    question=row['question'],
                    plan_data=json.loads(row['plan_data']),
                    status=PlanStatus(row['status']),
                    created_at=datetime.fromisoformat(row['created_at']),
                    updated_at=datetime.fromisoformat(row['updated_at'])
                ))
            
            return plans


class UserSessionRepository:
    """用户会话数据仓库"""
    
    def __init__(self, db: SQLiteDB):
        self.db = db
    
    async def create(self, session_id: str, user_id: str, 
                    session_data: Dict = None, expires_at: datetime = None) -> UserSessionModel:
        """创建用户会话"""
        await self.db.create_user_session(session_id, user_id, session_data, expires_at)
        
        # 返回创建的会话对象
        session_data_db = await self.db.get_user_session(session_id)
        if session_data_db:
            return UserSessionModel(
                id=session_data_db['id'],
                user_id=session_data_db['user_id'],
                session_data=session_data_db['session_data'],
                created_at=datetime.fromisoformat(session_data_db['created_at']),
                expires_at=datetime.fromisoformat(session_data_db['expires_at']) if session_data_db['expires_at'] else None,
                is_active=bool(session_data_db['is_active'])
            )
    
    async def get_by_id(self, session_id: str) -> Optional[UserSessionModel]:
        """根据ID获取用户会话"""
        session_data = await self.db.get_user_session(session_id)
        if session_data:
            return UserSessionModel(
                id=session_data['id'],
                user_id=session_data['user_id'],
                session_data=session_data['session_data'],
                created_at=datetime.fromisoformat(session_data['created_at']),
                expires_at=datetime.fromisoformat(session_data['expires_at']) if session_data['expires_at'] else None,
                is_active=bool(session_data['is_active'])
            )
        return None


# 仓库工厂函数
async def get_conversation_repo() -> ConversationRepository:
    """获取会话仓库实例"""
    db = await get_db()
    return ConversationRepository(db)


async def get_message_repo() -> MessageRepository:
    """获取消息仓库实例"""
    db = await get_db()
    return MessageRepository(db)


async def get_plan_repo() -> PlanRepository:
    """获取计划仓库实例"""
    db = await get_db()
    return PlanRepository(db)


async def get_user_session_repo() -> UserSessionRepository:
    """获取用户会话仓库实例"""
    db = await get_db()
    return UserSessionRepository(db)