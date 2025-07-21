"""
智能报告服务配置管理
"""
import os
from typing import Optional, Dict, Any
from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """应用配置"""
    
    # 基础配置
    app_name: str = "intelligent-reports-service"
    app_version: str = "1.0.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    
    # 数据库配置
    database_url: str = Field(..., env="DATABASE_URL")
    database_pool_size: int = 20
    database_max_overflow: int = 30
    
    # Redis配置
    redis_url: str = Field(..., env="REDIS_URL")
    redis_password: Optional[str] = Field(None, env="REDIS_PASSWORD")
    
    # 消息队列配置
    rabbitmq_url: str = Field(..., env="RABBITMQ_URL")
    
    # 模型服务配置
    model_service_url: str = Field(..., env="MODEL_SERVICE_URL")
    
    # JWT配置
    jwt_secret_key: str = Field(..., env="JWT_SECRET_KEY")
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24
    
    # 工作空间配置
    workspace_path: str = Field("/tmp/reports", env="WORKSPACE_PATH")
    max_workspace_size: int = 1024 * 1024 * 1024  # 1GB
    
    # 并发配置
    max_concurrent_tasks: int = 5
    task_timeout: int = 300  # 5分钟
    
    # 日志配置
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # 外部API配置
    tavily_api_key: Optional[str] = Field(None, env="TAVILY_API_KEY")
    google_api_key: Optional[str] = Field(None, env="GOOGLE_API_KEY")
    google_cse_id: Optional[str] = Field(None, env="GOOGLE_CSE_ID")
    
    # 代理配置
    http_proxy: Optional[str] = Field(None, env="HTTP_PROXY")
    https_proxy: Optional[str] = Field(None, env="HTTPS_PROXY")
    
    # 模型配置
    default_planner_model: str = "gpt-4"
    default_actor_model: str = "gpt-4"
    default_tool_model: str = "gpt-3.5-turbo"
    default_vision_model: str = "gpt-4-vision-preview"
    
    # 监控配置
    enable_prometheus: bool = True
    prometheus_port: int = 9090
    
    # 前端配置
    frontend_url: str = Field("http://localhost:3000", env="FRONTEND_URL")
    cors_origins: list = ["http://localhost:3000", "http://localhost:8000"]
    
    class Config:
        env_file = ".env"
        case_sensitive = False


class ModelConfig(BaseSettings):
    """模型配置"""
    
    # OpenAI配置
    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY")
    openai_base_url: Optional[str] = Field(None, env="OPENAI_BASE_URL")
    openai_organization: Optional[str] = Field(None, env="OPENAI_ORGANIZATION")
    
    # Azure OpenAI配置
    azure_openai_api_key: Optional[str] = Field(None, env="AZURE_OPENAI_API_KEY")
    azure_openai_endpoint: Optional[str] = Field(None, env="AZURE_OPENAI_ENDPOINT")
    azure_openai_api_version: str = "2023-05-15"
    
    # Anthropic配置
    anthropic_api_key: Optional[str] = Field(None, env="ANTHROPIC_API_KEY")
    
    # 其他模型配置
    zhipu_api_key: Optional[str] = Field(None, env="ZHIPU_API_KEY")
    moonshot_api_key: Optional[str] = Field(None, env="MOONSHOT_API_KEY")
    deepseek_api_key: Optional[str] = Field(None, env="DEEPSEEK_API_KEY")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


class ToolConfig(BaseSettings):
    """工具配置"""
    
    # 搜索工具配置
    enable_tavily_search: bool = True
    enable_google_search: bool = True
    enable_baidu_search: bool = True
    
    # 文件工具配置
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    allowed_file_extensions: list = [
        ".txt", ".md", ".pdf", ".docx", ".xlsx", ".csv", ".json", ".xml", ".html"
    ]
    
    # 代码执行工具配置
    enable_code_execution: bool = True
    code_execution_timeout: int = 30
    max_code_output_size: int = 10 * 1024  # 10KB
    
    # 可视化工具配置
    default_chart_width: int = 800
    default_chart_height: int = 600
    chart_dpi: int = 300
    
    # 多媒体工具配置
    enable_image_analysis: bool = True
    enable_video_analysis: bool = False
    enable_audio_analysis: bool = False
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# 全局配置实例
settings = Settings()
model_config = ModelConfig()
tool_config = ToolConfig()


def get_model_provider_config(provider: str) -> Dict[str, Any]:
    """获取模型提供商配置"""
    configs = {
        "openai": {
            "api_key": model_config.openai_api_key,
            "base_url": model_config.openai_base_url,
            "organization": model_config.openai_organization,
        },
        "azure": {
            "api_key": model_config.azure_openai_api_key,
            "azure_endpoint": model_config.azure_openai_endpoint,
            "api_version": model_config.azure_openai_api_version,
        },
        "anthropic": {
            "api_key": model_config.anthropic_api_key,
        },
        "zhipu": {
            "api_key": model_config.zhipu_api_key,
        },
        "moonshot": {
            "api_key": model_config.moonshot_api_key,
        },
        "deepseek": {
            "api_key": model_config.deepseek_api_key,
        }
    }
    
    return configs.get(provider, {})


def get_proxy_config() -> Dict[str, Optional[str]]:
    """获取代理配置"""
    return {
        "http": settings.http_proxy,
        "https": settings.https_proxy
    }


def validate_required_configs():
    """验证必需的配置"""
    required_configs = [
        ("database_url", settings.database_url),
        ("redis_url", settings.redis_url),
        ("rabbitmq_url", settings.rabbitmq_url),
        ("model_service_url", settings.model_service_url),
        ("jwt_secret_key", settings.jwt_secret_key),
    ]
    
    missing_configs = []
    for name, value in required_configs:
        if not value:
            missing_configs.append(name)
    
    if missing_configs:
        raise ValueError(f"Missing required configurations: {', '.join(missing_configs)}")


def get_workspace_path(user_id: str, report_id: str) -> str:
    """获取工作空间路径"""
    return os.path.join(settings.workspace_path, user_id, report_id)


def get_cors_config() -> Dict[str, Any]:
    """获取CORS配置"""
    return {
        "allow_origins": settings.cors_origins,
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["*"],
    }