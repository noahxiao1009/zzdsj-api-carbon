#!/bin/bash

# 任务管理服务构建脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 构建信息
APP_NAME="task-manager"
VERSION=$(git describe --tags --always --dirty 2>/dev/null || echo "v1.0.0")
COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
DATE=$(date +%Y-%m-%d_%H:%M:%S)
GO_VERSION=$(go version | awk '{print $3}')

# 构建标志
LDFLAGS="-s -w -X main.version=${VERSION} -X main.commit=${COMMIT} -X main.date=${DATE}"

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 显示构建信息
show_build_info() {
    log_info "=== 构建信息 ==="
    echo "应用名称: $APP_NAME"
    echo "版本: $VERSION"
    echo "提交: $COMMIT"
    echo "构建时间: $DATE"
    echo "Go版本: $GO_VERSION"
    echo "构建标志: $LDFLAGS"
    echo "=========================="
}

# 基础构建
build_basic() {
    log_info "执行基础构建..."
    mkdir -p build
    
    go build -o build/$APP_NAME ./cmd/server
    
    local size=$(ls -lh build/$APP_NAME | awk '{print $5}')
    log_info "✓ 基础构建完成: build/$APP_NAME ($size)"
}

# 优化构建 (减小体积)
build_optimized() {
    log_info "执行优化构建..."
    mkdir -p build
    
    # 禁用CGO，减小体积，添加构建信息
    CGO_ENABLED=0 go build \
        -ldflags="$LDFLAGS" \
        -o build/${APP_NAME}-optimized \
        ./cmd/server
    
    local size=$(ls -lh build/${APP_NAME}-optimized | awk '{print $5}')
    log_info "✓ 优化构建完成: build/${APP_NAME}-optimized ($size)"
}

# 静态链接构建
build_static() {
    log_info "执行静态链接构建..."
    mkdir -p build
    
    # 完全静态链接，适合容器部署
    CGO_ENABLED=0 go build \
        -ldflags="$LDFLAGS -extldflags '-static'" \
        -a -installsuffix cgo \
        -o build/${APP_NAME}-static \
        ./cmd/server
    
    local size=$(ls -lh build/${APP_NAME}-static | awk '{print $5}')
    log_info "✓ 静态构建完成: build/${APP_NAME}-static ($size)"
}

# Linux AMD64构建
build_linux_amd64() {
    log_info "执行Linux AMD64构建..."
    mkdir -p dist
    
    GOOS=linux GOARCH=amd64 CGO_ENABLED=0 go build \
        -ldflags="$LDFLAGS" \
        -o dist/${APP_NAME}-linux-amd64 \
        ./cmd/server
    
    local size=$(ls -lh dist/${APP_NAME}-linux-amd64 | awk '{print $5}')
    log_info "✓ Linux AMD64构建完成: dist/${APP_NAME}-linux-amd64 ($size)"
}

# Linux ARM64构建
build_linux_arm64() {
    log_info "执行Linux ARM64构建..."
    mkdir -p dist
    
    GOOS=linux GOARCH=arm64 CGO_ENABLED=0 go build \
        -ldflags="$LDFLAGS" \
        -o dist/${APP_NAME}-linux-arm64 \
        ./cmd/server
    
    local size=$(ls -lh dist/${APP_NAME}-linux-arm64 | awk '{print $5}')
    log_info "✓ Linux ARM64构建完成: dist/${APP_NAME}-linux-arm64 ($size)"
}

# macOS AMD64构建
build_darwin_amd64() {
    log_info "执行macOS AMD64构建..."
    mkdir -p dist
    
    GOOS=darwin GOARCH=amd64 CGO_ENABLED=0 go build \
        -ldflags="$LDFLAGS" \
        -o dist/${APP_NAME}-darwin-amd64 \
        ./cmd/server
    
    local size=$(ls -lh dist/${APP_NAME}-darwin-amd64 | awk '{print $5}')
    log_info "✓ macOS AMD64构建完成: dist/${APP_NAME}-darwin-amd64 ($size)"
}

# macOS ARM64构建 (Apple Silicon)
build_darwin_arm64() {
    log_info "执行macOS ARM64构建..."
    mkdir -p dist
    
    GOOS=darwin GOARCH=arm64 CGO_ENABLED=0 go build \
        -ldflags="$LDFLAGS" \
        -o dist/${APP_NAME}-darwin-arm64 \
        ./cmd/server
    
    local size=$(ls -lh dist/${APP_NAME}-darwin-arm64 | awk '{print $5}')
    log_info "✓ macOS ARM64构建完成: dist/${APP_NAME}-darwin-arm64 ($size)"
}

# Windows AMD64构建
build_windows_amd64() {
    log_info "执行Windows AMD64构建..."
    mkdir -p dist
    
    GOOS=windows GOARCH=amd64 CGO_ENABLED=0 go build \
        -ldflags="$LDFLAGS" \
        -o dist/${APP_NAME}-windows-amd64.exe \
        ./cmd/server
    
    local size=$(ls -lh dist/${APP_NAME}-windows-amd64.exe | awk '{print $5}')
    log_info "✓ Windows AMD64构建完成: dist/${APP_NAME}-windows-amd64.exe ($size)"
}

# 多平台构建
build_all_platforms() {
    log_info "执行多平台构建..."
    
    build_linux_amd64
    build_linux_arm64
    build_darwin_amd64
    build_darwin_arm64
    build_windows_amd64
    
    log_info "=== 多平台构建完成 ==="
    ls -lh dist/
}

