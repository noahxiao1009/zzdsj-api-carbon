#!/bin/bash

# 批量修复PM2配置文件中的硬编码路径
echo "正在批量修复PM2配置文件..."

# 服务列表（手动列出确保准确性）
services=(
    "model-service"
    "chat-service" 
    "database-service"
    "knowledge-graph-service"
    "mcp-service"
    "messaging-service"
    "scheduler-service"
    "tools-service"
    "intelligent-reports-service"
    "kaiban-service"
)

for service in "${services[@]}"; do
    config_file="$service/ecosystem.config.js"
    
    if [ -f "$config_file" ]; then
        echo "修复 $service..."
        
        # 使用sed替换硬编码路径
        sed -i '' 's|cwd: "/Users/wxn/Desktop/carbon/zzdsl-api-carbon/[^"]*"|cwd: __dirname|g' "$config_file"
        sed -i '' 's|PYTHONPATH: "/Users/wxn/Desktop/carbon/zzdsl-api-carbon/[^"]*"|PYTHONPATH: __dirname|g' "$config_file"
        
        # 在文件开头添加必要的代码
        if ! grep -q "const.*__dirname" "$config_file"; then
            # 创建临时文件
            temp_file=$(mktemp)
            echo "const path = require('path');" > "$temp_file"
            echo "const currentDir = __dirname;" >> "$temp_file"
            echo "" >> "$temp_file"
            cat "$config_file" >> "$temp_file"
            mv "$temp_file" "$config_file"
            
            # 将__dirname替换为currentDir以保持一致性
            sed -i '' 's/__dirname/currentDir/g' "$config_file"
        fi
        
        echo "✅ $service 配置已更新"
    else
        echo "⚠️  $config_file 不存在，跳过"
    fi
done

echo ""
echo "🎉 批量修复完成！"
echo ""
echo "现在所有服务都使用相对路径，可以在任何环境中部署。"