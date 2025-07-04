"""
模型服务API接口
支持中国国内各个模型厂商的模型配置和使用
"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
import uuid
import time
import asyncio
import json

from ..schemas.model_provider import (
    ModelProvider,
    ModelProviderCreate,
    ModelProviderUpdate,
    ModelProviderListResponse,
    ModelInfo,
    ModelInfoCreate,
    ModelInfoUpdate,
    ModelListResponse,
    ModelTestRequest,
    ModelTestResponse,
    ModelConfigRequest,
    ModelConfigResponse,
    ModelUsageStats,
    ProviderType,
    ModelType
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/models", tags=["模型管理"])

# 内存存储，实际项目中应该使用数据库
providers_db: Dict[str, Dict] = {}
models_db: Dict[str, Dict] = {}
configs_db: Dict[str, Dict] = {}

# 支持的中国国内模型厂商预设配置
SUPPORTED_PROVIDERS = {
    "zhipu": {
        "name": "智谱AI",
        "provider_type": "zhipu",
        "display_name": "智谱AI",
        "description": "智谱AI是一家专注于大模型研发的中国人工智能公司，提供GLM系列模型。",
        "api_base": "https://open.bigmodel.cn/api/paas/v4",
        "logo": "/zhipu-logo.png",
        "models": [
            {
                "model_id": "glm-4",
                "name": "GLM-4",
                "model_type": "chat",
                "description": "智谱AI最新对话模型",
                "context_length": 128000,
                "pricing": {"input": 0.1, "output": 0.1},
                "capabilities": ["text_generation", "function_calling"]
            },
            {
                "model_id": "glm-4v",
                "name": "GLM-4V",
                "model_type": "multimodal",
                "description": "支持图像理解的多模态模型",
                "context_length": 8192,
                "pricing": {"input": 0.2, "output": 0.2},
                "capabilities": ["text_generation", "image_understanding"]
            },
            {
                "model_id": "embedding-2",
                "name": "Embedding-2",
                "model_type": "embedding",
                "description": "中文文本嵌入模型",
                "context_length": 1024,
                "pricing": {"input": 0.001, "output": 0},
                "capabilities": ["text_embedding"]
            }
        ]
    },
    "baidu": {
        "name": "百度文心",
        "provider_type": "baidu",
        "display_name": "百度文心",
        "description": "百度文心大模型是百度研发的知识增强大语言模型，具有中文理解和知识覆盖优势。",
        "api_base": "https://aip.baidubce.com",
        "logo": "/baidu-logo.png",
        "models": [
            {
                "model_id": "ernie-4.0-8k",
                "name": "ERNIE-4.0-8K",
                "model_type": "chat",
                "description": "文心大模型4.0版本",
                "context_length": 8192,
                "pricing": {"input": 0.12, "output": 0.12},
                "capabilities": ["text_generation", "function_calling"]
            },
            {
                "model_id": "ernie-3.5-8k",
                "name": "ERNIE-3.5-8K",
                "model_type": "chat",
                "description": "文心大模型3.5版本",
                "context_length": 8192,
                "pricing": {"input": 0.012, "output": 0.012},
                "capabilities": ["text_generation"]
            }
        ]
    },
    "iflytek": {
        "name": "讯飞星火",
        "provider_type": "iflytek",
        "display_name": "讯飞星火",
        "description": "科大讯飞开发的大语言模型，在语音交互和垂直领域应用方面具有优势。",
        "api_base": "https://spark-api.xf-yun.com/v1",
        "logo": "/iflytek-logo.png",
        "models": [
            {
                "model_id": "spark-3.5",
                "name": "星火认知3.5",
                "model_type": "chat",
                "description": "科大讯飞的大语言模型，专注于认知智能和语音交互",
                "context_length": 8192,
                "pricing": {"input": 0.018, "output": 0.018},
                "capabilities": ["text_generation"]
            }
        ]
    }
}

# 辅助函数
def _mask_api_key(api_key: str) -> str:
    """脱敏API密钥"""
    if not api_key or len(api_key) < 8:
        return "****"
    return api_key[:4] + "*" * (len(api_key) - 8) + api_key[-4:]

def _generate_id() -> str:
    """生成UUID"""
    return str(uuid.uuid4())

# ==================== 模型提供商相关接口 ====================

@router.get("/providers", response_model=List[Dict[str, Any]])
async def get_providers():
    """
    获取所有支持的模型提供商
    """
    try:
        providers = []
        
        # 返回预设的提供商信息
        for provider_key, provider_data in SUPPORTED_PROVIDERS.items():
            # 检查是否已配置
            configured_provider = providers_db.get(provider_key)
            
            provider_info = {
                "id": provider_key,
                "name": provider_data["name"],
                "display_name": provider_data["display_name"],
                "provider_type": provider_data["provider_type"],
                "description": provider_data["description"],
                "logo": provider_data["logo"],
                "api_base": provider_data["api_base"],
                "is_configured": configured_provider is not None,
                "is_enabled": configured_provider["is_enabled"] if configured_provider else False,
                "model_count": len(provider_data["models"]),
                "supported_models": provider_data["models"]
            }
            
            # 如果已配置，添加脱敏的API密钥信息
            if configured_provider:
                provider_info.update({
                    "api_key_masked": _mask_api_key(configured_provider.get("api_key", "")),
                    "created_at": configured_provider.get("created_at"),
                    "updated_at": configured_provider.get("updated_at")
                })
            
            providers.append(provider_info)
        
        return {
            "success": True,
            "data": providers,
            "total": len(providers)
        }
        
    except Exception as e:
        logger.error(f"获取模型提供商列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取模型提供商列表失败")

@router.get("/providers/{provider_id}")
async def get_provider_details(provider_id: str):
    """
    获取特定提供商的详细信息
    """
    try:
        if provider_id not in SUPPORTED_PROVIDERS:
            raise HTTPException(status_code=404, detail="提供商不存在")
        
        provider_data = SUPPORTED_PROVIDERS[provider_id]
        configured_provider = providers_db.get(provider_id)
        
        provider_info = {
            "id": provider_id,
            "name": provider_data["name"],
            "display_name": provider_data["display_name"],
            "provider_type": provider_data["provider_type"],
            "description": provider_data["description"],
            "logo": provider_data["logo"],
            "api_base": provider_data["api_base"],
            "is_configured": configured_provider is not None,
            "is_enabled": configured_provider["is_enabled"] if configured_provider else False,
            "models": provider_data["models"]
        }
        
        if configured_provider:
            provider_info.update({
                "api_key_masked": _mask_api_key(configured_provider.get("api_key", "")),
                "created_at": configured_provider.get("created_at"),
                "updated_at": configured_provider.get("updated_at"),
                "enabled_models": configured_provider.get("enabled_models", [])
            })
        
        return {
            "success": True,
            "data": provider_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取提供商详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取提供商详情失败")

@router.post("/providers/{provider_id}/configure")
async def configure_provider(provider_id: str, request: dict):
    """
    配置模型提供商的API密钥和设置
    """
    try:
        if provider_id not in SUPPORTED_PROVIDERS:
            raise HTTPException(status_code=404, detail="提供商不存在")
        
        api_key = request.get("api_key")
        api_base = request.get("api_base")
        
        if not api_key:
            raise HTTPException(status_code=400, detail="API密钥不能为空")
        
        # 模拟API连接测试
        await asyncio.sleep(0.5)  # 模拟网络延迟
        
        now = datetime.now().isoformat()
        
        # 保存配置
        providers_db[provider_id] = {
            "id": provider_id,
            "api_key": api_key,
            "api_base": api_base or SUPPORTED_PROVIDERS[provider_id]["api_base"],
            "is_enabled": True,
            "enabled_models": [],
            "created_at": now,
            "updated_at": now
        }
        
        return {
            "success": True,
            "message": "提供商配置成功",
            "data": {
                "provider_id": provider_id,
                "is_configured": True,
                "test_result": {
                    "success": True,
                    "latency": 120.5,
                    "message": "API连接测试成功"
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"配置提供商失败: {str(e)}")
        raise HTTPException(status_code=500, detail="配置提供商失败")

@router.post("/providers/{provider_id}/test")
async def test_provider_connection(provider_id: str):
    """
    测试提供商API连接
    """
    try:
        if provider_id not in SUPPORTED_PROVIDERS:
            raise HTTPException(status_code=404, detail="提供商不存在")
        
        configured_provider = providers_db.get(provider_id)
        if not configured_provider:
            raise HTTPException(status_code=400, detail="提供商尚未配置")
        
        # 模拟API连接测试
        start_time = time.time()
        await asyncio.sleep(0.3)  # 模拟网络延迟
        latency = (time.time() - start_time) * 1000
        
        return {
            "success": True,
            "data": {
                "provider_id": provider_id,
                "test_result": {
                    "success": True,
                    "latency": round(latency, 2),
                    "message": "API连接正常",
                    "timestamp": datetime.now().isoformat()
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"测试提供商连接失败: {str(e)}")
        raise HTTPException(status_code=500, detail="测试提供商连接失败")

@router.post("/providers/{provider_id}/models/select")
async def select_provider_models(provider_id: str, request: dict):
    """
    选择启用提供商的特定模型
    """
    try:
        if provider_id not in SUPPORTED_PROVIDERS:
            raise HTTPException(status_code=404, detail="提供商不存在")
        
        configured_provider = providers_db.get(provider_id)
        if not configured_provider:
            raise HTTPException(status_code=400, detail="提供商尚未配置")
        
        selected_models = request.get("selected_models", [])
        
        # 验证选择的模型是否存在
        available_models = [m["model_id"] for m in SUPPORTED_PROVIDERS[provider_id]["models"]]
        invalid_models = [m for m in selected_models if m not in available_models]
        
        if invalid_models:
            raise HTTPException(status_code=400, detail=f"无效的模型: {invalid_models}")
        
        # 更新启用的模型列表
        providers_db[provider_id]["enabled_models"] = selected_models
        providers_db[provider_id]["updated_at"] = datetime.now().isoformat()
        
        return {
            "success": True,
            "message": "模型选择已更新",
            "data": {
                "provider_id": provider_id,
                "enabled_models": selected_models,
                "total_enabled": len(selected_models)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"选择提供商模型失败: {str(e)}")
        raise HTTPException(status_code=500, detail="选择提供商模型失败")

# ==================== 模型相关接口 ====================

@router.get("/")
async def get_models(
    provider: Optional[str] = Query(None, description="提供商筛选"),
    model_type: Optional[str] = Query(None, description="模型类型筛选"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    enabled_only: bool = Query(True, description="仅显示已启用的模型")
):
    """
    获取模型列表
    """
    try:
        models = []
        
        for provider_id, provider_data in SUPPORTED_PROVIDERS.items():
            # 应用提供商筛选
            if provider and provider_id != provider:
                continue
            
            configured_provider = providers_db.get(provider_id)
            enabled_models = configured_provider.get("enabled_models", []) if configured_provider else []
            
            for model_data in provider_data["models"]:
                # 应用已启用筛选
                if enabled_only and model_data["model_id"] not in enabled_models:
                    continue
                
                # 应用模型类型筛选
                if model_type and model_data["model_type"] != model_type:
                    continue
                
                # 应用搜索筛选
                if search:
                    search_text = f"{model_data['name']} {model_data['description']}".lower()
                    if search.lower() not in search_text:
                        continue
                
                model_info = {
                    "id": f"{provider_id}_{model_data['model_id']}",
                    "model_id": model_data["model_id"],
                    "name": model_data["name"],
                    "model_type": model_data["model_type"],
                    "description": model_data["description"],
                    "provider_id": provider_id,
                    "provider_name": provider_data["name"],
                    "context_length": model_data["context_length"],
                    "capabilities": model_data["capabilities"],
                    "pricing": model_data["pricing"],
                    "is_enabled": model_data["model_id"] in enabled_models,
                    "is_configured": configured_provider is not None
                }
                
                models.append(model_info)
        
        return {
            "success": True,
            "data": {
                "models": models,
                "total": len(models),
                "filters": {
                    "provider": provider,
                    "model_type": model_type,
                    "search": search,
                    "enabled_only": enabled_only
                }
            }
        }
        
    except Exception as e:
        logger.error(f"获取模型列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取模型列表失败")

@router.get("/{provider_id}/{model_id}")
async def get_model_details(provider_id: str, model_id: str):
    """
    获取特定模型的详细信息
    """
    try:
        if provider_id not in SUPPORTED_PROVIDERS:
            raise HTTPException(status_code=404, detail="提供商不存在")
        
        provider_data = SUPPORTED_PROVIDERS[provider_id]
        model_data = None
        
        for model in provider_data["models"]:
            if model["model_id"] == model_id:
                model_data = model
                break
        
        if not model_data:
            raise HTTPException(status_code=404, detail="模型不存在")
        
        configured_provider = providers_db.get(provider_id)
        enabled_models = configured_provider.get("enabled_models", []) if configured_provider else []
        
        model_info = {
            "id": f"{provider_id}_{model_id}",
            "model_id": model_id,
            "name": model_data["name"],
            "model_type": model_data["model_type"],
            "description": model_data["description"],
            "provider_id": provider_id,
            "provider_name": provider_data["name"],
            "provider_logo": provider_data["logo"],
            "context_length": model_data["context_length"],
            "capabilities": model_data["capabilities"],
            "pricing": model_data["pricing"],
            "is_enabled": model_id in enabled_models,
            "is_configured": configured_provider is not None,
            "usage_examples": _get_model_usage_examples(model_data["model_type"])
        }
        
        return {
            "success": True,
            "data": model_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取模型详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取模型详情失败")

@router.post("/{provider_id}/{model_id}/test")
async def test_model(provider_id: str, model_id: str, request: ModelTestRequest):
    """
    测试模型调用
    """
    try:
        if provider_id not in SUPPORTED_PROVIDERS:
            raise HTTPException(status_code=404, detail="提供商不存在")
        
        configured_provider = providers_db.get(provider_id)
        if not configured_provider:
            raise HTTPException(status_code=400, detail="提供商尚未配置")
        
        # 检查模型是否存在
        provider_data = SUPPORTED_PROVIDERS[provider_id]
        model_exists = any(m["model_id"] == model_id for m in provider_data["models"])
        
        if not model_exists:
            raise HTTPException(status_code=404, detail="模型不存在")
        
        # 模拟模型调用
        start_time = time.time()
        await asyncio.sleep(1.0)  # 模拟模型响应时间
        latency = (time.time() - start_time) * 1000
        
        # 模拟回复
        response_text = f"这是来自{provider_data['name']}的{model_id}模型的测试回复。您的消息是：{request.message}"
        
        return {
            "success": True,
            "message": "模型测试成功",
            "latency": round(latency, 2),
            "response": response_text,
            "token_usage": {
                "input_tokens": len(request.message),
                "output_tokens": len(response_text),
                "total_tokens": len(request.message) + len(response_text)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"测试模型失败: {str(e)}")
        raise HTTPException(status_code=500, detail="测试模型失败")

# ==================== 配置管理接口 ====================

@router.post("/config")
async def create_model_config(request: ModelConfigRequest):
    """
    创建模型配置
    """
    try:
        config_id = _generate_id()
        now = datetime.now().isoformat()
        
        config_data = {
            "id": config_id,
            "name": request.name,
            "provider_id": request.provider_id,
            "model_id": request.model_id,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "top_p": request.top_p,
            "frequency_penalty": request.frequency_penalty,
            "presence_penalty": request.presence_penalty,
            "system_prompt": request.system_prompt,
            "config": request.config,
            "created_at": now,
            "updated_at": now
        }
        
        configs_db[config_id] = config_data
        
        return {
            "success": True,
            "message": "模型配置创建成功",
            "data": config_data
        }
        
    except Exception as e:
        logger.error(f"创建模型配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail="创建模型配置失败")

@router.get("/config")
async def get_model_configs(
    provider: Optional[str] = Query(None, description="提供商筛选"),
    status: Optional[str] = Query(None, description="状态筛选")
):
    """
    获取模型配置列表
    """
    try:
        configs = []
        
        for config_data in configs_db.values():
            # 应用提供商筛选
            if provider and config_data["provider_id"] != provider:
                continue
            
            configs.append(config_data)
        
        return {
            "success": True,
            "data": {
                "configs": configs,
                "total": len(configs)
            }
        }
        
    except Exception as e:
        logger.error(f"获取模型配置列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取模型配置列表失败")

@router.get("/health")
async def get_models_health():
    """
    获取模型服务健康状态
    """
    try:
        total_providers = len(SUPPORTED_PROVIDERS)
        configured_providers = len(providers_db)
        total_models = sum(len(p["models"]) for p in SUPPORTED_PROVIDERS.values())
        enabled_models = sum(len(p.get("enabled_models", [])) for p in providers_db.values())
        
        health_data = {
            "service_status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "statistics": {
                "total_providers": total_providers,
                "configured_providers": configured_providers,
                "total_models": total_models,
                "enabled_models": enabled_models,
                "total_configs": len(configs_db)
            },
            "provider_status": {}
        }
        
        # 检查各提供商状态
        for provider_id in SUPPORTED_PROVIDERS.keys():
            configured = provider_id in providers_db
            health_data["provider_status"][provider_id] = {
                "configured": configured,
                "enabled": providers_db[provider_id]["is_enabled"] if configured else False,
                "model_count": len(providers_db[provider_id].get("enabled_models", [])) if configured else 0
            }
        
        return {
            "success": True,
            "data": health_data
        }
        
    except Exception as e:
        logger.error(f"获取健康状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取健康状态失败")

# ==================== 辅助函数 ====================

def _get_model_usage_examples(model_type: str) -> List[Dict[str, str]]:
    """获取模型使用示例"""
    examples = {
        "chat": [
            {"title": "日常对话", "prompt": "你好，请介绍一下你自己"},
            {"title": "问答助手", "prompt": "请解释一下什么是人工智能"},
            {"title": "创意写作", "prompt": "请写一首关于春天的诗"}
        ],
        "embedding": [
            {"title": "文本嵌入", "prompt": "将这段文本转换为向量表示"},
            {"title": "语义搜索", "prompt": "找出与查询最相似的文档"},
            {"title": "文本聚类", "prompt": "将相似的文本分组"}
        ],
        "code": [
            {"title": "代码生成", "prompt": "用Python写一个快速排序算法"},
            {"title": "代码解释", "prompt": "解释这段代码的功能"},
            {"title": "代码优化", "prompt": "优化这段代码的性能"}
        ],
        "multimodal": [
            {"title": "图像描述", "prompt": "描述这张图片的内容"},
            {"title": "视觉问答", "prompt": "图片中有几个人?"},
            {"title": "图文理解", "prompt": "根据图片和文字，回答问题"}
        ]
    }
    
    return examples.get(model_type, []) 