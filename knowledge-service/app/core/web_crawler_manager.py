"""
网页爬虫管理器
支持URL导入、内容清洗、格式转换和向量化处理
集成LlamaIndex和markitdown框架
"""

import asyncio
import logging
import hashlib
import time
from typing import Dict, List, Any, Optional, Union
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass
from enum import Enum

import aiohttp
import requests
from bs4 import BeautifulSoup
from markitdown import MarkItDown
from sqlalchemy.orm import Session

# LlamaIndex组件
try:
    from llama_index.readers.web import SimpleWebPageReader, TrafilaturaWebReader
    from llama_index.core import Document as LlamaDocument
    from llama_index.core.node_parser import SentenceSplitter
    LLAMAINDEX_AVAILABLE = True
except ImportError:
    LLAMAINDEX_AVAILABLE = False
    print("LlamaIndex not available, using fallback implementation")

logger = logging.getLogger(__name__)


class CrawlMode(Enum):
    """爬虫模式"""
    SINGLE_URL = "single_url"           # 单个URL
    URL_LIST = "url_list"               # URL列表
    SITEMAP = "sitemap"                 # 站点地图
    DOMAIN_CRAWL = "domain_crawl"       # 域名爬取（有限深度）


class CrawlStatus(Enum):
    """爬取状态"""
    PENDING = "pending"
    CRAWLING = "crawling"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class CrawlConfig:
    """爬虫配置"""
    # 基础配置
    mode: CrawlMode = CrawlMode.SINGLE_URL
    max_pages: int = 50
    max_depth: int = 2
    concurrent_requests: int = 5
    request_delay: float = 1.0
    
    # 内容过滤
    content_filters: List[str] = None  # CSS选择器，要移除的元素
    content_selectors: List[str] = None  # CSS选择器，要保留的元素
    min_content_length: int = 100
    max_content_length: int = 100000
    
    # 文件格式
    output_format: str = "markdown"  # markdown, html, text
    include_metadata: bool = True
    extract_images: bool = False
    
    # 请求配置
    headers: Dict[str, str] = None
    timeout: int = 30
    follow_redirects: bool = True
    respect_robots_txt: bool = True
    
    # 处理配置
    use_llamaindex: bool = True
    use_trafilatura: bool = True  # 更好的内容提取
    chunk_size: int = 1000
    chunk_overlap: int = 200


@dataclass
class CrawlResult:
    """爬取结果"""
    url: str
    title: str
    content: str
    markdown_content: str
    metadata: Dict[str, Any]
    status: CrawlStatus
    error_message: Optional[str] = None
    content_hash: str = ""
    crawl_time: float = 0
    file_size: int = 0


