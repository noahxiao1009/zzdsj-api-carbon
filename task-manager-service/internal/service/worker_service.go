package service

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/go-redis/redis/v8"
	"github.com/google/uuid"
	"github.com/sirupsen/logrus"

	"task-manager-service/internal/config"
	"task-manager-service/internal/model"
)

type WorkerService struct {
	db         *sql.DB
	rdb        *redis.Client
	config     *config.Config
	log        *logrus.Entry
	workers    map[string]*Worker
	workersMux sync.RWMutex
	running    bool
	ctx        context.Context
	cancel     context.CancelFunc
	wg         sync.WaitGroup
}

type Worker struct {
	ID           string
	Status       string // idle, busy, stopped
	CurrentTask  string
	LastActivity time.Time
	ProcessedTasks int64
	SucceededTasks int64
	FailedTasks    int64
	StartedAt      time.Time
	service      *WorkerService
	log          *logrus.Entry
}

func NewWorkerService(db *sql.DB, rdb *redis.Client, cfg *config.Config) *WorkerService {
	return &WorkerService{
		db:      db,
		rdb:     rdb,
		config:  cfg,
		log:     logrus.WithField("component", "worker-service"),
		workers: make(map[string]*Worker),
		running: false,
	}
}

// Start 启动工作进程池
func (ws *WorkerService) Start(ctx context.Context) error {
	ws.ctx, ws.cancel = context.WithCancel(ctx)
	ws.running = true

	ws.log.Infof("Starting %d workers...", ws.config.Worker.PoolSize)

	// 启动工作进程
	for i := 0; i < ws.config.Worker.PoolSize; i++ {
		worker := ws.createWorker()
		ws.addWorker(worker)
		
		ws.wg.Add(1)
		go func(w *Worker) {
			defer ws.wg.Done()
			w.run(ws.ctx)
		}(worker)
	}

	// 启动心跳监控
	ws.wg.Add(1)
	go func() {
		defer ws.wg.Done()
		ws.heartbeatMonitor(ws.ctx)
	}()

	// 启动清理任务
	ws.wg.Add(1)
	go func() {
		defer ws.wg.Done()
		ws.cleanupMonitor(ws.ctx)
	}()

	ws.log.Info("✓ All workers started successfully")
	return nil
}

// Stop 停止工作进程池
func (ws *WorkerService) Stop() {
	if !ws.running {
		return
	}

	ws.log.Info("Stopping worker service...")
	ws.running = false
	
	if ws.cancel != nil {
		ws.cancel()
	}

	// 等待所有工作进程完成
	ws.wg.Wait()

	// 清理工作进程状态
	ws.workersMux.Lock()
	for id, worker := range ws.workers {
		worker.updateStatus("stopped")
		ws.cleanupWorkerRedis(id)
		delete(ws.workers, id)
	}
	ws.workersMux.Unlock()

	ws.log.Info("✓ Worker service stopped")
}

// createWorker 创建新的工作进程
func (ws *WorkerService) createWorker() *Worker {
	workerID := uuid.New().String()
	
	return &Worker{
		ID:           workerID,
		Status:       "idle",
		LastActivity: time.Now(),
		StartedAt:    time.Now(),
		service:      ws,
		log:          logrus.WithField("worker_id", workerID),
	}
}

// addWorker 添加工作进程到池中
func (ws *WorkerService) addWorker(worker *Worker) {
	ws.workersMux.Lock()
	defer ws.workersMux.Unlock()
	
	ws.workers[worker.ID] = worker
	worker.updateStatus("idle")
}

// removeWorker 从池中移除工作进程
func (ws *WorkerService) removeWorker(workerID string) {
	ws.workersMux.Lock()
	defer ws.workersMux.Unlock()
	
	if worker, exists := ws.workers[workerID]; exists {
		worker.updateStatus("stopped")
		ws.cleanupWorkerRedis(workerID)
		delete(ws.workers, workerID)
	}
}

// Worker.run 工作进程主循环
func (w *Worker) run(ctx context.Context) {
	w.log.Info("Worker started")
	defer w.log.Info("Worker stopped")

	ticker := time.NewTicker(w.service.config.Worker.PollInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			if err := w.processNextTask(ctx); err != nil {
				w.log.Errorf("Error processing task: %v", err)
			}
		}
	}
}

// processNextTask 处理下一个任务
func (w *Worker) processNextTask(ctx context.Context) error {
	// 从高优先级到低优先级检查队列
	priorities := []string{"critical", "high", "normal", "low"}
	
	for _, priority := range priorities {
		taskID, err := w.dequeueTask(ctx, priority)
		if err != nil {
			continue
		}
		
		if taskID != "" {
			return w.executeTask(ctx, taskID)
		}
	}
	
	return nil // 没有任务
}

