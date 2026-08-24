# 服务器批量：Xvfb 虚拟显示 + Patchright 隐身 Chromium + xdotool 真实鼠标按住
# 全程在容器虚拟显示里，不碰任何物理鼠标；xdotool 发的是 OS 级真实输入事件（可过 PX）
FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive DISPLAY=:99 PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb x11-utils xdotool \
    ca-certificates wget gnupg fonts-liberation \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 \
    libpango-1.0-0 libcairo2 libatspi2.0-0 libx11-6 libxcb1 libxext6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements-linux.txt .
RUN pip install --no-cache-dir -r requirements-linux.txt \
    && python -m patchright install --with-deps chromium

COPY . /app/
RUN chmod +x /app/entrypoint.sh

# 默认跑 PX 按住验证；批量时改 CMD 为 linux_register.py
CMD ["/app/entrypoint.sh", "px_hold_test.py"]
