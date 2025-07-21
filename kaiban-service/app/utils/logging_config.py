"""
日志配置工具
"""

import logging
import sys
from pathlib import Path


def setup_logging(level: str = "INFO") -> None:
    """设置应用日志配置"""
    
    # 创建日志目录
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # 日志格式
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # 配置根日志记录器
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=log_format,
        handlers=[
            # 控制台输出
            logging.StreamHandler(sys.stdout),
            # 文件输出
            logging.FileHandler(log_dir / "kaiban-service.log", encoding="utf-8")
        ]
    )
    
    # 设置第三方库日志级别
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("redis").setLevel(logging.WARNING)
    
    logger = logging.getLogger(__name__)
    logger.info("日志系统已配置完成") 