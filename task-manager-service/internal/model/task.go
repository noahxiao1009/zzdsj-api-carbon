package model

import (
	"database/sql/driver"
	"encoding/json"
	"time"
)

// TaskStatus 任务状态枚举
type TaskStatus string

const (
	TaskStatusQueued     TaskStatus = "queued"
	TaskStatusProcessing TaskStatus = "processing"
	TaskStatusCompleted  TaskStatus = "completed"
	TaskStatusFailed     TaskStatus = "failed"
	TaskStatusCanceled   TaskStatus = "canceled"
	TaskStatusRetrying   TaskStatus = "retrying"
)

// TaskPriority 任务优先级枚举
type TaskPriority string

const (
	TaskPriorityLow    TaskPriority = "low"
	TaskPriorityNormal TaskPriority = "normal"
	TaskPriorityHigh   TaskPriority = "high"
	TaskPriorityCritical TaskPriority = "critical"
)

// TaskType 任务类型枚举
type TaskType string

const (
	TaskTypeDocumentProcessing  TaskType = "document_processing"
	TaskTypeBatchProcessing     TaskType = "batch_processing"
	TaskTypeKnowledgeIndexing   TaskType = "knowledge_indexing"
	TaskTypeEmbeddingGeneration TaskType = "embedding_generation"
	TaskTypeVectorStorage       TaskType = "vector_storage"
	TaskTypeHealthCheck         TaskType = "health_check"
	TaskTypeURLDownload         TaskType = "url_download_processing"
)

// JSONMap 用于处理JSON字段
type JSONMap map[string]interface{}

func (j JSONMap) Value() (driver.Value, error) {
	return json.Marshal(j)
}

func (j *JSONMap) Scan(value interface{}) error {
	if value == nil {
		*j = make(JSONMap)
		return nil
	}
	
	switch v := value.(type) {
	case []byte:
		return json.Unmarshal(v, j)
	case string:
		return json.Unmarshal([]byte(v), j)
	default:
		*j = make(JSONMap)
		return nil
	}
}

// Task 任务模型
type Task struct {
	ID            string       `json:"id" db:"id"`
	TaskType      TaskType     `json:"task_type" db:"task_type"`
	Status        TaskStatus   `json:"status" db:"status"`
	Priority      TaskPriority `json:"priority" db:"priority"`
	KbID          string       `json:"kb_id" db:"kb_id"`
	Payload       JSONMap      `json:"payload" db:"payload"`
	Result        JSONMap      `json:"result" db:"result"`
	Progress      int          `json:"progress" db:"progress"`
	RetryCount    int          `json:"retry_count" db:"retry_count"`
	MaxRetries    int          `json:"max_retries" db:"max_retries"`
	ErrorMessage  string       `json:"error_message" db:"error_message"`
	WorkerID      string       `json:"worker_id" db:"worker_id"`
	CreatedAt     time.Time    `json:"created_at" db:"created_at"`
	UpdatedAt     time.Time    `json:"updated_at" db:"updated_at"`
	StartedAt     *time.Time   `json:"started_at" db:"started_at"`
	CompletedAt   *time.Time   `json:"completed_at" db:"completed_at"`
	ScheduledFor  *time.Time   `json:"scheduled_for" db:"scheduled_for"`
	Timeout       int          `json:"timeout" db:"timeout"` // 超时时间(秒)
}

// TaskCreateRequest 创建任务请求
type TaskCreateRequest struct {
	TaskType    TaskType     `json:"task_type" binding:"required"`
	KbID        string       `json:"kb_id" binding:"required"`
	Priority    TaskPriority `json:"priority"`
	Payload     JSONMap      `json:"payload" binding:"required"`
	MaxRetries  int          `json:"max_retries"`
	Timeout     int          `json:"timeout"`
	ScheduleFor *time.Time   `json:"schedule_for"`
}

// TaskResponse 任务响应
type TaskResponse struct {
	*Task
	EstimatedCompletion *time.Time `json:"estimated_completion"`
	QueuePosition       int        `json:"queue_position"`
}

