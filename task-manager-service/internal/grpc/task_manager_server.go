package grpc

import (
	"context"
	"fmt"
	"time"

	"github.com/sirupsen/logrus"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"task-manager-service/internal/model"
	"task-manager-service/internal/service"
	pb "task-manager-service/pkg/proto"
)

// TaskManagerServer gRPC服务实现
type TaskManagerServer struct {
	pb.UnimplementedTaskManagerServiceServer
	taskService *service.TaskService
	log         *logrus.Entry
}

// NewTaskManagerServer 创建gRPC服务器
func NewTaskManagerServer(taskService *service.TaskService) *TaskManagerServer {
	return &TaskManagerServer{
		taskService: taskService,
		log:         logrus.WithField("component", "grpc-server"),
	}
}

// SubmitTask 提交任务
func (s *TaskManagerServer) SubmitTask(ctx context.Context, req *pb.TaskSubmitRequest) (*pb.TaskSubmitResponse, error) {
	s.log.Infof("Received task submission: type=%s, kb_id=%s, service=%s", 
		req.TaskType, req.KnowledgeBaseId, req.ServiceName)

	// 验证请求参数
	if err := s.validateTaskSubmitRequest(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "Invalid request: %v", err)
	}

	// 转换payload
	payload := make(model.JSONMap)
	for k, v := range req.Payload {
		payload[k] = v
	}
	
	// 添加服务来源信息
	payload["service_name"] = req.ServiceName
	payload["callback_url"] = req.CallbackUrl

	// 创建任务请求
	taskReq := &model.TaskCreateRequest{
		TaskType:   model.TaskType(req.TaskType),
		KbID:       req.KnowledgeBaseId,
		Priority:   model.TaskPriority(req.Priority),
		Payload:    payload,
		MaxRetries: int(req.MaxRetries),
		Timeout:    int(req.TimeoutSeconds),
	}

	// 创建任务
	task, err := s.taskService.CreateTask(ctx, taskReq)
	if err != nil {
		s.log.Errorf("Failed to create task: %v", err)
		return nil, status.Errorf(codes.Internal, "Failed to create task: %v", err)
	}

	// 预计完成时间（简化算法）
	estimatedCompletion := time.Now().Add(time.Duration(req.TimeoutSeconds) * time.Second).Unix()

	response := &pb.TaskSubmitResponse{
		TaskId:              task.ID,
		Status:              string(task.Status),
		Message:             "Task submitted successfully",
		CreatedAt:           task.CreatedAt.Unix(),
		EstimatedCompletion: estimatedCompletion,
		QueueName:           fmt.Sprintf("%s:%s", task.TaskType, task.Priority),
	}

	s.log.Infof("Task submitted successfully: %s", task.ID)
	return response, nil
}

// GetTaskStatus 获取任务状态
func (s *TaskManagerServer) GetTaskStatus(ctx context.Context, req *pb.TaskStatusRequest) (*pb.TaskStatusResponse, error) {
	if req.TaskId == "" {
		return nil, status.Errorf(codes.InvalidArgument, "Task ID is required")
	}

	task, err := s.taskService.GetTask(ctx, req.TaskId)
	if err != nil {
		if err == service.ErrTaskNotFound {
			return nil, status.Errorf(codes.NotFound, "Task not found: %s", req.TaskId)
		}
		s.log.Errorf("Failed to get task %s: %v", req.TaskId, err)
		return nil, status.Errorf(codes.Internal, "Failed to get task: %v", err)
	}

	// 转换元数据
	metadata := make(map[string]string)
	for k, v := range task.Payload {
		if str, ok := v.(string); ok {
			metadata[k] = str
		} else {
			metadata[k] = fmt.Sprintf("%v", v)
		}
	}

	response := &pb.TaskStatusResponse{
		TaskId:       task.ID,
		Status:       string(task.Status),
		Progress:     int32(task.Progress),
		Message:      task.ErrorMessage,
		ErrorMessage: task.ErrorMessage,
		CreatedAt:    task.CreatedAt.Unix(),
		Metadata:     metadata,
		WorkerId:     task.WorkerID,
	}

	if task.StartedAt != nil {
		response.StartedAt = task.StartedAt.Unix()
	}

	if task.CompletedAt != nil {
		response.CompletedAt = task.CompletedAt.Unix()
	}

	return response, nil
}

