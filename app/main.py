from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from app.routers import auth, cases
from app.db.database import init_db
import os

app = FastAPI(
    title="OneLogi-Post",
    description="物流案件一括一元投稿アプリ",
    version="0.1.0"
)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router)
app.include_router(cases.router)

@app.on_event("startup")
async def startup_event():
    init_db()

@app.get("/", response_class=HTMLResponse)
async def read_root():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>OneLogi-Post</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-50">
        <div class="min-h-screen flex items-center justify-center">
            <div class="bg-white p-8 rounded-lg shadow-md">
                <h1 class="text-3xl font-bold text-center mb-4">OneLogi-Post</h1>
                <p class="text-gray-600 text-center mb-6">物流案件一括一元投稿アプリ</p>
                <a href="/auth/login" class="block bg-blue-500 text-white py-2 px-4 rounded text-center hover:bg-blue-600">ログイン</a>
            </div>
        </div>
    </body>
    </html>
    """

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "OneLogi-Post backend is running"}