// TaskListRequest 任务列表查询请求
type TaskListRequest struct {
	KbID        string       `form:"kb_id"`
	Status      TaskStatus   `form:"status"`
	TaskType    TaskType     `form:"task_type"`
	Priority    TaskPriority `form:"priority"`
	Page        int          `form:"page" binding:"min=1"`
	PageSize    int          `form:"page_size" binding:"min=1,max=100"`
	SortBy      string       `form:"sort_by"`
	SortOrder   string       `form:"sort_order"`
}

// TaskStats 任务统计信息
type TaskStats struct {
	TotalTasks      int64            `json:"total_tasks"`
	QueuedTasks     int64            `json:"queued_tasks"`
	ProcessingTasks int64            `json:"processing_tasks"`
	CompletedTasks  int64            `json:"completed_tasks"`
	FailedTasks     int64            `json:"failed_tasks"`
	StatusBreakdown map[string]int64 `json:"status_breakdown"`
	TypeBreakdown   map[string]int64 `json:"type_breakdown"`
	AvgProcessTime  float64          `json:"avg_process_time"`
	SuccessRate     float64          `json:"success_rate"`
}

// WorkerInfo 工作进程信息
type WorkerInfo struct {
	ID              string     `json:"id"`
	Status          string     `json:"status"` // idle, busy, stopped
	CurrentTaskID   string     `json:"current_task_id"`
	TasksProcessed  int64      `json:"tasks_processed"`
	TasksSucceeded  int64      `json:"tasks_succeeded"`
	TasksFailed     int64      `json:"tasks_failed"`
	LastHeartbeat   time.Time  `json:"last_heartbeat"`
	StartedAt       time.Time  `json:"started_at"`
	LastTaskAt      *time.Time `json:"last_task_at"`
	AverageTaskTime float64    `json:"average_task_time"`
}

// SystemStats 系统统计信息
type SystemStats struct {
	TotalWorkers    int          `json:"total_workers"`
	ActiveWorkers   int          `json:"active_workers"`
	IdleWorkers     int          `json:"idle_workers"`
	BusyWorkers     int          `json:"busy_workers"`
	QueueSize       int64        `json:"queue_size"`
	ProcessingRate  float64      `json:"processing_rate"` // tasks/minute
	Workers         []WorkerInfo `json:"workers"`
	TaskStats       TaskStats    `json:"task_stats"`
}

// IsValidStatus 检查任务状态是否有效
func (t TaskStatus) IsValid() bool {
	switch t {
	case TaskStatusQueued, TaskStatusProcessing, TaskStatusCompleted, 
		 TaskStatusFailed, TaskStatusCanceled, TaskStatusRetrying:
		return true
	default:
		return false
	}
}

// IsValidPriority 检查优先级是否有效
func (p TaskPriority) IsValid() bool {
	switch p {
	case TaskPriorityLow, TaskPriorityNormal, TaskPriorityHigh, TaskPriorityCritical:
		return true
	default:
		return false
	}
}

// IsValidTaskType 检查任务类型是否有效
func (t TaskType) IsValid() bool {
	switch t {
	case TaskTypeDocumentProcessing, TaskTypeBatchProcessing, TaskTypeKnowledgeIndexing,
		 TaskTypeEmbeddingGeneration, TaskTypeVectorStorage, TaskTypeHealthCheck, TaskTypeURLDownload:
		return true
	default:
		return false
	}
}

// GetPriorityValue 获取优先级数值(用于排序)
func (p TaskPriority) GetValue() int {
	switch p {
	case TaskPriorityCritical:
		return 4
	case TaskPriorityHigh:
		return 3
	case TaskPriorityNormal:
		return 2
	case TaskPriorityLow:
		return 1
	default:
		return 2
	}
}

// CanRetry 检查任务是否可以重试
func (t *Task) CanRetry() bool {
	return t.RetryCount < t.MaxRetries && 
		   (t.Status == TaskStatusFailed || t.Status == TaskStatusRetrying)
}

// IsTerminal 检查任务是否已结束
func (t *Task) IsTerminal() bool {
	return t.Status == TaskStatusCompleted || 
		   t.Status == TaskStatusFailed || 
		   t.Status == TaskStatusCanceled
}

// Duration 获取任务执行时长
func (t *Task) Duration() time.Duration {
	if t.StartedAt == nil {
		return 0
	}
	
	endTime := time.Now()
	if t.CompletedAt != nil {
		endTime = *t.CompletedAt
	}
	
	return endTime.Sub(*t.StartedAt)
}