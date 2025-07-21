# 智能体编排系统 (Flow Builder) 实现文档

## 概述

基于前端智能体编排页面 `http://localhost:5173/agent-system/flow-builder` 的设计，实现了一套完整的后端智能体编排系统。该系统支持三种基础智能体模版，采用DAG执行方式，并直接集成Agno官方API。

## 核心特性

### 1. 三种基础智能体模版

#### 1.1 基础对话模版 (basic_conversation)
- **目标场景**: 客户服务、日常咨询、快速问答
- **执行节点**: 5个节点线性执行
- **特点**: 毫秒级响应、轻量化架构、高并发支持
- **成本**: 低

**DAG执行流程**:
```
用户输入 → 意图识别智能体 → 回复生成智能体 → 输出结果
```

#### 1.2 知识库问答模版 (knowledge_base)
- **目标场景**: 技术支持、产品咨询、政策解读
- **执行节点**: 7个节点复杂检索流程
- **特点**: 知识库检索增强、引用和溯源、智能相关性评分
- **成本**: 中

**DAG执行流程**:
```
问题输入 → 查询分析智能体 → 知识检索智能体 → 答案合成智能体 → 置信度检查 → 输出答案
                                                                   ↓ (低置信度)
                                                               兜底智能体 → 输出答案
```

#### 1.3 深度思考模版 (deep_thinking)
- **目标场景**: 战略分析、复杂决策、研究报告
- **执行节点**: 8个节点复杂协作流程
- **特点**: 多步骤推理、团队协作能力、质量检查机制
- **成本**: 高

**DAG执行流程**:
```
任务输入 → 任务分析智能体 → 复杂度检查
                           ↓ (低复杂度)
                       单体解决智能体 → 输出结果
                           ↓ (高复杂度)
                       团队协调节点
                    ↙        ↓        ↘
               研究智能体  分析智能体  规划智能体
                    ↘        ↓        ↙
                         综合智能体 → 输出结果
```

### 2. DAG执行引擎

#### 2.1 核心特性
- **拓扑排序**: 确保节点按正确顺序执行
- **条件分支**: 支持基于条件的分支控制
- **并行执行**: 支持多节点并行处理
- **错误恢复**: 完善的异常处理机制
- **执行监控**: 详细的执行路径追踪

#### 2.2 节点类型
```python
- AGENT: 智能体节点
- CONDITION: 条件判断节点
- MERGE: 结果合并节点
- PARALLEL: 并行执行节点
- INPUT: 输入节点
- OUTPUT: 输出节点
```

### 3. Agno API集成

#### 3.1 直接使用官方API
- **无二次封装**: 直接使用Agno官方Python SDK
- **模型支持**: Claude、OpenAI、Anthropic等主流模型
- **工具集成**: 推理、搜索、计算、文件处理等工具
- **异步支持**: 全面支持异步操作

#### 3.2 智能体生命周期管理
```python
# 创建智能体
agent = Agent(
    name="智能体名称",
    model=Claude(id="claude-3-5-sonnet"),
    tools=[ReasoningTools(), SearchTools()],
    instructions="智能体指令",
    markdown=True
)

# 执行任务
response = await agent.arun(message, user_id=user_id)
```

## API接口设计

### 1. 模版管理接口

#### 获取模版列表
```http
GET /api/v1/flow-builder/templates
```

**响应示例**:
```json
{
  "success": true,
  "data": [
    {
      "template_id": "basic_conversation",
      "name": "基础对话模版",
      "description": "快速响应的轻量级对话助手",
      "category": "conversation",
      "recommended": true,
      "use_cases": ["客户服务", "日常咨询", "快速问答"],
      "estimated_cost": "低",
      "features": ["毫秒级响应速度", "直接准确回答"],
      "agentType": "simple-qa"
    }
  ]
}
```

#### 获取模版详情
```http
GET /api/v1/flow-builder/templates/{template_id}
```

### 2. 智能体创建接口

#### 基于模版创建智能体
```http
POST /api/v1/flow-builder/agents
```

**请求示例**:
```json
{
  "template_id": "basic_conversation",
  "configuration": {
    "basic_configuration": {
      "agent_name": "客服助手",
      "description": "专业的客服对话助手"
    },
    "model_configuration": {
      "model_name": "claude-3-5-sonnet",
      "temperature": 0.7,
      "max_tokens": 1000
    },
    "capability_configuration": {
      "enabled_tools": ["search", "calculator"],
      "knowledge_base_ids": [],
      "memory_enabled": true
    }
  }
}
```

### 3. 执行管理接口

#### 执行智能体
```http
POST /api/v1/flow-builder/agents/{agent_id}/execute
```

**请求示例**:
```json
{
  "message": "你好，请帮我分析一下这个问题",
  "stream": false,
  "additional_context": {
    "user_preference": "detailed",
    "language": "zh-CN"
  }
}
```

#### 流式执行
```http
GET /api/v1/flow-builder/executions/{execution_id}/stream
```

支持Server-Sent Events (SSE)流式响应：
```javascript
const eventSource = new EventSource('/api/v1/flow-builder/executions/exec_123/stream');
eventSource.onmessage = function(event) {
  const data = JSON.parse(event.data);
  console.log('执行进度:', data);
};
```

#### 获取执行状态
```http
GET /api/v1/flow-builder/executions/{execution_id}/status
```

### 4. 辅助接口

#### 获取可用模型
```http
GET /api/v1/flow-builder/models
```

#### 获取可用工具
```http
GET /api/v1/flow-builder/tools
```

#### 健康检查
```http
GET /api/v1/flow-builder/health
```

## 文件结构

