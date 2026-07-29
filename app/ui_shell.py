"""左サイドレール共通シェル（全ページ共通の外枠）。

各ページは body_html（.body の中身）を作って render_page(...) に渡すだけ。
- 左レール：[C]arroo ロゴ／ナビ（出す・見る追う）／設定・ユーザー・ログアウト
- 右：トップバー（ページ名・中央ツール・右アクション）＋ 作業面
- デザイントークン（墨レール＋紙面＋意味の緑/琥珀）、ライト/ダーク対応
"""
import html as _html

from app.tenancy import feature_enabled


def esc(value) -> str:
    """HTMLエスケープ。ユーザー入力を画面に埋め込む際は必ず通す（XSS対策）。

    None は空文字、その他は文字列化してから & < > " ' をエスケープする。
    """
    if value is None:
        return ""
    return _html.escape(str(value), quote=True)

# ---- SVG 定義（Cマーク＋ナビ line icons。currentColor 基準） ----
SVG_DEFS = """
<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>
 <g id="cmarkC"><path d="M70.9 27.9 A30 30 0 1 0 70.9 72.1" fill="none" stroke="var(--cream)" stroke-width="15.5" stroke-linecap="round"/><circle cx="70.9" cy="27.9" r="9.6" fill="var(--signal-br)"/></g>
 <g id="cmarkInk"><path d="M70.9 27.9 A30 30 0 1 0 70.9 72.1" fill="none" stroke="currentColor" stroke-width="15.5" stroke-linecap="round"/><circle cx="70.9" cy="27.9" r="9.6" fill="var(--signal-br)"/></g>
 <g id="i-dash" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="9" rx="1.4"/><rect x="14" y="3" width="7" height="5" rx="1.4"/><rect x="14" y="12" width="7" height="9" rx="1.4"/><rect x="3" y="16" width="7" height="5" rx="1.4"/></g>
 <g id="i-load" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2.7 20 7v10l-8 4.3L4 17V7z"/><path d="M4 7l8 4.3L20 7M12 11.3V21.3"/></g>
 <g id="i-truck" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 6h11v9H2z"/><path d="M13 9h4l4 3v3h-8z"/><circle cx="7" cy="18" r="2"/><circle cx="17.5" cy="18" r="2"/></g>
 <g id="i-repeat" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 9a7 7 0 0 1 12-3l2 2"/><path d="M20 15A7 7 0 0 1 8 18l-2-2"/><path d="M18 4v4h-4M6 20v-4h4"/></g>
 <g id="i-list" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M8 6h12M8 12h12M8 18h12M3.5 6h.01M3.5 12h.01M3.5 18h.01"/></g>
 <g id="i-gear" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/></g>
 <g id="i-users" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3.2"/><path d="M3 20a6 6 0 0 1 12 0M16 5.5a3 3 0 0 1 0 5.6M15 20a6 6 0 0 1 6-.2"/></g>
 <g id="i-out" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4h4a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-4M10 17l5-5-5-5M15 12H3"/></g>
 <g id="i-chev" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M15 5l-7 7 7 7"/></g>
 <g id="i-alert" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/></g>
 <g id="i-ops" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21h18M6 21V7l6-4 6 4v14"/><path d="M9 21v-4h6v4M9 10h.01M12 10h.01M15 10h.01M9 13h.01M12 13h.01M15 13h.01"/></g>
 <g id="i-card" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="5" width="20" height="14" rx="2.5"/><path d="M2 10h20"/></g>
</defs></svg>
"""

