"""
智能体服务配置
基于原ZZDSJ项目的配置系统，适配智能体服务需求
集成ServiceClient SDK配置
"""

import os
from typing import List, Optional, Dict, Any
from pydantic_settings import BaseSettings
from pydantic import Field, validator
from pathlib import Path

class Settings(BaseSettings):
    """智能体服务配置类"""
    
    # 基础配置
    APP_NAME: str = "Agent Service"
    VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False, env="DEBUG")
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8081, env="PORT")
    WORKERS: int = Field(default=1, env="WORKERS")
    
    # 日志配置
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FORMAT: str = Field(default="json", env="LOG_FORMAT")
    
    # CORS配置
    ALLOWED_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        env="ALLOWED_ORIGINS"
    )
    
    # 数据库配置 (连接到基础服务)
    DATABASE_URL: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/agent_db",
        env="DATABASE_URL"
    )
    
    # Redis配置 (用于缓存和会话)
    REDIS_URL: str = Field(
        default="redis://localhost:6379/1",
        env="REDIS_URL"
    )
    
    # ==================== ServiceClient SDK 配置 ====================
    
    # 网关服务配置
    GATEWAY_URL: str = Field(
        default="http://localhost:8080",
        env="GATEWAY_URL"
    )
    
    # 服务超时配置（秒）
    MODEL_SERVICE_TIMEOUT: int = Field(default=120, env="MODEL_SERVICE_TIMEOUT")
    BASE_SERVICE_TIMEOUT: int = Field(default=10, env="BASE_SERVICE_TIMEOUT")
    KNOWLEDGE_SERVICE_TIMEOUT: int = Field(default=30, env="KNOWLEDGE_SERVICE_TIMEOUT")
    DATABASE_SERVICE_TIMEOUT: int = Field(default=15, env="DATABASE_SERVICE_TIMEOUT")
    DEFAULT_SERVICE_TIMEOUT: int = Field(default=30, env="DEFAULT_SERVICE_TIMEOUT")
    
    # 重试配置
    DEFAULT_RETRY_TIMES: int = Field(default=3, env="DEFAULT_RETRY_TIMES")
    MODEL_SERVICE_RETRY_TIMES: int = Field(default=2, env="MODEL_SERVICE_RETRY_TIMES")
    MAX_RETRY_DELAY: int = Field(default=60, env="MAX_RETRY_DELAY")
    
    # 熔断器配置
    CIRCUIT_BREAKER_ENABLED: bool = Field(default=True, env="CIRCUIT_BREAKER_ENABLED")
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = Field(default=5, env="CIRCUIT_BREAKER_FAILURE_THRESHOLD")
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT: int = Field(default=60, env="CIRCUIT_BREAKER_RECOVERY_TIMEOUT")
    
    # 连接池配置
    CONNECTION_POOL_SIZE: int = Field(default=100, env="CONNECTION_POOL_SIZE")
    MAX_CONNECTIONS_PER_HOST: int = Field(default=10, env="MAX_CONNECTIONS_PER_HOST")
    
    # 监控和指标配置
    ENABLE_SERVICE_METRICS: bool = Field(default=True, env="ENABLE_SERVICE_METRICS")
    METRICS_RETENTION_HOURS: int = Field(default=24, env="METRICS_RETENTION_HOURS")
    
    # 消息队列配置
    RABBITMQ_URL: str = Field(
        default="amqp://localhost:5672",
        env="RABBITMQ_URL"
    )
    ENABLE_EVENT_PUBLISHING: bool = Field(default=True, env="ENABLE_EVENT_PUBLISHING")
    
    # 缓存配置
    ENABLE_LOCAL_CACHE: bool = Field(default=True, env="ENABLE_LOCAL_CACHE")
    CACHE_TTL_SECONDS: int = Field(default=300, env="CACHE_TTL_SECONDS")
    MAX_CACHE_SIZE: int = Field(default=1000, env="MAX_CACHE_SIZE")
    
    # 服务发现配置
    SERVICE_REGISTRY_URL: str = Field(
        default="http://localhost:8500",  # Consul地址
        env="SERVICE_REGISTRY_URL"
    )
    ENABLE_SERVICE_DISCOVERY: bool = Field(default=False, env="ENABLE_SERVICE_DISCOVERY")
    SERVICE_HEALTH_CHECK_INTERVAL: int = Field(default=30, env="SERVICE_HEALTH_CHECK_INTERVAL")
    
    # ==================== Agno框架配置 ====================
    
    AGNO_CONFIG: Dict[str, Any] = {
        "default_model_provider": "openai",
        "max_agents_per_user": 50,
        "max_team_size": 10,
        "execution_timeout": 300,
        "enable_monitoring": True,
        "enable_caching": True
    }
    
    # ==================== 模型配置 ====================
    
    OPENAI_API_KEY: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    ZHIPU_API_KEY: Optional[str] = Field(default=None, env="ZHIPU_API_KEY")
    MOONSHOT_API_KEY: Optional[str] = Field(default=None, env="MOONSHOT_API_KEY")
    
    # ==================== 工具配置 ====================
    
    ENABLE_WEB_SEARCH: bool = Field(default=True, env="ENABLE_WEB_SEARCH")
    ENABLE_CODE_EXECUTION: bool = Field(default=False, env="ENABLE_CODE_EXECUTION")
    ENABLE_FILE_OPERATIONS: bool = Field(default=True, env="ENABLE_FILE_OPERATIONS")
    
    # ==================== 安全配置 ====================
    
    SECRET_KEY: str = Field(default="your-secret-key", env="SECRET_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    
    # ==================== 存储配置 ====================
    
    UPLOAD_DIR: str = Field(default="./uploads", env="UPLOAD_DIR")
    MAX_FILE_SIZE: int = Field(default=10 * 1024 * 1024, env="MAX_FILE_SIZE")  # 10MB
    
    # ==================== 监控配置 ====================
    
    ENABLE_METRICS: bool = Field(default=True, env="ENABLE_METRICS")
    METRICS_PORT: int = Field(default=9090, env="METRICS_PORT")
    
    # ==================== 外部服务配置（向后兼容） ====================
    
    GATEWAY_SERVICE_URL: str = Field(
        default="http://localhost:8080",
        env="GATEWAY_SERVICE_URL"
    )
    
    KNOWLEDGE_SERVICE_URL: str = Field(
        default="http://localhost:8082", 
        env="KNOWLEDGE_SERVICE_URL"
    )
    
    MODEL_SERVICE_URL: str = Field(
        default="http://localhost:8083",
        env="MODEL_SERVICE_URL"
    )
    
    BASE_SERVICE_URL: str = Field(
        default="http://localhost:8084",
        env="BASE_SERVICE_URL"
    )

    # ==================== 验证器 ====================

    @validator('ALLOWED_ORIGINS', pre=True)
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @validator('UPLOAD_DIR', pre=True)
    def create_upload_dir(cls, v):
        upload_path = Path(v)
        upload_path.mkdir(parents=True, exist_ok=True)
        return str(upload_path)
    
    @validator('CONNECTION_POOL_SIZE')
    def validate_pool_size(cls, v):
        if v < 1:
            raise ValueError("连接池大小必须大于0")
        return v
    
    @validator('DEFAULT_RETRY_TIMES')
    def validate_retry_times(cls, v):
        if v < 0:
            raise ValueError("重试次数不能为负数")
        return v

    # ==================== ServiceClient SDK配置方法 ====================
    
    def get_service_config(self) -> Dict[str, Any]:
        """获取ServiceClient SDK配置"""
        return {
            "gateway_url": self.GATEWAY_URL,
            "default_timeout": self.DEFAULT_SERVICE_TIMEOUT,
            "default_retry_times": self.DEFAULT_RETRY_TIMES,
            "max_retry_delay": self.MAX_RETRY_DELAY,
            "circuit_breaker_enabled": self.CIRCUIT_BREAKER_ENABLED,
            "circuit_breaker_failure_threshold": self.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
            "circuit_breaker_recovery_timeout": self.CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
            "connection_pool_size": self.CONNECTION_POOL_SIZE,
            "max_connections_per_host": self.MAX_CONNECTIONS_PER_HOST,
            "enable_metrics": self.ENABLE_SERVICE_METRICS,
            "enable_cache": self.ENABLE_LOCAL_CACHE,
            "cache_ttl": self.CACHE_TTL_SECONDS,
            "max_cache_size": self.MAX_CACHE_SIZE,
            "rabbitmq_url": self.RABBITMQ_URL,
            "enable_events": self.ENABLE_EVENT_PUBLISHING
        }
    
    def get_service_specific_config(self, service_name: str) -> Dict[str, Any]:
        """获取特定服务的配置"""
        base_config = self.get_service_config()
        
        # 服务特定超时配置
        timeout_map = {
            "model-service": self.MODEL_SERVICE_TIMEOUT,
            "base-service": self.BASE_SERVICE_TIMEOUT,
            "knowledge-service": self.KNOWLEDGE_SERVICE_TIMEOUT,
            "database-service": self.DATABASE_SERVICE_TIMEOUT
        }
        
        # 服务特定重试配置
        retry_map = {
            "model-service": self.MODEL_SERVICE_RETRY_TIMES,
        }
        
        if service_name in timeout_map:
            base_config["timeout"] = timeout_map[service_name]
        
        if service_name in retry_map:
            base_config["retry_times"] = retry_map[service_name]
        
        return base_config
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

# 全局配置实例
settings = Settings()

async def init_settings():
    """初始化配置"""
    # 创建必要的目录
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    
    # 验证必要的API密钥
    api_keys = {
        "OpenAI": settings.OPENAI_API_KEY,
        "Anthropic": settings.ANTHROPIC_API_KEY, 
        "ZhiPu": settings.ZHIPU_API_KEY,
        "Moonshot": settings.MOONSHOT_API_KEY
    }
    
    available_providers = [name for name, key in api_keys.items() if key]
    
    if not available_providers:
        print("警告: 未配置任何AI模型API密钥")
    else:
        print(f"可用的AI模型提供商: {', '.join(available_providers)}")
    
    # 验证ServiceClient配置
    service_config = settings.get_service_config()
    print(f"ServiceClient配置: 网关地址={service_config['gateway_url']}")
    print(f"熔断器: {'启用' if service_config['circuit_breaker_enabled'] else '禁用'}")
    print(f"事件发布: {'启用' if service_config['enable_events'] else '禁用'}")

def get_settings() -> Settings:
    """获取配置实例"""
    return settings
