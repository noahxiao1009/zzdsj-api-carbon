package storage

import (
	"context"
	"fmt"
	"strconv"
	"time"

	"github.com/go-redis/redis/v8"
	log "github.com/sirupsen/logrus"

	"vector-processing-service/internal/config"
)

// RedisClient Redis客户端
type RedisClient struct {
	client *redis.Client
	config *config.RedisConfig
}

// NewRedisClient 创建Redis客户端
func NewRedisClient(cfg *config.RedisConfig) (*RedisClient, error) {
	log.WithFields(log.Fields{
		"host": cfg.Host,
		"port": cfg.Port,
		"db":   cfg.DB,
	}).Info("初始化Redis客户端")

	// Redis客户端配置
	rdb := redis.NewClient(&redis.Options{
		Addr:     fmt.Sprintf("%s:%d", cfg.Host, cfg.Port),
		Password: cfg.Password,
		DB:       cfg.DB,
		
		// 连接池配置
		PoolSize:     cfg.Pool.MaxActive,
		MinIdleConns: cfg.Pool.MaxIdle,
		IdleTimeout:  cfg.Pool.IdleTimeout,
		
		// 连接超时配置
		DialTimeout:  5 * time.Second,
		ReadTimeout:  3 * time.Second,
		WriteTimeout: 3 * time.Second,
	})

	// 测试连接
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := rdb.Ping(ctx).Err(); err != nil {
		return nil, fmt.Errorf("Redis连接测试失败: %w", err)
	}

	client := &RedisClient{
		client: rdb,
		config: cfg,
	}

	log.Info("Redis客户端初始化成功")
	return client, nil
}

// Set 设置键值
func (r *RedisClient) Set(ctx context.Context, key string, value interface{}, expiration time.Duration) error {
	return r.client.Set(ctx, key, value, expiration).Err()
}

// Get 获取值
func (r *RedisClient) Get(ctx context.Context, key string) (string, error) {
	return r.client.Get(ctx, key).Result()
}

// HSet 设置哈希字段
func (r *RedisClient) HSet(ctx context.Context, key string, field string, value interface{}) error {
	return r.client.HSet(ctx, key, field, value).Err()
}

// HGet 获取哈希字段
func (r *RedisClient) HGet(ctx context.Context, key string, field string) (string, error) {
	return r.client.HGet(ctx, key, field).Result()
}

// HMSet 批量设置哈希字段
func (r *RedisClient) HMSet(ctx context.Context, key string, values map[string]interface{}, expiration time.Duration) error {
	pipe := r.client.TxPipeline()
	pipe.HMSet(ctx, key, values)
	if expiration > 0 {
		pipe.Expire(ctx, key, expiration)
	}
	_, err := pipe.Exec(ctx)
	return err
}

// HGetAll 获取所有哈希字段
func (r *RedisClient) HGetAll(ctx context.Context, key string) (map[string]string, error) {
	return r.client.HGetAll(ctx, key).Result()
}

// Del 删除键
func (r *RedisClient) Del(ctx context.Context, keys ...string) error {
	return r.client.Del(ctx, keys...).Err()
}

// Exists 检查键是否存在
func (r *RedisClient) Exists(ctx context.Context, keys ...string) (int64, error) {
	return r.client.Exists(ctx, keys...).Result()
}

// Expire 设置过期时间
func (r *RedisClient) Expire(ctx context.Context, key string, expiration time.Duration) error {
	return r.client.Expire(ctx, key, expiration).Err()
}

// TTL 获取剩余过期时间
func (r *RedisClient) TTL(ctx context.Context, key string) (time.Duration, error) {
	return r.client.TTL(ctx, key).Result()
}

// LPush 从左侧推入列表
func (r *RedisClient) LPush(ctx context.Context, key string, values ...interface{}) error {
	return r.client.LPush(ctx, key, values...).Err()
}

// RPop 从右侧弹出列表
func (r *RedisClient) RPop(ctx context.Context, key string) (string, error) {
	return r.client.RPop(ctx, key).Result()
}

// BRPop 阻塞式从右侧弹出列表
func (r *RedisClient) BRPop(ctx context.Context, timeout time.Duration, keys ...string) ([]string, error) {
	return r.client.BRPop(ctx, timeout, keys...).Result()
}

// LLen 获取列表长度
func (r *RedisClient) LLen(ctx context.Context, key string) (int64, error) {
	return r.client.LLen(ctx, key).Result()
}

// SAdd 添加到集合
func (r *RedisClient) SAdd(ctx context.Context, key string, members ...interface{}) error {
	return r.client.SAdd(ctx, key, members...).Err()
}

// SMembers 获取集合所有成员
func (r *RedisClient) SMembers(ctx context.Context, key string) ([]string, error) {
	return r.client.SMembers(ctx, key).Result()
}

// SIsMember 检查是否是集合成员
func (r *RedisClient) SIsMember(ctx context.Context, key string, member interface{}) (bool, error) {
	return r.client.SIsMember(ctx, key, member).Result()
}

// ZAdd 添加到有序集合
func (r *RedisClient) ZAdd(ctx context.Context, key string, members ...*redis.Z) error {
	return r.client.ZAdd(ctx, key, members...).Err()
}

// ZRange 获取有序集合范围
func (r *RedisClient) ZRange(ctx context.Context, key string, start, stop int64) ([]string, error) {
	return r.client.ZRange(ctx, key, start, stop).Result()
}

// ZRangeWithScores 获取有序集合范围（带分数）
func (r *RedisClient) ZRangeWithScores(ctx context.Context, key string, start, stop int64) ([]redis.Z, error) {
	return r.client.ZRangeWithScores(ctx, key, start, stop).Result()
}

