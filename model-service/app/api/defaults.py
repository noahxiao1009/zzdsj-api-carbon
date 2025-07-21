"""
模型服务默认模型管理API扩展
为前端系统设置页面提供默认模型配置功能
"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
import uuid
import json

from ..schemas.model_provider import ModelType, ProviderType
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
defaults_router = APIRouter(prefix="/api/v1/models", tags=["默认模型管理"])

# 扩展数据模型

class SetDefaultModelRequest(BaseModel):
    """设置默认模型请求"""
    provider_id: str = Field(..., description="提供商ID")
    model_id: str = Field(..., description="模型ID")
    config_params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="配置参数")
    scope: str = Field("system", description="配置范围: system/user")
    user_id: Optional[str] = Field(None, description="用户ID（用户级配置时需要）")

class BatchSetDefaultRequest(BaseModel):
    """批量设置默认模型请求"""
    defaults: List[Dict[str, Any]] = Field(..., description="默认模型配置列表")
    scope: str = Field("system", description="配置范围")
    user_id: Optional[str] = Field(None, description="用户ID")

class DefaultModelConfig(BaseModel):
    """默认模型配置"""
    id: str
    category: ModelType
    provider_id: str
    model_id: str
    model_name: str
    provider_name: str
    scope: str
    user_id: Optional[str] = None
    config_params: Dict[str, Any] = {}
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

class ProviderCategory(BaseModel):
    """厂商分类"""
    category: str
    category_name: str
    category_description: str
    providers: List[Dict[str, Any]]
    total_models: int
    enabled_models: int

class ModelCategoryGroup(BaseModel):
    """模型类别组织"""
    category: ModelType
    category_name: str
    category_description: str
    icon: str
    models: List[Dict[str, Any]]
    default_model_id: Optional[str] = None
    total_count: int
    enabled_count: int

# 内存存储 - 默认模型配置
default_configs_db: Dict[str, Dict] = {}

# 预设默认模型配置
SYSTEM_DEFAULT_CONFIGS = {
    "chat": {
        "provider_id": "zhipu",
        "model_id": "glm-4",
        "config_params": {
            "temperature": 0.7,
            "max_tokens": 4000,
            "top_p": 0.9
        }
    },
    "embedding": {
        "provider_id": "zhipu", 
        "model_id": "embedding-2",
        "config_params": {
            "batch_size": 100
        }
    },
    "multimodal": {
        "provider_id": "zhipu",
        "model_id": "glm-4v",
        "config_params": {
            "temperature": 0.5,
            "max_tokens": 2000
        }
    }
}

# 厂商分类配置
PROVIDER_CATEGORIES = {
    "domestic_major": {
        "category_name": "国内主流厂商",
        "category_description": "国内大型科技公司的主流AI模型服务",
        "providers": ["zhipu", "baidu", "iflytek"]
    },
    "domestic_emerging": {
        "category_name": "国内新兴厂商", 
        "category_description": "国内新兴AI公司和专业模型厂商",
        "providers": ["moonshot", "deepseek", "minimax"]
    },
    "international": {
        "category_name": "国际厂商",
        "category_description": "国际知名AI厂商的模型服务",
        "providers": ["openai", "anthropic", "cohere"]
    },
    "open_source": {
        "category_name": "开源/自定义",
        "category_description": "开源模型和自定义部署的模型服务",
        "providers": ["ollama", "vllm", "custom"]
    }
}

# 模型类别配置
MODEL_CATEGORY_CONFIG = {
    "chat": {
        "category_name": "对话模型",
        "category_description": "用于文本对话和内容生成的大语言模型",
        "icon": "message-circle",
        "default_config": {
            "temperature": 0.7,
            "max_tokens": 4000,
            "top_p": 0.9,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0
        }
    },
    "embedding": {
        "category_name": "嵌入模型", 
        "category_description": "用于文本向量化和语义搜索的嵌入模型",
        "icon": "vector",
        "default_config": {
            "batch_size": 100,
            "normalize": True
        }
    },
    "multimodal": {
        "category_name": "多模态模型",
        "category_description": "支持图像理解和多模态交互的模型",
        "icon": "image-text",
        "default_config": {
            "temperature": 0.5,
            "max_tokens": 2000,
            "detail_level": "high"
        }
    },
    "code": {
        "category_name": "代码模型",
        "category_description": "专门用于代码生成和理解的模型",
        "icon": "code",
        "default_config": {
            "temperature": 0.3,
            "max_tokens": 8000,
            "top_p": 0.8
        }
    },
    "image": {
        "category_name": "图像模型",
        "category_description": "用于图像生成和编辑的模型",
        "icon": "image",
        "default_config": {
            "quality": "standard",
            "size": "1024x1024",
            "style": "natural"
        }
    }
}

def _generate_id() -> str:
    """生成UUID"""
    return str(uuid.uuid4())

def _get_provider_info(provider_id: str) -> Dict[str, Any]:
    """获取提供商信息"""
    from .models import SUPPORTED_PROVIDERS
    return SUPPORTED_PROVIDERS.get(provider_id, {})

def _get_model_info(provider_id: str, model_id: str) -> Dict[str, Any]:
    """获取模型信息"""
    from .models import SUPPORTED_PROVIDERS
    provider_data = SUPPORTED_PROVIDERS.get(provider_id, {})
    for model in provider_data.get("models", []):
        if model["model_id"] == model_id:
            return model
    return {}

def _initialize_system_defaults():
    """初始化系统默认配置"""
    for category, config in SYSTEM_DEFAULT_CONFIGS.items():
        config_id = f"system_default_{category}"
        if config_id not in default_configs_db:
            provider_info = _get_provider_info(config["provider_id"])
            model_info = _get_model_info(config["provider_id"], config["model_id"])
            
            default_configs_db[config_id] = {
                "id": config_id,
                "category": category,
                "provider_id": config["provider_id"],
                "model_id": config["model_id"],
                "model_name": model_info.get("name", config["model_id"]),
                "provider_name": provider_info.get("name", config["provider_id"]),
                "scope": "system",
                "user_id": None,
                "config_params": config["config_params"],
                "is_active": True,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }

# 初始化系统默认配置
_initialize_system_defaults()

# ==================== 按厂商组织的接口 ====================

@defaults_router.get("/providers/organized")
async def get_providers_organized():
    """
    按类别组织提供商列表
    """
    try:
        from .models import SUPPORTED_PROVIDERS, providers_db
        
        organized_providers = {}
        statistics = {
            "total_providers": 0,
            "configured_providers": 0,
            "total_models": 0,
            "enabled_models": 0
        }
        
        for category, config in PROVIDER_CATEGORIES.items():
            category_providers = []
            
            for provider_id in config["providers"]:
                if provider_id not in SUPPORTED_PROVIDERS:
                    continue
                    
                provider_data = SUPPORTED_PROVIDERS[provider_id]
                configured_provider = providers_db.get(provider_id)
                
                enabled_models = configured_provider.get("enabled_models", []) if configured_provider else []
                
                provider_info = {
                    "id": provider_id,
                    "name": provider_data["name"],
                    "display_name": provider_data["display_name"],
                    "description": provider_data["description"],
                    "logo": provider_data["logo"],
                    "api_base": provider_data["api_base"],
                    "is_configured": configured_provider is not None,
                    "is_enabled": configured_provider["is_enabled"] if configured_provider else False,
                    "model_count": len(provider_data["models"]),
                    "enabled_model_count": len(enabled_models),
                    "supported_categories": list(set(m["model_type"] for m in provider_data["models"]))
                }
                
                category_providers.append(provider_info)
                
                # 更新统计信息
                statistics["total_providers"] += 1
                if configured_provider:
                    statistics["configured_providers"] += 1
                statistics["total_models"] += len(provider_data["models"])
                statistics["enabled_models"] += len(enabled_models)
            
            organized_providers[category] = {
                "category": category,
                "category_name": config["category_name"],
                "category_description": config["category_description"],
                "providers": category_providers,
                "total_models": sum(p["model_count"] for p in category_providers),
                "enabled_models": sum(p["enabled_model_count"] for p in category_providers)
            }
        
        return {
            "success": True,
            "data": {
                **organized_providers,
                "statistics": statistics
            }
        }
        
    except Exception as e:
        logger.error(f"获取按厂商组织的列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取厂商列表失败")

# ==================== 按模型类别组织的接口 ====================

@defaults_router.get("/models/by-category")
async def get_models_by_category(
    enabled_only: bool = Query(True, description="仅显示已启用模型"),
    include_defaults: bool = Query(True, description="包含默认模型信息")
):
    """
    按模型类别组织模型列表
    """
    try:
        from .models import SUPPORTED_PROVIDERS, providers_db
        
        models_by_category = {}
        
        for category, config in MODEL_CATEGORY_CONFIG.items():
            category_models = []
            default_model_id = None
            
            # 获取该类别的默认模型
            if include_defaults:
                for default_config in default_configs_db.values():
                    if default_config["category"] == category and default_config["scope"] == "system":
                        default_model_id = f"{default_config['provider_id']}_{default_config['model_id']}"
                        break
            
            # 收集该类别的所有模型
            for provider_id, provider_data in SUPPORTED_PROVIDERS.items():
                configured_provider = providers_db.get(provider_id)
                enabled_models = configured_provider.get("enabled_models", []) if configured_provider else []
                
                for model_data in provider_data["models"]:
                    if model_data["model_type"] != category:
                        continue
                    
                    # 应用已启用筛选
                    if enabled_only and model_data["model_id"] not in enabled_models:
                        continue
                    
                    model_info = {
                        "id": f"{provider_id}_{model_data['model_id']}",
                        "model_id": model_data["model_id"],
                        "name": model_data["name"],
                        "provider_id": provider_id,
                        "provider_name": provider_data["name"],
                        "provider_logo": provider_data["logo"],
                        "description": model_data["description"],
                        "capabilities": model_data["capabilities"],
                        "context_length": model_data["context_length"],
                        "pricing": model_data["pricing"],
                        "is_default": f"{provider_id}_{model_data['model_id']}" == default_model_id,
                        "is_enabled": model_data["model_id"] in enabled_models,
                        "is_configured": configured_provider is not None
                    }
                    
                    category_models.append(model_info)
            
            models_by_category[f"{category}_models"] = {
                "category": category,
                "category_name": config["category_name"],
                "category_description": config["category_description"],
                "icon": config["icon"],
                "default_model_id": default_model_id,
                "models": category_models,
                "total_count": len(category_models),
                "enabled_count": sum(1 for m in category_models if m["is_enabled"])
            }
        
        return {
            "success": True,
            "data": models_by_category
        }
        
    except Exception as e:
        logger.error(f"获取按类别组织的模型列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取模型列表失败")

# ==================== 默认模型管理接口 ====================

@defaults_router.get("/defaults")
async def get_default_models(
    scope: str = Query("system", description="配置范围: system/user"),
    user_id: Optional[str] = Query(None, description="用户ID（用户级配置时需要）")
):
    """
    获取所有类别的默认模型配置
    """
    try:
        defaults = []
        
        for config_data in default_configs_db.values():
            # 应用范围筛选
            if config_data["scope"] != scope:
                continue
            
            # 应用用户筛选
            if scope == "user" and config_data["user_id"] != user_id:
                continue
            
            defaults.append(config_data)
        
        return {
            "success": True,
            "data": {
                "defaults": defaults,
                "total": len(defaults),
                "scope": scope,
                "user_id": user_id
            }
        }
        
    except Exception as e:
        logger.error(f"获取默认模型配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取默认模型配置失败")

@defaults_router.put("/defaults/{category}")
async def set_default_model(
    category: ModelType,
    request: SetDefaultModelRequest
):
    """
    设置指定类别的默认模型
    """
    try:
        from .models import SUPPORTED_PROVIDERS
        
        # 验证提供商和模型是否存在
        if request.provider_id not in SUPPORTED_PROVIDERS:
            raise HTTPException(status_code=404, detail="提供商不存在")
        
        provider_data = SUPPORTED_PROVIDERS[request.provider_id]
        model_exists = any(m["model_id"] == request.model_id for m in provider_data["models"])
        
        if not model_exists:
            raise HTTPException(status_code=404, detail="模型不存在")
        
        # 验证模型类型匹配
        model_info = _get_model_info(request.provider_id, request.model_id)
        if model_info.get("model_type") != category:
            raise HTTPException(status_code=400, detail=f"模型类型不匹配，期望: {category}")
        
        # 生成配置ID
        config_id = f"{request.scope}_default_{category}"
        if request.scope == "user" and request.user_id:
            config_id = f"user_{request.user_id}_default_{category}"
        
        # 获取提供商和模型信息
        provider_info = _get_provider_info(request.provider_id)
        
        now = datetime.now().isoformat()
        
        # 保存或更新默认配置
        default_configs_db[config_id] = {
            "id": config_id,
            "category": category,
            "provider_id": request.provider_id,
            "model_id": request.model_id,
            "model_name": model_info.get("name", request.model_id),
            "provider_name": provider_info.get("name", request.provider_id),
            "scope": request.scope,
            "user_id": request.user_id,
            "config_params": request.config_params,
            "is_active": True,
            "created_at": default_configs_db.get(config_id, {}).get("created_at", now),
            "updated_at": now
        }
        
        return {
            "success": True,
            "message": f"{category}类别默认模型设置成功",
            "data": {
                "category": category,
                "provider_id": request.provider_id,
                "model_id": request.model_id,
                "model_name": model_info.get("name"),
                "scope": request.scope,
                "config_id": config_id
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"设置默认模型失败: {str(e)}")
        raise HTTPException(status_code=500, detail="设置默认模型失败")

@defaults_router.delete("/defaults/{category}")
async def reset_default_model(
    category: ModelType,
    scope: str = Query("system", description="配置范围"),
    user_id: Optional[str] = Query(None, description="用户ID")
):
    """
    重置指定类别的默认模型为系统默认
    """
    try:
        # 生成配置ID
        config_id = f"{scope}_default_{category}"
        if scope == "user" and user_id:
            config_id = f"user_{user_id}_default_{category}"
        
        if config_id not in default_configs_db:
            raise HTTPException(status_code=404, detail="默认配置不存在")
        
        # 删除配置
        deleted_config = default_configs_db.pop(config_id)
        
        return {
            "success": True,
            "message": f"{category}类别默认模型已重置",
            "data": {
                "category": category,
                "scope": scope,
                "deleted_config": deleted_config
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重置默认模型失败: {str(e)}")
        raise HTTPException(status_code=500, detail="重置默认模型失败")

@defaults_router.put("/defaults/batch")
async def set_default_models_batch(request: BatchSetDefaultRequest):
    """
    批量设置多个类别的默认模型
    """
    try:
        results = []
        errors = []
        
        for default_config in request.defaults:
            try:
                category = default_config.get("category")
                provider_id = default_config.get("provider_id")
                model_id = default_config.get("model_id")
                config_params = default_config.get("config_params", {})
                
                if not all([category, provider_id, model_id]):
                    errors.append({
                        "config": default_config,
                        "error": "缺少必要字段: category, provider_id, model_id"
                    })
                    continue
                
                # 创建单个设置请求
                set_request = SetDefaultModelRequest(
                    provider_id=provider_id,
                    model_id=model_id,
                    config_params=config_params,
                    scope=request.scope,
                    user_id=request.user_id
                )
                
                # 调用单个设置方法
                result = await set_default_model(category, set_request)
                results.append({
                    "category": category,
                    "success": True,
                    "data": result["data"]
                })
                
            except Exception as e:
                errors.append({
                    "config": default_config,
                    "error": str(e)
                })
        
        return {
            "success": len(errors) == 0,
            "message": f"批量设置完成，成功: {len(results)}, 失败: {len(errors)}",
            "data": {
                "successful": results,
                "failed": errors,
                "total_processed": len(request.defaults),
                "success_count": len(results),
                "error_count": len(errors)
            }
        }
        
    except Exception as e:
        logger.error(f"批量设置默认模型失败: {str(e)}")
        raise HTTPException(status_code=500, detail="批量设置默认模型失败")

# ==================== 配置模板接口 ====================

@defaults_router.get("/config-templates/{model_type}")
async def get_model_config_templates(model_type: ModelType):
    """
    获取指定模型类型的配置模板
    """
    try:
        # 预设配置模板
        templates = {
            "chat": [
                {
                    "name": "保守配置",
                    "description": "适合正式业务场景，输出稳定可靠",
                    "config": {
                        "temperature": 0.3,
                        "max_tokens": 2000,
                        "top_p": 0.8,
                        "frequency_penalty": 0.0,
                        "presence_penalty": 0.0
                    }
                },
                {
                    "name": "均衡配置",
                    "description": "兼顾创意和稳定性的通用配置",
                    "config": {
                        "temperature": 0.7,
                        "max_tokens": 4000,
                        "top_p": 0.9,
                        "frequency_penalty": 0.0,
                        "presence_penalty": 0.0
                    }
                },
                {
                    "name": "创意配置",
                    "description": "适合创意写作和头脑风暴",
                    "config": {
                        "temperature": 0.9,
                        "max_tokens": 4000,
                        "top_p": 0.95,
                        "frequency_penalty": 0.2,
                        "presence_penalty": 0.1
                    }
                }
            ],
            "embedding": [
                {
                    "name": "标准配置",
                    "description": "通用文本嵌入配置",
                    "config": {
                        "batch_size": 100,
                        "normalize": True,
                        "truncate": True
                    }
                },
                {
                    "name": "高性能配置",
                    "description": "大批量处理优化配置",
                    "config": {
                        "batch_size": 500,
                        "normalize": True,
                        "truncate": True,
                        "parallel_requests": 5
                    }
                }
            ],
            "multimodal": [
                {
                    "name": "高质量配置",
                    "description": "图像理解高质量配置",
                    "config": {
                        "temperature": 0.5,
                        "max_tokens": 2000,
                        "detail_level": "high",
                        "image_quality": "hd"
                    }
                }
            ],
            "code": [
                {
                    "name": "代码生成配置",
                    "description": "专用于代码生成的配置",
                    "config": {
                        "temperature": 0.3,
                        "max_tokens": 8000,
                        "top_p": 0.8,
                        "stop_sequences": ["```"]
                    }
                }
            ],
            "image": [
                {
                    "name": "标准图像生成",
                    "description": "通用图像生成配置",
                    "config": {
                        "quality": "standard",
                        "size": "1024x1024",
                        "style": "natural"
                    }
                }
            ]
        }
        
        # 参数定义
        parameter_definitions = {
            "temperature": {
                "type": "float",
                "min": 0.0,
                "max": 2.0,
                "default": 0.7,
                "step": 0.1,
                "description": "控制输出的随机性，值越高越随机"
            },
            "max_tokens": {
                "type": "integer",
                "min": 1,
                "max": 8000,
                "default": 4000,
                "description": "最大输出token数量"
            },
            "top_p": {
                "type": "float",
                "min": 0.0,
                "max": 1.0,
                "default": 0.9,
                "step": 0.05,
                "description": "核采样参数，控制候选词汇范围"
            },
            "frequency_penalty": {
                "type": "float",
                "min": -2.0,
                "max": 2.0,
                "default": 0.0,
                "step": 0.1,
                "description": "频率惩罚，减少重复内容"
            },
            "presence_penalty": {
                "type": "float",
                "min": -2.0,
                "max": 2.0,
                "default": 0.0,
                "step": 0.1,
                "description": "存在惩罚，鼓励话题多样性"
            }
        }
        
        model_templates = templates.get(model_type, [])
        
        return {
            "success": True,
            "data": {
                "model_type": model_type,
                "templates": model_templates,
                "parameter_definitions": parameter_definitions,
                "total_templates": len(model_templates)
            }
        }
        
    except Exception as e:
        logger.error(f"获取配置模板失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取配置模板失败")

# ==================== 前端集成接口 ====================

@defaults_router.get("/frontend/system-settings")
async def get_system_settings_data():
    """
    获取系统设置页面所需的完整数据
    """
    try:
        # 获取按厂商组织的数据
        providers_result = await get_providers_organized()
        
        # 获取按类别组织的模型
        models_result = await get_models_by_category(enabled_only=False, include_defaults=True)
        
        # 获取默认配置
        defaults_result = await get_default_models(scope="system")
        
        return {
            "success": True,
            "data": {
                "providers": providers_result["data"],
                "models_by_category": models_result["data"],
                "default_configs": defaults_result["data"]["defaults"],
                "categories": MODEL_CATEGORY_CONFIG,
                "provider_categories": PROVIDER_CATEGORIES,
                "last_updated": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"获取系统设置数据失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取系统设置数据失败")

@defaults_router.post("/frontend/test-model")
async def test_model_for_frontend(request: dict):
    """
    前端模型测试接口
    """
    try:
        provider_id = request.get("provider_id")
        model_id = request.get("model_id")
        message = request.get("message", "你好，这是一个测试消息")
        
        if not all([provider_id, model_id]):
            raise HTTPException(status_code=400, detail="缺少必要参数")
        
        # 调用现有的模型测试接口
        from .models import ModelTestRequest
        test_request = ModelTestRequest(message=message)
        
        # 这里调用模型测试逻辑（模拟）
        import time
        import asyncio
        
        start_time = time.time()
        await asyncio.sleep(0.8)  # 模拟测试延迟
        latency = (time.time() - start_time) * 1000
        
        return {
            "success": True,
            "test_result": {
                "latency": round(latency, 2),
                "response_preview": f"测试成功！来自{provider_id}的{model_id}模型回复：{message[:50]}...",
                "token_usage": {
                    "input_tokens": len(message),
                    "output_tokens": 25
                },
                "error": None,
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"前端模型测试失败: {str(e)}")
        return {
            "success": False,
            "test_result": {
                "latency": 0,
                "response_preview": None,
                "token_usage": None,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        }