# Carroo 本番用 Dockerfile（Web UI＋投稿ワーカー一体型）
# 🔴 Trabox投稿に Playwright/Chromium が必要なため、公式Playwrightイメージを使う
#    （playwright==1.35.0 に合わせたタグ。requirements変更時はタグも合わせる）
FROM mcr.microsoft.com/playwright/python:v1.35.0-jammy

WORKDIR /app

# Python 依存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m playwright install chromium

# アプリケーション
COPY . .
RUN chmod +x /app/entrypoint.sh

# Cloud Run は PORT 環境変数を渡す（デフォルト 8080）
ENV PORT=8080

# Xvfb 上で headed Chromium を動かすため entrypoint.sh 経由で起動（Trabox headless 対策）
CMD ["/app/entrypoint.sh"]
