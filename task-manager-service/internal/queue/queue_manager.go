package queue

import (
	"context"
	"encoding/json"
	"sync"
	"time"

	"github.com/redis/go-redis/v9"
	"github.com/sirupsen/logrus"

	"task-manager-service/internal/config"
	"task-manager-service/internal/model"
)

// QueueManager 队列管理器
type QueueManager struct {
	taskQueue        *TaskQueue
	config           *config.Config
	log              *logrus.Entry
	schedulerRunning bool
	schedulerStop    chan struct{}
	mu               sync.RWMutex
}

// NewQueueManager 创建队列管理器
func NewQueueManager(redisClient *redis.Client, cfg *config.Config) *QueueManager {
	taskQueue := NewTaskQueue(redisClient, cfg.Task.QueuePrefix)
	
	return &QueueManager{
		taskQueue:     taskQueue,
		config:        cfg,
		log:           logrus.WithField("component", "queue-manager"),
		schedulerStop: make(chan struct{}),
	}
}

// Start 启动队列管理器
func (qm *QueueManager) Start(ctx context.Context) error {
	qm.mu.Lock()
	defer qm.mu.Unlock()

	if qm.schedulerRunning {
		return nil
	}

	// 启动调度任务处理器
	go qm.runScheduledTaskProcessor(ctx)
	
	// 启动过期任务清理器
	go qm.runExpiredTaskCleaner(ctx)

	qm.schedulerRunning = true
	qm.log.Info("Queue manager started successfully")
	
	return nil
}

// Stop 停止队列管理器
func (qm *QueueManager) Stop() error {
	qm.mu.Lock()
	defer qm.mu.Unlock()

	if !qm.schedulerRunning {
		return nil
	}

	close(qm.schedulerStop)
	qm.schedulerRunning = false
	qm.log.Info("Queue manager stopped")
	
	return nil
}

// PushTask 推送任务到队列
func (qm *QueueManager) PushTask(ctx context.Context, task *model.Task) error {
	return qm.taskQueue.PushTask(ctx, task)
}

// PopTask 从队列弹出任务
func (qm *QueueManager) PopTask(ctx context.Context, taskTypes []model.TaskType, timeout time.Duration) (*TaskMessage, error) {
	return qm.taskQueue.PopTask(ctx, taskTypes, timeout)
}

// CompleteTask 标记任务完成
func (qm *QueueManager) CompleteTask(ctx context.Context, taskID string, taskType model.TaskType) error {
	return qm.taskQueue.CompleteTask(ctx, taskID, taskType)
}

// FailTask 标记任务失败
func (qm *QueueManager) FailTask(ctx context.Context, taskID string, taskType model.TaskType, shouldRetry bool, taskMsg *TaskMessage) error {
	return qm.taskQueue.FailTask(ctx, taskID, taskType, shouldRetry, taskMsg)
}

// GetQueueInfo 获取队列信息
func (qm *QueueManager) GetQueueInfo(ctx context.Context, taskType model.TaskType) (*QueueInfo, error) {
	return qm.taskQueue.GetQueueInfo(ctx, taskType)
}

// GetAllQueueInfo 获取所有队列信息
func (qm *QueueManager) GetAllQueueInfo(ctx context.Context) (map[string]*QueueInfo, error) {
	return qm.taskQueue.GetAllQueueInfo(ctx)
}

// GetQueueStats 获取队列统计信息
func (qm *QueueManager) GetQueueStats(ctx context.Context) (map[string]interface{}, error) {
	allInfo, err := qm.GetAllQueueInfo(ctx)
	if err != nil {
		return nil, err
	}

	stats := map[string]interface{}{
		"total_queues": len(allInfo),
		"queues":       allInfo,
	}

	// 计算总体统计
	totalQueued := int64(0)
	totalProcessing := int64(0)
	totalCompleted := int64(0)
	totalFailed := int64(0)

	for _, info := range allInfo {
		totalQueued += info.Length
		totalProcessing += info.Processing
		totalCompleted += info.Completed
		totalFailed += info.Failed
	}

	stats["summary"] = map[string]int64{
		"total_queued":    totalQueued,
		"total_processing": totalProcessing,
		"total_completed": totalCompleted,
		"total_failed":    totalFailed,
	}

	return stats, nil
}

// PurgeFailedTasks 清除失败任务
func (qm *QueueManager) PurgeFailedTasks(ctx context.Context, taskType model.TaskType, maxAge time.Duration) error {
	failedKey := qm.taskQueue.getFailedKey(taskType)
	
	// 获取失败队列中的任务
	tasks, err := qm.taskQueue.client.LRange(ctx, failedKey, 0, -1).Result()
	if err != nil {
		return err
	}

	cutoffTime := time.Now().Add(-maxAge)
	purgedCount := 0

	for _, taskData := range tasks {
		var taskMsg TaskMessage
		if err := json.Unmarshal([]byte(taskData), &taskMsg); err != nil {
			continue
		}

		// 检查任务是否超过最大年龄
		if taskMsg.CreatedAt.Before(cutoffTime) {
			// 移除过期的失败任务
			removed, err := qm.taskQueue.client.LRem(ctx, failedKey, 1, taskData).Result()
			if err != nil {
				qm.log.Errorf("Failed to remove failed task %s: %v", taskMsg.TaskID, err)
				continue
			}
			
			if removed > 0 {
				purgedCount++
			}
		}
	}

	qm.log.Infof("Purged %d failed tasks from queue %s", purgedCount, taskType)
	return nil
}

