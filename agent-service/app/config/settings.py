"""
智能体服务配置
基于原ZZDSJ项目的配置系统，适配智能体服务需求
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
    
    # Agno框架配置
    AGNO_CONFIG: Dict[str, Any] = {
        "default_model_provider": "openai",
        "max_agents_per_user": 50,
        "max_team_size": 10,
        "execution_timeout": 300,
        "enable_monitoring": True,
        "enable_caching": True
    }
    
    # 模型配置
    OPENAI_API_KEY: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    ZHIPU_API_KEY: Optional[str] = Field(default=None, env="ZHIPU_API_KEY")
    MOONSHOT_API_KEY: Optional[str] = Field(default=None, env="MOONSHOT_API_KEY")
    
    # 工具配置
    ENABLE_WEB_SEARCH: bool = Field(default=True, env="ENABLE_WEB_SEARCH")
    ENABLE_CODE_EXECUTION: bool = Field(default=False, env="ENABLE_CODE_EXECUTION")
    ENABLE_FILE_OPERATIONS: bool = Field(default=True, env="ENABLE_FILE_OPERATIONS")
    
    # 安全配置
    SECRET_KEY: str = Field(default="your-secret-key", env="SECRET_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    
    # 存储配置
    UPLOAD_DIR: str = Field(default="./uploads", env="UPLOAD_DIR")
    MAX_FILE_SIZE: int = Field(default=10 * 1024 * 1024, env="MAX_FILE_SIZE")  # 10MB
    
    # 监控配置
    ENABLE_METRICS: bool = Field(default=True, env="ENABLE_METRICS")
    METRICS_PORT: int = Field(default=9090, env="METRICS_PORT")
    
    # 外部服务配置
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

def get_settings() -> Settings:
    """获取配置实例"""
    return settings