// Incr 增加计数
func (r *RedisClient) Incr(ctx context.Context, key string) (int64, error) {
	return r.client.Incr(ctx, key).Result()
}

// IncrBy 按指定值增加
func (r *RedisClient) IncrBy(ctx context.Context, key string, value int64) (int64, error) {
	return r.client.IncrBy(ctx, key, value).Result()
}

// Decr 减少计数
func (r *RedisClient) Decr(ctx context.Context, key string) (int64, error) {
	return r.client.Decr(ctx, key).Result()
}

// Keys 获取匹配的键
func (r *RedisClient) Keys(ctx context.Context, pattern string) ([]string, error) {
	return r.client.Keys(ctx, pattern).Result()
}

// Ping 测试连接
func (r *RedisClient) Ping(ctx context.Context) error {
	return r.client.Ping(ctx).Err()
}

// FlushDB 清空当前数据库
func (r *RedisClient) FlushDB(ctx context.Context) error {
	return r.client.FlushDB(ctx).Err()
}

// GetStats 获取Redis统计信息
func (r *RedisClient) GetStats(ctx context.Context) (*RedisStats, error) {
	info, err := r.client.Info(ctx, "stats", "memory", "clients").Result()
	if err != nil {
		return nil, fmt.Errorf("获取Redis信息失败: %w", err)
	}

	stats := &RedisStats{
		Connected: true,
	}

	// 解析统计信息（简化实现）
	// 实际应该解析INFO命令的返回结果
	
	// 获取连接数
	if poolStats := r.client.PoolStats(); poolStats != nil {
		stats.TotalConnections = int(poolStats.TotalConns)
	}

	// 获取键空间统计
	dbSize, err := r.client.DBSize(ctx).Result()
	if err == nil {
		stats.TotalKeys = dbSize
	}

	return stats, nil
}

// Pipeline 创建管道
func (r *RedisClient) Pipeline() redis.Pipeliner {
	return r.client.Pipeline()
}

// TxPipeline 创建事务管道
func (r *RedisClient) TxPipeline() redis.Pipeliner {
	return r.client.TxPipeline()
}

// Close 关闭连接
func (r *RedisClient) Close() error {
	if r.client != nil {
		err := r.client.Close()
		if err != nil {
			log.WithError(err).Error("关闭Redis连接失败")
			return err
		}
		log.Info("Redis连接已关闭")
	}
	return nil
}

// GetClient 获取原生客户端（用于复杂操作）
func (r *RedisClient) GetClient() *redis.Client {
	return r.client
}

// ExecuteLua 执行Lua脚本
func (r *RedisClient) ExecuteLua(ctx context.Context, script string, keys []string, args ...interface{}) (interface{}, error) {
	return r.client.Eval(ctx, script, keys, args...).Result()
}

// Lock 分布式锁
func (r *RedisClient) Lock(ctx context.Context, key string, expiration time.Duration) (bool, error) {
	result, err := r.client.SetNX(ctx, key, "locked", expiration).Result()
	if err != nil {
		return false, fmt.Errorf("获取分布式锁失败: %w", err)
	}
	return result, nil
}

// Unlock 释放分布式锁
func (r *RedisClient) Unlock(ctx context.Context, key string) error {
	// 使用Lua脚本确保原子性
	script := `
		if redis.call("GET", KEYS[1]) == ARGV[1] then
			return redis.call("DEL", KEYS[1])
		else
			return 0
		end
	`
	_, err := r.client.Eval(ctx, script, []string{key}, "locked").Result()
	return err
}

// SetWithLock 带锁的设置操作
func (r *RedisClient) SetWithLock(ctx context.Context, key string, value interface{}, lockKey string, expiration time.Duration) error {
	// 获取锁
	lockCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()

	locked, err := r.Lock(lockCtx, lockKey, 10*time.Second)
	if err != nil {
		return err
	}
	if !locked {
		return fmt.Errorf("获取锁失败: %s", lockKey)
	}

	// 释放锁
	defer func() {
		if unlockErr := r.Unlock(context.Background(), lockKey); unlockErr != nil {
			log.WithError(unlockErr).WithField("lock_key", lockKey).Error("释放锁失败")
		}
	}()

	// 执行设置操作
	return r.Set(ctx, key, value, expiration)
}

// BatchGet 批量获取
func (r *RedisClient) BatchGet(ctx context.Context, keys []string) (map[string]string, error) {
	if len(keys) == 0 {
		return make(map[string]string), nil
	}

	pipe := r.client.Pipeline()
	cmds := make([]*redis.StringCmd, len(keys))
	
	for i, key := range keys {
		cmds[i] = pipe.Get(ctx, key)
	}

	_, err := pipe.Exec(ctx)
	if err != nil && err != redis.Nil {
		return nil, fmt.Errorf("批量获取失败: %w", err)
	}

	result := make(map[string]string)
	for i, cmd := range cmds {
		val, err := cmd.Result()
		if err != nil && err != redis.Nil {
			continue
		}
		if err != redis.Nil {
			result[keys[i]] = val
		}
	}

	return result, nil
}

// BatchSet 批量设置
func (r *RedisClient) BatchSet(ctx context.Context, pairs map[string]interface{}, expiration time.Duration) error {
	if len(pairs) == 0 {
		return nil
	}

	pipe := r.client.TxPipeline()
	
	for key, value := range pairs {
		pipe.Set(ctx, key, value, expiration)
	}

	_, err := pipe.Exec(ctx)
	return err
}