package handler

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/gorilla/websocket"
	"github.com/sirupsen/logrus"

	"task-manager-service/internal/model"
	"task-manager-service/internal/service"
)

// PollingHandler 任务状态轮询处理器
type PollingHandler struct {
	taskService    *service.TaskService
	log            *logrus.Entry
	wsUpgrader     websocket.Upgrader
	activeClients  map[string]*WSClient
	clientsMutex   sync.RWMutex
	pollingTicker  *time.Ticker
	stopPolling    chan struct{}
	pollingRunning bool
}

// WSClient WebSocket客户端
type WSClient struct {
	ID           string
	Conn         *websocket.Conn
	TaskIDs      []string          // 订阅的任务ID
	KbIDs        []string          // 订阅的知识库ID
	TaskTypes    []model.TaskType  // 订阅的任务类型
	LastSeen     time.Time
	SendChannel  chan []byte
	CloseChannel chan struct{}
}

// TaskStatusUpdate 任务状态更新消息
type TaskStatusUpdate struct {
	Type      string      `json:"type"`
	Timestamp time.Time   `json:"timestamp"`
	TaskID    string      `json:"task_id"`
	Status    string      `json:"status"`
	Progress  int         `json:"progress"`
	Message   string      `json:"message"`
	Task      *model.Task `json:"task,omitempty"`
}

// PollingRequest 轮询请求
type PollingRequest struct {
	TaskIDs   []string          `form:"task_ids"`
	KbIDs     []string          `form:"kb_ids"`
	TaskTypes []model.TaskType  `form:"task_types"`
	Since     *time.Time        `form:"since"`
	Timeout   int               `form:"timeout"`
}

// PollingResponse 轮询响应
type PollingResponse struct {
	Updates   []TaskStatusUpdate `json:"updates"`
	Timestamp time.Time          `json:"timestamp"`
	HasMore   bool               `json:"has_more"`
}

func NewPollingHandler(taskService *service.TaskService) *PollingHandler {
	handler := &PollingHandler{
		taskService:   taskService,
		log:           logrus.WithField("component", "polling-handler"),
		activeClients: make(map[string]*WSClient),
		stopPolling:   make(chan struct{}),
		wsUpgrader: websocket.Upgrader{
			CheckOrigin: func(r *http.Request) bool {
				return true // 允许跨域，生产环境应该更严格
			},
			ReadBufferSize:  1024,
			WriteBufferSize: 1024,
		},
	}

	// 启动轮询协程
	go handler.startPollingLoop()

	return handler
}

// StartPolling 开始轮询
func (ph *PollingHandler) startPollingLoop() {
	ph.pollingTicker = time.NewTicker(2 * time.Second) // 每2秒轮询一次
	ph.pollingRunning = true
	ph.log.Info("Task status polling started")

	for {
		select {
		case <-ph.pollingTicker.C:
			ph.pollTaskUpdates()
		case <-ph.stopPolling:
			ph.pollingTicker.Stop()
			ph.pollingRunning = false
			ph.log.Info("Task status polling stopped")
			return
		}
	}
}

// StopPolling 停止轮询
func (ph *PollingHandler) StopPolling() {
	if ph.pollingRunning {
		close(ph.stopPolling)
	}
	
	// 关闭所有WebSocket连接
	ph.clientsMutex.Lock()
	for _, client := range ph.activeClients {
		close(client.CloseChannel)
	}
	ph.activeClients = make(map[string]*WSClient)
	ph.clientsMutex.Unlock()
}

