# Cloud Run ポスター関数用 Dockerfile
# Playwright ブラウザ自動化エンジン

FROM python:3.11-slim

# 作業ディレクトリ
WORKDIR /app

# システムパッケージ（Playwright 依存）
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Python 依存パッケージ
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright ブラウザをインストール
RUN playwright install chromium

# アプリケーションコード
COPY . .

# Cloud Run が PORT 環境変数を使用（デフォルト 8080）
ENV PORT=8080

# Cloud Functions フレームワーク
RUN pip install --no-cache-dir functions-framework

# ポスター関数を起動
CMD exec functions-framework --target=post_to_platforms --debug --source=/app/functions/poster.py
