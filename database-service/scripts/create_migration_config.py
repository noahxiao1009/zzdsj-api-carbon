#!/usr/bin/env python3
"""
创建迁移配置文件的辅助脚本
"""
import argparse
import sys
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent.parent))

from app.core.migration.migration_config import MigrationConfig

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="创建迁移配置文件")
    parser.add_argument("--source-db", required=True, help="源数据库URL")
    parser.add_argument("--target-db", required=True, help="目标数据库URL")
    parser.add_argument("--output", "-o", default="migration_config.json", help="输出配置文件路径")
    parser.add_argument("--tables", nargs="+", help="指定要迁移的表")
    parser.add_argument("--batch-size", type=int, default=1000, help="批处理大小")
    parser.add_argument("--validate", action="store_true", help="迁移后验证数据")
    parser.add_argument("--backup", action="store_true", help="创建备份")
    
    args = parser.parse_args()
    
    # 创建配置
    config = MigrationConfig.create_default_config(args.source_db, args.target_db)
    
    # 更新配置
    if args.tables:
        config.tables_to_migrate = args.tables
    
    config.batch_size = args.batch_size
    config.validate_after_migration = args.validate
    config.create_backup = args.backup
    
    # 保存配置
    config.to_file(args.output)
    
    print(f"配置文件已创建: {args.output}")
    print(f"源数据库: {args.source_db}")
    print(f"目标数据库: {args.target_db}")
    print(f"迁移表数: {len(config.tables_to_migrate)}")
    print(f"批处理大小: {config.batch_size}")
    
    print("\n请根据实际情况修改配置文件中的数据库连接信息。")

if __name__ == "__main__":
    main()