const path = require('path');
const currentDir = __dirname;

module.exports = {
  apps: [{
    name: "kaiban-service",
    script: "main.py",
    interpreter: "python",
    cwd: currentDir,
    instances: 1,
    exec_mode: "fork",
    env: {
      NODE_ENV: "development",
      SERVICE_NAME: "kaiban-service",
      SERVICE_PORT: 8092,
      LOG_LEVEL: "INFO",
      PYTHONPATH: currentDir
    },
    env_production: {
      NODE_ENV: "production",
      SERVICE_NAME: "kaiban-service",
      SERVICE_PORT: 8092,
      LOG_LEVEL: "WARNING",
      PYTHONPATH: currentDir
    },
    watch: false,
    max_memory_restart: "1G",
    restart_delay: 3000,
    min_uptime: "10s",
    max_restarts: 10,
    merge_logs: true,
    log_date_format: "YYYY-MM-DD HH:mm:ss",
    error_file: "logs/pm2-kaiban-error.log",
    out_file: "logs/pm2-kaiban-out.log",
    log_file: "logs/pm2-kaiban-combined.log",
    pid_file: "logs/pm2-kaiban.pid"
  }]
};