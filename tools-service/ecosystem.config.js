module.exports = {
  apps: [{
    name: "tools-service",
    script: "main.py", 
    interpreter: "python",
    cwd: "/Users/wxn/Desktop/carbon/zzdsl-api-carbon/tools-service",
    instances: 1,
    exec_mode: "fork",
    env: {
      NODE_ENV: "development",
      SERVICE_NAME: "tools-service",
      SERVICE_PORT: 8090,
      LOG_LEVEL: "INFO",
      PYTHONPATH: "/Users/wxn/Desktop/carbon/zzdsl-api-carbon/tools-service"
    },
    env_production: {
      NODE_ENV: "production",
      SERVICE_NAME: "tools-service",
      SERVICE_PORT: 8090,
      LOG_LEVEL: "WARNING",
      PYTHONPATH: "/Users/wxn/Desktop/carbon/zzdsl-api-carbon/tools-service"
    },
    watch: false,
    max_memory_restart: "1G",
    restart_delay: 3000,
    min_uptime: "10s",
    max_restarts: 10,
    merge_logs: true,
    log_date_format: "YYYY-MM-DD HH:mm:ss",
    error_file: "logs/pm2-tools-error.log",
    out_file: "logs/pm2-tools-out.log",
    log_file: "logs/pm2-tools-combined.log",
    pid_file: "logs/pm2-tools.pid"
  }]
};