"""法務ページ（特商法表記・利用規約・プライバシーポリシー）。

⚠️ いずれも【雛形】です。実際の事業者情報を記入し、公開前に必ず専門家
（弁護士・行政書士等）のレビューを受けてください。公開（ログイン不要）。
"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.ui_shell import CSS, _BRAND_CSS

router = APIRouter(prefix="/legal", tags=["legal"])

# 記入が必要な箇所は 〔 〕 で示す。公開前に実値へ置換すること。
_DRAFT_BANNER = (
    '<div class="draft">⚠️ これは<b>雛形</b>です。〔 〕内を実際の情報に置き換え、'
    '公開前に弁護士・行政書士等の専門家レビューを受けてください。</div>')


def _doc(title: str, inner: str) -> str:
    return f"""<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Carroo — {title}</title>
<style>{CSS}</style><style>{_BRAND_CSS}
.doc{{max-width:760px;margin:0 auto;padding:40px 22px 72px}}
.doc h1{{font-size:26px;letter-spacing:-.02em;margin:6px 0 4px}}
.doc .up{{font-size:12px;color:var(--faint)}}
.doc h2{{font-size:16px;margin:30px 0 8px;border-top:1px solid var(--line);padding-top:20px}}
.doc p,.doc li{{font-size:14px;color:var(--ink-2);line-height:1.85}}
.doc table{{width:100%;border-collapse:collapse;font-size:14px;margin:8px 0}}
.doc th,.doc td{{text-align:left;vertical-align:top;padding:10px 12px;border-bottom:1px solid var(--line-soft)}}
.doc th{{width:34%;color:var(--muted);font-weight:600;background:var(--raise)}}
.draft{{background:var(--amber-wash);border:1px solid var(--amber);color:var(--amber);border-radius:12px;padding:12px 15px;margin:0 0 22px;font-size:13px}}
.doc a.back{{color:var(--signal-ink);font-size:13px}}
.doc .foot{{margin-top:40px;padding-top:16px;border-top:1px solid var(--line);color:var(--faint);font-size:12px;display:flex;gap:16px;flex-wrap:wrap}}
</style></head><body>{{SVG}}
<div class="doc">
  <a class="back" href="/">← Carroo トップへ</a>
  {inner}
  <div class="foot">
    <a href="/legal/tokushoho">特定商取引法に基づく表記</a>
    <a href="/legal/terms">利用規約</a>
    <a href="/legal/privacy">プライバシーポリシー</a>
  </div>
