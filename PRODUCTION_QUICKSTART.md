# 🚀 本番環境デプロイメント クイックスタート

GCP に OneLogi-Post をデプロイするための **最短パス** ガイド。

---

## ⚡ 5分で開始

### Step 1: GCP プロジェクト作成（2分）

```bash
# GCP Console で新規プロジェクトを作成
# https://console.cloud.google.com/projectcreate
# プロジェクト ID: carroo-production

# ローカルでプロジェクトを設定
export GCP_PROJECT_ID="carroo-production"
gcloud config set project $GCP_PROJECT_ID
gcloud auth login
gcloud auth application-default login
```

### Step 2: 環境変数を設定（1分）

```bash
# .env ファイルを確認
cat .env | grep -E "GCP_|TRABOX|WEBKIT"

# すべての変数が設定されていることを確認
# 未設定の場合は .env を編集
```

### Step 3: ローカルテスト（1分）

```bash
# ローカルで正常に動作することを確認
python test_cloud_tasks_local.py

# 期待される出力:
# ✅ Local Task Queue テスト完了
# ✅ Database Posting History テスト完了
```

### Step 4: 本番環境へデプロイ（1分）

```bash
# デプロイスクリプトを実行
# 自動的に以下が実行されます:
# - gcloud API を有効化
# - Docker イメージをビルド
# - Cloud Run にデプロイ
# - Cloud Tasks キューを作成

./scripts/deploy_production.sh $GCP_PROJECT_ID

# 出力例:
# ✅ デプロイメント完了！
# Cloud Run URL: https://us-central1-carroo-production.run.app/poster
```

---

## 📊 デプロイ後の確認

### ✅ 1. Cloud Run が起動しているか確認

```bash
gcloud run services describe poster --region us-central1

# 期待される出力:
# Status: ✓ Ready
```

### ✅ 2. Cloud Tasks キューが作成されたか確認

```bash
gcloud tasks queues describe posting-queue --location us-central1

# 期待される出力:
# state: RUNNING
# maxConcurrentDispatches: 1
```

### ✅ 3. ログを確認

```bash
gcloud run logs read poster --limit 10

# エラーがなければ正常です
```

---

## 🧪 実運用テスト

### テスト 1: Web UI で投稿してみる

```bash
# Web UI にアクセス
http://localhost:8000

# または本番 URL にアクセス
# http://your-domain.com

# テスト投稿:
# - pick_location: 東京都
# - drop_location: 大阪府
# - cargo_weight: 100
# - vehicle_type: small_truck
# - freight_rate: 50000
# - pickup_date: 2026-07-20
# - post_to_trabox: ☑（チェック）
# - post_to_webkit: ☐（未チェック）

# ✅ 期待される結果:
# - 即座に「投稿をキューに追加しました ✅」と表示
# - HTTP 202 で返す
```

### テスト 2: 投稿履歴で status を確認

```bash
# ダッシュボード → 投稿履歴
# Status が以下のように変わるか確認:

# 0-1秒: pending    （投稿待機中）
# 1-10秒: success   （投稿完了）
```

### テスト 3: ログで実行確認

```bash
# リアルタイムログを確認
gcloud run logs read poster --follow

# 期待されるログ:
# 🚀 投稿処理開始: Case ID 1
# 📦 トラボックス投稿開始
# ✅ 投稿成功
```

---

## 💰 運用コスト確認

### 月額 ¥0 の理由

```
【使用量の計算】
5ユーザー × 1日5投稿 × 30日 = 150投稿/月

【GCP 無料枠】
- Cloud Functions: 200万リクエスト/月 >> 150リクエスト ✅
- Cloud Tasks: 100万タスク/月 >> 150タスク ✅
- Cloud Run: 180万 vCPU・秒/月 >> 11,250 vCPU・秒 ✅

【結果】
合計月額: ¥0
```

### コスト監視

```bash
# GCP の課金を確認
# https://console.cloud.google.com/billing

# 無料枠の使用状況
gcloud billing accounts list
```

---

## 🔧 よくあるトラブル

### ❌ デプロイ失敗: "Address already in use"

```bash
# ポート 8000 が使用中の場合
lsof -i :8000
kill -9 <PID>
```

### ❌ Cloud Run でタイムアウト: "504 Gateway Timeout"

```bash
# メモリを増やす
gcloud run deploy poster \
  --memory 4Gi \
  --timeout 7200 \
  --region us-central1
```

### ❌ 投稿が実行されない

```bash
# 1. ログを確認
gcloud run logs read poster --limit 50

# 2. キューの状態を確認
gcloud tasks queues describe posting-queue --location us-central1

# 3. 環境変数が設定されているか確認
gcloud run services describe poster --region us-central1 \
  --format='value(spec.template.spec.containers[0].env)'
```

### ❌ 認証エラー: "No permission"

```bash
# gcloud 認証を再設定
gcloud auth login
gcloud auth application-default login

# Cloud Run の認証設定を確認
gcloud run services get-iam-policy poster --region us-central1
```

---

## 📝 デプロイ情報の記録

```bash
# デプロイ情報を記録
cat > DEPLOYMENT_INFO.txt << EOF
デプロイメント日時: $(date)
GCP Project ID: $GCP_PROJECT_ID
Cloud Run URL: $(gcloud run services describe poster --region us-central1 --format='value(status.url)')
Queue: posting-queue
Region: us-central1
Status: ✅ 本番運用中
EOF

# Git に記録
git add DEPLOYMENT_INFO.txt
git commit -m "Record: Production deployment on $(date +%Y-%m-%d)"
git push origin main
```

---

## 🎯 本番環境チェックリスト

実施項目:
- [ ] GCP プロジェクト作成
- [ ] gcloud 認証設定
- [ ] 環境変数設定確認
- [ ] ローカルテスト実行
- [ ] デプロイスクリプト実行
- [ ] Cloud Run 確認
- [ ] Cloud Tasks 確認
- [ ] テスト投稿実行
- [ ] ログ確認
- [ ] 投稿履歴確認
- [ ] コスト確認（¥0）

---

## 📞 サポート

問題が発生した場合:

```bash
# 1. ローカルテストで確認
python test_cloud_tasks_local.py

# 2. ログを確認
gcloud run logs read poster --limit 50

# 3. ドキュメントを確認
# GCP_SETUP.md - 詳細セットアップガイド
# DEPLOYMENT_CHECKLIST.md - 完全チェックリスト
# DEPLOYMENT.md - デプロイメントガイド

# 4. GitHub リポジトリの Issues
# https://github.com/hiroto-aves/Carroo/issues
```

---

## 🎉 デプロイメント完了

**おめでとうございます！**

OneLogi-Post が本番環境で稼働しています。

- **Web UI**: http://localhost:8000 または本番 URL
- **Cloud Run**: https://us-central1-your-project.run.app/poster
- **Cloud Tasks**: posting-queue
- **月額コスト**: ¥0

### 次のステップ

1. **運用開始**: チームがアプリを使用開始
2. **監視設定**: Cloud Monitoring ダッシュボード
3. **バックアップ**: 定期的なDB バックアップ設定
4. **スケーリング**: 必要に応じてリソース調整

---

**プロジェクト**: OneLogi-Post  
**バージョン**: Step 17 + 本番環境デプロイ  
**ステータス**: ✅ 本番運用中  
**コスト**: ¥0/月
