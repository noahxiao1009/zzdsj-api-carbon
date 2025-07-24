# 微服务PM2管理指南

## 概述

本项目为NextAgent的微服务架构，提供了完整的PM2进程管理支持。支持单独启动每个微服务或批量管理所有服务。

## 服务列表

| 服务简称 | 服务名称 | 端口 | 说明 |
|---------|----------|------|------|
| gateway | gateway-service | 8080 | 网关服务，统一入口 |
| agent | agent-service | 8081 | 智能体服务，基于Agno框架 |
| knowledge | knowledge-service | 8082 | 知识库服务，基于LlamaIndex |
| chat | chat-service | 8083 | 聊天服务，对话管理 |
| database | database-service | 8084 | 数据库服务，统一数据层 |
| base | base-service | 8085 | 基础服务，用户权限管理 |
| system | system-service | 8086 | 系统服务，配置管理 |
| kg | knowledge-graph-service | 8087 | 知识图谱服务 |
| model | model-service | 8088 | 模型服务，AI模型管理 |
| mcp | mcp-service | 8089 | MCP服务，FastMCP框架 |
| tools | tools-service | 8090 | 工具服务，集成工具组件 |
| reports | intelligent-reports-service | 8091 | 智能报告服务，Co-Sight |
| kaiban | kaiban-service | 8092 | 看板服务，工作流管理 |
| messaging | messaging-service | 8093 | 消息服务，异步通信 |
| scheduler | scheduler-service | 8094 | 调度服务，任务调度 |

## 核心服务

核心服务（必须启动）：
- **gateway-service** (8080): 网关入口
- **knowledge-service** (8082): 知识库管理
- **agent-service** (8081): 智能体功能
- **model-service** (8088): 模型服务
- **database-service** (8084): 数据管理

## 快速启动

### 方式一：交互式管理界面（强烈推荐）

```bash
# 启动交互式管理界面（默认）
./start-services.sh

# 或者显式调用
./start-services.sh interactive

# 生产环境交互式管理
./pm2-manager.sh interactive production

# 直接进入PM2管理器
./pm2-manager.sh
```

**交互式界面功能**：
- 🎯 **可视化服务列表**: 显示所有服务状态、端口、类型
- 🔄 **多选操作**: 支持单选、多选、全选服务
- 📊 **实时状态**: 彩色显示服务运行状态
- ⚡ **快捷操作**: 一键启动核心服务或所有服务
- 🛠️ **环境切换**: 开发/生产环境快速切换

### 方式二：使用快速启动脚本

```bash
# 启动核心服务
./start-services.sh core

# 启动所有服务
./start-services.sh all

# 使用全局配置启动
./start-services.sh global

# 停止所有服务
./start-services.sh stop

# 查看状态
./start-services.sh status
```

### 方式三：使用PM2管理脚本（高级用户）

```bash
# 交互式选择启动服务
./pm2-manager.sh select:start

# 交互式选择停止服务  
./pm2-manager.sh select:stop

# 显示帮助
./pm2-manager.sh help

# 启动核心服务
./pm2-manager.sh start:core

# 启动所有服务
./pm2-manager.sh start:all

# 启动单个服务
./pm2-manager.sh start knowledge
./pm2-manager.sh start agent production

# 停止服务
./pm2-manager.sh stop knowledge
./pm2-manager.sh stop:all

# 重启服务
./pm2-manager.sh restart knowledge
./pm2-manager.sh restart:all

# 查看状态
./pm2-manager.sh status

# 查看日志
./pm2-manager.sh logs
./pm2-manager.sh logs knowledge

# 监控服务
./pm2-manager.sh monitor
```

### 方式四：直接使用PM2命令

```bash
# 使用全局配置启动所有服务
pm2 start ecosystem.all.config.js

# 启动单个服务
cd knowledge-service
pm2 start ecosystem.config.js

# 查看状态
pm2 status

# 停止所有服务
pm2 stop all

# 删除所有服务
pm2 delete all
```

## 环境配置

支持两种环境：
- **development** (默认): 开发环境，详细日志
- **production**: 生产环境，优化配置

```bash
# 开发环境启动
./pm2-manager.sh start knowledge development

# 生产环境启动
./pm2-manager.sh start knowledge production
```

