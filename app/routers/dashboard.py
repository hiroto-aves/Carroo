from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse
from app.dependencies import get_current_user
from app.ui_nav import main_nav
from app.ui_shell import render_page, esc
from app.db.database import get_db_connection
from app.tenancy import scope_tenant
from datetime import datetime, timedelta

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _period_controls(active: str, date_from: str, date_to: str) -> str:
    """期間セレクタ: 今月 / 前月 / 過去1年 ＋ 年月範囲（YYYY年MM月〜YYYY年MM月）。"""
    opts = [("this_month", "今月"), ("last_month", "前月"), ("year", "過去1年")]
    seg = '<div class="seg perseg">'
    for key, label in opts:
        on = " on" if active == key else ""
        seg += f'<a class="{on.strip()}" href="/dashboard/?period={key}">{label}</a>'
    seg += "</div>"
    # 年月レンジ（type=month）。custom 選択時は入力値を保持
    fm = date_from if (active == "custom" and date_from) else ""
    tm = date_to if (active == "custom" and date_to) else ""
    ph = ' style="border-color:var(--signal)"' if active == "custom" else ""
    form = (
        f'<form method="get" action="/dashboard/" style="display:flex;align-items:center;gap:6px">'
        f'<input type="hidden" name="period" value="custom">'
        f'<input type="month" name="date_from" value="{fm}"{ph} style="width:132px;padding:5px 8px;font-size:12px" required>'
        f'<span style="color:var(--faint);font-size:12px">〜</span>'
        f'<input type="month" name="date_to" value="{tm}"{ph} style="width:132px;padding:5px 8px;font-size:12px" required>'
        f'<button class="btn ghost" type="submit" style="padding:6px 12px;font-size:12px">表示</button>'
        f'</form>'
    )
    return f'<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">{seg}{form}</div>'


def _month_bounds(ym: str):
    """'YYYY-MM' → (月初 date, 月末 date)。"""
    from datetime import date as _date
    y, m = int(ym[:4]), int(ym[5:7])
    first = _date(y, m, 1)
    nm_y, nm_m = (y + 1, 1) if m == 12 else (y, m + 1)
    last = _date(nm_y, nm_m, 1) - timedelta(days=1)
    return first, last


def _period_range(period: str, date_from: str, date_to: str):
    """期間指定 → (from, to, ラベル)。today は JST。"""
    from datetime import datetime, timedelta, timezone
    jst = timezone(timedelta(hours=9))
    today = datetime.now(jst).date()
    if period == "custom" and date_from and date_to:
        # 年月レンジ: from の月初 〜 to の月末
        try:
            f0, _ = _month_bounds(date_from)
            _, t1 = _month_bounds(date_to)
            if f0 > t1:
                f0, t1 = t1.replace(day=1), _month_bounds(date_from)[1]
            label = f"{f0.year}年{f0.month}月〜{t1.year}年{t1.month}月"
            return f0.isoformat(), t1.isoformat(), label
        except (ValueError, IndexError):
            pass
    if period == "last_month":
        first_this = today.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        first_prev = last_prev.replace(day=1)
        return first_prev.isoformat(), last_prev.isoformat(), "前月"
    if period == "year":
        start = (today - timedelta(days=364))
        return start.isoformat(), today.isoformat(), "過去1年"
    if period == "all":
        return None, None, "累計"
    # 既定: 今月
    first = today.replace(day=1)
    return first.isoformat(), today.isoformat(), "今月"


