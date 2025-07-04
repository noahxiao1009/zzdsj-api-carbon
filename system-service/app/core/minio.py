"""
System Service MinIO存储管理
"""

import io
import logging
from typing import Optional, Dict, Any, BinaryIO
from minio import Minio
from minio.error import S3Error

from app.core.config import settings

logger = logging.getLogger(__name__)

# 全局MinIO客户端
minio_client: Optional[Minio] = None


def init_minio() -> None:
    """初始化MinIO客户端"""
    global minio_client
    
    try:
        minio_client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure
        )
        
        # 检查存储桶是否存在，不存在则创建
        if not minio_client.bucket_exists(settings.minio_bucket_name):
            minio_client.make_bucket(settings.minio_bucket_name)
            logger.info(f"创建存储桶: {settings.minio_bucket_name}")
        
        logger.info("MinIO客户端初始化成功")
        
    except Exception as e:
        logger.error(f"MinIO客户端初始化失败: {e}")
        raise


def get_minio_client() -> Minio:
    """获取MinIO客户端"""
    if minio_client is None:
        init_minio()
    return minio_client


def upload_file(file_name: str, file_data: BinaryIO, file_size: int, content_type: str = None) -> bool:
    """上传文件到MinIO"""
    try:
        client = get_minio_client()
        
        client.put_object(
            bucket_name=settings.minio_bucket_name,
            object_name=file_name,
            data=file_data,
            length=file_size,
            content_type=content_type
        )
        
        logger.info(f"文件上传成功: {file_name}")
        return True
        
    except S3Error as e:
        logger.error(f"文件上传失败 {file_name}: {e}")
        return False


def download_file(file_name: str) -> Optional[bytes]:
    """从MinIO下载文件"""
    try:
        client = get_minio_client()
        
        response = client.get_object(settings.minio_bucket_name, file_name)
        data = response.read()
        response.close()
        response.release_conn()
        
        return data
        
    except S3Error as e:
        logger.error(f"文件下载失败 {file_name}: {e}")
        return None


def delete_file(file_name: str) -> bool:
    """删除MinIO中的文件"""
    try:
        client = get_minio_client()
        client.remove_object(settings.minio_bucket_name, file_name)
        
        logger.info(f"文件删除成功: {file_name}")
        return True
        
    except S3Error as e:
        logger.error(f"文件删除失败 {file_name}: {e}")
        return False


def get_file_info(file_name: str) -> Optional[Dict[str, Any]]:
    """获取文件信息"""
    try:
        client = get_minio_client()
        stat = client.stat_object(settings.minio_bucket_name, file_name)
        
        return {
            "name": file_name,
            "size": stat.size,
            "etag": stat.etag,
            "last_modified": stat.last_modified,
            "content_type": stat.content_type
        }
        
    except S3Error as e:
        logger.error(f"获取文件信息失败 {file_name}: {e}")
        return None


def check_minio_health() -> bool:
    """检查MinIO连接健康状态"""
    try:
        client = get_minio_client()
        return client.bucket_exists(settings.minio_bucket_name)
    except Exception as e:
        logger.error(f"MinIO健康检查失败: {e}")
        return False


# 导出
__all__ = [
    "init_minio",
    "get_minio_client",
    "upload_file",
    "download_file", 
    "delete_file",
    "get_file_info",
    "check_minio_health"
] 