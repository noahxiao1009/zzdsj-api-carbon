"""
工具管理器
统一管理和调度各种工具
"""

import asyncio
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from app.schemas.tool_schemas import (
    ToolRequest, ToolResponse, ToolInfo, ToolStatus, ToolMetrics,
    ToolType, ToolAction
)
from app.tools.webagent_tool import WebAgentTool
from app.tools.scraperr_tool import ScrapeerrTool
from app.core.logger import logger


class ToolManager:
    """工具管理器"""
    
    def __init__(self):
        self.tools: Dict[str, Any] = {}
        self.metrics: Dict[str, ToolMetrics] = {}
        self.last_health_check = datetime.now()
        self._initialized = False
    
    async def initialize(self):
        """初始化工具管理器"""
        if self._initialized:
            return
            
        logger.info("初始化工具管理器...")
        
        try:
            # 初始化WebAgent工具
            self.tools["webagent"] = WebAgentTool()
            await self.tools["webagent"].initialize()
            logger.info("WebAgent工具初始化成功")
            
            # 初始化Scraperr工具
            self.tools["scraperr"] = ScrapeerrTool()
            await self.tools["scraperr"].initialize()
            logger.info("Scraperr工具初始化成功")
            
            # 初始化性能指标
            for tool_name in self.tools.keys():
                self.metrics[tool_name] = ToolMetrics(tool_name=tool_name)
            
            self._initialized = True
            logger.info("工具管理器初始化完成")
            
        except Exception as e:
            logger.error(f"工具管理器初始化失败: {e}", exc_info=True)
            raise
    
    async def execute_tool(self, request: ToolRequest) -> ToolResponse:
        """执行工具调用"""
        start_time = time.time()
        tool_name = request.tool_name.value
        
        logger.info(f"执行工具调用: {tool_name}.{request.action}")
        
        try:
            # 检查工具是否存在
            if tool_name not in self.tools:
                return ToolResponse(
                    success=False,
                    data=None,
                    message=f"工具 {tool_name} 未找到"
                )
            
            # 获取工具实例
            tool = self.tools[tool_name]
            
            # 执行工具调用
            result = await tool.execute(request)
            
            # 记录执行时间
            execution_time = time.time() - start_time
            result.execution_time = execution_time
            
            # 更新性能指标
            await self._update_metrics(tool_name, True, execution_time)
            
            logger.info(f"工具调用成功: {tool_name}.{request.action}, 耗时: {execution_time:.2f}s")
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"工具调用失败: {str(e)}"
            logger.error(f"{error_msg}, 耗时: {execution_time:.2f}s", exc_info=True)
            
            # 更新性能指标
            await self._update_metrics(tool_name, False, execution_time)
            
            return ToolResponse(
                success=False,
                data=None,
                message=error_msg,
                execution_time=execution_time
            )
    
    async def batch_execute(self, requests: List[ToolRequest], parallel: bool = False) -> List[ToolResponse]:
        """批量执行工具调用"""
        logger.info(f"批量执行工具调用: {len(requests)} 个请求, 并行: {parallel}")
        
        if parallel:
            # 并行执行
            tasks = [self.execute_tool(req) for req in requests]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理异常结果
            final_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    final_results.append(ToolResponse(
                        success=False,
                        data=None,
                        message=f"批量执行异常: {str(result)}"
                    ))
                else:
                    final_results.append(result)
            
            return final_results
        else:
            # 串行执行
            results = []
            for request in requests:
                result = await self.execute_tool(request)
                results.append(result)
            return results
    
    async def get_tool_info(self, tool_name: str) -> Optional[ToolInfo]:
        """获取工具信息"""
        if tool_name not in self.tools:
            return None
        
        tool = self.tools[tool_name]
        schema = await tool.get_schema()
        
        return ToolInfo(
            name=tool_name,
            type=ToolType(tool_name),
            description=schema.get("description", ""),
            version=schema.get("version", "1.0.0"),
            status="active",
            supported_actions=list(schema.get("actions", {}).keys()),
            schema=schema
        )
    
    async def list_tools(self) -> List[ToolInfo]:
        """列出所有工具"""
        tools_info = []
        for tool_name in self.tools.keys():
            info = await self.get_tool_info(tool_name)
            if info:
                tools_info.append(info)
        return tools_info
    
    async def get_tools_status(self) -> Dict[str, ToolStatus]:
        """获取所有工具状态"""
        status = {}
        
        for tool_name, tool in self.tools.items():
            try:
                # 健康检查
                health_result = await tool.health_check()
                
                # 获取性能指标
                metrics = self.metrics.get(tool_name)
                metrics_data = {
                    "total_calls": metrics.total_calls,
                    "success_rate": metrics.success_rate,
                    "avg_response_time": metrics.avg_response_time
                } if metrics else {}
                
                status[tool_name] = ToolStatus(
                    tool_name=tool_name,
                    status="active" if health_result else "error",
                    last_check=datetime.now(),
                    error_message=None if health_result else "健康检查失败",
                    metrics=metrics_data
                )
                
            except Exception as e:
                status[tool_name] = ToolStatus(
                    tool_name=tool_name,
                    status="error",
                    last_check=datetime.now(),
                    error_message=str(e),
                    metrics=None
                )
        
        self.last_health_check = datetime.now()
        return status
    
    async def get_tool_metrics(self, tool_name: str) -> Optional[ToolMetrics]:
        """获取工具性能指标"""
        return self.metrics.get(tool_name)
    
    async def reset_metrics(self, tool_name: str = None):
        """重置性能指标"""
        if tool_name:
            if tool_name in self.metrics:
                self.metrics[tool_name] = ToolMetrics(tool_name=tool_name)
        else:
            for name in self.metrics.keys():
                self.metrics[name] = ToolMetrics(tool_name=name)
        
        logger.info(f"重置性能指标: {tool_name or '所有工具'}")
    
    async def cleanup(self):
        """清理资源"""
        logger.info("清理工具管理器资源...")
        
        for tool_name, tool in self.tools.items():
            try:
                if hasattr(tool, 'cleanup'):
                    await tool.cleanup()
                logger.info(f"工具 {tool_name} 清理完成")
            except Exception as e:
                logger.error(f"工具 {tool_name} 清理失败: {e}")
        
        self.tools.clear()
        self.metrics.clear()
        self._initialized = False
    
    async def _update_metrics(self, tool_name: str, success: bool, execution_time: float):
        """更新性能指标"""
        if tool_name not in self.metrics:
            return
        
        metrics = self.metrics[tool_name]
        metrics.total_calls += 1
        
        if success:
            metrics.success_calls += 1
        else:
            metrics.error_calls += 1
        
        # 更新平均响应时间（移动平均）
        if metrics.avg_response_time == 0:
            metrics.avg_response_time = execution_time
        else:
            # 使用指数移动平均
            alpha = 0.1
            metrics.avg_response_time = (
                alpha * execution_time + 
                (1 - alpha) * metrics.avg_response_time
            )
        
        # 更新24小时内调用次数（简化实现）
        metrics.last_24h_calls += 1
    
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized
    
    def get_supported_tools(self) -> List[str]:
        """获取支持的工具列表"""
        return list(self.tools.keys())
    
    def get_supported_actions(self, tool_name: str) -> List[str]:
        """获取工具支持的操作"""
        if tool_name not in self.tools:
            return []
        
        # 根据工具类型返回支持的操作
        if tool_name == "webagent":
            return ["search", "visit"]
        elif tool_name == "scraperr":
            return ["scrape", "list_jobs", "get_job", "delete_job"]
        else:
            return []
    
    async def get_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """获取工具模式"""
        if tool_name not in self.tools:
            return None
        
        tool = self.tools[tool_name]
        return await tool.get_schema()
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        tools_status = await self.get_tools_status()
        overall_healthy = all(
            status.status == "active" for status in tools_status.values()
        )
        
        return {
            "overall_healthy": overall_healthy,
            "tools": tools_status,
            "timestamp": datetime.now().isoformat()
        }
    
    async def get_metrics(self) -> Dict[str, Any]:
        """获取所有工具指标"""
        metrics = {}
        for tool_name, tool_metrics in self.metrics.items():
            metrics[tool_name] = {
                "total_calls": tool_metrics.total_calls,
                "success_calls": tool_metrics.success_calls,
                "error_calls": tool_metrics.error_calls,
                "success_rate": tool_metrics.success_rate,
                "avg_response_time": tool_metrics.avg_response_time,
                "last_24h_calls": tool_metrics.last_24h_calls
            }
        
        return metrics