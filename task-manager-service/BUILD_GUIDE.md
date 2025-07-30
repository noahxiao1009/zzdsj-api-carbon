# 任务管理服务构建指南

## 🛠 直接使用 go build

### 基础构建

```bash
# 进入项目目录
cd /Users/wxn/Desktop/carbon/zzdsl-api-carbon/task-manager-service

# 下载依赖
go mod download && go mod tidy

# 基础构建
go build -o task-manager ./cmd/server

# 运行
./task-manager
```

### 优化构建

```bash
# 禁用CGO，减小体积
CGO_ENABLED=0 go build -ldflags="-s -w" -o task-manager-small ./cmd/server

# 查看大小对比
ls -lh task-manager*
```

### 静态链接构建

```bash
# 完全静态链接（适合容器部署）
CGO_ENABLED=0 go build \
  -ldflags="-s -w -extldflags '-static'" \
  -a -installsuffix cgo \
  -o task-manager-static \
  ./cmd/server
```

## 🌍 跨平台构建

### Linux 版本

```bash
# Linux AMD64
GOOS=linux GOARCH=amd64 CGO_ENABLED=0 \
  go build -ldflags="-s -w" -o task-manager-linux-amd64 ./cmd/server

# Linux ARM64 (树莓派等)
GOOS=linux GOARCH=arm64 CGO_ENABLED=0 \
  go build -ldflags="-s -w" -o task-manager-linux-arm64 ./cmd/server
```

### macOS 版本

```bash
# macOS Intel
GOOS=darwin GOARCH=amd64 CGO_ENABLED=0 \
  go build -ldflags="-s -w" -o task-manager-macos-intel ./cmd/server

# macOS Apple Silicon
GOOS=darwin GOARCH=arm64 CGO_ENABLED=0 \
  go build -ldflags="-s -w" -o task-manager-macos-arm ./cmd/server
```

### Windows 版本

```bash
# Windows AMD64
GOOS=windows GOARCH=amd64 CGO_ENABLED=0 \
  go build -ldflags="-s -w" -o task-manager-windows.exe ./cmd/server
```

## 🚀 使用构建脚本

### 基本使用

```bash
# 基础构建
./scripts/build.sh

# 优化构建
./scripts/build.sh optimized

# Linux构建
./scripts/build.sh linux

# 所有平台构建
./scripts/build.sh all
```

### 构建选项

| 选项 | 说明 | 输出文件 |
|------|------|----------|
| `basic` | 基础构建（默认）| `build/task-manager` |
| `optimized` | 优化构建，减小体积 | `build/task-manager-optimized` |
| `static` | 静态链接构建 | `build/task-manager-static` |
| `linux` | Linux AMD64 | `dist/task-manager-linux-amd64` |
| `linux-arm` | Linux ARM64 | `dist/task-manager-linux-arm64` |
| `macos` | macOS Intel | `dist/task-manager-darwin-amd64` |
| `macos-arm` | macOS Apple Silicon | `dist/task-manager-darwin-arm64` |
| `windows` | Windows AMD64 | `dist/task-manager-windows-amd64.exe` |
| `all` | 所有平台 | `dist/` 目录下所有平台版本 |
| `release` | 创建发布包 | `release/` 目录下压缩包 |

## 📦 构建标志说明

### LDFLAGS 参数

```bash
# -s: 去除符号表
# -w: 去除调试信息
# -X: 设置变量值
go build -ldflags="-s -w -X main.version=v1.0.0 -X main.commit=abc123" ./cmd/server
```

### CGO_ENABLED

```bash
# CGO_ENABLED=0: 禁用CGO，创建静态二进制
# CGO_ENABLED=1: 启用CGO（默认）
CGO_ENABLED=0 go build ./cmd/server
```

## 🎯 生产环境构建推荐

### 服务器部署（推荐）

