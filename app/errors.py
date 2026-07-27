"""エラーの共通体系。

方針: エンドユーザーには「やさしい日本語の説明」を、管理者には「エラーコード」と
「参照ID」を同時に見せる。参照IDでサーバーログ（Cloud Logging）を検索すれば
原因の詳細（スタックトレース）にたどり着ける。

- new_ref(): 参照ID（短いランダム文字列）
- classify(msg): 例外メッセージから (code, ユーザー向け説明) を推定
- format_detail(user_msg, code, ref): 画面表示用の1行に整形
- AppError: code を持つ業務例外（ルーターから raise）
"""
import secrets

# コード → (ユーザー向け説明, 管理者向けヒント)
ERROR_CATALOG = {
    "E-SYS-500":   ("予期しないエラーが発生しました。時間をおいて再度お試しください。",
                    "未捕捉の例外。参照IDでログ検索しスタックトレースを確認。"),
    "E-VALIDATION":("入力内容に誤りがあります。赤字の項目を確認してください。",
                    "リクエストのバリデーション失敗（型/必須）。"),
    "E-AUTH-401":  ("ユーザー名またはパスワードが違います。",
                    "認証失敗。"),
    "E-AUTH-429":  ("試行回数が多すぎます。しばらく待って再度お試しください。",
                    "ログインレート制限に到達。"),
    "E-AUTH-403":  ("この操作を行う権限がありません。",
                    "権限不足（管理者専用操作など）。"),
    "E-POST-TIMEOUT": ("投稿サイトの反応が遅く、時間内に完了できませんでした。自動で再試行します。",
                       "Playwright のタイムアウト。サイト構造変更/高負荷の可能性。"),
    "E-POST-LOGIN":   ("投稿サイトへのログインに失敗しました。認証情報をご確認ください。",
                       "Trabox/WebKit ログイン失敗。認証情報の変更/失効を確認。"),
    "E-POST-INPUT":   ("投稿内容の一部が投稿サイトに受け付けられませんでした。入力内容をご確認ください。",
                       "サイト側の入力エラー（必須項目/コード不一致など。例: vacantarea）。"),
    "E-POST-SELECTOR":("投稿サイトの画面が変わった可能性があります。管理者にご連絡ください。",
                       "セレクタ不一致。サイトのDOM変更の可能性が高い。"),
    "E-POST-NETWORK": ("通信エラーが発生しました。自動で再試行します。",
                       "ネットワーク/接続エラー。"),
    "E-POST-UNKNOWN": ("投稿処理でエラーが発生しました。管理者にご連絡ください。",
                       "分類不能の投稿エラー。error_message 全文を確認。"),
}


def new_ref() -> str:
    """参照ID（例: 'a1b2c3d4'）。ユーザー画面とサーバーログを紐づける。"""
    return secrets.token_hex(4)


def user_message(code: str) -> str:
    return ERROR_CATALOG.get(code, ERROR_CATALOG["E-SYS-500"])[0]


def format_detail(user_msg: str, code: str, ref: str = None) -> str:
    """画面表示用の1行。既存のフロント（result.detail 表示）がそのまま使える形。"""
    tail = f"コード: {code}" + (f" / 参照: {ref}" if ref else "")
    return f"{user_msg}（{tail}）"


def classify(message) -> tuple:
    """例外/メッセージ文字列から (code, ユーザー向け説明) を推定（主に投稿エラー用）。"""
    m = str(message or "").lower()
    jp = str(message or "")
    if "timeout" in m or "タイムアウト" in jp:
        code = "E-POST-TIMEOUT"
    elif "入力エラー" in jp or "invalid" in m or "受け付け" in jp:
        code = "E-POST-INPUT"
    elif "ログイン" in jp or "login" in m or "認証" in jp:
        code = "E-POST-LOGIN"
    elif "selector" in m or "locator" in m or "not found" in m or "セレクタ" in jp:
        code = "E-POST-SELECTOR"
    elif ("network" in m or "connection" in m or "接続" in jp
          or "econn" in m or "dns" in m):
        code = "E-POST-NETWORK"
    else:
        code = "E-POST-UNKNOWN"
    return code, user_message(code)


class AppError(Exception):
    """code を持つ業務例外。ルーターで raise すると共通ハンドラが整形して返す。"""
    def __init__(self, code: str, user_msg: str = None, status_code: int = 400):
        self.code = code
        self.user_msg = user_msg or user_message(code)
        self.status_code = status_code
        super().__init__(f"{code}: {self.user_msg}")
