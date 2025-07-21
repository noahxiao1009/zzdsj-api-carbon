"""
智能报告服务数据库迁移脚本
创建所有必要的数据库表
"""

import asyncio
from sqlalchemy import text
from app.config.database import init_database, get_db_session, Base, init_db_engine
from app.models.database_models import (
    User, Report, ReportFile, ReportTask, ReportSession, 
    ReportLog, ModelUsage, SystemConfig, UserQuota, ReportTemplate
)
from app.common.logger_util import logger


async def create_all_tables():
    """创建所有数据库表"""
    try:
        logger.info("开始创建数据库表...")
        
        # 初始化数据库引擎
        engine = await init_db_engine()
        
        # 创建所有表
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("数据库表创建成功")
        return True
        
    except Exception as e:
        logger.error(f"创建数据库表失败: {e}", exc_info=True)
        return False


async def create_indexes():
    """创建数据库索引"""
    try:
        logger.info("开始创建数据库索引...")
        
        indexes = [
            # 用户表索引
            "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
            "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
            "CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active)",
            
            # 报告表索引
            "CREATE INDEX IF NOT EXISTS idx_reports_user_id ON reports(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status)",
            "CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_reports_user_status ON reports(user_id, status)",
            
            # 报告文件表索引
            "CREATE INDEX IF NOT EXISTS idx_report_files_report_id ON report_files(report_id)",
            "CREATE INDEX IF NOT EXISTS idx_report_files_filename ON report_files(filename)",
            
            # 报告任务表索引
            "CREATE INDEX IF NOT EXISTS idx_report_tasks_report_id ON report_tasks(report_id)",
            "CREATE INDEX IF NOT EXISTS idx_report_tasks_status ON report_tasks(status)",
            "CREATE INDEX IF NOT EXISTS idx_report_tasks_task_index ON report_tasks(report_id, task_index)",
            
            # 会话表索引
            "CREATE INDEX IF NOT EXISTS idx_report_sessions_user_id ON report_sessions(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_report_sessions_session_id ON report_sessions(session_id)",
            "CREATE INDEX IF NOT EXISTS idx_report_sessions_status ON report_sessions(status)",
            
            # 日志表索引
            "CREATE INDEX IF NOT EXISTS idx_report_logs_report_id ON report_logs(report_id)",
            "CREATE INDEX IF NOT EXISTS idx_report_logs_session_id ON report_logs(session_id)",
            "CREATE INDEX IF NOT EXISTS idx_report_logs_log_level ON report_logs(log_level)",
            "CREATE INDEX IF NOT EXISTS idx_report_logs_created_at ON report_logs(created_at)",
            
            # 模型使用记录表索引
            "CREATE INDEX IF NOT EXISTS idx_model_usage_user_id ON model_usage(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_model_usage_report_id ON model_usage(report_id)",
            "CREATE INDEX IF NOT EXISTS idx_model_usage_model_provider ON model_usage(model_provider)",
            "CREATE INDEX IF NOT EXISTS idx_model_usage_created_at ON model_usage(created_at)",
            
            # 系统配置表索引
            "CREATE INDEX IF NOT EXISTS idx_system_configs_config_key ON system_configs(config_key)",
            "CREATE INDEX IF NOT EXISTS idx_system_configs_config_type ON system_configs(config_type)",
            
            # 用户配额表索引
            "CREATE INDEX IF NOT EXISTS idx_user_quotas_user_id ON user_quotas(user_id)",
            
            # 报告模板表索引
            "CREATE INDEX IF NOT EXISTS idx_report_templates_category ON report_templates(category)",
            "CREATE INDEX IF NOT EXISTS idx_report_templates_is_public ON report_templates(is_public)",
            "CREATE INDEX IF NOT EXISTS idx_report_templates_is_active ON report_templates(is_active)",
            "CREATE INDEX IF NOT EXISTS idx_report_templates_created_by ON report_templates(created_by)"
        ]
        
        async with get_db_session() as session:
            for index_sql in indexes:
                try:
                    await session.execute(text(index_sql))
                    logger.debug(f"创建索引: {index_sql}")
                except Exception as e:
                    logger.warning(f"创建索引失败: {index_sql}, 错误: {e}")
            
            await session.commit()
        
        logger.info("数据库索引创建完成")
        return True
        
    except Exception as e:
        logger.error(f"创建数据库索引失败: {e}", exc_info=True)
        return False


