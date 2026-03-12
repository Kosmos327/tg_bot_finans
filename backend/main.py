"""
FastAPI application entry point for tg_bot_finans.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from backend.routers import auth, dashboard, deals, journal, settings

app = FastAPI(
    title="tg_bot_finans API",
    description="Role-based financial management system for Telegram Mini App",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# CORS (allow all in dev; restrict in production)
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(auth.router)
app.include_router(deals.router)
app.include_router(dashboard.router)
app.include_router(journal.router)
app.include_router(settings.router)

# ---------------------------------------------------------------------------
# Static files (Mini App)
# ---------------------------------------------------------------------------
miniapp_path = os.path.join(os.path.dirname(__file__), "..", "miniapp")
if os.path.isdir(miniapp_path):
    app.mount("/app", StaticFiles(directory=miniapp_path, html=True), name="miniapp")


@app.get("/health")
def health():
    return {"status": "ok"}
