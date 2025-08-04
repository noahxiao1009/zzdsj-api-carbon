#!/usr/bin/env python3
"""
测试知识库服务与SSE消息推送服务的集成
验证文档处理过程中的实时进度推送
"""

import asyncio
import aiohttp
import json
import os
import tempfile
from datetime import datetime
from typing import List, Dict

# 测试配置
KNOWLEDGE_SERVICE_URL = "http://localhost:8082"
MESSAGE_PUSH_URL = "http://localhost:8089"
TEST_USER_ID = "test-user-sse-123"
TEST_KB_ID = "test-kb-sse-demo"

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
        
    async def listen_messages(self, timeout: int = 60):
        """监听消息"""
        try:
            start_time = datetime.now()
            async for line in self.response.content:
                line_str = line.decode('utf-8').strip()
                if not line_str:
                    continue
                    
                if line_str.startswith('data: '):
                    data_str = line_str[6:]  # 移除 'data: ' 前缀
                    try:
                        message = json.loads(data_str)
                        self.messages.append(message)
                        
                        # 打印收到的消息
                        msg_type = message.get('type', 'unknown')
                        msg_data = message.get('data', {})
                        
                        if msg_type == 'progress':
                            progress = msg_data.get('progress', 0)
                            stage = msg_data.get('stage', '')
                            text = msg_data.get('message', '')
                            print(f"   📊 进度 {progress}% ({stage}): {text}")
                        elif msg_type == 'status':
                            status = msg_data.get('status', '')
                            text = msg_data.get('message', '')
                            print(f"   📢 状态变更 ({status}): {text}")
                        elif msg_type == 'error':
                            error_msg = msg_data.get('error_message', '')
                            print(f"   ❌ 错误: {error_msg}")
                        elif msg_type == 'success':
                            text = msg_data.get('message', '')
                            result = msg_data.get('result', {})
                            print(f"   ✅ 成功: {text}")
                            if result:
                                print(f"      结果: {result}")
                        else:
                            print(f"   📨 消息 ({msg_type}): {msg_data.get('message', str(msg_data))}")
                            
                    except json.JSONDecodeError:
                        pass
                
                # 检查超时
                if (datetime.now() - start_time).total_seconds() > timeout:
                    print(f"   ⏰ 监听超时 ({timeout}s)")
                    break
                        
        except asyncio.CancelledError:
            print("   🛑 监听被取消")
        except Exception as e:
            print(f"   ❌ 监听出错: {e}")
    
    async def disconnect(self):
        """断开连接"""
        if self.response:
            self.response.close()
        if self.session:
            await self.session.close()


