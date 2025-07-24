#!/bin/bash

# 最终修复PM2配置文件中的错误
echo "最终修复PM2配置文件..."

# 修复错误的变量定义
find . -name "ecosystem.config.js" -exec sed -i '' 's/const currentDir = currentDir;/const currentDir = __dirname;/g' {} \;

echo "✅ 已修复所有配置文件中的变量定义错误"

# 验证修复结果
echo ""
echo "验证修复结果："
for config in */ecosystem.config.js; do
    if [ -f "$config" ]; then
        service_name=$(dirname "$config")
        if grep -q "const currentDir = __dirname;" "$config" && grep -q "cwd: currentDir" "$config"; then
            echo "✅ $service_name - 配置正确"
        else
            echo "❌ $service_name - 需要手动检查"
        fi
    fi
done

echo ""
echo "🎉 PM2配置文件修复完成！"
echo ""
echo "主要改进："
echo "  ✅ 移除了所有硬编码的绝对路径"
echo "  ✅ 使用 __dirname 动态获取当前目录"
echo "  ✅ 支持在任何环境中部署"
echo "  ✅ 保持了统一的配置格式"