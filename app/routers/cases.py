from fastapi import APIRouter, HTTPException, status, Form, Depends, Cookie
from fastapi.responses import HTMLResponse, JSONResponse
from app.models.schemas import CaseCreate, Case
from app.db.database import get_db_connection
from app.automations.trabox import TraboxAutomation
from app.automations.webkit import WebkitAutomation
from app.dependencies import get_current_user
from app.services.cloud_tasks import get_task_client
from typing import Optional
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cases", tags=["cases"])

# 都道府県一覧（Trabox の地図ボタンに対応する正式名称）
PREFECTURES = [
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
    "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
    "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県",
    "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県",
    "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県",
    "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県",
    "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
]

# 市区町村一覧のキャッシュ（都道府県ごと・プロセス内）
_CITY_CACHE: dict = {}


@router.get("/api/cities")
async def get_cities(pref: str):
    """都道府県 → 市区町村一覧（HeartRails Geo API のプロキシ＋キャッシュ）

    オープンAPI（キー不要）: https://geoapi.heartrails.com/
    返却形式は Trabox の市区町村選択肢と同じ（政令指定都市は「大阪市北区」形式）
    """
    if pref not in PREFECTURES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不正な都道府県名です: {pref}",
        )
    if pref in _CITY_CACHE:
        return {"pref": pref, "cities": _CITY_CACHE[pref]}

    import urllib.request
    import urllib.parse

    url = (
        "https://geoapi.heartrails.com/api/json?method=getCities&prefecture="
        + urllib.parse.quote(pref)
    )
    try:
        with urllib.request.urlopen(url, timeout=8) as res:
            data = json.loads(res.read())
        cities = [c["city"] for c in data["response"]["location"]]
        if not cities:
            raise ValueError("空の市区町村リスト")
        _CITY_CACHE[pref] = cities
        return {"pref": pref, "cities": cities}
    except Exception as e:
        logger.warning(f"市区町村一覧の取得失敗 ({pref}): {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="市区町村一覧の取得に失敗しました（手入力してください）",
        )

def _get_contact_defaults(access_token: Optional[str]) -> dict:
    """ログイン中ユーザーの連絡先初期設定を取得（未ログイン・未設定なら空欄）

    初期設定画面（/settings/）で登録した連絡先が案件登録フォームに自動入力される。
    """
    empty = {"name": "", "phone": "", "email": ""}
    if not access_token:
        return empty
    try:
        from app.utils.security import decode_access_token
        from app.db import store
        token_data = decode_access_token(access_token)
        if not token_data or not token_data.get("user_id"):
            return empty
        creds = store.get_credentials(token_data["user_id"])
        return {
            "name": creds.get("contact_name", "") or "",
            "phone": creds.get("contact_phone", "") or "",
            "email": creds.get("contact_email", "") or "",
        }
    except Exception as e:
        logger.warning(f"連絡先初期設定の取得失敗（空欄で続行）: {e}")
        return empty


SETUP_REQUIRED_HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Carroo - 初期設定が必要です</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50">
    <nav class="bg-white shadow-sm border-b border-gray-200">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16 items-center">
                <a href="/dashboard/" class="text-2xl font-bold text-blue-600 hover:opacity-80 transition">📦 Carroo</a>
                <div class="flex items-center gap-4">
                    <a href="/auth/me" class="text-gray-600 hover:text-gray-900">プロフィール</a>
                    <a href="/auth/logout" class="text-red-600 hover:text-red-700">ログアウト</a>
                </div>
            </div>
        </div>
    </nav>
    <div class="min-h-screen flex items-center justify-center px-4 -mt-16">
        <div class="max-w-lg w-full bg-white rounded-2xl shadow-lg p-10 text-center">
            <div class="text-6xl mb-4">⚙️</div>
            <h1 class="text-2xl font-bold text-gray-900 mb-4">初期設定が必要です</h1>
            <p class="text-gray-600 mb-8">
                案件登録には<span class="font-semibold">連絡先メールアドレス</span>の登録が必要です。<br>
                投稿の成否通知がこのアドレスに届きます。
            </p>
            <a href="/settings/" class="inline-block bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-8 rounded-lg transition">初期設定へ進む</a>
        </div>
    </div>
