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

# フォームのフィールド名 → 画面表示用の日本語ラベル。
# E-VALIDATION（型不一致等）発生時に「どの項目か」をユーザーにも見せるための対応表。
# 未登録のフィールド名はそのままの名前で表示する（隠さない）。
FIELD_LABELS = {
    "pick_location": "積地", "drop_location": "卸地",
    "pick_pref": "積地(都道府県)", "pick_city": "積地(市区町村)",
    "drop_pref": "卸地(都道府県)", "drop_city": "卸地(市区町村)",
    "cargo_weight": "荷物重量", "vehicle_type": "希望車両(車種形状)",
    "truck_weight": "希望車両(トン数)",
    "freight_rate": "運賃", "freight_negotiable": "運賃(要相談)",
    "pickup_date": "積み日", "pickup_time": "積み時間",
    "drop_date": "着日", "drop_time": "卸し時間",
    "contact_name": "担当者名", "contact_phone": "担当者電話番号",
    "contact_email": "担当者メールアドレス",
    "cargo_type": "荷物区分(品目)", "package_type": "荷姿",
    "truck_count": "台数", "share": "積合せ",
    "highway_fee": "高速代", "omakase_billing": "おまかせ請求受入可否",
    "contact_method": "連絡方法", "visibility": "公開範囲",
    "remarks": "備考", "moving_case": "引越し案件",
    "transport_types": "輸送取扱区分", "equipment_items": "必要装備",
    "equipment_other": "必要装備(その他)",
    "loading_time_option": "積み時間区分", "unloading_time_option": "卸し時間区分",
    "post_to_trabox": "投稿先(トラボックス)", "post_to_webkit": "投稿先(WebKit)",
    "date_variants": "複数日程",
}

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
    "E-POST-NOTLISTED":("まだ掲載されていないため、変更・取下げできません。先に投稿してください。",
                        "掲載番号(baggage_no)が未記録。初回投稿が未掲載/番号取得失敗。リトライ不可。"),
    "E-POST-UNKNOWN": ("投稿処理でエラーが発生しました。管理者にご連絡ください。",
                       "分類不能の投稿エラー。error_message 全文を確認。"),
}

# リトライしても状況が変わらない（＝Cloud Tasks で再試行させても無駄な）エラーコード。
# tasks.py はこれらを全プラットフォームで検出したら、リトライせず即DLQ退避する。
NON_RETRYABLE_CODES = frozenset({"E-POST-NOTLISTED"})


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
    if ("掲載中の番号が見つかりません" in jp or "未登録または削除済み" in jp
            or "掲載番号" in jp and "見つかり" in jp):
        code = "E-POST-NOTLISTED"
    elif "timeout" in m or "タイムアウト" in jp:
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