// PollTaskStatus HTTP轮询接口
func (ph *PollingHandler) PollTaskStatus(c *gin.Context) {
	var req PollingRequest
	if err := c.ShouldBindQuery(&req); err != nil {
		ph.log.Errorf("Invalid polling request: %v", err)
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Invalid request parameters",
			"message": err.Error(),
		})
		return
	}

	// 设置默认超时
	if req.Timeout <= 0 {
		req.Timeout = 30 // 30秒
	}
	if req.Timeout > 300 {
		req.Timeout = 300 // 最大5分钟
	}

	// 设置默认的since时间
	if req.Since == nil {
		since := time.Now().Add(-1 * time.Minute)
		req.Since = &since
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), time.Duration(req.Timeout)*time.Second)
	defer cancel()

	// 轮询任务状态更新
	updates, err := ph.getTaskUpdates(ctx, &req)
	if err != nil {
		ph.log.Errorf("Failed to get task updates: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to get task updates",
			"message": err.Error(),
		})
		return
	}

	response := PollingResponse{
		Updates:   updates,
		Timestamp: time.Now(),
		HasMore:   len(updates) > 0,
	}

	c.JSON(http.StatusOK, response)
}

// WSTaskStatus WebSocket任务状态订阅
func (ph *PollingHandler) WSTaskStatus(c *gin.Context) {
	// 升级HTTP连接为WebSocket
	conn, err := ph.wsUpgrader.Upgrade(c.Writer, c.Request, nil)
	if err != nil {
		ph.log.Errorf("Failed to upgrade WebSocket connection: %v", err)
		return
	}

	// 创建客户端
	clientID := fmt.Sprintf("client_%d", time.Now().UnixNano())
	client := &WSClient{
		ID:           clientID,
		Conn:         conn,
		LastSeen:     time.Now(),
		SendChannel:  make(chan []byte, 256),
		CloseChannel: make(chan struct{}),
	}

	// 注册客户端
	ph.clientsMutex.Lock()
	ph.activeClients[clientID] = client
	ph.clientsMutex.Unlock()

	ph.log.Infof("WebSocket client connected: %s", clientID)

	// 启动客户端处理协程
	go ph.handleWSClient(client)
}

// GetActivePollingClients 获取活跃轮询客户端
func (ph *PollingHandler) GetActivePollingClients(c *gin.Context) {
	ph.clientsMutex.RLock()
	defer ph.clientsMutex.RUnlock()

	clients := make([]map[string]interface{}, 0)
	for _, client := range ph.activeClients {
		clients = append(clients, map[string]interface{}{
			"id":          client.ID,
			"task_ids":    client.TaskIDs,
			"kb_ids":      client.KbIDs,
			"task_types":  client.TaskTypes,
			"last_seen":   client.LastSeen,
			"connected":   true,
		})
	}

	c.JSON(http.StatusOK, gin.H{
		"active_clients": clients,
		"total_clients":  len(clients),
		"polling_status": ph.pollingRunning,
	})
}

// NotifyTaskUpdate 通知任务状态更新
func (ph *PollingHandler) NotifyTaskUpdate(taskID string, status string, progress int, message string, task *model.Task) {
	update := TaskStatusUpdate{
		Type:      "task_update",
		Timestamp: time.Now(),
		TaskID:    taskID,
		Status:    status,
		Progress:  progress,
		Message:   message,
		Task:      task,
	}

	// 发送给所有感兴趣的WebSocket客户端
	ph.broadcastUpdate(update)
}

// 私有方法

// pollTaskUpdates 轮询任务更新
func (ph *PollingHandler) pollTaskUpdates() {
	ph.clientsMutex.RLock()
	clientCount := len(ph.activeClients)
	ph.clientsMutex.RUnlock()

	if clientCount == 0 {
		return // 没有活跃客户端
	}

	// 获取所有订阅的任务ID
	allTaskIDs := ph.getAllSubscribedTaskIDs()
	if len(allTaskIDs) == 0 {
		return
	}

	// 检查任务状态变化
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	for _, taskID := range allTaskIDs {
		task, err := ph.taskService.GetTask(ctx, taskID)
		if err != nil {
			continue
		}

		// 检查是否有状态变化
		if ph.shouldNotifyUpdate(task.Task) {
			update := TaskStatusUpdate{
				Type:      "task_update",
				Timestamp: time.Now(),
				TaskID:    task.ID,
				Status:    string(task.Status),
				Progress:  task.Progress,
				Message:   "Task status updated",
				Task:      task.Task,
			}

			ph.broadcastUpdate(update)
		}
	}
}

