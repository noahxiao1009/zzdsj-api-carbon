package service

import (
	"context"
	"fmt"
	"sync"
	"time"

	log "github.com/sirupsen/logrus"

	"vector-processing-service/internal/config"
	"vector-processing-service/internal/storage"
	"vector-processing-service/pkg/embedding"
	"vector-processing-service/pkg/metrics"
)

// VectorService 向量处理服务
type VectorService struct {
	storage          *storage.Manager
	embeddingService *embedding.Service
	config           *config.Config
	
	// 工作池
	workers       chan struct{}
	requestQueue  chan *ProcessingRequest
	responseMap   sync.Map
	
	// 统计信息
	stats *ServiceStats
	mutex sync.RWMutex
}

// ProcessingRequest 处理请求
type ProcessingRequest struct {
	ID           string
	Type         RequestType
	Data         interface{}
	ResponseChan chan *ProcessingResponse
	Context      context.Context
	CreatedAt    time.Time
}

// ProcessingResponse 处理响应
type ProcessingResponse struct {
	ID      string
	Success bool
	Data    interface{}
	Error   error
	Duration time.Duration
}

// RequestType 请求类型
type RequestType int

const (
	RequestTypeEmbedding RequestType = iota
	RequestTypeBatchEmbedding
	RequestTypeVectorStorage
	RequestTypeBatchVectorStorage
	RequestTypeSimilarity
)

// ServiceStats 服务统计
type ServiceStats struct {
	TotalRequests     int64
	SuccessRequests   int64
	FailedRequests    int64
	AverageLatency    time.Duration
	CurrentWorkers    int
	QueueLength       int
	ProcessingRequests int64
}

// EmbeddingRequest 嵌入请求
type EmbeddingRequest struct {
	RequestID string
	Text      string
	Model     string
	KBId      string
	Metadata  map[string]string
}

// EmbeddingResponse 嵌入响应
type EmbeddingResponse struct {
	RequestID       string
	Embedding       []float32
	Dimension       int
	Model           string
	ProcessingTime  time.Duration
}

// BatchEmbeddingRequest 批量嵌入请求
type BatchEmbeddingRequest struct {
	BatchID           string
	Requests          []*EmbeddingRequest
	BatchSize         int
	ParallelProcessing bool
}

// BatchEmbeddingResponse 批量嵌入响应
type BatchEmbeddingResponse struct {
	BatchID             string
	Responses           []*EmbeddingResponse
	TotalCount          int
	SuccessCount        int
	FailedCount         int
	TotalProcessingTime time.Duration
}

// VectorStorageRequest 向量存储请求
type VectorStorageRequest struct {
	RequestID      string
	CollectionName string
	DocumentID     string
	ChunkID        string
	Vector         []float32
	Metadata       map[string]string
	KBId           string
}

// VectorStorageResponse 向量存储响应
type VectorStorageResponse struct {
	RequestID   string
	VectorID    string
	StorageTime time.Duration
}

// SimilarityRequest 相似度请求
type SimilarityRequest struct {
	RequestID      string
	QueryVector    []float32
	TargetVector   []float32
	SimilarityType string
}

// SimilarityResponse 相似度响应
type SimilarityResponse struct {
	RequestID       string
	SimilarityScore float32
	SimilarityType  string
}

// NewVectorService 创建向量服务
func NewVectorService(
	storage *storage.Manager,
	embeddingService *embedding.Service,
	config *config.Config,
) *VectorService {
	service := &VectorService{
		storage:          storage,
		embeddingService: embeddingService,
		config:           config,
		workers:          make(chan struct{}, config.Processing.Workers),
		requestQueue:     make(chan *ProcessingRequest, config.Processing.QueueSize),
		stats:            &ServiceStats{},
	}

	// 启动工作池
	service.startWorkerPool()

	return service
}

