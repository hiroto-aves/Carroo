from fastapi import APIRouter, HTTPException, status, Form, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from app.models.schemas import CaseCreate, Case
from app.db.database import get_db_connection
from app.automations.trabox import TraboxAutomation
from app.automations.webkit import WebkitAutomation
from app.dependencies import get_current_user
from app.services.cloud_tasks import get_task_client
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cases", tags=["cases"])

@router.get("/register", response_class=HTMLResponse)
async def case_register_page():
    return """
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Carroo - 案件登録</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-50">
        <!-- ナビゲーションバー -->
        <nav class="bg-white shadow-sm border-b border-gray-200">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="flex justify-between h-16 items-center">
                    <div class="flex items-center">
                        <span class="text-2xl font-bold text-blue-600">📦 Carroo</span>
                    </div>
                    <div class="flex items-center gap-4">
                        <a href="/auth/me" class="text-gray-600 hover:text-gray-900">プロフィール</a>
                        <a href="/auth/logout" class="text-red-600 hover:text-red-700">ログアウト</a>
                    </div>
                </div>
            </div>
        </nav>

        <div class="min-h-screen py-12 px-4">
            <div class="max-w-4xl mx-auto">
                <!-- ヘッダー -->
                <div class="mb-8">
                    <h1 class="text-4xl font-bold text-gray-900 mb-2">案件登録</h1>
                    <p class="text-gray-600">複数のプラットフォームへ一括投稿できます</p>
                </div>

                <!-- フォーム -->
                <div class="bg-white rounded-2xl shadow-lg overflow-hidden">
                    <div class="p-8">

                    <form method="post" action="/cases/register" class="space-y-8">
                        <!-- セクション 1: 基本情報 -->
                        <div>
                            <h3 class="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                                <span class="w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm font-bold mr-3">1</span>
                                基本情報
                            </h3>

                            <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-2">積地（都道府県）</label>
                                    <input type="text" name="pick_location" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition" required placeholder="東京都">
                                </div>
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-2">卸地（都道府県）</label>
                                    <input type="text" name="drop_location" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition" required placeholder="大阪府">
                                </div>
                            </div>

                            <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-2">荷物重量（kg）</label>
                                    <input type="number" name="cargo_weight" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition" step="0.1" required>
                                </div>
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-2">車種</label>
                                    <select name="vehicle_type" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition" required>
                                        <option value="">選択してください</option>
                                        <option value="small_truck">小型トラック</option>
                                        <option value="medium_truck">中型トラック</option>
                                        <option value="large_truck">大型トラック</option>
                                        <option value="trailer">トレーラー</option>
                                    </select>
                                </div>
                            </div>

                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-2">運賃（円）</label>
                                <input type="number" name="freight_rate" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition" step="100" required>
                        </div>
                    </div>

                        </div>
                        </div>

                        <!-- セクション 2: 日時情報 -->
                        <div>
                            <h3 class="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                                <span class="w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm font-bold mr-3">2</span>
                                日時情報
                            </h3>

                            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-2">積地日付</label>
                                    <input type="date" name="pickup_date" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition" required>
                                </div>
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-2">積地時間</label>
                                    <input type="time" name="pickup_time" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition">
                                </div>
                            </div>
                        </div>

                        <!-- セクション 3: 連絡先 -->
                        <div>
                            <h3 class="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                                <span class="w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm font-bold mr-3">3</span>
                                連絡先
                            </h3>

                            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-2">担当者名</label>
                                    <input type="text" name="contact_name" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition" placeholder="山田太郎">
                                </div>
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-2">電話番号</label>
                                    <input type="tel" name="contact_phone" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition" placeholder="09012345678">
                                </div>
                            </div>

                            <div class="mt-6">
                                <label class="block text-sm font-medium text-gray-700 mb-2">メールアドレス</label>
                                <input type="email" name="contact_email" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition" placeholder="example@domain.com">
                            </div>
                        </div>

                        <!-- セクション 4: 投稿先選択 -->
                        <div>
                            <h3 class="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                                <span class="w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm font-bold mr-3">4</span>
                                投稿先を選択
                            </h3>

                            <div class="space-y-3">
                                <label class="flex items-center p-4 border border-gray-300 rounded-lg cursor-pointer hover:bg-blue-50 transition">
                                    <input type="checkbox" name="post_to_trabox" class="w-5 h-5 text-blue-600 rounded">
                                    <div class="ml-3">
                                        <span class="block font-medium text-gray-900">トラボックス</span>
                                        <span class="block text-sm text-gray-600">Playwright を使用した自動投稿</span>
                                    </div>
                                </label>
                                <label class="flex items-center p-4 border border-gray-300 rounded-lg cursor-pointer hover:bg-blue-50 transition">
                                    <input type="checkbox" name="post_to_webkit" class="w-5 h-5 text-blue-600 rounded">
                                    <div class="ml-3">
                                        <span class="block font-medium text-gray-900">Webkit</span>
                                        <span class="block text-sm text-gray-600">XML API を使用した自動投稿</span>
                                    </div>
                                </label>
                            </div>
                        </div>

                        <!-- トラボックス認証情報 -->
                        <div id="trabox-auth" class="hidden bg-gradient-to-br from-blue-50 to-blue-100 p-6 rounded-lg border border-blue-200">
                            <h4 class="font-semibold text-gray-900 mb-4">🔐 トラボックスのログイン情報</h4>
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-2">ユーザーID</label>
                                    <input type="text" name="trabox_username" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition" placeholder="ログインID">
                                </div>
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-2">パスワード</label>
                                    <input type="password" name="trabox_password" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition" placeholder="パスワード">
                                </div>
                            </div>
                        </div>

                        <!-- 送信ボタン -->
                        <button type="submit" class="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-lg transition duration-200 mt-8">
                            ✓ 案件を登録
                        </button>
                    </form>
                    </div>
                </div>
            </div>
        </div>
            </div>
        </div>

        <script>
            const traboxCheckbox = document.querySelector('input[name="post_to_trabox"]');
            const traboxAuth = document.getElementById('trabox-auth');

            traboxCheckbox.addEventListener('change', () => {
                traboxAuth.classList.toggle('hidden');
            });
        </script>
    </body>
    </html>
    """

