"""
迁移配置类
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path
import json

@dataclass
class MigrationConfig:
    """迁移配置"""
    
    # 数据库连接配置
    source_db_url: str
    target_db_url: str
    
    # 迁移选项
    tables_to_migrate: List[str] = field(default_factory=list)
    batch_size: int = 1000
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # 验证选项
    validate_after_migration: bool = True
    validate_data_integrity: bool = True
    
    # 备份选项
    create_backup: bool = True
    backup_path: Optional[str] = None
    
    # 日志选项
    log_level: str = "INFO"
    log_file: Optional[str] = None
    
    # 并发选项
    max_concurrent_tables: int = 1
    max_concurrent_batches: int = 5
    
    # 错误处理
    stop_on_error: bool = False
    skip_existing_records: bool = True
    
    # 数据转换选项
    custom_transformations: Dict[str, Any] = field(default_factory=dict)
    field_mappings: Dict[str, Dict[str, str]] = field(default_factory=dict)
    
    @classmethod
    def from_file(cls, config_path: str) -> 'MigrationConfig':
        """从配置文件加载配置"""
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        return cls(**config_data)
    
    def to_file(self, config_path: str) -> None:
        """保存配置到文件"""
        config_file = Path(config_path)
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 转换为字典
        config_dict = {
            'source_db_url': self.source_db_url,
            'target_db_url': self.target_db_url,
            'tables_to_migrate': self.tables_to_migrate,
            'batch_size': self.batch_size,
            'max_retries': self.max_retries,
            'retry_delay': self.retry_delay,
            'validate_after_migration': self.validate_after_migration,
            'validate_data_integrity': self.validate_data_integrity,
            'create_backup': self.create_backup,
            'backup_path': self.backup_path,
            'log_level': self.log_level,
            'log_file': self.log_file,
            'max_concurrent_tables': self.max_concurrent_tables,
            'max_concurrent_batches': self.max_concurrent_batches,
            'stop_on_error': self.stop_on_error,
            'skip_existing_records': self.skip_existing_records,
            'custom_transformations': self.custom_transformations,
            'field_mappings': self.field_mappings
        }
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)
    
    @classmethod
    def create_default_config(cls, source_db_url: str, target_db_url: str) -> 'MigrationConfig':
        """创建默认配置"""
        return cls(
            source_db_url=source_db_url,
            target_db_url=target_db_url,
            tables_to_migrate=[
                'users', 'roles', 'permissions', 'user_role', 'role_permissions',
                'user_settings', 'api_keys', 'user_sessions',
                'assistants', 'assistant_knowledge_base', 'conversations', 'messages',
                'knowledge_bases', 'documents', 'document_chunks',
                'agent_definitions', 'agent_templates', 'agent_runs',
                'tools', 'tool_configurations', 'tool_executions',
                'system_configs', 'model_providers'
            ],
            batch_size=1000,
            validate_after_migration=True,
            create_backup=True,
            log_level="INFO"
        )
    
    def validate(self) -> List[str]:
        """验证配置"""
        errors = []
        
        if not self.source_db_url:
            errors.append("源数据库URL不能为空")
        
        if not self.target_db_url:
            errors.append("目标数据库URL不能为空")
        
        if self.batch_size <= 0:
            errors.append("批处理大小必须大于0")
        
        if self.max_retries < 0:
            errors.append("最大重试次数不能小于0")
        
        if self.retry_delay < 0:
            errors.append("重试延迟不能小于0")
        
        if self.max_concurrent_tables <= 0:
            errors.append("最大并发表数必须大于0")
        
        if self.max_concurrent_batches <= 0:
            errors.append("最大并发批次数必须大于0")
        
        return errors