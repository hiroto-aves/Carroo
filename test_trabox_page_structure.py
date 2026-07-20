"""Trabox ダッシュボードのページ構造を確認"""
import asyncio
import os
from pathlib import Path
from playwright.async_api import async_playwright


async def inspect_dashboard():
    """ダッシュボードページの構造を確認"""

    username = os.getenv("TRABOX_TEST_USERNAME")
    password = os.getenv("TRABOX_TEST_PASSWORD")

    if not username or not password:
        print("❌ 環境変数設定が必要です")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        try:
            # ログイン
            print("🔐 ログイン中...")
            await page.goto("https://www.trabox.com/baggage/list/opened", timeout=30000)
            await page.fill("input[name='loginid']", username, timeout=10000)
            await page.fill("input[name='loginpwd']", password, timeout=10000)
            await page.click("span:has-text('ログイン')", timeout=10000)
            await page.wait_for_load_state("networkidle", timeout=15000)
            print(f"✅ ログイン完了: {page.url}")

            # ページ HTML を取得
            html = await page.content()

            # 保存
            output_file = Path("trabox_dashboard_html.html")
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"\n📄 HTML保存完了: {output_file} ({len(html)} bytes)")

            # キーワード検索
            print("\n🔍 ページ内のテキスト検索:")
            keywords = ["新規登録", "登録", "baggage", "register", "新規", "追加", "作成"]
            for keyword in keywords:
                if keyword in html:
                    # 含まれるキーワードの前後を表示
                    idx = html.find(keyword)
                    start = max(0, idx - 100)
                    end = min(len(html), idx + len(keyword) + 100)
                    print(f"\n  ✅ '{keyword}' が見つかりました")
                    print(f"     ...{html[start:end]}...")
                else:
                    print(f"  ❌ '{keyword}' は見つかりません")

            # ボタンとリンクを抽出
            print("\n📋 ボタン・リンク要素:")
            buttons = await page.locator("button, a[role='button'], input[type='button'], input[type='submit']").all()
            print(f"総数: {len(buttons)} 個\n")
            for i, btn in enumerate(buttons[:20]):
                try:
                    tag = await btn.evaluate("el => el.tagName")
                    text = await btn.text_content()
                    href = await btn.get_attribute("href")
                    onclick = await btn.get_attribute("onclick")
                    print(f"[{i}] <{tag}> text='{text.strip()}' href='{href}' onclick='{onclick}'")
                except Exception as e:
                    print(f"[{i}] エラー: {e}")

            # 画面にあるテキスト要素（h1, h2, p など）を確認
            print("\n📝 ページタイトル・見出し:")
            title = await page.title()
            print(f"  <title>: {title}")

            h1s = await page.locator("h1").all()
            for h1 in h1s[:5]:
                text = await h1.text_content()
                print(f"  <h1>: {text}")

            h2s = await page.locator("h2").all()
            for h2 in h2s[:5]:
                text = await h2.text_content()
                print(f"  <h2>: {text}")

            # iframe が存在するか確認
            iframes = await page.locator("iframe").all()
            print(f"\n📱 iframe: {len(iframes)} 個")
            for i, iframe in enumerate(iframes[:5]):
                src = await iframe.get_attribute("src")
                print(f"  [{i}] src='{src}'")

        except Exception as e:
            print(f"\n❌ エラー: {e}")
            import traceback
            traceback.print_exc()

        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(inspect_dashboard())
