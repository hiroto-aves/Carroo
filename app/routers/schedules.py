"""繰り返し空車ルール（Phase 2）。フィーチャーフラグ FEATURE_RECURRING 配下。

- UI: /schedules/register（作成）・/schedules/（一覧）・toggle/delete
- /schedules/materialize: Cloud Scheduler が日次で叩く（トークン認証）
- OFF 時は 403（UIも trucks 側ナビで非表示）
"""
import logging
import os
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.dependencies import get_current_user
from app.db import store
from app.tenancy import current_tenant_id, feature_enabled
from app.services import recurrence
from app.services.scheduler_service import materialize
from app.routers.trucks import PREFS, WEIGHTS, VEHICLES, _nav, _opts
from app.ui_shell import render_page
from app.widgets import pref_picker, PREF_PICKER_JS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/schedules", tags=["schedules"])

WEEKDAYS = [("0", "月"), ("1", "火"), ("2", "水"), ("3", "木"),
            ("4", "金"), ("5", "土"), ("6", "日")]


def _require_feature(current_user: dict = Depends(get_current_user)) -> dict:
    """繰り返し機能が有効なテナント/環境でのみ通す（オプション制御の要）。"""
    if not feature_enabled("recurring", current_user):
        raise HTTPException(403, "空車定期登録はご利用のプランでは無効です")
    return current_user


