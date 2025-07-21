"""
WebAgent工具包装器
基于阿里巴巴WebSailor项目的集成
"""

import os
import sys
import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

# 添加WebSailor路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../WebAgent/WebSailor/src'))

from app.schemas.tool_schemas import ToolRequest, ToolResponse
from app.core.logger import logger

try:
    from tool_search import Search
    from tool_visit import Visit
    from react_agent import MultiTurnReactAgent
    from qwen_agent.tools import BaseTool
    WEBAGENT_AVAILABLE = True
except ImportError as e:
    logger.warning(f"WebSailor依赖导入失败: {e}")
    WEBAGENT_AVAILABLE = False


class WebAgentTool:
    """WebSailor工具包装器"""
    
    def __init__(self):
        self.name = "websailor"
        self.version = "1.0.0"
        self.description = "阿里巴巴WebSailor智能搜索工具"
        self._initialized = False
        self.search_tool = None
        self.visit_tool = None
        
        # API配置
        self.api_keys = {
            'serper_key': os.getenv('GOOGLE_SEARCH_KEY', ''),
            'jina_keys': os.getenv('JINA_API_KEYS', '').split(',') if os.getenv('JINA_API_KEYS') else [],
            'dashscope_key': os.getenv('DASHSCOPE_API_KEY', '')
        }
    
    async def initialize(self):
        """初始化WebSailor工具"""
        if self._initialized:
            return
        
        if not WEBAGENT_AVAILABLE:
            logger.error("WebSailor依赖不可用，无法初始化")
            return
        
        logger.info("初始化WebSailor工具...")
        
        try:
            # 检查API密钥
            missing_keys = []
            if not self.api_keys['serper_key']:
                missing_keys.append('GOOGLE_SEARCH_KEY')
            if not self.api_keys['jina_keys']:
                missing_keys.append('JINA_API_KEYS')
            
            if missing_keys:
                logger.warning(f"缺少API密钥: {missing_keys}")
            
            # 设置环境变量供WebSailor使用
            if self.api_keys['serper_key']:
                os.environ['GOOGLE_SEARCH_KEY'] = self.api_keys['serper_key']
            if self.api_keys['jina_keys']:
                os.environ['JINA_API_KEYS'] = ','.join(self.api_keys['jina_keys'])
            
            # 初始化工具
            if self.api_keys['serper_key']:
                self.search_tool = Search()
            if self.api_keys['jina_keys']:
                self.visit_tool = Visit()
            
            self._initialized = True
            logger.info("WebSailor工具初始化成功")
            
        except Exception as e:
            logger.error(f"WebSailor工具初始化失败: {e}", exc_info=True)
            raise
    
    
    async def execute(self, request: ToolRequest) -> ToolResponse:
        """执行工具调用"""
        if not self._initialized:
            await self.initialize()
        
        if not WEBAGENT_AVAILABLE:
            return ToolResponse(
                success=False,
                data=None,
                message="WebSailor依赖不可用"
            )
        
        action = request.action
        params = request.parameters
        
        try:
            if action == "search":
                result = await self._search(params)
            elif action == "visit":
                result = await self._visit(params)
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
            logger.error(f"WebSailor工具执行失败: {e}", exc_info=True)
            return ToolResponse(
                success=False,
                data=None,
                message=str(e)
            )
    
    async def _search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行搜索"""
        query = params.get("query", "")
        
        if not query:
            raise ValueError("搜索查询不能为空")
        
        logger.info(f"WebSailor搜索: {query}")
        
        if not self.search_tool:
            return {
                "query": query,
                "results": "",
                "message": "搜索工具未初始化或缺少API密钥"
            }
        
        try:
            # 使用WebSailor的Search工具
            search_params = {"query": [query] if isinstance(query, str) else query}
            results = self.search_tool.call(search_params)
            
            return {
                "query": query,
                "results": results,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"WebSailor搜索失败: {e}")
            return {
                "query": query,
                "results": "",
                "error": str(e)
            }
    
    async def _visit(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """访问网页"""
        url = params.get("url", "")
        goal = params.get("goal", "提取网页内容")
        
        if not url:
            raise ValueError("URL不能为空")
        
        logger.info(f"WebSailor访问网页: {url}")
        
        if not self.visit_tool:
            return {
                "url": url,
                "content": "",
                "message": "访问工具未初始化或缺少API密钥"
            }
        
        try:
            # 使用WebSailor的Visit工具
            visit_params = {"url": url, "goal": goal}
            content = self.visit_tool.call(visit_params)
            
            return {
                "url": url,
                "goal": goal,
                "content": content,
                "content_length": len(content),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"WebSailor访问网页失败: {e}")
            return {
                "url": url,
                "content": "",
                "error": str(e)
            }
    
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            if not WEBAGENT_AVAILABLE:
                return False
            
            # 检查基本配置
            has_any_key = self.api_keys['serper_key'] or bool(self.api_keys['jina_keys'])
            if not has_any_key:
                logger.warning("所有API密钥都缺失")
                return False
            
            return self._initialized
            
        except Exception as e:
            logger.error(f"WebSailor健康检查失败: {e}")
            return False
    
    async def get_schema(self) -> Dict[str, Any]:
        """获取工具模式"""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "available": WEBAGENT_AVAILABLE,
            "actions": {
                "search": {
                    "description": "使用WebSailor执行智能搜索",
                    "parameters": {
                        "query": {
                            "type": "string",
                            "required": True,
                            "description": "搜索查询"
                        }
                    }
                },
                "visit": {
                    "description": "访问并提取网页内容",
                    "parameters": {
                        "url": {
                            "type": "string",
                            "required": True,
                            "description": "目标URL"
                        },
                        "goal": {
                            "type": "string",
                            "required": False,
                            "default": "提取网页内容",
                            "description": "访问目标"
                        }
                    }
                }
            },
            "requirements": {
                "serper_api_key": "Google搜索API密钥",
                "jina_api_keys": "Jina Reader API密钥列表（逗号分隔）"
            },
            "configuration": {
                "serper_configured": bool(self.api_keys['serper_key']),
                "jina_configured": bool(self.api_keys['jina_keys'])
            }
        }
    
    async def cleanup(self):
        """清理资源"""
        self.search_tool = None
        self.visit_tool = None
        self._initialized = False
        logger.info("WebSailor工具清理完成")