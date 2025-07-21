# Copyright 2025 ZTE Corporation.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from fastapi import Request, Response
from typing import Optional, Dict, List

from cosight_server.sdk.common.config import custom_config
from cosight_server.sdk.common.api_result import json_result
from cosight_server.sdk.common.cache import Cache
from app.common.logger_util import logger
from cosight_server.sdk.common.singleton import SingletonMetaCls
from cosight_server.sdk.common.utils import async_request
from cosight_server.sdk.services.session_manager import SessionManagerBase
from app.services.history_service import get_history_service
from app.database.models import MessageRole, MessageType, SaveMessageRequest


class AISSessionManager(SessionManagerBase, metaclass=SingletonMetaCls):
    _api_key_service = None
    
    @property
    def api_key_service(self):
        if self._api_key_service is None:
            self._api_key_service = ApiKeyService()
        return self._api_key_service
        
    async def login(self, response: Response, cookie: str, referer: str):
        """
        登录处理的抽象方法
        :param response: Response对象
        :param cookie: cookie字符串
        :param referer: 来源页面
        """
        user_id = self._read_user_id(cookie) or "admin"
        return json_result(200, "", {"id": user_id, "authValue": user_id})

    def logout(self, response: Response, cookie: str):
        """
        登出处理的抽象方法
        :param response: Response对象
        :param cookie: cookie字符串
        """
        return json_result(200, "logged out")

    def check_request(self, cookie: str):
        """
        检查请求有效性的抽象方法
        :param cookie: cookie字符串
        """
        return json_result(200, "check success")

    async def authority(self, request: Request):
        """
        权限验证
        :param request: Request对象
        """

        cookie = request.headers.get("cookie")
        api_key = request.headers.get("Authorization")
        logger.info(f"check_validation >>>>>>>>>>>>>>>>> cookie: {cookie}, api_key: {api_key}")

        if api_key:
            return await self.api_key_service.validate_api_key(api_key)
        
        if custom_config.get('environment') == 'dev-mode':
            return True
        
        if not cookie:
            return False

        code = self.get_property_from_cookie(cookie, 'Z-AUTH-CODE-28001')
        params = {"code": code}
        logger.info(f"check_validation >>>>>>>>>>>>>>>>> params: {params}")
        
        service_info = Cache.get(MSB_SERVICE_INFO_KEY) or {}
        common_component_service_info = service_info.get("common_component_service_info", None)   
        if not common_component_service_info:
            service_info = refresh_msb_service_info()
            common_component_service_info = service_info.get("common_component_service_info", None)

        protocol, ip, port = common_component_service_info.get("protocol"), common_component_service_info.get("ip"), common_component_service_info.get("port")
        if not all([protocol, ip, port]):
            return False

        common_component_url = f'{protocol}://{ip}:{port}/authorization/user-token'
        logger.info(f'check_validation ==============> common_component_url: {common_component_url}')
        response_data = await async_request(common_component_url, params, method='post')
        if not response_data or response_data['code'] != 10001:
            logger.error(f"Failed to get the user token: {response_data.get('message', 'unknown error')}")
            return False

        return True

    def get_validation_info(self, cookie: str):
        """
        获取验证信息的抽象方法
        :param cookie: cookie字符串
        """
        return {}

    def get_req_session_id(self, cookie: str):
        """
        获取请求session ID的抽象方法
        :param cookie: cookie字符串
        """
        return "admin"

    def get_user_id(self, session_id: str):
        """
        获取用户ID的抽象方法
        :param session_id: 会话ID
        """
        return self._read_user_id(session_id)
    
    def get_property_from_cookie(self, cookie, property_name, default_value=None):
        return self._get_property_from_cookie(cookie, property_name, default_value)
    
    async def get_conversation_history(self, user_id: str, conversation_id: str = None) -> List[Dict]:
        """获取用户的会话历史记录"""
        try:
            history_service = await get_history_service()
            history_response = await history_service.get_user_conversation_history(
                user_id=user_id, 
                conversation_id=conversation_id
            )
            
            # 转换为CoSight格式
            cosight_history = await history_service.convert_chat_history_to_cosight_format(
                history_response.conversation_id
            )
            
            logger.info(f"获取用户历史记录: {user_id}, 会话: {history_response.conversation_id}, 消息数: {len(cosight_history)}")
            return cosight_history
            
        except Exception as e:
            logger.error(f"获取会话历史失败: {e}")
            return []
    
    async def save_user_message(self, user_id: str, content: str, role: str, 
                               conversation_id: str = None, message_type: str = "chat") -> str:
        """保存用户消息到数据库"""
        try:
            history_service = await get_history_service()
            
            # 转换角色和消息类型
            msg_role = MessageRole.USER if role == "user" else MessageRole.ASSISTANT
            msg_type = MessageType.CHAT
            if message_type == "plan":
                msg_type = MessageType.PLAN
            elif message_type == "execution":
                msg_type = MessageType.EXECUTION
            elif message_type == "result":
                msg_type = MessageType.RESULT
            
            save_request = SaveMessageRequest(
                conversation_id=conversation_id,
                user_id=user_id,
                content=content,
                role=msg_role,
                message_type=msg_type
            )
            
            message = await history_service.save_message(save_request)
            logger.info(f"保存用户消息: {message.id} 到会话: {message.conversation_id}")
            
            return message.conversation_id
            
        except Exception as e:
            logger.error(f"保存用户消息失败: {e}")
            return conversation_id
    
    async def save_cosight_session(self, user_id: str, question: str, plan_result: str, 
                                  plan_data: Dict, conversation_id: str = None) -> str:
        """保存完整的CoSight会话"""
        try:
            history_service = await get_history_service()
            final_conversation_id = await history_service.save_cosight_conversation(
                user_id=user_id,
                question=question,
                plan_result=plan_result,
                plan_data=plan_data,
                conversation_id=conversation_id
            )
            
            logger.info(f"保存CoSight会话: {final_conversation_id}")
            return final_conversation_id
            
        except Exception as e:
            logger.error(f"保存CoSight会话失败: {e}")
            return conversation_id
    
    async def get_user_conversations(self, user_id: str, limit: int = 10) -> List[Dict]:
        """获取用户的会话列表"""
        try:
            history_service = await get_history_service()
            conversations_response = await history_service.get_conversations(user_id, limit)
            
            conversations = []
            for conv in conversations_response.conversations:
                conversations.append({
                    "id": conv.id,
                    "title": conv.title,
                    "created_at": conv.created_at.isoformat(),
                    "updated_at": conv.updated_at.isoformat(),
                    "is_active": conv.is_active,
                    "metadata": conv.metadata
                })
            
            return conversations
            
        except Exception as e:
            logger.error(f"获取用户会话列表失败: {e}")
            return []
