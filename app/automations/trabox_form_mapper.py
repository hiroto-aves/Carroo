"""Trabox フォームマッピング
case_data → Trabox フォームフィールドの対応関係
"""
from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class TraboxFormMapper:
    """case_data を Trabox フォームフィールドにマップ

    TODO: 実際のフォーム構造を確認後、セレクター・フィールド名を更新
    """

    # フィールドマッピング定義
    # {case_data_key: (selector, field_type, value_transformer)}
    FIELD_MAPPING = {
        # 出発地・目的地
        "pick_location": {
            "selector": "select[name='from_prefecture']",  # TODO: 実際のセレクターを確認
            "type": "select",
            "description": "出発地（都道府県）",
        },
        "drop_location": {
            "selector": "select[name='to_prefecture']",  # TODO: 実際のセレクターを確認
            "type": "select",
            "description": "目的地（都道府県）",
        },
        # 荷物情報
        "cargo_weight": {
            "selector": "input[name='weight']",  # TODO: 実際のセレクターを確認
            "type": "number",
            "description": "荷物の重量（kg）",
        },
        "vehicle_type": {
            "selector": "select[name='vehicle_type']",  # TODO: 実際のセレクターを確認
            "type": "select",
            "description": "車種",
        },
        # 料金
        "freight_rate": {
            "selector": "input[name='freight_rate']",  # TODO: 実際のセレクターを確認
            "type": "number",
            "description": "運送料金（円）",
        },
        # 日時
        "pickup_date": {
            "selector": "input[name='pickup_date']",  # TODO: 実際のセレクターを確認
            "type": "date",
            "description": "ピックアップ日",
        },
        "pickup_time": {
            "selector": "input[name='pickup_time']",  # TODO: 実際のセレクターを確認
            "type": "time",
            "description": "ピックアップ時間",
        },
        # 連絡先
        "contact_name": {
            "selector": "input[name='contact_name']",  # TODO: 実際のセレクターを確認
            "type": "text",
            "description": "連絡先名",
        },
        "contact_phone": {
            "selector": "input[name='contact_phone']",  # TODO: 実際のセレクターを確認
            "type": "tel",
            "description": "連絡先電話番号",
        },
        "contact_email": {
            "selector": "input[name='contact_email']",  # TODO: 実際のセレクターを確認
            "type": "email",
            "description": "連絡先メール",
        },
    }

    # 送信ボタンセレクター
    SUBMIT_BUTTON_SELECTOR = "button:has-text('登録'), button[type='submit']"  # TODO: 実際のセレクターを確認

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
