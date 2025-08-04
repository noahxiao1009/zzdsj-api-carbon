-- 添加切分策略支持到知识库系统
-- 执行时间：2025-07-30

-- 1. 创建切分策略表
CREATE TABLE IF NOT EXISTS splitter_strategies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    config JSONB NOT NULL,
    is_system BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    created_by VARCHAR(100) DEFAULT 'system',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT unique_strategy_name UNIQUE (name)
);

-- 2. 添加知识库默认切分策略字段
ALTER TABLE knowledge_bases 
ADD COLUMN IF NOT EXISTS default_splitter_strategy_id UUID,
ADD COLUMN IF NOT EXISTS default_splitter_config JSONB;

-- 3. 添加外键约束
ALTER TABLE knowledge_bases 
ADD CONSTRAINT fk_kb_default_splitter 
FOREIGN KEY (default_splitter_strategy_id) 
REFERENCES splitter_strategies(id) 
ON DELETE SET NULL;

-- 4. 扩展任务表以支持详细进度信息
ALTER TABLE processing_tasks 
ADD COLUMN IF NOT EXISTS total_chunks INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS processed_chunks INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS embedding_progress INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS current_stage VARCHAR(50) DEFAULT 'pending',
ADD COLUMN IF NOT EXISTS stage_details JSONB DEFAULT '{}';

-- 5. 创建系统预设切分策略
INSERT INTO splitter_strategies (name, description, config, is_system, is_active) 
VALUES 
(
    'basic_chunking',
    '基础切分策略 - 适用于一般文档',
    '{
        "chunk_size": 1000,
        "chunk_overlap": 200,
        "chunk_strategy": "basic",
        "preserve_structure": true,
        "separators": ["\n\n", "\n", " ", ""],
        "length_function": "len"
    }',
    true,
    true
),
(
    'semantic_chunking', 
    '语义切分策略 - 基于语义边界分割',
    '{
        "chunk_size": 1500,
        "chunk_overlap": 150,
        "chunk_strategy": "semantic",
        "preserve_structure": true,
        "use_semantic_splitter": true,
        "embedding_model": "text-embedding-ada-002",
        "similarity_threshold": 0.7
    }',
    true,
    true
),
(
    'smart_chunking',
    '智能切分策略 - 基于文档结构智能分割',
    '{
        "chunk_size": 2000,
        "chunk_overlap": 100,
        "chunk_strategy": "smart",
        "preserve_structure": true,
        "detect_headers": true,
        "detect_paragraphs": true,
        "detect_lists": true,
        "min_chunk_size": 100,
        "max_chunk_size": 3000
    }',
    true,
    true
),
(
    'code_chunking',
    '代码切分策略 - 专门针对代码文件',
    '{
        "chunk_size": 1500,
        "chunk_overlap": 50,
        "chunk_strategy": "code",
        "preserve_structure": true,
        "detect_functions": true,
        "detect_classes": true,
        "detect_imports": true,
        "language_specific": true
    }',
    true,
    true
),
(
    'large_document',
    '大文档切分策略 - 适用于长文档',
    '{
        "chunk_size": 3000,
        "chunk_overlap": 300,
        "chunk_strategy": "hierarchical",
        "preserve_structure": true,
        "use_hierarchy": true,
        "max_depth": 3,
        "min_section_size": 500
    }',
    true,
    true
);

-- 6. 创建索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_splitter_strategies_active ON splitter_strategies(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_splitter_strategies_system ON splitter_strategies(is_system);
CREATE INDEX IF NOT EXISTS idx_kb_default_splitter ON knowledge_bases(default_splitter_strategy_id);
CREATE INDEX IF NOT EXISTS idx_processing_tasks_stage ON processing_tasks(current_stage);
CREATE INDEX IF NOT EXISTS idx_processing_tasks_progress ON processing_tasks(processed_chunks, total_chunks);

-- 7. 创建更新时间触发器
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_splitter_strategies_updated_at 
    BEFORE UPDATE ON splitter_strategies 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 8. 设置现有知识库的默认策略（如果没有设置）
UPDATE knowledge_bases 
SET default_splitter_strategy_id = (
    SELECT id FROM splitter_strategies 
    WHERE name = 'basic_chunking' AND is_system = true 
    LIMIT 1
)
WHERE default_splitter_strategy_id IS NULL;

-- 9. 添加切分策略使用统计表（可选，用于分析）
CREATE TABLE IF NOT EXISTS splitter_strategy_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id UUID NOT NULL REFERENCES splitter_strategies(id),
    kb_id VARCHAR(36) NOT NULL REFERENCES knowledge_bases(id),
    usage_count INTEGER DEFAULT 1,
    last_used_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT unique_strategy_kb_usage UNIQUE (strategy_id, kb_id)
);

CREATE INDEX IF NOT EXISTS idx_strategy_usage_kb ON splitter_strategy_usage(kb_id);
CREATE INDEX IF NOT EXISTS idx_strategy_usage_strategy ON splitter_strategy_usage(strategy_id);

-- 10. 插入使用统计记录触发器函数
CREATE OR REPLACE FUNCTION record_strategy_usage()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO splitter_strategy_usage (strategy_id, kb_id, usage_count, last_used_at)
    VALUES (
        COALESCE(NEW.splitter_strategy_id, (
            SELECT default_splitter_strategy_id 
            FROM knowledge_bases 
            WHERE id = NEW.kb_id
        )),
        NEW.kb_id,
        1,
        NOW()
    )
    ON CONFLICT (strategy_id, kb_id) 
    DO UPDATE SET 
        usage_count = splitter_strategy_usage.usage_count + 1,
        last_used_at = NOW();
    
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 注意：这个触发器需要在processing_tasks表存在时创建
-- CREATE TRIGGER record_splitter_strategy_usage
--     AFTER INSERT ON processing_tasks
--     FOR EACH ROW EXECUTE FUNCTION record_strategy_usage();

COMMENT ON TABLE splitter_strategies IS '文档切分策略配置表';
COMMENT ON TABLE splitter_strategy_usage IS '切分策略使用统计表';
COMMENT ON COLUMN knowledge_bases.default_splitter_strategy_id IS '知识库默认切分策略ID';
COMMENT ON COLUMN knowledge_bases.default_splitter_config IS '知识库默认切分配置（覆盖策略配置）';
COMMENT ON COLUMN processing_tasks.total_chunks IS '文档总切分块数';
COMMENT ON COLUMN processing_tasks.processed_chunks IS '已处理的切分块数';
COMMENT ON COLUMN processing_tasks.embedding_progress IS '向量化进度百分比';
COMMENT ON COLUMN processing_tasks.current_stage IS '当前处理阶段';
COMMENT ON COLUMN processing_tasks.stage_details IS '阶段详细信息';