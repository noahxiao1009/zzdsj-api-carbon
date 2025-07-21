"""
配置加载工具类
用于加载YAML配置文件，特别是硅基流动模型配置
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import os

logger = logging.getLogger(__name__)


class ConfigLoader:
    """配置加载器"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self._configs = {}
    
    def load_yaml_config(self, config_name: str) -> Optional[Dict[str, Any]]:
        """
        加载YAML配置文件
        
        Args:
            config_name: 配置文件名（不含扩展名）
            
        Returns:
            配置字典或None
        """
        if config_name in self._configs:
            return self._configs[config_name]
        
        config_file = self.config_dir / f"{config_name}.yaml"
        
        try:
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    self._configs[config_name] = config
                    logger.info(f"Loaded config: {config_file}")
                    return config
            else:
                logger.warning(f"Config file not found: {config_file}")
                return None
        except Exception as e:
            logger.error(f"Failed to load config {config_file}: {e}")
            return None
    
    def get_siliconflow_config(self) -> Optional[Dict[str, Any]]:
        """获取硅基流动配置"""
        return self.load_yaml_config("siliconflow_config")
    
    def get_embedding_models(self) -> Dict[str, Any]:
        """
        从配置中获取嵌入模型信息，按提供商分组
        
        Returns:
            按提供商分组的嵌入模型配置字典
        """
        config = self.get_siliconflow_config()
        if not config:
            return self._get_default_models()
        
        # 按提供商分组的模型数据
        providers = {
            "siliconflow": {
                "name": "硅基流动",
                "display_name": "SiliconFlow",
                "description": "硅基流动提供的高性能AI模型服务",
                "models": [],
                "is_configured": True,
                "api_base": "https://api.siliconflow.cn/v1"
            },
            "openai": {
                "name": "OpenAI",
                "display_name": "OpenAI",
                "description": "OpenAI官方嵌入模型服务",
                "models": [],
                "is_configured": False,
                "api_base": "https://api.openai.com/v1"
            },
            "azure_openai": {
                "name": "Azure OpenAI",
                "display_name": "Azure OpenAI",
                "description": "微软Azure平台的OpenAI服务",
                "models": [],
                "is_configured": False,
                "api_base": ""
            },
            "huggingface": {
                "name": "HuggingFace",
                "display_name": "HuggingFace",
                "description": "HuggingFace开源模型社区",
                "models": [],
                "is_configured": False,
                "api_base": "https://api-inference.huggingface.co"
            }
        }
        
        # 从硅基流动配置中提取嵌入模型
        embedding_config = config.get("embedding_config", {})
        if embedding_config:
            providers["siliconflow"]["models"].append({
                "model_name": embedding_config.get("model", "Qwen/Qwen3-Embedding-8B"),
                "dimension": embedding_config.get("dimension", 8192),
                "description": "Qwen3 高性能嵌入模型，支持中英文语义理解",
                "max_input_length": embedding_config.get("max_input_length", 2048),
                "batch_size": embedding_config.get("batch_size", 100),
                "is_default": True
            })
        
        # 添加OpenAI模型
        providers["openai"]["models"].extend([
            {
                "model_name": "text-embedding-3-small",
                "dimension": 1536,
                "description": "OpenAI 最新小型嵌入模型，性价比高",
                "max_input_length": 8191,
                "is_default": True
            },
            {
                "model_name": "text-embedding-3-large", 
                "dimension": 3072,
                "description": "OpenAI 最新大型嵌入模型，精度更高",
                "max_input_length": 8191,
                "is_default": False
            },
            {
                "model_name": "text-embedding-ada-002",
                "dimension": 1536,
                "description": "OpenAI 经典嵌入模型",
                "max_input_length": 8191,
                "is_default": False
            }
        ])
        
        # 添加Azure OpenAI模型
        providers["azure_openai"]["models"].extend([
            {
                "model_name": "text-embedding-ada-002",
                "dimension": 1536,
                "description": "Azure OpenAI 嵌入模型",
                "max_input_length": 8191,
                "is_default": True
            }
        ])
        
        # 添加HuggingFace模型
        providers["huggingface"]["models"].extend([
            {
                "model_name": "sentence-transformers/all-MiniLM-L6-v2",
                "dimension": 384,
                "description": "轻量级多语言嵌入模型",
                "max_input_length": 256,
                "is_default": True
            },
            {
                "model_name": "sentence-transformers/all-mpnet-base-v2",
                "dimension": 768,
                "description": "高质量英文嵌入模型",
                "max_input_length": 384,
                "is_default": False
            }
        ])
        
        # 统计信息
        total_models = sum(len(provider["models"]) for provider in providers.values())
        provider_counts = {pid: len(provider["models"]) for pid, provider in providers.items()}
        
        return {
            "success": True,
            "providers": providers,
            "total_providers": len(providers),
            "total_models": total_models,
            "provider_counts": provider_counts,
            "config_source": "siliconflow_config.yaml"
        }
    
    def _get_default_models(self) -> Dict[str, Any]:
        """获取默认模型配置（当配置文件不存在时）"""
        models = [
            {
                "provider": "openai",
                "model_name": "text-embedding-3-small",
                "dimension": 1536,
                "description": "OpenAI 最新小型嵌入模型"
            },
            {
                "provider": "openai", 
                "model_name": "text-embedding-3-large",
                "dimension": 3072,
                "description": "OpenAI 最新大型嵌入模型"
            },
            {
                "provider": "azure_openai",
                "model_name": "text-embedding-ada-002",
                "dimension": 1536,
                "description": "Azure OpenAI 嵌入模型"
            },
            {
                "provider": "huggingface",
                "model_name": "sentence-transformers/all-MiniLM-L6-v2",
                "dimension": 384,
                "description": "HuggingFace 轻量级嵌入模型"
            }
        ]
        
        provider_counts = {}
        for model in models:
            provider = model["provider"]
            provider_counts[provider] = provider_counts.get(provider, 0) + 1
        
        return {
            "success": True,
            "models": models,
            "total": len(models),
            "provider_counts": provider_counts,
            "config_source": "default"
        }


# 全局配置加载器实例
_config_loader = None

def get_config_loader() -> ConfigLoader:
    """获取配置加载器实例"""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
    return _config_loader
