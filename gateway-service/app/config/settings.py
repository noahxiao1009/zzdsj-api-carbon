"""
Gateway Service Configuration - 网关服务配置
基于原ZZDSJ Backend API配置系统改造的网关层配置
"""

try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings

from pydantic import Field
from typing import List, Dict, Any, Optional
import os
import secrets
import warnings

def generate_secure_key() -> str:
    """生成安全的密钥"""
    return secrets.token_hex(32)

def get_jwt_secret_key() -> str:
    """获取JWT密钥，优先使用环境变量，否则生成安全密钥"""
    key = os.getenv("JWT_SECRET_KEY")
    if not key:
        warnings.warn(
            "JWT_SECRET_KEY环境变量未设置！正在生成临时密钥。",
            UserWarning
        )
        return generate_secure_key()
    return key

class GatewaySettings(BaseSettings):
    """网关服务配置设置"""
    
    # 服务基础信息
    SERVICE_NAME: str = Field(default="gateway-service", description="服务名称")
    SERVICE_IP: str = Field(default="0.0.0.0", description="服务IP")
    SERVICE_PORT: int = Field(default=8080, description="服务端口")
    SERVICE_VERSION: str = Field(default="1.0.0", description="服务版本")
    
    # 应用基础配置
    APP_NAME: str = Field(default="ZZDSJ Gateway Service", description="应用名称")
    APP_VERSION: str = Field(default="1.0.0", description="应用版本")
    DEBUG: bool = Field(default=True, description="调试模式")
    APP_ENV: str = Field(default="development", description="应用环境")
    
    # JWT配置
    SECRET_KEY: str = Field(default_factory=get_jwt_secret_key, description="应用密钥")
    JWT_SECRET_KEY: str = Field(default_factory=get_jwt_secret_key, description="JWT密钥")
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT算法")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60 * 24 * 8, description="JWT过期时间(分钟)")
    
    # CORS配置
    CORS_ORIGINS: List[str] = Field(
        default=[
            "http://localhost:3000", 
            "http://localhost:8000",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8000"
        ],
        description="允许的CORS源"
    )
    CORS_ALLOW_CREDENTIALS: bool = Field(default=True, description="CORS允许凭证")
    CORS_ALLOW_METHODS: List[str] = Field(
        default=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        description="CORS允许的方法"
    )
    CORS_ALLOW_HEADERS: List[str] = Field(default=["*"], description="CORS允许的头部")
    
    # 后端服务配置
    AGENT_SERVICE_URL: str = Field(
        default="http://localhost:8081",
        description="智能体服务URL"
    )
    KNOWLEDGE_SERVICE_URL: str = Field(
        default="http://localhost:8082",
        description="知识库服务URL"
    )
    MODEL_SERVICE_URL: str = Field(
        default="http://localhost:8083",
        description="模型服务URL"
    )
    BASE_SERVICE_URL: str = Field(
        default="http://localhost:8084",
        description="基础服务URL"
    )
    
    # 负载均衡配置
    LOAD_BALANCER_ALGORITHM: str = Field(
        default="round_robin",
        description="负载均衡算法: round_robin, weighted_round_robin, random, ip_hash"
    )
    HEALTH_CHECK_INTERVAL: int = Field(default=30, description="健康检查间隔(秒)")
    HEALTH_CHECK_TIMEOUT: int = Field(default=5, description="健康检查超时(秒)")
    HEALTH_CHECK_RETRIES: int = Field(default=3, description="健康检查重试次数")
    
    # 限流配置
    RATE_LIMIT_ENABLED: bool = Field(default=True, description="是否启用限流")
    RATE_LIMIT_DEFAULT_RPM: int = Field(default=60, description="默认每分钟请求限制")
    RATE_LIMIT_BURST_SIZE: int = Field(default=10, description="突发请求大小")
    
    # 路径级别的限流配置
    RATE_LIMIT_PATHS: Dict[str, int] = Field(
        default={
            "/api/auth/*": 30,     # 认证相关限制更严格
            "/api/chat/*": 120,    # 聊天接口允许更多请求
            "/api/models/*": 90,   # 模型接口中等限制
            "/api/upload/*": 20,   # 上传接口限制较严格
        },
        description="路径级别的限流配置"
    )
    
    # 监控配置
    MONITORING_ENABLED: bool = Field(default=True, description="是否启用监控")
    METRICS_ENABLED: bool = Field(default=True, description="是否启用指标收集")
    
    # 监控路径配置
    MONITORING_EXCLUDE_PATHS: List[str] = Field(
        default=[
            "/health",
            "/metrics", 
            "/docs",
            "/redoc",
            "/openapi.json",
            "/static/*"
        ],
        description="不监控的路径"
    )
    
    # 日志配置
    LOG_LEVEL: str = Field(default="INFO", description="日志级别")
    LOG_FORMAT: str = Field(default="json", description="日志格式: text, json")
    LOG_REQUEST_BODY: bool = Field(default=False, description="是否记录请求体")
    LOG_RESPONSE_BODY: bool = Field(default=False, description="是否记录响应体")
    
    # 请求超时配置
    GATEWAY_REQUEST_TIMEOUT: int = Field(default=30, description="网关请求超时(秒)")
    BACKEND_REQUEST_TIMEOUT: int = Field(default=60, description="后端请求超时(秒)")
    
    # 重试配置
    RETRY_ENABLED: bool = Field(default=True, description="是否启用重试")
    RETRY_MAX_ATTEMPTS: int = Field(default=3, description="最大重试次数")
    RETRY_BACKOFF_FACTOR: float = Field(default=0.5, description="重试退避因子")
    
    # 熔断器配置
    CIRCUIT_BREAKER_ENABLED: bool = Field(default=True, description="是否启用熔断器")
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = Field(default=5, description="熔断器失败阈值")
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT: int = Field(default=60, description="熔断器恢复超时(秒)")
    
    # Redis配置
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis连接URL"
    )
    REDIS_MAX_CONNECTIONS: int = Field(default=10, description="Redis最大连接数")
    REDIS_TIMEOUT: int = Field(default=5, description="Redis超时(秒)")
    
    # 缓存配置
    CACHE_ENABLED: bool = Field(default=True, description="是否启用缓存")
    CACHE_TTL: int = Field(default=300, description="缓存TTL(秒)")
    
    # 文件上传配置
    MAX_FILE_SIZE: int = Field(default=10 * 1024 * 1024, description="最大文件大小(字节)")
    UPLOAD_PATH: str = Field(default="uploads", description="上传文件路径")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        env_prefix = "GATEWAY_"

