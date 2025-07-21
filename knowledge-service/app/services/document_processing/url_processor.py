"""
URL内容抓取和处理器
使用markitdown库进行格式化处理
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse, urljoin
import aiohttp
import uuid
from datetime import datetime

try:
    from markitdown import MarkItDown
    MARKITDOWN_AVAILABLE = True
except ImportError:
    MARKITDOWN_AVAILABLE = False
    logging.warning("markitdown library not available, URL processing will be limited")

from app.schemas.knowledge_schemas import DocumentMetadata

logger = logging.getLogger(__name__)


class URLProcessor:
    """URL内容抓取和处理器"""
    
    def __init__(self):
        self.session = None
        self.markitdown = MarkItDown() if MARKITDOWN_AVAILABLE else None
        self.processed_urls = 0
        self.success_count = 0
        self.error_count = 0
        self.total_processing_time = 0.0
        
        # 支持的内容类型
        self.supported_content_types = {
            'text/html',
            'text/plain',
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/json',
            'text/markdown',
            'text/csv'
        }
        
        logger.info("URLProcessor initialized")
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60),
            headers={
                'User-Agent': 'ZZDSJ-Knowledge-Service/1.0 (URL Content Processor)'
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
    
    async def process_url(self, url: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        处理单个URL
        
        Args:
            url: 要处理的URL
            metadata: 额外的元数据
            
        Returns:
            处理结果字典
        """
        start_time = time.time()
        
        try:
            # 验证URL格式
            parsed_url = urlparse(url)
            if not parsed_url.scheme or not parsed_url.netloc:
                return {
                    "success": False,
                    "error": f"Invalid URL format: {url}",
                    "url": url
                }
            
            # 获取URL内容
            content_result = await self._fetch_url_content(url)
            if not content_result["success"]:
                return content_result
            
            # 使用markitdown处理内容
            processed_result = await self._process_with_markitdown(
                content_result["content"],
                content_result["content_type"],
                url
            )
            
            if not processed_result["success"]:
                return processed_result
            
            # 构建文档元数据
            doc_metadata = DocumentMetadata(
                id=str(uuid.uuid4()),
                filename=self._extract_filename_from_url(url),
                file_size=len(content_result["content"]),
                file_type=self._get_file_type_from_content_type(content_result["content_type"]),
                mime_type=content_result["content_type"],
                source_type="url",
                source_path=url,
                upload_time=datetime.now(),
                processing_status="completed",
                metadata={
                    "url": url,
                    "title": processed_result.get("title", ""),
                    "content_type": content_result["content_type"],
                    "content_length": len(processed_result["content"]),
                    "extracted_at": datetime.now().isoformat(),
                    **(metadata or {})
                }
            )
            
            processing_time = time.time() - start_time
            self.processed_urls += 1
            self.success_count += 1
            self.total_processing_time += processing_time
            
            logger.info(f"Successfully processed URL: {url} in {processing_time:.3f}s")
            
            return {
                "success": True,
                "content": processed_result["content"],
                "metadata": doc_metadata.dict(),
                "processing_time": processing_time,
                "original_content_type": content_result["content_type"],
                "processed_format": "markdown"
            }
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.error_count += 1
            
            logger.error(f"Failed to process URL {url}: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "url": url,
                "processing_time": processing_time
            }
    
    async def process_urls_batch(self, urls: List[str], metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        批量处理多个URL
        
        Args:
            urls: URL列表
            metadata: 共同的元数据
            
        Returns:
            批量处理结果
        """
        start_time = time.time()
        
        try:
            # 并发处理URL（限制并发数）
            semaphore = asyncio.Semaphore(5)  # 最多5个并发请求
            
            async def process_single_url(url):
                async with semaphore:
                    return await self.process_url(url, metadata)
            
            tasks = [process_single_url(url) for url in urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 统计结果
            successful_results = []
            failed_results = []
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    failed_results.append({
                        "url": urls[i],
                        "error": str(result)
                    })
                elif result.get("success"):
                    successful_results.append(result)
                else:
                    failed_results.append(result)
            
            processing_time = time.time() - start_time
            
            logger.info(
                f"Batch URL processing completed: {len(successful_results)} success, "
                f"{len(failed_results)} failed, {processing_time:.3f}s"
            )
            
            return {
                "success": True,
                "total_urls": len(urls),
                "successful_count": len(successful_results),
                "failed_count": len(failed_results),
                "successful_results": successful_results,
                "failed_results": failed_results,
                "processing_time": processing_time
            }
            
        except Exception as e:
            logger.error(f"Batch URL processing failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "total_urls": len(urls)
            }
    
    async def _fetch_url_content(self, url: str) -> Dict[str, Any]:
        """
        获取URL内容
        
        Args:
            url: 目标URL
            
        Returns:
            内容获取结果
        """
        try:
            if not self.session:
                raise RuntimeError("URLProcessor must be used as async context manager")
            
            async with self.session.get(url) as response:
                # 检查响应状态
                if response.status != 200:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status}: {response.reason}",
                        "url": url
                    }
                
                # 检查内容类型
                content_type = response.headers.get('content-type', '').split(';')[0].strip()
                if content_type not in self.supported_content_types:
                    return {
                        "success": False,
                        "error": f"Unsupported content type: {content_type}",
                        "url": url
                    }
                
                # 读取内容
                if content_type.startswith('text/') or content_type == 'application/json':
                    content = await response.text()
                else:
                    content = await response.read()
                
                return {
                    "success": True,
                    "content": content,
                    "content_type": content_type,
                    "url": url
                }
                
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "Request timeout",
                "url": url
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "url": url
            }
    
    async def _process_with_markitdown(self, content: Any, content_type: str, url: str) -> Dict[str, Any]:
        """
        使用markitdown处理内容
        
        Args:
            content: 原始内容
            content_type: 内容类型
            url: 源URL
            
        Returns:
            处理结果
        """
        try:
            if not MARKITDOWN_AVAILABLE:
                # 如果markitdown不可用，进行简单的文本处理
                return await self._fallback_text_processing(content, content_type)
            
            # 根据内容类型选择处理方式
            if content_type == 'text/html':
                # HTML内容处理
                result = self.markitdown.convert(content, file_extension='.html')
            elif content_type == 'application/pdf':
                # PDF内容处理
                result = self.markitdown.convert(content, file_extension='.pdf')
            elif content_type in ['application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
                # Word文档处理
                ext = '.docx' if 'openxml' in content_type else '.doc'
                result = self.markitdown.convert(content, file_extension=ext)
            elif content_type in ['application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']:
                # Excel文档处理
                ext = '.xlsx' if 'openxml' in content_type else '.xls'
                result = self.markitdown.convert(content, file_extension=ext)
            elif content_type == 'text/csv':
                # CSV文件处理
                result = self.markitdown.convert(content, file_extension='.csv')
            elif content_type == 'application/json':
                # JSON文件处理
                result = self.markitdown.convert(content, file_extension='.json')
            else:
                # 纯文本或其他格式
                result = self.markitdown.convert(content, file_extension='.txt')
            
            # 提取标题（如果有）
            title = self._extract_title_from_markdown(result.text_content)
            
            return {
                "success": True,
                "content": result.text_content,
                "title": title,
                "format": "markdown"
            }
            
        except Exception as e:
            logger.error(f"markitdown processing failed for {url}: {e}")
            # 回退到简单文本处理
            return await self._fallback_text_processing(content, content_type)
    
    async def _fallback_text_processing(self, content: Any, content_type: str) -> Dict[str, Any]:
        """
        回退的文本处理方法
        
        Args:
            content: 原始内容
            content_type: 内容类型
            
        Returns:
            处理结果
        """
        try:
            if content_type == 'text/html':
                # 简单的HTML标签清理
                import re
                text_content = re.sub(r'<[^>]+>', '', str(content))
                text_content = re.sub(r'\s+', ' ', text_content).strip()
            elif isinstance(content, bytes):
                # 尝试解码字节内容
                try:
                    text_content = content.decode('utf-8')
                except UnicodeDecodeError:
                    text_content = content.decode('utf-8', errors='ignore')
            else:
                text_content = str(content)
            
            return {
                "success": True,
                "content": text_content,
                "title": "",
                "format": "text"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Fallback text processing failed: {e}"
            }
    
    def _extract_filename_from_url(self, url: str) -> str:
        """从URL提取文件名"""
        try:
            parsed = urlparse(url)
            path = parsed.path
            if path and path != '/':
                filename = path.split('/')[-1]
                if filename and '.' in filename:
                    return filename
            
            # 如果无法提取文件名，使用域名
            domain = parsed.netloc.replace('www.', '')
            return f"{domain}_content.txt"
            
        except Exception:
            return "url_content.txt"
    
    def _get_file_type_from_content_type(self, content_type: str) -> str:
        """从内容类型获取文件类型"""
        content_type_map = {
            'text/html': 'html',
            'text/plain': 'text',
            'application/pdf': 'pdf',
            'application/msword': 'doc',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
            'application/vnd.ms-excel': 'xls',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
            'application/json': 'json',
            'text/markdown': 'md',
            'text/csv': 'csv'
        }
        
        return content_type_map.get(content_type, 'unknown')
    
    def _extract_title_from_markdown(self, markdown_content: str) -> str:
        """从Markdown内容中提取标题"""
        try:
            lines = markdown_content.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('# '):
                    return line[2:].strip()
                elif line.startswith('## '):
                    return line[3:].strip()
            
            # 如果没有找到标题，返回第一行非空内容的前50个字符
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    return line[:50] + ('...' if len(line) > 50 else '')
            
            return ""
            
        except Exception:
            return ""
    
    def get_stats(self) -> Dict[str, Any]:
        """获取处理统计信息"""
        avg_processing_time = (
            self.total_processing_time / self.processed_urls 
            if self.processed_urls > 0 else 0
        )
        
        success_rate = (
            self.success_count / self.processed_urls 
            if self.processed_urls > 0 else 0
        )
        
        return {
            "total_processed": self.processed_urls,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "success_rate": success_rate,
            "avg_processing_time": avg_processing_time,
            "total_processing_time": self.total_processing_time,
            "markitdown_available": MARKITDOWN_AVAILABLE,
            "supported_content_types": list(self.supported_content_types)
        }


# 全局URL处理器实例
_url_processor = None

def get_url_processor() -> URLProcessor:
    """获取URL处理器实例"""
    global _url_processor
    if _url_processor is None:
        _url_processor = URLProcessor()
    return _url_processor