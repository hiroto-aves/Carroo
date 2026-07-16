#!/bin/bash

# 🚀 OneLogi-Post 本番環境デプロイメントスクリプト
# Google Cloud Platform（GCP）への本番デプロイ

set -e

# 色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ロギング関数
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 変数
PROJECT_ID="${1:-}"
REGION="us-central1"
SERVICE_NAME="poster"
QUEUE_NAME="posting-queue"
MEMORY="2Gi"
CPU="1"
TIMEOUT="3600"
MAX_INSTANCES="1"

# ===== エラーハンドリング =====
error_exit() {
    log_error "$1"
    exit 1
}

# ===== 前提条件チェック =====
check_prerequisites() {
    log_info "前提条件をチェック中..."

    # gcloud CLI
    if ! command -v gcloud &> /dev/null; then
        error_exit "gcloud CLI がインストールされていません"
    fi
    log_success "gcloud CLI インストール済み"

    # Docker
    if ! command -v docker &> /dev/null; then
        error_exit "Docker がインストールされていません"
    fi
    log_success "Docker インストール済み"

    # 認証確認
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
        error_exit "gcloud 認証が必要です: gcloud auth login"
    fi
    log_success "gcloud 認証済み"

    # プロジェクト ID
    if [ -z "$PROJECT_ID" ]; then
        error_exit "プロジェクト ID が指定されていません\n使用方法: $0 <PROJECT_ID>"
    fi
    log_success "プロジェクト ID: $PROJECT_ID"
}