## 日志管理

每个服务都有独立的日志文件：

```
{service-name}/logs/
├── pm2-{service}-error.log     # 错误日志
├── pm2-{service}-out.log       # 输出日志
├── pm2-{service}-combined.log  # 合并日志
└── pm2-{service}.pid          # 进程ID文件
```

查看日志：
```bash
# 查看特定服务日志
./pm2-manager.sh logs knowledge

# 查看所有服务日志
./pm2-manager.sh logs

# 实时监控
pm2 monit
```

## 服务依赖

推荐的启动顺序：
1. **database-service** (8084) - 数据库服务
2. **gateway-service** (8080) - 网关服务  
3. **model-service** (8088) - 模型服务
4. **knowledge-service** (8082) - 知识库服务
5. **agent-service** (8081) - 智能体服务
6. 其他支撑服务

## 性能配置

不同服务的内存限制：
- **model-service**: 3G (AI模型加载需要更多内存)
- **knowledge-service**: 2G (向量计算)
- **knowledge-graph-service**: 2G (图计算)
- **intelligent-reports-service**: 2G (报告生成)
- **gateway-service**: 1G
- **其他服务**: 1G

## 故障处理

### 常见问题

1. **端口占用**
```bash
# 检查端口占用
lsof -i :8080

# 杀死占用进程
kill -9 <PID>
```

2. **服务启动失败**
```bash
# 查看详细错误日志
./pm2-manager.sh logs <service>

# 重启服务
./pm2-manager.sh restart <service>
```

3. **内存不足**
```bash
# 查看内存使用
pm2 monit

# 重启高内存服务
./pm2-manager.sh restart model
```

### 健康检查

```bash
# 服务状态检查
curl http://localhost:8080/health  # 网关
curl http://localhost:8082/health  # 知识库
curl http://localhost:8081/health  # 智能体

# PM2状态检查
pm2 status
pm2 info <service-name>
```

## 开发调试

### 单服务调试模式

```bash
# 停止PM2中的服务
./pm2-manager.sh stop knowledge

# 直接运行调试
cd knowledge-service
python main.py
```

### 热重载模式

开发时可以启用watch模式（需要修改ecosystem配置）：
```javascript
// ecosystem.config.js
{
  watch: true,
  watch_delay: 1000,
  ignore_watch: ["logs", "*.log", "node_modules"]
}
```

## 生产部署

### 生产环境启动

```bash
# 生产环境启动所有服务
./pm2-manager.sh start:all production

# 保存PM2配置
pm2 save

# 设置开机自启
pm2 startup
```

### 集群模式

对于高并发服务，可以启用集群模式（需要修改配置）：
```javascript
{
  instances: "max",  // 或指定数量
  exec_mode: "cluster"
}
```

## 监控告警

### PM2 Plus集成

```bash
# 连接PM2 Plus（可选）
pm2 plus

# 设置监控告警
pm2 set pmx:http true
pm2 set pmx:http-latency 200
pm2 set pmx:http-code 500
```

### 自定义监控

可以结合以下工具：
- **Prometheus**: 指标收集
- **Grafana**: 可视化监控
- **ELK Stack**: 日志分析

## 备份恢复

### 配置备份

```bash
# 保存当前配置
pm2 save

# 备份配置文件
cp ~/.pm2/dump.pm2 ./backup/pm2-backup-$(date +%Y%m%d).pm2
```

### 快速恢复

```bash
# 恢复服务
pm2 resurrect

# 或重新启动所有服务
./start-services.sh all
```

## 最佳实践

1. **分阶段启动**: 先启动核心服务，再启动扩展服务
2. **监控内存**: 定期检查服务内存使用情况
3. **日志轮转**: 配置日志文件自动轮转，避免磁盘满
4. **定期重启**: 长期运行的服务建议定期重启
5. **版本管理**: 部署前确保所有依赖版本正确

## 支持与帮助

如遇问题，请检查：
1. 日志文件中的错误信息
2. 端口是否被占用
3. Python环境和依赖是否正确安装
4. 服务配置文件是否正确

更多帮助：
```bash
./pm2-manager.sh help
pm2 --help
```