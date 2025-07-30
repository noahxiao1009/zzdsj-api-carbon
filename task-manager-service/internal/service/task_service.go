package service

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/go-redis/redis/v8"
	"github.com/google/uuid"
	"github.com/sirupsen/logrus"

	"task-manager-service/internal/config"
	"task-manager-service/internal/model"
)

var (
	ErrTaskNotFound     = errors.New("task not found")
	ErrTaskNotCancelable = errors.New("task not cancelable")
	ErrTaskNotRetryable = errors.New("task not retryable")
)

type TaskService struct {
	db     *sql.DB
	rdb    *redis.Client
	config *config.Config
	log    *logrus.Entry
}

func NewTaskService(db *sql.DB, rdb *redis.Client, cfg *config.Config) *TaskService {
	return &TaskService{
		db:     db,
		rdb:    rdb,
		config: cfg,
		log:    logrus.WithField("component", "task-service"),
	}
}

// CreateTask 创建任务
func (s *TaskService) CreateTask(ctx context.Context, req *model.TaskCreateRequest) (*model.TaskResponse, error) {
	taskID := uuid.New().String()
	
	// 设置默认值
	if req.Priority == "" {
		req.Priority = model.TaskPriority(s.config.Task.DefaultPriority)
	}
	if req.MaxRetries == 0 {
		req.MaxRetries = s.config.Task.MaxRetryAttempts
	}
	if req.Timeout == 0 {
		req.Timeout = int(s.config.Worker.TaskTimeout.Seconds())
	}

	now := time.Now()
	scheduledFor := &now
	if req.ScheduleFor != nil {
		scheduledFor = req.ScheduleFor
	}

	// 序列化payload
	payloadJSON, err := json.Marshal(req.Payload)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal payload: %w", err)
	}

	// 插入数据库
	query := `
		INSERT INTO tasks (
			id, task_type, status, priority, kb_id, payload, 
			retry_count, max_retries, timeout, created_at, updated_at, scheduled_for
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
	`
	
	_, err = s.db.ExecContext(ctx, query,
		taskID, req.TaskType, model.TaskStatusQueued, req.Priority, req.KbID,
		payloadJSON, 0, req.MaxRetries, req.Timeout, now, now, scheduledFor,
	)
	if err != nil {
		s.log.Errorf("Failed to insert task: %v", err)
		return nil, fmt.Errorf("failed to create task: %w", err)
	}

	// 添加到Redis队列
	err = s.enqueueTask(ctx, taskID, req.Priority)
	if err != nil {
		s.log.Errorf("Failed to enqueue task: %v", err)
		// 删除数据库记录
		s.db.ExecContext(ctx, "DELETE FROM tasks WHERE id = $1", taskID)
		return nil, fmt.Errorf("failed to enqueue task: %w", err)
	}

	// 获取创建的任务
	task, err := s.GetTask(ctx, taskID)
	if err != nil {
		return nil, err
	}

	s.log.Infof("Task created successfully: %s (type: %s, priority: %s)", taskID, req.TaskType, req.Priority)
	return task, nil
}

