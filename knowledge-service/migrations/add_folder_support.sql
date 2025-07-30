-- 知识库文件夹支持迁移脚本
-- 添加文件夹管理功能的数据库表

-- 1. 创建知识库文件夹表
CREATE TABLE IF NOT EXISTS knowledge_folders (
    id VARCHAR(255) PRIMARY KEY,
    kb_id VARCHAR(255) NOT NULL,
    parent_id VARCHAR(255),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    folder_type VARCHAR(50) DEFAULT 'user_created',
    level INTEGER DEFAULT 0,
    full_path VARCHAR(1000),
    sort_order INTEGER DEFAULT 0,
    enable_scoped_search BOOLEAN DEFAULT TRUE,
    search_priority INTEGER DEFAULT 0,
    enable_semantic_grouping BOOLEAN DEFAULT TRUE,
    auto_classify_rules JSONB DEFAULT '{}',
    classification_keywords TEXT[],
    document_count INTEGER DEFAULT 0,
    total_document_count INTEGER DEFAULT 0,
    total_size INTEGER DEFAULT 0,
    chunk_count INTEGER DEFAULT 0,
    is_public BOOLEAN DEFAULT TRUE,
    access_permissions JSONB DEFAULT '{}',
    status VARCHAR(20) DEFAULT 'active',
    is_system_folder BOOLEAN DEFAULT FALSE,
    folder_metadata JSONB DEFAULT '{}',
    tags TEXT[],
    color VARCHAR(20) DEFAULT '#1890ff',
    icon VARCHAR(50) DEFAULT 'folder',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 外键约束
    FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES knowledge_folders(id) ON DELETE CASCADE
);

-- 2. 为documents表添加folder_id字段
ALTER TABLE documents ADD COLUMN IF NOT EXISTS folder_id VARCHAR(255);
ALTER TABLE documents ADD CONSTRAINT fk_documents_folder 
    FOREIGN KEY (folder_id) REFERENCES knowledge_folders(id) ON DELETE SET NULL;

-- 3. 创建文件夹-文档映射表（支持软链接）
CREATE TABLE IF NOT EXISTS folder_document_mappings (
    id VARCHAR(255) PRIMARY KEY,
    folder_id VARCHAR(255) NOT NULL,
    doc_id VARCHAR(255) NOT NULL,
    mapping_type VARCHAR(50) DEFAULT 'primary',
    relevance_score INTEGER DEFAULT 100,
    display_priority INTEGER DEFAULT 0,
    auto_classified BOOLEAN DEFAULT FALSE,
    classification_confidence INTEGER DEFAULT 0,
    classification_reason TEXT,
    mapping_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 外键约束
    FOREIGN KEY (folder_id) REFERENCES knowledge_folders(id) ON DELETE CASCADE,
    FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE,
    
    -- 唯一约束
    UNIQUE(folder_id, doc_id, mapping_type)
);

-- 4. 创建文件夹搜索索引表
CREATE TABLE IF NOT EXISTS folder_search_indexes (
    id VARCHAR(255) PRIMARY KEY,
    folder_id VARCHAR(255) NOT NULL,
    kb_id VARCHAR(255) NOT NULL,
    searchable_content TEXT,
    keywords TEXT[],
    semantic_tags TEXT[],
    total_documents INTEGER DEFAULT 0,
    total_chunks INTEGER DEFAULT 0,
    avg_relevance_score INTEGER DEFAULT 0,
    boost_factor INTEGER DEFAULT 1,
    enable_fuzzy_search BOOLEAN DEFAULT TRUE,
    last_indexed_at TIMESTAMP WITH TIME ZONE,
    index_version VARCHAR(50) DEFAULT '1.0',
    needs_reindex BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 外键约束
    FOREIGN KEY (folder_id) REFERENCES knowledge_folders(id) ON DELETE CASCADE,
    FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE
);

-- 5. 创建文件夹访问日志表
CREATE TABLE IF NOT EXISTS folder_access_logs (
    id VARCHAR(255) PRIMARY KEY,
    folder_id VARCHAR(255) NOT NULL,
    kb_id VARCHAR(255) NOT NULL,
    access_type VARCHAR(50) NOT NULL,
    user_id VARCHAR(255),
    session_id VARCHAR(255),
    search_query TEXT,
    search_results_count INTEGER DEFAULT 0,
    search_duration INTEGER DEFAULT 0,
    access_duration INTEGER DEFAULT 0,
    documents_accessed INTEGER DEFAULT 0,
    access_metadata JSONB DEFAULT '{}',
    user_agent VARCHAR(500),
    ip_address VARCHAR(50),
    access_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 外键约束
    FOREIGN KEY (folder_id) REFERENCES knowledge_folders(id) ON DELETE CASCADE,
    FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE
);

