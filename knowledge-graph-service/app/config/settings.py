"""
知识图谱服务配置管理
"""
import os
from typing import Optional, List
from enum import Enum

try:
    from pydantic import BaseSettings, Field
except ImportError:
    from pydantic_settings import BaseSettings
    from pydantic import Field

class GraphDatabaseType(str, Enum):
    """图数据库类型"""
    ARANGODB = "arangodb"
    POSTGRESQL_AGE = "postgresql_age"
    NEO4J = "neo4j"

class KnowledgeGraphServiceSettings(BaseSettings):
    """知识图谱服务配置"""
    
    # 服务基础配置
    SERVICE_NAME: str = Field(default="knowledge-graph-service", description="服务名称")
    HOST: str = Field(default="0.0.0.0", description="服务主机")
    PORT: int = Field(default=8087, description="服务端口")
    DEBUG: bool = Field(default=True, description="调试模式")
    LOG_LEVEL: str = Field(default="INFO", description="日志级别")
    
    # 网关配置
    GATEWAY_URL: str = Field(default="http://localhost:8080", description="网关地址")
    SERVICE_ID: str = Field(default="knowledge-graph-service", description="服务ID")
    
    # 数据库配置
    DATABASE_URL: str = Field(default="postgresql://user:password@localhost:5432/knowledge_graph", description="PostgreSQL数据库连接")
    
    # ArangoDB配置
    ARANGODB_URL: str = Field(default="http://localhost:8529", description="ArangoDB连接地址")
    ARANGODB_DATABASE: str = Field(default="knowledge_graph", description="ArangoDB数据库名")
    ARANGODB_DATABASE_PREFIX: str = Field(default="kg_", description="ArangoDB数据库前缀")
    ARANGODB_USERNAME: str = Field(default="root", description="ArangoDB用户名")
    ARANGODB_PASSWORD: str = Field(default="password", description="ArangoDB密码")
    
    # 图数据库配置
    GRAPH_DATABASE_TYPE: GraphDatabaseType = Field(default=GraphDatabaseType.ARANGODB, description="图数据库类型")
    GRAPH_DATABASE_TENANT_MODE: bool = Field(default=True, description="租户模式")
    GRAPH_DATABASE_MAX_CONNECTIONS: int = Field(default=10, description="最大连接数")
    
    # 租户配置
    GRAPH_TENANT_USERS_PER_SHARD: int = Field(default=1000, description="每个分片的用户数")
    GRAPH_TENANT_MAX_CACHED_DBS: int = Field(default=100, description="最大缓存数据库数")
    
    # Redis配置
    REDIS_URL: str = Field(default="redis://localhost:6379/0", description="Redis连接地址")
    REDIS_PASSWORD: Optional[str] = Field(default=None, description="Redis密码")
    
    # Celery配置
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/0", description="Celery代理地址")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/0", description="Celery结果后端")
    CELERY_TASK_SERIALIZER: str = Field(default="json", description="任务序列化器")
    CELERY_RESULT_SERIALIZER: str = Field(default="json", description="结果序列化器")
    
    # 知识图谱处理配置
    CHUNK_SIZE: int = Field(default=500, description="文本分块大小")
    MAX_ENTITIES: int = Field(default=1000, description="最大实体数量")
    MAX_RELATIONS: int = Field(default=5000, description="最大关系数量")
    CONFIDENCE_THRESHOLD: float = Field(default=0.7, description="置信度阈值")
    
    # LLM配置
    LLM_TEMPERATURE: float = Field(default=0.3, description="LLM温度参数")
    LLM_MAX_TOKENS: int = Field(default=8192, description="LLM最大令牌数")
    LLM_TIMEOUT: int = Field(default=60, description="LLM超时时间")
    
    # 可视化配置
    VISUALIZATION_WIDTH: int = Field(default=1200, description="可视化宽度")
    VISUALIZATION_HEIGHT: int = Field(default=800, description="可视化高度")
    VISUALIZATION_PHYSICS: bool = Field(default=True, description="启用物理模拟")
    VISUALIZATION_THEME: str = Field(default="light", description="可视化主题")
    
    # 文件存储配置
    UPLOAD_DIR: str = Field(default="uploads", description="上传目录")
    VISUALIZATION_DIR: str = Field(default="visualizations", description="可视化文件目录")
    MAX_FILE_SIZE: int = Field(default=10 * 1024 * 1024, description="最大文件大小")
    
    # 任务配置
    TASK_TIMEOUT: int = Field(default=3600, description="任务超时时间")
    TASK_RETRY_TIMES: int = Field(default=3, description="任务重试次数")
    TASK_RETRY_DELAY: int = Field(default=60, description="任务重试延迟")
    
    # 安全配置
    JWT_SECRET_KEY: str = Field(default="knowledge-graph-secret", description="JWT密钥")
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT算法")
    JWT_EXPIRATION_HOURS: int = Field(default=24, description="JWT过期时间")
    
    # 监控配置
    PROMETHEUS_ENABLED: bool = Field(default=True, description="启用Prometheus监控")
    PROMETHEUS_PORT: int = Field(default=9090, description="Prometheus端口")
    
    # 第三方服务配置
    KNOWLEDGE_SERVICE_URL: str = Field(default="http://localhost:8082", description="知识服务地址")
    MODEL_SERVICE_URL: str = Field(default="http://localhost:8088", description="模型服务地址")
    BASE_SERVICE_URL: str = Field(default="http://localhost:8085", description="基础服务地址")
    
    # CORS配置
    ALLOWED_ORIGINS: List[str] = Field(default=["*"], description="允许的跨域源")
        
    # Pydantic v2 配置
    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "env_prefix": "KG_",
        "extra": "ignore"
    }

