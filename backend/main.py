import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from backend.routers import deals, settings, auth

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Финансовая система API",
    description="Backend API для Telegram Mini App учёта сделок",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(deals.router)
app.include_router(settings.router)
app.include_router(auth.router)

# Serve miniapp static files if directory exists
miniapp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "miniapp")
if os.path.isdir(miniapp_dir):
    app.mount("/miniapp", StaticFiles(directory=miniapp_dir, html=True), name="miniapp")


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok", "service": "tg_bot_finans"}


@app.get("/")
async def root() -> dict:
    return {"message": "Финансовая система API", "docs": "/docs"}
