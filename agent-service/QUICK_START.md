# 智能体服务快速启动指南

## 快速启动

### 1. 安装依赖
```bash
pip install fastapi uvicorn pydantic pydantic-settings
```

### 2. 配置环境变量（可选）
```bash
cp .env.example .env
# 编辑 .env 文件配置AI模型API密钥
```

### 3. 启动服务
```bash
python main.py
```

服务将在 http://localhost:8081 启动

## API文档

启动后访问：
- **Swagger UI**: http://localhost:8081/docs
- **ReDoc**: http://localhost:8081/redoc
- **健康检查**: http://localhost:8081/health

## 测试API

### 获取模板列表
```bash
curl http://localhost:8081/api/v1/templates/list
```

### 创建智能体
```bash
curl -X POST http://localhost:8081/api/v1/agents/create \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "basic_conversation",
    "basic_configuration": {
      "agent_name": "测试助手",
      "agent_description": "一个测试智能体"
    },
    "model_configuration": {
      "provider": "openai",
      "model": "gpt-4o-mini",
      "temperature": 0.7,
      "max_tokens": 1000
    },
    "capability_configuration": {
      "tools": []
    }
  }'
```

### 与智能体对话
```bash
curl -X POST http://localhost:8081/api/v1/agents/{agent_id}/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "你好！",
    "stream": false
  }'
```

## 开发模式

设置环境变量启用调试模式：
```bash
export DEBUG=true
python main.py
```

## Docker部署

```bash
# 构建镜像
docker build -t agent-service:latest .

# 运行容器
docker run -p 8081:8081 agent-service:latest
```

## 集成其他服务

智能体服务设计为微服务架构的一部分：

- **网关服务**: http://localhost:8080 (路由和负载均衡)
- **知识库服务**: http://localhost:8082 (知识检索)
- **模型服务**: http://localhost:8083 (模型管理)
- **基础服务**: http://localhost:8084 (用户和权限)

