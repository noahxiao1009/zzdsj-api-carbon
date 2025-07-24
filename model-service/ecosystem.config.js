const path = require('path');
const currentDir = __dirname;

module.exports = {
  apps: [{
    name: "model-service",
    script: "main.py",
    interpreter: "python",
    cwd: currentDir,
    instances: 1,
    exec_mode: "fork",
    env: {
      NODE_ENV: "development",
      SERVICE_NAME: "model-service",
      SERVICE_PORT: 8088,
      LOG_LEVEL: "INFO",
      PYTHONPATH: currentDir
    },
    env_production: {
      NODE_ENV: "production",
      SERVICE_NAME: "model-service",
      SERVICE_PORT: 8088,
      LOG_LEVEL: "WARNING",
      PYTHONPATH: currentDir
    },
    watch: false,
    max_memory_restart: "3G",
    restart_delay: 3000,
    min_uptime: "10s",
    max_restarts: 10,
    merge_logs: true,
    log_date_format: "YYYY-MM-DD HH:mm:ss",
    error_file: "logs/pm2-model-error.log",
    out_file: "logs/pm2-model-out.log",
    log_file: "logs/pm2-model-combined.log",
    pid_file: "logs/pm2-model.pid"
  }]
};