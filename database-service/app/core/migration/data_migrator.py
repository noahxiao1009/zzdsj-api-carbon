"""
数据迁移工具
用于将原始项目的数据迁移到新的微服务架构中
"""
import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import json
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from ..models import *
from .migration_config import MigrationConfig
from .migration_validator import MigrationValidator

logger = logging.getLogger(__name__)

class DataMigrator:
    """数据迁移器"""
    
    def __init__(self, source_db_url: str, target_db_url: str, config: MigrationConfig):
        self.source_db_url = source_db_url
        self.target_db_url = target_db_url
        self.config = config
        self.validator = MigrationValidator()
        
        # 创建数据库连接
        self.source_engine = create_engine(source_db_url)
        self.target_engine = create_async_engine(target_db_url)
        
        # 创建会话
        self.source_session = sessionmaker(bind=self.source_engine)
        self.target_session = sessionmaker(bind=self.target_engine, class_=AsyncSession)
        
        # 迁移统计
        self.migration_stats = {
            'total_records': 0,
            'migrated_records': 0,
            'failed_records': 0,
            'skipped_records': 0,
            'start_time': None,
            'end_time': None,
            'errors': []
        }
    
    async def migrate_all(self) -> Dict[str, Any]:
        """执行完整的数据迁移"""
        logger.info("开始数据迁移...")
        self.migration_stats['start_time'] = datetime.now()
        
        try:
            # 按依赖顺序迁移表
            migration_order = [
                'users',
                'roles', 
                'permissions',
                'user_role',
                'role_permissions',
                'user_settings',
                'api_keys',
                'user_sessions',
                'knowledge_bases',
                'documents',
                'document_chunks',
                'assistants',
                'assistant_knowledge_base',
                'conversations',
                'messages',
                'agent_definitions',
                'agent_templates',
                'tools',
                'tool_configurations',
                'system_configs',
                'model_providers'
            ]
            
            for table_name in migration_order:
                if table_name in self.config.tables_to_migrate:
                    await self.migrate_table(table_name)
            
            # 迁移完成后验证数据
            if self.config.validate_after_migration:
                await self.validate_migration()
                
        except Exception as e:
            logger.error(f"数据迁移失败: {e}")
            self.migration_stats['errors'].append(str(e))
            raise
        finally:
            self.migration_stats['end_time'] = datetime.now()
            
        return self.migration_stats
    
    async def migrate_table(self, table_name: str) -> None:
        """迁移单个表的数据"""
        logger.info(f"开始迁移表: {table_name}")
        
        try:
            # 获取源数据
            source_data = self.get_source_data(table_name)
            if not source_data:
                logger.info(f"表 {table_name} 没有数据需要迁移")
                return
            
            # 转换数据格式
            transformed_data = await self.transform_data(table_name, source_data)
            
            # 批量插入目标数据库
            await self.insert_target_data(table_name, transformed_data)
            
            logger.info(f"表 {table_name} 迁移完成，共迁移 {len(transformed_data)} 条记录")
            
        except Exception as e:
            logger.error(f"迁移表 {table_name} 失败: {e}")
            self.migration_stats['errors'].append(f"{table_name}: {str(e)}")
            raise
    
    def get_source_data(self, table_name: str) -> List[Dict[str, Any]]:
        """从源数据库获取数据"""
        with self.source_session() as session:
            # 根据表名构建查询
            query = text(f"SELECT * FROM {table_name}")
            result = session.execute(query)
            
            # 转换为字典列表
            columns = result.keys()
            data = []
            for row in result:
                data.append(dict(zip(columns, row)))
            
            self.migration_stats['total_records'] += len(data)
            return data
    
    async def transform_data(self, table_name: str, source_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """转换数据格式以适应新的数据库结构"""
        transformed_data = []
        
        for record in source_data:
            try:
                # 根据表名应用特定的转换规则
                transformed_record = await self.apply_transformation_rules(table_name, record)
                if transformed_record:
                    transformed_data.append(transformed_record)
                    self.migration_stats['migrated_records'] += 1
                else:
                    self.migration_stats['skipped_records'] += 1
                    
            except Exception as e:
                logger.warning(f"转换记录失败 {table_name}: {e}")
                self.migration_stats['failed_records'] += 1
                self.migration_stats['errors'].append(f"{table_name} record transformation: {str(e)}")
        
        return transformed_data
    
    async def apply_transformation_rules(self, table_name: str, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """应用表特定的转换规则"""
        
        # 通用字段处理
        transformed = {}
        
        # 处理时间字段
        for key, value in record.items():
            if isinstance(value, datetime):
                transformed[key] = value
            elif key.endswith('_at') and isinstance(value, str):
                try:
                    transformed[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                except:
                    transformed[key] = value
            else:
                transformed[key] = value
        
        # 表特定的转换规则
        if table_name == 'users':
            return await self.transform_user_record(transformed)
        elif table_name == 'assistants':
            return await self.transform_assistant_record(transformed)
        elif table_name == 'knowledge_bases':
            return await self.transform_knowledge_base_record(transformed)
        elif table_name == 'documents':
            return await self.transform_document_record(transformed)
        elif table_name == 'conversations':
            return await self.transform_conversation_record(transformed)
        elif table_name == 'messages':
            return await self.transform_message_record(transformed)
        else:
            return transformed
    
    async def transform_user_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """转换用户记录"""
        # 确保必需字段存在
        if not record.get('id'):
            record['id'] = str(uuid.uuid4())
        
        # 处理密码字段
        if 'password' in record and 'password_hash' not in record:
            record['password_hash'] = record.pop('password')
        
        # 设置默认值
        record.setdefault('is_active', True)
        record.setdefault('is_verified', False)
        record.setdefault('created_at', datetime.now())
        
        return record
    
    async def transform_assistant_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """转换助手记录"""
        # 处理配置字段
        if 'config' in record and isinstance(record['config'], str):
            try:
                record['config'] = json.loads(record['config'])
            except:
                record['config'] = {}
        
        # 处理模型配置
        if 'model_config' in record and isinstance(record['model_config'], str):
            try:
                record['model_config'] = json.loads(record['model_config'])
            except:
                record['model_config'] = {}
        
        return record
    
    async def transform_knowledge_base_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """转换知识库记录"""
        # 处理设置字段
        if 'settings' in record and isinstance(record['settings'], str):
            try:
                record['settings'] = json.loads(record['settings'])
            except:
                record['settings'] = {}
        
        return record
    
    async def transform_document_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """转换文档记录"""
        # 处理元数据字段
        if 'metadata' in record and isinstance(record['metadata'], str):
            try:
                record['metadata'] = json.loads(record['metadata'])
            except:
                record['metadata'] = {}
        
        return record
    
    async def transform_conversation_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """转换对话记录"""
        # 处理设置字段
        if 'settings' in record and isinstance(record['settings'], str):
            try:
                record['settings'] = json.loads(record['settings'])
            except:
                record['settings'] = {}
        
        return record
    
    async def transform_message_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """转换消息记录"""
        # 处理内容字段
        if 'content' in record and isinstance(record['content'], str):
            try:
                # 如果内容是JSON字符串，尝试解析
                parsed_content = json.loads(record['content'])
                record['content'] = parsed_content
            except:
                # 如果不是JSON，保持原样
                pass
        
        # 处理元数据字段
        if 'metadata' in record and isinstance(record['metadata'], str):
            try:
                record['metadata'] = json.loads(record['metadata'])
            except:
                record['metadata'] = {}
        
        return record
    
    async def insert_target_data(self, table_name: str, data: List[Dict[str, Any]]) -> None:
        """批量插入数据到目标数据库"""
        if not data:
            return
        
        async with self.target_session() as session:
            try:
                # 根据表名获取对应的模型类
                model_class = self.get_model_class(table_name)
                
                if model_class:
                    # 使用ORM插入
                    objects = [model_class(**record) for record in data]
                    session.add_all(objects)
                else:
                    # 使用原生SQL插入
                    await self.insert_raw_data(session, table_name, data)
                
                await session.commit()
                
            except Exception as e:
                await session.rollback()
                logger.error(f"插入数据到表 {table_name} 失败: {e}")
                raise
    
    def get_model_class(self, table_name: str):
        """根据表名获取对应的模型类"""
        model_mapping = {
            'users': User,
            'roles': Role,
            'permissions': Permission,
            'user_settings': UserSettings,
            'api_keys': ApiKey,
            'user_sessions': UserSession,
            'assistants': Assistant,
            'assistant_knowledge_base': AssistantKnowledgeBase,
            'conversations': Conversation,
            'messages': Message,
            'knowledge_bases': KnowledgeBase,
            'documents': Document,
            'document_chunks': DocumentChunk,
            'agent_definitions': AgentDefinition,
            'agent_templates': AgentTemplate,
            'tools': Tool,
            'tool_configurations': ToolConfiguration,
            'system_configs': SystemConfig,
            'model_providers': ModelProvider
        }
        
        return model_mapping.get(table_name)
    
    async def insert_raw_data(self, session: AsyncSession, table_name: str, data: List[Dict[str, Any]]) -> None:
        """使用原生SQL插入数据"""
        if not data:
            return
        
        # 构建插入语句
        columns = list(data[0].keys())
        placeholders = ', '.join([f':{col}' for col in columns])
        query = text(f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})")
        
        # 批量执行
        await session.execute(query, data)
    
    async def validate_migration(self) -> Dict[str, Any]:
        """验证迁移结果"""
        logger.info("开始验证迁移结果...")
        
        validation_results = {}
        
        for table_name in self.config.tables_to_migrate:
            try:
                # 验证记录数量
                source_count = self.get_source_record_count(table_name)
                target_count = await self.get_target_record_count(table_name)
                
                validation_results[table_name] = {
                    'source_count': source_count,
                    'target_count': target_count,
                    'match': source_count == target_count
                }
                
                if source_count != target_count:
                    logger.warning(f"表 {table_name} 记录数量不匹配: 源={source_count}, 目标={target_count}")
                
            except Exception as e:
                logger.error(f"验证表 {table_name} 失败: {e}")
                validation_results[table_name] = {'error': str(e)}
        
        return validation_results
    
    def get_source_record_count(self, table_name: str) -> int:
        """获取源数据库记录数量"""
        with self.source_session() as session:
            result = session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            return result.scalar()
    
    async def get_target_record_count(self, table_name: str) -> int:
        """获取目标数据库记录数量"""
        async with self.target_session() as session:
            result = await session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            return result.scalar()
    
    def generate_migration_report(self) -> Dict[str, Any]:
        """生成迁移报告"""
        duration = None
        if self.migration_stats['start_time'] and self.migration_stats['end_time']:
            duration = (self.migration_stats['end_time'] - self.migration_stats['start_time']).total_seconds()
        
        return {
            'migration_stats': self.migration_stats,
            'duration_seconds': duration,
            'success_rate': (self.migration_stats['migrated_records'] / max(self.migration_stats['total_records'], 1)) * 100,
            'timestamp': datetime.now().isoformat()
        }
    
    async def cleanup(self):
        """清理资源"""
        if hasattr(self, 'source_engine'):
            self.source_engine.dispose()
        if hasattr(self, 'target_engine'):
            await self.target_engine.dispose()