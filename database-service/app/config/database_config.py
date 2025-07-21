"""
数据库管理微服务配置
支持ES、PostgreSQL、Milvus、Redis、Nacos、RabbitMQ等基础数据库服务
"""

import os
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum


class DatabaseType(str, Enum):
    """数据库类型枚举"""
    POSTGRESQL = "postgresql"
    ELASTICSEARCH = "elasticsearch"
    MILVUS = "milvus"
    REDIS = "redis"
    NACOS = "nacos"
    RABBITMQ = "rabbitmq"


class DatabaseStatus(str, Enum):
    """数据库状态枚举"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    CONNECTING = "connecting"
    DISCONNECTED = "disconnected"


class PostgreSQLConfig(BaseModel):
    """PostgreSQL数据库配置"""
    host: str = Field("localhost", description="PostgreSQL主机地址")
    port: int = Field(5432, description="PostgreSQL端口")
    username: str = Field("postgres", description="用户名")
    password: str = Field("password", description="密码")
    database: str = Field("carbon_db", description="数据库名")
    schema: str = Field("public", description="模式名")
    max_connections: int = Field(20, description="最大连接数")
    connection_timeout: int = Field(30, description="连接超时时间(秒)")
    
    @property
    def database_url(self) -> str:
        """获取数据库连接URL"""
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    @property
    def async_database_url(self) -> str:
        """获取异步数据库连接URL"""
        return f"postgresql+asyncpg://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    @property
    def sync_database_url(self) -> str:
        """获取同步数据库连接URL"""
        return f"postgresql+psycopg2://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


class ElasticsearchConfig(BaseModel):
    """Elasticsearch配置"""
    hosts: List[str] = Field(["http://localhost:9200"], description="ES集群地址")
    username: Optional[str] = Field(None, description="用户名")
    password: Optional[str] = Field(None, description="密码")
    api_key: Optional[str] = Field(None, description="API密钥")
    timeout: int = Field(30, description="连接超时时间(秒)")
    max_retries: int = Field(3, description="最大重试次数")
    retry_on_timeout: bool = Field(True, description="超时重试")
    
    # 索引配置
    default_index_settings: Dict[str, Any] = Field(
        default_factory=lambda: {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "refresh_interval": "1s"
        },
        description="默认索引设置"
    )


class MilvusConfig(BaseModel):
    """Milvus向量数据库配置"""
    host: str = Field("localhost", description="Milvus主机地址")
    port: int = Field(19530, description="Milvus端口")
    username: Optional[str] = Field(None, description="用户名")
    password: Optional[str] = Field(None, description="密码")
    secure: bool = Field(False, description="是否使用安全连接")
    timeout: int = Field(10, description="连接超时时间(秒)")
    
    # 集合配置
    default_dimension: int = Field(1536, description="默认向量维度")
    default_metric_type: str = Field("IP", description="默认度量类型")
    default_index_type: str = Field("IVF_FLAT", description="默认索引类型")
    collection_consistency_level: str = Field("Strong", description="一致性级别")


class RedisConfig(BaseModel):
    """Redis配置"""
    host: str = Field("localhost", description="Redis主机地址")
    port: int = Field(6379, description="Redis端口")
    password: Optional[str] = Field(None, description="密码")
    db: int = Field(0, description="数据库索引")
    max_connections: int = Field(20, description="最大连接数")
    connection_timeout: int = Field(10, description="连接超时时间(秒)")
    retry_on_timeout: bool = Field(True, description="超时重试")
    
    # 集群配置
    cluster_enabled: bool = Field(False, description="是否启用集群模式")
    cluster_nodes: List[str] = Field(default_factory=list, description="集群节点")


class NacosConfig(BaseModel):
    """Nacos服务发现配置"""
    server_addresses: List[str] = Field(["localhost:8848"], description="Nacos服务器地址")
    namespace: str = Field("public", description="命名空间")
    group: str = Field("DEFAULT_GROUP", description="分组")
    username: Optional[str] = Field(None, description="用户名")
    password: Optional[str] = Field(None, description="密码")
    
    # 服务注册配置
    service_name: str = Field("database-service", description="服务名")
    service_ip: str = Field("127.0.0.1", description="服务IP")
    service_port: int = Field(8089, description="服务端口")
    cluster_name: str = Field("default", description="集群名")
    
    # 配置管理
    config_format: str = Field("yaml", description="配置格式")
    config_timeout: int = Field(10, description="配置超时时间(秒)")


class RabbitMQConfig(BaseModel):
    """RabbitMQ消息队列配置"""
    host: str = Field("localhost", description="RabbitMQ主机地址")
    port: int = Field(5672, description="RabbitMQ端口")
    username: str = Field("guest", description="用户名")
    password: str = Field("guest", description="密码")
    virtual_host: str = Field("/", description="虚拟主机")
    
    # 连接配置
    connection_timeout: int = Field(10, description="连接超时时间(秒)")
    max_channels: int = Field(10, description="最大通道数")
    heartbeat: int = Field(60, description="心跳间隔(秒)")
    
    # 队列配置
    default_exchange: str = Field("carbon.direct", description="默认交换机")
    default_queue_durable: bool = Field(True, description="默认队列持久化")
    default_message_ttl: int = Field(3600000, description="默认消息TTL(毫秒)")


class DatabaseServiceConfig(BaseModel):
    """数据库服务配置"""
    
    # 基础配置
    service_name: str = Field("database-service", description="服务名称")
    service_port: int = Field(8089, description="服务端口")
    debug: bool = Field(False, description="调试模式")
    
    # 各数据库配置
    postgresql: PostgreSQLConfig = Field(default_factory=PostgreSQLConfig, description="PostgreSQL配置")
    elasticsearch: ElasticsearchConfig = Field(default_factory=ElasticsearchConfig, description="Elasticsearch配置")
    milvus: MilvusConfig = Field(default_factory=MilvusConfig, description="Milvus配置")
    redis: RedisConfig = Field(default_factory=RedisConfig, description="Redis配置")
    nacos: NacosConfig = Field(default_factory=NacosConfig, description="Nacos配置")
    rabbitmq: RabbitMQConfig = Field(default_factory=RabbitMQConfig, description="RabbitMQ配置")
    
    # 健康检查配置
    health_check_enabled: bool = Field(True, description="是否启用健康检查")
    health_check_interval: int = Field(60, description="健康检查间隔(秒)")
    health_check_timeout: int = Field(10, description="健康检查超时时间(秒)")
    
    # 监控配置
    monitoring_enabled: bool = Field(True, description="是否启用监控")
    metrics_port: int = Field(9090, description="监控端口")
    log_level: str = Field("INFO", description="日志级别")
    
    # 网关注册配置
    gateway_enabled: bool = Field(True, description="是否启用网关注册")
    gateway_url: str = Field("http://localhost:8080", description="网关地址")
    gateway_token: Optional[str] = Field(None, description="网关认证令牌")
    
    @classmethod
    def from_env(cls) -> "DatabaseServiceConfig":
        """从环境变量创建配置"""
        return cls(
            service_name=os.getenv("DB_SERVICE_NAME", "database-service"),
            service_port=int(os.getenv("DB_SERVICE_PORT", "8089")),
            debug=os.getenv("DEBUG", "false").lower() == "true",
            
            postgresql=PostgreSQLConfig(
                host=os.getenv("POSTGRES_HOST", "localhost"),
                port=int(os.getenv("POSTGRES_PORT", "5432")),
                username=os.getenv("POSTGRES_USER", "postgres"),
                password=os.getenv("POSTGRES_PASSWORD", "password"),
                database=os.getenv("POSTGRES_DB", "carbon_db"),
                schema=os.getenv("POSTGRES_SCHEMA", "public"),
                max_connections=int(os.getenv("POSTGRES_MAX_CONNECTIONS", "20")),
                connection_timeout=int(os.getenv("POSTGRES_TIMEOUT", "30"))
            ),
            
            elasticsearch=ElasticsearchConfig(
                hosts=os.getenv("ELASTICSEARCH_HOSTS", "http://localhost:9200").split(","),
                username=os.getenv("ELASTICSEARCH_USERNAME"),
                password=os.getenv("ELASTICSEARCH_PASSWORD"),
                api_key=os.getenv("ELASTICSEARCH_API_KEY"),
                timeout=int(os.getenv("ELASTICSEARCH_TIMEOUT", "30"))
            ),
            
            milvus=MilvusConfig(
                host=os.getenv("MILVUS_HOST", "localhost"),
                port=int(os.getenv("MILVUS_PORT", "19530")),
                username=os.getenv("MILVUS_USERNAME"),
                password=os.getenv("MILVUS_PASSWORD"),
                secure=os.getenv("MILVUS_SECURE", "false").lower() == "true",
                timeout=int(os.getenv("MILVUS_TIMEOUT", "10"))
            ),
            
            redis=RedisConfig(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", "6379")),
                password=os.getenv("REDIS_PASSWORD"),
                db=int(os.getenv("REDIS_DB", "0")),
                max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", "20"))
            ),
            
            nacos=NacosConfig(
                server_addresses=os.getenv("NACOS_SERVERS", "localhost:8848").split(","),
                namespace=os.getenv("NACOS_NAMESPACE", "public"),
                group=os.getenv("NACOS_GROUP", "DEFAULT_GROUP"),
                username=os.getenv("NACOS_USERNAME"),
                password=os.getenv("NACOS_PASSWORD"),
                service_name=os.getenv("NACOS_SERVICE_NAME", "database-service"),
                service_ip=os.getenv("NACOS_SERVICE_IP", "127.0.0.1"),
                service_port=int(os.getenv("NACOS_SERVICE_PORT", "8089"))
            ),
            
            rabbitmq=RabbitMQConfig(
                host=os.getenv("RABBITMQ_HOST", "localhost"),
                port=int(os.getenv("RABBITMQ_PORT", "5672")),
                username=os.getenv("RABBITMQ_USERNAME", "guest"),
                password=os.getenv("RABBITMQ_PASSWORD", "guest"),
                virtual_host=os.getenv("RABBITMQ_VHOST", "/")
            ),
            
            health_check_enabled=os.getenv("HEALTH_CHECK_ENABLED", "true").lower() == "true",
            health_check_interval=int(os.getenv("HEALTH_CHECK_INTERVAL", "60")),
            monitoring_enabled=os.getenv("MONITORING_ENABLED", "true").lower() == "true",
            metrics_port=int(os.getenv("METRICS_PORT", "9090")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            
            gateway_enabled=os.getenv("GATEWAY_ENABLED", "true").lower() == "true",
            gateway_url=os.getenv("GATEWAY_URL", "http://localhost:8080"),
            gateway_token=os.getenv("GATEWAY_TOKEN")
        )


# 全局配置实例
database_config = DatabaseServiceConfig.from_env()


def get_database_config() -> DatabaseServiceConfig:
    """获取数据库服务配置"""
    return database_config


def get_database_config_by_type(db_type: DatabaseType) -> BaseModel:
    """根据数据库类型获取配置"""
    config = get_database_config()
    
    config_mapping = {
        DatabaseType.POSTGRESQL: config.postgresql,
        DatabaseType.ELASTICSEARCH: config.elasticsearch,
        DatabaseType.MILVUS: config.milvus,
        DatabaseType.REDIS: config.redis,
        DatabaseType.NACOS: config.nacos,
        DatabaseType.RABBITMQ: config.rabbitmq
    }
    
    if db_type not in config_mapping:
        raise ValueError(f"不支持的数据库类型: {db_type}")
    
    return config_mapping[db_type] 