package grpc

import (
	"fmt"
	"net"

	"google.golang.org/grpc"
	"google.golang.org/grpc/reflection"
	"github.com/sirupsen/logrus"

	"task-manager-service/internal/service"
	pb "task-manager-service/pkg/proto"
)

// Server gRPC服务器
type Server struct {
	server      *grpc.Server
	listener    net.Listener
	taskService *service.TaskService
	log         *logrus.Entry
}

// NewGRPCServer 创建gRPC服务器
func NewGRPCServer(taskService *service.TaskService, port int) (*Server, error) {
	// 创建监听器
	listener, err := net.Listen("tcp", fmt.Sprintf(":%d", port))
	if err != nil {
		return nil, fmt.Errorf("failed to listen on port %d: %w", port, err)
	}

	// 创建gRPC服务器
	grpcServer := grpc.NewServer()

	// 注册服务
	taskManagerServer := NewTaskManagerServer(taskService)
	
	// 注册反射服务（开发环境使用）
	reflection.Register(grpcServer)

	server := &Server{
		server:      grpcServer,
		listener:    listener,
		taskService: taskService,
		log:         logrus.WithField("component", "grpc-server"),
	}

	// 注册TaskManager服务
	pb.RegisterTaskManagerServiceServer(grpcServer, taskManagerServer)

	return server, nil
}

// Start 启动gRPC服务器
func (s *Server) Start() error {
	s.log.Infof("Starting gRPC server on %s", s.listener.Addr().String())
	
	return s.server.Serve(s.listener)
}

// Stop 停止gRPC服务器
func (s *Server) Stop() {
	s.log.Info("Stopping gRPC server...")
	s.server.GracefulStop()
	s.log.Info("gRPC server stopped")
}

// GetAddress 获取服务器地址
func (s *Server) GetAddress() string {
	return s.listener.Addr().String()
}