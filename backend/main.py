import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from backend.routers import deals, settings, auth, dashboard, journal
from config.config import validate_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Validate required environment variables at startup
validate_settings()

app = FastAPI(
    title="Финансовая система API",
    description="Backend API для Telegram Mini App учёта сделок",
    version="2.0.0",
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
app.include_router(dashboard.router)
app.include_router(journal.router)

# Serve miniapp static files if directory exists
_miniapp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "miniapp")
if os.path.isdir(_miniapp_dir):
    app.mount("/miniapp", StaticFiles(directory=_miniapp_dir, html=True), name="miniapp")


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}


@app.head("/health")
async def health_check_head() -> Response:
    return Response(status_code=200)


@app.get("/")
async def root() -> dict:
    return {"status": "ok"}


@app.head("/")
async def root_head() -> Response:
    return Response(status_code=200)
