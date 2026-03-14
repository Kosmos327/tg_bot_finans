import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from backend.routers import deals, settings, auth, dashboard, journal
from backend.routers import billing, expenses, reports, receivables
from config.config import settings as app_settings, validate_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Whether to start Telegram bot polling alongside the API server.
# Set RUN_BOT=true in the environment to enable polling.
# When RUN_BOT=false (default), only the FastAPI server runs — useful
# when a separate bot process handles polling, or to avoid conflict errors.
RUN_BOT: bool = os.getenv("RUN_BOT", "false").lower() == "true"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Optionally start Telegram bot polling alongside FastAPI."""
    # Validate required environment variables at startup (inside lifespan so
    # module import does not fail during build/test when env vars are absent).
    validate_settings()

    polling_task = None
    bot = None

    if RUN_BOT:
        from aiogram import Bot, Dispatcher
        from aiogram.fsm.storage.memory import MemoryStorage
        from aiogram.exceptions import TelegramConflictError

        try:
            from bot.handlers import router as bot_router

            bot = Bot(token=app_settings.telegram_bot_token)
            dp = Dispatcher(storage=MemoryStorage())
            dp.include_router(bot_router)

            polling_task = asyncio.create_task(
                dp.start_polling(bot, skip_updates=True)
            )
            app.state.bot_polling_task = polling_task
            logger.info("Telegram bot polling started")
        except TelegramConflictError as exc:
            logger.error(
                "TelegramConflictError: %s. "
                "Another bot instance is already running. "
                "Set RUN_BOT=false or stop the other instance.",
                exc,
            )
            polling_task = None
        except Exception as exc:
            logger.warning("Telegram bot polling NOT started: %s", exc)
            polling_task = None
    else:
        logger.info("RUN_BOT=false — Telegram bot polling is disabled")

    logger.info("FastAPI started")

    try:
        yield
    finally:
        if polling_task is not None:
            polling_task.cancel()
            try:
                await polling_task
            except BaseException:
                pass
        if bot is not None:
            try:
                await bot.session.close()
            except Exception:
                pass
        logger.info("FastAPI shutdown complete")


app = FastAPI(
    title="Финансовая система API",
    description="Backend API для Telegram Mini App учёта сделок",
    version="2.0.0",
    lifespan=lifespan,
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
app.include_router(billing.router)
app.include_router(expenses.router)
app.include_router(reports.router)
app.include_router(receivables.router)

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
