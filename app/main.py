"""
FastAPI application entry point.

Run with:
    uvicorn app.main:app --reload

Environment variables:
    DATABASE_URL – PostgreSQL connection string
                   e.g. postgresql://user:password@host:5432/database
"""

import logging
import os
import warnings

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.routers import billing, clients, deals, expenses, managers, reports

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Финансовая система API",
    description="Backend API для Telegram Mini App учёта сделок (PostgreSQL)",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(managers.router)
app.include_router(clients.router)
app.include_router(deals.router)
app.include_router(billing.router)
app.include_router(expenses.router)
app.include_router(reports.router)

# Serve miniapp static files if the directory exists
_miniapp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "miniapp")
if os.path.isdir(_miniapp_dir):
    from fastapi.staticfiles import StaticFiles

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
