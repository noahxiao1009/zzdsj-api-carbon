#!/usr/bin/env python3
"""
简单的SSE功能验证测试
直接测试SSE客户端发送进度消息
"""

import asyncio
import aiohttp
import json
import sys
from datetime import datetime

# 测试配置
MESSAGE_PUSH_URL = "http://localhost:8089"
TEST_USER_ID = "test-user-simple"
TEST_TASK_ID = "test-task-123"

async def test_sse_connection_and_messages():
    """测试SSE连接和消息发送"""
    print("🔗 建立SSE连接...")
    
    # 建立SSE连接
    sse_url = f"{MESSAGE_PUSH_URL}/sse/user/{TEST_USER_ID}"
    session = aiohttp.ClientSession()
    
    try:
        response = await session.get(sse_url)
        connection_id = response.headers.get('X-Connection-ID')
        print(f"✅ SSE连接成功: {connection_id}")
        
        # 启动消息监听
        messages = []
        
        async def listen_messages():
            try:
                async for line in response.content:
                    line_str = line.decode('utf-8').strip()
                    if line_str.startswith('data: '):
                        data_str = line_str[6:]
                        try:
                            message = json.loads(data_str)
                            messages.append(message)
                            
                            msg_type = message.get('type', 'unknown')
                            msg_data = message.get('data', {})
                            
                            if msg_type == 'progress':
                                progress = msg_data.get('progress', 0)
                                stage = msg_data.get('stage', '')
                                text = msg_data.get('message', '')
                                print(f"📊 进度 {progress}% ({stage}): {text}")
                            elif msg_type == 'success':
                                text = msg_data.get('message', '')
                                print(f"✅ 成功: {text}")
                            elif msg_type == 'error':
                                error_msg = msg_data.get('error_message', '')
                                print(f"❌ 错误: {error_msg}")
                            else:
                                print(f"📨 消息 ({msg_type}): {msg_data.get('message', str(msg_data))}")
                                
                        except json.JSONDecodeError:
                            pass
            except asyncio.CancelledError:
                print("🛑 监听停止")
        
        # 启动监听任务
        listen_task = asyncio.create_task(listen_messages())
        
        # 等待连接稳定
        await asyncio.sleep(1)
        
        # 发送测试消息
        print("\n📤 发送测试进度消息...")
        await send_test_progress_messages()
        
        # 等待消息接收
        await asyncio.sleep(3)
        
        # 停止监听
        listen_task.cancel()
        
        print(f"\n📊 总共收到 {len(messages)} 条消息")
        
        # 验证消息
        progress_msgs = [m for m in messages if m.get('type') == 'progress']
        success_msgs = [m for m in messages if m.get('type') == 'success']
        
        print(f"📈 进度消息: {len(progress_msgs)} 条")
        print(f"✅ 成功消息: {len(success_msgs)} 条")
        
        return len(progress_msgs) >= 3 and len(success_msgs) >= 1
        
    finally:
        response.close()
        await session.close()


async def send_test_progress_messages():
    """发送测试进度消息"""
    test_messages = [
        {
            "type": "progress",
            "service": "knowledge-service",
            "source": "test_integration",
            "target": {"user_id": TEST_USER_ID, "task_id": TEST_TASK_ID},
            "data": {
                "task_id": TEST_TASK_ID,
                "progress": 20,
                "stage": "extract",
                "message": "开始文档提取",
                "details": {"step": "初始化"}
            }
        },
        {
            "type": "progress",
            "service": "knowledge-service", 
            "source": "test_integration",
            "target": {"user_id": TEST_USER_ID, "task_id": TEST_TASK_ID},
            "data": {
                "task_id": TEST_TASK_ID,
                "progress": 50,
                "stage": "chunk",
                "message": "文档分块处理中",
                "details": {"chunks": 10}
            }
        },
        {
            "type": "progress",
            "service": "knowledge-service",
            "source": "test_integration", 
            "target": {"user_id": TEST_USER_ID, "task_id": TEST_TASK_ID},
            "data": {
                "task_id": TEST_TASK_ID,
                "progress": 80,
                "stage": "embed",
                "message": "生成向量嵌入",
                "details": {"embeddings": 10}
            }
        },
        {
            "type": "success",
            "service": "knowledge-service",
            "source": "test_integration",
            "target": {"user_id": TEST_USER_ID, "task_id": TEST_TASK_ID},
            "data": {
                "task_id": TEST_TASK_ID,
                "message": "文档处理完成",
                "result": {"chunks": 10, "status": "completed"}
            }
        }
    ]
    
    async with aiohttp.ClientSession() as session:
        for i, message_data in enumerate(test_messages):
            try:
                async with session.post(
                    f"{MESSAGE_PUSH_URL}/sse/api/v1/messages/send",
                    json=message_data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        print(f"  ✅ 消息 {i+1} 发送成功: {result.get('message_id', '')}")
                    else:
                        print(f"  ❌ 消息 {i+1} 发送失败: {response.status}")
                        
                # 间隔发送
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"  ❌ 消息 {i+1} 发送异常: {e}")


async def main():
    """主函数"""
    print("=" * 60)
    print("SSE功能简单验证测试")
    print("=" * 60)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"消息推送服务: {MESSAGE_PUSH_URL}")
    print(f"测试用户: {TEST_USER_ID}")
    print(f"测试任务: {TEST_TASK_ID}")
    
    try:
        # 测试SSE功能
        success = await test_sse_connection_and_messages()
        
        print("\n" + "=" * 60)
        print("测试结果")
        print("=" * 60)
        
        if success:
            print("🎉 SSE功能测试通过！")
            print("✅ SSE连接正常")
            print("✅ 消息发送正常")
            print("✅ 进度推送功能可用")
            return 0
        else:
            print("❌ SSE功能测试失败！")
            return 1
            
    except KeyboardInterrupt:
        print("\n测试被中断")
        return 1
    except Exception as e:
        print(f"\n测试异常: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)