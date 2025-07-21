"""
处理任务Repository
处理异步任务的数据库操作
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from app.models.knowledge_models import ProcessingJob
from .base_repository import BaseRepository


class ProcessingJobRepository(BaseRepository[ProcessingJob]):
    """处理任务数据访问层"""
    
    def __init__(self, db: Session):
        super().__init__(ProcessingJob, db)
    
    async def get_by_knowledge_base(
        self, 
        kb_id: UUID, 
        job_type: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0, 
        limit: int = 100
    ) -> List[ProcessingJob]:
        """获取知识库的处理任务"""
        query = self.db.query(ProcessingJob)\
            .filter(ProcessingJob.kb_id == kb_id)
        
        if job_type:
            query = query.filter(ProcessingJob.job_type == job_type)
        
        if status:
            query = query.filter(ProcessingJob.status == status)
        
        return query.order_by(ProcessingJob.created_at.desc())\
            .offset(skip)\
            .limit(limit)\
            .all()
    
    async def get_by_document(
        self, 
        doc_id: UUID,
        job_type: Optional[str] = None
    ) -> List[ProcessingJob]:
        """获取文档的处理任务"""
        query = self.db.query(ProcessingJob)\
            .filter(ProcessingJob.doc_id == doc_id)
        
        if job_type:
            query = query.filter(ProcessingJob.job_type == job_type)
        
        return query.order_by(ProcessingJob.created_at.desc()).all()
    
    async def get_pending_jobs(
        self, 
        job_type: Optional[str] = None,
        limit: int = 100
    ) -> List[ProcessingJob]:
        """获取待处理的任务"""
        query = self.db.query(ProcessingJob)\
            .filter(ProcessingJob.status == "pending")
        
        if job_type:
            query = query.filter(ProcessingJob.job_type == job_type)
        
        return query.order_by(
            ProcessingJob.priority.desc(),
            ProcessingJob.created_at
        ).limit(limit).all()
    
    async def get_running_jobs(self, job_type: Optional[str] = None) -> List[ProcessingJob]:
        """获取正在运行的任务"""
        query = self.db.query(ProcessingJob)\
            .filter(ProcessingJob.status == "running")
        
        if job_type:
            query = query.filter(ProcessingJob.job_type == job_type)
        
        return query.order_by(ProcessingJob.started_at).all()
    
    async def get_failed_jobs(
        self, 
        kb_id: Optional[UUID] = None,
        limit: int = 100
    ) -> List[ProcessingJob]:
        """获取失败的任务"""
        query = self.db.query(ProcessingJob)\
            .filter(ProcessingJob.status == "failed")
        
        if kb_id:
            query = query.filter(ProcessingJob.kb_id == kb_id)
        
        return query.order_by(ProcessingJob.completed_at.desc())\
            .limit(limit)\
            .all()
    
    async def update_job_status(
        self,
        job_id: UUID,
        status: str,
        progress: Optional[float] = None,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None
    ) -> Optional[ProcessingJob]:
        """更新任务状态"""
        job = await self.get_by_id(job_id)
        if not job:
            return None
        
        job.status = status
        
        if progress is not None:
            job.progress = progress
        
        if result is not None:
            job.result = result
        
        if error_message is not None:
            job.error_message = error_message
        
        if error_details is not None:
            job.error_details = error_details
        
        # 设置时间戳
        if status == "running" and not job.started_at:
            job.started_at = func.now()
        elif status in ["completed", "failed", "cancelled"]:
            job.completed_at = func.now()
            if job.started_at:
                # 计算实际耗时（这里需要在应用层计算）
                pass
        
        self.db.commit()
        self.db.refresh(job)
        
        return job
    
    async def update_job_progress(
        self,
        job_id: UUID,
        processed_items: int,
        total_items: Optional[int] = None
    ) -> Optional[ProcessingJob]:
        """更新任务进度"""
        job = await self.get_by_id(job_id)
        if not job:
            return None
        
        job.processed_items = processed_items
        
        if total_items is not None:
            job.total_items = total_items
        
        # 计算进度百分比
        if job.total_items > 0:
            job.progress = min(1.0, job.processed_items / job.total_items)
        
        self.db.commit()
        self.db.refresh(job)
        
        return job
    
    async def cancel_pending_jobs(
        self, 
        kb_id: UUID, 
        job_type: Optional[str] = None
    ) -> List[ProcessingJob]:
        """取消待处理的任务"""
        query = self.db.query(ProcessingJob)\
            .filter(
                and_(
                    ProcessingJob.kb_id == kb_id,
                    ProcessingJob.status == "pending"
                )
            )
        
        if job_type:
            query = query.filter(ProcessingJob.job_type == job_type)
        
        jobs = query.all()
        
        for job in jobs:
            job.status = "cancelled"
            job.completed_at = func.now()
        
        self.db.commit()
        
        for job in jobs:
            self.db.refresh(job)
        
        return jobs
    
    async def get_job_statistics(
        self, 
        kb_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """获取任务统计信息"""
        query = self.db.query(ProcessingJob)
        
        if kb_id:
            query = query.filter(ProcessingJob.kb_id == kb_id)
        
        # 总体统计
        total_stats = query.with_entities(
            func.count(ProcessingJob.id).label('total_jobs'),
            func.count(ProcessingJob.id).filter(
                ProcessingJob.status == "pending"
            ).label('pending_jobs'),
            func.count(ProcessingJob.id).filter(
                ProcessingJob.status == "running"
            ).label('running_jobs'),
            func.count(ProcessingJob.id).filter(
                ProcessingJob.status == "completed"
            ).label('completed_jobs'),
            func.count(ProcessingJob.id).filter(
                ProcessingJob.status == "failed"
            ).label('failed_jobs'),
            func.avg(ProcessingJob.actual_duration).label('avg_duration')
        ).first()
        
        # 按任务类型统计
        type_stats = query.with_entities(
            ProcessingJob.job_type,
            func.count(ProcessingJob.id).label('count')
        ).group_by(ProcessingJob.job_type).all()
        
        return {
            'total_jobs': total_stats.total_jobs or 0,
            'pending_jobs': total_stats.pending_jobs or 0,
            'running_jobs': total_stats.running_jobs or 0,
            'completed_jobs': total_stats.completed_jobs or 0,
            'failed_jobs': total_stats.failed_jobs or 0,
            'avg_duration': float(total_stats.avg_duration or 0),
            'job_types_distribution': {
                job_type: count for job_type, count in type_stats
            }
        }
    
    async def cleanup_old_jobs(self, days_old: int = 30) -> int:
        """清理旧的已完成任务"""
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days_old)
        
        deleted_count = self.db.query(ProcessingJob)\
            .filter(
                and_(
                    ProcessingJob.status.in_(["completed", "failed", "cancelled"]),
                    ProcessingJob.completed_at < cutoff_date
                )
            )\
            .delete()
        
        self.db.commit()
        return deleted_count
    
    async def retry_failed_job(self, job_id: UUID) -> Optional[ProcessingJob]:
        """重试失败的任务"""
        job = await self.get_by_id(job_id)
        if not job or job.status != "failed":
            return None
        
        # 重置任务状态
        job.status = "pending"
        job.progress = 0.0
        job.processed_items = 0
        job.error_message = None
        job.error_details = {}
        job.started_at = None
        job.completed_at = None
        job.actual_duration = None
        
        self.db.commit()
        self.db.refresh(job)
        
        return job