# Makefile for Task Manager Service

# 变量定义
APP_NAME := task-manager-service
BINARY_NAME := task-manager
VERSION := $(shell git describe --tags --always --dirty)
COMMIT := $(shell git rev-parse --short HEAD)
DATE := $(shell date +%Y-%m-%d_%H:%M:%S)
LDFLAGS := -ldflags "-X main.version=$(VERSION) -X main.commit=$(COMMIT) -X main.date=$(DATE)"

# Go相关变量
GOCMD := go
GOBUILD := $(GOCMD) build
GOCLEAN := $(GOCMD) clean
GOTEST := $(GOCMD) test
GOGET := $(GOCMD) get
GOMOD := $(GOCMD) mod
GOFMT := gofmt

# 目录
CMD_DIR := cmd/server
BUILD_DIR := build
DIST_DIR := dist

.PHONY: all build clean test coverage deps fmt vet lint run dev docker docker-build docker-run docker-stop install help

# 默认目标
all: clean fmt vet test build

# 构建
build:
	@echo "Building $(BINARY_NAME)..."
	@mkdir -p $(BUILD_DIR)
	CGO_ENABLED=0 GOOS=linux GOARCH=amd64 $(GOBUILD) $(LDFLAGS) -o $(BUILD_DIR)/$(BINARY_NAME) ./$(CMD_DIR)
	@echo "Build completed: $(BUILD_DIR)/$(BINARY_NAME)"

# 构建多平台版本
build-all:
	@echo "Building for multiple platforms..."
	@mkdir -p $(DIST_DIR)
	
	# Linux AMD64
	CGO_ENABLED=0 GOOS=linux GOARCH=amd64 $(GOBUILD) $(LDFLAGS) -o $(DIST_DIR)/$(BINARY_NAME)-linux-amd64 ./$(CMD_DIR)
	
	# Linux ARM64
	CGO_ENABLED=0 GOOS=linux GOARCH=arm64 $(GOBUILD) $(LDFLAGS) -o $(DIST_DIR)/$(BINARY_NAME)-linux-arm64 ./$(CMD_DIR)
	
	# macOS AMD64
	CGO_ENABLED=0 GOOS=darwin GOARCH=amd64 $(GOBUILD) $(LDFLAGS) -o $(DIST_DIR)/$(BINARY_NAME)-darwin-amd64 ./$(CMD_DIR)
	
	# macOS ARM64 (Apple Silicon)
	CGO_ENABLED=0 GOOS=darwin GOARCH=arm64 $(GOBUILD) $(LDFLAGS) -o $(DIST_DIR)/$(BINARY_NAME)-darwin-arm64 ./$(CMD_DIR)
	
	# Windows AMD64
	CGO_ENABLED=0 GOOS=windows GOARCH=amd64 $(GOBUILD) $(LDFLAGS) -o $(DIST_DIR)/$(BINARY_NAME)-windows-amd64.exe ./$(CMD_DIR)
	
	@echo "Multi-platform build completed in $(DIST_DIR)/"

# 清理
clean:
	@echo "Cleaning..."
	$(GOCLEAN)
	rm -rf $(BUILD_DIR)
	rm -rf $(DIST_DIR)
	@echo "Clean completed"

# 测试
test:
	@echo "Running tests..."
	$(GOTEST) -v ./...

# 测试覆盖率
coverage:
	@echo "Running tests with coverage..."
	$(GOTEST) -coverprofile=coverage.out ./...
	$(GOCMD) tool cover -html=coverage.out -o coverage.html
	@echo "Coverage report generated: coverage.html"

# 依赖管理
deps:
	@echo "Downloading dependencies..."
	$(GOMOD) download
	$(GOMOD) tidy

# 代码格式化
fmt:
	@echo "Formatting code..."
	@find . -name "*.go" -not -path "./vendor/*" | xargs $(GOFMT) -s -w
	@echo "Code formatted"

# 代码检查
vet:
	@echo "Running go vet..."
	$(GOCMD) vet ./...

# 代码质量检查 (需要安装golangci-lint)
lint:
	@echo "Running linter..."
	@if command -v golangci-lint > /dev/null; then \
		golangci-lint run; \
	else \
		echo "golangci-lint not found. Install it with: go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest"; \
	fi

# 运行服务
run: build
	@echo "Starting $(BINARY_NAME)..."
	./$(BUILD_DIR)/$(BINARY_NAME)

# 开发模式运行
dev:
	@echo "Starting development server..."
	$(GOCMD) run ./$(CMD_DIR)

# 安装到系统
install: build
	@echo "Installing $(BINARY_NAME)..."
	sudo cp $(BUILD_DIR)/$(BINARY_NAME) /usr/local/bin/
	@echo "Installed to /usr/local/bin/$(BINARY_NAME)"