def _truck_dashboard(current_user: dict, store):
    """トップページ「空車ミックス」表示: 空車一覧＋空車定期登録一覧。"""
    from datetime import date
    from app.tenancy import feature_enabled
    user_id = current_user["id"]
    is_admin = current_user.get("is_admin", False)

    # ---- 空車一覧（直近） ----
    trucks = store.search_trucks(is_admin, user_id, {}, tenant_id=scope_tenant(current_user))
    live_trucks = 0
    trows = ""
    for t in trucks[:12]:
        tb = store.get_truck_platform_state(t["id"], "trabox")
        wk = store.get_truck_platform_state(t["id"], "webkit")
        is_live = "live" in (tb, wk)
        if is_live:
            live_trucks += 1
        chip = ('<span class="chip live">◐ 掲載中</span>' if is_live
                else '<span class="chip wait">待機</span>')
        trows += f"""<div class="rrow" style="grid-template-columns:1fr 150px 110px">
          <div class="place">{esc(t.get('vacant_pref',''))}{esc(t.get('vacant_city',''))} → {esc(t.get('dest_pref',''))}{esc(t.get('dest_city',''))}
            <small>{esc(t.get('vacant_date',''))} {esc(t.get('vacant_time',''))} 発 ／ {esc(t.get('truck_weight',''))}{esc(t.get('vehicle_type',''))}</small></div>
          <div style="text-align:right">{chip}</div>
          <div style="text-align:right"><a href="/trucks/{t['id']}/manage" style="color:var(--signal-ink);font-size:12px">管理 →</a></div>
        </div>"""
    if not trows:
        trows = '<div style="padding:32px;text-align:center;color:var(--faint)">空車の登録はまだありません。<a href="/trucks/register" style="color:var(--signal-ink)">空車を出す →</a></div>'

    # ---- 空車定期登録一覧 ----
    sched_card = ""
    if feature_enabled("recurring", current_user):
        from app.services import recurrence
        srows = ""
        rules = store.list_schedules(is_admin, user_id, tenant_id=scope_tenant(current_user))
        active_cnt = sum(1 for s in rules if s.get("status") == "active")
        for s in rules[:12]:
            paused = s.get("status") != "active"
            nd = recurrence.due_dates(s, date.today(), date.today() + timedelta(days=60))
            nxt = nd[0].isoformat() if nd else "—"
            chip = ('<span class="chip off">停止中</span>' if paused
                    else '<span class="chip live">稼働中</span>')
            srows += f"""<div class="rrow" style="grid-template-columns:1fr 150px 110px">
              <div class="place">{esc(s.get('vacant_pref',''))}{esc(s.get('vacant_city',''))} → {esc(s.get('dest_pref',''))}{esc(s.get('dest_city',''))}
                <small>{recurrence.describe(s)} ／ 次回 {nxt}</small></div>
              <div style="text-align:right">{chip}</div>
              <div style="text-align:right"><a href="/schedules/" style="color:var(--signal-ink);font-size:12px">一覧 →</a></div>
            </div>"""
        if not srows:
            srows = '<div style="padding:32px;text-align:center;color:var(--faint)">定期登録はまだありません。<a href="/schedules/register" style="color:var(--signal-ink)">定期登録を作成 →</a></div>'
        sched_card = f"""<div class="ledger" style="margin-top:18px">
          <div class="lhead"><span class="t">空車定期登録 <span style="color:var(--faint);font-weight:500">稼働中 {active_cnt}</span></span><a class="a" href="/schedules/">すべて →</a></div>
          {srows}
        </div>"""

    body = _failed_banner(current_user["id"], current_user.get("is_admin", False)) + f"""
<div class="stats" style="grid-template-columns:repeat(3,1fr)">
  <div class="cell"><div class="k">空車登録数</div><div class="v num">{len(trucks)}</div></div>
  <div class="cell"><div class="k">掲載中 <span class="sub">（現在）</span></div><div class="v num sig">{live_trucks}</div></div>
  <div class="cell"><div class="k">定期登録</div><div class="v num">{store.list_schedules(is_admin, user_id, tenant_id=scope_tenant(current_user)).__len__() if feature_enabled('recurring', current_user) else '—'}</div></div>
</div>
<div class="ledger">
  <div class="lhead"><span class="t">空車一覧</span><a class="a" href="/trucks/">すべて →</a></div>
  {trows}
</div>
{sched_card}
"""
    actions = '<a class="btn" href="/trucks/register"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>空車を出す</a>'
    return render_page(title="ダッシュボード", active="dashboard", body=body,
                       user=current_user, topbar_actions=actions)


def _failed_banner(user_id: int, is_admin: bool) -> str:
    """投稿できなかったタスク（DLQ）が本人にあれば、上部に警告バナーを出す。"""
    from app.db import store
    try:
        n = store.count_dead_letters(user_id=None if is_admin else user_id)
    except Exception:
        n = 0
    if not n:
        return ""
    return (f'<a href="/failed/" style="display:flex;align-items:center;gap:10px;'
            f'background:var(--amber-wash);border:1px solid var(--amber);border-radius:12px;'
            f'padding:12px 15px;margin-bottom:16px;color:var(--amber);font-weight:600;font-size:13.5px">'
            f'⚠️ 投稿できなかった{"" if is_admin else ""}タスクが {n} 件あります。'
            f'<span style="margin-left:auto;font-weight:700">確認する →</span></a>')


