"""
系统服务的服务间通信集成
包含文件上传、文档管理、敏感词过滤、政策搜索等基础工具
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Union, BinaryIO
from datetime import datetime, timedelta
import json
import sys
import os
import hashlib
import mimetypes
from pathlib import Path
import uuid

# 添加shared模块到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), "../../../shared"))

from service_client import (
    ServiceClient, 
    AsyncServiceClient,
    CallMethod, 
    CallConfig, 
    RetryStrategy,
    ServiceCallError,
    call_service,
    publish_event
)

logger = logging.getLogger(__name__)


class FileManager:
    """文件管理器"""
    
    def __init__(self, upload_dir: str = "/tmp/uploads"):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        
        # 支持的文件类型
        self.allowed_types = {
            "document": [".pdf", ".doc", ".docx", ".txt", ".md"],
            "image": [".jpg", ".jpeg", ".png", ".gif", ".bmp"],
            "video": [".mp4", ".avi", ".mov", ".wmv"],
            "audio": [".mp3", ".wav", ".flac", ".aac"],
            "archive": [".zip", ".rar", ".7z", ".tar", ".gz"]
        }
        
        # 文件大小限制 (MB)
        self.size_limits = {
            "document": 50,
            "image": 10, 
            "video": 500,
            "audio": 100,
            "archive": 200
        }
    
    def get_file_type(self, filename: str) -> str:
        """获取文件类型"""
        ext = Path(filename).suffix.lower()
        for file_type, extensions in self.allowed_types.items():
            if ext in extensions:
                return file_type
        return "unknown"
    
    def validate_file(self, filename: str, file_size: int) -> Dict[str, Any]:
        """验证文件"""
        file_type = self.get_file_type(filename)
        
        if file_type == "unknown":
            return {
                "valid": False,
                "error": f"不支持的文件类型: {Path(filename).suffix}",
                "allowed_types": self.allowed_types
            }
        
        # 检查文件大小
        size_limit_mb = self.size_limits.get(file_type, 10)
        size_limit_bytes = size_limit_mb * 1024 * 1024
        
        if file_size > size_limit_bytes:
            return {
                "valid": False,
                "error": f"文件大小超过限制: {file_size} bytes > {size_limit_bytes} bytes",
                "size_limit_mb": size_limit_mb
            }
        
        return {
            "valid": True,
            "file_type": file_type,
            "size_limit_mb": size_limit_mb
        }


class SensitiveWordFilter:
    """敏感词过滤器"""
    
    def __init__(self):
        # 敏感词库 (实际应用中应从数据库加载)
        self.sensitive_words = set([
            "暴力", "恐怖", "政治敏感", "违法", "色情"
        ])
        
        # 替换字符
        self.replacement_char = "*"
    
    def check_content(self, content: str) -> Dict[str, Any]:
        """检查内容是否包含敏感词"""
        found_words = []
        content_lower = content.lower()
        
        for word in self.sensitive_words:
            if word.lower() in content_lower:
                found_words.append(word)
        
        return {
            "has_sensitive_words": len(found_words) > 0,
            "found_words": found_words,
            "word_count": len(found_words)
        }
    
    def filter_content(self, content: str) -> Dict[str, Any]:
        """过滤敏感词"""
        filtered_content = content
        found_words = []
        
        for word in self.sensitive_words:
            if word.lower() in content.lower():
                found_words.append(word)
                # 替换敏感词
                replacement = self.replacement_char * len(word)
                filtered_content = filtered_content.replace(word, replacement)
        
        return {
            "original_content": content,
            "filtered_content": filtered_content,
            "found_words": found_words,
            "changes_made": len(found_words) > 0
        }


class SystemServiceIntegration:
    """系统服务集成类 - 基础工具和文件管理"""
    
    def __init__(self):
        self.service_client = None
        self.async_client = None
        self.file_manager = FileManager()
        self.sensitive_filter = SensitiveWordFilter()
        
        # 不同操作的配置
        self.file_config = CallConfig(
            timeout=60,   # 文件操作允许较长时间
            retry_times=2,
            retry_strategy=RetryStrategy.EXPONENTIAL,
            circuit_breaker_enabled=True
        )
        
        self.filter_config = CallConfig(
            timeout=10,   # 内容过滤要快
            retry_times=1,
            retry_strategy=RetryStrategy.LINEAR
        )
        
        self.auth_config = CallConfig(
            timeout=5,    # 权限检查要快
            retry_times=2,
            retry_strategy=RetryStrategy.LINEAR
        )
        
        # 支持的工具类型
        self.supported_tools = {
            "file_upload": {
                "description": "文件上传和管理",
                "capabilities": ["上传", "下载", "删除", "元数据管理"]
            },
            "content_filter": {
                "description": "内容敏感词过滤",
                "capabilities": ["敏感词检测", "内容过滤", "词库管理"]
            },
            "document_converter": {
                "description": "文档格式转换",
                "capabilities": ["PDF转换", "图片提取", "文本提取"]
            },
            "policy_search": {
                "description": "政策搜索器",
                "capabilities": ["政策检索", "法规查询", "合规检查"]
            }
        }
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.service_client = ServiceClient()
        self.async_client = AsyncServiceClient()
        await self.service_client.__aenter__()
        await self.async_client.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.service_client:
            await self.service_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.async_client:
            await self.async_client.__aexit__(exc_type, exc_val, exc_tb)
    
    # ==================== 文件管理 ====================
    
    async def upload_file(
        self, 
        file_content: bytes, 
        filename: str, 
        user_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """上传文件"""
        try:
            # 权限检查
            permission_check = await self._check_file_permission(user_id, "UPLOAD")
            if not permission_check.get("allowed"):
                return {
                    "success": False,
                    "error": "文件上传权限不足",
                    "required_permission": "file:upload"
                }
            
            # 文件验证
            file_validation = self.file_manager.validate_file(filename, len(file_content))
            if not file_validation["valid"]:
                return {
                    "success": False,
                    "error": file_validation["error"],
                    "validation_details": file_validation
                }
            
            # 生成文件ID和路径
            file_id = str(uuid.uuid4())
            file_ext = Path(filename).suffix
            safe_filename = f"{file_id}{file_ext}"
            file_path = self.file_manager.upload_dir / safe_filename
            
            # 保存文件
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            # 计算文件哈希
            file_hash = hashlib.md5(file_content).hexdigest()
            
            # 获取MIME类型
            mime_type, _ = mimetypes.guess_type(filename)
            
            # 保存文件信息到数据库
            file_info = {
                "file_id": file_id,
                "original_filename": filename,
                "safe_filename": safe_filename,
                "file_path": str(file_path),
                "file_size": len(file_content),
                "file_hash": file_hash,
                "mime_type": mime_type,
                "file_type": file_validation["file_type"],
                "user_id": user_id,
                "uploaded_at": datetime.now().isoformat(),
                "metadata": metadata or {}
            }
            
            save_result = await self._save_file_metadata(file_info)
            if not save_result["success"]:
                # 删除已上传的文件
                file_path.unlink(missing_ok=True)
                return save_result
            
            # 发布文件上传事件
            await publish_event(
                "file.uploaded",
                {
                    "file_id": file_id,
                    "filename": filename,
                    "file_size": len(file_content),
                    "user_id": user_id,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            logger.info(f"文件上传成功: {filename} -> {file_id}")
            return {
                "success": True,
                "file_id": file_id,
                "filename": filename,
                "file_size": len(file_content),
                "file_type": file_validation["file_type"],
                "upload_url": f"/files/{file_id}"
            }
            
        except Exception as e:
            logger.error(f"文件上传失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def download_file(self, file_id: str, user_id: str) -> Dict[str, Any]:
        """下载文件"""
        try:
            # 权限检查
            permission_check = await self._check_file_permission(user_id, "DOWNLOAD")
            if not permission_check.get("allowed"):
                return {
                    "success": False,
                    "error": "文件下载权限不足"
                }
            
            # 获取文件信息
            file_info = await self._get_file_metadata(file_id)
            if not file_info["success"]:
                return file_info
            
            file_data = file_info["data"]
            file_path = Path(file_data["file_path"])
            
            # 检查文件是否存在
            if not file_path.exists():
                return {
                    "success": False,
                    "error": "文件不存在",
                    "file_id": file_id
                }
            
            # 读取文件内容
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            # 记录下载日志
            await publish_event(
                "file.downloaded",
                {
                    "file_id": file_id,
                    "filename": file_data["original_filename"],
                    "user_id": user_id,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            return {
                "success": True,
                "file_content": file_content,
                "filename": file_data["original_filename"],
                "mime_type": file_data["mime_type"],
                "file_size": file_data["file_size"]
            }
            
        except Exception as e:
            logger.error(f"文件下载失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # ==================== 内容过滤 ====================
    
    async def filter_content(self, content: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """过滤内容中的敏感词"""
        try:
            # 检查内容
            check_result = self.sensitive_filter.check_content(content)
            
            if not check_result["has_sensitive_words"]:
                return {
                    "success": True,
                    "filtered_content": content,
                    "has_sensitive_words": False,
                    "changes_made": False
                }
            
            # 过滤敏感词
            filter_result = self.sensitive_filter.filter_content(content)
            
            # 记录过滤事件
            await publish_event(
                "content.filtered",
                {
                    "user_id": user_id,
                    "sensitive_words_count": len(filter_result["found_words"]),
                    "content_length": len(content),
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            return {
                "success": True,
                "filtered_content": filter_result["filtered_content"],
                "has_sensitive_words": True,
                "found_words": filter_result["found_words"],
                "changes_made": filter_result["changes_made"]
            }
            
        except Exception as e:
            logger.error(f"内容过滤失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def check_content_compliance(self, content: str) -> Dict[str, Any]:
        """检查内容合规性"""
        try:
            # 敏感词检查
            sensitive_check = self.sensitive_filter.check_content(content)
            
            # 内容长度检查
            content_length = len(content)
            is_too_long = content_length > 10000  # 10K字符限制
            
            # 综合评分
            compliance_score = 100
            issues = []
            
            if sensitive_check["has_sensitive_words"]:
                compliance_score -= len(sensitive_check["found_words"]) * 10
                issues.append("包含敏感词")
            
            if is_too_long:
                compliance_score -= 20
                issues.append("内容过长")
            
            compliance_level = "high" if compliance_score >= 80 else (
                "medium" if compliance_score >= 60 else "low"
            )
            
            return {
                "success": True,
                "compliance_score": max(0, compliance_score),
                "compliance_level": compliance_level,
                "issues": issues,
                "sensitive_words": sensitive_check["found_words"],
                "content_length": content_length,
                "is_compliant": compliance_score >= 60
            }
            
        except Exception as e:
            logger.error(f"合规性检查失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # ==================== 政策搜索 ====================
    
    async def search_policies(self, query: str, category: Optional[str] = None) -> Dict[str, Any]:
        """搜索政策法规"""
        try:
            # 这里应该连接到政策数据库或API
            # 目前返回模拟数据
            
            mock_policies = [
                {
                    "policy_id": "policy_001",
                    "title": "数据安全管理办法",
                    "category": "数据安全",
                    "content_preview": "为了保护个人信息和重要数据...",
                    "effective_date": "2024-01-01",
                    "relevance_score": 0.95
                },
                {
                    "policy_id": "policy_002", 
                    "title": "网络安全法实施条例",
                    "category": "网络安全",
                    "content_preview": "为了保障网络安全...",
                    "effective_date": "2023-06-01",
                    "relevance_score": 0.88
                }
            ]
            
            # 简单的关键词匹配过滤
            filtered_policies = []
            for policy in mock_policies:
                if query.lower() in policy["title"].lower() or query.lower() in policy["content_preview"].lower():
                    if not category or policy["category"] == category:
                        filtered_policies.append(policy)
            
            return {
                "success": True,
                "query": query,
                "category": category,
                "total_results": len(filtered_policies),
                "policies": filtered_policies
            }
            
        except Exception as e:
            logger.error(f"政策搜索失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # ==================== 辅助方法 ====================
    
    async def _check_file_permission(self, user_id: str, action: str) -> Dict[str, Any]:
        """检查文件操作权限"""
        try:
            result = await self.service_client.call(
                service_name="base-service",
                method=CallMethod.POST,
                path="/api/v1/permissions/check",
                config=self.auth_config,
                json={
                    "user_id": user_id,
                    "resource_type": "file",
                    "action": action
                }
            )
            
            return result
            
        except ServiceCallError as e:
            logger.error(f"权限检查失败: {e}")
            if e.status_code == 503:
                return {"allowed": True, "fallback": True}
            return {"allowed": False, "error": str(e)}
    
    async def _save_file_metadata(self, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """保存文件元数据到数据库"""
        try:
            result = await self.service_client.call(
                service_name="database-service",
                method=CallMethod.POST,
                path="/api/v1/files",
                config=self.file_config,
                json=file_info
            )
            
            return result
            
        except ServiceCallError as e:
            logger.error(f"保存文件元数据失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _get_file_metadata(self, file_id: str) -> Dict[str, Any]:
        """获取文件元数据"""
        try:
            result = await self.service_client.call(
                service_name="database-service",
                method=CallMethod.GET,
                path=f"/api/v1/files/{file_id}",
                config=self.file_config
            )
            
            return result
            
        except ServiceCallError as e:
            logger.error(f"获取文件元数据失败: {e}")
            return {"success": False, "error": str(e)}


# ==================== 全局便捷函数 ====================

async def upload_file_with_integration(
    file_content: bytes, 
    filename: str, 
    user_id: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """全局文件上传函数"""
    async with SystemServiceIntegration() as system_service:
        return await system_service.upload_file(file_content, filename, user_id, metadata)

async def filter_content_with_integration(content: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    """全局内容过滤函数"""
    async with SystemServiceIntegration() as system_service:
        return await system_service.filter_content(content, user_id)

async def search_policies_with_integration(query: str, category: Optional[str] = None) -> Dict[str, Any]:
    """全局政策搜索函数"""
    async with SystemServiceIntegration() as system_service:
        return await system_service.search_policies(query, category)
