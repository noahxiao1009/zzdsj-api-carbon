"""
模型管理器
负责模型注册、配置、默认模型设置等核心功能
"""

import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import uuid
import json

from ..schemas.model_provider import ModelType, ProviderType, ModelInfo, ModelProvider

logger = logging.getLogger(__name__)


class ModelManager:
    """模型管理器 - 统一管理所有模型相关操作"""
    
    def __init__(self):
        # 内存存储，实际项目中应该使用数据库
        self.providers_db: Dict[str, Dict] = {}
        self.models_db: Dict[str, Dict] = {}
        self.user_preferences_db: Dict[str, Dict] = {}
        self.system_defaults_db: Dict[str, Dict] = {}
        
        # 初始化系统默认配置
        self._initialize_system_defaults()
    
    def _initialize_system_defaults(self):
        """初始化系统默认模型配置"""
        system_defaults = {
            ModelType.CHAT: {
                "provider_id": "zhipu",
                "model_id": "glm-4",
                "config": {
                    "temperature": 0.7,
                    "max_tokens": 4000,
                    "top_p": 0.9
                }
            },
            ModelType.EMBEDDING: {
                "provider_id": "zhipu",
                "model_id": "embedding-2",
                "config": {
                    "batch_size": 100,
                    "normalize": True
                }
            },
            ModelType.MULTIMODAL: {
                "provider_id": "zhipu",
                "model_id": "glm-4v",
                "config": {
                    "temperature": 0.5,
                    "max_tokens": 2000,
                    "detail": "high"
                }
            },
            ModelType.CODE: {
                "provider_id": "deepseek",
                "model_id": "deepseek-coder",
                "config": {
                    "temperature": 0.3,
                    "max_tokens": 8000,
                    "top_p": 0.8
                }
            }
        }
        
        for model_type, config in system_defaults.items():
            self.system_defaults_db[model_type] = {
                "id": f"system_default_{model_type}",
                "model_type": model_type,
                "provider_id": config["provider_id"],
                "model_id": config["model_id"],
                "config": config["config"],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
    
    # ==================== 模型注册和管理 ====================
    
    async def register_model(self, model_config: Dict[str, Any]) -> str:
        """
        注册新模型
        
        Args:
            model_config: 模型配置信息
            
        Returns:
            模型ID
        """
        try:
            model_id = model_config.get("model_id") or str(uuid.uuid4())
            
            # 验证必要字段
            required_fields = ["name", "provider_id", "model_type"]
            for field in required_fields:
                if field not in model_config:
                    raise ValueError(f"缺少必要字段: {field}")
            
            # 构建模型信息
            model_info = {
                "id": model_id,
                "model_id": model_config["model_id"],
                "name": model_config["name"],
                "provider_id": model_config["provider_id"],
                "model_type": model_config["model_type"],
                "description": model_config.get("description", ""),
                "capabilities": model_config.get("capabilities", []),
                "context_length": model_config.get("context_length"),
                "max_tokens": model_config.get("max_tokens"),
                "pricing": model_config.get("pricing", {}),
                "config": model_config.get("config", {}),
                "is_enabled": model_config.get("is_enabled", True),
                "is_default": model_config.get("is_default", False),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            # 保存到数据库
            self.models_db[model_id] = model_info
            
            logger.info(f"模型注册成功: {model_id}")
            return model_id
            
        except Exception as e:
            logger.error(f"模型注册失败: {e}")
            raise
    
    async def get_available_models(
        self, 
        user_id: Optional[str] = None,
        model_type: Optional[ModelType] = None,
        provider_id: Optional[str] = None,
        enabled_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        获取可用模型列表
        
        Args:
            user_id: 用户ID（用于获取用户特定的模型权限）
            model_type: 模型类型筛选
            provider_id: 提供商筛选
            enabled_only: 仅返回已启用的模型
            
        Returns:
            模型列表
        """
        try:
            from .models import SUPPORTED_PROVIDERS, providers_db
            
            models = []
            
            for provider_key, provider_data in SUPPORTED_PROVIDERS.items():
                # 应用提供商筛选
                if provider_id and provider_key != provider_id:
                    continue
                
                configured_provider = providers_db.get(provider_key)
                enabled_models = configured_provider.get("enabled_models", []) if configured_provider else []
                
                for model_data in provider_data["models"]:
                    # 应用模型类型筛选
                    if model_type and model_data["model_type"] != model_type:
                        continue
                    
                    # 应用已启用筛选
                    if enabled_only and model_data["model_id"] not in enabled_models:
                        continue
                    
                    # 检查用户权限（如果提供了user_id）
                    if user_id:
                        # TODO: 实现用户权限检查逻辑
                        pass
                    
                    model_info = {
                        "id": f"{provider_key}_{model_data['model_id']}",
                        "model_id": model_data["model_id"],
                        "name": model_data["name"],
                        "provider_id": provider_key,
                        "provider_name": provider_data["name"],
                        "model_type": model_data["model_type"],
                        "description": model_data["description"],
                        "capabilities": model_data["capabilities"],
                        "context_length": model_data["context_length"],
                        "pricing": model_data["pricing"],
                        "is_enabled": model_data["model_id"] in enabled_models,
                        "is_configured": configured_provider is not None
                    }
                    
                    models.append(model_info)
            
            return models
            
        except Exception as e:
            logger.error(f"获取可用模型列表失败: {e}")
            raise
    
    # ==================== 默认模型管理 ====================
    
    async def set_system_default_model(
        self, 
        model_type: ModelType, 
        provider_id: str, 
        model_id: str,
        config: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        设置系统级默认模型
        
        Args:
            model_type: 模型类型
            provider_id: 提供商ID
            model_id: 模型ID
            config: 模型配置参数
            
        Returns:
            是否设置成功
        """
        try:
            # 验证模型是否存在
            if not await self._validate_model_exists(provider_id, model_id):
                raise ValueError(f"模型不存在: {provider_id}:{model_id}")
            
            # 验证模型类型匹配
            if not await self._validate_model_type(provider_id, model_id, model_type):
                raise ValueError(f"模型类型不匹配: {model_type}")
            
            # 更新系统默认配置
            self.system_defaults_db[model_type] = {
                "id": f"system_default_{model_type}",
                "model_type": model_type,
                "provider_id": provider_id,
                "model_id": model_id,
                "config": config or {},
                "created_at": self.system_defaults_db.get(model_type, {}).get("created_at", datetime.now().isoformat()),
                "updated_at": datetime.now().isoformat()
            }
            
            logger.info(f"系统默认模型设置成功: {model_type} -> {provider_id}:{model_id}")
            return True
            
        except Exception as e:
            logger.error(f"设置系统默认模型失败: {e}")
            raise
    
    async def set_user_default_model(
        self, 
        user_id: str,
        model_type: ModelType, 
        provider_id: str, 
        model_id: str,
        config: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        设置用户级默认模型
        
        Args:
            user_id: 用户ID
            model_type: 模型类型
            provider_id: 提供商ID
            model_id: 模型ID
            config: 模型配置参数
            
        Returns:
            是否设置成功
        """
        try:
            # 验证模型是否存在
            if not await self._validate_model_exists(provider_id, model_id):
                raise ValueError(f"模型不存在: {provider_id}:{model_id}")
            
            # 验证模型类型匹配
            if not await self._validate_model_type(provider_id, model_id, model_type):
                raise ValueError(f"模型类型不匹配: {model_type}")
            
            # 获取或创建用户偏好设置
            if user_id not in self.user_preferences_db:
                self.user_preferences_db[user_id] = {
                    "user_id": user_id,
                    "default_models": {},
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }
            
            # 更新用户默认模型配置
            self.user_preferences_db[user_id]["default_models"][model_type] = {
                "provider_id": provider_id,
                "model_id": model_id,
                "config": config or {},
                "set_at": datetime.now().isoformat()
            }
            
            self.user_preferences_db[user_id]["updated_at"] = datetime.now().isoformat()
            
            logger.info(f"用户默认模型设置成功: {user_id} {model_type} -> {provider_id}:{model_id}")
            return True
            
        except Exception as e:
            logger.error(f"设置用户默认模型失败: {e}")
            raise
    
    async def get_default_model(
        self, 
        model_type: ModelType,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取默认模型配置
        
        Args:
            model_type: 模型类型
            user_id: 用户ID（如果提供，优先返回用户级配置）
            
        Returns:
            默认模型配置
        """
        try:
            # 优先返回用户级配置
            if user_id and user_id in self.user_preferences_db:
                user_defaults = self.user_preferences_db[user_id]["default_models"]
                if model_type in user_defaults:
                    user_config = user_defaults[model_type]
                    return {
                        "source": "user",
                        "user_id": user_id,
                        "model_type": model_type,
                        "provider_id": user_config["provider_id"],
                        "model_id": user_config["model_id"],
                        "config": user_config["config"],
                        "set_at": user_config["set_at"]
                    }
            
            # 返回系统级配置
            if model_type in self.system_defaults_db:
                system_config = self.system_defaults_db[model_type]
                return {
                    "source": "system",
                    "user_id": None,
                    "model_type": model_type,
                    "provider_id": system_config["provider_id"],
                    "model_id": system_config["model_id"],
                    "config": system_config["config"],
                    "set_at": system_config["updated_at"]
                }
            
            # 如果没有配置，返回空
            return {
                "source": "none",
                "user_id": user_id,
                "model_type": model_type,
                "provider_id": None,
                "model_id": None,
                "config": {},
                "set_at": None
            }
            
        except Exception as e:
            logger.error(f"获取默认模型配置失败: {e}")
            raise
    
    async def get_user_model_preferences(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户的模型偏好设置
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户模型偏好设置
        """
        try:
            if user_id not in self.user_preferences_db:
                return {
                    "user_id": user_id,
                    "default_models": {},
                    "created_at": None,
                    "updated_at": None
                }
            
            return self.user_preferences_db[user_id]
            
        except Exception as e:
            logger.error(f"获取用户模型偏好失败: {e}")
            raise
    
    async def reset_user_default_model(
        self, 
        user_id: str, 
        model_type: ModelType
    ) -> bool:
        """
        重置用户默认模型为系统默认
        
        Args:
            user_id: 用户ID
            model_type: 模型类型
            
        Returns:
            是否重置成功
        """
        try:
            if user_id in self.user_preferences_db:
                user_defaults = self.user_preferences_db[user_id]["default_models"]
                if model_type in user_defaults:
                    del user_defaults[model_type]
                    self.user_preferences_db[user_id]["updated_at"] = datetime.now().isoformat()
                    
                    logger.info(f"用户默认模型重置成功: {user_id} {model_type}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"重置用户默认模型失败: {e}")
            raise
    
    # ==================== 模型配置管理 ====================
    
    async def create_model_config(
        self, 
        name: str,
        provider_id: str,
        model_id: str,
        config: Dict[str, Any],
        user_id: Optional[str] = None,
        description: Optional[str] = None
    ) -> str:
        """
        创建模型配置预设
        
        Args:
            name: 配置名称
            provider_id: 提供商ID
            model_id: 模型ID
            config: 配置参数
            user_id: 用户ID（如果是用户级配置）
            description: 配置描述
            
        Returns:
            配置ID
        """
        try:
            config_id = str(uuid.uuid4())
            
            # 验证模型是否存在
            if not await self._validate_model_exists(provider_id, model_id):
                raise ValueError(f"模型不存在: {provider_id}:{model_id}")
            
            config_info = {
                "id": config_id,
                "name": name,
                "description": description or "",
                "provider_id": provider_id,
                "model_id": model_id,
                "config": config,
                "user_id": user_id,
                "scope": "user" if user_id else "system",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            # 保存配置（这里应该保存到数据库）
            # TODO: 实现配置持久化存储
            
            logger.info(f"模型配置创建成功: {config_id}")
            return config_id
            
        except Exception as e:
            logger.error(f"创建模型配置失败: {e}")
            raise
    
    # ==================== 辅助方法 ====================
    
    async def _validate_model_exists(self, provider_id: str, model_id: str) -> bool:
        """验证模型是否存在"""
        try:
            from .models import SUPPORTED_PROVIDERS
            
            if provider_id not in SUPPORTED_PROVIDERS:
                return False
            
            provider_data = SUPPORTED_PROVIDERS[provider_id]
            return any(m["model_id"] == model_id for m in provider_data["models"])
            
        except Exception:
            return False
    
    async def _validate_model_type(
        self, 
        provider_id: str, 
        model_id: str, 
        expected_type: ModelType
    ) -> bool:
        """验证模型类型是否匹配"""
        try:
            from .models import SUPPORTED_PROVIDERS
            
            if provider_id not in SUPPORTED_PROVIDERS:
                return False
            
            provider_data = SUPPORTED_PROVIDERS[provider_id]
            for model in provider_data["models"]:
                if model["model_id"] == model_id:
                    return model["model_type"] == expected_type
            
            return False
            
        except Exception:
            return False
    
    async def get_model_statistics(self) -> Dict[str, Any]:
        """获取模型统计信息"""
        try:
            from .models import SUPPORTED_PROVIDERS, providers_db
            
            total_providers = len(SUPPORTED_PROVIDERS)
            configured_providers = len(providers_db)
            total_models = sum(len(p["models"]) for p in SUPPORTED_PROVIDERS.values())
            enabled_models = sum(len(p.get("enabled_models", [])) for p in providers_db.values())
            
            # 按类型统计模型
            models_by_type = {}
            for provider_data in SUPPORTED_PROVIDERS.values():
                for model in provider_data["models"]:
                    model_type = model["model_type"]
                    if model_type not in models_by_type:
                        models_by_type[model_type] = 0
                    models_by_type[model_type] += 1
            
            # 按提供商统计模型
            models_by_provider = {}
            for provider_id, provider_data in SUPPORTED_PROVIDERS.items():
                models_by_provider[provider_id] = {
                    "name": provider_data["name"],
                    "total_models": len(provider_data["models"]),
                    "enabled_models": len(providers_db.get(provider_id, {}).get("enabled_models", [])),
                    "configured": provider_id in providers_db
                }
            
            return {
                "total_providers": total_providers,
                "configured_providers": configured_providers,
                "total_models": total_models,
                "enabled_models": enabled_models,
                "models_by_type": models_by_type,
                "models_by_provider": models_by_provider,
                "system_defaults": len(self.system_defaults_db),
                "user_preferences": len(self.user_preferences_db),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取模型统计信息失败: {e}")
            raise


# 全局模型管理器实例
model_manager = ModelManager()