@router.get("/", response_class=HTMLResponse)
async def dashboard(current_user: dict = Depends(get_current_user),
                    period: str = "this_month",
                    date_from: str = None, date_to: str = None):
    """ユーザーダッシュボード"""
    from app.db import store

    try:
        user_id = current_user["id"]
        username = current_user["username"]

        is_admin = current_user.get("is_admin", False)

        # トップページ表示内容（設定で切替）: freight=荷物評価 / truck=空車ミックス
        if current_user.get("dashboard_mode") == "truck":
            return _truck_dashboard(current_user, store)

        d_from, d_to, period_label = _period_range(period, date_from, date_to)
        st = store.dashboard_stats(is_admin, user_id,
                                   date_from=d_from, date_to=d_to,
                                   tenant_id=scope_tenant(current_user))

        # 進行中の経路（最近の案件を経路の線で表示）
        rows_html = ""
        for c in store.recent_cases(user_id, 6):
            cid = c["id"]
            ex = c.get("extras") or {}
            cs = c.get("contract_status")
            live = any(store.get_platform_state(cid, p) == "live" for p in ("trabox", "webkit"))
            if cs == "成約":
                fill, w, chip, dcls, amb = "var(--signal)", 100, '<span class="chip met">🤝 成約</span>', " met", False
            elif cs == "不成立":
                fill, w, chip, dcls, amb = "var(--route)", 100, '<span class="chip off">✕ 不成立</span>', "", False
            elif live:
                fill, w, chip, dcls, amb = "var(--signal)", 62, '<span class="chip live">◐ 掲載中</span>', "", False
            else:
                fill, w, chip, dcls, amb = "var(--amber)", 26, '<span class="chip wait">⏳ 未決</span>', "", True
            node = (f'<span class="node" style="left:{w}%;'
                    + ('border-color:var(--amber);box-shadow:0 0 0 4px var(--amber-wash)' if amb else '')
                    + '"></span>') if w < 100 else ""
            rows_html += f"""<div class="rrow">
              <div class="place">{esc(c.get('pick_location',''))}<small>{esc(c.get('pickup_date',''))} {esc(c.get('pickup_time') or '')} 積</small></div>
              <div class="track"><div class="base"></div><div class="fill" style="width:{w}%;background:{fill}"></div>
                <span class="o"></span>{node}<span class="d{dcls}"></span></div>
              <div style="text-align:right">
                <div class="place" style="text-align:right">{esc(c.get('drop_location',''))}<small>{esc(ex.get('drop_date',''))} {esc(ex.get('drop_time',''))} 卸</small></div>
                <div style="margin-top:4px"><a href="/cases/{cid}/manage">{chip}</a></div>
              </div>
            </div>"""
        if not rows_html:
            rows_html = '<div style="padding:36px;text-align:center;color:var(--faint)">案件がまだありません。<a href="/cases/register" style="color:var(--signal-ink)">最初の荷物を出す →</a></div>'

        seg = _period_controls(period, date_from, date_to)
        body = _failed_banner(user_id, is_admin) + f"""
<div class="stats">
  <div class="cell"><div class="k">投稿数 <span class="sub">（{period_label}）</span></div><div class="v num">{st['total']}</div></div>
  <div class="cell"><div class="k">掲載中 <span class="sub">（現在）</span></div><div class="v num sig">{st['live']}</div></div>
  <div class="cell"><div class="k">成約数</div><div class="v num">{st['contracted']}</div></div>
  <div class="cell"><div class="k">成約率</div><div class="v num">{st['rate']}%</div></div>
  <div class="cell"><div class="k">未決</div><div class="v num amb">{st['pending']}</div></div>
</div>
<div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:18px;font-size:13px;align-items:center">
  <span class="chip live">📢 掲載中 {st['live']}</span>
  <span class="chip met">🤝 成約 {st['contracted']}</span>
  <span class="chip wait">⏳ 未決 {st['pending']}</span>
  <span class="chip off">✕ 不成立 {st['failed']}</span>
  <span style="margin-left:auto;color:var(--faint)">対象期間 <b>{period_label}</b></span>
</div>
<div class="ledger">
  <div class="lhead"><span class="t">進行中の経路</span><a class="a" href="/dashboard/cases">すべての案件 →</a></div>
  {rows_html}
</div>
"""
        actions = '<a class="btn" href="/cases/register"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>出す</a>'
        return render_page(title="ダッシュボード", active="dashboard", body=body,
                           user=current_user, topbar_center=seg, topbar_actions=actions)


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
        }, tenant_id=scope_tenant(current_user))
        # owner 表示用にユーザー名を引く（管理者のみ必要）
        uname_by_id = {}
        if is_admin:
            uname_by_id = {u["id"]: u["username"] for u in store.list_users()}
        cases = rows  # dict のリスト

        user_options = ""
        if is_admin:
            for u in store.list_users():
                sel = " selected" if str(u["id"]) == str(q_user) else ""
                user_options += f'<option value="{u["id"]}"{sel}>{esc(u["username"])}</option>'

        # 登録者名の候補（アカウント内 / 管理者は全件）
        reg_names = store.list_registrants(is_admin, user_id, tenant_id=scope_tenant(current_user))
        registrant_opts = '<option value="">すべて</option>' + "".join(
            f'<option value="{esc(n)}"{" selected" if n==registrant else ""}>{esc(n)}</option>' for n in reg_names)

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
            tds = "".join(f'<td class="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">{esc(cell(case, k))}</td>' for k in visible)
            body += (f'<tr class="border-b border-gray-100 hover:bg-gray-50">'
                     f'<td class="px-4 py-3"><input type="checkbox" class="row-sel w-4 h-4" value="{cid}"></td>'
                     f'<td class="px-4 py-3 text-sm font-semibold text-gray-900">#{cid}</td>{tds}'
                     f'<td class="px-4 py-3 text-sm whitespace-nowrap">'
                     f'<a href="/cases/{cid}/manage" class="text-blue-600 hover:text-blue-700 font-medium">管理</a>'
                     f' <button type="button" data-act="quickDeleteCase" data-args="[{cid}]" '
                     f'class="ml-2 text-red-600 hover:text-red-700 font-medium">削除</button></td></tr>')
        colspan = len(visible) + 3
        if not cases:
            body = f'<tr><td colspan="{colspan}" class="px-6 py-8 text-center text-gray-500">条件に一致する案件がありません</td></tr>'

        # カラム設定チェックボックス
        col_checks = "".join(
            f'<label class="flex items-center gap-1.5 text-sm"><input type="checkbox" name="cols" value="{k}"{" checked" if k in visible else ""}{" disabled" if k=="owner" and not is_admin else ""} class="w-4 h-4">{label_map[k]}</label>'
            for k, _ in ALL_COLS if (is_admin or k != "owner"))

        admin_link = '<a href="/admin/users" class="text-gray-600 hover:text-blue-600 transition">👥 ユーザー管理</a>' if is_admin else ''
        user_filter = f'<div><label class="block text-xs font-medium text-gray-600 mb-1">ユーザー</label><select name="q_user" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"><option value="">全員</option>{user_options}</select></div>' if is_admin else ''

        content = f"""<div>
  <p class="hl" style="margin:-4px 0 16px">{'全ユーザー' if is_admin else '自分'}の案件 {len(cases)} 件</p>

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

  <div id="bulk-delete-bar" class="hidden bg-red-50 border border-red-200 rounded-lg shadow p-3 mb-3 flex items-center gap-3">
    <span class="text-sm text-red-800 font-semibold"><span id="bulk-delete-count">0</span>件選択中</span>
    <button type="button" data-act="bulkDeleteCases" class="bg-red-600 hover:bg-red-700 text-white text-sm font-semibold px-4 py-2 rounded-lg">選択した案件を一括削除</button>
    <button type="button" onclick="document.querySelectorAll('.row-sel').forEach(c=>c.checked=false);updateBulkDeleteBar();" class="text-gray-500 hover:text-gray-700 text-sm">選択解除</button>
  </div>

  <div class="bg-white rounded-lg shadow overflow-hidden"><div class="overflow-x-auto"><table class="w-full">
    <thead class="bg-gray-50 border-b border-gray-200"><tr>
      <th class="px-4 py-3"><input type="checkbox" id="row-sel-all" class="w-4 h-4"></th>
      <th class="px-4 py-3 text-left text-xs font-semibold text-gray-700">ID</th>{th}
      <th class="px-4 py-3 text-left text-xs font-semibold text-gray-700">操作</th>
    </tr></thead>
    <tbody>{body}</tbody>
  </table></div></div>

  <form id="bulkDeleteForm" method="post" action="/cases/bulk-delete" style="display:none"><input type="hidden" name="case_ids" id="bulkDeleteIds"></form>
  <form id="quickDeleteForm" method="post" style="display:none"><input type="hidden" name="platforms" value="trabox,webkit"></form>
  <script>
    function updateBulkDeleteBar() {{
      const n = document.querySelectorAll('.row-sel:checked').length;
      document.getElementById('bulk-delete-count').textContent = n;
      document.getElementById('bulk-delete-bar').classList.toggle('hidden', n === 0);
    }}
    document.querySelectorAll('.row-sel').forEach(cb => cb.addEventListener('change', updateBulkDeleteBar));
    const selAll = document.getElementById('row-sel-all');
    if (selAll) {{
      selAll.addEventListener('change', () => {{
        document.querySelectorAll('.row-sel').forEach(cb => {{ cb.checked = selAll.checked; }});
        updateBulkDeleteBar();
      }});
    }}
    function quickDeleteCase(cid) {{
      if (!confirm('案件 #' + cid + ' のトラボックス・WebKit両方の掲載を削除します。よろしいですか？（登録の履歴は残ります）')) return;
      const f = document.getElementById('quickDeleteForm');
      f.action = '/cases/' + cid + '/delete';
      f.submit();
    }}
    function bulkDeleteCases() {{
      const ids = Array.from(document.querySelectorAll('.row-sel:checked')).map(cb => cb.value);
      if (ids.length === 0) return;
      if (!confirm(ids.length + '件の案件のトラボックス・WebKit両方の掲載を一括削除します。よろしいですか？（登録の履歴は残ります）')) return;
      document.getElementById('bulkDeleteIds').value = ids.join(',');
      document.getElementById('bulkDeleteForm').submit();
    }}
  </script>
</div>"""
        actions = ('<a class="btn ghost" href="/dashboard/cases/history">履歴</a>'
                   '<a class="btn" href="/cases/register" style="margin-left:8px">＋ 荷物を出す</a>')
        return render_page(title="荷物一覧", active="load_list", body=content,
                           user=current_user, topbar_actions=actions)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cases/history", response_class=HTMLResponse)
