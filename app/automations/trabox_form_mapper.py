"""Trabox フォームマッピング
case_data → Trabox 荷物登録フォーム（https://www.trabox.com/baggage/register）の対応関係

🔴 【重要】2026-07-22 実DOM解析に基づく確定版
- Trabox は Vue + Ant Design 製の SPA。name 属性なし、rc_select_N の id は動的に変わる
- 全フォーム行が「.tbx-form-item > .label-wrapper（行ラベル）」の規則構造
  → 行ラベル基準のセレクターが最も堅牢（id・rc_select 番号には絶対に依存しない）

【実DOMで確認済みのフォーム構造】
- 発/着 日時: .ui-datetime-select クリック → カレンダー（td[title="YYYY-MM-DD"]）
  + 時メニュー（"9時" 等）+ 分メニュー（"00分" 等、10分刻み）のドロップダウン
- 発地/着地 都道府県: .ant-select クリック → 日本地図型ドロップダウン
  （.ui-prefecture-dropdown-container 内の button.map-button、表記は「東京」「大阪」等の短縮形）
- 荷姿: ラジオ（BS1=パレット / BS2=その他）【必須】
- 希望車両: .ant-select ×2（1つ目=重量クラス「軽/1t〜8t/問わず」、2つ目=車種「平/箱/ウイング等」）
- 運賃: 「運賃」行内の input.ant-input（円・税別）【必須】
- 積み時間/卸し時間: placeholder 付きフリーテキスト
- 登録ボタン: button.ant-btn-primary テキスト「登録」
"""
from typing import Any, Optional, Tuple
from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)


