package database

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	_ "github.com/lib/pq"
	"github.com/sirupsen/logrus"

	"task-manager-service/internal/config"
)

// Connect 连接PostgreSQL数据库
func Connect(cfg config.DatabaseConfig) (*sql.DB, error) {
	dsn := fmt.Sprintf("host=%s port=%d user=%s password=%s dbname=%s sslmode=%s",
		cfg.Host, cfg.Port, cfg.User, cfg.Password, cfg.Database, cfg.SSLMode)

	db, err := sql.Open("postgres", dsn)
	if err != nil {
		return nil, fmt.Errorf("failed to open database connection: %w", err)
	}

	// 配置连接池
	db.SetMaxOpenConns(25)
	db.SetMaxIdleConns(5)
	db.SetConnMaxLifetime(time.Hour)

	// 测试连接
	if err := db.Ping(); err != nil {
		db.Close()
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	// 创建表结构
	if err := createTables(db); err != nil {
		db.Close()
		return nil, fmt.Errorf("failed to create tables: %w", err)
	}

	logrus.Info("✓ Database connected and initialized successfully")
	return db, nil
}

// createTables 创建数据库表
func createTables(db *sql.DB) error {
	// 创建任务表
	tasksTable := `
	CREATE TABLE IF NOT EXISTS tasks (
		id VARCHAR(36) PRIMARY KEY,
		task_type VARCHAR(50) NOT NULL,
		status VARCHAR(20) NOT NULL DEFAULT 'queued',
		priority VARCHAR(20) NOT NULL DEFAULT 'normal',
		kb_id VARCHAR(36) NOT NULL,
		payload JSONB NOT NULL DEFAULT '{}',
		result JSONB NOT NULL DEFAULT '{}',
		progress INTEGER NOT NULL DEFAULT 0,
		retry_count INTEGER NOT NULL DEFAULT 0,
		max_retries INTEGER NOT NULL DEFAULT 3,
		error_message TEXT DEFAULT '',
		worker_id VARCHAR(36) DEFAULT '',
		timeout INTEGER NOT NULL DEFAULT 300,
		created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
		updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
		started_at TIMESTAMP WITH TIME ZONE,
		completed_at TIMESTAMP WITH TIME ZONE,
		scheduled_for TIMESTAMP WITH TIME ZONE
	);
	`

	if _, err := db.Exec(tasksTable); err != nil {
		return fmt.Errorf("failed to create tasks table: %w", err)
	}

	// 创建索引
	indexes := []string{
		"CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);",
		"CREATE INDEX IF NOT EXISTS idx_tasks_kb_id ON tasks(kb_id);",
		"CREATE INDEX IF NOT EXISTS idx_tasks_task_type ON tasks(task_type);",
		"CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority);",
		"CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);",
		"CREATE INDEX IF NOT EXISTS idx_tasks_scheduled_for ON tasks(scheduled_for);",
		"CREATE INDEX IF NOT EXISTS idx_tasks_worker_id ON tasks(worker_id);",
		"CREATE INDEX IF NOT EXISTS idx_tasks_status_priority ON tasks(status, priority);",
		"CREATE INDEX IF NOT EXISTS idx_tasks_kb_id_status ON tasks(kb_id, status);",
	}

	for _, index := range indexes {
		if _, err := db.Exec(index); err != nil {
			logrus.Warnf("Failed to create index: %v", err)
		}
	}

	logrus.Info("✓ Database tables and indexes created successfully")
	return nil
}

// HealthCheck 数据库健康检查
func HealthCheck(db *sql.DB) error {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := db.PingContext(ctx); err != nil {
		return fmt.Errorf("database ping failed: %w", err)
	}

	// 测试简单查询
	var count int
	err := db.QueryRowContext(ctx, "SELECT COUNT(*) FROM tasks WHERE 1=0").Scan(&count)
	if err != nil {
		return fmt.Errorf("database query test failed: %w", err)
	}

	return nil
}

// GetDatabaseStats 获取数据库统计信息
func GetDatabaseStats(db *sql.DB) (map[string]interface{}, error) {
	stats := make(map[string]interface{})
	
	// 连接池统计
	dbStats := db.Stats()
	stats["connection_pool"] = map[string]interface{}{
		"max_open_connections":     dbStats.MaxOpenConnections,
		"open_connections":         dbStats.OpenConnections,
		"in_use":                  dbStats.InUse,
		"idle":                    dbStats.Idle,
		"wait_count":              dbStats.WaitCount,
		"wait_duration":           dbStats.WaitDuration.String(),
		"max_idle_closed":         dbStats.MaxIdleClosed,
		"max_idle_time_closed":    dbStats.MaxIdleTimeClosed,
		"max_lifetime_closed":     dbStats.MaxLifetimeClosed,
	}

	// 表统计
	var totalTasks int64
	err := db.QueryRow("SELECT COUNT(*) FROM tasks").Scan(&totalTasks)
	if err != nil {
		logrus.Warnf("Failed to get tasks count: %v", err)
	} else {
		stats["total_tasks"] = totalTasks
	}

	// 表大小 (PostgreSQL specific)
	var tableSize string
	err = db.QueryRow("SELECT pg_size_pretty(pg_total_relation_size('tasks'))").Scan(&tableSize)
	if err != nil {
		logrus.Warnf("Failed to get table size: %v", err)
	} else {
		stats["table_size"] = tableSize
	}

	return stats, nil
}