CSS = """
:root{
 --ink:#14171A;--paper:#F2F4F1;--surface:#FFFFFF;--raise:#FAFBF9;
 --line:#E2E5DF;--line-soft:#ECEEE8;--muted:#6E756F;--faint:#9AA19A;--ink-2:#333A36;
 --signal:#0FA36B;--signal-br:#1FBE83;--signal-wash:#E6F4EC;--signal-ink:#0B7D53;
 --amber:#C8892B;--amber-wash:#F6ECD9;--route:#C2C9C3;
 --rail:#15181C;--rail-2:#1B2024;--rail-line:#282E31;--rail-txt:#C7CEC8;--rail-txt-dim:#7E867F;--cream:#F4F2EC;
 --shadow:0 1px 2px rgba(20,23,26,.05),0 18px 46px -20px rgba(20,23,26,.22);
 --sans:-apple-system,BlinkMacSystemFont,"Hiragino Kaku Gothic ProN","Yu Gothic","Segoe UI",system-ui,sans-serif;
 --mono:ui-monospace,"SF Mono",Menlo,monospace;--r:14px;
}
/* ダークトークン（OS設定 と 明示 data-theme=dark の両方で同一を適用） */
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
 --ink:#E9ECE9;--paper:#0C0E10;--surface:#15181B;--raise:#1A1E21;
 --line:#282D2F;--line-soft:#20241F;--muted:#8A918B;--faint:#666C67;--ink-2:#C4CBC5;
 --signal:#22C58A;--signal-br:#33D398;--signal-wash:#13271F;--signal-ink:#7FE3BC;
 --amber:#E0B060;--amber-wash:#2A2416;--route:#39413C;
 --rail:#0E1113;--rail-2:#161A1D;--rail-line:#242A2D;--rail-txt:#C2C9C3;--rail-txt-dim:#727A74;
 --shadow:0 1px 2px rgba(0,0,0,.5),0 26px 64px -26px rgba(0,0,0,.75);
}}
:root[data-theme="dark"]{
 --ink:#E9ECE9;--paper:#0C0E10;--surface:#15181B;--raise:#1A1E21;
 --line:#282D2F;--line-soft:#20241F;--muted:#8A918B;--faint:#666C67;--ink-2:#C4CBC5;
 --signal:#22C58A;--signal-br:#33D398;--signal-wash:#13271F;--signal-ink:#7FE3BC;
 --amber:#E0B060;--amber-wash:#2A2416;--route:#39413C;
 --rail:#0E1113;--rail-2:#161A1D;--rail-line:#242A2D;--rail-txt:#C2C9C3;--rail-txt-dim:#727A74;
 --shadow:0 1px 2px rgba(0,0,0,.5),0 26px 64px -26px rgba(0,0,0,.75);
}
*{box-sizing:border-box}
html,body{margin:0;height:100%}
body{background:var(--paper);color:var(--ink);font-family:var(--sans);line-height:1.5;letter-spacing:-.006em;-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}
.num{font-variant-numeric:tabular-nums}.mono{font-family:var(--mono)}
.app{display:grid;grid-template-columns:236px 1fr;min-height:100vh}
@media(max-width:820px){.app{grid-template-columns:64px 1fr}.rail .lbl,.rail .logotype .rest,.rail .group,.rail .who div,.rail .nav .badge{display:none}}
/* 手動折り畳み（localStorage 記憶） */
.app.railcol{grid-template-columns:64px 1fr}
.app.railcol .rail .lbl,.app.railcol .rail .logotype .rest,.app.railcol .rail .group,.app.railcol .rail .who div,.app.railcol .rail .nav .badge{display:none}
.app.railcol .rail .top{flex-direction:column;align-items:flex-start;gap:12px}
.app.railcol .rail nav{overflow:visible}
.app.railcol .railtoggle svg{transform:rotate(180deg)}
/* 折り畳み時：アイコンホバーでラベルをポップ表示 */
.app.railcol .nav[data-tip]:hover::after{content:attr(data-tip);position:absolute;left:calc(100% + 10px);top:50%;transform:translateY(-50%);background:var(--rail-2);color:var(--cream);font-size:12.5px;font-weight:600;white-space:nowrap;padding:6px 10px;border-radius:8px;border:1px solid var(--rail-line);box-shadow:0 6px 20px -6px rgba(0,0,0,.5);z-index:40;pointer-events:none}
.app.railcol .nav[data-tip]:hover::before{content:"";position:absolute;left:calc(100% + 4px);top:50%;transform:translateY(-50%) rotate(45deg);width:8px;height:8px;background:var(--rail-2);border-left:1px solid var(--rail-line);border-bottom:1px solid var(--rail-line);z-index:40;pointer-events:none}
/* rail */
.rail{background:var(--rail);color:var(--rail-txt);display:flex;flex-direction:column;border-right:1px solid var(--rail-line);position:sticky;top:0;height:100vh}
.rail .top{padding:20px 18px 12px;display:flex;align-items:flex-start;justify-content:space-between;gap:8px}
.rail .top .railtoggle{align-self:center}
.railtoggle{background:transparent;border:0;color:var(--rail-txt-dim);cursor:pointer;padding:6px;border-radius:8px;display:inline-flex;line-height:0}
.railtoggle:hover{background:var(--rail-2);color:var(--rail-txt)}
.railtoggle svg{width:18px;height:18px;transition:transform .15s}
.logotype{display:inline-flex;align-items:center;font-weight:680;letter-spacing:-.05em;font-size:26px;color:var(--cream);line-height:1}
.logotype .logoC{height:.92em;width:auto;margin-right:.01em;transform:translateY(.055em)}
.rail nav{padding:6px 12px;display:flex;flex-direction:column;gap:2px;flex:1;overflow:auto}
.group{font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--rail-txt-dim);padding:16px 10px 6px;font-weight:650}
.nav{display:flex;align-items:center;gap:11px;padding:9px 10px;border-radius:10px;color:var(--rail-txt);font-size:14px;font-weight:500;position:relative}
.nav svg{width:19px;height:19px;flex:0 0 auto;opacity:.9}
.nav:hover{background:var(--rail-2)}
.nav.on{background:var(--rail-2);color:var(--cream);font-weight:600}
.nav.on::before{content:"";position:absolute;left:-12px;top:8px;bottom:8px;width:3px;border-radius:3px;background:var(--signal-br)}
.nav.on svg{opacity:1;color:var(--signal-br)}
.nav .badge{margin-left:auto;font-size:11px;font-weight:700;color:var(--signal-br);background:var(--signal-wash);padding:1px 7px;border-radius:999px}
.rail .foot{border-top:1px solid var(--rail-line);padding:12px}
.who{display:flex;align-items:center;gap:10px;padding:6px 8px;border-radius:10px;cursor:pointer;position:relative}
.who:hover{background:var(--rail-2)}
.ava{width:30px;height:30px;border-radius:8px;background:linear-gradient(150deg,#2b3237,#1a1f22);display:grid;place-items:center;color:var(--cream);font-size:12px;font-weight:700;flex:0 0 auto}
.who .nm{font-size:13px;color:var(--cream);font-weight:600}.who .rl{font-size:11px;color:var(--rail-txt-dim)}
/* content */
.content{min-width:0;display:flex;flex-direction:column}
.topbar{display:flex;align-items:center;gap:14px;padding:15px 24px;border-bottom:1px solid var(--line);background:var(--surface);position:sticky;top:0;z-index:5}
.topbar .crumb{font-size:12px;color:var(--faint)} .topbar h3{font-size:17px;margin:0;letter-spacing:-.02em}
.spacer{margin-left:auto}
.seg{display:flex;border:1px solid var(--line);border-radius:9px;overflow:hidden}
.seg a{font-size:12px;padding:6px 11px;color:var(--muted)} .seg a.on{background:var(--ink);color:var(--surface)}
.btn{border:0;border-radius:10px;background:var(--signal);color:#fff;font-weight:640;font-size:13px;padding:9px 15px;display:inline-flex;gap:7px;align-items:center;cursor:pointer}
.btn:hover{filter:brightness(1.05)}
.btn.ghost{background:transparent;color:var(--ink);border:1px solid var(--line)}
.btn.danger{background:transparent;color:#C9503E;border:1px solid var(--line)}
.body{padding:24px;max-width:1160px;width:100%}
/* common components */
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);box-shadow:var(--shadow)}
.hl{color:var(--muted);font-size:13px}
.chip{font-size:11.5px;font-weight:650;padding:4px 10px;border-radius:999px;display:inline-block}
.chip.live{color:var(--signal-ink);background:var(--signal-wash)}.chip.wait{color:var(--amber);background:var(--amber-wash)}
.chip.met{color:#fff;background:var(--signal)}.chip.off{color:var(--muted);background:var(--line-soft)}
label.fl{font-size:12px;color:var(--faint);display:block;margin-bottom:5px}
input,select,textarea{font-family:var(--sans);font-size:15px;color:var(--ink);background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:10px 12px;width:100%}
input:focus,select:focus,textarea:focus{outline:none;border-color:var(--signal);box-shadow:0 0 0 3px var(--signal-wash)}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th{text-align:left;color:var(--muted);font-weight:600;padding:11px 14px;background:var(--raise);border-bottom:1px solid var(--line-soft)}
td{padding:12px 14px;border-top:1px solid var(--line-soft)}
h1.pt{font-size:26px;margin:0 0 4px;letter-spacing:-.03em}
/* dashboard stats + route ledger */
.stats{display:grid;grid-template-columns:repeat(5,1fr);border:1px solid var(--line);border-radius:var(--r);overflow:hidden;background:var(--surface);margin-bottom:18px}
@media(max-width:760px){.stats{grid-template-columns:repeat(2,1fr)}}
.cell{padding:14px 16px;border-right:1px solid var(--line-soft);border-bottom:1px solid var(--line-soft)}
.cell .k{font-size:11.5px;color:var(--muted)} .cell .v{font-size:26px;font-weight:660;letter-spacing:-.03em;margin-top:2px}
.cell .v.sig{color:var(--signal)} .cell .v.amb{color:var(--amber)} .cell .k .sub{font-size:11px;color:var(--faint)}
.ledger{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);overflow:hidden}
.lhead{display:flex;align-items:center;justify-content:space-between;padding:14px 16px;border-bottom:1px solid var(--line-soft)}
.lhead .t{font-weight:620;font-size:14px}.lhead .a{font-size:12px;color:var(--signal-ink);font-weight:600}
.rrow{display:grid;grid-template-columns:150px 1fr 130px;gap:16px;align-items:center;padding:13px 16px;border-top:1px solid var(--line-soft)}
.rrow:first-child{border-top:0}
.place{font-size:13px;font-weight:560}.place small{display:block;color:var(--faint);font-weight:500;font-size:11px;margin-top:1px}
.track{position:relative;height:20px}
.track .base{position:absolute;top:50%;left:0;right:0;height:2px;background:var(--route);transform:translateY(-50%);border-radius:2px}
.track .fill{position:absolute;top:50%;left:0;height:2px;transform:translateY(-50%);border-radius:2px}
.track .o{position:absolute;top:50%;left:0;width:9px;height:9px;border-radius:50%;background:var(--ink);transform:translate(-50%,-50%)}
.track .d{position:absolute;top:50%;left:100%;width:9px;height:9px;border-radius:50%;border:2px solid var(--route);background:var(--surface);transform:translate(-50%,-50%)}
.track .d.met{border-color:var(--signal);background:var(--signal)}
.track .node{position:absolute;top:50%;width:8px;height:8px;border-radius:50%;background:var(--surface);border:2px solid var(--signal);transform:translate(-50%,-50%);box-shadow:0 0 0 4px var(--signal-wash)}
.perseg a{text-decoration:none}
/* 折りたたみヘルプ（開閉が分かる矢印＋アクセント色） */
.helpbox{border:1px solid var(--signal);background:var(--signal-wash);border-radius:12px;overflow:hidden;margin-bottom:16px}
.helpbox>summary{cursor:pointer;list-style:none;display:flex;align-items:center;gap:9px;
 padding:12px 15px;font-weight:650;font-size:13.5px;color:var(--signal-ink);user-select:none}
.helpbox>summary::-webkit-details-marker{display:none}
.helpbox>summary .chev{margin-left:auto;transition:transform .18s;flex:0 0 auto;color:var(--signal-ink)}
.helpbox[open]>summary .chev{transform:rotate(90deg)}
.helpbox[open]>summary{border-bottom:1px solid var(--signal)}
.helpbox>summary:hover{filter:brightness(.98)}
.helpbox .help-body{padding:12px 16px 14px;font-size:13px;color:var(--ink-2);line-height:1.7;background:var(--surface)}
.helpbox .help-body ul{margin:0;padding-left:18px}
.helpbox .help-body b{color:var(--ink)}
/* 送信ボタンのスピナー（押下即時フィードバック・二度押し防止） */
.spin{display:inline-block;width:14px;height:14px;border:2px solid rgba(255,255,255,.4);
 border-top-color:#fff;border-radius:50%;animation:spin .6s linear infinite;vertical-align:-2px;margin-right:7px}
@keyframes spin{to{transform:rotate(360deg)}}
button.is-busy,.is-busy{opacity:.9;cursor:progress}
@media(prefers-reduced-motion:reduce){.spin{animation:none}}
/* ==== 都道府県マルチ選択ピッカー（Trabox準拠） ==== */
.prefpick{position:relative}
.pp-box{display:flex;align-items:center;gap:6px;flex-wrap:wrap;min-height:42px;padding:7px 10px;
 border:1px solid var(--line);border-radius:10px;background:var(--surface);cursor:pointer}
.pp-box:focus{outline:none;border-color:var(--signal);box-shadow:0 0 0 3px var(--signal-wash)}
.pp-ph{color:var(--faint);font-size:14px}
.pp-chev{margin-left:auto;color:var(--faint);flex:0 0 auto}
.pp-chip{display:inline-flex;align-items:center;gap:5px;background:var(--signal-wash);color:var(--signal-ink);
 border:1px solid var(--line-soft);border-radius:8px;padding:3px 6px 3px 9px;font-size:12.5px;font-weight:600}
.pp-x{border:0;background:transparent;color:var(--signal-ink);cursor:pointer;font-size:14px;line-height:1;padding:0 2px}
.pp-x:hover{color:#C9503E}
.pp-pop{position:absolute;z-index:60;top:calc(100% + 6px);left:0;right:0;background:var(--surface);
 border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow);padding:14px;max-height:60vh;overflow:auto}
.pp-head{display:flex;gap:8px;align-items:center;margin-bottom:12px;flex-wrap:wrap}
.pp-head button{border:1px solid var(--line);background:var(--surface);color:var(--ink);border-radius:8px;
 padding:5px 12px;font-size:12.5px;font-weight:600;cursor:pointer}
.pp-head .pp-done{margin-left:auto;background:var(--signal);color:#fff;border-color:var(--signal)}
.pp-head button:hover{filter:brightness(1.04)}
.pp-grid{display:grid;gap:10px}
.pp-region{display:grid;grid-template-columns:110px 1fr;gap:10px;align-items:start;
 padding:8px 0;border-top:1px solid var(--line-soft)}
.pp-region:first-child{border-top:0}
.pp-reg{display:flex;align-items:center;gap:7px;font-size:13px;font-weight:600;color:var(--ink);cursor:pointer}
.pp-reg input{width:auto;margin:0}
.pp-prefs{display:flex;flex-wrap:wrap;gap:6px}
.pp-pref{border:1px solid var(--line);background:var(--surface);color:var(--ink);border-radius:8px;
 padding:5px 11px;font-size:13px;cursor:pointer;font-family:var(--sans)}
.pp-pref:hover{border-color:var(--signal);background:var(--raise)}
.pp-pref.on{background:var(--signal);border-color:var(--signal);color:#fff;font-weight:600}
@media(max-width:640px){.pp-region{grid-template-columns:1fr}}
/* ネイティブ日時入力(カレンダー/時計)をテーマに追従させる。
   これが無いとダーク時にピッカーアイコンが黒のまま暗背景に埋もれて見えない。 */
:root{color-scheme:light dark}
:root[data-theme="dark"]{color-scheme:dark}
:root[data-theme="light"]{color-scheme:light}
input[type="date"],input[type="time"],input[type="month"],input[type="datetime-local"]{color-scheme:inherit}
/* ==== 旧Tailwindフォーム橋渡し ====
   荷物/空車/定期登録など一部フォームはまだ Tailwind の固定グレー/ブルーで書かれており、
   ダークテーマだと「暗い背景に暗いグレー文字・浮いた白い箱」で読みにくくなる。
   ここでダーク時のみ、それらのクラスをアプリのトークンへ橋渡しする（フォーム側は無改修）。 */
@media (prefers-color-scheme:dark){
 :root:not([data-theme="light"]) .bg-white{background:var(--surface)}
 :root:not([data-theme="light"]) .bg-gray-50{background:var(--raise)}
 :root:not([data-theme="light"]) .bg-gray-100{background:var(--line-soft)}
 :root:not([data-theme="light"]) .bg-gray-200,:root:not([data-theme="light"]) .bg-gray-300{background:var(--line)}
 :root:not([data-theme="light"]) .bg-gray-400,:root:not([data-theme="light"]) .bg-gray-500{background:var(--faint);color:var(--paper)}
 :root:not([data-theme="light"]) .text-gray-900{color:var(--ink)}
 :root:not([data-theme="light"]) .text-gray-800,:root:not([data-theme="light"]) .text-gray-700{color:var(--ink-2)}
 :root:not([data-theme="light"]) .text-gray-600{color:var(--muted)}
 :root:not([data-theme="light"]) .text-gray-500,:root:not([data-theme="light"]) .text-gray-400{color:var(--faint)}
 :root:not([data-theme="light"]) .border-gray-100,:root:not([data-theme="light"]) .border-gray-200{border-color:var(--line-soft)}
 :root:not([data-theme="light"]) .border-gray-300{border-color:var(--line)}
 :root:not([data-theme="light"]) .shadow,:root:not([data-theme="light"]) .shadow-sm,:root:not([data-theme="light"]) .shadow-lg{box-shadow:var(--shadow)}
 :root:not([data-theme="light"]) .text-blue-600,:root:not([data-theme="light"]) .text-blue-700,:root:not([data-theme="light"]) .text-blue-800,:root:not([data-theme="light"]) .text-blue-900{color:var(--signal-ink)}
 :root:not([data-theme="light"]) .bg-blue-50{background:var(--signal-wash)}
 :root:not([data-theme="light"]) .border-blue-200{border-color:var(--line-soft)}
 :root:not([data-theme="light"]) .bg-blue-600{background:var(--signal)}
 :root:not([data-theme="light"]) .hover\\:bg-blue-700:hover{background:var(--signal-br)}
 :root:not([data-theme="light"]) .hover\\:bg-blue-50:hover{background:var(--signal-wash)}
 :root:not([data-theme="light"]) .hover\\:text-blue-600:hover{color:var(--signal-ink)}
}
:root[data-theme="dark"] .bg-white{background:var(--surface)}
:root[data-theme="dark"] .bg-gray-50{background:var(--raise)}
:root[data-theme="dark"] .bg-gray-100{background:var(--line-soft)}
:root[data-theme="dark"] .bg-gray-200,:root[data-theme="dark"] .bg-gray-300{background:var(--line)}
:root[data-theme="dark"] .bg-gray-400,:root[data-theme="dark"] .bg-gray-500{background:var(--faint);color:var(--paper)}
:root[data-theme="dark"] .text-gray-900{color:var(--ink)}
:root[data-theme="dark"] .text-gray-800,:root[data-theme="dark"] .text-gray-700{color:var(--ink-2)}
:root[data-theme="dark"] .text-gray-600{color:var(--muted)}
:root[data-theme="dark"] .text-gray-500,:root[data-theme="dark"] .text-gray-400{color:var(--faint)}
:root[data-theme="dark"] .border-gray-100,:root[data-theme="dark"] .border-gray-200{border-color:var(--line-soft)}
:root[data-theme="dark"] .border-gray-300{border-color:var(--line)}
:root[data-theme="dark"] .shadow,:root[data-theme="dark"] .shadow-sm,:root[data-theme="dark"] .shadow-lg{box-shadow:var(--shadow)}
:root[data-theme="dark"] .text-blue-600,:root[data-theme="dark"] .text-blue-700,:root[data-theme="dark"] .text-blue-800,:root[data-theme="dark"] .text-blue-900{color:var(--signal-ink)}
:root[data-theme="dark"] .bg-blue-50{background:var(--signal-wash)}
:root[data-theme="dark"] .border-blue-200{border-color:var(--line-soft)}
:root[data-theme="dark"] .bg-blue-600{background:var(--signal)}
:root[data-theme="dark"] .hover\\:bg-blue-700:hover{background:var(--signal-br)}
:root[data-theme="dark"] .hover\\:bg-blue-50:hover{background:var(--signal-wash)}
:root[data-theme="dark"] .hover\\:text-blue-600:hover{color:var(--signal-ink)}
"""


