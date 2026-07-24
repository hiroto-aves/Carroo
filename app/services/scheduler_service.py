"""繰り返しルールの日次マテリアライズ。

Cloud Scheduler が毎日 /schedules/materialize を叩く → 本サービスが、
各 active ルールについて「今日〜今日+lead_days」で発生する空車のうち未生成の分を
truck_postings 化し、既存の投稿キュー（kind=truck register）へ投入する。

- 重複防止: store.mark_materialized(schedule_id, vacant_date) で1回だけ生成。
- lead_days: 空車日の何日前までに投稿するか（既定3日前まで先行投稿）。
"""
import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from app.db import store
from app.services import recurrence
from app.services.cloud_tasks import get_task_client

logger = logging.getLogger(__name__)

DEFAULT_LEAD_DAYS = 3


def materialize(run_date: Optional[date] = None,
                tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """発生予定の空車を生成してキュー投入。生成した一覧を返す。"""
    run_date = run_date or date.today()
    created: List[Dict[str, Any]] = []
    schedules = store.list_active_schedules(tenant_id)
    logger.info(f"[Materialize] 実行 run_date={run_date} active数={len(schedules)}")

    for sched in schedules:
        try:
            lead = int(sched.get("lead_days") if sched.get("lead_days") is not None
                       else DEFAULT_LEAD_DAYS)
            window_end = run_date + timedelta(days=max(lead, 0))
            for d in recurrence.due_dates(sched, run_date, window_end):
                vd = d.isoformat()
                # 既に生成済みならスキップ（冪等）
                if not store.mark_materialized(sched["id"], vd):
                    continue
                posting = recurrence.occurrence_to_posting(sched, d)
                posting["schedule_id"] = sched["id"]
                user_id = sched["user_id"]
                tenant = sched.get("tenant_id", "takeuchi")
                truck_id = store.create_truck(user_id, posting, tenant_id=tenant)
                for p, want in (("trabox", posting["post_to_trabox"]),
                                ("webkit", posting["post_to_webkit"])):
                    if want:
                        store.add_truck_event(truck_id, p, "register", "pending")
                td = dict(posting)
                td["truck_id"] = truck_id
                get_task_client().add_task({
                    "kind": "truck", "action": "register",
                    "user_id": user_id, "truck_data": td,
                })
                created.append({"schedule_id": sched["id"], "truck_id": truck_id,
                                "vacant_date": vd})
                logger.info(f"[Materialize] 生成 schedule={sched['id']} "
                            f"truck={truck_id} vacant={vd}")
        except Exception as e:
            logger.error(f"[Materialize] schedule={sched.get('id')} でエラー: {e}")

    logger.info(f"[Materialize] 生成件数={len(created)}")
    return created