</body>
</html>"""


@router.get("/register", response_class=HTMLResponse)
async def case_register_page(access_token: Optional[str] = Cookie(None)):
    contact = _get_contact_defaults(access_token)
    # 🔴 初期設定（連絡先メール）未登録の場合は案件登録に進めない
    if not contact["email"]:
        return HTMLResponse(SETUP_REQUIRED_HTML)
    pref_options = "".join(
        f'<option value="{p}">{p}</option>' for p in PREFECTURES
    )
    # 希望車両の選択肢は Trabox の実ドロップダウンに準拠（TraboxFormMapper が唯一の情報源）
    from app.automations.trabox_form_mapper import TraboxFormMapper
    weight_options = "".join(
        f'<option value="{w}">{w}</option>'
        for w in TraboxFormMapper.TRUCK_WEIGHT_OPTIONS
    )
    shape_options = "".join(
        f'<option value="{s}">{s}</option>'
        for s in TraboxFormMapper.VEHICLE_SHAPE_OPTIONS
    )
    html = """
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Carroo - 案件登録</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-50">
        <!-- ナビゲーションバー -->
        <nav class="bg-white shadow-sm border-b border-gray-200">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="flex justify-between h-16 items-center">
                    <div class="flex items-center">
                        <a href="/dashboard/" class="text-2xl font-bold text-blue-600 hover:opacity-80 transition">📦 Carroo</a>
                    </div>
                    <div class="flex items-center gap-4">
                        <a href="/auth/me" class="text-gray-600 hover:text-gray-900">プロフィール</a>
                        <a href="/auth/logout" class="text-red-600 hover:text-red-700">ログアウト</a>
                    </div>
                </div>
            </div>
        </nav>

        <div class="min-h-screen py-12 px-4">
            <div class="max-w-4xl mx-auto">
                <!-- ヘッダー -->
                <div class="mb-8">
                    <h1 class="text-4xl font-bold text-gray-900 mb-2">案件登録</h1>
                    <p class="text-gray-600">複数のプラットフォームへ一括投稿できます</p>
                </div>

                <!-- フォーム -->
                <div class="bg-white rounded-2xl shadow-lg overflow-hidden">
                    <div class="p-8">

                    <form method="post" action="/cases/register" class="space-y-8">
                        <!-- セクション 1: 基本情報 -->
                        <div>
                            <h3 class="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                                <span class="w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm font-bold mr-3">1</span>
                                基本情報
                            </h3>

                            <!-- 🔴 Trabox は市区町村まで必須（都道府県だけでは登録不可） -->
                            <!-- 積地と積み日時を横並びに配置 -->
                            <div class="mb-6">
                                <h4 class="text-base font-semibold text-gray-800 mb-3">📍 積地・積み日時</h4>
                                <div class="grid grid-cols-1 md:grid-cols-2 gap-6 p-4 border border-gray-200 rounded-lg">
                                    <div class="space-y-4">
                                        <div>
                                            <label class="block text-sm font-medium text-gray-700 mb-2">積み日<span class="ml-1 px-1.5 py-0.5 text-xs font-semibold text-red-600 bg-red-50 rounded">必須</span></label>
                                            <input type="date" name="pickup_date" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 transition" required>
                                        </div>
                                        <div>
                                            <label class="block text-sm font-medium text-gray-700 mb-2">積み時間<span class="ml-1 px-1.5 py-0.5 text-xs font-semibold text-red-600 bg-red-50 rounded">必須</span></label>
                                            <input type="time" name="pickup_time" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 transition" required>
                                        </div>
                                    </div>
                                    <div>
                                        <label class="block text-sm font-medium text-gray-700 mb-2">積地<span class="ml-1 px-1.5 py-0.5 text-xs font-semibold text-red-600 bg-red-50 rounded">必須</span></label>
                                        <div class="space-y-2">
                                            <select name="pick_pref" id="pick_pref" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 transition" required>
                                                <option value="">都道府県を選択</option>
                                                PREF_OPTIONS
                                            </select>
                                            <select name="pick_city" id="pick_city" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 transition bg-white disabled:bg-gray-100 disabled:text-gray-400" required disabled>
                                                <option value="">都道府県を先に選択してください</option>
                                            </select>
                                            <input type="text" name="pick_address" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 transition" placeholder="番地・建物（任意）">
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <!-- 卸地と着日時を横並びに配置 -->
                            <div class="mb-6">
                                <h4 class="text-base font-semibold text-gray-800 mb-3">🏁 卸地・着日時</h4>
                                <div class="grid grid-cols-1 md:grid-cols-2 gap-6 p-4 border border-gray-200 rounded-lg">
                                    <div class="space-y-4">
                                        <div>
                                            <label class="block text-sm font-medium text-gray-700 mb-2">着日<span class="ml-1 px-1.5 py-0.5 text-xs font-semibold text-red-600 bg-red-50 rounded">必須</span></label>
                                            <input type="date" name="drop_date" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 transition" required>
                                        </div>
                                        <div>
                                            <label class="block text-sm font-medium text-gray-700 mb-2">卸し時間<span class="ml-1 px-1.5 py-0.5 text-xs font-semibold text-red-600 bg-red-50 rounded">必須</span></label>
                                            <input type="time" name="drop_time" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 transition" required>
                                        </div>
                                    </div>
                                    <div>
                                        <label class="block text-sm font-medium text-gray-700 mb-2">卸地<span class="ml-1 px-1.5 py-0.5 text-xs font-semibold text-red-600 bg-red-50 rounded">必須</span></label>
                                        <div class="space-y-2">
                                            <select name="drop_pref" id="drop_pref" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 transition" required>
                                                <option value="">都道府県を選択</option>
                                                PREF_OPTIONS
                                            </select>
                                            <select name="drop_city" id="drop_city" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 transition bg-white disabled:bg-gray-100 disabled:text-gray-400" required disabled>
                                                <option value="">都道府県を先に選択してください</option>
                                            </select>
                                            <input type="text" name="drop_address" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 transition" placeholder="番地・建物（任意）">
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-2">荷物重量（kg）<span class="ml-1 px-1.5 py-0.5 text-xs font-semibold text-red-600 bg-red-50 rounded">必須</span></label>
                                    <input type="number" name="cargo_weight" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition" step="0.1" required>
                                </div>
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-2">希望車両（トン数 / 形状）</label>
                                    <div class="flex gap-3">
                                        <select name="truck_weight" class="w-1/2 px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition">
                                            WEIGHT_OPTIONS
                                        </select>
                                        <select name="vehicle_type" class="w-1/2 px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition">
                                            SHAPE_OPTIONS
                                        </select>
                                    </div>
                                </div>
                            </div>

                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-2">運賃（円）<span class="ml-1 px-1.5 py-0.5 text-xs font-semibold text-red-600 bg-red-50 rounded">必須</span></label>
                                <div class="flex items-center gap-4">
                                    <input type="number" name="freight_rate" id="freight_rate" class="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition disabled:bg-gray-100 disabled:text-gray-400" step="100" required>
                                    <label class="flex items-center gap-2 whitespace-nowrap cursor-pointer">
                                        <input type="checkbox" name="freight_negotiable" id="freight_negotiable" value="yes" class="w-5 h-5 text-blue-600 rounded">
                                        <span class="text-sm font-medium text-gray-700">要相談 <span class="text-xs text-gray-500">（Traboxのみ）</span></span>
                                    </label>
                                </div>
                                <p id="webkit-alert" class="hidden mt-2 text-sm font-semibold text-red-600"></p>
                        </div>
                    </div>

                        </div>
                        </div>

                        <!-- セクション 2.5: 詳細設定（Trabox 全項目対応・既定値プリセット） -->
                        <div>
                            <details class="group">
                                <summary class="cursor-pointer text-lg font-semibold text-gray-900 mb-4 flex items-center list-none">
                                    <span class="w-8 h-8 bg-gray-500 text-white rounded-full flex items-center justify-center text-sm font-bold mr-3">+</span>
                                    詳細設定（任意・既定値のままでOK）
                                    <span class="ml-2 text-gray-400 text-sm group-open:hidden">▼ 開く</span>
                                    <span class="ml-2 text-gray-400 text-sm hidden group-open:inline">▲ 閉じる</span>
                                </summary>
                                <div class="grid grid-cols-1 md:grid-cols-2 gap-6 p-4 bg-gray-50 rounded-lg">
                                    <div>
                                        <label class="block text-sm font-medium text-gray-700 mb-2">荷種</label>
                                        <input type="text" name="cargo_type" value="鋼材" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg transition">
                                    </div>
                                    <div>
                                        <label class="block text-sm font-medium text-gray-700 mb-2">荷姿・輸送形状</label>
                                        <select name="package_type" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg transition">
                                            <option value="その他" selected>その他</option>
                                            <option value="パレット">パレット</option>
                                            <option value="ケース">ケース</option>
                                            <option value="袋">袋</option>
                                            <option value="ハダカ">ハダカ</option>
                                            <option value="フレコンパック">フレコンパック</option>
                                            <option value="ドラム類">ドラム類</option>
                                            <option value="缶類">缶類</option>
                                            <option value="ラック">ラック</option>
                                            <option value="バラ">バラ</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label class="block text-sm font-medium text-gray-700 mb-2">台数</label>
                                        <input type="number" name="truck_count" value="1" min="1" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg transition">
                                    </div>
                                    <div>
                                        <label class="block text-sm font-medium text-gray-700 mb-2">積合</label>
                                        <select name="share" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg transition">
                                            <option value="不可" selected>不可</option>
                                            <option value="可能">可能</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label class="block text-sm font-medium text-gray-700 mb-2">高速代</label>
                                        <select name="highway_fee" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg transition">
                                            <option value="支払わない" selected>支払わない</option>
                                            <option value="別途支払う">別途支払う</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label class="block text-sm font-medium text-gray-700 mb-2">おまかせ請求受入可否</label>
                                        <select name="omakase_billing" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg transition">
                                            <option value="受入不可" selected>受入不可</option>
                                            <option value="必須">必須</option>
                                            <option value="推奨">推奨</option>
                                            <option value="受入可">受入可</option>
                                            <option value="未定">未定</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label class="block text-sm font-medium text-gray-700 mb-2">連絡方法</label>
                                        <select name="contact_method" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg transition">
                                            <option value="電話で受付" selected>電話で受付</option>
                                            <option value="オンラインで受付">オンラインで受付</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label class="block text-sm font-medium text-gray-700 mb-2">公開範囲</label>
                                        <select name="visibility" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg transition">
                                            <option value="すべて" selected>すべて</option>
                                            <option value="限定">限定</option>
                                        </select>
                                    </div>
                                    <div class="md:col-span-2">
                                        <label class="flex items-center gap-2 cursor-pointer">
                                            <input type="checkbox" name="moving_case" value="yes" class="w-5 h-5 text-blue-600 rounded">
                                            <span class="text-sm font-medium text-gray-700">引越し案件</span>
                                        </label>
                                    </div>
                                    <div class="md:col-span-2">
                                        <label class="block text-sm font-medium text-gray-700 mb-2">備考</label>
                                        <textarea name="remarks" rows="2" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg transition" placeholder="運送会社への連絡事項など"></textarea>
                                    </div>
                                </div>
                            </details>
                        </div>

                        <!-- セクション 3: 連絡先 -->
                        <div>
                            <h3 class="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                                <span class="w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm font-bold mr-3">3</span>
                                連絡先
                            </h3>

                            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-2">登録者名 <span class="text-xs text-gray-400">（案件を登録した人。一覧で絞り込めます）</span></label>
                                    <input type="text" name="contact_name" value="CONTACT_NAME_VALUE" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition" placeholder="山田太郎">
                                </div>
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-2">電話番号</label>
                                    <input type="tel" name="contact_phone" value="CONTACT_PHONE_VALUE" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition" placeholder="09012345678">
                                </div>
                            </div>

                            <div class="mt-6">
                                <label class="block text-sm font-medium text-gray-700 mb-2">メールアドレス</label>
                                <input type="email" name="contact_email" value="CONTACT_EMAIL_VALUE" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition" placeholder="example@domain.com">
                            </div>
                            <p class="text-xs text-gray-500 mt-2">💡 <a href="/settings/" class="text-blue-600 hover:underline">初期設定</a> に登録した連絡先が自動で入ります（この画面で上書きも可能）</p>
                        </div>

                        <!-- セクション 4: 投稿先選択 -->
                        <div>
                            <h3 class="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                                <span class="w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm font-bold mr-3">4</span>
                                投稿先を選択
                            </h3>

                            <div class="space-y-3">
                                <label class="flex items-center p-4 border border-gray-300 rounded-lg cursor-pointer hover:bg-blue-50 transition">
                                    <input type="checkbox" name="post_to_trabox" value="yes" class="w-5 h-5 text-blue-600 rounded">
                                    <div class="ml-3">
                                        <span class="block font-medium text-gray-900">トラボックス</span>
                                        <span class="block text-sm text-gray-600">Playwright を使用した自動投稿</span>
                                    </div>
                                </label>
                                <label class="flex items-center p-4 border border-gray-300 rounded-lg cursor-pointer hover:bg-blue-50 transition">
                                    <input type="checkbox" name="post_to_webkit" id="post_to_webkit" value="yes" class="w-5 h-5 text-blue-600 rounded">
                                    <div class="ml-3">
                                        <span class="block font-medium text-gray-900">Webkit</span>
                                        <span class="block text-sm text-gray-600">XML API を使用した自動投稿</span>
                                    </div>
                                </label>
                            </div>
                        </div>

                        <!-- トラボックス認証情報 -->
                        <div id="trabox-auth" class="hidden bg-gradient-to-br from-blue-50 to-blue-100 p-6 rounded-lg border border-blue-200">
                            <h4 class="font-semibold text-gray-900 mb-4">🔐 トラボックスのログイン情報</h4>
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-2">ユーザーID</label>
                                    <input type="text" name="trabox_username" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition" placeholder="ログインID">
                                </div>
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-2">パスワード</label>
                                    <input type="password" name="trabox_password" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition" placeholder="パスワード">
                                </div>
                            </div>
                        </div>

                        <!-- 送信ボタン -->
                        <button type="submit" class="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-lg transition duration-200 mt-8">
                            ✓ 案件を登録
                        </button>
                    </form>
                    </div>
                </div>
            </div>
        </div>
            </div>
        </div>

        <script>
            // 都道府県 → 市区町村の連動セレクト（積地/卸地それぞれ独立に動作）
            function setupCityLoader(prefId, cityId) {
                const prefSel = document.getElementById(prefId);
                const citySel = () => document.getElementById(cityId);

                prefSel.addEventListener('change', async () => {
                    const sel = citySel();
                    const pref = prefSel.value;
                    if (!pref) {
                        sel.innerHTML = '<option value="">都道府県を先に選択してください</option>';
                        sel.disabled = true;
                        return;
                    }
                    sel.innerHTML = '<option value="">読み込み中...</option>';
                    sel.disabled = true;
                    try {
                        const res = await fetch('/cases/api/cities?pref=' + encodeURIComponent(pref));
                        if (!res.ok) throw new Error('API error');
                        const data = await res.json();
                        sel.innerHTML = '<option value="">市区町村を選択</option>' +
                            data.cities.map(c => '<option value="' + c + '">' + c + '</option>').join('');
                        sel.disabled = false;
                    } catch (e) {
                        // API失敗時は手入力にフォールバック
                        const input = document.createElement('input');
                        input.type = 'text';
                        input.name = sel.name;
                        input.id = cityId;
                        input.required = true;
                        input.placeholder = '市区町村を入力（例: 港区）';
                        input.className = 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 transition';
                        sel.replaceWith(input);
                    }
                });
            }
            setupCityLoader('pick_pref', 'pick_city');
            setupCityLoader('drop_pref', 'drop_city');

            // 運賃「要相談」と WebKit の排他制御
            // （WebKit は金額必須のため、要相談の案件は Trabox にしか投稿できない）
            const negotiableCheckbox = document.getElementById('freight_negotiable');
            const freightInput = document.getElementById('freight_rate');
            const webkitCheckbox = document.getElementById('post_to_webkit');
            const webkitAlert = document.getElementById('webkit-alert');

            function showWebkitAlert(message) {
                webkitAlert.textContent = '⚠ ' + message;
                webkitAlert.classList.remove('hidden');
                setTimeout(() => webkitAlert.classList.add('hidden'), 5000);
            }

            negotiableCheckbox.addEventListener('change', () => {
                if (negotiableCheckbox.checked) {
                    freightInput.disabled = true;
                    freightInput.required = false;
                    freightInput.value = '';
                    if (webkitCheckbox.checked) {
                        webkitCheckbox.checked = false;
                        showWebkitAlert('金額の要相談にチェックが入っているため WebKit の選択を解除しました');
                    }
                } else {
                    freightInput.disabled = false;
                    freightInput.required = true;
                }
            });

            webkitCheckbox.addEventListener('click', (e) => {
                if (negotiableCheckbox.checked) {
                    e.preventDefault();
                    showWebkitAlert('金額の要相談にチェックが入っているため WebKit を選べません');
                }
            });

            const traboxCheckbox = document.querySelector('input[name="post_to_trabox"]');
            const traboxAuth = document.getElementById('trabox-auth');

            traboxCheckbox.addEventListener('change', () => {
                traboxAuth.classList.toggle('hidden');
            });
        </script>
    </body>
    </html>
    """
    return (
        html.replace("PREF_OPTIONS", pref_options)
        .replace("WEIGHT_OPTIONS", weight_options)
        .replace("SHAPE_OPTIONS", shape_options)
        .replace("CONTACT_NAME_VALUE", contact["name"])
        .replace("CONTACT_PHONE_VALUE", contact["phone"])
        .replace("CONTACT_EMAIL_VALUE", contact["email"])
    )

@router.post("/register")
async def register_case(
    # 後方互換: 旧API（結合済み文字列）でも新UI（pref+city 分割）でも受け付ける
    pick_location: Optional[str] = Form(None),
    drop_location: Optional[str] = Form(None),
    cargo_weight: float = Form(...),
    vehicle_type: str = Form("問わず"),
    truck_weight: Optional[str] = Form(None),
    moving_case: Optional[str] = Form(None),
    freight_rate: Optional[float] = Form(None),
    freight_negotiable: Optional[str] = Form(None),
    pickup_date: str = Form(...),
    pickup_time: Optional[str] = Form(None),
    contact_name: Optional[str] = Form(None),
    contact_phone: Optional[str] = Form(None),
    contact_email: Optional[str] = Form(None),
    post_to_trabox: Optional[str] = Form(None),
    post_to_webkit: Optional[str] = Form(None),
    # --- 発地/着地の分割入力（Trabox は市区町村必須） ---
    pick_pref: Optional[str] = Form(None),
    pick_city: Optional[str] = Form(None),
    pick_address: Optional[str] = Form(None),
    drop_pref: Optional[str] = Form(None),
    drop_city: Optional[str] = Form(None),
    drop_address: Optional[str] = Form(None),
    # --- 拡張キー（Trabox フォーム全項目 = 必要十分条件。未指定は既定値） ---
    drop_date: Optional[str] = Form(None),
    drop_time: Optional[str] = Form(None),
    cargo_type: Optional[str] = Form(None),
    package_type: Optional[str] = Form(None),
    truck_count: Optional[int] = Form(None),
    share: Optional[str] = Form(None),
    highway_fee: Optional[str] = Form(None),
    omakase_billing: Optional[str] = Form(None),
    contact_method: Optional[str] = Form(None),
    visibility: Optional[str] = Form(None),
    remarks: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
):
    """
    案件登録 + 非同期投稿キュー追加エンドポイント

    フロー（GCP Cloud Tasks）:
    1. DB に案件データを保存（同期）
    2. Cloud Tasks にタスク追加（0.1秒で即座に返す）
    3. 背景で Cloud Run が投稿処理を実行

    投稿先:
    - トラボックス: .env の TRABOX_TEST_USERNAME, TRABOX_TEST_PASSWORD
    - WebKIT: .env の WEBKIT_LOGIN_ID, WEBKIT_LOGIN_PASSWORD
    """

    from app.db import store

    try:
        user_id = current_user["id"]

        # チェックボックスの値を堅牢に判定
        # （ブラウザは value 未指定のチェックボックスを "on" で送るため
        #   "yes"/"on"/"true"/"1" いずれも「チェック済み」とみなす）
        def _checked(v) -> bool:
            return str(v).lower() in ("yes", "on", "true", "1")

        want_trabox = _checked(post_to_trabox)
        want_webkit = _checked(post_to_webkit)

        # Step 0: 発地/着地を組み立て（新UI: pref+city+address 分割入力）
        # Trabox は市区町村必須のため「東京都港区」形式に結合する
        if pick_pref and pick_city:
            pick_location = f"{pick_pref}{pick_city}{pick_address or ''}"
        if drop_pref and drop_city:
            drop_location = f"{drop_pref}{drop_city}{drop_address or ''}"
        if not pick_location or not drop_location:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="発地・着地は都道府県と市区町村まで必須です（例: 東京都港区）",
            )

        # 積み時間・着日・卸し時間は必須（ブラウザ回避の送信に対する防御）
        if not pickup_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="積み時間は必須です",
            )
        if not drop_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="着日は必須です",
            )
        if not drop_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="卸し時間は必須です",
            )

        # 🔴 初期設定（連絡先メール）未登録なら登録不可（通知先が無いため）
        if not store.get_credentials(user_id).get("contact_email"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="初期設定でメールアドレスを登録してから案件登録してください（/settings/）",
            )

        # 運賃: 金額指定 or 要相談のどちらかが必須。
        # 要相談は Trabox のみ対応（WebKit は金額必須のため併用不可）
        is_negotiable = freight_negotiable == "yes"
        if not is_negotiable and freight_rate is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="運賃の金額を入力するか「要相談」にチェックしてください",
            )
        if is_negotiable and want_webkit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="金額の要相談にチェックが入っているため WebKit を選べません",
            )
        if is_negotiable:
            freight_rate = 0  # DB は NOT NULL のため 0 を保存（実値は要相談）

        # 拡張キー（Trabox フォーム全項目に対応。指定されたものだけ保持し、
        # 未指定は投稿時に TraboxFormMapper.TRABOX_DEFAULTS が適用される）
        extras = {
            k: v for k, v in {
                "truck_weight": truck_weight,
                "moving_case": True if moving_case == "yes" else None,
                "freight_negotiable": True if is_negotiable else None,
                "drop_date": drop_date,
                "drop_time": drop_time,
                "cargo_type": cargo_type,
                "package_type": package_type,
                "truck_count": truck_count,
                "share": share,
                "highway_fee": highway_fee,
                "omakase_billing": omakase_billing,
                "contact_method": contact_method,
                "visibility": visibility,
                "remarks": remarks,
            }.items() if v not in (None, "")
        }

        # Step 1: 案件データを Firestore に保存（extras は map で保持。contact_name=登録者名）
        case_id = store.create_case(user_id, {
            "pick_location": pick_location, "drop_location": drop_location,
            "cargo_weight": cargo_weight, "vehicle_type": vehicle_type,
            "freight_rate": freight_rate, "pickup_date": pickup_date,
            "pickup_time": pickup_time, "contact_name": contact_name,
            "contact_phone": contact_phone, "contact_email": contact_email,
            "extras": extras,
        })

        # Step 2: 投稿用データを構築（拡張キーはフラットにマージ）
        case_data = {
            "case_id": case_id,
            "user_id": user_id,
            "pick_location": pick_location,
            "drop_location": drop_location,
            "cargo_weight": cargo_weight,
            "vehicle_type": vehicle_type,
            "freight_rate": freight_rate,
            "pickup_date": pickup_date,
            "pickup_time": pickup_time,
            "contact_name": contact_name,
            "contact_phone": contact_phone,
            "contact_email": contact_email,
            "post_to_trabox": want_trabox,
            "post_to_webkit": want_webkit,
            **extras,
        }

        # Step 3: Cloud Tasks にタスク追加（0.1秒で返す）
        task_client = get_task_client()
        task_name = task_client.add_posting_task(case_data, user_id)
        logger.info(f"✅ タスク追加: Case ID {case_id} → {task_name}")

        # Step 4: posting_history に「pending」状態で記録（追記式）
        if want_trabox:
            store.add_posting_event(case_id, "trabox", "register", "pending")
        if want_webkit:
            store.add_posting_event(case_id, "webkit", "register", "pending")

        # Step 5: 結果画面を返す（投稿処理は背景で実行される）
        platforms = []
        if want_trabox:
            platforms.append("トラボックス")
        if want_webkit:
            platforms.append("WebKit")
        platforms_text = "・".join(platforms) if platforms else "なし（案件保存のみ）"

        return HTMLResponse(f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Carroo - 登録完了</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50">
    <nav class="bg-white shadow-sm border-b border-gray-200">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16 items-center">
                <a href="/dashboard/" class="text-2xl font-bold text-blue-600 hover:opacity-80 transition">📦 Carroo</a>
                <div class="flex items-center gap-4">
                    <a href="/auth/me" class="text-gray-600 hover:text-gray-900">プロフィール</a>
                    <a href="/auth/logout" class="text-red-600 hover:text-red-700">ログアウト</a>
                </div>
            </div>
        </div>
    </nav>

    <div class="min-h-screen flex items-center justify-center px-4 -mt-16">
        <div class="max-w-lg w-full bg-white rounded-2xl shadow-lg p-10 text-center">
            <div class="text-6xl mb-4">✅</div>
            <h1 class="text-2xl font-bold text-gray-900 mb-2">案件を登録しました</h1>
            <p class="text-gray-600 mb-6">案件ID: <span class="font-mono font-semibold">{case_id}</span></p>

            <div class="text-left bg-gray-50 rounded-lg p-4 mb-6 text-sm space-y-2">
                <p><span class="text-gray-500">積地:</span> <span class="font-medium">{pick_location}</span></p>
                <p><span class="text-gray-500">卸地:</span> <span class="font-medium">{drop_location}</span></p>
                <p><span class="text-gray-500">積み日:</span> <span class="font-medium">{pickup_date}</span></p>
                <p><span class="text-gray-500">投稿先:</span> <span class="font-medium">{platforms_text}</span></p>
            </div>

            <p class="text-sm text-gray-500 mb-8">
                投稿は背景で実行中です（1〜2分程度）。<br>
                結果（成功/失敗・荷物番号）はダッシュボードの案件詳細で確認できます。
            </p>

            <div class="flex gap-4 justify-center">
                <a href="/cases/{case_id}/manage" class="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2.5 px-6 rounded-lg transition">投稿状況を確認</a>
                <a href="/cases/register" class="bg-gray-100 hover:bg-gray-200 text-gray-900 font-semibold py-2.5 px-6 rounded-lg transition">続けて登録</a>
            </div>
        </div>
    </div>
</body>
</html>""")

    except HTTPException:
        # バリデーションエラー等はそのまま返す（detail を握りつぶさない）
        raise
    except Exception as e:
        logger.error(f"❌ エラー: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ============ 案件管理（変更・削除）画面とエンドポイント ============

def _platform_label(p: str) -> str:
    return {"trabox": "トラボックス", "webkit": "WebKit"}.get(p, p)


def _load_case_row(case_id: int, user_id: int):
    """案件を取得（store の dict をそのまま返す。extras は map）"""
    from app.db import store
    return store.get_case(case_id, user_id)


@router.get("/{case_id}/manage", response_class=HTMLResponse)
async def case_manage_page(case_id: int, access_token: Optional[str] = Cookie(None)):
    """案件管理画面: プラットフォーム別/一括の変更・削除＋投稿履歴タイムライン"""
    from app.utils.security import decode_access_token
    from app.db import store
    from app.db.store import get_platform_state, get_active_baggage_no
    td = decode_access_token(access_token) if access_token else None
    user_id = td.get("user_id") if td else None
    if not user_id:
        return HTMLResponse('<meta http-equiv="refresh" content="0; url=/auth/login">')

    row = _load_case_row(case_id, user_id)
    if not row:
        return HTMLResponse("<h1>案件が見つかりません</h1>", status_code=404)

    extras = row.get("extras") or {}
    pickup = f"{row.get('pickup_date','')} {row.get('pickup_time') or ''}".strip()
    drop = f"{extras.get('drop_date','')} {extras.get('drop_time','')}".strip() or "翌日"
    freight = "要相談" if extras.get("freight_negotiable") else f"{int(float(row.get('freight_rate') or 0)):,}円（税別）"

    # プラットフォームカード
    STATE = {
        "live": ('● 掲載中', 'text-green-700 bg-green-50 border-green-200'),
        "deleted": ('✓ 削除済み', 'text-gray-500 bg-gray-100 border-gray-200'),
        "working": ('◍ 処理中…', 'text-amber-700 bg-amber-50 border-amber-200'),
        "error": ('⚠ エラー', 'text-red-700 bg-red-50 border-red-200'),
        "none": ('未投稿', 'text-gray-400 bg-gray-50 border-gray-200'),
    }
    cards = ""
    active_platforms = []
    for p, dot in (("trabox", "#16a34a"), ("webkit", "#7c3aed")):
        st = get_platform_state(case_id, p)
        no = get_active_baggage_no(case_id, p)
        if st in ("live", "working"):
            active_platforms.append(p)
        badge_txt, badge_cls = STATE[st]
        num_label = "伝票番号" if p == "webkit" else "荷物番号"
        num_html = f'<p class="text-sm text-gray-600 mt-1">{num_label} <span class="font-mono font-semibold text-gray-900">{no}</span></p>' if no else ''
        disabled = 'disabled' if st in ("working", "none") else ''
        if st == "live":
            actions = f'''
              <button onclick="editCase('{p}')" class="flex-1 border border-gray-300 rounded-lg py-2 text-sm font-semibold hover:bg-gray-50">変更</button>
              <button onclick="deleteCase('{p}')" class="flex-1 border border-red-200 text-red-600 bg-red-50 rounded-lg py-2 text-sm font-semibold hover:brightness-95">削除</button>'''
        elif st == "deleted":
            actions = f'<button onclick="editCase(\'{p}\',true)" class="flex-1 border border-gray-300 rounded-lg py-2 text-sm font-semibold hover:bg-gray-50">再投稿</button>'
        elif st == "working":
            actions = '<span class="text-sm text-amber-700">処理完了までお待ちください（メールでも通知します）</span>'
        else:
            actions = f'<button onclick="editCase(\'{p}\',true)" class="flex-1 border border-gray-300 rounded-lg py-2 text-sm font-semibold hover:bg-gray-50">投稿する</button>'
        cards += f'''
        <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-5 flex flex-col gap-3">
          <div class="flex items-center justify-between">
            <span class="font-bold flex items-center gap-2"><span style="width:9px;height:9px;border-radius:50%;background:{dot};display:inline-block"></span>{_platform_label(p)}</span>
            <span class="text-xs font-bold px-2.5 py-1 rounded-full border {badge_cls}">{badge_txt}</span>
          </div>
          {num_html}
          <div class="flex gap-2 mt-1">{actions}</div>
        </div>'''

    # 履歴タイムライン（Firestore）
    hist = store.list_posting_history(case_id)
    ACT = {"register": ("登録", "text-green-700 bg-green-50 border-green-200"),
           "update": ("変更", "text-blue-700 bg-blue-50 border-blue-200"),
           "delete": ("削除", "text-red-700 bg-red-50 border-red-200")}
    ST_TXT = {"success": "成功", "error": "失敗", "pending": "処理中"}
    rows_html = ""
    for h in hist:
        plat, action, stt = h.get("platform"), h.get("action"), h.get("status")
        no, err = h.get("baggage_no"), h.get("error_message")
        ts = h.get("updated_at") or h.get("posted_at")
        act_txt, act_cls = ACT.get(action, (action, ""))
        detail = ""
        if no:
            lbl = "伝票番号" if plat == "webkit" else "荷物番号"
            detail = f'<span class="text-gray-500 font-mono">{lbl} {no}</span>'
        if stt == "error" and err:
            detail = f'<span class="text-red-600">{err[:80]}</span>'
        rows_html += f'''
        <div class="grid grid-cols-[130px_110px_1fr] gap-3 items-baseline px-4 py-3 border-b border-gray-100 last:border-0">
          <span class="text-xs text-gray-500 font-mono">{ts or ''}</span>
          <span class="text-sm font-semibold">{_platform_label(plat)}</span>
          <span class="text-sm text-gray-700"><span class="font-bold">{act_txt} {ST_TXT.get(stt,stt)}</span>
            <span class="text-xs font-bold px-2 py-0.5 rounded border {act_cls} ml-1">{act_txt}</span> {detail}</span>
        </div>'''
    if not rows_html:
        rows_html = '<p class="text-gray-400 text-center py-8">履歴がありません</p>'

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Carroo - 案件管理 #{case_id}</title><script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-gray-50">
<nav class="bg-white shadow-sm border-b border-gray-200"><div class="max-w-4xl mx-auto px-4 py-3.5 flex items-center justify-between">
  <a href="/dashboard/" class="text-2xl font-bold text-blue-600 hover:opacity-80">📦 Carroo</a>
  <div class="flex gap-4 text-sm text-gray-600"><a href="/dashboard/" class="hover:text-blue-600">ダッシュボード</a><a href="/auth/logout" class="hover:text-red-600">ログアウト</a></div>
</div></nav>
<div class="max-w-4xl mx-auto px-4 py-8">
  <p class="text-sm text-gray-500 mb-3"><a href="/dashboard/" class="text-blue-600">ダッシュボード</a> › 案件 #{case_id}</p>
  <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
    <div class="text-xs text-gray-500 font-mono">案件 ID {case_id} ・ {row.get('created_at','')} 登録 ・ 登録者: {row.get('contact_name','') or '-'}</div>
    <h1 class="text-2xl font-bold mt-1">{row.get('pick_location','')} <span class="text-gray-400 font-normal mx-2">→</span> {row.get('drop_location','')}</h1>
    <div class="flex flex-wrap gap-x-6 gap-y-1 mt-4 text-sm text-gray-700">
      <span><span class="text-gray-400 mr-1">積み</span>{pickup}</span>
      <span><span class="text-gray-400 mr-1">着</span>{drop}</span>
      <span><span class="text-gray-400 mr-1">車両</span>{extras.get('truck_weight','')} {row.get('vehicle_type','')}</span>
      <span><span class="text-gray-400 mr-1">荷種</span>{extras.get('cargo_type','鋼材')}</span>
      <span><span class="text-gray-400 mr-1">運賃</span>{freight}</span>
    </div>
  </div>

  <div class="flex items-center gap-3 mt-5 mb-1 flex-wrap">
    <span class="text-sm text-gray-500">一括操作:</span>
    <button onclick="editCase('both')" class="bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold px-4 py-2 rounded-lg">両方を変更</button>
    <button onclick="deleteCase('both')" class="border border-red-200 text-red-600 bg-red-50 text-sm font-semibold px-4 py-2 rounded-lg hover:brightness-95">両方を削除</button>
  </div>
  <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-2">{cards}</div>

  <h2 class="text-base font-bold mt-8 mb-1">投稿履歴</h2>
  <p class="text-sm text-gray-500 mb-3">登録・変更・削除をすべて記録します。削除しても登録の履歴は残ります。</p>
  <div class="bg-white rounded-xl border border-gray-200 shadow-sm">{rows_html}</div>
</div>

<form id="actForm" method="post" style="display:none"><input type="hidden" name="platforms" id="fPlatforms"></form>
<script>
  const CASE_ID = {case_id};
  function editCase(which) {{
    const p = which === 'both' ? 'trabox,webkit' : which;
    location.href = '/cases/' + CASE_ID + '/edit?platforms=' + p;
  }}
  function deleteCase(which) {{
    const plats = which === 'both' ? 'トラボックスとWebKitの両方' : (which==='trabox'?'トラボックス':'WebKit');
    if (!confirm(plats + 'の掲載を削除します。よろしいですか？（登録の履歴は残ります）')) return;
    const f = document.getElementById('actForm');
    f.action = '/cases/' + CASE_ID + '/delete';
    document.getElementById('fPlatforms').value = which === 'both' ? 'trabox,webkit' : which;
    f.submit();
  }}
</script>
</body></html>""")


@router.post("/{case_id}/delete")
async def case_delete(case_id: int, platforms: str = Form(...),
                      current_user: dict = Depends(get_current_user)):
    """指定プラットフォームの掲載を削除（非同期）。履歴に delete を追記"""
    from app.db import store
    user_id = current_user["id"]
    row = _load_case_row(case_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="案件が見つかりません")
    plats = [p for p in platforms.split(",") if p in ("trabox", "webkit")]
    if not plats:
        raise HTTPException(status_code=400, detail="削除対象のプラットフォームが不正です")
    # 履歴に delete イベントを pending で追記
    for p in plats:
        store.add_posting_event(case_id, p, "delete", "pending")
    # 非同期タスクを投入
    get_task_client().add_task({
        "action": "delete", "user_id": user_id, "case_id": case_id, "platforms": plats,
    })
    return HTMLResponse(f'<meta http-equiv="refresh" content="0; url=/cases/{case_id}/manage">')


@router.get("/{case_id}/edit", response_class=HTMLResponse)
async def case_edit_page(case_id: int, platforms: str = "trabox,webkit",
                         access_token: Optional[str] = Cookie(None)):
    """変更フォーム（現在値プリフィル）。platforms で対象を指定（一括/個別）"""
    from app.utils.security import decode_access_token
    td = decode_access_token(access_token) if access_token else None
    user_id = td.get("user_id") if td else None
    if not user_id:
        return HTMLResponse('<meta http-equiv="refresh" content="0; url=/auth/login">')
    row = _load_case_row(case_id, user_id)
    if not row:
        return HTMLResponse("<h1>案件が見つかりません</h1>", status_code=404)
    ex = row.get("extras") or {}
    pl, dl = row.get("pick_location", ""), row.get("drop_location", "")
    plats = [p for p in platforms.split(",") if p in ("trabox", "webkit")]
    target_label = "・".join(_platform_label(p) for p in plats)

    from app.automations.trabox_form_mapper import TraboxFormMapper as M
    pick_pref_full = next((p for p in PREFECTURES if pl.startswith(p)), "")
    drop_pref_full = next((p for p in PREFECTURES if dl.startswith(p)), "")
    pick_city = M.extract_city(pl) or ""
    drop_city = M.extract_city(dl) or ""

    def opts(items, selected):
        return "".join(f'<option value="{i}"{" selected" if i==selected else ""}>{i}</option>' for i in items)
    weight_opts = opts(M.TRUCK_WEIGHT_OPTIONS, ex.get("truck_weight", "問わず"))
    shape_opts = opts(M.VEHICLE_SHAPE_OPTIONS, row.get("vehicle_type", ""))
    pref_opts_pick = '<option value="">都道府県</option>' + opts(PREFECTURES, pick_pref_full)
    pref_opts_drop = '<option value="">都道府県</option>' + opts(PREFECTURES, drop_pref_full)
    freight_val = "" if ex.get("freight_negotiable") else int(float(row.get("freight_rate") or 0))

    I = 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Carroo - 変更 #{case_id}</title><script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-gray-50">
<nav class="bg-white shadow-sm border-b border-gray-200"><div class="max-w-3xl mx-auto px-4 py-3.5 flex items-center justify-between">
  <a href="/dashboard/" class="text-2xl font-bold text-blue-600 hover:opacity-80">📦 Carroo</a>
  <a href="/cases/{case_id}/manage" class="text-sm text-gray-600 hover:text-blue-600">← 案件管理へ戻る</a>
</div></nav>
<div class="max-w-3xl mx-auto px-4 py-8">
  <h1 class="text-2xl font-bold">案件の変更</h1>
  <p class="text-gray-600 mt-1 mb-6">変更対象: <span class="font-semibold text-blue-700">{target_label}</span> ・ 案件 #{case_id}</p>
  <form method="post" action="/cases/{case_id}/update" class="bg-white rounded-xl border border-gray-200 shadow-sm p-6 space-y-5">
    <input type="hidden" name="platforms" value="{','.join(plats)}">
    <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
      <div><label class="block text-sm font-medium mb-1">積み日</label><input type="date" name="pickup_date" value="{row.get('pickup_date','')}" class="{I}" required></div>
      <div><label class="block text-sm font-medium mb-1">積み時間</label><input type="time" name="pickup_time" value="{row.get('pickup_time') or ''}" class="{I}" required></div>
      <div><label class="block text-sm font-medium mb-1">着日</label><input type="date" name="drop_date" value="{ex.get('drop_date','')}" class="{I}" required></div>
      <div><label class="block text-sm font-medium mb-1">卸し時間</label><input type="time" name="drop_time" value="{ex.get('drop_time','')}" class="{I}" required></div>
    </div>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
      <div><label class="block text-sm font-medium mb-1">積地</label>
        <div class="flex gap-2"><select name="pick_pref" class="{I}" required>{pref_opts_pick}</select>
        <input type="text" name="pick_city" value="{pick_city}" placeholder="市区町村" class="{I}" required></div></div>
      <div><label class="block text-sm font-medium mb-1">卸地</label>
        <div class="flex gap-2"><select name="drop_pref" class="{I}" required>{pref_opts_drop}</select>
        <input type="text" name="drop_city" value="{drop_city}" placeholder="市区町村" class="{I}" required></div></div>
    </div>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
      <div><label class="block text-sm font-medium mb-1">荷物重量(kg)</label><input type="number" name="cargo_weight" value="{int(float(row.get('cargo_weight') or 0))}" class="{I}" required></div>
      <div><label class="block text-sm font-medium mb-1">希望車両（トン数/形状）</label>
        <div class="flex gap-2"><select name="truck_weight" class="{I}">{weight_opts}</select><select name="vehicle_type" class="{I}">{shape_opts}</select></div></div>
      <div><label class="block text-sm font-medium mb-1">荷種</label><input type="text" name="cargo_type" value="{ex.get('cargo_type','鋼材')}" class="{I}"></div>
      <div><label class="block text-sm font-medium mb-1">運賃(円)</label><input type="number" name="freight_rate" value="{freight_val}" class="{I}"></div>
      <div><label class="block text-sm font-medium mb-1">登録者名</label><input type="text" name="contact_name" value="{row.get('contact_name','') or ''}" class="{I}"></div>
    </div>
    <div class="flex gap-3 pt-2">
      <button type="submit" class="bg-blue-600 hover:bg-blue-700 text-white font-semibold px-6 py-2.5 rounded-lg">この内容で変更する</button>
      <a href="/cases/{case_id}/manage" class="bg-gray-100 hover:bg-gray-200 text-gray-900 font-semibold px-6 py-2.5 rounded-lg">キャンセル</a>
    </div>
  </form>
</div></body></html>""")


