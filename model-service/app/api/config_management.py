"""
模型配置管理API
提供用户自定义模型配置的创建、管理和切换功能
"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
import uuid
import json

from ..schemas.model_provider import ModelType
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
config_router = APIRouter(prefix="/api/v1/models", tags=["模型配置管理"])

# 扩展数据模型

class UserConfigRequest(BaseModel):
    """用户配置请求"""
    name: str = Field(..., description="配置名称")
    category: ModelType = Field(..., description="模型类别")
    provider_id: str = Field(..., description="提供商ID")
    model_id: str = Field(..., description="模型ID")
    config_params: Dict[str, Any] = Field(..., description="配置参数")
    is_default: bool = Field(False, description="是否设为默认配置")
    user_id: str = Field(..., description="用户ID")

class SwitchConfigRequest(BaseModel):
    """切换配置请求"""
    category: ModelType = Field(..., description="模型类别")
    provider_id: str = Field(..., description="提供商ID")
    model_id: str = Field(..., description="模型ID")
    config_id: Optional[str] = Field(None, description="配置ID，为空则使用默认配置")
    user_id: str = Field(..., description="用户ID")

class UserModelConfig(BaseModel):
    """用户模型配置"""
    id: str
    user_id: str
    name: str
    category: ModelType
    provider_id: str
    model_id: str
    config_params: Dict[str, Any]
    is_default: bool
    usage_count: int
    last_used_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

class FrontendStateUpdate(BaseModel):
    """前端状态更新"""
    user_id: str = Field(..., description="用户ID")
    active_configs: Optional[Dict[str, str]] = Field(None, description="激活的配置")
    recent_models: Optional[List[Dict[str, Any]]] = Field(None, description="最近使用的模型")
    preferences: Optional[Dict[str, Any]] = Field(None, description="用户偏好")

# 内存存储 - 用户配置
user_configs_db: Dict[str, Dict] = {}
frontend_states_db: Dict[str, Dict] = {}

def _generate_id() -> str:
    """生成UUID"""
    return str(uuid.uuid4())

def _get_provider_info(provider_id: str) -> Dict[str, Any]:
    """获取提供商信息"""
    from .models import SUPPORTED_PROVIDERS
    return SUPPORTED_PROVIDERS.get(provider_id, {})

def _get_model_info(provider_id: str, model_id: str) -> Dict[str, Any]:
    """获取模型信息"""
    from .models import SUPPORTED_PROVIDERS
    provider_data = SUPPORTED_PROVIDERS.get(provider_id, {})
    for model in provider_data.get("models", []):
        if model["model_id"] == model_id:
            return model
    return {}

# ==================== 用户配置管理接口 ====================

@config_router.post("/user-configs")
async def save_user_config(request: UserConfigRequest):
    """
    保存用户的模型配置
    """
    try:
        from .models import SUPPORTED_PROVIDERS
        
        # 验证提供商和模型是否存在
        if request.provider_id not in SUPPORTED_PROVIDERS:
            raise HTTPException(status_code=404, detail="提供商不存在")
        
        provider_data = SUPPORTED_PROVIDERS[request.provider_id]
        model_info = _get_model_info(request.provider_id, request.model_id)
        
        if not model_info:
            raise HTTPException(status_code=404, detail="模型不存在")
        
        # 验证模型类型匹配
        if model_info.get("model_type") != request.category:
            raise HTTPException(status_code=400, detail=f"模型类型不匹配，期望: {request.category}")
        
        # 检查配置名称是否重复
        existing_configs = [
            config for config in user_configs_db.values()
            if config["user_id"] == request.user_id 
            and config["name"] == request.name
            and config["category"] == request.category
        ]
        
        if existing_configs:
            raise HTTPException(status_code=400, detail="配置名称已存在")
        
        config_id = _generate_id()
        now = datetime.now()
        
        # 如果设为默认，取消同类别其他默认配置
        if request.is_default:
            for config in user_configs_db.values():
                if (config["user_id"] == request.user_id 
                    and config["category"] == request.category 
                    and config["is_default"]):
                    config["is_default"] = False
                    config["updated_at"] = now.isoformat()
        
        # 保存配置
        provider_info = _get_provider_info(request.provider_id)
        
        user_configs_db[config_id] = {
            "id": config_id,
            "user_id": request.user_id,
            "name": request.name,
            "category": request.category,
            "provider_id": request.provider_id,
            "model_id": request.model_id,
            "model_name": model_info.get("name", request.model_id),
            "provider_name": provider_info.get("name", request.provider_id),
            "config_params": request.config_params,
            "is_default": request.is_default,
            "usage_count": 0,
            "last_used_at": None,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }
        
        return {
            "success": True,
            "message": "用户配置保存成功",
            "data": user_configs_db[config_id]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"保存用户配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail="保存用户配置失败")

@config_router.get("/user-configs")
async def get_user_configs(
    user_id: str = Query(..., description="用户ID"),
    category: Optional[ModelType] = Query(None, description="模型类别筛选"),
    search: Optional[str] = Query(None, description="搜索关键词")
):
    """
    获取用户的模型配置列表
    """
    try:
        configs = []
        
        for config_data in user_configs_db.values():
            # 用户筛选
            if config_data["user_id"] != user_id:
                continue
            
            # 类别筛选
            if category and config_data["category"] != category:
                continue
            
            # 搜索筛选
            if search:
                search_text = f"{config_data['name']} {config_data['model_name']} {config_data['provider_name']}".lower()
                if search.lower() not in search_text:
                    continue
            
            configs.append(config_data)
        
        # 按使用次数和更新时间排序
        configs.sort(key=lambda x: (x["usage_count"], x["updated_at"]), reverse=True)
        
        return {
            "success": True,
            "data": {
                "configs": configs,
                "total": len(configs),
                "filters": {
                    "category": category,
                    "search": search
                }
            }
        }
        
    except Exception as e:
        logger.error(f"获取用户配置列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取用户配置列表失败")

@config_router.get("/user-configs/{config_id}")
async def get_user_config_details(
    config_id: str,
    user_id: str = Query(..., description="用户ID")
):
    """
    获取用户配置详情
    """
    try:
        if config_id not in user_configs_db:
            raise HTTPException(status_code=404, detail="配置不存在")
        
        config_data = user_configs_db[config_id]
        
        # 验证用户权限
        if config_data["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="无权限访问此配置")
        
        # 获取模型和提供商的详细信息
        provider_info = _get_provider_info(config_data["provider_id"])
        model_info = _get_model_info(config_data["provider_id"], config_data["model_id"])
        
        enhanced_config = {
            **config_data,
            "provider_info": provider_info,
            "model_info": model_info
        }
        
        return {
            "success": True,
            "data": enhanced_config
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取用户配置详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取用户配置详情失败")

@config_router.put("/user-configs/{config_id}")
async def update_user_config(
    config_id: str,
    request: dict,
    user_id: str = Query(..., description="用户ID")
):
    """
    更新用户配置
    """
    try:
        if config_id not in user_configs_db:
            raise HTTPException(status_code=404, detail="配置不存在")
        
        config_data = user_configs_db[config_id]
        
        # 验证用户权限
        if config_data["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="无权限修改此配置")
        
        # 更新配置
        updatable_fields = ["name", "config_params", "is_default"]
        updated_fields = []
        
        for field in updatable_fields:
            if field in request:
                if field == "name":
                    # 检查名称是否重复
                    existing_configs = [
                        config for config in user_configs_db.values()
                        if config["user_id"] == user_id 
                        and config["name"] == request[field]
                        and config["category"] == config_data["category"]
                        and config["id"] != config_id
                    ]
                    
                    if existing_configs:
                        raise HTTPException(status_code=400, detail="配置名称已存在")
                
                if field == "is_default" and request[field]:
                    # 取消同类别其他默认配置
                    for config in user_configs_db.values():
                        if (config["user_id"] == user_id 
                            and config["category"] == config_data["category"] 
                            and config["id"] != config_id
                            and config["is_default"]):
                            config["is_default"] = False
                
                config_data[field] = request[field]
                updated_fields.append(field)
        
        if updated_fields:
            config_data["updated_at"] = datetime.now().isoformat()
        
        return {
            "success": True,
            "message": "用户配置更新成功",
            "data": {
                "config_id": config_id,
                "updated_fields": updated_fields,
                "config": config_data
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新用户配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail="更新用户配置失败")

@config_router.delete("/user-configs/{config_id}")
async def delete_user_config(
    config_id: str,
    user_id: str = Query(..., description="用户ID")
):
    """
    删除用户配置
    """
    try:
        if config_id not in user_configs_db:
            raise HTTPException(status_code=404, detail="配置不存在")
        
        config_data = user_configs_db[config_id]
        
        # 验证用户权限
        if config_data["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="无权限删除此配置")
        
        # 删除配置
        deleted_config = user_configs_db.pop(config_id)
        
        return {
            "success": True,
            "message": "用户配置删除成功",
            "data": {
                "config_id": config_id,
                "deleted_config": deleted_config
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除用户配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail="删除用户配置失败")

# ==================== 配置切换接口 ====================

@config_router.put("/active-config")
async def switch_active_config(request: SwitchConfigRequest):
    """
    切换当前激活的模型配置
    """
    try:
        from .models import SUPPORTED_PROVIDERS
        
        # 验证提供商和模型是否存在
        if request.provider_id not in SUPPORTED_PROVIDERS:
            raise HTTPException(status_code=404, detail="提供商不存在")
        
        model_info = _get_model_info(request.provider_id, request.model_id)
        if not model_info:
            raise HTTPException(status_code=404, detail="模型不存在")
        
        # 验证模型类型匹配
        if model_info.get("model_type") != request.category:
            raise HTTPException(status_code=400, detail=f"模型类型不匹配，期望: {request.category}")
        
        # 获取或创建用户前端状态
        user_id = request.user_id
        if user_id not in frontend_states_db:
            frontend_states_db[user_id] = {
                "user_id": user_id,
                "active_configs": {},
                "recent_models": [],
                "preferences": {},
                "last_activity": datetime.now().isoformat(),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
        
        user_state = frontend_states_db[user_id]
        
        # 更新激活配置
        config_key = f"{request.provider_id}_{request.model_id}"
        if request.config_id:
            # 验证配置是否存在且属于该用户
            if request.config_id not in user_configs_db:
                raise HTTPException(status_code=404, detail="用户配置不存在")
            
            config_data = user_configs_db[request.config_id]
            if config_data["user_id"] != user_id:
                raise HTTPException(status_code=403, detail="无权限使用此配置")
            
            user_state["active_configs"][request.category] = request.config_id
            
            # 更新配置使用统计
            config_data["usage_count"] += 1
            config_data["last_used_at"] = datetime.now().isoformat()
        else:
            # 使用默认配置
            user_state["active_configs"][request.category] = "default"
        
        # 更新最近使用的模型
        recent_model = {
            "category": request.category,
            "provider_id": request.provider_id,
            "model_id": request.model_id,
            "provider_name": _get_provider_info(request.provider_id).get("name"),
            "model_name": model_info.get("name"),
            "config_id": request.config_id,
            "used_at": datetime.now().isoformat()
        }
        
        # 移除重复记录并添加到首位
        user_state["recent_models"] = [
            m for m in user_state["recent_models"]
            if not (m["provider_id"] == request.provider_id and m["model_id"] == request.model_id)
        ]
        user_state["recent_models"].insert(0, recent_model)
        
        # 保持最近使用列表长度
        if len(user_state["recent_models"]) > 10:
            user_state["recent_models"] = user_state["recent_models"][:10]
        
        # 更新状态时间戳
        user_state["last_activity"] = datetime.now().isoformat()
        user_state["updated_at"] = datetime.now().isoformat()
        
        return {
            "success": True,
            "message": "配置切换成功",
            "data": {
                "category": request.category,
                "provider_id": request.provider_id,
                "model_id": request.model_id,
                "config_id": request.config_id,
                "active_config": user_state["active_configs"][request.category]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"切换配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail="切换配置失败")

@config_router.get("/active-config")
async def get_active_configs(user_id: str = Query(..., description="用户ID")):
    """
    获取用户当前激活的配置
    """
    try:
        if user_id not in frontend_states_db:
            return {
                "success": True,
                "data": {
                    "active_configs": {},
                    "recent_models": [],
                    "message": "用户尚未设置任何配置"
                }
            }
        
        user_state = frontend_states_db[user_id]
        
        # 获取激活配置的详细信息
        active_config_details = {}
        for category, config_ref in user_state["active_configs"].items():
            if config_ref == "default":
                # 获取系统默认配置
                from .defaults import default_configs_db
                default_config = None
                for config_data in default_configs_db.values():
                    if config_data["category"] == category and config_data["scope"] == "system":
                        default_config = config_data
                        break
                
                active_config_details[category] = {
                    "type": "default",
                    "config": default_config
                }
            else:
                # 获取用户自定义配置
                if config_ref in user_configs_db:
                    active_config_details[category] = {
                        "type": "user",
                        "config": user_configs_db[config_ref]
                    }
        
        return {
            "success": True,
            "data": {
                "active_configs": active_config_details,
                "recent_models": user_state["recent_models"],
                "last_activity": user_state["last_activity"]
            }
        }
        
    except Exception as e:
        logger.error(f"获取激活配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取激活配置失败")

# ==================== 前端状态管理接口 ====================

@config_router.get("/frontend/state")
async def get_frontend_state(user_id: str = Query(..., description="用户ID")):
    """
    获取前端当前状态
    """
    try:
        if user_id not in frontend_states_db:
            # 创建默认状态
            frontend_states_db[user_id] = {
                "user_id": user_id,
                "active_configs": {},
                "recent_models": [],
                "preferences": {},
                "last_activity": datetime.now().isoformat(),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
        
        user_state = frontend_states_db[user_id]
        
        return {
            "success": True,
            "data": user_state
        }
        
    except Exception as e:
        logger.error(f"获取前端状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取前端状态失败")

@config_router.put("/frontend/state")
async def update_frontend_state(request: FrontendStateUpdate):
    """
    更新前端状态
    """
    try:
        user_id = request.user_id
        
        # 获取或创建用户状态
        if user_id not in frontend_states_db:
            frontend_states_db[user_id] = {
                "user_id": user_id,
                "active_configs": {},
                "recent_models": [],
                "preferences": {},
                "last_activity": datetime.now().isoformat(),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
        
        user_state = frontend_states_db[user_id]
        
        # 更新状态
        updated_fields = []
        
        if request.active_configs is not None:
            user_state["active_configs"].update(request.active_configs)
            updated_fields.append("active_configs")
        
        if request.recent_models is not None:
            user_state["recent_models"] = request.recent_models[:10]  # 限制长度
            updated_fields.append("recent_models")
        
        if request.preferences is not None:
            user_state["preferences"].update(request.preferences)
            updated_fields.append("preferences")
        
        # 更新时间戳
        user_state["last_activity"] = datetime.now().isoformat()
        user_state["updated_at"] = datetime.now().isoformat()
        
        return {
            "success": True,
            "message": "前端状态更新成功",
            "data": {
                "updated_fields": updated_fields,
                "state": user_state
            }
        }
        
    except Exception as e:
        logger.error(f"更新前端状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail="更新前端状态失败")

# ==================== 统计接口 ====================

@config_router.get("/user-configs/statistics")
async def get_user_config_statistics(user_id: str = Query(..., description="用户ID")):
    """
    获取用户配置统计信息
    """
    try:
        user_configs = [
            config for config in user_configs_db.values()
            if config["user_id"] == user_id
        ]
        
        # 按类别统计
        category_stats = {}
        total_usage = 0
        
        for config in user_configs:
            category = config["category"]
            if category not in category_stats:
                category_stats[category] = {
                    "total_configs": 0,
                    "default_configs": 0,
                    "total_usage": 0
                }
            
            category_stats[category]["total_configs"] += 1
            if config["is_default"]:
                category_stats[category]["default_configs"] += 1
            category_stats[category]["total_usage"] += config["usage_count"]
            total_usage += config["usage_count"]
        
        # 最常用的配置
        most_used_configs = sorted(user_configs, key=lambda x: x["usage_count"], reverse=True)[:5]
        
        # 最近创建的配置
        recent_configs = sorted(user_configs, key=lambda x: x["created_at"], reverse=True)[:5]
        
        return {
            "success": True,
            "data": {
                "total_configs": len(user_configs),
                "total_usage": total_usage,
                "category_statistics": category_stats,
                "most_used_configs": most_used_configs,
                "recent_configs": recent_configs,
                "created_at": min([c["created_at"] for c in user_configs]) if user_configs else None,
                "last_updated": max([c["updated_at"] for c in user_configs]) if user_configs else None
            }
        }
        
    except Exception as e:
        logger.error(f"获取用户配置统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取用户配置统计失败")