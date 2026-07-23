# Carroo 本番デプロイ手順書（GCP Cloud Run）

最終更新: 2026-07-23

このドキュメントは Carroo を GCP Cloud Run に本番デプロイし、社用端末（Jamf Now 配信）で
アプリとして使えるようにするまでの手順です。

---

## 0. 前提と現在の状態

- **GCPプロジェクト**: `aves-carroo-production`（gcloud 認証済み）
- **アプリ構成**: 単一の FastAPI アプリ（Web UI ＋ 投稿ワーカー `/tasks/execute` 一体型）
- **投稿**: Trabox は Playwright（Chromium）でブラウザ操作、WebKit は XML API
- **認証**: 永続ログイン（10年＋スライディング更新）。端末紛失時はアカウント削除で無効化
- **PWA対応済み**: manifest・アイコン・メタタグ注入済み → ホーム画面追加でアプリ起動

---

## 1. データ永続化: Firestore（実質¥0・データ消失なし）

Carroo は **Firestore（Nativeモード）** にデータを保存する。Cloud Run のインスタンスは
使い捨てだが、Firestore は独立したマネージドDBのためデータは消えない。無料枠が大きく、
社内数名・低頻度なら**実質 ¥0**（Cloud SQL のような最低月額が無い）。

- ローカル開発: Firestore エミュレータ（`FIRESTORE_EMULATOR_HOST` 設定時に自動接続）
- 本番: Cloud Run のサービスアカウントで自動認証（ADC）

初回起動時に管理者アカウント（ユーザー名「管理者」）が自動作成される。
デプロイ後、管理者でログイン → 初期設定で Trabox/WebKit 認証情報・連絡先を登録する。

## 2. 事前準備（GCP API 有効化）

```bash
gcloud config set project aves-carroo-production

gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  cloudtasks.googleapis.com \
  secretmanager.googleapis.com \
  firestore.googleapis.com

# Firestore データベース作成（Nativeモード・初回のみ）
gcloud firestore databases create --location=us-central1 2>/dev/null || true
```

---

## 3. 認証情報（Secret）の登録

`.env` の値は Secret Manager に入れ、Cloud Run から参照します（環境変数直書きより安全）。

```bash
# 例: 主要シークレットを登録（値は実際の .env から）
for KEY in SECRET_KEY ENCRYPTION_KEY \
           TRABOX_TEST_USERNAME TRABOX_TEST_PASSWORD \
           WEBKIT_API_KEY WEBKIT_PERSON_ID WEBKIT_LOGIN_ID WEBKIT_LOGIN_PASSWORD \
           SMTP_HOST SMTP_PORT SMTP_USER SMTP_PASSWORD MAIL_FROM; do
  VALUE=$(grep "^$KEY=" .env | cut -d= -f2-)
  printf '%s' "$VALUE" | gcloud secrets create "$KEY" --data-file=- 2>/dev/null \
    || printf '%s' "$VALUE" | gcloud secrets versions add "$KEY" --data-file=-
done
```

---

## 4. デプロイ（Cloud Run）

```bash
gcloud run deploy carroo \
  --source . \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 2Gi --cpu 2 \
  --timeout 3600 \
  --min-instances 1 --max-instances 1 \
  --set-env-vars "COOKIE_SECURE=true,GCP_PROJECT_ID=aves-carroo-production" \
  --set-secrets "SECRET_KEY=SECRET_KEY:latest,ENCRYPTION_KEY=ENCRYPTION_KEY:latest,TRABOX_TEST_USERNAME=TRABOX_TEST_USERNAME:latest,TRABOX_TEST_PASSWORD=TRABOX_TEST_PASSWORD:latest,WEBKIT_API_KEY=WEBKIT_API_KEY:latest,WEBKIT_PERSON_ID=WEBKIT_PERSON_ID:latest,WEBKIT_LOGIN_ID=WEBKIT_LOGIN_ID:latest,WEBKIT_LOGIN_PASSWORD=WEBKIT_LOGIN_PASSWORD:latest,SMTP_HOST=SMTP_HOST:latest,SMTP_PORT=SMTP_PORT:latest,SMTP_USER=SMTP_USER:latest,SMTP_PASSWORD=SMTP_PASSWORD:latest,MAIL_FROM=MAIL_FROM:latest"
```

ポイント:
- `COOKIE_SECURE=true` … 本番HTTPSでCookieを暗号化通信限定に（**必須**）
- `--min/max-instances 1` … Trabox の同時実行回避（データは Firestore なので複数でも可だが順序実行のため1）
- `--memory 2Gi --cpu 2` … Playwright(Chromium) 起動のため
- `--timeout 3600` … 投稿は最大数十秒だが余裕を持たせる

デプロイ完了で `https://carroo-xxxxx-uc.a.run.app` のURLが払い出される。

---

## 5. Cloud Tasks（非同期投稿キュー）

順序実行（同時1件）のキューを作成し、受け先を Cloud Run の `/tasks/execute` に向ける。

```bash
gcloud tasks queues create posting-queue --location us-central1 \
  --max-concurrent-dispatches 1 --max-dispatches-per-second 1

# 払い出されたURLを CLOUD_RUN_URL に設定して再デプロイ（環境変数追加）
gcloud run services update carroo --region us-central1 \
  --update-env-vars "CLOUD_RUN_URL=https://carroo-xxxxx-uc.a.run.app/tasks/execute"
```

※ `GCP_PROJECT_ID` が設定されていると本アプリは自動で Cloud Tasks を使う。

---

## 6. 動作確認

1. `https://carroo-xxxxx-uc.a.run.app/auth/login` にアクセス
2. 管理者でログイン → 案件を1件登録（両方チェック、先日付）
3. 1〜2分後にメール受信＋ダッシュボードで成功確認 → テスト案件は削除

---

## 7. Jamf Now でアプリ配信

1. Jamf Now 管理画面 → **Web Clip（ウェブクリップ）** を作成
2. URL: 本番URL（`https://carroo-xxxxx-uc.a.run.app/dashboard/`）
3. アイコン: `static/icons/icon-192.png` をアップロード（または任意画像）
4. 対象端末（社用iPhone等）に配信
5. 端末のホーム画面にCarrooアイコンが追加され、タップでフルスクリーン起動

- 社内PC: ブラウザで本番URLをブックマーク、またはChromeで「アプリとしてインストール」
- 永続ログインのため、初回ログイン後は再ログイン不要

---

## 8. 運用メモ

- **アカウント無効化**: 端末紛失時は管理者がユーザー管理画面で該当ユーザーを削除
  → 次アクセスで即ログイン不能（サーバー側でユーザー存在を毎回確認）
- **月額コスト**: 方式Bなら Cloud Run 無料枠中心でほぼ¥0（min-instances 1 の常時起動分に注意）、
  方式Aは Cloud SQL 分が加算
- **再デプロイ**: コード更新後は `gcloud run deploy carroo --source . --region us-central1` を再実行

---