# 创建全局设置实例
settings = KnowledgeGraphServiceSettings()

# 根据环境变量覆盖配置
def load_settings():
    """加载配置"""
    global settings
    
    # 从环境变量更新配置
    if os.getenv("KG_SERVICE_PORT"):
        settings.PORT = int(os.getenv("KG_SERVICE_PORT"))
    
    if os.getenv("KG_DEBUG"):
        settings.DEBUG = os.getenv("KG_DEBUG").lower() == "true"
    
    if os.getenv("KG_ARANGODB_URL"):
        settings.ARANGODB_URL = os.getenv("KG_ARANGODB_URL")
    
    if os.getenv("KG_ARANGODB_DATABASE"):
        settings.ARANGODB_DATABASE = os.getenv("KG_ARANGODB_DATABASE")
    
    if os.getenv("KG_ARANGODB_USERNAME"):
        settings.ARANGODB_USERNAME = os.getenv("KG_ARANGODB_USERNAME")
    
    if os.getenv("KG_ARANGODB_PASSWORD"):
        settings.ARANGODB_PASSWORD = os.getenv("KG_ARANGODB_PASSWORD")
    
    if os.getenv("KG_REDIS_URL"):
        settings.REDIS_URL = os.getenv("KG_REDIS_URL")
    
    if os.getenv("KG_CELERY_BROKER_URL"):
        settings.CELERY_BROKER_URL = os.getenv("KG_CELERY_BROKER_URL")
    
    if os.getenv("KG_CELERY_RESULT_BACKEND"):
        settings.CELERY_RESULT_BACKEND = os.getenv("KG_CELERY_RESULT_BACKEND")
    
    return settings

# 获取数据库连接字符串
def get_arangodb_connection_string() -> str:
    """获取ArangoDB连接字符串"""
    return f"{settings.ARANGODB_URL}/_db/{settings.ARANGODB_DATABASE}"

# 获取租户数据库名称
def get_tenant_database_name(user_id: str, project_id: str) -> str:
    """获取租户数据库名称"""
    if settings.GRAPH_DATABASE_TENANT_MODE:
        return f"kg_tenant_{user_id}_{project_id}"
    else:
        return settings.ARANGODB_DATABASE

# 获取图集合名称
def get_graph_collection_name(graph_id: str) -> str:
    """获取图集合名称"""
    return f"graph_{graph_id}"

# 日志配置
def get_logging_config() -> dict:
    """获取日志配置"""
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
            },
            "json": {
                "format": '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "module": "%(module)s", "message": "%(message)s"}',
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": settings.LOG_LEVEL,
                "formatter": "default",
                "stream": "ext://sys.stdout"
            },
            "file": {
                "class": "logging.FileHandler",
                "level": settings.LOG_LEVEL,
                "formatter": "json",
                "filename": "knowledge_graph_service.log"
            }
        },
        "loggers": {
            "": {
                "level": settings.LOG_LEVEL,
                "handlers": ["console", "file"]
            }
        }
    }

# 初始化设置
def init_settings():
    """初始化设置"""
    load_settings()
    
    # 创建必要的目录
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.VISUALIZATION_DIR, exist_ok=True)
    
    # 设置日志
    import logging.config
    logging.config.dictConfig(get_logging_config())
    
    logger = logging.getLogger(__name__)
    logger.info(f"Knowledge Graph Service initialized with settings: {settings.dict()}")

# 运行时初始化
if __name__ == "__main__":
    init_settings()
    print("Configuration loaded successfully!")
    print(f"Service will run on {settings.HOST}:{settings.PORT}")
    print(f"ArangoDB: {settings.ARANGODB_URL}")
    print(f"Redis: {settings.REDIS_URL}")
    print(f"Graph Database Type: {settings.GRAPH_DATABASE_TYPE}")