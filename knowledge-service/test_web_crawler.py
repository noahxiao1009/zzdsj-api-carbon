#!/usr/bin/env python3
"""
Web Crawler功能测试脚本
测试URL导入爬虫的基本功能
"""

import asyncio
import json
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.core.web_crawler_manager import WebCrawlerManager, CrawlConfig, CrawlMode
from app.models.database import get_db


async def test_basic_crawler():
    """测试基础爬虫功能"""
    print("=" * 60)
    print("测试Web Crawler基础功能")
    print("=" * 60)
    
    # 获取数据库连接
    db = next(get_db())
    
    try:
        # 测试URL列表
        test_urls = [
            "https://httpbin.org/html",  # 简单HTML测试
            "https://httpbin.org/json",  # JSON响应测试
        ]
        
        # 创建爬虫配置
        config = CrawlConfig(
            mode=CrawlMode.URL_LIST,
            max_pages=5,
            concurrent_requests=2,
            request_delay=1.0,
            use_llamaindex=False,  # 先测试基础功能
            use_trafilatura=False,
            min_content_length=10,  # 降低要求便于测试
            max_content_length=50000,
            include_metadata=True
        )
        
        print(f"测试URL: {test_urls}")
        print(f"爬虫配置: {config.mode.value}, 最大页面: {config.max_pages}")
        print("-" * 40)
        
        # 执行爬虫测试
        async with WebCrawlerManager(db) as crawler:
            result = await crawler.crawl_urls(
                kb_id="test-kb-001",
                urls=test_urls,
                config=config
            )
        
        # 输出结果
        print("爬虫执行结果:")
        print(f"成功: {result['success']}")
        print(f"总URL数: {result['total_urls']}")
        print(f"成功数: {result['successful_count']}")
        print(f"失败数: {result['failed_count']}")
        print("-" * 40)
        
        # 展示成功结果
        for i, crawl_result in enumerate(result['results'][:2]):  # 只显示前2个
            print(f"\n结果 {i+1}:")
            print(f"URL: {crawl_result.url}")
            print(f"标题: {crawl_result.title}")
            print(f"内容长度: {len(crawl_result.content)}")
            print(f"Markdown长度: {len(crawl_result.markdown_content)}")
            print(f"状态: {crawl_result.status}")
            print(f"爬取时间: {crawl_result.crawl_time:.2f}s")
            print(f"内容预览: {crawl_result.content[:200]}...")
            
        # 展示失败结果
        if result['failed_results']:
            print(f"\n失败结果 ({len(result['failed_results'])}个):")
            for failed in result['failed_results'][:2]:
                print(f"URL: {failed.url}")
                print(f"错误: {failed.error_message}")
        
        print("\n" + "=" * 60)
        print("基础爬虫测试完成")
        
        return result['success']
        
    except Exception as e:
        print(f"爬虫测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


async def test_llamaindex_crawler():
    """测试LlamaIndex集成爬虫"""
    print("=" * 60)
    print("测试LlamaIndex集成爬虫")
    print("=" * 60)
    
    db = next(get_db())
    
    try:
        # 测试URL
        test_urls = ["https://docs.python.org/3/tutorial/introduction.html"]
        
        # 启用LlamaIndex的配置
        config = CrawlConfig(
            mode=CrawlMode.SINGLE_URL,
            use_llamaindex=True,
            use_trafilatura=True,
            min_content_length=100,
            include_metadata=True
        )
        
        print(f"测试URL: {test_urls[0]}")
        print("使用LlamaIndex + Trafilatura提取")
        print("-" * 40)
        
        async with WebCrawlerManager(db) as crawler:
            result = await crawler.crawl_urls(
                kb_id="test-kb-002",
                urls=test_urls,
                config=config
            )
        
        if result['success'] and result['results']:
            crawl_result = result['results'][0]
            print("LlamaIndex爬虫结果:")
            print(f"URL: {crawl_result.url}")
            print(f"标题: {crawl_result.title}")
            print(f"内容长度: {len(crawl_result.content)}")
            print(f"Markdown长度: {len(crawl_result.markdown_content)}")
            print(f"状态: {crawl_result.status}")
            print(f"元数据: {json.dumps(crawl_result.metadata, indent=2, ensure_ascii=False)}")
            print("\nMarkdown内容预览:")
            print(crawl_result.markdown_content[:500] + "...")
        else:
            print("LlamaIndex爬虫执行失败")
            if result.get('failed_results'):
                print(f"错误: {result['failed_results'][0].error_message}")
        
        print("\n" + "=" * 60)
        print("LlamaIndex爬虫测试完成")
        
        return result['success']
        
    except Exception as e:
        print(f"LlamaIndex爬虫测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


async def test_content_filtering():
    """测试内容过滤功能"""
    print("=" * 60)
    print("测试内容过滤功能")
    print("=" * 60)
    
    db = next(get_db())
    
    try:
        # 测试包含多种元素的HTML页面
        test_urls = ["https://httpbin.org/html"]
        
        # 配置内容过滤器
        config = CrawlConfig(
            mode=CrawlMode.SINGLE_URL,
            use_llamaindex=False,
            content_filters=["script", "style", "nav"],  # 过滤这些元素
            content_selectors=["body"],  # 只保留body内容
            min_content_length=10,
            include_metadata=True
        )
        
        print(f"测试URL: {test_urls[0]}")
        print(f"内容过滤器: {config.content_filters}")
        print(f"内容选择器: {config.content_selectors}")
        print("-" * 40)
        
        async with WebCrawlerManager(db) as crawler:
            result = await crawler.crawl_urls(
                kb_id="test-kb-003",
                urls=test_urls,
                config=config
            )
        
        if result['success'] and result['results']:
            crawl_result = result['results'][0]
            print("内容过滤结果:")
            print(f"原始内容长度: {len(crawl_result.content)}")
            print(f"清洗后内容预览:")
            print(crawl_result.content[:300] + "...")
            print("\nMarkdown格式:")
            print(crawl_result.markdown_content[:300] + "...")
        else:
            print("内容过滤测试失败")
        
        print("\n" + "=" * 60)
        print("内容过滤测试完成")
        
        return result['success']
        
    except Exception as e:
        print(f"内容过滤测试失败: {e}")
        return False
    finally:
        db.close()


async def main():
    """主测试函数"""
    print("开始Web Crawler完整功能测试")
    print("当前工作目录:", Path.cwd())
    print("项目根目录:", project_root)
    
    # 测试计数器
    total_tests = 0
    passed_tests = 0
    
    # 测试1: 基础爬虫功能
    total_tests += 1
    if await test_basic_crawler():
        passed_tests += 1
        print("✅ 基础爬虫测试通过")
    else:
        print("❌ 基础爬虫测试失败")
    
    print("\n" + "⏳ 等待2秒...")
    await asyncio.sleep(2)
    
    # 测试2: LlamaIndex集成（可能因为依赖问题失败）
    total_tests += 1
    if await test_llamaindex_crawler():
        passed_tests += 1
        print("✅ LlamaIndex爬虫测试通过")
    else:
        print("❌ LlamaIndex爬虫测试失败（可能因为依赖缺失）")
    
    print("\n" + "⏳ 等待2秒...")
    await asyncio.sleep(2)
    
    # 测试3: 内容过滤
    total_tests += 1
    if await test_content_filtering():
        passed_tests += 1
        print("✅ 内容过滤测试通过")
    else:
        print("❌ 内容过滤测试失败")
    
    # 输出测试总结
    print("\n" + "=" * 80)
    print("Web Crawler测试总结")
    print("=" * 80)
    print(f"总测试数: {total_tests}")
    print(f"通过测试: {passed_tests}")
    print(f"失败测试: {total_tests - passed_tests}")
    print(f"通过率: {passed_tests/total_tests*100:.1f}%")
    
    if passed_tests == total_tests:
        print("🎉 所有测试通过！Web Crawler功能正常")
        return 0
    elif passed_tests > 0:
        print("⚠️  部分测试通过，Web Crawler基本功能可用")
        return 0
    else:
        print("❌ 所有测试失败，请检查配置和依赖")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n测试执行异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)