"""
バッチ投稿・スケジューリングサービス
複数案件の一括投稿と投稿スケジューリングを管理します
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from app.db.database import get_db_connection
from app.automations.trabox import TraboxAutomation
from app.automations.webkit import WebkitAutomation

logger = logging.getLogger(__name__)


class BatchPostingService:
    """バッチ投稿サービス"""

    def __init__(self):
        self.trabox = TraboxAutomation()
        self.webkit = WebkitAutomation()
        self.posting_queue = []
        self.is_processing = False

    async def queue_cases_for_batch_posting(
        self,
        user_id: int,
        case_ids: List[int],
        platforms: List[str],
        schedule_time: Optional[datetime] = None,
        batch_name: str = ""
    ) -> Dict[str, Any]:
        """複数の案件をバッチ投稿キューに追加"""
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            batch_id = await self._create_batch_entry(
                cursor, user_id, batch_name, schedule_time
            )

            queued_count = 0
            for case_id in case_ids:
                # 案件の存在確認
                cursor.execute(
                    "SELECT id FROM cases WHERE id = ? AND user_id = ?",
                    (case_id, user_id)
                )
                if cursor.fetchone():
                    cursor.execute(
                        """INSERT INTO posting_queue
                        (batch_id, case_id, platform, status, scheduled_at)
                        VALUES (?, ?, ?, ?, ?)""",
                        (batch_id, case_id, ",".join(platforms), "pending", schedule_time)
                    )
                    queued_count += 1

            conn.commit()

            logger.info(f"[Batch] {queued_count}件の案件をキューに追加しました (Batch ID: {batch_id})")

            return {
                "status": "success",
                "batch_id": batch_id,
                "queued_cases": queued_count,
                "scheduled_at": schedule_time,
                "message": f"{queued_count}件の案件がバッチ投稿キューに追加されました"
            }

        except Exception as e:
            conn.rollback()
            logger.error(f"[Batch] キューイング失敗: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
        finally:
            conn.close()

    async def process_batch_posting(self, batch_id: int) -> Dict[str, Any]:
        """バッチ投稿を実行"""
        if self.is_processing:
            return {
                "status": "warning",
                "message": "別のバッチ投稿が実行中です"
            }

        self.is_processing = True
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # バッチ情報を取得
            cursor.execute(
                "SELECT id, user_id FROM posting_batches WHERE id = ?",
                (batch_id,)
            )
            batch = cursor.fetchone()

            if not batch:
                return {
                    "status": "error",
                    "message": "バッチが見つかりません"
                }

            # キューイング済みの案件を取得
            cursor.execute(
                """SELECT DISTINCT case_id, platform FROM posting_queue
                WHERE batch_id = ? AND status = 'pending'
                ORDER BY case_id""",
                (batch_id,)
            )
            queue_items = cursor.fetchall()

            results = {
                "batch_id": batch_id,
                "total_items": len(queue_items),
                "successful": 0,
                "failed": 0,
                "details": []
            }

            for case_id, platform_str in queue_items:
                platforms = platform_str.split(",")

                # 案件情報を取得
                cursor.execute(
                    """SELECT id, pick_location, drop_location, cargo_weight,
                            vehicle_type, freight_rate, pickup_date, pickup_time,
                            contact_name, contact_phone, contact_email
                    FROM cases WHERE id = ?""",
                    (case_id,)
                )
                case = cursor.fetchone()

                if not case:
                    continue

                case_data = self._case_tuple_to_dict(case)

                # 各プラットフォームに投稿
                for platform in platforms:
                    result = await self._post_to_platform(platform, case_data)

                    # 投稿結果を記録
                    cursor.execute(
                        """INSERT INTO posting_history
                        (case_id, platform, status, error_message)
                        VALUES (?, ?, ?, ?)""",
                        (case_id, platform, result["status"],
                         result.get("message") if result["status"] == "error" else None)
                    )

                    # キューステータスを更新
                    cursor.execute(
                        """UPDATE posting_queue SET status = ?
                        WHERE batch_id = ? AND case_id = ? AND platform = ?""",
                        (result["status"], batch_id, case_id, platform)
                    )

                    conn.commit()

                    if result["status"] == "success":
                        results["successful"] += 1
                    else:
                        results["failed"] += 1

                    results["details"].append({
                        "case_id": case_id,
                        "platform": platform,
                        "status": result["status"],
                        "message": result.get("message", "成功")
                    })

                logger.info(f"[Batch] 案件 #{case_id} の投稿完了")

            # バッチステータスを更新
            cursor.execute(
                """UPDATE posting_batches SET status = 'completed', completed_at = ?
                WHERE id = ?""",
                (datetime.now(), batch_id)
            )
            conn.commit()

            results["message"] = f"バッチ投稿完了: {results['successful']}成功, {results['failed']}失敗"
            logger.info(f"[Batch] バッチ #{batch_id} 完了: {results['message']}")

            return results

        except Exception as e:
            logger.error(f"[Batch] 処理エラー: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
        finally:
            conn.close()
            self.is_processing = False

    async def schedule_posting(
        self,
        batch_id: int,
        scheduled_time: datetime
    ) -> Dict[str, Any]:
        """投稿をスケジュール"""
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # バッチをスケジュール状態に更新
            cursor.execute(
                """UPDATE posting_batches SET status = 'scheduled', scheduled_at = ?
                WHERE id = ?""",
                (scheduled_time, batch_id)
            )
            conn.commit()

            # スケジュール実行時刻を計算
            time_until = (scheduled_time - datetime.now()).total_seconds()

            logger.info(f"[Batch] バッチ #{batch_id} は {scheduled_time} にスケジュールされました")

            return {
                "status": "success",
                "batch_id": batch_id,
                "scheduled_at": scheduled_time,
                "seconds_until_execution": int(time_until),
                "message": f"バッチ投稿は {scheduled_time.strftime('%Y-%m-%d %H:%M:%S')} に実行予定です"
            }

        except Exception as e:
            conn.rollback()
            logger.error(f"[Batch] スケジュール失敗: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
        finally:
            conn.close()

    async def get_batch_status(self, batch_id: int) -> Dict[str, Any]:
        """バッチの状態を取得"""
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """SELECT id, user_id, status, created_at, scheduled_at, completed_at
                FROM posting_batches WHERE id = ?""",
                (batch_id,)
            )
            batch = cursor.fetchone()

            if not batch:
                return {
                    "status": "error",
                    "message": "バッチが見つかりません"
                }

            # キューイング状態の統計
            cursor.execute(
                """SELECT status, COUNT(*) as count
                FROM posting_queue WHERE batch_id = ?
                GROUP BY status""",
                (batch_id,)
            )
            stats = cursor.fetchall()

            status_count = {row[0]: row[1] for row in stats}

            return {
                "status": "success",
                "batch_id": batch_id,
                "batch_status": batch[2],
                "created_at": batch[3],
                "scheduled_at": batch[4],
                "completed_at": batch[5],
                "queue_stats": {
                    "pending": status_count.get("pending", 0),
                    "success": status_count.get("success", 0),
                    "error": status_count.get("error", 0),
                    "total": sum(status_count.values())
                }
            }

        except Exception as e:
            logger.error(f"[Batch] 状態取得失敗: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
        finally:
            conn.close()

    async def _create_batch_entry(
        self,
        cursor,
        user_id: int,
        batch_name: str,
        schedule_time: Optional[datetime]
    ) -> int:
        """バッチエントリを作成"""
        cursor.execute(
            """INSERT INTO posting_batches
            (user_id, batch_name, status, created_at, scheduled_at)
            VALUES (?, ?, ?, ?, ?)""",
            (user_id, batch_name, "pending", datetime.now(), schedule_time)
        )
        return cursor.lastrowid

    async def _post_to_platform(
        self,
        platform: str,
        case_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """特定のプラットフォームに投稿"""
        try:
            if platform == "trabox":
                return await self.trabox.post_case(case_data)
            elif platform == "webkit":
                return await self.webkit.post_case(case_data)
            else:
                return {
                    "status": "error",
                    "message": f"不明なプラットフォーム: {platform}"
                }
        except Exception as e:
            logger.error(f"[{platform}] 投稿失敗: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    def _case_tuple_to_dict(self, case_tuple) -> Dict[str, Any]:
        """ケースタプルを辞書に変換"""
        return {
            "case_id": case_tuple[0],
            "pick_location": case_tuple[1],
            "drop_location": case_tuple[2],
            "cargo_weight": case_tuple[3],
            "vehicle_type": case_tuple[4],
            "freight_rate": case_tuple[5],
            "pickup_date": case_tuple[6],
            "pickup_time": case_tuple[7],
            "contact_name": case_tuple[8],
            "contact_phone": case_tuple[9],
            "contact_email": case_tuple[10],
        }
