"""WebKIT API コード値マッピング
仕様書から抽出したコード値定義
"""

# 都道府県コード
PREFECTURES = {
    '道北': '01', '道央': '02', '道東': '03', '道南': '04',
    '青森県': '05', '岩手県': '06', '宮城県': '07', '秋田県': '08',
    '山形県': '09', '福島県': '10', '茨城県': '11', '栃木県': '12',
    '群馬県': '13', '山梨県': '14', '埼玉県': '15', '千葉県': '16',
    '東京都': '17', '神奈川県': '18', '新潟県': '19', '長野県': '20',
    '富山県': '21', '石川県': '22', '福井県': '23', '岐阜県': '24',
    '静岡県': '25', '愛知県': '26', '三重県': '27', '滋賀県': '28',
    '京都府': '29', '大阪府': '30', '兵庫県': '31', '奈良県': '32',
    '和歌山県': '33', '鳥取県': '34', '島根県': '35', '岡山県': '36',
    '広島県': '37', '山口県': '38', '徳島県': '39', '香川県': '40',
    '愛媛県': '41', '高知県': '42', '福岡県': '43', '佐賀県': '44',
    '長崎県': '45', '熊本県': '46', '大分県': '47', '宮崎県': '48',
    '鹿児島県': '49', '沖縄県': '50',
}

# 車種コード
VEHICLE_TYPES = {
    '平型': '1',
    'バン型': '2',
    'ウイング型': '3',
    '保冷車': '4',
    '冷凍車': '5',
    '車載車': '6',
    '重機運搬車': '7',
    '危険物運搬車': '8',
    'ダンプ': '9',
    '幌': '10',
    'ユニック': '11',
    '海上コンテナー用': '12',
    'その他': '13',
    '冷蔵車': '14',
}

# 輸送品区分
CARGO_TYPES = {
    '農産物': '1',
    '畜産物': '2',
    '水産物': '3',
    '食料品': '4',
    '飲料品': '5',
    '木材': '6',
    '砂利・砂等': '7',
    '金属製品': '8',
    '鋼材': '9',
    '建材': '10',
    '電気製品': '11',
    '機械・装置': '12',
    'セメント': '13',
    'セメント製品': '14',
    '紙・パルプ製品': '15',
    '石油製品': '16',
    '化学製品': '17',
    'その他危険物': '18',
    '衣料・雑貨': '19',
    '引越貨物': '20',
    'その他': '21',
}

# 荷扱い
HANDLING = {
    '手積': '1',
    '機械積': '2',
    '機械積(フォーク)': '3',
    '機械積(クレーン)': '4',
    '指定なし': '9',
}

# 輸送取扱
TRANSPORT_HANDLING = {
    '保冷': '1',
    '冷凍': '2',
    '常温': '3',
    'ワレモノ・壊れ物': '4',
    '雨濡厳禁': '5',
    '貴重品': '6',
    '危険物': '7',
    '冷蔵': '8',
}

# 輸送品形状
CARGO_SHAPE = {
    'ケース': '1',
    '袋': '2',
    'ハダカ': '3',
    'フレコンパック': '4',
    'ドラム類': '5',
    '缶類': '6',
    'パレット': '7',
    'ラック': '8',
    'バラ': '9',
    'その他': '10',
}

# 安全装置
SAFETY_DEVICE = {
    'ヘルメット': '1',
    '安全靴': '2',
    '安全帯': '3',
    'その他': '4',
}


# Trabox 車種形状（平/箱/ウイング等）→ WebKIT 車種コード（[車種]シート）
# WebKIT には「箱型」がなく「バン型=2」が該当。付帯（-低床等）は基本形にまとめる。
TRABOX_SHAPE_TO_WEBKIT_CAR = {
    "問わず": "13",   # その他
    "平": "1", "平-低床": "1", "平-パワーゲート": "1", "平-エアサス": "1",
    "箱": "2", "箱-低床": "2", "箱-パワーゲート": "2", "箱-エアサス": "2",
    "ウイング": "3", "ウイング-低床": "3", "ウイング-パワーゲート": "3",
    "ウイング-エアサス": "3", "ウイング又は平": "3", "ウイング又は箱": "3",
    "ユニック": "11", "冷凍": "5", "保冷": "4", "他": "13",
    # 旧UIの英字コードも後方互換で受ける
    "small_truck": "1", "medium_truck": "2", "large_truck": "3",
    "refrigerated": "4", "frozen": "5", "other": "13",
}


