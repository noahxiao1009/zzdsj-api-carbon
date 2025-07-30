package config

import (
	"fmt"
	"time"

	"github.com/spf13/viper"
)

type Config struct {
	Port        int           `mapstructure:"port"`
	GRPCPort    int           `mapstructure:"grpc_port"`
	Environment string        `mapstructure:"environment"`
	LogLevel    string        `mapstructure:"log_level"`
	Database    DatabaseConfig `mapstructure:"database"`
	Redis       RedisConfig   `mapstructure:"redis"`
	Worker      WorkerConfig  `mapstructure:"worker"`
	Task        TaskConfig    `mapstructure:"task"`
	MinIO       MinIOConfig   `mapstructure:"minio"`
	Upload      UploadConfig  `mapstructure:"upload"`
}

type DatabaseConfig struct {
	Host     string `mapstructure:"host"`
	Port     int    `mapstructure:"port"`
	User     string `mapstructure:"user"`
	Password string `mapstructure:"password"`
	Database string `mapstructure:"database"`
	SSLMode  string `mapstructure:"ssl_mode"`
}

type RedisConfig struct {
	Host     string `mapstructure:"host"`
	Port     int    `mapstructure:"port"`
	Password string `mapstructure:"password"`
	DB       int    `mapstructure:"db"`
}

type WorkerConfig struct {
	PoolSize           int           `mapstructure:"pool_size"`
	MaxConcurrentTasks int           `mapstructure:"max_concurrent_tasks"`
	TaskTimeout        time.Duration `mapstructure:"task_timeout"`
	PollInterval       time.Duration `mapstructure:"poll_interval"`
}

type TaskConfig struct {
	MaxRetryAttempts  int           `mapstructure:"max_retry_attempts"`
	RetryBackoffBase  time.Duration `mapstructure:"retry_backoff_base"`
	RetryBackoffMax   time.Duration `mapstructure:"retry_backoff_max"`
	DefaultPriority   string        `mapstructure:"default_priority"`
	QueuePrefix       string        `mapstructure:"queue_prefix"`
}

type MinIOConfig struct {
	Endpoint   string `mapstructure:"endpoint"`
	AccessKey  string `mapstructure:"access_key"`
	SecretKey  string `mapstructure:"secret_key"`
	BucketName string `mapstructure:"bucket_name"`
	UseSSL     bool   `mapstructure:"use_ssl"`
}

type UploadConfig struct {
	MaxFileSize       int64 `mapstructure:"max_file_size"`        // 最大文件大小(字节)
	MaxBatchSize      int   `mapstructure:"max_batch_size"`       // 批量上传最大文件数
	ConcurrencyLimit  int   `mapstructure:"concurrency_limit"`    // 并发上传限制
	RateLimit         int   `mapstructure:"rate_limit"`           // 每秒请求限制
	BurstLimit        int   `mapstructure:"burst_limit"`          // 突发请求限制
}

func Load() (*Config, error) {
	viper.SetConfigName("config")
	viper.SetConfigType("yaml")
	viper.AddConfigPath(".")
	viper.AddConfigPath("./config")
	viper.AddConfigPath("/etc/task-manager")

	// 设置默认值
	setDefaults()

	// 自动读取环境变量
	viper.AutomaticEnv()

	// 读取配置文件
	if err := viper.ReadInConfig(); err != nil {
		if _, ok := err.(viper.ConfigFileNotFoundError); !ok {
			return nil, fmt.Errorf("error reading config file: %w", err)
		}
	}

	var config Config
	if err := viper.Unmarshal(&config); err != nil {
		return nil, fmt.Errorf("error unmarshaling config: %w", err)
	}

	return &config, nil
}

func setDefaults() {
	// 服务配置
	viper.SetDefault("port", 8084)
	viper.SetDefault("grpc_port", 8085)
	viper.SetDefault("environment", "development")
	viper.SetDefault("log_level", "info")

	// 数据库配置
	viper.SetDefault("database.host", "localhost")
	viper.SetDefault("database.port", 5434)
	viper.SetDefault("database.user", "zzdsj_demo")
	viper.SetDefault("database.password", "zzdsj123")
	viper.SetDefault("database.database", "zzdsj_demo")
	viper.SetDefault("database.ssl_mode", "disable")

	// Redis配置
	viper.SetDefault("redis.host", "localhost")
	viper.SetDefault("redis.port", 6379)
	viper.SetDefault("redis.password", "")
	viper.SetDefault("redis.db", 1)

	// 工作进程配置
	viper.SetDefault("worker.pool_size", 10)
	viper.SetDefault("worker.max_concurrent_tasks", 50)
	viper.SetDefault("worker.task_timeout", "5m")
	viper.SetDefault("worker.poll_interval", "1s")

	// 任务配置
	viper.SetDefault("task.max_retry_attempts", 3)
	viper.SetDefault("task.retry_backoff_base", "1s")
	viper.SetDefault("task.retry_backoff_max", "60s")
	viper.SetDefault("task.default_priority", "normal")
	viper.SetDefault("task.queue_prefix", "task_queue")

	// MinIO配置
	viper.SetDefault("minio.endpoint", "localhost:9000")
	viper.SetDefault("minio.access_key", "minioadmin")
	viper.SetDefault("minio.secret_key", "minioadmin")
	viper.SetDefault("minio.bucket_name", "zzdsl-documents")
	viper.SetDefault("minio.use_ssl", false)

	// 文件上传配置
	viper.SetDefault("upload.max_file_size", 100*1024*1024) // 100MB
	viper.SetDefault("upload.max_batch_size", 20)           // 20个文件
	viper.SetDefault("upload.concurrency_limit", 10)        // 10个并发上传
	viper.SetDefault("upload.rate_limit", 100)              // 每秒100个请求
	viper.SetDefault("upload.burst_limit", 200)             // 突发200个请求
}

func (c *Config) GetDatabaseDSN() string {
	return fmt.Sprintf("host=%s port=%d user=%s password=%s dbname=%s sslmode=%s",
		c.Database.Host,
		c.Database.Port,
		c.Database.User,
		c.Database.Password,
		c.Database.Database,
		c.Database.SSLMode,
	)
}

func (c *Config) GetRedisAddr() string {
	return fmt.Sprintf("%s:%d", c.Redis.Host, c.Redis.Port)
}