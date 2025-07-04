"""
MCP Service 服务管理API
提供MCP服务的创建、配置、部署、管理等接口
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.core.config import settings
from app.core.database import get_db
from app.models.mcp import MCPServiceConfig, MCPServiceDeployment, MCPServiceHealthCheck
from app.services.mcp_manager import MCPServiceManager
from app.services.deployment_manager import DeploymentManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/services", tags=["MCP服务管理"])


# 依赖注入
def get_service_manager() -> MCPServiceManager:
    """获取MCP服务管理器"""
    return MCPServiceManager()


def get_deployment_manager() -> DeploymentManager:
    """获取部署管理器"""
    return DeploymentManager()


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_service(
    service_data: dict,
    db: Session = Depends(get_db),
    service_manager: MCPServiceManager = Depends(get_service_manager)
):
    """
    创建新的MCP服务配置
    
    参数:
        service_data: 服务配置数据
    """
    try:
        # 检查服务名称是否已存在
        existing_service = db.query(MCPServiceConfig).filter(
            MCPServiceConfig.name == service_data.get("name")
        ).first()
        
        if existing_service:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"服务名称 '{service_data.get('name')}' 已存在"
            )
        
        # 创建服务配置
        service = await service_manager.create_service(service_data, db)
        
        logger.info(f"创建MCP服务成功: {service.name}")
        
        return {
            "success": True,
            "message": "服务创建成功",
            "data": {
                "id": service.id,
                "deployment_id": service.deployment_id,
                "name": service.name,
                "status": service.status,
                "created_at": service.created_at.isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建MCP服务失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建服务失败: {str(e)}"
        )


@router.get("/")
async def list_services(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页大小"),
    status_filter: Optional[str] = Query(None, description="状态筛选"),
    service_type: Optional[str] = Query(None, description="服务类型筛选"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    db: Session = Depends(get_db)
):
    """
    获取MCP服务列表
    
    支持分页、筛选和搜索
    """
    try:
        # 构建查询
        query = db.query(MCPServiceConfig)
        
        # 状态筛选
        if status_filter:
            query = query.filter(MCPServiceConfig.status == status_filter)
        
        # 服务类型筛选
        if service_type:
            query = query.filter(MCPServiceConfig.service_type == service_type)
        
        # 搜索
        if search:
            search_filter = or_(
                MCPServiceConfig.name.ilike(f"%{search}%"),
                MCPServiceConfig.description.ilike(f"%{search}%")
            )
            query = query.filter(search_filter)
        
        # 总数
        total = query.count()
        
        # 分页
        offset = (page - 1) * size
        services = query.offset(offset).limit(size).all()
        
        # 计算总页数
        pages = (total + size - 1) // size
        
        # 构建响应数据
        items = []
        for service in services:
            items.append({
                "id": service.id,
                "deployment_id": service.deployment_id,
                "name": service.name,
                "description": service.description,
                "service_type": service.service_type,
                "status": service.status,
                "image": service.image,
                "service_port": service.service_port,
                "host_port": service.host_port,
                "ip_address": service.ip_address,
                "created_at": service.created_at.isoformat(),
                "updated_at": service.updated_at.isoformat(),
                "last_health_check": service.last_health_check.isoformat() if service.last_health_check else None
            })
        
        return {
            "success": True,
            "data": {
                "items": items,
                "pagination": {
                    "total": total,
                    "page": page,
                    "size": size,
                    "pages": pages
                }
            }
        }
        
    except Exception as e:
        logger.error(f"获取服务列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取服务列表失败: {str(e)}"
        )


@router.get("/{service_id}")
async def get_service(
    service_id: int = Path(..., description="服务ID"),
    db: Session = Depends(get_db)
):
    """
    获取指定MCP服务的详细信息
    """
    try:
        service = db.query(MCPServiceConfig).filter(
            MCPServiceConfig.id == service_id
        ).first()
        
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"服务不存在: {service_id}"
            )
        
        # 获取工具数量
        tools_count = len(service.tools) if service.tools else 0
        
        # 获取最近的健康检查
        latest_health_check = db.query(MCPServiceHealthCheck).filter(
            MCPServiceHealthCheck.service_config_id == service_id
        ).order_by(MCPServiceHealthCheck.checked_at.desc()).first()
        
        # 获取部署历史
        deployment_history = db.query(MCPServiceDeployment).filter(
            MCPServiceDeployment.service_config_id == service_id
        ).order_by(MCPServiceDeployment.started_at.desc()).limit(5).all()
        
        service_data = {
            "id": service.id,
            "deployment_id": service.deployment_id,
            "name": service.name,
            "description": service.description,
            "service_type": service.service_type,
            "status": service.status,
            
            # Docker信息
            "image": service.image,
            "container_id": service.container_id,
            "service_port": service.service_port,
            "host_port": service.host_port,
            "deploy_directory": service.deploy_directory,
            
            # 网络配置
            "network_name": service.network_name,
            "ip_address": service.ip_address,
            
            # 配置信息
            "settings": service.settings,
            "environment_vars": service.environment_vars,
            
            # 资源限制
            "cpu_limit": service.cpu_limit,
            "memory_limit": service.memory_limit,
            "disk_limit": service.disk_limit,
            
            # 健康检查配置
            "health_check_url": service.health_check_url,
            "health_check_interval": service.health_check_interval,
            "health_check_timeout": service.health_check_timeout,
            "health_check_retries": service.health_check_retries,
            
            # 时间信息
            "created_at": service.created_at.isoformat(),
            "updated_at": service.updated_at.isoformat(),
            "last_started_at": service.last_started_at.isoformat() if service.last_started_at else None,
            "last_stopped_at": service.last_stopped_at.isoformat() if service.last_stopped_at else None,
            "last_health_check": service.last_health_check.isoformat() if service.last_health_check else None,
            
            # 统计信息
            "tools_count": tools_count,
            
            # 最新健康检查
            "latest_health_check": {
                "status": latest_health_check.status if latest_health_check else "unknown",
                "checked_at": latest_health_check.checked_at.isoformat() if latest_health_check else None,
                "response_time_ms": latest_health_check.response_time_ms if latest_health_check else None
            } if latest_health_check else None,
            
            # 部署历史
            "deployment_history": [
                {
                    "deployment_id": dep.deployment_id,
                    "status": dep.status,
                    "deployment_type": dep.deployment_type,
                    "started_at": dep.started_at.isoformat(),
                    "completed_at": dep.completed_at.isoformat() if dep.completed_at else None,
                    "duration_seconds": dep.duration_seconds
                }
                for dep in deployment_history
            ]
        }
        
        return {
            "success": True,
            "data": service_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取服务详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取服务详情失败: {str(e)}"
        )


@router.put("/{service_id}")
async def update_service(
    service_id: int = Path(..., description="服务ID"),
    service_data: dict = None,
    db: Session = Depends(get_db),
    service_manager: MCPServiceManager = Depends(get_service_manager)
):
    """
    更新MCP服务配置
    """
    try:
        service = db.query(MCPServiceConfig).filter(
            MCPServiceConfig.id == service_id
        ).first()
        
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"服务不存在: {service_id}"
            )
        
        # 更新服务配置
        updated_service = await service_manager.update_service(service_id, service_data, db)
        
        logger.info(f"更新MCP服务成功: {updated_service.name}")
        
        return {
            "success": True,
            "message": "服务更新成功",
            "data": {
                "id": updated_service.id,
                "name": updated_service.name,
                "status": updated_service.status,
                "updated_at": updated_service.updated_at.isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新MCP服务失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新服务失败: {str(e)}"
        )


@router.delete("/{service_id}")
async def delete_service(
    service_id: int = Path(..., description="服务ID"),
    force: bool = Query(False, description="是否强制删除"),
    db: Session = Depends(get_db),
    service_manager: MCPServiceManager = Depends(get_service_manager)
):
    """
    删除MCP服务
    """
    try:
        service = db.query(MCPServiceConfig).filter(
            MCPServiceConfig.id == service_id
        ).first()
        
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"服务不存在: {service_id}"
            )
        
        # 检查服务状态
        if service.status == "running" and not force:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="服务正在运行，请先停止服务或使用force=true强制删除"
            )
        
        # 删除服务
        await service_manager.delete_service(service_id, force, db)
        
        logger.info(f"删除MCP服务成功: {service.name}")
        
        return {
            "success": True,
            "message": "服务删除成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除MCP服务失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除服务失败: {str(e)}"
        )


@router.post("/{service_id}/start")
async def start_service(
    service_id: int = Path(..., description="服务ID"),
    db: Session = Depends(get_db),
    service_manager: MCPServiceManager = Depends(get_service_manager)
):
    """
    启动MCP服务
    """
    try:
        result = await service_manager.start_service(service_id, db)
        
        return {
            "success": True,
            "message": "服务启动请求已提交",
            "data": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动MCP服务失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"启动服务失败: {str(e)}"
        )


@router.post("/{service_id}/stop")
async def stop_service(
    service_id: int = Path(..., description="服务ID"),
    force: bool = Query(False, description="是否强制停止"),
    db: Session = Depends(get_db),
    service_manager: MCPServiceManager = Depends(get_service_manager)
):
    """
    停止MCP服务
    """
    try:
        result = await service_manager.stop_service(service_id, force, db)
        
        return {
            "success": True,
            "message": "服务停止请求已提交",
            "data": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"停止MCP服务失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"停止服务失败: {str(e)}"
        )


@router.post("/{service_id}/restart")
async def restart_service(
    service_id: int = Path(..., description="服务ID"),
    db: Session = Depends(get_db),
    service_manager: MCPServiceManager = Depends(get_service_manager)
):
    """
    重启MCP服务
    """
    try:
        result = await service_manager.restart_service(service_id, db)
        
        return {
            "success": True,
            "message": "服务重启请求已提交",
            "data": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重启MCP服务失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"重启服务失败: {str(e)}"
        )


@router.get("/{service_id}/health")
async def check_service_health(
    service_id: int = Path(..., description="服务ID"),
    db: Session = Depends(get_db),
    service_manager: MCPServiceManager = Depends(get_service_manager)
):
    """
    检查MCP服务健康状态
    """
    try:
        health_result = await service_manager.check_service_health(service_id, db)
        
        return {
            "success": True,
            "data": health_result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"检查服务健康状态失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"检查服务健康状态失败: {str(e)}"
        )


@router.get("/{service_id}/logs")
async def get_service_logs(
    service_id: int = Path(..., description="服务ID"),
    lines: int = Query(100, ge=1, le=1000, description="日志行数"),
    since: Optional[str] = Query(None, description="开始时间"),
    db: Session = Depends(get_db),
    service_manager: MCPServiceManager = Depends(get_service_manager)
):
    """
    获取MCP服务日志
    """
    try:
        logs = await service_manager.get_service_logs(service_id, lines, since, db)
        
        return {
            "success": True,
            "data": logs
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取服务日志失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取服务日志失败: {str(e)}"
        )


# 导出路由
__all__ = ["router"] 