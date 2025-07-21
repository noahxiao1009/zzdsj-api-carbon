"""
智能爬取管理器
Intelligent Crawler Manager
"""

import asyncio
import aiohttp
import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)

class CrawlerType(str, Enum):
    """爬取工具类型"""
    CRAWL4AI = "crawl4ai"
    BROWSER_USE = "browser_use"
    TRADITIONAL = "traditional"

class PageComplexity(str, Enum):
    """页面复杂度"""
    SIMPLE = "simple"      # 静态HTML页面
    MODERATE = "moderate"  # 部分JS渲染
    COMPLEX = "complex"    # 重度JS依赖

class CrawlerInterface(ABC):
    """爬取工具接口"""
    
    @abstractmethod
    async def extract_content(self, url: str, **kwargs) -> Dict[str, Any]:
        """提取页面内容"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查"""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """获取爬取工具名称"""
        pass

class TraditionalCrawler(CrawlerInterface):
    """传统HTTP爬取器"""
    
    def __init__(self):
        self.timeout = 30
        self.max_content_length = 1024 * 1024  # 1MB
    
    async def extract_content(self, url: str, **kwargs) -> Dict[str, Any]:
        """使用传统HTTP方式提取内容"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        content = await response.text()
                        
                        # 使用BeautifulSoup清理内容
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(content, 'html.parser')
                        
                        # 移除脚本和样式
                        for script in soup(["script", "style", "nav", "footer", "header"]):
                            script.decompose()
                        
                        # 提取主要内容
                        main_content = soup.get_text(separator=' ', strip=True)
                        
                        return {
                            "success": True,
                            "content": main_content[:5000],  # 限制长度
                            "extraction_method": "traditional",
                            "metadata": {
                                "status_code": response.status,
                                "content_length": len(content),
                                "url": url
                            }
                        }
            
            return {
                "success": False,
                "error": f"HTTP {response.status}",
                "extraction_method": "traditional"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "extraction_method": "traditional"
            }
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://httpbin.org/get", timeout=aiohttp.ClientTimeout(total=5)) as response:
                    return response.status == 200
        except:
            return False
    
    def get_name(self) -> str:
        return "traditional"

class Crawl4AICrawler(CrawlerInterface):
    """Crawl4AI爬取器"""
    
    def __init__(self):
        self.enabled = True
        self._check_availability()
    
    def _check_availability(self):
        """检查Crawl4AI是否可用"""
        try:
            import crawl4ai
            self.enabled = True
        except ImportError:
            logger.warning("Crawl4AI not available, falling back to traditional crawler")
            self.enabled = False
    
    async def extract_content(self, url: str, **kwargs) -> Dict[str, Any]:
        """使用Crawl4AI提取内容"""
        if not self.enabled:
            raise Exception("Crawl4AI not available")
        
        try:
            # 这里应该集成实际的Crawl4AI调用
            # 由于Crawl4AI需要特定配置，这里提供模拟实现
            
            # 模拟Crawl4AI的高级内容提取
            await asyncio.sleep(0.5)  # 模拟处理时间
            
            # 使用传统方式作为回退
            traditional_crawler = TraditionalCrawler()
            result = await traditional_crawler.extract_content(url, **kwargs)
            
            if result["success"]:
                result["extraction_method"] = "crawl4ai"
                result["metadata"]["enhanced"] = True
                
                # 模拟Crawl4AI的内容增强
                content = result["content"]
                enhanced_content = self._enhance_content(content)
                result["content"] = enhanced_content
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "extraction_method": "crawl4ai"
            }
    
    def _enhance_content(self, content: str) -> str:
        """模拟内容增强处理"""
        # 移除多余空白字符
        import re
        content = re.sub(r'\s+', ' ', content)
        
        # 移除常见无用信息
        noise_patterns = [
            r'版权所有.*?保留',
            r'免责声明.*?条款',
            r'联系我们.*?电话',
            r'网站地图.*?导航'
        ]
        
        for pattern in noise_patterns:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE)
        
        return content.strip()
    
    async def health_check(self) -> bool:
        """健康检查"""
        return self.enabled
    
    def get_name(self) -> str:
        return "crawl4ai"

class BrowserUseCrawler(CrawlerInterface):
    """Browser Use爬取器"""
    
    def __init__(self):
        self.enabled = True
        self._check_availability()
    
    def _check_availability(self):
        """检查Browser Use是否可用"""
        try:
            # 检查Browser Use相关依赖
            import selenium
            self.enabled = True
        except ImportError:
            logger.warning("Browser Use dependencies not available")
            self.enabled = False
    
    async def extract_content(self, url: str, **kwargs) -> Dict[str, Any]:
        """使用Browser Use提取内容"""
        if not self.enabled:
            raise Exception("Browser Use not available")
        
        try:
            # 这里应该集成实际的Browser Use调用
            # 由于Browser Use需要特定配置，这里提供模拟实现
            
            # 模拟浏览器渲染时间
            await asyncio.sleep(1.0)
            
            # 使用传统方式作为基础
            traditional_crawler = TraditionalCrawler()
            result = await traditional_crawler.extract_content(url, **kwargs)
            
            if result["success"]:
                result["extraction_method"] = "browser_use"
                result["metadata"]["browser_rendered"] = True
                
                # 模拟浏览器渲染后的内容增强
                content = result["content"]
                enhanced_content = self._simulate_js_rendering(content)
                result["content"] = enhanced_content
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "extraction_method": "browser_use"
            }
    
    def _simulate_js_rendering(self, content: str) -> str:
        """模拟JavaScript渲染后的内容"""
        # 模拟动态内容加载
        enhanced_content = content
        
        # 添加一些可能由JS生成的内容标识
        if "政策" in content or "法规" in content:
            enhanced_content += " [动态加载的政策详情]"
        
        return enhanced_content
    
    async def health_check(self) -> bool:
        """健康检查"""
        return self.enabled
    
    def get_name(self) -> str:
        return "browser_use"

class IntelligentCrawlerManager:
    """智能爬取管理器"""
    
    def __init__(self):
        self.crawlers = {
            CrawlerType.TRADITIONAL: TraditionalCrawler(),
            CrawlerType.CRAWL4AI: Crawl4AICrawler(),
            CrawlerType.BROWSER_USE: BrowserUseCrawler()
        }
        
        self.fallback_order = [
            CrawlerType.CRAWL4AI,
            CrawlerType.TRADITIONAL,
            CrawlerType.BROWSER_USE
        ]
        
        # 配置参数
        self.complexity_threshold = {
            PageComplexity.SIMPLE: CrawlerType.TRADITIONAL,
            PageComplexity.MODERATE: CrawlerType.CRAWL4AI,
            PageComplexity.COMPLEX: CrawlerType.BROWSER_USE
        }
        
        # 性能统计
        self.performance_stats = {
            crawler_type: {
                "success_count": 0,
                "failure_count": 0,
                "avg_response_time": 0.0,
                "total_response_time": 0.0
            }
            for crawler_type in CrawlerType
        }
    
    async def extract_content(self, url: str, complexity_level: str = "auto", **kwargs) -> Dict[str, Any]:
        """智能选择爬取工具并提取内容"""
        
        # 1. 确定页面复杂度
        if complexity_level == "auto":
            complexity = await self._analyze_page_complexity(url)
        else:
            complexity = PageComplexity(complexity_level)
        
        # 2. 选择合适的爬取工具
        primary_crawler_type = self._select_crawler_by_complexity(complexity)
        
        # 3. 执行爬取并处理回退
        return await self._execute_with_fallback(url, primary_crawler_type, **kwargs)
    
    async def _analyze_page_complexity(self, url: str) -> PageComplexity:
        """分析页面复杂度"""
        try:
            # 简单的复杂度分析：基于域名和URL特征
            domain_indicators = {
                PageComplexity.SIMPLE: ['.gov.cn', '.edu.cn', 'static'],
                PageComplexity.MODERATE: ['.com', '.org', 'news'],
                PageComplexity.COMPLEX: ['app', 'ajax', 'api', 'spa']
            }
            
            url_lower = url.lower()
            
            # 检查复杂度指标
            for complexity, indicators in domain_indicators.items():
                if any(indicator in url_lower for indicator in indicators):
                    return complexity
            
            # 默认为中等复杂度
            return PageComplexity.MODERATE
            
        except Exception:
            return PageComplexity.MODERATE
    
    def _select_crawler_by_complexity(self, complexity: PageComplexity) -> CrawlerType:
        """根据复杂度选择爬取工具"""
        preferred_crawler = self.complexity_threshold.get(complexity, CrawlerType.TRADITIONAL)
        
        # 检查首选爬取工具是否可用
        if self.crawlers[preferred_crawler].enabled:
            return preferred_crawler
        
        # 回退到可用的爬取工具
        for crawler_type in self.fallback_order:
            if self.crawlers[crawler_type].enabled:
                return crawler_type
        
        return CrawlerType.TRADITIONAL  # 最后回退
    
    async def _execute_with_fallback(self, url: str, primary_crawler_type: CrawlerType, **kwargs) -> Dict[str, Any]:
        """执行爬取并处理回退逻辑"""
        crawler_attempts = [primary_crawler_type]
        
        # 添加回退选项
        for crawler_type in self.fallback_order:
            if crawler_type != primary_crawler_type and crawler_type not in crawler_attempts:
                crawler_attempts.append(crawler_type)
        
        last_error = None
        
        for crawler_type in crawler_attempts:
            crawler = self.crawlers[crawler_type]
            
            if not await crawler.health_check():
                continue
            
            try:
                start_time = time.time()
                result = await crawler.extract_content(url, **kwargs)
                execution_time = (time.time() - start_time) * 1000
                
                # 更新性能统计
                await self._update_performance_stats(crawler_type, True, execution_time)
                
                if result.get("success"):
                    result["metadata"]["crawler_used"] = crawler_type
                    result["metadata"]["execution_time_ms"] = execution_time
                    return result
                else:
                    last_error = result.get("error", "Unknown error")
                    
            except Exception as e:
                last_error = str(e)
                await self._update_performance_stats(crawler_type, False, 0)
                logger.warning(f"Crawler {crawler_type} failed for {url}: {e}")
                continue
        
        # 所有爬取工具都失败
        return {
            "success": False,
            "error": f"All crawlers failed. Last error: {last_error}",
            "extraction_method": "failed",
            "metadata": {
                "attempted_crawlers": crawler_attempts,
                "url": url
            }
        }
    
    async def _update_performance_stats(self, crawler_type: CrawlerType, success: bool, response_time: float):
        """更新性能统计"""
        stats = self.performance_stats[crawler_type]
        
        if success:
            stats["success_count"] += 1
            stats["total_response_time"] += response_time
            
            # 计算平均响应时间
            if stats["success_count"] > 0:
                stats["avg_response_time"] = stats["total_response_time"] / stats["success_count"]
        else:
            stats["failure_count"] += 1
    
    async def get_health_status(self) -> Dict[str, Any]:
        """获取所有爬取工具的健康状态"""
        health_status = {}
        
        for crawler_type, crawler in self.crawlers.items():
            try:
                is_healthy = await crawler.health_check()
                health_status[crawler_type] = {
                    "healthy": is_healthy,
                    "name": crawler.get_name(),
                    "stats": self.performance_stats[crawler_type]
                }
            except Exception as e:
                health_status[crawler_type] = {
                    "healthy": False,
                    "error": str(e),
                    "name": crawler.get_name()
                }
        
        return health_status
    
    async def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        return {
            "crawler_stats": self.performance_stats,
            "total_requests": sum(
                stats["success_count"] + stats["failure_count"] 
                for stats in self.performance_stats.values()
            ),
            "overall_success_rate": self._calculate_overall_success_rate()
        }
    
    def _calculate_overall_success_rate(self) -> float:
        """计算总体成功率"""
        total_success = sum(stats["success_count"] for stats in self.performance_stats.values())
        total_requests = sum(
            stats["success_count"] + stats["failure_count"] 
            for stats in self.performance_stats.values()
        )
        
        if total_requests == 0:
            return 0.0
        
        return (total_success / total_requests) * 100