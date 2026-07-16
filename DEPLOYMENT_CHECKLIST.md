# 🚀 本番環境デプロイメント チェックリスト

物流案件一括投稿アプリ（Carroo）を GCP にデプロイするための完全チェックリストです。

---

## 📋 Phase 1: 準備（30分）

### 1.1 GCP プロジェクト作成
- [ ] GCP Console にアクセス: https://console.cloud.google.com
- [ ] 新規プロジェクトを作成（プロジェクト名: `carroo-production`）
- [ ] プロジェクト ID をメモ: `your-project-id`

### 1.2 gcloud CLI セットアップ
```bash
# gcloud のバージョン確認
gcloud --version

# ログイン
gcloud auth login

# Application Default Credentials を設定
gcloud auth application-default login

# プロジェクトを設定
gcloud config set project your-project-id

# 確認
gcloud config list
```

**チェック:**
- [ ] `gcloud config list` で正しいプロジェクト ID が表示されている

### 1.3 必要な API を有効化
```bash
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable cloudrun.googleapis.com
gcloud services enable cloudtasks.googleapis.com
gcloud services enable logging.googleapis.com
gcloud services enable artifactregistry.googleapis.com
```

**チェック:**
- [ ] すべての API が正常に有効化されたか確認

---

## 📋 Phase 2: 環境変数設定（15分）

### 2.1 .env ファイルを設定
```bash
# ローカルで .env を確認
cat .env | grep -E "GCP_|TRABOX|WEBKIT"
```

**必須環境変数:**
- [ ] `GCP_PROJECT_ID` = `your-project-id`
- [ ] `TRABOX_TEST_USERNAME` = トラボックスのユーザー名
- [ ] `TRABOX_TEST_PASSWORD` = トラボックスのパスワード
- [ ] `WEBKIT_LOGIN_ID` = WebKIT のログイン ID
- [ ] `WEBKIT_LOGIN_PASSWORD` = WebKIT のパスワード
- [ ] `WEBKIT_API_KEY` = WebKIT の API キー
- [ ] `WEBKIT_PERSON_ID` = WebKIT の担当者 ID

### 2.2 本番環境用 .env.prod を作成
```bash
# ローカルの .env をコピーして本番用に
cp .env .env.prod

# Cloud Run にアップロード時に使用
# gcloud run deploy ... --env-file .env.prod
```

**チェック:**
- [ ] `.env.prod` が作成されている
- [ ] すべての必須変数が設定されている

---

## 📋 Phase 3: ローカル検証（30分）

### 3.1 ローカルテスト実行
```bash
# LocalTaskQueue でテスト
python test_cloud_tasks_local.py
```

**期待される出力:**
```
✅ Local Task Queue テスト完了
✅ Database Posting History テスト完了
🎉 すべてのテストが完了しました
```

**チェック:**
- [ ] ローカルテスト成功

### 3.2 Web UI 起動テスト
```bash
# Web UI を起動
python main.py

# 別ターミナルでヘルスチェック
curl http://localhost:8000/health
```

**期待される応答:**
```json
{"status":"ok","message":"OneLogi-Post backend is running"}
```

**チェック:**
- [ ] Web UI が起動している
- [ ] ヘルスチェック HTTP 200

### 3.3 ポスター関数（ローカルシミュレーション）
```bash
# Cloud Run ポスター関数をローカルでテスト
python functions/poster.py
```

**期待される出力:**
```
POST TO PLATFORMS - Test Case
```

**チェック:**
- [ ] ポスター関数がエラーなく実行できる

---

## 📋 Phase 4: GCP デプロイ（45分）

### 4.1 Docker イメージをビルド
```bash
# ローカルでビルド
docker build -t carroo-poster:latest .

# イメージを確認
docker images | grep carroo-poster
```

**チェック:**
- [ ] Docker イメージがビルドされている

### 4.2 デプロイスクリプトを実行
```bash
# デプロイを実行
export GCP_PROJECT_ID="your-project-id"
./scripts/deploy_to_gcp.sh $GCP_PROJECT_ID
```

