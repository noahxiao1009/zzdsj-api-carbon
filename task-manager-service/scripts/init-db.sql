-- 任务管理服务数据库初始化脚本

-- 创建数据库 (如果不存在)
-- CREATE DATABASE zzdsj_demo;

-- 切换到目标数据库
\c zzdsj_demo;

-- 创建任务表
CREATE TABLE IF NOT EXISTS tasks (
    id VARCHAR(36) PRIMARY KEY,
    task_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    priority VARCHAR(20) NOT NULL DEFAULT 'normal',
    kb_id VARCHAR(36) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    result JSONB NOT NULL DEFAULT '{}',
    progress INTEGER NOT NULL DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    retry_count INTEGER NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
    max_retries INTEGER NOT NULL DEFAULT 3 CHECK (max_retries >= 0),
    error_message TEXT DEFAULT '',
    worker_id VARCHAR(36) DEFAULT '',
    timeout INTEGER NOT NULL DEFAULT 300 CHECK (timeout > 0),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    scheduled_for TIMESTAMP WITH TIME ZONE,
    
    -- 约束检查
    CONSTRAINT valid_status CHECK (status IN ('queued', 'processing', 'completed', 'failed', 'canceled', 'retrying')),
    CONSTRAINT valid_priority CHECK (priority IN ('low', 'normal', 'high', 'critical')),
    CONSTRAINT valid_task_type CHECK (task_type IN ('document_processing', 'batch_processing', 'knowledge_indexing', 'embedding_generation', 'vector_storage', 'health_check')),
    CONSTRAINT valid_completion_time CHECK (completed_at IS NULL OR completed_at >= started_at),
    CONSTRAINT valid_start_time CHECK (started_at IS NULL OR started_at >= created_at)
);

-- 创建索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_kb_id ON tasks(kb_id);
CREATE INDEX IF NOT EXISTS idx_tasks_task_type ON tasks(task_type);
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_updated_at ON tasks(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_scheduled_for ON tasks(scheduled_for) WHERE scheduled_for IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tasks_worker_id ON tasks(worker_id) WHERE worker_id != '';

-- 复合索引
CREATE INDEX IF NOT EXISTS idx_tasks_status_priority ON tasks(status, priority);
CREATE INDEX IF NOT EXISTS idx_tasks_kb_id_status ON tasks(kb_id, status);
CREATE INDEX IF NOT EXISTS idx_tasks_type_status ON tasks(task_type, status);
CREATE INDEX IF NOT EXISTS idx_tasks_status_created ON tasks(status, created_at DESC);

-- 创建更新时间自动更新触发器
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_tasks_updated_at 
    BEFORE UPDATE ON tasks 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 创建任务历史表 (用于审计)
CREATE TABLE IF NOT EXISTS task_history (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(36) NOT NULL,
    old_status VARCHAR(20),
    new_status VARCHAR(20),
    old_progress INTEGER,
    new_progress INTEGER,
    changed_by VARCHAR(36),
    change_reason TEXT,
    changed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_task_history_task_id ON task_history(task_id);
CREATE INDEX IF NOT EXISTS idx_task_history_changed_at ON task_history(changed_at DESC);

-- 创建状态变更历史触发器
CREATE OR REPLACE FUNCTION log_task_status_change()
RETURNS TRIGGER AS $$
BEGIN
    -- 只在状态或进度发生变化时记录
    IF OLD.status != NEW.status OR OLD.progress != NEW.progress THEN
        INSERT INTO task_history (task_id, old_status, new_status, old_progress, new_progress, changed_by)
        VALUES (NEW.id, OLD.status, NEW.status, OLD.progress, NEW.progress, NEW.worker_id);
    END IF;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER log_task_status_change_trigger
    AFTER UPDATE ON tasks
    FOR EACH ROW EXECUTE FUNCTION log_task_status_change();

-- 创建任务统计视图
CREATE OR REPLACE VIEW task_statistics AS
SELECT 
    COUNT(*) as total_tasks,
    COUNT(*) FILTER (WHERE status = 'queued') as queued_tasks,
    COUNT(*) FILTER (WHERE status = 'processing') as processing_tasks,
    COUNT(*) FILTER (WHERE status = 'completed') as completed_tasks,
    COUNT(*) FILTER (WHERE status = 'failed') as failed_tasks,
    COUNT(*) FILTER (WHERE status = 'canceled') as canceled_tasks,
    COUNT(*) FILTER (WHERE status = 'retrying') as retrying_tasks,
    
    -- 按类型统计
    COUNT(*) FILTER (WHERE task_type = 'document_processing') as document_processing_tasks,
    COUNT(*) FILTER (WHERE task_type = 'batch_processing') as batch_processing_tasks,
    COUNT(*) FILTER (WHERE task_type = 'knowledge_indexing') as knowledge_indexing_tasks,
    COUNT(*) FILTER (WHERE task_type = 'embedding_generation') as embedding_generation_tasks,
    COUNT(*) FILTER (WHERE task_type = 'vector_storage') as vector_storage_tasks,
    COUNT(*) FILTER (WHERE task_type = 'health_check') as health_check_tasks,
    
    -- 按优先级统计
    COUNT(*) FILTER (WHERE priority = 'low') as low_priority_tasks,
    COUNT(*) FILTER (WHERE priority = 'normal') as normal_priority_tasks,
    COUNT(*) FILTER (WHERE priority = 'high') as high_priority_tasks,
    COUNT(*) FILTER (WHERE priority = 'critical') as critical_priority_tasks,
    
    -- 平均处理时间 (秒)
    COALESCE(AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) FILTER (WHERE status = 'completed' AND started_at IS NOT NULL AND completed_at IS NOT NULL), 0) as avg_processing_time_seconds,
    
    -- 成功率
    ROUND(
        (COUNT(*) FILTER (WHERE status = 'completed')::FLOAT / NULLIF(COUNT(*), 0) * 100), 2
    ) as success_rate_percent,
    
    -- 今日任务统计
    COUNT(*) FILTER (WHERE DATE(created_at) = CURRENT_DATE) as today_tasks,
    COUNT(*) FILTER (WHERE DATE(created_at) = CURRENT_DATE AND status = 'completed') as today_completed_tasks
FROM tasks;

-- 创建按知识库ID分组的统计视图
CREATE OR REPLACE VIEW task_statistics_by_kb AS
SELECT 
    kb_id,
    COUNT(*) as total_tasks,
    COUNT(*) FILTER (WHERE status = 'queued') as queued_tasks,
    COUNT(*) FILTER (WHERE status = 'processing') as processing_tasks,
    COUNT(*) FILTER (WHERE status = 'completed') as completed_tasks,
    COUNT(*) FILTER (WHERE status = 'failed') as failed_tasks,
    COALESCE(AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) FILTER (WHERE status = 'completed'), 0) as avg_processing_time_seconds,
    ROUND((COUNT(*) FILTER (WHERE status = 'completed')::FLOAT / NULLIF(COUNT(*), 0) * 100), 2) as success_rate_percent,
    MAX(updated_at) as last_activity
