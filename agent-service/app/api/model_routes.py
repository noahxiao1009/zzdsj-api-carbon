"""
模型管理API路由
管理AI模型配置和调用
"""

import logging
from typing import Dict, Any, List

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer

from app.config.settings import settings

router = APIRouter()
security = HTTPBearer()
logger = logging.getLogger(__name__)

@router.get("/list")
async def list_models():
    """获取可用模型列表"""
    try:
        models = []
        
        # OpenAI模型
        if settings.OPENAI_API_KEY:
            models.extend([
                {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "name": "GPT-4o",
                    "description": "OpenAI最新多模态模型",
                    "type": "chat",
                    "available": True
                },
                {
                    "provider": "openai", 
                    "model": "gpt-4o-mini",
                    "name": "GPT-4o Mini",
                    "description": "OpenAI轻量级模型",
                    "type": "chat",
                    "available": True
                },
                {
                    "provider": "openai",
                    "model": "o3-mini",
                    "name": "o3 Mini",
                    "description": "OpenAI推理模型",
                    "type": "reasoning",
                    "available": True
                }
            ])
        
        # Anthropic模型
        if settings.ANTHROPIC_API_KEY:
            models.extend([
                {
                    "provider": "anthropic",
                    "model": "claude-3-5-sonnet",
                    "name": "Claude 3.5 Sonnet",
                    "description": "Anthropic最强模型",
                    "type": "chat",
                    "available": True
                },
                {
                    "provider": "anthropic",
                    "model": "claude-3-haiku",
                    "name": "Claude 3 Haiku",
                    "description": "Anthropic快速模型",
                    "type": "chat", 
                    "available": True
                }
            ])
        
        return {
            "models": models,
            "total": len(models)
        }
        
    except Exception as e:
        logger.error(f"获取模型列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取模型列表失败: {str(e)}")

@router.get("/providers")
async def list_providers():
    """获取可用模型提供商"""
    try:
        providers = []
        
        if settings.OPENAI_API_KEY:
            providers.append({
                "name": "openai",
                "display_name": "OpenAI",
                "available": True,
                "models_count": 3
            })
            
        if settings.ANTHROPIC_API_KEY:
            providers.append({
                "name": "anthropic",
                "display_name": "Anthropic",
                "available": True,
                "models_count": 2
            })
            
        return {
            "providers": providers,
            "total": len(providers)
        }
        
    except Exception as e:
        logger.error(f"获取提供商列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取提供商列表失败: {str(e)}")
