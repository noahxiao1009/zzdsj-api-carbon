"""
内部系统认证中间件
用于系统内部调用system接口的内部Token验证
"""

import hashlib
import hmac
import secrets
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from fastapi import HTTPException, Depends, Request, Header
import jwt

logger = logging.getLogger(__name__)

# 内部Token配置
INTERNAL_SECRET_KEY = "internal-secret-key-change-in-production"  # 应从环境变量获取
INTERNAL_TOKEN_ALGORITHM = "HS256"
INTERNAL_TOKEN_EXPIRATION = timedelta(hours=1)


class InternalTokenManager:
    """内部Token管理器"""
    
    def __init__(self, secret_key: str = INTERNAL_SECRET_KEY):
        self.secret_key = secret_key
        self.algorithm = INTERNAL_TOKEN_ALGORITHM
        self.valid_services = {
            "gateway-service": "网关服务",
            "agent-service": "智能体服务",
            "knowledge-service": "知识库服务",
            "model-service": "模型服务",
            "base-service": "基础服务",
            "database-service": "数据库服务",
            "system-service": "系统服务",
            "knowledge-graph-service": "知识图谱服务",
            "mcp-service": "MCP服务"
        }
    
    def generate_token(self, service_name: str, permissions: list = None) -> str:
        """生成内部Token"""
        if service_name not in self.valid_services:
            raise ValueError(f"无效的服务名称: {service_name}")
        
        payload = {
            "service_name": service_name,
            "service_description": self.valid_services[service_name],
            "permissions": permissions or ["system:*"],  # 默认给予系统全权限
            "exp": datetime.utcnow() + INTERNAL_TOKEN_EXPIRATION,
            "iat": datetime.utcnow(),
            "type": "internal_token",
            "issuer": "gateway-service"
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """验证内部Token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # 检查token类型
            if payload.get("type") != "internal_token":
                raise jwt.InvalidTokenError("Invalid token type")
            
            # 检查发行者
            if payload.get("issuer") != "gateway-service":
                raise jwt.InvalidTokenError("Invalid token issuer")
            
            # 检查服务名称是否有效
            service_name = payload.get("service_name")
            if service_name not in self.valid_services:
                raise jwt.InvalidTokenError("Invalid service name")
            
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("内部Token已过期")
            raise HTTPException(status_code=401, detail="内部Token已过期")
        except jwt.InvalidTokenError as e:
            logger.warning(f"无效的内部Token: {str(e)}")
            raise HTTPException(status_code=401, detail="无效的内部Token")
        except Exception as e:
            logger.error(f"内部Token验证失败: {str(e)}")
            raise HTTPException(status_code=401, detail="内部Token验证失败")
    
    def has_permission(self, token_data: Dict[str, Any], required_permission: str) -> bool:
        """检查权限"""
        permissions = token_data.get("permissions", [])
        
        # 检查具体权限
        if required_permission in permissions:
            return True
        
        # 检查通配符权限
        for permission in permissions:
            if permission.endswith(":*"):
                prefix = permission[:-1]  # 去掉 *
                if required_permission.startswith(prefix):
                    return True
        
        # 系统全权限
        if "system:*" in permissions:
            return True
        
        return False


# 全局内部Token管理器实例
internal_token_manager = InternalTokenManager()


def extract_internal_token(request: Request) -> Optional[str]:
    """从请求中提取内部Token"""
    # 方式1: X-Internal-Token 头
    internal_token = request.headers.get("X-Internal-Token")
    if internal_token:
        return internal_token
    
    # 方式2: Authorization 头，格式: Internal {token}
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.startswith("Internal "):
        return auth_header.split(" ")[1]
    
    # 方式3: 查询参数（不推荐，仅用于调试）
    token_param = request.query_params.get("internal_token")
    if token_param:
        return token_param
    
    return None


async def verify_internal_token(request: Request) -> Dict[str, Any]:
    """验证内部Token的依赖函数"""
    try:
        # 提取内部Token
        token = extract_internal_token(request)
        
        if not token:
            raise HTTPException(
                status_code=401,
                detail="缺少内部Token。请在请求头中提供 X-Internal-Token"
            )
        
        # 验证Token
        token_data = internal_token_manager.verify_token(token)
        
        # 记录内部调用日志
        service_name = token_data.get("service_name")
        logger.info(f"内部服务 {service_name} 访问 {request.url.path}")
        
        return token_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"内部Token验证失败: {str(e)}")
        raise HTTPException(status_code=401, detail="内部认证失败")


def require_internal_permission(required_permission: str):
    """内部权限验证装饰器"""
    async def permission_dependency(
        token_data: Dict[str, Any] = Depends(verify_internal_token)
    ):
        if not internal_token_manager.has_permission(token_data, required_permission):
            service_name = token_data.get("service_name", "unknown")
            raise HTTPException(
                status_code=403,
                detail=f"服务 {service_name} 缺少权限: {required_permission}"
            )
        
        return token_data
    
    return permission_dependency


class ServiceTokens:
    """服务Token管理类"""
    
    def __init__(self):
        self.service_tokens = {}
        self._generate_service_tokens()
    
    def _generate_service_tokens(self):
        """为所有服务生成Token"""
        for service_name in internal_token_manager.valid_services.keys():
            token = internal_token_manager.generate_token(service_name)
            self.service_tokens[service_name] = token
            logger.info(f"为服务 {service_name} 生成内部Token")
    
    def get_service_token(self, service_name: str) -> Optional[str]:
        """获取服务Token"""
        return self.service_tokens.get(service_name)
    
    def refresh_service_token(self, service_name: str) -> str:
        """刷新服务Token"""
        token = internal_token_manager.generate_token(service_name)
        self.service_tokens[service_name] = token
        logger.info(f"刷新服务 {service_name} 的内部Token")
        return token
    
    def refresh_all_tokens(self):
        """刷新所有服务Token"""
        for service_name in internal_token_manager.valid_services.keys():
            self.refresh_service_token(service_name)
        logger.info("刷新所有服务的内部Token")


# 全局服务Token管理器实例
service_tokens = ServiceTokens()


# 服务间调用的辅助函数
def get_internal_token_for_service(service_name: str) -> str:
    """获取服务的内部Token（供微服务调用）"""
    token = service_tokens.get_service_token(service_name)
    if not token:
        raise ValueError(f"服务 {service_name} 的内部Token不存在")
    return token


def create_internal_request_headers(service_name: str) -> Dict[str, str]:
    """创建内部请求的头部（供微服务调用）"""
    token = get_internal_token_for_service(service_name)
    return {
        "X-Internal-Token": token,
        "X-Service-Name": service_name,
        "Content-Type": "application/json"
    }


# 系统管理接口（仅供网关内部使用）
class InternalAuthManager:
    """内部认证管理器"""
    
    @staticmethod
    def generate_service_token(service_name: str, permissions: list = None) -> str:
        """生成服务Token"""
        return internal_token_manager.generate_token(service_name, permissions)
    
    @staticmethod
    def validate_service_token(token: str) -> Dict[str, Any]:
        """验证服务Token"""
        return internal_token_manager.verify_token(token)
    
    @staticmethod
    def list_valid_services() -> Dict[str, str]:
        """列出有效的服务"""
        return internal_token_manager.valid_services.copy()
    
    @staticmethod
    def refresh_all_service_tokens():
        """刷新所有服务Token"""
        service_tokens.refresh_all_tokens()
    
    @staticmethod
    def get_service_token_info(service_name: str) -> Optional[Dict[str, Any]]:
        """获取服务Token信息"""
        token = service_tokens.get_service_token(service_name)
        if not token:
            return None
        
        try:
            token_data = internal_token_manager.verify_token(token)
            return {
                "service_name": token_data.get("service_name"),
                "service_description": token_data.get("service_description"),
                "permissions": token_data.get("permissions"),
                "expires_at": datetime.fromtimestamp(token_data.get("exp")).isoformat(),
                "issued_at": datetime.fromtimestamp(token_data.get("iat")).isoformat()
            }
        except Exception:
            return None


# 全局内部认证管理器实例
internal_auth_manager = InternalAuthManager() 