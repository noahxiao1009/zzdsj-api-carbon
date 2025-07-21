#!/usr/bin/env python3
"""
数据迁移脚本
用于执行从原始项目到微服务架构的数据迁移
"""
import asyncio
import argparse
import logging
import sys
import os
from pathlib import Path
from datetime import datetime
import json

# 添加项目路径
sys.path.append(str(Path(__file__).parent.parent))

from app.core.migration.data_migrator import DataMigrator
from app.core.migration.migration_config import MigrationConfig
from app.core.migration.migration_validator import MigrationValidator

def setup_logging(log_level: str = "INFO", log_file: str = None):
    """设置日志"""
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    handlers = [logging.StreamHandler(sys.stdout)]
    
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding='utf-8'))
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=log_format,
        handlers=handlers
    )

async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="数据迁移工具")
    parser.add_argument("--config", "-c", required=True, help="配置文件路径")
    parser.add_argument("--dry-run", action="store_true", help="试运行模式，不实际执行迁移")
    parser.add_argument("--validate-only", action="store_true", help="仅验证现有迁移结果")
    parser.add_argument("--tables", nargs="+", help="指定要迁移的表")
    parser.add_argument("--output", "-o", help="输出报告文件路径")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    
    args = parser.parse_args()
    
    try:
        # 加载配置
        if not os.path.exists(args.config):
            print(f"错误: 配置文件不存在: {args.config}")
            return 1
        
        config = MigrationConfig.from_file(args.config)
        
        # 验证配置
        config_errors = config.validate()
        if config_errors:
            print("配置错误:")
            for error in config_errors:
                print(f"  - {error}")
            return 1
        
        # 设置日志
        log_level = "DEBUG" if args.verbose else config.log_level
        setup_logging(log_level, config.log_file)
        
        logger = logging.getLogger(__name__)
        logger.info("开始数据迁移任务...")
        
        # 如果指定了特定表，更新配置
        if args.tables:
            config.tables_to_migrate = args.tables
            logger.info(f"指定迁移表: {args.tables}")
        
        # 仅验证模式
        if args.validate_only:
            logger.info("执行验证模式...")
            validator = MigrationValidator()
            validation_results = await validator.validate_migration(
                config.source_db_url,
                config.target_db_url,
                config.tables_to_migrate
            )
            
            # 输出验证结果
            print_validation_results(validation_results)
            
            # 保存报告
            if args.output:
                save_report(validation_results, args.output)
            
            return 0 if validation_results['overall_status'] == 'success' else 1
        
        # 创建迁移器
        migrator = DataMigrator(
            config.source_db_url,
            config.target_db_url,
            config
        )
        
        try:
            if args.dry_run:
                logger.info("试运行模式 - 不会实际修改数据")
                # 在试运行模式下，我们可以执行一些检查
                await perform_dry_run_checks(migrator, config)
            else:
                # 执行实际迁移
                logger.info("开始执行数据迁移...")
                migration_results = await migrator.migrate_all()
                
                # 生成迁移报告
                report = migrator.generate_migration_report()
                
                # 输出结果
                print_migration_results(migration_results, report)
                
                # 保存报告
                if args.output:
                    save_report(report, args.output)
                
                # 检查是否有错误
                if migration_results['failed_records'] > 0:
                    logger.warning(f"迁移完成，但有 {migration_results['failed_records']} 条记录失败")
                    return 1
                
                logger.info("数据迁移成功完成!")
                return 0
        
        finally:
            await migrator.cleanup()
    
    except Exception as e:
        logger.error(f"迁移过程中发生错误: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

async def perform_dry_run_checks(migrator: DataMigrator, config: MigrationConfig):
    """执行试运行检查"""
    logger = logging.getLogger(__name__)
    
    logger.info("检查源数据库连接...")
    try:
        # 测试源数据库连接
        with migrator.source_session() as session:
            session.execute("SELECT 1")
        logger.info("✓ 源数据库连接正常")
    except Exception as e:
        logger.error(f"✗ 源数据库连接失败: {e}")
        return
    
    logger.info("检查目标数据库连接...")
    try:
        # 测试目标数据库连接
        async with migrator.target_session() as session:
            await session.execute("SELECT 1")
        logger.info("✓ 目标数据库连接正常")
    except Exception as e:
        logger.error(f"✗ 目标数据库连接失败: {e}")
        return
    
    logger.info("检查表结构...")
    for table_name in config.tables_to_migrate:
        try:
            # 检查源表是否存在
            source_count = migrator.get_source_record_count(table_name)
            logger.info(f"✓ 源表 {table_name}: {source_count} 条记录")
            
            # 检查目标表是否存在
            target_count = await migrator.get_target_record_count(table_name)
            logger.info(f"✓ 目标表 {table_name}: {target_count} 条记录")
            
        except Exception as e:
            logger.error(f"✗ 检查表 {table_name} 失败: {e}")

def print_migration_results(migration_results: dict, report: dict):
    """打印迁移结果"""
    print("\n" + "="*60)
    print("数据迁移结果")
    print("="*60)
    
    print(f"总记录数: {migration_results['total_records']}")
    print(f"成功迁移: {migration_results['migrated_records']}")
    print(f"失败记录: {migration_results['failed_records']}")
    print(f"跳过记录: {migration_results['skipped_records']}")
    
    if report.get('duration_seconds'):
        print(f"耗时: {report['duration_seconds']:.2f} 秒")
    
    print(f"成功率: {report['success_rate']:.2f}%")
    
    if migration_results['errors']:
        print("\n错误信息:")
        for error in migration_results['errors'][:10]:  # 只显示前10个错误
            print(f"  - {error}")
        if len(migration_results['errors']) > 10:
            print(f"  ... 还有 {len(migration_results['errors']) - 10} 个错误")

def print_validation_results(validation_results: dict):
    """打印验证结果"""
    print("\n" + "="*60)
    print("数据验证结果")
    print("="*60)
    
    print(f"总体状态: {validation_results['overall_status']}")
    print(f"验证表数: {validation_results['summary']['total_tables']}")
    print(f"通过验证: {validation_results['summary']['passed_tables']}")
    print(f"验证失败: {validation_results['summary']['failed_tables']}")
    
    if validation_results['summary']['warnings']:
        print(f"\n警告信息:")
        for warning in validation_results['summary']['warnings'][:10]:
            print(f"  - {warning}")
    
    # 详细表验证结果
    print(f"\n详细验证结果:")
    for table_name, table_result in validation_results['tables'].items():
        status_symbol = "✓" if table_result['status'] == 'passed' else "✗"
        print(f"  {status_symbol} {table_name}: {table_result['status']}")
        
        if table_result.get('errors'):
            for error in table_result['errors'][:3]:  # 只显示前3个错误
                print(f"    - {error}")

def save_report(report: dict, output_path: str):
    """保存报告到文件"""
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 添加时间戳
    report['generated_at'] = datetime.now().isoformat()
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n报告已保存到: {output_path}")

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)