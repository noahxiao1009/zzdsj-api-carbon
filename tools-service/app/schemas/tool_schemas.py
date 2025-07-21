"""
工具服务数据模型定义
"""

from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


class ToolType(str, Enum):
    """工具类型枚举"""
    WEBAGENT = "webagent"
    SCRAPERR = "scraperr"


class ToolAction(str, Enum):
    """工具操作枚举"""
    # WebAgent操作
    SEARCH = "search"
    ANALYZE = "analyze"
    
    # Scraperr操作
    CRAWL = "crawl"
    SPIDER = "spider"
    LIST_JOBS = "list_jobs"
    GET_JOB = "get_job"
    DELETE_JOB = "delete_job"


class ToolRequest(BaseModel):
    """工具请求模型"""
    tool_name: ToolType = Field(..., description="工具名称")
    action: ToolAction = Field(..., description="执行操作")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="操作参数")
    context: Optional[Dict[str, Any]] = Field(None, description="上下文信息")
    
    class Config:
        schema_extra = {
            "example": {
                "tool_name": "webagent",
                "action": "search",
                "parameters": {
                    "query": "人工智能最新发展",
                    "engine": "google",
                    "max_results": 10
                },
                "context": {
                    "user_id": "user_123",
                    "session_id": "session_456"
                }
            }
        }


class ToolResponse(BaseModel):
    """工具响应模型"""
    success: bool = Field(..., description="是否成功")
    data: Any = Field(None, description="返回数据")
    message: str = Field(..., description="响应消息")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")
    execution_time: Optional[float] = Field(None, description="执行时间(秒)")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "results": [
                        {
                            "title": "AI发展报告",
                            "url": "https://example.com",
                            "snippet": "人工智能技术快速发展..."
                        }
                    ]
                },
                "message": "搜索完成",
                "metadata": {
                    "query": "人工智能最新发展",
                    "total_results": 1,
                    "engine": "google"
                },
                "execution_time": 2.35
            }
        }


# ========== WebAgent 相关模型 ==========

class SearchEngine(str, Enum):
    """搜索引擎枚举"""
    GOOGLE = "google"
    BING = "bing"
    BAIDU = "baidu"
    DUCKDUCKGO = "duckduckgo"


class WebAgentSearchRequest(BaseModel):
    """WebAgent搜索请求"""
    query: str = Field(..., description="搜索查询", min_length=1, max_length=500)
    engine: SearchEngine = Field(SearchEngine.GOOGLE, description="搜索引擎")
    max_results: int = Field(10, description="最大结果数", ge=1, le=50)
    language: str = Field("zh-CN", description="搜索语言")
    safe_search: bool = Field(True, description="安全搜索")
    
    class Config:
        schema_extra = {
            "example": {
                "query": "Python机器学习框架对比",
                "engine": "google",
                "max_results": 15,
                "language": "zh-CN",
                "safe_search": True
            }
        }


class WebAgentAnalyzeRequest(BaseModel):
    """WebAgent分析请求"""
    content: str = Field(..., description="待分析内容")
    analysis_type: str = Field("summary", description="分析类型")
    criteria: Optional[Dict[str, Any]] = Field(None, description="分析标准")


class SearchResult(BaseModel):
    """搜索结果模型"""
    title: str = Field(..., description="标题")
    url: str = Field(..., description="链接")
    snippet: str = Field(..., description="摘要")
    position: int = Field(..., description="排名位置")
    domain: str = Field(..., description="域名")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")


# ========== Scraperr 相关模型 ==========

class ScrapingRule(BaseModel):
    """爬取规则模型"""
    selector: str = Field(..., description="CSS选择器或XPath")
    attribute: Optional[str] = Field(None, description="提取属性")
    extract_type: str = Field("text", description="提取类型: text, html, attribute, href")
    multiple: bool = Field(False, description="是否提取多个")
    required: bool = Field(False, description="是否必需")


