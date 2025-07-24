#!/bin/bash

# 修复PM2配置文件中的硬编码路径问题
# 将所有硬编码的绝对路径替换为动态的相对路径

echo "正在修复PM2配置文件中的硬编码路径..."

# 服务列表和端口映射
declare -A SERVICES
SERVICES=(
    ["gateway-service"]=8080
    ["agent-service"]=8081
    ["knowledge-service"]=8082
    ["chat-service"]=8083
    ["database-service"]=8084
    ["base-service"]=8085
    ["system-service"]=8086
    ["knowledge-graph-service"]=8087
    ["model-service"]=8088
    ["mcp-service"]=8089
    ["tools-service"]=8090
    ["intelligent-reports-service"]=8091
    ["kaiban-service"]=8092
    ["messaging-service"]=8093
    ["scheduler-service"]=8094
)

# 为每个服务创建标准化的PM2配置
for service_name in "${!SERVICES[@]}"; do
    port=${SERVICES[$service_name]}
    config_file="$service_name/ecosystem.config.js"
    
    if [ -d "$service_name" ]; then
        echo "修复 $service_name..."
        
        # 生成标准化的PM2配置
        cat > "$config_file" << EOF
const path = require('path');
const currentDir = __dirname;

module.exports = {
  apps: [{
    name: "$service_name",
    script: "main.py",
    interpreter: "python",
    cwd: currentDir,
    instances: 1,
    exec_mode: "fork",
    env: {
      NODE_ENV: "development",
      SERVICE_NAME: "$service_name",
      SERVICE_PORT: $port,
      LOG_LEVEL: "INFO",
      PYTHONPATH: currentDir
    },
    env_production: {
      NODE_ENV: "production",
      SERVICE_NAME: "$service_name", 
      SERVICE_PORT: $port,
      LOG_LEVEL: "WARNING",
      PYTHONPATH: currentDir
    },
    watch: false,
    max_memory_restart: "1G",
    restart_delay: 3000,
    min_uptime: "10s",
    max_restarts: 10,
    merge_logs: true,
    log_date_format: "YYYY-MM-DD HH:mm:ss",
    error_file: "logs/pm2-${service_name%-service}-error.log",
    out_file: "logs/pm2-${service_name%-service}-out.log", 
    log_file: "logs/pm2-${service_name%-service}-combined.log",
    pid_file: "logs/pm2-${service_name%-service}.pid"
  }]
};
EOF
        
        echo "✅ $service_name 配置已更新"
    else
        echo "⚠️  $service_name 目录不存在，跳过"
    fi
done

# 特殊处理：为高内存需求的服务调整内存限制
echo ""
echo "调整特殊服务的内存配置..."

# 模型服务需要更多内存
if [ -f "model-service/ecosystem.config.js" ]; then
    sed -i '' 's/max_memory_restart: "1G"/max_memory_restart: "3G"/' model-service/ecosystem.config.js
    echo "✅ model-service 内存限制调整为 3G"
fi

# 知识库服务需要更多内存
if [ -f "knowledge-service/ecosystem.config.js" ]; then
    sed -i '' 's/max_memory_restart: "1G"/max_memory_restart: "2G"/' knowledge-service/ecosystem.config.js
    echo "✅ knowledge-service 内存限制调整为 2G"
fi

# 知识图谱服务需要更多内存
if [ -f "knowledge-graph-service/ecosystem.config.js" ]; then
    sed -i '' 's/max_memory_restart: "1G"/max_memory_restart: "2G"/' knowledge-graph-service/ecosystem.config.js
    echo "✅ knowledge-graph-service 内存限制调整为 2G"
fi

# 智能报告服务需要更多内存
if [ -f "intelligent-reports-service/ecosystem.config.js" ]; then
    sed -i '' 's/max_memory_restart: "1G"/max_memory_restart: "2G"/' intelligent-reports-service/ecosystem.config.js
    echo "✅ intelligent-reports-service 内存限制调整为 2G"
fi

echo ""
echo "🎉 所有PM2配置文件已修复完成！"
echo ""
echo "主要改进："
echo "  ✅ 移除硬编码的绝对路径"
echo "  ✅ 使用 __dirname 获取当前目录"
echo "  ✅ 统一配置格式和标准"
echo "  ✅ 根据服务类型调整内存限制"
echo ""
echo "现在可以在任何环境中正常启动微服务了！"