def _nav_item(active, key, href, icon, label, badge=None):
    on = " on" if active == key else ""
    b = f'<span class="badge">{badge}</span>' if badge else ""
    return (f'<a class="nav{on}" href="{href}" data-tip="{label}"><svg><use href="#{icon}"/></svg>'
            f'<span class="lbl">{label}</span>{b}</a>')


def _sidebar(active, user):
    is_admin = user.get("is_admin") if user else False
    uname = esc((user or {}).get("username", "") or "ゲスト")
    initial = esc(((user or {}).get("username", "") or "C")[0])
    is_super = bool(user and user.get("is_super"))
    home = "/ops/" if is_super else "/dashboard/"

    if is_super:
        # 運営者は運営機能のみ（荷物/空車を出す等のテナント業務は非表示）
        nav = f'{_nav_item(active,"ops","/ops/","i-ops","運営コンソール")}'
        foot_extra = ""
    else:
        recurring = (_nav_item(active, "schedules", "/schedules/", "i-repeat", "空車定期登録")
                     if feature_enabled("recurring", user) else "")
        users = (_nav_item(active, "users", "/admin/users", "i-users", "ユーザー管理")
                 if is_admin else "")
        billing_nav = (_nav_item(active, "billing", "/billing/", "i-card", "お支払い")
                       if (user and user.get("role") == "owner") else "")
        nav = f"""
    {_nav_item(active,"dashboard","/dashboard/","i-dash","ダッシュボード")}
    <div class="group">出す</div>
    {_nav_item(active,"load_new","/cases/register","i-load","荷物を出す")}
    {_nav_item(active,"truck_new","/trucks/register","i-truck","空車を出す")}
    <div class="group">見る・追う</div>
    {_nav_item(active,"load_list","/dashboard/cases","i-list","荷物一覧")}
    {_nav_item(active,"truck_list","/trucks/","i-truck","空車一覧")}
    {recurring}
    {_nav_item(active,"failed","/failed/","i-alert","失敗した投稿")}"""
        foot_extra = f"{billing_nav}{users}"

    return f"""<aside class="rail">
  <div class="top"><a class="logotype" href="{home}"><svg class="logoC" viewBox="12 12 69 77"><use href="#cmarkC"/></svg><span class="rest">arroo</span></a><button class="railtoggle" type="button" data-act="cRailToggle" aria-label="サイドバーを折り畳む"><svg><use href="#i-chev"/></svg></button></div>
  <nav>{nav}</nav>
  <div class="foot">
    {_nav_item(active,"settings","/settings/","i-gear","設定")}
    {foot_extra}
    <a class="nav" href="/auth/logout" data-tip="ログアウト"><svg><use href="#i-out"/></svg><span class="lbl">ログアウト</span></a>
    <a class="who" href="/auth/me" data-tip="アカウント"><span class="ava">{initial}</span><div><div class="nm">{uname}</div><div class="rl">アカウント設定</div></div></a>
  </div>
</aside>"""