// SubmitBatchTasks 批量提交任务
func (s *TaskManagerServer) SubmitBatchTasks(ctx context.Context, req *pb.BatchTaskSubmitRequest) (*pb.BatchTaskSubmitResponse, error) {
	s.log.Infof("Received batch task submission: batch_id=%s, count=%d", 
		req.BatchId, len(req.Tasks))

	if len(req.Tasks) == 0 {
		return nil, status.Errorf(codes.InvalidArgument, "No tasks provided")
	}

	if len(req.Tasks) > 100 {
		return nil, status.Errorf(codes.InvalidArgument, "Too many tasks (max 100)")
	}

	responses := make([]*pb.TaskSubmitResponse, 0, len(req.Tasks))
	submittedCount := int32(0)
	failedCount := int32(0)

	// 转换为模型任务请求
	taskRequests := make([]model.TaskCreateRequest, 0, len(req.Tasks))
	for _, taskReq := range req.Tasks {
		// 验证请求
		if err := s.validateTaskSubmitRequest(taskReq); err != nil {
			failedCount++
			responses = append(responses, &pb.TaskSubmitResponse{
				Status:  "failed",
				Message: fmt.Sprintf("Validation failed: %v", err),
			})
			continue
		}

		// 转换payload
		payload := make(model.JSONMap)
		for k, v := range taskReq.Payload {
			payload[k] = v
		}
		payload["service_name"] = taskReq.ServiceName
		payload["callback_url"] = taskReq.CallbackUrl
		payload["batch_id"] = req.BatchId

		modelReq := model.TaskCreateRequest{
			TaskType:   model.TaskType(taskReq.TaskType),
			KbID:       taskReq.KnowledgeBaseId,
			Priority:   model.TaskPriority(taskReq.Priority),
			Payload:    payload,
			MaxRetries: int(taskReq.MaxRetries),
			Timeout:    int(taskReq.TimeoutSeconds),
		}

		taskRequests = append(taskRequests, modelReq)
	}

	// 批量创建任务
	if len(taskRequests) > 0 {
		tasks, err := s.taskService.CreateBatchTasks(ctx, taskRequests)
		if err != nil {
			s.log.Errorf("Failed to create batch tasks: %v", err)
			return nil, status.Errorf(codes.Internal, "Failed to create batch tasks: %v", err)
		}

		// 构建响应
		for _, task := range tasks {
			estimatedCompletion := time.Now().Add(10 * time.Minute).Unix() // 简化预估
			
			response := &pb.TaskSubmitResponse{
				TaskId:              task.ID,
				Status:              string(task.Status),
				Message:             "Task submitted successfully",
				CreatedAt:           task.CreatedAt.Unix(),
				EstimatedCompletion: estimatedCompletion,
				QueueName:           fmt.Sprintf("%s:%s", task.TaskType, task.Priority),
			}
			responses = append(responses, response)
			submittedCount++
		}
	}

	batchResponse := &pb.BatchTaskSubmitResponse{
		BatchId:        req.BatchId,
		Responses:      responses,
		TotalCount:     int32(len(req.Tasks)),
		SubmittedCount: submittedCount,
		FailedCount:    failedCount,
	}

	s.log.Infof("Batch tasks submitted: batch_id=%s, submitted=%d, failed=%d", 
		req.BatchId, submittedCount, failedCount)

	return batchResponse, nil
}

// WatchTaskStatus 监听任务状态
func (s *TaskManagerServer) WatchTaskStatus(req *pb.TaskWatchRequest, stream pb.TaskManagerService_WatchTaskStatusServer) error {
	s.log.Infof("Started watching task status: task_id=%s, batch_id=%s", 
		req.TaskId, req.BatchId)

	if req.TaskId == "" && req.BatchId == "" {
		return status.Errorf(codes.InvalidArgument, "Either task_id or batch_id is required")
	}

	// 创建上下文用于取消
	ctx := stream.Context()
	
	// 实现简化的轮询监听
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	lastStatus := ""
	lastProgress := int32(-1)

	for {
		select {
		case <-ctx.Done():
			s.log.Infof("Task watch cancelled: task_id=%s", req.TaskId)
			return nil
		case <-ticker.C:
			if req.TaskId != "" {
				// 监听单个任务
				task, err := s.taskService.GetTask(ctx, req.TaskId)
				if err != nil {
					if err == service.ErrTaskNotFound {
						return status.Errorf(codes.NotFound, "Task not found: %s", req.TaskId)
					}
					continue
				}

				// 检查状态是否变化
				if string(task.Status) != lastStatus || int32(task.Progress) != lastProgress {
					update := &pb.TaskStatusUpdate{
						TaskId:    task.ID,
						Status:    string(task.Status),
						Progress:  int32(task.Progress),
						Message:   fmt.Sprintf("Task status: %s", task.Status),
						Timestamp: time.Now().Unix(),
						Metadata:  make(map[string]string),
					}

					// 添加元数据
					for k, v := range task.Payload {
						if str, ok := v.(string); ok {
							update.Metadata[k] = str
						}
					}

					if err := stream.Send(update); err != nil {
						s.log.Errorf("Failed to send status update: %v", err)
						return err
					}

					lastStatus = string(task.Status)
					lastProgress = int32(task.Progress)

					// 如果任务已结束，停止监听
					if task.IsTerminal() {
						s.log.Infof("Task completed, stopping watch: %s", req.TaskId)
						return nil
					}
				}
			}
			// TODO: 实现批次监听逻辑
		}
	}
}