@router.get("/register", response_class=HTMLResponse)
async def register_page(current_user: dict = Depends(_require_feature)):
    today = date.today().isoformat()
    days = "".join(
        f'<label class="inline-flex items-center gap-1 mr-3"><input type="checkbox" '
        f'name="byday" value="{v}"> {lbl}</label>' for v, lbl in WEEKDAYS
    )
    body = f"""
<div class="max-w-3xl">
  <p class="hl" style="margin:-4px 0 18px">毎週・隔週・毎日・毎月のパターンで空車を自動投稿します。</p>
  <div id="msg" class="hidden mb-4 p-3 rounded-lg"></div>
  <form id="f" class="bg-white rounded-lg shadow p-6 space-y-6">
    <div>
      <label class="block text-sm font-medium mb-1">ルール名（任意）</label>
      <input name="name" placeholder="例: 毎週火木 練馬→大阪" class="border rounded px-3 py-2 w-full">
    </div>
    <div class="border rounded-lg p-4 space-y-3 bg-gray-50">
      <div class="flex items-center gap-4">
        <label class="font-medium">繰り返し:</label>
        <select name="freq" id="freq" class="border rounded px-3 py-2">
          <option value="WEEKLY">毎週</option><option value="BIWEEKLY">隔週</option>
          <option value="DAILY">毎日</option><option value="MONTHLY">毎月</option>
        </select>
      </div>
      <div id="byday_row"><span class="text-sm text-gray-600 mr-2">曜日:</span>{days}</div>
      <div id="monthday_row" class="hidden"><span class="text-sm text-gray-600 mr-2">日:</span>
        <input type="number" name="bymonthday" min="1" max="31" value="1" class="border rounded px-3 py-2 w-24"> 日</div>
      <label class="inline-flex items-center gap-2 text-sm"><input type="checkbox" name="skip_holidays" checked> 祝日はスキップする</label>
    </div>
    <div class="grid md:grid-cols-2 gap-6">
      <div class="space-y-3">
        <h2 class="font-semibold border-b pb-1">空車地</h2>
        <input type="time" name="vacant_time" value="09:00" class="border rounded px-3 py-2 w-full">
        <select id="vacant_pref" name="vacant_pref" class="border rounded px-3 py-2 w-full">{_opts(PREFS,"東京都")}</select>
        <select id="vacant_city" name="vacant_city" required class="border rounded px-3 py-2 w-full bg-white"><option value="">読み込み中...</option></select>
      </div>
      <div class="space-y-3">
        <h2 class="font-semibold border-b pb-1">行先地</h2>
        <div class="flex items-center gap-2 text-sm">空車日の
          <input type="number" name="dest_offset_days" value="1" min="0" max="14" class="border rounded px-2 py-1 w-16">日後
          <input type="time" name="dest_time" value="07:00" class="border rounded px-2 py-1"></div>
        <select id="dest_pref" name="dest_pref" class="border rounded px-3 py-2 w-full">{_opts(PREFS,"大阪府")}</select>
        <select id="dest_city" name="dest_city" required class="border rounded px-3 py-2 w-full bg-white"><option value="">読み込み中...</option></select>
      </div>
    </div>
    <div>
      <label class="block text-sm font-medium mb-1">その他対応可能行先（複数可）</label>
      {pref_picker("dest_able", placeholder="都道府県を選択（任意）")}
    </div>
    <div class="grid md:grid-cols-3 gap-4">
      <div><label class="block text-sm mb-1">積載重量</label>
        <select name="truck_weight" class="border rounded px-3 py-2 w-full">{_opts(WEIGHTS,"2t")}</select></div>
      <div><label class="block text-sm mb-1">車種</label>
        <select name="vehicle_type" class="border rounded px-3 py-2 w-full">{_opts(VEHICLES,"平")}</select></div>
      <div><label class="block text-sm mb-1">最低運賃(税別円)</label>
        <input name="min_freight" type="number" placeholder="任意" class="border rounded px-3 py-2 w-full"></div>
    </div>
    <div class="grid md:grid-cols-4 gap-4">
      <div><label class="block text-sm mb-1">初期登録回数</label>
        <input name="initial_count" type="number" value="0" min="0" max="12" class="border rounded px-3 py-2 w-full">
        <p class="text-xs text-gray-500 mt-1">作成時に直近この回数分を即投稿（0=しない）</p></div>
      <div><label class="block text-sm mb-1">何日前に投稿</label>
        <input name="lead_days" type="number" value="3" min="0" max="14" class="border rounded px-3 py-2 w-full"></div>
      <div><label class="block text-sm mb-1">有効開始日</label>
        <input name="active_from" type="date" value="{today}" class="border rounded px-3 py-2 w-full"></div>
      <div><label class="block text-sm mb-1">有効終了日（空=無期限）</label>
        <input name="active_until" type="date" class="border rounded px-3 py-2 w-full"></div>
    </div>
    <div class="flex items-center gap-6 border-t pt-4">
      <span class="font-medium">投稿先:</span>
      <label class="flex items-center gap-2"><input type="checkbox" name="post_to_trabox" checked> トラボックス</label>
      <label class="flex items-center gap-2"><input type="checkbox" name="post_to_webkit" checked> WebKit</label>
    </div>
    <button type="submit" class="bg-purple-600 hover:bg-purple-700 text-white font-semibold py-2.5 px-8 rounded-lg">空車定期登録を作成</button>
  </form>
</div>
<script>
const freq=document.getElementById('freq');
function upd(){{ const w=freq.value;
  document.getElementById('byday_row').style.display=(w==='WEEKLY'||w==='BIWEEKLY')?'':'none';
  document.getElementById('monthday_row').style.display=(w==='MONTHLY')?'':'none'; }}
freq.addEventListener('change',upd); upd();

// 都道府県 → 市区町村の連動セレクト（空車を出す画面と同じ /cases/api/cities を利用）
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
      // API失敗時は手入力にフォールバック
      const input=document.createElement('input');
      input.type='text'; input.name=sel.name; input.id=cityId; input.required=true;
      input.placeholder='市区町村を入力（例: 練馬区）';
      input.className=sel.className;
      sel.replaceWith(input);
    }}
  }}
  prefSel.addEventListener('change',load); load();  // 初期の既定都道府県でも自動ロード
}}
setupCityLoader('vacant_pref','vacant_city');
setupCityLoader('dest_pref','dest_city');
document.getElementById('f').addEventListener('submit', async (e)=>{{
  e.preventDefault(); const msg=document.getElementById('msg');
  const r=await fetch('/schedules/register',{{method:'POST',body:new URLSearchParams(new FormData(e.target))}});
  const j=await r.json();
  msg.className='mb-4 p-3 rounded-lg '+(r.ok?'bg-green-50 text-green-700':'bg-red-50 text-red-700');
  if(r.ok){{ const now=j.posted_now>0?('・今すぐ'+j.posted_now+'件を投稿しました'):('・直近の投稿予定は '+(j.next||'-')+'（当日朝に自動投稿）');
    msg.textContent='✅ ルール作成: '+j.describe+now; }}
  else msg.textContent='エラー: '+(j.detail||'失敗');
  if(!r.ok) window.__idle(e.target.__busyBtn);
  msg.classList.remove('hidden'); if(r.ok) setTimeout(()=>location.href='/schedules/',2200);
}});
</script>""" + PREF_PICKER_JS
    return render_page(title="空車定期登録の作成", active="schedules", body=body,
                       user=current_user, crumb="Carroo / 空車定期登録")