SHELL_CLOSE = "</div></main></div></body></html>"


# ---- 未ログイン用ブランドページ（ホーム/ログイン）。本体と同じ意匠・ライト/ダーク対応 ----
_BRAND_CSS = """
*{box-sizing:border-box}html,body{margin:0;height:100%}
body{background:var(--paper);color:var(--ink);font-family:var(--sans);line-height:1.55;
 letter-spacing:-.006em;-webkit-font-smoothing:antialiased;
 background-image:radial-gradient(120% 90% at 50% -10%,var(--signal-wash) 0%,transparent 55%)}
.auth{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:32px 20px}
.auth-in{width:100%;max-width:396px}
.brand{display:flex;flex-direction:column;align-items:center;text-align:center;margin-bottom:26px}
.wordmark{display:inline-flex;align-items:center;font-weight:680;letter-spacing:-.05em;
 font-size:40px;line-height:1;color:var(--ink)}
.wordmark .wmC{height:.92em;width:auto;margin-right:.01em;transform:translateY(.055em)}
.tagline{color:var(--muted);font-size:13.5px;margin-top:10px}
.panel{background:var(--surface);border:1px solid var(--line);border-radius:18px;box-shadow:var(--shadow);padding:28px}
.panel h2{font-size:17px;margin:0 0 18px;letter-spacing:-.02em}
label.fl{display:block;font-size:12.5px;color:var(--faint);margin-bottom:6px;font-weight:600}
.field{margin-bottom:16px}
.auth input{width:100%;font-size:15px;color:var(--ink);background:var(--surface);
 border:1px solid var(--line);border-radius:11px;padding:11px 13px;font-family:var(--sans)}
.auth input:focus{outline:none;border-color:var(--signal);box-shadow:0 0 0 3px var(--signal-wash)}
.btn-primary{width:100%;border:0;border-radius:11px;background:var(--signal);color:#fff;font-weight:660;
 font-size:14.5px;padding:12px;cursor:pointer;margin-top:6px;transition:filter .12s}
.btn-primary:hover{filter:brightness(1.06)}
.btn-primary:focus-visible{outline:2px solid var(--signal-ink);outline-offset:2px}
.err{display:none;margin-bottom:16px;padding:11px 13px;border-radius:11px;font-size:13px;
 background:var(--amber-wash);color:var(--amber);border:1px solid var(--line-soft)}
.err.show{display:block}
.hint{text-align:center;color:var(--faint);font-size:12.5px;margin:18px 0 0}
.foot{text-align:center;color:var(--faint);font-size:11.5px;margin-top:22px;letter-spacing:.02em}
.linkbtn{display:block;text-align:center;border-radius:11px;background:var(--signal);color:#fff;
 font-weight:660;font-size:14.5px;padding:12px;margin-top:4px}
.linkbtn:hover{filter:brightness(1.06)}
"""