# UPX压缩 (如果可用)
compress_with_upx() {
    if command -v upx &> /dev/null; then
        log_info "使用UPX压缩二进制文件..."
        
        # 压缩优化版本
        if [ -f "build/${APP_NAME}-optimized" ]; then
            cp build/${APP_NAME}-optimized build/${APP_NAME}-compressed
            upx --best build/${APP_NAME}-compressed
            
            local original_size=$(ls -lh build/${APP_NAME}-optimized | awk '{print $5}')
            local compressed_size=$(ls -lh build/${APP_NAME}-compressed | awk '{print $5}')
            log_info "✓ UPX压缩完成: $original_size → $compressed_size"
        fi
    else
        log_warn "UPX未安装，跳过压缩 (可选安装: brew install upx)"
    fi
}

# 创建发布包
create_release() {
    log_info "创建发布包..."
    mkdir -p release
    
    # 复制配置文件
    cp -r config release/
    cp -r scripts release/
    cp README.md release/ 2>/dev/null || true
    cp docs/QUICK_START.md release/ 2>/dev/null || true
    
    # 创建各平台的发布包
    if [ -d "dist" ]; then
        for binary in dist/*; do
            if [ -f "$binary" ]; then
                basename=$(basename "$binary")
                platform=$(echo "$basename" | sed "s/${APP_NAME}-//")
                
                mkdir -p "release/$platform"
                cp "$binary" "release/$platform/$APP_NAME"
                cp -r config "release/$platform/"
                
                # 创建启动脚本
                if [[ $platform == *"windows"* ]]; then
                    echo "@echo off" > "release/$platform/start.bat"
                    echo "$APP_NAME.exe" >> "release/$platform/start.bat"
                else
                    echo "#!/bin/bash" > "release/$platform/start.sh"
                    echo "./$APP_NAME" >> "release/$platform/start.sh"
                    chmod +x "release/$platform/start.sh"
                fi
                
                # 创建tar.gz包
                tar -czf "release/${APP_NAME}-${platform}.tar.gz" -C release "$platform"
                rm -rf "release/$platform"
            fi
        done
        
        log_info "✓ 发布包创建完成: release/"
        ls -lh release/*.tar.gz
    fi
}

# 清理构建产物
clean() {
    log_info "清理构建产物..."
    rm -rf build dist release
    log_info "✓ 清理完成"
}

# 验证构建
verify_build() {
    local binary="$1"
    
    if [ ! -f "$binary" ]; then
        log_error "二进制文件不存在: $binary"
        return 1
    fi
    
    # 检查文件类型
    file_info=$(file "$binary")
    log_info "文件信息: $file_info"
    
    # 检查版本信息 (如果二进制支持)
    if [[ "$file_info" == *"executable"* ]]; then
        if timeout 5s "$binary" --version 2>/dev/null; then
            log_info "✓ 版本检查通过"
        else
            log_warn "无法获取版本信息 (正常，服务不支持--version)"
        fi
    fi
    
    log_info "✓ 构建验证完成: $binary"
}

# 显示使用说明
show_usage() {
    echo "任务管理服务构建脚本"
    echo
    echo "使用方法:"
    echo "  $0 [build_type]"
    echo
    echo "构建类型:"
    echo "  basic       - 基础构建 (默认)"
    echo "  optimized   - 优化构建 (小体积)"
    echo "  static      - 静态链接构建"
    echo "  linux       - Linux AMD64构建"
    echo "  linux-arm   - Linux ARM64构建"
    echo "  macos       - macOS AMD64构建"
    echo "  macos-arm   - macOS ARM64构建"
    echo "  windows     - Windows AMD64构建"
    echo "  all         - 所有平台构建"
    echo "  release     - 创建发布包"
    echo "  clean       - 清理构建产物"
    echo
    echo "示例:"
    echo "  $0                # 基础构建"
    echo "  $0 optimized      # 优化构建"
    echo "  $0 all            # 多平台构建"
    echo "  $0 release        # 创建发布包"
}

# 主函数
main() {
    local build_type="${1:-basic}"
    
    if [ "$build_type" = "--help" ] || [ "$build_type" = "-h" ]; then
        show_usage
        exit 0
    fi
    
    # 检查Go环境
    if ! command -v go &> /dev/null; then
        log_error "Go未安装，请先安装Go"
        exit 1
    fi
    
    # 显示构建信息
    show_build_info
    
    # 执行构建
    case $build_type in
        "basic")
            build_basic
            verify_build "build/$APP_NAME"
            ;;
        "optimized")
            build_optimized
            compress_with_upx
            verify_build "build/${APP_NAME}-optimized"
            ;;
        "static")
            build_static
            verify_build "build/${APP_NAME}-static"
            ;;
        "linux")
            build_linux_amd64
            verify_build "dist/${APP_NAME}-linux-amd64"
            ;;
        "linux-arm")
            build_linux_arm64
            verify_build "dist/${APP_NAME}-linux-arm64"
            ;;
        "macos")
            build_darwin_amd64
            verify_build "dist/${APP_NAME}-darwin-amd64"
            ;;
        "macos-arm")
            build_darwin_arm64
            verify_build "dist/${APP_NAME}-darwin-arm64"
            ;;
        "windows")
            build_windows_amd64
            verify_build "dist/${APP_NAME}-windows-amd64.exe"
            ;;
        "all")
            build_all_platforms
            ;;
        "release")
            build_all_platforms
            create_release
            ;;
        "clean")
            clean
            ;;
        *)
            log_error "未知构建类型: $build_type"
            show_usage
            exit 1
            ;;
    esac
    
    log_info "🎉 构建完成！"
}

# 如果直接运行脚本
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    main "$@"
fi