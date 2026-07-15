# セットアップガイド

OneLogi-Post の開発環境をセットアップするための手順です。

## 前提条件

- Python 3.7 以上
- Git
- テキストエディタ

## 1. リポジトリのクローン

```bash
git clone https://github.com/hiroto-aves/Carroo.git
cd Carroo
```

## 2. 環境変数の設定

### 2.1 .env ファイルを作成

```bash
cp .env.example .env
```

### 2.2 .env ファイルを編集

```
DEBUG=False
DATABASE_URL=sqlite:///./carroo.db
SECRET_KEY=your-random-secret-key-here

# トラボックス設定
TRABOX_HEADLESS=True
TRABOX_TEST_USERNAME=your_test_username  # ← テストアカウントのユーザー名
TRABOX_TEST_PASSWORD=your_test_password  # ← テストアカウントのパスワード

# WebKIT API設定
WEBKIT_API_KEY=your_20_digit_api_key     # ← WebKIT APIキー
WEBKIT_PERSON_ID=your_14_digit_person_id # ← WebKIT 担当者ID
```

### 2.3 ファイルのパーミッション

`.env` ファイルが Git に追跡されていないことを確認：

```bash
git status | grep ".env"  # 何も出力されないこと
```

## 3. 仮想環境の構築

```bash
# 仮想環境を作成
python3 -m venv venv

# 仮想環境を有効化
source venv/bin/activate

# 依存パッケージをインストール
pip install -r requirements.txt

# Playwright ブラウザをインストール
playwright install chromium
```

## 4. データベースの初期化

```bash
python -c "from app.db.database import init_db; init_db(); print('✓ Database initialized')"
```

## 5. アプリケーションの起動

```bash
# 仮想環境が有効か確認
which python  # venv/bin/python を指し示すこと

# アプリケーションを起動
python main.py
```

ブラウザで http://localhost:8000 にアクセスしてください。

## 6. ログイン

デフォルトのテストユーザーでログイン：

- **Username**: admin
- **Password**: admin

または新規登録してアカウントを作成：

1. トップページから「登録する」をクリック
2. ユーザー名、メール、パスワードを入力
3. 「登録」をクリック
4. ログイン画面からログイン

## 7. テストアカウントの設定

トラボックスやWebKIT との自動投稿をテストする場合：

### トラボックスのテストアカウント

1. トラボックスの開発者ページからテストアカウントを作成
2. `.env` ファイルに認証情報を設定：
   ```
   TRABOX_TEST_USERNAME=your_test_username
   TRABOX_TEST_PASSWORD=your_test_password
   ```

### WebKIT API キー

1. WebKIT の公式ドキュメント参照：
   - `/Users/aves/Projects/Carroo/WebKIT API仕様書.xlsx`
2. APIキー（20桁）と担当者ID（14桁）を取得
3. `.env` ファイルに設定：
   ```
   WEBKIT_API_KEY=your_20_digit_key
   WEBKIT_PERSON_ID=your_14_digit_person_id
   ```

## 8. テストの実行

```bash
# データベース永続化テスト
python test_db_persistence.py

# 統合テスト
python test_integration.py

# バッチ投稿テスト
python test_batch_posting.py

# トラボックス要素検査テスト
python scripts/test_trabox_inspection.py
```

## 9. トラブルシューティング

### ポート 8000 が使用中

別のポートで起動：
```bash
uvicorn app.main:app --port 8001 --reload
```

### Playwright ブラウザのエラー

```bash
# ブラウザを再インストール
playwright install --with-deps chromium
```

### データベースエラー

```bash
# データベースをリセット
rm carroo.db
python -c "from app.db.database import init_db; init_db()"
```

### 環境変数が読み込まれない

```bash
# 仮想環境を再度有効化
deactivate
source venv/bin/activate

# python-dotenv が正しくインストールされているか確認
pip install python-dotenv
```

## 10. 本番環境へのデプロイ

本番環境でのセキュリティについては [SECURITY.md](./SECURITY.md) を参照してください。

### Docker を使用したデプロイ

```bash
# Dockerfile を使用してビルド
docker build -t onelogis-post:latest .

# コンテナを実行
docker run -p 8000:8000 --env-file .env.prod onelogis-post:latest
```

## 参考資料

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Playwright Documentation](https://playwright.dev/python/)
- [WebKIT API Specification](../WebKIT%20API仕様書.xlsx)
- [Security Guide](./SECURITY.md)
- [Project Progress](../PROGRESS.md)