FROM tasks
GROUP BY kb_id;

-- 创建清理过期任务的函数
CREATE OR REPLACE FUNCTION cleanup_old_tasks(days_to_keep INTEGER DEFAULT 30)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    -- 删除超过指定天数的已完成任务
    DELETE FROM tasks 
    WHERE status IN ('completed', 'failed', 'canceled')
    AND created_at < NOW() - INTERVAL '%d days' % days_to_keep;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    -- 记录清理日志
    RAISE NOTICE 'Cleaned up % old tasks', deleted_count;
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- 创建重置卡住任务的函数
CREATE OR REPLACE FUNCTION reset_stuck_tasks(timeout_minutes INTEGER DEFAULT 30)
RETURNS INTEGER AS $$
DECLARE
    reset_count INTEGER;
BEGIN
    -- 重置超时的处理中任务
    UPDATE tasks 
    SET status = 'failed',
        error_message = 'Task timeout - reset by cleanup job',
        completed_at = NOW(),
        updated_at = NOW()
    WHERE status = 'processing'
    AND started_at < NOW() - INTERVAL '%d minutes' % timeout_minutes;
    
    GET DIAGNOSTICS reset_count = ROW_COUNT;
    
    -- 记录重置日志
    RAISE NOTICE 'Reset % stuck tasks', reset_count;
    
    RETURN reset_count;
END;
$$ LANGUAGE plpgsql;

-- 插入一些测试数据 (仅在开发环境)
DO $$
BEGIN
    IF current_setting('server_version_num')::integer >= 120000 THEN
        -- 只在开发环境插入测试数据
        IF EXISTS (SELECT 1 FROM pg_database WHERE datname = 'zzdsj_demo') THEN
            INSERT INTO tasks (id, task_type, status, priority, kb_id, payload, created_at) VALUES
            ('550e8400-e29b-41d4-a716-446655440001', 'health_check', 'completed', 'low', 'kb_test_001', '{"message": "health check"}', NOW() - INTERVAL '1 hour'),
            ('550e8400-e29b-41d4-a716-446655440002', 'document_processing', 'queued', 'normal', 'kb_test_002', '{"file_path": "/tmp/test.pdf"}', NOW() - INTERVAL '30 minutes'),
            ('550e8400-e29b-41d4-a716-446655440003', 'embedding_generation', 'processing', 'high', 'kb_test_003', '{"documents": 100}', NOW() - INTERVAL '15 minutes')
            ON CONFLICT (id) DO NOTHING;
            
            RAISE NOTICE 'Test data inserted successfully';
        END IF;
    END IF;
END $$;

-- 设置数据库配置优化
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;

-- 重新加载配置
SELECT pg_reload_conf();

-- 显示创建完成信息
DO $$
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '=== 任务管理服务数据库初始化完成 ===';
    RAISE NOTICE '数据库: zzdsj_demo';
    RAISE NOTICE '表: tasks, task_history';
    RAISE NOTICE '视图: task_statistics, task_statistics_by_kb';
    RAISE NOTICE '函数: cleanup_old_tasks(), reset_stuck_tasks()';
    RAISE NOTICE '触发器: 自动更新时间戳, 状态变更历史';
    RAISE NOTICE '============================================';
    RAISE NOTICE '';
END $$;