package config

import (
	"fmt"
	"os"
	"path/filepath"
	"time"

	"gopkg.in/yaml.v3"
)

// Config 应用配置
type Config struct {
	Server      ServerConfig      `yaml:"server"`
	GRPC        GRPCConfig        `yaml:"grpc"`
	TaskManager TaskManagerConfig `yaml:"task_manager"`
	Redis       RedisConfig       `yaml:"redis"`
	Milvus      MilvusConfig      `yaml:"milvus"`
	Embedding   EmbeddingConfig   `yaml:"embedding"`
	Processing  ProcessingConfig  `yaml:"processing"`
	Monitoring  MonitoringConfig  `yaml:"monitoring"`
	Security    SecurityConfig    `yaml:"security"`
	Storage     StorageConfig     `yaml:"storage"`
	Development DevelopmentConfig `yaml:"development"`
}

// ServerConfig 服务器配置
type ServerConfig struct {
	Port              int           `yaml:"port"`
	Host              string        `yaml:"host"`
	Name              string        `yaml:"name"`
	Version           string        `yaml:"version"`
	Environment       string        `yaml:"environment"`
	MaxConnections    int           `yaml:"max_connections"`
	ConnectionTimeout time.Duration `yaml:"connection_timeout"`
	IdleTimeout       time.Duration `yaml:"idle_timeout"`
	ReadTimeout       time.Duration `yaml:"read_timeout"`
	WriteTimeout      time.Duration `yaml:"write_timeout"`
}

// GRPCConfig gRPC配置
type GRPCConfig struct {
	Port            int              `yaml:"port"`
	MaxRecvMsgSize  int              `yaml:"max_recv_msg_size"`
	MaxSendMsgSize  int              `yaml:"max_send_msg_size"`
	Keepalive       KeepaliveConfig  `yaml:"keepalive"`
	TLS             TLSConfig        `yaml:"tls"`
}

// KeepaliveConfig Keepalive配置
type KeepaliveConfig struct {
	Time                time.Duration `yaml:"time"`
	Timeout             time.Duration `yaml:"timeout"`
	PermitWithoutStream bool          `yaml:"permit_without_stream"`
}

// TLSConfig TLS配置
type TLSConfig struct {
	Enabled  bool   `yaml:"enabled"`
	CertFile string `yaml:"cert_file"`
	KeyFile  string `yaml:"key_file"`
}

// TaskManagerConfig 任务管理器配置
type TaskManagerConfig struct {
	Address    string             `yaml:"address"`
	Timeout    time.Duration      `yaml:"timeout"`
	MaxRetries int                `yaml:"max_retries"`
	GRPC       TaskManagerGRPC    `yaml:"grpc"`
}

// TaskManagerGRPC 任务管理器gRPC配置
type TaskManagerGRPC struct {
	Keepalive KeepaliveConfig `yaml:"keepalive"`
}

// RedisConfig Redis配置
type RedisConfig struct {
	Host     string          `yaml:"host"`
	Port     int             `yaml:"port"`
	Password string          `yaml:"password"`
	DB       int             `yaml:"db"`
	Pool     RedisPoolConfig `yaml:"pool"`
	Cluster  RedisCluster    `yaml:"cluster"`
}

// RedisPoolConfig Redis连接池配置
type RedisPoolConfig struct {
	MaxIdle     int           `yaml:"max_idle"`
	MaxActive   int           `yaml:"max_active"`
	IdleTimeout time.Duration `yaml:"idle_timeout"`
	Wait        bool          `yaml:"wait"`
}

// RedisCluster Redis集群配置
type RedisCluster struct {
	Enabled bool     `yaml:"enabled"`
	Nodes   []string `yaml:"nodes"`
}

// MilvusConfig Milvus配置
type MilvusConfig struct {
	Host       string               `yaml:"host"`
	Port       int                  `yaml:"port"`
	Username   string               `yaml:"username"`
	Password   string               `yaml:"password"`
	Connection MilvusConnectionConfig `yaml:"connection"`
	Default    MilvusDefaultConfig   `yaml:"default"`
}

