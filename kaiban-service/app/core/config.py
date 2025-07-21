"""
应用配置管理
"""

import os
import yaml
from typing import Dict, List, Any, Optional
try:
    from pydantic_settings import BaseSettings
    from pydantic import validator
except ImportError:
    from pydantic import BaseSettings, validator
from pathlib import Path

class DatabaseConfig(BaseSettings):
    """数据库配置"""
    host: str = "localhost"
    port: int = 5432
    database: str = "kaiban_db"
    username: str = "postgres"
    password: str = "password"
    pool_size: int = 10
    max_overflow: int = 20
    echo: bool = False
    
    @property
    def url(self) -> str:
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"

class RedisConfig(BaseSettings):
    """Redis配置"""
    host: str = "localhost"
    port: int = 6379
    password: str = ""
    database: int = 0
    max_connections: int = 10
    socket_timeout: int = 30
    socket_connect_timeout: int = 30
    health_check_interval: int = 30
    
    @property
    def url(self) -> str:
        auth = f":{self.password}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.database}"

class ExternalServiceConfig(BaseSettings):
    """外部服务配置"""
    url: str
    timeout: int = 30
    retry_count: int = 3
    health_check_path: str = "/health"

class SecurityConfig(BaseSettings):
    """安全配置"""
    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]
    cors_methods: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    cors_headers: List[str] = ["Content-Type", "Authorization", "X-User-ID", "X-Request-ID"]

class WorkflowConfig(BaseSettings):
    """工作流配置"""
    max_concurrent_workflows: int = 50
    default_timeout: int = 300
    max_steps_per_workflow: int = 100
    auto_save_interval: int = 30
    checkpoint_enabled: bool = True

class TaskConfig(BaseSettings):
    """任务配置"""
    max_concurrent_tasks: int = 100
    default_priority: str = "medium"
    auto_assign: bool = False
    status_sync_interval: int = 10

class EventConfig(BaseSettings):
    """事件配置"""
    max_subscribers: int = 1000
    event_retention_days: int = 30
    batch_size: int = 100
    processing_timeout: int = 60