async def cases_history(current_user: dict = Depends(get_current_user),
                        q: str = "", date_from: str = "", date_to: str = ""):
    """荷物の投稿履歴（登録/変更/取下げの全イベント。削除済みも残る追記式ログ）。"""
    from app.db import store
    from app.widgets import event_chip, history_filter_form, in_period
    from app.tenancy import feature_enabled
    is_admin = current_user.get("is_admin")
    uid = current_user["id"]
    can_re = feature_enabled("reregister", current_user)
    cases = {c["id"]: c for c in store.list_all_cases(scope_tenant(current_user))}
    events = store.list_all_posting_events(1000)
    if not is_admin:
        events = [e for e in events if cases.get(e.get("case_id"), {}).get("user_id") == uid]
    ql = (q or "").strip().lower()
    rows = ""
    shown = 0
    for e in events:
        if not in_period(e.get("posted_at"), date_from, date_to):
            continue
        c = cases.get(e.get("case_id"), {})
        route = f"{c.get('pick_location','')} → {c.get('drop_location','')}"
        pf = "トラボックス" if e.get("platform") == "trabox" else "WebKit"
        if ql and ql not in f"{route} #{e.get('case_id','')} {e.get('baggage_no') or ''} {pf}".lower():
            continue
        shown += 1
        if shown > 400:
            continue
        re_btn = (f'<a class="btn ghost" style="padding:4px 10px;font-size:12px" '
                  f'href="/cases/register?from={e.get("case_id","")}">再登録</a>' if can_re else "")
        rows += (f'<tr><td style="color:var(--faint);white-space:nowrap">{esc(e.get("posted_at",""))}</td>'
                 f'<td class="mono">#{e.get("case_id","")}</td><td>{esc(route)}</td>'
                 f'<td>{event_chip(e.get("action"), e.get("status"))}</td>'
                 f'<td>{pf}</td><td class="mono" style="color:var(--faint)">{esc(e.get("baggage_no") or "")}</td>'
                 f'<td style="text-align:right">{re_btn}</td></tr>')
    if not rows:
        rows = '<tr><td colspan="7" style="text-align:center;color:var(--faint);padding:28px">該当する履歴はありません</td></tr>'
    body = f"""
  <h1 class="pt">荷物の履歴</h1>
  <p class="hl" style="margin:0 0 14px">登録・変更・取下げの全操作ログ（新しい順{'／全ユーザー' if is_admin else ''}）。該当 {shown} 件{'（先頭400件を表示）' if shown>400 else ''}。</p>
  {history_filter_form('/dashboard/cases/history', q, date_from, date_to, '経路・案件ID・荷物番号')}
  <div class="card" style="overflow-x:auto"><table>
    <thead><tr><th>日時</th><th>案件</th><th>経路</th><th>操作</th><th>投稿先</th><th>荷物番号</th><th></th></tr></thead>
    <tbody>{rows}</tbody></table></div>"""
    actions = '<a class="btn ghost" href="/dashboard/cases">← 荷物一覧へ</a>'
    return HTMLResponse(render_page(title="荷物の履歴", active="load_list", body=body,
                                    user=current_user, topbar_actions=actions))


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
