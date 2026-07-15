# Progress Tracking

## ⏳ バックログ (未着手)
- [ ] Playwright codegen を使用したトラボックス要素検査・自動化コード生成
- [ ] トラボックス実際のログイン・投稿テスト（テスト環境）
- [ ] Webkit API キー設定とエンドツーエンドテスト
- [ ] エラーハンドリング・スクリーンショット保存機能の改善
- [ ] データベース永続化テスト
- [ ] フロントエンドの UX 改善（デザイン・レスポンシブ対応）
- [ ] ユーザー管理画面（ダッシュボード）実装
- [ ] 投稿履歴表示機能

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
  - [x] モジュール分離（routers, automations, models, db, utils）
- [x] FastAPI アプリケーション骨組み実装
  - [x] `app/main.py` でアプリケーションオブジェクト生成
  - [x] `app/config.py` で環境変数・設定管理
  - [x] `app/db/database.py` で SQLite 接続・テーブル初期化
  - [x] `app/models/schemas.py` で Pydantic データモデル定義
- [x] ルーター実装
  - [x] `app/routers/auth.py` - ログイン・登録画面＆エンドポイント
  - [x] `app/routers/cases.py` - 案件登録画面＆投稿ロジック
- [x] 自動投稿モジュール
  - [x] `app/automations/trabox.py` - Playwright ベースの自動ログイン・投稿（強化版）
  - [x] `app/automations/webkit.py` - HTTP 非同期 API 投稿モジュール
- [x] エントリーポイント
  - [x] `main.py` を作成（`uvicorn` で起動可能）
- [x] `.env.example` ファイル作成
- [x] **Step 1: バックエンド起動テスト** ✅
  - [x] Python 3.7 互換性修正（`List[T]` 型）
  - [x] 依存パッケージ追加（email-validator, httpx）
  - [x] FastAPI サーバーの起動確認
- [x] **Step 2: Playwright ブラウザインストール** ✅
  - [x] Chromium ブラウザエンジンのインストール
  - [x] FFMPEG コーデックのインストール
  - [x] Playwright async API の動作確認
- [x] **Step 3: トラボックス自動投稿ロジック詳細実装** ✅
  - [x] エラーハンドリング・ロギング強化
  - [x] タイムアウト管理（30秒）
  - [x] 複数セレクタによる要素検出
  - [x] ログイン・フォーム入力・送信メソッド実装
  - [x] スクリーンショット保存機能
- [x] **Step 4: JWT ベースのセッション管理** ✅
  - [x] `app/utils/security.py` - パスワードハッシュ化・JWT トークン生成
  - [x] `app/dependencies.py` - 認証依存関係
  - [x] HTTP-only Cookie によるトークン管理
  - [x] `/auth/me` エンドポイント実装
  - [x] `/auth/logout` エンドポイント実装
  - [x] 認証ユーザー情報をルーターに注入
  - [x] ロギング設定追加

## 📝 開発メモ
- Python 3.7.11 で環境構築（要件は 3.11+ だが、互換性あり）
- トラボックスのログイン画面は `name="loginid"`, `name="loginpwd"`、ログインボタンは「ログイン」のテキストを持つ `<span>` であることが判明している。
- 以前のSelenium実装時にMacのGatekeeper（マルウェア検証エラー）に遭遇したため、Playwrightのブラウザバイナリインストール時にも権限エラーに注意すること。
- Tailwind CSS は CDN 経由で読み込み（開発時）