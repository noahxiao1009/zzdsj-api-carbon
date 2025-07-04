"""
MCP Service 日志系统配置
"""

import logging
import logging.handlers
import sys
import os
from pathlib import Path
from typing import Dict, Any
import json
from datetime import datetime

from app.core.config import settings


class JSONFormatter(logging.Formatter):
    """JSON格式日志格式化器"""
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录为JSON"""
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # 添加异常信息
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # 添加额外字段
        if hasattr(record, "service_id"):
            log_entry["service_id"] = record.service_id
        if hasattr(record, "tool_name"):
            log_entry["tool_name"] = record.tool_name
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        return json.dumps(log_entry, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """文本格式日志格式化器"""
    
    def __init__(self):
        super().__init__(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )


def setup_logging() -> None:
    """设置日志系统"""
    
    # 创建日志目录
    log_dir = Path(settings.log_file_path).parent
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # 根日志器配置
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))
    
    # 清除已有的处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    if settings.log_format.lower() == "json":
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(TextFormatter())
    
    root_logger.addHandler(console_handler)
    
    # 文件处理器
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            filename=settings.log_file_path,
            maxBytes=100 * 1024 * 1024,  # 100MB
            backupCount=settings.log_backup_count,
            encoding="utf-8"
        )
        file_handler.setLevel(getattr(logging, settings.log_level.upper()))
        
        if settings.log_format.lower() == "json":
            file_handler.setFormatter(JSONFormatter())
        else:
            file_handler.setFormatter(TextFormatter())
        
        root_logger.addHandler(file_handler)
    except Exception as e:
        print(f"无法创建文件日志处理器: {e}")
    
    # 设置特定模块的日志级别
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("redis").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    # 开发环境下的详细日志
    if settings.debug:
        logging.getLogger("app").setLevel(logging.DEBUG)
    else:
        logging.getLogger("app").setLevel(logging.INFO)
    
    logging.info("日志系统初始化完成")


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的日志器"""
    return logging.getLogger(name)


def log_mcp_operation(logger: logging.Logger, operation: str, service_id: str, 
                      tool_name: str = None, user_id: str = None, 
                      request_id: str = None, **kwargs) -> None:
    """记录MCP操作日志"""
    extra = {
        "operation": operation,
        "service_id": service_id
    }
    
    if tool_name:
        extra["tool_name"] = tool_name
    if user_id:
        extra["user_id"] = user_id
    if request_id:
        extra["request_id"] = request_id
    
    extra.update(kwargs)
    
    message = f"MCP操作: {operation}"
    if service_id:
        message += f" | 服务: {service_id}"
    if tool_name:
        message += f" | 工具: {tool_name}"
    
    logger.info(message, extra=extra)


# 创建专用日志器
mcp_logger = get_logger("mcp-service")
performance_logger = get_logger("mcp-service.performance")
security_logger = get_logger("mcp-service.security")


# 导出
__all__ = [
    "setup_logging",
    "get_logger",
    "log_mcp_operation",
    "mcp_logger",
    "performance_logger", 
    "security_logger",
    "JSONFormatter",
    "TextFormatter"
] 