# 创建全局设置实例
try:
    gateway_settings = GatewaySettings()
except Exception as e:
    warnings.warn(f"网关配置加载失败，使用默认设置: {e}")
    gateway_settings = GatewaySettings()

def get_settings() -> GatewaySettings:
    """获取设置实例"""
    return gateway_settings

def get_backend_services() -> Dict[str, str]:
    """获取后端服务配置"""
    settings = get_settings()
    return {
        "agent": settings.AGENT_SERVICE_URL,
        "knowledge": settings.KNOWLEDGE_SERVICE_URL,
        "model": settings.MODEL_SERVICE_URL,
        "base": settings.BASE_SERVICE_URL,
    }

def get_rate_limit_config() -> Dict[str, Any]:
    """获取限流配置"""
    settings = get_settings()
    return {
        "enabled": settings.RATE_LIMIT_ENABLED,
        "default_rpm": settings.RATE_LIMIT_DEFAULT_RPM,
        "burst_size": settings.RATE_LIMIT_BURST_SIZE,
        "path_limits": settings.RATE_LIMIT_PATHS,
    }

def get_monitoring_config() -> Dict[str, Any]:
    """获取监控配置"""
    settings = get_settings()
    return {
        "enabled": settings.MONITORING_ENABLED,
        "metrics_enabled": settings.METRICS_ENABLED,
        "exclude_paths": settings.MONITORING_EXCLUDE_PATHS,
        "log_level": settings.LOG_LEVEL,
        "log_format": settings.LOG_FORMAT,
    }

__all__ = [
    "gateway_settings", 
    "get_settings", 
    "GatewaySettings",
    "get_backend_services",
    "get_rate_limit_config", 
    "get_monitoring_config"
]