@router.post("/{case_id}/update")
async def case_update(case_id: int,
                      platforms: str = Form(...),
                      pickup_date: str = Form(...), pickup_time: str = Form(...),
                      drop_date: str = Form(...), drop_time: str = Form(...),
                      pick_pref: str = Form(...), pick_city: str = Form(...),
                      drop_pref: str = Form(...), drop_city: str = Form(...),
                      cargo_weight: float = Form(...), truck_weight: str = Form(None),
                      vehicle_type: str = Form("問わず"), cargo_type: str = Form("鋼材"),
                      freight_rate: Optional[float] = Form(None),
                      contact_name: str = Form(None),
                      current_user: dict = Depends(get_current_user)):
    """案件を変更: cases を更新し、指定プラットフォームへ非同期で変更を反映"""
    from app.db import store
    user_id = current_user["id"]
    row = store.get_case(case_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="案件が見つかりません")
    plats = [p for p in platforms.split(",") if p in ("trabox", "webkit")]
    if not plats:
        raise HTTPException(status_code=400, detail="対象プラットフォームが不正です")

    pick_location = f"{pick_pref}{pick_city}"
    drop_location = f"{drop_pref}{drop_city}"
    extras = dict(row.get("extras") or {})
    extras.update({
        "truck_weight": truck_weight, "drop_date": drop_date, "drop_time": drop_time,
        "cargo_type": cargo_type,
    })
    fields = {
        "pick_location": pick_location, "drop_location": drop_location,
        "cargo_weight": cargo_weight, "vehicle_type": vehicle_type,
        "freight_rate": freight_rate or 0, "pickup_date": pickup_date,
        "pickup_time": pickup_time, "extras": extras,
    }
    if contact_name is not None:
        fields["contact_name"] = contact_name  # 登録者名の変更も反映
    store.update_case(case_id, user_id, fields)

    # 履歴に update を pending 追記 → 非同期タスク投入
    for p in plats:
        store.add_posting_event(case_id, p, "update", "pending")
    get_task_client().add_task({
        "action": "update", "user_id": user_id, "case_id": case_id, "platforms": plats,
    })
    return HTMLResponse(f'<meta http-equiv="refresh" content="0; url=/cases/{case_id}/manage">')
