# 智能报告微服务

基于Co-Sight的智能报告生成微服务，支持通过iframe嵌入到前端系统中。

## 快速启动

### 方式1: 直接启动
```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
python main.py
```

### 方式2: 使用启动脚本
```bash
python start_service.py
```

### 方式3: Docker部署
```bash
# 构建镜像
docker build -t intelligent-reports-service .

# 启动容器
docker run -d -p 7788:7788 intelligent-reports-service
```

## 访问地址

- **健康检查**: http://localhost:7788/health
- **Co-Sight界面**: http://localhost:7788/cosight/
- **API文档**: http://localhost:7788/docs

## 环境配置

在项目根目录创建 `.env` 文件，配置LLM和搜索引擎：

```env
# 基础LLM配置
API_KEY=your_api_key
API_BASE_URL=https://api.siliconflow.cn/v1
MODEL_NAME=deepseek-chat

# 可选：专用模型配置
PLAN_API_KEY=your_plan_api_key
PLAN_MODEL_NAME=deepseek-chat
ACT_API_KEY=your_act_api_key
ACT_MODEL_NAME=deepseek-chat

# 搜索引擎配置（可选）
TAVILY_API_KEY=your_tavily_key
GOOGLE_API_KEY=your_google_key
SEARCH_ENGINE_ID=your_search_engine_id
```

## 微服务特性

1. **服务注册**: 自动向网关注册服务
2. **健康检查**: 提供标准的健康检查接口
3. **CORS支持**: 支持跨域请求
4. **错误处理**: 统一的错误处理机制
5. **日志记录**: 结构化日志输出

## 原Co-Sight功能

保持Co-Sight的完整功能：

- 智能研究报告生成
- 多LLM模型支持
- 搜索引擎集成
- 实时WebSocket通信
- 文件上传处理
- 多语言支持

## 与前端集成

可通过iframe嵌入到前端系统：

```html
<iframe 
  src="http://localhost:7788/cosight/" 
  width="100%" 
  height="800px"
  frameborder="0">
</iframe>
```

## 目录结构

```
intelligent-reports-service/
├── main.py                    # 微服务入口
├── start_service.py          # 启动脚本
├── Dockerfile               # Docker配置
├── requirements.txt         # 依赖列表
├── cosight_server/          # Co-Sight原始代码
│   ├── deep_research/       # 核心研究功能
│   ├── web/                # 前端资源
│   └── sdk/                # SDK组件
├── app/                    # Co-Sight应用代码
├── config/                 # 配置文件
├── work_space/             # 工作空间
└── upload_files/           # 上传文件目录
```

## 故障排除

1. **服务启动失败**: 检查端口7788是否被占用
2. **配置问题**: 确保.env文件配置正确
3. **依赖错误**: 运行 `pip install -r requirements.txt`
4. **权限问题**: 确保工作目录有写入权限