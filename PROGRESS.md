# Progress Tracking

## ⏳ バックログ (未着手)
- [ ] バックエンド（FastAPI）の基本環境構築
- [ ] 案件入力フォームのHTML/Tailwind CSS作成（チェックボックスの横並びデザイン含む）
- [ ] フォームデータを受け取るAPIエンドポイントの実装
- [ ] Playwrightの導入と開発環境での認証テスト
- [ ] トラボックス自動ログイン＆投稿ロジックの実装（`playwright codegen` を活用）
- [ ] Webkit用ダミー投稿モジュールの作成（将来のAPI連携用）
- [ ] 動的チェックボックスによる条件分岐実装（チェックが入ったサービスのみ実行）

## 🔄 進行中 (In Progress)
- [ ] なし（一からのスタート準備完了）

## ✅ 完了 (Completed)
- [x] 新要件の定義と技術選定の刷新 (FastAPI + Playwright + Tailwind CSS)
- [x] `README.md`, `claude.md`, `progress.md` の作成

## 📝 開発メモ
- トラボックスのログイン画面は `name="loginid"`, `name="loginpwd"`、ログインボタンは「ログイン」のテキストを持つ `<span>` であることが判明している。
- 以前のSelenium実装時にMacのGatekeeper（マルウェア検証エラー）に遭遇したため、Playwrightのブラウザバイナリインストール時にも権限エラーに注意すること。