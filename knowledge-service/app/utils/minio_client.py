"""
MinIO 客户端工具
处理 MinIO 对象存储的连接和操作
"""

import io
import logging
from typing import Optional, List, Dict, Any
from minio import Minio
from minio.error import S3Error
from app.config.settings import settings

logger = logging.getLogger(__name__)

# 全局MinIO客户端实例
_minio_client: Optional[Minio] = None

def get_minio_client() -> Minio:
    """获取MinIO客户端实例"""
    global _minio_client
    if _minio_client is None:
        _minio_client = Minio(
            settings.storage.minio_endpoint,
            access_key=settings.storage.minio_access_key,
            secret_key=settings.storage.minio_secret_key,
            secure=settings.storage.minio_secure
        )
        logger.info(f"MinIO client initialized for {settings.storage.minio_endpoint}")
    return _minio_client

def ensure_bucket_exists(bucket_name: str) -> bool:
    """确保存储桶存在，不存在则创建"""
    try:
        client = get_minio_client()
        found = client.bucket_exists(bucket_name)
        if not found:
            client.make_bucket(bucket_name)
            logger.info(f"Created bucket {bucket_name}")
        else:
            logger.info(f"Bucket {bucket_name} already exists")
        return True
    except S3Error as e:
        logger.error(f"Error ensuring bucket {bucket_name} exists: {e}")
        return False

def upload_to_minio(file_name: str, file_data: io.BytesIO, content_type: str) -> bool:
    """上传文件到MinIO"""
    try:
        client = get_minio_client()
        bucket_name = settings.storage.minio_bucket_name
        
        # 确保存储桶存在
        if not ensure_bucket_exists(bucket_name):
            return False
        
        # 上传文件
        client.put_object(
            bucket_name=bucket_name,
            object_name=file_name,
            data=file_data,
            length=file_data.getbuffer().nbytes,
            content_type=content_type
        )
        logger.info(f"Successfully uploaded {file_name} to {bucket_name}")
        return True
    except S3Error as e:
        logger.error(f"Error uploading {file_name}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error uploading {file_name}: {e}")
        return False

def download_from_minio(file_name: str) -> Optional[bytes]:
    """从MinIO下载文件"""
    try:
        client = get_minio_client()
        bucket_name = settings.storage.minio_bucket_name
        
        response = client.get_object(bucket_name, file_name)
        data = response.read()
        response.close()
        response.release_conn()
        
        logger.info(f"Successfully downloaded {file_name} from {bucket_name}")
        return data
    except S3Error as e:
        logger.error(f"Error downloading {file_name}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error downloading {file_name}: {e}")
        return None

def delete_from_minio(file_name: str) -> bool:
    """从MinIO删除文件"""
    try:
        client = get_minio_client()
        bucket_name = settings.storage.minio_bucket_name
        
        client.remove_object(bucket_name, file_name)
        logger.info(f"Successfully deleted {file_name} from {bucket_name}")
        return True
    except S3Error as e:
        logger.error(f"Error deleting {file_name}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error deleting {file_name}: {e}")
        return False

def list_files_in_minio(prefix: str = "") -> List[str]:
    """列出MinIO中的文件"""
    try:
        client = get_minio_client()
        bucket_name = settings.storage.minio_bucket_name
        
        objects = client.list_objects(bucket_name, prefix=prefix)
        file_list = [obj.object_name for obj in objects]
        
        logger.info(f"Found {len(file_list)} files in {bucket_name}")
        return file_list
    except S3Error as e:
        logger.error(f"Error listing files: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error listing files: {e}")
        return []

def get_file_info_from_minio(file_name: str) -> Optional[Dict[str, Any]]:
    """获取MinIO中文件的信息"""
    try:
        client = get_minio_client()
        bucket_name = settings.storage.minio_bucket_name
        
        stat = client.stat_object(bucket_name, file_name)
        return {
            "name": file_name,
            "size": stat.size,
            "etag": stat.etag,
            "last_modified": stat.last_modified,
            "content_type": stat.content_type
        }
    except S3Error as e:
        logger.error(f"Error getting file info for {file_name}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting file info for {file_name}: {e}")
        return None

def test_minio_connection() -> bool:
    """测试MinIO连接"""
    try:
        client = get_minio_client()
        bucket_name = settings.storage.minio_bucket_name
        
        # 尝试检查桶是否存在或创建桶
        return ensure_bucket_exists(bucket_name)
    except Exception as e:
        logger.error(f"MinIO connection test failed: {e}")
        return False

# 导出函数
__all__ = [
    "get_minio_client",
    "ensure_bucket_exists", 
    "upload_to_minio",
    "download_from_minio",
    "delete_from_minio",
    "list_files_in_minio", 
    "get_file_info_from_minio",
    "test_minio_connection"
]
