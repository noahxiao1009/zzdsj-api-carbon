"""
Chat Service 日志配置
基于原始项目的日志管理实现
"""

import logging
import logging.config
import sys
from pathlib import Path
from typing import Dict, Any

from app.core.config import settings


def setup_logging() -> None:
    """设置日志配置"""
    
    # 创建日志目录
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # 日志配置
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "detailed": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(pathname)s:%(lineno)d - %(funcName)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "json": {
                "format": '{"timestamp": "%(asctime)s", "name": "%(name)s", "level": "%(levelname)s", "message": "%(message)s", "pathname": "%(pathname)s", "lineno": %(lineno)d, "funcName": "%(funcName)s"}',
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": settings.log_level,
                "formatter": "default",
                "stream": sys.stdout,
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": settings.log_level,
                "formatter": "detailed",
                "filename": log_dir / "chat-service.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8",
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "detailed",
                "filename": log_dir / "chat-service-error.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8",
            },
        },
        "loggers": {
            "": {  # root logger
                "level": settings.log_level,
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "uvicorn.error": {
                "level": "INFO",
                "handlers": ["console", "error_file"],
                "propagate": False,
            },
            "uvicorn.access": {
                "level": "INFO",
                "handlers": ["file"],
                "propagate": False,
            },
            "sqlalchemy": {
                "level": "WARNING",
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "sqlalchemy.engine": {
                "level": "WARNING" if not settings.debug else "INFO",
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "redis": {
                "level": "WARNING",
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "agno": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "chat_service": {
                "level": settings.log_level,
                "handlers": ["console", "file"],
                "propagate": False,
            },
        },
    }
    
    # 应用日志配置
    logging.config.dictConfig(config)
    
    # 设置根日志器
    logger = logging.getLogger("chat_service")
    logger.info(f"日志系统已初始化，级别: {settings.log_level}")


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的日志器"""
    return logging.getLogger(f"chat_service.{name}")


def log_function_call(func_name: str, args: Dict[str, Any] = None, level: str = "DEBUG"):
    """记录函数调用"""
    logger = get_logger("function_calls")
    if args:
        logger.log(getattr(logging, level), f"调用函数 {func_name}，参数: {args}")
    else:
        logger.log(getattr(logging, level), f"调用函数 {func_name}")


def log_error(error: Exception, context: str = "", logger_name: str = "error"):
    """记录错误信息"""
    logger = get_logger(logger_name)
    if context:
        logger.error(f"错误发生在 {context}: {str(error)}", exc_info=True)
    else:
        logger.error(f"发生错误: {str(error)}", exc_info=True) 