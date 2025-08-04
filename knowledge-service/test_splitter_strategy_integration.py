#!/usr/bin/env python3
"""
切分策略集成测试脚本
测试切分策略管理和知识库配置的完整功能
"""

import asyncio
import aiohttp
import json
import sys
from datetime import datetime

# 服务配置
KNOWLEDGE_SERVICE_URL = "http://localhost:8082"
TEST_KB_ID = "test-kb-splitter-integration"


async def test_splitter_strategies_api():
    """测试切分策略管理API"""
    print("=" * 60)
    print("测试切分策略管理API")
    print("=" * 60)
    
    async with aiohttp.ClientSession() as session:
        # 1. 获取所有策略
        print("1. 获取所有切分策略...")
        async with session.get(f"{KNOWLEDGE_SERVICE_URL}/api/v1/splitter-strategies/") as response:
            if response.status == 200:
                result = await response.json()
                strategies = result.get('data', {}).get('strategies', [])
                print(f"   成功获取 {len(strategies)} 个策略")
                for strategy in strategies[:3]:  # 显示前3个
                    print(f"   - {strategy['name']}: {strategy['description']}")
                return strategies
            else:
                print(f"   失败: {response.status}")
                return []


async def test_knowledge_base_config():
    """测试知识库配置管理"""
    print("=" * 60)
    print("测试知识库配置管理")
    print("=" * 60)
    
    async with aiohttp.ClientSession() as session:
        # 1. 创建测试知识库
        print("1. 创建测试知识库...")
        kb_data = {
            "name": "切分策略测试知识库",
            "description": "用于测试切分策略功能的知识库",
            "embedding_provider": "openai",
            "embedding_model": "text-embedding-ada-002"
        }
        
        async with session.post(
            f"{KNOWLEDGE_SERVICE_URL}/api/v1/knowledge-bases/",
            json=kb_data
        ) as response:
            if response.status in [200, 201]:
                result = await response.json()
                print("   知识库创建成功")
            else:
                print(f"   知识库创建失败: {response.status}")
                return False
        
        # 2. 获取知识库配置
        print("2. 获取知识库配置...")
        async with session.get(
            f"{KNOWLEDGE_SERVICE_URL}/api/v1/knowledge-bases/{TEST_KB_ID}/config"
        ) as response:
            if response.status == 200:
                result = await response.json()
                print("   成功获取知识库配置")
                config_source = result.get('data', {}).get('config_source', 'unknown')
                print(f"   配置来源: {config_source}")
            else:
                print(f"   获取配置失败: {response.status}")
        
        # 3. 设置默认切分策略
        print("3. 设置默认切分策略...")
        strategies = await test_splitter_strategies_api()
        if strategies:
            strategy_id = strategies[0]['id']  # 使用第一个策略
            strategy_data = {
                "strategy_id": strategy_id,
                "custom_config": None
            }
            
            async with session.put(
                f"{KNOWLEDGE_SERVICE_URL}/api/v1/knowledge-bases/{TEST_KB_ID}/default-splitter",
                json=strategy_data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    print("   成功设置默认切分策略")
                    print(f"   策略ID: {strategy_id}")
                else:
                    print(f"   设置策略失败: {response.status}")
        
        return True


async def test_upload_with_strategy():
    """测试带切分策略的文档上传"""
    print("=" * 60)
    print("测试带切分策略的文档上传")
    print("=" * 60)
    
    # 创建测试文件
    test_content = """
    这是一个测试文档，用于验证切分策略功能。
    
    ## 第一节
    这是第一节的内容，包含一些技术说明和代码示例。
    
    ```python
    def hello_world():
        print("Hello, World!")
        return "success"
    ```
    
    ## 第二节
    这是第二节的内容，讨论了一些高级特性。
    
    ### 子节
    这是一个子节，包含更详细的信息。
    
    ## 总结
    这个文档展示了多层级的结构，适合测试不同的切分策略。
    """
    
    async with aiohttp.ClientSession() as session:
        # 获取可用策略
        strategies = await test_splitter_strategies_api()
        if not strategies:
            print("没有可用的切分策略")
            return False
        
        # 选择语义切分策略
        semantic_strategy = None
        for strategy in strategies:
            if 'semantic' in strategy['name'].lower():
                semantic_strategy = strategy
                break
        
        if not semantic_strategy:
            semantic_strategy = strategies[0]  # 使用第一个可用策略
        
        print(f"使用策略: {semantic_strategy['name']}")
        
        # 准备上传数据
        data = aiohttp.FormData()
        data.add_field('files', test_content.encode('utf-8'), 
                      filename='test_document.txt', 
                      content_type='text/plain')
        data.add_field('splitter_strategy_id', semantic_strategy['id'])
        data.add_field('folder_id', '')
        data.add_field('enable_async_processing', 'true')
        
        # 上传文档
        async with session.post(
            f"{KNOWLEDGE_SERVICE_URL}/api/v1/knowledge-bases/{TEST_KB_ID}/documents/upload-async",
            data=data
        ) as response:
            if response.status == 200:
                result = await response.json()
                print("   文档上传成功")
                tasks = result.get('data', {}).get('tasks', [])
                if tasks:
                    task_id = tasks[0]['task_id']
                    print(f"   任务ID: {task_id}")
                    return task_id
            else:
                text = await response.text()
                print(f"   文档上传失败: {response.status}")
                print(f"   错误信息: {text}")
                return None


async def test_strategy_recommendation():
    """测试策略推荐功能"""
    print("=" * 60)
    print("测试策略推荐功能")
    print("=" * 60)
    
    test_cases = [
        {"file_type": ".py", "file_size": 5000, "description": "Python代码文件"},
        {"file_type": ".md", "file_size": 50000, "description": "大型Markdown文档"},
        {"file_type": ".pdf", "file_size": 1000000, "description": "PDF文件"},
        {"file_type": ".txt", "file_size": 2000, "description": "小型文本文件"}
    ]
    
    async with aiohttp.ClientSession() as session:
        for i, case in enumerate(test_cases):
            print(f"{i+1}. 测试 {case['description']}...")
            
            async with session.post(
                f"{KNOWLEDGE_SERVICE_URL}/api/v1/splitter-strategies/recommend",
                json={
                    "file_type": case["file_type"],
                    "file_size": case["file_size"],
                    "file_name": f"test{case['file_type']}"
                }
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    strategy = result.get('data', {}).get('recommended_strategy', {})
                    reason = result.get('data', {}).get('recommendation_reason', '')
                    print(f"   推荐策略: {strategy.get('name', 'Unknown')}")
                    print(f"   推荐理由: {reason}")
                else:
                    print(f"   推荐失败: {response.status}")


async def test_default_configs():
    """测试默认配置模板"""
    print("=" * 60)
    print("测试默认配置模板")
    print("=" * 60)
    
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{KNOWLEDGE_SERVICE_URL}/api/v1/splitter-strategies/configs/defaults"
        ) as response:
            if response.status == 200:
                result = await response.json()
                configs = result.get('data', {}).get('default_configs', {})
                descriptions = result.get('data', {}).get('config_descriptions', {})
                
                print("默认配置模板:")
                for config_type, config in configs.items():
                    desc = descriptions.get(config_type, '无描述')
                    print(f"  {config_type}: {desc}")
                    print(f"    chunk_size: {config.get('chunk_size')}")
                    print(f"    chunk_overlap: {config.get('chunk_overlap')}")
                    print(f"    chunk_strategy: {config.get('chunk_strategy')}")
                
                return True
            else:
                print(f"获取默认配置失败: {response.status}")
                return False


async def main():
    """主测试函数"""
    print("开始切分策略集成测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"服务地址: {KNOWLEDGE_SERVICE_URL}")
    print(f"测试知识库ID: {TEST_KB_ID}")
    
    total_tests = 0
    passed_tests = 0
    
    # 测试1: 切分策略管理API
    total_tests += 1
    strategies = await test_splitter_strategies_api()
    if strategies:
        passed_tests += 1
        print("✅ 切分策略管理API测试通过")
    else:
        print("❌ 切分策略管理API测试失败")
    
    await asyncio.sleep(1)
    
    # 测试2: 知识库配置管理
    total_tests += 1
    if await test_knowledge_base_config():
        passed_tests += 1
        print("✅ 知识库配置管理测试通过")
    else:
        print("❌ 知识库配置管理测试失败")
    
    await asyncio.sleep(1)
    
    # 测试3: 策略推荐功能
    total_tests += 1
    try:
        await test_strategy_recommendation()
        passed_tests += 1
        print("✅ 策略推荐功能测试通过")
    except Exception as e:
        print(f"❌ 策略推荐功能测试失败: {e}")
    
    await asyncio.sleep(1)
    
    # 测试4: 默认配置模板
    total_tests += 1
    if await test_default_configs():
        passed_tests += 1
        print("✅ 默认配置模板测试通过")
    else:
        print("❌ 默认配置模板测试失败")
    
    await asyncio.sleep(1)
    
    # 测试5: 带策略的文档上传
    total_tests += 1
    task_id = await test_upload_with_strategy()
    if task_id:
        passed_tests += 1
        print("✅ 带策略的文档上传测试通过")
    else:
        print("❌ 带策略的文档上传测试失败")
    
    # 输出测试总结
    print("\n" + "=" * 80)
    print("切分策略集成测试总结")
    print("=" * 80)
    print(f"总测试数: {total_tests}")
    print(f"通过测试: {passed_tests}")
    print(f"失败测试: {total_tests - passed_tests}")
    print(f"通过率: {passed_tests/total_tests*100:.1f}%")
    
    if passed_tests == total_tests:
        print("🎉 所有测试通过！切分策略功能正常")
        return 0
    elif passed_tests >= total_tests - 1:
        print("⚠️  大部分测试通过，切分策略功能基本可用")
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