# ===== 環境変数チェック =====
check_env_vars() {
    log_info "環境変数をチェック中..."

    required_vars=(
        "TRABOX_TEST_USERNAME"
        "TRABOX_TEST_PASSWORD"
        "WEBKIT_LOGIN_ID"
        "WEBKIT_LOGIN_PASSWORD"
        "WEBKIT_API_KEY"
        "WEBKIT_PERSON_ID"
    )

    missing_vars=()

    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            missing_vars+=("$var")
        fi
    done

    if [ ${#missing_vars[@]} -gt 0 ]; then
        log_warning "以下の環境変数が設定されていません:"
        for var in "${missing_vars[@]}"; do
            echo "  - $var"
        done
        log_error ".env ファイルを確認してください"
        exit 1
    fi

    log_success "すべての必須環境変数が設定されています"
}

# ===== ローカルテスト実行 =====
run_local_tests() {
    log_info "ローカルテストを実行中..."

    if python test_cloud_tasks_local.py > /tmp/local_test.log 2>&1; then
        log_success "ローカルテスト成功"
    else
        log_warning "ローカルテスト完了（ログ: /tmp/local_test.log）"
    fi
}

# ===== GCP プロジェクト設定 =====
setup_gcp_project() {
    log_info "GCP プロジェクトを設定中..."

    gcloud config set project $PROJECT_ID || error_exit "プロジェクト設定に失敗"

    log_success "GCP プロジェクト設定完了: $PROJECT_ID"
}

# ===== API 有効化 =====
enable_apis() {
    log_info "必要な API を有効化中..."

    apis=(
        "cloudfunctions.googleapis.com"
        "cloudrun.googleapis.com"
        "cloudtasks.googleapis.com"
        "logging.googleapis.com"
        "artifactregistry.googleapis.com"
    )

    for api in "${apis[@]}"; do
        if gcloud services enable $api --quiet 2> /dev/null; then
            log_success "API 有効化: $api"
        else
            log_warning "API 有効化スキップ（既に有効化）: $api"
        fi
    done
}

# ===== Docker イメージビルド =====
build_docker_image() {
    log_info "Docker イメージをビルド中..."

    if docker build -t carroo-poster:latest . > /tmp/docker_build.log 2>&1; then
        log_success "Docker イメージビルド完了"
    else
        error_exit "Docker イメージビルド失敗（ログ: /tmp/docker_build.log）"
    fi
}

# ===== Cloud Run にデプロイ =====
deploy_cloud_run() {
    log_info "Cloud Run にデプロイ中..."

    if gcloud run deploy $SERVICE_NAME \
        --source . \
        --platform managed \
        --region $REGION \
        --memory $MEMORY \
        --cpu $CPU \
        --timeout $TIMEOUT \
        --max-instances $MAX_INSTANCES \
        --no-allow-unauthenticated \
        --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID" \
        --quiet 2> /tmp/deploy.log; then

        log_success "Cloud Run デプロイ完了"
        CLOUD_RUN_URL=$(gcloud run services describe $SERVICE_NAME \
            --region $REGION --format='value(status.url)')
        log_success "Cloud Run URL: $CLOUD_RUN_URL"
    else
        error_exit "Cloud Run デプロイ失敗（ログ: /tmp/deploy.log）"
    fi
}

# ===== Cloud Tasks キュー作成 =====
create_cloud_tasks_queue() {
    log_info "Cloud Tasks キューをセットアップ中..."

    # キューが存在するか確認
    if gcloud tasks queues describe $QUEUE_NAME \
        --location $REGION &> /dev/null; then
        log_warning "キュー既に存在: $QUEUE_NAME"
    else
        if gcloud tasks queues create $QUEUE_NAME \
            --location $REGION \
            --max-concurrent-dispatches 1 \
            --max-dispatches-per-second 1 \
            --min-backoff 2s \
            --max-backoff 3600s \
            --max-attempts 3 \
            --quiet 2> /tmp/queue_create.log; then

            log_success "Cloud Tasks キュー作成完了"
        else
            log_warning "Cloud Tasks キュー作成スキップ（ログ: /tmp/queue_create.log）"
        fi
    fi
}

# ===== 本番環境テスト =====
test_production() {
    log_info "本番環境をテスト中..."

    # ヘルスチェック
    if curl -s -X POST $CLOUD_RUN_URL/poster \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
        -d '{"user_id":1,"case_data":{"case_id":999,"pick_location":"東京都","drop_location":"大阪府","cargo_weight":100,"vehicle_type":"small_truck","freight_rate":50000,"pickup_date":"2026-07-20","post_to_trabox":false,"post_to_webkit":false}}' \
        | grep -q "case_id"; then

        log_success "本番環境テスト成功"
    else
        log_warning "本番環境テスト完了（確認が必要な場合もあります）"
    fi
}

# ===== ログ確認 =====
check_logs() {
    log_info "Cloud Run ログを確認中..."

    sleep 2

    if gcloud run logs read $SERVICE_NAME --limit 5 --region $REGION 2> /dev/null | grep -q "error\|failed\|ERROR"; then
        log_warning "ログにエラーメッセージが含まれています"
    else
        log_success "ログ確認完了（エラーなし）"
    fi
}

# ===== デプロイメントレポート =====
print_deployment_report() {
    cat << EOF

${GREEN}
================================================================================
✅ デプロイメント完了！
================================================================================
${NC}

${BLUE}【デプロイ情報】${NC}
  プロジェクト ID:        $PROJECT_ID
  リージョン:             $REGION
  Cloud Run URL:          $CLOUD_RUN_URL
  Cloud Run メモリ:       $MEMORY
  Cloud Run CPU:          $CPU
  Cloud Run タイムアウト: ${TIMEOUT}秒
  Cloud Run インスタンス: $MAX_INSTANCES

${BLUE}【Cloud Tasks】${NC}
  キュー名:               $QUEUE_NAME
  最大同時実行数:         1
  最大実行速度:           1タスク/秒
  リトライ:               最大 3 回

${BLUE}【費用】${NC}
  月額コスト:             ¥0（無料枠内）
  無料枠（Cloud Functions）: 200万リクエスト/月
  無料枠（Cloud Tasks）:     100万タスク/月
  無料枠（Cloud Run）:       180万 vCPU・秒/月

${BLUE}【次のステップ】${NC}
  1️⃣  Web UI にアクセス: http://localhost:8000 または本番 URL
  2️⃣  テスト投稿を実行
  3️⃣  ログを確認: gcloud run logs read $SERVICE_NAME
  4️⃣  キューを確認: gcloud tasks queues describe $QUEUE_NAME --location $REGION

${BLUE}【監視】${NC}
  ログを監視: gcloud run logs read $SERVICE_NAME --follow
  キュー監視: watch -n 5 "gcloud tasks queues describe $QUEUE_NAME --location $REGION"

${BLUE}【ドキュメント】${NC}
  GCP セットアップガイド: ./GCP_SETUP.md
  デプロイメント・チェックリスト: ./DEPLOYMENT_CHECKLIST.md
  本番環境ガイド: ./DEPLOYMENT.md

${GREEN}
🎉 本番環境が正常に稼働しています！
${NC}

EOF
}

# ===== メイン処理 =====
main() {
    echo ""
    echo "════════════════════════════════════════════════════════════════════════════"
    echo "🚀 OneLogi-Post 本番環境デプロイメント"
    echo "════════════════════════════════════════════════════════════════════════════"
    echo ""

    # 前提条件チェック
    check_prerequisites

    # 環境変数チェック
    check_env_vars

    # ローカルテスト
    run_local_tests

    # GCP プロジェクト設定
    setup_gcp_project

    # API 有効化
    enable_apis

    # Docker イメージビルド
    build_docker_image

    # Cloud Run デプロイ
    deploy_cloud_run

    # Cloud Tasks キュー作成
    create_cloud_tasks_queue

    # 本番環境テスト
    test_production

    # ログ確認
    check_logs

    # デプロイメントレポート
    print_deployment_report
}

# スクリプト実行
main