-- 6. 创建索引以优化查询性能

-- 知识库文件夹索引
CREATE INDEX IF NOT EXISTS idx_folder_kb_parent ON knowledge_folders(kb_id, parent_id);
CREATE INDEX IF NOT EXISTS idx_folder_path ON knowledge_folders(full_path);
CREATE INDEX IF NOT EXISTS idx_folder_level_order ON knowledge_folders(level, sort_order);
CREATE INDEX IF NOT EXISTS idx_folder_status ON knowledge_folders(status);
CREATE INDEX IF NOT EXISTS idx_folder_created_at ON knowledge_folders(created_at);
CREATE INDEX IF NOT EXISTS idx_folder_search_priority ON knowledge_folders(enable_scoped_search, search_priority);

-- 文档表新增索引
CREATE INDEX IF NOT EXISTS idx_doc_folder ON documents(folder_id);
CREATE INDEX IF NOT EXISTS idx_doc_kb_folder ON documents(kb_id, folder_id);

-- 文件夹文档映射索引
CREATE INDEX IF NOT EXISTS idx_folder_doc_mapping ON folder_document_mappings(folder_id, doc_id);
CREATE INDEX IF NOT EXISTS idx_mapping_type ON folder_document_mappings(mapping_type);
CREATE INDEX IF NOT EXISTS idx_relevance_score ON folder_document_mappings(relevance_score);
CREATE INDEX IF NOT EXISTS idx_auto_classified ON folder_document_mappings(auto_classified);

-- 搜索索引表索引
CREATE INDEX IF NOT EXISTS idx_folder_search_kb ON folder_search_indexes(kb_id, folder_id);
CREATE INDEX IF NOT EXISTS idx_search_needs_reindex ON folder_search_indexes(needs_reindex);
CREATE INDEX IF NOT EXISTS idx_search_boost_factor ON folder_search_indexes(boost_factor);
CREATE INDEX IF NOT EXISTS idx_search_last_indexed ON folder_search_indexes(last_indexed_at);

-- 访问日志索引
CREATE INDEX IF NOT EXISTS idx_access_folder_time ON folder_access_logs(folder_id, access_time);
CREATE INDEX IF NOT EXISTS idx_access_type_time ON folder_access_logs(access_type, access_time);
CREATE INDEX IF NOT EXISTS idx_access_user ON folder_access_logs(user_id, access_time);
CREATE INDEX IF NOT EXISTS idx_access_kb ON folder_access_logs(kb_id, access_time);

-- 7. 创建用于自动更新 updated_at 字段的触发器函数
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 为相关表创建触发器
CREATE TRIGGER update_knowledge_folders_updated_at 
    BEFORE UPDATE ON knowledge_folders 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_folder_document_mappings_updated_at 
    BEFORE UPDATE ON folder_document_mappings 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_folder_search_indexes_updated_at 
    BEFORE UPDATE ON folder_search_indexes 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 8. 插入一些系统默认文件夹（可选）
-- 注意：这里需要根据实际的知识库ID进行调整
/*
INSERT INTO knowledge_folders (id, kb_id, name, description, folder_type, level, full_path, is_system_folder, icon, color)
VALUES 
    ('system-temp-folder', 'your-kb-id-here', '临时文件', '系统临时文件存储', 'system_generated', 0, '/临时文件', TRUE, 'clock-circle', '#faad14'),
    ('system-archive-folder', 'your-kb-id-here', '归档文件', '已归档的历史文档', 'system_generated', 0, '/归档文件', TRUE, 'archive', '#722ed1');
*/

-- 迁移完成后的验证查询
-- SELECT 'Migration completed successfully' as status;
-- SELECT COUNT(*) as folder_count FROM knowledge_folders;
-- SELECT COUNT(*) as mapping_count FROM folder_document_mappings;
-- SELECT COUNT(*) as index_count FROM folder_search_indexes;