// dequeueTask 从队列中取出任务
func (w *Worker) dequeueTask(ctx context.Context, priority string) (string, error) {
	queueKey := fmt.Sprintf("%s:%s", w.service.config.Task.QueuePrefix, priority)
	
	result, err := w.service.rdb.BRPop(ctx, time.Second, queueKey).Result()
	if err != nil {
		if err == redis.Nil {
			return "", nil // 队列为空
		}
		return "", err
	}
	
	if len(result) < 2 {
		return "", fmt.Errorf("invalid queue result")
	}
	
	return result[1], nil
}

// executeTask 执行任务
func (w *Worker) executeTask(ctx context.Context, taskID string) error {
	w.updateStatus("busy")
	w.CurrentTask = taskID
	defer func() {
		w.updateStatus("idle")
		w.CurrentTask = ""
		w.LastActivity = time.Now()
	}()

	w.log.Infof("Processing task: %s", taskID)

	// 更新任务状态为处理中
	now := time.Now()
	_, err := w.service.db.ExecContext(ctx, `
		UPDATE tasks 
		SET status = $1, started_at = $2, updated_at = $3, worker_id = $4 
		WHERE id = $5
	`, model.TaskStatusProcessing, now, now, w.ID, taskID)
	
	if err != nil {
		w.log.Errorf("Failed to update task status: %v", err)
		return err
	}

	// 获取任务详情
	task, err := w.getTask(ctx, taskID)
	if err != nil {
		w.log.Errorf("Failed to get task details: %v", err)
		return err
	}

	// 创建任务执行上下文
	taskCtx, taskCancel := context.WithTimeout(ctx, time.Duration(task.Timeout)*time.Second)
	defer taskCancel()

	// 执行任务
	var result model.JSONMap
	var taskErr error

	switch task.TaskType {
	case model.TaskTypeDocumentProcessing:
		result, taskErr = w.processDocument(taskCtx, task)
	case model.TaskTypeBatchProcessing:
		result, taskErr = w.processBatch(taskCtx, task)
	case model.TaskTypeKnowledgeIndexing:
		result, taskErr = w.processKnowledgeIndexing(taskCtx, task)
	case model.TaskTypeEmbeddingGeneration:
		result, taskErr = w.processEmbedding(taskCtx, task)
	case model.TaskTypeVectorStorage:
		result, taskErr = w.processVectorStorage(taskCtx, task)
	case model.TaskTypeHealthCheck:
		result, taskErr = w.processHealthCheck(taskCtx, task)
	default:
		taskErr = fmt.Errorf("unknown task type: %s", task.TaskType)
	}

	// 更新统计
	w.ProcessedTasks++
	if taskErr != nil {
		w.FailedTasks++
		return w.handleTaskFailure(ctx, task, taskErr)
	} else {
		w.SucceededTasks++
		return w.handleTaskSuccess(ctx, task, result)
	}
}

// handleTaskSuccess 处理任务成功
func (w *Worker) handleTaskSuccess(ctx context.Context, task *model.Task, result model.JSONMap) error {
	now := time.Now()
	
	resultJSON, err := json.Marshal(result)
	if err != nil {
		w.log.Errorf("Failed to marshal task result: %v", err)
		resultJSON = []byte("{}")
	}
	
	_, err = w.service.db.ExecContext(ctx, `
		UPDATE tasks 
		SET status = $1, result = $2, progress = 100, completed_at = $3, updated_at = $4
		WHERE id = $5
	`, model.TaskStatusCompleted, resultJSON, now, now, task.ID)
	
	if err != nil {
		w.log.Errorf("Failed to update task success: %v", err)
		return err
	}
	
	w.log.Infof("Task completed successfully: %s", task.ID)
	
	// 发送完成通知 (如果需要)
	w.sendTaskNotification(ctx, task, "completed", result)
	
	return nil
}

