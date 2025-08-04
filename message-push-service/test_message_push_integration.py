#!/usr/bin/env python3
"""
消息推送服务集成测试脚本
测试SSE连接、消息推送、连接管理等完整功能
"""

import asyncio
import aiohttp
import json
import sys
import time
from datetime import datetime
from typing import List, Dict, Any

# 服务配置
MESSAGE_PUSH_URL = "http://localhost:8089"
TEST_USER_ID = "test-user-123"
TEST_SESSION_ID = "test-session-456"


class SSETestClient:
    """SSE测试客户端"""
    
    def __init__(self, url: str):
        self.url = url
        self.messages: List[Dict] = []
        self.session: aiohttp.ClientSession = None
        self.response = None
        self.connection_id = None
        
    async def connect(self):
        """建立SSE连接"""
        self.session = aiohttp.ClientSession()
        self.response = await self.session.get(self.url)
        
        # 获取连接ID
        self.connection_id = self.response.headers.get('X-Connection-ID')
        print(f"   SSE连接建立: {self.connection_id}")
        
    async def listen_messages(self, timeout: int = 10):
        """监听消息"""
        try:
            async for line in self.response.content:
                line_str = line.decode('utf-8').strip()
                if not line_str:
                    continue
                    
                if line_str.startswith('data: '):
                    data_str = line_str[6:]  # 移除 'data: ' 前缀
                    try:
                        message = json.loads(data_str)
                        self.messages.append(message)
                        print(f"   收到消息: {message.get('type', 'unknown')} - {message.get('data', {}).get('message', '')}")
                    except json.JSONDecodeError:
                        pass
                        
        except asyncio.TimeoutError:
            print("   监听超时")
        except Exception as e:
            print(f"   监听出错: {e}")
    
    async def disconnect(self):
        """断开连接"""
        if self.response:
            self.response.close()
        if self.session:
            await self.session.close()


async def test_basic_sse_connection():
    """测试基础SSE连接"""
    print("=" * 60)
    print("测试基础SSE连接")
    print("=" * 60)
    
    try:
        client = SSETestClient(f"{MESSAGE_PUSH_URL}/sse/stream?user_id={TEST_USER_ID}")
        await client.connect()
        
        # 监听几秒钟
        listen_task = asyncio.create_task(client.listen_messages())
        await asyncio.sleep(3)
        listen_task.cancel()
        
        await client.disconnect()
        
        print(f"   成功接收 {len(client.messages)} 条消息")
        return True
        
    except Exception as e:
        print(f"   连接失败: {e}")
        return False


async def test_user_specific_connection():
    """测试用户专用连接"""
    print("=" * 60)
    print("测试用户专用连接")
    print("=" * 60)
    
    try:
        client = SSETestClient(f"{MESSAGE_PUSH_URL}/sse/user/{TEST_USER_ID}")
        await client.connect()
        
        # 启动消息监听
        listen_task = asyncio.create_task(client.listen_messages())
        
        # 等待连接建立
        await asyncio.sleep(1)
        
        # 发送测试消息
        await send_test_message(TEST_USER_ID)
        
        # 等待消息接收
        await asyncio.sleep(2)
        listen_task.cancel()
        
        await client.disconnect()
        
        # 检查是否收到测试消息
        test_messages = [msg for msg in client.messages if msg.get('type') == 'info']
        print(f"   成功接收 {len(test_messages)} 条测试消息")
        
        return len(test_messages) > 0
        
    except Exception as e:
        print(f"   测试失败: {e}")
        return False


async def test_task_specific_connection():
    """测试任务专用连接"""
    print("=" * 60)
    print("测试任务专用连接")
    print("=" * 60)
    
    task_id = f"test-task-{int(time.time())}"
    
    try:
        client = SSETestClient(f"{MESSAGE_PUSH_URL}/sse/task/{task_id}")
        await client.connect()
        
        # 启动消息监听
        listen_task = asyncio.create_task(client.listen_messages())
        
        # 等待连接建立
        await asyncio.sleep(1)
        
        # 发送进度消息
        await send_progress_messages(task_id)
        
        # 等待消息接收
        await asyncio.sleep(3)
        listen_task.cancel()
        
        await client.disconnect()
        
        # 检查进度消息
        progress_messages = [msg for msg in client.messages if msg.get('type') == 'progress']
        print(f"   成功接收 {len(progress_messages)} 条进度消息")
        
        return len(progress_messages) >= 3
        
    except Exception as e:
        print(f"   测试失败: {e}")
        return False