// GenerateEmbedding 生成嵌入向量
func (s *VectorService) GenerateEmbedding(ctx context.Context, req *EmbeddingRequest) (*EmbeddingResponse, error) {
	start := time.Now()
	defer func() {
		metrics.EmbeddingRequestDuration.Observe(time.Since(start).Seconds())
		metrics.EmbeddingRequestsTotal.Inc()
	}()

	log.WithFields(log.Fields{
		"request_id": req.RequestID,
		"model":      req.Model,
		"text_len":   len(req.Text),
	}).Info("开始生成嵌入向量")

	// 生成嵌入向量
	embedding, err := s.embeddingService.GenerateEmbedding(ctx, req.Text, req.Model)
	if err != nil {
		metrics.EmbeddingRequestsTotal.Inc()
		log.WithError(err).WithField("request_id", req.RequestID).Error("生成嵌入向量失败")
		return nil, fmt.Errorf("生成嵌入向量失败: %w", err)
	}

	response := &EmbeddingResponse{
		RequestID:      req.RequestID,
		Embedding:      embedding,
		Dimension:      len(embedding),
		Model:          req.Model,
		ProcessingTime: time.Since(start),
	}

	// 更新统计
	s.updateStats(true, time.Since(start))

	log.WithFields(log.Fields{
		"request_id": req.RequestID,
		"dimension":  len(embedding),
		"duration":   time.Since(start),
	}).Info("嵌入向量生成完成")

	return response, nil
}

// BatchGenerateEmbeddings 批量生成嵌入向量
func (s *VectorService) BatchGenerateEmbeddings(ctx context.Context, req *BatchEmbeddingRequest) (*BatchEmbeddingResponse, error) {
	start := time.Now()
	defer func() {
		metrics.BatchEmbeddingRequestDuration.Observe(time.Since(start).Seconds())
		metrics.BatchEmbeddingRequestsTotal.Inc()
	}()

	log.WithFields(log.Fields{
		"batch_id":    req.BatchID,
		"batch_size":  len(req.Requests),
		"parallel":    req.ParallelProcessing,
	}).Info("开始批量生成嵌入向量")

	var responses []*EmbeddingResponse
	var successCount, failedCount int

	if req.ParallelProcessing {
		// 并行处理
		responses = s.processEmbeddingsConcurrently(ctx, req.Requests)
	} else {
		// 串行处理
		responses = s.processEmbeddingsSerially(ctx, req.Requests)
	}

	// 统计结果
	for _, resp := range responses {
		if resp != nil {
			successCount++
		} else {
			failedCount++
		}
	}

	batchResponse := &BatchEmbeddingResponse{
		BatchID:             req.BatchID,
		Responses:           responses,
		TotalCount:          len(req.Requests),
		SuccessCount:        successCount,
		FailedCount:         failedCount,
		TotalProcessingTime: time.Since(start),
	}

	log.WithFields(log.Fields{
		"batch_id":     req.BatchID,
		"total":        len(req.Requests),
		"success":      successCount,
		"failed":       failedCount,
		"duration":     time.Since(start),
	}).Info("批量嵌入向量生成完成")

	return batchResponse, nil
}

// StoreVector 存储向量
func (s *VectorService) StoreVector(ctx context.Context, req *VectorStorageRequest) (*VectorStorageResponse, error) {
	start := time.Now()
	defer func() {
		metrics.VectorStorageRequestDuration.Observe(time.Since(start).Seconds())
		metrics.VectorStorageRequestsTotal.Inc()
	}()

	log.WithFields(log.Fields{
		"request_id":  req.RequestID,
		"collection":  req.CollectionName,
		"document_id": req.DocumentID,
		"chunk_id":    req.ChunkID,
		"vector_dim":  len(req.Vector),
	}).Info("开始存储向量")

	// 存储向量到Milvus
	vectorID, err := s.storage.StoreVector(ctx, &storage.VectorData{
		CollectionName: req.CollectionName,
		DocumentID:     req.DocumentID,
		ChunkID:        req.ChunkID,
		Vector:         req.Vector,
		Metadata:       req.Metadata,
	})
	if err != nil {
		metrics.VectorStorageErrorsTotal.Inc()
		log.WithError(err).WithField("request_id", req.RequestID).Error("存储向量失败")
		return nil, fmt.Errorf("存储向量失败: %w", err)
	}

	response := &VectorStorageResponse{
		RequestID:   req.RequestID,
		VectorID:    vectorID,
		StorageTime: time.Since(start),
	}

	log.WithFields(log.Fields{
		"request_id": req.RequestID,
		"vector_id":  vectorID,
		"duration":   time.Since(start),
	}).Info("向量存储完成")

	return response, nil
}

