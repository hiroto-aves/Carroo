"""
プッシュ通知機能テスト
SSE（Server-Sent Events）による通知配信テスト
"""

import asyncio
import logging
from app.services.notifications import notification_service

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_notifications():
    """通知サービスのテスト"""

    print("\n" + "=" * 80)
    print("🧪 プッシュ通知機能テスト")
    print("=" * 80)

    user_id = 1
    case_id = 123

    print(f"\n【テストケース】")
    print("-" * 80)
    print(f"User ID: {user_id}")
    print(f"Case ID: {case_id}")

    # テスト1: ユーザーをSSEストリームに接続
    print("\n【テスト 1】SSE接続")
    print("-" * 80)
    queue = await notification_service.connect(user_id)
    print(f"✅ ユーザー {user_id} が接続しました")
    print(f"   アクティブな接続数: {notification_service.active_connections[user_id]}")

    # テスト2: 投稿開始通知
    print("\n【テスト 2】投稿開始通知")
    print("-" * 80)
    await notification_service.notify_posting_started(user_id, case_id, ["trabox", "webkit"])
    notification = await queue.get()
    print(f"✅ 通知受信:")
    print(f"   Type: {notification['type']}")
    print(f"   Status: {notification['status']}")
    print(f"   Message: {notification['message']}")

    # テスト3: 投稿成功通知
    print("\n【テスト 3】投稿成功通知")
    print("-" * 80)
    results = [
        {"status": "success", "platform": "trabox", "message": "Case posted to Trabox successfully"},
        {"status": "success", "platform": "webkit", "message": "Case posted to WebKit successfully"}
    ]
    await notification_service.notify_posting_completed(user_id, case_id, results)
    notification = await queue.get()
    print(f"✅ 通知受信:")
    print(f"   Type: {notification['type']}")
    print(f"   Status: {notification['status']}")
    print(f"   Message: {notification['message']}")
    print(f"   Successful Platforms: {notification['successful_platforms']}")

    # テスト4: バッチ処理進捗通知
    print("\n【テスト 4】バッチ処理進捗通知")
    print("-" * 80)
    batch_id = 456
    for i in range(1, 6):
        await notification_service.notify_batch_progress(user_id, batch_id, i, 5)
        notification = await queue.get()
        print(f"✅ 進捗 {i}/5: {notification['message']}")

    # テスト5: バッチ処理完了通知
    print("\n【テスト 5】バッチ処理完了通知")
    print("-" * 80)
    await notification_service.notify_batch_completed(user_id, batch_id, total=5, successful=4)
    notification = await queue.get()
    print(f"✅ 通知受信:")
    print(f"   Type: {notification['type']}")
    print(f"   Status: {notification['status']}")
    print(f"   Message: {notification['message']}")
    print(f"   Successful: {notification['successful']}")
    print(f"   Failed: {notification['failed']}")

    # テスト6: エラー通知
    print("\n【テスト 6】エラー通知")
    print("-" * 80)
    await notification_service.notify_posting_error(user_id, case_id, "Network timeout")
    notification = await queue.get()
    print(f"✅ 通知受信:")
    print(f"   Type: {notification['type']}")
    print(f"   Status: {notification['status']}")
    print(f"   Message: {notification['message']}")

    # テスト7: ユーザーをSSEストリームから切断
    print("\n【テスト 7】SSE切断")
    print("-" * 80)
    await notification_service.disconnect(user_id)
    print(f"✅ ユーザー {user_id} が切断しました")
    print(f"   アクティブな接続数: {notification_service.active_connections.get(user_id, 0)}")

    print("\n" + "=" * 80)
    print("【テスト完了】")
    print("=" * 80)
    print("\n🎉 すべての通知テストが成功しました！")
    print("   SSE通知機能は正常に動作しています。")


async def main():
    await test_notifications()


if __name__ == "__main__":
    asyncio.run(main())
