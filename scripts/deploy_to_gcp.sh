#!/bin/bash

# GCP Cloud Run デプロイメントスクリプト
# 使用方法: ./scripts/deploy_to_gcp.sh <PROJECT_ID>

set -e

PROJECT_ID="${1:-}"

if [ -z "$PROJECT_ID" ]; then
    echo "❌ エラー: GCP プロジェクトID が指定されていません"
    echo "使用方法: ./scripts/deploy_to_gcp.sh <PROJECT_ID>"
    echo ""
    echo "例："
    echo "  ./scripts/deploy_to_gcp.sh my-logistics-project"
    exit 1
fi

echo "🚀 GCP Cloud Run デプロイメント開始"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "プロジェクト ID: $PROJECT_ID"
echo "デプロイ対象: ポスター関数（投稿エンジン）"
echo "リージョン: us-central1"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# GCP プロジェクトを設定
echo ""
echo "📍 GCP プロジェクトを設定中..."
gcloud config set project "$PROJECT_ID"

# Cloud Run にデプロイ
echo ""
echo "📦 Cloud Run にデプロイ中..."
gcloud run deploy poster \
    --source . \
    --platform managed \
    --region us-central1 \
    --memory 2Gi \
    --cpu 1 \
    --timeout 3600 \
    --max-instances 1 \
    --no-allow-unauthenticated \
    --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID" \
    --allow-unauthenticated

# デプロイ完了
echo ""
echo "✅ Cloud Run デプロイ完了！"
echo ""

# Cloud Run の URL を取得
CLOUD_RUN_URL=$(gcloud run services describe poster --region us-central1 --format='value(status.url)')

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 デプロイ情報"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "サービス名: poster"
echo "URL: $CLOUD_RUN_URL"
echo "リージョン: us-central1"
echo "メモリ: 2GB"
echo "CPU: 1"
echo "タイムアウト: 3600秒（1時間）"
echo "最大インスタンス数: 1"
echo ""

# Cloud Tasks キューを設定
echo "📋 Cloud Tasks キューを設定中..."
echo ""

# キューが存在するか確認
QUEUE_EXISTS=$(gcloud tasks queues describe posting-queue \
    --location us-central1 \
    --format='value(name)' 2>/dev/null || echo "")

if [ -z "$QUEUE_EXISTS" ]; then
    echo "  └─ キュー「posting-queue」を作成中..."
    gcloud tasks queues create posting-queue \
        --location us-central1 \
        --max-concurrent-dispatches 1 \
        --max-dispatches-per-second 1 \
        --min-backoff 2s \
        --max-backoff 3600s \
        --max-attempts 3
    echo "  └─ ✅ キュー作成完了"
else
    echo "  └─ キュー「posting-queue」は既に存在します"
    echo "  └─ キュー設定を確認中..."
    gcloud tasks queues describe posting-queue --location us-central1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📝 次のステップ"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1️⃣  環境変数を設定"
echo "  $ export GCP_PROJECT_ID='$PROJECT_ID'"
echo "  $ export CLOUD_RUN_URL='$CLOUD_RUN_URL'"
echo ""
echo "2️⃣  Web UI（Cloud Functions）をデプロイ"
echo "  $ gcloud functions deploy register-case \\"
echo "      --region us-central1 \\"
echo "      --runtime python311 \\"
echo "      --trigger-http \\"
echo "      --allow-unauthenticated"
echo ""
echo "3️⃣  テスト投稿を実行"
echo "  $ curl -X POST http://localhost:8000/cases/register \\"
echo "      -F pick_location='東京都' \\"
echo "      -F drop_location='大阪府' \\"
echo "      -F cargo_weight='100' \\"
echo "      -F vehicle_type='small_truck' \\"
echo "      -F freight_rate='50000' \\"
echo "      -F pickup_date='2026-07-20' \\"
echo "      -F post_to_trabox='yes'"
echo ""
echo "4️⃣  ログを確認"
echo "  $ gcloud run logs read poster --limit 50"
echo ""

echo "✅ デプロイメント完了！"
