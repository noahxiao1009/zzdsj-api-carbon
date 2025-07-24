module.exports = {
  apps: [{
    name: "scheduler-service",
    script: "main.py",
    interpreter: "python",
    cwd: "/Users/wxn/Desktop/carbon/zzdsl-api-carbon/scheduler-service",
    instances: 1,
    exec_mode: "fork",
    env: {
      NODE_ENV: "development",
      SERVICE_NAME: "scheduler-service",
      SERVICE_PORT: 8094,
      LOG_LEVEL: "INFO",
      PYTHONPATH: "/Users/wxn/Desktop/carbon/zzdsl-api-carbon/scheduler-service"
    },
    env_production: {
      NODE_ENV: "production",
      SERVICE_NAME: "scheduler-service",
      SERVICE_PORT: 8094,
      LOG_LEVEL: "WARNING",
      PYTHONPATH: "/Users/wxn/Desktop/carbon/zzdsl-api-carbon/scheduler-service"
    },
    watch: false,
    max_memory_restart: "1G",
    restart_delay: 3000,
    min_uptime: "10s",
    max_restarts: 10,
    merge_logs: true,
    log_date_format: "YYYY-MM-DD HH:mm:ss",
    error_file: "logs/pm2-scheduler-error.log",
    out_file: "logs/pm2-scheduler-out.log",
    log_file: "logs/pm2-scheduler-combined.log",
    pid_file: "logs/pm2-scheduler.pid"
  }]
};