@router.post("/register")
async def create_schedule(
    current_user: dict = Depends(_require_feature),
    request: Request = None,
):
    form = await request.form()
    freq = form.get("freq", "WEEKLY")
    byday = [int(x) for x in form.getlist("byday")] if freq in ("WEEKLY", "BIWEEKLY") else []
    if freq in ("WEEKLY", "BIWEEKLY") and not byday:
        raise HTTPException(400, "曜日を1つ以上選択してください")
    want_trabox = form.get("post_to_trabox") is not None
    want_webkit = form.get("post_to_webkit") is not None
    if not want_trabox and not want_webkit:
        raise HTTPException(400, "投稿先を1つ以上選択してください")
    # 市区町村は Trabox/WebKit とも必須（空だと vacantarea 等で投稿失敗するため事前に弾く）
    if not (form.get("vacant_city") or "").strip():
        raise HTTPException(400, "空車地の市区町村は必須です（例: 練馬区）")
    if not (form.get("dest_city") or "").strip():
        raise HTTPException(400, "行先地の市区町村は必須です（例: 大阪市北区）")

    def _prefs(s):
        return [p.strip() for p in (s or "").replace("、", ",").split(",") if p.strip()]

    data = {
        "name": form.get("name") or "",
        "freq": freq, "byday": byday,
        "bymonthday": int(form.get("bymonthday") or 1),
        "skip_holidays": form.get("skip_holidays") is not None,
        "vacant_time": form.get("vacant_time") or "09:00",
        "vacant_pref": form.get("vacant_pref"), "vacant_city": form.get("vacant_city") or "",
        "dest_offset_days": int(form.get("dest_offset_days") or 1),
        "dest_time": form.get("dest_time") or "07:00",
        "dest_pref": form.get("dest_pref"), "dest_city": form.get("dest_city") or "",
        "dest_able_prefs": _prefs(form.get("dest_able")),
        "truck_weight": form.get("truck_weight") or "問わず",
        "vehicle_type": form.get("vehicle_type") or "問わず",
        "min_freight": form.get("min_freight") or None,
        "lead_days": int(form.get("lead_days") or 3),
        "active_from": form.get("active_from") or date.today().isoformat(),
        "active_until": form.get("active_until") or None,
        "contact_name": current_user.get("username"),
        "post_to_trabox": want_trabox, "post_to_webkit": want_webkit,
        "status": "active",
    }
    sid = store.create_schedule(current_user["id"], data,
                                tenant_id=current_tenant_id(current_user))
    # 初期登録回数: >0 なら lead 無視で直近その回数分を即投稿。0 なら lead_days 窓内のみ即投稿。
    try:
        initial_count = int(form.get("initial_count") or 0)
    except ValueError:
        initial_count = 0
    from app.services.scheduler_service import (
        materialize_schedule, materialize_schedule_initial)
    try:
        if initial_count > 0:
            immediate = materialize_schedule_initial(sid, initial_count)
        else:
            immediate = materialize_schedule(sid)
    except Exception as e:
        logger.error(f"作成直後の即時マテリアライズ失敗 schedule_id={sid}: {e}")
        immediate = []
    # 次回投稿予定日（今日から60日以内の最初の発生日）
    nd = recurrence.due_dates(data, date.today(), date.today() + timedelta(days=60))
    logger.info(f"✅ 空車定期登録作成: schedule_id={sid} 即時投稿={len(immediate)}件")
    return {"status": "created", "schedule_id": sid,
            "describe": recurrence.describe(data),
            "posted_now": len(immediate),
            "next": nd[0].isoformat() if nd else None}


