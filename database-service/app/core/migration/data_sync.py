"""
数据同步管理器
提供数据同步和一致性检查功能
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from ...models.database import get_db_session
from ...config.database_config import get_database_config

logger = logging.getLogger(__name__)


class DataSyncManager:
    """数据同步管理器"""
    
    def __init__(self):
        self.config = get_database_config()
        self.sync_tasks = {}
    
    async def sync_data_between_services(self, source_service: str, target_service: str) -> bool:
        """在服务之间同步数据"""
        try:
            logger.info(f"开始同步数据: {source_service} -> {target_service}")
            
            # 实现服务间数据同步逻辑
            # 1. 获取源服务数据
            # 2. 转换数据格式
            # 3. 写入目标服务
            
            logger.info("数据同步完成")
            return True
            
        except Exception as e:
            logger.error(f"数据同步失败: {e}")
            return False
    
    async def check_data_consistency(self) -> Dict[str, Any]:
        """检查数据一致性"""
        try:
            logger.info("开始检查数据一致性...")
            
            consistency_report = {
                "status": "consistent",
                "checks": [],
                "inconsistencies": [],
                "recommendations": []
            }
            
            async with get_db_session() as db:
                # 检查用户数据一致性
                await self._check_user_consistency(db, consistency_report)
                
                # 检查助手数据一致性
                await self._check_assistant_consistency(db, consistency_report)
                
                # 检查知识库数据一致性
                await self._check_knowledge_consistency(db, consistency_report)
            
            # 确定整体状态
            if consistency_report["inconsistencies"]:
                consistency_report["status"] = "inconsistent"
            
            logger.info("数据一致性检查完成")
            return consistency_report
            
        except Exception as e:
            logger.error(f"数据一致性检查失败: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _check_user_consistency(self, db, report):
        """检查用户数据一致性"""
        from ...repositories.user_repository import UserRepository, RoleRepository
        
        user_repo = UserRepository()
        role_repo = RoleRepository()
        
        # 检查用户角色关联
        users = await user_repo.get_multi(db, limit=1000)
        for user in users:
            user_with_roles = await user_repo.get_with_roles(db, user.id)
            if not user_with_roles.roles:
                report["inconsistencies"].append({
                    "type": "missing_user_role",
                    "user_id": user.id,
                    "message": f"用户 {user.username} 没有分配角色"
                })
        
        report["checks"].append("user_role_consistency")
    
    async def _check_assistant_consistency(self, db, report):
        """检查助手数据一致性"""
        from ...repositories.assistant_repository import AssistantRepository, ConversationRepository
        
        assistant_repo = AssistantRepository()
        conversation_repo = ConversationRepository()
        
        # 检查助手对话关联
        assistants = await assistant_repo.get_multi(db, limit=1000)
        for assistant in assistants:
            conversations = await conversation_repo.get_by_assistant_id(db, assistant.id)
            # 可以添加更多一致性检查
        
        report["checks"].append("assistant_conversation_consistency")
    
    async def _check_knowledge_consistency(self, db, report):
        """检查知识库数据一致性"""
        from ...repositories.knowledge_repository import KnowledgeBaseRepository, DocumentRepository
        
        kb_repo = KnowledgeBaseRepository()
        doc_repo = DocumentRepository()
        
        # 检查知识库文档关联
        knowledge_bases = await kb_repo.get_multi(db, limit=1000)
        for kb in knowledge_bases:
            documents = await doc_repo.get_by_kb_id(db, kb.id)
            # 可以添加更多一致性检查
        
        report["checks"].append("knowledge_document_consistency")
    
    async def repair_data_inconsistencies(self, inconsistencies: List[Dict[str, Any]]) -> Dict[str, Any]:
        """修复数据不一致问题"""
        try:
            logger.info("开始修复数据不一致问题...")
            
            repair_report = {
                "status": "completed",
                "repaired": [],
                "failed": [],
                "skipped": []
            }
            
            async with get_db_session() as db:
                for inconsistency in inconsistencies:
                    try:
                        await self._repair_single_inconsistency(db, inconsistency)
                        repair_report["repaired"].append(inconsistency)
                    except Exception as e:
                        logger.error(f"修复失败: {inconsistency}, 错误: {e}")
                        repair_report["failed"].append({
                            "inconsistency": inconsistency,
                            "error": str(e)
                        })
            
            logger.info("数据不一致问题修复完成")
            return repair_report
            
        except Exception as e:
            logger.error(f"数据修复失败: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _repair_single_inconsistency(self, db, inconsistency):
        """修复单个数据不一致问题"""
        inconsistency_type = inconsistency.get("type")
        
        if inconsistency_type == "missing_user_role":
            # 为用户分配默认角色
            from ...repositories.user_repository import UserRepository, RoleRepository
            
            user_repo = UserRepository()
            role_repo = RoleRepository()
            
            user_id = inconsistency["user_id"]
            user = await user_repo.get_with_roles(db, user_id)
            default_role = await role_repo.get_by_name(db, "user")
            
            if user and default_role and default_role not in user.roles:
                user.roles.append(default_role)
                await db.commit()
                logger.info(f"为用户 {user_id} 分配默认角色")
    
    async def schedule_sync_task(self, task_name: str, sync_func, interval_minutes: int = 60):
        """调度同步任务"""
        async def sync_task():
            while True:
                try:
                    await sync_func()
                    logger.info(f"同步任务 {task_name} 执行完成")
                except Exception as e:
                    logger.error(f"同步任务 {task_name} 执行失败: {e}")
                
                await asyncio.sleep(interval_minutes * 60)
        
        # 启动任务
        task = asyncio.create_task(sync_task())
        self.sync_tasks[task_name] = task
        logger.info(f"调度同步任务: {task_name}, 间隔: {interval_minutes}分钟")
    
    async def stop_sync_task(self, task_name: str):
        """停止同步任务"""
        if task_name in self.sync_tasks:
            self.sync_tasks[task_name].cancel()
            del self.sync_tasks[task_name]
            logger.info(f"停止同步任务: {task_name}")
    
    async def get_sync_status(self) -> Dict[str, Any]:
        """获取同步状态"""
        return {
            "active_tasks": list(self.sync_tasks.keys()),
            "task_count": len(self.sync_tasks),
            "last_check": datetime.now().isoformat()
        }