# Carroo エラー体系仕様書 ver1.0

**最終更新: 2026-07-27 / 対象リビジョン: carroo-00046-nr2**

## 0. 改版ルール（重要）
- **`app/errors.py`（ERROR_CATALOG / classify / AppError）や共通ハンドラ（`app/main.py`）を変更したら、必ずこの仕様書も改版する。**
- 上書きせず、`エラー体系仕様書_ver1.1.md` のようにバージョンを上げた新ファイルを作り履歴を残す（`docs/` 仕様書の共通ルールに準拠）。
- 変更時は下部「改版履歴」に1行追記する。

## 1. 目的・方針
- **エンドユーザー**にはやさしい日本語の説明を出す。
- **管理者**が原因調査できるよう、**エラーコード**（＋500系は**参照ID**）を必ず併記する。
- コードは `detail` 文字列に埋め込むため、既存のフロント表示（`result.detail`）がそのまま対応できる。
- 表示形式: `{やさしい説明}（コード: {CODE}[ / 参照: {REF}]）`
  - 例: `投稿サイトの反応が遅く…（コード: E-POST-TIMEOUT / 参照: a1b2c3d4）`

## 2. 実装の場所
| 役割 | ファイル |
|---|---|
| コード表・分類・整形・業務例外 | `app/errors.py` |
| 共通例外ハンドラ（AppError / 422 / 未捕捉500） | `app/main.py` |
| 投稿失敗の分類適用（DBの error_message・結果メール） | `app/services/poster.py` の `_friendly()` |
| ログイン失敗の文言 | `app/routers/auth.py` |

- **参照ID**: 未捕捉例外(500)時に `new_ref()`（8桁hex）を発行。`logging.getLogger("errors").exception("[E-SYS-500] ref=... path=...")` で全文＋スタックトレースを出力。Cloud Logging で `ref=xxxx` を検索すれば当該エラーに到達できる。
- **生メッセージ** は必ずログ側に残し、画面/DB/メールにはやさしい説明＋コードのみ（内部情報を露出しない）。

## 3. エラーコード一覧（ERROR_CATALOG）
| コード | ユーザー向け説明 | 管理者向けヒント |
|---|---|---|
| `E-SYS-500` | 予期しないエラーが発生しました。時間をおいて再度お試しください。 | 未捕捉例外。参照IDでログ検索しトレース確認。 |
| `E-VALIDATION` | 入力内容に誤りがあります。赤字の項目を確認してください。 | リクエストのバリデーション失敗（型/必須）。 |
| `E-AUTH-401` | ユーザー名またはパスワードが違います。 | 認証失敗。 |
| `E-AUTH-429` | 試行回数が多すぎます。しばらく待って再度お試しください。 | ログインレート制限に到達。 |
| `E-AUTH-403` | この操作を行う権限がありません。 | 権限不足（管理者専用操作など）。 |
| `E-POST-TIMEOUT` | 投稿サイトの反応が遅く、時間内に完了できませんでした。自動で再試行します。 | Playwright タイムアウト。サイト構造変更/高負荷。 |
| `E-POST-LOGIN` | 投稿サイトへのログインに失敗しました。認証情報をご確認ください。 | Trabox/WebKit ログイン失敗。認証情報の変更/失効。 |
| `E-POST-INPUT` | 投稿内容の一部が投稿サイトに受け付けられませんでした。入力内容をご確認ください。 | サイト側入力エラー（必須/コード不一致。例: vacantarea）。 |
| `E-POST-SELECTOR` | 投稿サイトの画面が変わった可能性があります。管理者にご連絡ください。 | セレクタ不一致。DOM変更の可能性大。 |
| `E-POST-NETWORK` | 通信エラーが発生しました。自動で再試行します。 | ネットワーク/接続エラー。 |
| `E-POST-UNKNOWN` | 投稿処理でエラーが発生しました。管理者にご連絡ください。 | 分類不能。error_message 全文を確認。 |

## 4. 自動分類ルール（classify）
投稿系の生メッセージを次の優先順でコードに割り当てる（`app/errors.py::classify`）:
1. `timeout` / `タイムアウト` → `E-POST-TIMEOUT`
2. `入力エラー` / `invalid` / `受け付け` → `E-POST-INPUT`
3. `ログイン` / `login` / `認証` → `E-POST-LOGIN`
4. `selector` / `locator` / `not found` / `セレクタ` → `E-POST-SELECTOR`
5. `network` / `connection` / `接続` / `econn` / `dns` → `E-POST-NETWORK`
6. それ以外 → `E-POST-UNKNOWN`

## 5. どこに出るか
- **フォーム送信のエラー**（ログイン・案件/空車登録・設定保存）: `detail` にコード込みで表示。
- **投稿の非同期失敗**: ダッシュボード/案件管理の状態・error_message、結果通知メール、DLQアラートに反映。
- **未捕捉500**: 画面に参照ID付きメッセージ、サーバーログに全文。

## 6. 運用フロー（管理者）
1. ユーザーからコード（と参照ID）を聞く。
2. `E-POST-*` は error_message とログの生メッセージで原因を特定。`E-SYS-500` は Cloud Logging で `ref=<参照ID>` を検索しトレース確認。
3. サイト構造変更（`E-POST-SELECTOR`/`TIMEOUT` 多発）ならセレクタ/待機の見直し。

## 7. 監視との連動
- `carroo_error_count`（severity>=ERROR）/ `carroo_dead_letter` / `carroo_login_failure` のログベースメトリクス＋アラートと併用。
- 参照ID・コードはログに残るため、アラート受信後の一次切り分けに使える。

---
## 改版履歴
- **ver1.0（2026-07-27）**: 初版。E-SYS/E-VALIDATION/E-AUTH-401,403,429/E-POST-TIMEOUT,LOGIN,INPUT,SELECTOR,NETWORK,UNKNOWN を定義。共通ハンドラ・poster 分類・ログイン文言に適用（rev carroo-00046-nr2）。
