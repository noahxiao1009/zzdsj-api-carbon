"""
历史记录服务 - 处理会话和消息的持久化业务逻辑
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

from app.database.repository import (
    get_conversation_repo, get_message_repo, get_plan_repo, get_user_session_repo
)
from app.database.models import (
    ConversationModel, MessageModel, PlanModel,
    MessageRole, MessageType, PlanStatus,
    ChatHistoryRequest, ChatHistoryResponse, ConversationListResponse,
    SaveMessageRequest, CreateConversationRequest
)
from app.common.logger_util import logger


class HistoryService:
    """历史记录服务"""
    
    async def create_conversation(self, user_id: str, title: str = None, 
                                metadata: Dict = None) -> ConversationModel:
        """创建新会话"""
        repo = await get_conversation_repo()
        
        if not title:
            title = f"会话 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        conversation = await repo.create(user_id, title, metadata or {})
        logger.info(f"创建新会话: {conversation.id} for user: {user_id}")
        
        return conversation
    
    async def get_conversations(self, user_id: str, limit: int = 10) -> ConversationListResponse:
        """获取用户的会话列表"""
        repo = await get_conversation_repo()
        conversations = await repo.get_by_user(user_id, limit)
        
        return ConversationListResponse(
            conversations=conversations,
            total_count=len(conversations)
        )
    
    async def get_conversation_by_id(self, conversation_id: str) -> Optional[ConversationModel]:
        """根据ID获取会话"""
        repo = await get_conversation_repo()
        return await repo.get_by_id(conversation_id)
    
    async def save_message(self, request: SaveMessageRequest) -> MessageModel:
        """保存消息到会话中"""
        # 如果没有指定会话ID，创建新会话
        conversation_id = request.conversation_id
        if not conversation_id:
            conversation = await self.create_conversation(
                request.user_id, 
                f"会话 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            conversation_id = conversation.id
        
        # 保存消息
        repo = await get_message_repo()
        message = await repo.save(
            conversation_id=conversation_id,
            content=request.content,
            role=request.role,
            message_type=request.message_type,
            metadata=request.metadata
        )
        
        logger.info(f"保存消息: {message.id} to conversation: {conversation_id}")
        return message
    
    async def get_conversation_history(self, conversation_id: str, 
                                     limit: int = 100) -> ChatHistoryResponse:
        """获取会话历史记录"""
        repo = await get_message_repo()
        messages = await repo.get_conversation_history(conversation_id, limit)
        
        return ChatHistoryResponse(
            conversation_id=conversation_id,
            messages=messages,
            total_count=len(messages)
        )
    
    async def get_user_conversation_history(self, user_id: str, 
                                          conversation_id: str = None,
                                          limit: int = 50) -> ChatHistoryResponse:
        """获取用户的会话历史（如果没有指定会话ID，返回最新会话的历史）"""
        if not conversation_id:
            # 获取用户最新的会话
            conversations = await self.get_conversations(user_id, 1)
            if conversations.conversations:
                conversation_id = conversations.conversations[0].id
            else:
                # 如果没有会话，创建一个新的
                conversation = await self.create_conversation(user_id)
                conversation_id = conversation.id
        
        return await self.get_conversation_history(conversation_id, limit)
    
    async def get_latest_messages(self, conversation_id: str, 
                                count: int = 10) -> List[MessageModel]:
        """获取会话中最新的几条消息"""
        repo = await get_message_repo()
        return await repo.get_latest_messages(conversation_id, count)
    
    async def save_plan(self, plan_id: str, conversation_id: str, user_id: str,
                       question: str, plan_data: Dict) -> PlanModel:
        """保存执行计划"""
        repo = await get_plan_repo()
        plan = await repo.save(plan_id, conversation_id, user_id, question, plan_data)
        
        logger.info(f"保存计划: {plan_id} for conversation: {conversation_id}")
        return plan
    
    async def get_plan(self, plan_id: str) -> Optional[PlanModel]:
        """获取执行计划"""
        repo = await get_plan_repo()
        return await repo.get_by_id(plan_id)
    
    async def update_plan_status(self, plan_id: str, status: PlanStatus) -> bool:
        """更新计划状态"""
        repo = await get_plan_repo()
        result = await repo.update_status(plan_id, status)
        
        logger.info(f"更新计划状态: {plan_id} -> {status.value}")
        return result
    
    async def get_conversation_plans(self, conversation_id: str) -> List[PlanModel]:
        """获取会话相关的所有计划"""
        repo = await get_plan_repo()
        return await repo.get_by_conversation(conversation_id)
    
    async def update_conversation(self, conversation_id: str, title: str = None,
                                metadata: Dict = None, is_active: bool = None) -> bool:
        """更新会话信息"""
        repo = await get_conversation_repo()
        result = await repo.update(conversation_id, title, metadata, is_active)
        
        if result:
            logger.info(f"更新会话: {conversation_id}")
        
        return result
    
    async def create_user_session(self, user_id: str, session_data: Dict = None,
                                expires_at: datetime = None) -> str:
        """创建用户会话"""
        session_id = str(uuid.uuid4())
        repo = await get_user_session_repo()
        
        await repo.create(session_id, user_id, session_data, expires_at)
        logger.info(f"创建用户会话: {session_id} for user: {user_id}")
        
        return session_id
    
    async def get_user_session(self, session_id: str) -> Optional[Dict]:
        """获取用户会话"""
        repo = await get_user_session_repo()
        session = await repo.get_by_id(session_id)
        
        if session:
            return {
                "session_id": session.id,
                "user_id": session.user_id,
                "session_data": session.session_data,
                "created_at": session.created_at,
                "expires_at": session.expires_at,
                "is_active": session.is_active
            }
        
        return None
    
    async def convert_chat_history_to_cosight_format(self, conversation_id: str) -> List[Dict]:
        """将聊天历史转换为CoSight格式"""
        history_response = await self.get_conversation_history(conversation_id)
        
        cosight_history = []
        for message in history_response.messages:
            cosight_message = {
                "role": message.role.value,
                "content": message.content
            }
            
            # 添加消息类型和元数据
            if message.message_type != MessageType.CHAT:
                cosight_message["message_type"] = message.message_type.value
            
            if message.metadata:
                cosight_message["metadata"] = message.metadata
            
            cosight_history.append(cosight_message)
        
        return cosight_history
    
    async def save_cosight_conversation(self, user_id: str, question: str, 
                                      plan_result: str, plan_data: Dict,
                                      conversation_id: str = None) -> str:
        """保存CoSight对话的完整流程"""
        # 创建或使用现有会话
        if not conversation_id:
            conversation = await self.create_conversation(
                user_id, 
                f"智能报告: {question[:50]}..."
            )
            conversation_id = conversation.id
        
        # 保存用户问题
        await self.save_message(SaveMessageRequest(
            conversation_id=conversation_id,
            user_id=user_id,
            content=question,
            role=MessageRole.USER,
            message_type=MessageType.CHAT
        ))
        
        # 保存计划数据
        plan_id = f"plan_{int(datetime.now().timestamp() * 1000000)}"
        await self.save_plan(plan_id, conversation_id, user_id, question, plan_data)
        
        # 保存AI回复
        await self.save_message(SaveMessageRequest(
            conversation_id=conversation_id,
            user_id=user_id,
            content=plan_result,
            role=MessageRole.ASSISTANT,
            message_type=MessageType.RESULT,
            metadata={"plan_id": plan_id}
        ))
        
        logger.info(f"保存CoSight完整对话: {conversation_id}")
        return conversation_id


# 全局服务实例
history_service = HistoryService()


async def get_history_service() -> HistoryService:
    """获取历史记录服务实例"""
    return history_service