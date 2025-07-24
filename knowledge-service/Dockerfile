# NextAgent - 知识库服务 Docker 镜像
# 基于 Python 3.11 Alpine 的轻量级镜像

FROM python:3.11-slim

# 设置维护者信息
LABEL maintainer="智政科技 <support@zhengtech.com>"
LABEL description="NextAgent - 知识库服务"
LABEL version="1.0.0"

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    gcc \
    g++ \
    git \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# 创建应用用户（安全最佳实践）
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 复制依赖文件
COPY requirements.txt .

# 升级 pip 并安装 Python 依赖
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建必要的目录
RUN mkdir -p /app/logs /app/uploads /app/temp && \
    chown -R appuser:appuser /app

# 创建健康检查脚本
RUN echo '#!/bin/bash\ncurl -f http://localhost:8082/health || exit 1' > /app/healthcheck.sh && \
    chmod +x /app/healthcheck.sh

# 切换到应用用户
USER appuser

# 暴露端口
EXPOSE 8082

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD /app/healthcheck.sh

# 设置启动命令
CMD ["python", "main.py"]