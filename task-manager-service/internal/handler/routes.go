package handler

import (
	"github.com/gin-gonic/gin"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

// RegisterRoutes 注册所有路由
func RegisterRoutes(router *gin.Engine, taskHandler *TaskHandler, uploadHandler *UploadHandler, pollingHandler *PollingHandler) {
	// 健康检查
	router.GET("/health", taskHandler.HealthCheck)
	
	// Prometheus指标
	router.GET("/metrics", gin.WrapH(promhttp.Handler()))

	// API版本1
	v1 := router.Group("/api/v1")
	{
		// 任务管理路由
		tasks := v1.Group("/tasks")
		{
			tasks.POST("", taskHandler.CreateTask)                    // 创建任务
			tasks.POST("/batch", taskHandler.CreateBatchTasks)        // 批量创建任务
			tasks.GET("", taskHandler.ListTasks)                      // 获取任务列表
			tasks.GET("/:id", taskHandler.GetTask)                    // 获取任务详情
			tasks.DELETE("/:id", taskHandler.CancelTask)              // 取消任务
			tasks.POST("/:id/retry", taskHandler.RetryTask)           // 重试任务
			tasks.PUT("/:id/progress", taskHandler.UpdateTaskProgress) // 更新任务进度
		}

		// 统计信息路由
		stats := v1.Group("/stats")
		{
			stats.GET("/tasks", taskHandler.GetTaskStats)     // 任务统计
			stats.GET("/system", taskHandler.GetSystemStats)  // 系统统计
		}

		// 队列信息路由
		queues := v1.Group("/queues")
		{
			queues.GET("/info", taskHandler.GetQueueInfo)  // 队列信息
		}

		// 文件上传路由
		uploads := v1.Group("/uploads")
		{
			uploads.POST("/file", uploadHandler.UploadFile)              // 单文件上传
			uploads.POST("/batch", uploadHandler.BatchUploadFiles)       // 批量文件上传
			uploads.POST("/url", uploadHandler.UploadFromURL)            // 从URL上传
			uploads.GET("/stats", uploadHandler.GetUploadStats)          // 上传统计
		}

		// 任务状态轮询路由
		polling := v1.Group("/polling")
		{
			polling.GET("/status", pollingHandler.PollTaskStatus)        // HTTP轮询
			polling.GET("/ws", pollingHandler.WSTaskStatus)              // WebSocket订阅
			polling.GET("/clients", pollingHandler.GetActivePollingClients) // 活跃客户端
		}
	}

	// 添加CORS中间件
	router.Use(func(c *gin.Context) {
		c.Header("Access-Control-Allow-Origin", "*")
		c.Header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		c.Header("Access-Control-Allow-Headers", "Content-Type, Authorization")
		
		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}
		
		c.Next()
	})

	// 404处理
	router.NoRoute(func(c *gin.Context) {
		c.JSON(404, gin.H{
			"error":   "Not Found",
			"message": "The requested endpoint does not exist",
			"path":    c.Request.URL.Path,
		})
	})
}