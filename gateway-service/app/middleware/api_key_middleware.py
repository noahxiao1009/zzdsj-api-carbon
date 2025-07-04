"""
API Key认证中间件
用于外部系统调用v1接口的API Key验证
"""

import hashlib
import hmac
import logging
import secrets
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from fastapi import HTTPException, Depends, Request, Header
import time

logger = logging.getLogger(__name__)


class APIKey:
    """API Key数据类"""
    
    def __init__(
        self,
        key_id: str,
        key_secret: str,
        name: str,
        permissions: List[str] = None,
        rate_limit: int = 1000,
        expires_at: Optional[datetime] = None,
        is_active: bool = True,
        metadata: Dict[str, Any] = None
    ):
        self.key_id = key_id
        self.key_secret = key_secret
        self.name = name
        self.permissions = permissions or []
        self.rate_limit = rate_limit  # 每小时请求限制
        self.expires_at = expires_at
        self.is_active = is_active
        self.metadata = metadata or {}
        self.created_at = datetime.now()
        self.last_used = None
        self.usage_count = 0


class RateLimiter:
    """API Key速率限制器"""
    
    def __init__(self):
        self.usage_records = {}  # {api_key_id: {hour: count}}
    
    def is_rate_limited(self, api_key: APIKey) -> bool:
        """检查是否超过速率限制"""
        current_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
        
        if api_key.key_id not in self.usage_records:
            self.usage_records[api_key.key_id] = {}
        
        key_records = self.usage_records[api_key.key_id]
        current_count = key_records.get(current_hour, 0)
        
        return current_count >= api_key.rate_limit
    
    def record_usage(self, api_key: APIKey):
        """记录API Key使用"""
        current_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
        
        if api_key.key_id not in self.usage_records:
            self.usage_records[api_key.key_id] = {}
        
        key_records = self.usage_records[api_key.key_id]
        key_records[current_hour] = key_records.get(current_hour, 0) + 1
        
        # 清理旧记录（保留24小时）
        cutoff_time = current_hour - timedelta(hours=24)
        expired_hours = [hour for hour in key_records.keys() if hour < cutoff_time]
        for hour in expired_hours:
            del key_records[hour]
    
    def get_usage_stats(self, api_key: APIKey) -> Dict[str, Any]:
        """获取使用统计"""
        current_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
        
        if api_key.key_id not in self.usage_records:
            return {
                "current_hour_usage": 0,
                "remaining_requests": api_key.rate_limit,
                "reset_time": (current_hour + timedelta(hours=1)).isoformat()
            }
        
        key_records = self.usage_records[api_key.key_id]
        current_usage = key_records.get(current_hour, 0)
        
        return {
            "current_hour_usage": current_usage,
            "remaining_requests": max(0, api_key.rate_limit - current_usage),
            "reset_time": (current_hour + timedelta(hours=1)).isoformat(),
            "rate_limit": api_key.rate_limit
        }