class LoggingConfig(BaseSettings):
    """日志配置"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_enabled: bool = True
    file_path: str = "logs/kaiban-service.log"
    max_file_size: str = "10MB"
    backup_count: int = 5

class CacheConfig(BaseSettings):
    """缓存配置"""
    default_ttl: int = 300
    workflow_ttl: int = 1800
    task_ttl: int = 600
    user_session_ttl: int = 3600

class APIConfig(BaseSettings):
    """API配置"""
    max_request_size: str = "10MB"
    rate_limit_requests_per_minute: int = 60
    rate_limit_burst_size: int = 10
    pagination_default_page_size: int = 20
    pagination_max_page_size: int = 100

class Settings(BaseSettings):
    """应用设置"""
    
    # 服务基础配置
    service_name: str = "kaiban-service"
    service_version: str = "1.0.0"
    host: str = "0.0.0.0"
    port: int = 8003
    debug: bool = True
    environment: str = "development"
    
    # 子配置
    database: DatabaseConfig = DatabaseConfig()
    redis: RedisConfig = RedisConfig()
    security: SecurityConfig = SecurityConfig()
    workflow: WorkflowConfig = WorkflowConfig()
    tasks: TaskConfig = TaskConfig()
    events: EventConfig = EventConfig()
    logging: LoggingConfig = LoggingConfig()
    cache: CacheConfig = CacheConfig()
    api: APIConfig = APIConfig()
    
    # 外部服务配置
    agent_service_url: str = "http://localhost:8001"
    model_service_url: str = "http://localhost:8002"
    knowledge_service_url: str = "http://localhost:8004"
    gateway_url: str = "http://localhost:8000"
    
    # 外部服务超时配置
    agent_service_timeout: int = 30
    model_service_timeout: int = 60
    knowledge_service_timeout: int = 45
    gateway_timeout: int = 10
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
    @classmethod
    def load_from_yaml(cls, config_path: str = "config.yaml") -> "Settings":
        """从YAML文件加载配置"""
        config_file = Path(config_path)
        if not config_file.exists():
            # 如果配置文件不存在，返回默认配置
            return cls()
            
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
            
        # 处理嵌套配置
        flat_config = {}
        
        # 服务配置
        if 'service' in config_data:
            service_config = config_data['service']
            flat_config.update({
                'service_name': service_config.get('name', 'kaiban-service'),
                'service_version': service_config.get('version', '1.0.0'),
                'host': service_config.get('host', '0.0.0.0'),
                'port': service_config.get('port', 8003),
                'debug': service_config.get('debug', True),
                'environment': service_config.get('environment', 'development')
            })
        
        # 数据库配置
        if 'database' in config_data and 'postgresql' in config_data['database']:
            db_config = config_data['database']['postgresql']
            flat_config['database'] = DatabaseConfig(**db_config)
        
        # Redis配置
        if 'redis' in config_data:
            flat_config['redis'] = RedisConfig(**config_data['redis'])
        
        # 外部服务配置
        if 'external_services' in config_data:
            ext_services = config_data['external_services']
            
            if 'agent_service' in ext_services:
                agent_config = ext_services['agent_service']
                flat_config['agent_service_url'] = agent_config.get('url', 'http://localhost:8001')
                flat_config['agent_service_timeout'] = agent_config.get('timeout', 30)
            
            if 'model_service' in ext_services:
                model_config = ext_services['model_service']
                flat_config['model_service_url'] = model_config.get('url', 'http://localhost:8002')
                flat_config['model_service_timeout'] = model_config.get('timeout', 60)
            
            if 'knowledge_service' in ext_services:
                knowledge_config = ext_services['knowledge_service']
                flat_config['knowledge_service_url'] = knowledge_config.get('url', 'http://localhost:8004')
                flat_config['knowledge_service_timeout'] = knowledge_config.get('timeout', 45)
        
        # 网关配置
        if 'gateway' in config_data:
            gateway_config = config_data['gateway']
            flat_config['gateway_url'] = gateway_config.get('url', 'http://localhost:8000')
            flat_config['gateway_timeout'] = gateway_config.get('timeout', 10)
        
        # 其他配置
        for config_name in ['security', 'workflow', 'tasks', 'events', 'logging', 'cache']:
            if config_name in config_data:
                config_class = {
                    'security': SecurityConfig,
                    'workflow': WorkflowConfig,
                    'tasks': TaskConfig,
                    'events': EventConfig,
                    'logging': LoggingConfig,
                    'cache': CacheConfig,
                }[config_name]
                flat_config[config_name] = config_class(**config_data[config_name])
        
        # API配置特殊处理
        if 'api' in config_data:
            api_config = config_data['api']
            api_flat = {}
            
            if 'rate_limit' in api_config:
                rate_limit = api_config['rate_limit']
                api_flat['rate_limit_requests_per_minute'] = rate_limit.get('requests_per_minute', 60)
                api_flat['rate_limit_burst_size'] = rate_limit.get('burst_size', 10)
            
            if 'pagination' in api_config:
                pagination = api_config['pagination']
                api_flat['pagination_default_page_size'] = pagination.get('default_page_size', 20)
                api_flat['pagination_max_page_size'] = pagination.get('max_page_size', 100)
            
            api_flat['max_request_size'] = api_config.get('max_request_size', '10MB')
            flat_config['api'] = APIConfig(**api_flat)
        
        return cls(**flat_config)

# 全局配置实例
settings = Settings.load_from_yaml()

# 兼容性属性，方便在其他模块中使用
AGENT_SERVICE_URL = settings.agent_service_url
MODEL_SERVICE_URL = settings.model_service_url
KNOWLEDGE_SERVICE_URL = settings.knowledge_service_url
GATEWAY_SERVICE_URL = settings.gateway_url

# 数据库URL
DATABASE_URL = settings.database.url
REDIS_URL = settings.redis.url 