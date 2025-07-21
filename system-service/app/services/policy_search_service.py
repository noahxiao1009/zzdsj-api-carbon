"""
政策搜索服务核心实现
Policy Search Service Implementation
"""

import asyncio
import aiohttp
import hashlib
import json
import time
import uuid
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlencode
import logging

from ..models.policy_models import (
    PolicySearchRequest, PolicySearchResponse, PolicySearchResult,
    PortalConfigModel, SearchStrategy, SearchLevel, ExtractionMethod
)
from ..repositories.policy_repository import PolicyRepository
from ..utils.crawler_utils import IntelligentCrawlerManager
from ..utils.text_utils import TextAnalyzer
from shared.service_client import call_service, CallMethod, CallConfig

logger = logging.getLogger(__name__)

class PolicySearchService:
    """政策搜索服务"""
    
    def __init__(self, repository: PolicyRepository):
        self.repository = repository
        self.crawler_manager = IntelligentCrawlerManager()
        self.text_analyzer = TextAnalyzer()
        
        # 缓存相关
        self._portal_cache = {}
        self._cache_ttl = 3600  # 1小时
        
        # 搜索配置
        self.max_concurrent_requests = 5
        self.default_timeout = 30
        self.quality_threshold = 0.6
    
    async def search_policies(self, request: PolicySearchRequest) -> PolicySearchResponse:
        """执行政策搜索"""
        start_time = time.time()
        
        # 1. 检查缓存
        if request.enable_caching:
            cache_key = self._generate_cache_key(request)
            cached_result = await self._get_cached_result(cache_key)
            if cached_result:
                return cached_result
        
        # 2. 执行搜索
        search_results = await self._execute_search(request)
        
        # 3. 构建响应
        execution_time = int((time.time() - start_time) * 1000)
        response = PolicySearchResponse(
            query=request.query,
            region=request.region,
            strategy=request.search_strategy,
            results=search_results.get("results", []),
            total_results=len(search_results.get("results", [])),
            search_time_ms=execution_time,
            cache_hit=False,
            search_levels_used=search_results.get("levels_used", []),
            statistics=search_results.get("statistics", {})
        )
        
        # 4. 缓存结果
        if request.enable_caching and response.total_results > 0:
            await self._cache_result(cache_key, response, request.cache_ttl_seconds)
        
        return response
    
    async def _execute_search(self, request: PolicySearchRequest) -> Dict[str, Any]:
        """执行具体搜索逻辑"""
        strategy = request.search_strategy
        results = []
        levels_used = []
        statistics = {
            "portal_responses": {},
            "crawling_stats": {},
            "quality_scores": []
        }
        
        if strategy == SearchStrategy.AUTO:
            # 自动策略：分层搜索直到满足质量要求
            results, levels_used = await self._auto_search(request, statistics)
        elif strategy == SearchStrategy.LOCAL_ONLY:
            results = await self._search_by_level(request, SearchLevel.LOCAL, statistics)
            levels_used = [SearchLevel.LOCAL]
        elif strategy == SearchStrategy.PROVINCIAL_ONLY:
            results = await self._search_by_level(request, SearchLevel.PROVINCIAL, statistics)
            levels_used = [SearchLevel.PROVINCIAL]
        elif strategy == SearchStrategy.SEARCH_ONLY:
            results = await self._search_by_level(request, SearchLevel.SEARCH_ENGINE, statistics)
            levels_used = [SearchLevel.SEARCH_ENGINE]
        elif strategy == SearchStrategy.HYBRID:
            # 混合策略：并行搜索多个层级
            results, levels_used = await self._hybrid_search(request, statistics)
        
        return {
            "results": results[:request.max_results],
            "levels_used": levels_used,
            "statistics": statistics
        }
    
    async def _auto_search(self, request: PolicySearchRequest, statistics: Dict) -> Tuple[List[PolicySearchResult], List[SearchLevel]]:
        """自动搜索策略：分层搜索直到满足质量要求"""
        search_levels = [SearchLevel.LOCAL, SearchLevel.PROVINCIAL, SearchLevel.SEARCH_ENGINE]
        all_results = []
        levels_used = []
        
        for level in search_levels:
            level_results = await self._search_by_level(request, level, statistics)
            if level_results:
                all_results.extend(level_results)
                levels_used.append(level)
                
                # 评估结果质量
                avg_quality = sum(r.content_quality_score for r in level_results) / len(level_results)
                statistics[f"{level}_quality"] = avg_quality
                
                # 如果质量满足要求且结果足够，停止搜索
                if avg_quality >= self.quality_threshold and len(all_results) >= request.max_results // 2:
                    break
        
        # 去重和排序
        unique_results = self._deduplicate_results(all_results)
        sorted_results = self._sort_results_by_relevance(unique_results, request.query)
        
        return sorted_results, levels_used
    
    async def _hybrid_search(self, request: PolicySearchRequest, statistics: Dict) -> Tuple[List[PolicySearchResult], List[SearchLevel]]:
        """混合搜索策略：并行搜索多个层级"""
        search_levels = [SearchLevel.LOCAL, SearchLevel.PROVINCIAL, SearchLevel.SEARCH_ENGINE]
        
        # 并行搜索任务
        tasks = []
        for level in search_levels:
            task = self._search_by_level(request, level, statistics)
            tasks.append(task)
        
        # 等待所有搜索完成
        level_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 合并结果
        all_results = []
        levels_used = []
        
        for i, results in enumerate(level_results):
            if not isinstance(results, Exception) and results:
                all_results.extend(results)
                levels_used.append(search_levels[i])
        
        # 去重和排序
        unique_results = self._deduplicate_results(all_results)
        sorted_results = self._sort_results_by_relevance(unique_results, request.query)
        
        return sorted_results, levels_used
    
    async def _search_by_level(self, request: PolicySearchRequest, level: SearchLevel, statistics: Dict) -> List[PolicySearchResult]:
        """按指定层级搜索"""
        try:
            # 获取该层级的门户配置
            portals = await self._get_portals_by_level(level, request.region)
            if not portals:
                return []
            
            # 并行搜索多个门户
            portal_tasks = []
            for portal in portals[:3]:  # 限制并发门户数
                task = self._search_single_portal(portal, request, statistics)
                portal_tasks.append(task)
            
            portal_results = await asyncio.gather(*portal_tasks, return_exceptions=True)
            
            # 合并门户结果
            level_results = []
            for results in portal_results:
                if not isinstance(results, Exception) and results:
                    level_results.extend(results)
            
            return level_results
            
        except Exception as e:
            logger.error(f"Level {level} search failed: {e}")
            statistics[f"{level}_error"] = str(e)
            return []
    
    async def _search_single_portal(self, portal: PortalConfigModel, request: PolicySearchRequest, statistics: Dict) -> List[PolicySearchResult]:
        """在单个门户中搜索"""
        try:
            # 构建搜索URL
            search_url = self._build_search_url(portal, request.query)
            
            # 执行HTTP请求
            start_time = time.time()
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=portal.timeout_seconds)) as session:
                async with session.get(search_url, headers=self._get_request_headers()) as response:
                    html_content = await response.text(encoding=portal.encoding)
                    response_time = (time.time() - start_time) * 1000
                    
                    statistics["portal_responses"][portal.name] = {
                        "status_code": response.status,
                        "response_time_ms": response_time,
                        "content_length": len(html_content)
                    }
            
            # 解析搜索结果
            raw_results = await self._parse_search_results(html_content, portal, search_url)
            
            # 智能爬取增强（如果启用）
            if request.enable_intelligent_crawling and raw_results:
                enhanced_results = await self._enhance_results_with_crawling(raw_results, statistics)
                return enhanced_results
            
            return raw_results
            
        except Exception as e:
            logger.error(f"Portal {portal.name} search failed: {e}")
            statistics["portal_responses"][portal.name] = {"error": str(e)}
            return []
    
    async def _enhance_results_with_crawling(self, raw_results: List[PolicySearchResult], statistics: Dict) -> List[PolicySearchResult]:
        """使用智能爬取增强结果"""
        enhanced_results = []
        crawling_stats = {"total": len(raw_results), "enhanced": 0, "failed": 0}
        
        # 限制爬取数量
        results_to_enhance = raw_results[:5]  # 最多增强5个结果
        
        for result in results_to_enhance:
            try:
                # 使用智能爬取管理器提取内容
                enhanced_content = await self.crawler_manager.extract_content(
                    result.url,
                    complexity_level="auto"
                )
                
                if enhanced_content.get("success"):
                    # 更新结果内容
                    result.content = enhanced_content.get("content", result.content)
                    result.extraction_method = ExtractionMethod(enhanced_content.get("extraction_method", "intelligent"))
                    
                    # 重新计算质量评分
                    result.content_quality_score = self.text_analyzer.calculate_content_quality(result.content)
                    result.relevance_score = self.text_analyzer.calculate_relevance(result.content, result.title)
                    
                    crawling_stats["enhanced"] += 1
                else:
                    crawling_stats["failed"] += 1
                
                enhanced_results.append(result)
                
            except Exception as e:
                logger.warning(f"Failed to enhance result {result.url}: {e}")
                crawling_stats["failed"] += 1
                enhanced_results.append(result)  # 保留原结果
        
        # 添加未增强的结果
        enhanced_results.extend(raw_results[5:])
        
        statistics["crawling_stats"] = crawling_stats
        return enhanced_results
    
    async def _parse_search_results(self, html_content: str, portal: PortalConfigModel, search_url: str) -> List[PolicySearchResult]:
        """解析搜索结果页面"""
        try:
            from bs4 import BeautifulSoup
            import re
            
            soup = BeautifulSoup(html_content, 'html.parser')
            results = []
            
            # 使用门户配置的选择器
            if portal.result_selector:
                result_elements = soup.select(portal.result_selector)
            else:
                # 通用选择器策略
                result_elements = self._find_result_elements(soup)
            
            for i, element in enumerate(result_elements[:portal.max_results]):
                try:
                    # 提取标题
                    title_elem = element.find(['h3', 'h4', 'h2', 'a']) or element
                    title = title_elem.get_text(strip=True) if title_elem else f"政策文档 {i+1}"
                    
                    # 提取链接
                    link_elem = element.find('a')
                    url = ""
                    if link_elem and link_elem.get('href'):
                        href = link_elem.get('href')
                        url = urljoin(portal.base_url, href)
                    
                    # 提取内容摘要
                    content_elem = element.find(['p', 'div', 'span']) or element
                    content = content_elem.get_text(strip=True) if content_elem else title
                    
                    # 提取发布日期
                    date_text = element.get_text()
                    published_date = self._extract_date(date_text)
                    
                    # 创建搜索结果
                    result = PolicySearchResult(
                        title=title[:200],  # 限制标题长度
                        url=url,
                        content=content[:1000],  # 限制内容长度
                        published_date=published_date,
                        source=portal.name,
                        search_level=SearchLevel(portal.level),
                        relevance_score=self.text_analyzer.calculate_relevance(content, title),
                        content_quality_score=self.text_analyzer.calculate_content_quality(content),
                        extraction_method=ExtractionMethod.TRADITIONAL,
                        metadata={
                            "portal_id": portal.id,
                            "search_url": search_url,
                            "result_index": i
                        }
                    )
                    
                    results.append(result)
                    
                except Exception as e:
                    logger.warning(f"Failed to parse result element {i}: {e}")
                    continue
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to parse search results: {e}")
            return []
    
    def _find_result_elements(self, soup) -> List:
        """通用搜索结果元素查找"""
        # 常见的搜索结果选择器
        selectors = [
            '.search-result', '.result-item', '.search-item',
            '.list-item', '.content-item', '.policy-item',
            'li[class*="result"]', 'div[class*="result"]',
            'li[class*="item"]', 'div[class*="item"]'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            if len(elements) >= 2:  # 至少找到2个元素才认为有效
                return elements
        
        # 如果没有找到，尝试查找链接集合
        links = soup.find_all('a', href=True)
        return links[:20]  # 最多返回20个链接
    
    def _extract_date(self, text: str) -> Optional[str]:
        """从文本中提取日期"""
        import re
        
        # 常见日期格式的正则表达式
        date_patterns = [
            r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})',  # 2023-12-01 或 2023/12/01
            r'(\d{4}年\d{1,2}月\d{1,2}日)',      # 2023年12月01日
            r'(\d{1,2}[-/]\d{1,2}[-/]\d{4})',    # 01-12-2023
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        
        return None
    
    def _build_search_url(self, portal: PortalConfigModel, query: str) -> str:
        """构建搜索URL"""
        # 替换参数模板中的查询占位符
        params = {}
        for key, value in portal.search_params.items():
            if "{query}" in str(value):
                params[key] = str(value).replace("{query}", query)
            else:
                params[key] = str(value)
        
        # 构建完整URL
        base_search_url = urljoin(portal.base_url, portal.search_endpoint)
        return f"{base_search_url}?{urlencode(params)}"
    
    def _get_request_headers(self) -> Dict[str, str]:
        """获取请求头"""
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
    
    def _deduplicate_results(self, results: List[PolicySearchResult]) -> List[PolicySearchResult]:
        """去重搜索结果"""
        seen_urls = set()
        seen_titles = set()
        unique_results = []
        
        for result in results:
            # 基于URL去重
            if result.url and result.url in seen_urls:
                continue
            
            # 基于标题相似度去重
            title_hash = hashlib.md5(result.title.encode()).hexdigest()
            if title_hash in seen_titles:
                continue
            
            seen_urls.add(result.url)
            seen_titles.add(title_hash)
            unique_results.append(result)
        
        return unique_results
    
    def _sort_results_by_relevance(self, results: List[PolicySearchResult], query: str) -> List[PolicySearchResult]:
        """按相关性排序结果"""
        # 重新计算相关性评分
        for result in results:
            result.relevance_score = self.text_analyzer.calculate_relevance(
                result.content + " " + result.title, 
                query
            )
        
        # 按相关性和质量评分排序
        return sorted(results, key=lambda x: (x.relevance_score + x.content_quality_score) / 2, reverse=True)
    
    async def _get_portals_by_level(self, level: SearchLevel, region: str) -> List[PortalConfigModel]:
        """获取指定层级和区域的门户配置"""
        cache_key = f"portals_{level}_{region}"
        
        if cache_key in self._portal_cache:
            return self._portal_cache[cache_key]
        
        portals = await self.repository.get_portals_by_level_and_region(level, region)
        self._portal_cache[cache_key] = portals
        
        # 缓存过期清理
        asyncio.create_task(self._clear_cache_after_delay(cache_key, self._cache_ttl))
        
        return portals
    
    async def _clear_cache_after_delay(self, cache_key: str, delay: int):
        """延时清理缓存"""
        await asyncio.sleep(delay)
        self._portal_cache.pop(cache_key, None)
    
    def _generate_cache_key(self, request: PolicySearchRequest) -> str:
        """生成缓存键"""
        key_data = {
            "query": request.query,
            "region": request.region,
            "strategy": request.search_strategy,
            "max_results": request.max_results,
            "enable_intelligent_crawling": request.enable_intelligent_crawling
        }
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_string.encode()).hexdigest()
    
    async def _get_cached_result(self, cache_key: str) -> Optional[PolicySearchResponse]:
        """获取缓存结果"""
        try:
            cached_data = await self.repository.get_cached_result(cache_key)
            if cached_data:
                # 检查是否过期
                if cached_data.cache_expires_at > datetime.now():
                    response = PolicySearchResponse(**cached_data.results)
                    response.cache_hit = True
                    return response
                else:
                    # 删除过期缓存
                    await self.repository.delete_cached_result(cache_key)
            
        except Exception as e:
            logger.warning(f"Failed to get cached result: {e}")
        
        return None
    
    async def _cache_result(self, cache_key: str, response: PolicySearchResponse, ttl_seconds: int):
        """缓存搜索结果"""
        try:
            expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
            
            await self.repository.save_cached_result(
                cache_key=cache_key,
                query=response.query,
                region=response.region,
                strategy=response.strategy,
                results=response.dict(),
                result_count=response.total_results,
                execution_time_ms=response.search_time_ms,
                expires_at=expires_at
            )
            
        except Exception as e:
            logger.warning(f"Failed to cache result: {e}")
    
    # ==================== 管理接口 ====================
    
    async def get_supported_regions(self) -> List[str]:
        """获取支持的区域列表"""
        return await self.repository.get_all_regions()
    
    async def get_portal_list(self, level: Optional[SearchLevel] = None, region: Optional[str] = None) -> List[PortalConfigModel]:
        """获取门户配置列表"""
        return await self.repository.get_portals(level=level, region=region)
    
    async def test_portal_connectivity(self, portal_id: str) -> Dict[str, Any]:
        """测试门户连通性"""
        portal = await self.repository.get_portal_by_id(portal_id)
        if not portal:
            return {"success": False, "error": "Portal not found"}
        
        try:
            start_time = time.time()
            test_url = self._build_search_url(portal, "测试")
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=portal.timeout_seconds)) as session:
                async with session.get(test_url, headers=self._get_request_headers()) as response:
                    response_time = (time.time() - start_time) * 1000
                    
                    return {
                        "success": response.status == 200,
                        "portal_id": portal_id,
                        "portal_name": portal.name,
                        "status_code": response.status,
                        "response_time_ms": response_time,
                        "test_url": test_url
                    }
        except Exception as e:
            return {
                "success": False,
                "portal_id": portal_id,
                "portal_name": portal.name,
                "error_message": str(e)
            }
    
    async def get_cache_statistics(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return await self.repository.get_cache_statistics()