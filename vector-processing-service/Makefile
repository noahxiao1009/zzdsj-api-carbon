.PHONY: proto build run test clean docker

# 项目信息
PROJECT_NAME := vector-processing-service
VERSION := v1.0.0
BUILD_TIME := $(shell date +%Y-%m-%d_%H:%M:%S)
GIT_COMMIT := $(shell git rev-parse --short HEAD)

# Go构建参数
LDFLAGS := -s -w -X main.Version=$(VERSION) -X main.BuildTime=$(BUILD_TIME) -X main.GitCommit=$(GIT_COMMIT)
GOBUILD := CGO_ENABLED=0 go build -ldflags="$(LDFLAGS)"

# 生成protobuf代码
proto:
	@echo "生成protobuf代码..."
	@mkdir -p pb
	protoc --go_out=pb --go-grpc_out=pb \
		--go_opt=paths=source_relative \
		--go-grpc_opt=paths=source_relative \
		../task-manager-service/protos/vector_service.proto
	protoc --go_out=pb --go-grpc_out=pb \
		--go_opt=paths=source_relative \
		--go-grpc_opt=paths=source_relative \
		../task-manager-service/protos/task_manager.proto

# 构建项目
build: proto
	@echo "构建项目..."
	$(GOBUILD) -o bin/$(PROJECT_NAME) ./cmd/server

# 构建优化版本
build-optimized: proto
	@echo "构建优化版本..."
	$(GOBUILD) -o bin/$(PROJECT_NAME)-optimized ./cmd/server

# 交叉编译Linux版本
build-linux: proto
	@echo "构建Linux版本..."
	GOOS=linux GOARCH=amd64 $(GOBUILD) -o bin/$(PROJECT_NAME)-linux ./cmd/server

# 运行服务
run: build
	@echo "启动服务..."
	./bin/$(PROJECT_NAME)

# 运行测试
test:
	@echo "运行测试..."
	go test -v ./...

# 性能测试
benchmark:
	@echo "运行性能测试..."
	go test -bench=. -benchmem ./...

# 清理构建文件
clean:
	@echo "清理构建文件..."
	rm -rf bin/
	rm -rf pb/

# 构建Docker镜像
docker:
	@echo "构建Docker镜像..."
	docker build -t $(PROJECT_NAME):$(VERSION) .
	docker tag $(PROJECT_NAME):$(VERSION) $(PROJECT_NAME):latest

# 运行Docker容器
docker-run:
	@echo "运行Docker容器..."
	docker run -p 8093:8093 --name $(PROJECT_NAME) $(PROJECT_NAME):latest

# 安装依赖
deps:
	@echo "安装依赖..."
	go mod tidy
	go mod download

# 代码格式化
fmt:
	@echo "格式化代码..."
	go fmt ./...

# 代码检查
lint:
	@echo "检查代码..."
	golangci-lint run

# 生成mock文件
mock:
	@echo "生成mock文件..."
	mockgen -source=internal/service/vector_service.go -destination=internal/service/mocks/vector_service_mock.go

# 帮助信息
help:
	@echo "可用命令:"
	@echo "  proto          - 生成protobuf代码"
	@echo "  build          - 构建项目"
	@echo "  build-optimized - 构建优化版本"
	@echo "  build-linux    - 交叉编译Linux版本"
	@echo "  run            - 运行服务"
	@echo "  test           - 运行测试"
	@echo "  benchmark      - 运行性能测试"
	@echo "  clean          - 清理构建文件"
	@echo "  docker         - 构建Docker镜像"
	@echo "  docker-run     - 运行Docker容器"
	@echo "  deps           - 安装依赖"
	@echo "  fmt            - 格式化代码"
	@echo "  lint           - 代码检查"
	@echo "  mock           - 生成mock文件"