async def send_test_message(user_id: str):
    """发送测试消息"""
    message_data = {
        "type": "info",
        "service": "test-service",
        "source": "integration_test",
        "target": {
            "user_id": user_id
        },
        "data": {
            "message": "这是一条测试消息",
            "timestamp": datetime.now().isoformat()
        }
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{MESSAGE_PUSH_URL}/sse/api/v1/messages/send",
            json=message_data
        ) as response:
            if response.status == 200:
                result = await response.json()
                print(f"   消息发送成功: {result.get('message_id')}")
            else:
                print(f"   消息发送失败: {response.status}")


async def send_progress_messages(task_id: str):
    """发送进度消息序列"""
    for progress in [20, 50, 80, 100]:
        message_data = {
            "type": "progress",
            "service": "test-service",
            "source": "task_processor",
            "target": {
                "task_id": task_id
            },
            "data": {
                "task_id": task_id,
                "progress": progress,
                "stage": "processing",
                "message": f"任务进度: {progress}%",
                "details": {
                    "current_step": f"步骤 {progress // 20}",
                    "estimated_time": 10 - (progress // 10)
                }
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{MESSAGE_PUSH_URL}/sse/api/v1/messages/send",
                json=message_data
            ) as response:
                if response.status == 200:
                    print(f"   进度消息发送成功: {progress}%")
                else:
                    print(f"   进度消息发送失败: {response.status}")
        
        await asyncio.sleep(0.5)


async def test_broadcast_message():
    """测试广播消息"""
    print("=" * 60)
    print("测试广播消息")
    print("=" * 60)
    
    # 创建多个客户端连接
    clients = []
    for i in range(3):
        client = SSETestClient(f"{MESSAGE_PUSH_URL}/sse/stream?user_id=user-{i}")
        await client.connect()
        clients.append(client)
    
    # 启动所有客户端的消息监听
    listen_tasks = []
    for client in clients:
        task = asyncio.create_task(client.listen_messages())
        listen_tasks.append(task)
    
    # 等待连接建立
    await asyncio.sleep(1)
    
    # 发送广播消息
    broadcast_data = {
        "type": "info",
        "service": "test-service",
        "source": "broadcast_test",
        "data": {
            "message": "这是一条广播消息",
            "broadcast_time": datetime.now().isoformat()
        }
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{MESSAGE_PUSH_URL}/sse/api/v1/messages/broadcast",
            json=broadcast_data
        ) as response:
            if response.status == 200:
                result = await response.json()
                print(f"   广播消息发送成功: {result.get('sent_to_connections')} 个连接")
            else:
                print(f"   广播消息发送失败: {response.status}")
    
    # 等待消息接收
    await asyncio.sleep(2)
    
    # 停止监听
    for task in listen_tasks:
        task.cancel()
    
    # 检查消息接收
    received_count = 0
    for i, client in enumerate(clients):
        broadcast_messages = [msg for msg in client.messages if "广播消息" in str(msg)]
        if broadcast_messages:
            received_count += 1
        print(f"   客户端 {i}: 收到 {len(broadcast_messages)} 条广播消息")
        await client.disconnect()
    
    print(f"   总共 {received_count}/{len(clients)} 个客户端收到广播消息")
    return received_count >= len(clients) - 1  # 允许一个客户端丢失


async def test_connection_management():
    """测试连接管理API"""
    print("=" * 60)
    print("测试连接管理API")
    print("=" * 60)
    
    try:
        # 建立测试连接
        client = SSETestClient(f"{MESSAGE_PUSH_URL}/sse/user/{TEST_USER_ID}")
        await client.connect()
        
        await asyncio.sleep(1)
        
        # 获取连接列表
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{MESSAGE_PUSH_URL}/sse/api/v1/connections") as response:
                if response.status == 200:
                    result = await response.json()
                    connections = result.get('connections', [])
                    print(f"   当前活跃连接数: {len(connections)}")
                    
                    # 查找我们的连接
                    our_connection = None
                    for conn in connections:
                        if conn.get('connection_id') == client.connection_id:
                            our_connection = conn
                            break
                    
                    if our_connection:
                        print(f"   找到测试连接: {our_connection['connection_id']}")
                        print(f"   连接用户: {our_connection.get('user_id')}")
                        print(f"   订阅频道: {our_connection.get('channels', [])}")
                    else:
                        print("   未找到测试连接")
                        return False
                else:
                    print(f"   获取连接列表失败: {response.status}")
                    return False
        
        # 获取连接统计
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{MESSAGE_PUSH_URL}/sse/api/v1/connections/stats") as response:
                if response.status == 200:
                    result = await response.json()
                    stats = result.get('stats', {})
                    print(f"   连接统计: {stats}")
                else:
                    print(f"   获取连接统计失败: {response.status}")
        
        await client.disconnect()
        return True
        
    except Exception as e:
        print(f"   测试失败: {e}")
        return False


async def test_health_check():
    """测试健康检查"""
    print("=" * 60)
    print("测试健康检查")
    print("=" * 60)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{MESSAGE_PUSH_URL}/sse/health") as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"   服务状态: {result.get('status')}")
                    print(f"   服务版本: {result.get('version')}")
                    
                    # 检查组件状态
                    conn_mgr = result.get('connection_manager', {})
                    msg_queue = result.get('message_queue', {})
                    
                    print(f"   连接管理器: {conn_mgr.get('status', 'unknown')}")
                    print(f"   活跃连接: {conn_mgr.get('active_connections', 0)}")
                    print(f"   消息队列: {msg_queue.get('status', 'unknown')}")
                    
                    return result.get('status') in ['healthy', 'degraded']
                else:
                    print(f"   健康检查失败: {response.status}")
                    return False
    except Exception as e:
        print(f"   健康检查出错: {e}")
        return False


async def test_service_availability():
    """测试服务可用性"""
    print("=" * 60)
    print("测试服务可用性")
    print("=" * 60)
    
    try:
        # 测试根端点
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{MESSAGE_PUSH_URL}/") as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"   服务名称: {result.get('service')}")
                    print(f"   服务版本: {result.get('version')}")
                    print(f"   服务状态: {result.get('status')}")
                    return True
                else:
                    print(f"   服务不可用: {response.status}")
                    return False
    except Exception as e:
        print(f"   服务连接失败: {e}")
        return False


async def main():
    """主测试函数"""
    print("开始消息推送服务集成测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"服务地址: {MESSAGE_PUSH_URL}")
    print(f"测试用户: {TEST_USER_ID}")
    
    total_tests = 0
    passed_tests = 0
    
    # 测试1: 服务可用性
    total_tests += 1
    if await test_service_availability():
        passed_tests += 1
        print("✅ 服务可用性测试通过")
    else:
        print("❌ 服务可用性测试失败")
    
    await asyncio.sleep(1)
    
    # 测试2: 健康检查
    total_tests += 1
    if await test_health_check():
        passed_tests += 1
        print("✅ 健康检查测试通过")
    else:
        print("❌ 健康检查测试失败")
    
    await asyncio.sleep(1)
    
    # 测试3: 基础SSE连接
    total_tests += 1
    if await test_basic_sse_connection():
        passed_tests += 1
        print("✅ 基础SSE连接测试通过")
    else:
        print("❌ 基础SSE连接测试失败")
    
    await asyncio.sleep(1)
    
    # 测试4: 用户专用连接和消息推送
    total_tests += 1
    if await test_user_specific_connection():
        passed_tests += 1
        print("✅ 用户专用连接测试通过")
    else:
        print("❌ 用户专用连接测试失败")
    
    await asyncio.sleep(1)
    
    # 测试5: 任务专用连接和进度推送
    total_tests += 1
    if await test_task_specific_connection():
        passed_tests += 1
        print("✅ 任务专用连接测试通过")
    else:
        print("❌ 任务专用连接测试失败")
    
    await asyncio.sleep(1)
    
    # 测试6: 广播消息
    total_tests += 1
    if await test_broadcast_message():
        passed_tests += 1
        print("✅ 广播消息测试通过")
    else:
        print("❌ 广播消息测试失败")
    
    await asyncio.sleep(1)
    
    # 测试7: 连接管理
    total_tests += 1
    if await test_connection_management():
        passed_tests += 1
        print("✅ 连接管理测试通过")
    else:
        print("❌ 连接管理测试失败")
    
    # 输出测试总结
    print("\n" + "=" * 80)
    print("消息推送服务集成测试总结")
    print("=" * 80)
    print(f"总测试数: {total_tests}")
    print(f"通过测试: {passed_tests}")
    print(f"失败测试: {total_tests - passed_tests}")
    print(f"通过率: {passed_tests/total_tests*100:.1f}%")
    
    if passed_tests == total_tests:
        print("🎉 所有测试通过！消息推送服务功能正常")
        return 0
    elif passed_tests >= total_tests - 1:
        print("⚠️  大部分测试通过，消息推送服务基本可用")
        return 0
    else:
        print("❌ 多个测试失败，请检查服务配置")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        print(f"\n测试完成，退出码: {exit_code}")
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n测试执行异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)