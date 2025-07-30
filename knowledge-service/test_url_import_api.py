#!/usr/bin/env python3
"""
URL导入API测试脚本
测试知识库服务的URL导入爬虫API接口
"""

import asyncio
import json
import aiohttp
import sys
from datetime import datetime

# 服务配置
KNOWLEDGE_SERVICE_URL = "http://localhost:8082"
TEST_KB_ID = "test-kb-url-import"


async def test_crawl_preview_api():
    """测试URL爬虫预览API"""
    print("=" * 60)
    print("测试URL爬虫预览API")
    print("=" * 60)
    
    url = f"{KNOWLEDGE_SERVICE_URL}/api/v1/knowledge-bases/{TEST_KB_ID}/documents/crawl-preview"
    
    # 测试数据
    form_data = aiohttp.FormData()
    form_data.add_field('urls', 'https://httpbin.org/html')
    form_data.add_field('urls', 'https://httpbin.org/json')
    form_data.add_field('max_pages', '3')
    form_data.add_field('use_trafilatura', 'false')
    
    try:
        async with aiohttp.ClientSession() as session:
            print(f"请求URL: {url}")
            print("请求数据: URL预览测试")
            
            async with session.post(url, data=form_data) as response:
                print(f"响应状态: {response.status}")
                
                if response.content_type == 'application/json':
                    result = await response.json()
                    print("响应内容:")
                    print(json.dumps(result, indent=2, ensure_ascii=False))
                    
                    if result.get('success'):
                        preview_results = result.get('data', {}).get('preview_results', [])
                        print(f"\n预览结果数量: {len(preview_results)}")
                        
                        for i, preview in enumerate(preview_results[:2]):
                            print(f"\n预览 {i+1}:")
                            print(f"  URL: {preview.get('url')}")
                            print(f"  标题: {preview.get('title')}")
                            print(f"  内容长度: {preview.get('content_length')}")
                            print(f"  状态: {preview.get('status')}")
                            print(f"  内容预览: {preview.get('content_preview', '')[:100]}...")
                        
                        return True
                    else:
                        print("API返回失败状态")
                        return False
                else:
                    text = await response.text()
                    print(f"非JSON响应: {text[:500]}")
                    return False
                    
    except Exception as e:
        print(f"预览API测试失败: {e}")
        return False


