# BioValue-AI Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv 包管理器
RUN pip install uv

# 复制项目文件
COPY pyproject.toml .
COPY conf.yaml .
COPY src/ ./src/
COPY sdk/ ./sdk/

# 安装 Python 依赖
RUN uv pip install --system -e .

# 创建数据目录
RUN mkdir -p /app/data/chroma

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