# ---- 公開ランディングページ（/）。ヒーロー/フッターは常に墨色（レールと同じ固定トーン）、
#      本文は通常トークンでテーマ追従。Do・Don't: レールは常に濃色固定、と同じ考え方を踏襲。 ----
LANDING_CSS = """
.mono{font-family:var(--mono)}.num{font-variant-numeric:tabular-nums}
.wrap{max-width:1080px;margin:0 auto;padding:0 24px}
.hero{background:var(--rail);color:var(--rail-txt);position:relative;overflow:hidden}
.hero::before{content:"";position:absolute;inset:0;background:radial-gradient(120% 70% at 15% 0%,rgba(31,190,131,.14) 0%,transparent 55%)}
.hero-in{position:relative;padding:96px 24px 84px;max-width:1080px;margin:0 auto}
.eyebrow{display:inline-flex;align-items:center;gap:8px;font-size:11.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--signal-br);font-weight:700;margin-bottom:26px}
.eyebrow .dot{width:6px;height:6px;border-radius:50%;background:var(--signal-br);box-shadow:0 0 0 3px rgba(31,190,131,.25)}
.hero h1{font-size:clamp(34px,5.4vw,64px);font-weight:700;letter-spacing:-.035em;line-height:1.12;margin:0 0 22px;color:var(--cream);max-width:15ch;text-wrap:balance}
.hero h1 b{color:var(--signal-br);font-weight:700}
.hero p.lede{font-size:17px;color:var(--rail-txt);max-width:46ch;margin:0 0 38px;line-height:1.75}
.cta-row{display:flex;gap:14px;flex-wrap:wrap;align-items:center;margin-bottom:64px}
.btn-p{background:var(--signal);color:#fff;font-weight:650;font-size:14.5px;padding:13px 26px;border-radius:11px;display:inline-flex;align-items:center;gap:8px;text-decoration:none;transition:filter .15s}
.btn-p:hover{filter:brightness(1.08)}
.btn-s{color:var(--cream);font-weight:600;font-size:14px;padding:13px 22px;border-radius:11px;border:1px solid var(--rail-line);text-decoration:none}
.btn-s:hover{background:var(--rail-2)}
.routecard{background:var(--rail-2);border:1px solid var(--rail-line);border-radius:16px;padding:22px 24px;max-width:560px}
.routecard .rhead{display:flex;justify-content:space-between;align-items:center;font-size:11.5px;color:var(--rail-txt-dim);margin-bottom:16px}
.routecard .rchip{font-size:11px;font-weight:700;padding:3px 10px;border-radius:999px;background:rgba(31,190,131,.16);color:var(--signal-br)}
.rtrack{position:relative;height:22px;margin:6px 0 14px}
.rtrack .base{position:absolute;top:50%;left:0;right:0;height:2px;background:var(--rail-line);transform:translateY(-50%)}
.rtrack .fill{position:absolute;top:50%;left:0;height:2px;background:var(--signal-br);transform:translateY(-50%);width:0;animation:fillRoute 2.2s .3s ease-out forwards}
.rtrack .o{position:absolute;top:50%;left:0;width:9px;height:9px;border-radius:50%;background:var(--cream);transform:translate(-50%,-50%)}
.rtrack .d{position:absolute;top:50%;left:100%;width:9px;height:9px;border-radius:50%;border:2px solid var(--rail-line);background:var(--rail-2);transform:translate(-50%,-50%);transition:all .4s .6s}
.rtrack.done .d{border-color:var(--signal-br);background:var(--signal-br)}
.rplaces{display:flex;justify-content:space-between;font-size:13px;color:var(--cream);font-weight:600}
.rplaces small{display:block;color:var(--rail-txt-dim);font-weight:500;font-size:11px;margin-top:2px}
.rmeta{display:flex;gap:18px;margin-top:16px;padding-top:16px;border-top:1px solid var(--rail-line);font-size:12px;color:var(--rail-txt-dim)}
.rmeta b{color:var(--cream);font-weight:650}
@keyframes fillRoute{to{width:100%}}
@media(prefers-reduced-motion:reduce){.rtrack .fill{animation:none;width:100%}}
.sec{padding:76px 0}
.sec-head{max-width:640px;margin:0 0 44px}
.k{font-size:11.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--signal-ink);font-weight:700;margin-bottom:12px}
.sec h2{font-size:clamp(24px,3vw,34px);letter-spacing:-.025em;margin:0 0 12px;text-wrap:balance}
.sec p.sub{color:var(--muted);font-size:15px;line-height:1.8;margin:0}
.feat-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--line);border:1px solid var(--line);border-radius:16px;overflow:hidden}
@media(max-width:860px){.feat-grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:600px){.feat-grid{grid-template-columns:1fr}}
.feat{background:var(--surface);padding:28px 26px}
.feat .ic{width:38px;height:38px;border-radius:10px;background:var(--signal-wash);color:var(--signal-ink);display:grid;place-items:center;margin-bottom:16px}
.feat h3{font-size:15.5px;margin:0 0 8px;letter-spacing:-.01em}
.feat p{font-size:13.5px;color:var(--muted);margin:0;line-height:1.7}
.feat.pro .ic{background:var(--amber-wash);color:var(--amber)}
.feat .tag{display:inline-block;margin-left:8px;font-size:9.5px;font-weight:700;letter-spacing:.05em;color:var(--amber);background:var(--amber-wash);padding:1px 7px;border-radius:999px;vertical-align:2px}
.origin{display:grid;grid-template-columns:1fr 1fr;gap:56px;align-items:start}
@media(max-width:800px){.origin{grid-template-columns:1fr}}
.origin blockquote{margin:0;font-size:20px;line-height:1.65;color:var(--ink);letter-spacing:-.01em;font-weight:500}
.origin .attr{margin-top:18px;font-size:12.5px;color:var(--faint)}
.origin ul{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:20px}
.origin li{display:flex;gap:14px}
.origin li .n{flex:0 0 auto;width:26px;height:26px;border-radius:8px;background:var(--raise);border:1px solid var(--line);color:var(--muted);font-size:11px;font-weight:700;display:grid;place-items:center;font-family:var(--mono)}
.origin li div{font-size:13.5px;color:var(--ink-2);line-height:1.7}
.origin li b{color:var(--ink)}
.flow{display:grid;grid-template-columns:repeat(3,1fr);gap:24px}
@media(max-width:760px){.flow{grid-template-columns:1fr}}
.flow .step{position:relative;padding-left:0}
.flow .num{font-family:var(--mono);font-size:12px;color:var(--faint);margin-bottom:10px;display:block}
.flow h3{font-size:16px;margin:0 0 8px}
.flow p{font-size:13.5px;color:var(--muted);margin:0;line-height:1.75}
.flow .arrow{display:none}
@media(min-width:761px){.flow .step:not(:last-child)::after{content:"";position:absolute;top:6px;right:-16px;width:12px;height:12px;border-top:1.5px solid var(--line);border-right:1.5px solid var(--line);transform:rotate(45deg)}}
.plans{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:700px){.plans{grid-template-columns:1fr}}
.plan{border:1px solid var(--line);border-radius:16px;background:var(--surface);padding:26px;box-shadow:var(--shadow)}
.plan.pro{border-color:var(--signal);box-shadow:0 0 0 3px var(--signal-wash)}
.plan .pname{font-size:12.5px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:var(--muted)}
.plan.pro .pname{color:var(--signal-ink)}
.plan .price{font-size:28px;font-weight:700;letter-spacing:-.02em;margin:8px 0 2px}
.plan .price small{font-size:13px;color:var(--faint);font-weight:500}
.plan .seat{font-size:12.5px;color:var(--muted);margin-bottom:16px}
.plan ul{list-style:none;margin:0;padding:0;font-size:13.5px}
.plan li{display:flex;gap:9px;padding:6px 0;color:var(--ink-2)}
.plan li b{color:var(--signal);flex:0 0 auto}
.plan .trial{display:inline-block;margin-top:16px;font-size:11.5px;color:var(--signal-ink);background:var(--signal-wash);padding:4px 10px;border-radius:999px;font-weight:650}
.cta-band{background:var(--rail);color:var(--cream);border-radius:20px;padding:56px 44px;text-align:center;position:relative;overflow:hidden}
.cta-band::before{content:"";position:absolute;inset:0;background:radial-gradient(90% 100% at 50% 0%,rgba(31,190,131,.14),transparent 60%)}
.cta-band .in{position:relative}
.cta-band h2{font-size:clamp(22px,3vw,30px);letter-spacing:-.02em;margin:0 0 12px}
.cta-band p{color:var(--rail-txt);font-size:14.5px;margin:0 0 26px}
footer.lp{background:var(--rail);color:var(--rail-txt-dim);padding:40px 24px;font-size:12.5px}
.foot-in{max-width:1080px;margin:0 auto;display:flex;justify-content:space-between;flex-wrap:wrap;gap:16px;align-items:center}
.foot-links{display:flex;gap:18px;flex-wrap:wrap}
.foot-links a{color:var(--rail-txt-dim);text-decoration:none}
.foot-links a:hover{color:var(--rail-txt)}
.foot-brand{display:inline-flex;align-items:center;font-weight:680;letter-spacing:-.05em;font-size:16px;color:var(--cream)}
.foot-brand svg{height:.9em;margin-right:2px;transform:translateY(.05em)}
"""

