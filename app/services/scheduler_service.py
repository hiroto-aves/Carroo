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


def _materialize_date(sched: Dict[str, Any], d: date,
                      created: List[Dict[str, Any]]) -> None:
    """指定の空車日1件を空車化＋キュー投入（冪等）。"""
    vd = d.isoformat()
    # 既に生成済みならスキップ（冪等）
    if not store.mark_materialized(sched["id"], vd):
        return
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


def _materialize_one(sched: Dict[str, Any], run_date: date,
                     created: List[Dict[str, Any]]) -> None:
    """1ルール分のマテリアライズ（lead_days 窓内の未生成分を空車化＋キュー投入）。"""
    lead = int(sched.get("lead_days") if sched.get("lead_days") is not None
               else DEFAULT_LEAD_DAYS)
    window_end = run_date + timedelta(days=max(lead, 0))
    for d in recurrence.due_dates(sched, run_date, window_end):
        _materialize_date(sched, d, created)


def materialize(run_date: Optional[date] = None,
                tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """発生予定の空車を生成してキュー投入。生成した一覧を返す。"""
    run_date = run_date or date.today()
    created: List[Dict[str, Any]] = []
    schedules = store.list_active_schedules(tenant_id)
    logger.info(f"[Materialize] 実行 run_date={run_date} active数={len(schedules)}")

    for sched in schedules:
        try:
            _materialize_one(sched, run_date, created)
        except Exception as e:
            logger.error(f"[Materialize] schedule={sched.get('id')} でエラー: {e}")

    logger.info(f"[Materialize] 生成件数={len(created)}")
    return created


def materialize_schedule(schedule_id: int,
                         run_date: Optional[date] = None) -> List[Dict[str, Any]]:
    """特定ルールだけを即マテリアライズ（ルール作成直後の即時投稿に使用）。

    lead_days 窓内に到来する空車日があればその分だけ即キュー投入する。
    窓外（先の日付のみ）なら空リスト＝翌朝以降の日次materialize待ち。
    """
    run_date = run_date or date.today()
    created: List[Dict[str, Any]] = []
    sched = store.get_schedule(schedule_id)
    if not sched or sched.get("status") != "active":
        return created
    try:
        _materialize_one(sched, run_date, created)
    except Exception as e:
        logger.error(f"[MaterializeOne] schedule={schedule_id} でエラー: {e}")
    logger.info(f"[MaterializeOne] schedule={schedule_id} 生成件数={len(created)}")
    return created


def materialize_schedule_initial(schedule_id: int, count: int,
                                 run_date: Optional[date] = None) -> List[Dict[str, Any]]:
    """作成直後に「初期登録回数」分の将来の該当日を即マテリアライズする。

    lead_days 窓は無視し、今日以降に到来する該当日の先頭 count 件をまとめて投稿する
    （例: 毎週土曜 count=4 → 直近4回分の土曜を即登録）。冪等なので日次と重複しない。
    """
    run_date = run_date or date.today()
    created: List[Dict[str, Any]] = []
    if count <= 0:
        return created
    sched = store.get_schedule(schedule_id)
    if not sched or sched.get("status") != "active":
        return created
    # 十分先まで（約1年）該当日を出し、先頭 count 件を採用（有効期限・祝日スキップは due_dates が考慮）
    horizon = run_date + timedelta(days=370)
    due = recurrence.due_dates(sched, run_date, horizon)[:max(count, 0)]
    for d in due:
        try:
            _materialize_date(sched, d, created)
        except Exception as e:
            logger.error(f"[MaterializeInit] schedule={schedule_id} date={d} でエラー: {e}")
    logger.info(f"[MaterializeInit] schedule={schedule_id} 要求={count} 生成={len(created)}")
    return created