```bash
# Linux服务器推荐构建
GOOS=linux GOARCH=amd64 CGO_ENABLED=0 go build \
  -ldflags="-s -w -X main.version=$(git describe --tags --always)" \
  -o task-manager-prod \
  ./cmd/server
```

### 容器部署（推荐）

```bash
# Docker容器推荐构建
CGO_ENABLED=0 go build \
  -ldflags="-s -w -extldflags '-static'" \
  -a -installsuffix cgo \
  -o task-manager-container \
  ./cmd/server
```

## 🔍 验证构建

### 检查文件信息

```bash
# 查看文件大小
ls -lh task-manager*

# 查看文件类型
file task-manager

# 查看依赖库
ldd task-manager  # Linux
otool -L task-manager  # macOS
```

### 测试运行

```bash
# 测试运行
./task-manager --help 2>/dev/null || echo "服务正常（不支持--help）"

# 检查版本信息（如果支持）
./task-manager --version 2>/dev/null || echo "无版本信息"
```

## 🚀 快速部署

### 复制到生产服务器

```bash
# 构建Linux版本
GOOS=linux GOARCH=amd64 CGO_ENABLED=0 \
  go build -ldflags="-s -w" -o task-manager-linux ./cmd/server

# 复制到服务器
scp task-manager-linux user@server:/opt/task-manager/
scp -r config user@server:/opt/task-manager/

# SSH到服务器启动
ssh user@server "cd /opt/task-manager && ./task-manager-linux"
```

### 使用systemd服务

创建 `/etc/systemd/system/task-manager.service`:

```ini
[Unit]
Description=Task Manager Service
After=network.target

[Service]
Type=simple
User=taskmanager
WorkingDirectory=/opt/task-manager
ExecStart=/opt/task-manager/task-manager-linux
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl enable task-manager
sudo systemctl start task-manager
sudo systemctl status task-manager
```

## 🎁 构建技巧

### 减小二进制体积

```bash
# 1. 使用构建标签去除调试信息
go build -tags netgo -ldflags="-s -w" ./cmd/server

# 2. 使用UPX压缩（如果安装了UPX）
upx --best task-manager

# 3. 去除符号表和调试信息
go build -ldflags="-s -w -buildid=" ./cmd/server
```

### 版本信息嵌入

```bash
# 嵌入Git信息
VERSION=$(git describe --tags --always --dirty)
COMMIT=$(git rev-parse --short HEAD)
DATE=$(date +%Y-%m-%d_%H:%M:%S)

go build -ldflags="-s -w \
  -X main.version=$VERSION \
  -X main.commit=$COMMIT \
  -X main.buildTime=$DATE" \
  ./cmd/server
```

### 构建缓存优化

```bash
# 清理构建缓存
go clean -cache

# 并行构建
go build -p 4 ./cmd/server

# 显示构建详情
go build -v ./cmd/server
```

## 🐛 常见问题

### 问题1: CGO错误

```bash
# 错误: CGO_ENABLED but no C compiler
# 解决: 禁用CGO
CGO_ENABLED=0 go build ./cmd/server
```

### 问题2: 依赖问题

```bash
# 错误: missing go.sum entry
# 解决: 重新整理依赖
go mod tidy
go mod download
```

### 问题3: 权限问题

```bash
# 错误: permission denied
# 解决: 添加执行权限
chmod +x task-manager
```

### 问题4: 动态链接库问题

```bash
# 错误: library not found
# 解决: 使用静态链接
CGO_ENABLED=0 go build -ldflags="-extldflags '-static'" ./cmd/server
```

## 📋 构建检查清单

- [ ] Go环境已安装（1.21+）
- [ ] 依赖已下载 (`go mod download`)
- [ ] 代码可以编译 (`go build`)
- [ ] 二进制文件可执行
- [ ] 目标平台正确
- [ ] 文件大小合理
- [ ] 无动态依赖（生产环境）
- [ ] 版本信息正确

使用这些方法，你就可以灵活地构建和部署任务管理服务了！🎉