class ScraperJob(BaseModel):
    """爬取任务模型"""
    job_id: Optional[str] = Field(None, description="任务ID")
    name: str = Field(..., description="任务名称")
    urls: List[str] = Field(..., description="目标URL列表")
    rules: Dict[str, ScrapingRule] = Field(..., description="爬取规则")
    options: Optional[Dict[str, Any]] = Field(default_factory=dict, description="爬取选项")
    status: str = Field("pending", description="任务状态")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    
    class Config:
        schema_extra = {
            "example": {
                "name": "新闻标题爬取",
                "urls": ["https://news.example.com"],
                "rules": {
                    "title": {
                        "selector": "h1.title",
                        "extract_type": "text",
                        "required": True
                    },
                    "content": {
                        "selector": ".content",
                        "extract_type": "text",
                        "required": False
                    }
                },
                "options": {
                    "delay": 1,
                    "timeout": 30,
                    "user_agent": "Mozilla/5.0..."
                }
            }
        }


class CrawlRequest(BaseModel):
    """单页爬取请求"""
    url: str = Field(..., description="目标URL")
    rules: Dict[str, ScrapingRule] = Field(..., description="爬取规则")
    options: Optional[Dict[str, Any]] = Field(default_factory=dict, description="爬取选项")


class SpiderRequest(BaseModel):
    """站点爬虫请求"""
    start_url: str = Field(..., description="起始URL")
    domain: Optional[str] = Field(None, description="限制域名")
    max_pages: int = Field(100, description="最大页面数", ge=1, le=1000)
    rules: Dict[str, ScrapingRule] = Field(..., description="爬取规则")
    link_selector: str = Field("a[href]", description="链接选择器")
    options: Optional[Dict[str, Any]] = Field(default_factory=dict, description="爬取选项")


class CrawlResult(BaseModel):
    """爬取结果模型"""
    url: str = Field(..., description="页面URL")
    data: Dict[str, Any] = Field(..., description="提取的数据")
    success: bool = Field(..., description="是否成功")
    error: Optional[str] = Field(None, description="错误信息")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")
    execution_time: float = Field(..., description="执行时间")


# ========== 工具管理相关模型 ==========

class ToolInfo(BaseModel):
    """工具信息模型"""
    name: str = Field(..., description="工具名称")
    type: ToolType = Field(..., description="工具类型")
    description: str = Field(..., description="工具描述")
    version: str = Field(..., description="版本号")
    status: str = Field(..., description="状态")
    supported_actions: List[str] = Field(..., description="支持的操作")
    schema: Dict[str, Any] = Field(..., description="参数模式")


class ToolStatus(BaseModel):
    """工具状态模型"""
    tool_name: str = Field(..., description="工具名称")
    status: str = Field(..., description="状态: active, inactive, error")
    last_check: datetime = Field(..., description="最后检查时间")
    error_message: Optional[str] = Field(None, description="错误信息")
    metrics: Optional[Dict[str, Any]] = Field(None, description="性能指标")


class ToolMetrics(BaseModel):
    """工具性能指标"""
    tool_name: str = Field(..., description="工具名称")
    total_calls: int = Field(0, description="总调用次数")
    success_calls: int = Field(0, description="成功调用次数")
    error_calls: int = Field(0, description="错误调用次数")
    avg_response_time: float = Field(0.0, description="平均响应时间")
    last_24h_calls: int = Field(0, description="24小时内调用次数")
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_calls == 0:
            return 0.0
        return (self.success_calls / self.total_calls) * 100


# ========== 批量操作模型 ==========

class BatchToolRequest(BaseModel):
    """批量工具请求"""
    requests: List[ToolRequest] = Field(..., description="请求列表")
    parallel: bool = Field(False, description="是否并行执行")
    max_workers: int = Field(5, description="最大并发数")


class BatchToolResponse(BaseModel):
    """批量工具响应"""
    results: List[ToolResponse] = Field(..., description="结果列表")
    summary: Dict[str, Any] = Field(..., description="执行摘要")
    total_time: float = Field(..., description="总执行时间")