// handleTaskFailure 处理任务失败
func (w *Worker) handleTaskFailure(ctx context.Context, task *model.Task, taskErr error) error {
	now := time.Now()
	
	// 检查是否可以重试
	if task.CanRetry() {
		// 重新入队重试
		backoffDuration := w.calculateBackoff(task.RetryCount)
		
		_, err := w.service.db.ExecContext(ctx, `
			UPDATE tasks 
			SET status = $1, retry_count = retry_count + 1, error_message = $2, updated_at = $3,
				scheduled_for = $4, worker_id = ''
			WHERE id = $5
		`, model.TaskStatusRetrying, taskErr.Error(), now, now.Add(backoffDuration), task.ID)
		
		if err != nil {
			w.log.Errorf("Failed to update task for retry: %v", err)
			return err
		}
		
		// 延迟重新入队
		go func() {
			time.Sleep(backoffDuration)
			queueKey := fmt.Sprintf("%s:%s", w.service.config.Task.QueuePrefix, task.Priority)
			w.service.rdb.LPush(context.Background(), queueKey, task.ID)
		}()
		
		w.log.Infof("Task scheduled for retry: %s (attempt %d/%d)", task.ID, task.RetryCount+1, task.MaxRetries)
	} else {
		// 标记为失败
		_, err := w.service.db.ExecContext(ctx, `
			UPDATE tasks 
			SET status = $1, error_message = $2, completed_at = $3, updated_at = $4
			WHERE id = $5
		`, model.TaskStatusFailed, taskErr.Error(), now, now, task.ID)
		
		if err != nil {
			w.log.Errorf("Failed to update task failure: %v", err)
			return err
		}
		
		w.log.Errorf("Task failed permanently: %s - %v", task.ID, taskErr)
		
		// 发送失败通知
		w.sendTaskNotification(ctx, task, "failed", model.JSONMap{"error": taskErr.Error()})
	}
	
	return nil
}

// getTask 获取任务详情
func (w *Worker) getTask(ctx context.Context, taskID string) (*model.Task, error) {
	query := `
		SELECT id, task_type, status, priority, kb_id, payload, result, progress,
			   retry_count, max_retries, error_message, worker_id, timeout,
			   created_at, updated_at, started_at, completed_at, scheduled_for
		FROM tasks WHERE id = $1
	`

	var task model.Task
	var payloadJSON, resultJSON sql.NullString
	var startedAt, completedAt, scheduledFor sql.NullTime

	err := w.service.db.QueryRowContext(ctx, query, taskID).Scan(
		&task.ID, &task.TaskType, &task.Status, &task.Priority, &task.KbID,
		&payloadJSON, &resultJSON, &task.Progress, &task.RetryCount, &task.MaxRetries,
		&task.ErrorMessage, &task.WorkerID, &task.Timeout,
		&task.CreatedAt, &task.UpdatedAt, &startedAt, &completedAt, &scheduledFor,
	)

	if err != nil {
		return nil, err
	}

	// 处理可空字段
	if startedAt.Valid {
		task.StartedAt = &startedAt.Time
	}
	if completedAt.Valid {
		task.CompletedAt = &completedAt.Time
	}
	if scheduledFor.Valid {
		task.ScheduledFor = &scheduledFor.Time
	}

	// 解析JSON字段
	if payloadJSON.Valid && payloadJSON.String != "" {
		json.Unmarshal([]byte(payloadJSON.String), &task.Payload)
	} else {
		task.Payload = make(model.JSONMap)
	}

	if resultJSON.Valid && resultJSON.String != "" {
		json.Unmarshal([]byte(resultJSON.String), &task.Result)
	} else {
		task.Result = make(model.JSONMap)
	}

	return &task, nil
}

// calculateBackoff 计算重试退避时间
func (w *Worker) calculateBackoff(retryCount int) time.Duration {
	base := w.service.config.Task.RetryBackoffBase
	max := w.service.config.Task.RetryBackoffMax
	
	// 指数退避
	backoff := base * time.Duration(1<<uint(retryCount))
	if backoff > max {
		backoff = max
	}
	
	return backoff
}

// updateStatus 更新工作进程状态到Redis
func (w *Worker) updateStatus(status string) {
	w.Status = status
	
	key := fmt.Sprintf("worker:%s", w.ID)
	data := map[string]interface{}{
		"id":                w.ID,
		"status":            status,
		"current_task_id":   w.CurrentTask,
		"tasks_processed":   w.ProcessedTasks,
		"tasks_succeeded":   w.SucceededTasks,
		"tasks_failed":      w.FailedTasks,
		"last_heartbeat":    time.Now().Unix(),
		"started_at":        w.StartedAt.Unix(),
		"average_task_time": w.calculateAverageTaskTime(),
	}
	
	if w.LastActivity.IsZero() {
		data["last_task_at"] = nil
	} else {
		data["last_task_at"] = w.LastActivity.Unix()
	}
	
	w.service.rdb.HMSet(context.Background(), key, data)
	w.service.rdb.Expire(context.Background(), key, time.Minute*5)
}

// calculateAverageTaskTime 计算平均任务处理时间
func (w *Worker) calculateAverageTaskTime() float64 {
	if w.ProcessedTasks == 0 {
		return 0
	}
	
	totalTime := time.Since(w.StartedAt).Seconds()
	return totalTime / float64(w.ProcessedTasks)
}

// sendTaskNotification 发送任务完成通知
func (w *Worker) sendTaskNotification(ctx context.Context, task *model.Task, status string, result model.JSONMap) {
	// 这里可以实现回调知识库服务的逻辑
	// 例如发送HTTP请求或消息队列通知
	w.log.Infof("Task notification sent: %s - %s", task.ID, status)
}

