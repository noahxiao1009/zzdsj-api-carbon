-- MCP微服务数据库初始化脚本
-- MCP Microservice Database Initialization Script

-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS zzdsl_mcp;

-- 使用数据库
\c zzdsl_mcp;

-- 创建扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 创建MCP服务表
CREATE TABLE IF NOT EXISTS mcp_services (
    id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(200) NOT NULL,
    description TEXT,
    type VARCHAR(50) NOT NULL, -- 'builtin', 'custom', 'third_party'
    category VARCHAR(50) NOT NULL, -- 'map', 'content', 'search', 'code', etc.
    version VARCHAR(20) DEFAULT '1.0.0',
    status VARCHAR(20) DEFAULT 'inactive', -- 'active', 'inactive', 'error', 'starting'
    config JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    
    -- Docker相关
    container_id VARCHAR(64),
    container_name VARCHAR(100),
    image_name VARCHAR(200),
    port_mapping JSONB, -- 端口映射配置
    
    -- 网络配置
    network_id VARCHAR(64),
    ip_address INET,
    vlan_id INTEGER,
    
    -- 资源配置
    cpu_limit VARCHAR(20),
    memory_limit VARCHAR(20),
    disk_limit VARCHAR(20),
    
    -- 服务配置
    service_url VARCHAR(500),
    health_check_url VARCHAR(500),
    api_key VARCHAR(500),
    auth_config JSONB,
    
    -- 统计信息
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 创建MCP工具表
CREATE TABLE IF NOT EXISTS mcp_tools (
    id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4(),
    service_id VARCHAR(36) NOT NULL REFERENCES mcp_services(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    description TEXT,
    tool_type VARCHAR(50), -- 'function', 'resource', 'prompt'
    schema JSONB NOT NULL, -- 工具schema定义
    enabled BOOLEAN DEFAULT TRUE,
    
    -- 使用统计
    usage_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    avg_execution_time_ms FLOAT DEFAULT 0.0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 创建MCP工具使用记录表
CREATE TABLE IF NOT EXISTS mcp_tool_usage (
    id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4(),
    service_id VARCHAR(36) NOT NULL REFERENCES mcp_services(id),
    tool_id VARCHAR(36) NOT NULL REFERENCES mcp_tools(id),
    user_id VARCHAR(36),
    session_id VARCHAR(36),
    
    -- 调用信息
    request_data JSONB,
    response_data JSONB,
    execution_time_ms INTEGER,
    status VARCHAR(20), -- 'success', 'error', 'timeout'
    error_message TEXT,
    
    -- 流式通信信息
    stream_id VARCHAR(36),
    is_streaming BOOLEAN DEFAULT FALSE,
    stream_events_count INTEGER DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 创建MCP服务网络配置表
CREATE TABLE IF NOT EXISTS mcp_networks (
    id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    network_type VARCHAR(20) NOT NULL DEFAULT 'vlan', -- 'vlan', 'bridge', 'overlay'
    vlan_id INTEGER UNIQUE,
    subnet CIDR NOT NULL,
    gateway INET NOT NULL,
    dns_servers INET[],
    
    -- 安全配置
    isolation_enabled BOOLEAN DEFAULT TRUE,
    allowed_ports INTEGER[],
    firewall_rules JSONB,
    
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 创建流式会话表
CREATE TABLE IF NOT EXISTS mcp_streams (
    id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4(),
    stream_id VARCHAR(100) NOT NULL UNIQUE,
    service_id VARCHAR(36) NOT NULL REFERENCES mcp_services(id),
    tool_id VARCHAR(36) REFERENCES mcp_tools(id),
    user_id VARCHAR(36),
    
    -- 流式配置
    stream_type VARCHAR(20) NOT NULL, -- 'sse', 'websocket'
    connection_id VARCHAR(100),
    
    -- 状态信息
    status VARCHAR(20) DEFAULT 'active', -- 'active', 'completed', 'error', 'timeout'
    events_sent INTEGER DEFAULT 0,
    last_event_at TIMESTAMP WITH TIME ZONE,
    
    -- 配置信息
    keepalive_interval INTEGER DEFAULT 30,
    timeout_seconds INTEGER DEFAULT 300,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_mcp_services_type ON mcp_services(type);
CREATE INDEX IF NOT EXISTS idx_mcp_services_category ON mcp_services(category);
CREATE INDEX IF NOT EXISTS idx_mcp_services_status ON mcp_services(status);
CREATE INDEX IF NOT EXISTS idx_mcp_services_container ON mcp_services(container_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_tools_service_name ON mcp_tools(service_id, name);
CREATE INDEX IF NOT EXISTS idx_tools_enabled ON mcp_tools(enabled);
CREATE INDEX IF NOT EXISTS idx_tools_type ON mcp_tools(tool_type);

CREATE INDEX IF NOT EXISTS idx_usage_service_id ON mcp_tool_usage(service_id);
CREATE INDEX IF NOT EXISTS idx_usage_tool_id ON mcp_tool_usage(tool_id);
CREATE INDEX IF NOT EXISTS idx_usage_user_id ON mcp_tool_usage(user_id);
CREATE INDEX IF NOT EXISTS idx_usage_created_at ON mcp_tool_usage(created_at);
CREATE INDEX IF NOT EXISTS idx_usage_status ON mcp_tool_usage(status);

CREATE INDEX IF NOT EXISTS idx_networks_vlan_id ON mcp_networks(vlan_id);
CREATE INDEX IF NOT EXISTS idx_networks_active ON mcp_networks(is_active);

CREATE INDEX IF NOT EXISTS idx_streams_service_id ON mcp_streams(service_id);
CREATE INDEX IF NOT EXISTS idx_streams_user_id ON mcp_streams(user_id);
CREATE INDEX IF NOT EXISTS idx_streams_status ON mcp_streams(status);
CREATE INDEX IF NOT EXISTS idx_streams_created_at ON mcp_streams(created_at);

-- 创建触发器函数：自动更新updated_at字段
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 为需要的表创建触发器
CREATE TRIGGER update_mcp_services_updated_at BEFORE UPDATE ON mcp_services FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_mcp_tools_updated_at BEFORE UPDATE ON mcp_tools FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_mcp_networks_updated_at BEFORE UPDATE ON mcp_networks FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_mcp_streams_updated_at BEFORE UPDATE ON mcp_streams FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 插入默认网络配置
INSERT INTO mcp_networks (name, network_type, vlan_id, subnet, gateway, dns_servers) VALUES
('mcp-vlan-100', 'vlan', 100, '172.20.0.0/16', '172.20.0.1', ARRAY['8.8.8.8', '8.8.4.4']),
('mcp-vlan-101', 'vlan', 101, '172.21.0.0/16', '172.21.0.1', ARRAY['8.8.8.8', '8.8.4.4']),
('mcp-vlan-102', 'vlan', 102, '172.22.0.0/16', '172.22.0.1', ARRAY['8.8.8.8', '8.8.4.4']),
('mcp-vlan-103', 'vlan', 103, '172.23.0.0/16', '172.23.0.1', ARRAY['8.8.8.8', '8.8.4.4'])
ON CONFLICT (name) DO NOTHING;

-- 创建示例MCP服务
INSERT INTO mcp_services (name, display_name, description, type, category, config, metadata) VALUES
('search-service', '搜索服务', '提供网络搜索和文档检索功能', 'builtin', 'search', 
 '{"tools": [{"name": "web_search", "type": "function", "description": "网络搜索工具", "schema": {"type": "object", "properties": {"query": {"type": "string"}}}}]}', 
 '{"author": "ZZDSJ", "tags": ["search", "web"]}'),
('weather-service', '天气服务', '提供天气查询和预报功能', 'builtin', 'utility', 
 '{"tools": [{"name": "get_weather", "type": "function", "description": "获取天气信息", "schema": {"type": "object", "properties": {"location": {"type": "string"}}}}]}', 
 '{"author": "ZZDSJ", "tags": ["weather", "utility"]}'),
('code-service', '代码服务', '提供代码生成和分析功能', 'builtin', 'code', 
 '{"tools": [{"name": "generate_code", "type": "function", "description": "生成代码", "schema": {"type": "object", "properties": {"language": {"type": "string"}, "description": {"type": "string"}}}}]}', 
 '{"author": "ZZDSJ", "tags": ["code", "generation"]}')
ON CONFLICT (name) DO NOTHING;

-- 创建示例工具
INSERT INTO mcp_tools (service_id, name, display_name, description, tool_type, schema) 
SELECT s.id, 'web_search', '网络搜索', '在互联网上搜索信息', 'function', 
       '{"type": "object", "properties": {"query": {"type": "string", "description": "搜索关键词"}, "count": {"type": "integer", "default": 10}}}'
FROM mcp_services s WHERE s.name = 'search-service'
ON CONFLICT DO NOTHING;

INSERT INTO mcp_tools (service_id, name, display_name, description, tool_type, schema) 
SELECT s.id, 'get_weather', '天气查询', '获取指定地点的天气信息', 'function', 
       '{"type": "object", "properties": {"location": {"type": "string", "description": "地点名称"}, "days": {"type": "integer", "default": 1}}}'
FROM mcp_services s WHERE s.name = 'weather-service'
ON CONFLICT DO NOTHING;

INSERT INTO mcp_tools (service_id, name, display_name, description, tool_type, schema) 
SELECT s.id, 'generate_code', '代码生成', '根据描述生成代码', 'function', 
       '{"type": "object", "properties": {"language": {"type": "string", "description": "编程语言"}, "description": {"type": "string", "description": "代码描述"}}}'
FROM mcp_services s WHERE s.name = 'code-service'
ON CONFLICT DO NOTHING;

-- 创建视图：服务统计信息
CREATE OR REPLACE VIEW mcp_service_stats AS
SELECT 
    s.id,
    s.name,
    s.display_name,
    s.status,
    s.type,
    s.category,
    COUNT(t.id) as tools_count,
    COUNT(CASE WHEN t.enabled = TRUE THEN 1 END) as enabled_tools_count,
    COALESCE(SUM(t.usage_count), 0) as total_usage_count,
    COALESCE(AVG(t.avg_execution_time_ms), 0) as avg_execution_time,
    s.last_used_at,
    s.created_at
FROM mcp_services s
LEFT JOIN mcp_tools t ON s.id = t.service_id
GROUP BY s.id, s.name, s.display_name, s.status, s.type, s.category, s.last_used_at, s.created_at;

-- 创建视图：工具使用统计
CREATE OR REPLACE VIEW mcp_tool_stats AS
SELECT 
    t.id,
    t.name,
    t.display_name,
    t.tool_type,
    t.enabled,
    s.name as service_name,
    t.usage_count,
    t.success_count,
    t.error_count,
    CASE WHEN t.usage_count > 0 THEN (t.success_count * 100.0 / t.usage_count) ELSE 0 END as success_rate,
    t.avg_execution_time_ms,
    t.created_at
FROM mcp_tools t
JOIN mcp_services s ON t.service_id = s.id;

-- 创建函数：获取服务健康状态
CREATE OR REPLACE FUNCTION get_service_health_status(service_name VARCHAR)
RETURNS TABLE (
    service_id VARCHAR,
    health_status VARCHAR,
    last_check TIMESTAMP WITH TIME ZONE,
    response_time_ms INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.id,
        CASE 
            WHEN s.status = 'active' THEN 'healthy'
            WHEN s.status = 'error' THEN 'unhealthy'
            ELSE 'unknown'
        END as health_status,
        s.updated_at as last_check,
        0 as response_time_ms -- 这里应该从实际的健康检查数据获取
    FROM mcp_services s
    WHERE s.name = service_name;
END;
$$ LANGUAGE plpgsql;

-- 创建函数：清理过期的流记录
CREATE OR REPLACE FUNCTION cleanup_expired_streams()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM mcp_streams 
    WHERE status IN ('completed', 'error', 'timeout') 
    AND created_at < NOW() - INTERVAL '1 day';
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- 创建定时任务（需要pg_cron扩展）
-- SELECT cron.schedule('cleanup-expired-streams', '0 2 * * *', 'SELECT cleanup_expired_streams();');

COMMIT;