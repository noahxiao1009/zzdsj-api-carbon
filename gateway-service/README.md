# Gateway Service - 网关服务

## 概述

智政科技AI智能办公助手系统的API网关服务，基于原ZZDSJ Backend API架构改造而成，负责统一管理所有微服务的访问入口。

## 功能特点

- **统一入口**: 所有API请求的统一入口点
- **路由分发**: 智能路由
- **负载均衡**: 负载均衡支持
- **服务发现**: 自动发现和健康检查
- **认证鉴权**: 统一的JWT令牌验证
- **限流熔断**: 防护系统过载和故障传播
- **监控日志**: 请求监控和日志记录

## 技术栈

- **FastAPI**: 高性能Web框架
- **Python 3.11**: 编程语言
- **Redis**: 缓存和会话存储
- **Docker**: 容器化部署

## 目录结构

```
gateway-service/
├── app/
│   ├── config/             # 配置模块
│   │   └── settings.py     # 应用配置
│   ├── middleware/         # 中间件
│   ├── routing/           # 路由管理
│   ├── discovery/         # 服务发现
│   └── utils/             # 工具函数
│       └── common/
│           └── logging_config.py  # 日志配置
├── main.py                # 主启动文件
├── requirements.txt       # Python依赖
├── Dockerfile            # Docker配置
└── README.md            # 项目文档
```

## 快速开始

### 本地开发

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 启动服务：
```bash
python main.py
```

3. 访问文档：
```
http://localhost:8080/docs
```

### Docker部署

1. 构建镜像：
```bash
docker build -t gateway-service .
```

2. 运行容器：
```bash
docker run -p 8080:8080 gateway-service
```

## 配置说明

主要配置项通过环境变量设置：

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| SERVICE_PORT | 8080 | 服务端口 |
| APP_ENV | development | 环境类型 |
| LOG_LEVEL | INFO | 日志级别 |
| AGENT_SERVICE_URL | http://localhost:8081 | 智能体服务地址 |
| KNOWLEDGE_SERVICE_URL | http://localhost:8082 | 知识库服务地址 |
| MODEL_SERVICE_URL | http://localhost:8083 | 模型服务地址 |
| BASE_SERVICE_URL | http://localhost:8084 | 基础服务地址 |

## API接口

### 基础接口

- `GET /` - 服务根路径
- `GET /health` - 健康检查
- `GET /docs` - API文档
- `GET /openapi.json` - OpenAPI规范

### 代理接口

- `/api/agent/*` - 智能体服务代理
- `/api/knowledge/*` - 知识库服务代理
- `/api/models/*` - 模型服务代理
- `/api/base/*` - 基础服务代理

## 监控和日志

网关服务提供完整的监控和日志功能：

- 请求响应时间监控
- 错误率统计
- 服务健康状态检查
- 结构化日志输出

## 开发指南

### 添加新的路由规则

在 `app/routing/` 目录下添加新的路由配置文件。

### 添加中间件

在 `app/middleware/` 目录下实现新的中间件功能。

### 配置服务发现

在 `app/discovery/` 目录下配置服务注册和发现逻辑。

