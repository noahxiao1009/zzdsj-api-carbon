"""
知识库文件夹管理器
提供文件夹的CRUD操作、层级管理和检索优化功能
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc

from app.models.folder_models import (
    KnowledgeFolder, 
    FolderDocumentMapping, 
    FolderSearchIndex,
    FolderAccessLog
)
from app.models.knowledge_models import Document, KnowledgeBase

logger = logging.getLogger(__name__)


class FolderManager:
    """知识库文件夹管理器"""
    
    def __init__(self, db: Session):
        self.db = db
        logger.info("Folder Manager initialized")
    
    # ===============================
    # 文件夹 CRUD 操作
    # ===============================
    
    def create_folder(
        self,
        kb_id: str,
        name: str,
        description: Optional[str] = None,
        parent_id: Optional[str] = None,
        folder_type: str = "user_created",
        color: str = "#1890ff",
        icon: str = "folder"
    ) -> Dict[str, Any]:
        """创建文件夹"""
        try:
            # 验证知识库存在
            kb = self.db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
            if not kb:
                return {"success": False, "error": "知识库不存在"}
            
            # 验证父文件夹（如果指定）
            level = 0
            full_path = f"/{name}"
            
            if parent_id:
                parent_folder = self.db.query(KnowledgeFolder).filter(
                    and_(
                        KnowledgeFolder.id == parent_id,
                        KnowledgeFolder.kb_id == kb_id
                    )
                ).first()
                
                if not parent_folder:
                    return {"success": False, "error": "父文件夹不存在"}
                
                if parent_folder.level >= 1:  # 最多支持二级目录
                    return {"success": False, "error": "最多支持二级目录"}
                
                level = parent_folder.level + 1
                full_path = f"{parent_folder.full_path}/{name}"
            
            # 检查同级名称重复
            existing = self.db.query(KnowledgeFolder).filter(
                and_(
                    KnowledgeFolder.kb_id == kb_id,
                    KnowledgeFolder.parent_id == parent_id,
                    KnowledgeFolder.name == name,
                    KnowledgeFolder.status == "active"
                )
            ).first()
            
            if existing:
                return {"success": False, "error": "同级目录下已存在相同名称的文件夹"}
            
            # 创建文件夹
            folder = KnowledgeFolder(
                kb_id=kb_id,
                parent_id=parent_id,
                name=name,
                description=description,
                folder_type=folder_type,
                level=level,
                full_path=full_path,
                color=color,
                icon=icon,
                sort_order=self._get_next_sort_order(kb_id, parent_id)
            )
            
            self.db.add(folder)
            self.db.commit()
            self.db.refresh(folder)
            
            # 创建搜索索引
            self._create_search_index(folder.id)
            
            logger.info(f"Created folder: {name} in knowledge base: {kb_id}")
            
            return {
                "success": True,
                "folder": self._format_folder_response(folder)
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create folder: {e}")
            return {"success": False, "error": str(e)}
    
    def get_folder(self, folder_id: str, kb_id: str) -> Optional[Dict[str, Any]]:
        """获取文件夹详情"""
        try:
            folder = self.db.query(KnowledgeFolder).filter(
                and_(
                    KnowledgeFolder.id == folder_id,
                    KnowledgeFolder.kb_id == kb_id,
                    KnowledgeFolder.status == "active"
                )
            ).first()
            
            if not folder:
                return None
            
            # 记录访问日志
            self._log_folder_access(folder_id, kb_id, "view")
            
            return self._format_folder_response(folder, include_documents=True)
            
        except Exception as e:
            logger.error(f"Failed to get folder {folder_id}: {e}")
            return None
    
    def list_folders(
        self,
        kb_id: str,
        parent_id: Optional[str] = None,
        include_documents: bool = False
    ) -> List[Dict[str, Any]]:
        """获取文件夹列表"""
        try:
            query = self.db.query(KnowledgeFolder).filter(
                and_(
                    KnowledgeFolder.kb_id == kb_id,
                    KnowledgeFolder.parent_id == parent_id,
                    KnowledgeFolder.status == "active"
                )
            ).order_by(KnowledgeFolder.sort_order, KnowledgeFolder.name)
            
            folders = query.all()
            
            return [
                self._format_folder_response(folder, include_documents=include_documents)
                for folder in folders
            ]
            
        except Exception as e:
            logger.error(f"Failed to list folders for kb {kb_id}: {e}")
            return []
    
    def get_folder_tree(self, kb_id: str) -> Dict[str, Any]:
        """获取完整的文件夹树结构"""
        try:
            # 获取所有文件夹
            all_folders = self.db.query(KnowledgeFolder).filter(
                and_(
                    KnowledgeFolder.kb_id == kb_id,
                    KnowledgeFolder.status == "active"
                )
            ).order_by(KnowledgeFolder.level, KnowledgeFolder.sort_order).all()
            
            # 构建树结构
            folder_map = {}
            root_folders = []
            
            for folder in all_folders:
                folder_data = self._format_folder_response(folder)
                folder_data["children"] = []
                folder_map[folder.id] = folder_data
                
                if folder.parent_id is None:
                    root_folders.append(folder_data)
                else:
                    if folder.parent_id in folder_map:
                        folder_map[folder.parent_id]["children"].append(folder_data)
            
            return {
                "success": True,
                "tree": root_folders,
                "total_folders": len(all_folders)
            }
            
        except Exception as e:
            logger.error(f"Failed to get folder tree for kb {kb_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def update_folder(
        self,
        folder_id: str,
        kb_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        color: Optional[str] = None,
        icon: Optional[str] = None
    ) -> Dict[str, Any]:
        """更新文件夹"""
        try:
            folder = self.db.query(KnowledgeFolder).filter(
                and_(
                    KnowledgeFolder.id == folder_id,
                    KnowledgeFolder.kb_id == kb_id,
                    KnowledgeFolder.status == "active"
                )
            ).first()
            
            if not folder:
                return {"success": False, "error": "文件夹不存在"}
            
            # 更新字段
            if name and name != folder.name:
                # 检查同级名称重复
                existing = self.db.query(KnowledgeFolder).filter(
                    and_(
                        KnowledgeFolder.kb_id == kb_id,
                        KnowledgeFolder.parent_id == folder.parent_id,
                        KnowledgeFolder.name == name,
                        KnowledgeFolder.id != folder_id,
                        KnowledgeFolder.status == "active"
                    )
                ).first()
                
                if existing:
                    return {"success": False, "error": "同级目录下已存在相同名称的文件夹"}
                
                folder.name = name
                # 更新完整路径
                folder.full_path = folder.get_full_path()
            
            if description is not None:
                folder.description = description
            if color:
                folder.color = color
            if icon:
                folder.icon = icon
            
            self.db.commit()
            
            # 更新搜索索引
            self._update_search_index(folder_id)
            
            logger.info(f"Updated folder: {folder_id}")
            
            return {
                "success": True,
                "folder": self._format_folder_response(folder)
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update folder {folder_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def delete_folder(self, folder_id: str, kb_id: str, force: bool = False) -> Dict[str, Any]:
        """删除文件夹"""
        try:
            folder = self.db.query(KnowledgeFolder).filter(
                and_(
                    KnowledgeFolder.id == folder_id,
                    KnowledgeFolder.kb_id == kb_id,
                    KnowledgeFolder.status == "active"
                )
            ).first()
            
            if not folder:
                return {"success": False, "error": "文件夹不存在"}
            
            # 检查是否有子文件夹
            has_children = self.db.query(KnowledgeFolder).filter(
                and_(
                    KnowledgeFolder.parent_id == folder_id,
                    KnowledgeFolder.status == "active"
                )
            ).first()
            
            if has_children and not force:
                return {"success": False, "error": "文件夹包含子文件夹，请先删除子文件夹或使用强制删除"}
            
            # 检查是否有文档
            doc_count = self.db.query(Document).filter(Document.folder_id == folder_id).count()
            
            if doc_count > 0 and not force:
                return {"success": False, "error": f"文件夹包含 {doc_count} 个文档，请先移动文档或使用强制删除"}
            
            # 执行删除
            if force:
                # 递归删除所有子文件夹
                self._recursive_delete_folder(folder_id)
                # 将文档移动到根目录
                self.db.query(Document).filter(Document.folder_id == folder_id).update(
                    {"folder_id": None}
                )
            
            # 标记为已删除
            folder.status = "deleted"
            self.db.commit()
            
            logger.info(f"Deleted folder: {folder_id} (force={force})")
            
            return {"success": True, "message": "文件夹删除成功"}
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to delete folder {folder_id}: {e}")
            return {"success": False, "error": str(e)}
    
    # ===============================
    # 文档-文件夹关联管理
    # ===============================
    
    def move_document_to_folder(
        self,
        doc_id: str,
        folder_id: Optional[str],
        kb_id: str
    ) -> Dict[str, Any]:
        """将文档移动到文件夹"""
        try:
            # 验证文档存在
            document = self.db.query(Document).filter(
                and_(
                    Document.id == doc_id,
                    Document.kb_id == kb_id
                )
            ).first()
            
            if not document:
                return {"success": False, "error": "文档不存在"}
            
            # 验证目标文件夹（如果不是移动到根目录）
            if folder_id:
                folder = self.db.query(KnowledgeFolder).filter(
                    and_(
                        KnowledgeFolder.id == folder_id,
                        KnowledgeFolder.kb_id == kb_id,
                        KnowledgeFolder.status == "active"
                    )
                ).first()
                
                if not folder:
                    return {"success": False, "error": "目标文件夹不存在"}
            
            # 更新文档的文件夹关联
            old_folder_id = document.folder_id
            document.folder_id = folder_id
            
            self.db.commit()
            
            # 更新文件夹统计
            if old_folder_id:
                self._update_folder_stats(old_folder_id)
            if folder_id:
                self._update_folder_stats(folder_id)
            
            logger.info(f"Moved document {doc_id} to folder {folder_id}")
            
            return {"success": True, "message": "文档移动成功"}
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to move document {doc_id} to folder {folder_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def get_folder_documents(
        self,
        folder_id: str,
        kb_id: str,
        page: int = 1,
        page_size: int = 20,
        include_subfolders: bool = False
    ) -> Dict[str, Any]:
        """获取文件夹中的文档"""
        try:
            # 构建查询条件
            if include_subfolders:
                # 获取所有子文件夹ID
                folder_ids = self._get_folder_and_children_ids(folder_id, kb_id)
                doc_query = self.db.query(Document).filter(
                    and_(
                        Document.kb_id == kb_id,
                        Document.folder_id.in_(folder_ids)
                    )
                )
            else:
                doc_query = self.db.query(Document).filter(
                    and_(
                        Document.kb_id == kb_id,
                        Document.folder_id == folder_id
                    )
                )
            
            # 分页
            total = doc_query.count()
            offset = (page - 1) * page_size
            documents = doc_query.offset(offset).limit(page_size).all()
            
            # 格式化响应
            doc_list = []
            for doc in documents:
                doc_data = {
                    "id": doc.id,
                    "filename": doc.filename,
                    "file_type": doc.file_type,
                    "file_size": doc.file_size,
                    "status": doc.status,
                    "created_at": doc.created_at.isoformat() if doc.created_at else None,
                    "folder_id": doc.folder_id
                }
                doc_list.append(doc_data)
            
            return {
                "success": True,
                "documents": doc_list,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": (total + page_size - 1) // page_size
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get documents for folder {folder_id}: {e}")
            return {"success": False, "error": str(e)}
    
    # ===============================
    # 文件夹检索功能
    # ===============================
    
    def search_in_folder(
        self,
        folder_id: str,
        kb_id: str,
        query: str,
        search_type: str = "semantic",
        include_subfolders: bool = True,
        limit: int = 10
    ) -> Dict[str, Any]:
        """在文件夹内检索"""
        try:
            # 记录搜索日志
            self._log_folder_access(folder_id, kb_id, "search", search_query=query)
            
            # 获取搜索范围内的文档ID
            if include_subfolders:
                folder_ids = self._get_folder_and_children_ids(folder_id, kb_id)
            else:
                folder_ids = [folder_id]
            
            # 获取文档列表
            documents = self.db.query(Document).filter(
                and_(
                    Document.kb_id == kb_id,
                    Document.folder_id.in_(folder_ids),
                    Document.status == "completed"
                )
            ).all()
            
            if not documents:
                return {
                    "success": True,
                    "results": [],
                    "total": 0,
                    "search_scope": f"文件夹范围内无可搜索文档"
                }
            
            # 这里可以集成具体的检索逻辑
            # 暂时返回简化的搜索结果
            results = []
            for doc in documents[:limit]:
                if query.lower() in doc.filename.lower() or (doc.content and query.lower() in doc.content.lower()):
                    results.append({
                        "document_id": doc.id,
                        "filename": doc.filename,
                        "relevance_score": 0.8,  # 简化评分
                        "snippet": f"...{query}相关内容...",
                        "folder_path": self._get_document_folder_path(doc.folder_id)
                    })
            
            return {
                "success": True,
                "results": results,
                "total": len(results),
                "search_scope": f"搜索范围：{len(folder_ids)} 个文件夹，{len(documents)} 个文档"
            }
            
        except Exception as e:
            logger.error(f"Failed to search in folder {folder_id}: {e}")
            return {"success": False, "error": str(e)}
    
    # ===============================
    # 内部辅助方法
    # ===============================
    
    def _format_folder_response(self, folder: KnowledgeFolder, include_documents: bool = False) -> Dict[str, Any]:
        """格式化文件夹响应"""
        response = {
            "id": folder.id,
            "name": folder.name,
            "description": folder.description,
            "folder_type": folder.folder_type,
            "level": folder.level,
            "full_path": folder.full_path,
            "parent_id": folder.parent_id,
            "color": folder.color,
            "icon": folder.icon,
            "document_count": folder.document_count,
            "total_document_count": folder.total_document_count,
            "total_size": folder.total_size,
            "status": folder.status,
            "created_at": folder.created_at.isoformat() if folder.created_at else None,
            "updated_at": folder.updated_at.isoformat() if folder.updated_at else None,
            "breadcrumb": folder.get_breadcrumb()
        }
        
        if include_documents:
            # 获取直接包含的文档
            documents = self.db.query(Document).filter(Document.folder_id == folder.id).all()
            response["documents"] = [
                {
                    "id": doc.id,
                    "filename": doc.filename,
                    "file_type": doc.file_type,
                    "file_size": doc.file_size,
                    "status": doc.status
                }
                for doc in documents
            ]
        
        return response
    
    def _get_next_sort_order(self, kb_id: str, parent_id: Optional[str]) -> int:
        """获取下一个排序序号"""
        max_order = self.db.query(func.max(KnowledgeFolder.sort_order)).filter(
            and_(
                KnowledgeFolder.kb_id == kb_id,
                KnowledgeFolder.parent_id == parent_id,
                KnowledgeFolder.status == "active"
            )
        ).scalar()
        
        return (max_order or 0) + 1
    
    def _create_search_index(self, folder_id: str):
        """创建文件夹搜索索引"""
        try:
            folder = self.db.query(KnowledgeFolder).filter(KnowledgeFolder.id == folder_id).first()
            if not folder:
                return
            
            # 构建搜索内容
            searchable_content = f"{folder.name} {folder.description or ''}"
            
            # 获取文件夹内文档的关键词
            documents = self.db.query(Document).filter(Document.folder_id == folder_id).all()
            keywords = [folder.name]
            
            # 创建搜索索引记录
            search_index = FolderSearchIndex(
                folder_id=folder_id,
                kb_id=folder.kb_id,
                searchable_content=searchable_content,
                keywords=keywords,
                total_documents=len(documents)
            )
            
            self.db.add(search_index)
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to create search index for folder {folder_id}: {e}")
    
    def _update_search_index(self, folder_id: str):
        """更新文件夹搜索索引"""
        try:
            search_index = self.db.query(FolderSearchIndex).filter(
                FolderSearchIndex.folder_id == folder_id
            ).first()
            
            if search_index:
                search_index.needs_reindex = True
                self.db.commit()
            else:
                self._create_search_index(folder_id)
                
        except Exception as e:
            logger.error(f"Failed to update search index for folder {folder_id}: {e}")
    
    def _update_folder_stats(self, folder_id: str):
        """更新文件夹统计信息"""
        try:
            folder = self.db.query(KnowledgeFolder).filter(KnowledgeFolder.id == folder_id).first()
            if not folder:
                return
            
            # 统计直接包含的文档
            doc_stats = self.db.query(
                func.count(Document.id).label('count'),
                func.sum(Document.file_size).label('total_size')
            ).filter(Document.folder_id == folder_id, Document.status == "completed").first()
            
            folder.document_count = doc_stats.count or 0
            folder.total_size = doc_stats.total_size or 0
            
            # 递归统计包括子文件夹的总数
            all_child_ids = folder.get_all_children_ids()
            all_folder_ids = [folder_id] + all_child_ids
            
            total_stats = self.db.query(
                func.count(Document.id).label('total_count')
            ).filter(Document.folder_id.in_(all_folder_ids), Document.status == "completed").first()
            
            folder.total_document_count = total_stats.total_count or 0
            
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to update stats for folder {folder_id}: {e}")
    
    def _recursive_delete_folder(self, folder_id: str):
        """递归删除文件夹及其子文件夹"""
        # 获取所有子文件夹
        children = self.db.query(KnowledgeFolder).filter(
            KnowledgeFolder.parent_id == folder_id
        ).all()
        
        # 递归删除子文件夹
        for child in children:
            self._recursive_delete_folder(child.id)
        
        # 删除当前文件夹
        self.db.query(KnowledgeFolder).filter(KnowledgeFolder.id == folder_id).update(
            {"status": "deleted"}
        )
    
    def _get_folder_and_children_ids(self, folder_id: str, kb_id: str) -> List[str]:
        """获取文件夹及其所有子文件夹的ID列表"""
        folder = self.db.query(KnowledgeFolder).filter(
            and_(
                KnowledgeFolder.id == folder_id,
                KnowledgeFolder.kb_id == kb_id
            )
        ).first()
        
        if not folder:
            return []
        
        return [folder_id] + folder.get_all_children_ids()
    
    def _get_document_folder_path(self, folder_id: Optional[str]) -> str:
        """获取文档所在文件夹的完整路径"""
        if not folder_id:
            return "/"
        
        folder = self.db.query(KnowledgeFolder).filter(KnowledgeFolder.id == folder_id).first()
        return folder.full_path if folder else "/"
    
    def _log_folder_access(
        self,
        folder_id: str,
        kb_id: str,
        access_type: str,
        search_query: Optional[str] = None
    ):
        """记录文件夹访问日志"""
        try:
            access_log = FolderAccessLog(
                folder_id=folder_id,
                kb_id=kb_id,
                access_type=access_type,
                search_query=search_query
            )
            
            self.db.add(access_log)
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to log folder access: {e}")


def get_folder_manager(db: Session) -> FolderManager:
    """获取文件夹管理器实例"""
    return FolderManager(db)