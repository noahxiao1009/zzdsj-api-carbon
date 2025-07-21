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
import httpx
from openai import OpenAI
import asyncio
from typing import Optional, Dict, Any

from app.common.logger_util import logger
from app.cosight.llm.chat_llm import ChatLLM
from shared.service_client import call_service, CallMethod
from config.config import *


async def get_model_config_from_service(model_type: str) -> Dict[str, Any]:
    """从模型服务获取模型配置"""
    try:
        # 获取已启用的模型列表
        models_response = await call_service(
            service_name="model-service",
            method=CallMethod.GET,
            path="/api/v1/models",
            params={"enabled_only": True, "model_type": "chat"}
        )
        
        if not models_response.get("success") or not models_response.get("data", {}).get("models"):
            logger.warning(f"没有找到可用的{model_type}模型，使用默认配置")
            return get_default_model_config()
        
        models = models_response["data"]["models"]
        
        # 选择第一个可用的模型
        selected_model = models[0]
        provider_id = selected_model["provider_id"]
        
        # 获取提供商配置
        provider_response = await call_service(
            service_name="model-service",
            method=CallMethod.GET,
            path=f"/api/v1/models/providers/{provider_id}"
        )
        
        if not provider_response.get("success"):
            logger.warning(f"获取提供商{provider_id}配置失败，使用默认配置")
            return get_default_model_config()
        
        provider_data = provider_response["data"]
        
        # 构造模型配置
        model_config = {
            "model": selected_model["model_id"],
            "base_url": provider_data["api_base"],
            "api_key": "your-api-key",  # 实际环境中需要从安全存储获取
            "max_tokens": 4000,
            "temperature": 0.7,
            "proxy": None
        }
        
        return model_config
        
    except Exception as e:
        logger.error(f"从模型服务获取配置失败: {e}")
        return get_default_model_config()

def get_default_model_config() -> Dict[str, Any]:
    """获取默认模型配置"""
    return {
        "model": "gpt-3.5-turbo",
        "base_url": "https://api.openai.com/v1",
        "api_key": "your-api-key",
        "max_tokens": 4000,
        "temperature": 0.7,
        "proxy": None
    }

def set_model(model_config: dict[str, Optional[str | int | float]]):
    http_client_kwargs = {
        "headers": {
            'Content-Type': 'application/json',
            'Authorization': f"Bearer {model_config['api_key']}"
        },
        "verify": False,
        "trust_env": False
    }

    if model_config.get('proxy'):
        http_client_kwargs["proxy"] = model_config['proxy']

    openai_llm = OpenAI(
        base_url=model_config['base_url'],
        api_key=model_config['api_key'],
        http_client=httpx.Client(**http_client_kwargs)
    )

    chat_llm_kwargs = {
        "model": model_config['model'],
        "base_url": model_config['base_url'],
        "api_key": model_config['api_key'],
        "client": openai_llm
    }

    if model_config.get('max_tokens') is not None:
        chat_llm_kwargs['max_tokens'] = model_config['max_tokens']
    if model_config.get('temperature') is not None:
        chat_llm_kwargs['temperature'] = model_config['temperature']

    return ChatLLM(**chat_llm_kwargs)

async def create_model_from_service(model_type: str):
    """从模型服务创建模型实例"""
    model_config = await get_model_config_from_service(model_type)
    return set_model(model_config)


# 初始化模型实例（使用默认配置）
llm_for_plan = None
llm_for_act = None
llm_for_tool = None
llm_for_vision = None

async def init_models():
    """初始化所有模型实例"""
    global llm_for_plan, llm_for_act, llm_for_tool, llm_for_vision
    
    try:
        # 先尝试从模型服务获取配置
        logger.info("正在从模型服务获取模型配置...")
        
        plan_model_config = await get_model_config_from_service("plan")
        logger.info(f"plan_model_config:{plan_model_config}\n")
        llm_for_plan = set_model(plan_model_config)
        
        act_model_config = await get_model_config_from_service("act")
        logger.info(f"act_model_config:{act_model_config}\n")
        llm_for_act = set_model(act_model_config)
        
        tool_model_config = await get_model_config_from_service("tool")
        logger.info(f"tool_model_config:{tool_model_config}\n")
        llm_for_tool = set_model(tool_model_config)
        
        vision_model_config = await get_model_config_from_service("vision")
        logger.info(f"vision_model_config:{vision_model_config}\n")
        llm_for_vision = set_model(vision_model_config)
        
        logger.info("所有模型实例初始化完成")
        
    except Exception as e:
        logger.error(f"初始化模型实例失败: {e}")
        logger.info("使用默认配置初始化模型...")
        
        # 回退到默认配置
        default_config = get_default_model_config()
        llm_for_plan = set_model(default_config)
        llm_for_act = set_model(default_config)
        llm_for_tool = set_model(default_config)
        llm_for_vision = set_model(default_config)

def get_plan_llm():
    """获取规划模型"""
    if llm_for_plan is None:
        # 如果模型未初始化，使用默认配置
        return set_model(get_default_model_config())
    return llm_for_plan

def get_act_llm():
    """获取执行模型"""
    if llm_for_act is None:
        return set_model(get_default_model_config())
    return llm_for_act

def get_tool_llm():
    """获取工具模型"""
    if llm_for_tool is None:
        return set_model(get_default_model_config())
    return llm_for_tool

def get_vision_llm():
    """获取视觉模型"""
    if llm_for_vision is None:
        return set_model(get_default_model_config())
    return llm_for_vision

# 保持向后兼容，使用默认配置初始化
try:
    plan_model_config = get_plan_model_config()
    logger.info(f"plan_model_config:{plan_model_config}\n")
    llm_for_plan = set_model(plan_model_config)
    
    act_model_config = get_act_model_config()
    logger.info(f"act_model_config:{act_model_config}\n")
    llm_for_act = set_model(act_model_config)
    
    tool_model_config = get_tool_model_config()
    logger.info(f"tool_model_config:{tool_model_config}\n")
    llm_for_tool = set_model(tool_model_config)
    
    vision_model_config = get_vision_model_config()
    logger.info(f"vision_model_config:{vision_model_config}\n")
    llm_for_vision = set_model(vision_model_config)
except Exception as e:
    logger.error(f"使用默认配置初始化失败: {e}")
    default_config = get_default_model_config()
    llm_for_plan = set_model(default_config)
    llm_for_act = set_model(default_config)
    llm_for_tool = set_model(default_config)
    llm_for_vision = set_model(default_config)
