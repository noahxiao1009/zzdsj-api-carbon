"""
微服务SDK配置管理
统一管理服务调用的配置参数
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class Environment(str, Enum):
    """环境枚举"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class ServiceConfig:
    """单个服务配置"""
    name: str
    base_url: Optional[str] = None
    timeout: int = 30
    retry_times: int = 3
    circuit_breaker_enabled: bool = True
    health_check_path: str = "/health"
    api_key: Optional[str] = None
    custom_headers: Dict[str, str] = field(default_factory=dict)


@dataclass
class GlobalConfig:
    """全局配置"""
    environment: Environment = Environment.DEVELOPMENT
    gateway_url: str = "http://localhost:8080"
    messaging_url: str = "http://localhost:8008"
    
    # 默认调用配置
    default_timeout: int = 30
    default_retry_times: int = 3
    default_retry_delay: float = 1.0
    
    # 熔断器配置
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: int = 60
    
    # 缓存配置
    service_cache_ttl: int = 60
    
    # 监控配置
    metrics_enabled: bool = True
    logging_enabled: bool = True
    
    # 服务配置
    services: Dict[str, ServiceConfig] = field(default_factory=dict)
    
    def get_service_config(self, service_name: str) -> ServiceConfig:
        """获取服务配置"""
        return self.services.get(service_name, ServiceConfig(name=service_name))


class ConfigManager:
    """配置管理器"""
    
    def __init__(self):
        self.config: Optional[GlobalConfig] = None
        self._load_config()
    
    def _load_config(self):
        """加载配置"""
        # 从环境变量加载
        env = os.getenv("MICROSERVICE_ENV", "development")
        
        self.config = GlobalConfig(
            environment=Environment(env),
            gateway_url=os.getenv("GATEWAY_URL", "http://localhost:8080"),
            messaging_url=os.getenv("MESSAGING_URL", "http://localhost:8008"),
            
            default_timeout=int(os.getenv("DEFAULT_TIMEOUT", "30")),
            default_retry_times=int(os.getenv("DEFAULT_RETRY_TIMES", "3")),
            default_retry_delay=float(os.getenv("DEFAULT_RETRY_DELAY", "1.0")),
            
            circuit_breaker_failure_threshold=int(os.getenv("CB_FAILURE_THRESHOLD", "5")),
            circuit_breaker_recovery_timeout=int(os.getenv("CB_RECOVERY_TIMEOUT", "60")),
            
            service_cache_ttl=int(os.getenv("SERVICE_CACHE_TTL", "60")),
            
            metrics_enabled=os.getenv("METRICS_ENABLED", "true").lower() == "true",
            logging_enabled=os.getenv("LOGGING_ENABLED", "true").lower() == "true"
        )
        
        # 加载服务特定配置
        self._load_service_configs()
    
    def _load_service_configs(self):
        """加载服务特定配置"""
        service_names = [
            "gateway-service", "database-service", "messaging-service",
            "agent-service", "knowledge-service", "model-service",
            "base-service", "system-service", "chat-service",
            "scheduler-service", "knowledge-graph-service", "mcp-service"
        ]
        
        for service_name in service_names:
            service_config = ServiceConfig(
                name=service_name,
                base_url=os.getenv(f"{service_name.upper().replace('-', '_')}_URL"),
                timeout=int(os.getenv(f"{service_name.upper().replace('-', '_')}_TIMEOUT", "30")),
                retry_times=int(os.getenv(f"{service_name.upper().replace('-', '_')}_RETRY", "3")),
                circuit_breaker_enabled=os.getenv(
                    f"{service_name.upper().replace('-', '_')}_CIRCUIT_BREAKER", 
                    "true"
                ).lower() == "true",
                api_key=os.getenv(f"{service_name.upper().replace('-', '_')}_API_KEY")
            )
            self.config.services[service_name] = service_config
    
    def get_config(self) -> GlobalConfig:
        """获取全局配置"""
        return self.config
    
    def get_service_config(self, service_name: str) -> ServiceConfig:
        """获取服务配置"""
        return self.config.get_service_config(service_name)
    
    def update_service_config(self, service_name: str, **kwargs):
        """更新服务配置"""
        if service_name not in self.config.services:
            self.config.services[service_name] = ServiceConfig(name=service_name)
        
        service_config = self.config.services[service_name]
        for key, value in kwargs.items():
            if hasattr(service_config, key):
                setattr(service_config, key, value)


# 全局配置管理器实例
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """获取配置管理器实例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_global_config() -> GlobalConfig:
    """获取全局配置"""
    return get_config_manager().get_config()


def get_service_config(service_name: str) -> ServiceConfig:
    """获取服务配置"""
    return get_config_manager().get_service_config(service_name) 