"""
Telegram bot entry point for tg_bot_finans.

Can be run standalone for development:
    python -m bot.main

In production, the bot is started automatically via FastAPI lifespan in
backend/main.py when running:
    uvicorn backend.main:app --host 0.0.0.0 --port 8000
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.handlers import router
from config.config import settings, validate_settings

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def main() -> None:
    validate_settings()

    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    logger.info("Bot started. Polling...")
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