class TraboxFormMapper:
    """case_data の値を Trabox フォーム操作用に変換するユーティリティ"""

    # ============ セレクター定義 ============

    # 送信ボタン（フォーム最下部のプライマリボタン）
    SUBMIT_BUTTON_SELECTOR = "button.ant-btn-primary:has-text('登録')"

    # 積み時間・卸し時間のフリーテキスト入力
    PICKUP_TIME_TEXT_SELECTOR = "input[placeholder='積み時間を入力してください']"
    DROP_TIME_TEXT_SELECTOR = "input[placeholder='卸し時間を入力してください']"

    # 表示中のドロップダウン
    # （Ant Design は閉じても DOM に残り、hidden クラスまたは display:none で隠れるため
    #   :visible 擬似クラスでの絞り込みが必須）
    VISIBLE_DROPDOWN = ".ant-dropdown:not(.ant-dropdown-hidden):visible"
    VISIBLE_SELECT_DROPDOWN = (
        ".ant-select-dropdown:not(.ant-select-dropdown-hidden):visible"
    )

    @staticmethod
    def row_selector(label: str) -> str:
        """フォーム行（.tbx-form-item）を行ラベルの完全一致で特定するセレクター

        例: row_selector("発") → 「発」行のみ（「発地」行にはマッチしない）
        """
        return f".tbx-form-item:has(.label-wrapper:text-is('{label}'))"

    # ============ 値変換 ============

    # 都道府県の正式名 → Trabox 地図ボタンの短縮表記
    # （北海道以外は「都/府/県」を除いた表記がボタンテキスト）
    @staticmethod
    def normalize_prefecture(value: str) -> Optional[str]:
        """「東京都」→「東京」のように Trabox 地図ボタン表記へ正規化

        住所が含まれる場合（例: 東京都港区）も先頭の都道府県だけを抽出する。
        """
        if not value:
            return None
        value = value.strip()
        if value.startswith("北海道"):
            return "北海道"
        # 先頭の都道府県名を抽出（〜都・〜府・〜県）
        m = re.match(r"^(.{2,3}?)[都府県]", value)
        if m:
            return m.group(1)
        # 既に短縮形（「東京」等）で渡された場合はそのまま
        return value[:4]

    @staticmethod
    def extract_city(value: str) -> Optional[str]:
        """住所文字列から市区町村部分を抽出（Trabox の市区町村は【必須】）

        例: 「東京都港区芝浦1-2-3」→「港区」、「愛知県海部郡蟹江町」→「海部郡蟹江町」
        都道府県のみ（「東京都」等）の場合は None を返す。
        """
        if not value:
            return None
        v = value.strip()
        if v.startswith("北海道"):
            rest = v[len("北海道"):]
        else:
            m = re.match(r"^.{2,3}?[都府県]", v)
            rest = v[m.end():] if m else ""
        rest = rest.strip()
        if not rest:
            return None
        # 優先順: 郡部（〜郡〜町/村）→ 政令指定都市（〜市〜区）→ 通常（市/区/町/村）
        m = re.match(r"^(.+?郡.+?[町村]|.+?市.+?区|.+?[市区町村])", rest)
        return m.group(1) if m else rest

    # 高速代【必須ラジオ】の既定値
    # 追加費用を荷主に約束しない安全側の既定。case_data の highway_fee で上書き可能
    DEFAULT_HIGHWAY_FEE = "支払わない"

    # 荷姿=その他 選択時に必須になる「荷種」の既定値
    # case_data の cargo_type で上書き可能
    DEFAULT_CARGO_TYPE = "雑貨"

    @staticmethod
    def weight_to_class(weight_kg: Any) -> str:
        """荷物重量(kg) → Trabox 希望車両の重量クラス

        実DOMで確認済みの選択肢: 問わず / 軽 / 1t / 2t / 3t / 4t / 5t / 6t / 7t / 8t …
        350kg 以下は軽、以降は積載可能な最小トンクラスに切り上げる。
        """
        try:
            kg = float(weight_kg)
        except (TypeError, ValueError):
            return "問わず"
        if kg <= 0:
            return "問わず"
        if kg <= 350:
            return "軽"
        tons = int(-(-kg // 1000))  # kg → t 切り上げ
        if tons <= 8:
            return f"{tons}t"
        # 8t 超は選択肢の存在が未確認のため「問わず」に倒す（安全側）
        return "問わず"

    # アプリの車種コード → Trabox 車種オプション表記
    VEHICLE_TYPE_MAPPING = {
        "small_truck": "平",
        "medium_truck": "箱",
        "large_truck": "ウイング",
        "refrigerated": "保冷",
        "frozen": "冷凍",
        "other": "問わず",
    }

    @classmethod
    def vehicle_to_option(cls, vehicle_type: str) -> str:
        """車種コード → Trabox ドロップダウンの選択肢テキスト

        日本語表記（「平」「箱」「ウイング」等）で直接渡された場合はそのまま使う。
        未知の値は「問わず」に倒す。
        """
        if not vehicle_type:
            return "問わず"
        mapped = cls.VEHICLE_TYPE_MAPPING.get(vehicle_type)
        if mapped:
            return mapped
        # 日本語表記のパススルー（実在確認済みの選択肢のみ）
        known = {"問わず", "平", "平-低床", "平-パワーゲート", "平-エアサス",
                 "箱", "箱-低床", "箱-パワーゲート", "箱-エアサス", "ウイング",
                 "保冷", "冷凍"}
        if vehicle_type in known:
            return vehicle_type
        logger.warning(f"[TraboxMapper] 未知の車種: {vehicle_type} → 問わず")
        return "問わず"

    @staticmethod
    def parse_date(value: Any) -> Optional[str]:
        """日付を YYYY-MM-DD（カレンダーの td[title] 形式）に正規化"""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")
        s = str(value).strip()
        for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(s[:10], fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(s).strftime("%Y-%m-%d")
        except ValueError:
            logger.warning(f"[TraboxMapper] 日付解析失敗: {value}")
            return None

    @staticmethod
    def parse_time(value: Any) -> Optional[Tuple[str, str]]:
        """時刻 "HH:MM" → (時メニュー表記, 分メニュー表記)

        分メニューは 10 分刻みのため最も近い値に丸める。
        例: "09:05" → ("9時", "10分")、"14:30" → ("14時", "30分")
        """
        if not value:
            return None
        s = str(value).strip()
        m = re.match(r"^(\d{1,2}):(\d{2})", s)
        if not m:
            logger.warning(f"[TraboxMapper] 時刻解析失敗: {value}")
            return None
        hour = int(m.group(1))
        minute = int(m.group(2))
        if not (0 <= hour <= 23):
            return None
        rounded = round(minute / 10) * 10
        if rounded == 60:
            # 繰り上がりで時が変わる場合（例: 9:58 → 10時00分）
            hour = (hour + 1) % 24
            rounded = 0
        return (f"{hour}時", f"{rounded:02d}分")

    @staticmethod
    def format_freight(value: Any) -> Optional[str]:
        """運賃を整数円の文字列に変換"""
        if value is None:
            return None
        try:
            return str(int(float(value)))
        except (TypeError, ValueError):
            logger.warning(f"[TraboxMapper] 運賃解析失敗: {value}")
            return None

    @staticmethod
    def month_title(date_str: str) -> str:
        """YYYY-MM-DD → カレンダーヘッダー表記「YYYY年 M月」（月はゼロ埋めなし）"""
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return f"{d.year}年 {d.month}月"
