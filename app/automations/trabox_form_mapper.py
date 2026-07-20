"""Trabox フォームマッピング
case_data → Trabox フォームフィールドの対応関係

🔴 【重要】Traboxはname属性を使わず、placeholder属性でフィールドを特定
"""
from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class TraboxFormMapper:
    """case_data を Trabox フォームフィールドにマップ

    ⭐ 2026-07-20 修正：
    - Trabox フォームはname属性がない
    - placeholder属性またはクラス+プレースホルダーで特定する
    """

    # フィールドマッピング定義
    # {case_data_key: (selector, field_type, value_transformer)}
    FIELD_MAPPING = {
        # 出発地・目的地 - select 要素で管理（rc_select_0, rc_select_1 等）
        "pick_location": {
            "selector": "input[id='rc_select_0'], .ant-select:nth-of-type(1) input",
            "type": "select",
            "description": "出発地（都道府県）",
            "placeholder": None,
        },
        "drop_location": {
            "selector": "input[id='rc_select_1'], .ant-select:nth-of-type(2) input",
            "type": "select",
            "description": "目的地（都道府県）",
            "placeholder": None,
        },
        # 荷物情報 - placeholder で特定
        "cargo_weight": {
            "selector": "input.ant-input.tbx-text-input",
            "type": "number",
            "description": "荷物の重量（kg）",
            "placeholder": None,  # 複数要素があるので手動マッピングが必要
        },
        "vehicle_type": {
            "selector": "input[id='rc_select_2'], .ant-select:nth-of-type(3) input",
            "type": "select",
            "description": "車種",
            "placeholder": None,
        },
        # 料金
        "freight_rate": {
            "selector": "input[id='rc_select_5'], .ant-select:nth-of-type(6) input",
            "type": "number",
            "description": "運送料金（円）",
            "placeholder": None,
        },
        # 日時 - 積み時間・卸し時間が別途ある
        "pickup_date": {
            "selector": "input[placeholder='日時を選択']",
            "type": "date",
            "description": "ピックアップ日",
            "placeholder": "日時を選択",
        },
        "pickup_time": {
            "selector": "input[placeholder='積み時間を入力してください']",
            "type": "time",
            "description": "ピックアップ時間",
            "placeholder": "積み時間を入力してください",
        },
        # 連絡先 - 未実装（要確認）
        "contact_name": {
            "selector": "input[placeholder*='名前'], input[placeholder*='担当']",
            "type": "text",
            "description": "連絡先名",
            "placeholder": None,
        },
        "contact_phone": {
            "selector": "input[placeholder*='電話'], input[placeholder*='携帯']",
            "type": "tel",
            "description": "連絡先電話番号",
            "placeholder": None,
        },
        "contact_email": {
            "selector": "input[placeholder*='メール'], input[type='email']",
            "type": "email",
            "description": "連絡先メール",
            "placeholder": None,
        },
    }

    # 送信ボタンセレクター
    SUBMIT_BUTTON_SELECTOR = "button:has-text('登録'), button[type='submit']"

    @classmethod
    def get_fields_to_fill(cls) -> Dict[str, Dict[str, Any]]:
        """入力すべきフィールド一覧を取得"""
        return cls.FIELD_MAPPING

    @classmethod
    def get_submit_button_selector(cls) -> str:
        """送信ボタンのセレクターを取得"""
        return cls.SUBMIT_BUTTON_SELECTOR

    @classmethod
    def transform_value(
        cls, key: str, value: Any
    ) -> Optional[str]:
        """値を Trabox フォーム対応に変換

        Args:
            key: case_data のキー
            value: 元の値

        Returns:
            変換後の値（文字列）
        """
        if value is None:
            return None

        field_info = cls.FIELD_MAPPING.get(key)
        if not field_info:
            return str(value)

        field_type = field_info.get("type")

        # 日付型の処理
        if field_type == "date":
            if isinstance(value, str):
                # YYYY-MM-DD 形式の場合はそのまま
                if len(value) == 10:
                    return value
                # それ以外は解析を試みる
                try:
                    parsed = datetime.fromisoformat(value)
                    return parsed.strftime("%Y-%m-%d")
                except ValueError:
                    logger.warning(f"日付解析失敗: {key}={value}")
                    return value
            elif isinstance(value, datetime):
                return value.strftime("%Y-%m-%d")

        # 時間型の処理
        if field_type == "time":
            if isinstance(value, str):
                # HH:MM 形式
                return value
            elif isinstance(value, datetime):
                return value.strftime("%H:%M")

        # 数値型の処理
        if field_type in ["number", "tel"]:
            return str(value)

        # select, text, email 等
        return str(value)

    @classmethod
    def validate_case_data(cls, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """case_data を検証してレポート

        Returns:
            {
                "valid_fields": [...],
                "missing_fields": [...],
                "unknown_fields": [...],
            }
        """
        valid_fields = []
        missing_fields = []
        unknown_fields = []

        # 定義済みフィールドをチェック
        for key in cls.FIELD_MAPPING.keys():
            if key in case_data:
                valid_fields.append(key)
            else:
                missing_fields.append(key)

        # 未定義フィールドをチェック
        for key in case_data.keys():
            if key not in cls.FIELD_MAPPING:
                unknown_fields.append(key)

        return {
            "valid_fields": valid_fields,
            "missing_fields": missing_fields,
            "unknown_fields": unknown_fields,
        }