// RetryFailedTasks 重试失败任务
func (qm *QueueManager) RetryFailedTasks(ctx context.Context, taskType model.TaskType, maxRetries int) error {
	failedKey := qm.taskQueue.getFailedKey(taskType)
	
	// 获取失败队列中的任务
	tasks, err := qm.taskQueue.client.LRange(ctx, failedKey, 0, -1).Result()
	if err != nil {
		return err
	}

	retriedCount := 0

	for _, taskData := range tasks {
		var taskMsg TaskMessage
		if err := json.Unmarshal([]byte(taskData), &taskMsg); err != nil {
			continue
		}

		// 检查是否可以重试
		if taskMsg.Attempts < maxRetries {
			// 从失败队列移除
			removed, err := qm.taskQueue.client.LRem(ctx, failedKey, 1, taskData).Result()
			if err != nil {
				qm.log.Errorf("Failed to remove failed task %s: %v", taskMsg.TaskID, err)
				continue
			}

			if removed > 0 {
				// 重新推入队列
				queueKey := qm.taskQueue.getQueueKey(taskMsg.TaskType, taskMsg.Priority)
				err = qm.taskQueue.client.RPush(ctx, queueKey, taskData).Err()
				if err != nil {
					qm.log.Errorf("Failed to requeue failed task %s: %v", taskMsg.TaskID, err)
					continue
				}
				
				retriedCount++
			}
		}
	}

	qm.log.Infof("Retried %d failed tasks from queue %s", retriedCount, taskType)
	return nil
}

// GetTaskPosition 获取任务在队列中的位置
func (qm *QueueManager) GetTaskPosition(ctx context.Context, taskID string, taskType model.TaskType, priority model.TaskPriority) (int, error) {
	queueKey := qm.taskQueue.getQueueKey(taskType, priority)
	
	// 获取队列中的所有任务
	tasks, err := qm.taskQueue.client.LRange(ctx, queueKey, 0, -1).Result()
	if err != nil {
		return -1, err
	}

	// 查找任务位置
	for i, taskData := range tasks {
		var taskMsg TaskMessage
		if err := json.Unmarshal([]byte(taskData), &taskMsg); err != nil {
			continue
		}

		if taskMsg.TaskID == taskID {
			return i + 1, nil // 返回1基索引
		}
	}

	return -1, nil // 未找到
}

// 私有方法

// runScheduledTaskProcessor 运行调度任务处理器
func (qm *QueueManager) runScheduledTaskProcessor(ctx context.Context) {
	ticker := time.NewTicker(10 * time.Second) // 每10秒检查一次
	defer ticker.Stop()

	qm.log.Info("Scheduled task processor started")

	for {
		select {
		case <-ctx.Done():
			qm.log.Info("Scheduled task processor stopped due to context cancellation")
			return
		case <-qm.schedulerStop:
			qm.log.Info("Scheduled task processor stopped")
			return
		case <-ticker.C:
			err := qm.taskQueue.ProcessScheduledTasks(ctx)
			if err != nil {
				qm.log.Errorf("Failed to process scheduled tasks: %v", err)
			}
		}
	}
}

// runExpiredTaskCleaner 运行过期任务清理器
func (qm *QueueManager) runExpiredTaskCleaner(ctx context.Context) {
	ticker := time.NewTicker(5 * time.Minute) // 每5分钟清理一次
	defer ticker.Stop()

	qm.log.Info("Expired task cleaner started")

	for {
		select {
		case <-ctx.Done():
			qm.log.Info("Expired task cleaner stopped due to context cancellation")
			return
		case <-qm.schedulerStop:
			qm.log.Info("Expired task cleaner stopped")
			return
		case <-ticker.C:
			// 清理超过1小时的过期任务
			maxAge := 1 * time.Hour
			err := qm.taskQueue.CleanExpiredTasks(ctx, maxAge)
			if err != nil {
				qm.log.Errorf("Failed to clean expired tasks: %v", err)
			}
		}
	}
}

// Health 健康检查
func (qm *QueueManager) Health(ctx context.Context) (bool, map[string]interface{}) {
	details := make(map[string]interface{})
	healthy := true

	// 检查Redis连接
	_, err := qm.taskQueue.client.Ping(ctx).Result()
	if err != nil {
		healthy = false
		details["redis"] = map[string]interface{}{
			"status": "unhealthy",
			"error":  err.Error(),
		}
	} else {
		details["redis"] = map[string]interface{}{
			"status": "healthy",
		}
	}

	// 检查调度器状态
	qm.mu.RLock()
	schedulerRunning := qm.schedulerRunning
	qm.mu.RUnlock()

	details["scheduler"] = map[string]interface{}{
		"running": schedulerRunning,
	}

	if !schedulerRunning {
		healthy = false
	}

	// 获取队列统计
	stats, err := qm.GetQueueStats(ctx)
	if err != nil {
		qm.log.Errorf("Failed to get queue stats for health check: %v", err)
		details["queue_stats"] = map[string]interface{}{
			"status": "error",
			"error":  err.Error(),
		}
	} else {
		details["queue_stats"] = stats
	}

	return healthy, details
}