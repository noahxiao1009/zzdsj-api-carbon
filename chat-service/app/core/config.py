"""
Chat Service 配置管理
基于原始项目的配置管理模式
"""

import os
from typing import List, Optional, Dict, Any
from pydantic import BaseSettings, Field
from functools import lru_cache


class Settings(BaseSettings):
    """Chat Service 配置"""
    
    # 服务基础配置
    service_name: str = "chat-service"
    version: str = "1.0.0"
    debug: bool = Field(default=False, env="DEBUG")
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8001, env="PORT")
    
    # 数据库配置
    database_url: str = Field(..., env="DATABASE_URL")
    db_echo: bool = Field(default=False, env="DB_ECHO")
    db_pool_size: int = Field(default=10, env="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=20, env="DB_MAX_OVERFLOW")
    db_pool_recycle: int = Field(default=3600, env="DB_POOL_RECYCLE")
    
    # Redis配置
    redis_url: str = Field(..., env="REDIS_URL")
    redis_password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    redis_db: int = Field(default=0, env="REDIS_DB")
    
    # Agno框架配置
    agno_enabled: bool = Field(default=True, env="AGNO_ENABLED")
    default_model: str = Field(default="gpt-3.5-turbo", env="DEFAULT_MODEL")
    agno_api_key: Optional[str] = Field(default=None, env="AGNO_API_KEY")
    agno_api_base: Optional[str] = Field(default=None, env="AGNO_API_BASE")
    agno_timeout: int = Field(default=60, env="AGNO_TIMEOUT")
    
    # 语音服务配置
    voice_enabled: bool = Field(default=True, env="VOICE_ENABLED")
    tts_provider: str = Field(default="azure", env="TTS_PROVIDER")
    stt_provider: str = Field(default="azure", env="STT_PROVIDER")
    azure_speech_key: Optional[str] = Field(default=None, env="AZURE_SPEECH_KEY")
    azure_speech_region: str = Field(default="eastus", env="AZURE_SPEECH_REGION")
    
    # 网关服务配置
    gateway_url: str = Field(..., env="GATEWAY_URL")
    gateway_token: Optional[str] = Field(default=None, env="GATEWAY_TOKEN")
    
    # 安全配置
    cors_origins: List[str] = Field(
        default=["*"], 
        env="CORS_ORIGINS"
    )
    allowed_hosts: List[str] = Field(
        default=["*"], 
        env="ALLOWED_HOSTS"
    )
    secret_key: str = Field(..., env="SECRET_KEY")
    
    # 会话配置
    session_timeout: int = Field(default=86400, env="SESSION_TIMEOUT")  # 24小时
    max_message_length: int = Field(default=10000, env="MAX_MESSAGE_LENGTH")
    max_history_length: int = Field(default=100, env="MAX_HISTORY_LENGTH")
    
    # 监控和日志配置
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    enable_metrics: bool = Field(default=True, env="ENABLE_METRICS")
    metrics_port: int = Field(default=9001, env="METRICS_PORT")
    
    # 文件上传配置
    upload_max_size: int = Field(default=10485760, env="UPLOAD_MAX_SIZE")  # 10MB
    upload_allowed_types: List[str] = Field(
        default=["audio/wav", "audio/mp3", "audio/m4a"], 
        env="UPLOAD_ALLOWED_TYPES"
    )
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """获取配置实例（缓存）"""
    return Settings()


# 全局配置实例
settings = get_settings()


def get_database_url() -> str:
    """获取数据库连接URL"""
    return settings.database_url


def get_redis_url() -> str:
    """获取Redis连接URL"""
    return settings.redis_url


def is_development() -> bool:
    """是否为开发环境"""
    return settings.debug


def get_cors_origins() -> List[str]:
    """获取CORS允许的源"""
    if isinstance(settings.cors_origins, str):
        return [origin.strip() for origin in settings.cors_origins.split(",")]
    return settings.cors_origins


def get_allowed_hosts() -> List[str]:
    """获取允许的主机"""
    if isinstance(settings.allowed_hosts, str):
        return [host.strip() for host in settings.allowed_hosts.split(",")]
    return settings.allowed_hosts 