@router.get("/", response_class=HTMLResponse)
async def list_page(current_user: dict = Depends(_require_feature)):
    rows = store.list_schedules(current_user.get("is_admin"), current_user["id"])
    items = ""
    for s in rows:
        nd = recurrence.due_dates(s, date.today(), date.today() + timedelta(days=60))
        nxt = nd[0].isoformat() if nd else "—"
        paused = s.get("status") != "active"
        badge = ('<span class="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-500 border">停止中</span>'
                 if paused else '<span class="text-xs px-2 py-0.5 rounded bg-green-50 text-green-700 border">稼働中</span>')
        plats = ("トラボックス " if s.get("post_to_trabox") else "") + ("WebKit" if s.get("post_to_webkit") else "")
        items += f"""<tr class="border-b hover:bg-gray-50">
          <td class="px-3 py-2 font-mono">{s['id']}</td>
          <td class="px-3 py-2">{s.get('name') or recurrence.describe(s)}</td>
          <td class="px-3 py-2 text-sm">{recurrence.describe(s)}</td>
          <td class="px-3 py-2 text-sm">{s.get('vacant_pref','')}{s.get('vacant_city','')} → {s.get('dest_pref','')}{s.get('dest_city','')}</td>
          <td class="px-3 py-2 text-sm">{nxt}</td>
          <td class="px-3 py-2">{badge}</td>
          <td class="px-3 py-2 text-sm whitespace-nowrap">
            <button data-act="tog" data-args="[{s['id']}]" class="text-blue-600 hover:underline">{'再開' if paused else '停止'}</button>
            <button data-act="del" data-args="[{s['id']}]" class="text-red-600 hover:underline ml-2">削除</button>
          </td></tr>"""
    if not items:
        items = '<tr><td colspan="7" class="px-3 py-8 text-center text-gray-400">空車定期登録はまだありません</td></tr>'
    body = f"""
<div class="card" style="overflow-x:auto">
    <table><thead><tr>
      <th>ID</th><th>名前</th><th>パターン</th><th>区間</th><th>次回</th><th>状態</th><th></th>
    </tr></thead><tbody>{items}</tbody></table>
</div>
<script>
async function tog(id){{ await fetch('/schedules/'+id+'/toggle',{{method:'POST'}}); location.reload(); }}
async function del(id){{ if(!confirm('このルールを削除しますか？（生成済みの空車は残ります）'))return;
  await fetch('/schedules/'+id+'/delete',{{method:'POST'}}); location.reload(); }}
</script>"""
    actions = '<a class="btn" href="/schedules/register">＋ 定期登録を作成</a>'
    return render_page(title="空車定期登録", active="schedules", body=body,
                       user=current_user, topbar_actions=actions)


@router.post("/{schedule_id}/toggle")
async def toggle_schedule(schedule_id: int, current_user: dict = Depends(_require_feature)):
    s = store.get_schedule(schedule_id, current_user["id"])
    if not s:
        raise HTTPException(404, "ルールが見つかりません")
    new_status = "paused" if s.get("status") == "active" else "active"
    store.update_schedule(schedule_id, current_user["id"], {"status": new_status})
    return {"status": new_status}


@router.post("/{schedule_id}/delete")
async def delete_schedule_route(schedule_id: int, current_user: dict = Depends(_require_feature)):
    if not store.delete_schedule(schedule_id, current_user["id"]):
        raise HTTPException(404, "ルールが見つかりません")
    return {"status": "deleted"}


def _check_scheduler_token(request: Request):
    import hmac
    token = request.headers.get("X-Scheduler-Token", "")
    expected = os.getenv("SCHEDULER_TOKEN", "")
    # 定数時間比較でタイミング攻撃を防ぐ（未設定時は常に拒否）
    if not expected or not hmac.compare_digest(token, expected):
        raise HTTPException(403, "invalid scheduler token")


@router.post("/materialize")
async def materialize_endpoint(request: Request):
    """Cloud Scheduler が日次で叩く。X-Scheduler-Token で認証（ログイン不要）。"""
    _check_scheduler_token(request)
    created = materialize()
    return {"status": "ok", "created": len(created), "items": created}


@router.post("/sync-contracts")
async def sync_contracts_endpoint(request: Request):
    """WebKit の成約状況(contracttype)を案件へ自動反映。Cloud Scheduler が定期で叩く。"""
    _check_scheduler_token(request)
    from app.services.contract_sync import sync_webkit_contracts
    result = await sync_webkit_contracts()
    return {"status": "ok", **result}