def get_prefecture_code(name: str) -> str:
    """都道府県名からコードを取得（前方一致。「東京都港区」→17）

    北海道は WebKIT では道北/道央/道東/道南に分かれるが、市区町村からの
    地域判定は本関数では行わず、暫定で道央(02)を返す（要・呼び出し側補正）。
    """
    if not name:
        return ''
    # 完全一致優先
    if name in PREFECTURES:
        return PREFECTURES[name]
    # 前方一致（住所文字列から都道府県を判定）
    if name.startswith('北海道'):
        return '02'  # 暫定: 道央
    for pref, code in PREFECTURES.items():
        if name.startswith(pref):
            return code
    return ''


def get_webkit_car_code(trabox_shape: str) -> str:
    """Trabox の車種形状 → WebKIT 車種コード（未知は 13=その他）"""
    if not trabox_shape:
        return '13'
    return TRABOX_SHAPE_TO_WEBKIT_CAR.get(trabox_shape, '13')


# Trabox 車種形状の付帯（例:「平-低床」の「-低床」）→ WebKIT [車種形状]シート準拠の
# 付帯コード。carkindtype（基本形）とは別に、WebKIT では任意項目として個別に送れる。
_TRAYHEIGHT_MAP = {"低床": "2", "中低床": "4", "高床": "3"}   # 荷台高さ（標準=1は既定のため送らない）
_LOADUNIT_PAWAGATE = "1"     # 荷役装置: パワーゲート
_SUSPENSION_AIRSUS = "1"     # 懸架装置: エアサス車


def get_shape_attrs(trabox_shape: str) -> dict:
    """Trabox車種形状文字列（例:「平-低床」）から WebKIT の付帯項目を抽出。

    該当が無ければキー自体を含めない（未指定=WebKIT側の既定=制限なし）。
    """
    attrs = {}
    if not trabox_shape:
        return attrs
    for label, code in _TRAYHEIGHT_MAP.items():
        if label in trabox_shape:
            attrs["trayheighttype"] = code
            break
    if "パワーゲート" in trabox_shape:
        attrs["loadunit"] = _LOADUNIT_PAWAGATE
    if "エアサス" in trabox_shape:
        attrs["suspension"] = _SUSPENSION_AIRSUS
    return attrs


def get_transport_type_codes(labels) -> str:
    """輸送取扱区分（複数選択・正規化仕様書 #10）のラベル配列 → WebKIT用カンマ区切りコード。

    未知のラベルは無視する。空/Noneなら空文字（フィールド自体を送らない）。
    """
    if not labels:
        return ""
    codes = [TRANSPORT_HANDLING[l] for l in labels if l in TRANSPORT_HANDLING]
    return ",".join(codes)


def get_safety_unit_codes(labels) -> str:
    """必要装備（複数選択・正規化仕様書 #11）のラベル配列 → WebKIT用カンマ区切りコード。

    未知のラベルは無視する。空/Noneなら空文字（フィールド自体を送らない）。
    """
    if not labels:
        return ""
    codes = [SAFETY_DEVICE[l] for l in labels if l in SAFETY_DEVICE]
    return ",".join(codes)


def get_cargo_shape_code(name: str) -> str:
    """輸送品形状名からコードを取得（未知は 10=その他）"""
    return CARGO_SHAPE.get(name, '10')

def get_vehicle_code(name: str) -> str:
    """車種名からコードを取得"""
    return VEHICLE_TYPES.get(name, '')

def get_cargo_type_code(name: str) -> str:
    """輸送品区分名からコードを取得"""
    return CARGO_TYPES.get(name, '')

def get_handling_code(name: str) -> str:
    """荷扱い名からコードを取得"""
    return HANDLING.get(name, '9')