@router.post("/register")
async def register_case(
    pick_location: str = Form(...),
    drop_location: str = Form(...),
    cargo_weight: float = Form(...),
    vehicle_type: str = Form(...),
    freight_rate: float = Form(...),
    pickup_date: str = Form(...),
    pickup_time: Optional[str] = Form(None),
    contact_name: Optional[str] = Form(None),
    contact_phone: Optional[str] = Form(None),
    contact_email: Optional[str] = Form(None),
    post_to_trabox: Optional[str] = Form(None),
    post_to_webkit: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
):
    """
    案件登録 + 非同期投稿キュー追加エンドポイント

    フロー（GCP Cloud Tasks）:
    1. DB に案件データを保存（同期）
    2. Cloud Tasks にタスク追加（0.1秒で即座に返す）
    3. 背景で Cloud Run が投稿処理を実行

    投稿先:
    - トラボックス: .env の TRABOX_TEST_USERNAME, TRABOX_TEST_PASSWORD
    - WebKIT: .env の WEBKIT_LOGIN_ID, WEBKIT_LOGIN_PASSWORD
    """

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        user_id = current_user["id"]

        # Step 1: 案件データを DB に保存
        cursor.execute(
            """INSERT INTO cases
            (user_id, pick_location, drop_location, cargo_weight, vehicle_type, freight_rate, pickup_date, pickup_time, contact_name, contact_phone, contact_email)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, pick_location, drop_location, cargo_weight, vehicle_type, freight_rate, pickup_date, pickup_time, contact_name, contact_phone, contact_email)
        )
        conn.commit()
        case_id = cursor.lastrowid

        # Step 2: 投稿用データを構築
        case_data = {
            "case_id": case_id,
            "user_id": user_id,
            "pick_location": pick_location,
            "drop_location": drop_location,
            "cargo_weight": cargo_weight,
            "vehicle_type": vehicle_type,
            "freight_rate": freight_rate,
            "pickup_date": pickup_date,
            "pickup_time": pickup_time,
            "contact_name": contact_name,
            "contact_phone": contact_phone,
            "contact_email": contact_email,
            "post_to_trabox": post_to_trabox == "yes",
            "post_to_webkit": post_to_webkit == "yes",
        }

        # Step 3: Cloud Tasks にタスク追加（0.1秒で返す）
        task_client = get_task_client()
        task_name = task_client.add_posting_task(case_data, user_id)
        logger.info(f"✅ タスク追加: Case ID {case_id} → {task_name}")

        # Step 4: posting_history に「pending」状態で記録
        if post_to_trabox == "yes":
            cursor.execute(
                "INSERT INTO posting_history (case_id, platform, status) VALUES (?, ?, ?)",
                (case_id, "trabox", "pending")
            )
        if post_to_webkit == "yes":
            cursor.execute(
                "INSERT INTO posting_history (case_id, platform, status) VALUES (?, ?, ?)",
                (case_id, "webkit", "pending")
            )
        conn.commit()

        # Step 5: 即座に返す（投稿処理は背景で実行）
        return JSONResponse(
            status_code=202,
            content={
                "status": "success",
                "message": "✅ 投稿をキューに追加しました",
                "case_id": case_id,
                "task_name": task_name,
                "platforms_queued": {
                    "trabox": post_to_trabox == "yes",
                    "webkit": post_to_webkit == "yes"
                }
            }
        )

    except Exception as e:
        conn.rollback()
        logger.error(f"❌ エラー: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    finally:
        conn.close()