**期待される出力:**
```
🚀 GCP Cloud Run デプロイメント開始
...
✅ Cloud Run デプロイ完了！
✅ Cloud Tasks キュー作成完了
```

**デプロイスクリプトが実行する処理:**
1. Cloud Run にコンテナをデプロイ
2. Cloud Tasks キューを自動作成
3. 設定を自動確認

**チェック:**
- [ ] デプロイスクリプト実行成功

### 4.3 デプロイ結果を確認
```bash
# Cloud Run サービスを確認
gcloud run services describe poster --region us-central1

# 出力例:
# Service name:  poster
# Region:        us-central1
# URL:           https://us-central1-your-project-id.run.app/
# Status:        ✓ Ready
```

**チェック:**
- [ ] Cloud Run サービス「poster」が READY 状態
- [ ] URL が表示されている

### 4.4 Cloud Tasks キューを確認
```bash
# キューを確認
gcloud tasks queues describe posting-queue --location us-central1

# 出力例:
# name: projects/your-project-id/locations/us-central1/queues/posting-queue
# state: RUNNING
# maxConcurrentDispatches: 1
# maxDispatchesPerSecond: 1
```

**チェック:**
- [ ] キュー「posting-queue」が RUNNING 状態
- [ ] `maxConcurrentDispatches: 1` に設定されている
- [ ] `maxDispatchesPerSecond: 1` に設定されている

---

## 📋 Phase 5: 本番環境テスト（30分）

### 5.1 ポスター関数のヘルスチェック
```bash
# Cloud Run URL を取得
CLOUD_RUN_URL=$(gcloud run services describe poster \
  --region us-central1 --format='value(status.url)')

# ヘルスチェック（テストなし）
curl -X POST $CLOUD_RUN_URL/poster \
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
```

**期待される応答:**
```json
{
  "case_id": 999,
  "user_id": 1,
  "total_platforms": 0,
  "successful": 0,
  "failed": 0,
  "timestamp": "2026-07-16T12:34:56.789Z"
}
```

**チェック:**
- [ ] HTTP 200 で応答が返ってくる

### 5.2 ログを確認
```bash
# 最近のログを表示
gcloud run logs read poster --limit 50

# エラーログだけ表示
gcloud run logs read poster --limit 50 | grep -i error
```

**期待される出力:**
- エラーがない
- または正常なログが表示されている

**チェック:**
- [ ] ログにエラーがない

### 5.3 キューの状態を確認
```bash
# キュー内のタスク数を確認
gcloud tasks queues describe posting-queue --location us-central1 \
  --format="value(stats)"
```

**期待される出力:**
```
tasks_run: 0
total_leased_count: 0
oldest_scheduled_time: N/A
```

**チェック:**
- [ ] キューが正常に動作している

---

## 📋 Phase 6: 実運用テスト（30分）

### 6.1 実際の案件を投稿（テスト投稿）
```bash
# Web UI にアクセス
# http://localhost:8000 または本番 URL

# テストユーザーで登録・ログイン
# テスト投稿を実行（投稿先は「トラボックスなし」で）
# → 即座に「投稿をキューに追加しました」と表示されるか確認
```

**チェック:**
- [ ] 投稿リクエストが即座に返ってくる（< 1秒）
- [ ] HTTP 202 で「キューに追加」メッセージが返ってくる
- [ ] case_id がレスポンスに含まれている

### 6.2 投稿履歴を確認
```bash
# Web UI のダッシュボードで投稿履歴を確認
# Status: pending → (数秒後) → success に変わるか確認
```

**チェック:**
- [ ] 投稿履歴が DB に記録されている
- [ ] Status が「pending」から「success」に更新されている

### 6.3 ログで動作確認
```bash
# Cloud Run ログを確認
gcloud run logs read poster --limit 50 --follow

# 投稿処理のログが表示されるか確認
# ✅ 投稿開始
# ✅ 投稿完了
# ✅ 結果を DB に記録
```

**チェック:**
- [ ] ログに投稿処理のメッセージが表示されている

