# Python环境配置指南

## 概述

NextAgent微服务支持多种Python环境配置方式，包括系统Python、虚拟环境、Conda环境等。

## 环境检测机制

PM2配置会按以下优先级检测Python解释器：

1. **环境变量** `PYTHON_INTERPRETER` - 手动指定的Python路径
2. **当前激活环境** `which python` - 自动检测当前激活的Python环境
3. **默认Python** `python` - 系统默认Python

## 使用方法

### 1. 自动检测（推荐）

```bash
# 激活你的Python环境，然后启动服务
conda activate your-env  # 或 source venv/bin/activate
./pm2-manager.sh start:core
```

### 2. 手动指定Python路径

```bash
# 指定具体的Python解释器路径
PYTHON_INTERPRETER=/opt/anaconda3/bin/python ./pm2-manager.sh start:core

# 使用特定的Conda环境
PYTHON_INTERPRETER=/opt/anaconda3/envs/nextAgent/bin/python ./pm2-manager.sh start knowledge

# 使用虚拟环境
PYTHON_INTERPRETER=/path/to/venv/bin/python ./pm2-manager.sh start:all
```

### 3. 交互式启动

```bash
# 交互式启动会自动检测当前Python环境
./pm2-manager.sh interactive

# 或指定Python环境的交互式启动
PYTHON_INTERPRETER=/opt/anaconda3/bin/python ./pm2-manager.sh interactive
```

## 常见环境配置

### Conda环境

```bash
# 1. 创建专用环境
conda create -n nextAgent python=3.11
conda activate nextAgent

# 2. 安装依赖（在每个服务目录下）
cd knowledge-service
pip install -r requirements.txt

# 3. 启动服务
./pm2-manager.sh start knowledge
```

### 虚拟环境

```bash
# 1. 创建虚拟环境
python -m venv venv
source venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动服务
./pm2-manager.sh start:core
```

### 系统Python

```bash
# 直接使用系统Python（不推荐用于生产环境）
./pm2-manager.sh start:all
```

## 验证环境配置

### 检查当前Python环境

```bash
which python
python --version
pip list | grep -E "(fastapi|uvicorn|torch)"
```

### 查看PM2进程信息

```bash
pm2 info knowledge-service
pm2 logs knowledge-service --lines 10
```

### 测试服务启动

```bash
# 测试单个服务
./pm2-manager.sh start knowledge development

# 查看启动日志
./pm2-manager.sh logs knowledge
```

## 环境隔离建议

### 开发环境

```bash
# 使用Conda环境进行开发
conda create -n nextAgent-dev python=3.11
conda activate nextAgent-dev
pip install -r requirements.txt

# 启动开发环境
./pm2-manager.sh start:core development
```

### 生产环境

```bash
# 使用独立的Python环境
PYTHON_INTERPRETER=/opt/python3.11/bin/python ./pm2-manager.sh start:all production
```

## 故障排除

### 问题1：Python路径不正确

```bash
# 症状：服务启动失败，提示找不到Python
# 解决：手动指定正确的Python路径
PYTHON_INTERPRETER=$(which python) ./pm2-manager.sh start knowledge
```

### 问题2：依赖包缺失

```bash
# 症状：ImportError或ModuleNotFoundError
# 解决：确保在正确的环境中安装依赖
conda activate your-env
pip install -r requirements.txt
```

### 问题3：权限错误

```bash
# 症状：Permission denied
# 解决：检查Python解释器权限
ls -la $(which python)
chmod +x /path/to/python  # 如需要
```

### 问题4：版本不兼容

```bash
# 症状：Python版本过低或过高
# 解决：使用推荐的Python版本
python --version  # 建议使用Python 3.11+
```

## 环境变量说明

| 变量名 | 描述 | 示例 |
|--------|------|------|
| `PYTHON_INTERPRETER` | Python解释器路径 | `/opt/anaconda3/bin/python` |
| `PYTHONPATH` | Python模块搜索路径 | 自动设置为服务目录 |
| `NODE_ENV` | 运行环境 | `development`/`production` |
| `LOG_LEVEL` | 日志级别 | `INFO`/`WARNING`/`ERROR` |

## 最佳实践

1. **使用虚拟环境**：避免全局包冲突
2. **固定Python版本**：确保环境一致性
3. **锁定依赖版本**：使用requirements.txt固定版本
4. **环境隔离**：开发/测试/生产使用不同环境
5. **自动化检测**：优先使用自动检测机制
6. **文档记录**：记录团队使用的环境配置

## 团队协作

### 共享环境配置

创建 `.env.example` 文件：

```bash
# Python环境配置示例
PYTHON_INTERPRETER=/opt/anaconda3/envs/nextAgent/bin/python
LOG_LEVEL=INFO
```

### CI/CD集成

```yaml
# GitHub Actions示例
- name: Setup Python Environment
  run: |
    conda create -n nextAgent python=3.11
    conda activate nextAgent
    pip install -r requirements.txt
    
- name: Start Services
  run: |
    PYTHON_INTERPRETER=/opt/miniconda3/envs/nextAgent/bin/python ./pm2-manager.sh start:all
```

现在你的微服务支持完全的环境灵活性，可以在任何Python环境中正常运行！