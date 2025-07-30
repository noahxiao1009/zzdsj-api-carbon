package main

import (
	"context"
	"fmt"
	"net"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/prometheus/client_golang/prometheus/promhttp"
	log "github.com/sirupsen/logrus"
	"google.golang.org/grpc"
	"google.golang.org/grpc/keepalive"
	"google.golang.org/grpc/reflection"

	pb "vector-processing-service/pb"
	"vector-processing-service/internal/config"
	"vector-processing-service/internal/handler"
	"vector-processing-service/internal/service"
	"vector-processing-service/internal/storage"
	"vector-processing-service/pkg/embedding"
	"vector-processing-service/pkg/metrics"
)

var (
	Version   = "dev"
	BuildTime = "unknown"
	GitCommit = "unknown"
)

func main() {
	// 初始化日志
	initLogging()

	log.WithFields(log.Fields{
		"version":    Version,
		"build_time": BuildTime,
		"git_commit": GitCommit,
	}).Info("向量处理服务启动")

	// 加载配置
	cfg, err := config.LoadConfig()
	if err != nil {
		log.Fatalf("加载配置失败: %v", err)
	}

	// 初始化存储层
	storageManager, err := initStorage(cfg)
	if err != nil {
		log.Fatalf("初始化存储失败: %v", err)
	}
	defer storageManager.Close()

	// 初始化嵌入服务
	embeddingService, err := initEmbeddingService(cfg)
	if err != nil {
		log.Fatalf("初始化嵌入服务失败: %v", err)
	}

	// 初始化向量服务
	vectorService := service.NewVectorService(
		storageManager,
		embeddingService,
		cfg,
	)

	// 初始化处理器
	vectorHandler := handler.NewVectorHandler(vectorService)

	// 启动监控服务
	go startMonitoring(cfg)

	// 启动gRPC服务器
	server := startGRPCServer(cfg, vectorHandler)

	// 等待退出信号
	waitForShutdown(server, storageManager)
}

func initLogging() {
	log.SetFormatter(&log.JSONFormatter{
		TimestampFormat: time.RFC3339,
	})
	log.SetLevel(log.InfoLevel)
	log.SetOutput(os.Stdout)
}

func initStorage(cfg *config.Config) (*storage.Manager, error) {
	log.Info("初始化存储管理器")

	// 初始化Redis
	redisClient, err := storage.NewRedisClient(&cfg.Redis)
	if err != nil {
		return nil, fmt.Errorf("初始化Redis失败: %w", err)
	}

	// 初始化Milvus
	milvusClient, err := storage.NewMilvusClient(&cfg.Milvus)
	if err != nil {
		return nil, fmt.Errorf("初始化Milvus失败: %w", err)
	}

	return storage.NewManager(redisClient, milvusClient), nil
}

func initEmbeddingService(cfg *config.Config) (*embedding.Service, error) {
	log.Info("初始化嵌入服务")

	service, err := embedding.NewService(&cfg.Embedding)
	if err != nil {
		return nil, fmt.Errorf("初始化嵌入服务失败: %w", err)
	}

	return service, nil
}

func startGRPCServer(cfg *config.Config, handler *handler.VectorHandler) *grpc.Server {
	log.WithField("port", cfg.GRPC.Port).Info("启动gRPC服务器")

	// gRPC服务器配置
	opts := []grpc.ServerOption{
		grpc.MaxRecvMsgSize(cfg.GRPC.MaxRecvMsgSize),
		grpc.MaxSendMsgSize(cfg.GRPC.MaxSendMsgSize),
		grpc.KeepaliveParams(keepalive.ServerParameters{
			Time:    cfg.GRPC.Keepalive.Time,
			Timeout: cfg.GRPC.Keepalive.Timeout,
		}),
		grpc.KeepaliveEnforcementPolicy(keepalive.EnforcementPolicy{
			PermitWithoutStream: cfg.GRPC.Keepalive.PermitWithoutStream,
		}),
		// 添加拦截器
		grpc.UnaryInterceptor(metrics.UnaryServerInterceptor()),
		grpc.StreamInterceptor(metrics.StreamServerInterceptor()),
	}

	server := grpc.NewServer(opts...)

	// 注册服务
	pb.RegisterVectorProcessingServiceServer(server, handler)

	// 启用反射（开发环境）
	if cfg.Development.Debug {
		reflection.Register(server)
	}

	// 启动监听
	listener, err := net.Listen("tcp", fmt.Sprintf(":%d", cfg.GRPC.Port))
	if err != nil {
		log.Fatalf("监听端口失败: %v", err)
	}

	go func() {
		if err := server.Serve(listener); err != nil {
			log.Fatalf("gRPC服务器启动失败: %v", err)
		}
	}()

	log.WithField("address", listener.Addr().String()).Info("gRPC服务器启动成功")
	return server
}

func startMonitoring(cfg *config.Config) {
	if !cfg.Monitoring.Prometheus.Enabled {
		return
	}

	// Prometheus metrics
	http.Handle(cfg.Monitoring.Prometheus.Path, promhttp.Handler())

	// 健康检查
	if cfg.Monitoring.Health.Enabled {
		http.HandleFunc(cfg.Monitoring.Health.Path, healthCheckHandler)
	}

	// 启动HTTP服务器
	addr := fmt.Sprintf(":%d", cfg.Monitoring.Prometheus.Port)
	log.WithField("address", addr).Info("启动监控服务")

	server := &http.Server{
		Addr:         addr,
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 30 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Errorf("监控服务启动失败: %v", err)
	}
}

func healthCheckHandler(w http.ResponseWriter, r *http.Request) {
	// 简单的健康检查
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(`{
		"status": "healthy",
		"service": "vector-processing-service",
		"version": "` + Version + `",
		"timestamp": "` + time.Now().Format(time.RFC3339) + `"
	}`))
}

func waitForShutdown(server *grpc.Server, storage *storage.Manager) {
	// 监听退出信号
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	sig := <-sigChan
	log.WithField("signal", sig).Info("收到退出信号，开始优雅关闭")

	// 创建超时上下文
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	// 关闭gRPC服务器
	done := make(chan struct{})
	go func() {
		server.GracefulStop()
		close(done)
	}()

	select {
	case <-done:
		log.Info("gRPC服务器已优雅关闭")
	case <-ctx.Done():
		log.Warn("gRPC服务器关闭超时，强制关闭")
		server.Stop()
	}

	// 关闭存储连接
	if err := storage.Close(); err != nil {
		log.WithError(err).Error("关闭存储连接失败")
	}

	log.Info("向量处理服务已关闭")
}