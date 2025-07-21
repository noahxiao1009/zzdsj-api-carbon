"""
日志工具
"""
import logging
import sys
from typing import Optional
from app.config.settings import settings


def setup_logging():
    """设置日志配置"""
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format=settings.log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('app.log', encoding='utf-8')
        ]
    )


def get_logger(name: str) -> logging.Logger:
    """获取日志记录器"""
    return logging.getLogger(name)


# 初始化日志配置
setup_logging()