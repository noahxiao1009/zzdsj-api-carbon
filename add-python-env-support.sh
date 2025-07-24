#!/bin/bash

# 为所有PM2配置添加Python环境支持
echo "正在为所有微服务添加Python环境支持..."

# Python环境检测代码模板
read -r -d '' PYTHON_DETECTION << 'EOF'
const path = require('path');
const { execSync } = require('child_process');
const currentDir = __dirname;

// 动态获取Python解释器路径
function getPythonInterpreter() {
  try {
    // 优先使用环境变量指定的Python路径
    if (process.env.PYTHON_INTERPRETER) {
      return process.env.PYTHON_INTERPRETER;
    }
    
    // 尝试获取当前激活的Python环境
    const pythonPath = execSync('which python', { encoding: 'utf8' }).trim();
    console.log(`使用Python解释器: ${pythonPath}`);
    return pythonPath;
  } catch (error) {
    console.warn('无法检测Python路径，使用默认值: python');
    return 'python';
  }
}

const pythonInterpreter = getPythonInterpreter();
EOF

# 服务列表
services=(
    "gateway-service"
    "agent-service"
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
        echo "处理 $service..."
        
        # 检查是否已经有Python检测代码
        if ! grep -q "getPythonInterpreter" "$config_file"; then
            # 创建临时文件
            temp_file=$(mktemp)
            
            # 写入Python检测代码
            echo "$PYTHON_DETECTION" > "$temp_file"
            echo "" >> "$temp_file"
            
            # 添加原配置文件内容，但跳过原有的头部导入
            sed '/^const path = require/d; /^const currentDir = __dirname/d; /^$/{ /^$/d; }' "$config_file" >> "$temp_file"
            
            # 替换interpreter配置
            sed -i '' 's/interpreter: "python"/interpreter: pythonInterpreter/g' "$temp_file"
            
            # 替换回原文件
            mv "$temp_file" "$config_file"
            
            echo "✅ $service 已添加Python环境支持"
        else
            echo "⏭️  $service 已有Python环境支持，跳过"
        fi
    else
        echo "⚠️  $config_file 不存在，跳过"
    fi
done

echo ""
echo "🎉 所有服务已添加Python环境支持！"
echo ""
echo "使用方法："
echo "  1. 默认自动检测: pm2 start ecosystem.config.js"
echo "  2. 手动指定环境: PYTHON_INTERPRETER=/path/to/python pm2 start ecosystem.config.js"
echo "  3. Conda环境示例: PYTHON_INTERPRETER=/opt/anaconda3/envs/myenv/bin/python pm2 start ecosystem.config.js"
echo ""
echo "环境变量优先级："
echo "  PYTHON_INTERPRETER > which python > python"