```
agent-service/
├── app/
│   ├── core/
│   │   ├── agno_api_manager.py        # Agno官方API管理器
│   │   └── dag_orchestrator.py        # DAG编排器
│   ├── api/
│   │   └── flow_builder_routes.py     # Flow Builder API路由
│   ├── schemas/
│   │   └── flow_builder_schemas.py    # API Schema定义
│   └── ...
├── main.py                            # 更新的主启动文件
└── FLOW_BUILDER_IMPLEMENTATION.md     # 本文档
```

## 核心类介绍

### 1. AgnoAPIManager
负责Agno官方API的集成和管理：
- 智能体创建和生命周期管理
- 模型和工具注册表
- 异步执行和流式响应
- 错误处理和重试机制

### 2. DAGOrchestrator
负责DAG执行流程的编排：
- DAG模版管理
- 执行图构建和拓扑排序
- 节点并行执行
- 条件分支控制
- 执行状态监控

### 3. DAGTemplate
定义智能体模版的DAG结构：
- 节点定义（类型、配置、依赖）
- 边定义（条件、权重）
- 变量和默认配置
- 元数据管理

## 与前端的集成

### 1. 数据结构对应
前端的智能体模版选择直接对应后端的三种基础模版：
- `simple-qa` ↔ `basic_conversation`
- `knowledge-qa` ↔ `knowledge_base`
- `deep-thinking` ↔ `deep_thinking`

### 2. 配置映射
前端的流程构建器配置映射到后端的DAG节点配置：
- 基础配置 → 智能体基础信息
- 模型配置 → Agno模型选择和参数
- 能力配置 → 工具和知识库配置
- 高级配置 → 执行参数和安全设置

### 3. 执行反馈
支持实时执行反馈：
- 同步执行：立即返回完整结果
- 异步执行：返回执行ID，通过轮询获取状态
- 流式执行：SSE实时推送执行进度和中间结果

## 性能优化

### 1. 连接池管理
- HTTP连接复用
- 智能体实例缓存
- 资源自动清理

### 2. 并发控制
- 节点并行执行
- 异步IO优化
- 背压控制

### 3. 缓存机制
- 模版配置缓存
- 模型响应缓存（可选）
- 执行结果缓存

## 错误处理

### 1. 分级错误处理
- 节点级错误：单个节点失败不影响整体
- 流程级错误：关键路径失败时的降级策略
- 系统级错误：全局异常捕获和恢复

### 2. 重试机制
- 智能体调用重试
- 网络请求重试
- 指数退避策略

### 3. 降级策略
- 兜底智能体激活
- 简化流程执行
- 缓存结果返回

## 监控和日志

### 1. 执行监控
- 节点执行时间统计
- 智能体调用成功率
- 系统资源使用监控

### 2. 业务指标
- 模版使用频率
- 平均响应时间
- 用户满意度评分

### 3. 日志记录
- 结构化日志输出
- 执行路径追踪
- 错误详情记录

## 安全考虑

### 1. 输入验证
- 参数类型检查
- 内容安全过滤
- 配额限制

### 2. 权限控制
- 用户身份验证
- 资源访问控制
- 操作审计日志

### 3. 数据保护
- 敏感信息脱敏
- 传输加密
- 存储安全

## 扩展性设计

### 1. 模版扩展
- 自定义模版支持
- 模版继承机制
- 社区模版导入

### 2. 节点扩展
- 自定义节点类型
- 插件式工具集成
- 第三方服务连接

### 3. 框架扩展
- 多框架支持
- 模型提供商扩展
- 部署方式适配

## 部署配置

### 1. 环境要求
```bash
# Python依赖
pip install agno fastapi uvicorn

# 环境变量
export AGNO_API_KEY="your_agno_api_key"
export OPENAI_API_KEY="your_openai_api_key"
export ANTHROPIC_API_KEY="your_anthropic_api_key"
```

### 2. 启动服务
```bash
# 开发模式
python main.py

# 生产模式
uvicorn main:app --host 0.0.0.0 --port 8081 --workers 4
```

### 3. 健康检查
```bash
curl http://localhost:8081/api/v1/flow-builder/health
```

## 测试用例

### 1. 基础对话测试
```bash
# 创建智能体
curl -X POST http://localhost:8081/api/v1/flow-builder/agents \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "basic_conversation",
    "configuration": {
      "basic_configuration": {"agent_name": "测试助手"}
    }
  }'

# 执行对话
curl -X POST http://localhost:8081/api/v1/flow-builder/agents/agent_xxx/execute \
  -H "Content-Type: application/json" \
  -d '{"message": "你好"}'
```

### 2. 知识库问答测试
```bash
# 带知识库的复杂查询
curl -X POST http://localhost:8081/api/v1/flow-builder/agents/agent_xxx/execute \
  -H "Content-Type: application/json" \
  -d '{
    "message": "请解释一下机器学习的基本概念",
    "additional_context": {"domain": "technology"}
  }'
```

### 3. 流式执行测试
```javascript
// 前端流式监听
const eventSource = new EventSource('/api/v1/flow-builder/executions/exec_xxx/stream');
eventSource.onmessage = function(event) {
  const data = JSON.parse(event.data);
  if (data.type === 'node_result') {
    console.log(`节点 ${data.node_id} 完成:`, data.result);
  }
};
```

## 总结

本实现提供了一套完整的智能体编排系统，具有以下优势：

1. **原生集成**: 直接使用Agno官方API，无二次封装
2. **模版化**: 三种内置模版覆盖主要应用场景
3. **DAG执行**: 支持复杂的条件分支和并行执行
4. **实时监控**: 提供详细的执行状态和进度反馈
5. **高性能**: 异步执行和优化的资源管理
6. **易扩展**: 支持自定义模版和节点类型

该系统为前端提供了强大的后端支持，能够满足各种复杂的智能体编排需求，同时保持了良好的可维护性和扩展性。