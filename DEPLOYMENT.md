# デプロイメントガイド

本番環境へのデプロイメント前の確認事項とチェックリストです。

## 📋 本番環境チェックリスト

### セキュリティ
- [ ] `.env` ファイルが `.gitignore` に登録されている
- [ ] 機密情報が コミット履歴に含まれていない
  ```bash
  git log --all -- '.env' | wc -l  # 0 であること
  ```
- [ ] 環境変数が正しく設定されている
  - `SECRET_KEY`: 強力なランダム文字列に変更
  - `TRABOX_TEST_USERNAME`, `TRABOX_TEST_PASSWORD`: 本番アカウント
  - `WEBKIT_LOGIN_ID`, `WEBKIT_LOGIN_PASSWORD`: 本番アカウント
  - `WEBKIT_API_KEY`, `WEBKIT_PERSON_ID`: 本番 API キー

### 依存関係
- [ ] `requirements.txt` が最新版である
  ```bash
  pip freeze > requirements.txt
  ```
- [ ] すべての依存パッケージがインストール可能である
  ```bash
  pip install -r requirements.txt
  ```

### データベース
- [ ] SQLite データベースが初期化されている
  ```bash
  python -c "from app.db.database import init_db; init_db()"
  ```
- [ ] テーブルスキーマが正しい
  ```bash
  sqlite3 carroo.db ".schema"
  ```

### テスト
- [ ] 全テストが成功している
  ```bash
  python -m pytest test_*.py -v
  ```
- [ ] キーとなるテストを実行確認
  - `test_multi_platform_posting.py`: 複数プラットフォーム同時投稿 ✅
  - `test_trabox_live.py`: トラボックス実環境テスト ✅
  - `test_webkit_login.py`: WebKIT 自動ログイン ✅
  - `test_notifications.py`: プッシュ通知機能 ✅

### アプリケーション
- [ ] 構文チェックが成功している
  ```bash
  find app -name "*.py" -exec python -m py_compile {} +
  ```
- [ ] ドキュメントが完備されている
  - [x] README.md
  - [x] CLAUDE.md
  - [x] PROGRESS.md
  - [x] docs/SETUP.md
  - [x] docs/SECURITY.md
  - [x] DEPLOYMENT.md（本ファイル）

## 🚀 デプロイメント手順

### ローカル環境での最終確認
```bash
# 1. 仮想環境の構築
python3 -m venv venv
source venv/bin/activate

# 2. 依存関係のインストール
pip install -r requirements.txt

# 3. Playwright ブラウザのインストール
playwright install chromium

# 4. データベースの初期化
python -c "from app.db.database import init_db; init_db()"

# 5. 環境変数ファイルの設定
cp .env.example .env
# .env を編集して本番情報を入力

# 6. テストの実行
python test_multi_platform_posting.py
python test_trabox_live.py
python test_notifications.py

# 7. アプリケーション起動テスト
python main.py
# http://localhost:8000 でアクセス確認
```

### 本番環境へのデプロイ

#### Docker を使用する場合
```bash
# Dockerfile を作成
docker build -t carroo:latest .

# コンテナを実行
docker run -d \
  -p 8000:8000 \
  --env-file .env.prod \
  -v ./carroo.db:/app/carroo.db \
  carroo:latest

# 動作確認
curl http://localhost:8000
```

#### 直接デプロイする場合
```bash
# サーバーにアップロード
scp -r ./* user@server:/path/to/app

# サーバーで実行
ssh user@server
cd /path/to/app
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### nginx リバースプロキシ設定例
```nginx
upstream uvicorn {
    server localhost:8000;
}

server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://uvicorn;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 📊 本番環境推奨スペック

- **OS**: Linux（Ubuntu 20.04 LTS 以上）
- **Python**: 3.9 以上
- **メモリ**: 2GB 以上
- **ストレージ**: 10GB 以上（ログ・DBを考慮）
- **ネットワーク**: 安定した通信環境

## 🔍 本番環境での監視

### ログ監視
```bash
# アプリケーションログ
tail -f app.log

# エラーログ
tail -f error.log
```

### ヘルスチェック
```bash
curl http://your-domain.com/health
```

### パフォーマンス監視
- Prometheus + Grafana での監視
- New Relic / DataDog などの APM ツール

## 🚨 本番環境でのトラブルシューティング

### ブラウザ自動化が動作しない
```bash
# Playwright ブラウザの依存関係をインストール
playwright install --with-deps chromium
```

### データベースロック
```bash
# SQLite ロックファイルを削除
rm -f carroo.db-shm carroo.db-wal
```

### メモリ不足
```bash
# uvicorn のワーカー数を減らす
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

## 📝 ロールバック手順

デプロイ失敗時の対応：
```bash
# 前回のコミットに戻す
git revert <commit-hash>

# または
git reset --hard HEAD~1

# 本番環境を再起動
systemctl restart app
```

## 📞 サポート

問題が発生した場合：
1. [SETUP.md](./docs/SETUP.md) を確認
2. [SECURITY.md](./docs/SECURITY.md) でセキュリティ設定を確認
3. テストスクリプトで動作確認
4. ログを確認して原因を特定
