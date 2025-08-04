#!/usr/bin/env python3
"""
测试修复后的文件上传和切分策略处理
"""

import requests
import json
import time

# 配置
KNOWLEDGE_SERVICE_URL = "http://localhost:8082"
TASK_MANAGER_URL = "http://localhost:8084"
TEST_KB_ID = "2337adac-4659-4802-aeec-4143f38a354e"  # SSE测试知识库

def test_upload_with_strategy():
    """测试带策略的文件上传"""
    
    print("=== 测试修复后的文件上传和切分策略处理 ===")
    
    # 1. 创建测试文件
    test_content = """
# 测试文档

这是一个测试文档，用于验证切分策略的处理。

## 第一部分
这是第一部分的内容，包含一些基本的文本信息。

## 第二部分  
这是第二部分的内容，包含更多的详细信息。

## 第三部分
这是第三部分的内容，用于测试文档的完整性。
"""
    
    # 保存测试文件
    with open("test_document.md", "w", encoding="utf-8") as f:
        f.write(test_content)
    
    print("1. 创建测试文件完成")
    
    # 2. 上传文件
    print("2. 开始上传文件...")
    
    with open("test_document.md", "rb") as f:
        files = {"files": ("test_document.md", f, "text/markdown")}
        data = {
            "user_id": "test-user",
            "enable_async_processing": "true",
            "splitter_strategy_id": "token_basic",  # 使用基础Token分块策略
            "chunk_size": "1000",
            "chunk_overlap": "200",
            "chunk_strategy": "token_based",
            "preserve_structure": "true"
        }
        
        response = requests.post(
            f"{KNOWLEDGE_SERVICE_URL}/api/v1/knowledge-bases/{TEST_KB_ID}/documents/upload-async",
            files=files,
            data=data
        )
    
    if response.status_code == 200:
        result = response.json()
        print(f"上传成功: {result}")
        
        # 获取任务ID
        task_id = None
        if result.get("data", {}).get("tasks"):
            task_id = result["data"]["tasks"][0].get("task_id")
        
        if task_id:
            print(f"任务ID: {task_id}")
            
            # 3. 监控任务状态
            print("3. 监控任务处理状态...")
            max_wait = 60  # 最多等待60秒
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                # 查询任务状态
                task_response = requests.get(f"{TASK_MANAGER_URL}/api/v1/tasks/{task_id}")
                
                if task_response.status_code == 200:
                    task_info = task_response.json()
                    status = task_info.get("status")
                    progress = task_info.get("progress", 0)
                    error_message = task_info.get("error_message")
                    
                    print(f"任务状态: {status}, 进度: {progress}%")
                    
                    if error_message:
                        print(f"错误信息: {error_message}")
                        break
                    
                    if status in ["completed", "failed"]:
                        print(f"任务完成，最终状态: {status}")
                        if status == "completed":
                            print("✅ 测试成功！文件上传和切分处理正常")
                        else:
                            print("❌ 测试失败！任务处理失败")
                        break
                
                time.sleep(2)
            else:
                print("⏰ 测试超时，任务未在预期时间内完成")
        else:
            print("❌ 未获取到任务ID")
    else:
        print(f"❌ 上传失败: {response.status_code} - {response.text}")

def test_strategy_mapping():
    """测试策略ID映射"""
    print("\n=== 测试策略ID映射 ===")
    
    # 测试获取策略列表
    response = requests.get(f"{KNOWLEDGE_SERVICE_URL}/api/v1/knowledge-bases/{TEST_KB_ID}/splitter-strategies")
    
    if response.status_code == 200:
        strategies = response.json()
        print(f"获取到 {len(strategies)} 个策略:")
        for strategy in strategies:
            print(f"  - {strategy.get('name')} (ID: {strategy.get('id')})")
    else:
        print(f"获取策略列表失败: {response.status_code}")

if __name__ == "__main__":
    try:
        test_strategy_mapping()
        test_upload_with_strategy()
    except Exception as e:
        print(f"测试过程中出现错误: {e}")
    finally:
        # 清理测试文件
        import os
        if os.path.exists("test_document.md"):
            os.remove("test_document.md") 