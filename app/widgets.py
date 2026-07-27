"""共通UIウィジェット。

pref_picker: Trabox準拠の都道府県マルチ選択（チップ表示＋ポップオーバー＋地域一括）。
値は従来と同じ「フルネームのカンマ区切り」を hidden input に入れるので、
バックエンド（_prefs で分解）は無変更で動く。表示ラベルは短縮名（岐阜 など）。
"""
from app.ui_shell import esc

# 地域 → 都道府県（フルネーム）。Trabox の地域区分に準拠。
REGIONS = [
    ("北海道", ["北海道"]),
    ("東北", ["青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県"]),
    ("北関東", ["茨城県", "栃木県", "群馬県"]),
    ("首都圏", ["埼玉県", "千葉県", "東京都", "神奈川県"]),
    ("甲信越", ["新潟県", "山梨県", "長野県"]),
    ("北陸", ["富山県", "石川県", "福井県"]),
    ("東海", ["岐阜県", "静岡県", "愛知県", "三重県"]),
    ("近畿", ["滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県"]),
    ("中国", ["鳥取県", "島根県", "岡山県", "広島県", "山口県"]),
    ("四国", ["徳島県", "香川県", "愛媛県", "高知県"]),
    ("九州・沖縄", ["福岡県", "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県"]),
]


def history_filter_form(action_url: str, q: str = "", date_from: str = "",
                        date_to: str = "", q_ph: str = "経路・ID など") -> str:
    """履歴ページ共通の絞り込みフォーム（キーワード＋期間）。GET 送信。"""
    return f"""
  <form method="get" action="{esc(action_url)}" class="card"
        style="padding:12px 14px;margin-bottom:14px;display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end">
    <div style="flex:1;min-width:200px"><label class="fl">キーワード（{esc(q_ph)}）</label>
      <input name="q" value="{esc(q)}" placeholder="例: 大阪 / 27532260"></div>
    <div style="width:150px"><label class="fl">期間（開始）</label>
      <input type="date" name="date_from" value="{esc(date_from)}"></div>
    <div style="width:150px"><label class="fl">期間（終了）</label>
      <input type="date" name="date_to" value="{esc(date_to)}"></div>
    <button class="btn" type="submit">絞り込み</button>
    <a class="btn ghost" href="{esc(action_url)}">クリア</a>
  </form>"""


def in_period(ymd: str, date_from: str, date_to: str) -> bool:
    """'YYYY-MM-DD...' 文字列の日付部が [date_from, date_to] に入るか（空は無制限）。"""
    day = (ymd or "")[:10]
    if not day:
        return not (date_from or date_to)
    if date_from and day < date_from:
        return False
    if date_to and day > date_to:
        return False
    return True


def event_chip(action: str, status: str) -> str:
    """履歴イベントの操作＋状態を色付きチップで表す（ui_shell の .chip を利用）。"""
    label = {"register": "登録", "update": "変更", "delete": "取下げ"}.get(action, action or "-")
    if status == "pending":
        return f'<span class="chip wait">{label}（処理中）</span>'
    if status == "error":
        return f'<span class="chip off">{label}（失敗）</span>'
    if action == "delete":
        return f'<span class="chip off">{label}</span>'
    return f'<span class="chip live">{label}</span>'


def short_name(pref: str) -> str:
    """表示用の短縮名（東京都→東京 / 北海道はそのまま / 和歌山県→和歌山）。"""
    if pref == "北海道":
        return pref
    return pref[:-1] if pref[-1] in "都道府県" else pref


def pref_picker(field: str, selected_csv: str = "", placeholder: str = "都道府県を選択") -> str:
    """1つ分のウィジェットHTML。field=hidden input の name（例: dest_able）。"""
    regions_html = ""
    for region, prefs in REGIONS:
        btns = "".join(
            f'<button type="button" class="pp-pref" data-pref="{esc(p)}">{esc(short_name(p))}</button>'
            for p in prefs)
        regions_html += (
            f'<div class="pp-region">'
            f'<label class="pp-reg"><input type="checkbox" class="pp-regck" data-region="{esc(region)}">'
            f'<span>{esc(region)}</span></label>'
            f'<div class="pp-prefs">{btns}</div></div>')
    return f"""
<div class="prefpick" data-field="{esc(field)}">
  <input type="hidden" name="{esc(field)}" value="{esc(selected_csv)}">
  <div class="pp-box" tabindex="0" role="button" aria-haspopup="true">
    <div class="pp-chips"></div>
    <span class="pp-ph">{esc(placeholder)}</span>
    <svg class="pp-chev" viewBox="0 0 24 24" width="16" height="16" fill="none"
         stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>
  </div>
  <div class="pp-pop" hidden>
    <div class="pp-head">
      <button type="button" class="pp-all">全国を選択</button>
      <button type="button" class="pp-none">すべて解除</button>
      <button type="button" class="pp-done">確定</button>
    </div>
    <div class="pp-grid">{regions_html}</div>
  </div>
</div>"""


