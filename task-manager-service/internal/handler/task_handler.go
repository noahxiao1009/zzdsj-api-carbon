package handler

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
	"github.com/sirupsen/logrus"

	"task-manager-service/internal/model"
	"task-manager-service/internal/service"
)

type TaskHandler struct {
	taskService *service.TaskService
	log         *logrus.Entry
}

func NewTaskHandler(taskService *service.TaskService) *TaskHandler {
	return &TaskHandler{
		taskService: taskService,
		log:         logrus.WithField("component", "task-handler"),
	}
}

// CreateTask 创建任务
func (h *TaskHandler) CreateTask(c *gin.Context) {
	var req model.TaskCreateRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		h.log.Errorf("Invalid request body: %v", err)
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Invalid request body",
			"message": err.Error(),
		})
		return
	}

	// 验证请求参数
	if !req.TaskType.IsValid() {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Invalid task type",
			"message": "Task type must be one of: document_processing, batch_processing, knowledge_indexing, embedding_generation, vector_storage, health_check, url_download_processing",
		})
		return
	}

	if req.Priority != "" && !req.Priority.IsValid() {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Invalid priority",
			"message": "Priority must be one of: low, normal, high, critical",
		})
		return
	}

	task, err := h.taskService.CreateTask(c.Request.Context(), &req)
	if err != nil {
		h.log.Errorf("Failed to create task: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to create task",
			"message": err.Error(),
		})
		return
	}

	h.log.Infof("Task created successfully: %s", task.ID)
	c.JSON(http.StatusCreated, task)
}

// GetTask 获取任务详情
func (h *TaskHandler) GetTask(c *gin.Context) {
	taskID := c.Param("id")
	if taskID == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Missing task ID",
			"message": "Task ID is required",
		})
		return
	}

	task, err := h.taskService.GetTask(c.Request.Context(), taskID)
	if err != nil {
		if err == service.ErrTaskNotFound {
			c.JSON(http.StatusNotFound, gin.H{
				"error":   "Task not found",
				"message": "Task with specified ID does not exist",
			})
			return
		}
		
		h.log.Errorf("Failed to get task %s: %v", taskID, err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to get task",
			"message": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, task)
}

// ListTasks 获取任务列表
func (h *TaskHandler) ListTasks(c *gin.Context) {
	var req model.TaskListRequest
	if err := c.ShouldBindQuery(&req); err != nil {
		h.log.Errorf("Invalid query parameters: %v", err)
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Invalid query parameters",
			"message": err.Error(),
		})
		return
	}

	// 设置默认值
	if req.Page <= 0 {
		req.Page = 1
	}
	if req.PageSize <= 0 {
		req.PageSize = 20
	}
	if req.PageSize > 100 {
		req.PageSize = 100
	}

	tasks, total, err := h.taskService.ListTasks(c.Request.Context(), &req)
	if err != nil {
		h.log.Errorf("Failed to list tasks: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to list tasks",
			"message": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"tasks": tasks,
		"pagination": gin.H{
			"page":       req.Page,
			"page_size":  req.PageSize,
			"total":      total,
			"total_pages": (total + int64(req.PageSize) - 1) / int64(req.PageSize),
		},
	})
}

// CancelTask 取消任务
func (h *TaskHandler) CancelTask(c *gin.Context) {
	taskID := c.Param("id")
	if taskID == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Missing task ID",
			"message": "Task ID is required",
		})
		return
	}

	err := h.taskService.CancelTask(c.Request.Context(), taskID)
	if err != nil {
		if err == service.ErrTaskNotFound {
			c.JSON(http.StatusNotFound, gin.H{
				"error":   "Task not found",
				"message": "Task with specified ID does not exist",
			})
			return
		}
		
		if err == service.ErrTaskNotCancelable {
			c.JSON(http.StatusConflict, gin.H{
				"error":   "Task not cancelable",
				"message": "Task is in a state that cannot be canceled",
			})
			return
		}

		h.log.Errorf("Failed to cancel task %s: %v", taskID, err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to cancel task",
			"message": err.Error(),
		})
		return
	}

	h.log.Infof("Task canceled successfully: %s", taskID)
	c.JSON(http.StatusOK, gin.H{
		"message": "Task canceled successfully",
		"task_id": taskID,
	})
}

