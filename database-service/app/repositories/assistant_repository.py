"""
助手相关的仓库实现
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload

from .base import BaseRepository
from ..models.assistant import Assistant, Conversation, Message, AgnoSession, AgnoToolExecution, AssistantRating
from ..schemas.assistant import (
    AssistantCreate, AssistantUpdate,
    ConversationCreate, ConversationUpdate,
    MessageCreate, MessageUpdate,
    AgnoSessionCreate, AgnoSessionUpdate
)


class AssistantRepository(BaseRepository[Assistant, AssistantCreate, AssistantUpdate]):
    """助手仓库"""
    
    def __init__(self):
        super().__init__(Assistant)
    
    async def get_by_user_id(self, db: AsyncSession, user_id: str) -> List[Assistant]:
        """根据用户ID获取助手列表"""
        return await self.get_multi(db, filters={"user_id": user_id})
    
    async def get_public_assistants(self, db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Assistant]:
        """获取公开助手列表"""
        return await self.get_multi(db, skip=skip, limit=limit, filters={"is_public": True, "is_active": True})
    
    async def get_by_framework(self, db: AsyncSession, framework: str) -> List[Assistant]:
        """根据框架类型获取助手列表"""
        return await self.get_multi(db, filters={"framework": framework})
    
    async def get_agno_assistants(self, db: AsyncSession) -> List[Assistant]:
        """获取Agno框架助手列表"""
        return await self.get_multi(db, filters={"is_agno_managed": True})
    
    async def search_assistants(
        self,
        db: AsyncSession,
        query: str,
        user_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Assistant]:
        """搜索助手"""
        filters = {"is_active": True}
        if user_id:
            filters["user_id"] = user_id
        
        return await self.search(
            db,
            query=query,
            search_fields=["name", "description"],
            skip=skip,
            limit=limit,
            filters=filters
        )
    
    async def get_popular_assistants(self, db: AsyncSession, limit: int = 10) -> List[Assistant]:
        """获取热门助手列表"""
        return await self.get_multi(
            db,
            limit=limit,
            filters={"is_public": True, "is_active": True},
            order_by="usage_count",
            order_desc=True
        )
    
    async def get_top_rated_assistants(self, db: AsyncSession, limit: int = 10) -> List[Assistant]:
        """获取高评分助手列表"""
        return await self.get_multi(
            db,
            limit=limit,
            filters={"is_public": True, "is_active": True},
            order_by="rating",
            order_desc=True
        )
    
    async def increment_usage(self, db: AsyncSession, assistant_id: str) -> Optional[Assistant]:
        """增加助手使用次数"""
        assistant = await self.get(db, assistant_id)
        if assistant:
            assistant.usage_count += 1
            await db.commit()
            await db.refresh(assistant)
        return assistant
    
    async def update_rating(self, db: AsyncSession, assistant_id: str) -> Optional[Assistant]:
        """更新助手评分"""
        # 计算平均评分
        query = select(func.avg(AssistantRating.rating)).where(AssistantRating.assistant_id == assistant_id)
        result = await db.execute(query)
        avg_rating = result.scalar() or 0.0
        
        assistant = await self.get(db, assistant_id)
        if assistant:
            assistant.rating = round(avg_rating, 2)
            await db.commit()
            await db.refresh(assistant)
        return assistant


class ConversationRepository(BaseRepository[Conversation, ConversationCreate, ConversationUpdate]):
    """对话仓库"""
    
    def __init__(self):
        super().__init__(Conversation)
    
    async def get_by_assistant_id(self, db: AsyncSession, assistant_id: str) -> List[Conversation]:
        """根据助手ID获取对话列表"""
        return await self.get_multi(db, filters={"assistant_id": assistant_id})
    
    async def get_by_user_id(self, db: AsyncSession, user_id: str) -> List[Conversation]:
        """根据用户ID获取对话列表"""
        return await self.get_multi(db, filters={"user_id": user_id})
    
    async def get_active_conversations(
        self,
        db: AsyncSession,
        user_id: Optional[str] = None,
        assistant_id: Optional[str] = None
    ) -> List[Conversation]:
        """获取活跃对话列表"""
        filters = {"is_active": True}
        if user_id:
            filters["user_id"] = user_id
        if assistant_id:
            filters["assistant_id"] = assistant_id
        
        return await self.get_multi(db, filters=filters, order_by="updated_at", order_desc=True)
    
    async def get_with_messages(self, db: AsyncSession, conversation_id: str) -> Optional[Conversation]:
        """获取对话及其消息"""
        return await self.get_with_relations(db, conversation_id, ["messages"])
    
    async def update_message_count(self, db: AsyncSession, conversation_id: str) -> Optional[Conversation]:
        """更新对话消息数量"""
        from datetime import datetime
        
        # 统计消息数量
        query = select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
        result = await db.execute(query)
        message_count = result.scalar() or 0
        
        conversation = await self.get(db, conversation_id)
        if conversation:
            conversation.message_count = message_count
            conversation.last_message_at = datetime.utcnow()
            await db.commit()
            await db.refresh(conversation)
        return conversation


class MessageRepository(BaseRepository[Message, MessageCreate, MessageUpdate]):
    """消息仓库"""
    
    def __init__(self):
        super().__init__(Message)
    
    async def get_by_conversation_id(
        self,
        db: AsyncSession,
        conversation_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Message]:
        """根据对话ID获取消息列表"""
        return await self.get_multi(
            db,
            skip=skip,
            limit=limit,
            filters={"conversation_id": conversation_id, "is_deleted": False},
            order_by="created_at",
            order_desc=False
        )
    
    async def get_recent_messages(
        self,
        db: AsyncSession,
        conversation_id: str,
        limit: int = 10
    ) -> List[Message]:
        """获取最近的消息"""
        return await self.get_multi(
            db,
            limit=limit,
            filters={"conversation_id": conversation_id, "is_deleted": False},
            order_by="created_at",
            order_desc=True
        )
    
    async def soft_delete(self, db: AsyncSession, message_id: str) -> Optional[Message]:
        """软删除消息"""
        message = await self.get(db, message_id)
        if message:
            message.is_deleted = True
            await db.commit()
            await db.refresh(message)
        return message
    
    async def get_conversation_context(
        self,
        db: AsyncSession,
        conversation_id: str,
        max_messages: int = 20
    ) -> List[Message]:
        """获取对话上下文"""
        return await self.get_multi(
            db,
            limit=max_messages,
            filters={"conversation_id": conversation_id, "is_deleted": False},
            order_by="created_at",
            order_desc=True
        )
    
    async def search_messages(
        self,
        db: AsyncSession,
        conversation_id: str,
        query: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Message]:
        """搜索消息"""
        return await self.search(
            db,
            query=query,
            search_fields=["content"],
            skip=skip,
            limit=limit,
            filters={"conversation_id": conversation_id, "is_deleted": False}
        )


class AgnoSessionRepository(BaseRepository[AgnoSession, AgnoSessionCreate, AgnoSessionUpdate]):
    """Agno会话仓库"""
    
    def __init__(self):
        super().__init__(AgnoSession)
    
    async def get_by_session_id(self, db: AsyncSession, session_id: str) -> Optional[AgnoSession]:
        """根据会话ID获取Agno会话"""
        return await self.get_by_field(db, "session_id", session_id)
    
    async def get_by_user_id(self, db: AsyncSession, user_id: str) -> List[AgnoSession]:
        """根据用户ID获取Agno会话列表"""
        return await self.get_multi(db, filters={"user_id": user_id})
    
    async def get_by_assistant_id(self, db: AsyncSession, assistant_id: str) -> List[AgnoSession]:
        """根据助手ID获取Agno会话列表"""
        return await self.get_multi(db, filters={"assistant_id": assistant_id})
    
    async def get_active_sessions(self, db: AsyncSession, user_id: str) -> List[AgnoSession]:
        """获取用户的活跃Agno会话"""
        return await self.get_multi(
            db,
            filters={"user_id": user_id, "is_active": True},
            order_by="last_activity",
            order_desc=True
        )
    
    async def update_activity(self, db: AsyncSession, session_id: str) -> Optional[AgnoSession]:
        """更新会话活动时间"""
        from datetime import datetime
        
        session = await self.get_by_session_id(db, session_id)
        if session:
            session.last_activity = datetime.utcnow()
            session.interaction_count += 1
            await db.commit()
            await db.refresh(session)
        return session
    
    async def deactivate_session(self, db: AsyncSession, session_id: str) -> Optional[AgnoSession]:
        """停用Agno会话"""
        session = await self.get_by_session_id(db, session_id)
        if session:
            session.is_active = False
            await db.commit()
            await db.refresh(session)
        return session
    
    async def get_with_tool_executions(self, db: AsyncSession, session_id: str) -> Optional[AgnoSession]:
        """获取会话及其工具执行记录"""
        return await self.get_with_relations(db, session_id, ["tool_executions"])


class AgnoToolExecutionRepository(BaseRepository[AgnoToolExecution, Dict[str, Any], Dict[str, Any]]):
    """Agno工具执行仓库"""
    
    def __init__(self):
        super().__init__(AgnoToolExecution)
    
    async def get_by_session_id(self, db: AsyncSession, session_id: str) -> List[AgnoToolExecution]:
        """根据会话ID获取工具执行记录"""
        return await self.get_multi(
            db,
            filters={"session_id": session_id},
            order_by="started_at",
            order_desc=True
        )
    
    async def get_successful_executions(self, db: AsyncSession, session_id: str) -> List[AgnoToolExecution]:
        """获取成功的工具执行记录"""
        return await self.get_multi(
            db,
            filters={"session_id": session_id, "success": True},
            order_by="started_at",
            order_desc=True
        )
    
    async def get_failed_executions(self, db: AsyncSession, session_id: str) -> List[AgnoToolExecution]:
        """获取失败的工具执行记录"""
        return await self.get_multi(
            db,
            filters={"session_id": session_id, "success": False},
            order_by="started_at",
            order_desc=True
        )
    
    async def complete_execution(
        self,
        db: AsyncSession,
        execution_id: str,
        output_data: Dict[str, Any],
        success: bool = True,
        error_message: Optional[str] = None
    ) -> Optional[AgnoToolExecution]:
        """完成工具执行"""
        from datetime import datetime
        
        execution = await self.get(db, execution_id)
        if execution:
            execution.output_data = output_data
            execution.success = success
            execution.error_message = error_message
            execution.completed_at = datetime.utcnow()
            
            # 计算执行时间
            if execution.started_at:
                execution_time = (execution.completed_at - execution.started_at).total_seconds() * 1000
                execution.execution_time_ms = int(execution_time)
            
            await db.commit()
            await db.refresh(execution)
        return execution


class AssistantRatingRepository(BaseRepository[AssistantRating, Dict[str, Any], Dict[str, Any]]):
    """助手评分仓库"""
    
    def __init__(self):
        super().__init__(AssistantRating)
    
    async def get_by_assistant_and_user(
        self,
        db: AsyncSession,
        assistant_id: str,
        user_id: str
    ) -> Optional[AssistantRating]:
        """根据助手ID和用户ID获取评分"""
        query = select(AssistantRating).where(
            and_(
                AssistantRating.assistant_id == assistant_id,
                AssistantRating.user_id == user_id
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_assistant_ratings(self, db: AsyncSession, assistant_id: str) -> List[AssistantRating]:
        """获取助手的所有评分"""
        return await self.get_multi(db, filters={"assistant_id": assistant_id})
    
    async def get_user_ratings(self, db: AsyncSession, user_id: str) -> List[AssistantRating]:
        """获取用户的所有评分"""
        return await self.get_multi(db, filters={"user_id": user_id})
    
    async def create_or_update_rating(
        self,
        db: AsyncSession,
        assistant_id: str,
        user_id: str,
        rating: int,
        comment: Optional[str] = None
    ) -> AssistantRating:
        """创建或更新评分"""
        existing = await self.get_by_assistant_and_user(db, assistant_id, user_id)
        
        if existing:
            existing.rating = rating
            existing.comment = comment
            await db.commit()
            await db.refresh(existing)
            return existing
        else:
            rating_data = {
                "assistant_id": assistant_id,
                "user_id": user_id,
                "rating": rating,
                "comment": comment
            }
            return await self.create(db, obj_in=rating_data)