---

## 📋 Phase 7: 監視・ログ設定（15分）

### 7.1 Cloud Logging ダッシュボードを設定
```bash
# Cloud Console で以下を確認
# https://console.cloud.google.com/logs

# ログフィルター例:
# resource.type="cloud_run_revision"
# resource.labels.service_name="poster"
```

**チェック:**
- [ ] ログが Cloud Logging に記録されている

### 7.2 アラート設定（オプション）
```bash
# エラーが発生した場合にメール通知を設定
# Cloud Console > Monitoring > Alerting policies
# → Notification channels を設定
```

**チェック:**
- [ ] メール通知の設定を確認（オプション）

### 7.3 ダッシュボード作成（オプション）
```bash
# Cloud Monitoring ダッシュボードを作成
# メトリクス例:
# - cloud.run.operation_count
# - cloud.run.operation_latencies
# - cloud.tasks.queued_tasks
```

**チェック:**
- [ ] ダッシュボードが表示されている（オプション）

---

## 📋 Phase 8: 本番環境確認（15分）

### 8.1 最終確認チェック
```bash
# 1. サービス状態を確認
gcloud run services describe poster --region us-central1 | grep Status

# 2. キュー状態を確認
gcloud tasks queues describe posting-queue --location us-central1 | grep state

# 3. 最新ログを確認
gcloud run logs read poster --limit 10
```

**チェック:**
- [ ] Cloud Run Status: ✓ Ready
- [ ] Queue state: RUNNING
- [ ] ログにエラーがない

### 8.2 ドキュメント更新
```bash
# デプロイ情報を記録
echo "
GCP Project ID: $GCP_PROJECT_ID
Cloud Run URL: $(gcloud run services describe poster --region us-central1 --format='value(status.url)')
Queue Name: posting-queue
Region: us-central1
Deployed: $(date)
" >> DEPLOYMENT_RECORD.txt
```

**チェック:**
- [ ] DEPLOYMENT_RECORD.txt に情報が記録されている

### 8.3 チーム通知
```bash
# デプロイ完了を通知
echo "✅ 本番環境デプロイ完了

Cloud Run: $(gcloud run services describe poster --region us-central1 --format='value(status.url)')
Queue: posting-queue (maxConcurrentDispatches: 1)
コスト: ¥0/月（無料枠内）

テスト完了。運用開始可能。"
```

**チェック:**
- [ ] デプロイ完了を確認

---

## 📊 チェックリスト完了確認

### 完了した Phase
- [ ] Phase 1: 準備
- [ ] Phase 2: 環境変数設定
- [ ] Phase 3: ローカル検証
- [ ] Phase 4: GCP デプロイ
- [ ] Phase 5: 本番環境テスト
- [ ] Phase 6: 実運用テスト
- [ ] Phase 7: 監視・ログ設定
- [ ] Phase 8: 本番環境確認

### 最終確認
- [ ] すべてのテストが成功している
- [ ] ログにエラーがない
- [ ] 投稿フロー（リクエスト → キュー追加 → 投稿実行）が正常に動作している
- [ ] 月額コスト ¥0 であることを確認

---

## 🎉 デプロイメント完了

本番環境への デプロイが完了しました！

### 運用開始
- **Web UI**: http://localhost:8000 または 本番 URL
- **Cloud Run**: https://us-central1-your-project-id.run.app/poster
- **Cloud Tasks**: posting-queue（maxConcurrentDispatches: 1）
- **ログ**: Cloud Logging（gcloud run logs read poster）

### 次のステップ
1. **定期バックアップ**: `gsutil cp carroo.db gs://bucket-name/backup/`
2. **ログ監視**: Cloud Monitoring ダッシュボード
3. **セキュリティ**: Cloud Run の認証設定確認
4. **スケーリング**: 必要に応じて Cloud Run のメモリを増加

---

**デプロイメント日時**: [記入してください]  
**デプロイ担当者**: [記入してください]  
**GCP Project ID**: your-project-id  
**ステータス**: ✅ 本番運用中
