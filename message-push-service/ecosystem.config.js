// PM2 Ecosystem 配置文件
// Message Push Service (SSE消息推送微服务) PM2部署配置

module.exports = {
  apps: [
    {
      // 主服务配置
      name: 'message-push-service',
      script: 'main.py',
      interpreter: 'python3',
      cwd: '/Users/wxn/Desktop/carbon/zzdsl-api-carbon/message-push-service',
      
      // 实例配置
      instances: 1, // SSE服务通常单实例运行
      exec_mode: 'fork',
      
      // 自动重启配置
      autorestart: true,
      watch: false,
      max_memory_restart: '512M',
      restart_delay: 4000,
      
      // 环境变量
      env: {
        NODE_ENV: 'development',
        SERVICE_NAME: 'message-push-service',
        SERVICE_PORT: 8089,
        SERVICE_VERSION: '1.0.0',
        ENVIRONMENT: 'development',
        
        // Redis配置
        REDIS_HOST: 'localhost',
        REDIS_PORT: 6379,
        REDIS_DB: 5,
        REDIS_PASSWORD: '',
        REDIS_MAX_CONNECTIONS: 20,
        
        // 日志配置
        LOG_LEVEL: 'INFO',
        LOG_FORMAT: 'colored',
        LOG_FILE: './logs/message-push-service.log',
        
        // 性能配置
        MAX_CONNECTIONS: 500,
        CONNECTION_TIMEOUT: 300,
        HEARTBEAT_INTERVAL: 30,
        MESSAGE_QUEUE_SIZE: 5000,
        
        // 开发环境特定配置
        DEBUG: 'true',
        RELOAD: 'true'
      },
      
      // 生产环境配置
      env_production: {
        NODE_ENV: 'production',
        SERVICE_NAME: 'message-push-service',
        SERVICE_PORT: 8089,
        SERVICE_VERSION: '1.0.0',
        ENVIRONMENT: 'production',
        
        // Redis配置
        REDIS_HOST: 'localhost',
        REDIS_PORT: 6379,
        REDIS_DB: 5,
        REDIS_PASSWORD: '',
        REDIS_MAX_CONNECTIONS: 50,
        
        // 日志配置
        LOG_LEVEL: 'INFO',
        LOG_FORMAT: 'json',
        LOG_FILE: './logs/message-push-service.log',
        
        // 性能配置
        MAX_CONNECTIONS: 1000,
        CONNECTION_TIMEOUT: 300,
        HEARTBEAT_INTERVAL: 30,
        MESSAGE_QUEUE_SIZE: 10000,
        
        // 监控配置
        ENABLE_METRICS: 'true',
        METRICS_PORT: 9090,
        
        // 生产环境特定配置
        DEBUG: 'false',
        RELOAD: 'false'
      },
      
      // 日志配置
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      error_file: './logs/pm2-message-push-error.log',
      out_file: './logs/pm2-message-push-out.log',
      combine_logs: true,
      log_file: './logs/pm2-message-push-combined.log',
      time: true,
      
      // 进程配置
      kill_timeout: 5000,
      listen_timeout: 8000,
      wait_ready: true,
      
      // 监控配置
      min_uptime: '10s',
      max_restarts: 10,
      
      // 高级配置
      node_args: [],
      args: [],
      
      // 忽略监听
      ignore_watch: [
        'node_modules',
        'logs',
        '*.log',
        '.git',
        '__pycache__',
        '*.pyc',
        'uploads',
        'temp'
      ],
      
      // 实例特定配置
      instance_var: 'INSTANCE_ID',
      
      // 自定义配置
      merge_logs: true,
      vizion: false,
      
      // 健康检查
      health_check_grace_period: 3000
    }
  ],

  // 部署配置
  deploy: {
    production: {
      user: 'ubuntu',
      host: 'your-production-server.com',
      ref: 'origin/main',
      repo: 'git@github.com:your-repo/message-push-service.git',
      path: '/var/www/message-push-service',
      'post-deploy': 'pip install -r requirements.txt && pm2 reload ecosystem.config.js --env production',
      'pre-setup': 'apt update && apt install python3 python3-pip',
      'post-setup': 'pip3 install -r requirements.txt'
    },
    
    staging: {
      user: 'ubuntu',
      host: 'your-staging-server.com',
      ref: 'origin/develop',
      repo: 'git@github.com:your-repo/message-push-service.git',
      path: '/var/www/message-push-service-staging',
      'post-deploy': 'pip install -r requirements.txt && pm2 reload ecosystem.config.js --env staging'
    }
  }
};