"""LLM适配器
将AI知识图谱框架与硅基流动LLM服务集成
"""

from typing import Optional, Dict, Any, List
import logging
import sys
from pathlib import Path

# 添加硅基流动客户端路径
sys.path.append(str(Path(__file__).parent.parent.parent.parent / "app" / "services"))
from siliconflow_client import get_siliconflow_client

logger = logging.getLogger(__name__)


class LLMAdapter:
    """LLM适配器类，封装硅基流动LLM调用"""
    
    def __init__(self):
        """初始化LLM适配器"""
        self.client = get_siliconflow_client()
        logger.info("LLM适配器初始化完成（硅基流动）")
    
    def call_llm(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.8,
        **kwargs
    ) -> str:
        """调用LLM生成响应
        
        Args:
            user_prompt: 用户提示
            system_prompt: 系统提示
            max_tokens: 最大token数
            temperature: 温度参数
            **kwargs: 其他参数
            
        Returns:
            LLM响应文本
        """
        try:
            # 构造消息
            messages = []
            
            if system_prompt:
                messages.append({
                    "role": "system", 
                    "content": system_prompt
                })
            
            messages.append({
                "role": "user",
                "content": user_prompt
            })
            
            # 调用硅基流动LLM
            import asyncio
            response = asyncio.create_task(
                self.client.chat_completion(
                    messages=messages, 
                    temperature=temperature, 
                    max_tokens=max_tokens
                )
            )
            
            # 在同步函数中运行异步任务
            loop = None
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            if loop.is_running():
                # 如果在异步环境中，直接await
                return asyncio.run_coroutine_threadsafe(
                    self.client.chat_completion(
                        messages=messages, 
                        temperature=temperature, 
                        max_tokens=max_tokens
                    ), 
                    loop
                ).result()
            else:
                # 如果不在异步环境中，使用run
                return loop.run_until_complete(
                    self.client.chat_completion(
                        messages=messages, 
                        temperature=temperature, 
                        max_tokens=max_tokens
                    )
                )
                
        except Exception as e:
            logger.error(f"LLM调用失败: {str(e)}")
            raise RuntimeError(f"LLM调用失败: {str(e)}")
    
    def is_available(self) -> bool:
        """检查LLM是否可用
        
        Returns:
            是否可用
        """
        try:
            return self.llm is not None
        except:
            return False


# 全局实例
_llm_adapter = None


def get_llm_adapter() -> LLMAdapter:
    """获取LLM适配器实例
    
    Returns:
        LLM适配器实例
    """
    global _llm_adapter
    if _llm_adapter is None:
        _llm_adapter = LLMAdapter()
    return _llm_adapter


def reset_llm_adapter():
    """重置LLM适配器实例"""
    global _llm_adapter
    _llm_adapter = None 