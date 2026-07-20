"""Trabox フォーム入力の詳細デバッグ

実際のフォーム要素を検査して、セレクターが正しいか確認
"""
import asyncio
import os
import json
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright


async def inspect_form_elements(page):
    """ページのフォーム要素を詳しく検査"""

    print("\n" + "="*80)
    print("📋 フォーム要素の詳細検査")
    print("="*80)

    # input 要素の情報を収集
    inputs = await page.locator("input").all()
    print(f"\n📝 input 要素: {len(inputs)} 個")
    for i, inp in enumerate(inputs[:15]):
        try:
            name = await inp.get_attribute("name")
            type_attr = await inp.get_attribute("type")
            id_attr = await inp.get_attribute("id")
            placeholder = await inp.get_attribute("placeholder")
            value = await inp.input_value()
            visible = await inp.is_visible()
            print(f"  [{i}] name='{name}' type='{type_attr}' id='{id_attr}' visible={visible}")
            print(f"       placeholder='{placeholder}' value='{value}'")
        except Exception as e:
            print(f"  [{i}] エラー: {e}")

    # select 要素の情報を収集
    selects = await page.locator("select").all()
    print(f"\n📝 select 要素: {len(selects)} 個")
    for i, sel in enumerate(selects[:10]):
        try:
            name = await sel.get_attribute("name")
            id_attr = await sel.get_attribute("id")
            visible = await sel.is_visible()
            print(f"  [{i}] name='{name}' id='{id_attr}' visible={visible}")
        except Exception as e:
            print(f"  [{i}] エラー: {e}")

    # textarea 要素
    textareas = await page.locator("textarea").all()
    print(f"\n📝 textarea 要素: {len(textareas)} 個")
    for i, ta in enumerate(textareas[:5]):
        try:
            name = await ta.get_attribute("name")
            id_attr = await ta.get_attribute("id")
            visible = await ta.is_visible()
            print(f"  [{i}] name='{name}' id='{id_attr}' visible={visible}")
        except Exception as e:
            print(f"  [{i}] エラー: {e}")

    # ボタン要素
    buttons = await page.locator("button, input[type='submit'], input[type='button']").all()
    print(f"\n📝 ボタン要素: {len(buttons)} 個")
    for i, btn in enumerate(buttons[:10]):
        try:
            text = await btn.text_content()
            type_attr = await btn.get_attribute("type")
            name = await btn.get_attribute("name")
            visible = await btn.is_visible()
            print(f"  [{i}] type='{type_attr}' name='{name}' text='{text}' visible={visible}")
        except Exception as e:
            print(f"  [{i}] エラー: {e}")


async def test_trabox_detailed():
    """Trabox フォーム入力を詳細にデバッグ"""

    username = os.getenv("TRABOX_TEST_USERNAME")
    password = os.getenv("TRABOX_TEST_PASSWORD")

    if not username or not password:
        print("❌ 環境変数が設定されていません:")
        print("  export TRABOX_TEST_USERNAME=...")
        print("  export TRABOX_TEST_PASSWORD=...")
        return

    screenshot_dir = Path("debug_inspection") / datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        try:
            # ログイン
            print("\n🔐 ステップ1: ログイン...")
            await page.goto("https://www.trabox.com/baggage/list/opened", timeout=30000)
            await page.fill("input[name='loginid']", username, timeout=10000)
            await page.fill("input[name='loginpwd']", password, timeout=10000)
            await page.click("span:has-text('ログイン')", timeout=10000)
            await page.wait_for_load_state("networkidle", timeout=15000)
            print("✅ ログイン成功")

            # 新規登録ボタン
            print("\n📝 ステップ2: 登録フォームへ...")
            try:
                await page.click("a:has-text('新規登録')", timeout=5000)
            except:
                await page.click("button:has-text('新規登録')", timeout=5000)
            await page.wait_for_load_state("networkidle", timeout=10000)
            print(f"✅ ナビゲート完了: {page.url}")

            # スクリーンショット
            await page.screenshot(path=screenshot_dir / "01_form_page.png")
            print(f"📸 スクリーンショット保存: {screenshot_dir}/01_form_page.png")

            # フォーム要素を検査
            await inspect_form_elements(page)

            # ページ HTML を保存
            html = await page.content()
            with open(screenshot_dir / "form_page.html", "w", encoding="utf-8") as f:
                f.write(html)
            print(f"\n📄 HTML保存完了: form_page.html ({len(html)} bytes)")

            # 試しに最初の input に入力してみる
            print("\n🧪 ステップ3: 最初の input 要素に入力を試みる...")
            first_input = page.locator("input[type='text'], input:not([type]), input[type='number']").first
            try:
                await first_input.fill("テスト値", timeout=5000)
                value = await first_input.input_value()
                print(f"✅ 入力成功: '{value}'")
            except Exception as e:
                print(f"❌ 入力失敗: {e}")

            await page.screenshot(path=screenshot_dir / "02_after_input.png")

            # 成功メッセージの確認
            print("\n🔍 ステップ4: 成功メッセージを検索...")
            success_patterns = ["登録完了", "成功", "完了しました", "荷物情報を登録"]
            for pattern in success_patterns:
                try:
                    count = await page.locator(f"text='{pattern}'").count()
                    print(f"  '{pattern}': {count} 個")
                except:
                    print(f"  '{pattern}': エラー")

            # URL を確認
            print(f"\n📍 URL: {page.url}")
            print(f"   /baggage/register で終わるか: {page.url.endswith('/baggage/register')}")

            print("\n" + "="*80)
            print(f"✅ 検査完了: {screenshot_dir}")
            print("="*80)

        except Exception as e:
            print(f"\n❌ エラー: {e}")
            import traceback
            traceback.print_exc()
            try:
                await page.screenshot(path=screenshot_dir / "error.png")
            except:
                pass

        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(test_trabox_detailed())