class APIKeyManager:
    """API Key管理器"""
    
    def __init__(self):
        self.api_keys: Dict[str, APIKey] = {}
        self.rate_limiter = RateLimiter()
        self._init_default_keys()
    
    def _init_default_keys(self):
        """初始化默认API Key"""
        # 创建一个默认的API Key用于测试
        default_key = self.create_api_key(
            name="Default Test Key",
            permissions=["knowledge:read", "knowledge:write", "agents:read", "files:upload"],
            rate_limit=100
        )
        logger.info(f"创建默认API Key: {default_key['key_id']}")
    
    def generate_key_pair(self) -> tuple[str, str]:
        """生成API Key对"""
        key_id = f"ak_{secrets.token_urlsafe(16)}"
        key_secret = secrets.token_urlsafe(32)
        return key_id, key_secret
    
    def create_api_key(
        self,
        name: str,
        permissions: List[str] = None,
        rate_limit: int = 1000,
        expires_days: Optional[int] = None,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """创建新的API Key"""
        key_id, key_secret = self.generate_key_pair()
        
        expires_at = None
        if expires_days:
            expires_at = datetime.now() + timedelta(days=expires_days)
        
        api_key = APIKey(
            key_id=key_id,
            key_secret=key_secret,
            name=name,
            permissions=permissions or [],
            rate_limit=rate_limit,
            expires_at=expires_at,
            metadata=metadata or {}
        )
        
        self.api_keys[key_id] = api_key
        
        return {
            "key_id": key_id,
            "key_secret": key_secret,
            "name": name,
            "permissions": permissions or [],
            "rate_limit": rate_limit,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "created_at": api_key.created_at.isoformat()
        }
    
    def get_api_key(self, key_id: str) -> Optional[APIKey]:
        """获取API Key"""
        return self.api_keys.get(key_id)
    
    def validate_api_key(self, key_id: str, key_secret: str) -> Optional[APIKey]:
        """验证API Key"""
        api_key = self.get_api_key(key_id)
        
        if not api_key:
            return None
        
        # 检查密钥是否匹配
        if not hmac.compare_digest(api_key.key_secret, key_secret):
            return None
        
        # 检查是否激活
        if not api_key.is_active:
            return None
        
        # 检查是否过期
        if api_key.expires_at and datetime.now() > api_key.expires_at:
            return None
        
        return api_key
    
    def update_usage(self, api_key: APIKey):
        """更新使用记录"""
        api_key.last_used = datetime.now()
        api_key.usage_count += 1
        self.rate_limiter.record_usage(api_key)
    
    def is_rate_limited(self, api_key: APIKey) -> bool:
        """检查速率限制"""
        return self.rate_limiter.is_rate_limited(api_key)
    
    def get_usage_stats(self, api_key: APIKey) -> Dict[str, Any]:
        """获取使用统计"""
        return self.rate_limiter.get_usage_stats(api_key)
    
    def has_permission(self, api_key: APIKey, required_permission: str) -> bool:
        """检查权限"""
        if not required_permission:
            return True
        
        # 检查具体权限
        if required_permission in api_key.permissions:
            return True
        
        # 检查通配符权限
        for permission in api_key.permissions:
            if permission.endswith(":*"):
                prefix = permission[:-1]  # 去掉 *
                if required_permission.startswith(prefix):
                    return True
        
        return False
    
    def list_api_keys(self) -> List[Dict[str, Any]]:
        """列出所有API Key"""
        result = []
        for api_key in self.api_keys.values():
            result.append({
                "key_id": api_key.key_id,
                "name": api_key.name,
                "permissions": api_key.permissions,
                "rate_limit": api_key.rate_limit,
                "is_active": api_key.is_active,
                "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
                "created_at": api_key.created_at.isoformat(),
                "last_used": api_key.last_used.isoformat() if api_key.last_used else None,
                "usage_count": api_key.usage_count,
                "metadata": api_key.metadata
            })
        return result
    
    def revoke_api_key(self, key_id: str) -> bool:
        """撤销API Key"""
        api_key = self.get_api_key(key_id)
        if api_key:
            api_key.is_active = False
            return True
        return False


# 全局API Key管理器实例
api_key_manager = APIKeyManager()


def extract_api_key_from_header(request: Request) -> tuple[Optional[str], Optional[str]]:
    """从请求头提取API Key"""
    # 支持多种认证方式
    
    # 方式1: X-API-Key 和 X-API-Secret 头
    api_key_id = request.headers.get("X-API-Key")
    api_key_secret = request.headers.get("X-API-Secret")
    
    if api_key_id and api_key_secret:
        return api_key_id, api_key_secret
    
    # 方式2: Authorization 头，格式: Bearer {key_id}:{key_secret}
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        if ":" in token:
            key_id, key_secret = token.split(":", 1)
            return key_id, key_secret
    
    # 方式3: API-Key 查询参数（不推荐，仅用于测试）
    api_key_param = request.query_params.get("api_key")
    api_secret_param = request.query_params.get("api_secret")
    
    if api_key_param and api_secret_param:
        return api_key_param, api_secret_param
    
    return None, None


async def verify_api_key(request: Request) -> Dict[str, Any]:
    """验证API Key的依赖函数"""
    try:
        # 提取API Key
        key_id, key_secret = extract_api_key_from_header(request)
        
        if not key_id or not key_secret:
            raise HTTPException(
                status_code=401,
                detail="缺少API Key。请在请求头中提供 X-API-Key 和 X-API-Secret"
            )
        
        # 验证API Key
        api_key = api_key_manager.validate_api_key(key_id, key_secret)
        
        if not api_key:
            raise HTTPException(
                status_code=401,
                detail="无效的API Key"
            )
        
        # 检查速率限制
        if api_key_manager.is_rate_limited(api_key):
            usage_stats = api_key_manager.get_usage_stats(api_key)
            raise HTTPException(
                status_code=429,
                detail=f"API调用频率超限。限制: {api_key.rate_limit}/小时，重置时间: {usage_stats['reset_time']}"
            )
        
        # 更新使用记录
        api_key_manager.update_usage(api_key)
        
        # 记录访问日志
        logger.info(f"API Key {key_id} ({api_key.name}) 访问 {request.url.path}")
        
        # 返回API Key信息
        return {
            "key_id": api_key.key_id,
            "name": api_key.name,
            "permissions": api_key.permissions,
            "usage_stats": api_key_manager.get_usage_stats(api_key)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API Key验证失败: {str(e)}")
        raise HTTPException(status_code=401, detail="API Key验证失败")


def require_api_permission(required_permission: str):
    """API权限验证装饰器"""
    async def permission_dependency(
        api_key_info: Dict[str, Any] = Depends(verify_api_key),
        request: Request = None
    ):
        key_id = api_key_info["key_id"]
        api_key = api_key_manager.get_api_key(key_id)
        
        if not api_key or not api_key_manager.has_permission(api_key, required_permission):
            raise HTTPException(
                status_code=403,
                detail=f"API Key缺少权限: {required_permission}"
            )
        
        return api_key_info
    
    return permission_dependency


# 便于外部使用的函数
def create_api_key(
    name: str,
    permissions: List[str] = None,
    rate_limit: int = 1000,
    expires_days: Optional[int] = None,
    metadata: Dict[str, Any] = None
) -> Dict[str, Any]:
    """创建API Key（供外部调用）"""
    return api_key_manager.create_api_key(
        name=name,
        permissions=permissions,
        rate_limit=rate_limit,
        expires_days=expires_days,
        metadata=metadata
    )


def list_api_keys() -> List[Dict[str, Any]]:
    """列出所有API Key（供外部调用）"""
    return api_key_manager.list_api_keys()


def revoke_api_key(key_id: str) -> bool:
    """撤销API Key（供外部调用）"""
    return api_key_manager.revoke_api_key(key_id)


def get_api_key_usage(key_id: str) -> Optional[Dict[str, Any]]:
    """获取API Key使用情况（供外部调用）"""
    api_key = api_key_manager.get_api_key(key_id)
    if api_key:
        return api_key_manager.get_usage_stats(api_key)
    return None 