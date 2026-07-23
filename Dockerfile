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

# Cloud Run は PORT 環境変数を渡す（デフォルト 8080）
ENV PORT=8080

# 🔴 Trabox の日付コンポーネント（Vue/ant-design）は headless Chromium だと
#    選択が確定せず投稿に失敗する。Xvfb（仮想ディスプレイ）上で headed Chromium を
#    動かすことで実ブラウザと同じ挙動にする。TRABOX_HEADLESS=False と併用すること。
#    Web UI＋/tasks/execute（投稿ワーカー）を同一プロセスで提供。
CMD exec xvfb-run -a --server-args="-screen 0 1440x2400x24" \
    uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1
