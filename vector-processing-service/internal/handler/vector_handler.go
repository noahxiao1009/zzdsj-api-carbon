package handler

import (
	"context"
	"time"

	log "github.com/sirupsen/logrus"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	pb "vector-processing-service/pb"
	"vector-processing-service/internal/service"
	"vector-processing-service/pkg/metrics"
)

// VectorHandler gRPC处理器
type VectorHandler struct {
	pb.UnimplementedVectorProcessingServiceServer
	vectorService *service.VectorService
}

// NewVectorHandler 创建向量处理器
func NewVectorHandler(vectorService *service.VectorService) *VectorHandler {
	return &VectorHandler{
		vectorService: vectorService,
	}
}

// GenerateEmbeddings 生成嵌入向量
func (h *VectorHandler) GenerateEmbeddings(ctx context.Context, req *pb.EmbeddingRequest) (*pb.EmbeddingResponse, error) {
	start := time.Now()
	defer func() {
		metrics.GRPCRequestDuration.WithLabelValues("GenerateEmbeddings").Observe(time.Since(start).Seconds())
		metrics.GRPCRequestsTotal.WithLabelValues("GenerateEmbeddings").Inc()
	}()

	log.WithFields(log.Fields{
		"request_id": req.RequestId,
		"model":      req.ModelName,
		"kb_id":      req.KbId,
		"text_len":   len(req.Text),
	}).Info("收到生成嵌入向量请求")

	// 验证请求参数
	if err := h.validateEmbeddingRequest(req); err != nil {
		metrics.GRPCRequestsTotal.WithLabelValues("GenerateEmbeddings", "error").Inc()
		log.WithError(err).WithField("request_id", req.RequestId).Error("请求参数验证失败")
		return nil, status.Errorf(codes.InvalidArgument, "请求参数验证失败: %v", err)
	}

	// 转换为服务层请求
	serviceReq := &service.EmbeddingRequest{
		RequestID: req.RequestId,
		Text:      req.Text,
		Model:     req.ModelName,
		KBId:      req.KbId,
		Metadata:  req.Metadata,
	}

	// 调用服务层
	serviceResp, err := h.vectorService.GenerateEmbedding(ctx, serviceReq)
	if err != nil {
		metrics.GRPCRequestsTotal.WithLabelValues("GenerateEmbeddings", "error").Inc()
		log.WithError(err).WithField("request_id", req.RequestId).Error("生成嵌入向量失败")
		return nil, status.Errorf(codes.Internal, "生成嵌入向量失败: %v", err)
	}

	// 转换响应
	response := &pb.EmbeddingResponse{
		RequestId:        serviceResp.RequestID,
		Success:          true,
		Embedding:        serviceResp.Embedding,
		Dimension:        int32(serviceResp.Dimension),
		ModelName:        serviceResp.Model,
		ProcessingTimeMs: serviceResp.ProcessingTime.Milliseconds(),
	}

	metrics.GRPCRequestsTotal.WithLabelValues("GenerateEmbeddings", "success").Inc()
	log.WithFields(log.Fields{
		"request_id": req.RequestId,
		"dimension":  serviceResp.Dimension,
		"duration":   serviceResp.ProcessingTime,
	}).Info("嵌入向量生成成功")

	return response, nil
}

