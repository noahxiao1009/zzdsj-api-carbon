package redis

import (
	"context"
	"fmt"
	"time"

	"github.com/go-redis/redis/v8"
	"github.com/sirupsen/logrus"

	"task-manager-service/internal/config"
)

// Connect 连接Redis
func Connect(cfg config.RedisConfig) (*redis.Client, error) {
	rdb := redis.NewClient(&redis.Options{
		Addr:         fmt.Sprintf("%s:%d", cfg.Host, cfg.Port),
		Password:     cfg.Password,
		DB:           cfg.DB,
		PoolSize:     10,
		MinIdleConns: 2,
		MaxRetries:   3,
		DialTimeout:  5 * time.Second,
		ReadTimeout:  3 * time.Second,
		WriteTimeout: 3 * time.Second,
		PoolTimeout:  4 * time.Second,
		IdleTimeout:  5 * time.Minute,
	})

	// 测试连接
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := rdb.Ping(ctx).Err(); err != nil {
		rdb.Close()
		return nil, fmt.Errorf("failed to ping Redis: %w", err)
	}

	logrus.Info("✓ Redis connected successfully")
	return rdb, nil
}

// HealthCheck Redis健康检查
func HealthCheck(rdb *redis.Client) error {
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()

	if err := rdb.Ping(ctx).Err(); err != nil {
		return fmt.Errorf("redis ping failed: %w", err)
	}

	// 测试基本操作
	testKey := "health_check_test"
	if err := rdb.Set(ctx, testKey, "ok", time.Second).Err(); err != nil {
		return fmt.Errorf("redis set operation failed: %w", err)
	}

	val, err := rdb.Get(ctx, testKey).Result()
	if err != nil {
		return fmt.Errorf("redis get operation failed: %w", err)
	}

	if val != "ok" {
		return fmt.Errorf("redis data integrity check failed")
	}

	// 清理测试key
	rdb.Del(ctx, testKey)

	return nil
}

// GetRedisStats 获取Redis统计信息
func GetRedisStats(rdb *redis.Client) (map[string]interface{}, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()

	stats := make(map[string]interface{})

	// 连接池统计
	poolStats := rdb.PoolStats()
	stats["connection_pool"] = map[string]interface{}{
		"total_conns": poolStats.TotalConns,
		"idle_conns":  poolStats.IdleConns,
		"stale_conns": poolStats.StaleConns,
		"hits":        poolStats.Hits,
		"misses":      poolStats.Misses,
		"timeouts":    poolStats.Timeouts,
	}

	// Redis信息
	info, err := rdb.Info(ctx, "memory", "stats", "keyspace").Result()
	if err != nil {
		logrus.Warnf("Failed to get Redis info: %v", err)
	} else {
		stats["redis_info"] = info
	}

	// 队列统计
	queueStats := make(map[string]interface{})
	priorities := []string{"critical", "high", "normal", "low"}
	
	for _, priority := range priorities {
		queueKey := fmt.Sprintf("task_queue:%s", priority)
		length, err := rdb.LLen(ctx, queueKey).Result()
		if err != nil {
			logrus.Warnf("Failed to get queue length for %s: %v", priority, err)
			continue
		}
		queueStats[priority] = length
	}
	stats["queue_lengths"] = queueStats

	return stats, nil
}

// ClearQueues 清空所有任务队列 (用于测试或重置)
func ClearQueues(rdb *redis.Client, queuePrefix string) error {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	priorities := []string{"critical", "high", "normal", "low"}
	
	for _, priority := range priorities {
		queueKey := fmt.Sprintf("%s:%s", queuePrefix, priority)
		
		if err := rdb.Del(ctx, queueKey).Err(); err != nil {
			logrus.Warnf("Failed to clear queue %s: %v", queueKey, err)
		} else {
			logrus.Infof("Queue cleared: %s", queueKey)
		}
	}

	return nil
}

