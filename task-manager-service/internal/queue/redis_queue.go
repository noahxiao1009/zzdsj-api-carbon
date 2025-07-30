package queue

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"
	"github.com/sirupsen/logrus"

	"task-manager-service/internal/model"
)

// TaskQueue Redis任务队列管理器
type TaskQueue struct {
	client      *redis.Client
	queuePrefix string
	log         *logrus.Entry
}

// QueueInfo 队列信息
type QueueInfo struct {
	QueueName   string `json:"queue_name"`
	Length      int64  `json:"length"`
	Processing  int64  `json:"processing"`
	Failed      int64  `json:"failed"`
	Completed   int64  `json:"completed"`
}

// TaskMessage 任务消息结构
type TaskMessage struct {
	TaskID    string          `json:"task_id"`
	TaskType  model.TaskType  `json:"task_type"`
	Priority  model.TaskPriority `json:"priority"`
	Payload   model.JSONMap   `json:"payload"`
	CreatedAt time.Time       `json:"created_at"`
	Attempts  int             `json:"attempts"`
	MaxRetries int            `json:"max_retries"`
}

// NewTaskQueue 创建任务队列管理器
func NewTaskQueue(client *redis.Client, queuePrefix string) *TaskQueue {
	return &TaskQueue{
		client:      client,
		queuePrefix: queuePrefix,
		log:         logrus.WithField("component", "task-queue"),
	}
}

// PushTask 推送任务到队列
func (tq *TaskQueue) PushTask(ctx context.Context, task *model.Task) error {
	queueKey := tq.getQueueKey(task.TaskType, task.Priority)
	
	// 创建任务消息
	taskMsg := &TaskMessage{
		TaskID:     task.ID,
		TaskType:   task.TaskType,
		Priority:   task.Priority,
		Payload:    task.Payload,
		CreatedAt:  task.CreatedAt,
		Attempts:   task.RetryCount,
		MaxRetries: task.MaxRetries,
	}

	// 序列化任务消息
	msgData, err := json.Marshal(taskMsg)
	if err != nil {
		return fmt.Errorf("failed to marshal task message: %w", err)
	}

	// 根据优先级选择推送方式
	var cmd *redis.IntCmd
	switch task.Priority {
	case model.TaskPriorityCritical, model.TaskPriorityHigh:
		// 高优先级任务推到队列头部
		cmd = tq.client.LPush(ctx, queueKey, msgData)
	default:
		// 普通和低优先级任务推到队列尾部
		cmd = tq.client.RPush(ctx, queueKey, msgData)
	}

	if err := cmd.Err(); err != nil {
		return fmt.Errorf("failed to push task to queue: %w", err)
	}

	// 记录队列统计
	err = tq.updateQueueStats(ctx, task.TaskType, "queued", 1)
	if err != nil {
		tq.log.Errorf("Failed to update queue stats: %v", err)
	}

	tq.log.Infof("Task %s pushed to queue %s", task.ID, queueKey)
	return nil
}

// PopTask 从队列弹出任务
func (tq *TaskQueue) PopTask(ctx context.Context, taskTypes []model.TaskType, timeout time.Duration) (*TaskMessage, error) {
	// 构建所有队列键
	queueKeys := make([]string, 0)
	
	// 按优先级顺序构建队列键
	priorities := []model.TaskPriority{
		model.TaskPriorityCritical,
		model.TaskPriorityHigh,
		model.TaskPriorityNormal,
		model.TaskPriorityLow,
	}

	for _, priority := range priorities {
		for _, taskType := range taskTypes {
			queueKey := tq.getQueueKey(taskType, priority)
			queueKeys = append(queueKeys, queueKey)
		}
	}

	// 使用BLPOP从多个队列中阻塞弹出任务
	result, err := tq.client.BLPop(ctx, timeout, queueKeys...).Result()
	if err != nil {
		if err == redis.Nil {
			return nil, nil // 超时，没有任务
		}
		return nil, fmt.Errorf("failed to pop task from queue: %w", err)
	}

	// result[0] 是队列名，result[1] 是任务数据
	taskData := result[1]
	queueName := result[0]

	// 反序列化任务消息
	var taskMsg TaskMessage
	if err := json.Unmarshal([]byte(taskData), &taskMsg); err != nil {
		return nil, fmt.Errorf("failed to unmarshal task message: %w", err)
	}

	// 将任务移到处理中队列
	processingKey := tq.getProcessingKey(taskMsg.TaskType)
	err = tq.client.LPush(ctx, processingKey, taskData).Err()
	if err != nil {
		tq.log.Errorf("Failed to move task to processing queue: %v", err)
	}

	// 更新队列统计
	err = tq.updateQueueStats(ctx, taskMsg.TaskType, "processing", 1)
	if err != nil {
		tq.log.Errorf("Failed to update queue stats: %v", err)
	}

	tq.log.Infof("Task %s popped from queue %s", taskMsg.TaskID, queueName)
	return &taskMsg, nil
}

