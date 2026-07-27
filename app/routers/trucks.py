"""空車（トラック空き）ルーター

荷物(cases)と分離した空車の登録・一覧・管理・削除。
投稿は kind="truck" タスクとしてキュー投入 → poster.execute_truck_task。
"""
import logging
from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse

from app.dependencies import get_current_user
from app.db import store
from app.services.cloud_tasks import get_task_client
from app.ui_shell import render_page, esc
from app.widgets import pref_picker, PREF_PICKER_JS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/trucks", tags=["trucks"])

PREFS = [
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
    "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
    "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県",
    "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県",
    "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県",
    "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県",
    "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
]
WEIGHTS = ["問わず", "軽", "1t", "2t", "3t", "4t", "5t", "8t", "10t", "13t", "15t", "トレーラー"]
VEHICLES = ["問わず", "平", "箱", "ウイング", "ユニック", "冷凍", "保冷"]

_STATE_BADGE = {
    "live": ("掲載中", "text-green-700 bg-green-50 border-green-200"),
    "working": ("処理中", "text-blue-700 bg-blue-50 border-blue-200"),
    "error": ("エラー", "text-red-700 bg-red-50 border-red-200"),
    "deleted": ("掲載終了", "text-gray-500 bg-gray-100 border-gray-200"),
    "none": ("未投稿", "text-gray-400 bg-gray-50 border-gray-200"),
}


def _nav(username: str) -> str:
    # 共通ナビに委譲（全ページで導線を統一）
    from app.ui_nav import main_nav
    return main_nav(username)


def _opts(values, selected=None):
    return "".join(
        f'<option value="{v}"{" selected" if v == selected else ""}>{v}</option>'
        for v in values
    )


