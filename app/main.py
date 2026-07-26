from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from app.routers import auth, cases, dashboard, notifications, settings, tasks, admin, trucks, schedules
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

# Content-Security-Policy（現行UI＝Tailwind CDN＋インラインscript/style/onclick 前提）
_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com; "
    "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
    "img-src 'self' data:; font-src 'self' data:; "
    "connect-src 'self'; "
    "object-src 'none'; base-uri 'self'; form-action 'self'; "
    "frame-ancestors 'none'"
)


@app.middleware("http")
async def security_headers_middleware(request, call_next):
    """全レスポンスに防御的セキュリティヘッダーを付与。

    - X-Frame-Options / frame-ancestors: クリックジャッキング防止
    - X-Content-Type-Options: MIMEスニッフィング防止
    - Referrer-Policy: リファラ漏洩の抑制
    - HSTS: 本番HTTPS(COOKIE_SECURE)時のみHTTPS強制
    - CSP: 現行UIを壊さない範囲で最大限厳格化。
        script は self＋Tailwind CDN のみ許可（外部スクリプト混入を遮断）。
        object/base-uri/form-action/frame-ancestors を封じ、外部への流出・クリック
        ジャッキング・base乗っ取りを防ぐ。connect/img/style は自ドメイン中心。
        ※ 完全strict化（script-src から 'unsafe-inline' 除去）は Tailwind セルフホスト＋
          onclick の addEventListener 化が前提のため将来対応。
    """
    response = await call_next(request)
    h = response.headers
    h.setdefault("X-Frame-Options", "DENY")
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    h.setdefault("Content-Security-Policy", _CSP)
    from app.config import settings as _st
    if _st.COOKIE_SECURE:
        h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """ブラウザが自動で叩く /favicon.ico に Route マーク(.ico 16/32/48)を返す。"""
    from fastapi.responses import FileResponse
    return FileResponse("static/icons/favicon.ico", media_type="image/x-icon")


# PWA（ホーム画面に追加してアプリとして起動可能に）用の head 注入内容
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
    '<script>if("serviceWorker"in navigator){navigator.serviceWorker.register("/static/sw.js").catch(function(){});}</script>'
)


@app.middleware("http")
async def pwa_head_middleware(request, call_next):
    """全HTMLページの <head> に PWA メタタグを一括注入（各画面を個別編集せず対応）

    これにより社用端末（Jamf配信）で「ホーム画面に追加」するとアプリとして
    フルスクリーン起動できる。
    """
    response = await call_next(request)
    try:
        ctype = response.headers.get("content-type", "")
        if "text/html" in ctype and hasattr(response, "body_iterator"):
            body = b"".join([chunk async for chunk in response.body_iterator])
            text = body.decode("utf-8", "ignore")
            if "</head>" in text and "manifest.json" not in text:
                text = text.replace("</head>", _PWA_HEAD + "</head>", 1)
            from starlette.responses import Response as _Resp
            new = _Resp(content=text, status_code=response.status_code,
                        media_type="text/html")
            # Set-Cookie 等のヘッダを引き継ぐ
            for k, v in response.headers.items():
                if k.lower() not in ("content-length", "content-type"):
                    new.headers[k] = v
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


app.include_router(auth.router)
app.include_router(cases.router)
app.include_router(dashboard.router)
app.include_router(notifications.router)
app.include_router(settings.router)
app.include_router(tasks.router)
app.include_router(admin.router)
app.include_router(trucks.router)
app.include_router(schedules.router)

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

@app.get("/", response_class=HTMLResponse)
async def read_root():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Carroo</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-50">
        <div class="min-h-screen flex items-center justify-center">
            <div class="bg-white p-8 rounded-lg shadow-md">
                <h1 class="text-3xl font-bold text-center mb-4">Carroo</h1>
                <p class="text-gray-600 text-center mb-6">物流案件一括一元投稿アプリ</p>
                <a href="/auth/login" class="block bg-blue-500 text-white py-2 px-4 rounded text-center hover:bg-blue-600">ログイン</a>
            </div>
        </div>
    </body>
    </html>
    """

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Carroo backend is running"}