// CompleteTask 标记任务完成
func (tq *TaskQueue) CompleteTask(ctx context.Context, taskID string, taskType model.TaskType) error {
	processingKey := tq.getProcessingKey(taskType)
	
	// 从处理中队列中移除任务
	removed, err := tq.removeTaskFromQueue(ctx, processingKey, taskID)
	if err != nil {
		return fmt.Errorf("failed to remove task from processing queue: %w", err)
	}

	if removed {
		// 更新统计
		err = tq.updateQueueStats(ctx, taskType, "completed", 1)
		if err != nil {
			tq.log.Errorf("Failed to update queue stats: %v", err)
		}
		
		tq.log.Infof("Task %s completed and removed from processing queue", taskID)
	}

	return nil
}

// FailTask 标记任务失败
func (tq *TaskQueue) FailTask(ctx context.Context, taskID string, taskType model.TaskType, shouldRetry bool, taskMsg *TaskMessage) error {
	processingKey := tq.getProcessingKey(taskType)
	
	// 从处理中队列中移除任务
	removed, err := tq.removeTaskFromQueue(ctx, processingKey, taskID)
	if err != nil {
		return fmt.Errorf("failed to remove task from processing queue: %w", err)
	}

	if removed {
		if shouldRetry && taskMsg != nil {
			// 重新推入队列进行重试
			taskMsg.Attempts++
			
			// 使用延迟队列实现退避重试
			retryDelay := tq.calculateRetryDelay(taskMsg.Attempts)
			err = tq.scheduleTask(ctx, taskMsg, retryDelay)
			if err != nil {
				tq.log.Errorf("Failed to schedule retry for task %s: %v", taskID, err)
				// 如果调度失败，移到失败队列
				return tq.moveToFailedQueue(ctx, taskID, taskType, taskMsg)
			}
			
			tq.log.Infof("Task %s scheduled for retry (attempt %d)", taskID, taskMsg.Attempts)
		} else {
			// 移到失败队列
			return tq.moveToFailedQueue(ctx, taskID, taskType, taskMsg)
		}
	}

	return nil
}

// GetQueueInfo 获取队列信息
func (tq *TaskQueue) GetQueueInfo(ctx context.Context, taskType model.TaskType) (*QueueInfo, error) {
	info := &QueueInfo{}
	
	// 计算所有优先级队列的总长度
	totalLength := int64(0)
	priorities := []model.TaskPriority{
		model.TaskPriorityCritical,
		model.TaskPriorityHigh,
		model.TaskPriorityNormal,
		model.TaskPriorityLow,
	}

	for _, priority := range priorities {
		queueKey := tq.getQueueKey(taskType, priority)
		length, err := tq.client.LLen(ctx, queueKey).Result()
		if err != nil {
			return nil, fmt.Errorf("failed to get queue length: %w", err)
		}
		totalLength += length
	}

	info.QueueName = string(taskType)
	info.Length = totalLength

	// 获取处理中任务数量
	processingKey := tq.getProcessingKey(taskType)
	processing, err := tq.client.LLen(ctx, processingKey).Result()
	if err != nil {
		return nil, fmt.Errorf("failed to get processing queue length: %w", err)
	}
	info.Processing = processing

	// 获取统计信息
	stats, err := tq.getQueueStats(ctx, taskType)
	if err != nil {
		tq.log.Errorf("Failed to get queue stats: %v", err)
		// 继续执行，不返回错误
	} else {
		info.Failed = stats["failed"]
		info.Completed = stats["completed"]
	}

	return info, nil
}

