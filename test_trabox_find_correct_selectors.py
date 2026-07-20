"""Traboxの正しいセレクターを自動検出"""
import asyncio
import os
import json
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright


async def find_correct_selectors():
    """Trabox フォームの正しいセレクターを自動検出"""

    username = os.getenv("TRABOX_TEST_USERNAME")
    password = os.getenv("TRABOX_TEST_PASSWORD")

    if not username or not password:
        print("❌ 環境変数が設定されていません")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        try:
            # ログイン
            print("\n🔐 ログイン中...")
            await page.goto("https://www.trabox.com/baggage/list/opened", timeout=30000)
            await page.fill("input[name='loginid']", username, timeout=10000)
            await page.fill("input[name='loginpwd']", password, timeout=10000)
            await page.click("span:has-text('ログイン')", timeout=10000)
            await page.wait_for_load_state("networkidle", timeout=15000)
            print("✅ ログイン完了")

            # メニュークリック
            print("\n📝 登録フォームに移動中...")
            await page.click("[data-menu-id='baggageRegister']", timeout=5000)
            await page.wait_for_load_state("networkidle", timeout=15000)
            print(f"✅ URL: {page.url}")

            # テキスト入力可能な要素を探す
            print("\n" + "="*80)
            print("🔍 テキスト入力可能な要素を検查")
            print("="*80)

            # visible な input[type='text'], input[type='number'], textarea を探す
            text_inputs = await page.locator(
                "input[type='text'], input:not([type]), input[type='number'], input[type='email'], input[type='tel'], textarea"
            ).all()

            print(f"\n📝 テキスト入力可能な要素: {len(text_inputs)} 個\n")

            selector_info = []

            for i, elem in enumerate(text_inputs[:20]):
                try:
                    # 要素の情報を取得
                    tag = await elem.evaluate("el => el.tagName")
                    input_type = await elem.get_attribute("type")
                    placeholder = await elem.get_attribute("placeholder")
                    value = await elem.input_value()

                    # 親要素からラベルを探す
                    parent_text = await elem.evaluate("""
                        (el) => {
                            // 親 .ant-form-item を探す
                            let item = el.closest('.ant-form-item');
                            if (item) {
                                let label = item.querySelector('label');
                                if (label) return label.textContent.trim();
                            }
                            // または input の前後のテキストを探す
                            if (el.previousElementSibling) {
                                let text = el.previousElementSibling.textContent;
                                if (text) return text.trim();
                            }
                            return null;
                        }
                    """)

                    # クリック可能性をテスト
                    await elem.scroll_into_view_if_needed()
                    is_visible = await elem.is_visible()
                    is_enabled = await elem.is_enabled()

                    # セレクターを生成
                    class_attr = await elem.get_attribute("class")
                    data_attr = await elem.evaluate("el => el.getAttribute('data-testid') || el.getAttribute('data-test')")

                    selector_info.append({
                        "index": i,
                        "tag": tag,
                        "type": input_type,
                        "placeholder": placeholder,
                        "label": parent_text,
                        "visible": is_visible,
                        "enabled": is_enabled,
                        "class": class_attr,
                        "data_attr": data_attr,
                    })

                    print(f"[{i}] <{tag}> type='{input_type}'")
                    if placeholder:
                        print(f"     placeholder: {placeholder}")
                    if parent_text:
                        print(f"     label: {parent_text}")
                    print(f"     visible: {is_visible}, enabled: {is_enabled}")
                    print("")

                except Exception as e:
                    print(f"[{i}] エラー: {e}\n")

            # 結果をJSON保存
            output_file = Path("trabox_selectors_analysis.json")
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(selector_info, f, ensure_ascii=False, indent=2)
            print(f"\n💾 分析結果を保存: {output_file}")

            # ボタンを確認
            print("\n" + "="*80)
            print("🔘 ボタン要素を検査")
            print("="*80)

            buttons = await page.locator("button, input[type='submit'], input[type='button']").all()
            print(f"\n📌 ボタン: {len(buttons)} 個\n")

            for i, btn in enumerate(buttons[:15]):
                try:
                    text = await btn.text_content()
                    btn_type = await btn.get_attribute("type")
                    print(f"[{i}] type='{btn_type}' text='{text.strip()}'")
                except:
                    pass

            print("\n" + "="*80)
            print("✅ 検査完了")
            print("="*80)

        except Exception as e:
            print(f"\n❌ エラー: {e}")
            import traceback
            traceback.print_exc()

        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(find_correct_selectors())
