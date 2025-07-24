module.exports = {
  apps: [
    // 网关服务 (8080) - 必须首先启动
    {
      name: "gateway-service",
      script: "./gateway-service/main.py",
      interpreter: "python",
      cwd: "/Users/wxn/Desktop/carbon/zzdsl-api-carbon",
      instances: 1,
      exec_mode: "fork",
      env: {
        NODE_ENV: "development",
        SERVICE_NAME: "gateway-service",
        SERVICE_PORT: 8080,
        LOG_LEVEL: "INFO"
      },
      env_production: {
        NODE_ENV: "production",
        SERVICE_NAME: "gateway-service",
        SERVICE_PORT: 8080,
        LOG_LEVEL: "WARNING"
      },
      watch: false,
      max_memory_restart: "1G",
      restart_delay: 5000,
      min_uptime: "10s",
      max_restarts: 10,
      merge_logs: true,
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      error_file: "./gateway-service/logs/pm2-error.log",
      out_file: "./gateway-service/logs/pm2-out.log",
      log_file: "./gateway-service/logs/pm2-combined.log"
    },

    // 智能体服务 (8081)
    {
      name: "agent-service",
      script: "./agent-service/main.py",
      interpreter: "python",
      cwd: "/Users/wxn/Desktop/carbon/zzdsl-api-carbon",
      instances: 1,
      exec_mode: "fork",
      env: {
        NODE_ENV: "development",
        SERVICE_NAME: "agent-service",
        SERVICE_PORT: 8081,
        LOG_LEVEL: "INFO"
      },
      env_production: {
        NODE_ENV: "production",
        SERVICE_NAME: "agent-service",
        SERVICE_PORT: 8081,
        LOG_LEVEL: "WARNING"
      },
      watch: false,
      max_memory_restart: "2G",
      restart_delay: 3000,
      min_uptime: "10s",
      max_restarts: 10,
      merge_logs: true,
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      error_file: "./agent-service/logs/pm2-error.log",
      out_file: "./agent-service/logs/pm2-out.log",
      log_file: "./agent-service/logs/pm2-combined.log"
    },

    // 知识库服务 (8082)
    {
      name: "knowledge-service",
      script: "./knowledge-service/main.py",
      interpreter: "python",
      cwd: "/Users/wxn/Desktop/carbon/zzdsl-api-carbon",
      instances: 1,
      exec_mode: "fork",
      env: {
        NODE_ENV: "development",
        SERVICE_NAME: "knowledge-service",
        SERVICE_PORT: 8082,
        LOG_LEVEL: "INFO"
      },
      env_production: {
        NODE_ENV: "production",
        SERVICE_NAME: "knowledge-service",
        SERVICE_PORT: 8082,
        LOG_LEVEL: "WARNING"
      },
      watch: false,
      max_memory_restart: "2G",
      restart_delay: 3000,
      min_uptime: "10s",
      max_restarts: 10,
      merge_logs: true,
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      error_file: "./knowledge-service/logs/pm2-error.log",
      out_file: "./knowledge-service/logs/pm2-out.log",
      log_file: "./knowledge-service/logs/pm2-combined.log"
    },

    // 聊天服务 (8083)
    {
      name: "chat-service",
      script: "./chat-service/main.py",
      interpreter: "python",
      cwd: "/Users/wxn/Desktop/carbon/zzdsl-api-carbon",
      instances: 1,
      exec_mode: "fork",
      env: {
        NODE_ENV: "development",
        SERVICE_NAME: "chat-service",
        SERVICE_PORT: 8083,
        LOG_LEVEL: "INFO"
      },
      env_production: {
        NODE_ENV: "production",
        SERVICE_NAME: "chat-service",
        SERVICE_PORT: 8083,
        LOG_LEVEL: "WARNING"
      },
      watch: false,
      max_memory_restart: "1G",
      restart_delay: 3000,
      min_uptime: "10s",
      max_restarts: 10,
      merge_logs: true,
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      error_file: "./chat-service/logs/pm2-error.log",
      out_file: "./chat-service/logs/pm2-out.log",
      log_file: "./chat-service/logs/pm2-combined.log"
    },

    // 数据库服务 (8084)
    {
      name: "database-service",
      script: "./database-service/main.py",
      interpreter: "python",
      cwd: "/Users/wxn/Desktop/carbon/zzdsl-api-carbon",
      instances: 1,
      exec_mode: "fork",
      env: {
        NODE_ENV: "development",
        SERVICE_NAME: "database-service",
        SERVICE_PORT: 8084,
        LOG_LEVEL: "INFO"
      },
      env_production: {
        NODE_ENV: "production",
        SERVICE_NAME: "database-service",
        SERVICE_PORT: 8084,
        LOG_LEVEL: "WARNING"
      },
      watch: false,
      max_memory_restart: "1G",
      restart_delay: 3000,
      min_uptime: "10s",
      max_restarts: 10,
      merge_logs: true,
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      error_file: "./database-service/logs/pm2-error.log",
      out_file: "./database-service/logs/pm2-out.log",
      log_file: "./database-service/logs/pm2-combined.log"
    },

    // 知识图谱服务 (8087)
    {
      name: "knowledge-graph-service",
      script: "./knowledge-graph-service/main.py",
      interpreter: "python",
      cwd: "/Users/wxn/Desktop/carbon/zzdsl-api-carbon",
      instances: 1,
      exec_mode: "fork",
      env: {
        NODE_ENV: "development",
        SERVICE_NAME: "knowledge-graph-service",
        SERVICE_PORT: 8087,
        LOG_LEVEL: "INFO"
      },
      env_production: {
        NODE_ENV: "production",
        SERVICE_NAME: "knowledge-graph-service",
        SERVICE_PORT: 8087,
        LOG_LEVEL: "WARNING"
      },
      watch: false,
      max_memory_restart: "2G",
      restart_delay: 3000,
      min_uptime: "10s",
      max_restarts: 10,
      merge_logs: true,
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      error_file: "./knowledge-graph-service/logs/pm2-error.log",
      out_file: "./knowledge-graph-service/logs/pm2-out.log",
      log_file: "./knowledge-graph-service/logs/pm2-combined.log"
    },

    // 模型服务 (8088)
    {
      name: "model-service",
      script: "./model-service/main.py",
      interpreter: "python",
      cwd: "/Users/wxn/Desktop/carbon/zzdsl-api-carbon",
      instances: 1,
      exec_mode: "fork",
      env: {
        NODE_ENV: "development",
        SERVICE_NAME: "model-service",
        SERVICE_PORT: 8088,
        LOG_LEVEL: "INFO"
      },
      env_production: {
        NODE_ENV: "production",
        SERVICE_NAME: "model-service",
        SERVICE_PORT: 8088,
        LOG_LEVEL: "WARNING"
      },
      watch: false,
      max_memory_restart: "3G",
      restart_delay: 3000,
      min_uptime: "10s",
      max_restarts: 10,
      merge_logs: true,
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      error_file: "./model-service/logs/pm2-error.log",
      out_file: "./model-service/logs/pm2-out.log",
      log_file: "./model-service/logs/pm2-combined.log"
    },

    // MCP服务 (8089)
    {
      name: "mcp-service",
      script: "./mcp-service/main.py",
      interpreter: "python",
      cwd: "/Users/wxn/Desktop/carbon/zzdsl-api-carbon",
      instances: 1,
      exec_mode: "fork",
      env: {
        NODE_ENV: "development",
        SERVICE_NAME: "mcp-service",
        SERVICE_PORT: 8089,
        LOG_LEVEL: "INFO"
      },
      env_production: {
        NODE_ENV: "production",
        SERVICE_NAME: "mcp-service",
        SERVICE_PORT: 8089,
        LOG_LEVEL: "WARNING"
      },
      watch: false,
      max_memory_restart: "1G",
      restart_delay: 3000,
      min_uptime: "10s",
      max_restarts: 10,
      merge_logs: true,
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      error_file: "./mcp-service/logs/pm2-error.log",
      out_file: "./mcp-service/logs/pm2-out.log",
      log_file: "./mcp-service/logs/pm2-combined.log"
    },

    // 工具服务 (8090)
    {
      name: "tools-service",
      script: "./tools-service/main.py",
      interpreter: "python",
      cwd: "/Users/wxn/Desktop/carbon/zzdsl-api-carbon",
      instances: 1,
      exec_mode: "fork",
      env: {
        NODE_ENV: "development",
        SERVICE_NAME: "tools-service",
        SERVICE_PORT: 8090,
        LOG_LEVEL: "INFO"
      },
      env_production: {
        NODE_ENV: "production",
        SERVICE_NAME: "tools-service",
        SERVICE_PORT: 8090,
        LOG_LEVEL: "WARNING"
      },
      watch: false,
      max_memory_restart: "1G",
      restart_delay: 3000,
      min_uptime: "10s",
      max_restarts: 10,
      merge_logs: true,
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      error_file: "./tools-service/logs/pm2-error.log",
      out_file: "./tools-service/logs/pm2-out.log",
      log_file: "./tools-service/logs/pm2-combined.log"
    },

    // 智能报告服务 (8091)
    {
      name: "intelligent-reports-service",
      script: "./intelligent-reports-service/main.py",
      interpreter: "python",
      cwd: "/Users/wxn/Desktop/carbon/zzdsl-api-carbon",
      instances: 1,
      exec_mode: "fork",
      env: {
        NODE_ENV: "development",
        SERVICE_NAME: "intelligent-reports-service",
        SERVICE_PORT: 8091,
        LOG_LEVEL: "INFO"
      },
      env_production: {
        NODE_ENV: "production",
        SERVICE_NAME: "intelligent-reports-service",
        SERVICE_PORT: 8091,
        LOG_LEVEL: "WARNING"
      },
      watch: false,
      max_memory_restart: "2G",
      restart_delay: 3000,
      min_uptime: "10s",
      max_restarts: 10,
      merge_logs: true,
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      error_file: "./intelligent-reports-service/logs/pm2-error.log",
      out_file: "./intelligent-reports-service/logs/pm2-out.log",
      log_file: "./intelligent-reports-service/logs/pm2-combined.log"
    },

    // 看板服务 (8092)
    {
      name: "kaiban-service",
      script: "./kaiban-service/main.py",
      interpreter: "python",
      cwd: "/Users/wxn/Desktop/carbon/zzdsl-api-carbon",
      instances: 1,
      exec_mode: "fork",
      env: {
        NODE_ENV: "development",
        SERVICE_NAME: "kaiban-service",
        SERVICE_PORT: 8092,
        LOG_LEVEL: "INFO"
      },
      env_production: {
        NODE_ENV: "production",
        SERVICE_NAME: "kaiban-service",
        SERVICE_PORT: 8092,
        LOG_LEVEL: "WARNING"
      },
      watch: false,
      max_memory_restart: "1G",
      restart_delay: 3000,
      min_uptime: "10s",
      max_restarts: 10,
      merge_logs: true,
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      error_file: "./kaiban-service/logs/pm2-error.log",
      out_file: "./kaiban-service/logs/pm2-out.log",
      log_file: "./kaiban-service/logs/pm2-combined.log"
    },

    // 消息服务 (8093)
    {
      name: "messaging-service",
      script: "./messaging-service/main.py",
      interpreter: "python",
      cwd: "/Users/wxn/Desktop/carbon/zzdsl-api-carbon",
      instances: 1,
      exec_mode: "fork",
      env: {
        NODE_ENV: "development",
        SERVICE_NAME: "messaging-service",
        SERVICE_PORT: 8093,
        LOG_LEVEL: "INFO"
      },
      env_production: {
        NODE_ENV: "production",
        SERVICE_NAME: "messaging-service",
        SERVICE_PORT: 8093,
        LOG_LEVEL: "WARNING"
      },
      watch: false,
      max_memory_restart: "1G",
      restart_delay: 3000,
      min_uptime: "10s",
      max_restarts: 10,
      merge_logs: true,
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      error_file: "./messaging-service/logs/pm2-error.log",
      out_file: "./messaging-service/logs/pm2-out.log",
      log_file: "./messaging-service/logs/pm2-combined.log"
    },

    // 调度服务 (8094)
    {
      name: "scheduler-service",
      script: "./scheduler-service/main.py",
      interpreter: "python",
      cwd: "/Users/wxn/Desktop/carbon/zzdsl-api-carbon",
      instances: 1,
      exec_mode: "fork",
      env: {
        NODE_ENV: "development",
        SERVICE_NAME: "scheduler-service",
        SERVICE_PORT: 8094,
        LOG_LEVEL: "INFO"
      },
      env_production: {
        NODE_ENV: "production",
        SERVICE_NAME: "scheduler-service",
        SERVICE_PORT: 8094,
        LOG_LEVEL: "WARNING"
      },
      watch: false,
      max_memory_restart: "1G",
      restart_delay: 3000,
      min_uptime: "10s",
      max_restarts: 10,
      merge_logs: true,
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      error_file: "./scheduler-service/logs/pm2-error.log",
      out_file: "./scheduler-service/logs/pm2-out.log",
      log_file: "./scheduler-service/logs/pm2-combined.log"
    }
  ]
};