// BatchGenerateEmbeddings 批量生成嵌入向量
func (h *VectorHandler) BatchGenerateEmbeddings(ctx context.Context, req *pb.BatchEmbeddingRequest) (*pb.BatchEmbeddingResponse, error) {
	start := time.Now()
	defer func() {
		metrics.GRPCRequestDuration.WithLabelValues("BatchGenerateEmbeddings").Observe(time.Since(start).Seconds())
		metrics.GRPCRequestsTotal.WithLabelValues("BatchGenerateEmbeddings").Inc()
	}()

	log.WithFields(log.Fields{
		"batch_id":    req.BatchId,
		"batch_size":  len(req.Requests),
		"parallel":    req.ParallelProcessing,
	}).Info("收到批量生成嵌入向量请求")

	// 验证批量请求
	if err := h.validateBatchEmbeddingRequest(req); err != nil {
		metrics.GRPCRequestsTotal.WithLabelValues("BatchGenerateEmbeddings", "error").Inc()
		log.WithError(err).WithField("batch_id", req.BatchId).Error("批量请求参数验证失败")
		return nil, status.Errorf(codes.InvalidArgument, "批量请求参数验证失败: %v", err)
	}

	// 转换为服务层请求
	serviceRequests := make([]*service.EmbeddingRequest, len(req.Requests))
	for i, pbReq := range req.Requests {
		serviceRequests[i] = &service.EmbeddingRequest{
			RequestID: pbReq.RequestId,
			Text:      pbReq.Text,
			Model:     pbReq.ModelName,
			KBId:      pbReq.KbId,
			Metadata:  pbReq.Metadata,
		}
	}

	serviceReq := &service.BatchEmbeddingRequest{
		BatchID:           req.BatchId,
		Requests:          serviceRequests,
		BatchSize:         int(req.BatchSize),
		ParallelProcessing: req.ParallelProcessing,
	}

	// 调用服务层
	serviceResp, err := h.vectorService.BatchGenerateEmbeddings(ctx, serviceReq)
	if err != nil {
		metrics.GRPCRequestsTotal.WithLabelValues("BatchGenerateEmbeddings", "error").Inc()
		log.WithError(err).WithField("batch_id", req.BatchId).Error("批量生成嵌入向量失败")
		return nil, status.Errorf(codes.Internal, "批量生成嵌入向量失败: %v", err)
	}

	// 转换响应
	responses := make([]*pb.EmbeddingResponse, len(serviceResp.Responses))
	for i, resp := range serviceResp.Responses {
		if resp != nil {
			responses[i] = &pb.EmbeddingResponse{
				RequestId:        resp.RequestID,
				Success:          true,
				Embedding:        resp.Embedding,
				Dimension:        int32(resp.Dimension),
				ModelName:        resp.Model,
				ProcessingTimeMs: resp.ProcessingTime.Milliseconds(),
			}
		} else {
			responses[i] = &pb.EmbeddingResponse{
				Success:      false,
				ErrorMessage: "处理失败",
			}
		}
	}

	response := &pb.BatchEmbeddingResponse{
		BatchId:               serviceResp.BatchID,
		Success:               serviceResp.FailedCount == 0,
		Responses:             responses,
		TotalCount:            int32(serviceResp.TotalCount),
		SuccessCount:          int32(serviceResp.SuccessCount),
		FailedCount:           int32(serviceResp.FailedCount),
		TotalProcessingTimeMs: serviceResp.TotalProcessingTime.Milliseconds(),
	}

	metrics.GRPCRequestsTotal.WithLabelValues("BatchGenerateEmbeddings", "success").Inc()
	log.WithFields(log.Fields{
		"batch_id":     req.BatchId,
		"total":        serviceResp.TotalCount,
		"success":      serviceResp.SuccessCount,
		"failed":       serviceResp.FailedCount,
		"duration":     serviceResp.TotalProcessingTime,
	}).Info("批量嵌入向量生成完成")

	return response, nil
}

