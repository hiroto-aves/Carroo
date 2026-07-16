# Cloud Run ポスター関数用 Dockerfile
# Playwright ブラウザ自動化エンジン

FROM python:3.11-slim

# 作業ディレクトリ
WORKDIR /app

# システムパッケージ（Playwright 依存関係）
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    wget \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcairo2 \
    libdrm2 \
    libgbm1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    && rm -rf /var/lib/apt/lists/*

# Python 依存パッケージ
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright ブラウザをインストール（依存関係付き）
RUN playwright install --with-deps chromium

# アプリケーションコード
COPY . .

# Cloud Run が PORT 環境変数を使用（デフォルト 8080）
ENV PORT=8080

# ポスター関数を起動
CMD exec functions-framework --target=post_to_platforms --debug --source=/app/functions/poster.py