def _page(user) -> str:
    from app.ui_shell import esc
    pref_opts = _opts(PREFS, "東京都")
    dpref_opts = _opts(PREFS, "大阪府")
    # 担当者名・電話番号の初期値＝初期設定(credentials)。未設定ならログインユーザー名を担当者名に。
    creds = store.get_credentials(user["id"]) or {}
    def_name = esc(creds.get("contact_name") or user.get("username") or "")
    def_phone = esc(creds.get("contact_phone") or "")
    body = f"""
<div class="max-w-3xl">
  <p class="hl" style="margin:-4px 0 18px">空車情報を Trabox / WebKit に一括投稿します。</p>
  <div id="msg" class="hidden mb-4 p-3 rounded-lg"></div>
  <form id="f" class="bg-white rounded-lg shadow p-6 space-y-6">
    <div class="grid md:grid-cols-2 gap-6">
      <div class="space-y-3">
        <h2 class="font-semibold text-gray-800 border-b pb-1">空車地</h2>
        <div class="flex gap-2">
          <input type="date" name="vacant_date" required class="border rounded px-3 py-2 w-full">
          <input type="time" name="vacant_time" value="09:00" class="border rounded px-3 py-2">
        </div>
        <select id="vacant_pref" name="vacant_pref" class="border rounded px-3 py-2 w-full">{pref_opts}</select>
        <select id="vacant_city" name="vacant_city" required class="border rounded px-3 py-2 w-full bg-white"><option value="">読み込み中...</option></select>
      </div>
      <div class="space-y-3">
        <h2 class="font-semibold text-gray-800 border-b pb-1">行先地</h2>
        <div class="flex gap-2">
          <input type="date" name="dest_date" required class="border rounded px-3 py-2 w-full">
          <input type="time" name="dest_time" value="09:00" class="border rounded px-3 py-2">
        </div>
        <select id="dest_pref" name="dest_pref" class="border rounded px-3 py-2 w-full">{dpref_opts}</select>
        <select id="dest_city" name="dest_city" required class="border rounded px-3 py-2 w-full bg-white"><option value="">読み込み中...</option></select>
      </div>
    </div>
    <div class="grid md:grid-cols-2 gap-6">
      <div>
        <label class="block text-sm font-medium mb-1">その他対応可能行先（複数可）</label>
        {pref_picker("dest_able", placeholder="都道府県を選択（任意）")}
      </div>
      <div>
        <label class="block text-sm font-medium mb-1">その他対応可能空車地（複数可）</label>
        {pref_picker("vacant_able", placeholder="都道府県を選択（任意）")}
      </div>
    </div>
    <div class="grid md:grid-cols-3 gap-4">
      <div><label class="block text-sm font-medium mb-1">積載重量</label>
        <select name="truck_weight" class="border rounded px-3 py-2 w-full">{_opts(WEIGHTS, "2t")}</select></div>
      <div><label class="block text-sm font-medium mb-1">車種</label>
        <select name="vehicle_type" class="border rounded px-3 py-2 w-full">{_opts(VEHICLES, "平")}</select></div>
      <div><label class="block text-sm font-medium mb-1">最低運賃（税別・円）</label>
        <input name="min_freight" type="number" placeholder="任意" class="border rounded px-3 py-2 w-full"></div>
    </div>
    <div class="grid md:grid-cols-2 gap-6">
      <div>
        <label class="block text-sm font-medium mb-1">担当者名</label>
        <input name="contact_name" value="{def_name}" required placeholder="山田太郎" class="border rounded px-3 py-2 w-full">
      </div>
      <div>
        <label class="block text-sm font-medium mb-1">電話番号</label>
        <input name="contact_phone" type="tel" value="{def_phone}" placeholder="09012345678" class="border rounded px-3 py-2 w-full">
      </div>
    </div>
    <div>
      <label class="block text-sm font-medium mb-1">備考</label>
      <textarea name="remarks" rows="2" class="border rounded px-3 py-2 w-full"></textarea>
    </div>
    <div class="flex items-center gap-6 border-t pt-4">
      <span class="font-medium">投稿先:</span>
      <label class="flex items-center gap-2"><input type="checkbox" name="post_to_trabox" checked> トラボックス</label>
      <label class="flex items-center gap-2"><input type="checkbox" name="post_to_webkit" checked> WebKit</label>
    </div>
    <button type="submit" class="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2.5 px-8 rounded-lg">空車を投稿する</button>
  </form>
</div>
<script>
// 都道府県 → 市区町村の連動セレクト（荷物を出す画面と同じ /cases/api/cities を利用）
function setupCityLoader(prefId, cityId){{
  const prefSel=document.getElementById(prefId);
  async function load(){{
    let sel=document.getElementById(cityId); const pref=prefSel.value;
    if(!pref){{ sel.innerHTML='<option value="">都道府県を先に選択</option>'; sel.disabled=true; return; }}
    sel.innerHTML='<option value="">読み込み中...</option>'; sel.disabled=true;
    try{{
      const res=await fetch('/cases/api/cities?pref='+encodeURIComponent(pref));
      if(!res.ok) throw new Error('api');
      const data=await res.json();
      sel.innerHTML='<option value="">市区町村を選択</option>'+
        data.cities.map(c=>'<option value="'+c+'">'+c+'</option>').join('');
      sel.disabled=false;
    }}catch(e){{
      const input=document.createElement('input');
      input.type='text'; input.name=sel.name; input.id=cityId; input.required=true;
      input.placeholder='市区町村を入力（例: 練馬区）'; input.className=sel.className;
      sel.replaceWith(input);
    }}
  }}
  prefSel.addEventListener('change',load); load();
}}
setupCityLoader('vacant_pref','vacant_city');
setupCityLoader('dest_pref','dest_city');

document.getElementById('f').addEventListener('submit', async (e) => {{
  e.preventDefault();
  const fd = new FormData(e.target);
  const msg = document.getElementById('msg');
  const r = await fetch('/trucks/register', {{method:'POST', body:new URLSearchParams(fd)}});
  const j = await r.json();
  msg.className = 'mb-4 p-3 rounded-lg ' + (r.ok ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700');
  msg.textContent = r.ok ? ('✅ 空車ID ' + j.truck_id + ' をキューに追加しました。数分後にメール通知が届きます。') : ('エラー: ' + (j.detail||'失敗'));
  if (!r.ok) window.__idle(e.target.__busyBtn);
  msg.classList.remove('hidden');
  if (r.ok) setTimeout(()=>location.href='/trucks/', 1500);
}});
</script>""" + PREF_PICKER_JS
    return render_page(title="空車を出す", active="truck_new", body=body, user=user)


@router.get("/register", response_class=HTMLResponse)
async def register_page(current_user: dict = Depends(get_current_user)):
    return _page(current_user)


