"""
Gateway Service Logging Configuration
"""

import logging

def get_logger(name: str = None) -> logging.Logger:
    """获取日志器实例"""
    if name is None:
        name = "gateway"
    elif not name.startswith("gateway."):
        name = f"gateway.{name}"
    
    return logging.getLogger(name)

# 提供常用的日志器实例
logger = get_logger()
access_logger = get_logger("access")
error_logger = get_logger("error")
monitoring_logger = get_logger("monitoring")

__all__ = ["get_logger", "logger", "access_logger", "error_logger", "monitoring_logger"]