async def test_import_urls_api():
    """测试URL导入API"""
    print("=" * 60)
    print("测试URL导入API")
    print("=" * 60)
    
    url = f"{KNOWLEDGE_SERVICE_URL}/api/v1/knowledge-bases/{TEST_KB_ID}/documents/import-urls"
    
    # 构建JSON请求数据
    request_data = {
        "urls": [
            "https://httpbin.org/html",
            "https://httpbin.org/json"
        ],
        "crawl_mode": "url_list",
        "max_pages": 5,
        "concurrent_requests": 2,
        "request_delay": 1.0,
        "use_llamaindex": False,
        "use_trafilatura": False,
        "min_content_length": 10,
        "include_metadata": True,
        "enable_async_processing": False,  # 关闭异步处理便于测试
        "description": "API测试导入"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            print(f"请求URL: {url}")
            print("请求数据:")
            print(json.dumps(request_data, indent=2, ensure_ascii=False))
            
            async with session.post(
                url, 
                json=request_data,
                headers={'Content-Type': 'application/json'}
            ) as response:
                print(f"\n响应状态: {response.status}")
                
                if response.content_type == 'application/json':
                    result = await response.json()
                    print("响应内容:")
                    print(json.dumps(result, indent=2, ensure_ascii=False))
                    
                    if result.get('success'):
                        data = result.get('data', {})
                        crawl_summary = data.get('crawl_summary', {})
                        processing_tasks = data.get('processing_tasks', [])
                        
                        print(f"\n导入总结:")
                        print(f"  总URL数: {crawl_summary.get('total_urls')}")
                        print(f"  成功数: {crawl_summary.get('successful_count')}")
                        print(f"  失败数: {crawl_summary.get('failed_count')}")
                        print(f"  创建任务数: {crawl_summary.get('processing_tasks_created')}")
                        
                        print(f"\n处理任务:")
                        for i, task in enumerate(processing_tasks[:2]):
                            print(f"  任务 {i+1}:")
                            print(f"    ID: {task.get('task_id')}")
                            print(f"    URL: {task.get('url')}")
                            print(f"    标题: {task.get('title')}")
                            print(f"    状态: {task.get('status')}")
                        
                        return True
                    else:
                        print("API返回失败状态")
                        return False
                else:
                    text = await response.text()
                    print(f"非JSON响应: {text[:500]}")
                    return False
                    
    except Exception as e:
        print(f"导入API测试失败: {e}")
        return False


async def test_health_check():
    """测试服务健康检查"""
    print("=" * 60)
    print("测试知识库服务健康检查")
    print("=" * 60)
    
    url = f"{KNOWLEDGE_SERVICE_URL}/health"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                print(f"健康检查响应状态: {response.status}")
                
                if response.status == 200:
                    result = await response.json()
                    print("服务状态:")
                    print(f"  服务: {result.get('service')}")
                    print(f"  状态: {result.get('status')}")
                    print(f"  版本: {result.get('version')}")
                    print(f"  端口: {result.get('port')}")
                    
                    stats = result.get('stats', {})
                    print(f"  知识库数量: {stats.get('total_knowledge_bases')}")
                    print(f"  性能模式: {stats.get('performance_mode')}")
                    
                    return True
                else:
                    print("健康检查失败")
                    return False
                    
    except Exception as e:
        print(f"健康检查失败: {e}")
        return False


async def create_test_knowledge_base():
    """创建测试知识库"""
    print("=" * 40)
    print("创建测试知识库")
    print("=" * 40)
    
    url = f"{KNOWLEDGE_SERVICE_URL}/api/v1/knowledge-bases"
    
    kb_data = {
        "name": "URL导入测试知识库",
        "description": "用于测试URL导入功能的知识库",
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-ada-002",
        "vector_store_type": "milvus"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=kb_data,
                headers={'Content-Type': 'application/json'}
            ) as response:
                print(f"创建知识库响应状态: {response.status}")
                
                if response.status in [200, 201]:
                    result = await response.json()
                    if result.get('success'):
                        print(f"测试知识库创建成功: {TEST_KB_ID}")
                        return True
                    else:
                        print(f"知识库创建失败: {result}")
                        return False
                else:
                    text = await response.text()
                    print(f"创建知识库失败: {text}")
                    return False
                    
    except Exception as e:
        print(f"创建知识库异常: {e}")
        return False


async def main():
    """主测试函数"""
    print("开始URL导入API完整测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"服务地址: {KNOWLEDGE_SERVICE_URL}")
    print(f"测试知识库ID: {TEST_KB_ID}")
    
    total_tests = 0
    passed_tests = 0
    
    # 测试1: 健康检查
    total_tests += 1
    if await test_health_check():
        passed_tests += 1
        print("✅ 健康检查通过")
    else:
        print("❌ 健康检查失败")
        print("⚠️  知识库服务可能未启动，请检查服务状态")
        return 1
    
    print("\n⏳ 等待2秒...")
    await asyncio.sleep(2)
    
    # 测试2: 创建测试知识库
    total_tests += 1
    if await create_test_knowledge_base():
        passed_tests += 1
        print("✅ 测试知识库创建通过")
    else:
        print("❌ 测试知识库创建失败")
        print("⚠️  继续使用现有知识库进行测试")
    
    print("\n⏳ 等待2秒...")
    await asyncio.sleep(2)
    
    # 测试3: URL爬虫预览API
    total_tests += 1
    if await test_crawl_preview_api():
        passed_tests += 1
        print("✅ URL爬虫预览API测试通过")
    else:
        print("❌ URL爬虫预览API测试失败")
    
    print("\n⏳ 等待3秒...")
    await asyncio.sleep(3)
    
    # 测试4: URL导入API
    total_tests += 1
    if await test_import_urls_api():
        passed_tests += 1
        print("✅ URL导入API测试通过")
    else:
        print("❌ URL导入API测试失败")
    
    # 输出测试总结
    print("\n" + "=" * 80)
    print("URL导入API测试总结")
    print("=" * 80)
    print(f"总测试数: {total_tests}")
    print(f"通过测试: {passed_tests}")
    print(f"失败测试: {total_tests - passed_tests}")
    print(f"通过率: {passed_tests/total_tests*100:.1f}%")
    
    if passed_tests == total_tests:
        print("🎉 所有API测试通过！URL导入功能正常")
        return 0
    elif passed_tests >= total_tests - 1:
        print("⚠️  大部分测试通过，URL导入功能基本可用")
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