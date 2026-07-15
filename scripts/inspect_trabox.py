"""
トラボックス UI 要素検査スクリプト
Playwright を使用して要素を自動検査し、
セレクタの最適化を提案します
"""

import asyncio
import json
from playwright.async_api import async_playwright
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TRABOX_URL = "https://www.torabox.com"


class TraboxInspector:
    """トラボックス UI 要素検査クラス"""

    def __init__(self):
        self.elements = {}
        self.selectors = {}

    async def inspect_page(self):
        """トラボックスのページ構造を検査"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()

            try:
                logger.info(f"Accessing {TRABOX_URL}...")
                await page.goto(TRABOX_URL, wait_until="domcontentloaded")

                logger.info("ページロード完了。以下の要素を自動検査しています...")

                # ログイン関連要素の検査
                await self._inspect_login_elements(page)

                # フォーム関連要素の検査
                await self._inspect_form_elements(page)

                # ボタン関連要素の検査
                await self._inspect_button_elements(page)

                logger.info("\n" + "=" * 80)
                logger.info("検査結果サマリー")
                logger.info("=" * 80)
                self._print_results()

                # JSON エクスポート
                self._export_to_json()

            except Exception as e:
                logger.error(f"エラー: {e}")
            finally:
                await browser.close()

    async def _inspect_login_elements(self, page):
        """ログイン関連要素を検査"""
        logger.info("\n【ログイン要素の検査】")

        selectors_to_check = [
            ('input[name="loginid"]', "ID入力フィールド"),
            ('input[name="loginpwd"]', "パスワード入力フィールド"),
            ('button:has-text("ログイン")', "ログインボタン（button）"),
            ('span:has-text("ログイン")', "ログインボタン（span）"),
            ('[data-testid="login-button"]', "ログインボタン（data-testid）"),
            ('form', "ログインフォーム"),
        ]

        for selector, description in selectors_to_check:
            try:
                count = await page.locator(selector).count()
                if count > 0:
                    logger.info(f"✓ {description}: 見つかりました ({count}個)")
                    element = page.locator(selector).first
                    tag_name = await element.evaluate("el => el.tagName")
                    class_name = await element.evaluate("el => el.className")
                    id_attr = await element.evaluate("el => el.id")

                    self.elements[description] = {
                        "selector": selector,
                        "count": count,
                        "tagName": tag_name,
                        "className": class_name,
                        "id": id_attr
                    }
                    logger.info(f"  要素: <{tag_name.lower()} class='{class_name}' id='{id_attr}'>")
                else:
                    logger.info(f"✗ {description}: 見つかりません")
            except Exception as e:
                logger.warning(f"✗ {description}: チェック失敗 - {e}")

    async def _inspect_form_elements(self, page):
        """フォーム関連要素を検査"""
        logger.info("\n【フォーム要素の検査】")

        form_selectors = [
            ('input[type="text"]', "テキスト入力"),
            ('input[type="number"]', "数値入力"),
            ('input[type="date"]', "日付入力"),
            ('input[type="time"]', "時間入力"),
            ('select', "セレクト（ドロップダウン）"),
            ('textarea', "テキストエリア"),
            ('input[type="checkbox"]', "チェックボックス"),
            ('input[type="radio"]', "ラジオボタン"),
        ]

        for selector, description in form_selectors:
            try:
                count = await page.locator(selector).count()
                if count > 0:
                    logger.info(f"✓ {description}: {count}個見つかりました")
                    self.elements[description] = {"selector": selector, "count": count}
            except Exception as e:
                logger.warning(f"✗ {description}: チェック失敗")

    async def _inspect_button_elements(self, page):
        """ボタン関連要素を検査"""
        logger.info("\n【ボタン要素の検査】")

        button_texts = ["送信", "登録", "確認", "キャンセル", "戻る"]

        for text in button_texts:
            try:
                button = page.locator(f"button:has-text('{text}'), span:has-text('{text}')")
                count = await button.count()
                if count > 0:
                    logger.info(f"✓ '{text}' ボタン: {count}個見つかりました")
                    self.elements[f"ボタン: {text}"] = {"selector": f"*:has-text('{text}')", "count": count}
            except Exception as e:
                logger.debug(f"'{text}' ボタン: 見つかりません")

    def _print_results(self):
        """検査結果を表示"""
        if not self.elements:
            logger.info("検査対象の要素が見つかりませんでした")
            return

        for description, info in self.elements.items():
            logger.info(f"\n{description}:")
            for key, value in info.items():
                logger.info(f"  {key}: {value}")

    def _export_to_json(self):
        """検査結果を JSON にエクスポート"""
        filename = "trabox_inspection_result.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.elements, f, ensure_ascii=False, indent=2)
        logger.info(f"\n✓ 検査結果を {filename} にエクスポートしました")


async def run_inspection():
    """検査を実行"""
    print("\n" + "=" * 80)
    print("🔍 トラボックス UI 要素自動検査")
    print("=" * 80)
    print("\n【重要】")
    print("このスクリプトはトラボックスのサイトを実際に開き、")
    print("UI 要素の構造を検査します。")
    print("\n検査中は以下の操作をしないでください：")
    print("  - ブラウザウィンドウを閉じる")
    print("  - ページを操作する")
    print("\n検査結果は trabox_inspection_result.json に保存されます。")
    print("=" * 80 + "\n")

    inspector = TraboxInspector()
    await inspector.inspect_page()


if __name__ == "__main__":
    asyncio.run(run_inspection())
