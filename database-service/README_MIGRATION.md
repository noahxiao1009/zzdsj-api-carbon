# 数据迁移工具使用指南

## 概述

本工具用于将原始项目的数据迁移到新的微服务架构中。支持批量迁移、数据验证、错误处理和回滚功能。

## 功能特性

- **批量数据迁移**: 支持大量数据的高效迁移
- **数据验证**: 迁移后自动验证数据完整性
- **错误处理**: 详细的错误日志和恢复机制
- **配置灵活**: 支持自定义迁移规则和字段映射
- **试运行模式**: 在实际迁移前进行安全检查
- **增量迁移**: 支持跳过已存在的记录

## 快速开始

### 1. 准备配置文件

使用辅助脚本创建配置文件：

```bash
python scripts/create_migration_config.py \
  --source-db "postgresql://user:pass@localhost:5432/old_db" \
  --target-db "postgresql://user:pass@localhost:5432/new_db" \
  --output migration_config.json \
  --validate \
  --backup
```

或者手动编辑 `scripts/migration_config.json` 文件：

```json
{
  "source_db_url": "postgresql://username:password@localhost:5432/source_database",
  "target_db_url": "postgresql://username:password@localhost:5432/target_database",
  "tables_to_migrate": ["users", "assistants", "conversations"],
  "batch_size": 1000,
  "validate_after_migration": true
}
```

### 2. 试运行检查

在实际迁移前，建议先进行试运行：

```bash
python scripts/migrate_data.py --config migration_config.json --dry-run
```

### 3. 执行迁移

```bash
python scripts/migrate_data.py --config migration_config.json --output migration_report.json
```

### 4. 验证结果

如果需要单独验证已迁移的数据：

```bash
python scripts/migrate_data.py --config migration_config.json --validate-only
```

## 详细使用说明

### 命令行参数

```bash
python scripts/migrate_data.py [选项]
```

**必需参数:**
- `--config, -c`: 配置文件路径

**可选参数:**
- `--dry-run`: 试运行模式，不实际执行迁移
- `--validate-only`: 仅验证现有迁移结果
- `--tables`: 指定要迁移的表（覆盖配置文件）
- `--output, -o`: 输出报告文件路径
- `--verbose, -v`: 详细输出

### 配置文件详解

#### 基本配置

```json
{
  "source_db_url": "源数据库连接URL",
  "target_db_url": "目标数据库连接URL",
  "tables_to_migrate": ["要迁移的表列表"]
}
```

#### 性能配置

```json
{
  "batch_size": 1000,                    // 批处理大小
  "max_concurrent_tables": 1,            // 最大并发表数
  "max_concurrent_batches": 5,           // 最大并发批次数
  "max_retries": 3,                      // 最大重试次数
  "retry_delay": 1.0                     // 重试延迟（秒）
}
```

#### 验证配置

```json
{
  "validate_after_migration": true,      // 迁移后验证
  "validate_data_integrity": true        // 验证数据完整性
}
```

#### 错误处理

```json
{
  "stop_on_error": false,                // 遇到错误是否停止
  "skip_existing_records": true          // 跳过已存在的记录
}
```

#### 自定义转换

```json
{
  "custom_transformations": {
    "users": {
      "password_field_mapping": {
        "source": "password",
        "target": "password_hash"
      }
    }
  },
  "field_mappings": {
    "users": {
      "password": "password_hash"
    }
  }
}
```

## 支持的表

工具支持以下表的迁移：

### 用户相关
- `users` - 用户信息
- `roles` - 角色定义
- `permissions` - 权限定义
- `user_role` - 用户角色关联
- `role_permissions` - 角色权限关联
- `user_settings` - 用户设置
- `api_keys` - API密钥
- `user_sessions` - 用户会话

### 助手相关
- `assistants` - 助手定义
- `assistant_knowledge_base` - 助手知识库关联
- `conversations` - 对话记录
- `messages` - 消息记录

### 知识库相关
- `knowledge_bases` - 知识库
- `documents` - 文档
- `document_chunks` - 文档分块

### 智能体相关
- `agent_definitions` - 智能体定义
- `agent_templates` - 智能体模板
- `agent_runs` - 智能体运行记录

### 工具相关
- `tools` - 工具定义
- `tool_configurations` - 工具配置
- `tool_executions` - 工具执行记录

### 系统相关
- `system_configs` - 系统配置
- `model_providers` - 模型提供商
- `framework_configs` - 框架配置
- `service_registry` - 服务注册
- `resource_permissions` - 资源权限

