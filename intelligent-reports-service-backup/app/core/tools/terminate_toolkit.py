"""
终止工具包
"""
from typing import Dict, Any
from app.core.tools.base import BaseTool
from app.utils.logging import get_logger


logger = get_logger(__name__)


class TerminateToolkit(BaseTool):
    """终止工具包"""
    
    def __init__(self):
        super().__init__(
            name="terminate_toolkit",
            description="用于终止任务执行的工具包",
            config={}
        )
    
    async def execute(self, *args, **kwargs) -> Any:
        """执行工具 - 此方法不直接使用"""
        return "TerminateToolkit is a collection of tools"
    
    def get_parameters(self) -> Dict[str, Any]:
        """获取参数定义"""
        return {}
    
    def terminate(self, reason: str = "任务完成", result: str = None) -> str:
        """终止任务执行
        
        Args:
            reason: 终止原因
            result: 最终结果
        
        Returns:
            终止信息
        """
        try:
            logger.info(f"Task terminated: {reason}")
            
            termination_message = f"任务终止: {reason}"
            if result:
                termination_message += f"\n最终结果: {result}"
            
            return termination_message
            
        except Exception as e:
            error_msg = f"终止任务失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
    
    def force_terminate(self, reason: str = "强制终止") -> str:
        """强制终止任务
        
        Args:
            reason: 终止原因
        
        Returns:
            终止信息
        """
        try:
            logger.warning(f"Task force terminated: {reason}")
            return f"任务已强制终止: {reason}"
            
        except Exception as e:
            error_msg = f"强制终止任务失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
    
    def pause(self, reason: str = "任务暂停") -> str:
        """暂停任务
        
        Args:
            reason: 暂停原因
        
        Returns:
            暂停信息
        """
        try:
            logger.info(f"Task paused: {reason}")
            return f"任务已暂停: {reason}"
            
        except Exception as e:
            error_msg = f"暂停任务失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
    
    def resume(self, reason: str = "任务恢复") -> str:
        """恢复任务
        
        Args:
            reason: 恢复原因
        
        Returns:
            恢复信息
        """
        try:
            logger.info(f"Task resumed: {reason}")
            return f"任务已恢复: {reason}"
            
        except Exception as e:
            error_msg = f"恢复任务失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg


def create_terminate_toolkit() -> TerminateToolkit:
    """创建终止工具包"""
    return TerminateToolkit()