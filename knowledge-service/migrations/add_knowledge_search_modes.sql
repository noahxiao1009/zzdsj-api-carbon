-- 知识库检索模式支持迁移脚本
-- 为智能体绑定知识库时提供检索模式配置

-- 1. 为knowledge_bases表添加检索模式相关字段
ALTER TABLE knowledge_bases ADD COLUMN IF NOT EXISTS default_search_mode VARCHAR(50) DEFAULT 'full_kb';
ALTER TABLE knowledge_bases ADD COLUMN IF NOT EXISTS search_mode_config JSONB DEFAULT '{}';
ALTER TABLE knowledge_bases ADD COLUMN IF NOT EXISTS folder_search_enabled BOOLEAN DEFAULT FALSE;

-- 2. 创建知识库检索模式配置表
CREATE TABLE IF NOT EXISTS kb_search_mode_configs (
    id VARCHAR(255) PRIMARY KEY,
    kb_id VARCHAR(255) NOT NULL,
    
    -- 检索模式类型
    search_mode VARCHAR(50) NOT NULL, -- full_kb, custom_folders, exclude_folders
    mode_name VARCHAR(255) NOT NULL, -- 模式名称，如"技术文档检索"、"全库检索"
    description TEXT, -- 模式描述
    
    -- 文件夹配置
    included_folders TEXT[], -- 包含的文件夹ID列表
    excluded_folders TEXT[], -- 排除的文件夹ID列表
    
    -- 检索参数
    search_config JSONB DEFAULT '{}', -- 检索参数配置
    
    -- 权重和优先级
    priority INTEGER DEFAULT 0, -- 模式优先级
    is_default BOOLEAN DEFAULT FALSE, -- 是否为默认模式
    is_active BOOLEAN DEFAULT TRUE, -- 是否激活
    
    -- 创建者和使用统计
    created_by VARCHAR(255), -- 创建者（可用于区分系统预设和用户自定义）
    usage_count INTEGER DEFAULT 0, -- 使用次数
    last_used_at TIMESTAMP WITH TIME ZONE,
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 外键约束
    FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    
    -- 唯一约束
    UNIQUE(kb_id, mode_name)
);

-- 3. 创建简化的知识库文件夹表
CREATE TABLE IF NOT EXISTS knowledge_folders (
    id VARCHAR(255) PRIMARY KEY,
    kb_id VARCHAR(255) NOT NULL,
    parent_id VARCHAR(255),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    level INTEGER DEFAULT 0,
    full_path VARCHAR(1000),
    
    -- 检索配置 (核心功能)
    enable_search BOOLEAN DEFAULT TRUE,
    search_scope VARCHAR(50) DEFAULT 'folder_only', -- folder_only, include_subfolders
    search_weight INTEGER DEFAULT 1, -- 1-10
    
    -- 统计信息
    document_count INTEGER DEFAULT 0,
    total_size INTEGER DEFAULT 0,
    
    -- 状态和标签
    status VARCHAR(20) DEFAULT 'active',
    folder_type VARCHAR(50) DEFAULT 'user_created', -- user_created, system_generated
    tags TEXT[] DEFAULT '{}',
    color VARCHAR(20) DEFAULT '#1890ff',
    icon VARCHAR(50) DEFAULT 'folder',
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 外键约束
    FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES knowledge_folders(id) ON DELETE CASCADE
);

-- 4. 为documents表添加folder_id字段（如果不存在）
ALTER TABLE documents ADD COLUMN IF NOT EXISTS folder_id VARCHAR(255);
ALTER TABLE documents ADD CONSTRAINT IF NOT EXISTS fk_documents_folder 
    FOREIGN KEY (folder_id) REFERENCES knowledge_folders(id) ON DELETE SET NULL;

