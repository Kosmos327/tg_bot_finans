"""
FastAPI application entry point.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.routers import deals, settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

app = FastAPI(
    title="Финансовая система учёта сделок",
    description="Backend API for the Telegram Mini App financial deals tracker",
    version="1.0.0",
)

# CORS — allow Telegram Mini App origin. Wildcard is safe here because
# the Mini App endpoints either use Telegram initData validation or are
# read-only public data. Note: allow_credentials cannot be True with
# allow_origins=["*"] per the CORS spec; credentials are handled via
# the custom X-Init-Data header instead.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(deals.router)
app.include_router(settings.router)

# Serve the Mini App static files under /miniapp
app.mount("/miniapp", StaticFiles(directory="miniapp", html=True), name="miniapp")


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
