package logger

import (
	"os"
	"strings"

	"github.com/sirupsen/logrus"
)

// Init 初始化日志配置
func Init(logLevel string) {
	// 设置日志级别
	level := parseLogLevel(logLevel)
	logrus.SetLevel(level)

	// 设置日志格式
	logrus.SetFormatter(&logrus.JSONFormatter{
		TimestampFormat: "2006-01-02 15:04:05",
		FieldMap: logrus.FieldMap{
			logrus.FieldKeyTime:  "timestamp",
			logrus.FieldKeyLevel: "level",
			logrus.FieldKeyMsg:   "message",
			logrus.FieldKeyFunc:  "function",
		},
	})

	// 设置输出到标准输出
	logrus.SetOutput(os.Stdout)

	// 启用函数名和行号 (仅在debug级别)
	if level <= logrus.DebugLevel {
		logrus.SetReportCaller(true)
	}

	logrus.WithFields(logrus.Fields{
		"service":   "task-manager",
		"log_level": logLevel,
	}).Info("Logger initialized successfully")
}

// parseLogLevel 解析日志级别
func parseLogLevel(levelStr string) logrus.Level {
	switch strings.ToLower(levelStr) {
	case "panic":
		return logrus.PanicLevel
	case "fatal":
		return logrus.FatalLevel
	case "error":
		return logrus.ErrorLevel
	case "warn", "warning":
		return logrus.WarnLevel
	case "info":
		return logrus.InfoLevel
	case "debug":
		return logrus.DebugLevel
	case "trace":
		return logrus.TraceLevel
	default:
		logrus.Warnf("Unknown log level '%s', defaulting to 'info'", levelStr)
		return logrus.InfoLevel
	}
}

// GetLogger 获取带有指定字段的logger
func GetLogger(component string) *logrus.Entry {
	return logrus.WithField("component", component)
}

// GetLoggerWithFields 获取带有多个字段的logger
func GetLoggerWithFields(fields logrus.Fields) *logrus.Entry {
	return logrus.WithFields(fields)
}

// LogWithContext 带上下文的日志记录
func LogWithContext(ctx map[string]interface{}, level logrus.Level, msg string) {
	entry := logrus.WithFields(logrus.Fields(ctx))
	entry.Log(level, msg)
}

// LogTaskEvent 记录任务事件日志
func LogTaskEvent(taskID, event, message string, extra map[string]interface{}) {
	fields := logrus.Fields{
		"task_id": taskID,
		"event":   event,
	}
	
	// 合并额外字段
	for k, v := range extra {
		fields[k] = v
	}
	
	logrus.WithFields(fields).Info(message)
}

// LogWorkerEvent 记录工作进程事件日志
func LogWorkerEvent(workerID, event, message string, extra map[string]interface{}) {
	fields := logrus.Fields{
		"worker_id": workerID,
		"event":     event,
	}
	
	// 合并额外字段
	for k, v := range extra {
		fields[k] = v
	}
	
	logrus.WithFields(fields).Info(message)
}

// LogAPIRequest 记录API请求日志
func LogAPIRequest(method, path, clientIP string, statusCode int, duration int64, extra map[string]interface{}) {
	fields := logrus.Fields{
		"method":      method,
		"path":        path,
		"client_ip":   clientIP,
		"status_code": statusCode,
		"duration_ms": duration,
		"type":        "api_request",
	}
	
	// 合并额外字段
	for k, v := range extra {
		fields[k] = v
	}
	
	entry := logrus.WithFields(fields)
	
	if statusCode >= 500 {
		entry.Error("API request failed")
	} else if statusCode >= 400 {
		entry.Warn("API request warning")
	} else {
		entry.Info("API request completed")
	}
}

// LogDatabaseOperation 记录数据库操作日志
func LogDatabaseOperation(operation, table string, duration int64, rowsAffected int64, err error) {
	fields := logrus.Fields{
		"operation":     operation,
		"table":         table,
		"duration_ms":   duration,
		"rows_affected": rowsAffected,
		"type":          "database_operation",
	}
	
	entry := logrus.WithFields(fields)
	
	if err != nil {
		entry.WithError(err).Error("Database operation failed")
	} else {
		entry.Info("Database operation completed")
	}
}

// LogRedisOperation 记录Redis操作日志
func LogRedisOperation(operation, key string, duration int64, err error) {
	fields := logrus.Fields{
		"operation":   operation,
		"key":         key,
		"duration_ms": duration,
		"type":        "redis_operation",
	}
	
	entry := logrus.WithFields(fields)
	
	if err != nil {
		entry.WithError(err).Error("Redis operation failed")
	} else {
		entry.Debug("Redis operation completed")
	}
}

// LogSystemMetric 记录系统指标日志
func LogSystemMetric(metric string, value interface{}, unit string, extra map[string]interface{}) {
	fields := logrus.Fields{
		"metric": metric,
		"value":  value,
		"unit":   unit,
		"type":   "system_metric",
	}
	
	// 合并额外字段
	for k, v := range extra {
		fields[k] = v
	}
	
	logrus.WithFields(fields).Info("System metric recorded")
}

// LogError 记录错误日志 (带更多上下文信息)
func LogError(err error, context string, extra map[string]interface{}) {
	fields := logrus.Fields{
		"context": context,
		"type":    "error",
	}
	
	// 合并额外字段
	for k, v := range extra {
		fields[k] = v
	}
	
	logrus.WithFields(fields).WithError(err).Error("Error occurred")
}

// LogPerformance 记录性能日志
func LogPerformance(operation string, duration int64, extra map[string]interface{}) {
	fields := logrus.Fields{
		"operation":   operation,
		"duration_ms": duration,
		"type":        "performance",
	}
	
	// 合并额外字段
	for k, v := range extra {
		fields[k] = v
	}
	
	entry := logrus.WithFields(fields)
	
	// 根据耗时判断日志级别
	if duration > 5000 { // > 5秒
		entry.Warn("Slow operation detected")
	} else if duration > 1000 { // > 1秒
		entry.Info("Operation completed")
	} else {
		entry.Debug("Operation completed")
	}
}