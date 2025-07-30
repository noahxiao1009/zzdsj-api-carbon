package handler

import (
	"context"
	"fmt"
	"mime/multipart"
	"net/http"
	"path/filepath"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
	"github.com/sirupsen/logrus"
	"golang.org/x/time/rate"

	"task-manager-service/internal/config"
	"task-manager-service/internal/model"
	"task-manager-service/internal/service"
)

type UploadHandler struct {
	taskService  *service.TaskService
	minioClient  *minio.Client
	rateLimiter  *rate.Limiter
	cfg          *config.Config
	log          *logrus.Entry
}

// FileUploadRequest 文件上传请求结构
type FileUploadRequest struct {
	KbID             string `form:"kb_id" binding:"required"`
	ChunkStrategy    string `form:"chunk_strategy"`
	EmbeddingModel   string `form:"embedding_model"`
	OverlapSize      int    `form:"overlap_size"`
	ChunkSize        int    `form:"chunk_size"`
	ProcessPriority  string `form:"process_priority"`
	ProcessImmediately bool `form:"process_immediately"`
}

// UploadResult 上传结果
type UploadResult struct {
	TaskID         string    `json:"task_id"`
	FileName       string    `json:"file_name"`
	FileSize       int64     `json:"file_size"`
	FileURL        string    `json:"file_url"`
	ContentType    string    `json:"content_type"`
	UploadedAt     time.Time `json:"uploaded_at"`
	Status         string    `json:"status"`
	Message        string    `json:"message"`
	QueuePosition  int       `json:"queue_position,omitempty"`
}

// BatchUploadResult 批量上传结果
type BatchUploadResult struct {
	TotalFiles     int            `json:"total_files"`
	SuccessCount   int            `json:"success_count"`
	FailedCount    int            `json:"failed_count"`
	Results        []UploadResult `json:"results"`
	BatchTaskID    string         `json:"batch_task_id,omitempty"`
	ProcessingTime float64        `json:"processing_time_ms"`
}

func NewUploadHandler(taskService *service.TaskService, cfg *config.Config) (*UploadHandler, error) {
	// 初始化MinIO客户端
	minioClient, err := minio.New(cfg.MinIO.Endpoint, &minio.Options{
		Creds:  credentials.NewStaticV4(cfg.MinIO.AccessKey, cfg.MinIO.SecretKey, ""),
		Secure: cfg.MinIO.UseSSL,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to initialize MinIO client: %w", err)
	}

	// 创建存储桶(如果不存在)
	ctx := context.Background()
	bucketName := cfg.MinIO.BucketName
	exists, err := minioClient.BucketExists(ctx, bucketName)
	if err != nil {
		return nil, fmt.Errorf("failed to check bucket existence: %w", err)
	}

	if !exists {
		err = minioClient.MakeBucket(ctx, bucketName, minio.MakeBucketOptions{})
		if err != nil {
			return nil, fmt.Errorf("failed to create bucket: %w", err)
		}
		logrus.Infof("Created MinIO bucket: %s", bucketName)
	}

	// 创建限流器 (每秒最多100个文件上传请求)
	rateLimiter := rate.NewLimiter(rate.Limit(cfg.Upload.RateLimit), cfg.Upload.BurstLimit)

	return &UploadHandler{
		taskService: taskService,
		minioClient: minioClient,
		rateLimiter: rateLimiter,
		cfg:         cfg,
		log:         logrus.WithField("component", "upload-handler"),
	}, nil
}

// UploadFile 单文件上传
func (h *UploadHandler) UploadFile(c *gin.Context) {
	startTime := time.Now()
	
	// 速率限制检查
	if !h.rateLimiter.Allow() {
		h.log.Warn("Rate limit exceeded for file upload")
		c.JSON(http.StatusTooManyRequests, gin.H{
			"error":   "Rate limit exceeded",
			"message": "Too many upload requests, please try again later",
		})
		return
	}

	// 解析请求参数
	var req FileUploadRequest
	if err := c.ShouldBind(&req); err != nil {
		h.log.Errorf("Invalid upload request: %v", err)
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Invalid request parameters",
			"message": err.Error(),
		})
		return
	}

	// 获取上传的文件
	file, fileHeader, err := c.Request.FormFile("file")
	if err != nil {
		h.log.Errorf("Failed to get uploaded file: %v", err)
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "No file uploaded",
			"message": "Please select a file to upload",
		})
		return
	}
	defer file.Close()

	// 验证文件大小
	if fileHeader.Size > h.cfg.Upload.MaxFileSize {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "File too large",
			"message": fmt.Sprintf("File size exceeds limit of %d MB", h.cfg.Upload.MaxFileSize/(1024*1024)),
		})
		return
	}

	// 验证文件类型
	contentType := fileHeader.Header.Get("Content-Type")
	if !h.isAllowedFileType(contentType, fileHeader.Filename) {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "File type not allowed",
			"message": "Only PDF, DOC, DOCX, TXT, and MD files are supported",
		})
		return
	}

	// 上传文件到MinIO
	result, err := h.uploadToMinIO(c.Request.Context(), file, fileHeader, &req)
	if err != nil {
		h.log.Errorf("Failed to upload file to MinIO: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "File upload failed",
			"message": err.Error(),
		})
		return
	}

	processingTime := time.Since(startTime).Seconds() * 1000
	h.log.Infof("File uploaded successfully: %s (%.2fms)", result.FileName, processingTime)

	c.JSON(http.StatusCreated, result)
}