// CancelTask 取消任务
func (s *TaskManagerServer) CancelTask(ctx context.Context, req *pb.TaskCancelRequest) (*pb.TaskCancelResponse, error) {
	if req.TaskId == "" {
		return nil, status.Errorf(codes.InvalidArgument, "Task ID is required")
	}

	err := s.taskService.CancelTask(ctx, req.TaskId)
	if err != nil {
		if err == service.ErrTaskNotFound {
			return nil, status.Errorf(codes.NotFound, "Task not found: %s", req.TaskId)
		}
		if err == service.ErrTaskNotCancelable {
			return nil, status.Errorf(codes.FailedPrecondition, "Task cannot be cancelled")
		}
		
		s.log.Errorf("Failed to cancel task %s: %v", req.TaskId, err)
		return nil, status.Errorf(codes.Internal, "Failed to cancel task: %v", err)
	}

	response := &pb.TaskCancelResponse{
		TaskId:      req.TaskId,
		Success:     true,
		Message:     "Task cancelled successfully",
		CancelledAt: time.Now().Unix(),
	}

	s.log.Infof("Task cancelled successfully: %s", req.TaskId)
	return response, nil
}

// ListTasks 获取任务列表
func (s *TaskManagerServer) ListTasks(ctx context.Context, req *pb.TaskListRequest) (*pb.TaskListResponse, error) {
	// 构建查询请求
	listReq := &model.TaskListRequest{
		KbID:     req.KnowledgeBaseId,
		Page:     int(req.Offset/req.Limit) + 1,
		PageSize: int(req.Limit),
		SortBy:   req.SortBy,
		SortOrder: req.SortOrder,
	}

	// 设置默认值
	if listReq.PageSize <= 0 {
		listReq.PageSize = 20
	}
	if listReq.PageSize > 100 {
		listReq.PageSize = 100
	}

	// 类型过滤
	if len(req.TaskTypes) > 0 && req.TaskTypes[0] != "" {
		listReq.TaskType = model.TaskType(req.TaskTypes[0])
	}

	// 状态过滤
	if len(req.Statuses) > 0 && req.Statuses[0] != "" {
		listReq.Status = model.TaskStatus(req.Statuses[0])
	}

	tasks, total, err := s.taskService.ListTasks(ctx, listReq)
	if err != nil {
		s.log.Errorf("Failed to list tasks: %v", err)
		return nil, status.Errorf(codes.Internal, "Failed to list tasks: %v", err)
	}

	// 转换任务列表
	taskResponses := make([]*pb.TaskStatusResponse, len(tasks))
	for i, task := range tasks {
		metadata := make(map[string]string)
		for k, v := range task.Payload {
			if str, ok := v.(string); ok {
				metadata[k] = str
			} else {
				metadata[k] = fmt.Sprintf("%v", v)
			}
		}

		taskResponse := &pb.TaskStatusResponse{
			TaskId:       task.ID,
			Status:       string(task.Status),
			Progress:     int32(task.Progress),
			Message:      task.ErrorMessage,
			ErrorMessage: task.ErrorMessage,
			CreatedAt:    task.CreatedAt.Unix(),
			Metadata:     metadata,
			WorkerId:     task.WorkerID,
		}

		if task.StartedAt != nil {
			taskResponse.StartedAt = task.StartedAt.Unix()
		}

		if task.CompletedAt != nil {
			taskResponse.CompletedAt = task.CompletedAt.Unix()
		}

		taskResponses[i] = taskResponse
	}

	response := &pb.TaskListResponse{
		Tasks:      taskResponses,
		TotalCount: int32(total),
		Limit:      req.Limit,
		Offset:     req.Offset,
		HasMore:    int64(req.Offset+req.Limit) < total,
	}

	return response, nil
}

// 私有方法

// validateTaskSubmitRequest 验证任务提交请求
func (s *TaskManagerServer) validateTaskSubmitRequest(req *pb.TaskSubmitRequest) error {
	if req.TaskType == "" {
		return fmt.Errorf("task_type is required")
	}

	if req.ServiceName == "" {
		return fmt.Errorf("service_name is required")
	}

	if req.KnowledgeBaseId == "" {
		return fmt.Errorf("knowledge_base_id is required")
	}

	// 验证任务类型
	taskType := model.TaskType(req.TaskType)
	if !taskType.IsValid() {
		return fmt.Errorf("invalid task_type: %s", req.TaskType)
	}

	// 验证优先级
	if req.Priority != "" {
		priority := model.TaskPriority(req.Priority)
		if !priority.IsValid() {
			return fmt.Errorf("invalid priority: %s", req.Priority)
		}
	}

	// 验证超时时间
	if req.TimeoutSeconds <= 0 {
		req.TimeoutSeconds = 1800 // 默认30分钟
	}
	if req.TimeoutSeconds > 7200 { // 最大2小时
		return fmt.Errorf("timeout_seconds too large (max 7200)")
	}

	// 验证重试次数
	if req.MaxRetries < 0 {
		req.MaxRetries = 3 // 默认3次
	}
	if req.MaxRetries > 10 {
		return fmt.Errorf("max_retries too large (max 10)")
	}

	return nil
}