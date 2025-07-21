#!/usr/bin/env python3
"""
Agno桥接层集成测试脚本
验证Kaiban工作流与Agno智能体框架的集成功能
"""

import asyncio
import sys
import os
import json
from typing import Dict, Any
from datetime import datetime

# 添加app路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.services.agno_bridge import agno_bridge

class TestWorkflow:
    """测试用的工作流类"""
    def __init__(self):
        self.id = "test-workflow-001"
        self.name = "测试智能客服工作流"
        self.description = "这是一个测试用的智能客服工作流，用于验证Agno桥接层功能"
        self.version = "1.0.0"
        self.status = "active"
        self.trigger_type = "manual"
        self.config = {
            "model_config": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "temperature": 0.7,
                "max_tokens": 1000
            },
            "tools": ["web_search", "knowledge_base"],
            "knowledge_base_ids": ["kb_001", "kb_002"],
            "auto_execution": True,
            "max_parallel_tasks": 3
        }

class TestTask:
    """测试用的任务类"""
    def __init__(self, task_id: str, title: str, description: str):
        self.id = task_id
        self.title = title
        self.description = description
        self.status = "pending"
        self.priority = "high"
        self.assignee = "AI智能体"
        self.due_date = None
        self.tags = ["测试", "集成"]
        self.meta_data = {"source": "integration_test"}

async def test_agno_bridge_health():
    """测试1: Agno桥接层健康状态"""
    print("🔍 测试1: 检查Agno桥接层健康状态")
    try:
        is_healthy = await agno_bridge.test_agent_connection()
        print(f"✅ 桥接层连接状态: {'健康' if is_healthy else '异常'}")
        print(f"📡 Agent服务地址: {agno_bridge.agent_service_url}")
        return is_healthy
    except Exception as e:
        print(f"❌ 健康检查失败: {str(e)}")
        return False

async def test_create_agent_from_workflow():
    """测试2: 从工作流创建智能体"""
    print("\n🔍 测试2: 从工作流创建智能体")
    try:
        test_workflow = TestWorkflow()
        user_id = "test_user_001"
        
        print(f"📋 工作流信息:")
        print(f"   - ID: {test_workflow.id}")
        print(f"   - 名称: {test_workflow.name}")
        print(f"   - 描述: {test_workflow.description}")
        
        # 创建智能体
        agent = await agno_bridge.create_agent_from_workflow(test_workflow, user_id)
        
        print(f"✅ 智能体创建成功:")
        print(f"   - Agent ID: {agent.get('agent_id', 'N/A')}")
        print(f"   - 响应数据: {json.dumps(agent, ensure_ascii=False, indent=2)}")
        
        return agent.get('agent_id')
        
    except Exception as e:
        print(f"❌ 创建智能体失败: {str(e)}")
        return None

async def test_workflow_execution(agent_id: str):
    """测试3: 智能体执行工作流"""
    print("\n🔍 测试3: 智能体执行工作流")
    try:
        if not agent_id:
            print("⚠️  跳过测试：没有可用的智能体ID")
            return None
            
        workflow_id = "test-workflow-001"
        user_id = "test_user_001"
        
        # 创建测试任务
        tasks = [
            TestTask("task_001", "理解客户问题", "分析客户提出的问题和需求"),
            TestTask("task_002", "查找解决方案", "在知识库中搜索相关解决方案"),
            TestTask("task_003", "生成回复", "基于找到的解决方案生成专业回复")
        ]
        
        print(f"🚀 执行参数:")
        print(f"   - Agent ID: {agent_id}")
        print(f"   - Workflow ID: {workflow_id}")
        print(f"   - 任务数量: {len(tasks)}")
        
        # 执行工作流
        result = await agno_bridge.execute_workflow_with_agent(
            agent_id=agent_id,
            workflow_id=workflow_id,
            tasks=tasks,
            user_id=user_id
        )
        
        print(f"✅ 工作流执行启动成功:")
        print(f"   - 执行ID: {result.get('execution_id', 'N/A')}")
        print(f"   - 状态: {result.get('status', 'N/A')}")
        print(f"   - 响应数据: {json.dumps(result, ensure_ascii=False, indent=2)}")
        
        return result
        
    except Exception as e:
        print(f"❌ 工作流执行失败: {str(e)}")
        return None

async def main():
    """主测试函数"""
    print("🚀 Agno桥接层集成测试开始")
    print("=" * 60)
    
    # 测试结果记录
    results = {}
    agent_id = None
    
    try:
        # 测试1: 健康检查
        results['health_check'] = await test_agno_bridge_health()
        
        # 测试2: 创建智能体
        agent_id = await test_create_agent_from_workflow()
        results['create_agent'] = bool(agent_id)
        
        # 测试3: 执行工作流
        execution_result = await test_workflow_execution(agent_id)
        results['workflow_execution'] = bool(execution_result)
        
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {str(e)}")
        results['error'] = str(e)
    
    # 输出测试报告
    print("\n" + "=" * 60)
    print("📊 测试报告")
    print("=" * 60)
    
    total_tests = len([k for k in results.keys() if k != 'error'])
    passed_tests = len([k for k, v in results.items() if k != 'error' and v])
    
    for test_name, result in results.items():
        if test_name == 'error':
            continue
        status = "✅ 通过" if result else "❌ 失败"
        print(f"   {test_name}: {status}")
    
    if 'error' in results:
        print(f"\n⚠️  错误信息: {results['error']}")
    
    print(f"\n📈 总体结果: {passed_tests}/{total_tests} 测试通过")
    
    if passed_tests == total_tests:
        print("🎉 所有测试通过！Agno桥接层集成正常工作。")
    elif passed_tests > 0:
        print("⚠️  部分测试通过，请检查失败的测试项。")
    else:
        print("💥 所有测试失败，请检查Agno服务连接和配置。")
    
    print(f"\n🕐 测试完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
    except Exception as e:
        print(f"\n�� 测试脚本异常: {str(e)}") 