# ページに一度だけ入れる初期化スクリプト（strict CSP: nonce はミドルウェアが自動付与）
PREF_PICKER_JS = """
<script>
(function(){
  function init(root){
    var hidden = root.querySelector('input[type=hidden]');
    var box = root.querySelector('.pp-box');
    var chips = root.querySelector('.pp-chips');
    var ph = root.querySelector('.pp-ph');
    var pop = root.querySelector('.pp-pop');
    var prefBtns = Array.prototype.slice.call(root.querySelectorAll('.pp-pref'));
    var regChecks = Array.prototype.slice.call(root.querySelectorAll('.pp-regck'));
    function labelOf(b){ return b.textContent; }
    function selected(){
      return hidden.value.split(',').map(function(s){return s.trim();}).filter(Boolean);
    }
    function setSelected(list){
      var uniq = []; list.forEach(function(v){ if(v && uniq.indexOf(v)<0) uniq.push(v); });
      hidden.value = uniq.join(',');
      render();
    }
    function render(){
      var sel = selected();
      // チップ
      chips.innerHTML = '';
      sel.forEach(function(v){
        var b = prefBtns.filter(function(x){return x.getAttribute('data-pref')===v;})[0];
        var lab = b ? labelOf(b) : v;
        var chip = document.createElement('span');
        chip.className = 'pp-chip';
        chip.innerHTML = '<span>'+lab+'</span>';
        var x = document.createElement('button');
        x.type='button'; x.className='pp-x'; x.textContent='×';
        x.addEventListener('click', function(e){ e.stopPropagation(); setSelected(sel.filter(function(s){return s!==v;})); });
        chip.appendChild(x); chips.appendChild(chip);
      });
      ph.style.display = sel.length ? 'none' : '';
      // ボタンの選択状態
      prefBtns.forEach(function(b){
        b.classList.toggle('on', sel.indexOf(b.getAttribute('data-pref'))>=0);
      });
      // 地域チェック（全選択/一部選択/未選択）
      regChecks.forEach(function(rc){
        var prefs = prefBtns.filter(function(b){ return b.parentNode===rc.closest('.pp-region').querySelector('.pp-prefs'); });
        var on = prefs.filter(function(b){ return sel.indexOf(b.getAttribute('data-pref'))>=0; }).length;
        rc.checked = on>0 && on===prefs.length;
        rc.indeterminate = on>0 && on<prefs.length;
      });
    }
    box.addEventListener('click', function(){ pop.hidden = !pop.hidden; });
    box.addEventListener('keydown', function(e){ if(e.key==='Enter'||e.key===' '){ e.preventDefault(); pop.hidden=!pop.hidden; } });
    prefBtns.forEach(function(b){
      b.addEventListener('click', function(){
        var v=b.getAttribute('data-pref'); var sel=selected();
        setSelected(sel.indexOf(v)>=0 ? sel.filter(function(s){return s!==v;}) : sel.concat([v]));
      });
    });
    regChecks.forEach(function(rc){
      rc.addEventListener('change', function(){
        var prefs = prefBtns.filter(function(b){ return b.parentNode===rc.closest('.pp-region').querySelector('.pp-prefs'); })
                            .map(function(b){return b.getAttribute('data-pref');});
        var sel=selected();
        if(rc.checked){ setSelected(sel.concat(prefs)); }
        else { setSelected(sel.filter(function(s){return prefs.indexOf(s)<0;})); }
      });
    });
    root.querySelector('.pp-all').addEventListener('click', function(){
      setSelected(prefBtns.map(function(b){return b.getAttribute('data-pref');}));
    });
    root.querySelector('.pp-none').addEventListener('click', function(){ setSelected([]); });
    root.querySelector('.pp-done').addEventListener('click', function(){ pop.hidden=true; });
    document.addEventListener('click', function(e){ if(!root.contains(e.target)) pop.hidden=true; });
    root.addEventListener('pprefresh', render);  // 外部から hidden 値を差し替えた後の再描画用
    render();
  }
  document.querySelectorAll('.prefpick').forEach(init);
})();
</script>"""


# 履歴から再登録：window.__prefill を読み、登録フォームの各項目に値を流し込む共通JS。
# 都道府県→市区町村の非同期セレクトと、都道府県マルチ選択(pref_picker)にも対応。
PREFILL_JS = """
<script>
(function(){
  var pf=window.__prefill; if(!pf) return;
  var form=document.getElementById('f')||document.querySelector('form'); if(!form) return;
  var cityPairs=[['vacant_pref','vacant_city'],['dest_pref','dest_city'],['pick_pref','pick_city'],['drop_pref','drop_city']];
  var cityNames=cityPairs.map(function(p){return p[1];});
  function setSimple(name,val){ if(val==null)return; var el=form.querySelector('[name="'+name+'"]'); if(!el)return;
    if(el.type==='checkbox'){ el.checked=(val===true||val==='yes'||val==='1'); } else { el.value=val; } }
  Object.keys(pf).forEach(function(k){ if(cityNames.indexOf(k)<0 && k!=='dest_able' && k!=='vacant_able') setSimple(k,pf[k]); });
  cityPairs.forEach(function(p){
    var ps=form.querySelector('[name="'+p[0]+'"]'); if(!ps||pf[p[0]]==null) return;
    ps.value=pf[p[0]]; ps.dispatchEvent(new Event('change'));
    var want=pf[p[1]]; if(want==null) return; var tries=0;
    var iv=setInterval(function(){ var cs=document.getElementById(p[1])||form.querySelector('[name="'+p[1]+'"]');
      if(cs){ if(cs.tagName==='SELECT'){ if(cs.options.length>1){ cs.value=want; clearInterval(iv);} } else { cs.value=want; clearInterval(iv);} }
      if(++tries>50) clearInterval(iv); },100); });
  ['dest_able','vacant_able'].forEach(function(name){
    if(pf[name]==null) return; var h=form.querySelector('input[type=hidden][name="'+name+'"]'); if(!h) return;
    h.value=pf[name]; var root=h.closest('.prefpick'); if(root) root.dispatchEvent(new Event('pprefresh')); });
})();
</script>"""
