"""
项目服务层
提供数据集项目管理的业务逻辑
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import json

from ..models.project import (
    KnowledgeGraphProject, 
    ProjectCreateRequest,
    ProjectUpdateRequest,
    ProjectListResponse,
    ProjectMemberManageRequest,
    ProjectBulkOperationRequest,
    ProjectStatus,
    ProjectMember,
    ProjectPermission,
    ProjectStatistics,
    generate_project_id,
    validate_project_permission,
    update_project_statistics
)
from ..models.graph import KnowledgeGraph
from ..repositories.arangodb_repository import ArangoDBRepository, get_arangodb_repository
from ..config.settings import settings

logger = logging.getLogger(__name__)


class ProjectService:
    """项目服务
    
    管理知识图谱项目的创建、更新、权限控制和统计
    """
    
    def __init__(self):
        """初始化项目服务"""
        self.arangodb_repo: Optional[ArangoDBRepository] = None
    
    async def initialize(self):
        """初始化服务依赖"""
        if not self.arangodb_repo:
            self.arangodb_repo = await get_arangodb_repository()
    
    async def create_project(self, request: ProjectCreateRequest, user_id: str) -> KnowledgeGraphProject:
        """创建项目"""
        await self.initialize()
        
        try:
            # 生成项目ID
            project_id = generate_project_id(user_id, request.name)
            
            # 创建项目对象
            project = KnowledgeGraphProject(
                project_id=project_id,
                name=request.name,
                description=request.description,
                project_type=request.project_type,
                status=ProjectStatus.ACTIVE,
                owner_id=user_id,
                knowledge_base_ids=request.knowledge_base_ids,
                tags=request.tags,
                settings=request.settings or {},
                statistics=ProjectStatistics()
            )
            
            # 保存项目
            await self.arangodb_repo.save_project(project)
            
            logger.info(f"Created project: {project_id} by user {user_id}")
            return project
            
        except Exception as e:
            logger.error(f"Failed to create project: {e}")
            raise
    
    async def get_project(self, project_id: str, user_id: str) -> Optional[KnowledgeGraphProject]:
        """获取项目详情"""
        await self.initialize()
        
        try:
            project = await self.arangodb_repo.get_project(project_id)
            if not project:
                return None
            
            # 权限检查
            if not validate_project_permission(user_id, project, ProjectPermission.VIEWER):
                raise PermissionError("无权限访问此项目")
            
            # 更新最后访问时间
            project.last_accessed_at = datetime.now()
            await self.arangodb_repo.save_project(project)
            
            return project
            
        except Exception as e:
            logger.error(f"Failed to get project {project_id}: {e}")
            raise
    
    async def update_project(self, project_id: str, request: ProjectUpdateRequest, user_id: str) -> Optional[KnowledgeGraphProject]:
        """更新项目"""
        await self.initialize()
        
        try:
            project = await self.arangodb_repo.get_project(project_id)
            if not project:
                return None
            
            # 权限检查
            if not validate_project_permission(user_id, project, ProjectPermission.EDITOR):
                raise PermissionError("无权限修改此项目")
            
            # 更新字段
            if request.name:
                project.name = request.name
            if request.description is not None:
                project.description = request.description
            if request.status:
                project.status = request.status
            if request.knowledge_base_ids is not None:
                project.knowledge_base_ids = request.knowledge_base_ids
            if request.tags is not None:
                project.tags = request.tags
            if request.settings:
                project.settings = request.settings
            
            project.updated_at = datetime.now()
            
            # 保存更新
            await self.arangodb_repo.save_project(project)
            
            logger.info(f"Updated project: {project_id} by user {user_id}")
            return project
            
        except Exception as e:
            logger.error(f"Failed to update project {project_id}: {e}")
            raise
    
    async def delete_project(self, project_id: str, user_id: str) -> bool:
        """删除项目"""
        await self.initialize()
        
        try:
            project = await self.arangodb_repo.get_project(project_id)
            if not project:
                return False
            
            # 权限检查
            if not validate_project_permission(user_id, project, ProjectPermission.OWNER):
                raise PermissionError("无权限删除此项目")
            
            # 软删除：标记为已删除状态
            project.status = ProjectStatus.DELETED
            project.updated_at = datetime.now()
            
            await self.arangodb_repo.save_project(project)
            
            # TODO: 删除关联的图谱数据
            await self._delete_project_graphs(project_id, user_id)
            
            logger.info(f"Deleted project: {project_id} by user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete project {project_id}: {e}")
            raise
    
    async def get_user_projects(self, user_id: str, page: int = 1, page_size: int = 20, 
                              status: Optional[ProjectStatus] = None) -> ProjectListResponse:
        """获取用户项目列表"""
        await self.initialize()
        
        try:
            # TODO: 实现更高效的项目列表查询
            # 暂时从所有项目中筛选
            all_projects = await self._get_all_projects()
            
            # 筛选用户有权限的项目
            user_projects = []
            for project in all_projects:
                if validate_project_permission(user_id, project, ProjectPermission.VIEWER):
                    if status is None or project.status == status:
                        user_projects.append(project)
            
            # 排序
            user_projects.sort(key=lambda x: x.updated_at, reverse=True)
            
            # 分页
            total = len(user_projects)
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            page_projects = user_projects[start_index:end_index]
            
            has_next = end_index < total
            
            return ProjectListResponse(
                projects=page_projects,
                total=total,
                page=page,
                page_size=page_size,
                has_next=has_next
            )
            
        except Exception as e:
            logger.error(f"Failed to get user projects: {e}")
            raise
    
    async def get_project_graphs(self, project_id: str, user_id: str) -> List[KnowledgeGraph]:
        """获取项目图谱列表"""
        await self.initialize()
        
        try:
            project = await self.arangodb_repo.get_project(project_id)
            if not project:
                return []
            
            # 权限检查
            if not validate_project_permission(user_id, project, ProjectPermission.VIEWER):
                raise PermissionError("无权限访问此项目")
            
            # TODO: 实现图谱查询
            # 暂时返回空列表
            return []
            
        except Exception as e:
            logger.error(f"Failed to get project graphs: {e}")
            raise
    
    async def manage_project_member(self, project_id: str, request: ProjectMemberManageRequest, user_id: str) -> bool:
        """管理项目成员"""
        await self.initialize()
        
        try:
            project = await self.arangodb_repo.get_project(project_id)
            if not project:
                return False
            
            # 权限检查
            if not validate_project_permission(user_id, project, ProjectPermission.OWNER):
                raise PermissionError("无权限管理项目成员")
            
            # 根据操作类型处理
            if request.action == "add":
                # 添加成员
                new_member = ProjectMember(
                    user_id=request.user_id,
                    permission=request.permission,
                    added_by=user_id
                )
                
                # 检查成员是否已存在
                for member in project.members:
                    if member.user_id == request.user_id:
                        return False
                
                project.members.append(new_member)
                
            elif request.action == "update":
                # 更新成员权限
                for member in project.members:
                    if member.user_id == request.user_id:
                        member.permission = request.permission
                        break
                else:
                    return False
                
            elif request.action == "remove":
                # 移除成员
                project.members = [member for member in project.members if member.user_id != request.user_id]
                
            else:
                raise ValueError(f"Unknown action: {request.action}")
            
            project.updated_at = datetime.now()
            await self.arangodb_repo.save_project(project)
            
            logger.info(f"Managed project member: {project_id} {request.action} {request.user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to manage project member: {e}")
            raise
    
    async def bulk_operation(self, request: ProjectBulkOperationRequest, user_id: str) -> Dict[str, Any]:
        """批量操作项目"""
        await self.initialize()
        
        try:
            results = {
                'success': [],
                'failed': [],
                'total': len(request.project_ids)
            }
            
            for project_id in request.project_ids:
                try:
                    project = await self.arangodb_repo.get_project(project_id)
                    if not project:
                        results['failed'].append({'project_id': project_id, 'error': 'Project not found'})
                        continue
                    
                    # 权限检查
                    if not validate_project_permission(user_id, project, ProjectPermission.OWNER):
                        results['failed'].append({'project_id': project_id, 'error': 'Permission denied'})
                        continue
                    
                    # 执行操作
                    if request.action == "archive":
                        project.status = ProjectStatus.ARCHIVED
                    elif request.action == "delete":
                        project.status = ProjectStatus.DELETED
                    elif request.action == "restore":
                        project.status = ProjectStatus.ACTIVE
                    else:
                        results['failed'].append({'project_id': project_id, 'error': 'Unknown action'})
                        continue
                    
                    project.updated_at = datetime.now()
                    await self.arangodb_repo.save_project(project)
                    
                    results['success'].append(project_id)
                    
                except Exception as e:
                    results['failed'].append({'project_id': project_id, 'error': str(e)})
                    continue
            
            logger.info(f"Bulk operation {request.action}: {len(results['success'])} success, {len(results['failed'])} failed")
            return results
            
        except Exception as e:
            logger.error(f"Failed to perform bulk operation: {e}")
            raise
    
    async def get_project_statistics(self, project_id: str, user_id: str) -> Optional[ProjectStatistics]:
        """获取项目统计信息"""
        await self.initialize()
        
        try:
            project = await self.arangodb_repo.get_project(project_id)
            if not project:
                return None
            
            # 权限检查
            if not validate_project_permission(user_id, project, ProjectPermission.VIEWER):
                raise PermissionError("无权限访问此项目")
            
            # 更新统计信息
            await self._update_project_statistics(project)
            
            return project.statistics
            
        except Exception as e:
            logger.error(f"Failed to get project statistics: {e}")
            raise
    
    async def export_project(self, project_id: str, user_id: str, export_format: str = 'json') -> Dict[str, Any]:
        """导出项目数据"""
        await self.initialize()
        
        try:
            project = await self.arangodb_repo.get_project(project_id)
            if not project:
                return {}
            
            # 权限检查
            if not validate_project_permission(user_id, project, ProjectPermission.VIEWER):
                raise PermissionError("无权限导出此项目")
            
            # 导出项目数据
            export_data = {
                'project': project.dict(),
                'graphs': [],  # TODO: 获取项目图谱
                'exported_at': datetime.now().isoformat(),
                'export_format': export_format
            }
            
            logger.info(f"Exported project {project_id} in format {export_format}")
            return export_data
            
        except Exception as e:
            logger.error(f"Failed to export project: {e}")
            raise
    
    async def import_project(self, import_data: Dict[str, Any], user_id: str) -> Optional[KnowledgeGraphProject]:
        """导入项目数据"""
        await self.initialize()
        
        try:
            # 验证导入数据
            if 'project' not in import_data:
                raise ValueError("Invalid import data: missing project")
            
            project_data = import_data['project']
            
            # 创建新项目
            new_project_id = generate_project_id(user_id, project_data['name'])
            project = KnowledgeGraphProject(
                project_id=new_project_id,
                name=project_data['name'],
                description=project_data.get('description'),
                project_type=project_data.get('project_type', 'document_set'),
                status=ProjectStatus.ACTIVE,
                owner_id=user_id,
                knowledge_base_ids=project_data.get('knowledge_base_ids', []),
                tags=project_data.get('tags', []),
                settings=project_data.get('settings', {}),
                statistics=ProjectStatistics()
            )
            
            # 保存项目
            await self.arangodb_repo.save_project(project)
            
            # TODO: 导入图谱数据
            
            logger.info(f"Imported project {new_project_id} by user {user_id}")
            return project
            
        except Exception as e:
            logger.error(f"Failed to import project: {e}")
            raise
    
    async def _get_all_projects(self) -> List[KnowledgeGraphProject]:
        """获取所有项目（临时实现）"""
        try:
            # TODO: 实现高效的项目查询
            # 暂时返回空列表
            return []
            
        except Exception as e:
            logger.error(f"Failed to get all projects: {e}")
            return []
    
    async def _delete_project_graphs(self, project_id: str, user_id: str):
        """删除项目关联的图谱"""
        try:
            # TODO: 实现图谱删除逻辑
            logger.info(f"Deleting graphs for project {project_id}")
            
        except Exception as e:
            logger.error(f"Failed to delete project graphs: {e}")
    
    async def _update_project_statistics(self, project: KnowledgeGraphProject):
        """更新项目统计信息"""
        try:
            # TODO: 实现统计信息更新
            stats = {
                'total_graphs': 0,
                'total_entities': 0,
                'total_relations': 0,
                'total_documents': len(project.document_ids),
                'last_activity': datetime.now()
            }
            
            update_project_statistics(project, stats)
            await self.arangodb_repo.save_project(project)
            
        except Exception as e:
            logger.error(f"Failed to update project statistics: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            await self.initialize()
            
            # 检查ArangoDB连接
            arangodb_health = await self.arangodb_repo.health_check()
            
            return {
                'status': 'healthy' if arangodb_health['status'] == 'healthy' else 'unhealthy',
                'arangodb': arangodb_health,
                'checked_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'checked_at': datetime.now().isoformat()
            }


# 全局项目服务实例
project_service = ProjectService()


async def get_project_service() -> ProjectService:
    """获取项目服务实例"""
    return project_service