// StoreVectors 存储向量
func (h *VectorHandler) StoreVectors(ctx context.Context, req *pb.VectorStorageRequest) (*pb.VectorStorageResponse, error) {
	start := time.Now()
	defer func() {
		metrics.GRPCRequestDuration.WithLabelValues("StoreVectors").Observe(time.Since(start).Seconds())
		metrics.GRPCRequestsTotal.WithLabelValues("StoreVectors").Inc()
	}()

	log.WithFields(log.Fields{
		"request_id":      req.RequestId,
		"collection_name": req.CollectionName,
		"document_id":     req.DocumentId,
		"chunk_id":        req.ChunkId,
		"vector_dim":      len(req.Vector),
	}).Info("收到存储向量请求")

	// 验证存储请求
	if err := h.validateVectorStorageRequest(req); err != nil {
		metrics.GRPCRequestsTotal.WithLabelValues("StoreVectors", "error").Inc()
		log.WithError(err).WithField("request_id", req.RequestId).Error("存储请求参数验证失败")
		return nil, status.Errorf(codes.InvalidArgument, "存储请求参数验证失败: %v", err)
	}

	// 转换为服务层请求
	serviceReq := &service.VectorStorageRequest{
		RequestID:      req.RequestId,
		CollectionName: req.CollectionName,
		DocumentID:     req.DocumentId,
		ChunkID:        req.ChunkId,
		Vector:         req.Vector,
		Metadata:       req.Metadata,
		KBId:           req.KbId,
	}

	// 调用服务层
	serviceResp, err := h.vectorService.StoreVector(ctx, serviceReq)
	if err != nil {
		metrics.GRPCRequestsTotal.WithLabelValues("StoreVectors", "error").Inc()
		log.WithError(err).WithField("request_id", req.RequestId).Error("存储向量失败")
		return nil, status.Errorf(codes.Internal, "存储向量失败: %v", err)
	}

	// 转换响应
	response := &pb.VectorStorageResponse{
		RequestId:     serviceResp.RequestID,
		Success:       true,
		VectorId:      serviceResp.VectorID,
		StorageTimeMs: serviceResp.StorageTime.Milliseconds(),
	}

	metrics.GRPCRequestsTotal.WithLabelValues("StoreVectors", "success").Inc()
	log.WithFields(log.Fields{
		"request_id": req.RequestId,
		"vector_id":  serviceResp.VectorID,
		"duration":   serviceResp.StorageTime,
	}).Info("向量存储成功")

	return response, nil
}

// BatchStoreVectors 批量存储向量
func (h *VectorHandler) BatchStoreVectors(ctx context.Context, req *pb.BatchVectorStorageRequest) (*pb.BatchVectorStorageResponse, error) {
	start := time.Now()
	defer func() {
		metrics.GRPCRequestDuration.WithLabelValues("BatchStoreVectors").Observe(time.Since(start).Seconds())
		metrics.GRPCRequestsTotal.WithLabelValues("BatchStoreVectors").Inc()
	}()

	log.WithFields(log.Fields{
		"batch_id":    req.BatchId,
		"batch_size":  len(req.Requests),
	}).Info("收到批量存储向量请求")

	// 验证批量存储请求
	if len(req.Requests) == 0 {
		return nil, status.Errorf(codes.InvalidArgument, "批量存储请求为空")
	}

	responses := make([]*pb.VectorStorageResponse, len(req.Requests))
	var successCount, failedCount int32

	// 逐个处理存储请求
	for i, storageReq := range req.Requests {
		resp, err := h.StoreVectors(ctx, storageReq)
		if err != nil {
			responses[i] = &pb.VectorStorageResponse{
				RequestId:    storageReq.RequestId,
				Success:      false,
				ErrorMessage: err.Error(),
			}
			failedCount++
		} else {
			responses[i] = resp
			successCount++
		}
	}

	response := &pb.BatchVectorStorageResponse{
		BatchId:      req.BatchId,
		Success:      failedCount == 0,
		Responses:    responses,
		TotalCount:   int32(len(req.Requests)),
		SuccessCount: successCount,
		FailedCount:  failedCount,
	}

	metrics.GRPCRequestsTotal.WithLabelValues("BatchStoreVectors", "success").Inc()
	log.WithFields(log.Fields{
		"batch_id":     req.BatchId,
		"total":        len(req.Requests),
		"success":      successCount,
		"failed":       failedCount,
		"duration":     time.Since(start),
	}).Info("批量向量存储完成")

	return response, nil
}

