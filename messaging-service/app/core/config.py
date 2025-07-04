"""
消息服务配置管理
"""

import os
from typing import List, Optional
from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """配置设置"""
    
    # 基础服务配置
    SERVICE_NAME: str = "messaging-service"
    VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False, env="DEBUG")
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8008, env="PORT")
    
    # 数据库配置
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/messaging_db",
        env="DATABASE_URL"
    )
    
    # Redis配置
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        env="REDIS_URL"
    )
    
    # RabbitMQ配置
    RABBITMQ_URL: str = Field(
        default="amqp://guest:guest@localhost:5672/",
        env="RABBITMQ_URL"
    )
    
    # WebSocket配置
    WEBSOCKET_MAX_CONNECTIONS: int = Field(default=1000, env="WEBSOCKET_MAX_CONNECTIONS")
    WEBSOCKET_PING_INTERVAL: int = Field(default=30, env="WEBSOCKET_PING_INTERVAL")
    WEBSOCKET_PING_TIMEOUT: int = Field(default=10, env="WEBSOCKET_PING_TIMEOUT")
    
    # 消息队列配置
    MESSAGE_QUEUE_EXCHANGE: str = Field(default="microservices", env="MESSAGE_QUEUE_EXCHANGE")
    MESSAGE_QUEUE_ROUTING_KEY: str = Field(default="messaging.events", env="MESSAGE_QUEUE_ROUTING_KEY")
    MESSAGE_BATCH_SIZE: int = Field(default=100, env="MESSAGE_BATCH_SIZE")
    MESSAGE_TIMEOUT: int = Field(default=30, env="MESSAGE_TIMEOUT")
    
    # 服务发现配置
    SERVICE_DISCOVERY_URL: str = Field(
        default="http://localhost:8500",  # Consul
        env="SERVICE_DISCOVERY_URL"
    )
    SERVICE_REGISTRY_TIMEOUT: int = Field(default=30, env="SERVICE_REGISTRY_TIMEOUT")
    HEALTH_CHECK_INTERVAL: int = Field(default=60, env="HEALTH_CHECK_INTERVAL")
    
    # 网关服务配置
    GATEWAY_URL: str = Field(
        default="http://localhost:8080",
        env="GATEWAY_URL"
    )
    
    # 认证配置
    JWT_SECRET_KEY: str = Field(
        default="your-secret-key-change-in-production",
        env="JWT_SECRET_KEY"
    )
    JWT_ALGORITHM: str = Field(default="HS256", env="JWT_ALGORITHM")
    JWT_EXPIRE_MINUTES: int = Field(default=1440, env="JWT_EXPIRE_MINUTES")  # 24小时
    
    # 日志配置
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FORMAT: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        env="LOG_FORMAT"
    )
    
    # 监控配置
    METRICS_ENABLED: bool = Field(default=True, env="METRICS_ENABLED")
    METRICS_PORT: int = Field(default=9090, env="METRICS_PORT")
    
    # 事件处理配置
    EVENT_BATCH_SIZE: int = Field(default=50, env="EVENT_BATCH_SIZE")
    EVENT_RETRY_ATTEMPTS: int = Field(default=3, env="EVENT_RETRY_ATTEMPTS")
    EVENT_RETRY_DELAY: int = Field(default=5, env="EVENT_RETRY_DELAY")
    
    # 微服务地址配置
    AGENT_SERVICE_URL: str = Field(default="http://localhost:8001", env="AGENT_SERVICE_URL")
    KNOWLEDGE_SERVICE_URL: str = Field(default="http://localhost:8002", env="KNOWLEDGE_SERVICE_URL")
    MODEL_SERVICE_URL: str = Field(default="http://localhost:8004", env="MODEL_SERVICE_URL")
    SYSTEM_SERVICE_URL: str = Field(default="http://localhost:8005", env="SYSTEM_SERVICE_URL")
    CHAT_SERVICE_URL: str = Field(default="http://localhost:8006", env="CHAT_SERVICE_URL")
    
    # 安全配置
    ALLOWED_HOSTS: List[str] = Field(
        default=["localhost", "127.0.0.1", "*"],
        env="ALLOWED_HOSTS"
    )
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        env="CORS_ORIGINS"
    )
    
    # 性能配置
    MAX_WORKERS: int = Field(default=4, env="MAX_WORKERS")
    CONNECTION_POOL_SIZE: int = Field(default=20, env="CONNECTION_POOL_SIZE")
    REQUEST_TIMEOUT: int = Field(default=30, env="REQUEST_TIMEOUT")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# 创建全局设置实例
settings = Settings()


def get_database_url() -> str:
    """获取数据库连接URL"""
    return settings.DATABASE_URL


def get_redis_url() -> str:
    """获取Redis连接URL"""
    return settings.REDIS_URL


def get_rabbitmq_url() -> str:
    """获取RabbitMQ连接URL"""
    return settings.RABBITMQ_URL


def is_development() -> bool:
    """判断是否为开发环境"""
    return settings.DEBUG


def get_service_urls() -> dict:
    """获取所有微服务URL"""
    return {
        "agent-service": settings.AGENT_SERVICE_URL,
        "knowledge-service": settings.KNOWLEDGE_SERVICE_URL,
        "model-service": settings.MODEL_SERVICE_URL,
        "system-service": settings.SYSTEM_SERVICE_URL,
        "chat-service": settings.CHAT_SERVICE_URL,
        "gateway-service": settings.GATEWAY_URL
    } 