// ComputeSimilarity 计算相似度
func (s *VectorService) ComputeSimilarity(ctx context.Context, req *SimilarityRequest) (*SimilarityResponse, error) {
	start := time.Now()
	defer func() {
		metrics.SimilarityComputationDuration.Observe(time.Since(start).Seconds())
		metrics.SimilarityComputationsTotal.Inc()
	}()

	log.WithFields(log.Fields{
		"request_id":      req.RequestID,
		"similarity_type": req.SimilarityType,
		"vector_dim":      len(req.QueryVector),
	}).Info("开始计算相似度")

	// 计算相似度
	score, err := s.computeVectorSimilarity(req.QueryVector, req.TargetVector, req.SimilarityType)
	if err != nil {
		log.WithError(err).WithField("request_id", req.RequestID).Error("计算相似度失败")
		return nil, fmt.Errorf("计算相似度失败: %w", err)
	}

	response := &SimilarityResponse{
		RequestID:       req.RequestID,
		SimilarityScore: score,
		SimilarityType:  req.SimilarityType,
	}

	log.WithFields(log.Fields{
		"request_id": req.RequestID,
		"score":      score,
		"duration":   time.Since(start),
	}).Info("相似度计算完成")

	return response, nil
}

// GetStats 获取服务统计
func (s *VectorService) GetStats() *ServiceStats {
	s.mutex.RLock()
	defer s.mutex.RUnlock()

	stats := *s.stats
	stats.QueueLength = len(s.requestQueue)
	stats.CurrentWorkers = len(s.workers)

	return &stats
}

// 启动工作池
func (s *VectorService) startWorkerPool() {
	for i := 0; i < s.config.Processing.Workers; i++ {
		go s.worker(i)
	}
	log.WithField("workers", s.config.Processing.Workers).Info("工作池启动完成")
}

// 工作协程
func (s *VectorService) worker(id int) {
	log.WithField("worker_id", id).Info("工作协程启动")

	for req := range s.requestQueue {
		s.processRequest(req)
	}

	log.WithField("worker_id", id).Info("工作协程退出")
}

// 处理请求
func (s *VectorService) processRequest(req *ProcessingRequest) {
	start := time.Now()
	var response *ProcessingResponse

	// 获取工作令牌
	s.workers <- struct{}{}
	defer func() {
		<-s.workers
	}()

	// 增加处理中计数
	s.mutex.Lock()
	s.stats.ProcessingRequests++
	s.mutex.Unlock()

	defer func() {
		s.mutex.Lock()
		s.stats.ProcessingRequests--
		s.mutex.Unlock()

		response.Duration = time.Since(start)
		select {
		case req.ResponseChan <- response:
		case <-req.Context.Done():
			log.WithField("request_id", req.ID).Warn("请求上下文已取消")
		}
	}()

	// 处理不同类型的请求
	switch req.Type {
	case RequestTypeEmbedding:
		data, err := s.GenerateEmbedding(req.Context, req.Data.(*EmbeddingRequest))
		response = &ProcessingResponse{
			ID:      req.ID,
			Success: err == nil,
			Data:    data,
			Error:   err,
		}

	case RequestTypeBatchEmbedding:
		data, err := s.BatchGenerateEmbeddings(req.Context, req.Data.(*BatchEmbeddingRequest))
		response = &ProcessingResponse{
			ID:      req.ID,
			Success: err == nil,
			Data:    data,
			Error:   err,
		}

	case RequestTypeVectorStorage:
		data, err := s.StoreVector(req.Context, req.Data.(*VectorStorageRequest))
		response = &ProcessingResponse{
			ID:      req.ID,
			Success: err == nil,
			Data:    data,
			Error:   err,
		}

	default:
		response = &ProcessingResponse{
			ID:      req.ID,
			Success: false,
			Error:   fmt.Errorf("不支持的请求类型: %d", req.Type),
		}
	}

	// 更新统计
	s.updateStats(response.Success, response.Duration)
}