// BatchUploadFiles 批量文件上传
func (h *UploadHandler) BatchUploadFiles(c *gin.Context) {
	startTime := time.Now()

	// 解析请求参数
	var req FileUploadRequest
	if err := c.ShouldBind(&req); err != nil {
		h.log.Errorf("Invalid batch upload request: %v", err)
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Invalid request parameters",
			"message": err.Error(),
		})
		return
	}

	// 获取多个文件
	form, err := c.MultipartForm()
	if err != nil {
		h.log.Errorf("Failed to parse multipart form: %v", err)
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Invalid multipart form",
			"message": err.Error(),
		})
		return
	}

	files := form.File["files"]
	if len(files) == 0 {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "No files uploaded",
			"message": "Please select files to upload",
		})
		return
	}

	// 限制批量上传文件数量
	if len(files) > h.cfg.Upload.MaxBatchSize {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Too many files",
			"message": fmt.Sprintf("Maximum %d files allowed per batch", h.cfg.Upload.MaxBatchSize),
		})
		return
	}

	// 并发上传文件
	results := h.processBatchUpload(c.Request.Context(), files, &req)

	// 如果有成功上传的文件，创建批量处理任务
	var batchTaskID string
	successResults := make([]UploadResult, 0)
	for _, result := range results {
		if result.Status == "uploaded" {
			successResults = append(successResults, result)
		}
	}

	if len(successResults) > 0 && req.ProcessImmediately {
		batchTaskID, err = h.createBatchProcessingTask(&req, successResults)
		if err != nil {
			h.log.Errorf("Failed to create batch processing task: %v", err)
		}
	}

	processingTime := time.Since(startTime).Seconds() * 1000
	
	batchResult := BatchUploadResult{
		TotalFiles:     len(files),
		SuccessCount:   len(successResults),
		FailedCount:    len(files) - len(successResults),
		Results:        results,
		BatchTaskID:    batchTaskID,
		ProcessingTime: processingTime,
	}

	h.log.Infof("Batch upload completed: %d/%d files successful (%.2fms)", 
		batchResult.SuccessCount, batchResult.TotalFiles, processingTime)

	c.JSON(http.StatusCreated, batchResult)
}

// UploadFromURL 从URL上传文件
func (h *UploadHandler) UploadFromURL(c *gin.Context) {
	var reqBody struct {
		URL             string `json:"url" binding:"required"`
		KbID            string `json:"kb_id" binding:"required"`
		ChunkStrategy   string `json:"chunk_strategy"`
		EmbeddingModel  string `json:"embedding_model"`
		ProcessPriority string `json:"process_priority"`
		ProcessImmediately bool `json:"process_immediately"`
	}

	if err := c.ShouldBindJSON(&reqBody); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Invalid request body",
			"message": err.Error(),
		})
		return
	}

	// 创建URL下载任务
	taskPayload := model.JSONMap{
		"url":              reqBody.URL,
		"kb_id":            reqBody.KbID,
		"chunk_strategy":   reqBody.ChunkStrategy,
		"embedding_model":  reqBody.EmbeddingModel,
		"process_immediately": reqBody.ProcessImmediately,
	}

	taskReq := &model.TaskCreateRequest{
		TaskType: "url_download_processing",
		KbID:     reqBody.KbID,
		Priority: model.TaskPriority(reqBody.ProcessPriority),
		Payload:  taskPayload,
		MaxRetries: 3,
		Timeout:    600, // 10分钟超时
	}

	task, err := h.taskService.CreateTask(c.Request.Context(), taskReq)
	if err != nil {
		h.log.Errorf("Failed to create URL download task: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to create download task",
			"message": err.Error(),
		})
		return
	}

	c.JSON(http.StatusCreated, gin.H{
		"task_id": task.ID,
		"url":     reqBody.URL,
		"status":  "queued",
		"message": "URL download task created successfully",
	})
}