_LANDING_DEFS = """
<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>
 <g id="lp-cmark"><path d="M70.9 27.9 A30 30 0 1 0 70.9 72.1" fill="none" stroke="var(--cream)" stroke-width="15.5" stroke-linecap="round"/><circle cx="70.9" cy="27.9" r="9.6" fill="var(--signal-br)"/></g>
 <g id="ic-sync" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 9a7 7 0 0 1 12-3l2 2"/><path d="M20 15A7 7 0 0 1 8 18l-2-2"/><path d="M18 4v4h-4M6 20v-4h4"/></g>
 <g id="ic-repeat" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M17 2.1 21 6l-4 3.9M3 12a9 9 0 0 1 15-6.7L21 6M7 21.9 3 18l4-3.9M21 12a9 9 0 0 1-15 6.7L3 18"/></g>
 <g id="ic-calendar" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="16" rx="2.5"/><path d="M16 3v4M8 3v4M3 10h18"/></g>
 <g id="ic-alert" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/></g>
 <g id="ic-chart" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="M7 15l4-4 3 3 5-6"/></g>
 <g id="ic-history" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/><path d="M12 7v5l4 2"/></g>
</defs></svg>
"""

_LANDING_BODY = """
<section class="hero">
  <div class="hero-in">
    <div class="eyebrow"><span class="dot"></span>物流案件 一括投稿ソフトウェア</div>
    <h1>積む場所から卸す場所まで、<br><b>二度打ちしない。</b></h1>
    <p class="lede">積地・卸地・重量・車種・運賃を一度入力すれば、トラボックスとWebKitへ同時に投稿。空車情報も、定期便もまとめて自動化します。</p>
    <div class="cta-row">
      <a class="btn-p" href="/auth/login">ログインして始める<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg></a>
      <a class="btn-s" href="#features">できることを見る</a>
    </div>
    <div class="routecard">
      <div class="rhead"><span>案件 #1042</span><span class="rchip">掲載中</span></div>
      <div class="rplaces">
        <div>東京都港区<small>7/29 09:00 積</small></div>
        <div style="text-align:right">大阪府北区<small>7/30 09:00 卸</small></div>
      </div>
      <div class="rtrack" id="rtrack"><div class="base"></div><div class="fill"></div><span class="o"></span><span class="d"></span></div>
      <div class="rmeta">
        <div>投稿先 <b>トラボックス・WebKit</b></div>
        <div>担当 <b>竹内運送</b></div>
      </div>
    </div>
  </div>
</section>

<main class="wrap">
  <section class="sec" id="features">
    <div class="sec-head">
      <div class="k">できること</div>
      <h2>一括投稿から、失敗の見える化まで</h2>
      <p class="sub">投稿ボタンを押すところで終わらせない。定期化、複数日程、そして「投稿できていなかった」を放置しない仕組みまで一体で提供します。</p>
    </div>
    <div class="feat-grid">
      <div class="feat"><div class="ic"><svg width="19" height="19" viewBox="0 0 24 24"><use href="#ic-sync"/></svg></div>
        <h3>トラボックス・WebKit 一括投稿</h3><p>1つのフォームから両サービスへ同時に投稿。項目のマッピングと必須条件の違いはCarrooが吸収します。</p></div>
      <div class="feat pro"><div class="ic"><svg width="19" height="19" viewBox="0 0 24 24"><use href="#ic-repeat"/></svg></div>
        <h3>空車定期登録<span class="tag">PRO</span></h3><p>毎週・隔週・毎日・毎月のパターンで空車情報を自動投稿。祝日スキップや先行投稿日数も設定できます。</p></div>
      <div class="feat pro"><div class="ic"><svg width="19" height="19" viewBox="0 0 24 24"><use href="#ic-calendar"/></svg></div>
        <h3>複数日程一括登録<span class="tag">PRO</span></h3><p>日程が流動的な荷物を、最大5パターン同時投稿。1件成約したら残りをワンクリックで取り下げ。</p></div>
      <div class="feat"><div class="ic"><svg width="19" height="19" viewBox="0 0 24 24"><use href="#ic-alert"/></svg></div>
        <h3>失敗の見える化</h3><p>投稿が3回失敗すると本人にメール通知＋専用画面に表示。原因を直して、その場で再投稿できます。</p></div>
      <div class="feat"><div class="ic"><svg width="19" height="19" viewBox="0 0 24 24"><use href="#ic-chart"/></svg></div>
        <h3>成約トラッキング</h3><p>掲載中・成約・成約率をダッシュボードで常時把握。経路は線一本で、成約すると緑の点に変わります。</p></div>
      <div class="feat pro"><div class="ic"><svg width="19" height="19" viewBox="0 0 24 24"><use href="#ic-history"/></svg></div>
        <h3>履歴から再登録<span class="tag">PRO</span></h3><p>過去の案件・空車をワンクリックで呼び出し、日付だけ変えて再投稿。同じ経路の反復入力をなくします。</p></div>
    </div>
  </section>

  <section class="sec">
    <div class="sec-head"><div class="k">なぜ Carroo か</div><h2>現場の入力ミスと、二度打ちから生まれた</h2></div>
    <div class="origin">
      <div>
        <blockquote>「毎日同じ経路を、トラボックスとWebKitに別々に打ち込んでいた」——そこから始まったソフトウェアです。</blockquote>
        <div class="attr">竹内運送・自社の物流案件投稿業務より</div>
      </div>
      <ul>
        <li><div class="n">01</div><div><b>現場発の設計。</b>物流会社が自分たちの反復作業を解決するために作り、実際の投稿業務で検証を重ねています。</div></li>
        <li><div class="n">02</div><div><b>外部サイトの変化に強い。</b>トラボックス・WebKit側の画面変更やタイムアウトに耐えるよう、自動化を作り直し続けています。</div></li>
        <li><div class="n">03</div><div><b>失敗を握りつぶさない。</b>投稿できなかった案件は必ず本人に返る設計。「実は投稿されていなかった」を起こしません。</div></li>
        <li><div class="n">04</div><div><b>チームで使える。</b>会社単位の契約で、担当者ごとにアカウントを分けて運用できます。</div></li>
      </ul>
    </div>
  </section>

  <section class="sec">
    <div class="sec-head"><div class="k">つかいかた</div><h2>登録して、まかせる</h2></div>
    <div class="flow">
      <div class="step"><span class="num">01 / 登録</span><h3>案件・空車を入力</h3><p>積地・卸地・重量・車種などを一度入力。担当者情報は初期設定から自動で入ります。</p><div class="arrow"></div></div>
      <div class="step"><span class="num">02 / 自動投稿</span><h3>Carrooが同時に投稿</h3><p>トラボックス・WebKitへバックグラウンドで投稿。定期便や複数日程もこの時点で自動化されます。</p></div>
      <div class="step"><span class="num">03 / 結果通知</span><h3>成否をメールと画面で確認</h3><p>成功・失敗をダッシュボードと通知メールで確認。失敗はその場で再投稿できます。</p></div>
    </div>
  </section>

  <section class="sec">
    <div class="sec-head"><div class="k">料金</div><h2>会社単位の契約、7日間無料</h2><p class="sub">1人目のアカウント料は基本料に含みます。2人目以降は人数分の従量課金。カード決済のみ、いつでも解約できます。</p></div>
    <div class="plans">
      <div class="plan">
        <div class="pname">Standard</div>
        <div class="price">¥4,000<small> / 月</small></div>
        <div class="seat">＋ ユーザー追加 ¥2,000 / 人・月</div>
        <ul>
          <li><b>✓</b>トラボックス・WebKit 一括投稿</li>
          <li><b>✓</b>空車の単発登録</li>
          <li><b>✓</b>成約トラッキング・ダッシュボード</li>
          <li><b>✓</b>失敗の見える化・再投稿</li>
        </ul>
        <span class="trial">7日間無料トライアル</span>
      </div>
      <div class="plan pro">
        <div class="pname">Pro</div>
        <div class="price">¥5,000<small> / 月</small></div>
        <div class="seat">＋ ユーザー追加 ¥3,000 / 人・月</div>
        <ul>
          <li><b>✓</b>Standard の全機能</li>
          <li><b>✓</b>空車定期登録（自動化）</li>
          <li><b>✓</b>複数日程一括登録</li>
          <li><b>✓</b>履歴から再登録</li>
        </ul>
        <span class="trial">7日間無料トライアル</span>
      </div>
    </div>
  </section>

  <section class="sec" style="padding-top:0">
    <div class="cta-band">
      <div class="in">
        <h2>今日の入力を、最後の二度打ちに。</h2>
        <p>7日間は無料でお試しいただけます。カード登録は必要ですが、期間中はいつでも解約できます。</p>
        <a class="btn-p" href="/auth/login">ログインして始める</a>
      </div>
    </div>
  </section>
</main>

<footer class="lp">
  <div class="foot-in">
    <span class="foot-brand"><svg width="18" height="18" viewBox="12 12 69 77"><use href="#lp-cmark"/></svg>arroo</span>
    <div class="foot-links">
      <a href="/legal/tokushoho">特定商取引法に基づく表記</a>
      <a href="/legal/terms">利用規約</a>
      <a href="/legal/privacy">プライバシーポリシー</a>
      <a href="/auth/login">ログイン</a>
    </div>
    <div>© 2026 Carroo</div>
  </div>
</footer>
<script>
(function(){
  var t = document.getElementById('rtrack');
  if(t){ setTimeout(function(){ t.classList.add('done'); }, 900); }
})();
</script>
"""


