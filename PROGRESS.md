# Progress Tracking

## ⏳ バックログ (未着手)
- [ ] Playwright ブラウザの実際のインストール＆テスト
- [ ] トラボックス自動ログイン＆投稿ロジックの詳細実装（`playwright codegen` を活用）
- [ ] Webkit API キー設定とエンドツーエンドテスト
- [ ] セッション管理・認証トークン実装
- [ ] エラーハンドリング・スクリーンショット保存機能の改善
- [ ] ユーザー認証画面の仕上げ（セッション管理、ログアウト）
- [ ] データベース永続化テスト
- [ ] フロントエンドの UX 改善（デザイン・レスポンシブ対応）

## 🔄 進行中 (In Progress)
- [ ] なし

## ✅ 完了 (Completed)
- [x] 新要件の定義と技術選定の刷新 (FastAPI + Playwright + Tailwind CSS)
- [x] `README.md`, `claude.md`, `PROGRESS.md` の作成
- [x] GitHub リポジトリの初期化・連携
- [x] バックエンド基本環境構築
  - [x] Python venv 仮想環境の作成
  - [x] FastAPI, Uvicorn, Playwright, python-multipart のインストール
  - [x] `requirements.txt` の生成
- [x] プロジェクト構造の整備
  - [x] `app/`, `static/`, `templates/` ディレクトリの作成
  - [x] モジュール分離（routers, automations, models, db）
- [x] FastAPI アプリケーション骨組み実装
  - [x] `app/main.py` でアプリケーションオブジェクト生成
  - [x] `app/config.py` で環境変数・設定管理
  - [x] `app/db/database.py` で SQLite 接続・テーブル初期化
  - [x] `app/models/schemas.py` で Pydantic データモデル定義
- [x] ルーター実装
  - [x] `app/routers/auth.py` - ログイン・登録画面＆エンドポイント
  - [x] `app/routers/cases.py` - 案件登録画面＆投稿ロジック
- [x] 自動投稿モジュール（スケルトン）
  - [x] `app/automations/trabox.py` - Playwright ベースの自動ログイン・投稿
  - [x] `app/automations/webkit.py` - Webhook API 投稿モジュール
- [x] エントリーポイント
  - [x] `main.py` を作成（`uvicorn` で起動可能）
- [x] `.env.example` ファイル作成

## 📝 開発メモ
- Python 3.7.11 で環境構築（要件は 3.11+ だが、互換性あり）
- トラボックスのログイン画面は `name="loginid"`, `name="loginpwd"`、ログインボタンは「ログイン」のテキストを持つ `<span>` であることが判明している。
- 以前のSelenium実装時にMacのGatekeeper（マルウェア検証エラー）に遭遇したため、Playwrightのブラウザバイナリインストール時にも権限エラーに注意すること。
- Tailwind CSS は CDN 経由で読み込み（開発時）