// ComputeSimilarity 计算相似度
func (h *VectorHandler) ComputeSimilarity(ctx context.Context, req *pb.SimilarityRequest) (*pb.SimilarityResponse, error) {
	start := time.Now()
	defer func() {
		metrics.GRPCRequestDuration.WithLabelValues("ComputeSimilarity").Observe(time.Since(start).Seconds())
		metrics.GRPCRequestsTotal.WithLabelValues("ComputeSimilarity").Inc()
	}()

	log.WithFields(log.Fields{
		"request_id":      req.RequestId,
		"similarity_type": req.SimilarityType,
		"query_dim":       len(req.QueryVector),
		"target_dim":      len(req.TargetVector),
	}).Info("收到计算相似度请求")

	// 验证相似度请求
	if err := h.validateSimilarityRequest(req); err != nil {
		metrics.GRPCRequestsTotal.WithLabelValues("ComputeSimilarity", "error").Inc()
		log.WithError(err).WithField("request_id", req.RequestId).Error("相似度请求参数验证失败")
		return nil, status.Errorf(codes.InvalidArgument, "相似度请求参数验证失败: %v", err)
	}

	// 转换为服务层请求
	serviceReq := &service.SimilarityRequest{
		RequestID:      req.RequestId,
		QueryVector:    req.QueryVector,
		TargetVector:   req.TargetVector,
		SimilarityType: req.SimilarityType,
	}

	// 调用服务层
	serviceResp, err := h.vectorService.ComputeSimilarity(ctx, serviceReq)
	if err != nil {
		metrics.GRPCRequestsTotal.WithLabelValues("ComputeSimilarity", "error").Inc()
		log.WithError(err).WithField("request_id", req.RequestId).Error("计算相似度失败")
		return nil, status.Errorf(codes.Internal, "计算相似度失败: %v", err)
	}

	// 转换响应
	response := &pb.SimilarityResponse{
		RequestId:       serviceResp.RequestID,
		Success:         true,
		SimilarityScore: serviceResp.SimilarityScore,
		SimilarityType:  serviceResp.SimilarityType,
	}

	metrics.GRPCRequestsTotal.WithLabelValues("ComputeSimilarity", "success").Inc()
	log.WithFields(log.Fields{
		"request_id": req.RequestId,
		"score":      serviceResp.SimilarityScore,
		"duration":   time.Since(start),
	}).Info("相似度计算成功")

	return response, nil
}

// GetProcessingStatus 获取处理状态
func (h *VectorHandler) GetProcessingStatus(ctx context.Context, req *pb.ProcessingStatusRequest) (*pb.ProcessingStatusResponse, error) {
	start := time.Now()
	defer func() {
		metrics.GRPCRequestDuration.WithLabelValues("GetProcessingStatus").Observe(time.Since(start).Seconds())
		metrics.GRPCRequestsTotal.WithLabelValues("GetProcessingStatus").Inc()
	}()

	log.WithFields(log.Fields{
		"request_id": req.RequestId,
		"batch_id":   req.BatchId,
	}).Info("收到获取处理状态请求")

	// 获取服务统计
	stats := h.vectorService.GetStats()

	// 构建响应
	response := &pb.ProcessingStatusResponse{
		RequestId: req.RequestId,
		Status:    "running",
		Progress:  int32(float64(stats.SuccessRequests) / float64(stats.TotalRequests) * 100),
		Message:   "服务正常运行",
		CreatedAt: time.Now().Unix(),
		Metadata: map[string]string{
			"total_requests":      string(rune(stats.TotalRequests)),
			"success_requests":    string(rune(stats.SuccessRequests)),
			"failed_requests":     string(rune(stats.FailedRequests)),
			"current_workers":     string(rune(stats.CurrentWorkers)),
			"queue_length":        string(rune(stats.QueueLength)),
			"processing_requests": string(rune(stats.ProcessingRequests)),
			"average_latency":     stats.AverageLatency.String(),
		},
	}

	metrics.GRPCRequestsTotal.WithLabelValues("GetProcessingStatus", "success").Inc()
	log.WithFields(log.Fields{
		"request_id":    req.RequestId,
		"total_requests": stats.TotalRequests,
		"success_rate":   float64(stats.SuccessRequests)/float64(stats.TotalRequests)*100,
		"duration":       time.Since(start),
	}).Info("处理状态查询成功")

	return response, nil
}

