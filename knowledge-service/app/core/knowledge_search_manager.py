"""
知识库检索模式管理器
支持智能体绑定知识库时的检索模式配置和管理
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc

from app.models.knowledge_models import KnowledgeBase, Document
from app.models.simple_folder_models import KnowledgeFolder, FolderSearchConfig

logger = logging.getLogger(__name__)


class KBSearchModeConfig:
    """知识库检索模式配置类"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_table_if_not_exists(self):
        """创建检索模式配置表（如果不存在）"""
        # 这里可以添加动态表创建逻辑，或者依赖迁移脚本
        pass


class KnowledgeSearchManager:
    """知识库检索模式管理器"""
    
    def __init__(self, db: Session):
        self.db = db
        logger.info("Knowledge Search Manager initialized")
    
    # ===============================
    # 检索模式管理
    # ===============================
    
    def get_search_modes(self, kb_id: str) -> List[Dict[str, Any]]:
        """获取知识库的所有检索模式"""
        try:
            # 获取知识库基本信息
            kb = self.db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
            if not kb:
                return []
            
            # 构建检索模式列表
            search_modes = []
            
            # 1. 全库检索模式
            full_kb_mode = {
                "id": f"full_kb_{kb_id}",
                "kb_id": kb_id,
                "search_mode": "full_kb",
                "mode_name": "全库检索",
                "description": "在整个知识库中进行检索，包含所有文档和文件夹",
                "is_default": True,
                "is_active": True,
                "priority": 100,
                "document_count": self._get_kb_document_count(kb_id),
                "folder_count": 0,
                "search_config": {
                    "similarity_threshold": 70,
                    "max_results": 20,
                    "enable_semantic_search": True,
                    "enable_keyword_search": True,
                    "sort_by": "relevance",
                    "sort_order": "desc"
                },
                "usage_count": 0,
                "created_by": "system"
            }
            search_modes.append(full_kb_mode)
            
            # 2. 获取文件夹信息
            folders = self.db.query(KnowledgeFolder).filter(
                and_(
                    KnowledgeFolder.kb_id == kb_id,
                    KnowledgeFolder.status == "active",
                    KnowledgeFolder.enable_search == True
                )
            ).order_by(KnowledgeFolder.level, KnowledgeFolder.name).all()
            
            # 3. 自定义文件夹检索模式
            if folders:
                custom_folder_mode = {
                    "id": f"custom_folders_{kb_id}",
                    "kb_id": kb_id,
                    "search_mode": "custom_folders",
                    "mode_name": "自定义文件夹检索",
                    "description": "选择特定的文件夹进行检索，可以包含或排除指定文件夹",
                    "is_default": False,
                    "is_active": True,
                    "priority": 80,
                    "available_folders": [self._format_folder_info(folder) for folder in folders],
                    "document_count": sum(folder.document_count or 0 for folder in folders),
                    "folder_count": len(folders),
                    "search_config": {
                        "similarity_threshold": 70,
                        "max_results": 15,
                        "enable_semantic_search": True,
                        "enable_keyword_search": True,
                        "sort_by": "relevance",
                        "sort_order": "desc",
                        "folder_selection_mode": "include"  # include 或 exclude
                    },
                    "usage_count": 0,
                    "created_by": "system"
                }
                search_modes.append(custom_folder_mode)
            
            # 4. 获取用户自定义的检索模式
            custom_modes = self._get_custom_search_modes(kb_id)
            search_modes.extend(custom_modes)
            
            # 按优先级排序
            search_modes.sort(key=lambda x: x.get("priority", 0), reverse=True)
            
            return search_modes
            
        except Exception as e:
            logger.error(f"Failed to get search modes for kb {kb_id}: {e}")
            return []
    
    def create_custom_search_mode(
        self,
        kb_id: str,
        mode_name: str,
        description: str,
        search_mode: str,
        included_folders: Optional[List[str]] = None,
        excluded_folders: Optional[List[str]] = None,
        search_config: Optional[Dict[str, Any]] = None,
        created_by: str = "user"
    ) -> Dict[str, Any]:
        """创建自定义检索模式"""
        try:
            # 验证知识库存在
            kb = self.db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
            if not kb:
                return {"success": False, "error": "知识库不存在"}
            
            # 检查模式名称是否已存在
            existing = self._check_mode_name_exists(kb_id, mode_name)
            if existing:
                return {"success": False, "error": f"检索模式名称 '{mode_name}' 已存在"}
            
            # 验证文件夹ID
            if included_folders:
                valid_folders = self._validate_folder_ids(kb_id, included_folders)
                if len(valid_folders) != len(included_folders):
                    return {"success": False, "error": "包含的文件夹列表中有无效的文件夹ID"}
            
            if excluded_folders:
                valid_folders = self._validate_folder_ids(kb_id, excluded_folders)
                if len(valid_folders) != len(excluded_folders):
                    return {"success": False, "error": "排除的文件夹列表中有无效的文件夹ID"}
            
            # 构建配置数据
            config_data = {
                "similarity_threshold": 70,
                "max_results": 15,
                "enable_semantic_search": True,
                "enable_keyword_search": True,
                "sort_by": "relevance",
                "sort_order": "desc"
            }
            if search_config:
                config_data.update(search_config)
            
            # 创建检索模式记录（这里模拟数据库操作）
            mode_id = f"custom_{kb_id}_{len(self._get_custom_search_modes(kb_id)) + 1}"
            
            custom_mode = {
                "id": mode_id,
                "kb_id": kb_id,
                "search_mode": search_mode,
                "mode_name": mode_name,
                "description": description,
                "included_folders": included_folders or [],
                "excluded_folders": excluded_folders or [],
                "search_config": config_data,
                "priority": 60,
                "is_default": False,
                "is_active": True,
                "created_by": created_by,
                "usage_count": 0,
                "created_at": "2025-07-29T00:00:00Z"
            }
            
            # 这里应该保存到数据库
            # 由于模型还未完全集成，先返回模拟数据
            
            logger.info(f"Created custom search mode: {mode_name} for kb: {kb_id}")
            
            return {
                "success": True,
                "message": "自定义检索模式创建成功",
                "mode": custom_mode
            }
            
        except Exception as e:
            logger.error(f"Failed to create custom search mode: {e}")
            return {"success": False, "error": str(e)}
    
    def update_search_mode(
        self,
        mode_id: str,
        kb_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """更新检索模式配置"""
        try:
            # 系统预设模式不允许修改核心配置
            if mode_id.startswith("full_kb_") or mode_id.startswith("custom_folders_"):
                allowed_fields = ["search_config"]
                updates = {k: v for k, v in updates.items() if k in allowed_fields}
            
            # 这里应该更新数据库记录
            # 暂时返回成功状态
            
            logger.info(f"Updated search mode: {mode_id}")
            
            return {
                "success": True,
                "message": "检索模式更新成功"
            }
            
        except Exception as e:
            logger.error(f"Failed to update search mode {mode_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def delete_search_mode(self, mode_id: str, kb_id: str) -> Dict[str, Any]:
        """删除自定义检索模式"""
        try:
            # 系统预设模式不允许删除
            if mode_id.startswith("full_kb_") or mode_id.startswith("custom_folders_"):
                return {"success": False, "error": "系统预设的检索模式不能删除"}
            
            # 这里应该从数据库中删除记录
            # 暂时返回成功状态
            
            logger.info(f"Deleted search mode: {mode_id}")
            
            return {
                "success": True,
                "message": "检索模式删除成功"
            }
            
        except Exception as e:
            logger.error(f"Failed to delete search mode {mode_id}: {e}")
            return {"success": False, "error": str(e)}
    
    # ===============================
    # 检索执行
    # ===============================
    
    def search_with_mode(
        self,
        kb_id: str,
        mode_id: str,
        query: str,
        search_type: str = "hybrid",
        limit: int = 10,
        custom_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """使用指定检索模式执行搜索"""
        try:
            # 获取检索模式配置
            mode_config = self._get_search_mode_config(kb_id, mode_id)
            if not mode_config:
                return {"success": False, "error": "检索模式不存在"}
            
            # 合并自定义配置
            search_config = mode_config.get("search_config", {})
            if custom_config:
                search_config.update(custom_config)
            
            # 根据模式类型执行不同的检索策略
            if mode_config["search_mode"] == "full_kb":
                return self._search_full_kb(kb_id, query, search_type, limit, search_config)
            elif mode_config["search_mode"] == "custom_folders":
                return self._search_custom_folders(kb_id, query, search_type, limit, search_config, mode_config)
            else:
                return self._search_with_folder_selection(kb_id, query, search_type, limit, search_config, mode_config)
            
        except Exception as e:
            logger.error(f"Failed to search with mode {mode_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def _search_full_kb(
        self,
        kb_id: str,
        query: str,
        search_type: str,
        limit: int,
        search_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """全库检索"""
        try:
            # 获取所有可检索的文档
            doc_query = self.db.query(Document).filter(
                and_(
                    Document.kb_id == kb_id,
                    Document.status == "completed"
                )
            )
            
            # 执行搜索
            results = self._execute_search(doc_query, query, search_type, limit, search_config)
            
            return {
                "success": True,
                "results": results,
                "total": len(results),
                "search_scope": "整个知识库",
                "search_mode": "full_kb",
                "query": query,
                "search_type": search_type
            }
            
        except Exception as e:
            logger.error(f"Full KB search failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _search_custom_folders(
        self,
        kb_id: str,
        query: str,
        search_type: str,
        limit: int,
        search_config: Dict[str, Any],
        mode_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """自定义文件夹检索（前端动态配置）"""
        try:
            # 这个模式需要前端传递具体的文件夹选择
            # 暂时返回可选文件夹列表，让前端进行选择
            available_folders = mode_config.get("available_folders", [])
            
            return {
                "success": True,
                "mode": "folder_selection_required",
                "available_folders": available_folders,
                "message": "请选择要检索的文件夹",
                "search_config": search_config
            }
            
        except Exception as e:
            logger.error(f"Custom folders search failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _search_with_folder_selection(
        self,
        kb_id: str,
        query: str,
        search_type: str,
        limit: int,
        search_config: Dict[str, Any],
        mode_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """基于文件夹选择的检索"""
        try:
            included_folders = mode_config.get("included_folders", [])
            excluded_folders = mode_config.get("excluded_folders", [])
            
            # 构建文档查询
            doc_query = self.db.query(Document).filter(
                and_(
                    Document.kb_id == kb_id,
                    Document.status == "completed"
                )
            )
            
            # 应用文件夹过滤
            if included_folders:
                doc_query = doc_query.filter(Document.folder_id.in_(included_folders))
            elif excluded_folders:
                doc_query = doc_query.filter(
                    or_(
                        Document.folder_id.is_(None),
                        ~Document.folder_id.in_(excluded_folders)
                    )
                )
            
            # 执行搜索
            results = self._execute_search(doc_query, query, search_type, limit, search_config)
            
            # 构建搜索范围描述
            scope_desc = self._build_scope_description(kb_id, included_folders, excluded_folders)
            
            return {
                "success": True,
                "results": results,
                "total": len(results),
                "search_scope": scope_desc,
                "search_mode": mode_config["search_mode"],
                "included_folders": included_folders,
                "excluded_folders": excluded_folders,
                "query": query,
                "search_type": search_type
            }
            
        except Exception as e:
            logger.error(f"Folder selection search failed: {e}")
            return {"success": False, "error": str(e)}
    
    # ===============================
    # 智能体绑定接口
    # ===============================
    
    def get_kb_search_config_for_agent(self, kb_id: str) -> Dict[str, Any]:
        """获取知识库的检索配置，供智能体绑定时使用"""
        try:
            # 获取知识库基本信息
            kb = self.db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
            if not kb:
                return {"success": False, "error": "知识库不存在"}
            
            # 获取所有可用的检索模式
            search_modes = self.get_search_modes(kb_id)
            
            # 获取默认检索模式
            default_mode = next(
                (mode for mode in search_modes if mode.get("is_default")),
                search_modes[0] if search_modes else None
            )
            
            # 获取文件夹统计信息
            folder_stats = self._get_folder_statistics(kb_id)
            
            return {
                "success": True,
                "kb_info": {
                    "id": kb.id,
                    "name": kb.name,
                    "description": kb.description,
                    "document_count": kb.document_count or 0,
                    "folder_search_enabled": getattr(kb, 'folder_search_enabled', True)
                },
                "search_modes": search_modes,
                "default_mode": default_mode,
                "folder_statistics": folder_stats,
                "binding_config": {
                    "recommended_mode": default_mode["id"] if default_mode else None,
                    "allow_mode_switching": True,
                    "support_custom_config": True
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get KB search config for agent: {e}")
            return {"success": False, "error": str(e)}
    
    def validate_agent_search_config(
        self,
        kb_id: str,
        search_mode_id: str,
        custom_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """验证智能体的检索配置"""
        try:
            # 验证检索模式是否存在
            mode_config = self._get_search_mode_config(kb_id, search_mode_id)
            if not mode_config:
                return {"success": False, "error": "指定的检索模式不存在"}
            
            # 验证自定义配置
            if custom_config:
                validation_errors = self._validate_search_config(custom_config)
                if validation_errors:
                    return {"success": False, "error": "自定义配置验证失败", "errors": validation_errors}
            
            # 生成最终配置
            final_config = mode_config.get("search_config", {}).copy()
            if custom_config:
                final_config.update(custom_config)
            
            return {
                "success": True,
                "validated_config": {
                    "mode_id": search_mode_id,
                    "mode_name": mode_config["mode_name"],
                    "search_config": final_config,
                    "description": mode_config["description"]
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to validate agent search config: {e}")
            return {"success": False, "error": str(e)}
    
    # ===============================
    # 辅助方法
    # ===============================
    
    def _get_custom_search_modes(self, kb_id: str) -> List[Dict[str, Any]]:
        """获取用户自定义的检索模式"""
        # 这里应该从数据库查询，暂时返回空列表
        return []
    
    def _get_search_mode_config(self, kb_id: str, mode_id: str) -> Optional[Dict[str, Any]]:
        """获取检索模式配置"""
        search_modes = self.get_search_modes(kb_id)
        return next((mode for mode in search_modes if mode["id"] == mode_id), None)
    
    def _check_mode_name_exists(self, kb_id: str, mode_name: str) -> bool:
        """检查模式名称是否已存在"""
        search_modes = self.get_search_modes(kb_id)
        return any(mode["mode_name"] == mode_name for mode in search_modes)
    
    def _validate_folder_ids(self, kb_id: str, folder_ids: List[str]) -> List[str]:
        """验证文件夹ID列表"""
        existing_folders = self.db.query(KnowledgeFolder.id).filter(
            and_(
                KnowledgeFolder.kb_id == kb_id,
                KnowledgeFolder.id.in_(folder_ids),
                KnowledgeFolder.status == "active"
            )
        ).all()
        
        return [folder.id for folder in existing_folders]
    
    def _format_folder_info(self, folder: KnowledgeFolder) -> Dict[str, Any]:
        """格式化文件夹信息"""
        return {
            "id": folder.id,
            "name": folder.name,
            "full_path": folder.full_path,
            "level": folder.level,
            "document_count": folder.document_count or 0,
            "enable_search": folder.enable_search,
            "search_scope": folder.search_scope,
            "search_weight": folder.search_weight
        }
    
    def _get_kb_document_count(self, kb_id: str) -> int:
        """获取知识库文档总数"""
        return self.db.query(func.count(Document.id)).filter(
            and_(
                Document.kb_id == kb_id,
                Document.status == "completed"
            )
        ).scalar() or 0
    
    def _get_folder_statistics(self, kb_id: str) -> Dict[str, Any]:
        """获取文件夹统计信息"""
        try:
            folder_stats = self.db.query(
                func.count(KnowledgeFolder.id).label('total_folders'),
                func.count(KnowledgeFolder.id).filter(KnowledgeFolder.level == 0).label('root_folders'),
                func.sum(KnowledgeFolder.document_count).label('organized_docs')
            ).filter(
                and_(
                    KnowledgeFolder.kb_id == kb_id,
                    KnowledgeFolder.status == "active"
                )
            ).first()
            
            total_docs = self._get_kb_document_count(kb_id)
            organized_docs = folder_stats.organized_docs or 0
            
            return {
                "total_folders": folder_stats.total_folders or 0,
                "root_folders": folder_stats.root_folders or 0,
                "total_documents": total_docs,
                "organized_documents": organized_docs,
                "unorganized_documents": total_docs - organized_docs,
                "organization_rate": round(organized_docs / max(total_docs, 1) * 100, 2)
            }
            
        except Exception as e:
            logger.error(f"Failed to get folder statistics: {e}")
            return {}
    
    def _execute_search(
        self,
        doc_query,
        query: str,
        search_type: str,
        limit: int,
        search_config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """执行具体的搜索逻辑"""
        try:
            # 简化的搜索实现
            documents = doc_query.limit(limit * 2).all()
            
            results = []
            for doc in documents:
                # 简单的相关性计算
                relevance = self._calculate_relevance(doc, query, search_type)
                
                # 应用相似度阈值
                threshold = search_config.get("similarity_threshold", 70) / 100
                if relevance >= threshold:
                    results.append({
                        "document_id": doc.id,
                        "filename": doc.filename,
                        "file_type": doc.file_type,
                        "file_size": doc.file_size,
                        "relevance_score": relevance,
                        "snippet": self._generate_snippet(doc.content, query) if doc.content else "",
                        "folder_path": self._get_folder_path(doc.folder_id),
                        "created_at": doc.created_at.isoformat() if doc.created_at else None,
                        "search_method": search_type
                    })
            
            # 排序和限制结果数量
            sort_by = search_config.get("sort_by", "relevance")
            sort_order = search_config.get("sort_order", "desc")
            
            if sort_by == "relevance":
                results.sort(key=lambda x: x["relevance_score"], reverse=(sort_order == "desc"))
            elif sort_by == "date":
                results.sort(key=lambda x: x["created_at"] or "", reverse=(sort_order == "desc"))
            elif sort_by == "filename":
                results.sort(key=lambda x: x["filename"], reverse=(sort_order == "desc"))
            
            max_results = search_config.get("max_results", limit)
            return results[:max_results]
            
        except Exception as e:
            logger.error(f"Search execution failed: {e}")
            return []
    
    def _calculate_relevance(self, document: Document, query: str, search_type: str) -> float:
        """计算文档相关性"""
        # 简化的相关性计算
        if not document.content:
            return 0.3
        
        query_lower = query.lower()
        filename_match = query_lower in document.filename.lower()
        content_match = query_lower in document.content.lower()
        
        relevance = 0.2  # 基础分数
        if filename_match:
            relevance += 0.4
        if content_match:
            relevance += 0.4
        
        return min(1.0, relevance)
    
    def _generate_snippet(self, content: str, query: str, max_length: int = 200) -> str:
        """生成搜索结果摘要"""
        if not content or not query:
            return ""
        
        query_lower = query.lower()
        content_lower = content.lower()
        
        pos = content_lower.find(query_lower)
        if pos == -1:
            return content[:max_length] + "..." if len(content) > max_length else content
        
        start = max(0, pos - max_length // 2)
        end = min(len(content), start + max_length)
        
        snippet = content[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."
        
        return snippet
    
    def _get_folder_path(self, folder_id: Optional[str]) -> str:
        """获取文件夹路径"""
        if not folder_id:
            return "/"
        
        folder = self.db.query(KnowledgeFolder).filter(KnowledgeFolder.id == folder_id).first()
        return folder.full_path if folder else "/"
    
    def _build_scope_description(
        self,
        kb_id: str,
        included_folders: List[str],
        excluded_folders: List[str]
    ) -> str:
        """构建搜索范围描述"""
        if included_folders:
            folder_names = self._get_folder_names(included_folders)
            return f"包含文件夹: {', '.join(folder_names)}"
        elif excluded_folders:
            folder_names = self._get_folder_names(excluded_folders)
            return f"排除文件夹: {', '.join(folder_names)}"
        else:
            return "整个知识库"
    
    def _get_folder_names(self, folder_ids: List[str]) -> List[str]:
        """获取文件夹名称列表"""
        folders = self.db.query(KnowledgeFolder.name).filter(
            KnowledgeFolder.id.in_(folder_ids)
        ).all()
        return [folder.name for folder in folders]
    
    def _validate_search_config(self, config: Dict[str, Any]) -> List[str]:
        """验证搜索配置"""
        errors = []
        
        if "similarity_threshold" in config:
            threshold = config["similarity_threshold"]
            if not isinstance(threshold, int) or threshold < 0 or threshold > 100:
                errors.append("相似度阈值必须是0-100之间的整数")
        
        if "max_results" in config:
            max_results = config["max_results"]
            if not isinstance(max_results, int) or max_results < 1 or max_results > 100:
                errors.append("最大结果数必须是1-100之间的整数")
        
        if "sort_by" in config:
            if config["sort_by"] not in ["relevance", "date", "size", "filename"]:
                errors.append("排序字段必须是relevance、date、size或filename之一")
        
        if "sort_order" in config:
            if config["sort_order"] not in ["asc", "desc"]:
                errors.append("排序顺序必须是asc或desc")
        
        return errors


def get_knowledge_search_manager(db: Session) -> KnowledgeSearchManager:
    """获取知识库检索管理器实例"""
    return KnowledgeSearchManager(db)