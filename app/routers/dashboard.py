from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse
from app.dependencies import get_current_user
from app.db.database import get_db_connection
from datetime import datetime

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/", response_class=HTMLResponse)
async def dashboard(current_user: dict = Depends(get_current_user)):
    """ユーザーダッシュボード"""
    from app.db import store

    try:
        user_id = current_user["id"]
        username = current_user["username"]

        case_count = store.count_user_cases(user_id)
        success_count = store.count_posting_by_status(user_id, "success")
        error_count = store.count_posting_by_status(user_id, "error")

        # 最近の案件（新しい順に5件）: (id, pick, drop, pickup_date, created_at) タプル互換
        recent_cases = [
            (c["id"], c.get("pick_location"), c.get("drop_location"),
             c.get("pickup_date"), c.get("created_at"))
            for c in store.recent_cases(user_id, 5)
        ]

        html = f"""
        <!DOCTYPE html>
        <html lang="ja">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Carroo - ダッシュボード</title>
            <script src="https://cdn.tailwindcss.com"></script>
        </head>
        <body class="bg-gray-50">
            <!-- ナビゲーションバー -->
            <nav class="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-50">
                <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div class="flex justify-between h-16 items-center">
                        <div class="flex items-center">
                            <a href="/dashboard" class="text-2xl font-bold text-blue-600">📦 Carroo</a>
                        </div>
                        <div class="flex items-center gap-6">
                            <div class="text-right">
                                <p class="text-sm text-gray-600">ログイン中:</p>
                                <p class="font-semibold text-gray-900">{username}</p>
                            </div>
                            <div class="w-px h-8 bg-gray-300"></div>
                            <a href="/cases/register" class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition">
                                + 新規案件
                            </a>
                            {'<a href="/admin/users" class="text-gray-600 hover:text-blue-600 transition">👥 ユーザー管理</a>' if current_user.get('is_admin') else ''}
                            <a href="/settings/" class="text-gray-600 hover:text-blue-600 transition">⚙️ 初期設定</a>
                            <a href="/auth/logout" class="text-gray-600 hover:text-red-600 transition">ログアウト</a>
                        </div>
                    </div>
                </div>
            </nav>

            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <!-- ページタイトル -->
                <div class="mb-8">
                    <h1 class="text-4xl font-bold text-gray-900">ダッシュボード</h1>
                    <p class="text-gray-600 mt-2">登録された案件と投稿履歴の確認</p>
                </div>

                <!-- 統計カード -->
                <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                    <!-- 総案件数 -->
                    <div class="bg-white rounded-lg shadow p-6 border-l-4 border-blue-600">
                        <div class="flex items-center justify-between">
                            <div>
                                <p class="text-gray-600 text-sm">総案件数</p>
                                <p class="text-3xl font-bold text-gray-900">{case_count}</p>
                            </div>
                            <div class="text-4xl">📦</div>
                        </div>
                    </div>

                    <!-- 投稿成功 -->
                    <div class="bg-white rounded-lg shadow p-6 border-l-4 border-green-600">
                        <div class="flex items-center justify-between">
                            <div>
                                <p class="text-gray-600 text-sm">投稿成功</p>
                                <p class="text-3xl font-bold text-green-600">{success_count}</p>
                            </div>
                            <div class="text-4xl">✓</div>
                        </div>
                    </div>

                    <!-- 投稿失敗 -->
                    <div class="bg-white rounded-lg shadow p-6 border-l-4 border-red-600">
                        <div class="flex items-center justify-between">
                            <div>
                                <p class="text-gray-600 text-sm">投稿失敗</p>
                                <p class="text-3xl font-bold text-red-600">{error_count}</p>
                            </div>
                            <div class="text-4xl">✗</div>
                        </div>
                    </div>

                    <!-- 成功率 -->
                    <div class="bg-white rounded-lg shadow p-6 border-l-4 border-purple-600">
                        <div class="flex items-center justify-between">
                            <div>
                                <p class="text-gray-600 text-sm">成功率</p>
                                <p class="text-3xl font-bold text-purple-600">
                                    {(success_count / max((success_count + error_count), 1) * 100):.0f}%
                                </p>
                            </div>
                            <div class="text-4xl">📊</div>
                        </div>
                    </div>
                </div>

                <!-- 最近の案件 -->
                <div class="bg-white rounded-lg shadow overflow-hidden">
                    <div class="px-6 py-4 border-b border-gray-200">
                        <h2 class="text-lg font-semibold text-gray-900">最近の案件</h2>
                    </div>

                    <div class="overflow-x-auto">
                        <table class="w-full">
                            <thead class="bg-gray-50 border-b border-gray-200">
                                <tr>
                                    <th class="px-6 py-3 text-left text-sm font-semibold text-gray-700">案件ID</th>
                                    <th class="px-6 py-3 text-left text-sm font-semibold text-gray-700">積地</th>
                                    <th class="px-6 py-3 text-left text-sm font-semibold text-gray-700">卸地</th>
                                    <th class="px-6 py-3 text-left text-sm font-semibold text-gray-700">日付</th>
                                    <th class="px-6 py-3 text-left text-sm font-semibold text-gray-700">アクション</th>
                                </tr>
                            </thead>
                            <tbody>
        """

        if recent_cases:
            for case in recent_cases:
                case_id, pick_loc, drop_loc, pickup_date, created_at = case
                html += f"""
                                <tr class="border-b border-gray-200 hover:bg-gray-50 transition">
                                    <td class="px-6 py-4 text-sm text-gray-900">#{case_id}</td>
                                    <td class="px-6 py-4 text-sm text-gray-600">{pick_loc}</td>
                                    <td class="px-6 py-4 text-sm text-gray-600">{drop_loc}</td>
                                    <td class="px-6 py-4 text-sm text-gray-600">{pickup_date}</td>
                                    <td class="px-6 py-4 text-sm">
                                        <a href="/dashboard/cases/{case_id}" class="text-blue-600 hover:text-blue-700 font-medium">
                                            詳細を見る →
                                        </a>
                                    </td>
                                </tr>
                """
        else:
            html += """
                                <tr>
                                    <td colspan="5" class="px-6 py-8 text-center text-gray-500">
                                        案件がまだ登録されていません
                                    </td>
                                </tr>
            """

        html += """
                            </tbody>
                        </table>
                    </div>

                    <div class="px-6 py-4 border-t border-gray-200 bg-gray-50">
                        <a href="/dashboard/cases" class="text-blue-600 hover:text-blue-700 font-medium">
                            すべての案件を見る →
                        </a>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

        return html

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cases", response_class=HTMLResponse)
async def cases_list(
    current_user: dict = Depends(get_current_user),
    q_user: str = "",
    date_from: str = "",
    date_to: str = "",
    pick: str = "",
    drop: str = "",
    vehicle: str = "",
    registrant: str = "",
):
    """案件一覧（ドロップダウン絞り込み・全項目表示・カラムカスタマイズ）

    一般ユーザー: 自分の案件のみ。管理者: 全ユーザー＋ユーザー絞り込み。
    絞り込み: ユーザー(管理者)・積み日期間・積地(都道府県)・卸地(都道府県)・
             車種(形状)・登録者名（アカウント内で誰が登録したか）。
    表示カラムはユーザーごとに選択可（credentials.case_columns に保存）。
    """
    from app.automations.trabox_form_mapper import TraboxFormMapper as M
    from app.routers.cases import PREFECTURES
    from app.db import store
    try:
        user_id = current_user["id"]
        is_admin = current_user.get("is_admin", False)

        # ---- 表示カラム定義（key, ラベル） ----
        ALL_COLS = [
            ("owner", "ユーザー"), ("registrant", "登録者"),
            ("pick", "積地"), ("drop", "卸地"),
            ("pickup_date", "積み日"), ("pickup_time", "積み時間"),
            ("drop_date", "着日"), ("drop_time", "卸し時間"),
            ("weight", "重量"), ("vehicle", "車種"), ("cargo_type", "荷種"),
            ("package_type", "荷姿"), ("freight", "運賃"), ("truck_count", "台数"),
            ("share", "積合"), ("highway_fee", "高速代"),
            ("omakase_billing", "おまかせ請求"), ("contact_method", "連絡方法"),
            ("moving_case", "引越し"), ("remarks", "備考"), ("created", "登録日"),
        ]
        DEFAULT_COLS = ["registrant", "pick", "drop", "pickup_date", "weight",
                        "vehicle", "cargo_type", "freight"]
        # ユーザーの選択カラムを取得（Firestore credentials）
        stored = store.get_credentials(user_id).get("case_columns")
        visible = stored if isinstance(stored, list) and stored else list(DEFAULT_COLS)
        valid_keys = {k for k, _ in ALL_COLS}
        visible = [c for c in visible if c in valid_keys and (is_admin or c != "owner")]
        if not visible:
            visible = list(DEFAULT_COLS)

        # ---- 検索（store が user_id 取得後 Python でフィルタ） ----
        rows = store.search_cases(is_admin, user_id, {
            "q_user": q_user, "date_from": date_from, "date_to": date_to,
            "pick": pick, "drop": drop, "vehicle": vehicle, "registrant": registrant,
        })
        # owner 表示用にユーザー名を引く（管理者のみ必要）
        uname_by_id = {}
        if is_admin:
            uname_by_id = {u["id"]: u["username"] for u in store.list_users()}
        cases = rows  # dict のリスト

        user_options = ""
        if is_admin:
            for u in store.list_users():
                sel = " selected" if str(u["id"]) == str(q_user) else ""
                user_options += f'<option value="{u["id"]}"{sel}>{u["username"]}</option>'

        # 登録者名の候補（アカウント内 / 管理者は全件）
        reg_names = store.list_registrants(is_admin, user_id)
        registrant_opts = '<option value="">すべて</option>' + "".join(
            f'<option value="{n}"{" selected" if n==registrant else ""}>{n}</option>' for n in reg_names)

        pref_opts_pick = '<option value="">すべて</option>' + "".join(
            f'<option value="{p}"{" selected" if p==pick else ""}>{p}</option>' for p in PREFECTURES)
        pref_opts_drop = '<option value="">すべて</option>' + "".join(
            f'<option value="{p}"{" selected" if p==drop else ""}>{p}</option>' for p in PREFECTURES)
        vehicle_opts = '<option value="">すべて</option>' + "".join(
            f'<option value="{s}"{" selected" if s==vehicle else ""}>{s}</option>'
            for s in M.VEHICLE_SHAPE_OPTIONS)

        # ---- 各案件の全項目を取り出すヘルパー（store dict 版） ----
        def cell(case, key):
            ex = case.get("extras") or {}
            if key == "owner": return uname_by_id.get(case.get("user_id"), "-")
            if key == "registrant": return case.get("contact_name") or "-"
            if key == "pick": return case.get("pick_location")
            if key == "drop": return case.get("drop_location")
            if key == "pickup_date": return case.get("pickup_date") or "-"
            if key == "pickup_time": return case.get("pickup_time") or "-"
            if key == "drop_date": return ex.get("drop_date", "-") or "翌日"
            if key == "drop_time": return ex.get("drop_time", "-") or "-"
            if key == "weight": return f"{float(case.get('cargo_weight') or 0):.0f}kg"
            if key == "vehicle":  # 重量＋形状を結合（例: 4t平）
                tw = ex.get("truck_weight", "") or ""
                tw = "" if tw in ("問わず", "") else tw
                return f"{tw}{case.get('vehicle_type','')}".strip() or "-"
            if key == "cargo_type": return ex.get("cargo_type", "-") or "-"
            if key == "package_type": return ex.get("package_type", "その他") or "その他"
            if key == "freight":
                return "要相談" if ex.get("freight_negotiable") else f"¥{float(case.get('freight_rate') or 0):,.0f}"
            if key == "truck_count": return str(ex.get("truck_count", 1) or 1)
            if key == "share": return ex.get("share", "不可") or "不可"
            if key == "highway_fee": return ex.get("highway_fee", "支払わない") or "支払わない"
            if key == "omakase_billing": return ex.get("omakase_billing", "受入不可") or "受入不可"
            if key == "contact_method": return ex.get("contact_method", "電話で受付") or "電話で受付"
            if key == "moving_case": return "○" if ex.get("moving_case") else "-"
            if key == "remarks": return (ex.get("remarks") or "-")[:20]
            if key == "created": return str(case.get("created_at") or "")[:10]
            return "-"

        label_map = dict(ALL_COLS)
        th = "".join(f'<th class="px-4 py-3 text-left text-xs font-semibold text-gray-700 whitespace-nowrap">{label_map[k]}</th>' for k in visible)
        body = ""
        for case in cases:
            cid = case["id"]
            tds = "".join(f'<td class="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">{cell(case, k)}</td>' for k in visible)
            body += f'<tr class="border-b border-gray-100 hover:bg-gray-50"><td class="px-4 py-3 text-sm font-semibold text-gray-900">#{cid}</td>{tds}<td class="px-4 py-3 text-sm whitespace-nowrap"><a href="/cases/{cid}/manage" class="text-blue-600 hover:text-blue-700 font-medium">管理</a></td></tr>'
        if not cases:
            body = f'<tr><td colspan="{len(visible)+2}" class="px-6 py-8 text-center text-gray-500">条件に一致する案件がありません</td></tr>'

        # カラム設定チェックボックス
        col_checks = "".join(
            f'<label class="flex items-center gap-1.5 text-sm"><input type="checkbox" name="cols" value="{k}"{" checked" if k in visible else ""}{" disabled" if k=="owner" and not is_admin else ""} class="w-4 h-4">{label_map[k]}</label>'
            for k, _ in ALL_COLS if (is_admin or k != "owner"))

        admin_link = '<a href="/admin/users" class="text-gray-600 hover:text-blue-600 transition">👥 ユーザー管理</a>' if is_admin else ''
        user_filter = f'<div><label class="block text-xs font-medium text-gray-600 mb-1">ユーザー</label><select name="q_user" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"><option value="">全員</option>{user_options}</select></div>' if is_admin else ''

        html = f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Carroo - 案件一覧</title><script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-gray-50">
<nav class="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-50"><div class="max-w-full mx-auto px-4 sm:px-6 lg:px-8"><div class="flex justify-between h-16 items-center">
  <a href="/dashboard" class="text-2xl font-bold text-blue-600">📦 Carroo</a>
  <div class="flex items-center gap-6">{admin_link}
    <a href="/cases/register" class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition">+ 新規案件</a>
    <a href="/auth/logout" class="text-gray-600 hover:text-red-600 transition">ログアウト</a></div>
</div></div></nav>
<div class="max-w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
  <a href="/dashboard" class="text-blue-600 hover:text-blue-700 text-sm">← ダッシュボードに戻る</a>
  <h1 class="text-3xl font-bold text-gray-900 mt-2 mb-1">案件一覧</h1>
  <p class="text-gray-600 mb-5">{'全ユーザー' if is_admin else '自分'}の案件 {len(cases)} 件</p>

  <form method="get" action="/dashboard/cases" class="bg-white rounded-lg shadow p-4 mb-4">
    <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 items-end">
      {user_filter}
      <div><label class="block text-xs font-medium text-gray-600 mb-1">積み日（開始）</label><input type="date" name="date_from" value="{date_from}" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"></div>
      <div><label class="block text-xs font-medium text-gray-600 mb-1">積み日（終了）</label><input type="date" name="date_to" value="{date_to}" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"></div>
      <div><label class="block text-xs font-medium text-gray-600 mb-1">積地</label><select name="pick" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm">{pref_opts_pick}</select></div>
      <div><label class="block text-xs font-medium text-gray-600 mb-1">卸地</label><select name="drop" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm">{pref_opts_drop}</select></div>
      <div><label class="block text-xs font-medium text-gray-600 mb-1">車種（形状）</label><select name="vehicle" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm">{vehicle_opts}</select></div>
      <div><label class="block text-xs font-medium text-gray-600 mb-1">登録者</label><select name="registrant" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm">{registrant_opts}</select></div>
    </div>
    <div class="flex gap-2 mt-3">
      <button type="submit" class="bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold px-5 py-2 rounded-lg">検索</button>
      <a href="/dashboard/cases" class="bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm font-semibold px-5 py-2 rounded-lg">クリア</a>
    </div>
  </form>

  <details class="bg-white rounded-lg shadow mb-4">
    <summary class="cursor-pointer px-4 py-3 text-sm font-semibold text-gray-700">表示カラムのカスタマイズ</summary>
    <form method="post" action="/dashboard/cases/columns" class="px-4 pb-4">
      <div class="flex flex-wrap gap-x-5 gap-y-2 mb-3">{col_checks}</div>
      <button type="submit" class="bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold px-5 py-2 rounded-lg">表示カラムを保存</button>
    </form>
  </details>

  <div class="bg-white rounded-lg shadow overflow-hidden"><div class="overflow-x-auto"><table class="w-full">
    <thead class="bg-gray-50 border-b border-gray-200"><tr>
      <th class="px-4 py-3 text-left text-xs font-semibold text-gray-700">ID</th>{th}
      <th class="px-4 py-3 text-left text-xs font-semibold text-gray-700">操作</th>
    </tr></thead>
    <tbody>{body}</tbody>
  </table></div></div>
</div></body></html>"""
        return html
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cases/columns")
async def save_case_columns(request: Request,
                            current_user: dict = Depends(get_current_user)):
    """表示カラム設定を保存（複数チェックボックス cols を JSON で保存）"""
    from fastapi.responses import RedirectResponse
    from app.db import store
    form = await request.form()
    cols = form.getlist("cols")  # チェックされたカラムキーの配列
    store.upsert_credentials(current_user["id"], {"case_columns": list(cols)})
    return RedirectResponse(url="/dashboard/cases", status_code=302)


@router.get("/cases/{case_id}", response_class=HTMLResponse)
async def case_detail(case_id: int, current_user: dict = Depends(get_current_user)):
    """旧・案件詳細は案件管理画面へ統合。互換のためリダイレクト。"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/cases/{case_id}/manage", status_code=302)
