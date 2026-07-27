"""失敗タスク（DLQ）— 投稿者本人向けの確認・再投稿・解決。

3回リトライしても投稿できなかったタスクは Firestore の dead_letter に退避され、
本人（＝投稿したユーザー）に紐づく。本人は自分の失敗だけを見て「再投稿／解決」できる。
管理者は全員分を閲覧・操作できる。
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse

from app.db import store
from app.dependencies import get_current_user
from app.ui_shell import render_page, esc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/failed", tags=["failed"])


def _owned_or_admin(d: dict, current_user: dict) -> bool:
    return current_user.get("is_admin") or d.get("user_id") == current_user["id"]


@router.get("/", response_class=HTMLResponse)
async def failed_page(current_user: dict = Depends(get_current_user)):
    is_admin = current_user.get("is_admin")
    items = store.list_dead_letters(user_id=None if is_admin else current_user["id"])
    rows = ""
    for d in items:
        p = d.get("payload") or {}
        cd = p.get("case_data") or {}
        td = p.get("truck_data") or {}
        tgt = cd.get("case_id") or p.get("case_id") or p.get("truck_id") or td.get("truck_id") or "-"
        if cd:
            route = f"{cd.get('pick_location','')} → {cd.get('drop_location','')}"
        elif td:
            route = (f"{td.get('vacant_pref','')}{td.get('vacant_city','')} → "
                     f"{td.get('dest_pref','')}{td.get('dest_city','')}")
        else:
            route = "-"
        kind = "荷物" if d.get("kind", "case") == "case" else "空車"
        act = {"register": "登録", "update": "変更", "delete": "取下げ"}.get(d.get("action"), d.get("action") or "-")
        rows += (f'<tr><td class="mono" style="color:var(--faint)">#{d["id"]}</td>'
                 f'<td style="color:var(--faint);white-space:nowrap">{esc(d.get("created_at",""))}</td>'
                 f'<td>{kind}・{act}</td><td class="mono">{esc(tgt)}</td><td>{esc(route)}</td>'
                 f'<td style="max-width:260px;color:var(--amber);font-size:12px">{esc((d.get("error") or "")[:160])}</td>'
                 f'<td style="text-align:right;white-space:nowrap">'
                 f'<button class="btn" style="padding:5px 12px;font-size:12px" data-act="dlqRetry" data-args="[{d["id"]}]">再投稿</button>'
                 f'<button class="btn ghost" style="padding:5px 12px;font-size:12px;margin-left:6px" data-act="dlqResolve" data-args="[{d["id"]}]">解決済み</button>'
                 f'</td></tr>')
    if not rows:
        rows = ('<tr><td colspan="7" style="text-align:center;color:var(--faint);padding:28px">'
                '投稿できなかったタスクはありません 🎉</td></tr>')
    body = f"""
  <h1 class="pt">失敗した投稿</h1>
  <p class="hl" style="margin:0 0 16px">3回試しても投稿できなかった{'（全ユーザー分）' if is_admin else 'あなたの'}案件です。
    原因が直ったら「再投稿」、対応不要なら「解決済み」を押してください。</p>
  <div class="card" style="overflow-x:auto"><table>
    <thead><tr><th>ID</th><th>発生</th><th>種別</th><th>対象</th><th>経路</th><th>エラー</th><th></th></tr></thead>
    <tbody>{rows}</tbody></table></div>
<script>
async function dlqRetry(id){{ if(!confirm('この投稿をもう一度実行しますか？'))return;
  var r=await fetch('/failed/'+id+'/retry',{{method:'POST'}}); var j=await r.json();
  if(r.ok) location.reload(); else alert('エラー: '+(j.detail||'失敗')); }}
async function dlqResolve(id){{ if(!confirm('この項目を解決済みにして一覧から消しますか？（再投稿はしません）'))return;
  var r=await fetch('/failed/'+id+'/resolve',{{method:'POST'}});
  if(r.ok) location.reload(); else alert('失敗'); }}
</script>"""
    return HTMLResponse(render_page(title="失敗した投稿", active="failed", body=body,
                                    user=current_user, crumb="Carroo"))


@router.post("/{did}/retry")
async def failed_retry(did: int, current_user: dict = Depends(get_current_user)):
    """退避した元データをそのままキューへ再投入し、解決済みにする。"""
    from app.services.cloud_tasks import get_task_client
    from app.utils.audit import audit
    d = store.get_dead_letter(did)
    if not d or d.get("resolved"):
        raise HTTPException(404, "対象の失敗タスクが見つかりません")
    if not _owned_or_admin(d, current_user):
        raise HTTPException(403, "この操作を行う権限がありません")
    payload = d.get("payload")
    if not payload:
        raise HTTPException(400, "再投稿に必要なデータがありません")
    get_task_client().add_task(payload)
    store.resolve_dead_letter(did, note="retried")
    audit("dead_letter_retry", dead_letter_id=did, by=current_user.get("username"))
    return {"status": "requeued", "dead_letter_id": did}


@router.post("/{did}/resolve")
async def failed_resolve(did: int, current_user: dict = Depends(get_current_user)):
    d = store.get_dead_letter(did)
    if not d:
        raise HTTPException(404, "対象の失敗タスクが見つかりません")
    if not _owned_or_admin(d, current_user):
        raise HTTPException(403, "この操作を行う権限がありません")
    from app.utils.audit import audit
    store.resolve_dead_letter(did, note="dismissed")
    audit("dead_letter_resolve", dead_letter_id=did, by=current_user.get("username"))
    return {"status": "resolved"}
