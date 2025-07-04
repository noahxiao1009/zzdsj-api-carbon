"""
API接口模块
按照规则文件要求实现三层接口划分：frontend、v1、system
"""

from .frontend import frontend_router
from .v1 import v1_router  
from .system import system_router
from .gateway import gateway_router

__all__ = [
    "frontend_router",
    "v1_router", 
    "system_router",
    "gateway_router"
] 