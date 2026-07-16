# 🚀 本番環境デプロイメント - 次のステップ

gcloud CLI のインストールは完了しました。ここからは **ユーザーが GCP アカウントで認証** する必要があります。

---

## 📋 進捗確認

### ✅ 完了
- [x] gcloud CLI インストール（`brew install google-cloud-sdk`）
- [x] PATH 設定（`.bashrc` に追加）
- [x] 実装コード完成（Cloud Tasks, Cloud Run, Playwright）
- [x] ローカルテスト成功（LocalTaskQueue で動作確認）
- [x] デプロイスクリプト作成
- [x] ドキュメント完備

### ⏳ 次に実行（ユーザー側）

---

## 🔐 Step 1: GCP アカウントで認証

### 1.1 gcloud をアクティベート

```bash
# ターミナルで実行
gcloud auth login

# ↓ ブラウザが開きます
# ↓ Google アカウントでログイン
# ↓ 「Cloud SDK が Cloud Platform プロジェクトへのアクセスをリクエストしています」
# ↓ 「許可」をクリック
```

### 1.2 認証完了確認

```bash
gcloud auth list

# 期待される出力:
#            ACTIVE  ACCOUNT
#     *             your-email@gmail.com
```

### 1.3 Application Default Credentials を設定

```bash
gcloud auth application-default login

# ↓ 再度ブラウザが開きます
# ↓ 「許可」をクリック
```

---

## 🏗️ Step 2: GCP プロジェクト作成

### 2.1 新規プロジェクト作成

```bash
# GCP Console で新規プロジェクトを作成
# https://console.cloud.google.com/projectcreate

# プロジェクト名: OneLogi-Post
# プロジェクト ID: aves-carroo-production
```

**またはコマンドラインで作成:**
```bash
gcloud projects create aves-carroo-production \
  --name="OneLogi-Post Production" \
  --set-as-default
```

### 2.2 プロジェクト ID を確認

```bash
gcloud config get-value project

# 出力例:
# aves-carroo-production
```

---

## 🚀 Step 3: 本番環境へデプロイ

### 3.1 環境変数確認

```bash
# .env ファイルが正しく設定されているか確認
cat .env | grep -E "TRABOX|WEBKIT"

# 未設定の場合は .env を編集
```

### 3.2 デプロイスクリプト実行

```bash
# プロジェクト ID を環境変数に設定
export GCP_PROJECT_ID="aves-carroo-production"

# デプロイ実行（約 5-10 分かかります）
./scripts/deploy_production.sh $GCP_PROJECT_ID

# 期待される出力:
# ✅ デプロイメント完了！
# Cloud Run URL: https://us-central1-aves-carroo-production.run.app/poster
```

---

## 📊 Step 4: 本番環境確認

### 4.1 Cloud Run サービスを確認

```bash
gcloud run services describe poster --region us-central1

# 期待される出力:
# Service name:  poster
# Region:        us-central1
# Status:        ✓ Ready
```

### 4.2 Cloud Tasks キューを確認

```bash
gcloud tasks queues describe posting-queue --location us-central1

# 期待される出力:
# state: RUNNING
# maxConcurrentDispatches: 1
```

### 4.3 ログを確認

```bash
gcloud run logs read poster --limit 10

# エラーがなければ正常です
```

---

## 🧪 Step 5: 実運用テスト

### 5.1 テスト投稿を実行

```bash
# Web UI で投稿
http://localhost:8000

# テストケース:
# - pick_location: 東京都
# - drop_location: 大阪府
# - cargo_weight: 100
# - vehicle_type: small_truck
# - freight_rate: 50000
# - post_to_trabox: ☑（チェック）
# - post_to_webkit: ☐（未チェック）

# 期待される結果:
# ✅ 即座に「投稿をキューに追加しました」と表示（< 1秒）
```

### 5.2 ログで投稿を確認

```bash
gcloud run logs read poster --follow

# 期待されるログ:
# 🚀 投稿処理開始
# ✅ 投稿成功
```

---

## 💰 Step 6: コスト確認

### 6.1 使用料金を確認

```bash
# GCP Console から確認
# https://console.cloud.google.com/billing

# または gcloud で確認
gcloud billing accounts list
```

### 6.2 無料枠内か確認

```
月額 ¥0 の理由:

5ユーザー × 1日5投稿 × 30日 = 150投稿/月

Cloud Functions: 200万リクエスト/月 >> 150リクエスト ✅
Cloud Tasks: 100万タスク/月 >> 150タスク ✅
Cloud Run: 180万 vCPU・秒/月 >> 11,250 vCPU・秒 ✅

合計: ¥0
```

---

## ✅ チェックリスト

実施状況:

- [ ] `gcloud auth login` を実行してログイン
- [ ] `gcloud auth list` で認証確認
- [ ] `gcloud auth application-default login` を実行
- [ ] GCP プロジェクト ID を取得
- [ ] `export GCP_PROJECT_ID="your-project-id"`
- [ ] `./scripts/deploy_production.sh $GCP_PROJECT_ID` を実行
- [ ] Cloud Run サービスが READY 状態か確認
- [ ] Cloud Tasks キューが RUNNING 状態か確認
- [ ] テスト投稿を実行
- [ ] ログで投稿処理を確認
- [ ] 月額費用が ¥0 か確認

---

## 🆘 トラブルシューティング

### ❌ `gcloud auth login` がタイムアウト

```bash
# ブラウザが開かない場合は --no-launch-browser を使用
gcloud auth login --no-launch-browser

# 表示される URL をブラウザで開く
```

### ❌ "No permission" エラー

```bash
# プロジェクトが存在するか確認
gcloud projects list

# プロジェクトを設定
gcloud config set project your-project-id

# 認証を再設定
gcloud auth login
```

### ❌ デプロイが失敗

```bash
# ローカルテストで確認
python test_cloud_tasks_local.py

# 詳細ログを確認
tail -f /tmp/deploy.log
```

---

## 📞 ドキュメント参照

- `PRODUCTION_QUICKSTART.md` - 5分クイックスタート
- `DEPLOYMENT_CHECKLIST.md` - 完全なチェックリスト
- `GCP_SETUP.md` - 詳細セットアップガイド
- `DEPLOYMENT.md` - デプロイメント全般ガイド

---

## 🎯 現在の状態

```
✅ 実装: 完成
✅ ローカルテスト: 成功
✅ ドキュメント: 完備
✅ gcloud CLI: インストール完了
⏳ GCP 認証: 次のステップ
⏳ 本番デプロイ: 準備完了・実行待ち
```

---

**次のアクション:**

```bash
# 1. GCP にログイン
gcloud auth login

# 2. プロジェクト ID を設定
export GCP_PROJECT_ID="your-project-id"

# 3. デプロイ実行
./scripts/deploy_production.sh $GCP_PROJECT_ID
```

**これだけで本番環境が起動します！🚀**
