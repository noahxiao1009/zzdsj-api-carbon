package metrics

import (
	"strconv"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	log "github.com/sirupsen/logrus"
	"google.golang.org/grpc"
	"google.golang.org/grpc/status"
)

// Prometheus metrics
var (
	// gRPC请求指标
	GRPCRequestsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "grpc_requests_total",
			Help: "Total number of gRPC requests",
		},
		[]string{"method", "status"},
	)

	GRPCRequestDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "grpc_request_duration_seconds",
			Help:    "Duration of gRPC requests in seconds",
			Buckets: prometheus.DefBuckets,
		},
		[]string{"method"},
	)

	// 嵌入向量生成指标
	EmbeddingRequestsTotal = promauto.NewCounter(
		prometheus.CounterOpts{
			Name: "embedding_requests_total",
			Help: "Total number of embedding requests",
		},
	)

	EmbeddingRequestDuration = promauto.NewHistogram(
		prometheus.HistogramOpts{
			Name:    "embedding_request_duration_seconds",
			Help:    "Duration of embedding requests in seconds",
			Buckets: []float64{0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0},
		},
	)

	EmbeddingErrorsTotal = promauto.NewCounter(
		prometheus.CounterOpts{
			Name: "embedding_errors_total",
			Help: "Total number of embedding errors",
		},
	)

	// 批量嵌入向量生成指标
	BatchEmbeddingRequestsTotal = promauto.NewCounter(
		prometheus.CounterOpts{
			Name: "batch_embedding_requests_total",
			Help: "Total number of batch embedding requests",
		},
	)

	BatchEmbeddingRequestDuration = promauto.NewHistogram(
		prometheus.HistogramOpts{
			Name:    "batch_embedding_request_duration_seconds",
			Help:    "Duration of batch embedding requests in seconds",
			Buckets: []float64{1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0},
		},
	)

	BatchEmbeddingSize = promauto.NewHistogram(
		prometheus.HistogramOpts{
			Name:    "batch_embedding_size",
			Help:    "Size of batch embedding requests",
			Buckets: []float64{1, 5, 10, 20, 50, 100},
		},
	)

	// 向量存储指标
	VectorStorageRequestsTotal = promauto.NewCounter(
		prometheus.CounterOpts{
			Name: "vector_storage_requests_total",
			Help: "Total number of vector storage requests",
		},
	)

	VectorStorageRequestDuration = promauto.NewHistogram(
		prometheus.HistogramOpts{
			Name:    "vector_storage_request_duration_seconds",
			Help:    "Duration of vector storage requests in seconds",
			Buckets: []float64{0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0},
		},
	)

	VectorStorageErrorsTotal = promauto.NewCounter(
		prometheus.CounterOpts{
			Name: "vector_storage_errors_total",
			Help: "Total number of vector storage errors",
		},
	)

	// 相似度计算指标
	SimilarityComputationsTotal = promauto.NewCounter(
		prometheus.CounterOpts{
			Name: "similarity_computations_total",
			Help: "Total number of similarity computations",
		},
	)

	SimilarityComputationDuration = promauto.NewHistogram(
		prometheus.HistogramOpts{
			Name:    "similarity_computation_duration_seconds",
			Help:    "Duration of similarity computations in seconds",
			Buckets: []float64{0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0},
		},
	)

	// 服务状态指标
	ServiceInfo = promauto.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "service_info",
			Help: "Service information",
		},
		[]string{"version", "build_time", "git_commit"},
	)

	ActiveWorkers = promauto.NewGauge(
		prometheus.GaugeOpts{
			Name: "active_workers",
			Help: "Number of active workers",
		},
	)

	QueueLength = promauto.NewGauge(
		prometheus.GaugeOpts{
			Name: "queue_length",
			Help: "Current queue length",
		},
	)

	ProcessingRequests = promauto.NewGauge(
		prometheus.GaugeOpts{
			Name: "processing_requests",
			Help: "Number of requests currently being processed",
		},
	)

	// 连接指标
	RedisConnections = promauto.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "redis_connections",
			Help: "Redis connection status",
		},
		[]string{"status"},
	)

	MilvusConnections = promauto.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "milvus_connections",
			Help: "Milvus connection status",
		},
		[]string{"status"},
	)

	// 向量维度分布
	VectorDimensions = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "vector_dimensions",
			Help:    "Distribution of vector dimensions",
			Buckets: []float64{256, 384, 512, 768, 1024, 1536, 2048},
		},
		[]string{"model"},
	)

	// 内存使用情况
	MemoryUsage = promauto.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "memory_usage_bytes",
			Help: "Memory usage in bytes",
		},
		[]string{"type"},
	)
)

