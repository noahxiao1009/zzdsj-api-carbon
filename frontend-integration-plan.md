# Agent-Orchestration-Service 前端集成方案

## 🎯 快速演示集成方案 (明天使用)

### 1. 在 zzdsj-vector-web 中添加导航菜单

```typescript
// 在主导航中添加新菜单项
const navigation = [
  // ... 现有菜单项
  {
    name: '智能体编排监控',
    icon: '🤖',
    href: '/agent-orchestration',
    description: '多智能体协作流程可视化监控'
  }
]
```

### 2. 创建 Agent-Orchestration 页面

```typescript
// pages/agent-orchestration/index.tsx
import React, { useEffect, useState } from 'react';

interface AgentOrchestrationPageProps {}

export default function AgentOrchestrationPage() {
  const [isServiceReady, setIsServiceReady] = useState(false);

  useEffect(() => {
    // 检查后端服务是否可用
    const checkService = async () => {
      try {
        const response = await fetch('http://localhost:8000/health');
        setIsServiceReady(response.ok);
      } catch (error) {
        console.error('Agent orchestration service not available:', error);
        setIsServiceReady(false);
      }
    };

    checkService();
    const interval = setInterval(checkService, 5000);
    return () => clearInterval(interval);
  }, []);

  if (!isServiceReady) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <h3 className="text-lg font-medium text-gray-900">启动智能体编排服务</h3>
          <p className="text-gray-500">请稍候，正在连接服务...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col">
      {/* 头部信息栏 */}
      <div className="bg-white shadow-sm border-b px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">智能体编排监控</h1>
            <p className="text-gray-600">多智能体协作流程实时可视化</p>
          </div>
          <div className="flex items-center space-x-4">
            <div className="flex items-center">
              <div className="w-2 h-2 bg-green-400 rounded-full mr-2"></div>
              <span className="text-sm text-gray-600">服务运行中</span>
            </div>
            <a 
              href="http://localhost:8000" 
              target="_blank" 
              rel="noopener noreferrer"
              className="text-blue-600 hover:text-blue-800 text-sm"
            >
              在新窗口打开 ↗
            </a>
          </div>
        </div>
      </div>

      {/* 嵌入的 Agent-Orchestration 界面 */}
      <div className="flex-1">
        <iframe
          src="http://localhost:8000"
          className="w-full h-full border-0"
          title="智能体编排监控系统"
          allow="clipboard-read; clipboard-write"
        />
      </div>
    </div>
  );
}
```

### 3. 添加路由配置

```typescript
// 在路由配置中添加
{
  path: '/agent-orchestration',
  component: AgentOrchestrationPage,
  meta: {
    title: '智能体编排监控',
    requiresAuth: true
  }
}
```

## 🚀 服务启动配置

### 启动 Agent-Orchestration 服务

```bash
# 1. 启动后端服务
cd /Users/wxn/Desktop/carbon/zzdsl-api-carbon/agent-orchestration-service/core
python run_server.py --host 0.0.0.0 --port 8000

# 2. 启动前端服务 (如果需要独立运行)
cd /Users/wxn/Desktop/carbon/zzdsl-api-carbon/agent-orchestration-service/frontend
npm run dev
```

### 环境配置

确保 `.env` 文件包含硅基流动配置：
```bash
DEFAULT_BASE_URL=https://api.siliconflow.cn/v1
DEFAULT_API_KEY=sk-jipjycienusxsfdptoweqvagdillzrumjjtcblfjfsrdhqxk
```

## 🎯 演示功能展示

### 核心演示场景

1. **多智能体协作流程**
   - Partner Agent: 接收用户需求，制定策略
   - Principal Agent: 任务分解和分配
   - Associate Agents: 并行执行具体任务

2. **实时可视化监控**
   - **Flow View**: 显示智能体执行节点和数据流
   - **Kanban View**: 任务状态看板管理
   - **Timeline View**: 执行时间线追踪

3. **项目化管理**
   - 创建新项目
   - 管理多个运行实例
   - 历史记录查看

### 演示脚本

```markdown
1. 在主导航点击"智能体编排监控"
2. 演示创建新项目
3. 输入复杂查询："帮我分析一下人工智能在教育领域的应用前景，包括技术趋势、市场机会和潜在挑战"
4. 实时观察：
   - Partner Agent 接收并理解需求
   - Principal Agent 分解为子任务
   - Associate Agents 并行执行
5. 切换不同视图：
   - Flow View: 看执行流程图
   - Kanban View: 看任务状态
   - Timeline View: 看时间线
6. 展示最终整合结果
```

## 📈 集成优势

1. **完整保留原功能**: 通过iframe完整保留所有功能
2. **统一用户体验**: 在现有系统中无缝集成
3. **快速部署**: 适合明天演示的时间要求
4. **独立维护**: 两个系统可独立开发维护

## 🔧 后续优化方案

演示成功后，可考虑深度集成：

1. **组件级集成**: 提取核心可视化组件
2. **API统一**: 统一认证和数据管理
3. **样式统一**: 适配现有设计系统
4. **状态同步**: 与现有智能体服务数据同步

---

**总结**: 这个方案能让您在明天的演示中完整展示多智能体协作的核心价值 - 实时可视化监控和流程追踪，同时保证了集成的快速性和稳定性。