async def insert_default_data():
    """插入默认数据"""
    try:
        logger.info("开始插入默认数据...")
        
        async with get_db_session() as session:
            # 插入默认系统配置
            default_configs = [
                {
                    "config_key": "system.workspace.base_path",
                    "config_value": {"path": "./workspace"},
                    "config_type": "path",
                    "description": "报告生成工作空间基础路径"
                },
                {
                    "config_key": "system.report.max_concurrent",
                    "config_value": {"count": 5},
                    "config_type": "integer",
                    "description": "最大并发报告生成数量"
                },
                {
                    "config_key": "system.session.timeout_hours",
                    "config_value": {"hours": 24},
                    "config_type": "integer",
                    "description": "会话超时时间(小时)"
                },
                {
                    "config_key": "system.file.max_size_mb",
                    "config_value": {"size": 100},
                    "config_type": "integer",
                    "description": "最大文件大小(MB)"
                },
                {
                    "config_key": "system.model.default_provider",
                    "config_value": {"provider": "zhipu"},
                    "config_type": "string",
                    "description": "默认模型提供商"
                }
            ]
            
            for config_data in default_configs:
                # 检查配置是否已存在
                existing = await session.execute(
                    text("SELECT id FROM system_configs WHERE config_key = :key"),
                    {"key": config_data["config_key"]}
                )
                if not existing.first():
                    config = SystemConfig(**config_data)
                    session.add(config)
            
            # 插入默认报告模板
            default_templates = [
                {
                    "name": "数据分析报告",
                    "description": "通用数据分析报告模板",
                    "category": "数据分析",
                    "template_query": "请分析{data_source}的数据，生成详细的分析报告，包括数据概况、趋势分析、异常检测和建议。",
                    "default_format": "PDF",
                    "config": {
                        "include_charts": True,
                        "include_summary": True,
                        "include_recommendations": True
                    },
                    "variables": [
                        {"name": "data_source", "type": "string", "description": "数据源名称", "required": True}
                    ],
                    "is_public": True
                },
                {
                    "name": "市场研究报告",
                    "description": "市场分析和研究报告模板",
                    "category": "市场研究",
                    "template_query": "针对{market_sector}进行深入的市场研究，分析{analysis_focus}，生成专业的市场研究报告。",
                    "default_format": "PDF",
                    "config": {
                        "include_competitive_analysis": True,
                        "include_market_trends": True,
                        "include_swot_analysis": True
                    },
                    "variables": [
                        {"name": "market_sector", "type": "string", "description": "市场领域", "required": True},
                        {"name": "analysis_focus", "type": "string", "description": "分析重点", "required": True}
                    ],
                    "is_public": True
                },
                {
                    "name": "技术文档报告",
                    "description": "技术文档和说明报告模板",
                    "category": "技术文档",
                    "template_query": "为{technology_topic}创建详细的技术文档，包括{content_requirements}。",
                    "default_format": "Markdown",
                    "config": {
                        "include_code_examples": True,
                        "include_diagrams": True,
                        "include_best_practices": True
                    },
                    "variables": [
                        {"name": "technology_topic", "type": "string", "description": "技术主题", "required": True},
                        {"name": "content_requirements", "type": "string", "description": "内容要求", "required": True}
                    ],
                    "is_public": True
                }
            ]
            
            for template_data in default_templates:
                # 检查模板是否已存在
                existing = await session.execute(
                    text("SELECT id FROM report_templates WHERE name = :name"),
                    {"name": template_data["name"]}
                )
                if not existing.first():
                    template = ReportTemplate(**template_data)
                    session.add(template)
            
            await session.commit()
        
        logger.info("默认数据插入完成")
        return True
        
    except Exception as e:
        logger.error(f"插入默认数据失败: {e}", exc_info=True)
        return False


async def run_migration():
    """运行完整的数据库迁移"""
    try:
        logger.info("开始运行数据库迁移...")
        
        # 1. 创建所有表
        if not await create_all_tables():
            return False
        
        # 2. 创建索引
        if not await create_indexes():
            return False
        
        # 3. 插入默认数据
        if not await insert_default_data():
            return False
        
        logger.info("数据库迁移完成")
        return True
        
    except Exception as e:
        logger.error(f"数据库迁移失败: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    # 运行迁移
    success = asyncio.run(run_migration())
    if success:
        print("数据库迁移成功")
    else:
        print("数据库迁移失败")
        exit(1)