// MilvusConnectionConfig Milvus连接配置
type MilvusConnectionConfig struct {
	Secure     bool          `yaml:"secure"`
	Timeout    time.Duration `yaml:"timeout"`
	MaxRetry   int           `yaml:"max_retry"`
	RetryDelay time.Duration `yaml:"retry_delay"`
}

// MilvusDefaultConfig Milvus默认配置
type MilvusDefaultConfig struct {
	Dimension  int    `yaml:"dimension"`
	MetricType string `yaml:"metric_type"`
	IndexType  string `yaml:"index_type"`
	NList      int    `yaml:"nlist"`
}

// EmbeddingConfig 嵌入配置
type EmbeddingConfig struct {
	DefaultModel string                    `yaml:"default_model"`
	Models       map[string]EmbeddingModel `yaml:"models"`
}

// EmbeddingModel 嵌入模型配置
type EmbeddingModel struct {
	Provider       string `yaml:"provider"`
	Dimension      int    `yaml:"dimension"`
	MaxBatchSize   int    `yaml:"max_batch_size"`
	MaxInputLength int    `yaml:"max_input_length"`
	APIBase        string `yaml:"api_base,omitempty"`
}

// ProcessingConfig 处理配置
type ProcessingConfig struct {
	Workers               int           `yaml:"workers"`
	MaxConcurrentRequests int           `yaml:"max_concurrent_requests"`
	QueueSize             int           `yaml:"queue_size"`
	Batch                 BatchConfig   `yaml:"batch"`
	Retry                 RetryConfig   `yaml:"retry"`
}

// BatchConfig 批处理配置
type BatchConfig struct {
	Size        int           `yaml:"size"`
	Timeout     time.Duration `yaml:"timeout"`
	MaxWaitTime time.Duration `yaml:"max_wait_time"`
}

// RetryConfig 重试配置
type RetryConfig struct {
	MaxAttempts   int           `yaml:"max_attempts"`
	BackoffBase   time.Duration `yaml:"backoff_base"`
	BackoffMax    time.Duration `yaml:"backoff_max"`
	Exponential   bool          `yaml:"exponential"`
}

// MonitoringConfig 监控配置
type MonitoringConfig struct {
	Prometheus PrometheusConfig `yaml:"prometheus"`
	Health     HealthConfig     `yaml:"health"`
	Logging    LoggingConfig    `yaml:"logging"`
}

// PrometheusConfig Prometheus配置
type PrometheusConfig struct {
	Enabled bool   `yaml:"enabled"`
	Port    int    `yaml:"port"`
	Path    string `yaml:"path"`
}

// HealthConfig 健康检查配置
type HealthConfig struct {
	Enabled  bool          `yaml:"enabled"`
	Port     int           `yaml:"port"`
	Path     string        `yaml:"path"`
	Interval time.Duration `yaml:"interval"`
}

// LoggingConfig 日志配置
type LoggingConfig struct {
	Level      string `yaml:"level"`
	Format     string `yaml:"format"`
	File       string `yaml:"file"`
	MaxSize    string `yaml:"max_size"`
	MaxBackups int    `yaml:"max_backups"`
	MaxAge     int    `yaml:"max_age"`
}

// SecurityConfig 安全配置
type SecurityConfig struct {
	RateLimit RateLimitConfig `yaml:"rate_limit"`
	Auth      AuthConfig      `yaml:"auth"`
}

// RateLimitConfig 限流配置
type RateLimitConfig struct {
	Enabled           bool `yaml:"enabled"`
	RequestsPerSecond int  `yaml:"requests_per_second"`
	Burst             int  `yaml:"burst"`
}

// AuthConfig 认证配置
type AuthConfig struct {
	Enabled   bool   `yaml:"enabled"`
	JWTSecret string `yaml:"jwt_secret"`
	TokenTTL  string `yaml:"token_ttl"`
}

