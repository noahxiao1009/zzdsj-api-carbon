module.exports = {
  apps: [{
    name: "knowledge-graph-service",
    script: "main.py",
    interpreter: "python",
    cwd: "/Users/wxn/Desktop/carbon/zzdsl-api-carbon/knowledge-graph-service",
    instances: 1,
    exec_mode: "fork",
    env: {
      NODE_ENV: "development",
      SERVICE_NAME: "knowledge-graph-service",
      SERVICE_PORT: 8087,
      LOG_LEVEL: "INFO",
      PYTHONPATH: "/Users/wxn/Desktop/carbon/zzdsl-api-carbon/knowledge-graph-service"
    },
    env_production: {
      NODE_ENV: "production",
      SERVICE_NAME: "knowledge-graph-service",
      SERVICE_PORT: 8087,
      LOG_LEVEL: "WARNING",
      PYTHONPATH: "/Users/wxn/Desktop/carbon/zzdsl-api-carbon/knowledge-graph-service"
    },
    watch: false,
    max_memory_restart: "2G",
    restart_delay: 3000,
    min_uptime: "10s",
    max_restarts: 10,
    merge_logs: true,
    log_date_format: "YYYY-MM-DD HH:mm:ss",
    error_file: "logs/pm2-kg-error.log",
    out_file: "logs/pm2-kg-out.log",
    log_file: "logs/pm2-kg-combined.log",
    pid_file: "logs/pm2-kg.pid"
  }]
};