// handleWSClient 处理WebSocket客户端
func (ph *PollingHandler) handleWSClient(client *WSClient) {
	defer func() {
		ph.removeClient(client.ID)
		client.Conn.Close()
		ph.log.Infof("WebSocket client disconnected: %s", client.ID)
	}()

	// 启动发送协程
	go ph.handleWSClientSend(client)

	// 读取客户端消息
	for {
		select {
		case <-client.CloseChannel:
			return
		default:
			// 设置读取超时
			client.Conn.SetReadDeadline(time.Now().Add(60 * time.Second))
			
			var msg map[string]interface{}
			err := client.Conn.ReadJSON(&msg)
			if err != nil {
				if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
					ph.log.Errorf("WebSocket read error: %v", err)
				}
				return
			}

			// 处理客户端消息
			ph.handleWSMessage(client, msg)
			client.LastSeen = time.Now()
		}
	}
}

// handleWSClientSend 处理WebSocket客户端发送
func (ph *PollingHandler) handleWSClientSend(client *WSClient) {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-client.CloseChannel:
			return
		case data := <-client.SendChannel:
			client.Conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			if err := client.Conn.WriteMessage(websocket.TextMessage, data); err != nil {
				ph.log.Errorf("WebSocket write error: %v", err)
				return
			}
		case <-ticker.C:
			// 发送心跳
			client.Conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			if err := client.Conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				return
			}
		}
	}
}

// handleWSMessage 处理WebSocket消息
func (ph *PollingHandler) handleWSMessage(client *WSClient, msg map[string]interface{}) {
	msgType, ok := msg["type"].(string)
	if !ok {
		return
	}

	switch msgType {
	case "subscribe":
		ph.handleSubscribeMessage(client, msg)
	case "unsubscribe":
		ph.handleUnsubscribeMessage(client, msg)
	case "ping":
		ph.sendWSMessage(client, map[string]interface{}{
			"type":      "pong",
			"timestamp": time.Now(),
		})
	}
}

// handleSubscribeMessage 处理订阅消息
func (ph *PollingHandler) handleSubscribeMessage(client *WSClient, msg map[string]interface{}) {
	if taskIDs, ok := msg["task_ids"].([]interface{}); ok {
		client.TaskIDs = make([]string, 0)
		for _, id := range taskIDs {
			if strID, ok := id.(string); ok {
				client.TaskIDs = append(client.TaskIDs, strID)
			}
		}
	}

	if kbIDs, ok := msg["kb_ids"].([]interface{}); ok {
		client.KbIDs = make([]string, 0)
		for _, id := range kbIDs {
			if strID, ok := id.(string); ok {
				client.KbIDs = append(client.KbIDs, strID)
			}
		}
	}

	if taskTypes, ok := msg["task_types"].([]interface{}); ok {
		client.TaskTypes = make([]model.TaskType, 0)
		for _, t := range taskTypes {
			if strType, ok := t.(string); ok {
				client.TaskTypes = append(client.TaskTypes, model.TaskType(strType))
			}
		}
	}

	// 发送订阅确认
	ph.sendWSMessage(client, map[string]interface{}{
		"type":       "subscribed",
		"task_ids":   client.TaskIDs,
		"kb_ids":     client.KbIDs,
		"task_types": client.TaskTypes,
		"timestamp":  time.Now(),
	})

	ph.log.Infof("Client %s subscribed to %d tasks, %d KBs, %d types", 
		client.ID, len(client.TaskIDs), len(client.KbIDs), len(client.TaskTypes))
}

// handleUnsubscribeMessage 处理取消订阅消息
func (ph *PollingHandler) handleUnsubscribeMessage(client *WSClient, msg map[string]interface{}) {
	client.TaskIDs = nil
	client.KbIDs = nil
	client.TaskTypes = nil

	ph.sendWSMessage(client, map[string]interface{}{
		"type":      "unsubscribed",
		"timestamp": time.Now(),
	})
}

