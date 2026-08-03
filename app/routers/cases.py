from fastapi import APIRouter, HTTPException, status, Form, Depends, Cookie, Query
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


def _setup_required_html(user: Optional[dict] = None) -> str:
    from app.ui_shell import render_page
    body = """
  <div class="card" style="max-width:480px;margin:8px auto;padding:36px;text-align:center">
    <div style="font-size:44px;line-height:1;margin-bottom:14px">⚙️</div>
    <h1 class="pt" style="margin-bottom:10px">初期設定が必要です</h1>
    <p class="hl" style="margin:0 0 24px">案件登録には<b style="color:var(--ink)">連絡先メールアドレス</b>の登録が必要です。<br>
      投稿の成否通知がこのアドレスに届きます。</p>
    <a class="btn" href="/settings/">初期設定へ進む</a>
  </div>"""
    return render_page(title="初期設定が必要です", active="load_new", body=body, user=user)


@router.get("/register", response_class=HTMLResponse)
async def case_register_page(access_token: Optional[str] = Cookie(None),
                             from_id: int = Query(None, alias="from")):
    contact = _get_contact_defaults(access_token)
    # 🔴 初期設定（連絡先メール）未登録の場合は案件登録に進めない
    if not contact["email"]:
        return HTMLResponse(_setup_required_html(_user_from_token(access_token)))
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
        <link rel="stylesheet" href="/static/tailwind.css">
    </head>
    <body class="bg-gray-50">
        <!-- ナビゲーションバー（共通） -->
        MAIN_NAV

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
                                            <div class="flex gap-2">
                                                <input type="time" name="pickup_time" class="w-1/2 px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 transition" required>
                                                <select name="loading_time_option" class="webkit-time-opt w-1/2 px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 transition">
                                                    <option value="以降">以降</option>
                                                    <option value="必着">必着</option>
                                                    <option value="迄">迄</option>
                                                    <option value="から">から</option>
                                                </select>
                                            </div>
                                            <p class="text-xs text-gray-500 mt-1">WebKit投稿時は必須項目です</p>
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
                                            <div class="flex gap-2">
                                                <input type="time" name="drop_time" class="w-1/2 px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 transition" required>
                                                <select name="unloading_time_option" class="webkit-time-opt w-1/2 px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 transition">
                                                    <option value="以降">以降</option>
                                                    <option value="必着">必着</option>
                                                    <option value="迄">迄</option>
                                                    <option value="から">から</option>
                                                </select>
                                            </div>
                                            <p class="text-xs text-gray-500 mt-1">WebKit投稿時は必須項目です</p>
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
                            MULTIDATE_UI

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

            // WebKit投稿時は積み/卸し時間区分（以降・必着・迄・から）を必須にする
            const timeOptSelects = document.querySelectorAll('.webkit-time-opt');
            function syncTimeOptRequired() {
                timeOptSelects.forEach(el => { el.required = webkitCheckbox.checked; });
            }
            webkitCheckbox.addEventListener('change', syncTimeOptRequired);
            syncTimeOptRequired();

        </script>
    </body>
    </html>
    """
    # 複数日程一括投稿（FEATURE_MULTIDATE 有効時のみ UI を差し込む。オプション機能）
    from app.tenancy import feature_enabled
    from app.ui_shell import shell_open, SHELL_CLOSE
    multidate_ui = _MULTIDATE_UI if feature_enabled("multidate") else ""
    built = (
        html.replace("MAIN_NAV", "")
        .replace("MULTIDATE_UI", multidate_ui)
        .replace("PREF_OPTIONS", pref_options)
        .replace("WEIGHT_OPTIONS", weight_options)
        .replace("SHAPE_OPTIONS", shape_options)
        .replace("CONTACT_NAME_VALUE", contact["name"])
        .replace("CONTACT_PHONE_VALUE", contact["phone"])
        .replace("CONTACT_EMAIL_VALUE", contact["email"])
    )
    # 既存テンプレの中身だけを取り出して左レール・シェルで包む
    inner = built.split('<body class="bg-gray-50">', 1)[-1].rsplit("</body>", 1)[0]
    # 履歴から再登録（Pro機能）: 過去の案件を元にフォームを埋める。日付は引き継がない。
    _user = _user_from_token(access_token)
    if from_id and feature_enabled("reregister", _user):
        prefill = _case_prefill(from_id, _user)
        if prefill:
            import json as _json
            from app.widgets import PREFILL_JS
            inner += (f'<script>window.__prefill={_json.dumps(prefill, ensure_ascii=False)};</script>'
                      + PREFILL_JS)
    return shell_open(title="荷物を出す", active="load_new",
                      user=_user) + inner + SHELL_CLOSE


def _case_prefill(case_id: int, user: dict) -> Optional[dict]:
    """再登録用: 既存案件から登録フォームの初期値 dict を作る（日付は除く）。"""
    from app.db import store
    from app.automations.trabox_form_mapper import TraboxFormMapper as M
    row = store.get_case(case_id, None if user and user.get("is_admin") else (user or {}).get("id"))
    if not row:
        return None
    ex = row.get("extras") or {}
    pl = row.get("pick_location", "") or ""
    dl = row.get("drop_location", "") or ""
    pick_pref = next((p for p in PREFECTURES if pl.startswith(p)), "")
    drop_pref = next((p for p in PREFECTURES if dl.startswith(p)), "")
    pf = {
        "pick_pref": pick_pref, "pick_city": (M.extract_city(pl) or ""),
        "drop_pref": drop_pref, "drop_city": (M.extract_city(dl) or ""),
        "pickup_time": row.get("pickup_time"), "drop_time": ex.get("drop_time"),
        "cargo_weight": (str(int(float(row.get("cargo_weight") or 0))) if row.get("cargo_weight") else None),
        "truck_weight": ex.get("truck_weight"), "vehicle_type": row.get("vehicle_type"),
        "cargo_type": ex.get("cargo_type"), "freight_rate": row.get("freight_rate"),
        "contact_name": row.get("contact_name"), "contact_phone": ex.get("contact_phone"),
        "remarks": ex.get("remarks"),
    }
    return {k: v for k, v in pf.items() if v not in (None, "")}


# 複数日程一括投稿 UI（FEATURE_MULTIDATE）。上の積み/着 日時が「1本目」、
# 追加行が別日程。送信時に JS が date_variants(JSON) にまとめる。
_MULTIDATE_UI = """
<style>
.md-box{margin-bottom:1.5rem;border:1px solid var(--line);border-radius:14px;padding:16px 18px;background:var(--raise)}
.md-head{display:flex;align-items:flex-start;gap:10px;cursor:pointer;font-weight:600;color:var(--ink)}
.md-head input[type="checkbox"]{width:18px;height:18px;margin-top:2px;flex:0 0 auto;accent-color:var(--signal)}
.md-desc{font-size:12.5px;color:var(--muted);margin:8px 0 0 28px;line-height:1.6}
.md-area{margin-top:14px}
.md-rows{display:flex;flex-direction:column;gap:10px}
.md-row{display:grid;grid-template-columns:1fr 1fr auto;gap:10px;align-items:end;
  background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:12px}
