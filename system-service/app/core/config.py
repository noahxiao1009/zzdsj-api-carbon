"""
System Service 配置管理
"""

import os
from typing import List, Optional, Dict, Any
from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """系统服务配置"""
    
    # 服务基础配置
    service_name: str = Field(default="system-service", env="SERVICE_NAME")
    service_version: str = Field(default="1.0.0", env="SERVICE_VERSION")
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=True, env="DEBUG")
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8005, env="PORT")
    
    # 数据库配置
    database_url: str = Field(
        default="postgresql://username:password@localhost:5432/system_service_db",
        env="DATABASE_URL"
    )
    db_echo: bool = Field(default=False, env="DB_ECHO")
    db_pool_size: int = Field(default=10, env="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=20, env="DB_MAX_OVERFLOW")
    
    # Redis配置
    redis_url: str = Field(default="redis://localhost:6379/5", env="REDIS_URL")
    redis_password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    redis_max_connections: int = Field(default=10, env="REDIS_MAX_CONNECTIONS")
    
    # MinIO存储配置
    minio_endpoint: str = Field(default="localhost:9000", env="MINIO_ENDPOINT")
    minio_access_key: str = Field(default="minioadmin", env="MINIO_ACCESS_KEY")
    minio_secret_key: str = Field(default="minioadmin", env="MINIO_SECRET_KEY")
    minio_secure: bool = Field(default=False, env="MINIO_SECURE")
    minio_bucket_name: str = Field(default="system-files", env="MINIO_BUCKET_NAME")
    
    # 文件上传配置
    upload_max_size: int = Field(default=100 * 1024 * 1024, env="UPLOAD_MAX_SIZE")  # 100MB
    upload_allowed_types: List[str] = Field(
        default=[
            "application/pdf", "text/plain", "text/markdown", "text/html", 
            "application/json", "text/csv", "image/jpeg", "image/png", 
            "image/gif", "audio/wav", "audio/mp3", "video/mp4"
        ],
        env="UPLOAD_ALLOWED_TYPES"
    )
    upload_temp_dir: str = Field(default="/tmp/uploads", env="UPLOAD_TEMP_DIR")
    
    # 敏感词过滤配置
    sensitive_words_enabled: bool = Field(default=True, env="SENSITIVE_WORDS_ENABLED")
    sensitive_words_mode: str = Field(default="local", env="SENSITIVE_WORDS_MODE")
    sensitive_words_cache_ttl: int = Field(default=3600, env="SENSITIVE_WORDS_CACHE_TTL")
    
    # 政策搜索配置
    policy_search_enabled: bool = Field(default=True, env="POLICY_SEARCH_ENABLED")
    policy_search_timeout: int = Field(default=30, env="POLICY_SEARCH_TIMEOUT")
    policy_search_cache_ttl: int = Field(default=7200, env="POLICY_SEARCH_CACHE_TTL")
    
    # 网关服务配置
    gateway_url: str = Field(default="http://localhost:8000", env="GATEWAY_URL")
    gateway_service_id: str = Field(default="system-service", env="GATEWAY_SERVICE_ID")
    
    # 安全配置
    secret_key: str = Field(default="system_service_secret_key", env="SECRET_KEY")
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        env="CORS_ORIGINS"
    )
    
    # 日志配置
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="json", env="LOG_FORMAT")
    log_file_path: str = Field(default="/app/logs/system-service.log", env="LOG_FILE_PATH")
    
    # 监控配置
    metrics_enabled: bool = Field(default=True, env="METRICS_ENABLED")
    health_check_timeout: int = Field(default=10, env="HEALTH_CHECK_TIMEOUT")
    
    # 服务发现配置
    nacos_server: str = Field(default="localhost:8848", env="NACOS_SERVER")
    nacos_namespace: str = Field(default="public", env="NACOS_NAMESPACE")
    nacos_group: str = Field(default="DEFAULT_GROUP", env="NACOS_GROUP")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# 创建全局配置实例
settings = Settings()


def get_settings() -> Settings:
    """获取配置实例"""
    return settings


# 导出常用配置
__all__ = ["settings", "get_settings", "Settings"] 