-- 简化的文件夹检索功能迁移脚本
-- 专注于检索范围控制和文件夹级别搜索

-- 1. 创建简化的知识库文件夹表
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
    
    -- 状态
    status VARCHAR(20) DEFAULT 'active',
    
    -- 时间戳
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

-- 3. 创建文件夹检索配置表
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

-- 4. 创建必要的索引

-- 知识库文件夹索引
CREATE INDEX IF NOT EXISTS idx_folder_kb_status ON knowledge_folders(kb_id, status);
CREATE INDEX IF NOT EXISTS idx_folder_search_enabled ON knowledge_folders(kb_id, enable_search);
CREATE INDEX IF NOT EXISTS idx_folder_path ON knowledge_folders(full_path);
CREATE INDEX IF NOT EXISTS idx_folder_level ON knowledge_folders(level);

-- 文档表新增索引
CREATE INDEX IF NOT EXISTS idx_doc_folder ON documents(folder_id);
CREATE INDEX IF NOT EXISTS idx_doc_kb_folder ON documents(kb_id, folder_id);

-- 检索配置索引
CREATE INDEX IF NOT EXISTS idx_search_config_kb ON folder_search_configs(kb_id);
CREATE INDEX IF NOT EXISTS idx_search_config_folder ON folder_search_configs(folder_id);

-- 5. 创建更新时间戳的触发器
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

CREATE TRIGGER update_folder_search_configs_updated_at 
    BEFORE UPDATE ON folder_search_configs 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 6. 创建统计信息更新的函数
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

-- 7. 创建触发器自动更新文件夹统计
CREATE OR REPLACE FUNCTION trigger_update_folder_stats()
RETURNS TRIGGER AS $$
BEGIN
    -- 更新新文件夹的统计
    IF NEW.folder_id IS NOT NULL THEN
        PERFORM update_folder_stats(NEW.folder_id);
    END IF;
    
    -- 如果是移动操作，更新旧文件夹的统计
    IF TG_OP = 'UPDATE' AND OLD.folder_id IS NOT NULL AND OLD.folder_id != NEW.folder_id THEN
        PERFORM update_folder_stats(OLD.folder_id);
    END IF;
    
    -- 如果是删除操作，更新原文件夹的统计
    IF TG_OP = 'DELETE' AND OLD.folder_id IS NOT NULL THEN
        PERFORM update_folder_stats(OLD.folder_id);
    END IF;
    
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- 为documents表创建统计更新触发器
CREATE TRIGGER update_folder_stats_on_document_change
    AFTER INSERT OR UPDATE OR DELETE ON documents
    FOR EACH ROW 
    WHEN (NEW.status = 'completed' OR OLD.status = 'completed')
    EXECUTE FUNCTION trigger_update_folder_stats();

-- 8. 插入一些示例数据（可选）
-- 注意：需要根据实际的知识库ID进行调整

/*
-- 示例：为现有知识库创建默认文件夹结构
INSERT INTO knowledge_folders (id, kb_id, name, description, level, full_path, search_scope, search_weight)
VALUES 
    ('tech-docs-folder', 'your-kb-id-here', '技术文档', '技术相关文档分类', 0, '/技术文档', 'include_subfolders', 8),
    ('user-docs-folder', 'your-kb-id-here', '用户文档', '用户手册和指南', 0, '/用户文档', 'folder_only', 6),
    ('api-docs-subfolder', 'your-kb-id-here', 'API文档', 'API接口文档', 1, '/技术文档/API文档', 'folder_only', 9);

-- 为文件夹设置检索配置
INSERT INTO folder_search_configs (id, folder_id, kb_id, similarity_threshold, max_results, enable_semantic_search)
VALUES 
    ('config-tech-docs', 'tech-docs-folder', 'your-kb-id-here', 75, 15, TRUE),
    ('config-user-docs', 'user-docs-folder', 'your-kb-id-here', 80, 12, TRUE),
    ('config-api-docs', 'api-docs-subfolder', 'your-kb-id-here', 85, 20, TRUE);
*/

-- 迁移完成验证
SELECT 'Simple folder search migration completed successfully' as status;
SELECT COUNT(*) as folder_count FROM knowledge_folders;
SELECT COUNT(*) as config_count FROM folder_search_configs;