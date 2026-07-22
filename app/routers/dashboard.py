from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse
from app.dependencies import get_current_user
from app.db.database import get_db_connection
from datetime import datetime

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/", response_class=HTMLResponse)
async def dashboard(current_user: dict = Depends(get_current_user)):
    """ユーザーダッシュボード"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        user_id = current_user["id"]
        username = current_user["username"]

        # 案件数を取得
        cursor.execute("SELECT COUNT(*) FROM cases WHERE user_id = ?", (user_id,))
        case_count = cursor.fetchone()[0]

        # 投稿成功数を取得
        cursor.execute("""
            SELECT COUNT(*) FROM posting_history
            WHERE case_id IN (SELECT id FROM cases WHERE user_id = ?)
            AND status = 'success'
        """, (user_id,))
        success_count = cursor.fetchone()[0]

        # 投稿失敗数を取得
        cursor.execute("""
            SELECT COUNT(*) FROM posting_history
            WHERE case_id IN (SELECT id FROM cases WHERE user_id = ?)
            AND status = 'error'
        """, (user_id,))
        error_count = cursor.fetchone()[0]

        # 最近の案件を取得
        cursor.execute("""
            SELECT id, pick_location, drop_location, pickup_date, created_at
            FROM cases
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 5
        """, (user_id,))
        recent_cases = cursor.fetchall()

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
    finally:
        conn.close()


@router.get("/cases", response_class=HTMLResponse)
async def cases_list(
    current_user: dict = Depends(get_current_user),
    q_user: str = "",
    date_from: str = "",
    date_to: str = "",
    pick: str = "",
    drop: str = "",
    vehicle: str = "",
):
    """案件一覧（ドロップダウン絞り込み・全項目表示・カラムカスタマイズ）

    一般ユーザー: 自分の案件のみ。管理者: 全ユーザー＋ユーザー絞り込み。
    絞り込み: ユーザー(管理者)・積み日期間・積地(都道府県)・卸地(都道府県)・車種(形状)。
    表示カラムはユーザーごとに選択可（user_credentials.case_columns に保存）。
    """
    import json as _json
    from app.automations.trabox_form_mapper import TraboxFormMapper as M
    from app.routers.cases import PREFECTURES
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        user_id = current_user["id"]
        is_admin = current_user.get("is_admin", False)

        # ---- 表示カラム定義（key, ラベル） ----
        ALL_COLS = [
            ("owner", "ユーザー"), ("pick", "積地"), ("drop", "卸地"),
            ("pickup_date", "積み日"), ("pickup_time", "積み時間"),
            ("drop_date", "着日"), ("drop_time", "卸し時間"),
            ("weight", "重量"), ("vehicle", "車種"), ("cargo_type", "荷種"),
            ("package_type", "荷姿"), ("freight", "運賃"), ("truck_count", "台数"),
            ("share", "積合"), ("highway_fee", "高速代"),
            ("omakase_billing", "おまかせ請求"), ("contact_method", "連絡方法"),
            ("moving_case", "引越し"), ("remarks", "備考"), ("created", "登録日"),
        ]
        DEFAULT_COLS = ["pick", "drop", "pickup_date", "weight", "vehicle",
                        "cargo_type", "freight"]
        # ユーザーの選択カラムを取得
        row = cursor.execute(
            "SELECT case_columns FROM user_credentials WHERE user_id = ?", (user_id,)
        ).fetchone()
        try:
            visible = _json.loads(row[0]) if row and row[0] else list(DEFAULT_COLS)
        except (ValueError, TypeError):
            visible = list(DEFAULT_COLS)
        # 管理者以外は owner を出さない
        valid_keys = {k for k, _ in ALL_COLS}
        visible = [c for c in visible if c in valid_keys and (is_admin or c != "owner")]
        if not visible:
            visible = list(DEFAULT_COLS)

        # ---- 検索条件 ----
        where, params = [], []
        if is_admin:
            if q_user:
                where.append("c.user_id = ?"); params.append(q_user)
        else:
            where.append("c.user_id = ?"); params.append(user_id)
        if date_from:
            where.append("c.pickup_date >= ?"); params.append(date_from)
        if date_to:
            where.append("c.pickup_date <= ?"); params.append(date_to)
        if pick:
            where.append("c.pick_location LIKE ?"); params.append(f"{pick}%")
        if drop:
            where.append("c.drop_location LIKE ?"); params.append(f"{drop}%")
        if vehicle:
            where.append("c.vehicle_type = ?"); params.append(vehicle)
        where_sql = ("WHERE " + " AND ".join(where)) if where else ""

        cursor.execute(f"""
            SELECT c.id, c.pick_location, c.drop_location, c.cargo_weight,
                   c.vehicle_type, c.freight_rate, c.pickup_date, c.pickup_time,
                   c.created_at, c.extras, u.username
            FROM cases c JOIN users u ON u.id = c.user_id
            {where_sql} ORDER BY c.created_at DESC
        """, params)
        cases = cursor.fetchall()

        user_options = ""
        if is_admin:
            for uid, uname in cursor.execute(
                "SELECT id, username FROM users ORDER BY id").fetchall():
                sel = " selected" if str(uid) == str(q_user) else ""
                user_options += f'<option value="{uid}"{sel}>{uname}</option>'

        pref_opts_pick = '<option value="">すべて</option>' + "".join(
            f'<option value="{p}"{" selected" if p==pick else ""}>{p}</option>' for p in PREFECTURES)
        pref_opts_drop = '<option value="">すべて</option>' + "".join(
            f'<option value="{p}"{" selected" if p==drop else ""}>{p}</option>' for p in PREFECTURES)
        vehicle_opts = '<option value="">すべて</option>' + "".join(
            f'<option value="{s}"{" selected" if s==vehicle else ""}>{s}</option>'
            for s in M.VEHICLE_SHAPE_OPTIONS)

        # ---- 各案件の全項目を取り出すヘルパー ----
        def cell(case, key):
            cid, pl, dl, wt, veh, rate, pdate, ptime, created, extras_json, owner = case
            ex = {}
            if extras_json:
                try: ex = _json.loads(extras_json)
                except (ValueError, TypeError): ex = {}
            if key == "owner": return owner
            if key == "pick": return pl
            if key == "drop": return dl
            if key == "pickup_date": return pdate or "-"
            if key == "pickup_time": return ptime or "-"
            if key == "drop_date": return ex.get("drop_date", "-") or "翌日"
            if key == "drop_time": return ex.get("drop_time", "-") or "-"
            if key == "weight": return f"{wt:.0f}kg"
            if key == "vehicle":  # 重量＋形状を結合（例: 4t平）
                tw = ex.get("truck_weight", "") or ""
                tw = "" if tw in ("問わず", "") else tw
                return f"{tw}{veh}".strip() or "-"
            if key == "cargo_type": return ex.get("cargo_type", "-") or "-"
            if key == "package_type": return ex.get("package_type", "その他") or "その他"
            if key == "freight":
                return "要相談" if ex.get("freight_negotiable") else f"¥{rate:,.0f}"
            if key == "truck_count": return str(ex.get("truck_count", 1) or 1)
            if key == "share": return ex.get("share", "不可") or "不可"
            if key == "highway_fee": return ex.get("highway_fee", "支払わない") or "支払わない"
            if key == "omakase_billing": return ex.get("omakase_billing", "受入不可") or "受入不可"
            if key == "contact_method": return ex.get("contact_method", "電話で受付") or "電話で受付"
            if key == "moving_case": return "○" if ex.get("moving_case") else "-"
            if key == "remarks": return (ex.get("remarks") or "-")[:20]
            if key == "created": return str(created or "")[:10]
            return "-"

        label_map = dict(ALL_COLS)
        th = "".join(f'<th class="px-4 py-3 text-left text-xs font-semibold text-gray-700 whitespace-nowrap">{label_map[k]}</th>' for k in visible)
        body = ""
        for case in cases:
            cid = case[0]
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
    finally:
        conn.close()


@router.post("/cases/columns")
async def save_case_columns(request: Request,
                            current_user: dict = Depends(get_current_user)):
    """表示カラム設定を保存（複数チェックボックス cols を JSON で保存）"""
    import json as _json
    from fastapi.responses import RedirectResponse
    form = await request.form()
    cols = form.getlist("cols")  # チェックされたカラムキーの配列
    user_id = current_user["id"]
    conn = get_db_connection()
    try:
        # user_credentials 行が無い場合に備えて UPSERT
        exists = conn.execute(
            "SELECT 1 FROM user_credentials WHERE user_id = ?", (user_id,)
        ).fetchone()
        payload = _json.dumps(cols, ensure_ascii=False)
        if exists:
            conn.execute(
                "UPDATE user_credentials SET case_columns = ? WHERE user_id = ?",
                (payload, user_id),
            )
        else:
            conn.execute(
                "INSERT INTO user_credentials (user_id, case_columns) VALUES (?, ?)",
                (user_id, payload),
            )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/dashboard/cases", status_code=302)


@router.get("/cases/{case_id}", response_class=HTMLResponse)
async def case_detail(case_id: int, current_user: dict = Depends(get_current_user)):
    """案件詳細"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        user_id = current_user["id"]

        # 案件を取得
        cursor.execute("""
            SELECT id, user_id, pick_location, drop_location, cargo_weight, vehicle_type,
                   freight_rate, pickup_date, pickup_time, contact_name, contact_phone,
                   contact_email, created_at
            FROM cases
            WHERE id = ? AND user_id = ?
        """, (case_id, user_id))

        case = cursor.fetchone()

        if not case:
            raise HTTPException(status_code=404, detail="案件が見つかりません")

        # 投稿履歴を取得
        cursor.execute("""
            SELECT id, platform, status, posted_at, error_message, baggage_no
            FROM posting_history
            WHERE case_id = ?
            ORDER BY posted_at DESC
        """, (case_id,))

        histories = cursor.fetchall()

        case_id, user_id, pick_loc, drop_loc, weight, vehicle, rate, date, time, contact_name, contact_phone, contact_email, created_at = case

        html = f"""
        <!DOCTYPE html>
        <html lang="ja">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Carroo - 案件詳細</title>
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
                        <a href="/auth/logout" class="text-gray-600 hover:text-red-600 transition">ログアウト</a>
                    </div>
                </div>
            </nav>

            <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <a href="/dashboard/cases" class="text-blue-600 hover:text-blue-700 text-sm">← 案件一覧に戻る</a>

                <h1 class="text-4xl font-bold text-gray-900 mt-4 mb-8">案件詳細 #{case_id}</h1>

                <!-- 案件情報 -->
                <div class="bg-white rounded-lg shadow overflow-hidden mb-8">
                    <div class="px-6 py-4 border-b border-gray-200 bg-gray-50">
                        <h2 class="text-lg font-semibold text-gray-900">案件情報</h2>
                    </div>
                    <div class="p-6">
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div>
                                <p class="text-sm text-gray-600">積地</p>
                                <p class="text-lg font-semibold text-gray-900">{pick_loc}</p>
                            </div>
                            <div>
                                <p class="text-sm text-gray-600">卸地</p>
                                <p class="text-lg font-semibold text-gray-900">{drop_loc}</p>
                            </div>
                            <div>
                                <p class="text-sm text-gray-600">荷物重量</p>
                                <p class="text-lg font-semibold text-gray-900">{weight:.1f} kg</p>
                            </div>
                            <div>
                                <p class="text-sm text-gray-600">車種</p>
                                <p class="text-lg font-semibold text-gray-900">{vehicle}</p>
                            </div>
                            <div>
                                <p class="text-sm text-gray-600">運賃</p>
                                <p class="text-lg font-semibold text-gray-900">¥{rate:,.0f}</p>
                            </div>
                            <div>
                                <p class="text-sm text-gray-600">積地日付</p>
                                <p class="text-lg font-semibold text-gray-900">{date}{f" {time}" if time else ""}</p>
                            </div>
                        </div>

                        <hr class="my-6">

                        <div>
                            <h3 class="font-semibold text-gray-900 mb-4">連絡先情報</h3>
                            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                                <div>
                                    <p class="text-sm text-gray-600">担当者名</p>
                                    <p class="text-gray-900">{contact_name or '(未設定)'}</p>
                                </div>
                                <div>
                                    <p class="text-sm text-gray-600">電話番号</p>
                                    <p class="text-gray-900">{contact_phone or '(未設定)'}</p>
                                </div>
                                <div>
                                    <p class="text-sm text-gray-600">メールアドレス</p>
                                    <p class="text-gray-900">{contact_email or '(未設定)'}</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 投稿履歴 -->
                <div class="bg-white rounded-lg shadow overflow-hidden">
                    <div class="px-6 py-4 border-b border-gray-200 bg-gray-50">
                        <h2 class="text-lg font-semibold text-gray-900">投稿履歴</h2>
                    </div>
                    <div class="p-6">
        """

        if histories:
            html += """
                        <div class="space-y-3">
            """
            for history in histories:
                hist_id, platform, status, posted_at, error_msg, baggage_no = history
                if status == 'success':
                    status_badge, status_color = '✓ 成功', 'bg-green-100 text-green-800'
                elif status == 'pending':
                    status_badge, status_color = '⏳ 投稿中', 'bg-yellow-100 text-yellow-800'
                else:
                    status_badge, status_color = '✗ エラー', 'bg-red-100 text-red-800'
                # エラー詳細は先頭150文字まで表示（Playwrightのログは長大なため）
                error_short = (error_msg[:150] + '…') if error_msg and len(error_msg) > 150 else error_msg

                html += f"""
                            <div class="flex items-start justify-between p-4 border border-gray-200 rounded-lg hover:bg-gray-50">
                                <div>
                                    <p class="font-semibold text-gray-900">{platform.upper()}</p>
                                    <p class="text-sm text-gray-600">{posted_at}</p>
                                    {f'<p class="text-sm text-gray-700 mt-1">荷物番号: <span class="font-mono font-semibold">{baggage_no}</span></p>' if baggage_no else ''}
                                    {f'<p class="text-sm text-red-600 mt-2">{error_short}</p>' if error_short else ''}
                                </div>
                                <span class="px-3 py-1 rounded-full text-sm font-medium {status_color}">
                                    {status_badge}
                                </span>
                            </div>
                """
            html += """
                        </div>
            """
        else:
            html += """
                        <p class="text-gray-500 text-center py-8">投稿履歴がありません</p>
            """

        html += """
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

        return html

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