// GetAllQueueInfo 获取所有队列信息
func (tq *TaskQueue) GetAllQueueInfo(ctx context.Context) (map[string]*QueueInfo, error) {
	taskTypes := []model.TaskType{
		model.TaskTypeDocumentProcessing,
		model.TaskTypeBatchProcessing,
		model.TaskTypeKnowledgeIndexing,
		model.TaskTypeEmbeddingGeneration,
		model.TaskTypeVectorStorage,
		model.TaskTypeURLDownload,
	}

	result := make(map[string]*QueueInfo)
	
	for _, taskType := range taskTypes {
		info, err := tq.GetQueueInfo(ctx, taskType)
		if err != nil {
			tq.log.Errorf("Failed to get info for queue %s: %v", taskType, err)
			continue
		}
		result[string(taskType)] = info
	}

	return result, nil
}

// CleanExpiredTasks 清理过期任务
func (tq *TaskQueue) CleanExpiredTasks(ctx context.Context, maxAge time.Duration) error {
	cutoffTime := time.Now().Add(-maxAge)
	
	taskTypes := []model.TaskType{
		model.TaskTypeDocumentProcessing,
		model.TaskTypeBatchProcessing,
		model.TaskTypeKnowledgeIndexing,
		model.TaskTypeEmbeddingGeneration,
		model.TaskTypeVectorStorage,
		model.TaskTypeURLDownload,
	}

	for _, taskType := range taskTypes {
		processingKey := tq.getProcessingKey(taskType)
		
		// 获取处理中的任务
		tasks, err := tq.client.LRange(ctx, processingKey, 0, -1).Result()
		if err != nil {
			tq.log.Errorf("Failed to get tasks from processing queue %s: %v", processingKey, err)
			continue
		}

		for _, taskData := range tasks {
			var taskMsg TaskMessage
			if err := json.Unmarshal([]byte(taskData), &taskMsg); err != nil {
				tq.log.Errorf("Failed to unmarshal task message: %v", err)
				continue
			}

			// 检查任务是否过期
			if taskMsg.CreatedAt.Before(cutoffTime) {
				// 移除过期任务
				removed, err := tq.removeTaskFromQueue(ctx, processingKey, taskMsg.TaskID)
				if err != nil {
					tq.log.Errorf("Failed to remove expired task %s: %v", taskMsg.TaskID, err)
					continue
				}

				if removed {
					// 移到失败队列
					err = tq.moveToFailedQueue(ctx, taskMsg.TaskID, taskType, &taskMsg)
					if err != nil {
						tq.log.Errorf("Failed to move expired task to failed queue: %v", err)
					}
					
					tq.log.Infof("Expired task %s removed from processing queue", taskMsg.TaskID)
				}
			}
		}
	}

	return nil
}

// 私有方法

// getQueueKey 获取队列键
func (tq *TaskQueue) getQueueKey(taskType model.TaskType, priority model.TaskPriority) string {
	return fmt.Sprintf("%s:%s:%s", tq.queuePrefix, taskType, priority)
}

// getProcessingKey 获取处理中队列键
func (tq *TaskQueue) getProcessingKey(taskType model.TaskType) string {
	return fmt.Sprintf("%s:%s:processing", tq.queuePrefix, taskType)
}

// getFailedKey 获取失败队列键
func (tq *TaskQueue) getFailedKey(taskType model.TaskType) string {
	return fmt.Sprintf("%s:%s:failed", tq.queuePrefix, taskType)
}

// getStatsKey 获取统计键
func (tq *TaskQueue) getStatsKey(taskType model.TaskType) string {
	return fmt.Sprintf("%s:%s:stats", tq.queuePrefix, taskType)
}

// removeTaskFromQueue 从队列中移除特定任务
func (tq *TaskQueue) removeTaskFromQueue(ctx context.Context, queueKey, taskID string) (bool, error) {
	// 获取队列中的所有任务
	tasks, err := tq.client.LRange(ctx, queueKey, 0, -1).Result()
	if err != nil {
		return false, err
	}

	// 查找并移除目标任务
	for _, taskData := range tasks {
		var taskMsg TaskMessage
		if err := json.Unmarshal([]byte(taskData), &taskMsg); err != nil {
			continue
		}

		if taskMsg.TaskID == taskID {
			// 移除任务
			_, err = tq.client.LRem(ctx, queueKey, 1, taskData).Result()
			return err == nil, err
		}
	}

	return false, nil
}