# Docker相关
docker: docker-build

docker-build:
	@echo "Building Docker image..."
	docker build -t $(APP_NAME):$(VERSION) .
	docker tag $(APP_NAME):$(VERSION) $(APP_NAME):latest
	@echo "Docker image built: $(APP_NAME):$(VERSION)"

docker-run:
	@echo "Running Docker container..."
	docker-compose up -d

docker-stop:
	@echo "Stopping Docker containers..."
	docker-compose down

docker-logs:
	@echo "Showing Docker logs..."
	docker-compose logs -f task-manager

# 数据库相关
db-up:
	@echo "Starting database services..."
	docker-compose up -d postgres redis

db-down:
	@echo "Stopping database services..."
	docker-compose stop postgres redis

db-reset:
	@echo "Resetting databases..."
	docker-compose down -v
	docker-compose up -d postgres redis

# 性能测试
benchmark:
	@echo "Running benchmarks..."
	$(GOTEST) -bench=. -benchmem ./...

# 生成文档
docs:
	@echo "Generating documentation..."
	@if command -v godoc > /dev/null; then \
		echo "Documentation server starting at http://localhost:6060"; \
		godoc -http=:6060; \
	else \
		echo "godoc not found. Install it with: go install golang.org/x/tools/cmd/godoc@latest"; \
	fi

# 代码统计
stats:
	@echo "Code statistics:"
	@find . -name "*.go" -not -path "./vendor/*" | xargs wc -l | tail -1
	@echo "Files:"
	@find . -name "*.go" -not -path "./vendor/*" | wc -l

# 版本信息
version:
	@echo "Version: $(VERSION)"
	@echo "Commit: $(COMMIT)"
	@echo "Date: $(DATE)"

# 工具安装
tools:
	@echo "Installing development tools..."
	go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
	go install golang.org/x/tools/cmd/godoc@latest
	go install github.com/swaggo/swag/cmd/swag@latest
	@echo "Tools installed"

# 生成API文档 (需要swag)
swag:
	@echo "Generating Swagger documentation..."
	@if command -v swag > /dev/null; then \
		swag init -g ./cmd/server/main.go -o ./docs; \
		echo "Swagger docs generated in ./docs/"; \
	else \
		echo "swag not found. Install it with: make tools"; \
	fi

# 压力测试
stress-test:
	@echo "Running stress test..."
	@if command -v hey > /dev/null; then \
		hey -n 1000 -c 10 -m POST \
			-H "Content-Type: application/json" \
			-d '{"task_type":"test","kb_id":"test123","payload":{"message":"hello"}}' \
			http://localhost:8084/api/v1/tasks; \
	else \
		echo "hey not found. Install it with: go install github.com/rakyll/hey@latest"; \
	fi

# 健康检查
health:
	@echo "Checking service health..."
	@curl -f http://localhost:8084/health || echo "Service is not healthy"

# 监控指标
metrics:
	@echo "Fetching metrics..."
	@curl -s http://localhost:8084/metrics | head -20

# 部署到生产环境
deploy-prod: build-all
	@echo "Deploying to production..."
	# 这里添加生产环境部署逻辑
	@echo "Deployment completed"

# 帮助信息
help:
	@echo "Available commands:"
	@echo "  build          - Build the application"
	@echo "  build-all      - Build for multiple platforms"
	@echo "  clean          - Clean build artifacts"
	@echo "  test           - Run tests"
	@echo "  coverage       - Run tests with coverage"
	@echo "  deps           - Download dependencies"
	@echo "  fmt            - Format code"
	@echo "  vet            - Run go vet"
	@echo "  lint           - Run linter (requires golangci-lint)"
	@echo "  run            - Build and run the application"
	@echo "  dev            - Run in development mode"
	@echo "  install        - Install to system (/usr/local/bin)"
	@echo "  docker-build   - Build Docker image"
	@echo "  docker-run     - Run Docker containers"
	@echo "  docker-stop    - Stop Docker containers"
	@echo "  docker-logs    - Show Docker logs"
	@echo "  db-up          - Start database services"
	@echo "  db-down        - Stop database services"
	@echo "  db-reset       - Reset databases"
	@echo "  benchmark      - Run benchmarks"
	@echo "  docs           - Generate documentation"
	@echo "  stats          - Show code statistics"
	@echo "  version        - Show version information"
	@echo "  tools          - Install development tools"
	@echo "  swag           - Generate Swagger documentation"
	@echo "  stress-test    - Run stress test"
	@echo "  health         - Check service health"
	@echo "  metrics        - Fetch metrics"
	@echo "  deploy-prod    - Deploy to production"
	@echo "  help           - Show this help message"