@router.post("/register")
async def register_truck(
    current_user: dict = Depends(get_current_user),
    vacant_date: str = Form(...), vacant_time: str = Form("09:00"),
    vacant_pref: str = Form(...), vacant_city: str = Form(""),
    dest_date: str = Form(...), dest_time: str = Form("09:00"),
    dest_pref: str = Form(...), dest_city: str = Form(""),
    dest_able: str = Form(""), vacant_able: str = Form(""),
    truck_weight: str = Form("問わず"), vehicle_type: str = Form("問わず"),
    min_freight: str = Form(""), remarks: str = Form(""),
    contact_name: str = Form(""), contact_phone: str = Form(""),
    post_to_trabox: str = Form(None), post_to_webkit: str = Form(None),
):
    user_id = current_user["id"]
    want_trabox = post_to_trabox is not None
    want_webkit = post_to_webkit is not None
    if not want_trabox and not want_webkit:
        raise HTTPException(400, "投稿先を1つ以上選択してください")
    # 市区町村は Trabox/WebKit とも必須（空だと vacantarea 等で投稿失敗する）
    if not (vacant_city or "").strip():
        raise HTTPException(400, "空車地の市区町村は必須です（例: 練馬区）")
    if not (dest_city or "").strip():
        raise HTTPException(400, "行先地の市区町村は必須です（例: 大阪市北区）")
    # 担当者名は Trabox 空車では必須。空ならログインユーザー名で補完。
    contact_name = (contact_name or "").strip() or current_user.get("username") or "担当"

    def _prefs(s):
        return [p.strip() for p in (s or "").replace("、", ",").split(",") if p.strip()]

    data = {
        "vacant_date": vacant_date, "vacant_time": vacant_time,
        "vacant_pref": vacant_pref, "vacant_city": vacant_city,
        "dest_date": dest_date, "dest_time": dest_time,
        "dest_pref": dest_pref, "dest_city": dest_city,
        "dest_able_prefs": _prefs(dest_able), "vacant_able_prefs": _prefs(vacant_able),
        "truck_weight": truck_weight, "vehicle_type": vehicle_type,
        "min_freight": min_freight or None, "remarks": remarks,
        "contact_name": contact_name, "contact_phone": (contact_phone or "").strip(),
        "post_to_trabox": want_trabox, "post_to_webkit": want_webkit,
    }
    truck_id = store.create_truck(user_id, data)

    # 履歴 pending → キュー投入
    for p, want in (("trabox", want_trabox), ("webkit", want_webkit)):
        if want:
            store.add_truck_event(truck_id, p, "register", "pending")
    td = dict(data)
    td["truck_id"] = truck_id
    get_task_client().add_task({
        "kind": "truck", "action": "register", "user_id": user_id, "truck_data": td,
    })
    logger.info(f"✅ 空車タスク追加: truck_id={truck_id}")
    return {"status": "queued", "truck_id": truck_id}


@router.get("/", response_class=HTMLResponse)
async def list_trucks(current_user: dict = Depends(get_current_user)):
    is_admin = current_user.get("is_admin")
    rows = store.search_trucks(is_admin, current_user["id"], {})
    items = ""
    for t in rows:
        tb = _STATE_BADGE[store.get_truck_platform_state(t["id"], "trabox")]
        wk = _STATE_BADGE[store.get_truck_platform_state(t["id"], "webkit")]
        items += f"""<tr class="border-b hover:bg-gray-50">
          <td class="px-3 py-2 font-mono">{t['id']}</td>
          <td class="px-3 py-2">{esc(t.get('vacant_date',''))} {esc(t.get('vacant_time',''))}</td>
          <td class="px-3 py-2">{esc(t.get('vacant_pref',''))}{esc(t.get('vacant_city',''))} → {esc(t.get('dest_pref',''))}{esc(t.get('dest_city',''))}</td>
          <td class="px-3 py-2">{esc(t.get('truck_weight',''))}{esc(t.get('vehicle_type',''))}</td>
          <td class="px-3 py-2"><span class="text-xs px-2 py-0.5 rounded border {tb[1]}">トラボックス {tb[0]}</span>
              <span class="text-xs px-2 py-0.5 rounded border {wk[1]}">WebKit {wk[0]}</span></td>
          <td class="px-3 py-2"><a href="/trucks/{t['id']}/manage" class="text-blue-600 hover:underline">管理</a></td>
        </tr>"""
    if not items:
        items = '<tr><td colspan="6" class="px-3 py-8 text-center text-gray-400">空車の登録はまだありません</td></tr>'
    body = f"""
<div class="card" style="overflow-x:auto">
    <table><thead>
      <tr><th>ID</th><th>空車日時</th><th>区間</th><th>車両</th><th>掲載状態</th><th></th></tr>
    </thead><tbody>{items}</tbody></table>
</div>"""
    actions = '<a class="btn" href="/trucks/register">＋ 空車を出す</a>'
    return render_page(title="空車一覧", active="truck_list", body=body,
                       user=current_user, topbar_actions=actions)


