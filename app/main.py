from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from app.routers import auth, cases, dashboard, notifications, settings, tasks, admin, trucks, schedules, failed, ops, billing, legal
from app.db.database import init_db, get_db_connection
from app.utils.security import hash_password
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = FastAPI(
    title="Carroo",
    description="物流案件一括一元投稿アプリ",
    version="0.1.0"
)

app.mount("/static", StaticFiles(directory="static"), name="static")

def _csp(nonce: str) -> str:
    """厳格CSP。script は self＋当該nonceのみ（unsafe-inline/eval・外部CDN無し）。

    Tailwind はセルフホスト化済みのため script から CDN を排除。style は多数の
    インライン style 属性が現行UIの基盤のため 'unsafe-inline' を維持（業界標準の妥協。
    出力は全てHTMLエスケープ済みで、危険なのは script 実行のため script を strict 化）。
    """
    script = f"script-src 'self' 'nonce-{nonce}'" if nonce else "script-src 'self'"
    return (
        "default-src 'self'; "
        f"{script}; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; font-src 'self' data:; "
        "connect-src 'self'; "
        "object-src 'none'; base-uri 'self'; "
        # Stripe Checkout / Customer Portal への外部リダイレクトを許可（課金導線）
        "form-action 'self' https://checkout.stripe.com https://billing.stripe.com; "
        "frame-ancestors 'none'"
    )


@app.middleware("http")
async def security_headers_middleware(request, call_next):
    """防御的セキュリティヘッダー。CSP は HTML の場合 html_rewrite 側が nonce 付きで
    上書きするため、ここでは非HTML用の base CSP（nonce無し script-src 'self'）を置く。"""
    response = await call_next(request)
    h = response.headers
    h.setdefault("X-Frame-Options", "DENY")
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    h.setdefault("Content-Security-Policy", _csp(""))
    from app.config import settings as _st
    if _st.COOKIE_SECURE:
        h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """ブラウザが自動で叩く /favicon.ico に Route マーク(.ico 16/32/48)を返す。"""
    from fastapi.responses import FileResponse
    return FileResponse("static/icons/favicon.ico", media_type="image/x-icon")


# PWA（ホーム画面に追加してアプリとして起動可能に）用の head 注入内容。
# 末尾に「クリック委譲ディスパッチャ」を含む: strict CSP 下ではインライン onclick が
# 使えないため、data-act（関数名）+ data-args（JSON配列）で window 上の関数を呼ぶ。
_PWA_HEAD = (
    '<link rel="manifest" href="/static/manifest.json">'
    '<meta name="theme-color" content="#0FA36B">'
    '<meta name="apple-mobile-web-app-capable" content="yes">'
    '<meta name="mobile-web-app-capable" content="yes">'
    '<meta name="apple-mobile-web-app-status-bar-style" content="default">'
    '<meta name="apple-mobile-web-app-title" content="Carroo">'
    # ホーム画面(PWA/iOS)は Route マーク、ブラウザタブ(favicon)は視認性優先の C モノグラム
    '<link rel="apple-touch-icon" href="/static/icons/icon-180.png">'
    '<link rel="icon" type="image/x-icon" href="/favicon.ico" sizes="any">'
    '<link rel="icon" type="image/png" sizes="48x48" href="/static/icons/favicon-32.png">'
    '<script>if("serviceWorker"in navigator){navigator.serviceWorker.register("/static/sw.js").catch(function(){});}'
    'document.addEventListener("click",function(e){var el=e.target.closest("[data-act]");'
    'if(!el)return;var f=window[el.getAttribute("data-act")];if(typeof f!=="function")return;'
    'e.preventDefault();var a=[];try{a=JSON.parse(el.getAttribute("data-args")||"[]");}catch(_){}'
    'f.apply(null,a);});'
    # 送信ボタンの即時フィードバック（押した瞬間にスピナー＋無効化。二度押し防止）
    'window.__busy=function(b){if(!b||b.dataset.busy)return;b.dataset.busy="1";b.dataset.lbl=b.innerHTML;'
    'b.disabled=true;b.classList.add("is-busy");'
    'b.innerHTML=\'<span class="spin"></span>\'+(b.getAttribute("data-busy-text")||"処理中…");};'
    'window.__idle=function(b){if(!b||!b.dataset.busy)return;b.disabled=false;b.classList.remove("is-busy");'
    'b.innerHTML=b.dataset.lbl;delete b.dataset.busy;};'
    'document.addEventListener("submit",function(e){var f=e.target;if(!f||f.tagName!=="FORM")return;'
    'var b=f.querySelector(\'button[type=submit],input[type=submit],button:not([type])\');'
    'if(b){f.__busyBtn=b;window.__busy(b);}},true);</script>'
)