// 并行处理嵌入向量
func (s *VectorService) processEmbeddingsConcurrently(ctx context.Context, requests []*EmbeddingRequest) []*EmbeddingResponse {
	var wg sync.WaitGroup
	responses := make([]*EmbeddingResponse, len(requests))

	// 控制并发数
	semaphore := make(chan struct{}, s.config.Processing.MaxConcurrentRequests)

	for i, req := range requests {
		wg.Add(1)
		go func(index int, request *EmbeddingRequest) {
			defer wg.Done()

			// 获取并发令牌
			semaphore <- struct{}{}
			defer func() { <-semaphore }()

			// 生成嵌入向量
			resp, err := s.GenerateEmbedding(ctx, request)
			if err != nil {
				log.WithError(err).WithField("request_id", request.RequestID).Error("并行生成嵌入向量失败")
				responses[index] = nil
			} else {
				responses[index] = resp
			}
		}(i, req)
	}

	wg.Wait()
	return responses
}

// 串行处理嵌入向量
func (s *VectorService) processEmbeddingsSerially(ctx context.Context, requests []*EmbeddingRequest) []*EmbeddingResponse {
	responses := make([]*EmbeddingResponse, len(requests))

	for i, req := range requests {
		resp, err := s.GenerateEmbedding(ctx, req)
		if err != nil {
			log.WithError(err).WithField("request_id", req.RequestID).Error("串行生成嵌入向量失败")
			responses[i] = nil
		} else {
			responses[i] = resp
		}
	}

	return responses
}

// 计算向量相似度
func (s *VectorService) computeVectorSimilarity(vector1, vector2 []float32, similarityType string) (float32, error) {
	if len(vector1) != len(vector2) {
		return 0, fmt.Errorf("向量维度不匹配: %d vs %d", len(vector1), len(vector2))
	}

	switch similarityType {
	case "cosine":
		return s.cosineSimilarity(vector1, vector2), nil
	case "euclidean":
		return s.euclideanDistance(vector1, vector2), nil
	case "dot_product":
		return s.dotProduct(vector1, vector2), nil
	default:
		return 0, fmt.Errorf("不支持的相似度类型: %s", similarityType)
	}
}

// 余弦相似度
func (s *VectorService) cosineSimilarity(a, b []float32) float32 {
	var dotProduct, normA, normB float32

	for i := range a {
		dotProduct += a[i] * b[i]
		normA += a[i] * a[i]
		normB += b[i] * b[i]
	}

	if normA == 0 || normB == 0 {
		return 0
	}

	return dotProduct / (float32(sqrt64(float64(normA * normB))))
}

// 欧几里得距离
func (s *VectorService) euclideanDistance(a, b []float32) float32 {
	var sum float32
	for i := range a {
		diff := a[i] - b[i]
		sum += diff * diff
	}
	return float32(sqrt64(float64(sum)))
}

// 点积
func (s *VectorService) dotProduct(a, b []float32) float32 {
	var product float32
	for i := range a {
		product += a[i] * b[i]
	}
	return product
}

// 更新统计信息
func (s *VectorService) updateStats(success bool, duration time.Duration) {
	s.mutex.Lock()
	defer s.mutex.Unlock()

	s.stats.TotalRequests++
	if success {
		s.stats.SuccessRequests++
	} else {
		s.stats.FailedRequests++
	}

	// 更新平均延迟（简单移动平均）
	if s.stats.TotalRequests == 1 {
		s.stats.AverageLatency = duration
	} else {
		s.stats.AverageLatency = time.Duration(
			(int64(s.stats.AverageLatency)*int64(s.stats.TotalRequests-1) + int64(duration)) / int64(s.stats.TotalRequests),
		)
	}
}

// sqrt64 计算平方根（简单实现）
func sqrt64(x float64) float64 {
	if x == 0 {
		return 0
	}
	
	// 牛顿法求平方根
	guess := x / 2
	for i := 0; i < 10; i++ {
		guess = (guess + x/guess) / 2
	}
	return guess
}