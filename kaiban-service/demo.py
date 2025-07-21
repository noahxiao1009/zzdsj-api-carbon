#!/usr/bin/env python3
"""
Kaiban Service 功能演示脚本
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, Any

BASE_URL = "http://localhost:8003"

def print_header(title: str):
    """打印标题"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def print_section(title: str):
    """打印章节"""
    print(f"\n🔹 {title}")
    print("-" * 40)

def make_request(method: str, endpoint: str, data: Dict[Any, Any] = None) -> Dict[Any, Any]:
    """发起HTTP请求"""
    url = f"{BASE_URL}{endpoint}"
    try:
        if method.upper() == "GET":
            response = requests.get(url)
        elif method.upper() == "POST":
            response = requests.post(url, json=data)
        elif method.upper() == "PUT":
            response = requests.put(url, json=data)
        elif method.upper() == "DELETE":
            response = requests.delete(url)
        
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return {}

def demo_service_info():
    """演示服务信息"""
    print_section("服务基础信息")
    
    # 服务信息
    info = make_request("GET", "/info")
    if info:
        print(f"✅ 服务名称: {info.get('name', 'N/A')}")
        print(f"✅ 版本: {info.get('version', 'N/A')}")
        print(f"✅ 状态: {info.get('status', 'N/A')}")
        print(f"✅ 启动时间: {info.get('start_time', 'N/A')}")
    
    # 健康检查
    health = make_request("GET", "/health")
    if health:
        print(f"✅ 健康状态: {health.get('status', 'N/A')}")

def demo_workflows():
    """演示工作流功能"""
    print_section("工作流管理演示")
    
    # 1. 创建工作流
    workflow_data = {
        "name": "AI文章生成工作流",
        "description": "自动化生成高质量文章的工作流程",
        "version": "1.0.0",
        "trigger_type": "manual",
        "config": {
            "steps": [
                {"name": "内容规划", "type": "planning"},
                {"name": "AI生成", "type": "generation"}, 
                {"name": "质量检查", "type": "review"},
                {"name": "发布", "type": "publish"}
            ]
        }
    }
    
    print("📝 创建工作流...")
    workflow = make_request("POST", "/api/v1/workflows", workflow_data)
    if workflow:
        workflow_id = workflow.get("id")
        print(f"✅ 工作流已创建，ID: {workflow_id}")
        
        # 2. 获取工作流列表
        print("\n📋 获取工作流列表...")
        workflows = make_request("GET", "/api/v1/workflows")
        if workflows:
            print(f"✅ 找到 {len(workflows)} 个工作流")
            for wf in workflows[:3]:  # 只显示前3个
                print(f"   - {wf.get('name')} (ID: {wf.get('id')})")
        
        # 3. 获取特定工作流
        print(f"\n🔍 获取工作流详情 (ID: {workflow_id})...")
        detail = make_request("GET", f"/api/v1/workflows/{workflow_id}")
        if detail:
            print(f"✅ 工作流名称: {detail.get('name')}")
            print(f"✅ 描述: {detail.get('description')}")
            print(f"✅ 状态: {detail.get('status')}")
        
        return workflow_id
    
    return None

def demo_boards(workflow_id: str = None):
    """演示看板功能"""
    print_section("看板管理演示")
    
    # 1. 创建看板
    board_data = {
        "name": "产品开发看板",
        "description": "跟踪产品开发进度的看板",
        "workflow_id": workflow_id
    }
    
    print("📝 创建看板...")
    board = make_request("POST", "/api/v1/boards", board_data)
    if board:
        board_id = board.get("id")
        print(f"✅ 看板已创建，ID: {board_id}")
        
        # 2. 获取看板列表
        print("\n📋 获取看板列表...")
        boards = make_request("GET", "/api/v1/boards")
        if boards:
            print(f"✅ 找到 {len(boards)} 个看板")
            for b in boards[:3]:
                print(f"   - {b.get('name')} (ID: {b.get('id')})")
        
        return board_id
    
    return None

