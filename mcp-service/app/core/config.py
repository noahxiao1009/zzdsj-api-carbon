"""
MCP Service 配置管理
"""

import os
from typing import List, Optional, Dict, Any
from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """MCP服务配置"""
    
    # 服务基础配置
    service_name: str = Field(default="mcp-service", env="SERVICE_NAME")
    service_version: str = Field(default="1.0.0", env="SERVICE_VERSION")
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=True, env="DEBUG")
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8008, env="PORT")
    
    # 数据库配置
    database_url: str = Field(
        default="postgresql://username:password@localhost:5432/mcp_service_db",
        env="DATABASE_URL"
    )
    db_echo: bool = Field(default=False, env="DB_ECHO")
    db_pool_size: int = Field(default=10, env="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=20, env="DB_MAX_OVERFLOW")
    
    # Redis配置
    redis_url: str = Field(default="redis://localhost:6379/8", env="REDIS_URL")
    redis_password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    redis_max_connections: int = Field(default=10, env="REDIS_MAX_CONNECTIONS")
    
    # FastMCP框架配置
    fastmcp_name: str = Field(default="ZZDSJ MCP Service", env="FASTMCP_NAME")
    fastmcp_description: str = Field(
        default="智政知识库MCP服务 - 提供统一的MCP工具管理和调用",
        env="FASTMCP_DESCRIPTION"
    )
    fastmcp_version: str = Field(default="2.0.0", env="FASTMCP_VERSION")
    
    # Docker网络配置
    docker_network: str = Field(default="mcp-network", env="DOCKER_NETWORK")
    docker_subnet: str = Field(default="172.28.0.0/16", env="DOCKER_SUBNET")
    docker_compose_path: str = Field(
        default="/app/deployments", 
        env="DOCKER_COMPOSE_PATH"
    )
    
    # 网关服务配置
    gateway_url: str = Field(default="http://localhost:8000", env="GATEWAY_URL")
    gateway_api_key: Optional[str] = Field(default=None, env="GATEWAY_API_KEY")
    gateway_service_id: str = Field(default="mcp-service", env="GATEWAY_SERVICE_ID")
    gateway_health_check_interval: int = Field(default=30, env="GATEWAY_HEALTH_CHECK_INTERVAL")
    
    # 安全配置
    secret_key: str = Field(
        default="your_super_secret_key_here_change_in_production",
        env="SECRET_KEY"
    )
    allowed_hosts: List[str] = Field(
        default=["localhost", "127.0.0.1", "*.mcp-service.local"],
        env="ALLOWED_HOSTS"
    )
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        env="CORS_ORIGINS"
    )
    
    # 日志配置
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="json", env="LOG_FORMAT")
    log_file_path: str = Field(default="/app/logs/mcp-service.log", env="LOG_FILE_PATH")
    log_max_size: str = Field(default="100MB", env="LOG_MAX_SIZE")
    log_backup_count: int = Field(default=5, env="LOG_BACKUP_COUNT")
    
    # MCP服务管理配置
    mcp_services_config_path: str = Field(
        default="/app/config/mcp_services.yaml",
        env="MCP_SERVICES_CONFIG_PATH"
    )
    mcp_tools_registry_path: str = Field(
        default="/app/data/tools_registry.json",
        env="MCP_TOOLS_REGISTRY_PATH"
    )
    mcp_default_timeout: int = Field(default=30, env="MCP_DEFAULT_TIMEOUT")
    mcp_max_retries: int = Field(default=3, env="MCP_MAX_RETRIES")
    
    # 外部服务配置
    external_api_timeout: int = Field(default=30, env="EXTERNAL_API_TIMEOUT")
    external_api_retries: int = Field(default=3, env="EXTERNAL_API_RETRIES")
    external_api_backoff_factor: float = Field(default=2.0, env="EXTERNAL_API_BACKOFF_FACTOR")
    
    # 监控和指标
    metrics_enabled: bool = Field(default=True, env="METRICS_ENABLED")
    metrics_path: str = Field(default="/metrics", env="METRICS_PATH")
    health_check_timeout: int = Field(default=10, env="HEALTH_CHECK_TIMEOUT")
    
    # WebSocket配置（预留）
    websocket_enabled: bool = Field(default=False, env="WEBSOCKET_ENABLED")
    websocket_path: str = Field(default="/ws", env="WEBSOCKET_PATH")
    
    # 性能配置
    max_concurrent_requests: int = Field(default=100, env="MAX_CONCURRENT_REQUESTS")
    request_rate_limit: int = Field(default=1000, env="REQUEST_RATE_LIMIT")
    cache_ttl_seconds: int = Field(default=3600, env="CACHE_TTL_SECONDS")
    
    # 开发工具配置
    enable_docs: bool = Field(default=True, env="ENABLE_DOCS")
    enable_redoc: bool = Field(default=True, env="ENABLE_REDOC")
    enable_openapi: bool = Field(default=True, env="ENABLE_OPENAPI")
    
    # MCP工具默认配置
    default_tool_categories: List[str] = Field(
        default=[
            "system", "database", "file", "search", 
            "knowledge", "agent", "utility", "custom"
        ],
        env="DEFAULT_TOOL_CATEGORIES"
    )
    
    # 服务发现配置
    nacos_server: str = Field(default="localhost:8848", env="NACOS_SERVER")
    nacos_namespace: str = Field(default="public", env="NACOS_NAMESPACE")
    nacos_group: str = Field(default="DEFAULT_GROUP", env="NACOS_GROUP")
    nacos_username: Optional[str] = Field(default=None, env="NACOS_USERNAME")
    nacos_password: Optional[str] = Field(default=None, env="NACOS_PASSWORD")
    
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