// moveToFailedQueue 移动任务到失败队列
func (tq *TaskQueue) moveToFailedQueue(ctx context.Context, taskID string, taskType model.TaskType, taskMsg *TaskMessage) error {
	failedKey := tq.getFailedKey(taskType)
	
	if taskMsg != nil {
		// 添加失败时间戳
		taskData, err := json.Marshal(taskMsg)
		if err != nil {
			return fmt.Errorf("failed to marshal failed task: %w", err)
		}

		err = tq.client.LPush(ctx, failedKey, taskData).Err()
		if err != nil {
			return fmt.Errorf("failed to push task to failed queue: %w", err)
		}
	}

	// 更新统计
	err := tq.updateQueueStats(ctx, taskType, "failed", 1)
	if err != nil {
		tq.log.Errorf("Failed to update queue stats: %v", err)
	}

	tq.log.Infof("Task %s moved to failed queue", taskID)
	return nil
}

// scheduleTask 调度任务(延迟重试)
func (tq *TaskQueue) scheduleTask(ctx context.Context, taskMsg *TaskMessage, delay time.Duration) error {
	// 使用Redis的ZADD实现延迟队列
	scheduleKey := fmt.Sprintf("%s:scheduled", tq.queuePrefix)
	executeTime := time.Now().Add(delay).Unix()
	
	taskData, err := json.Marshal(taskMsg)
	if err != nil {
		return fmt.Errorf("failed to marshal scheduled task: %w", err)
	}

	err = tq.client.ZAdd(ctx, scheduleKey, redis.Z{
		Score:  float64(executeTime),
		Member: taskData,
	}).Err()

	if err != nil {
		return fmt.Errorf("failed to schedule task: %w", err)
	}

	return nil
}

// ProcessScheduledTasks 处理调度任务
func (tq *TaskQueue) ProcessScheduledTasks(ctx context.Context) error {
	scheduleKey := fmt.Sprintf("%s:scheduled", tq.queuePrefix)
	now := time.Now().Unix()

	// 获取到期的任务
	tasks, err := tq.client.ZRangeByScore(ctx, scheduleKey, &redis.ZRangeBy{
		Min: "0",
		Max: fmt.Sprintf("%d", now),
	}).Result()

	if err != nil {
		return fmt.Errorf("failed to get scheduled tasks: %w", err)
	}

	for _, taskData := range tasks {
		var taskMsg TaskMessage
		if err := json.Unmarshal([]byte(taskData), &taskMsg); err != nil {
			tq.log.Errorf("Failed to unmarshal scheduled task: %v", err)
			continue
		}

		// 重新推入队列
		queueKey := tq.getQueueKey(taskMsg.TaskType, taskMsg.Priority)
		err = tq.client.RPush(ctx, queueKey, taskData).Err()
		if err != nil {
			tq.log.Errorf("Failed to requeue scheduled task %s: %v", taskMsg.TaskID, err)
			continue
		}

		// 从调度队列中移除
		err = tq.client.ZRem(ctx, scheduleKey, taskData).Err()
		if err != nil {
			tq.log.Errorf("Failed to remove scheduled task %s: %v", taskMsg.TaskID, err)
		}

		tq.log.Infof("Scheduled task %s requeued", taskMsg.TaskID)
	}

	return nil
}

// calculateRetryDelay 计算重试延迟
func (tq *TaskQueue) calculateRetryDelay(attempts int) time.Duration {
	// 指数退避算法: delay = base * 2^(attempts-1)
	baseDelay := 1 * time.Second
	maxDelay := 5 * time.Minute

	delay := time.Duration(float64(baseDelay) * float64(1<<(attempts-1)))
	if delay > maxDelay {
		delay = maxDelay
	}

	return delay
}

// updateQueueStats 更新队列统计
func (tq *TaskQueue) updateQueueStats(ctx context.Context, taskType model.TaskType, statType string, increment int64) error {
	statsKey := tq.getStatsKey(taskType)
	_, err := tq.client.HIncrBy(ctx, statsKey, statType, increment).Result()
	return err
}

// getQueueStats 获取队列统计
func (tq *TaskQueue) getQueueStats(ctx context.Context, taskType model.TaskType) (map[string]int64, error) {
	statsKey := tq.getStatsKey(taskType)
	stats, err := tq.client.HGetAll(ctx, statsKey).Result()
	if err != nil {
		return nil, err
	}

	result := make(map[string]int64)
	for key, value := range stats {
		if val, err := redis.NewCmd(ctx, "PARSE", value).Int64(); err == nil {
			result[key] = val
		}
	}

	return result, nil
}