"""Trabox 投稿ロジックのテストスクリプト

使用方法:
    python test_trabox_posting.py

環境変数:
    TRABOX_TEST_USERNAME: Trabox テストアカウントのユーザー名
    TRABOX_TEST_PASSWORD: Trabox テストアカウントのパスワード
"""
import asyncio
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

# ロギング設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_trabox_posting():
    """Trabox 投稿テスト"""
    from app.config import settings
    from app.automations.trabox import TraboxAutomation
    from app.utils.structured_logging import structured_logger

    # テストアカウント確認
    if not settings.TRABOX_TEST_USERNAME or not settings.TRABOX_TEST_PASSWORD:
        logger.error("❌ TRABOX_TEST_USERNAME または TRABOX_TEST_PASSWORD が設定されていません")
        logger.error("環境変数を設定してください:")
        logger.error("  export TRABOX_TEST_USERNAME=your_username")
        logger.error("  export TRABOX_TEST_PASSWORD=your_password")
        return False

    logger.info("=" * 80)
    logger.info("🚀 Trabox 投稿テスト開始")
    logger.info("=" * 80)

    # テストデータ
    test_case_data = {
        "pick_location": "東京都",  # TODO: 実際の値を確認
        "drop_location": "大阪府",  # TODO: 実際の値を確認
        "cargo_weight": 100,
        "vehicle_type": "small_truck",
        "freight_rate": 50000,
        "pickup_date": (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d"),
        "pickup_time": "10:00",
        "contact_name": "テスト太郎",
        "contact_phone": "09012345678",
        "contact_email": "test@example.com",
    }

    logger.info("\n📋 テストデータ:")
    for key, value in test_case_data.items():
        logger.info(f"  {key}: {value}")

    # TraboxAutomation を実行
    trabox = TraboxAutomation(
        user_id=1,
        case_id=999,  # テスト用 ID
        username=settings.TRABOX_TEST_USERNAME,
        password=settings.TRABOX_TEST_PASSWORD,
    )

    logger.info(f"\n🔍 トレース ID: {structured_logger.trace_id}")
    logger.info(f"🔍 セッション ID: {structured_logger.session_id}")

    try:
        logger.info("\n▶️  投稿処理開始...")
        result = await trabox.post_case(test_case_data)

        logger.info("\n" + "=" * 80)
        logger.info("✅ テスト成功！")
        logger.info("=" * 80)
        logger.info(f"\n投稿結果:")
        for key, value in result.items():
            logger.info(f"  {key}: {value}")

        # デバッグ情報を表示
        logger.info(f"\n📸 キャプチャ数: {trabox.debug_capture.get_screenshots_count()}")
        logger.info(f"📝 コンソールログ: {len(trabox.debug_capture.get_console_logs())} 件")
        logger.info(f"⚠️  ページエラー: {len(trabox.debug_capture.get_page_errors())} 件")

        # デバッグログの保存先を表示
        debug_dir = Path("debug_logs") / datetime.now().strftime("%Y-%m-%d") / structured_logger.trace_id
        if debug_dir.exists():
            logger.info(f"\n📁 デバッグログ保存先: {debug_dir}")
            logger.info("   ファイル一覧:")
            for file in debug_dir.glob("*"):
                logger.info(f"     - {file.name}")

        return True

    except Exception as e:
        logger.error("\n" + "=" * 80)
        logger.error("❌ テスト失敗")
        logger.error("=" * 80)
        logger.error(f"\nエラー: {e}")
        logger.exception(e)

        # デバッグログの保存先を表示
        debug_dir = Path("debug_logs") / datetime.now().strftime("%Y-%m-%d") / structured_logger.trace_id
        if debug_dir.exists():
            logger.error(f"\n📁 デバッグログ保存先: {debug_dir}")
            logger.error("   ファイル一覧:")
            for file in debug_dir.glob("*"):
                logger.error(f"     - {file.name}")
            logger.error("\n💡 エラーの詳細はデバッグログを確認してください")

        return False


async def main():
    """メイン処理"""
    success = await test_trabox_posting()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