// uploadToMinIO 上传文件到MinIO并创建处理任务
func (h *UploadHandler) uploadToMinIO(ctx context.Context, file multipart.File, fileHeader *multipart.FileHeader, req *FileUploadRequest) (*UploadResult, error) {
	// 生成唯一文件名
	fileExt := filepath.Ext(fileHeader.Filename)
	objectName := fmt.Sprintf("%s/%s%s", req.KbID, uuid.New().String(), fileExt)

	// 上传到MinIO
	info, err := h.minioClient.PutObject(ctx, h.cfg.MinIO.BucketName, objectName, file, fileHeader.Size, minio.PutObjectOptions{
		ContentType: fileHeader.Header.Get("Content-Type"),
		UserMetadata: map[string]string{
			"original-filename": fileHeader.Filename,
			"kb-id":            req.KbID,
			"uploaded-at":      time.Now().Format(time.RFC3339),
		},
	})
	if err != nil {
		return nil, fmt.Errorf("failed to upload to MinIO: %w", err)
	}

	// 生成文件访问URL
	fileURL := fmt.Sprintf("%s/%s/%s", h.cfg.MinIO.Endpoint, h.cfg.MinIO.BucketName, objectName)
	if h.cfg.MinIO.UseSSL {
		fileURL = "https://" + fileURL
	} else {
		fileURL = "http://" + fileURL
	}

	result := &UploadResult{
		FileName:    fileHeader.Filename,
		FileSize:    info.Size,
		FileURL:     fileURL,
		ContentType: fileHeader.Header.Get("Content-Type"),
		UploadedAt:  time.Now(),
		Status:      "uploaded",
		Message:     "File uploaded successfully",
	}

	// 如果需要立即处理，创建处理任务
	if req.ProcessImmediately {
		taskID, queuePos, err := h.createProcessingTask(ctx, objectName, fileHeader, req)
		if err != nil {
			h.log.Errorf("Failed to create processing task: %v", err)
			result.Status = "upload_completed_task_failed"
			result.Message = "File uploaded but failed to create processing task"
		} else {
			result.TaskID = taskID
			result.QueuePosition = queuePos
			result.Status = "queued_for_processing"
			result.Message = "File uploaded and queued for processing"
		}
	}

	return result, nil
}

// processBatchUpload 并发处理批量上传
func (h *UploadHandler) processBatchUpload(ctx context.Context, files []*multipart.FileHeader, req *FileUploadRequest) []UploadResult {
	results := make([]UploadResult, len(files))
	var wg sync.WaitGroup
	semaphore := make(chan struct{}, h.cfg.Upload.ConcurrencyLimit) // 控制并发数

	for i, fileHeader := range files {
		wg.Add(1)
		go func(index int, fh *multipart.FileHeader) {
			defer wg.Done()
			
			// 获取信号量
			semaphore <- struct{}{}
			defer func() { <-semaphore }()

			// 打开文件
			file, err := fh.Open()
			if err != nil {
				results[index] = UploadResult{
					FileName: fh.Filename,
					Status:   "failed",
					Message:  fmt.Sprintf("Failed to open file: %v", err),
				}
				return
			}
			defer file.Close()

			// 验证文件大小和类型
			if fh.Size > h.cfg.Upload.MaxFileSize {
				results[index] = UploadResult{
					FileName: fh.Filename,
					Status:   "failed",
					Message:  "File size exceeds limit",
				}
				return
			}

			contentType := fh.Header.Get("Content-Type")
			if !h.isAllowedFileType(contentType, fh.Filename) {
				results[index] = UploadResult{
					FileName: fh.Filename,
					Status:   "failed",
					Message:  "File type not allowed",
				}
				return
			}

			// 上传文件
			result, err := h.uploadToMinIO(ctx, file, fh, req)
			if err != nil {
				results[index] = UploadResult{
					FileName: fh.Filename,
					Status:   "failed",
					Message:  err.Error(),
				}
				return
			}

			results[index] = *result
		}(i, fileHeader)
	}

	wg.Wait()
	return results
}

