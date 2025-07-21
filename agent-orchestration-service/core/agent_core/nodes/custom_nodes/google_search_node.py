"""
Tavily搜索工具实现 - 使用Tavily API
基于BaseToolNode的正确实现方式
"""

import logging
import asyncio
import aiohttp
import json
import os
from typing import Dict, Any, List
from ...framework.tool_registry import tool_registry
from ..base_tool_node import BaseToolNode

logger = logging.getLogger(__name__)

# Tavily API配置
TAVILY_API_KEY = "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"
TAVILY_API_URL = "https://api.tavily.com/search"


@tool_registry(
    toolset_name="G",
    name="search_tool",
    description="搜索网络信息，获取最新的搜索结果。适用于查找一般信息、最新发展或不同观点。",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索查询词，应该具体而精确"
            },
            "max_results": {
                "type": "integer",
                "description": "最大结果数量，默认为5",
                "default": 5
            }
        },
        "required": ["query"]
    },
    default_knowledge_item_type="SEARCH_RESULTS_LIST",
)
class GoogleSearchNode(BaseToolNode):
    """
    Google搜索工具节点，使用Tavily API作为后端实现
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.api_key = TAVILY_API_KEY
        if not self.api_key:
            logger.warning("Tavily API密钥未配置")
    
    async def _fetch_search_results(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """执行Tavily搜索查询"""
        logger.debug("executing_tavily_search", extra={"query": query, "max_results": max_results})
        
        search_results = []
        success_flag = False
        error_message = None
        
        if not self.api_key:
            error_message = "Tavily API密钥未配置"
            return {
                "query": query,
                "success": success_flag,
                "results_summary": f"[搜索失败: {error_message}]",
                "results": search_results,
                "error_message": error_message
            }
        
        try:
            logger.info("starting_tavily_search", extra={"query": query, "max_results": max_results})
            
            # 构造Tavily API请求
            payload = {
                "api_key": self.api_key,
                "query": query,
                "search_depth": "advanced",  # 使用高级搜索模式
                "include_answer": False,     # 暂时不需要AI总结
                "include_raw_content": True, # 包含完整内容
                "max_results": min(max_results, 10),  # Tavily限制最大10个结果
                "include_images": False,     # 不需要图片
                "include_domains": [],       # 不限制域名
                "exclude_domains": []        # 不排除域名
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    TAVILY_API_URL,
                    json=payload,
                    headers={
                        "Content-Type": "application/json"
                    }
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # 转换Tavily响应格式为期望的格式
                        results = data.get("results", [])
                        for result in results:
                            search_results.append({
                                "title": result.get("title", ""),
                                "url": result.get("url", ""),
                                "snippet": result.get("content", ""),
                                "content": result.get("content", ""),
                                "score": result.get("score", 0.0)
                            })
                        
                        success_flag = True
                        logger.info("tavily_search_completed", extra={
                            "query": query, 
                            "results_count": len(search_results),
                            "response_time": data.get("response_time", "unknown")
                        })
                        
                    else:
                        error_text = await response.text()
                        error_message = f"Tavily API错误 (状态码: {response.status}): {error_text}"
                        logger.error("tavily_api_error", extra={
                            "query": query,
                            "status_code": response.status,
                            "error": error_text
                        })
                
        except aiohttp.ClientError as e:
            error_message = f"网络请求失败: {str(e)}"
            logger.error("tavily_network_error", extra={
                "query": query, 
                "error": error_message
            }, exc_info=True)
        except json.JSONDecodeError as e:
            error_message = f"响应解析失败: {str(e)}"
            logger.error("tavily_json_error", extra={
                "query": query, 
                "error": error_message
            }, exc_info=True)
        except Exception as e:
            error_message = f"搜索失败: {str(e)}"
            logger.error("tavily_search_error", extra={
                "query": query, 
                "error": error_message
            }, exc_info=True)
        
        return {
            "query": query,
            "success": success_flag,
            "results_summary": f"找到 {len(search_results)} 个结果: '{query}'" if success_flag else f"[搜索失败: {error_message}]",
            "results": search_results,
            "error_message": error_message if not success_flag else None
        }
    
    async def exec_async(self, prep_res: dict) -> dict:
        """
        核心执行逻辑：
        1. 从prep_res获取参数
        2. 检查知识库中是否有缓存结果
        3. 执行Tavily搜索查询
        4. 构造返回结果
        """
        try:
            tool_params = prep_res.get("tool_params", {})
            shared_context = prep_res.get("shared_context", {})
            
            query = tool_params.get("query", "")
            max_results = tool_params.get("max_results", 5)
            
            if not query:
                return {
                    "status": "error",
                    "error_message": "搜索查询不能为空",
                    "payload": {"error": "搜索查询不能为空"}
                }
            
            logger.info("tavily_search_tool_exec_start", extra={
                "query": query, 
                "max_results": max_results,
                "api_key_configured": bool(self.api_key)
            })
            
            # 检查知识库缓存
            kb = shared_context.get('refs', {}).get('run', {}).get('runtime', {}).get("knowledge_base")
            cached_result = None
            
            if kb:
                synthetic_uri = f"tavily_search_query://{query}"
                existing_item = await kb.get_item_by_uri(synthetic_uri)
                if existing_item:
                    logger.info("search_query_found_in_kb", extra={"query": query})
                    cached_results = existing_item.get("content", [])
                    cached_result = {
                        "query": query,
                        "success": True,
                        "results_summary": f"找到 {len(cached_results)} 个结果: '{query}' (来自知识库)",
                        "results": cached_results,
                        "source": "knowledge_base"
                    }
            
            # 如果有缓存，直接返回缓存结果
            if cached_result:
                return {
                    "status": "success",
                    "payload": {"main_content_for_llm": cached_result}
                }
            
            # 执行实际搜索
            search_result = await self._fetch_search_results(query, max_results)
            
            # 准备知识库项目
            knowledge_items_to_add = []
            if search_result["success"] and search_result["results"]:
                knowledge_items_to_add.append({
                    "item_type": "SEARCH_RESULTS_LIST",
                    "content": search_result["results"],
                    "source_uri": f"tavily_search_query://{query}",
                    "metadata": {"query_string": query, "search_engine": "Tavily"}
                })
            
            # 构造最终返回结果
            final_payload = {
                "main_content_for_llm": search_result
            }
        
            return {
                "status": "success" if search_result["success"] else "error",
                "payload": final_payload,
                "error_message": search_result.get("error_message"),
                "_knowledge_items_to_add": knowledge_items_to_add
            }
        
        except Exception as e:
            error_msg = f"Tavily搜索工具执行失败: {str(e)}"
            logger.error("tavily_search_tool_fatal_error", extra={
                "error": error_msg,
                "query": query if 'query' in locals() else "未知查询"
            }, exc_info=True)
            
            return {
                "status": "error",
                "error_message": error_msg,
                "payload": {
                    "error": error_msg,
                    "query": query if 'query' in locals() else "未知查询"
                }
            }


if __name__ == "__main__":
    # 测试代码
    async def test_search():
        node = GoogleSearchNode()
        
        test_prep_res = {
            "tool_params": {
                "query": "latest LLM development frameworks 2025",
                "max_results": 5
            },
            "shared_context": {}
        }
        
        result = await node.exec_async(test_prep_res)
        print(f"搜索结果: {result}")
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 运行测试
    asyncio.run(test_search())