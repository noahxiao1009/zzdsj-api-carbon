"""
文件夹检索管理器
专注于文件夹级别的检索功能实现
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc

from app.models.simple_folder_models import KnowledgeFolder, FolderSearchConfig
from app.models.knowledge_models import Document, DocumentChunk
from app.models.database import get_db

logger = logging.getLogger(__name__)


class FolderSearchManager:
    """文件夹检索管理器"""
    
    def __init__(self, db: Session):
        self.db = db
        logger.info("Folder Search Manager initialized")
    
    # ===============================
    # 检索范围管理
    # ===============================
    
    def get_search_scopes(self, kb_id: str) -> List[Dict[str, Any]]:
        """获取知识库的所有检索范围选项"""
        try:
            # 获取知识库级别的选项
            scopes = [
                {
                    "id": f"kb_{kb_id}",
                    "name": "整个知识库",
                    "type": "knowledge_base",
                    "description": "在整个知识库中检索",
                    "document_count": self._get_kb_document_count(kb_id)
                }
            ]
            
            # 获取所有文件夹作为检索范围
            folders = self.db.query(KnowledgeFolder).filter(
                and_(
                    KnowledgeFolder.kb_id == kb_id,
                    KnowledgeFolder.status == "active",
                    KnowledgeFolder.enable_search == True
                )
            ).order_by(KnowledgeFolder.level, KnowledgeFolder.name).all()
            
            for folder in folders:
                scope_info = {
                    "id": folder.id,
                    "name": folder.name,
                    "type": "folder",
                    "level": folder.level,
                    "full_path": folder.full_path,
                    "description": folder.description or f"在 {folder.full_path} 中检索",
                    "document_count": folder.document_count,
                    "search_scope": folder.search_scope,
                    "search_weight": folder.search_weight
                }
                scopes.append(scope_info)
            
            return scopes
            
        except Exception as e:
            logger.error(f"Failed to get search scopes for kb {kb_id}: {e}")
            return []
    
    def set_folder_search_config(
        self,
        folder_id: str,
        kb_id: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """设置文件夹的检索配置"""
        try:
            # 检查文件夹是否存在
            folder = self.db.query(KnowledgeFolder).filter(
                and_(
                    KnowledgeFolder.id == folder_id,
                    KnowledgeFolder.kb_id == kb_id,
                    KnowledgeFolder.status == "active"
                )
            ).first()
            
            if not folder:
                return {"success": False, "error": "文件夹不存在"}
            
            # 获取或创建检索配置
            search_config = self.db.query(FolderSearchConfig).filter(
                FolderSearchConfig.folder_id == folder_id
            ).first()
            
            if not search_config:
                search_config = FolderSearchConfig(
                    folder_id=folder_id,
                    kb_id=kb_id
                )
                self.db.add(search_config)
            
            # 更新配置
            if "similarity_threshold" in config:
                search_config.similarity_threshold = config["similarity_threshold"]
            if "max_results" in config:
                search_config.max_results = config["max_results"]
            if "enable_semantic_search" in config:
                search_config.enable_semantic_search = config["enable_semantic_search"]
            if "enable_keyword_search" in config:
                search_config.enable_keyword_search = config["enable_keyword_search"]
            if "sort_by" in config:
                search_config.sort_by = config["sort_by"]
            if "sort_order" in config:
                search_config.sort_order = config["sort_order"]
            if "allowed_file_types" in config:
                search_config.allowed_file_types = config["allowed_file_types"]
            if "boost_recent_documents" in config:
                search_config.boost_recent_documents = config["boost_recent_documents"]
            if "boost_factor" in config:
                search_config.boost_factor = config["boost_factor"]
            
            # 更新文件夹的基础检索设置
            if "search_scope" in config:
                folder.search_scope = config["search_scope"]
            if "search_weight" in config:
                folder.search_weight = config["search_weight"]
            if "enable_search" in config:
                folder.enable_search = config["enable_search"]
            
            self.db.commit()
            
            return {
                "success": True,
                "message": "检索配置更新成功",
                "config": self._format_search_config(search_config, folder)
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to set folder search config: {e}")
            return {"success": False, "error": str(e)}
    
    def get_folder_search_config(self, folder_id: str, kb_id: str) -> Optional[Dict[str, Any]]:
        """获取文件夹的检索配置"""
        try:
            folder = self.db.query(KnowledgeFolder).filter(
                and_(
                    KnowledgeFolder.id == folder_id,
                    KnowledgeFolder.kb_id == kb_id
                )
            ).first()
            
            if not folder:
                return None
            
            search_config = self.db.query(FolderSearchConfig).filter(
                FolderSearchConfig.folder_id == folder_id
            ).first()
            
            return self._format_search_config(search_config, folder)
            
        except Exception as e:
            logger.error(f"Failed to get folder search config: {e}")
            return None
    
    # ===============================
    # 核心检索功能
    # ===============================
    
    def search_in_scope(
        self,
        kb_id: str,
        query: str,
        search_scope_id: str,
        search_type: str = "hybrid",
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """在指定范围内检索"""
        try:
            # 确定检索范围
            if search_scope_id.startswith("kb_"):
                # 整个知识库检索
                return self._search_in_knowledge_base(kb_id, query, search_type, limit, filters)
            else:
                # 文件夹检索
                return self._search_in_folder(kb_id, search_scope_id, query, search_type, limit, filters)
                
        except Exception as e:
            logger.error(f"Failed to search in scope {search_scope_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def _search_in_knowledge_base(
        self,
        kb_id: str,
        query: str,
        search_type: str,
        limit: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """在整个知识库中检索"""
        try:
            # 构建文档查询
            doc_query = self.db.query(Document).filter(
                and_(
                    Document.kb_id == kb_id,
                    Document.status == "completed"
                )
            )
            
            # 应用过滤器
            if filters and "file_types" in filters:
                doc_query = doc_query.filter(Document.file_type.in_(filters["file_types"]))
            
            # 执行搜索逻辑
            if search_type == "keyword":
                results = self._keyword_search(doc_query, query, limit)
            elif search_type == "semantic":
                results = self._semantic_search(doc_query, query, limit)
            else:  # hybrid
                results = self._hybrid_search(doc_query, query, limit)
            
            return {
                "success": True,
                "results": results,
                "total": len(results),
                "search_scope": "整个知识库",
                "search_type": search_type,
                "query": query
            }
            
        except Exception as e:
            logger.error(f"Failed to search in knowledge base: {e}")
            return {"success": False, "error": str(e)}
    
    def _search_in_folder(
        self,
        kb_id: str,
        folder_id: str,
        query: str,
        search_type: str,
        limit: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """在指定文件夹中检索"""
        try:
            # 获取文件夹信息
            folder = self.db.query(KnowledgeFolder).filter(
                and_(
                    KnowledgeFolder.id == folder_id,
                    KnowledgeFolder.kb_id == kb_id,
                    KnowledgeFolder.status == "active"
                )
            ).first()
            
            if not folder:
                return {"success": False, "error": "文件夹不存在"}
            
            if not folder.enable_search:
                return {"success": False, "error": "此文件夹禁用了检索功能"}
            
            # 获取检索配置
            search_config = self.db.query(FolderSearchConfig).filter(
                FolderSearchConfig.folder_id == folder_id
            ).first()
            
            # 确定检索范围内的文件夹ID
            folder_ids = folder.get_search_scope_folders()
            
            # 构建文档查询
            doc_query = self.db.query(Document).filter(
                and_(
                    Document.kb_id == kb_id,
                    Document.folder_id.in_(folder_ids),
                    Document.status == "completed"
                )
            )
            
            # 应用检索配置中的过滤器
            if search_config and search_config.allowed_file_types:
                doc_query = doc_query.filter(Document.file_type.in_(search_config.allowed_file_types))
            
            # 应用外部过滤器
            if filters and "file_types" in filters:
                doc_query = doc_query.filter(Document.file_type.in_(filters["file_types"]))
            
            # 确定结果数量限制
            result_limit = limit
            if search_config and search_config.max_results:
                result_limit = min(limit, search_config.max_results)
            
            # 执行搜索
            if search_type == "keyword":
                results = self._keyword_search(doc_query, query, result_limit, search_config)
            elif search_type == "semantic":
                results = self._semantic_search(doc_query, query, result_limit, search_config)
            else:  # hybrid
                results = self._hybrid_search(doc_query, query, result_limit, search_config)
            
            # 应用文件夹权重
            if folder.search_weight > 1:
                for result in results:
                    result["relevance_score"] = min(1.0, result["relevance_score"] * folder.search_weight / 10)
            
            return {
                "success": True,
                "results": results,
                "total": len(results),
                "search_scope": f"文件夹: {folder.full_path}",
                "search_scope_type": folder.search_scope,
                "folder_info": {
                    "id": folder.id,
                    "name": folder.name,
                    "full_path": folder.full_path,
                    "document_count": folder.document_count
                },
                "search_type": search_type,
                "query": query
            }
            
        except Exception as e:
            logger.error(f"Failed to search in folder {folder_id}: {e}")
            return {"success": False, "error": str(e)}
    
    # ===============================
    # 具体搜索算法实现
    # ===============================
    
    def _keyword_search(
        self,
        doc_query,
        query: str,
        limit: int,
        search_config: Optional[FolderSearchConfig] = None
    ) -> List[Dict[str, Any]]:
        """关键词搜索"""
        try:
            # 简化的关键词搜索实现
            documents = doc_query.filter(
                or_(
                    Document.filename.ilike(f"%{query}%"),
                    Document.content.ilike(f"%{query}%")
                )
            ).limit(limit).all()
            
            results = []
            for doc in documents:
                # 计算简单的相关性得分
                score = 0.5
                if query.lower() in doc.filename.lower():
                    score += 0.3
                if doc.content and query.lower() in doc.content.lower():
                    score += 0.2
                
                # 应用时间权重提升
                if search_config and search_config.boost_recent_documents:
                    from datetime import datetime, timedelta
                    if doc.created_at and doc.created_at > datetime.now() - timedelta(days=30):
                        score *= search_config.boost_factor
                
                results.append({
                    "document_id": doc.id,
                    "filename": doc.filename,
                    "file_type": doc.file_type,
                    "file_size": doc.file_size,
                    "relevance_score": min(1.0, score),
                    "snippet": self._generate_snippet(doc.content, query) if doc.content else "",
                    "folder_path": self._get_folder_path(doc.folder_id),
                    "created_at": doc.created_at.isoformat() if doc.created_at else None
                })
            
            # 按相关性排序
            results.sort(key=lambda x: x["relevance_score"], reverse=True)
            return results
            
        except Exception as e:
            logger.error(f"Keyword search failed: {e}")
            return []
    
    def _semantic_search(
        self,
        doc_query,
        query: str,
        limit: int,
        search_config: Optional[FolderSearchConfig] = None
    ) -> List[Dict[str, Any]]:
        """语义搜索 - 这里是简化实现，实际应该调用向量搜索"""
        try:
            # 简化实现：暂时使用关键词搜索模拟
            # 实际应该：
            # 1. 将query转换为向量
            # 2. 在向量数据库中搜索
            # 3. 根据相似度排序
            
            documents = doc_query.limit(limit * 2).all()  # 获取更多候选
            
            results = []
            for doc in documents:
                # 模拟语义相似度计算
                score = self._calculate_semantic_similarity(doc, query)
                
                # 应用相似度阈值
                threshold = 0.7
                if search_config and search_config.similarity_threshold:
                    threshold = search_config.similarity_threshold / 100
                
                if score >= threshold:
                    results.append({
                        "document_id": doc.id,
                        "filename": doc.filename,
                        "file_type": doc.file_type,
                        "file_size": doc.file_size,
                        "relevance_score": score,
                        "snippet": self._generate_snippet(doc.content, query) if doc.content else "",
                        "folder_path": self._get_folder_path(doc.folder_id),
                        "created_at": doc.created_at.isoformat() if doc.created_at else None,
                        "search_method": "semantic"
                    })
            
            # 按相关性排序并限制结果数量
            results.sort(key=lambda x: x["relevance_score"], reverse=True)
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []
    
    def _hybrid_search(
        self,
        doc_query,
        query: str,
        limit: int,
        search_config: Optional[FolderSearchConfig] = None
    ) -> List[Dict[str, Any]]:
        """混合搜索：结合关键词和语义搜索"""
        try:
            # 获取关键词搜索结果
            keyword_results = self._keyword_search(doc_query, query, limit // 2, search_config)
            
            # 获取语义搜索结果
            semantic_results = self._semantic_search(doc_query, query, limit // 2, search_config)
            
            # 合并去重
            seen_docs = set()
            merged_results = []
            
            # 先添加关键词结果
            for result in keyword_results:
                if result["document_id"] not in seen_docs:
                    result["search_method"] = "keyword"
                    merged_results.append(result)
                    seen_docs.add(result["document_id"])
            
            # 再添加语义结果
            for result in semantic_results:
                if result["document_id"] not in seen_docs:
                    result["search_method"] = "semantic"
                    merged_results.append(result)
                    seen_docs.add(result["document_id"])
                else:
                    # 如果文档已存在，提升其相关性得分
                    for existing in merged_results:
                        if existing["document_id"] == result["document_id"]:
                            existing["relevance_score"] = min(1.0, existing["relevance_score"] + 0.1)
                            existing["search_method"] = "hybrid"
                            break
            
            # 重新排序
            merged_results.sort(key=lambda x: x["relevance_score"], reverse=True)
            return merged_results[:limit]
            
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            return []
    
    # ===============================
    # 辅助方法
    # ===============================
    
    def _calculate_semantic_similarity(self, document: Document, query: str) -> float:
        """计算语义相似度 - 简化实现"""
        # 这里是简化实现，实际应该调用embedding模型
        if not document.content:
            return 0.3
        
        # 简单的词汇重叠计算
        query_words = set(query.lower().split())
        doc_words = set(document.content.lower().split())
        
        if not query_words:
            return 0.0
        
        overlap = len(query_words.intersection(doc_words))
        similarity = overlap / len(query_words)
        
        return min(1.0, similarity + 0.2)  # 基础得分提升
    
    def _generate_snippet(self, content: str, query: str, max_length: int = 200) -> str:
        """生成搜索结果摘要"""
        if not content or not query:
            return ""
        
        query_lower = query.lower()
        content_lower = content.lower()
        
        # 找到查询词的位置
        pos = content_lower.find(query_lower)
        if pos == -1:
            return content[:max_length] + "..." if len(content) > max_length else content
        
        # 计算摘要起始位置
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
    
    def _get_kb_document_count(self, kb_id: str) -> int:
        """获取知识库文档总数"""
        return self.db.query(func.count(Document.id)).filter(
            and_(
                Document.kb_id == kb_id,
                Document.status == "completed"
            )
        ).scalar() or 0
    
    def _format_search_config(
        self,
        search_config: Optional[FolderSearchConfig],
        folder: KnowledgeFolder
    ) -> Dict[str, Any]:
        """格式化检索配置"""
        base_config = {
            "folder_id": folder.id,
            "folder_name": folder.name,
            "enable_search": folder.enable_search,
            "search_scope": folder.search_scope,
            "search_weight": folder.search_weight
        }
        
        if search_config:
            base_config.update({
                "similarity_threshold": search_config.similarity_threshold,
                "max_results": search_config.max_results,
                "enable_semantic_search": search_config.enable_semantic_search,
                "enable_keyword_search": search_config.enable_keyword_search,
                "sort_by": search_config.sort_by,
                "sort_order": search_config.sort_order,
                "allowed_file_types": search_config.allowed_file_types,
                "boost_recent_documents": search_config.boost_recent_documents,
                "boost_factor": search_config.boost_factor
            })
        else:
            # 默认配置
            base_config.update({
                "similarity_threshold": 70,
                "max_results": 10,
                "enable_semantic_search": True,
                "enable_keyword_search": True,
                "sort_by": "relevance",
                "sort_order": "desc",
                "allowed_file_types": [],
                "boost_recent_documents": False,
                "boost_factor": 1
            })
        
        return base_config


def get_folder_search_manager(db: Session) -> FolderSearchManager:
    """获取文件夹检索管理器实例"""
    return FolderSearchManager(db)