def landing_page() -> str:
    """公開トップページ（/）。本体と同じデザイントークンを使った紹介ページ。
    ヒーロー/フッターは常に墨色固定（レールと同じ扱い）、本文はテーマ追従。"""
    return f"""<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Carroo — 物流案件を、二度打ちしない。</title>
<style>{CSS}</style><style>{LANDING_CSS}</style></head>
<body>{_LANDING_DEFS}{_LANDING_BODY}</body></html>"""


def brand_page(*, title, inner, user=None) -> str:
    """未ログインのブランドページ（ホーム・ログイン）の共通シェル。
    本体のデザイントークン＋統一Cマークで、ライト/ダークに追従する。"""
    _theme = (user or {}).get("theme") or "auto"
    _dt = f' data-theme="{_theme}"' if _theme in ("light", "dark") else ""
    return f"""<!DOCTYPE html><html lang="ja"{_dt}><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Carroo — {title}</title>
<style>{CSS}</style><style>{_BRAND_CSS}</style></head>
<body>{SVG_DEFS}
<div class="auth"><div class="auth-in">
  <div class="brand">
    <div class="wordmark"><svg class="wmC" viewBox="12 12 69 77"><use href="#cmarkInk"/></svg><span>arroo</span></div>
    <div class="tagline">物流案件を Trabox・WebKit へ一括投稿</div>
  </div>
  {inner}
  <div class="foot" style="display:flex;flex-direction:column;gap:8px;align-items:center">
    <div style="display:flex;gap:14px;flex-wrap:wrap;justify-content:center">
      <a href="/legal/tokushoho" style="color:var(--faint)">特定商取引法に基づく表記</a>
      <a href="/legal/terms" style="color:var(--faint)">利用規約</a>
      <a href="/legal/privacy" style="color:var(--faint)">プライバシーポリシー</a>
    </div>
    <div>© 2026 Carroo</div>
  </div>
</div></div>
</body></html>"""