-- 5. 创建文件夹检索配置表
CREATE TABLE IF NOT EXISTS folder_search_configs (
    id VARCHAR(255) PRIMARY KEY,
    folder_id VARCHAR(255) NOT NULL UNIQUE,
    kb_id VARCHAR(255) NOT NULL,
    
    -- 检索参数配置
    similarity_threshold INTEGER DEFAULT 70, -- 0-100
    max_results INTEGER DEFAULT 10,
    enable_semantic_search BOOLEAN DEFAULT TRUE,
    enable_keyword_search BOOLEAN DEFAULT TRUE,
    
    -- 结果排序配置
    sort_by VARCHAR(50) DEFAULT 'relevance', -- relevance, date, size, filename
    sort_order VARCHAR(10) DEFAULT 'desc', -- asc, desc
    
    -- 文件类型过滤
    allowed_file_types TEXT[], -- 允许的文件类型
    
    -- 高级配置
    boost_recent_documents BOOLEAN DEFAULT FALSE,
    boost_factor INTEGER DEFAULT 1, -- 1-5
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 外键约束
    FOREIGN KEY (folder_id) REFERENCES knowledge_folders(id) ON DELETE CASCADE,
    FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE
);

-- 6. 创建知识库检索使用日志表
CREATE TABLE IF NOT EXISTS kb_search_usage_logs (
    id VARCHAR(255) PRIMARY KEY,
    kb_id VARCHAR(255) NOT NULL,
    search_mode_id VARCHAR(255), -- 使用的检索模式ID
    
    -- 检索信息
    search_query TEXT NOT NULL,
    search_type VARCHAR(50), -- keyword, semantic, hybrid
    search_scope VARCHAR(100), -- 实际检索范围描述
    
    -- 结果信息
    results_count INTEGER DEFAULT 0,
    search_duration INTEGER DEFAULT 0, -- 搜索耗时（毫秒）
    
    -- 用户信息
    user_id VARCHAR(255),
    agent_id VARCHAR(255), -- 如果是智能体调用
    session_id VARCHAR(255),
    
    -- 元数据
    search_metadata JSONB DEFAULT '{}',
    
    -- 时间戳
    search_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 外键约束
    FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    FOREIGN KEY (search_mode_id) REFERENCES kb_search_mode_configs(id) ON DELETE SET NULL
);

-- 7. 创建索引

-- 知识库检索模式配置索引
CREATE INDEX IF NOT EXISTS idx_search_mode_kb ON kb_search_mode_configs(kb_id);
CREATE INDEX IF NOT EXISTS idx_search_mode_active ON kb_search_mode_configs(kb_id, is_active);
CREATE INDEX IF NOT EXISTS idx_search_mode_default ON kb_search_mode_configs(kb_id, is_default);
CREATE INDEX IF NOT EXISTS idx_search_mode_type ON kb_search_mode_configs(search_mode);

-- 知识库文件夹索引
CREATE INDEX IF NOT EXISTS idx_folder_kb_status ON knowledge_folders(kb_id, status);
CREATE INDEX IF NOT EXISTS idx_folder_search_enabled ON knowledge_folders(kb_id, enable_search);
CREATE INDEX IF NOT EXISTS idx_folder_path ON knowledge_folders(full_path);
CREATE INDEX IF NOT EXISTS idx_folder_level ON knowledge_folders(level);
CREATE INDEX IF NOT EXISTS idx_folder_parent ON knowledge_folders(parent_id);

-- 文档表索引
CREATE INDEX IF NOT EXISTS idx_doc_folder ON documents(folder_id);
CREATE INDEX IF NOT EXISTS idx_doc_kb_folder ON documents(kb_id, folder_id);
CREATE INDEX IF NOT EXISTS idx_doc_kb_status ON documents(kb_id, status);

-- 检索配置索引
CREATE INDEX IF NOT EXISTS idx_search_config_kb ON folder_search_configs(kb_id);
CREATE INDEX IF NOT EXISTS idx_search_config_folder ON folder_search_configs(folder_id);

-- 使用日志索引
CREATE INDEX IF NOT EXISTS idx_usage_kb_time ON kb_search_usage_logs(kb_id, search_time);
CREATE INDEX IF NOT EXISTS idx_usage_mode_time ON kb_search_usage_logs(search_mode_id, search_time);
CREATE INDEX IF NOT EXISTS idx_usage_agent ON kb_search_usage_logs(agent_id, search_time);