## 数据转换规则

### 自动转换

工具会自动处理以下转换：

1. **时间字段**: 自动转换时间格式
2. **JSON字段**: 自动解析JSON字符串
3. **UUID字段**: 自动生成缺失的UUID
4. **默认值**: 为必需字段设置默认值

### 表特定转换

#### 用户表 (users)
- `password` → `password_hash`: 密码字段重命名
- 自动设置 `is_active=true`, `is_verified=false`
- 自动生成缺失的 `id` 字段

#### 助手表 (assistants)
- 自动解析 `config` 和 `model_config` JSON字段

#### 知识库表 (knowledge_bases)
- 自动解析 `settings` JSON字段

#### 文档表 (documents)
- 自动解析 `metadata` JSON字段

#### 消息表 (messages)
- 自动解析 `content` 和 `metadata` JSON字段

## 验证功能

### 验证项目

1. **记录数量验证**: 比较源数据库和目标数据库的记录数量
2. **数据完整性验证**: 随机抽样比较数据内容
3. **关键字段验证**: 检查主键、时间字段等关键字段
4. **数据类型验证**: 验证JSON字段等特殊数据类型

### 验证报告

验证完成后会生成详细报告，包括：

- 总体验证状态
- 各表验证结果
- 错误和警告信息
- 数据统计信息

## 错误处理

### 常见错误

1. **连接错误**: 检查数据库连接配置
2. **表不存在**: 确认表名正确且表已创建
3. **字段不匹配**: 检查字段映射配置
4. **数据类型错误**: 检查数据转换规则
5. **约束违反**: 检查外键约束和唯一约束

### 错误恢复

- 支持自动重试机制
- 详细的错误日志记录
- 支持跳过错误记录继续迁移
- 支持从断点继续迁移

## 性能优化

### 批处理

- 使用批量插入提高性能
- 可配置批处理大小
- 支持并发处理

### 内存管理

- 流式处理大量数据
- 及时释放内存资源
- 避免一次性加载所有数据

### 数据库优化

- 使用事务确保数据一致性
- 合理使用索引
- 优化查询语句

## 监控和日志

### 日志配置

```json
{
  "log_level": "INFO",
  "log_file": "./logs/migration.log"
}
```

### 监控指标

- 迁移进度
- 成功/失败记录数
- 处理速度
- 错误统计

## 最佳实践

### 迁移前准备

1. **备份数据**: 始终在迁移前备份重要数据
2. **测试环境**: 先在测试环境验证迁移脚本
3. **检查依赖**: 确认表之间的依赖关系
4. **资源准备**: 确保足够的磁盘空间和内存

### 迁移过程

1. **分批迁移**: 对于大量数据，建议分批进行
2. **监控进度**: 实时监控迁移进度和系统资源
3. **错误处理**: 及时处理迁移过程中的错误
4. **验证数据**: 每批迁移后验证数据正确性

### 迁移后检查

1. **完整性验证**: 全面验证数据完整性
2. **功能测试**: 测试应用程序功能
3. **性能测试**: 检查系统性能
4. **清理工作**: 清理临时文件和日志

## 故障排除

### 常见问题

**Q: 迁移过程中断怎么办？**
A: 工具支持断点续传，重新运行迁移脚本即可从断点继续。

**Q: 如何处理数据冲突？**
A: 配置 `skip_existing_records: true` 跳过已存在的记录。

**Q: 迁移速度太慢怎么办？**
A: 调整 `batch_size` 和并发参数，优化数据库连接。

**Q: 如何回滚迁移？**
A: 使用备份数据恢复，或者编写反向迁移脚本。

### 联系支持

如果遇到问题，请提供以下信息：

1. 错误日志
2. 配置文件
3. 数据库版本信息
4. 系统环境信息

## 示例

### 完整迁移示例

```bash
# 1. 创建配置文件
python scripts/create_migration_config.py \
  --source-db "postgresql://user:pass@localhost:5432/old_db" \
  --target-db "postgresql://user:pass@localhost:5432/new_db" \
  --output my_migration.json

# 2. 试运行检查
python scripts/migrate_data.py -c my_migration.json --dry-run

# 3. 执行迁移
python scripts/migrate_data.py -c my_migration.json -o migration_report.json

# 4. 验证结果
python scripts/migrate_data.py -c my_migration.json --validate-only
```

### 部分表迁移示例

```bash
# 只迁移用户相关表
python scripts/migrate_data.py \
  -c migration_config.json \
  --tables users roles permissions user_role \
  -o user_migration_report.json
```