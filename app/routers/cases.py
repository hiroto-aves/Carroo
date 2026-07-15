from fastapi import APIRouter, HTTPException, status, Form
from fastapi.responses import HTMLResponse
from app.models.schemas import CaseCreate, Case
from app.db.database import get_db_connection
from app.automations.trabox import TraboxAutomation
from app.automations.webkit import WebkitAutomation
from typing import Optional

router = APIRouter(prefix="/cases", tags=["cases"])

@router.get("/register", response_class=HTMLResponse)
async def case_register_page():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>OneLogi-Post - 案件登録</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-50">
        <div class="min-h-screen py-8">
            <div class="max-w-2xl mx-auto bg-white p-8 rounded-lg shadow-md">
                <h1 class="text-3xl font-bold mb-8 text-center">案件登録</h1>

                <form method="post" action="/cases/register" class="space-y-6">
                    <!-- 基本情報 -->
                    <div class="border-b pb-6">
                        <h2 class="text-lg font-semibold mb-4">基本情報</h2>

                        <div class="grid grid-cols-2 gap-4 mb-4">
                            <div>
                                <label class="block text-gray-700 mb-2">積地（都道府県）</label>
                                <input type="text" name="pick_location" class="w-full px-4 py-2 border rounded" required placeholder="東京都">
                            </div>
                            <div>
                                <label class="block text-gray-700 mb-2">卸地（都道府県）</label>
                                <input type="text" name="drop_location" class="w-full px-4 py-2 border rounded" required placeholder="大阪府">
                            </div>
                        </div>

                        <div class="mb-4">
                            <label class="block text-gray-700 mb-2">荷物重量（kg）</label>
                            <input type="number" name="cargo_weight" class="w-full px-4 py-2 border rounded" step="0.1" required>
                        </div>

                        <div class="mb-4">
                            <label class="block text-gray-700 mb-2">車種</label>
                            <select name="vehicle_type" class="w-full px-4 py-2 border rounded" required>
                                <option value="">選択</option>
                                <option value="small_truck">小型トラック</option>
                                <option value="medium_truck">中型トラック</option>
                                <option value="large_truck">大型トラック</option>
                                <option value="trailer">トレーラー</option>
                            </select>
                        </div>

                        <div class="mb-4">
                            <label class="block text-gray-700 mb-2">運賃（円）</label>
                            <input type="number" name="freight_rate" class="w-full px-4 py-2 border rounded" step="100" required>
                        </div>
                    </div>

                    <!-- 日時情報 -->
                    <div class="border-b pb-6">
                        <h2 class="text-lg font-semibold mb-4">日時情報</h2>

                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label class="block text-gray-700 mb-2">積地日付</label>
                                <input type="date" name="pickup_date" class="w-full px-4 py-2 border rounded" required>
                            </div>
                            <div>
                                <label class="block text-gray-700 mb-2">積地時間</label>
                                <input type="time" name="pickup_time" class="w-full px-4 py-2 border rounded">
                            </div>
                        </div>
                    </div>

                    <!-- 連絡先 -->
                    <div class="border-b pb-6">
                        <h2 class="text-lg font-semibold mb-4">連絡先</h2>

                        <div class="mb-4">
                            <label class="block text-gray-700 mb-2">担当者名</label>
                            <input type="text" name="contact_name" class="w-full px-4 py-2 border rounded">
                        </div>

                        <div class="mb-4">
                            <label class="block text-gray-700 mb-2">電話番号</label>
                            <input type="tel" name="contact_phone" class="w-full px-4 py-2 border rounded">
                        </div>

                        <div class="mb-4">
                            <label class="block text-gray-700 mb-2">メールアドレス</label>
                            <input type="email" name="contact_email" class="w-full px-4 py-2 border rounded">
                        </div>
                    </div>

                    <!-- 投稿先選択 -->
                    <div class="pb-6">
                        <h2 class="text-lg font-semibold mb-4">投稿先</h2>

                        <div class="flex gap-6">
                            <label class="flex items-center gap-2 cursor-pointer">
                                <input type="checkbox" name="post_to_trabox" class="w-4 h-4">
                                <span class="text-gray-700">トラボックス</span>
                            </label>
                            <label class="flex items-center gap-2 cursor-pointer">
                                <input type="checkbox" name="post_to_webkit" class="w-4 h-4">
                                <span class="text-gray-700">Webkit</span>
                            </label>
                        </div>
                    </div>

                    <!-- 認証情報（トラボックス用） -->
                    <div id="trabox-auth" class="hidden bg-gray-50 p-4 rounded mb-6">
                        <h3 class="font-semibold mb-3">トラボックスのログイン情報</h3>
                        <div class="mb-3">
                            <label class="block text-gray-700 mb-2">ユーザーID</label>
                            <input type="text" name="trabox_username" class="w-full px-4 py-2 border rounded">
                        </div>
                        <div class="mb-3">
                            <label class="block text-gray-700 mb-2">パスワード</label>
                            <input type="password" name="trabox_password" class="w-full px-4 py-2 border rounded">
                        </div>
                    </div>

                    <button type="submit" class="w-full bg-blue-500 text-white py-3 rounded font-semibold hover:bg-blue-600">
                        案件を登録
                    </button>
                </form>
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
    post_to_trabox: bool = Form(False),
    post_to_webkit: bool = Form(False),
    trabox_username: Optional[str] = Form(None),
    trabox_password: Optional[str] = Form(None),
):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        user_id = 1  # TODO: セッションから取得

        cursor.execute(
            """INSERT INTO cases
            (user_id, pick_location, drop_location, cargo_weight, vehicle_type, freight_rate, pickup_date, pickup_time, contact_name, contact_phone, contact_email)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, pick_location, drop_location, cargo_weight, vehicle_type, freight_rate, pickup_date, pickup_time, contact_name, contact_phone, contact_email)
        )
        conn.commit()
        case_id = cursor.lastrowid

        case_data = {
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
        }

        results = []

        if post_to_trabox and trabox_username and trabox_password:
            case_data["username"] = trabox_username
            case_data["password"] = trabox_password
            trabox = TraboxAutomation()
            result = await trabox.post_case(case_data)
            results.append(result)

            cursor.execute(
                "INSERT INTO posting_history (case_id, platform, status, error_message) VALUES (?, ?, ?, ?)",
                (case_id, "trabox", result.get("status"), result.get("message") if result.get("status") == "error" else None)
            )
            conn.commit()

        if post_to_webkit:
            webkit = WebkitAutomation()
            result = await webkit.post_case(case_data)
            results.append(result)

            cursor.execute(
                "INSERT INTO posting_history (case_id, platform, status, error_message) VALUES (?, ?, ?, ?)",
                (case_id, "webkit", result.get("status"), result.get("message") if result.get("status") == "error" else None)
            )
            conn.commit()

        return {
            "status": "success",
            "case_id": case_id,
            "posting_results": results,
            "message": "Case registered and posted successfully"
        }

    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    finally:
        conn.close()
