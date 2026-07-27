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
 <g id="i-dash" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="9" rx="1.4"/><rect x="14" y="3" width="7" height="5" rx="1.4"/><rect x="14" y="12" width="7" height="9" rx="1.4"/><rect x="3" y="16" width="7" height="5" rx="1.4"/></g>
 <g id="i-load" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2.7 20 7v10l-8 4.3L4 17V7z"/><path d="M4 7l8 4.3L20 7M12 11.3V21.3"/></g>
 <g id="i-truck" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 6h11v9H2z"/><path d="M13 9h4l4 3v3h-8z"/><circle cx="7" cy="18" r="2"/><circle cx="17.5" cy="18" r="2"/></g>
 <g id="i-repeat" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 9a7 7 0 0 1 12-3l2 2"/><path d="M20 15A7 7 0 0 1 8 18l-2-2"/><path d="M18 4v4h-4M6 20v-4h4"/></g>
 <g id="i-list" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M8 6h12M8 12h12M8 18h12M3.5 6h.01M3.5 12h.01M3.5 18h.01"/></g>
 <g id="i-gear" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/></g>
 <g id="i-users" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3.2"/><path d="M3 20a6 6 0 0 1 12 0M16 5.5a3 3 0 0 1 0 5.6M15 20a6 6 0 0 1 6-.2"/></g>
 <g id="i-out" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4h4a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-4M10 17l5-5-5-5M15 12H3"/></g>
 <g id="i-chev" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M15 5l-7 7 7 7"/></g>
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
.who{display:flex;align-items:center;gap:10px;padding:6px 8px;border-radius:10px}
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
    recurring = (_nav_item(active, "schedules", "/schedules/", "i-repeat", "空車定期登録")
                 if feature_enabled("recurring") else "")
    users = (_nav_item(active, "users", "/admin/users", "i-users", "ユーザー管理")
             if is_admin else "")
    return f"""<aside class="rail">
  <div class="top"><a class="logotype" href="/dashboard/"><svg class="logoC" viewBox="12 12 69 77"><use href="#cmarkC"/></svg><span class="rest">arroo</span></a><button class="railtoggle" type="button" data-act="cRailToggle" aria-label="サイドバーを折り畳む"><svg><use href="#i-chev"/></svg></button></div>
  <nav>
    {_nav_item(active,"dashboard","/dashboard/","i-dash","ダッシュボード")}
    <div class="group">出す</div>
    {_nav_item(active,"load_new","/cases/register","i-load","荷物を出す")}
    {_nav_item(active,"truck_new","/trucks/register","i-truck","空車を出す")}
    <div class="group">見る・追う</div>
    {_nav_item(active,"load_list","/dashboard/cases","i-list","荷物一覧")}
    {_nav_item(active,"truck_list","/trucks/","i-truck","空車一覧")}
    {recurring}
  </nav>
  <div class="foot">
    {_nav_item(active,"settings","/settings/","i-gear","設定")}
    {users}
    <a class="nav" href="/auth/logout" data-tip="ログアウト"><svg><use href="#i-out"/></svg><span class="lbl">ログアウト</span></a>
    <div class="who"><span class="ava">{initial}</span><div><div class="nm">{uname}</div><div class="rl">Carroo</div></div></div>
  </div>
</aside>"""


SHELL_CLOSE = "</div></main></div></body></html>"


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
