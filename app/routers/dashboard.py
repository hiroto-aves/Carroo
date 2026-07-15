from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from app.dependencies import get_current_user
from app.db.database import get_db_connection
from datetime import datetime

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/", response_class=HTMLResponse)
async def dashboard(current_user: dict = Depends(get_current_user)):
    """ユーザーダッシュボード"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        user_id = current_user["id"]
        username = current_user["username"]

        # 案件数を取得
        cursor.execute("SELECT COUNT(*) FROM cases WHERE user_id = ?", (user_id,))
        case_count = cursor.fetchone()[0]

        # 投稿成功数を取得
        cursor.execute("""
            SELECT COUNT(*) FROM posting_history
            WHERE case_id IN (SELECT id FROM cases WHERE user_id = ?)
            AND status = 'success'
        """, (user_id,))
        success_count = cursor.fetchone()[0]

        # 投稿失敗数を取得
        cursor.execute("""
            SELECT COUNT(*) FROM posting_history
            WHERE case_id IN (SELECT id FROM cases WHERE user_id = ?)
            AND status = 'error'
        """, (user_id,))
        error_count = cursor.fetchone()[0]

        # 最近の案件を取得
        cursor.execute("""
            SELECT id, pick_location, drop_location, pickup_date, created_at
            FROM cases
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 5
        """, (user_id,))
        recent_cases = cursor.fetchall()

        html = f"""
        <!DOCTYPE html>
        <html lang="ja">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>OneLogi-Post - ダッシュボード</title>
            <script src="https://cdn.tailwindcss.com"></script>
        </head>
        <body class="bg-gray-50">
            <!-- ナビゲーションバー -->
            <nav class="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-50">
                <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div class="flex justify-between h-16 items-center">
                        <div class="flex items-center">
                            <a href="/dashboard" class="text-2xl font-bold text-blue-600">📦 OneLogi-Post</a>
                        </div>
                        <div class="flex items-center gap-6">
                            <div class="text-right">
                                <p class="text-sm text-gray-600">ログイン中:</p>
                                <p class="font-semibold text-gray-900">{username}</p>
                            </div>
                            <div class="w-px h-8 bg-gray-300"></div>
                            <a href="/cases/register" class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition">
                                + 新規案件
                            </a>
                            <a href="/auth/logout" class="text-gray-600 hover:text-red-600 transition">ログアウト</a>
                        </div>
                    </div>
                </div>
            </nav>

            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <!-- ページタイトル -->
                <div class="mb-8">
                    <h1 class="text-4xl font-bold text-gray-900">ダッシュボード</h1>
                    <p class="text-gray-600 mt-2">登録された案件と投稿履歴の確認</p>
                </div>

                <!-- 統計カード -->
                <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                    <!-- 総案件数 -->
                    <div class="bg-white rounded-lg shadow p-6 border-l-4 border-blue-600">
                        <div class="flex items-center justify-between">
                            <div>
                                <p class="text-gray-600 text-sm">総案件数</p>
                                <p class="text-3xl font-bold text-gray-900">{case_count}</p>
                            </div>
                            <div class="text-4xl">📦</div>
                        </div>
                    </div>

                    <!-- 投稿成功 -->
                    <div class="bg-white rounded-lg shadow p-6 border-l-4 border-green-600">
                        <div class="flex items-center justify-between">
                            <div>
                                <p class="text-gray-600 text-sm">投稿成功</p>
                                <p class="text-3xl font-bold text-green-600">{success_count}</p>
                            </div>
                            <div class="text-4xl">✓</div>
                        </div>
                    </div>

                    <!-- 投稿失敗 -->
                    <div class="bg-white rounded-lg shadow p-6 border-l-4 border-red-600">
                        <div class="flex items-center justify-between">
                            <div>
                                <p class="text-gray-600 text-sm">投稿失敗</p>
                                <p class="text-3xl font-bold text-red-600">{error_count}</p>
                            </div>
                            <div class="text-4xl">✗</div>
                        </div>
                    </div>

                    <!-- 成功率 -->
                    <div class="bg-white rounded-lg shadow p-6 border-l-4 border-purple-600">
                        <div class="flex items-center justify-between">
                            <div>
                                <p class="text-gray-600 text-sm">成功率</p>
                                <p class="text-3xl font-bold text-purple-600">
                                    {(success_count / max((success_count + error_count), 1) * 100):.0f}%
                                </p>
                            </div>
                            <div class="text-4xl">📊</div>
                        </div>
                    </div>
                </div>

                <!-- 最近の案件 -->
                <div class="bg-white rounded-lg shadow overflow-hidden">
                    <div class="px-6 py-4 border-b border-gray-200">
                        <h2 class="text-lg font-semibold text-gray-900">最近の案件</h2>
                    </div>

                    <div class="overflow-x-auto">
                        <table class="w-full">
                            <thead class="bg-gray-50 border-b border-gray-200">
                                <tr>
                                    <th class="px-6 py-3 text-left text-sm font-semibold text-gray-700">案件ID</th>
                                    <th class="px-6 py-3 text-left text-sm font-semibold text-gray-700">積地</th>
                                    <th class="px-6 py-3 text-left text-sm font-semibold text-gray-700">卸地</th>
                                    <th class="px-6 py-3 text-left text-sm font-semibold text-gray-700">日付</th>
                                    <th class="px-6 py-3 text-left text-sm font-semibold text-gray-700">アクション</th>
                                </tr>
                            </thead>
                            <tbody>
        """

        if recent_cases:
            for case in recent_cases:
                case_id, pick_loc, drop_loc, pickup_date, created_at = case
                html += f"""
                                <tr class="border-b border-gray-200 hover:bg-gray-50 transition">
                                    <td class="px-6 py-4 text-sm text-gray-900">#{case_id}</td>
                                    <td class="px-6 py-4 text-sm text-gray-600">{pick_loc}</td>
                                    <td class="px-6 py-4 text-sm text-gray-600">{drop_loc}</td>
                                    <td class="px-6 py-4 text-sm text-gray-600">{pickup_date}</td>
                                    <td class="px-6 py-4 text-sm">
                                        <a href="/dashboard/cases/{case_id}" class="text-blue-600 hover:text-blue-700 font-medium">
                                            詳細を見る →
                                        </a>
                                    </td>
                                </tr>
                """
        else:
            html += """
                                <tr>
                                    <td colspan="5" class="px-6 py-8 text-center text-gray-500">
                                        案件がまだ登録されていません
                                    </td>
                                </tr>
            """

        html += """
                            </tbody>
                        </table>
                    </div>

                    <div class="px-6 py-4 border-t border-gray-200 bg-gray-50">
                        <a href="/dashboard/cases" class="text-blue-600 hover:text-blue-700 font-medium">
                            すべての案件を見る →
                        </a>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

        return html

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/cases", response_class=HTMLResponse)
async def cases_list(current_user: dict = Depends(get_current_user)):
    """案件一覧"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        user_id = current_user["id"]
        username = current_user["username"]

        # すべての案件を取得
        cursor.execute("""
            SELECT id, pick_location, drop_location, cargo_weight, vehicle_type,
                   freight_rate, pickup_date, created_at
            FROM cases
            WHERE user_id = ?
            ORDER BY created_at DESC
        """, (user_id,))
        cases = cursor.fetchall()

        html = f"""
        <!DOCTYPE html>
        <html lang="ja">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>OneLogi-Post - 案件一覧</title>
            <script src="https://cdn.tailwindcss.com"></script>
        </head>
        <body class="bg-gray-50">
            <!-- ナビゲーションバー -->
            <nav class="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-50">
                <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div class="flex justify-between h-16 items-center">
                        <div class="flex items-center">
                            <a href="/dashboard" class="text-2xl font-bold text-blue-600">📦 OneLogi-Post</a>
                        </div>
                        <div class="flex items-center gap-6">
                            <a href="/cases/register" class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition">
                                + 新規案件
                            </a>
                            <a href="/auth/logout" class="text-gray-600 hover:text-red-600 transition">ログアウト</a>
                        </div>
                    </div>
                </div>
            </nav>

            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <div class="flex items-center justify-between mb-8">
                    <div>
                        <a href="/dashboard" class="text-blue-600 hover:text-blue-700 text-sm">← ダッシュボードに戻る</a>
                        <h1 class="text-4xl font-bold text-gray-900 mt-2">案件一覧</h1>
                        <p class="text-gray-600 mt-2">全 {len(cases)} 件の案件</p>
                    </div>
                </div>

                <div class="bg-white rounded-lg shadow overflow-hidden">
                    <div class="overflow-x-auto">
                        <table class="w-full">
                            <thead class="bg-gray-50 border-b border-gray-200">
                                <tr>
                                    <th class="px-6 py-3 text-left text-sm font-semibold text-gray-700">ID</th>
                                    <th class="px-6 py-3 text-left text-sm font-semibold text-gray-700">積地</th>
                                    <th class="px-6 py-3 text-left text-sm font-semibold text-gray-700">卸地</th>
                                    <th class="px-6 py-3 text-left text-sm font-semibold text-gray-700">重量</th>
                                    <th class="px-6 py-3 text-left text-sm font-semibold text-gray-700">車種</th>
                                    <th class="px-6 py-3 text-left text-sm font-semibold text-gray-700">運賃</th>
                                    <th class="px-6 py-3 text-left text-sm font-semibold text-gray-700">日付</th>
                                    <th class="px-6 py-3 text-left text-sm font-semibold text-gray-700">アクション</th>
                                </tr>
                            </thead>
                            <tbody>
        """

        if cases:
            for case in cases:
                case_id, pick_loc, drop_loc, weight, vehicle, rate, date, created = case
                html += f"""
                                <tr class="border-b border-gray-200 hover:bg-gray-50 transition">
                                    <td class="px-6 py-4 text-sm font-semibold text-gray-900">#{case_id}</td>
                                    <td class="px-6 py-4 text-sm text-gray-600">{pick_loc}</td>
                                    <td class="px-6 py-4 text-sm text-gray-600">{drop_loc}</td>
                                    <td class="px-6 py-4 text-sm text-gray-600">{weight:.1f}kg</td>
                                    <td class="px-6 py-4 text-sm text-gray-600">{vehicle}</td>
                                    <td class="px-6 py-4 text-sm text-gray-600">¥{rate:,.0f}</td>
                                    <td class="px-6 py-4 text-sm text-gray-600">{date}</td>
                                    <td class="px-6 py-4 text-sm">
                                        <a href="/dashboard/cases/{case_id}" class="text-blue-600 hover:text-blue-700 font-medium">
                                            詳細
                                        </a>
                                    </td>
                                </tr>
                """
        else:
            html += """
                                <tr>
                                    <td colspan="8" class="px-6 py-8 text-center text-gray-500">
                                        案件がまだ登録されていません
                                    </td>
                                </tr>
            """

        html += """
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

        return html

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/cases/{case_id}", response_class=HTMLResponse)
async def case_detail(case_id: int, current_user: dict = Depends(get_current_user)):
    """案件詳細"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        user_id = current_user["id"]

        # 案件を取得
        cursor.execute("""
            SELECT id, user_id, pick_location, drop_location, cargo_weight, vehicle_type,
                   freight_rate, pickup_date, pickup_time, contact_name, contact_phone,
                   contact_email, created_at
            FROM cases
            WHERE id = ? AND user_id = ?
        """, (case_id, user_id))

        case = cursor.fetchone()

        if not case:
            raise HTTPException(status_code=404, detail="案件が見つかりません")

        # 投稿履歴を取得
        cursor.execute("""
            SELECT id, platform, status, posted_at, error_message
            FROM posting_history
            WHERE case_id = ?
            ORDER BY posted_at DESC
        """, (case_id,))

        histories = cursor.fetchall()

        case_id, user_id, pick_loc, drop_loc, weight, vehicle, rate, date, time, contact_name, contact_phone, contact_email, created_at = case

        html = f"""
        <!DOCTYPE html>
        <html lang="ja">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>OneLogi-Post - 案件詳細</title>
            <script src="https://cdn.tailwindcss.com"></script>
        </head>
        <body class="bg-gray-50">
            <!-- ナビゲーションバー -->
            <nav class="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-50">
                <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div class="flex justify-between h-16 items-center">
                        <div class="flex items-center">
                            <a href="/dashboard" class="text-2xl font-bold text-blue-600">📦 OneLogi-Post</a>
                        </div>
                        <a href="/auth/logout" class="text-gray-600 hover:text-red-600 transition">ログアウト</a>
                    </div>
                </div>
            </nav>

            <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <a href="/dashboard/cases" class="text-blue-600 hover:text-blue-700 text-sm">← 案件一覧に戻る</a>

                <h1 class="text-4xl font-bold text-gray-900 mt-4 mb-8">案件詳細 #{case_id}</h1>

                <!-- 案件情報 -->
                <div class="bg-white rounded-lg shadow overflow-hidden mb-8">
                    <div class="px-6 py-4 border-b border-gray-200 bg-gray-50">
                        <h2 class="text-lg font-semibold text-gray-900">案件情報</h2>
                    </div>
                    <div class="p-6">
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div>
                                <p class="text-sm text-gray-600">積地</p>
                                <p class="text-lg font-semibold text-gray-900">{pick_loc}</p>
                            </div>
                            <div>
                                <p class="text-sm text-gray-600">卸地</p>
                                <p class="text-lg font-semibold text-gray-900">{drop_loc}</p>
                            </div>
                            <div>
                                <p class="text-sm text-gray-600">荷物重量</p>
                                <p class="text-lg font-semibold text-gray-900">{weight:.1f} kg</p>
                            </div>
                            <div>
                                <p class="text-sm text-gray-600">車種</p>
                                <p class="text-lg font-semibold text-gray-900">{vehicle}</p>
                            </div>
                            <div>
                                <p class="text-sm text-gray-600">運賃</p>
                                <p class="text-lg font-semibold text-gray-900">¥{rate:,.0f}</p>
                            </div>
                            <div>
                                <p class="text-sm text-gray-600">積地日付</p>
                                <p class="text-lg font-semibold text-gray-900">{date}{f" {time}" if time else ""}</p>
                            </div>
                        </div>

                        <hr class="my-6">

                        <div>
                            <h3 class="font-semibold text-gray-900 mb-4">連絡先情報</h3>
                            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                                <div>
                                    <p class="text-sm text-gray-600">担当者名</p>
                                    <p class="text-gray-900">{contact_name or '(未設定)'}</p>
                                </div>
                                <div>
                                    <p class="text-sm text-gray-600">電話番号</p>
                                    <p class="text-gray-900">{contact_phone or '(未設定)'}</p>
                                </div>
                                <div>
                                    <p class="text-sm text-gray-600">メールアドレス</p>
                                    <p class="text-gray-900">{contact_email or '(未設定)'}</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 投稿履歴 -->
                <div class="bg-white rounded-lg shadow overflow-hidden">
                    <div class="px-6 py-4 border-b border-gray-200 bg-gray-50">
                        <h2 class="text-lg font-semibold text-gray-900">投稿履歴</h2>
                    </div>
                    <div class="p-6">
        """

        if histories:
            html += """
                        <div class="space-y-3">
            """
            for history in histories:
                hist_id, platform, status, posted_at, error_msg = history
                status_badge = '✓ 成功' if status == 'success' else '✗ エラー'
                status_color = 'bg-green-100 text-green-800' if status == 'success' else 'bg-red-100 text-red-800'

                html += f"""
                            <div class="flex items-start justify-between p-4 border border-gray-200 rounded-lg hover:bg-gray-50">
                                <div>
                                    <p class="font-semibold text-gray-900">{platform.upper()}</p>
                                    <p class="text-sm text-gray-600">{posted_at}</p>
                                    {f'<p class="text-sm text-red-600 mt-2">{error_msg}</p>' if error_msg else ''}
                                </div>
                                <span class="px-3 py-1 rounded-full text-sm font-medium {status_color}">
                                    {status_badge}
                                </span>
                            </div>
                """
            html += """
                        </div>
            """
        else:
            html += """
                        <p class="text-gray-500 text-center py-8">投稿履歴がありません</p>
            """

        html += """
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

        return html

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