async def test_sse_document_processing():
    """测试SSE文档处理进度推送"""
    print("=" * 80)
    print("测试SSE文档处理进度推送")
    print("=" * 80)
    
    try:
        # 1. 建立SSE连接
        sse_url = f"{MESSAGE_PUSH_URL}/sse/user/{TEST_USER_ID}"
        client = SSETestClient(sse_url)
        await client.connect()
        
        # 2. 启动消息监听
        listen_task = asyncio.create_task(client.listen_messages(timeout=120))
        
        # 3. 等待连接建立
        await asyncio.sleep(1)
        
        # 4. 创建测试知识库
        kb_result = await create_test_knowledge_base()
        if not kb_result:
            print("   ❌ 创建测试知识库失败")
            return False
        
        print(f"   ✅ 测试知识库创建成功: {TEST_KB_ID}")
        
        # 5. 创建测试文档
        test_content = """
        这是一个测试文档，用于验证SSE进度推送功能。
        
        文档内容包含多个段落，用于测试文档分块功能。
        
        第一部分：介绍
        本文档用于测试知识库服务与SSE消息推送服务的集成。
        
        第二部分：功能描述
        系统会在文档处理过程中发送实时进度更新。
        包括文档分块、向量化、存储等各个阶段。
        
        第三部分：预期结果
        用户应该能够实时看到文档处理的进度信息。
        包括百分比进度、当前阶段、详细信息等。
        
        第四部分：测试验证
        验证SSE连接是否正常工作。
        验证进度消息是否按预期发送。
        验证错误处理是否正确。
        
        第五部分：总结
        通过这个测试确保SSE进度推送功能正常运行。
        为用户提供良好的实时反馈体验。
        """
        
        # 6. 上传文档并监听进度
        print("   📤 开始上传测试文档...")
        upload_result = await upload_test_document(test_content)
        
        if upload_result:
            print("   ✅ 文档上传成功，正在处理...")
            
            # 7. 等待处理完成（最多120秒）
            await asyncio.sleep(60)  # 等待处理完成
            
        else:
            print("   ❌ 文档上传失败")
            return False
        
        # 8. 停止监听
        listen_task.cancel()
        
        # 9. 分析收到的消息
        progress_messages = [msg for msg in client.messages if msg.get('type') == 'progress']
        status_messages = [msg for msg in client.messages if msg.get('type') == 'status']
        success_messages = [msg for msg in client.messages if msg.get('type') == 'success']
        error_messages = [msg for msg in client.messages if msg.get('type') == 'error']
        
        print(f"\n   📊 收到进度消息: {len(progress_messages)} 条")
        print(f"   📢 收到状态消息: {len(status_messages)} 条")
        print(f"   ✅ 收到成功消息: {len(success_messages)} 条")
        print(f"   ❌ 收到错误消息: {len(error_messages)} 条")
        
        # 10. 验证进度消息的完整性
        if progress_messages:
            progresses = [msg.get('data', {}).get('progress', 0) for msg in progress_messages]
            stages = [msg.get('data', {}).get('stage', '') for msg in progress_messages]
            
            print(f"   📈 进度范围: {min(progresses)}% - {max(progresses)}%")
            print(f"   🔄 处理阶段: {list(set(stages))}")
            
            # 检查是否有完整的进度流程
            has_extract = any(stage == 'extract' for stage in stages)
            has_chunk = any(stage == 'chunk' for stage in stages)
            has_embed = any(stage == 'embed' for stage in stages)
            
            print(f"   ✅ 文档提取阶段: {'是' if has_extract else '否'}")
            print(f"   ✅ 文档分块阶段: {'是' if has_chunk else '否'}")
            print(f"   ✅ 向量嵌入阶段: {'是' if has_embed else '否'}")
        
        await client.disconnect()
        
        # 判断测试是否成功
        success = (
            len(progress_messages) >= 3 and  # 至少3条进度消息
            len(success_messages) >= 1 and   # 至少1条成功消息
            len(error_messages) == 0         # 没有错误消息
        )
        
        return success
        
    except Exception as e:
        print(f"   ❌ 测试异常: {e}")
        return False


async def create_test_knowledge_base():
    """创建测试知识库"""
    try:
        kb_data = {
            "name": "SSE测试知识库",
            "description": "用于测试SSE进度推送功能的知识库",
            "settings": {
                "chunk_size": 500,
                "chunk_overlap": 50,
                "chunk_strategy": "token_based"
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{KNOWLEDGE_SERVICE_URL}/api/v1/knowledge-bases/",
                json=kb_data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get('success', False)
                else:
                    # 如果知识库已存在，也算成功
                    return response.status == 409
                    
    except Exception as e:
        print(f"   ❌ 创建知识库异常: {e}")
        return False


async def upload_test_document(content: str):
    """上传测试文档"""
    try:
        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        try:
            # 准备上传数据
            with open(temp_file_path, 'rb') as file:
                form_data = aiohttp.FormData()
                form_data.add_field('files', file, filename='test_document.txt', content_type='text/plain')
                form_data.add_field('user_id', TEST_USER_ID)
                form_data.add_field('enable_async_processing', 'true')
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{KNOWLEDGE_SERVICE_URL}/api/v1/knowledge-bases/{TEST_KB_ID}/documents/upload-async",
                        data=form_data
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            return result.get('success', False)
                        else:
                            error_text = await response.text()
                            print(f"   ❌ 上传失败 ({response.status}): {error_text}")
                            return False
        finally:
            # 清理临时文件
            os.unlink(temp_file_path)
            
    except Exception as e:
        print(f"   ❌ 上传文档异常: {e}")
        return False


async def main():
    """主测试函数"""
    print("开始SSE进度推送集成测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"知识库服务: {KNOWLEDGE_SERVICE_URL}")
    print(f"消息推送服务: {MESSAGE_PUSH_URL}")
    print(f"测试用户: {TEST_USER_ID}")
    print(f"测试知识库: {TEST_KB_ID}")
    
    try:
        # 测试SSE文档处理进度推送
        success = await test_sse_document_processing()
        
        print("\n" + "=" * 80)
        print("SSE进度推送集成测试结果")
        print("=" * 80)
        
        if success:
            print("🎉 测试通过！SSE进度推送功能正常")
            return 0
        else:
            print("❌ 测试失败！请检查服务配置和连接")
            return 1
            
    except KeyboardInterrupt:
        print("\n测试被用户中断")
        return 1
    except Exception as e:
        print(f"\n测试执行异常: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)