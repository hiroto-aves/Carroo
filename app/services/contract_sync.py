"""WebKit の成約状況（contracttype）を Carroo の案件へ自動反映する同期処理。

WebKit 荷物一覧取得で自社の {slipno: contracttype} を取得し、Carroo の
posting_history から slipno→case_id を引いて contract_status を更新する。

反映ルール（手動優先・保守的）:
- contracttype 1(成約済) / 4(仮成約) → 案件を「成約」
- contracttype 2(不成立)           → 案件を「不成立」
- 既に手動/自動で成約・不成立が入っている案件は上書きしない（未決のみ更新）。
"""
import logging
from typing import Any, Dict

from app.db import store

logger = logging.getLogger(__name__)

_CONTRACT_MAP = {"1": "成約", "4": "成約", "2": "不成立"}


async def sync_webkit_contracts(person_id: str = None) -> Dict[str, Any]:
    from app.automations.webkit import WebkitAutomation
    auto = WebkitAutomation(person_id=person_id)
    slip_ct = await auto.list_contracts()          # {slipno: contracttype}
    if not slip_ct:
        return {"checked": 0, "updated": 0, "items": []}

    slip_to_case = store.webkit_slip_to_case()      # {slipno: case_id}
    updated = []
    for slipno, ct in slip_ct.items():
        status = _CONTRACT_MAP.get(ct)
        if not status:
            continue
        case_id = slip_to_case.get(slipno)
        if not case_id:
            continue
        if store.set_contract_status_system(case_id, status, only_if_pending=True):
            updated.append({"case_id": case_id, "slipno": slipno, "status": status})
            logger.info(f"[成約同期] case={case_id} slip={slipno} → {status}")

    logger.info(f"[成約同期] WebKit {len(slip_ct)}件チェック / {len(updated)}件更新")
    return {"checked": len(slip_ct), "updated": len(updated), "items": updated}
