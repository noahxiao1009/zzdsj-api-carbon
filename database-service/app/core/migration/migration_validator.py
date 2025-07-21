"""
迁移验证器
用于验证数据迁移的完整性和正确性
"""
import logging
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
import hashlib
import json

logger = logging.getLogger(__name__)

class MigrationValidator:
    """迁移验证器"""
    
    def __init__(self):
        self.validation_results = {}
    
    async def validate_migration(self, source_db_url: str, target_db_url: str, 
                               tables: List[str]) -> Dict[str, Any]:
        """验证完整的迁移结果"""
        logger.info("开始验证数据迁移...")
        
        # 创建数据库连接
        source_engine = create_engine(source_db_url)
        target_engine = create_async_engine(target_db_url)
        
        source_session = sessionmaker(bind=source_engine)
        target_session = sessionmaker(bind=target_engine, class_=AsyncSession)
        
        validation_results = {
            'overall_status': 'success',
            'tables': {},
            'summary': {
                'total_tables': len(tables),
                'passed_tables': 0,
                'failed_tables': 0,
                'warnings': []
            }
        }
        
        try:
            for table_name in tables:
                logger.info(f"验证表: {table_name}")
                
                table_result = await self.validate_table(
                    source_session, target_session, table_name
                )
                
                validation_results['tables'][table_name] = table_result
                
                if table_result['status'] == 'passed':
                    validation_results['summary']['passed_tables'] += 1
                else:
                    validation_results['summary']['failed_tables'] += 1
                    validation_results['overall_status'] = 'failed'
                
                if table_result.get('warnings'):
                    validation_results['summary']['warnings'].extend(
                        [f"{table_name}: {w}" for w in table_result['warnings']]
                    )
        
        except Exception as e:
            logger.error(f"验证过程中发生错误: {e}")
            validation_results['overall_status'] = 'error'
            validation_results['error'] = str(e)
        
        finally:
            source_engine.dispose()
            await target_engine.dispose()
        
        return validation_results
    
    async def validate_table(self, source_session, target_session, 
                           table_name: str) -> Dict[str, Any]:
        """验证单个表的迁移结果"""
        result = {
            'status': 'passed',
            'checks': {},
            'warnings': [],
            'errors': []
        }
        
        try:
            # 1. 验证记录数量
            count_check = await self.validate_record_count(
                source_session, target_session, table_name
            )
            result['checks']['record_count'] = count_check
            
            if not count_check['passed']:
                result['status'] = 'failed'
                result['errors'].append(count_check['message'])
            
            # 2. 验证数据完整性
            integrity_check = await self.validate_data_integrity(
                source_session, target_session, table_name
            )
            result['checks']['data_integrity'] = integrity_check
            
            if not integrity_check['passed']:
                result['status'] = 'failed'
                result['errors'].extend(integrity_check.get('errors', []))
            
            # 3. 验证关键字段
            key_fields_check = await self.validate_key_fields(
                source_session, target_session, table_name
            )
            result['checks']['key_fields'] = key_fields_check
            
            if not key_fields_check['passed']:
                result['warnings'].extend(key_fields_check.get('warnings', []))
            
            # 4. 验证数据类型
            data_types_check = await self.validate_data_types(
                source_session, target_session, table_name
            )
            result['checks']['data_types'] = data_types_check
            
            if not data_types_check['passed']:
                result['warnings'].extend(data_types_check.get('warnings', []))
        
        except Exception as e:
            logger.error(f"验证表 {table_name} 时发生错误: {e}")
            result['status'] = 'error'
            result['errors'].append(str(e))
        
        return result
    
    async def validate_record_count(self, source_session, target_session, 
                                  table_name: str) -> Dict[str, Any]:
        """验证记录数量"""
        try:
            # 获取源数据库记录数
            with source_session() as session:
                source_result = session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                source_count = source_result.scalar()
            
            # 获取目标数据库记录数
            async with target_session() as session:
                target_result = await session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                target_count = target_result.scalar()
            
            passed = source_count == target_count
            message = f"源数据库: {source_count}, 目标数据库: {target_count}"
            
            if not passed:
                message += f" (差异: {abs(source_count - target_count)})"
            
            return {
                'passed': passed,
                'source_count': source_count,
                'target_count': target_count,
                'message': message
            }
        
        except Exception as e:
            return {
                'passed': False,
                'error': str(e),
                'message': f"无法验证记录数量: {e}"
            }
    
    async def validate_data_integrity(self, source_session, target_session, 
                                    table_name: str) -> Dict[str, Any]:
        """验证数据完整性"""
        try:
            # 获取表结构
            columns = await self.get_table_columns(target_session, table_name)
            if not columns:
                return {
                    'passed': False,
                    'errors': [f"无法获取表 {table_name} 的列信息"]
                }
            
            # 随机抽样验证
            sample_size = min(100, await self.get_table_record_count(target_session, table_name))
            
            if sample_size == 0:
                return {
                    'passed': True,
                    'message': "表为空，跳过数据完整性验证"
                }
            
            # 获取样本数据
            source_samples = self.get_sample_data(source_session, table_name, sample_size)
            target_samples = await self.get_sample_data_async(target_session, table_name, sample_size)
            
            # 比较数据
            mismatches = self.compare_sample_data(source_samples, target_samples, columns)
            
            passed = len(mismatches) == 0
            
            result = {
                'passed': passed,
                'sample_size': sample_size,
                'mismatches': len(mismatches)
            }
            
            if not passed:
                result['errors'] = mismatches[:10]  # 只显示前10个错误
                if len(mismatches) > 10:
                    result['errors'].append(f"... 还有 {len(mismatches) - 10} 个不匹配项")
            
            return result
        
        except Exception as e:
            return {
                'passed': False,
                'errors': [f"数据完整性验证失败: {e}"]
            }
    
    async def validate_key_fields(self, source_session, target_session, 
                                table_name: str) -> Dict[str, Any]:
        """验证关键字段"""
        try:
            # 定义关键字段
            key_fields = ['id', 'created_at', 'updated_at']
            
            warnings = []
            
            # 检查主键字段
            if 'id' in key_fields:
                null_count = await self.count_null_values(target_session, table_name, 'id')
                if null_count > 0:
                    warnings.append(f"主键字段 'id' 有 {null_count} 个空值")
            
            # 检查时间字段
            for field in ['created_at', 'updated_at']:
                if await self.column_exists(target_session, table_name, field):
                    null_count = await self.count_null_values(target_session, table_name, field)
                    if null_count > 0:
                        warnings.append(f"时间字段 '{field}' 有 {null_count} 个空值")
            
            return {
                'passed': len(warnings) == 0,
                'warnings': warnings
            }
        
        except Exception as e:
            return {
                'passed': False,
                'warnings': [f"关键字段验证失败: {e}"]
            }
    
    async def validate_data_types(self, source_session, target_session, 
                                table_name: str) -> Dict[str, Any]:
        """验证数据类型"""
        try:
            warnings = []
            
            # 获取列信息
            columns = await self.get_table_columns(target_session, table_name)
            
            for column in columns:
                column_name = column['column_name']
                data_type = column['data_type']
                
                # 检查JSON字段
                if data_type.lower() in ['json', 'jsonb']:
                    invalid_json_count = await self.count_invalid_json(
                        target_session, table_name, column_name
                    )
                    if invalid_json_count > 0:
                        warnings.append(
                            f"JSON字段 '{column_name}' 有 {invalid_json_count} 个无效值"
                        )
            
            return {
                'passed': len(warnings) == 0,
                'warnings': warnings
            }
        
        except Exception as e:
            return {
                'passed': False,
                'warnings': [f"数据类型验证失败: {e}"]
            }
    
    async def get_table_columns(self, target_session, table_name: str) -> List[Dict[str, Any]]:
        """获取表的列信息"""
        async with target_session() as session:
            query = text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = :table_name
                ORDER BY ordinal_position
            """)
            result = await session.execute(query, {'table_name': table_name})
            return [dict(row) for row in result]
    
    async def get_table_record_count(self, target_session, table_name: str) -> int:
        """获取表记录数"""
        async with target_session() as session:
            result = await session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            return result.scalar()
    
    def get_sample_data(self, source_session, table_name: str, sample_size: int) -> List[Dict[str, Any]]:
        """获取源数据库样本数据"""
        with source_session() as session:
            query = text(f"SELECT * FROM {table_name} ORDER BY RANDOM() LIMIT :limit")
            result = session.execute(query, {'limit': sample_size})
            columns = result.keys()
            return [dict(zip(columns, row)) for row in result]
    
    async def get_sample_data_async(self, target_session, table_name: str, sample_size: int) -> List[Dict[str, Any]]:
        """获取目标数据库样本数据"""
        async with target_session() as session:
            query = text(f"SELECT * FROM {table_name} ORDER BY RANDOM() LIMIT :limit")
            result = await session.execute(query, {'limit': sample_size})
            columns = result.keys()
            return [dict(zip(columns, row)) for row in result]
    
    def compare_sample_data(self, source_data: List[Dict[str, Any]], 
                          target_data: List[Dict[str, Any]], 
                          columns: List[Dict[str, Any]]) -> List[str]:
        """比较样本数据"""
        mismatches = []
        
        # 创建索引以便快速查找
        target_index = {self.create_record_hash(record): record for record in target_data}
        
        for source_record in source_data:
            source_hash = self.create_record_hash(source_record)
            
            if source_hash not in target_index:
                mismatches.append(f"源记录未在目标数据库中找到: {source_record.get('id', 'unknown')}")
            else:
                # 详细比较字段
                target_record = target_index[source_hash]
                field_mismatches = self.compare_records(source_record, target_record)
                mismatches.extend(field_mismatches)
        
        return mismatches
    
    def create_record_hash(self, record: Dict[str, Any]) -> str:
        """创建记录的哈希值"""
        # 排序键以确保一致性
        sorted_items = sorted(record.items())
        record_str = json.dumps(sorted_items, default=str, sort_keys=True)
        return hashlib.md5(record_str.encode()).hexdigest()
    
    def compare_records(self, source_record: Dict[str, Any], 
                       target_record: Dict[str, Any]) -> List[str]:
        """比较两条记录"""
        mismatches = []
        
        for key, source_value in source_record.items():
            if key not in target_record:
                mismatches.append(f"字段 '{key}' 在目标记录中缺失")
                continue
            
            target_value = target_record[key]
            
            # 处理不同类型的比较
            if not self.values_equal(source_value, target_value):
                mismatches.append(
                    f"字段 '{key}' 值不匹配: 源='{source_value}', 目标='{target_value}'"
                )
        
        return mismatches
    
    def values_equal(self, value1: Any, value2: Any) -> bool:
        """比较两个值是否相等"""
        # 处理None值
        if value1 is None and value2 is None:
            return True
        if value1 is None or value2 is None:
            return False
        
        # 处理JSON字段
        if isinstance(value1, (dict, list)) or isinstance(value2, (dict, list)):
            try:
                return json.dumps(value1, sort_keys=True) == json.dumps(value2, sort_keys=True)
            except:
                return str(value1) == str(value2)
        
        # 处理字符串比较
        if isinstance(value1, str) and isinstance(value2, str):
            return value1.strip() == value2.strip()
        
        # 默认比较
        return value1 == value2
    
    async def count_null_values(self, target_session, table_name: str, column_name: str) -> int:
        """统计空值数量"""
        async with target_session() as session:
            query = text(f"SELECT COUNT(*) FROM {table_name} WHERE {column_name} IS NULL")
            result = await session.execute(query)
            return result.scalar()
    
    async def column_exists(self, target_session, table_name: str, column_name: str) -> bool:
        """检查列是否存在"""
        async with target_session() as session:
            query = text("""
                SELECT COUNT(*) FROM information_schema.columns
                WHERE table_name = :table_name AND column_name = :column_name
            """)
            result = await session.execute(query, {
                'table_name': table_name,
                'column_name': column_name
            })
            return result.scalar() > 0
    
    async def count_invalid_json(self, target_session, table_name: str, column_name: str) -> int:
        """统计无效JSON值数量"""
        try:
            async with target_session() as session:
                # PostgreSQL特定的JSON验证查询
                query = text(f"""
                    SELECT COUNT(*) FROM {table_name}
                    WHERE {column_name} IS NOT NULL
                    AND NOT ({column_name}::text ~ '^\\s*[{{\\[].*[}}\\]]\\s*$')
                """)
                result = await session.execute(query)
                return result.scalar()
        except:
            return 0