@router.get("/{truck_id}/manage", response_class=HTMLResponse)
async def manage_truck(truck_id: int, current_user: dict = Depends(get_current_user)):
    is_admin = current_user.get("is_admin")
    t = store.get_truck(truck_id, None if is_admin else current_user["id"])
    if not t:
        raise HTTPException(404, "空車が見つかりません")
    tb = _STATE_BADGE[store.get_truck_platform_state(truck_id, "trabox")]
    wk = _STATE_BADGE[store.get_truck_platform_state(truck_id, "webkit")]

    def _plat_block(pf, badge):
        st = badge[0]
        btn = (f'<button data-act="delTruck" data-args=\'["{pf}"]\' class="mt-2 border border-red-200 text-red-600 '
               f'bg-red-50 rounded px-3 py-1 text-sm">掲載終了</button>' if st in ("掲載中", "エラー") else "")
        return f"""<div class="border rounded-lg p-4">
          <div class="font-semibold mb-1">{'トラボックス' if pf=='trabox' else 'WebKit'}</div>
          <span class="text-xs px-2 py-0.5 rounded border {badge[1]}">{st}</span>{btn}</div>"""

    hist = ""
    for h in store.list_truck_history(truck_id):
        act = {"register": "登録", "update": "変更", "delete": "削除"}.get(h.get("action"), h.get("action"))
        sta = {"success": "成功", "error": "失敗", "pending": "処理中"}.get(h.get("status"), h.get("status"))
        pf = "トラボックス" if h.get("platform") == "trabox" else "WebKit"
        err = f'<span class="text-red-600 text-xs">{(h.get("error_message") or "")[:120]}</span>' if h.get("status") == "error" else ""
        bn = f' 伝票番号 {h.get("baggage_no")}' if h.get("baggage_no") else ""
        hist += f'<div class="text-sm py-1 border-b">{pf} {act} <b>{sta}</b>{bn} {err}</div>'

    body = f"""
<div class="max-w-3xl">
  <a href="/trucks/" class="hl" style="color:var(--signal-ink)">← 空車一覧</a>
  <p class="hl" style="margin:8px 0 16px">{esc(t.get('vacant_pref',''))}{esc(t.get('vacant_city',''))} → {esc(t.get('dest_pref',''))}{esc(t.get('dest_city',''))}
     ／ {esc(t.get('vacant_date',''))} {esc(t.get('vacant_time',''))} ／ {esc(t.get('truck_weight',''))}{esc(t.get('vehicle_type',''))}</p>
  <div class="grid grid-cols-2 gap-4 mb-6">{_plat_block('trabox', tb)}{_plat_block('webkit', wk)}</div>
  <h2 class="font-semibold mb-2">投稿履歴</h2>
  <div class="card p-4" style="padding:16px">{hist or '<span class="text-gray-400">履歴なし</span>'}</div>
</div>
<script>
async function delTruck(pf) {{
  if(!confirm(pf+' の掲載を終了しますか？')) return;
  const r = await fetch('/trucks/{truck_id}/delete', {{method:'POST', body:new URLSearchParams({{platforms:pf}})}});
  location.reload();
}}
</script>"""
    return render_page(title=f"空車 #{truck_id}", active="truck_list", body=body,
                       user=current_user, crumb="Carroo / 空車")


@router.post("/{truck_id}/delete")
async def delete_truck(truck_id: int, platforms: str = Form(...),
                       current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    if not store.get_truck(truck_id, None if current_user.get("is_admin") else user_id):
        raise HTTPException(404, "空車が見つかりません")
    plats = [p for p in platforms.split(",") if p in ("trabox", "webkit")]
    if not plats:
        raise HTTPException(400, "対象プラットフォームが不正です")
    from app.utils.audit import audit
    audit("truck_delete", truck_id=truck_id, user_id=user_id,
          username=current_user.get("username"), platforms=",".join(plats))
    for p in plats:
        store.add_truck_event(truck_id, p, "delete", "pending")
    get_task_client().add_task({
        "kind": "truck", "action": "delete", "user_id": user_id,
        "truck_id": truck_id, "platforms": plats,
    })
    return {"status": "queued"}