// createProcessingTask 创建文档处理任务
func (h *UploadHandler) createProcessingTask(ctx context.Context, objectName string, fileHeader *multipart.FileHeader, req *FileUploadRequest) (string, int, error) {
	taskPayload := model.JSONMap{
		"file_path":        objectName,
		"original_filename": fileHeader.Filename,
		"file_size":        fileHeader.Size,
		"content_type":     fileHeader.Header.Get("Content-Type"),
		"kb_id":           req.KbID,
		"chunk_strategy":  req.ChunkStrategy,
		"embedding_model": req.EmbeddingModel,
		"chunk_size":      req.ChunkSize,
		"overlap_size":    req.OverlapSize,
		"bucket_name":     h.cfg.MinIO.BucketName,
	}

	priority := model.TaskPriorityNormal
	if req.ProcessPriority != "" {
		priority = model.TaskPriority(req.ProcessPriority)
	}

	taskCreateReq := &model.TaskCreateRequest{
		TaskType:   model.TaskTypeDocumentProcessing,
		KbID:       req.KbID,
		Priority:   priority,
		Payload:    taskPayload,
		MaxRetries: 3,
		Timeout:    1800, // 30分钟超时
	}

	task, err := h.taskService.CreateTask(ctx, taskCreateReq)
	if err != nil {
		return "", 0, err
	}

	// 获取队列位置（简化实现）
	queuePos := 1

	return task.ID, queuePos, nil
}

// createBatchProcessingTask 创建批量处理任务
func (h *UploadHandler) createBatchProcessingTask(req *FileUploadRequest, results []UploadResult) (string, error) {
	batchItems := make([]map[string]interface{}, len(results))
	for i, result := range results {
		batchItems[i] = map[string]interface{}{
			"file_name":    result.FileName,
			"file_url":     result.FileURL,
			"file_size":    result.FileSize,
			"content_type": result.ContentType,
		}
	}

	taskPayload := model.JSONMap{
		"batch_items":     batchItems,
		"kb_id":          req.KbID,
		"chunk_strategy": req.ChunkStrategy,
		"embedding_model": req.EmbeddingModel,
		"chunk_size":     req.ChunkSize,
		"overlap_size":   req.OverlapSize,
		"total_files":    len(results),
	}

	priority := model.TaskPriorityNormal
	if req.ProcessPriority != "" {
		priority = model.TaskPriority(req.ProcessPriority)
	}

	taskCreateReq := &model.TaskCreateRequest{
		TaskType:   model.TaskTypeBatchProcessing,
		KbID:       req.KbID,
		Priority:   priority,
		Payload:    taskPayload,
		MaxRetries: 2,
		Timeout:    3600, // 1小时超时
	}

	task, err := h.taskService.CreateTask(context.Background(), taskCreateReq)
	if err != nil {
		return "", err
	}

	return task.ID, nil
}

// isAllowedFileType 检查文件类型是否允许
func (h *UploadHandler) isAllowedFileType(contentType, filename string) bool {
	allowedTypes := map[string]bool{
		"application/pdf":  true,
		"application/msword": true,
		"application/vnd.openxmlformats-officedocument.wordprocessingml.document": true,
		"text/plain": true,
		"text/markdown": true,
		"text/html": true,
	}

	// 检查MIME类型
	if allowedTypes[contentType] {
		return true
	}

	// 检查文件扩展名
	ext := filepath.Ext(filename)
	allowedExtensions := map[string]bool{
		".pdf":  true,
		".doc":  true,
		".docx": true,
		".txt":  true,
		".md":   true,
		".html": true,
		".htm":  true,
	}

	return allowedExtensions[ext]
}

// GetUploadStats 获取上传统计
func (h *UploadHandler) GetUploadStats(c *gin.Context) {
	// 从任务服务获取上传相关统计
	kbID := c.Query("kb_id")
	
	stats, err := h.taskService.GetTaskStats(c.Request.Context(), kbID)
	if err != nil {
		h.log.Errorf("Failed to get upload stats: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to get upload statistics",
			"message": err.Error(),
		})
		return
	}

	// 添加上传相关的统计信息
	uploadStats := gin.H{
		"task_stats": stats,
		"upload_config": gin.H{
			"max_file_size":     h.cfg.Upload.MaxFileSize,
			"max_batch_size":    h.cfg.Upload.MaxBatchSize,
			"concurrency_limit": h.cfg.Upload.ConcurrencyLimit,
			"rate_limit":        h.cfg.Upload.RateLimit,
		},
		"storage_info": gin.H{
			"bucket_name": h.cfg.MinIO.BucketName,
			"endpoint":    h.cfg.MinIO.Endpoint,
		},
	}

	c.JSON(http.StatusOK, uploadStats)
}