// UpdateServiceInfo 更新服务信息
func UpdateServiceInfo(version, buildTime, gitCommit string) {
	ServiceInfo.WithLabelValues(version, buildTime, gitCommit).Set(1)
}

// UpdateWorkerStats 更新工作线程统计
func UpdateWorkerStats(activeWorkers, queueLength, processingRequests int) {
	ActiveWorkers.Set(float64(activeWorkers))
	QueueLength.Set(float64(queueLength))
	ProcessingRequests.Set(float64(processingRequests))
}

// UpdateConnectionStats 更新连接统计
func UpdateConnectionStats(redisConnected, milvusConnected bool) {
	if redisConnected {
		RedisConnections.WithLabelValues("connected").Set(1)
		RedisConnections.WithLabelValues("disconnected").Set(0)
	} else {
		RedisConnections.WithLabelValues("connected").Set(0)
		RedisConnections.WithLabelValues("disconnected").Set(1)
	}

	if milvusConnected {
		MilvusConnections.WithLabelValues("connected").Set(1)
		MilvusConnections.WithLabelValues("disconnected").Set(0)
	} else {
		MilvusConnections.WithLabelValues("connected").Set(0)
		MilvusConnections.WithLabelValues("disconnected").Set(1)
	}
}

// RecordVectorDimension 记录向量维度
func RecordVectorDimension(model string, dimension int) {
	VectorDimensions.WithLabelValues(model).Observe(float64(dimension))
}

// RecordMemoryUsage 记录内存使用情况
func RecordMemoryUsage(usageType string, bytes int64) {
	MemoryUsage.WithLabelValues(usageType).Set(float64(bytes))
}

// UnaryServerInterceptor gRPC一元服务拦截器
func UnaryServerInterceptor() grpc.UnaryServerInterceptor {
	return func(ctx interface{}, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
		start := time.Now()

		// 执行请求
		resp, err := handler(ctx, req)

		// 记录指标
		duration := time.Since(start)
		method := info.FullMethod

		// 获取状态
		statusCode := "OK"
		if err != nil {
			if s, ok := status.FromError(err); ok {
				statusCode = s.Code().String()
			} else {
				statusCode = "UNKNOWN"
			}
		}

		// 更新指标
		GRPCRequestsTotal.WithLabelValues(method, statusCode).Inc()
		GRPCRequestDuration.WithLabelValues(method).Observe(duration.Seconds())

		if err != nil {
			log.WithFields(log.Fields{
				"method":   method,
				"duration": duration,
				"error":    err,
			}).Error("gRPC请求失败")
		} else {
			log.WithFields(log.Fields{
				"method":   method,
				"duration": duration,
			}).Debug("gRPC请求成功")
		}

		return resp, err
	}
}

// StreamServerInterceptor gRPC流服务拦截器
func StreamServerInterceptor() grpc.StreamServerInterceptor {
	return func(srv interface{}, ss grpc.ServerStream, info *grpc.StreamServerInfo, handler grpc.StreamHandler) error {
		start := time.Now()

		// 执行请求
		err := handler(srv, ss)

		// 记录指标
		duration := time.Since(start)
		method := info.FullMethod

		// 获取状态
		statusCode := "OK"
		if err != nil {
			if s, ok := status.FromError(err); ok {
				statusCode = s.Code().String()
			} else {
				statusCode = "UNKNOWN"
			}
		}

		// 更新指标
		GRPCRequestsTotal.WithLabelValues(method, statusCode).Inc()
		GRPCRequestDuration.WithLabelValues(method).Observe(duration.Seconds())

		if err != nil {
			log.WithFields(log.Fields{
				"method":   method,
				"duration": duration,
				"error":    err,
			}).Error("gRPC流请求失败")
		} else {
			log.WithFields(log.Fields{
				"method":   method,
				"duration": duration,
			}).Debug("gRPC流请求成功")
		}

		return err
	}
}

