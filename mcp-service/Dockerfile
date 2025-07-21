# MCP Service Dockerfile
# 基于Python 3.11的官方镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    wget \
    git \
    build-essential \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    pkg-config \
    docker.io \
    iputils-ping \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# 升级pip
RUN pip install --upgrade pip setuptools wheel

# 复制requirements文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app/ ./app/
COPY main.py ./
COPY config/ ./config/

# 创建必要的目录
RUN mkdir -p /app/logs /app/data /app/temp

# 创建非root用户
RUN useradd --create-home --shell /bin/bash --user-group mcp-user && \
    chown -R mcp-user:mcp-user /app

# 切换到非root用户
USER mcp-user

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8089/health || exit 1

# 暴露端口
EXPOSE 8089

# 启动命令
CMD ["python", "main.py"]