// StorageConfig 存储配置
type StorageConfig struct {
	TempDir         string `yaml:"temp_dir"`
	MaxTempSize     string `yaml:"max_temp_size"`
	CleanupInterval string `yaml:"cleanup_interval"`
}

// DevelopmentConfig 开发配置
type DevelopmentConfig struct {
	Debug                 bool `yaml:"debug"`
	PprofEnabled          bool `yaml:"pprof_enabled"`
	MockExternalServices  bool `yaml:"mock_external_services"`
}

// LoadConfig 加载配置文件
func LoadConfig() (*Config, error) {
	// 默认配置文件路径
	configPath := "config/config.yaml"
	
	// 检查环境变量中的配置路径
	if envPath := os.Getenv("CONFIG_PATH"); envPath != "" {
		configPath = envPath
	}

	// 检查配置文件是否存在
	if _, err := os.Stat(configPath); os.IsNotExist(err) {
		// 尝试从多个路径查找配置文件
		possiblePaths := []string{
			"config/config.yaml",
			"./config.yaml",
			"../config/config.yaml",
			"/etc/vector-service/config.yaml",
		}

		found := false
		for _, path := range possiblePaths {
			if _, err := os.Stat(path); err == nil {
				configPath = path
				found = true
				break
			}
		}

		if !found {
			return nil, fmt.Errorf("配置文件不存在: %s", configPath)
		}
	}

	// 读取配置文件
	data, err := os.ReadFile(configPath)
	if err != nil {
		return nil, fmt.Errorf("读取配置文件失败 %s: %w", configPath, err)
	}

	// 解析配置
	var config Config
	if err := yaml.Unmarshal(data, &config); err != nil {
		return nil, fmt.Errorf("解析配置文件失败: %w", err)
	}

	// 应用环境变量覆盖
	applyEnvOverrides(&config)

	// 验证配置
	if err := validateConfig(&config); err != nil {
		return nil, fmt.Errorf("配置验证失败: %w", err)
	}

	return &config, nil
}

// applyEnvOverrides 应用环境变量覆盖
func applyEnvOverrides(config *Config) {
	// Redis配置
	if host := os.Getenv("REDIS_HOST"); host != "" {
		config.Redis.Host = host
	}
	if password := os.Getenv("REDIS_PASSWORD"); password != "" {
		config.Redis.Password = password
	}

	// Milvus配置
	if host := os.Getenv("MILVUS_HOST"); host != "" {
		config.Milvus.Host = host
	}
	if username := os.Getenv("MILVUS_USERNAME"); username != "" {
		config.Milvus.Username = username
	}
	if password := os.Getenv("MILVUS_PASSWORD"); password != "" {
		config.Milvus.Password = password
	}

	// 任务管理器配置
	if address := os.Getenv("TASK_MANAGER_ADDRESS"); address != "" {
		config.TaskManager.Address = address
	}

	// 环境配置
	if env := os.Getenv("ENVIRONMENT"); env != "" {
		config.Server.Environment = env
	}
}

// validateConfig 验证配置
func validateConfig(config *Config) error {
	if config.Server.Port <= 0 {
		return fmt.Errorf("服务器端口必须大于0")
	}

	if config.Processing.Workers <= 0 {
		return fmt.Errorf("工作进程数必须大于0")
	}

	if config.Processing.MaxConcurrentRequests <= 0 {
		return fmt.Errorf("最大并发请求数必须大于0")
	}

	if config.Embedding.DefaultModel == "" {
		return fmt.Errorf("必须指定默认嵌入模型")
	}

	return nil
}

// GetConfigDir 获取配置目录
func GetConfigDir() string {
	if dir := os.Getenv("CONFIG_DIR"); dir != "" {
		return dir
	}
	
	// 获取可执行文件目录
	executable, err := os.Executable()
	if err != nil {
		return "./config"
	}
	
	return filepath.Join(filepath.Dir(executable), "config")
}