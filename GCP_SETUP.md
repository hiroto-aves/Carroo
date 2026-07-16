# GCP Cloud Tasks デプロイメント ガイド

Google Cloud Platform（GCP）に OneLogi-Post をデプロイするための完全ガイドです。

## 📋 前提条件

- GCP アカウント（無料枠で充分）
- gcloud CLI インストール済み
- Docker インストール済み
- Git インストール済み

## 🔧 セットアップ手順

### Step 1: GCP プロジェクト作成

```bash
# 1. GCP Console で新規プロジェクト作成
# https://console.cloud.google.com/projectcreate

# 2. gcloud で プロジェクトを設定
export GCP_PROJECT_ID="your-project-id"
gcloud config set project $GCP_PROJECT_ID

# 3. API を有効化
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable cloudrun.googleapis.com
gcloud services enable cloudtasks.googleapis.com
gcloud services enable logging.googleapis.com
gcloud services enable storage.googleapis.com
```

### Step 2: 認証情報セットアップ

```bash
# gcloud CLI でログイン
gcloud auth login

# Application Default Credentials を設定
gcloud auth application-default login

# 確認
gcloud auth list
```

### Step 3: 環境変数設定

```bash
# ローカル開発環境
cp .env.example .env

# .env ファイルを編集して以下を設定:
# GCP_PROJECT_ID=your-project-id
# TRABOX_TEST_USERNAME=your-username
# TRABOX_TEST_PASSWORD=your-password
# WEBKIT_LOGIN_ID=your-login-id
# WEBKIT_LOGIN_PASSWORD=your-password
# WEBKIT_API_KEY=your-api-key
# WEBKIT_PERSON_ID=your-person-id
```

### Step 4: ローカルテスト

```bash
# LocalTaskQueue を使ったテスト（GCP なしで動作確認）
python test_cloud_tasks_local.py

# 期待される出力:
# ✅ Local Task Queue テスト
# ✅ Database Posting History テスト
# ✅ 環境変数セットアップテスト
```

## 🚀 本番環境デプロイ

### デプロイスクリプト実行

```bash
# Cloud Run にデプロイ
./scripts/deploy_to_gcp.sh your-project-id

# 出力例:
# 🚀 GCP Cloud Run デプロイメント開始
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# プロジェクト ID: your-project-id
# ...
# ✅ Cloud Run デプロイ完了！
# 🎉 デプロイ情報
# Service URL: https://us-central1-your-project-id.run.app
```

### デプロイ後の確認

```bash
# Cloud Run サービスを確認
gcloud run services describe poster --region us-central1

# ログを確認
gcloud run logs read poster --limit 50

# Cloud Tasks キューを確認
gcloud tasks queues describe posting-queue --location us-central1
```

## 🧪 本番環境テスト

### テスト 1: Cloud Tasks キューが動作しているか確認

```bash
# キューの統計情報を確認
gcloud tasks queues describe posting-queue --location us-central1

# 出力項目:
# - name: posting-queue
# - state: RUNNING
# - maxConcurrentDispatches: 1
# - maxDispatchesPerSecond: 1
```

### テスト 2: Cloud Run が起動しているか確認

```bash
# ポスター関数にリクエストを送信
curl -X POST https://us-central1-your-project-id.run.app/poster \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -d '{
    "user_id": 1,
    "case_data": {
      "case_id": 999,
      "pick_location": "東京都",
      "drop_location": "大阪府",
      "cargo_weight": 100,
      "vehicle_type": "small_truck",
      "freight_rate": 50000,
      "pickup_date": "2026-07-20",
      "post_to_trabox": false,
      "post_to_webkit": false
    }
  }'

# 期待される応答:
# {
#   "case_id": 999,
#   "user_id": 1,
#   "total_platforms": 0,
#   "successful": 0,
#   "failed": 0,
#   "timestamp": "2026-07-16T12:34:56.789Z"
# }
```

### テスト 3: 統合テスト

```bash
# 本番環境でエンドツーエンドテストを実行
python test_cloud_tasks_e2e.py

# 期待される流れ:
# 1. Web UI に投稿リクエスト → 即座に返す
# 2. Cloud Tasks がタスクをキューに追加
# 3. Cloud Run が投稿処理を実行
# 4. posting_history に結果を記録
```

## 📊 モニタリング

### Cloud Logging

```bash
# 投稿エンジンのログを確認
gcloud run logs read poster --limit 100 --format json

# フィルター例：エラーログだけ表示
gcloud run logs read poster --limit 50 --format json | grep -i error
```

### Cloud Monitoring（Metrics）

