module.exports = {
  apps: [{
    name: "messaging-service",
    script: "main.py",
    interpreter: "python",
    cwd: "/Users/wxn/Desktop/carbon/zzdsl-api-carbon/messaging-service",
    instances: 1,
    exec_mode: "fork",
    env: {
      NODE_ENV: "development",
      SERVICE_NAME: "messaging-service",
      SERVICE_PORT: 8093,
      LOG_LEVEL: "INFO",
      PYTHONPATH: "/Users/wxn/Desktop/carbon/zzdsl-api-carbon/messaging-service"
    },
    env_production: {
      NODE_ENV: "production",
      SERVICE_NAME: "messaging-service",
      SERVICE_PORT: 8093,
      LOG_LEVEL: "WARNING",
      PYTHONPATH: "/Users/wxn/Desktop/carbon/zzdsl-api-carbon/messaging-service"
    },
    watch: false,
    max_memory_restart: "1G",
    restart_delay: 3000,
    min_uptime: "10s",
    max_restarts: 10,
    merge_logs: true,
    log_date_format: "YYYY-MM-DD HH:mm:ss",
    error_file: "logs/pm2-messaging-error.log",
    out_file: "logs/pm2-messaging-out.log",
    log_file: "logs/pm2-messaging-combined.log",
    pid_file: "logs/pm2-messaging.pid"
  }]
};