.md-leg{grid-column:1/-1;font-size:11px;font-weight:700;letter-spacing:.04em;color:var(--muted);margin-bottom:-4px}
.md-cell{display:flex;flex-direction:column;gap:4px;min-width:0}
.md-cell label{font-size:11px;color:var(--faint);font-weight:600}
.md-cell .pair{display:flex;gap:6px}
.md-cell .pair input{min-width:0}
.md-del{align-self:center;color:var(--danger,#C9503E);background:none;border:1px solid var(--line);
  border-radius:8px;width:34px;height:34px;font-size:16px;cursor:pointer;padding:0}
.md-del:hover{background:var(--signal-wash)}
.md-add{margin-top:10px;font-size:13px;font-weight:600;color:var(--signal-ink);
  background:var(--signal-wash);border:1px solid var(--signal);border-radius:9px;padding:8px 14px;cursor:pointer}
.md-add:hover{filter:brightness(.97)}
@media(max-width:640px){
  .md-row{grid-template-columns:1fr 1fr}
  .md-del{grid-column:1/-1;width:100%;height:38px}
}
</style>
<div class="md-box">
  <label class="md-head">
    <input type="checkbox" id="md_toggle"> <span>複数日程で一括登録する（急ぎ・日程が柔軟なとき）</span>
  </label>
  <p class="md-desc">上の「積み日時・着日時」が1本目です。別日程を追加すると、同じ荷物を各日程で同時に投稿します。1件決まったら残りを一括で取り下げできます（最大5日程）。</p>
  <div id="md_area" class="md-area hidden">
    <div id="md_rows" class="md-rows"></div>
    <button type="button" id="md_add" class="md-add">＋ 日程を追加</button>
  </div>
  <input type="hidden" name="date_variants" id="date_variants">
</div>
<script>
(function(){
  const toggle=document.getElementById('md_toggle');
  const area=document.getElementById('md_area'), rowsEl=document.getElementById('md_rows');
  const addBtn=document.getElementById('md_add'), hidden=document.getElementById('date_variants');
  const form=document.querySelector('form[action="/cases/register"]');
  if(!toggle||!form) return;
  const MAX=4;  // 1本目(本体)＋追加4行＝最大5日程
  function addRow(){
    if(rowsEl.children.length>=MAX) return;
    const el=document.createElement('div');
    el.className='md-row';
    el.innerHTML='<div class="md-leg">追加日程 '+(rowsEl.children.length+2)+'本目</div>'+
      '<div class="md-cell"><label>積地 日付・時刻</label><div class="pair">'+
        '<input type="date" class="md-pd"><input type="time" class="md-pt"></div></div>'+
      '<div class="md-cell"><label>卸地 日付・時刻</label><div class="pair">'+
        '<input type="date" class="md-dd"><input type="time" class="md-dt"></div></div>'+
      '<button type="button" class="md-del" title="この日程を削除">×</button>';
    el.querySelector('.md-del').addEventListener('click',()=>{el.remove();renumber();updateAddBtn();});
    rowsEl.appendChild(el);
    updateAddBtn();
  }
  function renumber(){ rowsEl.querySelectorAll('.md-row .md-leg').forEach((n,i)=>{n.textContent='追加日程 '+(i+2)+'本目';}); }
  function updateAddBtn(){ addBtn.style.display = rowsEl.children.length>=MAX ? 'none' : ''; }
  toggle.addEventListener('change',()=>{ area.classList.toggle('hidden',!toggle.checked);
    if(toggle.checked && rowsEl.children.length===0) addRow(); });
  addBtn.addEventListener('click',addRow);
  form.addEventListener('submit',()=>{
    if(!toggle.checked){ hidden.value=''; return; }
    const g=(n)=>{const el=form.querySelector('[name="'+n+'"]'); return el?el.value:'';};
    const arr=[{pickup_date:g('pickup_date'),pickup_time:g('pickup_time'),drop_date:g('drop_date'),drop_time:g('drop_time')}];
    rowsEl.querySelectorAll('.md-row').forEach(r=>{
      const pd=r.querySelector('.md-pd').value,pt=r.querySelector('.md-pt').value,
            dd=r.querySelector('.md-dd').value,dt=r.querySelector('.md-dt').value;
      if(pd&&pt&&dd&&dt) arr.push({pickup_date:pd,pickup_time:pt,drop_date:dd,drop_time:dt});
    });
    hidden.value=JSON.stringify(arr);
  });
})();
</script>
"""

def _user_from_token(access_token):
    """access_token(Cookie) からサイドバー表示用のユーザー dict を得る。"""
    try:
        from app.utils.security import decode_access_token
        from app.db import store
        td = decode_access_token(access_token) if access_token else None
        if not td:
            return None
        return store.get_user_by_id(td.get("user_id"))
    except Exception:
        return None


def _batch_result_page(case_ids, group_id, pick_location, drop_location,
                        variants, want_trabox, want_webkit, user=None) -> HTMLResponse:
    """複数日程一括登録の結果ページ（各日程の案件IDとグループ管理導線）。左レール・シェル。"""
    from app.ui_shell import render_page, esc
    plats = "・".join([p for p, w in (("トラボックス", want_trabox), ("WebKit", want_webkit)) if w]) or "なし"
    rows = ""
    for cid, v in zip(case_ids, variants):
        rows += (f'<tr><td class="mono" style="color:var(--faint)">{cid}</td>'
                 f'<td>{esc(v["pickup_date"])} {esc(v["pickup_time"])} 積 → {esc(v["drop_date"])} {esc(v["drop_time"])} 卸</td>'
                 f'<td><a href="/cases/{cid}/manage" style="color:var(--signal-ink);font-weight:600">状況</a></td></tr>')
    body = f"""
  <div class="card" style="max-width:640px;margin:8px auto;padding:28px">
    <div style="text-align:center;margin-bottom:20px">
      <div style="font-size:48px;line-height:1;margin-bottom:10px">✅</div>
      <h1 class="pt" style="margin-bottom:4px">{len(case_ids)}件の日程で一括登録しました</h1>
      <p class="hl" style="margin:0">{esc(pick_location)} → {esc(drop_location)}／投稿先 {plats}</p>
    </div>
    <div class="card" style="overflow:hidden;margin-bottom:18px;box-shadow:none">
      <table><thead><tr><th>案件ID</th><th>日程</th><th></th></tr></thead><tbody>{rows}</tbody></table>
    </div>
    <div style="background:var(--amber-wash);border:1px solid var(--line-soft);border-radius:12px;padding:14px;font-size:13px;color:var(--amber);margin-bottom:20px">
      💡 1件が成約したら、<b>グループ管理画面から残りをまとめて取り下げ</b>できます（二重成約防止）。
    </div>
    <div style="display:flex;gap:12px;justify-content:center">
      <a class="btn" href="/cases/group/{group_id}">グループを管理</a>
      <a class="btn ghost" href="/cases/register">続けて登録</a>
    </div>
  </div>"""
    return HTMLResponse(render_page(
        title="一括登録完了", active="load_new", body=body, user=user,
        page_title="一括登録完了", crumb="Carroo · 荷物"))


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
    # --- WebKit 積/卸日時指定区分（WebKIT API仕様書準拠。WebKit投稿時は必須） ---
    loading_time_option: Optional[str] = Form(None),
    unloading_time_option: Optional[str] = Form(None),
    # --- 複数日程一括投稿（FEATURE_MULTIDATE）: JSON配列
    #     [{"pickup_date","pickup_time","drop_date","drop_time"}, ...] ---
    date_variants: Optional[str] = Form(None),
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

        # WebKit投稿時は積み/卸し時間区分が必須（WebKIT API仕様書: loaddatetype/destdatetype 必須項目）
        _TIME_OPT_CHOICES = ("以降", "必着", "迄", "から")
        if want_webkit:
            if loading_time_option not in _TIME_OPT_CHOICES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="積み時間区分（以降・必着・迄・から）はWebKit投稿時は必須です",
                )
            if unloading_time_option not in _TIME_OPT_CHOICES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="卸し時間区分（以降・必着・迄・から）はWebKit投稿時は必須です",
                )

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
                "loading_time_option": loading_time_option,
                "unloading_time_option": unloading_time_option,
            }.items() if v not in (None, "")
        }

        # --- 複数日程一括投稿（FEATURE_MULTIDATE）: date_variants があれば
        #     日時だけ違う N 件を group_id で束ねて生成・投稿する。
        #     無ければ従来どおり単発（フォームの pickup/drop 日時 1本）。---
        from app.tenancy import feature_enabled, current_tenant_id
        import json as _json

        variants = [{"pickup_date": pickup_date, "pickup_time": pickup_time,
                     "drop_date": drop_date, "drop_time": drop_time}]
        if date_variants and feature_enabled("multidate", current_user):
            try:
                parsed = _json.loads(date_variants)
                cleaned = []
                for v in parsed:
                    if v.get("pickup_date") and v.get("pickup_time") \
                            and v.get("drop_date") and v.get("drop_time"):
                        cleaned.append({
                            "pickup_date": v["pickup_date"], "pickup_time": v["pickup_time"],
                            "drop_date": v["drop_date"], "drop_time": v["drop_time"]})
                if cleaned:
                    variants = cleaned[:5]  # 上限5日程（スパム/コスト防止）
            except Exception as e:
                logger.warning(f"date_variants 解析失敗（単発として続行）: {e}")

        tenant_id = current_tenant_id(current_user)
        group_id = store.next_group_id() if len(variants) > 1 else None
        task_client = get_task_client()

        def _create_and_enqueue(v: dict) -> int:
            extras_v = dict(extras)
            extras_v["drop_date"] = v["drop_date"]
            extras_v["drop_time"] = v["drop_time"]
            cid = store.create_case(user_id, {
                "pick_location": pick_location, "drop_location": drop_location,
                "cargo_weight": cargo_weight, "vehicle_type": vehicle_type,
                "freight_rate": freight_rate, "pickup_date": v["pickup_date"],
                "pickup_time": v["pickup_time"], "contact_name": contact_name,
                "contact_phone": contact_phone, "contact_email": contact_email,
                "extras": extras_v,
            }, group_id=group_id, tenant_id=tenant_id)
            case_data = {
                "case_id": cid, "user_id": user_id,
                "pick_location": pick_location, "drop_location": drop_location,
                "cargo_weight": cargo_weight, "vehicle_type": vehicle_type,
                "freight_rate": freight_rate,
                "pickup_date": v["pickup_date"], "pickup_time": v["pickup_time"],
                "contact_name": contact_name, "contact_phone": contact_phone,
                "contact_email": contact_email,
                "post_to_trabox": want_trabox, "post_to_webkit": want_webkit,
                **extras_v,
            }
            task_client.add_posting_task(case_data, user_id)
            if want_trabox:
                store.add_posting_event(cid, "trabox", "register", "pending")
            if want_webkit:
                store.add_posting_event(cid, "webkit", "register", "pending")
            logger.info(f"✅ タスク追加: Case ID {cid} (group={group_id})")
            return cid

        case_ids = [_create_and_enqueue(v) for v in variants]
        case_id = case_ids[0]

        # 複数日程の場合は一括結果ページを返す
        if len(case_ids) > 1:
            return _batch_result_page(case_ids, group_id, pick_location,
                                      drop_location, variants, want_trabox, want_webkit,
                                      user=current_user)

        # Step 5: 結果画面を返す（投稿処理は背景で実行される）
        platforms = []
        if want_trabox:
            platforms.append("トラボックス")
        if want_webkit:
            platforms.append("WebKit")
        platforms_text = "・".join(platforms) if platforms else "なし（案件保存のみ）"

        from app.ui_shell import render_page, esc
        body = f"""
  <div class="card" style="max-width:560px;margin:8px auto;padding:32px;text-align:center">
    <div style="font-size:52px;line-height:1;margin-bottom:12px">✅</div>
    <h1 class="pt" style="margin-bottom:6px">案件を登録しました</h1>
    <p class="hl" style="margin:0 0 22px">案件ID: <span class="mono" style="font-weight:600">{case_id}</span></p>
    <div style="text-align:left;background:var(--raise);border:1px solid var(--line-soft);border-radius:12px;padding:16px;margin-bottom:20px;font-size:13.5px;display:grid;gap:8px">
      <div><span class="hl">積地:</span> <b>{esc(pick_location)}</b></div>
      <div><span class="hl">卸地:</span> <b>{esc(drop_location)}</b></div>
      <div><span class="hl">積み日:</span> <b>{esc(pickup_date)}</b></div>
      <div><span class="hl">投稿先:</span> <b>{platforms_text}</b></div>
    </div>
    <p class="hl" style="font-size:12.5px;margin:0 0 24px">投稿は背景で実行中です（1〜2分程度）。<br>結果（成功/失敗・荷物番号）はダッシュボードの案件詳細で確認できます。</p>
    <div style="display:flex;gap:12px;justify-content:center">
      <a class="btn" href="/cases/{case_id}/manage">投稿状況を確認</a>
      <a class="btn ghost" href="/cases/register">続けて登録</a>
    </div>
  </div>"""
        return HTMLResponse(render_page(
            title="登録完了", active="load_new", body=body,
            user=current_user, page_title="登録完了",
            crumb="Carroo · 荷物"))

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

    # 成約ステータス（手動マーク）
    _cs = row.get("contract_status")
    _cs_map = {"成約": ("🤝 成約", "text-green-700 bg-green-50 border-green-200"),
               "不成立": ("✕ 不成立", "text-gray-500 bg-gray-100 border-gray-200")}
    cs_txt, cs_cls = _cs_map.get(_cs, ("⏳ 未決（結果待ち）", "text-amber-700 bg-amber-50 border-amber-200"))

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
              <button data-act="editCase" data-args='["{p}"]' class="flex-1 border border-gray-300 rounded-lg py-2 text-sm font-semibold hover:bg-gray-50">変更</button>
              <button data-act="deleteCase" data-args='["{p}"]' class="flex-1 border border-red-200 text-red-600 bg-red-50 rounded-lg py-2 text-sm font-semibold hover:brightness-95">削除</button>'''
        elif st == "deleted":
            actions = f'<button data-act="editCase" data-args=\'["{p}",true]\' class="flex-1 border border-gray-300 rounded-lg py-2 text-sm font-semibold hover:bg-gray-50">再投稿</button>'
        elif st == "working":
            actions = '<span class="text-sm text-amber-700">処理完了までお待ちください（メールでも通知します）</span>'
        else:
            actions = f'<button data-act="editCase" data-args=\'["{p}",true]\' class="flex-1 border border-gray-300 rounded-lg py-2 text-sm font-semibold hover:bg-gray-50">投稿する</button>'
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
        <div class="grid gap-3 items-baseline px-4 py-3 border-b border-gray-100 last:border-0" style="grid-template-columns:130px 110px 1fr">
          <span class="text-xs text-gray-500 font-mono">{ts or ''}</span>
          <span class="text-sm font-semibold">{_platform_label(plat)}</span>
          <span class="text-sm text-gray-700"><span class="font-bold">{act_txt} {ST_TXT.get(stt,stt)}</span>
            <span class="text-xs font-bold px-2 py-0.5 rounded border {act_cls} ml-1">{act_txt}</span> {detail}</span>
        </div>'''
    if not rows_html:
        rows_html = '<p class="text-gray-400 text-center py-8">履歴がありません</p>'

    from app.ui_shell import shell_open, SHELL_CLOSE, esc
    _u = store.get_user_by_id(user_id)
    return HTMLResponse(shell_open(title=f"荷物 #{case_id}", active="load_list",
                                   user=_u, crumb="Carroo / 荷物") + f"""
<div class="max-w-4xl">
  <p class="text-sm text-gray-500 mb-3"><a href="/dashboard/cases" class="text-blue-600">荷物一覧</a> › 案件 #{case_id}</p>
  <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
    <div class="text-xs text-gray-500 font-mono">案件 ID {case_id} ・ {esc(row.get('created_at',''))} 登録 ・ 登録者: {esc(row.get('contact_name','') or '-')}</div>
    <h1 class="text-2xl font-bold mt-1">{esc(row.get('pick_location',''))} <span class="text-gray-400 font-normal mx-2">→</span> {esc(row.get('drop_location',''))}</h1>
    <div class="flex flex-wrap gap-x-6 gap-y-1 mt-4 text-sm text-gray-700">
      <span><span class="text-gray-400 mr-1">積み</span>{pickup}</span>
      <span><span class="text-gray-400 mr-1">着</span>{drop}</span>
      <span><span class="text-gray-400 mr-1">車両</span>{esc(extras.get('truck_weight',''))} {esc(row.get('vehicle_type',''))}</span>
      <span><span class="text-gray-400 mr-1">荷種</span>{esc(extras.get('cargo_type','鋼材'))}</span>
      <span><span class="text-gray-400 mr-1">運賃</span>{freight}</span>
    </div>
  </div>

  <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-4 mt-4 flex items-center gap-3 flex-wrap">
    <span class="text-sm text-gray-500">成約:</span>
    <span class="text-sm font-bold px-2.5 py-1 rounded-full border {cs_cls}">{cs_txt}</span>
    <div class="flex gap-2 ml-auto">
      <button data-act="setContract" data-args='["成約"]' class="bg-green-600 hover:bg-green-700 text-white text-sm font-semibold px-4 py-2 rounded-lg">🤝 成約にする</button>
      <button data-act="setContract" data-args='["不成立"]' class="border border-gray-300 text-gray-700 text-sm font-semibold px-3 py-2 rounded-lg hover:bg-gray-50">✕ 不成立</button>
      <button data-act="setContract" data-args='[""]' class="text-gray-400 text-sm px-2 hover:text-gray-600">未決に戻す</button>
    </div>
  </div>
  <p class="text-xs text-gray-400 mt-1">※ 電話等で決まったらここで記録してください（ダッシュボードの成約数・成約率に反映されます）。</p>

  <div class="flex items-center gap-3 mt-5 mb-1 flex-wrap">
    <span class="text-sm text-gray-500">一括操作:</span>
    <button data-act="editCase" data-args='["both"]' class="bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold px-4 py-2 rounded-lg">両方を変更</button>
    <button data-act="deleteCase" data-args='["both"]' class="border border-red-200 text-red-600 bg-red-50 text-sm font-semibold px-4 py-2 rounded-lg hover:brightness-95">両方を削除</button>
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
  async function setContract(s) {{
    await fetch('/cases/' + CASE_ID + '/contract', {{method:'POST', body:new URLSearchParams({{status:s}})}});
    location.reload();
  }}
</script>
""" + SHELL_CLOSE)


@router.post("/{case_id}/contract")
async def case_set_contract(case_id: int, status: str = Form(""),
                            current_user: dict = Depends(get_current_user)):
    """成約ステータスを手動記録（'成約' / '不成立' / '' = 未決）。"""
    from app.db import store
    valid = {"成約", "不成立", ""}
    if status not in valid:
        raise HTTPException(status_code=400, detail="不正なステータスです")
    if not store.set_contract_status(case_id, current_user["id"], status):
        raise HTTPException(status_code=404, detail="案件が見つかりません")
    return {"status": "ok", "contract_status": status or None}


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
    from app.utils.audit import audit
    audit("case_delete", case_id=case_id, user_id=user_id,
          username=current_user.get("username"), platforms=",".join(plats))
    # 履歴に delete イベントを pending で追記
    for p in plats:
        store.add_posting_event(case_id, p, "delete", "pending")
    # 非同期タスクを投入
    get_task_client().add_task({
        "action": "delete", "user_id": user_id, "case_id": case_id, "platforms": plats,
    })
    return HTMLResponse(f'<meta http-equiv="refresh" content="0; url=/cases/{case_id}/manage">')


@router.get("/group/{group_id}", response_class=HTMLResponse)
async def case_group_page(group_id: int, current_user: dict = Depends(get_current_user)):
    """複数日程一括投稿グループの管理（各日程の状態＋一括取り下げ）。"""
    from app.db import store
    user_id = current_user["id"]
    is_admin = current_user.get("is_admin")
    cases = store.list_group_cases(group_id, None if is_admin else user_id)
    if not cases:
        raise HTTPException(status_code=404, detail="グループが見つかりません")

    _badge = {"live": ("掲載中", "text-green-700 bg-green-50"),
              "working": ("処理中", "text-blue-700 bg-blue-50"),
              "error": ("エラー", "text-red-700 bg-red-50"),
              "deleted": ("取下げ", "text-gray-500 bg-gray-100"),
              "none": ("—", "text-gray-400 bg-gray-50")}
    rows = ""
    for c in cases:
        cid = c["id"]
        tb = _badge[store.get_platform_state(cid, "trabox")]
        wk = _badge[store.get_platform_state(cid, "webkit")]
        ex = c.get("extras") or {}
        rows += (f'<tr class="border-b"><td class="px-3 py-2 font-mono">{cid}</td>'
                 f'<td class="px-3 py-2">{esc(c.get("pickup_date",""))} {esc(c.get("pickup_time",""))} 積 → '
                 f'{esc(ex.get("drop_date",""))} {esc(ex.get("drop_time",""))} 卸</td>'
                 f'<td class="px-3 py-2"><span class="text-xs px-2 py-0.5 rounded {tb[1]}">トラボックス {tb[0]}</span> '
                 f'<span class="text-xs px-2 py-0.5 rounded {wk[1]}">WebKit {wk[0]}</span></td>'
                 f'<td class="px-3 py-2 text-sm"><a href="/cases/{cid}/manage" class="text-blue-600 hover:underline">個別</a>'
                 f' <button data-act="keepOne" data-args="[{cid}]" class="ml-2 text-amber-700 hover:underline">これで成約→他を取下げ</button></td></tr>')
    c0 = cases[0]
    from app.ui_shell import shell_open, SHELL_CLOSE, esc
    return HTMLResponse(shell_open(title=f"複数日程グループ #{group_id}", active="load_list",
                                   user=current_user, crumb="Carroo / 荷物") + f"""
<div class="max-w-4xl">
  <p class="text-gray-600 mb-4">{esc(c0.get('pick_location',''))} → {esc(c0.get('drop_location',''))}／{len(cases)}日程</p>
  <div class="bg-white rounded-lg shadow overflow-x-auto mb-4">
    <table class="w-full text-sm"><thead class="bg-gray-100 text-left text-gray-600">
      <tr><th class="px-3 py-2">案件ID</th><th class="px-3 py-2">日程</th><th class="px-3 py-2">掲載状態</th><th class="px-3 py-2"></th></tr>
    </thead><tbody>{rows}</tbody></table>
  </div>
  <button data-act="cancelAll" class="bg-red-600 hover:bg-red-700 text-white font-semibold py-2.5 px-6 rounded-lg">全ての日程を取り下げる</button>
</div>
<script>
async function keepOne(keep){{ if(!confirm('この日程で成約とし、他の日程の掲載を取り下げますか？'))return;
  await fetch('/cases/group/{group_id}/cancel',{{method:'POST',body:new URLSearchParams({{keep}})}}); location.reload(); }}
async function cancelAll(){{ if(!confirm('このグループの全ての掲載を取り下げますか？'))return;
  await fetch('/cases/group/{group_id}/cancel',{{method:'POST'}}); location.reload(); }}
</script>""" + SHELL_CLOSE)


@router.post("/group/{group_id}/cancel")
async def case_group_cancel(group_id: int, keep: Optional[int] = Form(None),
                            current_user: dict = Depends(get_current_user)):
    """グループの掲載を一括取り下げ。keep 指定時はその案件を残して他を取り下げる。"""
    from app.db import store
    user_id = current_user["id"]
    cases = store.list_group_cases(group_id, None if current_user.get("is_admin") else user_id)
    if not cases:
        raise HTTPException(status_code=404, detail="グループが見つかりません")
    cancelled = 0
    for c in cases:
        cid = c["id"]
        if keep is not None and int(cid) == int(keep):
            continue
        # 現在 live/error のプラットフォームだけ取り下げる
        plats = [p for p in ("trabox", "webkit")
                 if store.get_platform_state(cid, p) in ("live", "error")]
        if not plats:
            continue
        for p in plats:
            store.add_posting_event(cid, p, "delete", "pending")
        get_task_client().add_task({
            "action": "delete", "user_id": c["user_id"], "case_id": cid, "platforms": plats,
        })
        cancelled += 1
    return {"status": "ok", "cancelled": cancelled}


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
    from app.ui_shell import shell_open, SHELL_CLOSE, esc
    return HTMLResponse(shell_open(title=f"変更 #{case_id}", active="load_list",
                                   user=_user_from_token(access_token), crumb="Carroo / 荷物") + f"""
<div class="max-w-3xl">
  <a href="/cases/{case_id}/manage" class="hl" style="color:var(--signal-ink)">← 案件管理へ戻る</a>
  <p class="text-gray-600 mt-1 mb-6">変更対象: <span class="font-semibold" style="color:var(--signal-ink)">{target_label}</span> ・ 案件 #{case_id}</p>
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
        <input type="text" name="pick_city" value="{esc(pick_city)}" placeholder="市区町村" class="{I}" required></div></div>
      <div><label class="block text-sm font-medium mb-1">卸地</label>
        <div class="flex gap-2"><select name="drop_pref" class="{I}" required>{pref_opts_drop}</select>
        <input type="text" name="drop_city" value="{esc(drop_city)}" placeholder="市区町村" class="{I}" required></div></div>
    </div>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
      <div><label class="block text-sm font-medium mb-1">荷物重量(kg)</label><input type="number" name="cargo_weight" value="{int(float(row.get('cargo_weight') or 0))}" class="{I}" required></div>
      <div><label class="block text-sm font-medium mb-1">希望車両（トン数/形状）</label>
        <div class="flex gap-2"><select name="truck_weight" class="{I}">{weight_opts}</select><select name="vehicle_type" class="{I}">{shape_opts}</select></div></div>
      <div><label class="block text-sm font-medium mb-1">荷種</label><input type="text" name="cargo_type" value="{esc(ex.get('cargo_type','鋼材'))}" class="{I}"></div>
      <div><label class="block text-sm font-medium mb-1">運賃(円)</label><input type="number" name="freight_rate" value="{freight_val}" class="{I}"></div>
      <div><label class="block text-sm font-medium mb-1">登録者名</label><input type="text" name="contact_name" value="{esc(row.get('contact_name','') or '')}" class="{I}"></div>
    </div>
    <div class="flex gap-3 pt-2">
      <button type="submit" class="bg-blue-600 hover:bg-blue-700 text-white font-semibold px-6 py-2.5 rounded-lg">この内容で変更する</button>
      <a href="/cases/{case_id}/manage" class="bg-gray-100 hover:bg-gray-200 text-gray-900 font-semibold px-6 py-2.5 rounded-lg">キャンセル</a>
    </div>
  </form>
</div>""" + SHELL_CLOSE)


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
