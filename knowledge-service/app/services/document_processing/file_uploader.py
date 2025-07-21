"""
文件上传服务
处理文件上传、验证和存储
"""

import os
import hashlib
import shutil
import uuid
import io
from pathlib import Path
from typing import Optional, Dict, Any, List
import aiofiles
from fastapi import UploadFile, HTTPException

from app.config.settings import settings
from app.utils.minio_client import upload_to_minio


class FileUploader:
    """文件上传处理服务"""
    
    def __init__(self):
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.max_file_size = settings.MAX_FILE_SIZE
        self.allowed_extensions = {
            '.pdf', '.doc', '.docx', '.txt', '.md', '.rtf',
            '.xls', '.xlsx', '.csv', '.ppt', '.pptx',
            '.html', '.htm', '.xml', '.json'
        }
        
        # 确保上传目录存在
        self.upload_dir.mkdir(parents=True, exist_ok=True)
    
    async def upload_file(
        self, 
        file: UploadFile, 
        kb_id: str,
        custom_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        上传文件到指定知识库目录
        
        Args:
            file: 上传的文件对象
            kb_id: 知识库ID
            custom_filename: 自定义文件名（可选）
            
        Returns:
            包含文件信息的字典
        """
        try:
            # 验证文件
            await self._validate_file(file)
            
            # 计算文件哈希
            file_hash = await self._calculate_file_hash(file)
            
            # 生成文件路径
            kb_dir = self.upload_dir / kb_id
            kb_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成唯一文件名
            file_extension = Path(file.filename).suffix.lower()
            if custom_filename:
                filename = f"{custom_filename}{file_extension}"
            else:
                unique_id = str(uuid.uuid4())[:8]
                original_name = Path(file.filename).stem
                filename = f"{original_name}_{unique_id}{file_extension}"
            
            file_path = kb_dir / filename
            
            # 检查文件是否已存在（基于哈希）
            existing_file = await self._check_duplicate_by_hash(kb_id, file_hash)
            if existing_file:
                return {
                    'success': False,
                    'error': 'File already exists',
                    'existing_file': existing_file,
                    'file_hash': file_hash
                }
            
            # 保存文件
            file_size = await self._save_file(file, file_path)
            
            # 返回文件信息
            return {
                'success': True,
                'filename': filename,
                'original_filename': file.filename,
                'file_path': str(file_path),
                'file_size': file_size,
                'file_hash': file_hash,
                'file_type': self._get_file_type(file_extension),
                'mime_type': file.content_type
            }
            
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"File upload failed: {str(e)}")
    
    async def _validate_file(self, file: UploadFile) -> None:
        """验证文件格式和大小"""
        if not file.filename:
            raise ValueError("No filename provided")
        
        # 检查文件扩展名
        file_extension = Path(file.filename).suffix.lower()
        if file_extension not in self.allowed_extensions:
            raise ValueError(f"File type {file_extension} not supported")
        
        # 检查文件大小
        file.file.seek(0, 2)  # 移动到文件末尾
        file_size = file.file.tell()
        file.file.seek(0)  # 重置到文件开头
        
        if file_size > self.max_file_size:
            raise ValueError(f"File size {file_size} exceeds maximum {self.max_file_size}")
        
        if file_size == 0:
            raise ValueError("Empty file not allowed")
    
    async def _calculate_file_hash(self, file: UploadFile) -> str:
        """计算文件MD5哈希"""
        hash_md5 = hashlib.md5()
        
        file.file.seek(0)
        while chunk := file.file.read(8192):
            hash_md5.update(chunk)
        file.file.seek(0)  # 重置文件指针
        
        return hash_md5.hexdigest()
    
    async def _save_file(self, file: UploadFile, file_path: Path) -> int:
        """保存文件到存储后端（MinIO或本地）"""
        file_size = 0
        file.file.seek(0)
        
        # 读取文件内容到内存
        file_content = b""
        while chunk := file.file.read(8192):
            file_content += chunk
            file_size += len(chunk)
        
        # 根据配置选择存储后端
        if settings.storage.storage_backend == "minio":
            # 上传到MinIO
            file_data = io.BytesIO(file_content)
            success = upload_to_minio(
                file_name=f"{file_path.parent.name}/{file_path.name}",
                file_data=file_data,
                content_type=file.content_type or "application/octet-stream"
            )
            if not success:
                raise Exception("Failed to upload file to MinIO")
        else:
            # 保存到本地文件系统
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(file_content)
        
        return file_size
    
    async def _check_duplicate_by_hash(self, kb_id: str, file_hash: str) -> Optional[Dict[str, Any]]:
        """检查基于哈希的重复文件"""
        # 这里应该查询数据库中是否已存在相同哈希的文件
        # 暂时返回None，具体实现需要结合Repository
        return None
    
    def _get_file_type(self, extension: str) -> str:
        """根据扩展名获取文件类型"""
        type_mapping = {
            '.pdf': 'pdf',
            '.doc': 'word',
            '.docx': 'word',
            '.txt': 'text',
            '.md': 'markdown',
            '.rtf': 'rtf',
            '.xls': 'excel',
            '.xlsx': 'excel',
            '.csv': 'csv',
            '.ppt': 'powerpoint',
            '.pptx': 'powerpoint',
            '.html': 'html',
            '.htm': 'html',
            '.xml': 'xml',
            '.json': 'json'
        }
        return type_mapping.get(extension, 'unknown')
    
    async def delete_file(self, file_path: str) -> bool:
        """删除文件"""
        try:
            path = Path(file_path)
            if path.exists() and path.is_file():
                path.unlink()
                return True
            return False
        except Exception as e:
            print(f"Error deleting file {file_path}: {e}")
            return False
    
    async def move_file(self, old_path: str, new_path: str) -> bool:
        """移动文件"""
        try:
            old_path_obj = Path(old_path)
            new_path_obj = Path(new_path)
            
            # 确保目标目录存在
            new_path_obj.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.move(str(old_path_obj), str(new_path_obj))
            return True
        except Exception as e:
            print(f"Error moving file from {old_path} to {new_path}: {e}")
            return False
    
    def get_file_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """获取文件信息"""
        try:
            path = Path(file_path)
            if not path.exists():
                return None
            
            stat = path.stat()
            return {
                'filename': path.name,
                'file_size': stat.st_size,
                'created_time': stat.st_ctime,
                'modified_time': stat.st_mtime,
                'file_type': self._get_file_type(path.suffix.lower())
            }
        except Exception as e:
            print(f"Error getting file info for {file_path}: {e}")
            return None
    
    async def batch_upload(
        self, 
        files: List[UploadFile], 
        kb_id: str
    ) -> List[Dict[str, Any]]:
        """批量上传文件"""
        results = []
        
        for file in files:
            try:
                result = await self.upload_file(file, kb_id)
                results.append(result)
            except Exception as e:
                results.append({
                    'success': False,
                    'filename': file.filename,
                    'error': str(e)
                })
        
        return results