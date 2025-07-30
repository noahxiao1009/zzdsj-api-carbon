package main

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/sirupsen/logrus"

	"task-manager-service/internal/config"
	"task-manager-service/internal/handler"
	"task-manager-service/internal/service"
	"task-manager-service/internal/grpc"
	"task-manager-service/pkg/database"
	"task-manager-service/pkg/logger"
	"task-manager-service/pkg/redis"
)

func main() {
	// 加载配置
	cfg, err := config.Load()
	if err != nil {
		logrus.Fatalf("Failed to load config: %v", err)
	}

	// 初始化日志
	logger.Init(cfg.LogLevel)
	log := logrus.WithField("service", "task-manager")

	log.Info("Starting Task Manager Service...")
	log.Infof("Environment: %s", cfg.Environment)
	log.Infof("Port: %d", cfg.Port)

	// 初始化数据库
	log.Info("Connecting to PostgreSQL...")
	db, err := database.Connect(cfg.Database)
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}
	defer db.Close()
	log.Info("✓ PostgreSQL connected successfully")

	// 初始化Redis
	log.Info("Connecting to Redis...")
	rdb, err := redis.Connect(cfg.Redis)
	if err != nil {
		log.Fatalf("Failed to connect to Redis: %v", err)
	}
	defer rdb.Close()
	log.Info("✓ Redis connected successfully")

	// 初始化服务层
	taskService := service.NewTaskService(db, rdb, cfg)
	workerService := service.NewWorkerService(db, rdb, cfg)

	// 启动工作进程池
	log.Infof("Starting worker pool with %d workers...", cfg.Worker.PoolSize)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	err = workerService.Start(ctx)
	if err != nil {
		log.Fatalf("Failed to start worker service: %v", err)
	}
	log.Info("✓ Worker pool started successfully")

	// 启动gRPC服务器
	grpcServer, err := grpc.NewGRPCServer(taskService, cfg.GRPCPort)
	if err != nil {
		log.Fatalf("Failed to create gRPC server: %v", err)
	}
	
	go func() {
		log.Infof("Starting gRPC server on port %d", cfg.GRPCPort)
		if err := grpcServer.Start(); err != nil {
			log.Errorf("gRPC server failed: %v", err)
		}
	}()
	log.Info("✓ gRPC server started successfully")

	// 初始化HTTP路由
	if cfg.Environment == "production" {
		gin.SetMode(gin.ReleaseMode)
	}

	router := gin.New()
	router.Use(gin.Logger(), gin.Recovery())

	// 初始化处理器
	taskHandler := handler.NewTaskHandler(taskService)
	uploadHandler, err := handler.NewUploadHandler(taskService, cfg)
	if err != nil {
		log.Fatalf("Failed to initialize upload handler: %v", err)
	}
	log.Info("✓ Upload handler initialized successfully")
	
	pollingHandler := handler.NewPollingHandler(taskService)
	log.Info("✓ Polling handler initialized successfully")

	// 注册路由
	handler.RegisterRoutes(router, taskHandler, uploadHandler, pollingHandler)

	// 启动HTTP服务器
	server := &http.Server{
		Addr:         fmt.Sprintf(":%d", cfg.Port),
		Handler:      router,
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 30 * time.Second,
		IdleTimeout:  120 * time.Second,
	}

	// 优雅启动
	go func() {
		log.Infof("Task Manager Service listening on :%d", cfg.Port)
		log.Info("API Documentation: http://localhost:8084/health")
		
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Failed to start server: %v", err)
		}
	}()

	// 等待中断信号
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Info("Shutting down Task Manager Service...")

	// 优雅关闭
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer shutdownCancel()

	// 停止接收新请求
	if err := server.Shutdown(shutdownCtx); err != nil {
		log.Errorf("Server forced to shutdown: %v", err)
	}

	// 停止工作进程
	cancel() // 取消worker context
	
	// 停止gRPC服务器
	log.Info("Stopping gRPC server...")
	grpcServer.Stop()
	
	// 停止轮询处理器
	log.Info("Stopping polling handler...")
	pollingHandler.StopPolling()
	
	// 等待工作进程完成
	log.Info("Waiting for workers to finish...")
	workerService.Stop()

	log.Info("✓ Task Manager Service stopped gracefully")
}