@app.middleware("http")
async def html_rewrite_middleware(request, call_next):
    """全HTMLに対して:
    1) <head> に PWA メタ＋クリック委譲ディスパッチャを注入（Jamf配信のPWA化）
    2) リクエストごとの nonce を全 <script> に付与し、CSP を nonce 付き strict で上書き
       （script-src から unsafe-inline/eval・外部CDN を排除。インライン script は
        nonce で許可、インライン onclick は data-act 方式へ移行済み）。
    """
    import secrets
    response = await call_next(request)
    try:
        ctype = response.headers.get("content-type", "")
        if "text/html" in ctype and hasattr(response, "body_iterator"):
            body = b"".join([chunk async for chunk in response.body_iterator])
            text = body.decode("utf-8", "ignore")
            if "</head>" in text and "manifest.json" not in text:
                text = text.replace("</head>", _PWA_HEAD + "</head>", 1)
            # 全 <script> に nonce を付与。属性付き(<script src= 等)を先に処理し、
            # その後で裸の <script> を処理する（順序を逆にすると nonce が二重付与される）。
            nonce = secrets.token_urlsafe(16)
            text = text.replace("<script ", f'<script nonce="{nonce}" ')
            text = text.replace("<script>", f'<script nonce="{nonce}">')
            from starlette.responses import Response as _Resp
            new = _Resp(content=text, status_code=response.status_code,
                        media_type="text/html")
            for k, v in response.headers.items():
                if k.lower() not in ("content-length", "content-type",
                                     "content-security-policy"):
                    new.headers[k] = v
            new.headers["Content-Security-Policy"] = _csp(nonce)
            return new
    except Exception:
        pass
    return response


@app.middleware("http")
async def sliding_session_middleware(request, call_next):
    """スライディングセッション: 有効なトークンでアクセスがあるたびに
    Cookie の有効期限を延長し直す。これにより「操作している限りログアウトされない」。
    token 内の remember フラグに応じて延長幅（通常8時間 / 保持30日）を切り替える。
    """
    response = await call_next(request)
    try:
        from app.utils.security import (
            decode_access_token, issue_access_token, set_auth_cookie,
        )
        token = request.cookies.get("access_token")
        if token:
            payload = decode_access_token(token)
            if payload and payload.get("user_id"):
                # ログアウト直後（Cookie削除レスポンス）は延長しない
                if "access_token=" not in response.headers.get("set-cookie", ""):
                    new_token, max_age = issue_access_token(
                        payload["user_id"], bool(payload.get("remember"))
                    )
                    set_auth_cookie(response, new_token, max_age)
    except Exception:
        pass  # セッション延長の失敗はリクエスト自体に影響させない
    return response


from fastapi import Request as _Req
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as _StarletteHTTPException
from app.errors import AppError, new_ref, format_detail, user_message


@app.exception_handler(AppError)
async def _app_error_handler(request: _Req, exc: AppError):
    """業務例外: やさしい説明＋コードを detail に埋め込んで返す。"""
    return JSONResponse(status_code=exc.status_code,
                        content={"detail": format_detail(exc.user_msg, exc.code),
                                 "code": exc.code})