// heartbeatMonitor 心跳监控
func (ws *WorkerService) heartbeatMonitor(ctx context.Context) {
	ticker := time.NewTicker(time.Minute)
	defer ticker.Stop()
	
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			ws.updateWorkersHeartbeat()
		}
	}
}

// updateWorkersHeartbeat 更新所有工作进程心跳
func (ws *WorkerService) updateWorkersHeartbeat() {
	ws.workersMux.RLock()
	defer ws.workersMux.RUnlock()
	
	for _, worker := range ws.workers {
		worker.updateStatus(worker.Status)
	}
}

// cleanupMonitor 清理监控
func (ws *WorkerService) cleanupMonitor(ctx context.Context) {
	ticker := time.NewTicker(time.Hour)
	defer ticker.Stop()
	
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			ws.cleanupStuckTasks(ctx)
		}
	}
}

// cleanupStuckTasks 清理卡死的任务
func (ws *WorkerService) cleanupStuckTasks(ctx context.Context) {
	// 查找处理中但超时的任务
	timeout := time.Now().Add(-time.Duration(ws.config.Worker.TaskTimeout) * 2)
	
	query := `
		UPDATE tasks 
		SET status = 'failed', error_message = 'Task timeout', completed_at = NOW(), updated_at = NOW()
		WHERE status = 'processing' AND started_at < $1
	`
	
	result, err := ws.db.ExecContext(ctx, query, timeout)
	if err != nil {
		ws.log.Errorf("Failed to cleanup stuck tasks: %v", err)
		return
	}
	
	count, _ := result.RowsAffected()
	if count > 0 {
		ws.log.Infof("Cleaned up %d stuck tasks", count)
	}
}

// cleanupWorkerRedis 清理工作进程的Redis状态
func (ws *WorkerService) cleanupWorkerRedis(workerID string) {
	key := fmt.Sprintf("worker:%s", workerID)
	ws.rdb.Del(context.Background(), key)
}

// 具体的任务处理方法

func (w *Worker) processDocument(ctx context.Context, task *model.Task) (model.JSONMap, error) {
	w.log.Infof("Processing document for task: %s", task.ID)
	
	// 模拟文档处理
	time.Sleep(time.Second * 2)
	
	result := model.JSONMap{
		"status":       "completed",
		"processed_at": time.Now(),
		"chunks":       42,
		"message":      "Document processed successfully",
	}
	
	return result, nil
}

func (w *Worker) processBatch(ctx context.Context, task *model.Task) (model.JSONMap, error) {
	w.log.Infof("Processing batch for task: %s", task.ID)
	
	// 模拟批处理
	time.Sleep(time.Second * 3)
	
	result := model.JSONMap{
		"status":        "completed",
		"processed_at":  time.Now(),
		"items_processed": 100,
		"message":       "Batch processed successfully",
	}
	
	return result, nil
}

func (w *Worker) processKnowledgeIndexing(ctx context.Context, task *model.Task) (model.JSONMap, error) {
	w.log.Infof("Processing knowledge indexing for task: %s", task.ID)
	
	// 模拟知识索引
	time.Sleep(time.Second * 4)
	
	result := model.JSONMap{
		"status":     "completed",
		"indexed_at": time.Now(),
		"documents":  25,
		"message":    "Knowledge indexed successfully",
	}
	
	return result, nil
}

func (w *Worker) processEmbedding(ctx context.Context, task *model.Task) (model.JSONMap, error) {
	w.log.Infof("Processing embedding generation for task: %s", task.ID)
	
	// 模拟嵌入生成
	time.Sleep(time.Second * 5)
	
	result := model.JSONMap{
		"status":        "completed",
		"generated_at":  time.Now(),
		"embeddings":    156,
		"dimensions":    768,
		"message":       "Embeddings generated successfully",
	}
	
	return result, nil
}

func (w *Worker) processVectorStorage(ctx context.Context, task *model.Task) (model.JSONMap, error) {
	w.log.Infof("Processing vector storage for task: %s", task.ID)
	
	// 模拟向量存储
	time.Sleep(time.Second * 3)
	
	result := model.JSONMap{
		"status":     "completed",
		"stored_at":  time.Now(),
		"vectors":    156,
		"collection": "knowledge_vectors",
		"message":    "Vectors stored successfully",
	}
	
	return result, nil
}

func (w *Worker) processHealthCheck(ctx context.Context, task *model.Task) (model.JSONMap, error) {
	w.log.Infof("Processing health check for task: %s", task.ID)
	
	// 模拟健康检查
	time.Sleep(time.Millisecond * 500)
	
	result := model.JSONMap{
		"status":       "healthy",
		"checked_at":   time.Now(),
		"response_time": "500ms",
		"message":      "Health check completed",
	}
	
	return result, nil
}