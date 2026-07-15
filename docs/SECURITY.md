# セキュリティガイド

## 環境変数の管理

このプロジェクトではセンシティブな情報（APIキー、ログイン認証情報など）を環境変数で管理しています。

### 📋 必須の環境変数

`.env.example` をコピーして、ローカル開発環境に `.env` ファイルを作成してください。

```bash
cp .env.example .env
```

### 🔐 .env ファイルの設定

`.env` ファイルには以下の情報を設定します：

```
# ==== トラボックス設定 ====
TRABOX_TEST_USERNAME=your_test_username
TRABOX_TEST_PASSWORD=your_test_password

# ==== WebKIT API設定 ====
WEBKIT_API_KEY=your_20_digit_key
WEBKIT_PERSON_ID=your_14_digit_id

# ==== その他設定 ====
SECRET_KEY=your_random_secret_key
```

### ⚠️ 重要な注意事項

1. **.env ファイルは Git でコミットしないこと**
   - `.gitignore` に `*.env` が登録されているため、自動的に除外されます
   - 確認: `git status` で `.env` が表示されないことを確認

2. **テストアカウントを使用すること**
   - 本番環境での実際のアカウント情報は絶対に使用しないこと
   - テスト用の別のアカウントを使用してください

3. **環境変数の検証**
   ```bash
   # 環境変数が正しく読み込まれているか確認
   python -c "from app.config import settings; print(f'API Key: {settings.WEBKIT_API_KEY[:10]}...')"
   ```

### 🔑 APIキー・認証情報の取得

#### WebKIT API
- 公式ドキュメント: `/Users/aves/Projects/Carroo/WebKIT API仕様書.xlsx`
- APIキー（20桁）と担当者ID（14桁）を取得してください

#### トラボックス
- テストアカウントを別途作成してください
- ユーザーID（ログインID）とパスワードを設定します

### 🛡️ 本番環境でのセキュリティ

本番環境では以下を実施してください：

1. **環境変数管理サービスを使用**
   - AWS Secrets Manager
   - Google Cloud Secret Manager
   - HashiCorp Vault
   - など

2. **機密情報のローテーション**
   - 定期的にパスワード・APIキーを変更
   - 漏洩時は即座に無効化

3. **アクセス制限**
   - 本番環境へのアクセスを最小限に
   - ロールベースのアクセス制御（RBAC）

4. **監査ログ**
   - すべてのAPI呼び出しをログに記録
   - 定期的なセキュリティ監査を実施

### 📝 Gitの状態確認

`.env` ファイルがGitに追跡されていないことを確認：

```bash
# ステージングエリアに .env がないことを確認
git status

# .env ファイルの履歴を確認しない
git log --oneline --all -- '.env' | wc -l  # 0 であること
```

### 🚨 セキュリティ違反の報告

もし機密情報がリポジトリに漏洩してしまった場合：

1. **即座に対応**
   ```bash
   # 履歴から削除（BFG Repo-Cleaner を使用）
   bfg --delete-files '.env'
   ```

2. **認証情報を無効化**
   - APIキーを再生成
   - パスワードを変更

3. **チーム全体に通知**
   - セキュリティインシデントとして報告

### ✅ チェックリスト

開発開始前に確認：

- [ ] `.env.example` をコピーして `.env` を作成した
- [ ] `.env` ファイルが `.gitignore` に登録されている
- [ ] 環境変数が正しく読み込まれている
- [ ] `git status` で `.env` が表示されない
- [ ] テストアカウント情報を使用している
- [ ] 本番環境の認証情報は `.env` に含めていない

### 参考資料

- [OWASP - Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [12 Factor App - Config](https://12factor.net/config)
- [Python python-dotenv Documentation](https://python-dotenv.readthedocs.io/)