-- 8. 创建更新时间戳的触发器
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 为相关表创建触发器
CREATE TRIGGER IF NOT EXISTS update_kb_search_mode_configs_updated_at 
    BEFORE UPDATE ON kb_search_mode_configs 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER IF NOT EXISTS update_knowledge_folders_updated_at 
    BEFORE UPDATE ON knowledge_folders 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER IF NOT EXISTS update_folder_search_configs_updated_at 
    BEFORE UPDATE ON folder_search_configs 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 9. 创建统计信息更新函数
CREATE OR REPLACE FUNCTION update_folder_stats(folder_id_param VARCHAR(255))
RETURNS VOID AS $$
BEGIN
    UPDATE knowledge_folders 
    SET 
        document_count = (
            SELECT COUNT(*) 
            FROM documents 
            WHERE folder_id = folder_id_param AND status = 'completed'
        ),
        total_size = (
            SELECT COALESCE(SUM(file_size), 0) 
            FROM documents 
            WHERE folder_id = folder_id_param AND status = 'completed'
        )
    WHERE id = folder_id_param;
END;
$$ LANGUAGE plpgsql;

-- 10. 创建检索模式使用计数更新函数
CREATE OR REPLACE FUNCTION update_search_mode_usage(mode_id_param VARCHAR(255))
RETURNS VOID AS $$
BEGIN
    UPDATE kb_search_mode_configs 
    SET 
        usage_count = usage_count + 1,
        last_used_at = NOW()
    WHERE id = mode_id_param;
END;
$$ LANGUAGE plpgsql;

-- 11. 插入系统预设的检索模式模板
INSERT INTO kb_search_mode_configs (id, kb_id, search_mode, mode_name, description, is_default, created_by, search_config)
SELECT 
    CONCAT('full_kb_', kb.id),
    kb.id,
    'full_kb',
    '全库检索',
    '在整个知识库中进行检索，包含所有文档和文件夹',
    TRUE,
    'system',
    '{"similarity_threshold": 70, "max_results": 20, "enable_semantic_search": true, "enable_keyword_search": true}'::jsonb
FROM knowledge_bases kb
WHERE NOT EXISTS (
    SELECT 1 FROM kb_search_mode_configs 
    WHERE kb_id = kb.id AND search_mode = 'full_kb'
);

-- 12. 更新knowledge_bases表的检索模式配置
UPDATE knowledge_bases 
SET 
    default_search_mode = 'full_kb',
    folder_search_enabled = TRUE,
    search_mode_config = '{"default_mode": "full_kb", "allow_custom_modes": true}'::jsonb
WHERE default_search_mode IS NULL;

-- 13. 创建一些示例文件夹结构（可选，需要根据实际情况调整）
/*
-- 示例：为知识库创建基础文件夹结构
INSERT INTO knowledge_folders (id, kb_id, name, description, level, full_path, search_scope, search_weight, folder_type)
SELECT 
    CONCAT('tech_docs_', kb.id),
    kb.id,
    '技术文档',
    '技术相关文档分类',
    0,
    '/技术文档',
    'include_subfolders',
    8,
    'system_generated'
FROM knowledge_bases kb
WHERE NOT EXISTS (
    SELECT 1 FROM knowledge_folders 
    WHERE kb_id = kb.id AND name = '技术文档'
);

INSERT INTO knowledge_folders (id, kb_id, name, description, level, full_path, search_scope, search_weight, folder_type)
SELECT 
    CONCAT('user_docs_', kb.id),
    kb.id,
    '用户文档',
    '用户手册和操作指南',
    0,
    '/用户文档',
    'folder_only',
    6,
    'system_generated'
FROM knowledge_bases kb
WHERE NOT EXISTS (
    SELECT 1 FROM knowledge_folders 
    WHERE kb_id = kb.id AND name = '用户文档'
);
*/

-- 迁移完成验证
SELECT 'Knowledge base search modes migration completed successfully' as status;
SELECT COUNT(*) as kb_count FROM knowledge_bases;
SELECT COUNT(*) as search_mode_count FROM kb_search_mode_configs;
SELECT COUNT(*) as folder_count FROM knowledge_folders;