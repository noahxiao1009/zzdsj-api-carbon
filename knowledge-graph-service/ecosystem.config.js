const path = require('path');
const { execSync } = require('child_process');
const currentDir = __dirname;

// 动态获取Python解释器路径
function getPythonInterpreter() {
  try {
    // 优先使用环境变量指定的Python路径
    if (process.env.PYTHON_INTERPRETER) {
      return process.env.PYTHON_INTERPRETER;
    }
    
    // 尝试获取当前激活的Python环境
    const pythonPath = execSync('which python', { encoding: 'utf8' }).trim();
    console.log(`使用Python解释器: ${pythonPath}`);
    return pythonPath;
  } catch (error) {
    console.warn('无法检测Python路径，使用默认值: python');
    return 'python';
  }
}

const pythonInterpreter = getPythonInterpreter();

module.exports = {
  apps: [{
    name: "knowledge-graph-service",
    script: "main.py",
    interpreter: pythonInterpreter,
    cwd: currentDir,
    instances: 1,
    exec_mode: "fork",
    env: {
      NODE_ENV: "development",
      SERVICE_NAME: "knowledge-graph-service",
      SERVICE_PORT: 8087,
      LOG_LEVEL: "INFO",
      PYTHONPATH: currentDir
    },
    env_production: {
      NODE_ENV: "production",
      SERVICE_NAME: "knowledge-graph-service",
      SERVICE_PORT: 8087,
      LOG_LEVEL: "WARNING",
      PYTHONPATH: currentDir
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