def demo_tasks(board_id: str = None):
    """演示任务功能"""
    print_section("任务管理演示")
    
    # 1. 创建任务
    task_data = {
        "title": "设计用户界面",
        "description": "设计新功能的用户界面原型",
        "status": "todo",
        "priority": "high",
        "board_id": board_id,
        "assignee": "张三",
        "tags": ["UI", "设计", "优先级高"],
        "due_date": "2025-07-15T10:00:00",
        "meta_data": {
            "estimated_hours": 16,
            "difficulty": "medium"
        }
    }
    
    print("📝 创建任务...")
    task = make_request("POST", "/api/v1/tasks", task_data)
    if task:
        task_id = task.get("id")
        print(f"✅ 任务已创建，ID: {task_id}")
        
        # 2. 创建更多示例任务
        additional_tasks = [
            {
                "title": "后端API开发", 
                "description": "实现核心业务逻辑API",
                "status": "in_progress",
                "priority": "high",
                "board_id": board_id,
                "assignee": "李四",
                "tags": ["后端", "API"]
            },
            {
                "title": "数据库优化",
                "description": "优化查询性能",
                "status": "done", 
                "priority": "medium",
                "board_id": board_id,
                "assignee": "王五",
                "tags": ["数据库", "优化"]
            }
        ]
        
        for task_info in additional_tasks:
            make_request("POST", "/api/v1/tasks", task_info)
        
        # 3. 获取任务列表
        print("\n📋 获取任务列表...")
        tasks = make_request("GET", "/api/v1/tasks")
        if tasks:
            print(f"✅ 找到 {len(tasks)} 个任务")
            status_count = {}
            for t in tasks:
                status = t.get('status', 'unknown')
                status_count[status] = status_count.get(status, 0) + 1
            
            print("📊 任务状态统计:")
            for status, count in status_count.items():
                print(f"   - {status}: {count} 个")
        
        return task_id
    
    return None

def demo_events():
    """演示事件系统"""
    print_section("事件系统演示")
    
    # 1. 创建事件订阅
    subscription_data = {
        "event_type": "task.status_changed",
        "callback_url": "http://localhost:8003/api/v1/events/webhook",
        "filters": {
            "priority": "high"
        }
    }
    
    print("📝 创建事件订阅...")
    subscription = make_request("POST", "/api/v1/events/subscribe", subscription_data)
    if subscription:
        print(f"✅ 订阅已创建，ID: {subscription.get('id')}")
    
    # 2. 发布事件
    event_data = {
        "event_type": "task.status_changed",
        "data": {
            "task_id": "123e4567-e89b-12d3-a456-426614174000",
            "old_status": "todo",
            "new_status": "in_progress",
            "priority": "high",
            "assignee": "张三"
        },
        "meta_data": {
            "source": "demo",
            "timestamp": datetime.now().isoformat()
        }
    }
    
    print("\n📤 发布事件...")
    result = make_request("POST", "/api/v1/events/publish", event_data)
    if result:
        print(f"✅ 事件已发布: {result.get('message', 'N/A')}")
    
    # 3. 获取事件列表
    print("\n📋 获取事件列表...")
    events = make_request("GET", "/api/v1/events")
    if events:
        print(f"✅ 找到 {len(events)} 个事件")
        for event in events[:3]:
            print(f"   - {event.get('event_type')} ({event.get('timestamp', 'N/A')})")

def demo_frontend():
    """演示前端界面"""
    print_section("前端界面演示")
    
    print("🌐 前端看板界面已启动")
    print(f"📋 访问地址: {BASE_URL}/frontend/board")
    print("✨ 功能特性:")
    print("   - 拖拽式任务管理")
    print("   - 实时状态更新")
    print("   - 响应式设计")
    print("   - 任务筛选和搜索")

def main():
    """主演示函数"""
    print_header("Kaiban Service 功能演示")
    print(f"🚀 连接服务: {BASE_URL}")
    print(f"⏰ 演示时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # 1. 服务基础信息
        demo_service_info()
        
        # 2. 工作流演示
        workflow_id = demo_workflows()
        
        # 3. 看板演示
        board_id = demo_boards(workflow_id)
        
        # 4. 任务演示
        task_id = demo_tasks(board_id)
        
        # 5. 事件系统演示
        demo_events()
        
        # 6. 前端界面演示
        demo_frontend()
        
        print_header("演示完成")
        print("🎉 所有功能演示已完成！")
        print(f"📖 详细API文档: {BASE_URL}/docs")
        print(f"📋 看板界面: {BASE_URL}/frontend/board")
        
    except KeyboardInterrupt:
        print("\n\n⚠️ 演示已中断")
    except Exception as e:
        print(f"\n\n❌ 演示出错: {e}")

if __name__ == "__main__":
    main() 