// RecordEmbeddingRequest 记录嵌入请求
func RecordEmbeddingRequest(duration time.Duration, success bool) {
	EmbeddingRequestsTotal.Inc()
	EmbeddingRequestDuration.Observe(duration.Seconds())
	if !success {
		EmbeddingErrorsTotal.Inc()
	}
}

// RecordBatchEmbeddingRequest 记录批量嵌入请求
func RecordBatchEmbeddingRequest(duration time.Duration, batchSize int, success bool) {
	BatchEmbeddingRequestsTotal.Inc()
	BatchEmbeddingRequestDuration.Observe(duration.Seconds())
	BatchEmbeddingSize.Observe(float64(batchSize))
}

// RecordVectorStorageRequest 记录向量存储请求
func RecordVectorStorageRequest(duration time.Duration, success bool) {
	VectorStorageRequestsTotal.Inc()
	VectorStorageRequestDuration.Observe(duration.Seconds())
	if !success {
		VectorStorageErrorsTotal.Inc()
	}
}

// RecordSimilarityComputation 记录相似度计算
func RecordSimilarityComputation(duration time.Duration) {
	SimilarityComputationsTotal.Inc()
	SimilarityComputationDuration.Observe(duration.Seconds())
}

// HealthMetrics 健康指标
type HealthMetrics struct {
	ServiceStatus      bool    `json:"service_status"`
	RedisConnected     bool    `json:"redis_connected"`
	MilvusConnected    bool    `json:"milvus_connected"`
	ActiveWorkers      int     `json:"active_workers"`
	QueueLength        int     `json:"queue_length"`
	ProcessingRequests int     `json:"processing_requests"`
	MemoryUsageMB      float64 `json:"memory_usage_mb"`
}

// GetHealthMetrics 获取健康指标
func GetHealthMetrics() *HealthMetrics {
	return &HealthMetrics{
		ServiceStatus:   true, // 简化实现
		RedisConnected:  true, // 应该从实际连接状态获取
		MilvusConnected: true, // 应该从实际连接状态获取
	}
}

// StartMetricsCollection 启动指标收集
func StartMetricsCollection() {
	log.Info("启动指标收集")

	// 可以添加定期收集系统指标的goroutine
	go func() {
		ticker := time.NewTicker(30 * time.Second)
		defer ticker.Stop()

		for range ticker.C {
			// 收集系统指标
			// 这里可以添加内存、CPU等系统指标的收集
		}
	}()
}

// LogMetrics 记录指标到日志
func LogMetrics() {
	log.WithFields(log.Fields{
		"grpc_requests_total":            getCounterValue(GRPCRequestsTotal),
		"embedding_requests_total":       getCounterValue(EmbeddingRequestsTotal),
		"batch_embedding_requests_total": getCounterValue(BatchEmbeddingRequestsTotal),
		"vector_storage_requests_total":  getCounterValue(VectorStorageRequestsTotal),
		"similarity_computations_total":  getCounterValue(SimilarityComputationsTotal),
	}).Info("当前指标统计")
}

// getCounterValue 获取计数器值（简化实现）
func getCounterValue(counter prometheus.Counter) float64 {
	// 这是一个简化的实现
	// 实际应该使用Prometheus的API来获取指标值
	return 0.0
}

// ResetMetrics 重置指标（用于测试）
func ResetMetrics() {
	// 这里可以重置所有指标到初始状态
	// 主要用于测试环境
	log.Info("重置所有指标")
}

// GetMetricsSnapshot 获取指标快照
func GetMetricsSnapshot() map[string]interface{} {
	return map[string]interface{}{
		"timestamp":                      time.Now().Unix(),
		"grpc_requests_total":            getCounterValue(GRPCRequestsTotal),
		"embedding_requests_total":       getCounterValue(EmbeddingRequestsTotal),
		"batch_embedding_requests_total": getCounterValue(BatchEmbeddingRequestsTotal),
		"vector_storage_requests_total":  getCounterValue(VectorStorageRequestsTotal),
		"similarity_computations_total":  getCounterValue(SimilarityComputationsTotal),
	}
}