</div></body></html>""".replace("{SVG}", "")


@router.get("/tokushoho", response_class=HTMLResponse)
async def tokushoho():
    inner = f"""
  <h1>特定商取引法に基づく表記</h1>
  <p class="up">最終改定日：〔YYYY年M月D日〕</p>
  {_DRAFT_BANNER}
  <table>
    <tr><th>販売事業者</th><td>〔事業者名 / 屋号〕</td></tr>
    <tr><th>運営統括責任者</th><td>〔氏名〕</td></tr>
    <tr><th>所在地</th><td>〔〒住所〕</td></tr>
    <tr><th>電話番号</th><td>〔電話番号〕（受付時間 〔平日10:00–17:00〕）</td></tr>
    <tr><th>メールアドレス</th><td>〔メール〕</td></tr>
    <tr><th>販売価格</th><td>各プランに表示（Standard：月額 ¥4,000＋追加ユーザー ¥2,000/人、Pro：月額 ¥5,000＋追加ユーザー ¥3,000/人）。<b>いずれも税別</b>。消費税は別途申し受けます。</td></tr>
    <tr><th>商品代金以外の必要料金</th><td>インターネット接続料金・通信料金等はお客様のご負担となります。</td></tr>
    <tr><th>お支払い方法</th><td>クレジットカード（決済代行：Stripe, Inc.）</td></tr>
    <tr><th>お支払い時期</th><td>お申込み時に無料トライアル（7日間）開始。トライアル終了後、毎月同日に自動課金。シート数変更時は日割りで次回請求に反映。</td></tr>
    <tr><th>役務の提供時期</th><td>お申込み手続き完了後、直ちにご利用いただけます。</td></tr>
    <tr><th>解約・返金について</th><td>「お支払い管理」画面よりいつでも解約できます。解約は当該請求期間の末日をもって効力を生じ、既にお支払い済みの料金の返金は行いません（日割り返金なし）。〔返金特約があれば記載〕</td></tr>
    <tr><th>動作環境</th><td>最新のブラウザ（Chrome/Safari/Edge 等）。</td></tr>
  </table>"""
    return HTMLResponse(_doc("特定商取引法に基づく表記", inner))


@router.get("/terms", response_class=HTMLResponse)
async def terms():
    inner = f"""
  <h1>利用規約</h1>
  <p class="up">最終改定日：〔YYYY年M月D日〕</p>
  {_DRAFT_BANNER}
  <p>本利用規約（以下「本規約」）は、〔事業者名〕（以下「当社」）が提供する物流案件一括投稿サービス「Carroo」（以下「本サービス」）の利用条件を定めるものです。</p>
  <h2>第1条（適用）</h2>
  <p>本規約は、利用者と当社との間の本サービスの利用に関わる一切の関係に適用されます。</p>
  <h2>第2条（利用登録）</h2>
  <p>本サービスは、会社（テナント）単位でご契約いただきます。会社管理者は、契約シート数の範囲で利用者アカウントを発行できます。</p>
  <h2>第3条（料金・支払い）</h2>
  <p>利用者は、当社が別途定めるプラン料金（基本料および契約シート数に応じた従量料金・いずれも税別）を、クレジットカードにて支払うものとします。無料トライアル期間は7日間とし、期間終了後は自動的に有料契約へ移行します。シート数の変更は、確認画面での承認後に反映され、日割りで請求されます。</p>
  <h2>第4条（禁止事項）</h2>
  <p>利用者は、法令違反、当社または第三者の権利侵害、外部サービス（トラボックス・WebKIT 等）の規約に反する行為、不正アクセス等を行ってはなりません。</p>
  <h2>第5条（外部サービス連携）</h2>
  <p>本サービスは外部の物流マッチングサービスへ投稿を代行します。外部サービスの仕様変更・障害・アカウント停止等に起因する不具合について、当社は責任を負いません。利用者は各外部サービスの利用規約を遵守するものとします。</p>
  <h2>第6条（解約）</h2>
  <p>利用者はいつでも解約できます。解約は当該請求期間の末日をもって効力を生じます。</p>
  <h2>第7条（免責事項）</h2>
  <p>当社は、本サービスの完全性・正確性・有用性等を保証せず、本サービスの利用により生じた損害について、当社の故意または重過失による場合を除き責任を負いません。〔損害賠償の上限額の定めがあれば記載〕</p>
  <h2>第8条（サービス内容の変更・停止）</h2>
  <p>当社は、利用者への事前通知のうえ、本サービスの内容を変更・停止できるものとします。</p>
  <h2>第9条（規約の変更）</h2>
  <p>当社は、必要と判断した場合、本規約を変更できます。変更後の規約は本サービス上に表示した時点で効力を生じます。</p>
  <h2>第10条（準拠法・裁判管轄）</h2>
  <p>本規約は日本法に準拠し、本サービスに関する紛争は〔管轄裁判所名〕を第一審の専属的合意管轄裁判所とします。</p>"""
    return HTMLResponse(_doc("利用規約", inner))


@router.get("/privacy", response_class=HTMLResponse)
async def privacy():
    inner = f"""
  <h1>プライバシーポリシー</h1>
  <p class="up">最終改定日：〔YYYY年M月D日〕</p>
  {_DRAFT_BANNER}
  <p>〔事業者名〕（以下「当社」）は、本サービスにおける個人情報の取扱いについて、以下のとおりプライバシーポリシーを定めます。</p>
  <h2>1. 取得する情報</h2>
  <p>氏名・会社名・メールアドレス・電話番号等の連絡先、ログイン情報、外部サービス（トラボックス／WebKIT）の認証情報、投稿する案件・空車の情報、操作ログ等。クレジットカード情報は当社では取得・保持せず、決済代行会社（Stripe, Inc.）が取り扱います。</p>
  <h2>2. 利用目的</h2>
  <p>本サービスの提供・投稿代行・本人確認・お問い合わせ対応・料金請求・不正利用の防止・サービス改善のため。</p>
  <h2>3. 第三者提供・委託</h2>
  <p>法令に基づく場合を除き、本人の同意なく第三者に提供しません。サービス提供に必要な範囲で、外部サービス（投稿先）および決済・クラウド基盤（Stripe／Google Cloud 等）へ情報を連携・委託することがあります。</p>
  <h2>4. 安全管理</h2>
  <p>認証情報は暗号化して保存し、通信は暗号化（HTTPS）します。アクセス制御・監査ログ等により適切に管理します。</p>
  <h2>5. 保管期間・開示・訂正・削除</h2>
  <p>利用目的の達成に必要な期間保管します。ご本人からの開示・訂正・利用停止・削除のご請求には、法令に従い対応します（お問い合わせ先：〔メール〕）。</p>
  <h2>6. Cookie 等</h2>
  <p>ログイン状態の維持等のため Cookie を使用します。</p>
  <h2>7. 改定</h2>
  <p>本ポリシーは必要に応じて改定します。改定後は本サービス上に表示した時点で効力を生じます。</p>
  <h2>8. お問い合わせ窓口</h2>
  <p>〔事業者名〕 個人情報保護管理者：〔氏名〕／〔メール〕</p>"""
    return HTMLResponse(_doc("プライバシーポリシー", inner))