class WebCrawlerManager:
    """网页爬虫管理器"""
    
    def __init__(self, db: Session):
        self.db = db
        self.markitdown = MarkItDown()
        self.session = None
        logger.info("Web Crawler Manager initialized")
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
    
    # ===============================
    # 主要爬取接口
    # ===============================
    
    async def crawl_urls(
        self,
        kb_id: str,
        urls: Union[str, List[str]],
        config: CrawlConfig = None
    ) -> Dict[str, Any]:
        """爬取URL列表"""
        try:
            if config is None:
                config = CrawlConfig()
            
            # 标准化URL输入
            if isinstance(urls, str):
                urls = [urls]
            
            # 根据模式处理URL
            if config.mode == CrawlMode.SITEMAP:
                urls = await self._extract_urls_from_sitemap(urls[0])
            elif config.mode == CrawlMode.DOMAIN_CRAWL:
                urls = await self._discover_urls_from_domain(urls[0], config)
            
            # 限制爬取数量
            if len(urls) > config.max_pages:
                urls = urls[:config.max_pages]
                logger.warning(f"Limited crawl to {config.max_pages} pages")
            
            # 并发爬取
            results = await self._crawl_urls_concurrently(urls, config)
            
            # 统计结果
            successful_results = [r for r in results if r.status == CrawlStatus.COMPLETED]
            failed_results = [r for r in results if r.status == CrawlStatus.FAILED]
            
            return {
                "success": True,
                "total_urls": len(urls),
                "successful_count": len(successful_results),
                "failed_count": len(failed_results),
                "results": successful_results,
                "failed_results": failed_results,
                "config": config.__dict__
            }
            
        except Exception as e:
            logger.error(f"Failed to crawl URLs: {e}")
            return {
                "success": False,
                "error": str(e),
                "total_urls": len(urls) if isinstance(urls, list) else 1,
                "successful_count": 0,
                "failed_count": 0,
                "results": [],
                "failed_results": []
            }
    
    async def _crawl_urls_concurrently(
        self,
        urls: List[str],
        config: CrawlConfig
    ) -> List[CrawlResult]:
        """并发爬取URL列表"""
        semaphore = asyncio.Semaphore(config.concurrent_requests)
        tasks = []
        
        for url in urls:
            task = self._crawl_single_url_with_semaphore(url, config, semaphore)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(CrawlResult(
                    url=urls[i],
                    title="",
                    content="",
                    markdown_content="",
                    metadata={},
                    status=CrawlStatus.FAILED,
                    error_message=str(result)
                ))
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _crawl_single_url_with_semaphore(
        self,
        url: str,
        config: CrawlConfig,
        semaphore: asyncio.Semaphore
    ) -> CrawlResult:
        """带信号量控制的单URL爬取"""
        async with semaphore:
            if config.request_delay > 0:
                await asyncio.sleep(config.request_delay)
            return await self._crawl_single_url(url, config)
    
    async def _crawl_single_url(self, url: str, config: CrawlConfig) -> CrawlResult:
        """爬取单个URL"""
        start_time = time.time()
        
        try:
            # 使用LlamaIndex读取器（如果可用且配置启用）
            if LLAMAINDEX_AVAILABLE and config.use_llamaindex:
                return await self._crawl_with_llamaindex(url, config, start_time)
            else:
                return await self._crawl_with_requests(url, config, start_time)
                
        except Exception as e:
            logger.error(f"Failed to crawl {url}: {e}")
            return CrawlResult(
                url=url,
                title="",
                content="",
                markdown_content="",
                metadata={"error": str(e)},
                status=CrawlStatus.FAILED,
                error_message=str(e),
                crawl_time=time.time() - start_time
            )
    
    async def _crawl_with_llamaindex(
        self,
        url: str,
        config: CrawlConfig,
        start_time: float
    ) -> CrawlResult:
        """使用LlamaIndex爬取URL"""
        try:
            # 选择读取器
            if config.use_trafilatura:
                reader = TrafilaturaWebReader()
            else:
                reader = SimpleWebPageReader(html_to_text=True)
            
            # 读取文档
            documents = reader.load_data([url])
            
            if not documents:
                raise Exception("No content extracted")
            
            doc = documents[0]
            content = doc.text
            title = doc.metadata.get('title', self._extract_title_from_url(url))
            
            # 清洗内容
            cleaned_content = self._clean_content(content, config)
            
            # 转换为Markdown
            markdown_content = self._convert_to_markdown(cleaned_content, url, config)
            
            # 构建元数据
            metadata = self._build_metadata(url, title, doc.metadata, config)
            
            # 计算内容哈希
            content_hash = hashlib.md5(cleaned_content.encode()).hexdigest()
            
            crawl_time = time.time() - start_time
            
            return CrawlResult(
                url=url,
                title=title,
                content=cleaned_content,
                markdown_content=markdown_content,
                metadata=metadata,
                status=CrawlStatus.COMPLETED,
                content_hash=content_hash,
                crawl_time=crawl_time,
                file_size=len(markdown_content)
            )
            
        except Exception as e:
            logger.error(f"LlamaIndex crawl failed for {url}: {e}")
            # 回退到requests方法
            return await self._crawl_with_requests(url, config, start_time)
    
    async def _crawl_with_requests(
        self,
        url: str,
        config: CrawlConfig,
        start_time: float
    ) -> CrawlResult:
        """使用requests爬取URL"""
        try:
            # 设置请求头
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            }
            
            if config.headers:
                headers.update(config.headers)
            
            # 发送请求
            if self.session:
                # 异步请求
                async with self.session.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=config.timeout),
                    allow_redirects=config.follow_redirects
                ) as response:
                    html_content = await response.text()
                    status_code = response.status
            else:
                # 同步请求（回退）
                response = requests.get(
                    url,
                    headers=headers,
                    timeout=config.timeout,
                    allow_redirects=config.follow_redirects
                )
                html_content = response.text
                status_code = response.status_code
            
            if status_code != 200:
                raise Exception(f"HTTP {status_code}")
            
            # 解析HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 提取标题
            title = self._extract_title(soup, url)
            
            # 清洗和提取内容
            content = self._extract_content(soup, config)
            
            # 转换为Markdown
            markdown_content = self._convert_to_markdown(content, url, config)
            
            # 构建元数据
            metadata = self._build_metadata(url, title, {"html_length": len(html_content)}, config)
            
            # 计算内容哈希
            content_hash = hashlib.md5(content.encode()).hexdigest()
            
            crawl_time = time.time() - start_time
            
            return CrawlResult(
                url=url,
                title=title,
                content=content,
                markdown_content=markdown_content,
                metadata=metadata,
                status=CrawlStatus.COMPLETED,
                content_hash=content_hash,
                crawl_time=crawl_time,
                file_size=len(markdown_content)
            )
            
        except Exception as e:
            logger.error(f"Requests crawl failed for {url}: {e}")
            return CrawlResult(
                url=url,
                title="",
                content="",
                markdown_content="",
                metadata={"error": str(e)},
                status=CrawlStatus.FAILED,
                error_message=str(e),
                crawl_time=time.time() - start_time
            )
    
    # ===============================
    # 内容处理方法
    # ===============================
    
    def _extract_title(self, soup: BeautifulSoup, url: str) -> str:
        """提取页面标题"""
        # 尝试多种方式提取标题
        title_selectors = [
            'title',
            'h1',
            '[property="og:title"]',
            '[name="twitter:title"]',
            '.title',
            '.page-title',
            '.article-title'
        ]
        
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                if selector == '[property="og:title"]' or selector == '[name="twitter:title"]':
                    title = element.get('content', '').strip()
                else:
                    title = element.get_text().strip()
                
                if title:
                    return title[:200]  # 限制长度
        
        # 回退到URL提取
        return self._extract_title_from_url(url)
    
    def _extract_title_from_url(self, url: str) -> str:
        """从URL提取标题"""
        try:
            parsed = urlparse(url)
            path = parsed.path.strip('/')
            if path:
                # 取路径的最后一部分
                title = path.split('/')[-1]
                # 移除文件扩展名
                if '.' in title:
                    title = title.rsplit('.', 1)[0]
                # 替换分隔符
                title = title.replace('-', ' ').replace('_', ' ')
                return title.title()
            else:
                return parsed.netloc
        except:
            return "Untitled Document"
    
    def _extract_content(self, soup: BeautifulSoup, config: CrawlConfig) -> str:
        """提取和清洗页面内容"""
        # 移除不需要的元素
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            element.decompose()
        
        # 应用自定义过滤器
        if config.content_filters:
            for selector in config.content_filters:
                for element in soup.select(selector):
                    element.decompose()
        
        # 提取主要内容
        if config.content_selectors:
            # 使用指定的选择器
            content_elements = []
            for selector in config.content_selectors:
                elements = soup.select(selector)
                content_elements.extend(elements)
        else:
            # 尝试自动识别主要内容区域
            main_selectors = [
                'main',
                'article',
                '.content',
                '.main-content',
                '.post-content',
                '.article-content',
                '#content',
                '.entry-content'
            ]
            
            content_elements = []
            for selector in main_selectors:
                elements = soup.select(selector)
                if elements:
                    content_elements = elements
                    break
            
            # 如果没找到主要内容区域，使用body
            if not content_elements:
                content_elements = [soup.body] if soup.body else [soup]
        
        # 提取文本内容
        content_parts = []
        for element in content_elements:
            if element:
                text = element.get_text(separator='\n', strip=True)
                if text:
                    content_parts.append(text)
        
        content = '\n\n'.join(content_parts)
        
        # 内容长度过滤
        if len(content) < config.min_content_length:
            raise Exception(f"Content too short: {len(content)} characters")
        
        if len(content) > config.max_content_length:
            content = content[:config.max_content_length]
            logger.warning(f"Content truncated to {config.max_content_length} characters")
        
        return content
    
    def _clean_content(self, content: str, config: CrawlConfig) -> str:
        """清洗文本内容"""
        # 移除多余的空白
        lines = content.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line:  # 跳过空行
                cleaned_lines.append(line)
        
        # 合并相邻的短行
        merged_lines = []
        current_paragraph = ""
        
        for line in cleaned_lines:
            if len(line) < 50 and current_paragraph:
                current_paragraph += " " + line
            else:
                if current_paragraph:
                    merged_lines.append(current_paragraph)
                current_paragraph = line
        
        if current_paragraph:
            merged_lines.append(current_paragraph)
        
        return '\n\n'.join(merged_lines)
    
    def _convert_to_markdown(self, content: str, url: str, config: CrawlConfig) -> str:
        """转换内容为Markdown格式"""
        if config.output_format == "text":
            return content
        elif config.output_format == "html":
            return f"<html><body>{content}</body></html>"
        
        # 转换为Markdown
        try:
            # 使用markitdown进行转换
            # 这里简化实现，实际可以更复杂
            markdown_content = content
            
            # 添加元数据头部
            if config.include_metadata:
                metadata_header = f"""---
title: {self._extract_title_from_url(url)}
source_url: {url}
crawl_date: {time.strftime('%Y-%m-%d %H:%M:%S')}
---

"""
                markdown_content = metadata_header + markdown_content
            
            return markdown_content
            
        except Exception as e:
            logger.error(f"Failed to convert to markdown: {e}")
            return content
    
    def _build_metadata(
        self,
        url: str,
        title: str,
        extracted_metadata: Dict[str, Any],
        config: CrawlConfig
    ) -> Dict[str, Any]:
        """构建文档元数据"""
        parsed_url = urlparse(url)
        
        metadata = {
            "source_type": "web_crawl",
            "url": url,
            "domain": parsed_url.netloc,
            "title": title,
            "crawl_timestamp": time.time(),
            "crawl_date": time.strftime('%Y-%m-%d %H:%M:%S'),
            "crawler_config": {
                "mode": config.mode.value,
                "use_llamaindex": config.use_llamaindex,
                "use_trafilatura": config.use_trafilatura
            }
        }
        
        # 合并提取的元数据
        metadata.update(extracted_metadata)
        
        return metadata
    
    # ===============================
    # URL发现方法
    # ===============================
    
    async def _extract_urls_from_sitemap(self, sitemap_url: str) -> List[str]:
        """从站点地图提取URL"""
        try:
            if self.session:
                async with self.session.get(sitemap_url) as response:
                    content = await response.text()
            else:
                response = requests.get(sitemap_url)
                content = response.text
            
            soup = BeautifulSoup(content, 'xml')
            urls = []
            
            # 提取URL
            for loc in soup.find_all('loc'):
                url = loc.text.strip()
                if url:
                    urls.append(url)
            
            logger.info(f"Extracted {len(urls)} URLs from sitemap")
            return urls
            
        except Exception as e:
            logger.error(f"Failed to extract URLs from sitemap {sitemap_url}: {e}")
            return []
    
    async def _discover_urls_from_domain(
        self,
        base_url: str,
        config: CrawlConfig
    ) -> List[str]:
        """从域名发现URL（有限深度爬取）"""
        try:
            discovered_urls = set([base_url])
            processed_urls = set()
            depth = 0
            
            while depth < config.max_depth and len(discovered_urls) < config.max_pages:
                current_level = discovered_urls - processed_urls
                if not current_level:
                    break
                
                new_urls = set()
                for url in current_level:
                    try:
                        if self.session:
                            async with self.session.get(url) as response:
                                html = await response.text()
                        else:
                            response = requests.get(url)
                            html = response.text
                        
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # 提取链接
                        for link in soup.find_all('a', href=True):
                            href = link['href']
                            full_url = urljoin(url, href)
                            
                            # 只处理同域名的链接
                            if urlparse(full_url).netloc == urlparse(base_url).netloc:
                                new_urls.add(full_url)
                        
                        processed_urls.add(url)
                        
                    except Exception as e:
                        logger.error(f"Failed to process {url}: {e}")
                        processed_urls.add(url)
                
                discovered_urls.update(new_urls)
                depth += 1
            
            result_urls = list(discovered_urls)[:config.max_pages]
            logger.info(f"Discovered {len(result_urls)} URLs from domain crawl")
            return result_urls
            
        except Exception as e:
            logger.error(f"Failed to discover URLs from domain {base_url}: {e}")
            return [base_url]


def get_web_crawler_manager(db: Session) -> WebCrawlerManager:
    """获取网页爬虫管理器实例"""
    return WebCrawlerManager(db)