// 验证嵌入请求
func (h *VectorHandler) validateEmbeddingRequest(req *pb.EmbeddingRequest) error {
	if req.RequestId == "" {
		return status.Error(codes.InvalidArgument, "请求ID不能为空")
	}
	if req.Text == "" {
		return status.Error(codes.InvalidArgument, "文本内容不能为空")
	}
	if req.ModelName == "" {
		return status.Error(codes.InvalidArgument, "模型名称不能为空")
	}
	if len(req.Text) > 8192 {
		return status.Error(codes.InvalidArgument, "文本长度超过限制")
	}
	return nil
}

// 验证批量嵌入请求
func (h *VectorHandler) validateBatchEmbeddingRequest(req *pb.BatchEmbeddingRequest) error {
	if req.BatchId == "" {
		return status.Error(codes.InvalidArgument, "批次ID不能为空")
	}
	if len(req.Requests) == 0 {
		return status.Error(codes.InvalidArgument, "批量请求不能为空")
	}
	if len(req.Requests) > 100 {
		return status.Error(codes.InvalidArgument, "批量请求数量超过限制")
	}

	// 验证每个子请求
	for i, subReq := range req.Requests {
		if err := h.validateEmbeddingRequest(subReq); err != nil {
			return status.Errorf(codes.InvalidArgument, "第%d个请求验证失败: %v", i+1, err)
		}
	}

	return nil
}

// 验证向量存储请求
func (h *VectorHandler) validateVectorStorageRequest(req *pb.VectorStorageRequest) error {
	if req.RequestId == "" {
		return status.Error(codes.InvalidArgument, "请求ID不能为空")
	}
	if req.CollectionName == "" {
		return status.Error(codes.InvalidArgument, "集合名称不能为空")
	}
	if req.DocumentId == "" {
		return status.Error(codes.InvalidArgument, "文档ID不能为空")
	}
	if len(req.Vector) == 0 {
		return status.Error(codes.InvalidArgument, "向量不能为空")
	}
	if len(req.Vector) > 2048 {
		return status.Error(codes.InvalidArgument, "向量维度超过限制")
	}
	return nil
}

// 验证相似度请求
func (h *VectorHandler) validateSimilarityRequest(req *pb.SimilarityRequest) error {
	if req.RequestId == "" {
		return status.Error(codes.InvalidArgument, "请求ID不能为空")
	}
	if len(req.QueryVector) == 0 {
		return status.Error(codes.InvalidArgument, "查询向量不能为空")
	}
	if len(req.TargetVector) == 0 {
		return status.Error(codes.InvalidArgument, "目标向量不能为空")
	}
	if len(req.QueryVector) != len(req.TargetVector) {
		return status.Error(codes.InvalidArgument, "查询向量和目标向量维度不匹配")
	}
	if req.SimilarityType == "" {
		return status.Error(codes.InvalidArgument, "相似度类型不能为空")
	}

	// 验证相似度类型
	validTypes := []string{"cosine", "euclidean", "dot_product"}
	valid := false
	for _, validType := range validTypes {
		if req.SimilarityType == validType {
			valid = true
			break
		}
	}
	if !valid {
		return status.Errorf(codes.InvalidArgument, "不支持的相似度类型: %s", req.SimilarityType)
	}

	return nil
}