@app.exception_handler(RequestValidationError)
async def _validation_handler(request: _Req, exc: RequestValidationError):
    """入力バリデーション失敗(422): 一般ユーザー向けに言い換え＋コード。"""
    return JSONResponse(status_code=422,
                        content={"detail": format_detail(user_message("E-VALIDATION"),
                                                         "E-VALIDATION"),
                                 "code": "E-VALIDATION"})


@app.exception_handler(_StarletteHTTPException)
async def _http_exception_handler(request: _Req, exc: _StarletteHTTPException):
    """401（未認証）はブラウザのページ遷移ならログイン画面へリダイレクトする。

    Jamf の Web Clip や直接URLアクセスで /dashboard/ 等を開いた際、Cookie が
    無い/失効していると get_current_user が 401 を投げるが、そのままだと
    {"detail":"Not authenticated"} という JSON が画面に出るだけで迷子になる。
    fetch/XHR からの 401（画面内の非同期呼び出し）はこれまで通り JSON のまま返す
    （JS 側が data.detail を見て処理するため）。
    """
    if exc.status_code == 401:
        accept = request.headers.get("accept", "")
        is_navigation = "text/html" in accept and request.headers.get(
            "sec-fetch-mode", "navigate") == "navigate"
        if is_navigation:
            from fastapi.responses import RedirectResponse
            next_path = request.url.path
            return RedirectResponse(
                url=f"/auth/login?next={next_path}", status_code=302)
    return JSONResponse(status_code=exc.status_code,
                        content={"detail": exc.detail},
                        headers=getattr(exc, "headers", None))


@app.exception_handler(Exception)
async def _unhandled_handler(request: _Req, exc: Exception):
    """未捕捉の例外(500): 参照IDを発行し、全文をログに残す（管理者が追える）。
    HTTPException はここに来ないので、業務の意図的な 4xx はそのまま通る。"""
    ref = new_ref()
    logging.getLogger("errors").exception(
        f"[E-SYS-500] ref={ref} path={request.url.path}")
    return JSONResponse(status_code=500,
                        content={"detail": format_detail(user_message("E-SYS-500"),
                                                         "E-SYS-500", ref),
                                 "code": "E-SYS-500", "ref": ref})


app.include_router(auth.router)
app.include_router(cases.router)
app.include_router(dashboard.router)
app.include_router(notifications.router)
app.include_router(settings.router)
app.include_router(tasks.router)
app.include_router(admin.router)
app.include_router(trucks.router)
app.include_router(schedules.router)
app.include_router(failed.router)
app.include_router(ops.router)
app.include_router(billing.router)
app.include_router(legal.router)

@app.on_event("startup")
async def startup_event():
    # フェイルセーフ: 本番(COOKIE_SECURE=True)でSECRET_KEYがデフォルトのままなら起動を止める。
    # （デフォルト鍵のままだと誰でもJWTを偽造でき、なりすましログインが可能になるため）
    from app.config import settings as _st
    if _st.COOKIE_SECURE and _st.SECRET_KEY == "your-secret-key-change-this-in-production":
        raise RuntimeError(
            "SECRET_KEY が本番でデフォルト値のままです。Secret Manager 等で必ず上書きしてください。")

    # データストアは Firestore。管理者アカウントが無ければ作成。
    from app.db import store
    try:
        store.ensure_seed_admin(hash_password)
    except Exception as e:
        logging.error(f"❌ 起動時の管理者シード確認エラー: {e}")
    # Stage 1（マルチテナント）移行を冪等に実施（挙動は変えない）
    try:
        from app.tenancy import current_tenant_id
        store.ensure_stage1(current_tenant_id())
    except Exception as e:
        logging.error(f"❌ 起動時の Stage1 移行エラー: {e}")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    from app.ui_shell import landing_page
    return landing_page()

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Carroo backend is running"}
