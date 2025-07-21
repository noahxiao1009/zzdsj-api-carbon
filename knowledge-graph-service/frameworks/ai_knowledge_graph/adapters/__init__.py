"""AI知识图谱适配器模块
提供与系统其他组件的集成适配器
"""

from .llm_adapter import get_llm_adapter
from .storage_adapter import get_storage_adapter

__all__ = [
    'get_llm_adapter',
    'get_storage_adapter'
] 