// broadcastUpdate 广播更新
func (ph *PollingHandler) broadcastUpdate(update TaskStatusUpdate) {
	data, err := json.Marshal(update)
	if err != nil {
		ph.log.Errorf("Failed to marshal update: %v", err)
		return
	}

	ph.clientsMutex.RLock()
	defer ph.clientsMutex.RUnlock()

	for _, client := range ph.activeClients {
		if ph.shouldSendToClient(client, update) {
			select {
			case client.SendChannel <- data:
			default:
				ph.log.Warnf("Client %s send channel full, skipping update", client.ID)
			}
		}
	}
}

// shouldSendToClient 判断是否应该向客户端发送更新
func (ph *PollingHandler) shouldSendToClient(client *WSClient, update TaskStatusUpdate) bool {
	// 检查任务ID订阅
	for _, taskID := range client.TaskIDs {
		if taskID == update.TaskID {
			return true
		}
	}

	// 检查知识库ID订阅
	if update.Task != nil {
		for _, kbID := range client.KbIDs {
			if kbID == update.Task.KbID {
				return true
			}
		}

		// 检查任务类型订阅
		for _, taskType := range client.TaskTypes {
			if taskType == update.Task.TaskType {
				return true
			}
		}
	}

	return false
}

// sendWSMessage 发送WebSocket消息
func (ph *PollingHandler) sendWSMessage(client *WSClient, msg map[string]interface{}) {
	data, err := json.Marshal(msg)
	if err != nil {
		ph.log.Errorf("Failed to marshal WebSocket message: %v", err)
		return
	}

	select {
	case client.SendChannel <- data:
	default:
		ph.log.Warnf("Client %s send channel full", client.ID)
	}
}

// removeClient 移除客户端
func (ph *PollingHandler) removeClient(clientID string) {
	ph.clientsMutex.Lock()
	defer ph.clientsMutex.Unlock()
	
	delete(ph.activeClients, clientID)
}

// getAllSubscribedTaskIDs 获取所有订阅的任务ID
func (ph *PollingHandler) getAllSubscribedTaskIDs() []string {
	ph.clientsMutex.RLock()
	defer ph.clientsMutex.RUnlock()

	taskIDSet := make(map[string]bool)
	for _, client := range ph.activeClients {
		for _, taskID := range client.TaskIDs {
			taskIDSet[taskID] = true
		}
	}

	taskIDs := make([]string, 0, len(taskIDSet))
	for taskID := range taskIDSet {
		taskIDs = append(taskIDs, taskID)
	}

	return taskIDs
}

// shouldNotifyUpdate 判断是否应该通知更新
func (ph *PollingHandler) shouldNotifyUpdate(task *model.Task) bool {
	// 简化实现：检查任务是否在最近更新
	return time.Since(task.UpdatedAt) < 5*time.Second
}

// getTaskUpdates 获取任务更新
func (ph *PollingHandler) getTaskUpdates(ctx context.Context, req *PollingRequest) ([]TaskStatusUpdate, error) {
	updates := make([]TaskStatusUpdate, 0)

	// 轮询等待更新
	ticker := time.NewTicker(1 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return updates, nil
		case <-ticker.C:
			// 检查任务更新
			if len(req.TaskIDs) > 0 {
				for _, taskID := range req.TaskIDs {
					task, err := ph.taskService.GetTask(ctx, taskID)
					if err != nil {
						continue
					}

					if task.UpdatedAt.After(*req.Since) {
						update := TaskStatusUpdate{
							Type:      "task_update",
							Timestamp: time.Now(),
							TaskID:    task.ID,
							Status:    string(task.Status),
							Progress:  task.Progress,
							Message:   "Task status polled",
							Task:      task.Task,
						}
						updates = append(updates, update)
					}
				}
			}

			if len(updates) > 0 {
				return updates, nil
			}
		}
	}
}