```bash
# Cloud Console から確認
# https://console.cloud.google.com/monitoring

# メトリクス例:
# - cloud.run.operation_count
# - cloud.run.operation_latencies
# - cloud.tasks.queued_tasks
```

### Cloud Trace（分散トレース）

```bash
# Cloud Console から確認
# https://console.cloud.google.com/traces
```

## 🔐 セキュリティ設定

### Cloud Run の認証設定

```bash
# Cloud Tasks のみアクセス可能（本番推奨）
gcloud run services update poster \
  --region us-central1 \
  --no-allow-unauthenticated

# Service Account を指定
gcloud run services update poster \
  --region us-central1 \
  --service-account=cloud-tasks@your-project-id.iam.gserviceaccount.com
```

### Cloud Tasks の認証設定

```bash
# Cloud Tasks のための Service Account を作成
gcloud iam service-accounts create cloud-tasks \
  --display-name="Cloud Tasks Service Account"

# Cloud Run Invoker ロールを付与
gcloud run services add-iam-policy-binding poster \
  --member=serviceAccount:cloud-tasks@your-project-id.iam.gserviceaccount.com \
  --role=roles/run.invoker \
  --region=us-central1
```

## 💾 バックアップと復旧

### データベースのバックアップ

```bash
# SQLite DB を Google Cloud Storage にバックアップ
gsutil cp carroo.db gs://your-project-id-backups/carroo-$(date +%Y%m%d).db

# 定期バックアップを設定（cron）
# 0 2 * * * gsutil cp ~/app/carroo.db gs://your-project-id-backups/carroo-$(date +\%Y\%m\%d).db
```

### ログのエクスポート

```bash
# Cloud Logging から BigQuery へエクスポート
gcloud logging sinks create bigquery-export \
  bigquery.googleapis.com/projects/your-project-id/datasets/logs \
  --log-filter='resource.type="cloud_run_revision"'
```

## 🐛 トラブルシューティング

### Cloud Run がタイムアウト

**症状**: HTTP 504 Gateway Timeout

**原因**: Playwright ブラウザプロセスが起動に時間がかかっている

**対策**:
```bash
# メモリを増やす
gcloud run deploy poster \
  --memory 4Gi \
  --timeout 3600

# またはタイムアウトを延長
--timeout 7200  # 2時間
```

### Cloud Tasks が実行されない

**症状**: キューにタスクが溜まっている

**原因**: Cloud Run エラーまたはキュー設定

**対策**:
```bash
# キューを再作成
gcloud tasks queues delete posting-queue --location us-central1
gcloud tasks queues create posting-queue \
  --location us-central1 \
  --max-concurrent-dispatches 1 \
  --max-dispatches-per-second 1
```

### メモリ不足（OOM）

**症状**: Cloud Run コンテナが強制終了

**原因**: Playwright インスタンスが複数起動している

**対策**:
```bash
# 1. Cloud Run の設定を確認
gcloud run services describe poster --region us-central1

# 2. max-instances = 1 であることを確認
# 3. maxConcurrentDispatches = 1 であることを確認
```

## 📞 サポート

問題が発生した場合：

1. **ログを確認**
   ```bash
   gcloud run logs read poster --limit 100
   ```

2. **Cloud Console で確認**
   - Cloud Run: https://console.cloud.google.com/run
   - Cloud Tasks: https://console.cloud.google.com/cloudtasks
   - Logs: https://console.cloud.google.com/logs

3. **ローカルで再現**
   ```bash
   python test_cloud_tasks_local.py
   ```

## 💰 コスト確認

```bash
# GCP の無料枠を確認
# https://console.cloud.google.com/billing

# 現在の使用料金
gcloud billing accounts list
gcloud billing budgets list
```

## ✅ デプロイメント チェックリスト

- [ ] GCP プロジェクト作成
- [ ] API 有効化（Cloud Run, Cloud Tasks, Logging）
- [ ] 認証情報セットアップ（gcloud auth）
- [ ] 環境変数設定（.env）
- [ ] ローカルテスト成功（test_cloud_tasks_local.py）
- [ ] デプロイスクリプト実行（deploy_to_gcp.sh）
- [ ] Cloud Run デプロイ確認
- [ ] Cloud Tasks キュー作成確認
- [ ] 本番環境テスト成功（curl, e2e）
- [ ] モニタリング設定（Logging, Monitoring）
- [ ] バックアップ設定
- [ ] セキュリティ設定確認

---

**プロジェクト**: OneLogi-Post  
**バージョン**: Step 17  
**最終更新**: 2026-07-16  
**ステータス**: 本番デプロイ準備完了 ✅
