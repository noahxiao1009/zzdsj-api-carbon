"""
Scraperr工具包装器
基于开源Scraperr项目的集成
"""

import os
import sys
import asyncio
import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

# 添加Scraperr路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../Scraperr/api/backend'))

from app.schemas.tool_schemas import ToolRequest, ToolResponse
from app.core.logger import logger

try:
    from job.models.job import Element
    from job.models.job_options import JobOptions
    from schemas.job import Job
    from job import insert
    from database.common import query
    SCRAPERR_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Scraperr依赖导入失败: {e}")
    SCRAPERR_AVAILABLE = False


class ScrapeerrTool:
    """Scraperr工具包装器"""
    
    def __init__(self):
        self.name = "scraperr"
        self.version = "1.0.0"
        self.description = "自托管网页爬取工具"
        self._initialized = False
        
        # 配置
        self.config = {
            'user_email': os.getenv('SCRAPERR_USER_EMAIL', 'admin@tools.local'),
            'spider_domain': os.getenv('SCRAPERR_SPIDER_DOMAIN', 'false').lower() == 'true',
            'download_media': os.getenv('SCRAPERR_DOWNLOAD_MEDIA', 'false').lower() == 'true',
            'max_concurrent': int(os.getenv('SCRAPERR_MAX_CONCURRENT', '3')),
        }
    
    async def initialize(self):
        """初始化Scraperr工具"""
        if self._initialized:
            return
        
        if not SCRAPERR_AVAILABLE:
            logger.error("Scraperr依赖不可用，无法初始化")
            return
        
        logger.info("初始化Scraperr工具...")
        
        try:
            # 检查数据库连接等基础设施
            self._initialized = True
            logger.info("Scraperr工具初始化成功")
            
        except Exception as e:
            logger.error(f"Scraperr工具初始化失败: {e}", exc_info=True)
            raise
    
    async def execute(self, request: ToolRequest) -> ToolResponse:
        """执行工具调用"""
        if not self._initialized:
            await self.initialize()
        
        if not SCRAPERR_AVAILABLE:
            return ToolResponse(
                success=False,
                data=None,
                message="Scraperr依赖不可用"
            )
        
        action = request.action
        params = request.parameters
        
        try:
            if action == "scrape":
                result = await self._scrape(params)
            elif action == "list_jobs":
                result = await self._list_jobs(params)
            elif action == "get_job":
                result = await self._get_job(params)
            elif action == "delete_job":
                result = await self._delete_job(params)
            else:
                raise ValueError(f"不支持的操作: {action}")
            
            return ToolResponse(
                success=True,
                data=result,
                message="执行成功",
                metadata={
                    "action": action,
                    "tool": self.name,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Scraperr工具执行失败: {e}", exc_info=True)
            return ToolResponse(
                success=False,
                data=None,
                message=str(e)
            )
    
    async def _scrape(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行网页爬取任务"""
        url = params.get("url", "")
        elements = params.get("elements", [])
        spider_domain = params.get("spider_domain", self.config['spider_domain'])
        download_media = params.get("download_media", self.config['download_media'])
        custom_headers = params.get("custom_headers", {})
        
        if not url:
            raise ValueError("URL不能为空")
        
        if not elements:
            # 默认提取常见元素
            elements = [
                {"name": "title", "xpath": "//title/text()"},
                {"name": "headings", "xpath": "//h1 | //h2 | //h3"},
                {"name": "paragraphs", "xpath": "//p"},
                {"name": "links", "xpath": "//a[@href]"}
            ]
        
        logger.info(f"Scraperr爬取: {url}")
        
        try:
            # 创建作业配置
            job_id = uuid.uuid4().hex
            
            # 构建元素列表
            scraperr_elements = []
            for elem in elements:
                if isinstance(elem, dict):
                    scraperr_elements.append(Element(
                        name=elem.get('name', ''),
                        xpath=elem.get('xpath', ''),
                        url=elem.get('url')
                    ))
                elif isinstance(elem, str):
                    # 简单字符串，假设是元素名称，使用默认xpath
                    default_xpaths = {
                        'title': '//title/text()',
                        'headings': '//h1 | //h2 | //h3',
                        'paragraphs': '//p',
                        'links': '//a[@href]',
                        'images': '//img[@src]'
                    }
                    xpath = default_xpaths.get(elem, f'//*[contains(@class, "{elem}")]')
                    scraperr_elements.append(Element(name=elem, xpath=xpath))
            
            # 创建作业选项
            job_options = JobOptions(
                spider=spider_domain,
                download_media=download_media,
                custom_headers=custom_headers
            )
            
            # 创建作业
            job = Job(
                id=job_id,
                url=url,
                elements=scraperr_elements,
                user=self.config['user_email'],
                time_created=datetime.now(),
                job_options=job_options,
                status="Queued"
            )
            
            # 提交作业
            job_dict = job.model_dump()
            await insert(job_dict)
            
            return {
                "job_id": job_id,
                "url": url,
                "status": "Queued",
                "elements_count": len(scraperr_elements),
                "spider_domain": spider_domain,
                "download_media": download_media,
                "timestamp": datetime.now().isoformat(),
                "message": "爬取任务已提交，正在处理中"
            }
            
        except Exception as e:
            logger.error(f"Scraperr爬取失败: {e}")
            return {
                "url": url,
                "error": str(e),
                "status": "Failed"
            }
    
    async def _list_jobs(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """列出爬取任务"""
        try:
            user_email = params.get("user_email", self.config['user_email'])
            limit = params.get("limit", 50)
            
            job_query = "SELECT * FROM jobs WHERE user = ? ORDER BY time_created DESC LIMIT ?"
            results = query(job_query, (user_email, limit))
            
            return {
                "jobs": results,
                "total": len(results),
                "user": user_email,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"列出任务失败: {e}")
            return {
                "jobs": [],
                "error": str(e)
            }
    
    async def _get_job(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """获取特定任务详情"""
        job_id = params.get("job_id", "")
        
        if not job_id:
            raise ValueError("任务ID不能为空")
        
        try:
            user_email = params.get("user_email", self.config['user_email'])
            job_query = "SELECT * FROM jobs WHERE id = ? AND user = ?"
            results = query(job_query, (job_id, user_email))
            
            if not results:
                return {
                    "job_id": job_id,
                    "found": False,
                    "message": "任务不存在或无权限访问"
                }
            
            job_data = results[0]
            return {
                "job_id": job_id,
                "found": True,
                "job": job_data,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取任务失败: {e}")
            return {
                "job_id": job_id,
                "found": False,
                "error": str(e)
            }
    
    async def _delete_job(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """删除爬取任务"""
        job_ids = params.get("job_ids", [])
        
        if not job_ids:
            raise ValueError("任务ID列表不能为空")
        
        if isinstance(job_ids, str):
            job_ids = [job_ids]
        
        try:
            from job import delete_jobs
            result = await delete_jobs(job_ids)
            
            return {
                "job_ids": job_ids,
                "deleted": result,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"删除任务失败: {e}")
            return {
                "job_ids": job_ids,
                "deleted": False,
                "error": str(e)
            }
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            if not SCRAPERR_AVAILABLE:
                return False
            
            # 检查数据库连接
            try:
                test_query = "SELECT 1"
                query(test_query, ())
                return self._initialized
            except Exception:
                return False
            
        except Exception as e:
            logger.error(f"Scraperr健康检查失败: {e}")
            return False
    
    async def get_schema(self) -> Dict[str, Any]:
        """获取工具模式"""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "available": SCRAPERR_AVAILABLE,
            "actions": {
                "scrape": {
                    "description": "提交网页爬取任务",
                    "parameters": {
                        "url": {
                            "type": "string",
                            "required": True,
                            "description": "目标URL"
                        },
                        "elements": {
                            "type": "array",
                            "required": False,
                            "description": "要提取的元素列表，每个元素包含name和xpath"
                        },
                        "spider_domain": {
                            "type": "boolean",
                            "default": False,
                            "description": "是否爬取整个域名"
                        },
                        "download_media": {
                            "type": "boolean",
                            "default": False,
                            "description": "是否下载媒体文件"
                        },
                        "custom_headers": {
                            "type": "object",
                            "default": {},
                            "description": "自定义请求头"
                        }
                    }
                },
                "list_jobs": {
                    "description": "列出爬取任务",
                    "parameters": {
                        "user_email": {
                            "type": "string",
                            "required": False,
                            "description": "用户邮箱"
                        },
                        "limit": {
                            "type": "integer",
                            "default": 50,
                            "description": "返回任务数量限制"
                        }
                    }
                },
                "get_job": {
                    "description": "获取任务详情",
                    "parameters": {
                        "job_id": {
                            "type": "string",
                            "required": True,
                            "description": "任务ID"
                        },
                        "user_email": {
                            "type": "string",
                            "required": False,
                            "description": "用户邮箱"
                        }
                    }
                },
                "delete_job": {
                    "description": "删除任务",
                    "parameters": {
                        "job_ids": {
                            "type": "array",
                            "required": True,
                            "description": "要删除的任务ID列表"
                        }
                    }
                }
            },
            "requirements": {
                "database": "MongoDB或SQLite数据库连接"
            },
            "configuration": {
                "user_email": self.config['user_email'],
                "spider_domain": self.config['spider_domain'],
                "download_media": self.config['download_media'],
                "max_concurrent": self.config['max_concurrent']
            }
        }
    
    async def cleanup(self):
        """清理资源"""
        self._initialized = False
        logger.info("Scraperr工具清理完成")