// GetQueueSizes 获取所有队列大小
func GetQueueSizes(rdb *redis.Client, queuePrefix string) (map[string]int64, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	sizes := make(map[string]int64)
	priorities := []string{"critical", "high", "normal", "low"}
	
	for _, priority := range priorities {
		queueKey := fmt.Sprintf("%s:%s", queuePrefix, priority)
		
		length, err := rdb.LLen(ctx, queueKey).Result()
		if err != nil {
			logrus.Warnf("Failed to get queue size for %s: %v", priority, err)
			sizes[priority] = 0
		} else {
			sizes[priority] = length
		}
	}

	return sizes, nil
}

// CleanupWorkerData 清理工作进程数据
func CleanupWorkerData(rdb *redis.Client) error {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	// 删除所有worker相关的key
	pattern := "worker:*"
	keys, err := rdb.Keys(ctx, pattern).Result()
	if err != nil {
		return fmt.Errorf("failed to get worker keys: %w", err)
	}

	if len(keys) > 0 {
		if err := rdb.Del(ctx, keys...).Err(); err != nil {
			return fmt.Errorf("failed to delete worker keys: %w", err)
		}
		logrus.Infof("Cleaned up %d worker data entries", len(keys))
	}

	return nil
}

// SetWorkerHeartbeat 设置工作进程心跳
func SetWorkerHeartbeat(rdb *redis.Client, workerID string, data map[string]interface{}) error {
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()

	key := fmt.Sprintf("worker:%s", workerID)
	
	// 设置心跳数据
	if err := rdb.HMSet(ctx, key, data).Err(); err != nil {
		return fmt.Errorf("failed to set worker heartbeat: %w", err)
	}

	// 设置过期时间
	if err := rdb.Expire(ctx, key, 5*time.Minute).Err(); err != nil {
		return fmt.Errorf("failed to set worker heartbeat expiration: %w", err)
	}

	return nil
}

// GetAllWorkers 获取所有活跃工作进程
func GetAllWorkers(rdb *redis.Client) (map[string]map[string]string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	pattern := "worker:*"
	keys, err := rdb.Keys(ctx, pattern).Result()
	if err != nil {
		return nil, fmt.Errorf("failed to get worker keys: %w", err)
	}

	workers := make(map[string]map[string]string)
	
	for _, key := range keys {
		data, err := rdb.HGetAll(ctx, key).Result()
		if err != nil {
			logrus.Warnf("Failed to get worker data for %s: %v", key, err)
			continue
		}
		
		workerID := key[7:] // 移除 "worker:" 前缀
		workers[workerID] = data
	}

	return workers, nil
}

// IsQueueEmpty 检查队列是否为空
func IsQueueEmpty(rdb *redis.Client, queueKey string) (bool, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	length, err := rdb.LLen(ctx, queueKey).Result()
	if err != nil {
		return false, fmt.Errorf("failed to check queue length: %w", err)
	}

	return length == 0, nil
}

// PushToQueue 将任务推入队列
func PushToQueue(rdb *redis.Client, queueKey, taskID string) error {
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()

	return rdb.LPush(ctx, queueKey, taskID).Err()
}

// PopFromQueue 从队列中取出任务 (非阻塞)
func PopFromQueue(rdb *redis.Client, queueKey string) (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()

	result, err := rdb.RPop(ctx, queueKey).Result()
	if err != nil {
		if err == redis.Nil {
			return "", nil // 队列为空
		}
		return "", err
	}

	return result, nil
}

// BlockingPopFromQueue 从队列中取出任务 (阻塞)
func BlockingPopFromQueue(rdb *redis.Client, queueKey string, timeout time.Duration) (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), timeout+time.Second)
	defer cancel()

	result, err := rdb.BRPop(ctx, timeout, queueKey).Result()
	if err != nil {
		if err == redis.Nil {
			return "", nil // 超时
		}
		return "", err
	}

	if len(result) < 2 {
		return "", fmt.Errorf("invalid queue result")
	}

	return result[1], nil
}