def shell_open(*, title, active, user=None, page_title=None, crumb="Carroo",
               topbar_center="", topbar_actions="", extra_head="") -> str:
    """シェルの先頭〜 <div class="body"> 開きまでを返す（大きな既存テンプレの包み込み用）。"""
    pt = page_title or title
    # ユーザー別テーマ: auto はOS設定に追従、light/dark は data-theme で明示上書き
    _theme = (user or {}).get("theme") or "auto"
    _dt = f' data-theme="{_theme}"' if _theme in ("light", "dark") else ""
    return f"""<!DOCTYPE html><html lang="ja"{_dt}><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Carroo — {title}</title>
<link rel="stylesheet" href="/static/tailwind.css">
<style>{CSS}</style>{extra_head}</head>
<body>{SVG_DEFS}
<div class="app" id="capp"><script>if(localStorage.getItem('carroo_rail')==='1')document.getElementById('capp').classList.add('railcol');function cRailToggle(){{var a=document.getElementById('capp');a.classList.toggle('railcol');localStorage.setItem('carroo_rail',a.classList.contains('railcol')?'1':'0');}}</script>
  {_sidebar(active, user or {})}
  <main class="content">
    <div class="topbar">
      <div><div class="crumb">{crumb}</div><h3>{pt}</h3></div>
      <div class="spacer"></div>
      {topbar_center}
      {topbar_actions}
    </div>
    <div class="body">"""


def render_page(*, title, active, body, user=None,
                page_title=None, crumb="Carroo",
                topbar_center="", topbar_actions="", extra_head=""):
    """全ページ共通の左レール・シェルを返す。"""
    return (shell_open(title=title, active=active, user=user, page_title=page_title,
                       crumb=crumb, topbar_center=topbar_center,
                       topbar_actions=topbar_actions, extra_head=extra_head)
            + body + SHELL_CLOSE)
"""(以降の各ルーターは自前の <html> を捨て、body_html を作って render_page に渡す)"""
