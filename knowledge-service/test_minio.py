#!/usr/bin/env python3
"""
MinIO 连接测试脚本
"""

import sys
import os
import io
import logging

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.config.settings import settings
from app.utils.minio_client import (
    test_minio_connection,
    upload_to_minio,
    list_files_in_minio,
    download_from_minio,
    delete_from_minio
)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_basic_connection():
    """测试基础连接"""
    logger.info("Testing MinIO connection...")
    logger.info(f"Endpoint: {settings.storage.minio_endpoint}")
    logger.info(f"Bucket: {settings.storage.minio_bucket_name}")
    
    if test_minio_connection():
        logger.info("✅ MinIO connection successful!")
        return True
    else:
        logger.error("❌ MinIO connection failed!")
        return False

def test_file_operations():
    """测试文件操作"""
    logger.info("Testing file operations...")
    
    # 创建测试文件
    test_content = b"This is a test file for MinIO upload"
    test_file_name = "test/test_file.txt"
    file_data = io.BytesIO(test_content)
    
    # 1. 上传测试
    logger.info("Testing file upload...")
    if upload_to_minio(test_file_name, file_data, "text/plain"):
        logger.info("✅ File upload successful!")
    else:
        logger.error("❌ File upload failed!")
        return False
    
    # 2. 列出文件测试
    logger.info("Testing file listing...")
    files = list_files_in_minio("test/")
    if test_file_name in files:
        logger.info("✅ File listing successful!")
        logger.info(f"Found files: {files}")
    else:
        logger.error("❌ File listing failed or file not found!")
        return False
    
    # 3. 下载测试
    logger.info("Testing file download...")
    downloaded_data = download_from_minio(test_file_name)
    if downloaded_data and downloaded_data == test_content:
        logger.info("✅ File download successful!")
    else:
        logger.error("❌ File download failed!")
        return False
    
    # 4. 删除测试
    logger.info("Testing file deletion...")
    if delete_from_minio(test_file_name):
        logger.info("✅ File deletion successful!")
    else:
        logger.error("❌ File deletion failed!")
        return False
    
    return True

def main():
    """主测试函数"""
    logger.info("=== MinIO 配置测试 ===")
    
    # 显示配置信息
    logger.info(f"MinIO 配置:")
    logger.info(f"  端点: {settings.storage.minio_endpoint}")
    logger.info(f"  访问密钥: {settings.storage.minio_access_key[:8]}...")
    logger.info(f"  存储桶: {settings.storage.minio_bucket_name}")
    logger.info(f"  安全连接: {settings.storage.minio_secure}")
    logger.info(f"  存储后端: {settings.storage.storage_backend}")
    
    # 测试连接
    if not test_basic_connection():
        return False
    
    # 测试文件操作
    if not test_file_operations():
        return False
    
    logger.info("🎉 所有测试通过！MinIO 配置正确！")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
