"""
启动任务处理器工作进程
独立运行的文档处理队列工作器
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.config.settings import settings
from app.queues.task_processor import get_task_processor
from app.queues.redis_queue import get_redis_queue

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("worker.log")
    ]
)

logger = logging.getLogger(__name__)


class WorkerManager:
    """工作器管理器"""
    
    def __init__(self):
        self.task_processor = None
        self.is_running = False
        self.shutdown_event = asyncio.Event()
        self.processing_task = None
    
    async def start(self):
        """启动工作器"""
        try:
            logger.info("正在启动文档处理工作器...")
            
            # 初始化任务处理器
            self.task_processor = await get_task_processor()
            
            # 检查Redis连接
            redis_queue = get_redis_queue()
            health = await redis_queue.health_check()
            
            if health.get("status") != "healthy":
                raise ConnectionError(f"Redis连接不健康: {health}")
            
            logger.info("Redis连接正常")
            logger.info(f"队列状态: {health}")
            
            # 设置信号处理
            self._setup_signal_handlers()
            
            # 开始处理任务
            self.is_running = True
            logger.info("文档处理工作器已启动，开始处理任务...")
            
            # 启动任务处理（3个工作进程）- 不等待完成
            self.processing_task = asyncio.create_task(
                self.task_processor.start_processing(
                    queue_name="document_processing",
                    max_workers=3
                )
            )
            
        except Exception as e:
            logger.error(f"工作器启动失败: {e}")
            raise
    
    async def stop(self):
        """停止工作器"""
        if self.is_running:
            logger.info("正在停止文档处理工作器...")
            self.is_running = False
            
            # 停止任务处理器
            if self.task_processor:
                await self.task_processor.stop_processing()
            
            # 取消处理任务
            if self.processing_task and not self.processing_task.done():
                self.processing_task.cancel()
                try:
                    await self.processing_task
                except asyncio.CancelledError:
                    logger.info("处理任务已取消")
            
            self.shutdown_event.set()
            logger.info("文档处理工作器已停止")
    
    def _setup_signal_handlers(self):
        """设置信号处理器"""
        def signal_handler(signum, frame):
            logger.info(f"收到信号 {signum}，准备关闭...")
            # 设置shutdown事件，让主循环退出
            self.shutdown_event.set()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def wait_for_shutdown(self):
        """等待关闭信号"""
        await self.shutdown_event.wait()


async def main():
    """主函数"""
    print(f"""
{'='*80}
    NextAgent - 知识库文档处理工作器
{'='*80}
    Redis连接: {settings.get_redis_url()}
    队列名称: document_processing
    工作进程: 3
    日志级别: {settings.log_level.upper()}
{'='*80}
""")
    
    worker_manager = WorkerManager()
    
    try:
        # 启动工作器
        await worker_manager.start()
        
        # 等待关闭信号
        await worker_manager.wait_for_shutdown()
        
    except KeyboardInterrupt:
        logger.info("收到键盘中断信号")
    except Exception as e:
        logger.error(f"工作器运行失败: {e}")
        sys.exit(1)
    finally:
        await worker_manager.stop()
        print("\n" + "="*80)
        print("    文档处理工作器已安全关闭")
        print("="*80)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"启动失败: {e}")
        sys.exit(1)