// RetryTask 重试任务
func (h *TaskHandler) RetryTask(c *gin.Context) {
	taskID := c.Param("id")
	if taskID == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Missing task ID",
			"message": "Task ID is required",
		})
		return
	}

	task, err := h.taskService.RetryTask(c.Request.Context(), taskID)
	if err != nil {
		if err == service.ErrTaskNotFound {
			c.JSON(http.StatusNotFound, gin.H{
				"error":   "Task not found",
				"message": "Task with specified ID does not exist",
			})
			return
		}
		
		if err == service.ErrTaskNotRetryable {
			c.JSON(http.StatusConflict, gin.H{
				"error":   "Task not retryable",
				"message": "Task cannot be retried in current state or has exceeded max retries",
			})
			return
		}

		h.log.Errorf("Failed to retry task %s: %v", taskID, err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to retry task",
			"message": err.Error(),
		})
		return
	}

	h.log.Infof("Task retried successfully: %s", taskID)
	c.JSON(http.StatusOK, task)
}

// GetTaskStats 获取任务统计信息
func (h *TaskHandler) GetTaskStats(c *gin.Context) {
	kbID := c.Query("kb_id")
	
	stats, err := h.taskService.GetTaskStats(c.Request.Context(), kbID)
	if err != nil {
		h.log.Errorf("Failed to get task stats: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to get task statistics",
			"message": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, stats)
}

// GetSystemStats 获取系统统计信息
func (h *TaskHandler) GetSystemStats(c *gin.Context) {
	stats, err := h.taskService.GetSystemStats(c.Request.Context())
	if err != nil {
		h.log.Errorf("Failed to get system stats: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to get system statistics",
			"message": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, stats)
}

// HealthCheck 健康检查
func (h *TaskHandler) HealthCheck(c *gin.Context) {
	healthy, details := h.taskService.HealthCheck(c.Request.Context())
	
	status := http.StatusOK
	if !healthy {
		status = http.StatusServiceUnavailable
	}

	c.JSON(status, gin.H{
		"status":  map[bool]string{true: "healthy", false: "unhealthy"}[healthy],
		"service": "task-manager",
		"version": "1.0.0",
		"details": details,
	})
}

// CreateBatchTasks 批量创建任务
func (h *TaskHandler) CreateBatchTasks(c *gin.Context) {
	var requests []model.TaskCreateRequest
	if err := c.ShouldBindJSON(&requests); err != nil {
		h.log.Errorf("Invalid request body: %v", err)
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Invalid request body",
			"message": err.Error(),
		})
		return
	}

	if len(requests) == 0 {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Empty request",
			"message": "At least one task is required",
		})
		return
	}

	if len(requests) > 100 {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Too many tasks",
			"message": "Maximum 100 tasks allowed per batch",
		})
		return
	}

	tasks, err := h.taskService.CreateBatchTasks(c.Request.Context(), requests)
	if err != nil {
		h.log.Errorf("Failed to create batch tasks: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to create batch tasks",
			"message": err.Error(),
		})
		return
	}

	h.log.Infof("Batch tasks created successfully: %d tasks", len(tasks))
	c.JSON(http.StatusCreated, gin.H{
		"tasks": tasks,
		"count": len(tasks),
	})
}

// GetQueueInfo 获取队列信息
func (h *TaskHandler) GetQueueInfo(c *gin.Context) {
	taskType := c.Query("task_type")
	priority := c.Query("priority")
	
	info, err := h.taskService.GetQueueInfo(c.Request.Context(), taskType, priority)
	if err != nil {
		h.log.Errorf("Failed to get queue info: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to get queue information",
			"message": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, info)
}

// UpdateTaskProgress 更新任务进度
func (h *TaskHandler) UpdateTaskProgress(c *gin.Context) {
	taskID := c.Param("id")
	if taskID == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Missing task ID",
			"message": "Task ID is required",
		})
		return
	}

	progressStr := c.PostForm("progress")
	progress, err := strconv.Atoi(progressStr)
	if err != nil || progress < 0 || progress > 100 {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Invalid progress",
			"message": "Progress must be an integer between 0 and 100",
		})
		return
	}

	message := c.PostForm("message")

	err = h.taskService.UpdateTaskProgress(c.Request.Context(), taskID, progress, message)
	if err != nil {
		if err == service.ErrTaskNotFound {
			c.JSON(http.StatusNotFound, gin.H{
				"error":   "Task not found",
				"message": "Task with specified ID does not exist",
			})
			return
		}

		h.log.Errorf("Failed to update task progress %s: %v", taskID, err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to update task progress",
			"message": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message":  "Task progress updated successfully",
		"task_id":  taskID,
		"progress": progress,
	})
}