// GetTask 获取任务详情
func (s *TaskService) GetTask(ctx context.Context, taskID string) (*model.TaskResponse, error) {
	query := `
		SELECT id, task_type, status, priority, kb_id, payload, result, progress,
			   retry_count, max_retries, error_message, worker_id, timeout,
			   created_at, updated_at, started_at, completed_at, scheduled_for
		FROM tasks WHERE id = $1
	`

	var task model.Task
	var payloadJSON, resultJSON sql.NullString
	var startedAt, completedAt, scheduledFor sql.NullTime

	err := s.db.QueryRowContext(ctx, query, taskID).Scan(
		&task.ID, &task.TaskType, &task.Status, &task.Priority, &task.KbID,
		&payloadJSON, &resultJSON, &task.Progress, &task.RetryCount, &task.MaxRetries,
		&task.ErrorMessage, &task.WorkerID, &task.Timeout,
		&task.CreatedAt, &task.UpdatedAt, &startedAt, &completedAt, &scheduledFor,
	)

	if err != nil {
		if err == sql.ErrNoRows {
			return nil, ErrTaskNotFound
		}
		s.log.Errorf("Failed to get task %s: %v", taskID, err)
		return nil, fmt.Errorf("failed to get task: %w", err)
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

	// 构建响应
	response := &model.TaskResponse{
		Task: &task,
	}

	// 计算预估完成时间
	if task.Status == model.TaskStatusProcessing && task.StartedAt != nil {
		avgTime := s.getAverageProcessingTime(ctx, task.TaskType)
		if avgTime > 0 {
			estimated := task.StartedAt.Add(time.Duration(avgTime) * time.Second)
			response.EstimatedCompletion = &estimated
		}
	}

	// 获取队列位置
	if task.Status == model.TaskStatusQueued {
		position := s.getQueuePosition(ctx, taskID, task.Priority)
		response.QueuePosition = position
	}

	return response, nil
}

// ListTasks 获取任务列表
func (s *TaskService) ListTasks(ctx context.Context, req *model.TaskListRequest) ([]*model.Task, int64, error) {
	// 构建查询条件
	where := "WHERE 1=1"
	args := []interface{}{}
	argIndex := 1

	if req.KbID != "" {
		where += fmt.Sprintf(" AND kb_id = $%d", argIndex)
		args = append(args, req.KbID)
		argIndex++
	}

	if req.Status != "" {
		where += fmt.Sprintf(" AND status = $%d", argIndex)
		args = append(args, req.Status)
		argIndex++
	}

	if req.TaskType != "" {
		where += fmt.Sprintf(" AND task_type = $%d", argIndex)
		args = append(args, req.TaskType)
		argIndex++
	}

	if req.Priority != "" {
		where += fmt.Sprintf(" AND priority = $%d", argIndex)
		args = append(args, req.Priority)
		argIndex++
	}

	// 构建排序
	orderBy := "ORDER BY created_at DESC"
	if req.SortBy != "" {
		direction := "ASC"
		if req.SortOrder == "desc" {
			direction = "DESC"
		}
		orderBy = fmt.Sprintf("ORDER BY %s %s", req.SortBy, direction)
	}

	// 计算总数
	countQuery := fmt.Sprintf("SELECT COUNT(*) FROM tasks %s", where)
	var total int64
	err := s.db.QueryRowContext(ctx, countQuery, args...).Scan(&total)
	if err != nil {
		s.log.Errorf("Failed to count tasks: %v", err)
		return nil, 0, fmt.Errorf("failed to count tasks: %w", err)
	}

	// 查询数据
	offset := (req.Page - 1) * req.PageSize
	query := fmt.Sprintf(`
		SELECT id, task_type, status, priority, kb_id, payload, result, progress,
			   retry_count, max_retries, error_message, worker_id, timeout,
			   created_at, updated_at, started_at, completed_at, scheduled_for
		FROM tasks %s %s
		LIMIT $%d OFFSET $%d
	`, where, orderBy, argIndex, argIndex+1)

	args = append(args, req.PageSize, offset)

	rows, err := s.db.QueryContext(ctx, query, args...)
	if err != nil {
		s.log.Errorf("Failed to query tasks: %v", err)
		return nil, 0, fmt.Errorf("failed to query tasks: %w", err)
	}
	defer rows.Close()

	var tasks []*model.Task
	for rows.Next() {
		var task model.Task
		var payloadJSON, resultJSON sql.NullString
		var startedAt, completedAt, scheduledFor sql.NullTime

		err := rows.Scan(
			&task.ID, &task.TaskType, &task.Status, &task.Priority, &task.KbID,
			&payloadJSON, &resultJSON, &task.Progress, &task.RetryCount, &task.MaxRetries,
			&task.ErrorMessage, &task.WorkerID, &task.Timeout,
			&task.CreatedAt, &task.UpdatedAt, &startedAt, &completedAt, &scheduledFor,
		)
		if err != nil {
			s.log.Errorf("Failed to scan task: %v", err)
			continue
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

		tasks = append(tasks, &task)
	}

	return tasks, total, nil
}

// CancelTask 取消任务
func (s *TaskService) CancelTask(ctx context.Context, taskID string) error {
	// 检查任务状态
	var status string
	err := s.db.QueryRowContext(ctx, "SELECT status FROM tasks WHERE id = $1", taskID).Scan(&status)
	if err != nil {
		if err == sql.ErrNoRows {
			return ErrTaskNotFound
		}
		return fmt.Errorf("failed to check task status: %w", err)
	}

	// 只有排队中和处理中的任务可以取消
	if status != string(model.TaskStatusQueued) && status != string(model.TaskStatusProcessing) {
		return ErrTaskNotCancelable
	}

	// 更新任务状态
	now := time.Now()
	_, err = s.db.ExecContext(ctx,
		"UPDATE tasks SET status = $1, updated_at = $2, completed_at = $3 WHERE id = $4",
		model.TaskStatusCanceled, now, now, taskID,
	)
	if err != nil {
		s.log.Errorf("Failed to cancel task %s: %v", taskID, err)
		return fmt.Errorf("failed to cancel task: %w", err)
	}

	// 从Redis队列中移除
	s.removeFromQueue(ctx, taskID)

	s.log.Infof("Task canceled: %s", taskID)
	return nil
}

// RetryTask 重试任务
func (s *TaskService) RetryTask(ctx context.Context, taskID string) (*model.TaskResponse, error) {
	// 获取任务信息
	task, err := s.GetTask(ctx, taskID)
	if err != nil {
		return nil, err
	}

	// 检查是否可以重试
	if !task.CanRetry() {
		return nil, ErrTaskNotRetryable
	}

	// 重置任务状态
	now := time.Now()
	_, err = s.db.ExecContext(ctx, `
		UPDATE tasks 
		SET status = $1, retry_count = retry_count + 1, updated_at = $2,
			started_at = NULL, completed_at = NULL, error_message = '', worker_id = ''
		WHERE id = $3
	`, model.TaskStatusQueued, now, taskID)
	if err != nil {
		s.log.Errorf("Failed to retry task %s: %v", taskID, err)
		return nil, fmt.Errorf("failed to retry task: %w", err)
	}

	// 重新入队
	err = s.enqueueTask(ctx, taskID, task.Priority)
	if err != nil {
		s.log.Errorf("Failed to re-enqueue task %s: %v", taskID, err)
		return nil, fmt.Errorf("failed to re-enqueue task: %w", err)
	}

	s.log.Infof("Task retried: %s", taskID)
	return s.GetTask(ctx, taskID)
}

// GetTaskStats 获取任务统计信息
func (s *TaskService) GetTaskStats(ctx context.Context, kbID string) (*model.TaskStats, error) {
	where := "WHERE 1=1"
	args := []interface{}{}
	if kbID != "" {
		where = "WHERE kb_id = $1"
		args = append(args, kbID)
	}

	query := fmt.Sprintf(`
		SELECT
			COUNT(*) as total_tasks,
			COUNT(*) FILTER (WHERE status = 'queued') as queued_tasks,
			COUNT(*) FILTER (WHERE status = 'processing') as processing_tasks,
			COUNT(*) FILTER (WHERE status = 'completed') as completed_tasks,
			COUNT(*) FILTER (WHERE status = 'failed') as failed_tasks,
			COALESCE(AVG(EXTRACT(EPOCH FROM (completed_at - started_at))), 0) as avg_process_time
		FROM tasks %s
	`, where)

	var stats model.TaskStats
	err := s.db.QueryRowContext(ctx, query, args...).Scan(
		&stats.TotalTasks, &stats.QueuedTasks, &stats.ProcessingTasks,
		&stats.CompletedTasks, &stats.FailedTasks, &stats.AvgProcessTime,
	)
	if err != nil {
		s.log.Errorf("Failed to get task stats: %v", err)
		return nil, fmt.Errorf("failed to get task stats: %w", err)
	}

	// 计算成功率
	if stats.TotalTasks > 0 {
		stats.SuccessRate = float64(stats.CompletedTasks) / float64(stats.TotalTasks) * 100
	}

	// 获取状态分布
	stats.StatusBreakdown = make(map[string]int64)
	stats.TypeBreakdown = make(map[string]int64)

	// 状态分布查询
	statusQuery := fmt.Sprintf("SELECT status, COUNT(*) FROM tasks %s GROUP BY status", where)
	rows, err := s.db.QueryContext(ctx, statusQuery, args...)
	if err == nil {
		defer rows.Close()
		for rows.Next() {
			var status string
			var count int64
			if rows.Scan(&status, &count) == nil {
				stats.StatusBreakdown[status] = count
			}
		}
	}

	// 类型分布查询
	typeQuery := fmt.Sprintf("SELECT task_type, COUNT(*) FROM tasks %s GROUP BY task_type", where)
	rows, err = s.db.QueryContext(ctx, typeQuery, args...)
	if err == nil {
		defer rows.Close()
		for rows.Next() {
			var taskType string
			var count int64
			if rows.Scan(&taskType, &count) == nil {
				stats.TypeBreakdown[taskType] = count
			}
		}
	}

	return &stats, nil
}

// GetSystemStats 获取系统统计信息
func (s *TaskService) GetSystemStats(ctx context.Context) (*model.SystemStats, error) {
	stats := &model.SystemStats{}
	
	// 获取任务统计
	taskStats, err := s.GetTaskStats(ctx, "")
	if err != nil {
		return nil, err
	}
	stats.TaskStats = *taskStats

	// 获取队列大小
	queueSize, err := s.rdb.LLen(ctx, s.getQueueKey("")).Result()
	if err == nil {
		stats.QueueSize = queueSize
	}

	// 获取工作进程信息 (从Redis中获取)
	workers, err := s.getWorkersInfo(ctx)
	if err == nil {
		stats.Workers = workers
		stats.TotalWorkers = len(workers)
		
		for _, worker := range workers {
			switch worker.Status {
			case "active":
				stats.ActiveWorkers++
			case "idle":
				stats.IdleWorkers++
			case "busy":
				stats.BusyWorkers++
			}
		}
	}

	// 计算处理速率 (tasks/minute)
	if stats.TaskStats.AvgProcessTime > 0 {
		stats.ProcessingRate = 60.0 / stats.TaskStats.AvgProcessTime
	}

	return stats, nil
}

// HealthCheck 健康检查
func (s *TaskService) HealthCheck(ctx context.Context) (bool, map[string]interface{}) {
	details := make(map[string]interface{})
	healthy := true

	// 检查数据库连接
	if err := s.db.PingContext(ctx); err != nil {
		details["database"] = map[string]interface{}{
			"status": "unhealthy",
			"error":  err.Error(),
		}
		healthy = false
	} else {
		details["database"] = map[string]interface{}{
			"status": "healthy",
		}
	}

	// 检查Redis连接
	if err := s.rdb.Ping(ctx).Err(); err != nil {
		details["redis"] = map[string]interface{}{
			"status": "unhealthy",
			"error":  err.Error(),
		}
		healthy = false
	} else {
		details["redis"] = map[string]interface{}{
			"status": "healthy",
		}
	}

	// 检查队列健康
	queueSize, err := s.rdb.LLen(ctx, s.getQueueKey("")).Result()
	if err != nil {
		details["queue"] = map[string]interface{}{
			"status": "unhealthy",
			"error":  err.Error(),
		}
		healthy = false
	} else {
		details["queue"] = map[string]interface{}{
			"status": "healthy",
			"size":   queueSize,
		}
	}

	return healthy, details
}

// 辅助方法

func (s *TaskService) enqueueTask(ctx context.Context, taskID string, priority model.TaskPriority) error {
	queueKey := s.getQueueKey(string(priority))
	return s.rdb.LPush(ctx, queueKey, taskID).Err()
}

func (s *TaskService) removeFromQueue(ctx context.Context, taskID string) {
	// 从所有可能的队列中移除
	priorities := []string{"low", "normal", "high", "critical"}
	for _, priority := range priorities {
		queueKey := s.getQueueKey(priority)
		s.rdb.LRem(ctx, queueKey, 0, taskID)
	}
}

func (s *TaskService) getQueueKey(priority string) string {
	if priority == "" {
		return s.config.Task.QueuePrefix
	}
	return fmt.Sprintf("%s:%s", s.config.Task.QueuePrefix, priority)
}

func (s *TaskService) getQueuePosition(ctx context.Context, taskID string, priority model.TaskPriority) int {
	queueKey := s.getQueueKey(string(priority))
	items, err := s.rdb.LRange(ctx, queueKey, 0, -1).Result()
	if err != nil {
		return -1
	}

	for i, item := range items {
		if item == taskID {
			return i + 1
		}
	}
	return -1
}

func (s *TaskService) getAverageProcessingTime(ctx context.Context, taskType model.TaskType) float64 {
	query := `
		SELECT AVG(EXTRACT(EPOCH FROM (completed_at - started_at)))
		FROM tasks 
		WHERE task_type = $1 AND status = 'completed' AND started_at IS NOT NULL AND completed_at IS NOT NULL
	`
	
	var avgTime sql.NullFloat64
	err := s.db.QueryRowContext(ctx, query, taskType).Scan(&avgTime)
	if err != nil || !avgTime.Valid {
		return 0
	}
	
	return avgTime.Float64
}

func (s *TaskService) getWorkersInfo(ctx context.Context) ([]model.WorkerInfo, error) {
	// 从Redis获取工作进程信息
	pattern := "worker:*"
	keys, err := s.rdb.Keys(ctx, pattern).Result()
	if err != nil {
		return nil, err
	}

	var workers []model.WorkerInfo
	for _, key := range keys {
		workerData, err := s.rdb.HGetAll(ctx, key).Result()
		if err != nil {
			continue
		}

		worker := model.WorkerInfo{
			ID:     workerData["id"],
			Status: workerData["status"],
		}

		// 解析其他字段...
		workers = append(workers, worker)
	}

	return workers, nil
}

// CreateBatchTasks 批量创建任务
func (s *TaskService) CreateBatchTasks(ctx context.Context, requests []model.TaskCreateRequest) ([]*model.TaskResponse, error) {
	var tasks []*model.TaskResponse
	
	// 使用事务
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	for _, req := range requests {
		task, err := s.createTaskInTx(ctx, tx, &req)
		if err != nil {
			return nil, err
		}
		tasks = append(tasks, task)
	}

	if err := tx.Commit(); err != nil {
		return nil, fmt.Errorf("failed to commit transaction: %w", err)
	}

	return tasks, nil
}

func (s *TaskService) createTaskInTx(ctx context.Context, tx *sql.Tx, req *model.TaskCreateRequest) (*model.TaskResponse, error) {
	// 与CreateTask类似的逻辑，但使用事务
	// 这里省略具体实现，逻辑与CreateTask相同
	return nil, nil
}

// GetQueueInfo 获取队列信息
func (s *TaskService) GetQueueInfo(ctx context.Context, taskType, priority string) (map[string]interface{}, error) {
	info := make(map[string]interface{})
	
	queueKey := s.getQueueKey(priority)
	size, err := s.rdb.LLen(ctx, queueKey).Result()
	if err != nil {
		return nil, err
	}
	
	info["queue_size"] = size
	info["queue_key"] = queueKey
	
	return info, nil
}

// UpdateTaskProgress 更新任务进度
func (s *TaskService) UpdateTaskProgress(ctx context.Context, taskID string, progress int, message string) error {
	now := time.Now()
	
	query := "UPDATE tasks SET progress = $1, updated_at = $2"
	args := []interface{}{progress, now}
	argIndex := 3
	
	if message != "" {
		query += fmt.Sprintf(", error_message = $%d", argIndex)
		args = append(args, message)
		argIndex++
	}
	
	query += fmt.Sprintf(" WHERE id = $%d", argIndex)
	args = append(args, taskID)
	
	result, err := s.db.ExecContext(ctx, query, args...)
	if err != nil {
		return fmt.Errorf("failed to update task progress: %w", err)
	}
	
	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}
	
	if rowsAffected == 0 {
		return ErrTaskNotFound
	}
	
	return nil
}